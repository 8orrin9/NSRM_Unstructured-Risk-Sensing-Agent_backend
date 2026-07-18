"""
Recommendation Service - 추천 키워드/태그 전역 집계

서빙 계층에서 서빙 DB(news_intelligence.db) 전체를 1회 집계하여
추천 키워드/추천 태그 집합을 산출하고 프로세스 수명 동안 캐시한다.
news_service._build_news_item 이 각 뉴스에 교집합을 주입한다.

읽기 전용: DB에 쓰지 않는다. 서빙 DB가 정적이므로 프로세스 수명 캐시로 충분하며,
운영에서 DB가 갱신되면 프로세스 재기동이 필요하다.

파이프라인 노드(recommend_keywords.py)는 서빙 DB에 존재하지 않는 테이블
(NEWS_KEYWORD_EXTRACTION 등)을 쿼리하는 버그가 있어 산출물이 비어 있다.
여기서는 실제 서빙 테이블(AGENT1_KEYWORD, AGENT2_DOC, AGENT4_RISK_EVAL 등)로 재구현한다.

[운영 배포 주의] monorepo 원본은 agents/ 유틸 2개를 import 하지만, 운영 백엔드는
서빙 축소본이라 agents/ 가 없다. 따라서 아래 두 함수를 이 파일 안에 복제(자립화)한다:
  - _string_similarity      ← agents/utils/textrank.py
  - load_existing_keywords  ← agents/Agent_4_Risk_Evaluator/nodes/recommend_keywords.py
엑셀 경로 등 상수는 backend/config.py (RECO_KEYWORD_SET_*) 에서 주입받는다.
"""
import sys
import json
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Set

import openpyxl

# backend/ 를 sys.path에 추가 (main.py와 동일 관례)
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    SERVED_RUN_IDS,
    RECO_KEYWORD_THRESHOLD,
    RECO_TAG_THRESHOLD,
    RECO_TAG_DUP_SIMILARITY,
    RECO_ABSTRACT_KEYWORD_BLACKLIST,
    RECO_KEYWORD_SET_EXCEL_PATH,
    RECO_KEYWORD_SET_SHEET_NAME,
    RECO_KEYWORD_COLUMN_INDEX,
    RECO_TARGET_REGION_COLUMN_INDEX,
    RECO_TARGET_REGION,
)
from database.connection import get_news_db


# run_id IN (?, ?) 플레이스홀더
_RUN_PH = ",".join("?" * len(SERVED_RUN_IDS))


# ─── agents/ 자립화 복제 (서빙 축소본엔 agents/ 없음) ──────────────────────────

def _string_similarity(s1: str, s2: str) -> float:
    """두 문자열의 Jaccard similarity. (원본: agents/utils/textrank.py)

    한 문자열이 다른 문자열에 포함되면 1.0, 아니면 문자 집합 기반 Jaccard.
    """
    if s1 in s2 or s2 in s1:
        return 1.0
    set1 = set(s1)
    set2 = set(s2)
    union = len(set1 | set2)
    if union == 0:
        return 0.0
    return len(set1 & set2) / union


def load_existing_keywords() -> Set[str]:
    """기존 뉴스 수집용 키워드셋(KR) 로드.

    원본: agents/Agent_4_Risk_Evaluator/nodes/recommend_keywords.py:load_existing_keywords.
    엑셀 경로/시트/열 인덱스는 config(RECO_KEYWORD_SET_*)에서 주입.
    """
    try:
        wb = openpyxl.load_workbook(RECO_KEYWORD_SET_EXCEL_PATH)
        ws = wb[RECO_KEYWORD_SET_SHEET_NAME]

        existing_keywords: Set[str] = set()

        # 2번째 행부터 읽기 (1행은 헤더)
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < max(RECO_KEYWORD_COLUMN_INDEX, RECO_TARGET_REGION_COLUMN_INDEX):
                continue

            target_region = row[RECO_TARGET_REGION_COLUMN_INDEX - 1]  # 0-based
            keyword_raw = row[RECO_KEYWORD_COLUMN_INDEX - 1]

            if target_region != RECO_TARGET_REGION:
                continue
            if not keyword_raw:
                continue

            # keyword 컬럼은 JSON 배열 형식 (예: '["ECCN", "ECCN 반도체"]')
            try:
                keywords = json.loads(keyword_raw)
                if isinstance(keywords, list):
                    existing_keywords.update(keywords)
            except (json.JSONDecodeError, TypeError):
                existing_keywords.add(str(keyword_raw).strip())

        wb.close()
        print(f"[INFO] 기존 키워드 {len(existing_keywords)}개 로드 완료")
        return existing_keywords

    except FileNotFoundError:
        print(f"[ERROR] Excel 파일을 찾을 수 없습니다: {RECO_KEYWORD_SET_EXCEL_PATH}")
        return set()
    except Exception as e:
        print(f"[ERROR] Excel 로드 실패: {e}")
        return set()


