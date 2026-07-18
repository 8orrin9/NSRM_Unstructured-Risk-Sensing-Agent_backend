# Golden Dataset (가짜 뉴스) 생성 방법 및 결과

공급망 Risk-Sensing 5-Agent 파이프라인의 **최신 평가지표를 모두 측정**하기 위한 정답(Ground Truth) 뉴스 데이터셋의 생성 방법론과 결과를 정리한다.

- **생성 스크립트**: `dev/Evaluation_Golden Dataset Creation/generate_golden_dataset.py`
- **보조 스크립트**: `dev/Evaluation_Golden Dataset Creation/add_natural_disaster_tags.py`
- **산출물**: `data/NEWS/golden_dataset.json` (총 51건)
- **최종 갱신**: 2026-07-15 (그룹 재정합 + 9-카테고리 전건 부여 + 실제 그룹화 검증 반영)

---

## 1. 배경과 설계 원칙

### 1.1 왜 가짜 뉴스인가
실제 수집 뉴스는 **고객 공급망 DB와의 관련성이 낮아** 평가지표(특히 DB Search, Routing, Cascaded 계열) 측정에 부적합하다. 따라서 파이프라인 각 단계의 정답을 결정론적으로 통제할 수 있는 **합성(가짜) 뉴스**를 생성한다.

### 1.2 핵심 설계 원칙
1. **전 단계 정답 동봉**: 각 뉴스는 파이프라인 모든 단계의 정답 라벨을 함께 보유한다. → Isolated 지표 측정 가능.
2. **FP도 하위 정답 보유**: False Positive 뉴스도 하위 단계 정답을 음성/공집합으로 채운다. → Cascaded 평가에서 **FP 누출의 전파 손실(Propagation Loss)** 측정 가능.
3. **라벨은 코드로 결정론적 계산, 본문만 LLM 생성**: title/content만 OpenAI(gpt-4o-mini)로 생성하고, 정답 라벨은 전부 코드가 계산한다.
4. **DB와 분리 보관**: 뉴스 재수집·재적재가 예정돼 있으므로 `golden_dataset.json`으로만 산출하고 `news_intelligence.db`(NEWS_MASTER)에는 적재하지 않는다.

### 1.3 Source of Truth
- 기준 DB = 현재 **`data/NEWS/news_intelligence.db`의 TAG_MASTER / TAG_KEYWORD_MAP** (실제 `supply_chain.db`와 정합).
- 엑셀(`DB_TAG_Risk Factor Pool_vF.xlsx`)은 **구 버전(협력사 123개)이므로 기준으로 쓰지 않는다.** (현행 DB는 협력사 14개)
- `gt_entities`는 실제 `supply_chain.db`를 **BOM 전개**하여 계산 → 실제 SQL 결과와 정합.

---

## 2. DB O/X 결정론적 통제 원리

라우팅의 핵심 축인 "공급망 DB 조회 결과 유무(DB O/X)"를 **태그 종류로 통제**한다.

| 태그 유형 | db_matched_count | 의미 |
|-----------|------------------|------|
| EVENT (`EVT_*`) | **0** | 검색 힌트일 뿐, DB 직접 매칭 없음 |
| SUPPLIER / SITE / MATERIAL / RAW_MATERIAL | **> 0** | 전부 `supply_chain.db`에서 생성 → 반드시 매칭 |

- **엔티티 태그(SUP/SITE/MAT/RAW)를 심으면 → DB O**
- **EVENT 태그만 심으면 → DB X**

### BOM 전개 (gt_entities 계산 경로)
엔티티 태그 하나를 아래 관계 테이블로 전개해 영향 엔티티 집합을 산출한다.

```
RAW  →(MATERIAL_RAW_MATERIAL_MAP)→ MATERIAL →(SITE_MATERIAL_MAP)→ SITE →(SITE_MASTER)→ SUPPLIER
SUPPLIER →(SITE_MASTER)→ SITE, →(SUPPLIER_RAW_MATERIAL_MAP)→ RAW
SITE.country='中국' →(SITE_MASTER)→ SITE/SUPPLIER → MATERIAL/RAW
```

