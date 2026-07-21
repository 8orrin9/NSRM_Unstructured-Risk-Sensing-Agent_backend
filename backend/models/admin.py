"""
Pydantic models for Admin 관리 API (키워드/태그 관리)

OP_KEYWORD / OP_TAG 운영 테이블 CRUD 및 AI 추천 응답 모델.
Frontend lib/types.ts (OpKeyword, OpTag, RecommendedKeyword, RecommendedTag)와 호환.
"""
from pydantic import BaseModel
from typing import List, Optional


# ─── OP_KEYWORD ────────────────────────────────────────────────────────────

class OpKeyword(BaseModel):
    """뉴스 수집용 키워드 (OP_KEYWORD 행)"""
    id: int
    risk_category_code: Optional[str] = None
    risk_category_name: Optional[str] = None
    risk_factor: Optional[str] = None
    keyword_group_name: Optional[str] = None
    keyword: Optional[str] = None
    target_region: Optional[str] = None
    description: Optional[str] = None
    source: str = "excel"


class OpKeywordCreate(BaseModel):
    """키워드 추가 요청 (id/생성시각 제외)"""
    risk_category_code: Optional[str] = None
    risk_category_name: Optional[str] = None
    risk_factor: Optional[str] = None
    keyword_group_name: Optional[str] = None
    keyword: str
    target_region: Optional[str] = None
    description: Optional[str] = None


# ─── OP_TAG ──────────────────────────────────────────────────────────────────

class OpTag(BaseModel):
    """태그 (OP_TAG 행)"""
    id: int
    tag_id: Optional[str] = None
    target_region: Optional[str] = None
    tag_type: Optional[str] = None
    name: Optional[str] = None
    domain: Optional[str] = None
    risk_factor: Optional[str] = None
    keyword_count: Optional[int] = None
    keywords_full: Optional[str] = None
    description: Optional[str] = None
    target_table_column: Optional[str] = None
    db_matched_count: Optional[int] = None
    source: str = "excel"


class OpTagCreate(BaseModel):
    """태그 추가 요청 (id/생성시각 제외). EVENT 타입만 허용(서버에서 강제)."""
    tag_id: Optional[str] = None
    target_region: Optional[str] = None
    tag_type: str = "EVENT"
    name: str
    domain: Optional[str] = None
    risk_factor: Optional[str] = None
    keyword_count: Optional[int] = None
    keywords_full: Optional[str] = None
    description: Optional[str] = None
    target_table_column: Optional[str] = None
    db_matched_count: Optional[int] = None


# ─── 공용 ────────────────────────────────────────────────────────────────────

class OpDeleteRequest(BaseModel):
    """다중 소프트 삭제 요청 — 비활성화할 행 id 목록"""
    ids: List[int]


# ─── AI 추천 ─────────────────────────────────────────────────────────────────

class RecommendedKeyword(BaseModel):
    """AI 추천 신규 키워드 (Risk 뉴스 반복 출현 키워드)"""
    keyword: str
    count: int


class RecommendedTag(BaseModel):
    """AI 추천 신규 태그 (파이프라인 EVENT 태그 제안)"""
    name: str
    tag_type: str = "EVENT"
    risk_factor: Optional[str] = None
    description: Optional[str] = None
    keywords_full: Optional[str] = None
