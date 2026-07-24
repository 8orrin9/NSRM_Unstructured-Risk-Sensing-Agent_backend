"""
Reports API Router
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from openai import AsyncOpenAI
from config import OPENAI_API_KEY
from services.news_service import get_news_by_id

router = APIRouter()


class ReportRequest(BaseModel):
    """리포트 생성 요청"""
    newsIds: List[str]
    recipient: Optional[str] = None
    sender: Optional[str] = None
    tone: Optional[str] = None
    instruction: Optional[str] = None


# Risk Category 한글 매핑
RISK_CATEGORIES_KO = {
    "geopolitical": "지정학적",
    "supply": "공급 중단",
    "material": "원자재",
    "tech": "기술/IP",
    "logistics": "물류/인프라",
    "cyber": "사이버/데이터",
    "esg": "ESG/규제",
    "financial": "재무/신용",
    "disaster": "재난/기후"
}

# Severity 한글 매핑 (3단 체계: High/Medium/Low)
SEVERITY_KO = {
    "high": "높음",
    "medium": "보통",
    "low": "낮음"
}


@router.post("/reports/generate")
async def generate_report(request: ReportRequest):
    """
    AI 리포트 생성 (스트리밍)
    OpenAI API를 사용하여 선택된 뉴스를 기반으로 리포트 생성
    """
    # API 키 확인
    if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY가 설정되지 않았거나 올바르지 않습니다."
        )

    # 선택된 뉴스 조회
    selected_news = []
    for news_id in request.newsIds:
        try:
            news = get_news_by_id(news_id)
            if news:
                selected_news.append(news)
        except Exception as e:
            print(f"Failed to fetch news {news_id}: {e}")
            continue

    if not selected_news:
        raise HTTPException(status_code=400, detail="선택된 뉴스를 찾을 수 없습니다.")

    # 뉴스 컨텍스트 생성
    context = "\n\n".join([
        f"""[뉴스 {i + 1}]
- 제목: {news.title}
- 카테고리: {RISK_CATEGORIES_KO.get(news.category, news.category)}
- 심각도: {SEVERITY_KO.get(news.severity, news.severity)} (영향도 {news.impactScore}/100)
- 출처: {news.source}
- 관련 공급망 생산지: {', '.join(news.relatedEntityIds) if news.relatedEntityIds else '없음'}
- 요약: {news.summary}
- 상세: {news.detail}"""
        for i, news in enumerate(selected_news)
    ])

    # 시스템 프롬프트
    system_prompt = """당신은 글로벌 반도체 제조사의 공급망 리스크 관리(SCRM) 애널리스트입니다.
수집된 리스크 뉴스를 바탕으로 경영진에게 보고할 간결하고 실행 가능한 리포트 초안을 작성합니다.
- 반드시 한국어로 작성합니다.
- 출력은 Markdown 형식입니다.
- 다음 구조를 따릅니다:
  # 공급망 리스크 리포트
  ## 1. 핵심 요약 (Executive Summary) — 3~4문장
  ## 2. 주요 리스크 상세 — 뉴스별 소제목과 영향 분석
  ## 3. 공급망 영향 평가 — 관련 생산지/의존도 관점
  ## 4. 권고 조치 (Recommended Actions)
- 번호 목록(1., 2., 3. ...)의 각 항목은 한 줄짜리 핵심 제목으로 쓰고,
  구체적인 실행 내용·근거·기한 등은 반드시 그 번호 항목 아래에 들여쓴 불렛포인트(- )로 2~4개씩 작성합니다.
  예시:
  1. **단기 대응 (0~2주)**
     - 대체 공급사 A/B에 긴급 견적 요청
     - 안전재고 4주분 확보 검토
- 과장 없이 사실 기반으로, 불확실성은 명시합니다."""

    # 사용자 프롬프트
    user_prompt = f"""아래는 오늘 수집된 공급망 리스크 뉴스입니다.
{f"발신: {request.sender}" if request.sender else ""}
{f"수신: {request.recipient}" if request.recipient else ""}
{f"작성 톤: {request.tone}" if request.tone else ""}
{f"추가 지시사항: {request.instruction}" if request.instruction else ""}

{context}

위 내용을 종합하여 리포트 초안을 Markdown으로 작성하세요."""

    # OpenAI 클라이언트 생성
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    async def stream_response():
        """OpenAI 스트리밍 응답"""
        try:
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_msg = f"\n\n[오류] 리포트 생성 실패: {str(e)}\n"
            yield error_msg

    return StreamingResponse(
        stream_response(),
        media_type="text/plain",
    )
