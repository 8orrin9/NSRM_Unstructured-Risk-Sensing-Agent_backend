"""
Backend configuration
"""
from pathlib import Path
import os
from dotenv import load_dotenv

# .env 파일 로드 (poc-a/ 디렉토리의 .env)
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# 서버 설정
PORT = 8007
HOST = "0.0.0.0"

# DB 경로 (backend/ 기준 상대 경로)
DB_PATH_NEWS = BASE_DIR / "data" / "NEWS" / "news_intelligence.db"
DB_PATH_SUPPLY_CHAIN = BASE_DIR / "data" / "SUPPLY_CHAIN" / "supply_chain.db"
DB_PATH_ONTOLOGY = BASE_DIR / "data" / "ONTOLOGY" / "ontology_layer.db"

# CORS 설정
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3007",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3007",
    # 배포된 frontend (Vercel)
    "https://frontend-cyan-ten-54.vercel.app",
]

# 환경변수 CORS_ORIGINS_EXTRA (쉼표 구분)로 추가 허용 origin 지정 가능
_extra = os.getenv("CORS_ORIGINS_EXTRA", "")
if _extra:
    CORS_ORIGINS += [o.strip() for o in _extra.split(",") if o.strip()]

# API 설정
API_PREFIX = "/api"

# 서빙 대상 파이프라인 run (full_run + golden). 그 외 run(isolated_* 등)은 노출 안 함.
SERVED_RUN_IDS = ["full_run_01", "golden_eval_20260715"]

# OpenAI API (Reporting 용)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
