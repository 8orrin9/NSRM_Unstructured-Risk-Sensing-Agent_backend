# Knowledge Graph DB (`insight_kg`) 생성 방법 및 결과

> **문서 목적**: 반도체 공급망 리스크 센싱을 위한 인사이트 지식그래프(Insight KG)를 어떻게 생성했는지(방법)와 무엇이 만들어졌는지(결과)를 기록한다. 160개 KOTRA 공급망 리포트를 소스로 처음부터 재구축한 v4 기준.
>
> **최종 갱신**: 2026-07-15 · **대상 브랜치**: `poc-a_operation`

---

## 1. 개요

### 1.1 Insight KG란

`insight_kg`는 KOTRA 공급망 리포트에서 추출한 **엔티티(국가·기업·소재·정책·조직 등)와 관계(인과·정책·공급·지리)로 구성된 지식그래프**다. 개별 뉴스가 아니라 "리포트가 서술하는 공급망 구조·인과 지식"을 그래프 형태로 축적해, 이후 뉴스가 들어왔을 때 그 뉴스가 어떤 리스크 구조에 닿는지 판단하는 **관계 골격(Layer 1)** 역할을 한다.

- **2-Layer 구조**: Layer 1 = Insight KG 관계 구조(본 문서), Layer 2 = 뉴스 매핑(Phase 2 이후)
- **소비 주체**: Phase 2 뉴스 그루퍼(News Grouper) — 뉴스 엔티티를 KG 노드에 매칭
- **기반 엔진**: LightRAG v1.5.4 (NetworkX 그래프 + JSON KV 저장소 + NanoVectorDB 벡터 저장소)

### 1.2 재구축 배경 (v3 → v4)

파일럿(v1~v3)은 6~47개 리포트로 구축한 소규모 KG였다. 도메인 커버리지를 확보하기 위해 확보 리포트를 **160개**(KOTRA 공급망 리포트 14~175호, 103·166호 결번)로 확장하고, **처음부터 재구축**했다.

| 버전 | 소스 리포트 | 노드(정규화 후) | 엣지(정규화 후) |
|------|-------------|------------------|------------------|
| v2 (파일럿) | 6개 | 103 | - |
| v3 | 47개 | 509 | 422 |
| **v4 (본 문서)** | **160개** | **9,985** | **11,501** |

- 기존 파일럿 산출물은 `backup/data/InsightKG/pilot_*`로 백업(15개 파일).

### 1.3 사용 기술 및 모델

| 구분 | 기술/모델 | 용도 |
|------|-----------|------|
| 그래프 엔진 | LightRAG v1.5.4 (lightrag-hku) | 청크→엔티티/관계 추출, GraphML 저장 |
| 전처리 LLM | gpt-5-mini | 리포트 원문 → `description_refined` 정제 |
| 추출 LLM | gpt-4o-mini | 엔티티/관계 추출, 관계 카테고리 분류 |
| 정규화 LLM | gpt-4o | 엔티티 정규화 룩업 생성 + 2차 재검토 |
| 임베딩 | text-embedding-3-small (1536-dim) | 청크/엔티티/관계 벡터화 |

> **모델 사용 원칙**: OpenAI API를 쓰는 단계는 사전에 모델을 확정하고 진행했다. 정규화의 체이닝 해소·적용·검증 단계는 **LLM을 쓰지 않는 결정론적 코드**다.

---

## 2. 아키텍처

### 2.1 엔티티 타입

LightRAG 추출 결과 실제 그래프에는 `organization`, `location`, `event`, `person`, `artifact`, `concept`, `data`, `material` 등 다양한 `entity_type`이 존재한다. 이 중 표기 이형이 실재할 법한 타입만 정규화 대상으로 삼는다(§4.4의 `MERGEABLE_TYPES`).

### 2.2 관계 카테고리 Taxonomy (5종)

추출된 각 엣지를 5개 카테고리로 재분류하고, 가중치(`weight`)와 특이도(`edge_specificity`)를 부여한다.

| 카테고리 | 의미 | weight | edge_specificity |
|----------|------|--------|------------------|
| CAUSAL | 인과관계(원인-결과, 직접 영향) | 1.0 | HIGH |
| POLICY_REGULATION | 정책/법규/규제 | 1.0 | HIGH |
| SUPPLY | 공급/의존/소싱 | 1.0 | HIGH |
| GEOGRAPHIC | 지리적 위치/소속 | 0.5 | MEDIUM |
| DESCRIPTIVE | 단순 언급/설명 | 0.2 | LOW |

