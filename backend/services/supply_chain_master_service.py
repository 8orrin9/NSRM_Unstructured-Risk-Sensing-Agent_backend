"""
Supply Chain Master Service — 공급망 마스터 테이블 조회 (조회 전용)

supply_chain.db의 4개 마스터 테이블을 관리자 화면에 조회 노출한다.
- SELECT 전용: 쓰기 없음(commit 불필요). 원천 데이터는 별도 시스템/DBA가 관리.
- is_active = 1 활성 행만 반환.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List
from models.supply_chain_master import (
    RawMaterialRow, MaterialRow, SiteRow, SupplierRow,
)
from database.connection import get_supply_chain_db


def list_raw_materials() -> List[RawMaterialRow]:
    """원자재 활성 전체 조회."""
    with get_supply_chain_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT no, raw_material_code, name_kor, name_eng, raw_material_type
            FROM RAW_MATERIAL_MASTER
            WHERE is_active = 1
            ORDER BY no ASC
        """)
        return [RawMaterialRow(**dict(r)) for r in cursor.fetchall()]


def list_materials() -> List[MaterialRow]:
    """자재 활성 전체 조회."""
    with get_supply_chain_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT no, material_code, name_kor, name_eng, material_type
            FROM MATERIAL_MASTER
            WHERE is_active = 1
            ORDER BY no ASC
        """)
        return [MaterialRow(**dict(r)) for r in cursor.fetchall()]


def list_sites() -> List[SiteRow]:
    """거점 활성 전체 조회."""
    with get_supply_chain_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT no, site_code, supplier_code, name, country, region, latitude, longitude
            FROM SITE_MASTER
            WHERE is_active = 1
            ORDER BY no ASC
        """)
        return [SiteRow(**dict(r)) for r in cursor.fetchall()]


def list_suppliers() -> List[SupplierRow]:
    """협력사 활성 전체 조회."""
    with get_supply_chain_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT no, supplier_code, name_kor, name_eng, country, region, latitude, longitude
            FROM SUPPLIER_MASTER
            WHERE is_active = 1
            ORDER BY no ASC
        """)
        return [SupplierRow(**dict(r)) for r in cursor.fetchall()]
