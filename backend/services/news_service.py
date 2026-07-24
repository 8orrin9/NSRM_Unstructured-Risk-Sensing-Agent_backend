"""
News Service - 뉴스 데이터 조회 및 변환 로직

DB 스키마: AGENT1~5 파이프라인 산출물 (news_intelligence.db)
- 서빙 대상 run은 config.SERVED_RUN_IDS 로 제한 (full_run_01 + golden_eval).
- 원문은 NEWS_MASTER(full_run) / GOLDEN_NEWS_MASTER(golden) 두 테이블에 분산.
"""
import sys
import json
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Optional, Dict
from models.news import NewsItem, NewsGroup, NewsStats, Severity, RiskCategory
from database.connection import get_news_db, get_supply_chain_db
from config import SERVED_RUN_IDS
from services.recommendation_service import (
    get_recommendation_index,
    RecommendationIndex,
    normalize_keyword,
)


# run_id IN (?, ?) 플레이스홀더 (모든 AGENT 쿼리에 일관 적용)
_RUN_PH = ",".join("?" * len(SERVED_RUN_IDS))


# Risk Category 매핑 (risk_category_name(한글) → Frontend RiskCategory)
RISK_CATEGORY_TO_FRONTEND: Dict[str, RiskCategory] = {
    "지정학 & 규제": "geopolitical",
    "공급집중&단일소싱": "supply",
    "원자재&희소물질": "material",
    "기술&지식재산": "tech",
    "물류&인프라": "logistics",
    "사이버&데이터": "cyber",
    "ESG & Compliance": "esg",
    "재무&신용 Risk": "financial",
    "자연재해&기후": "disaster",
}


def determine_severity(issue_priority: str, risk_score: float) -> Severity:
    """
    risk_score(=impactScore/100) 단일 임계값으로 3단계 severity 결정.

    프론트 NewsOverlay 게이지 경계(25/75)와 정합:
    - risk_score >= 0.75 → high    (impactScore >= 75)
    - risk_score >= 0.25 → medium  (impactScore >= 25)
    - 그 외              → low

    issue_priority 인자는 호출부 호환을 위해 유지하되 사용하지 않는다.
    """
    if risk_score >= 0.75:
        return "high"
    elif risk_score >= 0.25:
        return "medium"
    else:
        return "low"


# ─── 공용 헬퍼 ────────────────────────────────────────────────────────────────

def _fetch_master_rows(cursor, news_ids: List[str]) -> Dict[str, dict]:
    """
    news_id -> 원문 딕셔너리. NEWS_MASTER(full_run) + GOLDEN_NEWS_MASTER(golden) UNION.
    GOLDEN에는 risk_category_name 컬럼이 없으므로 NULL, origin으로 출처 구분.
    """
    if not news_ids:
        return {}
    ph = ",".join("?" * len(news_ids))
    cursor.execute(f"""
        SELECT news_id, source, title, description, content, url, pub_date,
               risk_category_name, 'NEWS_MASTER' AS origin
        FROM NEWS_MASTER WHERE news_id IN ({ph})
        UNION ALL
        SELECT news_id, source, title, description, content, url, pub_date,
               NULL AS risk_category_name, 'GOLDEN' AS origin
        FROM GOLDEN_NEWS_MASTER WHERE news_id IN ({ph})
    """, (*news_ids, *news_ids))
    return {r["news_id"]: dict(r) for r in cursor.fetchall()}


def _run_id_for_origin(origin: str) -> str:
    """마스터 출처 → run_id (news_id는 run 간 1:1 대응, 겹침 없음)."""
    return "full_run_01" if origin == "NEWS_MASTER" else "golden_eval_20260715"


def _resolve_category(cursor, master_row: dict) -> RiskCategory:
    """risk_category_name(한글) → Frontend RiskCategory. golden은 GOLDEN_GROUND_TRUTH에서 조회."""
    cat_name = master_row.get("risk_category_name")
    if not cat_name and master_row.get("origin") == "GOLDEN":
        cursor.execute(
            "SELECT risk_category_name FROM GOLDEN_GROUND_TRUTH WHERE news_id = ?",
            (master_row["news_id"],),
        )
        gt = cursor.fetchone()
        if gt:
            cat_name = gt["risk_category_name"]
    return RISK_CATEGORY_TO_FRONTEND.get(cat_name, "geopolitical")


