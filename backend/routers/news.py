"""
News API Router
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from models.news import NewsItem, NewsGroup, NewsStats, Severity
from services.news_service import get_news_list, get_news_by_id, get_news_groups, get_news_stats

router = APIRouter()


@router.get("/news/stats", response_model=NewsStats)
async def get_stats():
    """뉴스 통계 조회"""
    try:
        stats = get_news_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/news/groups", response_model=List[NewsGroup])
async def list_groups():
    """뉴스 그룹 목록 조회"""
    try:
        groups = get_news_groups()
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch groups: {str(e)}")


@router.get("/news", response_model=List[NewsItem])
async def list_news(
    severity: Optional[Severity] = Query(None, description="Severity 필터"),
    risk_factor: Optional[str] = Query(None, description="Risk Factor 필터"),
    limit: int = Query(100, ge=1, le=1000, description="최대 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
    domestic_only: bool = Query(False, description="국내 기사만 조회 (NAVER_NEWS)"),
):
    """뉴스 목록 조회"""
    try:
        news_items = get_news_list(
            severity=severity,
            risk_factor=risk_factor,
            limit=limit,
            offset=offset,
            domestic_only=domestic_only,
        )
        return news_items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch news: {str(e)}")


@router.get("/news/{news_id}", response_model=NewsItem)
async def get_news(news_id: str):
    """특정 뉴스 조회"""
    news = get_news_by_id(news_id)
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    return news
