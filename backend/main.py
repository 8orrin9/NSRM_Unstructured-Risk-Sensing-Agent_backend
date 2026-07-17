"""
FastAPI Backend for NSRM Risk-Sensing poc-a
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

# backend/ 디렉토리를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from config import CORS_ORIGINS, API_PREFIX
from routers import news, entities, reports

# FastAPI 앱 생성
app = FastAPI(
    title="NSRM Risk-Sensing API",
    description="Frontend-Backend 연동 REST API",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(news.router, prefix=API_PREFIX, tags=["News"])
app.include_router(entities.router, prefix=API_PREFIX, tags=["Entities"])
app.include_router(reports.router, prefix=API_PREFIX, tags=["Reports"])


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "NSRM Risk-Sensing API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from config import PORT, HOST

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )
