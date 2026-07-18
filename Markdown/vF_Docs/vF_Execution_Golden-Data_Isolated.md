# Golden Dataset "Isolated" 평가 실행 설계

> 작성일: 2026-07-15
> 대상 DB: `data/NEWS/news_intelligence.db`
> 관련 문서: [`vF_Execution_Golden-Data.md`](./vF_Execution_Golden-Data.md) (Cascaded 실행) · [`vF_GoldenDataset_Evaluation-Methodology.md`](./vF_GoldenDataset_Evaluation-Methodology.md) · [`vF_GoldenDataset_Fake-News.md`](./vF_GoldenDataset_Fake-News.md)
>
> ⚠️ **이 문서는 구현 전 설계(design)이다.** Cascaded 실행은 위 `vF_Execution_Golden-Data.md`에 있으며, 본 문서는 그 후속인 Isolated 평가 실행 방법을 정의한다. 실제 코드/스크립트는 아직 작성되지 않았다.

---

## 1. 목적 (Why)

[평가 방법론](./vF_GoldenDataset_Evaluation-Methodology.md) §0에 따르면 후속 모듈 지표는 **Isolated**와 **Cascaded** 두 방식으로 측정한다.

| 구분 | 입력 | 측정 목적 |
|------|------|-----------|
| **Cascaded** | 직전 단계의 **실제 출력** | 실제 파이프라인 흐름에서의 성능 (이미 `golden_eval_20260715`로 측정) |
| **Isolated** | 직전 단계의 **정답(Ground Truth)** 주입 | 해당 모듈 **자체** 성능 (본 문서 대상) |

- **Propagation Loss = Isolated − Cascaded** 를 계산하려면 Isolated가 반드시 필요하다.
- Cascaded 실행(`vF_Execution_Golden-Data.md`)은 이미 완료했으므로, 본 문서는 **정답을 주입한 Isolated 실행**만 다룬다.

### Isolated가 필요한 모듈 (3개)
Agent_1(News Analyzer)의 지표(FP P/R, Keyword P/R)는 입력이 원문 뉴스라 **Isolated=Cascaded**로 동일하다. 따라서 정답 주입이 필요한 것은 후속 3개 모듈뿐이다.

| 모듈 | 주입할 정답 | 정답 필드(GOLDEN_GROUND_TRUTH) |
|------|-------------|-------------------------------|
| **Agent_2** Tag Mapper | 정답 키워드 | `gt_keywords` |
| **Agent_3** DB Searcher | 정답 태그 | `gt_tags` |
| **Agent_4** Risk Evaluator | 정답 엔티티(+시점) | `gt_entities` (+ `gt_event_timing`) |

---

## 2. 채택 방식: 독립 Isolated 오케스트레이터 (별도 스크립트)

### 2.1 왜 별도 스크립트인가 (Cascaded 오케스트레이터를 재사용하지 않는 이유)

Isolated는 Cascaded와 **실행 모델이 근본적으로 다르다.**
- Cascaded: `1→5→2→3→4` 전체 체인을 순차 실행하며 직전 Agent의 실제 출력 JSON을 이어받음.
- Isolated: 각 모듈을 **독립적으로** 실행한다. 정답을 주입하므로 **직전 Agent의 실제 출력이 필요 없다.**

```
Tag Mapper Isolated   : gt_keywords 주입 → Agent_2 그래프 실행 → 적재 → 평가
DB Searcher Isolated  : gt_tags 주입     → Agent_3 그래프 실행 → 적재 → 평가
Risk Eval Isolated    : gt_entities 주입 → Agent_4 그래프 실행 → 적재 → 평가
```

이 구조에서 기존 5-러너 체인 오케스트레이터를 재사용하려면 각 러너에 `if ISOLATED_MODE` 분기를 심어야 해서, **실뉴스/Cascaded 파이프라인 회귀 위험**과 코드 오염이 생긴다. 대신 **얇은 별도 오케스트레이터**를 두면:

1. 기존 5개 러너·오케스트레이터·로더를 **건드리지 않음** → 회귀 위험 0.
2. 정답 주입·변환 로직이 **한 파일에 집중**.
3. 기존 run_id 태깅 방식을 재사용 → 같은 `AGENT*` 테이블에 `isolated_*` run_id로 append. 평가 시 run_id로만 Cascaded/Isolated 구분.

### 2.2 "복제"가 아님 — 재사용하는 것과 새로 만드는 것

| 재사용 (그대로) | 새로 작성 (Isolated 전용) |
|-----------------|--------------------------|
| 각 Agent의 **그래프/노드 로직** (`create_*_graph`, State 정의) — 이게 평가 대상 | 정답 주입 오케스트레이터 1개 |
| 기존 **로더**(`load_agent_2/3/4.py`) — run_id 기반 적재 | 정답→입력구조 **변환 함수** 3개 |
| **run_id 배치 태깅**·`PIPELINE_RUN` 안전장치 | (그래프를 직접 import해 호출하거나, 정답 주입된 입력 JSON을 만들어 러너에 넘김) |

