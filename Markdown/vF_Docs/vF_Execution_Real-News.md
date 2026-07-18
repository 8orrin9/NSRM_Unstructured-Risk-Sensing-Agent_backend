# 실제 수집 뉴스 기반 5-Agent 파이프라인 실행 & DB 적재

> 작성일: 2026-07-15
> 대상 DB: `data/NEWS/news_intelligence.db`
> 관련 문서: [`vF_GoldenDataset_Evaluation-Methodology.md`](./vF_GoldenDataset_Evaluation-Methodology.md)

---

## 1. 목적 (Why)

poc-a의 5-Agent 뉴스 Risk-Sensing 파이프라인을 **실제 수집 뉴스**로 돌리고, 각 Agent의 출력물을 `news_intelligence.db`에 구조적으로 적재한다.

지금 보유한 데이터는 실제 수집 뉴스라 **정답 라벨이 없어** 정식 평가(`vF_GoldenDataset_Evaluation-Methodology.md`)를 바로 수행할 수 없다. 대신 각 Agent의 예측 출력을 **평가지표 계산이 가능한 형태**로 DB에 적재해두어, 추후 가짜뉴스 골든데이터셋 평가 결과와 비교할 토대를 만든다.

### 핵심 제약
- 파이프라인(`run_full_pipeline.py`)을 테스트로 여러 번 돌려도 **기존 데이터가 덮어써지면 안 됨** → `run_id` 배치 태깅으로 append-only 누적.
- DB 스키마가 여러 번 변경되어 기존 Agent/로더 코드와 맞지 않음 → 코드 수정 필요.

---

## 2. 파이프라인 구조

### 2.1 Agent 실행 순서 (JSON 파일로 데이터 전달)

```
Agent1 (News Analyzer) → Agent5 (News Grouper) → Agent2 (Tag Mapper)
   → Agent3 (DB Searcher) → Agent4 (Risk Evaluator)
```

| Agent | 역할 | 입력 | 출력 JSON |
|-------|------|------|-----------|
| **Agent_1** News Analyzer | 번역·요약·키워드·FP 필터링 | `NEWS_MASTER` (is_active=1) | `output_news_analyzer.json` |
| **Agent_5** News Grouper | KG 매핑·뉴스 그룹핑·인사이트 | Agent1의 `is_relevant=True` | `output_news_grouper.json` |
| **Agent_2** Tag Mapper | Risk Factor 태그 매핑 | Agent5의 `documents_for_next_agents` | `output_tag_mapper.json` |
| **Agent_3** DB Searcher | 리스크 시나리오·SQL 생성/검색 | Agent2의 태그 매핑 뉴스 | `output_db_searcher.json` |
| **Agent_4** Risk Evaluator | Risk 평가·이벤트 시점·이슈 분류 | Agent3 출력 | `output_risk_evaluator.json` |

### 2.2 데이터 흐름의 감소 패턴 (정상 동작)

각 단계에서 처리 건수가 줄어드는 것은 **설계상 정상**이다.

```
Agent_1 처리 (전체)
  └→ is_relevant=True 만 Agent_5로 (False Positive 필터링으로 감소)
       └→ documents_for_next_agents = 통합문서 + 개별문서
            (그룹 뉴스는 통합문서로도, 개별문서로도 이중 전달)
            └→ Agent_3는 태그가 매핑된 문서(mapped_tags>0)만 처리
```

**중요 — 그룹 뉴스의 이중 처리:** Agent_5는 그룹에 속한 뉴스를 두 방식으로 다음 Agent에 전달한다.
1. 그룹 단위 **통합문서**(`is_grouped=True`) 1건
2. 각 뉴스의 **개별문서** (그룹 소속 여부와 무관하게 모두)

즉 그룹 뉴스는 "그룹으로 합쳐진 관점"과 "개별 관점" 모두로 평가된다. Agent_5 러너 코드(`documents_for_next_agents` 생성부)가 이를 보장한다.

---

## 3. 작업 내용 (What & How)

### 3.1 사용자 확정 결정
1. 빈 테이블 7개 **전면 재설계** (DROP 후 신 스키마 재생성).
2. **run_id 배치 태깅** 안전장치.
3. **사후 로더 유지** (Agent는 JSON 출력 → 별도 load 스크립트가 DB 적재).
4. **5개 Agent 모두 적재**.
5. Agent1 정본 뉴스 = **NEWS_MASTER 115행** (신 슬림 스키마).
6. 구 로더 8개는 **backup/으로 이동 후** 신규 작성.

