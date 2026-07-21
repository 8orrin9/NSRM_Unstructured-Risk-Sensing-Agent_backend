"""
Pydantic models for 공급망 Database 마스터 조회 API (조회 전용)

supply_chain.db의 4개 마스터 테이블(RAW_MATERIAL_MASTER, MATERIAL_MASTER,
SITE_MASTER, SUPPLIER_MASTER) 조회 응답 모델. 관리자 화면 노출용으로
created_at/updated_at/is_active는 제외한다.
Frontend lib/types.ts (RawMaterialRow, MaterialRow, SiteRow, SupplierRow)와 호환.
"""
from pydantic import BaseModel
from typing import Optional


class RawMaterialRow(BaseModel):
    """원자재 (RAW_MATERIAL_MASTER 행)"""
    no: int
    raw_material_code: str
    name_kor: str
    name_eng: str
    raw_material_type: Optional[str] = None


class MaterialRow(BaseModel):
    """자재 (MATERIAL_MASTER 행)"""
    no: int
    material_code: str
    name_kor: str
    name_eng: str
    material_type: Optional[str] = None


class SiteRow(BaseModel):
    """거점 (SITE_MASTER 행)"""
    no: int
    site_code: str
    supplier_code: str
    name: str
    country: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SupplierRow(BaseModel):
    """협력사 (SUPPLIER_MASTER 행)"""
    no: int
    supplier_code: str
    name_kor: str
    name_eng: str
    country: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