def normalize_keyword(keyword: str) -> str:
    """키워드 정규화 (소문자, 공백 제거).

    models/news_intelligence_db.py:442 와 동일 로직. 루트 models 패키지가
    backend/models 와 이름 충돌하여 직접 import 할 수 없으므로 복제한다.
    """
    return keyword.lower().replace(" ", "").replace("　", "")


@dataclass(frozen=True)
class RecommendationIndex:
    """전역 추천 집계 결과."""
    recommended_keywords: Set[str]            # 추천 키워드 (원문 표기)
    recommended_tags: Dict[str, str]          # normalized -> 대표 라벨(원문)


# ─── 기존 자산 로드 ────────────────────────────────────────────────────────────

def load_existing_keyword_pool() -> Set[str]:
    """뉴스 수집용 키워드 Pool (기존 키워드셋, KR). Agent_4 로직 재사용."""
    return load_existing_keywords()


def load_existing_tag_names(cursor) -> Set[str]:
    """기존 활용 태그 이름 집합 (normalized).

    TAG_MASTER.name(마스터) + AGENT2_TAG.tag_name(실제 매핑에 쓰인 태그) 합집합.
    """
    names: Set[str] = set()
    cursor.execute("SELECT name FROM TAG_MASTER WHERE name IS NOT NULL")
    for (name,) in cursor.fetchall():
        names.add(normalize_keyword(name))
    cursor.execute("SELECT DISTINCT tag_name FROM AGENT2_TAG WHERE tag_name IS NOT NULL")
    for (name,) in cursor.fetchall():
        names.add(normalize_keyword(name))
    return names


def load_existing_event_tag_names(cursor) -> Set[str]:
    """기존 EVENT 태그 이름 집합 (원문). 유사도 중복 판정용."""
    cursor.execute("SELECT name FROM TAG_MASTER WHERE tag_type = 'EVENT' AND name IS NOT NULL")
    return {row[0] for row in cursor.fetchall()}


def load_existing_event_keywords(cursor) -> Set[str]:
    """기존 EVENT 태그에 매핑된 키워드 집합 (normalized)."""
    cursor.execute("""
        SELECT DISTINCT k.keyword
        FROM TAG_KEYWORD_MAP k
        JOIN TAG_MASTER t ON k.tag_id = t.tag_id AND k.target_region = t.target_region
        WHERE t.tag_type = 'EVENT' AND k.keyword IS NOT NULL
    """)
    return {normalize_keyword(row[0]) for row in cursor.fetchall()}


# ─── Risk 뉴스 집합 ────────────────────────────────────────────────────────────

def _risk_news_ids(cursor) -> Set[str]:
    """추천 집계 대상 Risk 뉴스 집합.

    서빙 대상 run 중 is_risk=1 인 개별 평가(is_grouped=0 아님, 그룹 평가도 포함하여
    코퍼스 전역 신호를 넓게 잡는다). recommend_keywords.py 원 로직의 is_risk=1 기준을 따른다.
    """
    cursor.execute(f"""
        SELECT DISTINCT news_id
        FROM AGENT4_RISK_EVAL
        WHERE run_id IN ({_RUN_PH}) AND is_risk = 1
    """, tuple(SERVED_RUN_IDS))
    return {row[0] for row in cursor.fetchall()}


# ─── 집계 ──────────────────────────────────────────────────────────────────────