> 주의: `SITE_MASTER.country`는 supply_chain.db에 **한글**(중국/미국/한국/대만 등)로 저장돼 있어, 태그의 영문 country를 한글로 매핑(EN2KR)한 뒤 조회한다.

---

## 3. 셀 매트릭스 (총 51건)

라우팅은 **(DB결과 O/X) × (Risk O/X) × (시점 진행/예정)** 3축으로 결정된다(Agent_4 `determine_issue_type` 로직과 동일). 이 3축이 곧 데이터셋 셀 구조다.

| 셀 | 조건 | Routing | 건수 | 설명 |
|----|------|---------|------|------|
| **1a** | FP · 완전 무관 | NONE | 5 | 프로야구·아이돌·부동산 등 |
| **1b** | FP · 반도체 언급 함정(리스크 무관) | NONE | 5 | 갤럭시 예약·채용·봉사 등 |
| **2a** | DB O · Risk O · 진행형 | **ISSUE** | 13 | 즉시 대응 |
| **2b** | DB O · Risk O · 예정형 | **SMD** | 8 | 예정 모니터링 |
| **2c** | DB O · Risk X | **SMD** | 6 | 구매 연관(긍정) 뉴스 |
| **2d** | DB X · Risk O | **SMD** | 10 | 리스크지만 당사 BOM 외 (EVENT 태그만) |
| **2e** | DB X · Risk X | NONE(Drop) | 4 | 무관·중립 뉴스 |

> 기존 48건 대비 +3건: 그룹 클러스터를 각 3건으로 맞추기 위해 G2(2a×1) · G3(2d×2) 멤버를 신규 추가(§4).

### Block 1 (FP) vs Block 2 (정상 파이프라인)
- **FP(10건)**: `is_false_positive=True`. News Analyzer의 관련성 필터가 첫 모듈이며, FP는 여기서 걸러진다. 하위 정답은 전부 공집합/음성(`gt_keywords=[]`, `gt_tags=[]`, `gt_entities={}`, `gt_is_risk=False`, `gt_routing="NONE"`).
- **non-FP(38건)**: `is_false_positive=False`. 전 단계 정답을 모두 계산해 보유.

---

## 4. 그룹화(News Grouper) 클러스터

### 4.1 그룹 성립 조건 (Agent_5 코드 확정)
News Grouper는 **본문에서 LLM(gpt-5-mini)이 추출한 엔티티를 KG 노드에 문자열 매칭**한 뒤, 다음 3조건으로 그룹을 만든다(`phase3_group_by_entities.py`, `kg_utils.py`).
1. 두 뉴스의 **공통 매칭 KG 노드 ≥ 2개**
2. 공통 노드 중 **최소 한 쌍이 KG에서 1-hop 이내 연결** (실제 런타임 `max_hop=1`)
3. Louvain 군집 후 **그룹 크기 ≥ 3건** + 인사이트 신뢰도 ≥ 0.6

→ 따라서 그룹 멤버는 **본문에 공유 KG 노드명이 실제로 등장**해야 하고, 클러스터 크기는 최소 3건이어야 한다. (기존 G2·G3가 1건이라 애초에 성립 불가했던 문제를 해소.)

### 4.2 정답(이상적 설계) 클러스터 — 3그룹 × 각 3건
KG 1-hop 연결이 실측 확인된 주제로 재구성. `gt_group` / `gt_group_shared_nodes`(성립 근거 노드쌍) / `gt_should_group` 필드로 표기.

| 그룹 | 주제 | 공유 KG 노드(1-hop) | 멤버 | 셀 |
|------|------|--------------------|------|----|
| **G1** | 중국 희소금속 수출통제 | 중국 – 갈륨 (1-hop) | GD_2a_011, GD_2a_012, GD_2b_023 | 2a·2b |
| **G2** | 미·중 반도체 지정학 규제 | 미국 – 중국 (1-hop) | GD_2a_015, GD_2b_024, GD_2a_049 | 2a·2b |
| **G3** | 첨단 장비·파운드리(ASML) | ASML – EUV (1-hop) | GD_2d_037, GD_2d_050, GD_2d_051 | 2d |

