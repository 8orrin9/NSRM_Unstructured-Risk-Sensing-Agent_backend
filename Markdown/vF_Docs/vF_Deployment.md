# vF_Deployment — Frontend / Backend 배포 가이드

NSRM 비정형 Risk-Sensing Agent(poc-a)를 외부에서 접속 가능한 웹으로 배포하는 방법을 정리한다.
실제 배포 과정에서 겪은 함정과 그 회피법까지 포함했으므로, **순서대로 따라 하면 동일하게 재현**된다.

---

## 0. 전체 구조 한눈에

이 서비스는 **두 개의 앱**으로 나뉜다. 각각 다른 플랫폼에 배포한다.

```
[사용자 브라우저]
      │  ① 화면(HTML/JS) 다운로드
      ▼
[Vercel]  Next.js frontend          ← UI (화면)
      │  ② 화면의 JS가 데이터 요청  fetch(API_URL + "/news" ...)
      ▼
[Render]  FastAPI backend + SQLite  ← 데이터 (API)
      │  ③ DB 조회 후 JSON 응답
      ▼
   브라우저 화면에 데이터 표시
```

| 역할 | 호스팅 | 이유 |
|------|--------|------|
| **frontend** (Next.js) | **Vercel** | Next.js 전용 최적화(CDN·엣지). 무료, sleep 없음 |
| **backend** (FastAPI + SQLite) | **Render** | 상시 서버라 파일 DB·경로 문제 없음. FastAPI 그대로 구동 |

> **왜 backend를 Vercel에 안 올렸나?**
> Vercel serverless는 함수 번들 500MB 제한이 있고, 무거운 `requirements.txt`와 data 파일이 합쳐져
> 번들이 폭발(958MB)해 배포가 실패했다. `.vercelignore`로도 번들 크기는 통제되지 않았다.
> FastAPI + 32MB SQLite 조합은 **상시 서버(Render)가 훨씬 자연스럽다.**

---

## 1. 연동의 핵심 — 두 앱을 잇는 것은 "환경변수 하나"

두 앱은 물리적으로 연결돼 있지 않다. **frontend가 backend의 주소를 알고 그리로 HTTP 요청을 보내는 것**이 연동의 전부다.

- frontend는 `NEXT_PUBLIC_API_URL` 환경변수를 읽어 API를 호출한다.
  (코드: `frontend/lib/api-client.ts` → `const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '...'`)
- backend는 `CORS_ORIGINS`에 frontend 주소가 있어야 그 요청을 허용한다.
  (브라우저 보안상, 다른 도메인 간 요청은 backend가 명시적으로 허용해야 통과된다.)

```
Vercel(frontend)  NEXT_PUBLIC_API_URL = <Render backend 주소>/api   ← frontend가 어디로 요청할지
Render(backend)   CORS_ORIGINS 에 <Vercel frontend 주소> 포함        ← backend가 그 요청을 허용
```

---

## 2. Backend 배포 (Render)

### 2-1. 배포용 레포 준비

운영 레포는 파이프라인·KG 산출물·poc-b 등 불필요 파일이 많아 그대로 올리면 무겁다.
**서빙에 실제로 필요한 것만** 담은 별도 레포를 쓴다.

배포 레포에 담을 것 (총 ~32MB):
```
backend/          FastAPI 코드 (main.py, config.py, database/, models/, services/, routers/)
data/             서빙용 SQLite DB 3개
  NEWS/news_intelligence.db        (~32MB)
  ONTOLOGY/ontology_layer.db
  SUPPLY_CHAIN/supply_chain.db
requirements.txt  서빙 전용 경량 의존성 (아래 참고)
render.yaml       Render 배포 설정
.gitignore        .venv / __pycache__ / .env 제외
README.md
```

**넣지 않는 것**: KG 산출물(`insight_kg/`, `reports/` — 서빙 코드가 읽지 않음. 필요한 정보는 이미 DB에 정리돼 있음),
파이프라인(`agents/`, `scripts/`), 백업, frontend, `.venv`, `__pycache__`.

> **함정 ①: requirements.txt 를 반드시 경량화할 것.**
> 원본 requirements에는 selenium/konlpy/langgraph/lightrag 등 파이프라인용 무거운 패키지가 가득하다.
> 서빙 코드(routers/services)가 실제 import 하는 것은 아래 5개뿐이다.

**서빙 전용 `requirements.txt`:**
```
fastapi>=0.138.0
uvicorn[standard]>=0.49.0
pydantic>=2.13.0
openai>=2.0.0
python-dotenv>=1.2.0
```

> **함정 ②: requirements.txt 주석은 영문으로.**
> Windows에서 pip이 파일을 cp949로 읽어 한글 주석에서 `UnicodeDecodeError`가 날 수 있다.
> (Render(Linux)는 UTF-8이라 무관하지만, 로컬 테스트 호환을 위해 영문 권장.)

### 2-2. config.py 확인/수정

`backend/config.py`에서 두 가지를 확인한다.

- **DB 경로**: `BASE_DIR = Path(__file__).parent.parent` 기준 `data/`를 가리킨다.
  배포 레포도 `data/`가 루트 바로 아래라면 **수정 불필요**(원본 구조 유지).
- **CORS_ORIGINS**: 배포된 frontend 주소를 추가한다.
  ```python
  CORS_ORIGINS = [
      "http://localhost:3000",   # 로컬 개발용 (유지)
      # ...
      "https://<your-frontend>.vercel.app",   # 배포된 frontend
  ]
  # 환경변수로 추가 허용 origin 지정 (선택)
  _extra = os.getenv("CORS_ORIGINS_EXTRA", "")
  if _extra:
      CORS_ORIGINS += [o.strip() for o in _extra.split(",") if o.strip()]
  ```