def compute_recommended_keywords(cursor, risk_ids: Set[str]) -> Set[str]:
    """Risk 뉴스에서 추출된 키워드 중 추천 키워드 집합.

    (a) 기존 키워드 Pool에 없고 (raw 비교, recommend_keywords.py:232 와 동일)
    (b) 뉴스 단위 dedup 후 등장 뉴스 수 >= RECO_KEYWORD_THRESHOLD.
    """
    if not risk_ids:
        return set()

    pool = load_existing_keyword_pool()

    # 뉴스별 키워드를 뉴스 단위로 dedup 후 등장 뉴스 수 집계
    cursor.execute(f"""
        SELECT DISTINCT news_id, keyword
        FROM AGENT1_KEYWORD
        WHERE run_id IN ({_RUN_PH}) AND keyword IS NOT NULL AND keyword != ''
    """, tuple(SERVED_RUN_IDS))

    counter: Counter = Counter()
    for news_id, keyword in cursor.fetchall():
        if news_id in risk_ids:
            counter[keyword] += 1

    return {
        kw for kw, cnt in counter.items()
        if cnt >= RECO_KEYWORD_THRESHOLD and kw not in pool
    }


def compute_recommended_tags(cursor, risk_ids: Set[str]) -> Dict[str, str]:
    """매핑 실패 키워드 중 추천 태그 집합 (normalized -> 대표 라벨).

    (a) EVENT 가능: 추상어 블랙리스트에 없음 (규칙 근사)
    (b) 기존 태그와 비중복: 기존 태그 이름(normalized)과 불일치 +
        기존 EVENT 키워드(normalized)에 없음 +
        기존 EVENT 태그 이름과 유사도 < RECO_TAG_DUP_SIMILARITY
    (c) normalized 기준 뉴스 단위 dedup 후 등장 뉴스 수 >= RECO_TAG_THRESHOLD.
    """
    if not risk_ids:
        return {}

    existing_tag_names = load_existing_tag_names(cursor)
    existing_event_keywords = load_existing_event_keywords(cursor)
    existing_event_tag_names = load_existing_event_tag_names(cursor)
    blacklist = set(RECO_ABSTRACT_KEYWORD_BLACKLIST)

    # AGENT2_DOC.unmatched_keywords(JSON 배열) → normalized 별 등장 뉴스 수
    cursor.execute(f"""
        SELECT news_id, unmatched_keywords
        FROM AGENT2_DOC
        WHERE run_id IN ({_RUN_PH})
          AND unmatched_keywords IS NOT NULL
          AND unmatched_keywords NOT IN ('', '[]', 'null')
    """, tuple(SERVED_RUN_IDS))

    counter: Counter = Counter()
    labels: Dict[str, str] = {}  # normalized -> 최초 등장 원문 라벨
    for news_id, raw in cursor.fetchall():
        if news_id not in risk_ids:
            continue
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(items, list):
            continue
        # 뉴스 내 동일 normalized는 1회로 (등장 뉴스 수 집계)
        seen_in_news: Set[str] = set()
        for it in items:
            if not isinstance(it, dict):
                continue
            keyword = it.get("keyword")
            if not keyword:
                continue
            norm = it.get("normalized") or normalize_keyword(keyword)
            if norm in seen_in_news:
                continue
            seen_in_news.add(norm)
            counter[norm] += 1
            labels.setdefault(norm, keyword)

    recommended: Dict[str, str] = {}
    for norm, cnt in counter.items():
        if cnt < RECO_TAG_THRESHOLD:
            continue
        label = labels[norm]
        # (a) 추상어 제외
        if label in blacklist:
            continue
        # (b) 기존 태그 이름/EVENT 키워드 중복 제외
        if norm in existing_tag_names or norm in existing_event_keywords:
            continue
        # (b) 기존 EVENT 태그 이름과 유사도 중복 제외
        if any(
            _string_similarity(normalize_keyword(label), normalize_keyword(tag_name))
            >= RECO_TAG_DUP_SIMILARITY
            for tag_name in existing_event_tag_names
        ):
            continue
        recommended[norm] = label

    return recommended


@lru_cache(maxsize=1)
def get_recommendation_index() -> RecommendationIndex:
    """전역 추천 집계를 1회 계산·캐시하여 반환."""
    with get_news_db() as conn:
        cursor = conn.cursor()
        risk_ids = _risk_news_ids(cursor)
        keywords = compute_recommended_keywords(cursor, risk_ids)
        # 태그 추천 기능 비활성화 (추후 재활성화 시 아래 복원)
        # tags = compute_recommended_tags(cursor, risk_ids)
        tags = {}
    return RecommendationIndex(recommended_keywords=keywords, recommended_tags=tags)