- 우선순위: CAUSAL > POLICY_REGULATION > SUPPLY > GEOGRAPHIC > DESCRIPTIVE
- HIGH specificity(CAUSAL+POLICY+SUPPLY) 비중이 KG의 도메인 의미 밀도를 나타내는 핵심 지표.

---

## 3. 생성 방법 (재구축 파이프라인)

### 3.1 실행 전제 (Windows / poc-a)

- 인터프리터: `.venv/Scripts/python.exe` (프로젝트 가상환경 필수)
- 인코딩: UTF-8 (`sys.stdout.reconfigure(encoding='utf-8')`)
- 명령어: `python3`가 아닌 `python` (MS Store 리다이렉터 회피)

### 3.2 전체 흐름

**레포트 전처리 → `news_intelligence.db` 정보 적재 → `insight_kg` 생성**

```bash
# Step 1: 160개 리포트 배치 적재 (news_intelligence.db INSIGHT_REPORT_MASTER)
python dev/data_pipeline/data_pipeline_report_batch_loader.py

# Step 2: 리포트 원문 정제 (description_refined 생성, 비동기 병렬 5)
python dev/data_pipeline/data_pipeline_report_refiner_async.py

# Step 3: Insight KG 구축 (청크→엔티티/관계 추출 + 임베딩, 병렬 8)
python dev/insight_kg/insight_kg_builder.py

# Step 4: 관계 재분류 (전 엣지 5개 카테고리, 병렬 8)
python dev/insight_kg/insight_kg_relation_categorizer_async.py

# Step 5-1: 엔티티 정규화 룩업 생성 (정밀도 우선 재설계 v2)
python dev/insight_kg/insight_kg_entity_normalizer_builder_v2.py

# Step 5-2: 체이닝 해소 (transitive resolution, LLM 미사용)
python dev/insight_kg/insight_kg_lookup_resolve_chains.py

# Step 5-3: 명백한 이형 수동 보강 (국가 한↔영, BIS) 후 재수렴
python dev/insight_kg/insight_kg_lookup_add_obvious.py
python dev/insight_kg/insight_kg_lookup_resolve_chains.py

# Step 6: 정규화 적용 (룩업 반영, LLM 미사용)
python dev/insight_kg/insight_kg_entity_normalizer_applier.py

# 검증
python dev/insight_kg/insight_kg_validate_normalized.py
```

### 3.3 각 단계 설명

**Step 1 — 배치 적재** (`data_pipeline_report_batch_loader.py`)
160개 리포트를 `news_intelligence.db`의 `INSIGHT_REPORT_MASTER`에 적재. 결과 160/160.

**Step 2 — 리포트 전처리** (`data_pipeline_report_refiner_async.py`, gpt-5-mini)
리포트 원문을 KG 추출에 적합한 정제 서술(`description_refined`)로 변환. 동기 버전 대비 지연(latency)이 병목이라 **비동기 병렬(동시성 5)**로 전환해 약 1.5시간 → 약 25분으로 단축. 결과 160/160, 실패 0.
> gpt-5-mini는 `max_tokens`가 아니라 `max_completion_tokens`를 사용하고 커스텀 temperature를 지원하지 않는다.

**Step 3 — KG 구축** (`insight_kg_builder.py`, gpt-4o-mini + text-embedding-3-small)
`description_refined`(총 3,457,946자)를 청크(`chunk_token_size=2000`, `overlap=200`)로 나눠 LightRAG로 엔티티/관계를 추출하고 임베딩. 160개 대응을 위해 `llm_model_max_async=2 → 8`로 상향. 결과 **10,281 노드 / 11,648 엣지** (1,179 청크).

**Step 4 — 관계 재분류** (`insight_kg_relation_categorizer_async.py`, gpt-4o-mini)
전 엣지(11,648개)를 §2.2의 5개 카테고리로 분류하고 weight·edge_specificity를 부여. LLM 호출은 **동시성 8로 병렬**, 그래프 쓰기는 결과를 모아 메인에서 일괄 반영(GraphML 1회 저장). HIGH specificity 74.9%.

**Step 5 — 엔티티 정규화** (§4에서 상세)
표기 이형(예: `SK하이닉스`/`SK Hynix`)을 하나의 대표명으로 통일하는 룩업 테이블을 만들고, 체이닝 해소·명백한 이형 보강까지 거쳐 296개 매핑을 확정.