def _get_keywords(cursor, run_id: str, news_id: str) -> List[str]:
    """AGENT1_KEYWORD 에서 rank 순 키워드 목록."""
    cursor.execute(f"""
        SELECT keyword FROM AGENT1_KEYWORD
        WHERE run_id IN ({_RUN_PH}) AND news_id = ?
        ORDER BY rank ASC
    """, (*SERVED_RUN_IDS, news_id))
    return [r["keyword"] for r in cursor.fetchall() if r["keyword"]]


def _get_tags(cursor, run_id: str, news_id: str) -> tuple:
    """AGENT2_TAG(태그명) + TAG_MASTER(조인 메타)로 (tags, tag_refs) 반환.

    AGENT2_TAG.target_region 은 NULL 이므로 tag_id 단독 조인.
    동일 tag_id 의 TAG_MASTER 행들은 target_table_column 이 동일하므로 존재 여부만 확인.
    linkable = EVENT 아님 AND non-empty target_table_column 존재 (EVENT 는 '').
    tag_name 기준 중복 제거(기존 DISTINCT tag_name 동작 유지).
    """
    from models.news import TagRef

    cursor.execute(f"""
        SELECT t.tag_id, t.tag_name, t.tag_type
        FROM AGENT2_TAG t
        WHERE t.run_id IN ({_RUN_PH}) AND t.news_id = ?
          AND t.tag_id IS NOT NULL AND t.tag_name IS NOT NULL
        GROUP BY t.tag_id, t.tag_name, t.tag_type
        ORDER BY MIN(t.id) ASC
    """, (*SERVED_RUN_IDS, news_id))
    rows = cursor.fetchall()

    tags: List[str] = []
    refs: List[TagRef] = []
    for r in rows:
        if r["tag_name"] in tags:
            continue
        cursor.execute("""
            SELECT 1 FROM TAG_MASTER
            WHERE tag_id = ? AND target_table_column IS NOT NULL
              AND target_table_column != '' LIMIT 1
        """, (r["tag_id"],))
        linkable = r["tag_type"] != "EVENT" and cursor.fetchone() is not None
        tags.append(r["tag_name"])
        refs.append(TagRef(
            tagId=r["tag_id"], tagName=r["tag_name"],
            tagType=r["tag_type"], linkable=linkable,
        ))
    return tags, refs


def _get_ko_text(cursor, news_id: str) -> dict:
    """AGENT1_ANALYSIS 에서 한글 title/summary."""
    cursor.execute(f"""
        SELECT title_ko, summary_ko FROM AGENT1_ANALYSIS
        WHERE run_id IN ({_RUN_PH}) AND news_id = ?
        LIMIT 1
    """, (*SERVED_RUN_IDS, news_id))
    row = cursor.fetchone()
    return dict(row) if row else {}


def _related_entity_ids_for_news(cursor, news_id: str) -> List[str]:
    """
    AGENT3_SCENARIO.search_results(JSON 배열) → supplier_code 리스트.
    각 item에서 ① 직접 코드(협력사코드/생산지코드/사이트코드) ② 이름 매칭 순으로 채택.
    site_code는 소속 supplier_code로 롤업(거점 매핑을 협력사 단위로 통일).
    중복 제거, 순서 보존.
    """
    def _add_supplier(codes, seen, scur, raw_code):
        """supplier_code면 그대로, site_code면 소속 supplier로 롤업하여 추가."""
        code = str(raw_code)
        if _is_supplier(scur, code):
            sup = code
        elif _is_site(scur, code):
            sup = _site_to_supplier(scur, code)
        else:
            sup = None
        if sup and sup not in seen:
            codes.append(sup); seen.add(sup)
    cursor.execute(f"""
        SELECT search_results FROM AGENT3_SCENARIO
        WHERE run_id IN ({_RUN_PH}) AND news_id = ?
          AND search_results IS NOT NULL AND search_results NOT IN ('', '[]')
    """, (*SERVED_RUN_IDS, news_id))
    rows = cursor.fetchall()
    if not rows:
        return []

    codes: List[str] = []
    seen = set()
    with get_supply_chain_db() as sc:
        scur = sc.cursor()
        for (raw,) in [(r["search_results"],) for r in rows]:
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                # 1) 직접 코드 우선 (site_code는 _add_supplier가 supplier로 롤업)
                for ck in ("협력사코드", "생산지코드", "사이트코드"):
                    code = it.get(ck)
                    if code:
                        _add_supplier(codes, seen, scur, code)
                # 2) 이름 매칭 fallback
                for nk in ("협력사명", "협력사명_영문", "생산지명"):
                    name = it.get(nk)
                    if not name or name == "?":
                        continue
                    matched = _match_name(scur, str(name))
                    if matched:
                        _add_supplier(codes, seen, scur, matched)
    return codes