### 3.2 발견·해결한 블로커

| # | 문제 | 해결 |
|---|------|------|
| **C1** | `NEWS_MASTER`(115행)에 `agent*_processed_at`·`category`·`_ko` 컬럼 없음(구 컬럼은 `NEWS_MASTER_OLD`에만). 기존 러너의 processed_at 필터/UPDATE가 크래시 | processed_at 로직 전면 제거, run_id 배치 방식으로 전환 |
| **C2** | Agent1/3/4/5 러너의 `json.dump`가 주석 처리됨. Agent3/4/5는 `TEST_MODE=True` 하드코딩 | `json.dump` 활성화 + `TEST_MODE`를 `PIPELINE_TEST_MODE` 환경변수로 전환(기본 False=전체) |
| **C3** | Agent4 stale JSON이 단일 시나리오 레거시 구조 | 로더는 최신 필드 기준 설계 + 레거시 필드 `.get()` 폴백 |
| **C4** | Agent4 `config.py`의 `AGENT3_OUTPUT_FILE`이 `dev/...` 경로(존재 안 함) | `backend/agents/Agent_3_DB_Searcher/output/...`로 수정 |
| **C5** | 마스터 오케스트레이터가 `from dev.Agent_1_...` 참조 + Agent1만 실행 | 전면 재작성(run_id 생성·subprocess 순차 실행) |

### 3.3 신규 DB 스키마 (12개 테이블)

공통 규칙: 모든 산출 테이블에 `run_id TEXT NOT NULL`, `created_at`, surrogate PK(`id AUTOINCREMENT`), 인덱스 `(run_id, news_id)`. 평가지표에 직접 쓰이는 값은 **조회 가능한 컬럼**, 부피 크고 지표에 안 쓰는 값은 **JSON blob(TEXT)**. NEWS_MASTER/TAG_MASTER로의 FK·CHECK 제약 없음(그룹 합성 news_id·값 도메인 변동 대응).

| 테이블 | 단위 | 핵심 컬럼 → 연결 지표 |
|--------|------|----------------------|
| **PIPELINE_RUN** | run 1행 | run_id PK, status(RUNNING/SUCCESS/FAILED/PARTIAL), news_count, agent1~5 count, started/finished_at |
| **AGENT1_ANALYSIS** | 뉴스 | is_relevant, relevance_score, title_ko, summary_ko → **FP P/R** |
| **AGENT1_KEYWORD** | 키워드 | keyword, score, rank → **Keyword P/R** |
| **AGENT5_GROUP** | 그룹 | group_name, group_theme, risk_perspectives, aggregate_confidence |
| **AGENT5_GROUP_MEMBER** | 그룹-뉴스 | group_id, news_id, shared_entities |
| **AGENT5_ENTITY** | 엔티티 | entity, entity_type, match_method, matched_kg_entity → **entity P/R** |
| **AGENT5_UNIFIED_DOC** | 통합문서 | original_news_ids, shared_entities, group_insight (재현용) |
| **AGENT2_DOC** | 뉴스 | mapping_quality_score, requires_hitl, is_grouped, original_news_ids |
| **AGENT2_TAG** | 태그 | keyword, tag_id, tag_type, confidence, match_bucket → **Tag Accuracy** |
| **AGENT3_SEARCH** | 뉴스 | search_strategy_id, fallback_strategy_used, scenario_count, total_result_count |
| **AGENT3_SCENARIO** | 시나리오 | risk_scenario, impact_level, sql, result_count, had_error → **DB Search Error Rate** |
| **AGENT4_RISK_EVAL** | 뉴스 | is_risk, risk_score, event_timing, issue_type, issue_priority → **Specificity/Timing/Routing/Critical Miss** |

- DROP 대상(구 빈 테이블 7개 + 트리거): `NEWS_GROUP_MEMBERSHIP`, `NEWS_GROUP`, `NEWS_ENTITY_EXTRACTION`, `NEWS_RISK_EVALUATION`, `AGENT_DB_SEARCH_LOG`, `NEWS_TAG_MAP`, `NEWS_KEYWORD_EXTRACTION`, trigger `update_group_last_news`.

### 3.4 안전장치 (run_id 배치 태깅)