즉 Agent 내부 로직은 복제하지 않고, **입력 준비 방식만 다른 새 진입점**을 만든다.

### 2.3 구현 옵션 두 가지 (택1, 구현자 판단)

- **옵션 B-1 (권장): 정답 주입 입력 JSON을 미리 생성 → 러너가 입력 경로만 env로 스위칭**
  - 각 Agent 러너의 입력 경로 하드코딩(아래 §3 각주)을 `os.environ.get("AGENTx_INPUT_PATH", 기본경로)`로 바꾸는 최소 수정만 러너에 가함(§2.1의 회귀 위험을 입력 경로 1줄로 최소화).
  - 별도 스크립트가 `GOLDEN_GROUND_TRUTH` + `GOLDEN_NEWS_MASTER`를 읽어 "정답이 주입된 입력 JSON"을 각 Agent output 포맷으로 생성.
  - 기존 오케스트레이터/그래프/로더 재사용도 자연스러움.
- **옵션 B-2: 그래프를 직접 import한 독립 스크립트**
  - `create_tag_mapper_graph()` 등을 import해 정답 주입 State로 직접 invoke. 러너 파일 자체를 안 건드림. 단, 병렬처리·저장·run_id 로직을 스크립트가 다시 구현해야 함.

> 권장: **B-1**. 러너 입력 경로 env화(3곳)는 이미 검증된 `NEWS_SOURCE_TABLE` 스위칭과 동일한 패턴이고, 병렬/저장/로더를 그대로 재사용할 수 있다.

---

## 3. 모듈별 정답 주입 상세 (근거: 코드 확인 완료)

### 3.1 Agent_2 (Tag Mapper) — 난이도 🟢 낮음

**입력 소비 지점**: `backend/agents/Agent_2_Tag_Mapper/scripts/run_full_pipeline.py`
- `:55` 입력 파일 `Agent_5_News_Grouper/output/output_news_grouper.json` 로드 (하드코딩)
- `:68` `documents_for_next_agents` 추출
- `:121` `TagMappingState(... keywords=doc.get("keywords", []) ...)` — **여기가 주입 지점**

**입력 keywords 구조** (`nodes/__init__.py:21`): `List[Dict]` = `[{"keyword": str, "score": float}, ...]`

**변환** (`gt_keywords` 문자열 리스트 → keywords):
```python
keywords = [{"keyword": kw, "score": 1.0} for kw in gt_keywords]
```
score는 정답이므로 1.0 고정. FP 뉴스는 `gt_keywords=[]` → 빈 리스트 주입(정상).

### 3.2 Agent_3 (DB Searcher) — 난이도 🟡 중간

**입력 소비 지점**: `backend/agents/Agent_3_DB_Searcher/scripts/run_full_pipeline.py`
- `:53` 입력 파일 `Agent_2_Tag_Mapper/output/output_tag_mapper.json` 로드 (하드코딩)
- `:60-63` `mapped_tags` 길이 > 0 인 뉴스만 필터
- `:106` `DBSearchState(... mapped_tags=article.get("mapped_tags", []) ...)` — **주입 지점**

**입력 mapped_tags 구조**: `[{tag_id, tag_type, tag_name, confidence, source, ...}]`

**변환** (`gt_tags` = tag_id 문자열 리스트 → mapped_tags):
gt_tags는 tag_id만 있으므로 `tag_type`/`name`을 **TAG_MASTER 조회로 보강**한다.

```python
# TAG_MASTER 실제 스키마: tag_id, target_region, tag_type, name, ... (복합키: tag_id+target_region)
# 같은 tag_id가 KR/GLOBAL 2행 존재 → KR 우선 선택(한글 name 확보)
def gt_tags_to_mapped_tags(cur, gt_tags):
    out = []
    for tid in gt_tags:
        row = cur.execute("""
            SELECT tag_id, tag_type, name FROM TAG_MASTER
            WHERE tag_id=? ORDER BY (target_region='KR') DESC LIMIT 1
        """, (tid,)).fetchone()
        if row:
            out.append({"tag_id": row[0], "tag_type": row[1], "tag_name": row[2],
                        "confidence": 1.0, "source": "golden_truth"})
    return out
```

> **검증 완료**: golden의 고유 gt_tags **39개 전부 TAG_MASTER에 존재**(누락 0). 변환이 결정론적으로 성립.
> **주의**: 컬럼명은 `tag_name`이 아니라 **`name`**. 복합키 `(tag_id, target_region)`이라 반드시 region 선택 규칙 필요.

### 3.3 Agent_4 (Risk Evaluator) — 난이도 🔴 높음

**입력 소비 지점**: `backend/agents/Agent_4_Risk_Evaluator/scripts/run_full_pipeline.py`
- `:125-128` `config.AGENT3_OUTPUT_FILE`(`Agent_3/output/output_db_searcher.json`) 로드
- `:68` `search_results_multi=article.get("search_results_multi", [])` — **주입 지점**

