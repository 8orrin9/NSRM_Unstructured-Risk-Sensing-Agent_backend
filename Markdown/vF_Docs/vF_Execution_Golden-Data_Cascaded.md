# Golden Dataset 기반 5-Agent 파이프라인 실행 & DB 적재

> 작성일: 2026-07-15
> 대상 DB: `data/NEWS/news_intelligence.db`
> 관련 문서: [`vF_Execution_Real-News.md`](./vF_Execution_Real-News.md) · [`vF_GoldenDataset_Fake-News.md`](./vF_GoldenDataset_Fake-News.md) · [`vF_GoldenDataset_Evaluation-Methodology.md`](./vF_GoldenDataset_Evaluation-Methodology.md)

---

## 1. 목적 (Why)

정답 라벨을 보유한 **가짜뉴스 Golden Dataset**(`data/NEWS/golden_dataset.json`, 51건)을 실뉴스와 **동일한 5-Agent 파이프라인**으로 처리하고, 각 Agent 출력을 `news_intelligence.db`에 적재한다.

실뉴스 실행([`vF_Execution_Real-News.md`](./vF_Execution_Real-News.md))은 정답이 없어 예측 출력만 쌓았지만, Golden Dataset은 전 단계 정답(`gt_*`)을 보유하므로 [평가 방법론](./vF_GoldenDataset_Evaluation-Methodology.md)의 **Cascaded 지표**(실제 파이프라인 흐름 성능)를 계산할 토대가 된다. 이번 실행은 파이프라인 전체를 1회 흘려보내는 **Cascaded** 측정용이며, 각 단계에 정답을 주입하는 **Isolated** 측정은 후속 작업이다.

### 핵심 제약
- 실뉴스 정본 배치(`full_run_01`)를 포함한 **기존 run_id 데이터를 절대 덮어쓰지 않는다** → golden 전용 신규 run_id(`golden_eval_20260715`) 사용.
- Golden Dataset은 NEWS_MASTER와 스키마가 달라, 파이프라인 정합을 위한 **별도 입력 테이블** + **정답 분리**가 필요.

---

## 2. 작업 내용 (What & How)

### 2.1 별도 테이블 2개 (입력 / 정답 분리)

Golden Dataset을 NEWS_MASTER가 아닌 별도 테이블로 적재하되, **정답 정보를 파이프라인 입력에서 완전히 분리**한다.

| 테이블 | 용도 | 비고 |
|--------|------|------|
| **GOLDEN_NEWS_MASTER** | 파이프라인 **입력** | NEWS_MASTER 스키마와 정합(Agent_1이 읽는 컬럼 보유). 정답 필드 제외. |
| **GOLDEN_GROUND_TRUTH** | 평가용 **정답(ground truth)** | `gt_*`, `is_false_positive`, `has_db_match` 등. `news_id`로 1:1. |

**GOLDEN_NEWS_MASTER 스키마** (NEWS_MASTER 미러링):
```
news_id(PK), source, source_type, title, description, content,
url(UNIQUE), pub_date, collected_at, is_active, created_at, updated_at
```

**결측 필드 합성 규칙** (golden엔 없지만 파이프라인이 필요로 하는 값):

| 컬럼 | 합성 방법 | 근거 |
|------|-----------|------|
| `description` | `record['brief']` (사건 개요) | Agent_1이 summary로 활용. 사용자 확정. |
| `url` | `"golden://" + news_id` | 결정적 합성값. Agent_1은 메타로만 보관(실제 접근 없음). 별도 테이블이라 UNIQUE 충돌 없음. |
| `source_type` | 상수 `"GOLDEN"` | Agent_1 메인 쿼리가 SELECT 안 함. |
| `collected_at` | 적재 시각 | Agent_1이 SELECT 안 함. |
| `pub_date` | `record['published_date']` | 직접 대응. |