- **구 G2(선전 캡켐)·구 G3(부산항 물류)는 폐기**: 캡켐 핵심 엔티티가 KG에 부재, 부산항 물류 노드가 1-hop 미연결(부산항–화물연대=5hop). 두 뉴스(GD_2a_013·014)는 **단독 뉴스로 강등**(본문 유지, `gt_group=null`).
- G1은 엔티티 태그(RAW_GALLIUM 등) 보유 → **DB O**. G3는 EVENT 태그 위주 → **DB X(2d)**.
- **should-not-group**: risk=True인데 그룹에 속하지 않는 단독 뉴스 22건을 확보(과잉그룹화 억제 평가용). `gt_should_group=false`.

### 4.3 실제 그룹화 검증 결과 및 갭 (중요 인사이트) ⚠️
정답 데이터셋을 **실제 Agent_5 파이프라인(Phase2 엔티티추출 → Phase3 그룹화, `max_hop=1`)에 투입**해 대조한 결과, 정답 설계와 실제 동작 사이에 다음 갭이 관측되었다. **이 갭은 결함이 아니라 News Grouper의 특성·개선점을 정량화한 측정 결과다.**

| 정답 그룹 | 실제 결과 | 판정 |
|-----------|-----------|------|
| **G3** (037/050/051) | 정확히 3건이 한 그룹으로 묶임 | ✅ 정합 |
| **G1** (원자재) | G2와 **하나의 메가클러스터로 병합** | ❌ 분리 실패 |
| **G2** (지정학) | G1과 병합 + 무관 뉴스 흡수 | ❌ 분리 실패 |

관측된 원인:
1. **엔티티 추출의 과일반화**: 지정학 계열 뉴스 대부분에서 LLM이 `미국 / 중국 / 수출통제 / 상무부 / 반도체` 같은 **범용 노드**를 공통 추출한다. 이들이 KG에서 서로 1-hop이라, 주제가 인접한 G1(원자재 통제)과 G2(규제)가 공통노드 ≥2를 만족해 **한 덩어리**로 묶인다.
2. **허브 노드 과잉그룹화**: G2의 공유노드 `미국(deg=360) / 중국(deg=688)`은 초대형 허브다. "중국"만 공유하는 무관 뉴스(GD_2a_020/021, GD_2b_026/029, GD_2c_031 등 7건)까지 클러스터에 흡수되었다.
3. **대비되는 G3의 성공**: `ASML / EUV / 극자외선 노광장비`는 반도체 장비 도메인에만 등장하는 **특이(저차수) 노드**라, 오염 없이 정확히 3건만 묶였다.

→ **개선 방향**: (a) 엔티티 추출 시 국가·범용 정책어 등 초빈출 노드 억제/불용어화, (b) 허브 노드 공유에 IDF 이상의 페널티 강화, (c) 그룹 판정에 "특이 노드 최소 1개 공유" 조건 추가 검토. **정답(`gt_group`)은 이상적 설계(G1/G2/G3)를 그대로 유지**하며, 이 갭을 그룹화 품질 평가의 지표(정밀도/오그룹화율)로 활용한다.

> 참고: Agent_4의 그룹화 기반 **우선순위 +1단계 상향**은 실제 News Grouper 출력(`original_news_ids`)에 의존하므로, 본 데이터셋 라벨에는 base_priority만 부여한다(§5.1).

---

## 5. 정답 라벨 스키마

각 뉴스는 아래 22개 키를 갖는다.

