# -*- coding: utf-8 -*-
"""
Tag Supply Chain Service - 태그 → 공급망(자재/원재료/협력사/거점) 조회 로직

TAG_MASTER.target_table_column(형식: "TABLE.column = 'value'")을 안전 파싱한 뒤
화이트리스트로 검증된 (tag_type, table, column) 조합에서만 supply_chain.db 를 조인한다.
value 는 항상 파라미터 바인딩(?)으로만 사용하고, table/column 은 상수 분기로만 진입한다.
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Optional
from models.tag_supply import SupplyRef, TagSupplyChain
from database.connection import get_news_db, get_supply_chain_db


# target_table_column 파싱: "TABLE.column = 'value'"
_TTC_RE = re.compile(r"^\s*(\w+)\.(\w+)\s*=\s*'(.*)'\s*$")

# 실데이터로 검증된 (tag_type, table, column) 화이트리스트
_ALLOWED = {
    ("SUPPLIER", "SUPPLIER_MASTER", "supplier_code"),
    ("SITE", "SITE_MASTER", "country"),
    ("MATERIAL", "MATERIAL_MASTER", "material_code"),
    ("RAW_MATERIAL", "RAW_MATERIAL_MASTER", "name_kor"),
    ("RAW_MATERIAL", "RAW_MATERIAL_MASTER", "raw_material_type"),
}


def _parse_ttc(ttc: str):
    """target_table_column → (table, column, value) 또는 None."""
    m = _TTC_RE.match(ttc or "")
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def _supplier_ref(row) -> SupplyRef:
    return SupplyRef(
        code=row["code"], nameKo=row["nameKo"] or row["code"],
        nameEng=row["nameEng"] or "", country=row["country"] or "",
        region=row["region"] or "",
    )


def _plain_ref(row) -> SupplyRef:
    """자재/원재료 등 country/region 없는 엔티티."""
    return SupplyRef(
        code=row["code"], nameKo=row["nameKo"] or row["code"],
        nameEng=row["nameEng"] or "",
    )


def get_tag_supply_chain(tag_id: str) -> Optional[TagSupplyChain]:
    """태그와 연결된 공급망 정보 조회. 비연결/미존재 태그는 None."""
    # 1) news DB: TAG_MASTER 에서 tag_type/name/첫 non-empty ttc (tag_id 단독, LIMIT 1)
    with get_news_db() as n:
        row = n.cursor().execute("""
            SELECT tag_type, name, target_table_column
            FROM TAG_MASTER
            WHERE tag_id = ? AND target_table_column IS NOT NULL
              AND target_table_column != '' LIMIT 1
        """, (tag_id,)).fetchone()
    if not row:
        return None

    parsed = _parse_ttc(row["target_table_column"])
    if not parsed:
        return None
    table, column, value = parsed
    tag_type = row["tag_type"]
    if (tag_type, table, column) not in _ALLOWED:
        return None

    result = TagSupplyChain(tagId=tag_id, tagType=tag_type, tagName=row["name"] or tag_id)

    # 2) supply_chain DB: tag_type 별 조인
    with get_supply_chain_db() as sc:
        cur = sc.cursor()
        if tag_type == "SUPPLIER":
            _supplier_chain(cur, result, value)
        elif tag_type == "SITE":
            _site_chain(cur, result, value)
        elif tag_type == "MATERIAL":
            _material_chain(cur, result, value)
        else:  # RAW_MATERIAL
            _raw_material_chain(cur, result, column, value)

    return result


def _supplier_chain(cur, result: TagSupplyChain, supplier_code: str) -> None:
    # 협력사 자기 자신
    cur.execute("""
        SELECT supplier_code AS code, name_kor AS nameKo, name_eng AS nameEng, country, region
        FROM SUPPLIER_MASTER WHERE supplier_code = ? AND is_active = 1
    """, (supplier_code,))
    result.suppliers = [_supplier_ref(r) for r in cur.fetchall()]

    # 거점
    cur.execute("""
        SELECT site_code AS code, name AS nameKo, '' AS nameEng, country, region
        FROM SITE_MASTER WHERE supplier_code = ? AND is_active = 1
    """, (supplier_code,))
    result.sites = [_supplier_ref(r) for r in cur.fetchall()]

    # 자재 (거점 경유)
    cur.execute("""
        SELECT DISTINCT mm.material_code AS code, mm.name_kor AS nameKo, mm.name_eng AS nameEng
        FROM SITE_MASTER st
        JOIN SITE_MATERIAL_MAP smm ON smm.site_code = st.site_code AND smm.is_active = 1
        JOIN MATERIAL_MASTER mm ON mm.material_code = smm.material_code AND mm.is_active = 1
        WHERE st.supplier_code = ? AND st.is_active = 1
    """, (supplier_code,))
    result.materials = [_plain_ref(r) for r in cur.fetchall()]

    # 원재료
    cur.execute("""
        SELECT DISTINCT rm.raw_material_code AS code, rm.name_kor AS nameKo, rm.name_eng AS nameEng
        FROM SUPPLIER_RAW_MATERIAL_MAP srm
        JOIN RAW_MATERIAL_MASTER rm ON rm.raw_material_code = srm.raw_material_code AND rm.is_active = 1
        WHERE srm.supplier_code = ? AND srm.is_active = 1
    """, (supplier_code,))
    result.rawMaterials = [_plain_ref(r) for r in cur.fetchall()]


def _site_chain(cur, result: TagSupplyChain, country: str) -> None:
    # 거점
    cur.execute("""
        SELECT site_code AS code, name AS nameKo, '' AS nameEng, country, region
        FROM SITE_MASTER WHERE country = ? AND is_active = 1
    """, (country,))
    result.sites = [_supplier_ref(r) for r in cur.fetchall()]

    # 협력사 (그 거점들의 supplier)
    cur.execute("""
        SELECT DISTINCT sup.supplier_code AS code, sup.name_kor AS nameKo, sup.name_eng AS nameEng,
               sup.country, sup.region
        FROM SITE_MASTER st
        JOIN SUPPLIER_MASTER sup ON sup.supplier_code = st.supplier_code AND sup.is_active = 1
        WHERE st.country = ? AND st.is_active = 1
    """, (country,))
    result.suppliers = [_supplier_ref(r) for r in cur.fetchall()]


def _material_chain(cur, result: TagSupplyChain, material_code: str) -> None:
    # 원재료
    cur.execute("""
        SELECT DISTINCT rm.raw_material_code AS code, rm.name_kor AS nameKo, rm.name_eng AS nameEng
        FROM MATERIAL_RAW_MATERIAL_MAP mr
        JOIN RAW_MATERIAL_MASTER rm ON rm.raw_material_code = mr.raw_material_code AND rm.is_active = 1
        WHERE mr.material_code = ? AND mr.is_active = 1
    """, (material_code,))
    result.rawMaterials = [_plain_ref(r) for r in cur.fetchall()]

    # 거점
    cur.execute("""
        SELECT DISTINCT st.site_code AS code, st.name AS nameKo, '' AS nameEng, st.country, st.region
        FROM SITE_MATERIAL_MAP smm
        JOIN SITE_MASTER st ON st.site_code = smm.site_code AND st.is_active = 1
        WHERE smm.material_code = ? AND smm.is_active = 1
    """, (material_code,))
    result.sites = [_supplier_ref(r) for r in cur.fetchall()]

    # 협력사 (거점 경유)
    cur.execute("""
        SELECT DISTINCT sup.supplier_code AS code, sup.name_kor AS nameKo, sup.name_eng AS nameEng,
               sup.country, sup.region
        FROM SITE_MATERIAL_MAP smm
        JOIN SITE_MASTER st ON st.site_code = smm.site_code AND st.is_active = 1
        JOIN SUPPLIER_MASTER sup ON sup.supplier_code = st.supplier_code AND sup.is_active = 1
        WHERE smm.material_code = ? AND smm.is_active = 1
    """, (material_code,))
    result.suppliers = [_supplier_ref(r) for r in cur.fetchall()]


def _raw_material_chain(cur, result: TagSupplyChain, column: str, value: str) -> None:
    # 1단계: raw_material_code 목록 해석 (column 은 화이트리스트 상수로만 분기)
    sql_col = "name_kor" if column == "name_kor" else "raw_material_type"
    cur.execute(f"""
        SELECT raw_material_code AS code, name_kor AS nameKo, name_eng AS nameEng
        FROM RAW_MATERIAL_MASTER WHERE {sql_col} = ? AND is_active = 1
    """, (value,))
    raw_rows = cur.fetchall()
    result.rawMaterials = [_plain_ref(r) for r in raw_rows]

    codes = [r["code"] for r in raw_rows]
    if not codes:
        return
    ph = ",".join("?" * len(codes))

    # 자재
    cur.execute(f"""
        SELECT DISTINCT mm.material_code AS code, mm.name_kor AS nameKo, mm.name_eng AS nameEng
        FROM MATERIAL_RAW_MATERIAL_MAP mr
        JOIN MATERIAL_MASTER mm ON mm.material_code = mr.material_code AND mm.is_active = 1
        WHERE mr.raw_material_code IN ({ph}) AND mr.is_active = 1
    """, tuple(codes))
    result.materials = [_plain_ref(r) for r in cur.fetchall()]

    # 협력사
    cur.execute(f"""
        SELECT DISTINCT sup.supplier_code AS code, sup.name_kor AS nameKo, sup.name_eng AS nameEng,
               sup.country, sup.region
        FROM SUPPLIER_RAW_MATERIAL_MAP srm
        JOIN SUPPLIER_MASTER sup ON sup.supplier_code = srm.supplier_code AND sup.is_active = 1
        WHERE srm.raw_material_code IN ({ph}) AND srm.is_active = 1
    """, tuple(codes))
    result.suppliers = [_supplier_ref(r) for r in cur.fetchall()]