- `risk_factor`/`keyword`/`risk_category_name`은 Agent_1이 읽지 않으므로 입력 테이블에서 제외. `risk_category_name`은 정답 성격이라 GOLDEN_GROUND_TRUTH로 이동.
- **GOLDEN_GROUND_TRUTH**: bool→INTEGER, 리스트/딕트(`gt_keywords`/`gt_tags`/`gt_entities`/`gt_group_shared_nodes`)는 JSON blob(TEXT). FK·CHECK 없음(프로젝트 관례).

### 2.2 Agent_1 입력 테이블 스위칭 (최소 수정)

5-Agent 중 **NEWS_MASTER를 직접 읽는 것은 Agent_1뿐**이고, Agent 5→2→3→4는 이전 Agent의 output JSON을 읽는 체인이다. 따라서 Agent_1만 golden 테이블을 읽게 하면 된다.

`backend/agents/Agent_1_News_Analyzer/scripts/run_full_pipeline.py`에 환경변수 스위칭 추가:
```python
news_source_table = os.environ.get("NEWS_SOURCE_TABLE", "NEWS_MASTER")
assert news_source_table in {"NEWS_MASTER", "GOLDEN_NEWS_MASTER"}
```
- 뉴스 조회·소스 통계 쿼리(2곳)의 하드코딩 `NEWS_MASTER`를 이 변수로 치환.
- **env 미설정 시 기존 NEWS_MASTER 동작 그대로** → 실뉴스 파이프라인에 회귀 없음.
- Agent 5/2/3/4, 오케스트레이터, 로더는 **무수정**(JSON 체인이라 golden 데이터가 자동으로 흐름).

### 2.3 신규 파일
- `scripts/db/load_golden_dataset.py` — GOLDEN 두 테이블 생성/적재. `--recreate`는 GOLDEN 두 테이블만 DROP(기존 AGENT*/PIPELINE_RUN/NEWS_MASTER 불변).

---

## 3. 기존 데이터 보존 / 동시 실행 회피

### 3.1 run_id 배치 태깅 (실뉴스와 동일 안전장치)
실뉴스 실행이 확립한 run_id 배치 방식을 그대로 사용한다. 로더가 `run_id` 기준으로만 DELETE→INSERT하므로 **다른 run_id 배치는 자동 보존**된다. golden은 신규 run_id `golden_eval_20260715`를 사용해 실뉴스 정본(`full_run_01`)과 분리 누적.

### 3.2 동시 실행 금지
golden과 실뉴스 파이프라인은 Agent 간 중간 output JSON 파일 경로를 공유하므로(run_id 태깅은 DB 적재만 보호), **동시 실행 시 충돌**한다. 따라서 실뉴스 실행 **완료 확인 후 순차 실행**했다. `NEWS_SOURCE_TABLE` env는 전역 `export` 없이 **golden 실행 커맨드에만 인라인** 지정.

### 3.3 실행 전 백업
`scripts/db/backup_news_db.py`로 DB 파일 전체(모든 18개 테이블 포함)를 백업 후 진행.

---

## 4. 실행 런북

```bash
# 0. DB 전체 백업
python scripts/db/backup_news_db.py

# 1. golden 테이블 생성 + 적재 (GOLDEN 두 테이블만 DROP/생성)
python scripts/db/load_golden_dataset.py --recreate

# 2. golden 전체 실행 (51건, 신규 run_id, 인라인 env)
NEWS_SOURCE_TABLE=GOLDEN_NEWS_MASTER \
  python backend/agents/scripts/run_full_pipeline.py --run-id golden_eval_20260715
```
> Windows: `python`(python3 아님), 한글 깨짐 방지 `PYTHONIOENCODING=utf-8` 권장.

---

## 5. 검증 결과

### 5.1 테이블 적재 (load_golden_dataset.py --recreate)
- GOLDEN_NEWS_MASTER: **51건**, GOLDEN_GROUND_TRUTH: **51건**
- news_id 1:1 미매칭 **0**, `description` NULL **0**, `url` 중복 **0**
- 기존 테이블 불변 확인: NEWS_MASTER 115, PIPELINE_RUN(적재 시점) 유지

**cell 분포** (설계와 일치):

