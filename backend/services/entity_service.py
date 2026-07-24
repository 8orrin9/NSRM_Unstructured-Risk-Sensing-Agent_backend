# -*- coding: utf-8 -*-
"""
Entity Service - 공급망 거점 데이터 조회 로직
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Optional
from models.entity import SupplyEntity, EntityStatus
from models.news import NewsItem, Severity
from database.connection import get_supply_chain_db, get_news_db
from config import SERVED_RUN_IDS

_RUN_PH = ",".join("?" * len(SERVED_RUN_IDS))


def get_entities(
    status: Optional[EntityStatus] = None,
    tier: Optional[int] = None
) -> List[SupplyEntity]:
    """
    공급망 거점 목록 조회

    Args:
        status: 상태 필터 (normal/watch/disrupted)
        tier: Tier 필터 (1/2/3)

    Returns:
        공급망 거점 리스트
    """
    with get_supply_chain_db() as conn:
        cursor = conn.cursor()

        # SUPPLIER_MASTER와 SITE_MASTER 조인
        query = """
        SELECT
            s.supplier_code as id,
            s.name_eng as name,
            s.name_kor as nameKo,
            s.country,
            s.region as city,
            COALESCE(s.latitude, 0) as lat,
            COALESCE(s.longitude, 0) as lng,
            s.is_active
        FROM SUPPLIER_MASTER s
        WHERE s.is_active = 1
        """

        params = []

        # 필터링은 간단히 구현 (tier는 별도 컬럼이 없으므로 임의 할당)
        query += " ORDER BY s.supplier_code"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        entities = []
        for idx, row in enumerate(rows):
            supplier_id = row["id"]

            # 위도/경도가 0이면 스킵
            if row["lat"] == 0 or row["lng"] == 0:
                continue

            # 공급 품목 조회
            cursor.execute("""
                SELECT DISTINCT sm.material_code, m.name_kor
                FROM SITE_MATERIAL_MAP sm
                INNER JOIN MATERIAL_MASTER m ON sm.material_code = m.material_code
                INNER JOIN SITE_MASTER st ON sm.site_code = st.site_code
                WHERE st.supplier_code = ?
                LIMIT 5
            """, (supplier_id,))
            products = [p["name_kor"] or p["material_code"] for p in cursor.fetchall()]

            # 관련 Risk 뉴스는 프론트엔드에서 계산하도록 빈 배열 반환
            active_risk_ids = []

            # Tier는 임의로 1-3 할당 (실제로는 별도 로직 필요)
            tier_value = (idx % 3) + 1

            # Status는 기본 normal (프론트엔드에서 뉴스 개수로 동적 결정)
            status_value = "normal"

            # Criticality 결정 (간단히 tier로)
            criticality: Severity = "high" if tier_value == 1 else ("medium" if tier_value == 2 else "low")

            entity = SupplyEntity(
                id=supplier_id,  # DB supplier_code 사용 (예: KR0001)
                name=row["name"],
                nameKo=row["nameKo"] or row["name"],
                type="supplier",
                tier=tier_value,
                category="Semiconductor Materials/Equipment",
                country=row["country"],
                city=row["city"] or "",
                lat=row["lat"],
                lng=row["lng"],
                criticality=criticality,
                status=status_value,
                products=products,
                activeRiskIds=active_risk_ids,
            )
            entities.append(entity)

        return entities


def get_max_severity_from_news_ids(news_ids: List[str]) -> str:
    """
    뉴스 ID 리스트에서 최고 severity 반환 (AGENT4_RISK_EVAL 기준)

    Returns:
        'high', 'medium', 'low' 중 하나
    """
    if not news_ids:
        return 'low'

    with get_news_db() as conn:
        cursor = conn.cursor()

        # determine_severity 로직을 SQL CASE로 미러링하여 최고 severity(rank 최소) 조회
        # risk_score 단일 임계값 기준 (3단 체계: 0.75/0.25)
        placeholders = ','.join('?' * len(news_ids))
        cursor.execute(f"""
            SELECT MIN(
                CASE
                    WHEN risk_score >= 0.75 THEN 0
                    WHEN risk_score >= 0.25 THEN 1
                    ELSE 2
                END
            ) as severity_rank
            FROM AGENT4_RISK_EVAL
            WHERE run_id IN ({_RUN_PH})
              AND is_grouped = 0
              AND news_id IN ({placeholders})
        """, (*SERVED_RUN_IDS, *news_ids))

        result = cursor.fetchone()
        if result and result['severity_rank'] is not None:
            rank = result['severity_rank']
            if rank < 3:
                return ['high', 'medium', 'low'][rank]
        return 'medium'  # 기본값


def get_related_news_ids(entity_id: str) -> List[str]:
    """
    특정 거점(supplier_code/site_code)과 관련된 뉴스 ID 조회

    AGENT3 search_results 기반 관련 거점 매칭(news_service._related_entity_ids_for_news)의
    역방향 인덱스. 노출 대상 뉴스(ISSUE/SMD 개별 평가)를 순회하여 entity_id를 포함하는 것 수집.
    """
    from services.news_service import _related_entity_ids_for_news

    with get_news_db() as conn:
        cursor = conn.cursor()

        # 노출 대상 뉴스(개별 ISSUE/SMD)만 대상으로 역인덱스 구성
        cursor.execute(f"""
            SELECT DISTINCT news_id FROM AGENT4_RISK_EVAL
            WHERE run_id IN ({_RUN_PH})
              AND issue_type IN ('ISSUE', 'SMD')
              AND is_grouped = 0
        """, tuple(SERVED_RUN_IDS))
        candidate_ids = [r["news_id"] for r in cursor.fetchall()]

        matched = []
        for news_id in candidate_ids:
            if entity_id in _related_entity_ids_for_news(cursor, news_id):
                matched.append(news_id)

        return matched


def get_entity_news(entity_id: str) -> List[NewsItem]:
    """특정 거점과 관련된 뉴스 목록 조회"""
    from services.news_service import get_news_by_id

    news_ids = get_related_news_ids(entity_id)
    news_items = []

    for news_id in news_ids:
        news = get_news_by_id(news_id)
        if news:
            news_items.append(news)

    return news_items