**입력 search_results_multi 구조**: `[{sql_id, scenario_id, sql, result_count, results:[{생산지명, 생산국가, ...}]}]`
→ Agent_4는 이 **SQL 검색 결과 행(row)들**을 소비해 리스크를 평가한다.

**변환의 어려움**: `gt_entities`는 코드 리스트(`{suppliers:["BHUE",...], sites:["S000009",...], materials:[...], raw_materials:[...]}`)인데, Agent_4 입력은 Agent_3의 **SQL 결과 행 구조**다. 두 방법:

- **방법 ①(권장, 충실): gt_entities 코드로 supply_chain.db 실제 조회** → 각 엔티티의 실제 행(생산지명/국가 등)을 만들어 `search_results_multi.results`로 구성. `generate_golden_dataset.py`의 `DomainDB.expand_entities()` 로직을 역참조하면 됨(정답 엔티티가 이미 그 BOM 전개 결과이므로 그대로 SELECT).
- **방법 ②(간소): search_results_multi를 최소 골격으로만 채우고 gt_entities를 State 별도 필드로 전달** → Agent_4 노드가 gt_entities를 직접 보게 해야 하므로 노드 수정 필요(회귀 위험 ↑). 권장하지 않음.

> Agent_4가 `results` 행에서 실제로 어떤 컬럼을 읽는지(예: 국가/공급사명으로 리스크 판정) 노드 코드를 추가 확인한 뒤 방법 ①의 SELECT 컬럼을 맞출 것.

---

## 4. 발견한 기존 이슈 (참고)

- **Agent_3 config 경로 상수 정정 완료**: `Agent_3_DB_Searcher/config.py`의 `AGENT2_OUTPUT_FILE`/`AGENT3_OUTPUT_FILE`가 존재하지 않는 `data/Dev_Data/...` 경로였음(dead code — 실제 러너는 하드코딩 사용). 실제 경로(`Agent_2/output/output_tag_mapper.json`, `Agent_3/output/output_db_searcher.json`)로 **이미 수정함**. Isolated에서 경로 env화 시 이 상수를 기준으로 삼으면 됨.
- **입력 경로 관리 불일치**: Agent_2는 러너 하드코딩(`:55`), Agent_3는 러너 하드코딩(`:53`)+config 상수 별도 존재, Agent_4는 config 상수(`AGENT3_OUTPUT_FILE`) 참조. env화 시 Agent별로 위치가 다름에 유의.
- **기존 env 패턴**: 세 러너 모두 `PIPELINE_TEST_MODE`, `PIPELINE_RUN_ID` 환경변수 패턴 보유 → `AGENTx_INPUT_PATH` 추가 시 동일 관례 따르면 됨.

---

## 5. 실행/평가 흐름 (설계)

```
1. 정답 주입 입력 JSON 생성 (신규 스크립트)
   - GOLDEN_GROUND_TRUTH + GOLDEN_NEWS_MASTER 읽어
   - Agent_2용: gt_keywords → keywords 주입한 news_analyzer 유사 JSON
   - Agent_3용: gt_tags → mapped_tags 주입한 tag_mapper 유사 JSON (TAG_MASTER 조회)
   - Agent_4용: gt_entities → search_results_multi 주입한 db_searcher 유사 JSON (supply_chain.db 조회)

2. 각 Agent를 Isolated run_id로 독립 실행 (입력 경로 env 스위칭)
   AGENT2_INPUT_PATH=<주입JSON> python .../Agent_2/scripts/run_full_pipeline.py  # run_id=isolated_tag_YYYYMMDD
   AGENT3_INPUT_PATH=<주입JSON> python .../Agent_3/scripts/run_full_pipeline.py  # run_id=isolated_db_YYYYMMDD
   AGENT4_INPUT_PATH=<주입JSON> python .../Agent_4/scripts/run_full_pipeline.py  # run_id=isolated_risk_YYYYMMDD
   → 기존 로더가 AGENT2_TAG / AGENT3_* / AGENT4_RISK_EVAL 에 isolated_* run_id로 적재

3. 평가: 각 isolated_* run_id 산출물 vs GOLDEN_GROUND_TRUTH JOIN → Isolated 지표
   Propagation Loss = Isolated − Cascaded(golden_eval_20260715)
```

> ⚠️ Cascaded 실행과 **동시 실행 금지**(중간 output JSON 경로 공유). run_id는 신규 `isolated_*`만 사용해 기존 배치 보존.

---

## 6. 난이도 요약

| 모듈 | 주입 | 변환 난이도 | 핵심 작업 |
|------|------|:---:|-----------|
| Agent_2 Tag Mapper | `gt_keywords`→keywords | 🟢 낮음 | 문자열→`{keyword,score}` 래핑 |
| Agent_3 DB Searcher | `gt_tags`→mapped_tags | 🟡 중간 | TAG_MASTER 조회로 tag_type/name 보강 (39개 전부 존재 확인) |
| Agent_4 Risk Evaluator | `gt_entities`→search_results_multi | 🔴 높음 | supply_chain.db 조회로 SQL결과 행 재구성 (노드 소비 컬럼 확인 필요) |
