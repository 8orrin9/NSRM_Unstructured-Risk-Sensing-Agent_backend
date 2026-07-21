"""
Admin API Router — AI 핵심 인사이트(그룹) 노출 관리
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException
from typing import List
from models.news import AdminGroup, AdminDisplayRequest
from models.admin import (
    OpKeyword, OpKeywordCreate, OpTag, OpTagCreate, OpDeleteRequest,
    RecommendedKeyword, RecommendedTag,
)
from services.news_service import get_admin_groups, save_admin_group_display
from services.admin_service import (
    list_keywords, create_keyword, soft_delete_keywords, recommend_keywords,
    list_tags, create_tag, soft_delete_tags, recommend_tags,
)

router = APIRouter()


@router.get("/admin/groups", response_model=List[AdminGroup])
async def list_admin_groups():
    """검증된 전체 그룹(숨김 포함) + 노출 상태 조회"""
    try:
        return get_admin_groups()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch admin groups: {str(e)}")


@router.post("/admin/groups/display")
async def update_admin_group_display(req: AdminDisplayRequest):
    """노출 그룹 선택 저장 (shownIds 전체 명시)"""
    try:
        updated = save_admin_group_display(req.shownIds)
        return {"success": True, "updated": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save display: {str(e)}")


# ─── 뉴스 수집용 키워드 관리 (OP_KEYWORD) ──────────────────────────────────────

@router.get("/admin/keywords", response_model=List[OpKeyword])
async def list_admin_keywords():
    """활성 수집 키워드 전체 조회"""
    try:
        return list_keywords()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch keywords: {str(e)}")


@router.post("/admin/keywords", response_model=OpKeyword)
async def create_admin_keyword(req: OpKeywordCreate):
    """키워드 추가"""
    try:
        return create_keyword(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create keyword: {str(e)}")


@router.post("/admin/keywords/delete")
async def delete_admin_keywords(req: OpDeleteRequest):
    """키워드 다중 소프트 삭제 (is_active=0)"""
    try:
        deleted = soft_delete_keywords(req.ids)
        return {"success": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete keywords: {str(e)}")


@router.get("/admin/keywords/recommendations", response_model=List[RecommendedKeyword])
async def recommend_admin_keywords():
    """AI 추천 신규 키워드 (Risk 뉴스 반복 출현)"""
    try:
        return recommend_keywords()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recommend keywords: {str(e)}")


# ─── 태그 관리 (OP_TAG) ──────────────────────────────────────────────────────

@router.get("/admin/tags", response_model=List[OpTag])
async def list_admin_tags():
    """활성 태그 전체 조회"""
    try:
        return list_tags()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tags: {str(e)}")


@router.post("/admin/tags", response_model=OpTag)
async def create_admin_tag(req: OpTagCreate):
    """태그 추가 (EVENT 타입만 허용)"""
    try:
        return create_tag(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create tag: {str(e)}")


@router.post("/admin/tags/delete")
async def delete_admin_tags(req: OpDeleteRequest):
    """태그 다중 소프트 삭제 (is_active=0)"""
    try:
        deleted = soft_delete_tags(req.ids)
        return {"success": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete tags: {str(e)}")


@router.get("/admin/tags/recommendations", response_model=List[RecommendedTag])
async def recommend_admin_tags():
    """AI 추천 신규 태그 (파이프라인 EVENT 제안)"""
    try:
        return recommend_tags()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recommend tags: {str(e)}")
