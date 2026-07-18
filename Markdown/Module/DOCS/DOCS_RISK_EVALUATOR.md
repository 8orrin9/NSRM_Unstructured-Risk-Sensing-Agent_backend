# Agent_4 Risk Evaluator 문서

**작성일**: 2026-07-08  
**버전**: 1.0  
**담당**: POC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [핵심 개념](#2-핵심-개념)
3. [데이터 흐름](#3-데이터-흐름)
4. [출력 구조 상세](#4-출력-구조-상세)
5. [Risk 판정 기준](#5-risk-판정-기준)
6. [Issue Type 분류](#6-issue-type-분류)
7. [다중 시나리오 평가](#7-다중-시나리오-평가)
8. [실전 예시](#8-실전-예시)
9. [설정 및 구성](#9-설정-및-구성)
10. [FAQ](#10-faq)

---

## 1. 개요

### 1.1 목적

Agent_4 Risk Evaluator는 **Agent_3 DB 검색 결과를 분석하여 실질적인 공급망 Risk 여부를 판정**하는 모듈입니다.

### 1.2 주요 기능

- ✅ **Risk 판정**: 뉴스 이벤트가 삼성전자 DS 공급망에 실질적 영향을 주는지 판단
- ✅ **Risk 요인 식별**: 구체적 Risk 요인 추출 (공급 집중도, 지정학적 리스크 등)
- ✅ **이벤트 시점 분류**: ONGOING (진행 중) vs SCHEDULED (예정)
- ✅ **Issue Type 결정**: ISSUE (즉각 조치), SMD (모니터링 필요), NONE (무시)
- ✅ **다중 시나리오 평가**: 여러 Risk 관점을 종합하여 최종 판정

### 1.3 입출력

| 구분 | 설명 |
|------|------|
| **입력** | Agent_3 출력 (뉴스 + Risk 시나리오 + DB 검색 결과) |
| **출력** | Risk 판정 + Issue Type + 이벤트 시점 분류 |

---

## 2. 핵심 개념

### 2.1 문제 정의

**수동 방식의 한계**:
```
Agent_3가 "미국 내 34개 생산지" 발견
↓
담당자가 수동으로 판단:
- "이게 진짜 Risk인가?"
- "즉각 조치가 필요한가?"
- "이벤트가 이미 발생했나?"
↓
주관적 판단 + 일관성 부족 + 시간 소요
```

**자동화 솔루션**:
```
Agent_3 검색 결과 (미국 34개 생산지)
↓
Agent_4가 자동으로:
  1. Risk 여부 판정 (논리적 인과관계 확인)
  2. Risk 요인 식별 (지정학적 리스크, 공급 집중도)
  3. 이벤트 시점 분류 (ONGOING/SCHEDULED)
  4. Issue Type 결정 (ISSUE/SMD/NONE)
↓
is_risk=False → "뉴스-DB 간 인과관계 부족, 단순 외교 협력" (3초 소요)
```

### 2.2 핵심 가치

1. **객관성**: 일관된 기준으로 Risk 판정 (도메인 지식 + 논리적 인과관계)
2. **구체성**: "~할 수 있음" 금지, 구체적 Risk 요인 명시
3. **우선순위화**: Issue Type으로 조치 우선순위 자동 결정
4. **시점 인식**: ONGOING vs SCHEDULED로 긴급성 파악

---

## 3. 데이터 흐름

### 3.1 전체 프로세스

```
┌─────────────────────────────────────────────────────────────────┐
│ [INPUT] Agent_3 출력                                            │
│ • 뉴스 (title_ko, summary_ko, content_ko)                       │
│ • Risk 시나리오 (risk_scenario, entities)                       │
│ • DB 검색 결과 (search_results_multi[])                         │
│ • 생성된 SQL (generated_sqls[])                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 1] 입력 검증 (validate_input)                            │
│ • 필수 필드 확인 (risk_scenario, search_results_multi)         │
│ • 시나리오 개수 확인 (단일 vs 다중)                            │
│ OUTPUT: validated_input                                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
                    [조건부 분기]
        ┌───────────────────┴──────────────────┐
        ↓ (단일 시나리오)                ↓ (다중 시나리오)
┌─────────────────────────────┐   ┌─────────────────────────────┐
│ [STEP 2A] Risk 평가         │   │ [STEP 2B] 다중 시나리오 평가│
│ (evaluate_risk_relevance)   │   │ (evaluate_multi_scenarios)  │
│                              │   │                              │
│ • LLM이 단일 시나리오 분석  │   │ • 시나리오별 Risk 판정      │
│ • 뉴스-DB 간 인과관계 확인  │   │ • 시나리오별 점수 산출      │
│ • Risk 요인 식별            │   │   ↓                          │
│                              │   │ [STEP 2C] Risk 통합 결정    │
│ OUTPUT:                      │   │ (aggregate_risk_decision)   │
│ - is_risk                    │   │                              │
│ - risk_score                 │   │ • 시나리오별 점수 집계      │
│ - risk_justification         │   │ • 가중평균으로 최종 판정    │
│ - risk_factors               │   │                              │
│                              │   │ OUTPUT:                      │
│                              │   │ - is_risk (최종)            │
│                              │   │ - risk_score (최종)         │
│                              │   │ - risk_justification        │
│                              │   │ - risk_factors              │
└─────────────────────────────┘   └─────────────────────────────┘
        └───────────────────┬──────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 3] 이벤트 시점 분류 (classify_event_timing)              │
│ • 뉴스 제목/본문 시제 분석                                      │
│ • ONGOING: 과거형/현재형 (이미 발생, 진행 중)                 │
│ • SCHEDULED: 미래형/추측 (예정, 계획)                          │
│ OUTPUT: event_timing, event_timing_confidence, justification    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 4] Issue Type 결정 (determine_issue_type)                │
│ • is_risk + event_timing 조합으로 Issue Type 결정              │
│                                                                  │
│ [ISSUE] is_risk=True + event_timing=ONGOING                     │
│   → 즉각 조치 필요 (Priority: HIGH/CRITICAL)                   │
│                                                                  │
│ [SMD] is_risk=True + event_timing=SCHEDULED                     │
│   → 모니터링 필요 (Priority: MEDIUM/LOW)                       │
│                                                                  │
│ [NONE] is_risk=False                                            │
│   → 조치 불필요 (Priority: NONE)                               │
│                                                                  │
│ OUTPUT: issue_type, issue_priority                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [OUTPUT] Risk 평가 결과                                         │
│ • Risk 판정 (is_risk, risk_score, risk_justification)          │
│ • Risk 요인 (risk_factors[])                                    │
│ • 이벤트 시점 (event_timing, event_timing_confidence)           │
│ • Issue Type (issue_type, issue_priority)                       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 노드별 상세 설명

#### validate_input
- **역할**: 입력 데이터 검증 및 시나리오 개수 확인
- **분기 조건**:
  - `len(risk_scenarios) > 1` → 다중 시나리오 평가 경로
  - `len(risk_scenarios) <= 1` → 단일 시나리오 평가 경로

#### evaluate_risk_relevance (단일 시나리오)
- **역할**: LLM을 통한 Risk 판정
- **입력**: 뉴스 + Risk 시나리오 + DB 검색 결과
- **처리**:
  1. 뉴스 이벤트 → DB 엔티티 → 공급망 영향 인과관계 확인
  2. 도메인 지식 활용 (반도체 공급망 의존도, 집중도)
  3. 구체적 Risk 요인 추출

#### evaluate_multi_scenarios (다중 시나리오)
- **역할**: 여러 Risk 관점을 개별 평가
- **처리**: 시나리오별로 `evaluate_risk_relevance` 로직 적용

#### aggregate_risk_decision (다중 시나리오 통합)
- **역할**: 시나리오별 점수를 종합하여 최종 Risk 판정
- **처리**:
  ```python
  # 가중평균 (신뢰도 기반)
  total_score = sum(s["risk_score"] * s["confidence"] for s in scenarios)
  total_weight = sum(s["confidence"] for s in scenarios)
  final_score = total_score / total_weight
  
  # 최종 판정
  is_risk = final_score >= 0.5
  ```

#### classify_event_timing
- **역할**: 이벤트 시점 분류
- **처리**:
  - 제목/본문에서 시제 키워드 탐지
  - ONGOING 키워드: "발생", "시행", "중단됨", "완료", "발표됨"
  - SCHEDULED 키워드: "예정", "계획", "~할 것으로 예상", "가능성"

#### determine_issue_type
- **역할**: Issue Type 결정
- **처리**:
  ```python
  if not is_risk:
      issue_type = "NONE"
      issue_priority = "NONE"
  elif event_timing == "ONGOING":
      issue_type = "ISSUE"
      issue_priority = "HIGH" if risk_score >= 0.7 else "CRITICAL"
  elif event_timing == "SCHEDULED":
      issue_type = "SMD"
      issue_priority = "MEDIUM" if risk_score >= 0.6 else "LOW"
  ```

---

## 4. 출력 구조 상세

### 4.1 전체 구조

```json
{
  "extraction_date": "2026-07-08T16:51:42.406826",
  "agent3_input_file": "...",
  "total_articles": 34,
  
  "statistics": {
    "issue_count": 0,
    "smd_count": 14,
    "none_count": 20,
    "risk_distribution": {
      "is_risk_true": 0,
      "is_risk_false": 34
    },
    "event_timing_distribution": {
      "ONGOING": 20,
      "SCHEDULED": 14
    },
    "average_risk_score": 0.06,
    "average_event_timing_confidence": 0.87
  },
  
  "results": [
    { /* 뉴스별 Risk 평가 결과 */ }
  ]
}
```

### 4.2 뉴스별 결과 구조

```json
{
  // ===== 입력 정보 (Agent_3 출력) =====
  "news_id": "a05f7c30878c2d4cbba4cd5addb76682",
  "title_ko": "중국 정부와 온두라스 정부가 일대일로 협력 문서에 서명하다",
  "summary_ko": "...",
  "content_ko": "...",
  "keywords": [...],
  "mapped_tags": [...],
  "risk_scenario": "중국과 온두라스 간의 일대일로 협력 강화로 인해 라스가스의 가스 공급망에 변화가 예상되며, 이로 인해 중남미 지역의 에너지 자원 가격 상승이 우려됨",
  "risk_scenario_entities": ["중국", "온두라스", "라스가스", "가스"],
  "generated_sql": "SELECT ...",
  "search_target_entities": ["SUPPLIER_MASTER"],
  
  // ===== STEP 2: Risk 평가 =====
  "is_risk": false,
  "risk_score": 0.05,
  "risk_justification": "뉴스는 중국-온두라스 간 일대일로 협력 MOU 체결에 관한 외교·인프라 협력 이슈이며, 삼성전자 DS 반도체 공급망의 원재료·특수가스·장비·물류 거점과 직접 연결되는 내용이 확인되지 않습니다. DB 조회에서도 매핑된 라스가스(RasGas Qatar)가 활성 협력사로 확인되지 않아, 뉴스 이벤트가 삼성전자 DS 공급망 엔티티에 영향을 준다는 인과관계가 성립하지 않습니다.",
  "risk_factors": [],
  
  // ===== STEP 3: 이벤트 시점 분류 =====
  "event_timing": "ONGOING",
  "event_timing_confidence": 0.98,
  "event_timing_justification": "뉴스 제목과 본문에서 '서명했다', '서명되었습니다'라고 과거형으로 명시되어 있습니다. 이는 예정이나 계획이 아니라 이미 발생·완료된 사건이므로 ONGOING으로 분류됩니다.",
  
  // ===== STEP 4: Issue Type 결정 =====
  "issue_type": "NONE",
  "issue_priority": "NONE",
  
  // ===== 메타데이터 =====
  "original_language": "korean",
  "mapping_quality_score": 0.2
}
```

### 4.3 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `is_risk` | bool | Risk 여부 (True/False) |
| `risk_score` | float | Risk 점수 (0.0 ~ 1.0) |
| `risk_justification` | str | 판정 근거 (2-3문장, 구체적) |
| `risk_factors[]` | List[str] | 식별된 Risk 요인들 |
| `event_timing` | str | "ONGOING" 또는 "SCHEDULED" |
| `event_timing_confidence` | float | 시점 분류 신뢰도 (0.0 ~ 1.0) |
| `event_timing_justification` | str | 시점 분류 근거 |
| `issue_type` | str | "ISSUE", "SMD", "NONE" |
| `issue_priority` | str | "CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE" |

---

## 5. Risk 판정 기준

### 5.1 Risk 인과관계 체인

Agent_4는 다음 **인과관계 체인**이 성립해야 Risk로 판정합니다:

```
뉴스 이벤트 → DB 엔티티 → 삼성전자 DS 공급망 영향
```

**예시 (Risk=True)**:
```
[뉴스] 중국 희토류 수출 제한
  ↓
[DB 검색] 미국 내 생산지 34곳이 희토류 사용
  ↓
[공급망 영향] 희토류 70% 중국 의존 → 미국 생산지 공급 차질 예상
  ↓
Risk=True, risk_factors=["공급 집중도 (중국 70%)", "지정학적 리스크"]
```

**예시 (Risk=False)**:
```
[뉴스] 중국-온두라스 일대일로 MOU 체결
  ↓
[DB 검색] 라스가스(카타르 기업)가 검색됨 (부적절한 매칭)
  ↓
[공급망 영향] 라스가스는 비활성 협력사 + 뉴스와 무관
  ↓
Risk=False, risk_factors=[] (인과관계 미성립)
```

### 5.2 Risk 판정 체크리스트

Agent_4는 다음 체크리스트를 확인합니다:

- [ ] 뉴스 이벤트가 DB 검색 결과의 엔티티와 직접 관련되는가?
- [ ] DB 검색 결과가 비어 있지 않은가? (result_count > 0)
- [ ] 검색된 엔티티가 활성 상태인가? (is_active = 1)
- [ ] 뉴스 이벤트가 해당 엔티티에 구체적 영향을 주는가?
- [ ] 도메인 지식상 영향이 타당한가? (예: 희토류 → 반도체 제조)

**하나라도 미충족 시 Risk=False**

### 5.3 Risk Score 산출

```python
# 기본 점수
base_score = 0.0

# 인과관계 성립 시
if causal_chain_valid:
    base_score += 0.5

# 도메인 규칙 매칭 시
if domain_rules_matched:
    base_score += 0.2

# 공급 집중도 높음 시
if supply_concentration_high:
    base_score += 0.2

# 지정학적 리스크 시
if geopolitical_risk:
    base_score += 0.1

# 최종 점수
risk_score = min(base_score, 1.0)

# 판정
is_risk = risk_score >= 0.5
```

---

## 6. Issue Type 분류

### 6.1 Issue Type 정의

| Issue Type | 정의 | 우선순위 | 조건 |
|-----------|------|----------|------|
| **ISSUE** | 즉각 조치 필요 | HIGH/CRITICAL | is_risk=True + event_timing=ONGOING |
| **SMD** | 모니터링 필요 (Situation Monitoring & Development) | MEDIUM/LOW | is_risk=True + event_timing=SCHEDULED |
| **NONE** | 조치 불필요 | NONE | is_risk=False |

### 6.2 Issue Priority 결정

```python
if issue_type == "ISSUE":
    if risk_score >= 0.7:
        issue_priority = "CRITICAL"  # 즉각 대응팀 소집
    else:
        issue_priority = "HIGH"      # 당일 내 조치 필요
        
elif issue_type == "SMD":
    if risk_score >= 0.6:
        issue_priority = "MEDIUM"    # 주간 모니터링
    else:
        issue_priority = "LOW"       # 월간 모니터링
        
else:  # NONE
    issue_priority = "NONE"
```

### 6.3 Issue Type 분포 예시

```json
{
  "statistics": {
    "issue_count": 0,      // 즉각 조치 필요: 0건
    "smd_count": 14,       // 모니터링 필요: 14건
    "none_count": 20       // 조치 불필요: 20건
  }
}
```

---

## 7. 다중 시나리오 평가

### 7.1 개념

**다중 시나리오 평가** = 하나의 뉴스를 **여러 Risk 관점**에서 평가하여 **종합 판정**

### 7.2 작동 방식

#### 1단계: 시나리오별 Risk 평가

```python
risk_scenarios = [
    {
        "scenario_id": "cluster_001",
        "risk_scenario": "SK하이닉스 공장 화재사고로 반도체 생산 차질",
        "confidence": 0.9
    },
    {
        "scenario_id": "cluster_002",
        "risk_scenario": "우크라이나 전쟁으로 네온가스 공급 중단",
        "confidence": 0.85
    }
]

# 시나리오별 Risk 평가
scenario_risks = []
for scenario in risk_scenarios:
    risk_result = evaluate_risk_relevance(scenario)
    scenario_risks.append({
        "scenario_id": scenario["scenario_id"],
        "is_risk": risk_result["is_risk"],
        "risk_score": risk_result["risk_score"],
        "confidence": scenario["confidence"]
    })
```

#### 2단계: 가중평균으로 최종 Risk 판정

```python
# 가중평균 계산
total_score = sum(
    r["risk_score"] * r["confidence"]
    for r in scenario_risks
)
total_weight = sum(r["confidence"] for r in scenario_risks)

final_risk_score = total_score / total_weight

# 최종 판정
final_is_risk = final_risk_score >= 0.5

# Risk 요인 통합
final_risk_factors = list(set(
    factor
    for r in scenario_risks
    for factor in r.get("risk_factors", [])
))
```

### 7.3 다중 시나리오 출력

```json
{
  "risk_scenarios": [
    {
      "scenario_id": "cluster_001",
      "risk_scenario": "SK하이닉스 공장 화재사고로 반도체 생산 차질",
      "is_risk": true,
      "risk_score": 0.85,
      "risk_factors": ["생산 집중도", "단일 공급사 의존"]
    },
    {
      "scenario_id": "cluster_002",
      "risk_scenario": "우크라이나 전쟁으로 네온가스 공급 중단",
      "is_risk": true,
      "risk_score": 0.75,
      "risk_factors": ["공급 집중도 (우크라이나 70%)", "지정학적 리스크"]
    }
  ],
  
  // 최종 판정 (가중평균)
  "is_risk": true,
  "risk_score": 0.81,  // (0.85 * 0.9 + 0.75 * 0.85) / (0.9 + 0.85)
  "risk_justification": "두 시나리오 모두 Risk로 판정. SK하이닉스 화재는 생산 집중도 위험, 우크라이나 네온가스는 공급 집중도 위험.",
  "risk_factors": ["생산 집중도", "단일 공급사 의존", "공급 집중도 (우크라이나 70%)", "지정학적 리스크"]
}
```

---

## 8. 실전 예시

### 8.1 뉴스 입력

```json
{
  "news_id": "a05f7c30878c2d4cbba4cd5addb76682",
  "title_ko": "중국 정부와 온두라스 정부가 일대일로 협력 문서에 서명하다",
  "summary_ko": "중국 정부와 온두라스 정부는 2023년 6월 12일, 실크로드 경제벨트 및 21세기 해상 실크로드 이니셔티브에 관한 양해각서에 서명했다.",
  "risk_scenario": "중국과 온두라스 간의 일대일로 협력 강화로 인해 라스가스의 가스 공급망에 변화가 예상되며, 이로 인해 중남미 지역의 에너지 자원 가격 상승이 우려됨",
  "generated_sql": "SELECT sup.name_kor AS 협력사명, sup.country AS 국가 FROM SUPPLIER_MASTER sup WHERE sup.name_kor LIKE '%라스가스%' AND sup.is_active = 1",
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "result_count": 0,
      "results": []  // 검색 결과 없음
    }
  ]
}
```

### 8.2 STEP 2: Risk 평가

```json
{
  "is_risk": false,
  "risk_score": 0.05,
  "risk_justification": "뉴스는 중국-온두라스 간 일대일로 협력 MOU 체결에 관한 외교·인프라 협력 이슈이며, 삼성전자 DS 반도체 공급망의 원재료·특수가스·장비·물류 거점과 직접 연결되는 내용이 확인되지 않습니다. DB 조회에서도 매핑된 라스가스(RasGas Qatar)가 활성 협력사로 확인되지 않아, 뉴스 이벤트가 삼성전자 DS 공급망 엔티티에 영향을 준다는 인과관계가 성립하지 않습니다. 따라서 중남미 에너지 가격 상승이나 라스가스 공급망 변화 시나리오는 근거가 부족한 추정입니다.",
  "risk_factors": []
}
```

**판정 근거**:
1. DB 검색 결과가 비어 있음 (result_count = 0)
2. 라스가스는 카타르 기업 + 온두라스와 무관
3. 뉴스-DB 간 인과관계 미성립
4. 단순 외교 협력 MOU (공급망 영향 없음)

### 8.3 STEP 3: 이벤트 시점 분류

```json
{
  "event_timing": "ONGOING",
  "event_timing_confidence": 0.98,
  "event_timing_justification": "뉴스 제목과 본문에서 '서명했다', '서명되었습니다'라고 과거형으로 명시되어 있습니다. 이는 예정이나 계획이 아니라 이미 발생·완료된 사건이므로 ONGOING으로 분류됩니다."
}
```

### 8.4 STEP 4: Issue Type 결정

```json
{
  "issue_type": "NONE",
  "issue_priority": "NONE"
}
```

**근거**: `is_risk=False` → 조치 불필요

---

## 9. 설정 및 구성

### 9.1 주요 설정 (config.py)

```python
# ===== LLM 모델 설정 =====
RISK_EVALUATION_MODEL = "gpt-5.5"          # Risk 평가용 (추론 특화)
EVENT_CLASSIFICATION_MODEL = "gpt-5.5"     # 이벤트 분류용

# ===== 타임아웃 설정 =====
RISK_EVALUATION_TIMEOUT = 60               # Risk 평가 타임아웃 (초)
EVENT_CLASSIFICATION_TIMEOUT = 30          # 이벤트 분류 타임아웃 (초)

# ===== 입출력 파일 =====
AGENT3_OUTPUT_FILE = PROJECT_ROOT / "dev" / "Agent_3_DB_Searcher" / "output" / "output_db_searcher.json"

# ===== 임계값 설정 =====
MIN_RISK_SCORE_THRESHOLD = 0.5             # Risk 점수 최소값
MIN_EVENT_TIMING_CONFIDENCE = 0.6          # 이벤트 시점 신뢰도 최소값
```

### 9.2 디렉터리 구조

```
dev/Agent_4_Risk_Evaluator/
├── config.py                    # 설정 파일
├── graph.py                     # LangGraph 워크플로우 정의
├── prompts.py                   # LLM 프롬프트
├── nodes/                       # 노드별 구현
│   ├── __init__.py             # State 정의
│   ├── validate_input.py       # 입력 검증
│   ├── evaluate_risk_relevance.py      # Risk 평가 (단일)
│   ├── evaluate_multi_scenarios.py     # 다중 시나리오 평가
│   ├── aggregate_risk_decision.py      # Risk 통합 결정
│   ├── classify_event_timing.py        # 이벤트 시점 분류
│   └── determine_issue_type.py         # Issue Type 결정
├── utils/                       # 유틸리티
│   └── llm_risk_evaluator.py   # LLM Risk 평가
├── scripts/
│   └── run_risk_evaluator.py   # 실행 스크립트
└── output/
    └── output_risk_evaluator.json # 최종 출력
```

---

## 10. FAQ

### Q1. Risk Score는 어떻게 산출되나요?

**A**: 
- 인과관계 성립 (0.5) + 도메인 규칙 (0.2) + 공급 집중도 (0.2) + 지정학적 리스크 (0.1)
- 최종 점수는 0.0 ~ 1.0 범위
- `is_risk = risk_score >= 0.5`

### Q2. ONGOING vs SCHEDULED 분류 기준은?

**A**: 
- **ONGOING**: 과거형/현재형 (발생, 시행, 중단됨, 완료, 발표됨)
- **SCHEDULED**: 미래형/추측 (예정, 계획, ~할 것으로 예상, 가능성)

### Q3. Issue Priority는 어떻게 결정되나요?

**A**: 
```python
ISSUE (ONGOING):
  risk_score >= 0.7 → CRITICAL (즉각 대응)
  risk_score < 0.7  → HIGH (당일 조치)

SMD (SCHEDULED):
  risk_score >= 0.6 → MEDIUM (주간 모니터링)
  risk_score < 0.6  → LOW (월간 모니터링)

NONE: NONE
```

### Q4. 다중 시나리오 평가는 언제 사용되나요?

**A**: 
- Agent_3가 여러 Risk 시나리오를 생성한 경우 (ENABLE_MULTI_SCENARIO=True)
- 하나의 뉴스를 여러 관점에서 평가하여 종합 판정

### Q5. Risk 판정이 너무 엄격한 경우는?

**A**: 
- `MIN_RISK_SCORE_THRESHOLD` 하향 조정 (0.5 → 0.4)
- 프롬프트에서 "구체적 인과관계 확인" 요구사항 완화

### Q6. 성능은 어느 정도인가요?

**A**: 
- 뉴스 1개당 처리 시간: 평균 **4-6초**
- LLM 호출 횟수: Risk 평가(1회) + 이벤트 분류(1회) = 총 2회
- 다중 시나리오: 시나리오 개수만큼 LLM 호출 증가

---

## 부록

### A. Risk 판정 예시

| 뉴스 | DB 검색 결과 | Risk 판정 | 근거 |
|------|-------------|----------|------|
| 중국 희토류 수출 제한 | 미국 34개 생산지 (희토류 사용) | is_risk=True | 희토류 70% 중국 의존 |
| 온두라스 외교 협력 | 라스가스 (검색 실패) | is_risk=False | 인과관계 미성립 |
| 호르무즈 해협 봉쇄 | 물류 경로 34개 | is_risk=True | 물류 병목 |

### B. 관련 문서

- Agent_3 DB Searcher 문서: `Markdown/Module/DOCS/DOCS_DB_SEARCHER.md`

### C. 변경 이력

| 날짜 | 버전 | 내용 |
|------|------|------|
| 2026-07-08 | 1.0 | 최초 작성 (다중 시나리오 평가 포함) |

---

**문서 작성자**: POC-A 개발팀  
**최종 업데이트**: 2026-07-08