```
오케스트레이터가 run_id 생성 (YYYYMMDD_HHMMSS_<uuid6>)
  → PIPELINE_RUN(RUNNING) INSERT
  → os.environ["PIPELINE_RUN_ID"] 설정
  → 각 러너가 출력 JSON 최상위에 "run_id" 기록
  → 로더가 JSON에서 run_id 읽어 DELETE FROM <table> WHERE run_id=? 후 INSERT
```

- **같은 run_id 재실행** → 해당 배치만 clean re-load (덮어쓰기, 중복 없음).
- **다른 run_id 실행** → 기존 배치 그대로 보존 + 새 배치 누적(append-only).

### 3.5 오케스트레이터 (subprocess 순차 실행)

5개 러너가 동일 모듈명(`graph`/`nodes`/`config`)을 각자 `sys.path` 조작으로 import하므로, 동일 프로세스에서 import하면 충돌한다. 따라서 각 러너·로더를 **별도 subprocess**로 격리 실행한다.

```
Agent1 → 로더1 → Agent5 → 로더5 → Agent2 → 로더2 → Agent3 → 로더3 → Agent4 → 로더4
```

단계 실패 시 `PIPELINE_RUN.status=FAILED` 기록 후 중단. 성공 시 count/finished_at/SUCCESS 갱신.

CLI: `--run-id`, `--from-agent N`, `--skip-loaders`.

### 3.6 변경/생성 파일 목록

**신규/재작성**
- `scripts/db/create_agent_tables.py` — 전면 재작성 (DROP 7개 + CREATE 12개, `--recreate`/`--drop-only`)
- `scripts/db/loader_common.py` — 로더 공통 유틸 (resolve_run_id/clear_run/as_json 등)
- `scripts/db/load_agent_1~5.py` — 신규 사후 로더 5개
- `backend/agents/scripts/run_full_pipeline.py` — 마스터 오케스트레이터 재작성

**수정 (러너 5개)**
- 공통: 출력 JSON에 `run_id` 기록, `json.dump` 활성화
- `Agent_1`: processed_at 로직·merge 제거(C1), `PIPELINE_TEST_MODE` 분기 추가
- `Agent_2/3/4/5`: `TEST_MODE`를 `PIPELINE_TEST_MODE` 환경변수로 전환
- `Agent_4/config.py`: `AGENT3_OUTPUT_FILE` 경로 수정(C4)

**이동 (backup/scripts/db/)**
- 구 로더 8개 + `fix_news_tag_map_schema.py`

---

## 4. 실행 런북

```bash
# 1. DB 백업
python scripts/db/backup_news_db.py

# 2. 신 스키마 재생성 (빈 테이블 7개 DROP + 신규 12개 CREATE)
python scripts/db/create_agent_tables.py --recreate

# 3-a. 샘플 스모크 테스트 (각 Agent 상위 30건만)
PIPELINE_TEST_MODE=1 python backend/agents/scripts/run_full_pipeline.py --run-id smoke_test_01

# 3-b. 전체 실행 (115건 전체, run_id 자동 생성)
python backend/agents/scripts/run_full_pipeline.py

# 4. 재실행 안전성 검증 (기존 run_id 보존, 새 배치 누적)
python backend/agents/scripts/run_full_pipeline.py
```

> Windows에서는 `python3`이 아닌 `python` 사용. 콘솔 한글 깨짐 방지를 위해 `PYTHONIOENCODING=utf-8` 권장.

---

## 5. 검증 결과

### 5.1 스키마 재생성
- 기존 빈 테이블 7개(모두 0행) DROP, 신규 12개 CREATE 완료.
- 유지 테이블: `NEWS_MASTER`(115), `NEWS_MASTER_OLD`(1235), `TAG_MASTER`(262), `TAG_KEYWORD_MAP`(717), `INSIGHT_REPORT_MASTER`(160).

### 5.2 스모크 테스트 (`run_id=smoke_test_01`, 21:03~21:24, 약 20분)

`PIPELINE_TEST_MODE=1` (각 Agent 상위 30건) — **status=SUCCESS**

| 테이블 | 적재 행수 |
|--------|-----------|
| AGENT1_ANALYSIS | 30 |
| AGENT1_KEYWORD | 273 |
| AGENT5_GROUP | 2 |
| AGENT5_GROUP_MEMBER | 12 |
| AGENT5_ENTITY | 95 |
| AGENT5_UNIFIED_DOC | 2 |
| AGENT2_DOC | 10 |
| AGENT2_TAG | 8 |
| AGENT3_SEARCH | 4 |
| AGENT3_SCENARIO | 4 |
| AGENT4_RISK_EVAL | 4 |

