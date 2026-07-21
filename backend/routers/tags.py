"""
Tags API Router
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException
from models.tag_supply import TagSupplyChain
from services.tag_supply_service import get_tag_supply_chain

router = APIRouter()


@router.get("/tags/{tag_id}/supply-chain", response_model=TagSupplyChain)
async def tag_supply_chain(tag_id: str):
    """특정 태그와 연결된 공급망 정보(자재/원재료/협력사/거점) 조회"""
    try:
        result = get_tag_supply_chain(tag_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tag supply chain: {str(e)}")
    if result is None:
        raise HTTPException(status_code=404, detail="Tag not linkable or not found")
    return result
