# vF_Deployment_Server Application

> **목적**: 개발 리포지토리(monorepo)에서 수정한 변경사항을 **운영 백엔드/프론트엔드 디렉토리에 반영**하는 절차를 정의한다.
> Claude Code가 "운영에 반영해줘" 요청을 받았을 때 **항상 이 문서를 먼저 확인**하고 따른다.
>
> 최종 갱신: 2026-07-18

---

## 1. 세 개의 리포지토리 (개발 ↔ 운영 분리)

이 프로젝트는 **개발용 monorepo 1개**와 **운영 배포용 리포 2개**로 나뉜다.
최신 코드 수정은 **항상 monorepo에서** 이뤄지고, 그 결과를 운영 리포 2개에 **반영(복사)** 한다.

| 구분 | 경로 | 역할 | git remote |
|------|------|------|-----------|
| **개발 (monorepo)** | `C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing` | 전체 소스·에이전트·스크립트·데이터의 원본(source of truth). poc-a / poc-b / shared 포함 | (기존 NSRM_Risk-Sensing) |
| **운영 백엔드** | `C:\Users\seokjjeong\Desktop\NSRM_Unstructured-Risk-Sensing-Agent` | FastAPI **서빙 전용** 축소 구조. Render 배포 대상 | `...NSRM_Unstructured-Risk-Sensing-Agent_backend.git` |
| **운영 프론트엔드** | `C:\Users\seokjjeong\Desktop\NSRM_Unstructured-Risk-Sensing-Agent_frontend` | Next.js. Vercel 배포 대상 | `...NSRM_Unstructured-Risk-Sensing-Agent_frontend.git` |

---

## 2. 디렉토리 매핑 (monorepo → 운영)

### 2-1. 백엔드

운영 백엔드는 **서빙에 필요한 것만** 담은 축소본이다. **`agents/`, `scripts/`, `test_*` 등은 운영에 존재하지 않으며, 서빙에도 사용되지 않는다.**

| monorepo 경로 | 운영 백엔드 경로 | 반영 대상? |
|---------------|-----------------|-----------|
| `poc-a/backend/main.py` | `backend/main.py` | ✅ 서빙 코드 |
| `poc-a/backend/config.py` | `backend/config.py` | ⚠️ **운영 전용 차이 있음 — 통째 덮어쓰기 금지** (§4) |
| `poc-a/backend/database/` | `backend/database/` | ✅ |
| `poc-a/backend/models/` | `backend/models/` | ✅ |
| `poc-a/backend/routers/` | `backend/routers/` | ✅ |
| `poc-a/backend/services/` | `backend/services/` | ✅ |
| `poc-a/data/NEWS/news_intelligence.db` | `data/NEWS/news_intelligence.db` | ✅ **서빙 DB (가장 흔한 반영 대상)** |
| `poc-a/data/SUPPLY_CHAIN/`, `poc-a/data/ONTOLOGY/` | `data/SUPPLY_CHAIN/`, `data/ONTOLOGY/` | ✅ 필요 시 |
| `poc-a/Markdown/vF_Docs/*.md` | `Markdown/vF_Docs/*.md` | ✅ 문서 동기화 시 |
| **`poc-a/backend/agents/**`** | **(없음)** | ❌ **반영 위치 없음. 서빙 무관** |
| **`poc-a/scripts/**`** | **(없음)** | ❌ **반영 위치 없음. 서빙 무관** |

> 운영 백엔드 `backend/` 하위에는 `config.py / main.py / database / models / routers / services`만 있다.
> monorepo에서 에이전트 코드(예: `Agent_4_Risk_Evaluator/...`)나 `scripts/db/*`를 수정했더라도 **운영 백엔드에 반영할 위치가 없고, 그 코드는 서빙에 관여하지 않는다.** 이런 변경의 실제 산출물은 대부분 **DB(`news_intelligence.db`)에 이미 반영**돼 있으므로, DB를 갱신하는 것이 곧 운영 반영이다.

### 2-2. 프론트엔드

운영 프론트엔드는 **monorepo의 `poc-a/frontend`와 1:1 대응**한다 (실측: `daily-news.tsx` 등 일치).

| monorepo 경로 | 운영 프론트 경로 | 반영 대상? |
|---------------|-----------------|-----------|
| `poc-a/frontend/app/` | `app/` | ✅ |
| `poc-a/frontend/components/` | `components/` | ✅ |
| `poc-a/frontend/lib/` | `lib/` | ✅ |
| `poc-a/frontend/public/` | `public/` | ✅ |
| `poc-a/frontend/*.config.*`, `package.json` 등 | 루트 동일 파일 | ✅ 의존성/설정 변경 시 |
| `.env.local` | `.env.local` | ⚠️ **운영 전용 — 덮어쓰기 금지** (§4) |

> **프론트엔드는 API로 데이터를 받는다.** 백엔드 DB만 바뀌고 프론트 소스 변경이 없다면 **프론트엔드에 반영할 파일은 없다** (DB 갱신 → API → 화면 자동 반영).

---

## 3. 반영 절차 (요청 유형별)

### 3-0. 공통 첫 단계 — "무엇이 실제로 바뀌었나" 확정
반영 대상 커밋/변경이 지목되면, **파일 목록을 먼저 분류**한다.
```bash
cd "C:/Users/seokjjeong/Desktop/NSRM_Risk-Sensing"
git show --stat <commit_hash>
```
각 변경 파일을 §2 매핑에 대입해 (a) 서빙 코드/데이터 → 반영, (b) `agents/`·`scripts/`·`test_*` → 반영 위치 없음(무시), (c) 운영 전용 설정 파일 → 덮어쓰기 금지로 나눈다.

