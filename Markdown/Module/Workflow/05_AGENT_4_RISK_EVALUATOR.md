# Agent_4: Risk Evaluator (Risk 평가 모듈)

## 목차
- [개요](#개요)
- [워크플로우](#워크플로우)
- [State 구조](#state-구조)
- [기능별 상세 설명](#기능별-상세-설명)
- [5가지 분기 로직 요약](#5가지-분기-로직-요약)

---

## 개요

### 모듈 역할
Agent_4는 Agent_3의 DB 검색 결과와 Risk 시나리오를 종합하여 **뉴스의 Risk 여부를 판정**하고, **최종 이슈 타입과 우선순위를 결정**하는 모듈입니다.

### 파이프라인 위치
```
Agent_3 (DB Searcher) → [Agent_4: Risk Evaluator] → 최종 출력
```

### 주요 기능 (7개)
1. **입력 검증** (`validate_input`)
2. **단일 시나리오 Risk 평가** (`evaluate_risk_relevance`)
3. **다중 시나리오 독립 평가** (`evaluate_multi_scenarios`)
4. **통합 판정** (`aggregate_risk_decision`)
5. **이벤트 시점 분류** (`classify_event_timing`)
6. **이슈 타입 결정** (`determine_issue_type`) ⭐ 5가지 분기 로직
7. **신규 키워드 제안** (`recommend_keywords`) 🆕

---

## 워크플로우

```
validate_input → [조건부 분기: 시나리오 개수]
    ↓
[단일 시나리오]              [다중 시나리오 (2개 이상)]
evaluate_risk_relevance       evaluate_multi_scenarios
    ↓                              ↓
    ↓                         aggregate_risk_decision
    ↓                              ↓
    └─────────→ [병합] ←──────────┘
                  ↓
         classify_event_timing
                  ↓
         determine_issue_type
                  ↓
  recommend_news_collection_keywords
                  ↓
                 END
```

### 조건부 분기
- `risk_scenarios` 필드에 2개 이상 → 다중 시나리오 경로
- 그 외 (None 또는 1개) → 단일 시나리오 경로

---

## State 구조

### 입력 필드 (Agent_3로부터)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `news_id` | str | 뉴스 ID |
| `title_ko` | str | 제목 (한글) |
| `summary_ko` | str | 요약 (한글) |
| `content_ko` | str | 본문 (한글) |
| `keywords` | List[Dict] | Agent_1 추출 키워드 |
| `mapped_tags` | List[Dict] | Agent_2 매핑 태그 |
| `risk_scenario` | str | LLM 생성 Risk 시나리오 |
| `impact_level` | str | "HIGH" \| "MEDIUM" \| "LOW" |
| `generated_sql` | Optional[str] | 생성된 SQL |
| `search_results` | List[Dict] | DB 검색 결과 |
| `risk_scenarios` | List[Dict] | 다중 시나리오 (2개 이상) |
| `search_results_multi` | List[Dict] | 다중 시나리오 검색 결과 |

### 출력 필드 (Agent_4 생성)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `is_risk` | bool | Risk 여부 |
| `risk_score` | float | Risk 점수 (0.0~1.0) |
| `risk_justification` | str | Risk 판정 근거 |
| `risk_factors` | List[str] | Risk 요인 배열 |
| `event_timing` | str | "ONGOING" \| "SCHEDULED" |
| `event_timing_confidence` | float | 시점 분류 신뢰도 |
| `issue_type` | str | "ISSUE" \| "SMD" \| "NONE" |
| `issue_priority` | str | "HIGH" \| "MEDIUM" \| "LOW" \| "NONE" |
| `classification_reason` | str | 분류 근거 (5가지 분기) |
| `recommended_keywords` | List[Dict] | 신규 키워드 제안 |
| `requires_keyword_hitl` | bool | 키워드 HITL 필요 여부 |

---

## 기능별 상세 설명

### 1. validate_input (입력 검증)

#### 📋 설명
Agent_3 출력의 최소한의 필수 필드만 검증합니다. **DB 검색 결과가 없어도 통과**합니다.

#### 🤖 사용 모델
LLM 호출 없음 (조건부 로직)

#### 📥 입력값
| 필드명 | 필수/선택 | 설명 |
|--------|-----------|------|
| `news_id` | ✅ 필수 | 뉴스 ID |
| `title_ko` | ✅ 필수 | 제목 (한글) |
| `summary_ko` | ✅ 필수 | 요약 (한글) |
| `risk_scenario` | ⚠️ 선택 | 없으면 경고만 |
| `mapped_tags` | ⚠️ 선택 | 없으면 경고만 |
| `search_results` | ⚠️ 선택 | 없어도 통과 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `error` | Optional[str] | 에러 메시지 (필수 필드 없을 때만) |

#### 📝 예시

**입력 (필수 필드만 있음)**:
```json
{
  "news_id": "news_001",
  "title_ko": "중국, 희토류 수출 중단",
  "summary_ko": "중국 정부가...",
  "search_results": []  // DB 결과 없음
}
```

**출력 (통과)**:
```
[WARNING] risk_scenario 없음 (news_id=news_001)
[WARNING] mapped_tags 없음 (news_id=news_001)
[INFO] DB 검색 결과 없음 (news_id=news_001) - Risk 평가로 진행
```

---

### 2. evaluate_risk_relevance (단일 시나리오 Risk 평가)

#### 📋 설명
뉴스 이벤트와 DB 검색 결과를 종합하여 Risk 여부를 LLM으로 판단합니다.

#### 🤖 사용 모델
- **모델**: `gpt-5.5` (GPT-5.5, 추론 특화)
- **온도**: 0.3 (낮은 창의성)
- **타임아웃**: 60초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `title_ko` | str | 뉴스 제목 |
| `summary_ko` | str | 뉴스 요약 |
| `content_ko` | str | 뉴스 본문 (500자 제한) |
| `keywords` | List[str] | 키워드 배열 |
| `mapped_tags` | List[str] | 태그 이름 배열 |
| `risk_scenario` | str | Risk 시나리오 |
| `search_results` | List[Dict] | DB 검색 결과 (실제 데이터) |
| `generated_sql` | str | 생성된 SQL |
| `domain_rules` | List[Dict] | 도메인 규칙 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `is_risk` | bool | Risk 여부 |
| `risk_score` | float | Risk 점수 (0.0~1.0) |
| `risk_justification` | str | 판정 근거 (2-3문장) |
| `risk_factors` | List[str] | Risk 요인 배열 |

#### 💬 프롬프트

**System**:
```
당신은 반도체 공급망 리스크 분석 전문가입니다.
뉴스 이벤트와 DB 검색 결과를 종합하여 삼성전자 공급망에 실질적 Risk가 발생하는지 판단하고 JSON으로 응답하세요.
```

**User**:
```
다음 뉴스와 DB 검색 결과를 분석하여 삼성전자 공급망에 Risk를 발생시키는지 판단해주세요.

**뉴스 제목**: {title_ko}
**뉴스 요약**: {summary_ko}
**뉴스 본문** (일부): {content_ko[:500]}

**키워드**: {keywords}
**매핑된 태그**: {tags}

**Risk 시나리오**: {risk_scenario}

**DB 검색 결과**:
- SQL: {generated_sql}
- 설명: {sql_explanation}
- 검색 대상 엔티티: {search_target_entities}
- 검색 결과 개수: {result_count}
- 실제 검색 결과:
{search_results}

**도메인 규칙**: {domain_rules}

**판정 기준**:
1. 논리적 인과 관계: 뉴스 이벤트 → DB 엔티티 → 삼성전자 공급망
2. 도메인 지식 활용: 반도체 공급망 특성, 의존도, 집중도
3. 구체성: "~할 수 있음" 금지, 구체적 Risk 요인 명시
4. 부분 매칭 허용: 협력사/생산지/자재 중 일부만 확인되어도 Risk 판정 가능

**출력 형식 (JSON)**:
{
  "is_risk": true,
  "risk_score": 0.85,
  "risk_justification": "근거 2-3문장",
  "risk_factors": ["요인1", "요인2", ...]
}
```

#### 📝 예시

**입력**:
```json
{
  "title_ko": "중국, 희토류 대미 수출 전면 중단 발표",
  "summary_ko": "중국 정부가 미국에 대한 희토류 수출을 즉시 중단한다고 발표...",
  "keywords": ["희토류", "중국", "수출 중단"],
  "risk_scenario": "중국의 희토류 수출 중단으로 삼성전자 협력사 5곳의 조달에 차질 예상",
  "search_results": [
    {"supplier_name": "ABC Materials", "material": "희토류", "country": "중국"},
    {"supplier_name": "XYZ Corp", "material": "희토류", "country": "중국"}
  ]
}
```

**출력**:
```json
{
  "is_risk": true,
  "risk_score": 0.92,
  "risk_justification": "중국이 희토류 수출을 전면 중단했으며, DB에서 2개 협력사가 중국산 희토류에 의존하는 것으로 확인됨. 해당 협력사들은 삼성전자에 핵심 부품을 공급하므로 공급망 차질 불가피.",
  "risk_factors": [
    "희토류 공급 차단",
    "중국 수출통제",
    "협력사 조달 위험"
  ]
}
```

---

### 3. evaluate_multi_scenarios (다중 시나리오 독립 평가)

#### 📋 설명
2개 이상의 Risk 시나리오를 **각각 독립적으로** LLM 평가합니다.

#### 🤖 사용 모델
- **모델**: `gpt-5.5`
- **온도**: 0.3
- **타임아웃**: 60초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `risk_scenarios` | List[Dict] | 시나리오 배열 (2개 이상) |
| `search_results_multi` | List[Dict] | 시나리오별 검색 결과 |
| `generated_sqls` | List[Dict] | 시나리오별 SQL |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `scenario_evaluations` | List[Dict] | 시나리오별 평가 결과 배열 |

**scenario_evaluations 구조**:
```json
[
  {
    "scenario_id": "cluster_001",
    "is_risk": true,
    "risk_score": 0.85,
    "risk_justification": "...",
    "risk_factors": [...],
    "search_result_count": 5,
    "impact_level": "HIGH"
  }
]
```

#### 💬 프롬프트
동일한 Risk 평가 프롬프트를 시나리오별로 독립 호출 (각 시나리오의 검색 결과만 전달)

#### 📝 예시

**입력**:
```json
{
  "risk_scenarios": [
    {
      "scenario_id": "cluster_001",
      "scenario_text": "중국 희토류 수출 중단으로 협력사 2곳 영향",
      "entities": ["희토류", "중국"]
    },
    {
      "scenario_id": "cluster_002",
      "scenario_text": "대만 지진으로 TSMC 생산 차질",
      "entities": ["대만", "TSMC", "지진"]
    }
  ],
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "results": [{"supplier": "ABC Materials", "material": "희토류"}]
    },
    {
      "sql_id": "sql_cluster_002",
      "results": [{"supplier": "TSMC", "site": "대만"}]
    }
  ]
}
```

**출력**:
```json
{
  "scenario_evaluations": [
    {
      "scenario_id": "cluster_001",
      "is_risk": true,
      "risk_score": 0.85,
      "risk_justification": "희토류 공급 협력사 2곳 확인",
      "risk_factors": ["희토류 공급 차단"],
      "search_result_count": 1
    },
    {
      "scenario_id": "cluster_002",
      "is_risk": true,
      "risk_score": 0.90,
      "risk_justification": "TSMC 생산 차질로 파운드리 조달 위험",
      "risk_factors": ["TSMC 생산 중단", "파운드리 공급 부족"],
      "search_result_count": 1
    }
  ]
}
```

---

### 4. aggregate_risk_decision (통합 판정)

#### 📋 설명
다중 시나리오의 개별 평가 결과를 통합하여 최종 Risk 판정을 내립니다.

#### 🤖 사용 모델
LLM 호출 없음 (규칙 기반 통합)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `scenario_evaluations` | List[Dict] | 시나리오별 평가 결과 |
| `is_grouped` | bool | 그룹 문서 여부 |
| `group_insight` | Dict | 그룹 인사이트 (선택) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `is_risk` | bool | 최종 Risk 여부 |
| `risk_score` | float | 최종 Risk 점수 (조정됨) |
| `risk_justification` | str | 최종 판정 근거 |
| `risk_factors` | List[str] | 통합 Risk 요인 |
| `final_risk_decision` | Dict | 통합 판정 상세 정보 |

#### 통합 규칙

| 규칙 | 내용 |
|------|------|
| **1** | 하나라도 `is_risk=True`면 최종 `is_risk=True` |
| **2** | 최종 `risk_score` = 개별 `risk_score`의 **최댓값** |
| **3** | `risk_justification` = 가장 높은 `risk_score`의 근거 |
| **4** | `risk_factors` = 모든 시나리오 factors의 **합집합** |

#### 그룹 문서 가중치

| 조건 | 가중치 |
|------|--------|
| 3개 이상 뉴스 그룹 | `risk_score × 1.15` (+15%) |
| 2개 뉴스 그룹 | `risk_score × 1.10` (+10%) |
| risk_perspectives 4개 이상 | `+0.05` 추가 |
| 최대값 | 1.0 (cap) |

#### 📝 예시

**입력**:
```json
{
  "scenario_evaluations": [
    {
      "scenario_id": "cluster_001",
      "is_risk": true,
      "risk_score": 0.85,
      "risk_justification": "희토류 공급 협력사 2곳 확인",
      "risk_factors": ["희토류 공급 차단"]
    },
    {
      "scenario_id": "cluster_002",
      "is_risk": true,
      "risk_score": 0.90,
      "risk_justification": "TSMC 생산 차질",
      "risk_factors": ["TSMC 생산 중단", "파운드리 공급 부족"]
    }
  ],
  "is_grouped": true,
  "group_insight": {
    "original_news_ids": ["news_001", "news_002", "news_003"]
  }
}
```

**출력**:
```json
{
  "is_risk": true,
  "risk_score": 0.99,  // max(0.90) × 1.15 = 1.035 → 1.0 (cap)
  "risk_justification": "[cluster_002] TSMC 생산 차질로 파운드리 조달 위험",
  "risk_factors": [
    "희토류 공급 차단",
    "TSMC 생산 중단",
    "파운드리 공급 부족"
  ],
  "final_risk_decision": {
    "leading_scenario_id": "cluster_002",
    "total_scenarios_evaluated": 2,
    "risk_scenarios_count": 2
  }
}
```

---

### 5. classify_event_timing (이벤트 시점 분류)

#### 📋 설명
뉴스 이벤트의 시점을 **ONGOING(진행형)** 또는 **SCHEDULED(예정형)**으로 분류합니다.

#### 🤖 사용 모델
- **모델**: `gpt-5.5`
- **온도**: 0.2 (매우 낮음)
- **타임아웃**: 30초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `title_ko` | str | 뉴스 제목 |
| `summary_ko` | str | 뉴스 요약 |
| `content_ko` | str | 뉴스 본문 (500자) |
| `risk_scenario` | str | Risk 시나리오 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `event_timing` | str | "ONGOING" \| "SCHEDULED" |
| `event_timing_confidence` | float | 신뢰도 (0.0~1.0) |
| `event_timing_justification` | str | 판정 근거 |

#### 분류 기준

| 시점 | 키워드 | 설명 |
|------|--------|------|
| **ONGOING** | 발생, 시행, 중단됨, 완료, 발표됨 (과거형/현재형) | 이미 발생 또는 현재 진행 중 |
| **SCHEDULED** | 예정, 계획, 할 것으로 예상, 가능성 (미래형/추측) | 예정 또는 예상되는 이벤트 |

#### 💬 프롬프트

**System**:
```
당신은 이벤트 시점 분석 전문가입니다.
뉴스 이벤트의 시점을 ONGOING(진행형) 또는 SCHEDULED(예정형)으로 분류하고 JSON으로 응답하세요.
```

**User**:
```
다음 뉴스 이벤트의 시점을 분류해주세요.

**뉴스 제목**: {title_ko}
**뉴스 요약**: {summary_ko}
**Risk 시나리오**: {risk_scenario}

**분류 기준**:
- ONGOING (진행형): 이미 발생, 현재 진행 중, 완료됨
  - 키워드: 발생, 시행, 중단됨, 완료, 발표됨 (과거형/현재형)
- SCHEDULED (예정형): 예정, 예상, 계획, 가능성
  - 키워드: 예정, 계획, 할 것으로 예상, 가능성, ~될 전망 (미래형/추측)

**판단 원칙**: 뉴스 시제를 우선 고려

**출력 형식 (JSON)**:
{
  "event_timing": "ONGOING",
  "event_timing_confidence": 0.95,
  "event_timing_justification": "판정 근거"
}
```

#### 📝 예시

**입력 1 (진행형)**:
```json
{
  "title_ko": "중국, 희토류 수출 중단 발표",
  "summary_ko": "중국 정부가 어제 희토류 수출을 전면 중단한다고 발표했다...",
  "risk_scenario": "중국의 희토류 수출 중단으로 협력사 조달 차질"
}
```

**출력 1**:
```json
{
  "event_timing": "ONGOING",
  "event_timing_confidence": 0.98,
  "event_timing_justification": "뉴스 제목에 '발표' 키워드, '어제'라는 과거 시점 명시. 이미 발생한 이벤트로 판단."
}
```

**입력 2 (예정형)**:
```json
{
  "title_ko": "중국, 다음 달 희토류 수출 규제 예고",
  "summary_ko": "중국 정부가 다음 달부터 희토류 수출을 규제할 것으로 예상된다...",
  "risk_scenario": "중국의 희토류 수출 규제로 협력사 조달 차질 예상"
}
```

**출력 2**:
```json
{
  "event_timing": "SCHEDULED",
  "event_timing_confidence": 0.95,
  "event_timing_justification": "뉴스 제목에 '예고' 키워드, '다음 달'이라는 미래 시점 명시. 예정된 이벤트로 판단."
}
```

---

### 6. determine_issue_type (이슈 타입 결정) ⭐

#### 📋 설명
**5가지 분기 로직**으로 DB 검색 결과 유무, Risk 판정, 이벤트 시점을 조합하여 최종 이슈 타입과 우선순위를 결정합니다.

#### 🤖 사용 모델
LLM 호출 없음 (조건부 로직)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `is_risk` | bool | Risk 평가 결과 |
| `event_timing` | str | 이벤트 시점 |
| `search_results` | List[Dict] | DB 검색 결과 |
| `search_results_multi` | List[Dict] | 다중 시나리오 검색 결과 |
| `impact_level` | str | Agent_3 전달 값 |
| `is_grouped` | bool | 그룹 문서 여부 |
| `group_insight` | Dict | 그룹 인사이트 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `issue_type` | str | "ISSUE" \| "SMD" \| "NONE" |
| `issue_priority` | str | "HIGH" \| "MEDIUM" \| "LOW" \| "NONE" |
| `classification_reason` | str | 분류 근거 |

#### 5가지 분기 로직

| Case | DB 결과 | Risk | 시점 | 결과 | 우선순위 | 설명 |
|------|---------|------|------|------|----------|------|
| **1** | ✅ | ✅ | 진행형 | **ISSUE** | **HIGH** | 즉시 대응 필요 |
| **2** | ✅ | ✅ | 예정형 | **SMD** | **MEDIUM** | 예정 모니터링 |
| **3** | ✅ | ❌ | - | **SMD** | **LOW** | 구매 연관 뉴스 |
| **4** | ❌ | ✅ | - | **SMD** | **LOW** | 이모저모 참고용 |
| **5** | ❌ | ❌ | - | **NONE** | **NONE** | 무관한 뉴스 (DROP) |

#### 그룹 문서 우선순위 조정

**ISSUE**:
- 3개 이상 그룹: HIGH 유지
- 2개 그룹: HIGH 유지

**SMD**:
- 3개 이상 그룹: LOW → MEDIUM, MEDIUM → HIGH
- 2개 그룹: LOW → MEDIUM

#### 📝 예시

**예시 1: Case 1 (DB O + Risk O + 진행형)**
```json
// 입력
{
  "is_risk": true,
  "event_timing": "ONGOING",
  "search_results": [{"supplier": "ABC"}],
  "is_grouped": false
}

// 출력
{
  "issue_type": "ISSUE",
  "issue_priority": "HIGH",
  "classification_reason": "DB 검색 결과 존재 + Risk 판정 + 진행형 이벤트"
}
```

**예시 2: Case 3 (DB O + Risk X)**
```json
// 입력
{
  "is_risk": false,
  "event_timing": "ONGOING",
  "search_results": [{"site": "평택"}],
  "is_grouped": false
}

// 출력
{
  "issue_type": "SMD",
  "issue_priority": "LOW",
  "classification_reason": "DB 검색 결과 존재하나 Risk 판정 없음 (구매 연관 뉴스)"
}
```

**예시 3: Case 5 (DB X + Risk X)**
```json
// 입력
{
  "is_risk": false,
  "event_timing": "ONGOING",
  "search_results": [],
  "is_grouped": false
}

// 출력
{
  "issue_type": "NONE",
  "issue_priority": "NONE",
  "classification_reason": "DB 검색 결과 없고 Risk 판정 없음 (무관한 뉴스)"
}
```

---

### 7. recommend_keywords (신규 키워드 제안) 🆕

#### 📋 설명
DB에서 Risk로 판정된 모든 뉴스의 키워드를 집계하여, **5회 이상 출현했으나 기존 Risk Factor 키워드셋에 없는 키워드**를 제안합니다 (HITL).

#### 🤖 사용 모델
LLM 호출 없음 (DB 집계 + Excel 비교)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `news_id` | str | 현재 뉴스 ID (노드 호출용, 실제로는 DB 전체 조회) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `recommended_keywords` | List[Dict] | 제안 키워드 정보 |
| `requires_keyword_hitl` | bool | HITL 필요 여부 |

**recommended_keywords 구조**:
```json
[
  {
    "keyword": "WBG 반도체",
    "count": 7,
    "related_news_ids": ["news_001", "news_003", "news_007"],
    "sample_contexts": ["...", "...", "..."]
  }
]
```

#### 처리 로직

1. **기존 Risk Factor 키워드셋 로드**
   - 파일: `DB_TAG_Risk Factor Pool_vF.xlsx`
   - 시트: `2. Keyword Set_ai`
   - 조건: `target_region='KR'`인 행만

2. **DB에서 Risk 뉴스 키워드 집계**
   ```sql
   SELECT kw.keyword, COUNT(*) as count
   FROM NEWS_KEYWORD_EXTRACTION kw
   INNER JOIN NEWS_RISK_EVALUATION risk ON kw.news_id = risk.news_id
   WHERE risk.is_risk = 1
   GROUP BY kw.keyword
   ORDER BY count DESC
   ```

3. **필터링**
   - 기존 키워드셋에 **없음**
   - **5회 이상** 출현

4. **관련 뉴스 샘플 수집** (최대 3개)

#### 📝 예시

**입력**: (DB 전체 조회, 입력 파라미터 없음)

**출력**:
```json
{
  "recommended_keywords": [
    {
      "keyword": "WBG 반도체",
      "count": 7,
      "related_news_ids": ["news_045", "news_067", "news_089"],
      "sample_contexts": [
        "차세대 WBG 반도체 공급 부족 우려...",
        "WBG 반도체 기업 투자 확대...",
        "WBG 반도체 시장 급성장..."
      ]
    },
    {
      "keyword": "탄소 배출권",
      "count": 5,
      "related_news_ids": ["news_023", "news_056", "news_091"],
      "sample_contexts": [
        "EU 탄소 배출권 규제 강화...",
        "탄소 배출권 가격 급등...",
        "탄소 배출권 제도 변경..."
      ]
    }
  ],
  "requires_keyword_hitl": true
}
```

**콘솔 로그**:
```
[INFO] 독립 실행 키워드 제안 시작
[INFO] 기존 Risk Factor 키워드: 342개
[INFO] 총 78개의 고유 키워드 집계 완료
[INFO] 2개의 신규 키워드 제안:
  - WBG 반도체 (출현 7회)
  - 탄소 배출권 (출현 5회)
```

---

## 5가지 분기 로직 요약

### 결정 트리

```
DB 검색 결과 있음?
├─ Yes (DB 존재)
│   └─ Risk 판정?
│       ├─ Yes (Risk O)
│       │   └─ 이벤트 시점?
│       │       ├─ 진행형 → [Case 1] ISSUE (HIGH)
│       │       └─ 예정형 → [Case 2] SMD (MEDIUM)
│       └─ No (Risk X)
│           └─ [Case 3] SMD (LOW) - 구매 연관
└─ No (DB 없음)
    └─ Risk 판정?
        ├─ Yes (Risk O) → [Case 4] SMD (LOW) - 이모저모 참고
        └─ No (Risk X) → [Case 5] NONE - DROP
```

### 결과 테이블

| Case | DB | Risk | 시점 | 타입 | 우선순위 | 용도 |
|------|-----|------|------|------|----------|------|
| 1 | O | O | 진행 | ISSUE | HIGH | 즉시 대응 필요 |
| 2 | O | O | 예정 | SMD | MEDIUM | 예정 모니터링 |
| 3 | O | X | - | SMD | LOW | 구매 연관 참고 |
| 4 | X | O | - | SMD | LOW | 이모저모 참고 |
| 5 | X | X | - | NONE | NONE | 무관 (DROP) |

---

## 문서 네비게이션

- **이전**: [Agent_3: DB Searcher](04_AGENT_3_DB_SEARCHER.md)
- **다음**: [실행 예시 (99_EXAMPLES.md)](99_EXAMPLES.md)
- **개요**: [시스템 개요 (00_OVERVIEW.md)](00_OVERVIEW.md)

---

**작성일**: 2026-07-12  
**버전**: 1.1  
**업데이트 내역**:
- 기능별 구조로 재작성 (설명, 모델, 입력, 출력, 프롬프트, 예시)
- 5가지 분기 로직 명확화