| 필드 | 설명 | 산출 방식 |
|------|------|-----------|
| `news_id` | `GD_<cell>_<seq>` (예: GD_2a_011) | 코드 |
| `cell` / `group` | 셀 코드 / 그룹 클러스터(레거시 표기, `gt_group`과 동일값) | 코드 |
| `title` / `content` | 뉴스 제목 / 본문(300~800자) | **LLM (gpt-4o-mini)** |
| `source` / `published_date` / `brief` | 출처 / 발행일 / 사건 개요 | 코드 |
| `is_false_positive` | FP 여부 | 코드 |
| `gt_keywords` | News Analyzer 정답 키워드 (태그 primary keyword) | 코드 |
| `gt_tags` | Tag Mapper 정답 태그 ID | 코드 |
| `gt_entities` | DB Searcher 정답 엔티티 (suppliers/sites/materials/raw_materials) | **BOM 전개** |
| `has_db_match` | DB 조회 결과 유무 | 코드 |
| `gt_is_risk` | Risk 여부 | 코드 |
| `gt_event_timing` | 발현 시점 (ONGOING/SCHEDULED/null) | 코드 |
| `gt_routing` | 최종 라우팅 (ISSUE/SMD/NONE) | 코드 (3축 규칙) |
| `gt_issue_priority` | 우선순위 (HIGH/MEDIUM/LOW/NONE) | 코드 (`determine_issue_type` base_priority) |
| `gt_severity` | frontend 심각도 (high/medium/low/null) | issue_priority 매핑 |
| `risk_category_name` | 9개 Risk 카테고리 중 1개 (**전건 부여**) | 코드 |
| `gt_group` | News Grouper 정답 그룹 (G1/G2/G3/null) | 코드 |
| `gt_group_shared_nodes` | 그룹 성립 근거 KG 공유 노드쌍 | 코드 (KG 실측) |
| `gt_should_group` | 그룹화 대상 여부 (bool) | 코드 |

> **`risk_category_name`은 전 51건에 부여**된다("관련 Risk Factor 카테고리"). 리스크 판정 자체는 `gt_is_risk`가 담당하므로, 무관 뉴스(FP 포함)도 소재 기준 근접 카테고리를 갖는 것과 충돌하지 않는다.

### 5.1 Routing / Priority / Severity 매핑

| DB | Risk | 시점 | routing | issue_priority | severity |
|----|------|------|---------|----------------|----------|
| O | O | 진행형 | ISSUE | HIGH | high |
| O | O | 예정형 | SMD | MEDIUM | medium |
| O | X | — | SMD | LOW | low |
| X | O | — | SMD | LOW | low |
| X | X | — | NONE | NONE | null |

> ⚠️ **severity 주의**: Agent_4가 실제 내는 심각도 값은 `issue_priority`(결정론적)이며, frontend가 쓰는 4단계 `severity` 컬럼은 **backend 산출 로직이 없이 랜덤 더미**(`backend/scripts/update_active_news_severity.py`)로 채워진 상태다. 따라서 issue_priority를 근사 매핑해 정답으로 부여하되, 산출 근거가 없는 `critical` 등급은 부여하지 않는다. critical 산출 로직이 정의되면 재정의 필요.

---

## 6. 생성 프로세스 & 실행법

### 6.1 사전 준비: 자연재해&기후 EVENT 태그 편입
9번째 Risk 카테고리 "자연재해&기후"의 EVENT 태그가 DB에 누락돼 있었다. 다른 카테고리와 동일한 명명/스키마 규칙으로 생성해 편입했다.

```bash
python "dev/Evaluation_Golden Dataset Creation/add_natural_disaster_tags.py"
```
- 엑셀 `2. Keyword Set`의 NATURAL_DISASTER 행 → `EVT_한파/폭염/가뭄/공장화재/산불/화학공장폭발` (6개)
- 결과: TAG_MASTER +12행(KR/GLOBAL), TAG_KEYWORD_MAP +48행
- `db_matched_count=0`, `target_table_column=''` (EVENT 규칙)
- 실행 전 news_intelligence.db 자동 백업, 재실행 방지 가드 내장

### 6.2 본문 생성 (LLM)
```bash
python "dev/Evaluation_Golden Dataset Creation/generate_golden_dataset.py"
```
- 시나리오별 `brief`, 톤(리스크/시점), 필수 포함 키워드를 프롬프트에 주입
- `{"title":..., "content":...}` JSON 형식으로 300~800자 한국어 기사 생성

### 6.3 라벨 재계산 + 신규/재생성분만 본문 생성 (`--relabel`)
라벨 로직이 바뀌었을 때, 기존 본문은 보존한 채 정답만 갱신한다. 단 **산출물에 없는 신규 항목**과 **`regen_body=True`로 지정한 항목**만 LLM으로 본문을 (재)생성한다(최소 비용).
```bash
python "dev/Evaluation_Golden Dataset Creation/generate_golden_dataset.py" --relabel
```
- 그룹 재정합 시 이 모드로 신규 G2/G3 멤버 3건 + 재생성 대상(공유노드 추가 필요분)만 생성했다.