**Step 6 — 정규화 적용** (`insight_kg_entity_normalizer_applier.py`, LLM 미사용)
`nx.relabel_nodes`로 이형 노드를 대표명으로 관계 재지정(중복 노드 자동 병합). 출력: `graph_chunk_entity_relation_normalized.graphml`.

---

## 4. 엔티티 정규화 (정밀도 우선 재설계)

### 4.1 문제: 과잉 그룹화

초기 정규화 방식은 이름만 LLM에 넘겨 "유사한 것 묶기"에 치우쳐, **약 30~40%의 오병합**을 냈다(예: Samsung SDI→삼성전자, 브렌트유/WTI→두바이유, Peru→Stellantis, 단계 2~7→부정적 영향). KG를 오염시키므로 폐기했다.

### 4.2 정밀도 우선 원칙

> **누락된 병합은 안전하고(원본 유지), 과잉 병합은 KG를 오염시킨다.** 조금이라도 동일 여부가 의심되면 통합하지 않는다.

### 4.3 룩업 생성 (`insight_kg_entity_normalizer_builder_v2.py`, gpt-4o)

핵심 개선 5가지:
1. **입력 강화** — 엔티티 이름뿐 아니라 `entity_type` + `description`(앞 200자)을 함께 제공
2. **entity_type별 배치** — 같은 타입끼리만 비교(타입이 다르면 후보에서 제외). 병합 후보는 `organization`, `location`, `person`, `event`, `material` 등 표기 이형이 실재할 타입(`MERGEABLE_TYPES`)으로 한정하고 `data`/`date`/`content`/`other`/`UNKNOWN`은 제외
3. **정밀도 우선 프롬프트** — 통합 가능(약어↔정식명, 번역 차이, 대소문자/공백 차이)과 절대 금지(다른 회사/제품/등급, 상하위개념, 부분포함, 인물/날짜)를 명시
4. **규칙 게이트(A)** — canonical 미존재·메타어·자기참조·타입 불일치 제거
5. **LLM 재검토 게이트(B)** — 살아남은 매핑을 gpt-4o로 "정말 같은 실체인가" 재판정("확신 없으면 false")

**결과**: 353 raw → 342 규칙 게이트 통과 → **284 최종**(LLM 재검토에서 58개 탈락) → 245 대표명.

### 4.4 체이닝 해소 (`insight_kg_lookup_resolve_chains.py`, LLM 미사용)

룩업에 `A→B`, `B→C`처럼 대표명이 다시 다른 이형을 가리키는 연쇄가 존재해 수렴하지 않는 문제를 코드로 해결. 각 이형의 매핑 체인을 "더 이상 이형이 아닌" 최종 대표명까지 추적하고, **순환(A→B→A)은 감지해 안전하게 끊는다**. 결정론적이며 LLM을 쓰지 않는다.

### 4.5 명백한 이형 보강 (`insight_kg_lookup_add_obvious.py`, LLM 미사용)

정밀도 우선 설계가 보수적으로 남긴, 육안으로 명백한 이형만 규칙으로 추가(그래프에서 동일 `entity_type` 확인 항목만):
- **국가 한↔영**(location, 한글 공식명 대표): China→중국, United States→미국, Korea/South Korea→한국, Japan→일본, Taiwan→대만, Russia→러시아, India→인도, Germany→독일, France→프랑스
- **BIS**(organization): 3개로 갈라진 대표명 → `미국 상무부 산업안보국(BIS)` 하나로

추가 후 체이닝 해소를 재실행하면 `US/USA/U.S./美/United States` 체인까지 전부 `미국`으로 자동 수렴한다. 최종 **296개 매핑 → 250개 대표명, 잔여 체인 0**.

---

## 5. 생성 결과

### 5.1 규모 (정규화 전 → 후)

| 지표 | 정규화 전 | 정규화 후 |
|------|-----------|-----------|
| 노드 | 10,281 | **9,985** (296개 병합, 2.9% 감소) |
| 엣지 | 11,648 | **11,501** (중복 엣지 자동 병합) |

### 5.2 관계 카테고리 분포 (정규화 후)

| 카테고리 | 엣지 수 | 비율 |
|----------|---------|------|
| POLICY_REGULATION | 3,743 | 32.5% |
| CAUSAL | 2,766 | 24.1% |
| DESCRIPTIVE | 2,647 | 23.0% |
| SUPPLY | 2,098 | 18.2% |
| GEOGRAPHIC | 247 | 2.1% |

