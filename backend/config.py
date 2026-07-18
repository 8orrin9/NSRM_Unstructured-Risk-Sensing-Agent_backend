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

# 추천 키워드/태그 집계 설정 (recommendation_service.py)
# - 키워드: Risk 뉴스에서 등장 뉴스 수 >= RECO_KEYWORD_THRESHOLD, 기존 Pool에 없음
# - 태그: 매핑 실패 키워드가 태그 형태로 등장 뉴스 수 >= RECO_TAG_THRESHOLD, EVENT 가능, 기존 태그와 비중복
RECO_KEYWORD_THRESHOLD = 5   # 키워드 등장 뉴스 수 임계값 (기존 recommend_keywords.py와 동일)
RECO_TAG_THRESHOLD = 3       # 태그 등장 뉴스 수 임계값 (unmatched 기반이라 키워드보다 희소)
RECO_TAG_DUP_SIMILARITY = 0.7  # 기존 EVENT 태그 이름과의 중복 판정 Jaccard 임계값
# EVENT 태그 부적합 추상어(블랙리스트) — Agent_2_Tag_Mapper/config.py 규칙 필터에서 가져옴
# (Agent_2 config는 패키지 __init__ 의존으로 서빙 계층에서 직접 import 불가하여 복제)
RECO_ABSTRACT_KEYWORD_BLACKLIST = ["제재", "규제", "리스크", "위기", "사건", "변동", "문제", "상황", "영향"]

# 뉴스 수집용 키워드 Pool 엑셀 (recommendation_service.load_existing_keyword_pool)
# 서빙 축소본에는 agents/가 없어 Agent_4 로직을 서빙 계층에서 복제 → 엑셀 경로만 여기서 지정
RECO_KEYWORD_SET_EXCEL_PATH = BASE_DIR / "data" / "TAG" / "DB_TAG_Risk Factor Pool_vF.xlsx"
RECO_KEYWORD_SET_SHEET_NAME = "2. Keyword Set_ai"
RECO_KEYWORD_COLUMN_INDEX = 5      # E열 (1-based)
RECO_TARGET_REGION_COLUMN_INDEX = 7  # G열 (1-based)
RECO_TARGET_REGION = "KR"

# OpenAI API (Reporting 용)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