### 3-A. DB 반영 (가장 흔함)
에이전트 재실행 등으로 `news_intelligence.db`가 바뀐 경우.

1. **운영 DB 백업** (덮어쓰기 전 필수)
   ```bash
   # 운영 data/NEWS/ 에 news_intelligence_backup_<timestamp>.db 로 복사
   ```
2. **테이블 단위 부분 교체 권장** — 전체 파일 통째 교체보다, 실제 바뀐 테이블/run만 교체하면 부작용이 적다.
   - 예: Agent_4 재실행 → `AGENT4_RISK_EVAL`에서 **서빙 대상 run만** (`SERVED_RUN_IDS`) `DELETE` 후 `INSERT` (idempotent).
   - 서빙 대상은 `backend/config.py`의 `SERVED_RUN_IDS = ["full_run_01", "golden_eval_20260715"]`. **비서빙 run(`isolated_*`)은 건드리지 않는다.**
3. **검증**: run별 행수 보존 + monorepo와 대상 run 완전 일치 + 비서빙 run 불변 확인.

> 파일 통째 교체가 필요하면(스키마 변경 등), 백업 후 monorepo DB로 덮어쓴다. 단 이 경우 서빙과 무관한 다른 테이블 변경까지 딸려옴을 인지한다.

### 3-B. 백엔드 서빙 코드 반영
`main.py / database / models / routers / services` 변경 시.

1. monorepo `poc-a/backend/<파일>` → 운영 `backend/<파일>` 복사.
2. **`config.py`는 예외** — §4 참조. 통째 복사 대신 **변경된 로직 부분만 수동 이식**.
3. 반영 후 운영 백엔드에서 import/기동 확인 (`.venv` 사용).

### 3-C. 프론트엔드 반영
`poc-a/frontend/<경로>` → 운영 프론트 `<경로>` 복사.
- **`.env.local`은 복사 금지** (§4).
- `package.json` 변경 시 운영 프론트에서 `npm install` 필요.

### 3-D. 문서 반영
`poc-a/Markdown/vF_Docs/*.md` → 운영 `Markdown/vF_Docs/*.md` 복사. (백엔드 리포에 문서 포함)

### 3-E. 반영 후 git (운영 리포)
- 운영 백엔드/프론트는 **각자의 remote**를 가진다 (§1). 커밋/푸시는 **사용자가 명시적으로 요청할 때만** 수행한다.
- monorepo의 브랜치 규칙(`CLAUDE.md`)과 운영 리포는 별개다. 운영 리포는 배포(Render/Vercel) 트리거와 연결될 수 있으므로 push 전 반드시 확인받는다.

---

## 4. 절대 규칙 / 주의점

1. **운영 전용 파일은 통째 덮어쓰지 않는다.** monorepo 값으로 덮으면 운영 설정이 깨진다.
   - `backend/config.py`: 운영은 **CORS에 배포 프론트 origin(`https://frontend-cyan-ten-54.vercel.app`)과 `CORS_ORIGINS_EXTRA` 환경변수 확장 로직**이 추가돼 있다. → **바뀐 로직만 수동 이식**, 통째 복사 금지.
   - `.env`, `.env.local`: 환경별 시크릿/URL. 운영 값 유지.
2. **`agents/`·`scripts/`는 운영에 반영하지 않는다.** 운영 백엔드에 해당 디렉토리가 없고 서빙에 쓰이지 않는다. 그 변경의 실제 효과는 DB에 있으므로 **DB 반영으로 대체**한다.
3. **DB는 반영 전 항상 백업**한다 (`data/NEWS/news_intelligence_backup_<ts>.db`).
4. **비서빙 run은 건드리지 않는다.** DB 부분 교체 시 `SERVED_RUN_IDS` 범위만.
5. **운영 리포 push는 사용자 확인 후에만.** 배포 자동 트리거 가능성.
6. **Windows: `python` 사용** (`python3` 금지 — MS Store 리다이렉터 회피). poc-a는 `.venv/Scripts/python.exe`.

---

## 5. 실행 기준 정보 (실측)

- **백엔드 서빙 포트**: `8007` (`config.py: PORT=8007`, `HOST=0.0.0.0`)
- **프론트 API URL**: `.env.local`의 `NEXT_PUBLIC_API_URL=http://localhost:8007/api`
- **서빙 대상 run**: `SERVED_RUN_IDS = ["full_run_01", "golden_eval_20260715"]`
- **서빙 DB**: `data/NEWS/news_intelligence.db` (+ `SUPPLY_CHAIN`, `ONTOLOGY`)
- **`.gitignore` 주의**: 운영 백엔드 `.gitignore`는 `*.log`, `.env`, `.venv/`만 제외한다. **DB(`*.db`)는 제외되지 않아 git으로 추적**된다 → DB 반영 후 운영 리포에 커밋하면 DB가 포함된다.

---

## 6. 반영 사례 로그

| 날짜 | 변경 내용 | 반영 결과 |
|------|-----------|-----------|
| 2026-07-18 | Agent_4 본문 전체 반영 재판정 (커밋 `77e6c30`, `68024b5`) | 실제 서빙 영향은 **`AGENT4_RISK_EVAL` 두 run(full_run_01 32건 + golden_eval 29건 = 61건)** 뿐. 운영 DB 백업 후 해당 run만 교체. Agent_4 소스/스크립트는 운영에 반영 위치 없어 미반영. `vF_Deployment.md`는 이미 동일. 프론트 소스 변경 없음. |
