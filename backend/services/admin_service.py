"""
Admin Service - 운영 키워드/태그 관리 (OP_KEYWORD, OP_TAG)

- 관리자 편집(추가/소프트삭제)은 OP_* 테이블에만 쓴다.
- AI 추천은 파이프라인 산출물(AGENT1_KEYWORD, AGENT4_RISK_EVAL, AGENT2_TAG)을 SELECT만 하여 계산.
- 쓰기 후 conn.commit() 필수 (get_news_db는 auto-commit 아님).
"""
import sys
import json
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List
from models.admin import (
    OpKeyword, OpKeywordCreate, OpTag, OpTagCreate,
    RecommendedKeyword, RecommendedTag,
)
from database.connection import get_news_db

# recommend_keywords.py(Agent_4)와 동일: Risk 뉴스에서 N회 이상 출현 키워드 추천
KEYWORD_THRESHOLD = 5


# ─── OP_KEYWORD ────────────────────────────────────────────────────────────

def list_keywords() -> List[OpKeyword]:
    """활성 키워드 전체 조회."""
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, risk_category_code, risk_category_name, risk_factor,
                   keyword_group_name, keyword, target_region, description, source
            FROM OP_KEYWORD
            WHERE is_active = 1
            ORDER BY id ASC
        """)
        return [OpKeyword(**dict(r)) for r in cursor.fetchall()]


def create_keyword(req: OpKeywordCreate) -> OpKeyword:
    """키워드 추가 (source='manual')."""
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO OP_KEYWORD (
                risk_category_code, risk_category_name, risk_factor,
                keyword_group_name, keyword, target_region,
                is_active, description, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, 'manual', ?)
        """, (
            req.risk_category_code, req.risk_category_name, req.risk_factor,
            req.keyword_group_name, req.keyword, req.target_region,
            req.description, created_at,
        ))
        new_id = cursor.lastrowid
        conn.commit()
        cursor.execute("""
            SELECT id, risk_category_code, risk_category_name, risk_factor,
                   keyword_group_name, keyword, target_region, description, source
            FROM OP_KEYWORD WHERE id = ?
        """, (new_id,))
        return OpKeyword(**dict(cursor.fetchone()))


def soft_delete_keywords(ids: List[int]) -> int:
    """키워드 다중 소프트 삭제 (is_active=0)."""
    if not ids:
        return 0
    ph = ",".join("?" * len(ids))
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE OP_KEYWORD SET is_active = 0 WHERE id IN ({ph})", tuple(ids))
        conn.commit()
        return cursor.rowcount


def _existing_keyword_set(cursor) -> set:
    """활성 OP_KEYWORD.keyword(JSON 배열 문자열)를 개별 키워드 set으로 전개.

    recommend_keywords.load_existing_keywords 와 동일하게 배열을 펼쳐 비교한다.
    """
    cursor.execute("SELECT keyword FROM OP_KEYWORD WHERE is_active = 1")
    existing = set()
    for (raw,) in cursor.fetchall():
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                existing.update(str(k).strip() for k in parsed)
            else:
                existing.add(str(parsed).strip())
        except (json.JSONDecodeError, TypeError):
            existing.add(str(raw).strip())
    return existing


def recommend_keywords() -> List[RecommendedKeyword]:
    """AI 추천 신규 키워드.

    Agent_4 recommend_keywords 로직 재구현(현 스키마 기준):
    Risk 뉴스(is_risk=1)의 AGENT1_KEYWORD 키워드를 집계 →
    KEYWORD_THRESHOLD 이상 출현 & 기존 키워드셋(OP_KEYWORD 전개) 미포함 → count 내림차순.
    """
    with get_news_db() as conn:
        cursor = conn.cursor()
        existing = _existing_keyword_set(cursor)

        cursor.execute("""
            SELECT k.keyword AS keyword, COUNT(*) AS cnt
            FROM AGENT1_KEYWORD k
            JOIN AGENT4_RISK_EVAL r
              ON r.run_id = k.run_id AND r.news_id = k.news_id
            WHERE r.is_risk = 1
              AND k.keyword IS NOT NULL AND k.keyword != ''
            GROUP BY k.keyword
            HAVING cnt >= ?
            ORDER BY cnt DESC, k.keyword ASC
        """, (KEYWORD_THRESHOLD,))

        recs = []
        for row in cursor.fetchall():
            kw = row["keyword"]
            if kw.strip() in existing:
                continue
            recs.append(RecommendedKeyword(keyword=kw, count=row["cnt"]))
        return recs


# ─── OP_TAG ──────────────────────────────────────────────────────────────────

def list_tags() -> List[OpTag]:
    """활성 태그 전체 조회."""
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tag_id, target_region, tag_type, name, domain, risk_factor,
                   keyword_count, keywords_full, description, target_table_column,
                   db_matched_count, source
            FROM OP_TAG
            WHERE is_active = 1
            ORDER BY id ASC
        """)
        return [OpTag(**dict(r)) for r in cursor.fetchall()]


def create_tag(req: OpTagCreate) -> OpTag:
    """태그 추가 (source='manual'). EVENT 타입만 허용 — 그 외는 강제로 EVENT 처리."""
    tag_type = "EVENT"  # 편집 가능한 태그는 EVENT로 제한
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO OP_TAG (
                tag_id, target_region, tag_type, name, domain, risk_factor,
                keyword_count, keywords_full, description, target_table_column,
                db_matched_count, is_active, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'manual', ?)
        """, (
            req.tag_id, req.target_region, tag_type, req.name, req.domain,
            req.risk_factor, req.keyword_count, req.keywords_full, req.description,
            req.target_table_column, req.db_matched_count, created_at,
        ))
        new_id = cursor.lastrowid
        conn.commit()
        cursor.execute("""
            SELECT id, tag_id, target_region, tag_type, name, domain, risk_factor,
                   keyword_count, keywords_full, description, target_table_column,
                   db_matched_count, source
            FROM OP_TAG WHERE id = ?
        """, (new_id,))
        return OpTag(**dict(cursor.fetchone()))


def soft_delete_tags(ids: List[int]) -> int:
    """태그 다중 소프트 삭제 (is_active=0)."""
    if not ids:
        return 0
    ph = ",".join("?" * len(ids))
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE OP_TAG SET is_active = 0 WHERE id IN ({ph})", tuple(ids))
        conn.commit()
        return cursor.rowcount


def recommend_tags() -> List[RecommendedTag]:
    """AI 추천 신규 태그.

    파이프라인이 제안·검토해 AGENT2_TAG(tag_type='EVENT')에 저장한 EVENT 태그 중
    현재 활성 OP_TAG.name 에 없는 것만. (EVENT 외 타입은 자동생성 대상이라 추천하지 않음)
    """
    with get_news_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM OP_TAG WHERE is_active = 1 AND name IS NOT NULL")
        existing = {str(r["name"]).strip() for r in cursor.fetchall()}

        cursor.execute("""
            SELECT tag_name, MAX(target_region) AS target_region
            FROM AGENT2_TAG
            WHERE tag_type = 'EVENT' AND tag_name IS NOT NULL AND tag_name != ''
            GROUP BY tag_name
            ORDER BY tag_name ASC
        """)
        recs = []
        for row in cursor.fetchall():
            name = str(row["tag_name"]).strip()
            if name in existing:
                continue
            recs.append(RecommendedTag(name=name, tag_type="EVENT"))
        return recs
