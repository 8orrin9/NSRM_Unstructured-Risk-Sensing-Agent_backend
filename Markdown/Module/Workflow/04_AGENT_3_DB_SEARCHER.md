# Agent_3: DB Searcher (DB 검색 모듈)

## 목차
- [개요](#개요)
- [워크플로우](#워크플로우)
- [State 구조](#state-구조)
- [기능별 상세 설명](#기능별-상세-설명)

---

## 개요

### 모듈 역할
Agent_3는 **Agent_2의 매핑 태그를 기반으로 Risk 시나리오를 생성하고, SQL을 자동 생성하여 공급망 DB를 검색**하는 모듈입니다.

### 파이프라인 위치
```
Agent_2 (Tag Mapper) → [Agent_3: DB Searcher] → Agent_4 (Risk Evaluator)
```

### 주요 기능 (4개)
1. **입력 검증** (`validate_input`)
2. **Risk 시나리오 생성** (`generate_risk_scenario`) - LLM + 온톨로지 조회
3. **SQL 자동 생성** (`generate_sql`) - Text-to-SQL + 구문 검증
4. **DB 검색** (`search_db`) - 공급망 DB 쿼리

---

## 워크플로우

```
validate_input
    ↓
generate_risk_scenario
    ↓
generate_sql
    ↓
search_db
    ↓
END
```

---

## State 구조

### 입력 필드 (Agent_2로부터)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `news_id` | str | 뉴스 ID |
| `title_ko` | str | 제목 (한글) |
| `summary_ko` | str | 요약 (한글) |
| `keywords` | List[Dict] | Agent_1 키워드 |
| `mapped_tags` | List[Dict] | Agent_2 매핑 태그 |

### 출력 필드 (Agent_3 생성)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `risk_scenario` | str | LLM 생성 Risk 시나리오 |
| `risk_scenario_entities` | List[str] | 추출 엔티티 |
| `risk_scenario_confidence` | float | 시나리오 신뢰도 |
| `impact_level` | str | "HIGH" \| "MEDIUM" \| "LOW" |
| `generated_sql` | Optional[str] | 생성된 SQL |
| `sql_explanation` | str | SQL 설명 |
| `search_target_entities` | List[str] | 검색 대상 엔티티 |
| `domain_rules` | List[Dict] | 도메인 규칙 (온톨로지) |
| `search_results` | List[Dict] | DB 검색 결과 |
| `risk_scenarios` | List[Dict] | 다중 시나리오 (2개 이상) |
| `generated_sqls` | List[Dict] | 다중 SQL |
| `search_results_multi` | List[Dict] | 다중 검색 결과 |

---

## 기능별 상세 설명

### 1. validate_input (입력 검증)

#### 📋 설명
Agent_2 출력을 검증합니다.

#### 🤖 사용 모델
LLM 호출 없음

#### 📥 입력값
| 필드명 | 필수/선택 | 설명 |
|--------|-----------|------|
| `mapped_tags` | ✅ 필수 | 최소 1개 이상 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `error` | Optional[str] | 검증 실패 시 에러 메시지 |

#### 📝 예시

**입력 (실패)**:
```json
{
  "mapped_tags": []
}
```

**출력**:
```json
{
  "error": "mapped_tags 필드 없음"
}
```

---

### 2. generate_risk_scenario (Risk 시나리오 생성 + 온톨로지 조회)

#### 📋 설명
4단계 처리를 수행합니다:
1. **LLM Risk 시나리오 생성**: 뉴스 + 태그 → 시나리오 문장
2. **태그 클러스터링** (다중 시나리오 모드): 태그를 2-4개 클러스터로 분류
3. **온톨로지 레이어 조회**: 도메인 규칙, 검색 대상 엔티티, 영향 범위 추출
4. **검색 전략 결정**: 전략 템플릿 매칭, 검색 우선순위 설정

#### 🤖 사용 모델
- **모델**: `gpt-5.5` (복잡한 추론 필요: 태그 클러스터링, Risk 연쇄 추론, 다중 시나리오 생성)
- **온도**: 0.3
- **타임아웃**: 60초
- **다중 시나리오**: `ENABLE_MULTI_SCENARIO=True`일 경우 2-4개 생성
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `title_ko` | str | 뉴스 제목 |
| `summary_ko` | str | 뉴스 요약 |
| `mapped_tags` | List[Dict] | Agent_2 매핑 태그 |
| `group_insight` | Optional[Dict] | 그룹 인사이트 (선택) |

#### 📤 출력값

**단일 시나리오 모드**:
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `risk_scenario` | str | LLM 생성 시나리오 |
| `risk_scenario_entities` | List[str] | 추출 엔티티 |
| `impact_level` | str | "HIGH" \| "MEDIUM" \| "LOW" |

**다중 시나리오 모드** (2-4개):
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `risk_scenarios` | List[Dict] | 시나리오 배열 |
| `risk_scenario` | str | 첫 번째 시나리오 (호환성) |

**risk_scenarios 구조**:
```json
[
  {
    "scenario_id": "cluster_001",
    "scenario_text": "중국 희토류 수출 중단으로 협력사 2곳 영향",
    "entities": ["희토류", "중국"],
    "impact_level": "HIGH",
    "confidence": 0.92
  }
]
```

#### 처리 단계

**Step 1: LLM 시나리오 생성**
- 뉴스 + 태그 → LLM (gpt-5.5) → 시나리오 문장
- KG 경로 활용 (옵션)

**Step 2: 태그 클러스터링** (다중 시나리오 모드)
- 태그를 2-4개 클러스터로 분류
- `group_insight` 활용 (Agent_5에서 전달)
- 클러스터별 시나리오 생성

**Step 3: 온톨로지 레이어 조회**
```sql
SELECT *
FROM DOMAIN_KNOWLEDGE_RULES
WHERE json_extract(applicable_tags, '$') LIKE '%TAG_ID%'
  AND is_active = 1
ORDER BY priority ASC
```

**조회 전략**:
1. 완전 매칭: 모든 tag_id 포함
2. 부분 매칭: 2개 이상 tag_id 포함
3. 타입 매칭: tag_type 조합 (예: EVENT + SUPPLIER → "SUPPLIER_EVENT")

**출력**:
- `domain_rules`: 도메인 지식 규칙 배열
  - `background_knowledge`: "희토류 80% 중국 생산"
  - `impact_assessment`: "글로벌 공급망 전체 영향"
  - `search_targets`: "1) RAW_MATERIAL_MASTER, 2) ..."
- `search_target_entities`: 검색 대상 테이블 배열 (search_targets 파싱)
  - 예: `["RAW_MATERIAL_MASTER", "MATERIAL_MASTER", "SUPPLIER_MASTER"]`
- `impact_scope`: 영향 범위 설명 (impact_assessment 값)

**Step 4: 검색 전략 결정**
```sql
SELECT strategy_id, strategy_name, sql_template
FROM SEARCH_STRATEGY_TEMPLATE
WHERE strategy_id = ?
```

**출력**:
- `search_strategy_id`: 전략 ID
- `search_strategy`: SQL 템플릿 정보

#### 💬 프롬프트 (LLM 시나리오 생성)

**System**:
```
당신은 반도체 공급망 리스크 분석 전문가입니다.
```

**User**:
```
다음 뉴스와 매핑된 태그를 기반으로 공급망 Risk 시나리오를 생성하세요.

**뉴스 정보**:
제목: {title_ko}
요약: {summary_ko}

**매핑된 태그**:
{formatted_tags}

**지식 그래프 경로 (Insight KG)**: (옵션)
{formatted_kg_paths}

**Risk 시나리오 생성 규칙**:
1. 엔티티와 이벤트의 관계를 명확히 기술
2. 지식 그래프 경로를 활용하여 엔티티 간 연관성 강화
3. 구체적으로 기술: 어떤 엔티티/이벤트/영향인지 명시
4. 추상적 표현 금지
5. 시나리오 길이: 1-3문장

**출력 형식 (JSON)**:
{
  "risk_scenario": "생성된 시나리오 문장",
  "entities": ["추출된 엔티티1", "엔티티2"],
  "confidence": 0.85,
  "impact_level": "HIGH"
}
```

**참고**: 실제 프롬프트는 `prompts.py`의 `RISK_SCENARIO_GENERATION_PROMPT` 참조

#### 📝 예시

**입력**:
```json
{
  "title_ko": "중국, 희토류 대미 수출 전면 중단",
  "summary_ko": "중국 정부가 7월 1일부터 미국에 대한 희토류 수출을 전면 중단...",
  "mapped_tags": [
    {"tag_id": "MAT_RARE_EARTH", "tag_name": "희토류"},
    {"tag_id": "SITE_CHINA", "tag_name": "중국"}
  ]
}
```

**출력**:
```json
{
  "risk_scenario": "중국의 희토류 수출 중단으로 삼성전자 협력사 3곳(ABC Materials, XYZ Corp, DEF Industries)의 조달에 차질이 예상됨. 해당 협력사들은 반도체 제조 핵심 부품을 공급하고 있어 생산 차질 우려.",
  "risk_scenario_entities": ["희토류", "중국", "ABC Materials", "XYZ Corp", "DEF Industries"],
  "impact_level": "HIGH",
  "risk_scenario_confidence": 0.92,
  "domain_rules": [
    {
      "rule_id": "RULE_MAT_001",
      "rule_name": "소재 공급 차단 시 협력사 조회",
      "search_strategy": "material_supplier_lookup"
    }
  ],
  "search_target_entities": ["희토류"]
}
```

---

### 3. generate_sql (SQL 자동 생성)

#### 📋 설명
LLM을 사용하여 **Text-to-SQL**을 수행하고, **구문 검증 + 재시도**를 통해 올바른 SQL을 생성합니다.

#### 🤖 사용 모델
- **모델**: `gpt-5.5` (복잡한 추론 필요: 복잡한 스키마 이해, 다중 JOIN 추론, WHERE 조건 최적화)
- **온도**: 0.1 (매우 낮음)
- **타임아웃**: 60초
- **재시도**: 최대 2회 (검증 실패 시)
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `title_ko` | str | 뉴스 제목 |
| `keywords` | List[str] | 키워드 배열 |
| `mapped_tags` | List[Dict] | 매핑 태그 |
| `risk_scenario` | str | Risk 시나리오 |
| `domain_rules` | List[Dict] | 도메인 규칙 |
| `search_target_entities` | List[str] | 검색 대상 엔티티 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `generated_sql` | Optional[str] | 생성된 SQL |
| `sql_explanation` | str | SQL 설명 |

#### DB 스키마 (제공)

```sql
-- SUPPLIER_MASTER: 협력사 마스터
CREATE TABLE SUPPLIER_MASTER (
  supplier_id TEXT PRIMARY KEY,
  supplier_name TEXT,
  country TEXT,
  tier INTEGER
);

-- SITE_MASTER: 생산지/공장 마스터
CREATE TABLE SITE_MASTER (
  site_id TEXT PRIMARY KEY,
  site_name TEXT,
  country TEXT,
  site_type TEXT
);

-- MATERIAL_MASTER: 자재 마스터
CREATE TABLE MATERIAL_MASTER (
  material_id TEXT PRIMARY KEY,
  material_name TEXT,
  category TEXT
);

-- SUPPLIER_MATERIAL: 협력사-자재 관계
CREATE TABLE SUPPLIER_MATERIAL (
  supplier_id TEXT,
  material_id TEXT,
  FOREIGN KEY (supplier_id) REFERENCES SUPPLIER_MASTER(supplier_id),
  FOREIGN KEY (material_id) REFERENCES MATERIAL_MASTER(material_id)
);

-- SUPPLIER_SITE: 협력사-생산지 관계
CREATE TABLE SUPPLIER_SITE (
  supplier_id TEXT,
  site_id TEXT,
  FOREIGN KEY (supplier_id) REFERENCES SUPPLIER_MASTER(supplier_id),
  FOREIGN KEY (site_id) REFERENCES SITE_MASTER(site_id)
);
```

#### 💬 프롬프트

**System**:
```
당신은 SQL 전문가입니다. 제공된 스키마만 사용하여 정확한 SQL을 생성하세요.
```

**User**:
```
다음 정보를 바탕으로 공급망 DB를 검색하는 SQL을 작성해주세요.

**뉴스 제목**: {title_ko}
**키워드**: {keywords}
**매핑된 태그**: {mapped_tags}
**Risk 시나리오**: {risk_scenario}
**검색 대상 엔티티**: {search_target_entities}
**도메인 규칙**: {domain_rules}

**DB 스키마**:
{schema}

**SQL 작성 원칙**:
1. 제공된 테이블과 컬럼명만 사용
2. JOIN 조건은 제공된 관계 메타데이터만 사용
3. 최대 100건 제한 (LIMIT 100)
4. 구체적 조건 사용 (LIKE 대신 = 우선)

**출력 형식 (JSON)**:
{
  "sql": "SELECT ... FROM ... WHERE ...",
  "explanation": "SQL 설명 (무엇을 검색하는지)"
}
```

#### 구문 검증 + 재시도

```python
# 1차 시도
sql = llm_generate_sql(prompt)
if validate_sql_syntax(sql):
    return sql

# 2차 시도 (에러 피드백 포함)
sql = llm_generate_sql(prompt + f"\n이전 SQL 에러: {error}")
if validate_sql_syntax(sql):
    return sql

# 3차 시도 실패 → Fallback SQL
return fallback_sql
```

#### 📝 예시

**입력**:
```json
{
  "title_ko": "중국, 희토류 대미 수출 중단",
  "keywords": ["희토류", "중국"],
  "mapped_tags": [
    {"tag_name": "희토류"},
    {"tag_name": "중국"}
  ],
  "risk_scenario": "중국의 희토류 수출 중단으로 협력사 3곳 조달 차질",
  "search_target_entities": ["희토류"],
  "domain_rules": [
    {"search_strategy": "material_supplier_lookup"}
  ]
}
```

**출력**:
```json
{
  "generated_sql": "SELECT DISTINCT s.supplier_id, s.supplier_name, s.country, m.material_name FROM SUPPLIER_MASTER s INNER JOIN SUPPLIER_MATERIAL sm ON s.supplier_id = sm.supplier_id INNER JOIN MATERIAL_MASTER m ON sm.material_id = m.material_id WHERE m.material_name LIKE '%희토류%' AND s.country = '중국' LIMIT 100",
  "sql_explanation": "중국 소재 협력사 중 희토류를 공급하는 업체 조회"
}
```

---

### 4. search_db (DB 검색)

#### 📋 설명
생성된 SQL을 공급망 DB(`supply_chain.db`)에서 실행합니다.

#### 🤖 사용 모델
LLM 호출 없음 (DB 쿼리)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `generated_sql` | str | 생성된 SQL |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `search_results` | List[Dict] | DB 검색 결과 (최대 100건) |

**search_results 구조**:
```json
[
  {
    "supplier_id": "SUP_001",
    "supplier_name": "ABC Materials",
    "country": "중국",
    "material_name": "희토류"
  }
]
```

#### 다중 시나리오 모드

`generated_sqls` 배열을 순회하여 각 SQL 실행:

```json
{
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "sql": "SELECT ...",
      "result_count": 3,
      "results": [...]
    }
  ]
}
```

#### 📝 예시

**입력**:
```json
{
  "generated_sql": "SELECT DISTINCT s.supplier_id, s.supplier_name, s.country, m.material_name FROM SUPPLIER_MASTER s INNER JOIN SUPPLIER_MATERIAL sm ON s.supplier_id = sm.supplier_id INNER JOIN MATERIAL_MASTER m ON sm.material_id = m.material_id WHERE m.material_name LIKE '%희토류%' AND s.country = '중국' LIMIT 100"
}
```

**출력**:
```json
{
  "search_results": [
    {
      "supplier_id": "SUP_001",
      "supplier_name": "ABC Materials",
      "country": "중국",
      "material_name": "희토류"
    },
    {
      "supplier_id": "SUP_005",
      "supplier_name": "XYZ Corp",
      "country": "중국",
      "material_name": "희토류"
    }
  ]
}
```

---

## 문서 네비게이션

- **이전**: [Agent_2: Tag Mapper](03_AGENT_2_TAG_MAPPER.md)
- **다음**: [Agent_4: Risk Evaluator](05_AGENT_4_RISK_EVALUATOR.md)
- **개요**: [시스템 개요 (00_OVERVIEW.md)](00_OVERVIEW.md)

---

**작성일**: 2026-07-12  
**버전**: 1.0