- **HIGH specificity 74.8%** — 정규화 전(74.9%) 대비 유지, 관계 품질 보존.

### 5.3 허브 노드 (차수 Top)

| 엔티티 | 차수 | 병합 반영 |
|--------|------|-----------|
| 중국 | 688 | China 병합 |
| KOTRA | 527 | |
| EU | 452 | |
| 미국 | 360 | United States·US·USA·U.S.·美 체인 병합 |
| 한국 | 203 | Korea·South Korea 병합 |
| 일본 | 162 | Japan 병합 |
| 한국무역협회 | 143 | |
| 니켈 | 110 | |
| 산업통상자원부 | 109 | |
| 러시아 | 106 | Russia 병합 |

### 5.4 연결성

- Connected Components: 2,618개
- 최대 Component: 6,577개 노드 (65.9%)
- 평균 차수: 2.3
- 고립 노드: 2,102개 (21.1%)

---

## 6. 검증 결과

`insight_kg_validate_normalized.py`로 정규화 그래프의 무결성을 확인.

- **병합 완전 반영 (PASS)**: 룩업 이형 296개 전부 그래프에서 소멸, 대표명 250개 전부 존재
- **주요 병합 확인**: 중국(688), 미국(360), 한국(203), 미국 상무부 산업안보국(BIS)(22)
- **관계 분포 보존**: HIGH specificity 74.8% 유지
- **정규화 오염 0건**: 과잉 병합 없음(정밀도 우선 원칙 준수)
- **고립 노드**: 정규화 전 2,177개 → 후 2,102개로 **오히려 감소**. 정규화 부작용이 아니라 LightRAG 추출 단계에서 생성된 단발성 언급 엔티티

---

## 7. 남은 과제

- **고립 노드 21%**: 추출 단계의 단발성 언급 엔티티. Phase 4 클러스터링은 최대 Component(65.9%) 중심으로 처리 예정. 향후 저차수 노드 정리 또는 추출 프롬프트 개선 여지
- **추가 정규화 여지**: 정밀도 우선 설계상 의심되는 이형은 보수적으로 미병합. 필요 시 육안 확인 후 `insight_kg_lookup_add_obvious.py`에 규칙 추가 → 체이닝 해소 재실행으로 안전하게 확장 가능

---

## 8. 관련 파일

### 8.1 파이프라인 스크립트

| 단계 | 경로 |
|------|------|
| 배치 적재 | `dev/data_pipeline/data_pipeline_report_batch_loader.py` |
| 리포트 전처리(비동기) | `dev/data_pipeline/data_pipeline_report_refiner_async.py` |
| KG 구축 | `dev/insight_kg/insight_kg_builder.py` |
| 관계 재분류(비동기) | `dev/insight_kg/insight_kg_relation_categorizer_async.py` |
| 정규화 룩업 생성(v2) | `dev/insight_kg/insight_kg_entity_normalizer_builder_v2.py` |
| 체이닝 해소 | `dev/insight_kg/insight_kg_lookup_resolve_chains.py` |
| 명백한 이형 보강 | `dev/insight_kg/insight_kg_lookup_add_obvious.py` |
| 정규화 적용 | `dev/insight_kg/insight_kg_entity_normalizer_applier.py` |
| 검증 | `dev/insight_kg/insight_kg_validate_normalized.py` |

### 8.2 산출물

```
data/NEWS/insight_kg/
├── graph_chunk_entity_relation.graphml            (원본, 12.76 MB)
├── graph_chunk_entity_relation_normalized.graphml (정규화, 11.67 MB) ★
├── kv_store_full_docs.json / kv_store_full_entities.json / kv_store_full_relations.json
├── kv_store_text_chunks.json / kv_store_*_chunks.json
├── kv_store_llm_response_cache.json
├── vdb_chunks.json / vdb_entities.json / vdb_relationships.json  (NanoVectorDB)
└── ...

data/NEWS/
└── entity_normalization_lookup.json               (룩업, 296개 매핑) ★

backup/data/InsightKG/
└── pilot_*                                          (파일럿 v3 백업, 15개 파일)

★ = Phase 2(뉴스 매핑)에서 사용
```

### 8.3 설계 문서

- 구축 상세 보고서: `Markdown/Module/Module_News Grouper_Insight_KG_Construction.md` (Section 13 = v4)
