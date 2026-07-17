# NSRM Unstructured Risk-Sensing Agent — Backend API

비정형 Risk 센싱 Agent의 FastAPI 백엔드. 뉴스 인텔리전스 파이프라인 산출물(SQLite)을
프론트엔드에 REST API로 서빙한다.

## 구성

```
backend/          FastAPI 애플리케이션
  main.py         앱 진입점 (app 객체)
  config.py       DB 경로 · CORS · API 설정
  database/       SQLite 연결
  models/         Pydantic 스키마
  services/       DB 조회 로직
  routers/        API 엔드포인트 (news / entities / reports)
data/             서빙용 SQLite DB (읽기 전용)
  NEWS/           news_intelligence.db
  ONTOLOGY/       ontology_layer.db
  SUPPLY_CHAIN/   supply_chain.db
requirements.txt  서빙 전용 경량 의존성
render.yaml       Render 배포 설정
```

## 로컬 실행

```bash
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8007
```

- API 문서: http://localhost:8007/docs
- 헬스 체크: http://localhost:8007/health

## 배포 (Render)

`render.yaml` 기반 Blueprint 배포. Render 대시보드에서 이 레포를 연결하면 자동 인식된다.

환경변수:
- `OPENAI_API_KEY` — 리포트 생성 기능용 (없으면 조회 API는 정상, 리포트만 비활성)
- `CORS_ORIGINS_EXTRA` — 추가 허용 origin (쉼표 구분, 선택)

프론트엔드는 별도로 Vercel에 배포되며, `NEXT_PUBLIC_API_URL`을 이 백엔드의 배포 URL로 지정한다.