### 6.4 검증만 (라벨 생성 + 커버리지 리포트, LLM 미호출)
```bash
python "dev/Evaluation_Golden Dataset Creation/generate_golden_dataset.py" --relabel --dry-run
```
- 커버리지·정합성 외에 **그룹 공유노드의 KG 1-hop 연결성**을 `networkx`로 자동 검증한다(§4.1 기준과 동일).

### 6.5 실제 그룹화 검증 (Agent_5 파이프라인 투입)
데이터셋을 News Grouper Phase2→Phase3(`max_hop=1`)에 투입해 실제 그룹화 결과를 정답과 대조한다(LLM 비용 발생).
```bash
python temp/run_grouper_on_golden.py
```
- 결과는 §4.3 참조(정답 설계 대비 실제 동작 갭 측정).

> 실행 환경: Windows에서 `python`(=python3) 사용, `.venv` 활성화 필요, `PYTHONIOENCODING=utf-8` 권장.

---

## 7. 생성 결과 (최종)

- **총 51건**, 본문 길이 402~680자 (평균 547자)

**[셀 분포]** `1a:5, 1b:5, 2a:13, 2b:8, 2c:6, 2d:10, 2e:4`

**[Routing 분포]** `ISSUE:13, SMD:24, NONE:14`

**[issue_priority 분포]** `HIGH:13, MEDIUM:8, LOW:16, NONE:14`

**[severity 분포]** `high:13, medium:8, low:16, null:14`

**[FP]** `false_positive:10, non_FP:41`

**[9개 Risk 카테고리 커버리지]** (전 51건 부여, 전부 ≥1건)

| 카테고리 | 건수 |
|----------|------|
| 기술&지식재산 | 9 |
| ESG & Compliance | 9 |
| 지정학 & 규제 | 6 |
| 재무&신용 Risk | 6 |
| 공급집중&단일소싱 | 6 |
| 물류&인프라 | 5 |
| 원자재&희소물질 | 5 |
| 사이버&데이터 | 3 |
| 자연재해&기후 | 2 |

**[정합성 검증]**
- 태그 유효성: 모든 `gt_tags`가 TAG_MASTER에 존재 (불일치 0)
- DB O/X 정합성: 셀 기대치와 `has_db_match` 불일치 0
- `risk_category_name`: 전 51건 부여 (누락 0)
- 그룹 정답(이상적 설계): `G1:3, G2:3, G3:3` (각 3건, 성립조건 충족)
- 그룹 공유노드 KG 1-hop 연결성: 중국–갈륨=1, 미국–중국=1, ASML–EUV=1 (전부 PASS)

**[실제 그룹화 검증]** (Agent_5 파이프라인 `max_hop=1` 투입, §4.3)
- **G3**: 정확히 3건 한 그룹 ✅
- **G1·G2**: 하나의 메가클러스터로 병합 + 무관 뉴스 7건 흡수 ❌ (구조적 특성 — 상세 §4.3)

---

## 8. 알려진 제약 및 향후 작업

1. **그룹화 품질 (분리 실패)**: 정답 G1(원자재)·G2(지정학)는 이상적 설계로 유지하나, 실제 Agent_5는 두 그룹을 하나로 병합하고 무관 뉴스까지 흡수한다(§4.3). 이는 엔티티 추출 과일반화 + 허브 노드(중국 deg=688, 미국 deg=360) 과잉그룹화에 기인하며, 데이터셋 자체가 아니라 Grouper 개선 대상이다. 개선 방향(범용 노드 불용어화, 허브 페널티 강화, 특이노드 공유 조건)은 §4.3 참조. 그룹 기반 우선순위 +1단계 상향은 실제 Grouper 출력에 의존하므로 본 데이터셋은 base_priority만 부여(§4.3 말미).
2. **severity `critical`**: backend 산출 로직 정의 후 정답 재부여.
3. **본문 내 날짜**: LLM이 본문에 임의 날짜를 넣는 경우가 있어 `published_date`와 어긋날 수 있음(FP 라벨에는 무영향). 엄격한 일관성이 필요하면 프롬프트에 기준일 주입 후 재생성.
4. **DB 미적재**: 뉴스 재수집·재적재 예정이므로 본 데이터셋은 파일로만 분리 보관.
