"""
Pydantic models for Entity API (Frontend types.ts와 호환)
"""
from pydantic import BaseModel
from typing import List, Literal
from models.news import Severity


EntityType = Literal["supplier", "site", "material"]
EntityStatus = Literal["normal", "watch", "disrupted"]


class SupplyEntity(BaseModel):
    """공급망 거점 (Frontend SupplyEntity와 동일)"""
    id: str
    name: str
    nameKo: str
    type: EntityType
    tier: Literal[1, 2, 3]
    category: str
    country: str
    city: str
    lat: float
    lng: float
    criticality: Severity
    status: EntityStatus
    products: List[str]
    activeRiskIds: List[str]  # news ids currently affecting