### 2-3. render.yaml

```yaml
services:
  - type: web
    name: nsrm-risk-sensing-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    # main.py 가 sys.path 에 backend/ 를 넣고 top-level import 를 쓰므로 backend/ 안에서 실행
    startCommand: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: PYTHON_VERSION
        value: "3.12"
      - key: OPENAI_API_KEY      # 리포트 기능용. 대시보드에서 값 입력
        sync: false
      - key: CORS_ORIGINS_EXTRA  # 추가 CORS origin (선택)
        sync: false
```

### 2-4. 로컬 검증 (Render에 올리기 전에)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
cd backend
../.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8009
```
확인:
```bash
curl http://127.0.0.1:8009/health              # {"status":"healthy"}
curl http://127.0.0.1:8009/api/news/stats      # {"total":42,...}
```

### 2-5. GitHub push → Render 연결

1. 준비한 레포를 GitHub에 push (DB 포함 확인 — `git ls-files` 로 `.db` 3개가 보여야 함)
2. https://dashboard.render.com → **New +** → **Blueprint**
3. 해당 GitHub 레포 연결 → Render가 `render.yaml` 자동 인식 → **Apply**
4. 배포 중 환경변수 입력: `OPENAI_API_KEY` (없으면 조회 API는 정상, 리포트만 비활성)
5. 완료 후 URL 확보 (예: `https://nsrm-risk-sensing-api.onrender.com`)
6. 검증: 브라우저에서 `<backend-url>/health` → `{"status":"healthy"}`

> **함정 ③: Render 무료 플랜은 15분 미사용 시 sleep.**
> 다음 첫 요청 시 깨어나는 데 **30초~1분** 걸린다. 시연 직전에 미리 한 번 열어 깨워두면 좋다.
> 상시 필요하면 유료 플랜($7/월~)으로 sleep 제거.

---

## 3. Frontend 배포 (Vercel)

### 3-1. 최초 배포

```bash
cd frontend
vercel --yes      # 새 프로젝트로 생성됨. Next.js 자동 감지
```
→ Production URL 확보 (예: `https://frontend-xxxx.vercel.app`)

> 이 단계에서 화면은 뜨지만 **데이터는 안 나온다**. 아직 backend 주소를 모르기 때문(기본값 localhost).

### 3-2. 환경변수 연결 (연동의 핵심)

Vercel 대시보드 → **해당 frontend 프로젝트** → Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL = https://nsrm-risk-sensing-api.onrender.com/api
```

> **함정 ④: 값 끝에 `/api` 를 반드시 붙일 것.**
> frontend 코드는 `${API_BASE_URL}/news` 형태로 호출한다. `/api`가 없으면 `.../news`로 잘못 호출돼 404.
> - ✅ `https://nsrm-risk-sensing-api.onrender.com/api`
> - ❌ `https://nsrm-risk-sensing-api.onrender.com`

> **함정 ⑤: 환경변수는 반드시 frontend 프로젝트에 넣을 것.**
> (실수 사례) 초반에 만들었다 버린 backend용 Vercel 프로젝트에 넣으면 아무 효과가 없다.
> 대상이 **frontend 프로젝트**인지 확인.

### 3-3. 재배포 (필수)

> **함정 ⑥: `NEXT_PUBLIC_` 환경변수는 빌드 시점에 코드에 박힌다.**
> 환경변수만 바꾸고 재배포하지 않으면 기존 빌드(localhost 박힌 버전)가 그대로 서빙된다.
> **반드시 재배포해야 반영된다.**

```bash
cd frontend
vercel --prod     # 또는 Vercel 대시보드에서 Redeploy
```

---

## 4. 최종 검증

1. `<backend-url>/health` → `{"status":"healthy"}`
2. 브라우저에서 frontend URL 접속 → 화면에 **뉴스/엔티티 데이터가 표시**되면 연동 성공
3. 안 뜨면 브라우저 개발자도구(F12) → Network/Console 확인:
   - `404` → `/api` 누락 (함정 ④)
   - `CORS` 에러 → backend `CORS_ORIGINS`에 frontend 주소 누락 (2-2)
   - 응답이 30초~1분 지연 후 정상 → Render sleep에서 깨어나는 중 (함정 ③, 정상)

---

## 5. 사내망 참고 (TLS 프록시)

사내 네트워크는 HTTPS를 검사하는 프록시가 있어, CLI(`vercel`, `curl`)에서
`self-signed certificate in certificate chain` 에러가 날 수 있다.

- **임시 회피**(로그인/배포 시): PowerShell에서 `$env:NODE_TLS_REJECT_UNAUTHORIZED="0"` 설정 후 명령 실행.
  작업 끝나면 `Remove-Item Env:NODE_TLS_REJECT_UNAUTHORIZED` 로 복구.
- 이는 **로컬 CLI 통신에만** 해당한다. 실제 배포된 Vercel↔Render, 브라우저↔서버 통신은
  정상 인증서라 영향 없다.

---

## 6. 보안 주의

- **API 키(`OPENAI_API_KEY`)는 절대 git에 커밋하지 않는다.** `.env`는 `.gitignore`에 포함.
- 키는 **Render 환경변수**에만 저장한다.
- 키가 노출되면 즉시 폐기(Revoke) 후 재발급.

---

## 부록: 현재 배포 정보 (2026-07 기준)

| 항목 | 값 |
|------|-----|
| backend (Render) | `https://nsrm-risk-sensing-api.onrender.com` |
| backend 레포 | `github.com/8orrin9/NSRM_Unstructured-Risk-Sensing-Agent_backend` |
| frontend (Vercel) | `https://frontend-cyan-ten-54.vercel.app` |
| API prefix | `/api` |
| 헬스체크 | `/health` |