def _site_to_supplier(scur, site_code: str) -> Optional[str]:
    """site_code → 소속 supplier_code (거점 매핑을 협력사 단위로 롤업)."""
    scur.execute(
        "SELECT supplier_code FROM SITE_MASTER WHERE site_code = ? AND is_active = 1 LIMIT 1",
        (site_code,),
    )
    row = scur.fetchone()
    if not row or not row["supplier_code"]:
        return None
    sup = row["supplier_code"]
    return sup if _is_supplier(scur, sup) else None


def _is_supplier(scur, code: str) -> bool:
    scur.execute(
        "SELECT 1 FROM SUPPLIER_MASTER WHERE supplier_code = ? AND is_active = 1 LIMIT 1",
        (code,),
    )
    return scur.fetchone() is not None


def _is_site(scur, code: str) -> bool:
    scur.execute(
        "SELECT 1 FROM SITE_MASTER WHERE site_code = ? AND is_active = 1 LIMIT 1",
        (code,),
    )
    return scur.fetchone() is not None


def _match_name(scur, name: str) -> Optional[str]:
    """협력사명/거점명 → supplier_code 또는 site_code."""
    scur.execute("""
        SELECT supplier_code FROM SUPPLIER_MASTER
        WHERE (name_kor = ? OR name_eng = ?) AND is_active = 1
        LIMIT 1
    """, (name, name))
    row = scur.fetchone()
    if row:
        return row["supplier_code"]
    scur.execute("""
        SELECT site_code FROM SITE_MASTER
        WHERE name LIKE ? AND is_active = 1
        LIMIT 1
    """, (f"%{name}%",))
    row = scur.fetchone()
    return row["site_code"] if row else None


def _get_unmatched_normalized(cursor, news_id: str) -> Dict[str, str]:
    """해당 뉴스의 매핑 실패 키워드 normalized -> 원문 라벨. 추천 태그 교집합용."""
    cursor.execute(f"""
        SELECT unmatched_keywords FROM AGENT2_DOC
        WHERE run_id IN ({_RUN_PH}) AND news_id = ?
          AND unmatched_keywords IS NOT NULL
          AND unmatched_keywords NOT IN ('', '[]', 'null')
    """, (*SERVED_RUN_IDS, news_id))
    result: Dict[str, str] = {}
    for (raw,) in cursor.fetchall():
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            keyword = it.get("keyword")
            if not keyword:
                continue
            norm = it.get("normalized") or normalize_keyword(keyword)
            result.setdefault(norm, keyword)
    return result


