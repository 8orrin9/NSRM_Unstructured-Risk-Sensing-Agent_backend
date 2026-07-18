"""
Pydantic models for News API (Frontend types.ts와 호환)
"""
from pydantic import BaseModel
from typing import List, Literal, Optional
from datetime import datetime


# Frontend Severity 타입과 동일
Severity = Literal["critical", "high", "medium", "low"]

# Frontend RiskCategory 타입과 동일
RiskCategory = Literal[
    "geopolitical",
    "supply",
    "material",
    "tech",
    "logistics",
    "cyber",
    "esg",
    "financial",
    "disaster"
]

# Frontend RiskFactor 타입과 동일
RiskFactor = Literal[
    "geopolitical_regulatory",
    "supply_singlesource",
    "rawmaterial_critical",
    "tech_ip",
    "logistics_infra",
    "cyber_data",
    "esg_compliance",
    "financial_credit",
    "disaster_climate"
]


class NewsItem(BaseModel):
    """뉴스 아이템 (Frontend NewsItem과 동일)"""
    id: str
    title: str
    source: str
    publishedAt: str  # ISO 8601
    category: RiskCategory
    severity: Severity
    summary: str
    detail: str = ""  # 목록 조회에서는 빈 문자열, 개별 조회에서만 전체 본문
    keywords: List[str]
    recommendedKeywords: List[str]  # 신규 Pool 추천 키워드
    tags: List[str]  # 리스크 태그
    recommendedTags: List[str] = []  # 신규 EVENT 태그 추천 (매핑 실패 키워드 기반)
    relatedEntityIds: List[str]
    region: str
    url: str
    impactScore: int  # 0-100
    riskJustification: str = ""  # AI 리스크 판단 근거 (AGENT4.risk_justification)
    isRisk: bool = False  # AGENT4.is_risk — Individual News 노출 게이트용


class NewsGroup(BaseModel):
    """뉴스 그룹 (Frontend NewsGroup과 동일)"""
    id: str
    title: str
    newsIds: List[str]
    rationale: str
    status: Literal["active", "dissolving"]


class ResolvedGroup(BaseModel):
    """해결된 그룹 (Frontend ResolvedGroup과 동일)"""
    id: str
    title: str
    rationale: str
    status: Literal["active", "dissolving"]
    items: List[NewsItem]
    severity: Severity
    category: RiskCategory
    isRisk: bool
    relatedEntityIds: List[str]
    latestAt: str
    earliestAt: str


class NewsStats(BaseModel):
    """뉴스 통계"""
    total: int
    critical: int
    high: int
    medium: int
    low: int
    groups: int


class KeywordPoolItem(BaseModel):
    """키워드 Pool 아이템"""
    keyword: str
    addedAt: str
    source: Literal["recommended", "manual"]
