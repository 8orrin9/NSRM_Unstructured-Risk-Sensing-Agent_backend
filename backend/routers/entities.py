"""
Entities API Router
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from models.entity import SupplyEntity, EntityStatus
from models.news import NewsItem
from services.entity_service import get_entities, get_entity_news

router = APIRouter()


@router.get("/entities", response_model=List[SupplyEntity])
async def list_entities(
    status: Optional[EntityStatus] = Query(None, description="Status 필터"),
    tier: Optional[int] = Query(None, ge=1, le=3, description="Tier 필터"),
):
    """공급망 거점 목록 조회"""
    try:
        entities = get_entities(status=status, tier=tier)
        return entities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch entities: {str(e)}")


@router.get("/entities/{entity_id}/news", response_model=List[NewsItem])
async def get_entity_related_news(entity_id: str):
    """특정 거점과 관련된 뉴스 조회"""
    try:
        news_items = get_entity_news(entity_id)
        return news_items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch entity news: {str(e)}")