def _build_news_item(cursor, news_id: str, master: dict, risk: dict,
                     include_detail: bool = False,
                     index: Optional[RecommendationIndex] = None) -> NewsItem:
    """마스터 원문 + AGENT 산출물을 조합하여 NewsItem 생성."""
    run_id = _run_id_for_origin(master["origin"])
    if index is None:
        index = get_recommendation_index()

    ko = _get_ko_text(cursor, news_id)
    title = ko.get("title_ko") or master.get("title") or ""
    summary = ko.get("summary_ko") or master.get("description") or ""

    risk_score = risk.get("risk_score", 0.5)
    issue_priority = risk.get("issue_priority", "MEDIUM")
    severity_value = determine_severity(issue_priority, risk_score)

    detail = ""
    if include_detail:
        # 원문(Full Contents)에는 순수 본문만 담는다. 요약은 별도 섹션에서 표시되므로
        # 중복 노출을 막기 위해 여기서 summary 를 앞에 붙이지 않는다.
        detail = master.get("content") or master.get("description") or ""

    # 추천 키워드: 전역 집계(index)와 이 뉴스의 값을 교집합
    keywords = _get_keywords(cursor, run_id, news_id)
    recommended_keywords = [k for k in keywords if k in index.recommended_keywords]
    # 태그 추천 기능 비활성화 (추후 재활성화 시 아래 복원)
    # unmatched = _get_unmatched_normalized(cursor, news_id)
    # recommended_tags = [
    #     label for norm, label in unmatched.items() if norm in index.recommended_tags
    # ]

    tag_names, tag_refs = _get_tags(cursor, run_id, news_id)

    # 골든 데이터는 과거 날짜이므로 서빙 시 '오늘 날짜'로 표기(사용자 지시).
    # 요청 시점마다 초가 달라지지 않도록 오늘 날짜 + 고정 시각(정오)으로 결정적 처리.
    if master.get("origin") == "GOLDEN":
        published_at = datetime.now().strftime("%Y-%m-%dT12:00:00+09:00")
    else:
        published_at = master.get("pub_date") or ""

    return NewsItem(
        id=news_id,
        title=title,
        source=master.get("source") or "",
        publishedAt=published_at,
        category=_resolve_category(cursor, master),
        severity=severity_value,
        summary=summary,
        detail=detail,
        keywords=keywords,
        recommendedKeywords=recommended_keywords,
        tags=tag_names,
        tagRefs=tag_refs,
        # recommendedTags=recommended_tags,  # 태그 추천 기능 비활성화
        relatedEntityIds=_related_entity_ids_for_news(cursor, news_id),
        region="Global",
        url=master.get("url") or "",
        impactScore=int(risk_score * 100),
        riskJustification=risk.get("risk_justification") or "",
        isRisk=bool(risk.get("is_risk")),
    )


# ─── API 서비스 함수 ──────────────────────────────────────────────────────────

def get_news_list(
    severity: Optional[Severity] = None,
    risk_factor: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    domestic_only: bool = False
) -> List[NewsItem]:
    """
    뉴스 목록 조회 (ISSUE 또는 SMD로 판정된 개별 뉴스만)

    그룹 멤버 뉴스도 개별 평가(is_grouped=0)가 있으면 자동 포함된다.
    """
    with get_news_db() as conn:
        cursor = conn.cursor()

        # 노출 게이트: AGENT4 개별 평가 중 ISSUE/SMD 개별 뉴스.
        # is_risk 필터는 서빙 단계에서 걸지 않는다(is_risk=isRisk 필드로 노출 →
        # Risk Factor Monitor는 전량, Individual News는 프론트에서 isRisk=true만).
        cursor.execute(f"""
            SELECT news_id, risk_score, issue_priority, issue_type, risk_justification, is_risk
            FROM AGENT4_RISK_EVAL
            WHERE run_id IN ({_RUN_PH})
              AND issue_type IN ('ISSUE', 'SMD')
              AND is_grouped = 0
        """, tuple(SERVED_RUN_IDS))
        risk_rows = {r["news_id"]: dict(r) for r in cursor.fetchall()}

        if not risk_rows:
            return []

        # 원문 일괄 조회
        masters = _fetch_master_rows(cursor, list(risk_rows.keys()))

        # 추천 키워드/태그 전역 집계 1회 취득 (뉴스 루프 밖)
        index = get_recommendation_index()

        news_items = []
        for news_id, risk in risk_rows.items():
            master = masters.get(news_id)
            if not master:
                continue  # 원문 없는 뉴스는 스킵

            # 국내 기사 필터 (NAVER_NEWS)
            if domestic_only and master.get("source") != "NAVER_NEWS":
                continue

            item = _build_news_item(cursor, news_id, master, risk, include_detail=False, index=index)

            # severity 후처리 필터
            if severity and item.severity != severity:
                continue

            news_items.append(item)

        # 최신순 정렬 후 페이징
        news_items.sort(key=lambda n: n.publishedAt, reverse=True)
        return news_items[offset:offset + limit]


