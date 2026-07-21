"""
Pydantic models for Tag → Supply Chain API (Frontend types.ts와 호환)
"""
from pydantic import BaseModel
from typing import List, Literal


class SupplyRef(BaseModel):
    """공급망 엔티티 참조 (협력사/거점/자재/원재료 공통)"""
    code: str          # supplier_code / site_code / material_code / raw_material_code
    nameKo: str
    nameEng: str = ""
    country: str = ""  # supplier / site 만
    region: str = ""   # supplier / site 만


class TagSupplyChain(BaseModel):
    """태그와 연결된 공급망 정보 (자재/원재료/협력사/거점)"""
    tagId: str
    tagType: Literal["SITE", "RAW_MATERIAL", "SUPPLIER", "MATERIAL"]
    tagName: str
    suppliers: List[SupplyRef] = []      # 협력사
    sites: List[SupplyRef] = []          # 거점
    materials: List[SupplyRef] = []      # 자재
    rawMaterials: List[SupplyRef] = []   # 원재료
