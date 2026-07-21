"""
Admin API Router — AI 핵심 인사이트(그룹) 노출 관리
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException
from typing import List
from models.news import AdminGroup, AdminDisplayRequest
from services.news_service import get_admin_groups, save_admin_group_display

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