def get_news_by_id(news_id: str) -> Optional[NewsItem]:
    """특정 뉴스 조회 (detail 포함, ISSUE/SMD 게이트 없음)."""
    with get_news_db() as conn:
        cursor = conn.cursor()

        masters = _fetch_master_rows(cursor, [news_id])
        master = masters.get(news_id)
        if not master:
            return None

        # AGENT4 개별 평가 조회 (없으면 기본값)
        cursor.execute(f"""
            SELECT risk_score, issue_priority, issue_type, risk_justification, is_risk
            FROM AGENT4_RISK_EVAL
            WHERE run_id IN ({_RUN_PH}) AND news_id = ? AND is_grouped = 0
            LIMIT 1
        """, (*SERVED_RUN_IDS, news_id))
        row = cursor.fetchone()
        risk = dict(row) if row else {"risk_score": 0.5, "issue_priority": "MEDIUM"}

        return _build_news_item(cursor, news_id, master, risk, include_detail=True)


def get_news_groups() -> List[NewsGroup]:
    """뉴스 그룹 목록 조회 (AGENT5_GROUP)."""
    with get_news_db() as conn:
        cursor = conn.cursor()

        # 서빙 표시 결정(SERVING_GROUP_DISPLAY)을 LEFT JOIN.
        # 결정 행이 없는 그룹은 기본 표시(COALESCE(is_displayed,1)=1)로 안전 처리.
        cursor.execute(f"""
            SELECT g.run_id, g.group_id, g.group_name, g.group_theme
            FROM AGENT5_GROUP g
            LEFT JOIN SERVING_GROUP_DISPLAY d
              ON d.run_id = g.run_id AND d.group_id = g.group_id
            WHERE g.run_id IN ({_RUN_PH})
              AND g.group_id != 'ungrouped'
              AND g.group_theme IS NOT NULL
              AND COALESCE(d.admin_override, d.is_displayed, 1) = 1
            ORDER BY g.group_id ASC
        """, tuple(SERVED_RUN_IDS))
        rows = cursor.fetchall()

        groups = []
        for row in rows:
            run_id = row["run_id"]
            group_id = row["group_id"]

            # 그룹 멤버 뉴스 조회
            cursor.execute("""
                SELECT news_id FROM AGENT5_GROUP_MEMBER
                WHERE run_id = ? AND group_id = ?
            """, (run_id, group_id))
            news_ids = [m["news_id"] for m in cursor.fetchall()]

            if not news_ids:
                continue

            groups.append(NewsGroup(
                id=f"{run_id}:{group_id}",  # run 간 group_id 충돌 방지
                title=row["group_name"] or (row["group_theme"][:40] if row["group_theme"] else group_id),
                newsIds=news_ids,
                rationale=row["group_theme"] or "",
                status="active",
            ))

        return groups


def get_news_stats() -> NewsStats:
    """뉴스 통계 조회 (/api/news 와 동일 노출셋 기준)."""
    with get_news_db() as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT risk_score, issue_priority
            FROM AGENT4_RISK_EVAL
            WHERE run_id IN ({_RUN_PH})
              AND issue_type IN ('ISSUE', 'SMD')
              AND is_grouped = 0
        """, tuple(SERVED_RUN_IDS))
        rows = cursor.fetchall()

        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for row in rows:
            sv = determine_severity(row["issue_priority"], row["risk_score"])
            severity_counts[sv] += 1

        # 그룹 개수 (서빙 표시 결정과 동일 기준)
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM AGENT5_GROUP g
            LEFT JOIN SERVING_GROUP_DISPLAY d
              ON d.run_id = g.run_id AND d.group_id = g.group_id
            WHERE g.run_id IN ({_RUN_PH})
              AND g.group_id != 'ungrouped'
              AND g.group_theme IS NOT NULL
              AND COALESCE(d.is_displayed, 1) = 1
        """, tuple(SERVED_RUN_IDS))
        groups_count = cursor.fetchone()["count"]

        return NewsStats(
            total=len(rows),
            high=severity_counts["high"],
            medium=severity_counts["medium"],
            low=severity_counts["low"],
            groups=groups_count,
        )


# ─── 관리자: AI 핵심 인사이트(그룹) 노출 관리 ───────────────────────────────────

