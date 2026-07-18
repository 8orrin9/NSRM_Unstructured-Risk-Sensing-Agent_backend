# Agent_3 DB Searcher 문서

**작성일**: 2026-07-08  
**버전**: 1.0  
**담당**: POC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [핵심 개념](#2-핵심-개념)
3. [데이터 흐름](#3-데이터-흐름)
4. [출력 구조 상세](#4-출력-구조-상세)
5. [다중 시나리오 모드](#5-다중-시나리오-모드)
6. [search_results vs search_results_multi](#6-search_results-vs-search_results_multi)
7. [실전 예시](#7-실전-예시)
8. [설정 및 구성](#8-설정-및-구성)
9. [활용 방안](#9-활용-방안)
10. [FAQ](#10-faq)

---

## 1. 개요

### 1.1 목적

Agent_3 DB Searcher는 **뉴스에서 추출된 정보를 바탕으로 공급망 데이터베이스를 자동으로 검색**하여, 실제로 영향받을 수 있는 협력사/자재/생산지를 발견하는 모듈입니다.

### 1.2 주요 기능

- ✅ **Risk 시나리오 자동 생성**: LLM이 뉴스와 태그를 분석하여 공급망 리스크 시나리오 생성
- ✅ **검색 전략 자동 결정**: 온톨로지 DB를 조회하여 최적의 검색 전략 선택
- ✅ **SQL 자동 생성**: LLM이 시나리오와 전략을 바탕으로 공급망 DB 검색 SQL 생성
- ✅ **다중 시나리오 지원**: 하나의 뉴스를 여러 리스크 관점에서 분석
- ✅ **스키마 준수 검증**: SQL 구문 검증 및 재시도 메커니즘

### 1.3 입출력

| 구분 | 설명 |
|------|------|
| **입력** | Agent_2 출력 (뉴스 + 키워드 + 매핑된 태그) |
| **출력** | 공급망 DB 검색 결과 (영향받는 협력사/자재/생산지 목록) |

---

## 2. 핵심 개념

### 2.1 문제 정의

**수동 방식의 한계**:
```
"미국 ITC가 두산밥캣 건설장비 수입금지 조사" 뉴스 발견
↓
담당자가 수동으로 공급망 DB 검색
↓
"이 뉴스가 어떤 협력사에 영향 주나?" 분석
↓
시간 소요 + 놓치는 협력사 발생
```

**자동화 솔루션**:
```
뉴스 입력
↓
Agent_3이 자동으로:
  1. Risk 시나리오 이해
  2. 검색 SQL 생성
  3. DB 조회 실행
↓
34개 미국 내 생산지 자동 발견 (3초 소요)
```

### 2.2 핵심 가치

1. **시간 절약**: 수동 검색 → 자동 검색 (분 단위 → 초 단위)
2. **완전성**: LLM이 다양한 관점에서 검색하여 놓치는 엔티티 최소화
3. **추적성**: 어떤 시나리오로 어떤 SQL을 실행했는지 모두 기록
4. **확장성**: 새로운 검색 전략을 온톨로지 DB에 추가하면 즉시 활용

---

## 3. 데이터 흐름

### 3.1 전체 프로세스

```
┌─────────────────────────────────────────────────────────────────┐
│ [INPUT] Agent_2 출력                                            │
│ • 뉴스 원문 (title_ko, summary_ko, content_ko)                 │
│ • 추출된 키워드 (keywords)                                      │
│ • 매핑된 태그 (mapped_tags)                                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 1] Risk 시나리오 생성 (LLM)                              │
│ • 태그 클러스터링 (다중 관점 발견)                              │
│ • 관점별 시나리오 생성                                          │
│ OUTPUT: risk_scenarios[]                                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 2] 온톨로지 레이어 조회                                  │
│ • 도메인 규칙 조회 (DOMAIN_KNOWLEDGE_RULES)                    │
│ • 검색 전략 결정 (SEARCH_STRATEGY_TEMPLATE)                    │
│ • 검색 대상 엔티티 결정                                         │
│ OUTPUT: search_strategy, search_target_entities                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 3] SQL 생성 (LLM)                                         │
│ • LLM 입력: 뉴스 + 시나리오 + 전략 + 스키마                    │
│ • SQL 검증 및 재시도 (최대 2회)                                │
│ OUTPUT: generated_sqls[]                                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 4] DB 검색 실행                                           │
│ • 공급망 DB (supply_chain.db)에 SQL 실행                       │
│ • 시나리오별 SQL 각각 실행 → 결과 분리 저장                    │
│ OUTPUT: search_results_multi[]                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [OUTPUT] 영향받는 공급망 엔티티 목록                           │
│ • 협력사, 자재, 생산지 레코드                                   │
│ • SQL별로 그룹화되어 추적 가능                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 노드별 상세 설명

#### validate_input
- **역할**: 입력 데이터 검증
- **검증 항목**: mapped_tags 존재 여부, 필수 필드 확인

#### generate_risk_scenario
- **역할**: Risk 시나리오 생성 및 온톨로지 조회
- **처리**:
  1. 태그 클러스터링 (다중 관점 발견)
  2. LLM을 통한 시나리오 생성
  3. 온톨로지 DB 조회 (도메인 규칙, 검색 전략)

#### generate_sql
- **역할**: SQL 자동 생성
- **처리**:
  1. LLM에 전체 컨텍스트 전달
  2. 시나리오별 SQL 생성
  3. SQL 구문 검증
  4. 실패 시 에러 피드백과 함께 재시도

#### search_db
- **역할**: 공급망 DB 검색
- **처리**:
  1. 생성된 SQL 실행
  2. 결과를 시나리오별로 그룹화
  3. search_results_multi에 저장

---

## 4. 출력 구조 상세

### 4.1 전체 구조

```json
{
  "extraction_date": "2026-07-08T20:50:46.770227",
  "agent2_input_file": "...",
  "total_articles_processed": 13,
  "total_errors": 0,
  
  "statistics": {
    "sql_generation_success_count": 13,
    "sql_generation_success_percentage": 100.0,
    "fallback_strategy_used_count": 8,
    "average_risk_confidence": 0.9,
    "impact_levels": {"HIGH": 10, "MEDIUM": 3}
  },
  
  "results": [
    { /* 뉴스별 검색 결과 */ }
  ]
}
```

### 4.2 뉴스별 결과 구조

```json
{
  // ===== 입력 정보 (Agent_2 출력) =====
  "news_id": "group_007",
  "title_ko": "트럼프 개입... 미국 ITC가 두산밥캣 조사",
  "summary_ko": "...",
  "content_ko": "...",
  "keywords": [...],
  "mapped_tags": [
    {
      "keyword": "미국",
      "tag_id": "SITE_미국(USA)",
      "tag_name": "미국",
      "tag_type": "SITE",
      "confidence": 1.0,
      "source": "exact_match"
    }
  ],
  
  // ===== STEP 1: Risk 시나리오 생성 =====
  "risk_scenarios": [
    {
      "scenario_id": "cluster_001",
      "risk_scenario": "미국 ITC가 두산밥캣 건설장비 수입금지 명령 조사 중, 공급 차질 예상",
      "entities": ["두산밥캣", "건설장비", "미국 ITC"],
      "confidence": 0.9,
      "impact_level": "HIGH",
      "cluster_type": "GENERAL",
      "cluster_focus": "건설장비 수입규제 리스크",
      "kg_paths": []
    }
  ],
  
  // 호환성 필드 (첫 번째 시나리오)
  "risk_scenario": "미국 ITC가 두산밥캣...",
  "risk_scenario_entities": ["두산밥캣", "건설장비", "미국 ITC"],
  "risk_scenario_confidence": 0.9,
  "impact_level": "HIGH",
  
  // ===== STEP 2: 온톨로지 조회 결과 =====
  "domain_rules": [],
  "search_target_entities": ["SITE_MASTER"],
  "search_strategy_id": "STRAT_SITE_COUNTRY_LIST",
  "search_strategy": {
    "strategy_name": "국가별 생산지 검색",
    "sql_template": "SELECT ... FROM SITE_MASTER WHERE country = ?"
  },
  "fallback_strategy_used": false,
  "impact_scope": "미국 내 협력사 및 생산지 영향 분석 필요",
  
  // ===== STEP 3: 생성된 SQL =====
  "generated_sqls": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "sql": "SELECT\n  s.name AS 생산지,\n  s.country AS 국가,\n  sup.name_kor AS 협력사\nFROM SITE_MASTER s\nJOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code\nWHERE s.country = 'United States'\n  AND s.is_active = 1\nLIMIT 100",
      "explanation": "미국 ITC 조사와 관련하여 미국 내 협력사 및 생산지 조회",
      "validation_attempts": 1,
      "is_fallback": false
    }
  ],
  
  // 호환성 필드 (첫 번째 SQL)
  "generated_sql": "SELECT ...",
  "sql_explanation": "미국 ITC 조사와 관련하여...",
  
  // ===== STEP 4: DB 검색 결과 (핵심!) =====
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "sql": "SELECT ...",
      "result_count": 34,
      "results": [
        {
          "생산지": "CMC Materials Taiwan Plant 1",
          "국가": "United States",
          "협력사": "CMC Materials Taiwan"
        },
        {
          "생산지": "에어프로덕츠(Air Products) Plant 2",
          "국가": "United States",
          "협력사": "에어프로덕츠(Air Products)"
        }
        // ... 32개 더
      ]
    }
  ],
  
  // 레거시 필드 (단일 SQL 모드, 현재 비활성)
  "search_results": [],
  
  // ===== 메타데이터 =====
  "tag_clusters": [...],
  "kg_paths": [],
  "error": null
}
```

### 4.3 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `risk_scenarios[]` | List[Dict] | LLM이 생성한 리스크 시나리오 (다중 관점) |
| `search_target_entities` | List[str] | 검색할 DB 테이블명 (예: ["SITE_MASTER"]) |
| `search_strategy_id` | str | 사용한 검색 전략 ID (온톨로지 DB에서 조회) |
| `generated_sqls[]` | List[Dict] | LLM이 생성한 SQL (시나리오별) |
| `search_results_multi[]` | List[Dict] | **DB 검색 결과 (시나리오별, SQL별)** |
| `sql_id` | str | SQL 고유 ID (search_results_multi 내) |
| `scenario_id` | str | 시나리오 ID (SQL과 시나리오 연결) |
| `validation_attempts` | int | SQL 검증 재시도 횟수 (1 = 1차 성공) |
| `fallback_strategy_used` | bool | Fallback 전략 사용 여부 |

---

## 5. 다중 시나리오 모드

### 5.1 개념

**다중 시나리오 모드** = 1개 뉴스 → **여러 리스크 관점** → 관점별 SQL → 관점별 DB 검색 결과

### 5.2 작동 방식

#### 1단계: 태그 클러스터링

하나의 뉴스에서 추출된 태그들을 **의미있는 관점(클러스터)**으로 그룹화:

```python
# 예: 한 뉴스에서 추출된 태그들
mapped_tags = [
    {"tag_name": "SK하이닉스", "tag_type": "SUPPLIER"},
    {"tag_name": "화재사고", "tag_type": "EVENT"},
    {"tag_name": "네온가스", "tag_type": "RAW_MATERIAL"},
    {"tag_name": "우크라이나", "tag_type": "SITE"}
]

# 클러스터링 결과 → 2개 관점
clusters = [
    {
        "cluster_id": "cluster_001",
        "cluster_type": "EVENT_SUPPLIER",  # 이벤트 관점
        "tags": [SK하이닉스, 화재사고],
        "focus": "SK하이닉스 화재사고 관련 리스크"
    },
    {
        "cluster_id": "cluster_002", 
        "cluster_type": "MATERIAL_DEPENDENCY",  # 소재 의존성 관점
        "tags": [네온가스, 우크라이나],
        "focus": "우크라이나산 네온가스 공급망 리스크"
    }
]
```

#### 2단계: 관점별 시나리오 생성

```python
risk_scenarios = [
    {
        "scenario_id": "cluster_001",
        "risk_scenario": "SK하이닉스 공장 화재사고로 반도체 생산 차질 예상",
        "entities": ["SK하이닉스", "화재사고"],
        "impact_level": "HIGH"
    },
    {
        "scenario_id": "cluster_002",
        "risk_scenario": "우크라이나 전쟁으로 네온가스 공급 중단 우려",
        "entities": ["네온가스", "우크라이나"],
        "impact_level": "HIGH"
    }
]
```

#### 3단계: 시나리오별 SQL 생성

```python
generated_sqls = [
    {
        "sql_id": "sql_cluster_001",
        "scenario_id": "cluster_001",
        "sql": "SELECT ... FROM SUPPLIER_MASTER WHERE name_kor = 'SK하이닉스'..."
    },
    {
        "sql_id": "sql_cluster_002",
        "scenario_id": "cluster_002", 
        "sql": "SELECT ... FROM RAW_MATERIAL_MASTER WHERE name_kor = '네온가스'..."
    }
]
```

#### 4단계: SQL별 DB 검색 및 결과 분리 저장

```python
search_results_multi = [
    {
        "sql_id": "sql_cluster_001",
        "scenario_id": "cluster_001",
        "result_count": 12,
        "results": [{"site": "평택 공장", ...}, ...]
    },
    {
        "sql_id": "sql_cluster_002",
        "scenario_id": "cluster_002",
        "result_count": 5,
        "results": [{"material": "네온가스", "supplier": "에어프로덕츠", ...}, ...]
    }
]
```

### 5.3 클러스터링 전략

`cluster_tags()` 함수가 사용하는 클러스터링 규칙:

1. **EVENT + SUPPLIER/SITE** → "협력사/생산지 이벤트 관점"
2. **RAW_MATERIAL + MATERIAL** → "소재 의존성 관점"
3. **POLICY** → "정책 규제 관점"
4. **같은 target_region** → "지역별 관점"

### 5.4 그룹화된 뉴스와의 관계

- ✅ **단일 뉴스**: 태그 클러스터링으로 여러 관점 발견
- ✅ **그룹화된 뉴스**: Agent_5에서 제공한 `group_insight`를 활용해 더 정교한 클러스터링 수행

```python
# generate_risk_scenario.py
if group_insight:
    # group_insight가 있으면 enhanced 클러스터링 사용
    clusters = cluster_tags_enhanced(
        state["mapped_tags"],
        group_insight=group_insight,  # Agent_5의 인사이트 활용
        max_clusters=MAX_SCENARIOS_PER_NEWS
    )
else:
    # 기본 클러스터링
    clusters = cluster_tags(...)
```

---

## 6. search_results vs search_results_multi

### 6.1 차이점 요약

| 구분 | search_results | search_results_multi |
|------|----------------|----------------------|
| **용도** | 단일 SQL 모드 (레거시) | 다중 시나리오 모드 (현재) |
| **구조** | 평탄한 리스트 | SQL별 그룹화된 딕셔너리 |
| **SQL 추적** | 불가능 | 가능 (sql_id, scenario_id) |
| **다중 시나리오** | 미지원 | 지원 |
| **현재 상태** | 빈 리스트 (호환성 유지) | 활성 사용 중 |

### 6.2 search_results (레거시)

```json
{
  "search_results": [
    {"생산지": "Plant A", "국가": "USA", "협력사": "Company X"},
    {"생산지": "Plant B", "국가": "USA", "협력사": "Company Y"}
  ]
}
```

**특징**:
- `ENABLE_MULTI_SCENARIO = False`일 때 사용
- 하나의 뉴스 → 하나의 SQL → 평탄한 결과 리스트
- SQL 메타데이터 없음

### 6.3 search_results_multi (현재)

```json
{
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "sql": "SELECT ...",
      "result_count": 34,
      "results": [
        {"생산지": "Plant A", "국가": "USA", "협력사": "Company X"},
        {"생산지": "Plant B", "국가": "USA", "협력사": "Company Y"}
      ]
    },
    {
      "sql_id": "sql_cluster_002",
      "scenario_id": "cluster_002",
      "sql": "SELECT ...",
      "result_count": 12,
      "results": [...]
    }
  ]
}
```

**특징**:
- `ENABLE_MULTI_SCENARIO = True`일 때 사용 (현재 기본값)
- 여러 시나리오 → 시나리오별 SQL → SQL별 결과 분리
- 완전한 추적성 (어떤 시나리오 → 어떤 SQL → 어떤 결과)

### 6.4 장점

**search_results_multi**의 핵심 이점:

1. **시나리오별 추적**: 어떤 리스크 관점에서 나온 결과인지 식별
2. **SQL 재현**: 결과와 함께 SQL도 저장되어 디버깅/검증 용이
3. **확장성**: 1개 뉴스에서 여러 시나리오 → 여러 SQL → 여러 결과 세트 관리

---

## 7. 실전 예시

### 7.1 뉴스 입력

```json
{
  "news_id": "group_007",
  "title_ko": "미국 ITC가 두산밥캣의 특정 건설장비에 대한 수입금지 명령 조사",
  "summary_ko": "도널드 트럼프 대통령의 개입 사태로 미국과 유럽 간 갈등...",
  "mapped_tags": [
    {"tag_name": "미국", "tag_type": "SITE", "confidence": 1.0}
  ]
}
```

### 7.2 STEP 1: Risk 시나리오 생성

```json
{
  "risk_scenario": "미국 ITC가 두산밥캣의 건설장비 수입금지 명령을 조사 중인 상황에서, 이로 인해 두산밥캣의 건설장비 공급에 차질이 발생할 것으로 예상됨",
  "entities": ["두산밥캣", "건설장비", "미국 ITC"],
  "impact_level": "HIGH",
  "confidence": 0.9
}
```

### 7.3 STEP 2: 검색 전략 결정

```json
{
  "search_strategy_id": "STRAT_SITE_COUNTRY_LIST",
  "search_target_entities": ["SITE_MASTER"],
  "impact_scope": "미국 내 협력사 및 생산지 영향 분석 필요"
}
```

### 7.4 STEP 3: SQL 생성

```sql
SELECT
  s.name AS 생산지,
  s.country AS 국가,
  sup.name_kor AS 협력사
FROM SITE_MASTER s
JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
WHERE s.country = 'United States'
  AND s.is_active = 1
  AND sup.is_active = 1
LIMIT 100
```

**LLM의 설명**:
> "이 쿼리는 미국 ITC와 관련된 두산밥캣의 건설장비 수입금지 명령 조사와 관련하여 미국 내 협력사 및 생산지를 조회합니다. 뉴스에서 언급된 미국과 유럽 간의 갈등을 반영하여, 미국 내에서 활동 중인 협력사 정보를 중심으로 데이터를 추출했습니다."

### 7.5 STEP 4: DB 검색 결과

```json
{
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "result_count": 34,
      "results": [
        {
          "생산지": "CMC Materials Taiwan Plant 1",
          "국가": "United States",
          "협력사": "CMC Materials Taiwan"
        },
        {
          "생산지": "에어프로덕츠(Air Products) Plant 2",
          "국가": "United States",
          "협력사": "에어프로덕츠(Air Products)"
        },
        {
          "생산지": "카봇마이크로일렉트로닉스 Plant 1",
          "국가": "United States",
          "협력사": "카봇마이크로일렉트로닉스"
        }
        // ... 31개 더
      ]
    }
  ]
}
```

### 7.6 해석

**발견**: 이 뉴스로 인해 **미국 내 34개 생산지**가 영향받을 수 있음

**영향받는 주요 협력사**:
- CMC Materials Taiwan
- 에어프로덕츠(Air Products)
- 카봇마이크로일렉트로닉스
- 기타 31개 협력사

**다음 액션**:
1. 해당 협력사 담당자에게 알림 발송
2. 대시보드에 영향 협력사 시각화
3. Agent_4로 전달하여 더 정교한 영향 분석 수행

---

## 8. 설정 및 구성

### 8.1 주요 설정 (config.py)

```python
# ===== 모델 설정 =====
RISK_SCENARIO_MODEL = "gpt-4o-mini"  # Risk 시나리오 생성용
OPENAI_MODEL = "gpt-4o-mini"          # SQL 생성용

# ===== 경로 설정 =====
ONTOLOGY_DB_PATH = PROJECT_ROOT / "data" / "ONTOLOGY" / "ontology_layer.db"
SUPPLY_CHAIN_DB_PATH = PROJECT_ROOT / "data" / "SUPPLY_CHAIN" / "supply_chain.db"

# ===== 다중 시나리오 설정 =====
ENABLE_MULTI_SCENARIO = True          # 다중 시나리오 생성 활성화
MAX_SCENARIOS_PER_NEWS = 4            # 뉴스당 최대 시나리오 수
MIN_TAGS_PER_CLUSTER = 2              # 클러스터링 최소 태그 수

# ===== KG 경로 활용 설정 =====
ENABLE_KG_PATH_ENRICHMENT = True      # KG 경로 기반 시나리오 강화
GRAPHML_PATH = PROJECT_ROOT / "data" / "NEWS" / "insight_kg" / "graph_chunk_entity_relation_normalized.graphml"
MAX_KG_PATH_LENGTH = 2                # 최대 hop 거리
MAX_KG_PATHS_PER_CLUSTER = 3          # 클러스터당 최대 KG 경로 수
```

### 8.2 온톨로지 DB 구조

Agent_3은 `ontology_layer.db`에서 검색 전략을 자동으로 조회합니다:

**주요 테이블**:
- `DOMAIN_KNOWLEDGE_RULES`: 도메인 규칙 (예: "무역규제 → SITE 우선 검색")
- `SEARCH_STRATEGY_TEMPLATE`: SQL 템플릿 (예: "국가별 생산지 검색")
- `DB_TABLE_METADATA`: 공급망 DB 테이블 메타데이터
- `DB_COLUMN_METADATA`: 컬럼별 설명 및 샘플 값
- `DB_TABLE_RELATIONSHIP`: 테이블 간 조인 관계

### 8.3 SQL 생성 프롬프트 강화 (2026-07-08 개선)

**문제**: LLM이 존재하지 않는 테이블/컬럼을 생성 (예: `sup.name`, `supply_chain_analysis`)

**해결**: 프롬프트 강화

```python
SQL_GENERATION_SYSTEM_PROMPT = """
당신은 공급망 데이터베이스 전문가입니다.

**CRITICAL: 스키마 준수 규칙 (위반 시 쿼리 실패)**:
1. **제공된 테이블만 사용**: DB 스키마 메타데이터에 명시된 테이블 외에는 절대 사용 금지
2. **제공된 컬럼만 사용**: 각 테이블의 스키마에 명시된 컬럼명만 사용
3. **JOIN 경로 준수**: 제공된 관계 메타데이터에 명시된 JOIN 조건만 사용

**검증 전 체크리스트**:
- [ ] 모든 테이블명이 스키마 메타데이터에 존재하는가?
- [ ] 모든 컬럼명이 해당 테이블 스키마에 존재하는가?
- [ ] WHERE 절에 is_active = 1이 포함되었는가?
- [ ] LIMIT 100이 포함되었는가?
"""
```

**결과**: 13개 뉴스 전체가 1차 시도에서 SQL 검증 통과 (재시도 0건)

---

## 9. 활용 방안

### 9.1 대시보드 연동

```python
# 영향받는 협력사 시각화
for result in db_searcher_output["results"]:
    if result["impact_level"] == "HIGH":
        affected_suppliers = [
            r["협력사"] 
            for multi in result["search_results_multi"]
            for r in multi["results"]
        ]
        dashboard.show_alert(
            title=result["title_ko"],
            suppliers=affected_suppliers
        )
```

### 9.2 알림 시스템

```python
# HIGH 영향 + 특정 협력사 발견 시 담당자 통지
for result in db_searcher_output["results"]:
    if result["impact_level"] == "HIGH":
        for multi in result["search_results_multi"]:
            for record in multi["results"]:
                if record["협력사"] in CRITICAL_SUPPLIERS:
                    send_alert(
                        supplier=record["협력사"],
                        news=result["title_ko"],
                        impact=result["risk_scenario"]
                    )
```

### 9.3 Agent_4 입력

Agent_3 출력을 Agent_4에 전달하여 더 정교한 영향 분석 수행:

```python
agent4_input = {
    "news_id": result["news_id"],
    "risk_scenario": result["risk_scenario"],
    "affected_entities": result["search_results_multi"][0]["results"],
    "impact_level": result["impact_level"]
}
```

### 9.4 주간 리포트 생성

```python
# 이번 주 공급망 리스크 요약
high_impact_news = [
    r for r in db_searcher_output["results"]
    if r["impact_level"] == "HIGH"
]

report = f"""
이번 주 HIGH 영향 뉴스: {len(high_impact_news)}건
총 영향받는 협력사: {count_affected_suppliers(high_impact_news)}개
주요 리스크:
{format_risks(high_impact_news)}
"""
```

---

## 10. FAQ

### Q1. search_results와 search_results_multi 중 어떤 걸 사용해야 하나요?

**A**: `search_results_multi`를 사용하세요. 현재 시스템은 다중 시나리오 모드(`ENABLE_MULTI_SCENARIO = True`)로 동작하며, `search_results`는 호환성 유지를 위해 빈 리스트로 남겨둡니다.

### Q2. SQL 검증이 실패하면 어떻게 되나요?

**A**: 
1. 에러 메시지와 함께 LLM에 재시도 요청 (최대 2회)
2. 재시도 시 "이전 SQL 생성 실패" 섹션에 에러 원인 명시
3. 모든 재시도 실패 시 fallback SQL 사용 (단순 조회 쿼리)

### Q3. 다중 시나리오가 생성되지 않고 1개만 나오는 이유는?

**A**: 
- 태그 수 부족: `MIN_TAGS_PER_CLUSTER = 2`인데 태그가 적을 때
- 클러스터링 조건 미충족: 태그들이 같은 타입이거나 분리하기 어려울 때
- 해결: 더 많은 태그 추출 또는 `MIN_TAGS_PER_CLUSTER` 값 조정

### Q4. 온톨로지 DB에 새로운 검색 전략을 추가하려면?

**A**: 
1. `ontology_layer.db`의 `SEARCH_STRATEGY_TEMPLATE` 테이블에 INSERT
2. `strategy_id`, `strategy_name`, `sql_template` 등 필드 작성
3. Agent_3이 자동으로 새 전략 인식 및 활용

```sql
INSERT INTO SEARCH_STRATEGY_TEMPLATE (
    strategy_id,
    strategy_name,
    description,
    sql_template,
    target_entity_types
) VALUES (
    'STRAT_CUSTOM_001',
    '맞춤 검색 전략',
    '특정 상황에 최적화된 검색',
    'SELECT ... FROM ... WHERE ...',
    'SUPPLIER,SITE'
);
```

### Q5. LLM이 생성한 SQL을 수동으로 수정할 수 있나요?

**A**: 
- 출력 JSON에서 `generated_sqls[].sql` 필드 확인
- 필요 시 수정 후 직접 DB 실행 가능
- 시스템 개선: SQL 템플릿 또는 프롬프트 수정 권장

### Q6. 검색 결과가 0개인 경우는 어떻게 처리하나요?

**A**: 
```json
{
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "result_count": 0,
      "results": []
    }
  ]
}
```
- `result_count = 0`으로 표시
- 뉴스가 공급망 DB에 등록되지 않은 엔티티 언급 시 발생
- 정상 동작이며, HITL 플래그로 수동 검토 트리거 가능

### Q7. 성능은 어느 정도인가요?

**A**: 
- 뉴스 1개당 처리 시간: 평균 **3-5초**
- LLM 호출 횟수: 시나리오 생성(1회) + SQL 생성(시나리오별 1회)
- 병렬 처리 지원: 여러 뉴스 동시 처리 가능

---

## 부록

### A. 디렉터리 구조

```
dev/Agent_3_DB_Searcher/
├── config.py                    # 설정 파일
├── graph.py                     # LangGraph 워크플로우 정의
├── prompts.py                   # LLM 프롬프트
├── nodes/                       # 노드별 구현
│   ├── __init__.py             # State 정의
│   ├── validate_input.py       # 입력 검증
│   ├── generate_risk_scenario.py  # Risk 시나리오 생성
│   ├── generate_sql.py         # SQL 생성
│   └── search_db.py            # DB 검색
├── utils/                       # 유틸리티
│   ├── llm_risk_scenario.py    # LLM Risk 시나리오 생성
│   ├── llm_sql_generator.py    # LLM SQL 생성
│   ├── ontology_query.py       # 온톨로지 조회
│   ├── sql_validator.py        # SQL 검증
│   ├── tag_clustering.py       # 태그 클러스터링
│   └── kg_path_finder.py       # KG 경로 탐색
├── scripts/
│   └── run_full_pipeline.py    # 전체 파이프라인 실행
└── output/
    └── output_db_searcher.json  # 최종 출력
```

### B. 관련 문서

- Agent_2 Tag Mapper 문서: `Markdown/Module/DOCS/DOCS_TAG_MAPPER.md`
- Agent_5 News Grouper 문서: `Markdown/Module/DOCS/DOCS_NEWS_GROUPER.md`
- 온톨로지 레이어 설계: `Markdown/Architecture/ONTOLOGY_DESIGN.md`

### C. 변경 이력

| 날짜 | 버전 | 내용 |
|------|------|------|
| 2026-07-08 | 1.0 | 최초 작성 (SQL 프롬프트 강화 반영) |

---

**문서 작성자**: POC-A 개발팀  
**최종 업데이트**: 2026-07-08