| cell | 1a | 1b | 2a | 2b | 2c | 2d | 2e | 합계 |
|------|----|----|----|----|----|----|----|------|
| 건수 | 5 | 5 | 13 | 8 | 6 | 10 | 4 | **51** |

### 5.2 파이프라인 실행 (`run_id=golden_eval_20260715`)
- Agent_1 입력 테이블: `GOLDEN_NEWS_MASTER` (51건), env 스위칭 정상 동작 확인.
- 기존 정본 배치 `full_run_01`(AGENT4 32건) 보존 상태에서 실행 → **run_id 누적 안전장치 실운영 확인**.

파이프라인 status **SUCCESS**. 단계별 적재 행수:

| 테이블 | 적재 행수 (golden_eval_20260715) |
|--------|-----------------|
| AGENT1_ANALYSIS | 51 |
| AGENT1_KEYWORD | 333 |
| AGENT5_GROUP | 5 |
| AGENT5_GROUP_MEMBER | 55 |
| AGENT5_ENTITY | 281 |
| AGENT5_UNIFIED_DOC | 27 |
| AGENT2_DOC | 38 |
| AGENT2_TAG | 100 |
| AGENT3_SEARCH | 29 |
| AGENT3_SCENARIO | 36 |
| AGENT4_RISK_EVAL | 29 |

**데이터 흐름 추적** (입력 51건이 단계별로 필터링되며 감소):

```
Agent_1  입력 51건 (GOLDEN_NEWS_MASTER 전량)
   │  False Positive 필터 (relevance_score ≥ 0.5)
   ▼
        관련 있음 34건 (66.7%)  ·  무관함 17건 제외 (33.3%)
Agent_5  그룹화 → 다음 단계 전달 문서 38개 (통합 4 + 개별 34)
   │  KG hop 그룹화: 그룹 5개, 멤버 55, 엔티티 281, 통합문서 27
   ▼
Agent_2  38개 문서 태그 매핑 → 태그 100개 부여
   │  mapped_tags > 0 필터
   ▼
Agent_3  DB 검색 29건  ·  시나리오 36개 생성
   ▼
Agent_4  리스크 평가 29건
        이슈 분포: 🔴 ISSUE 16 (55.2%) · 🟡 SMD 10 (34.5%) · ⚪ NONE 3 (10.3%)
        Risk=True 25건 (86.2%) · 평균 Risk 0.74
```

> Agent_1의 FP 필터 결과(관련 34 / 무관 17)는 golden 정답(`is_false_positive`)과 대조해 Cascaded FP 지표를 산출할 수 있다(후속 평가 스크립트).

### 5.3 run_id 누적 안전장치 검증

```sql
SELECT run_id, status FROM PIPELINE_RUN;
SELECT run_id, COUNT(*) FROM AGENT4_RISK_EVAL GROUP BY run_id;  -- full_run_01 + golden_eval 공존
```

**결과** — 실뉴스 정본 배치와 golden 배치가 같은 테이블에 run_id로 분리 공존(덮어쓰기 없음):

| run_id | PIPELINE_RUN status | AGENT4_RISK_EVAL 행수 |
|--------|:---:|:---:|
| `full_run_01` (실뉴스 정본) | SUCCESS | 32 (보존) |
| `golden_eval_20260715` (golden) | SUCCESS | 29 (신규 append) |

→ run_id 배치 태깅 안전장치가 실운영에서 정상 동작함을 확인.

---

## 6. 참고 / 후속

- **Isolated 지표**: 이번 실행은 Cascaded용. 각 단계에 정답(`gt_keywords`/`gt_tags`/`gt_entities` 등)을 주입하는 Isolated 측정은 파이프라인에 정답 주입 지점 추가가 필요해 별도 설계.
- **평가 스크립트**: run_id로 필터한 AGENT* 산출물을 GOLDEN_GROUND_TRUTH와 `news_id` JOIN하여 지표 계산하는 스크립트는 후속 작업.
- **News Grouper(Agent_5) 평가**: [방법론 문서](./vF_GoldenDataset_Evaluation-Methodology.md) §6.1에 따라 그룹화는 우선 평가 대상이 아니며 insight_kg 재정합 후 반영.