def _renderable_member_ids(cursor, run_id: str, group_id: str) -> List[str]:
    """프론트가 실제로 렌더하는 멤버 news_id 목록.

    compute_group_serving.renderable_members 와 동일 조건
    (ISSUE/SMD, is_grouped=0). 목록의 memberCount 와 서빙 후보 판정을 일치시킨다.
    """
    cursor.execute("""
        SELECT m.news_id
        FROM AGENT5_GROUP_MEMBER m
        JOIN AGENT4_RISK_EVAL r
          ON r.run_id = m.run_id AND r.news_id = m.news_id
        WHERE m.run_id = ? AND m.group_id = ?
          AND r.issue_type IN ('ISSUE', 'SMD')
          AND r.is_grouped = 0
    """, (run_id, group_id))
    return [row["news_id"] for row in cursor.fetchall()]


def get_admin_groups() -> List["AdminGroup"]:
    """검증된 전체 그룹(숨김 포함) + 각 그룹의 노출 상태 조회 (관리자용).

    노출 필터(is_displayed/admin_override)는 적용하지 않고 검증 조건만 적용.
    단, 렌더 가능 멤버 < MIN_RENDERABLE_MEMBERS 인 그룹은 표기 자격 미달로 제외
    (compute_group_serving 자동 숨김 기준과 동일 — 관리자가 강제 노출해도 카드가
    제대로 안 그려지므로 선택 대상에서 뺀다).
    """
    from models.news import AdminGroup

    # compute_group_serving.MIN_RENDERABLE_MEMBERS 와 동기화 유지.
    MIN_RENDERABLE_MEMBERS = 3

    with get_news_db() as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT g.run_id, g.group_id, g.group_name, g.group_theme,
                   d.is_displayed, d.admin_override
            FROM AGENT5_GROUP g
            LEFT JOIN SERVING_GROUP_DISPLAY d
              ON d.run_id = g.run_id AND d.group_id = g.group_id
            WHERE g.run_id IN ({_RUN_PH})
              AND g.group_id != 'ungrouped'
              AND g.group_theme IS NOT NULL
            ORDER BY g.group_id ASC
        """, tuple(SERVED_RUN_IDS))
        rows = cursor.fetchall()

        groups: List[AdminGroup] = []
        for row in rows:
            run_id = row["run_id"]
            group_id = row["group_id"]

            member_ids = _renderable_member_ids(cursor, run_id, group_id)
            if len(member_ids) < MIN_RENDERABLE_MEMBERS:
                continue

            auto = row["is_displayed"] if row["is_displayed"] is not None else 1
            override = row["admin_override"]  # 0/1/None
            shown = bool(override) if override is not None else bool(auto)

            groups.append(AdminGroup(
                id=f"{run_id}:{group_id}",
                title=row["group_name"] or (row["group_theme"][:40] if row["group_theme"] else group_id),
                theme=row["group_theme"] or "",
                memberCount=len(member_ids),
                newsIds=member_ids,
                autoDisplayed=bool(auto),
                adminOverride=None if override is None else bool(override),
                currentlyShown=shown,
            ))

        return groups


def save_admin_group_display(shown_ids: List[str]) -> int:
    """노출 그룹 선택 저장 (관리자용).

    관리자 화면에 표기된 그룹(get_admin_groups 대상 = 멤버≥3)을 대상으로,
    shown_ids 에 포함되면 admin_override=1, 아니면 0 으로 UPSERT.
    (전체 명시 저장 → 체크 해제=숨김. 화면에 안 나온 그룹은 건드리지 않는다.)
    """
    shown_set = set(shown_ids)
    computed_at = datetime.now().isoformat(timespec="seconds")

    # 대상 = 관리자 화면에 실제 표기된 그룹 (멤버≥3 등 표기 기준 일치)
    targets = get_admin_groups()

    with get_news_db() as conn:
        cursor = conn.cursor()

        updated = 0
        for g in targets:
            run_id, group_id = g.id.split(":", 1)  # "{run_id}:{group_id}"
            override = 1 if g.id in shown_set else 0
            cursor.execute("""
                INSERT INTO SERVING_GROUP_DISPLAY (run_id, group_id, admin_override, computed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id, group_id)
                DO UPDATE SET admin_override = excluded.admin_override,
                              computed_at = excluded.computed_at
            """, (run_id, group_id, override, computed_at))
            updated += 1

        conn.commit()  # DatabaseConnection 은 auto-commit 아님 — 명시 필요
        return updated