**데이터 흐름 추적 (30 → 10 → 12 → …):**
- Agent_1: 30건 처리 → 그중 `is_relevant=True` **10건**만 Agent_5로.
- Agent_5: 관련뉴스 10건 → `documents_for_next_agents` **12건**(통합문서 2 + 개별문서 10). **그룹 뉴스가 개별로도 전달됨을 확인.**
- Agent_2: 스모크에서는 러너 `TEST_LIMIT` 영향으로 10건 입력. (전체 실행에서는 12건 그대로 전달 — 스모크 전용 아티팩트)
- Agent_3: 태그가 매핑된 문서(`mapped_tags>0`)만 처리 → 4건.

### 5.3 안전장치 검증 (통과)
- **같은 run_id 재실행** → AGENT4_RISK_EVAL 4건 유지(clean reload, 중복 없음).
- **다른 run_id(smoke_test_02) 적재** → smoke_test_01(4건) 보존 + smoke_test_02(4건) 누적 → 공존 확인. (검증 후 smoke_test_02 정리)

### 5.4 전체 실행 (`run_id=full_run_01`, 21:28~22:2x, 약 1시간)

`PIPELINE_TEST_MODE` 미설정 → 115건 전체 처리 — **status=SUCCESS**

| 테이블 | 적재 행수 |
|--------|-----------|
| AGENT1_ANALYSIS | 115 |
| AGENT1_KEYWORD | 1078 |
| AGENT5_GROUP | 10 |
| AGENT5_GROUP_MEMBER | 75 |
| AGENT5_ENTITY | 618 |
| AGENT5_UNIFIED_DOC | 44 |
| AGENT2_DOC | 74 |
| AGENT2_TAG | 63 |
| AGENT3_SEARCH | 32 |
| AGENT3_SCENARIO | 35 |
| AGENT4_RISK_EVAL | 32 |

**데이터 흐름 (115 → 65 → 74 → 32):**
- Agent_1: 115건 전체 → `is_relevant=True` **65건**.
- Agent_5: 관련뉴스 65건 → 그룹 **10개**, 통합문서 44건. `documents_for_next_agents` = 통합 + 개별.
- Agent_2: **74건** 처리(그룹 통합 + 개별), 태그 63개.
- Agent_3: 태그 매핑된 문서만 → **32건**(시나리오 35개).
- Agent_4: **32건** Risk 평가.

**run_id 누적 안전장치 실운영 확인:** smoke_test_01(SUCCESS, 4건) 배치가 보존된 상태에서 full_run_01(SUCCESS, 32건)이 추가 → 두 배치가 모든 산출 테이블에 공존. 덮어쓰기 없음.

```
=== run_id별 AGENT4_RISK_EVAL 누적 ===
  smoke_test_01: 4
  full_run_01:  32
```

---

## 6. 참고 / 미확정

- `scenario_evaluations`(Agent4) — **blob 유지 결정(실측 후)**. full_run_01의 32건 중 이 필드가 채워진 건 2건(총 시나리오 평가 5개)뿐이고, 항목 구조는 중첩 배열(`scenario_id`, `is_risk`, `risk_score`, `risk_justification`, `risk_factors[]`, `search_result_count`, `impact_level`)이다. 채워지는 비율이 낮고 뉴스별 리스크 판정(`is_risk`/`risk_score`)은 이미 AGENT4_RISK_EVAL의 독립 컬럼으로 조회 가능하므로, 시나리오별 세부는 재현용 JSON blob으로 두는 게 단순·충분하다. 향후 시나리오 단위 지표가 필요해지면 AGENT3_SCENARIO처럼 별도 행 테이블로 승격 검토.
- 속도: Agent_1(뉴스 1건당 LLM 4회)이 최대 병목, Agent_5는 배치당 3초 딜레이(Rate Limit 방지). 5단계 subprocess 직렬이라 시간이 합산됨.
- 스모크의 Agent별 `TEST_LIMIT` 불일치(Agent_2=10, 그 외 30)로 중간 문서 잘림 발생 — 전체 실행(`PIPELINE_TEST_MODE` 미설정)에서는 잘림 없음.

### 검증 쿼리
```sql
SELECT * FROM PIPELINE_RUN;
SELECT run_id, COUNT(*) FROM AGENT4_RISK_EVAL GROUP BY run_id;  -- run별 누적 확인
```
