# 공급망 DB 온톨로지 레이어 설계 문서

## 1. 개요

### 1.1 목적

공급망 DB (`supply_chain.db`)의 테이블 구조를 LLM이 이해하고 적절한 Text-to-SQL을 생성할 수 있도록 **메타데이터 레이어(온톨로지)**를 구축합니다.

### 1.2 핵심 원칙

1. **RDB 구조 유지**: 기존 공급망 DB는 변경하지 않음
2. **메타데이터 분리**: 온톨로지 정보는 별도 DB 파일 (`ontology_layer.db`)에 저장
3. **LLM 친화적**: 자연어 설명과 검색 힌트 제공
4. **점진적 학습**: 쿼리 패턴 학습 및 개선 가능

### 1.3 배경

현재 시스템은 다음 프로세스를 따릅니다:

```
1. 뉴스 수집
2. 뉴스에서 키워드 추출 및 태그 매핑
3. 태그 기반으로 LLM이 검색 전략 수립
4. LLM이 Text-to-SQL 생성  ← 온톨로지 활용 지점
5. DB 검색
6. 검색 결과 기반 공급망 리스크 판단
```

**문제점**: 4단계에서 LLM이 DB 구조를 정확히 이해하지 못하면 잘못된 SQL 생성
- 잘못된 테이블 선택 (예: ASML을 RAW_MATERIAL_MASTER에서 검색)
- 잘못된 JOIN 경로 (예: SUPPLIER → MATERIAL 직접 JOIN)
- 도메인 지식 부족 (예: 네온가스 → 우크라이나 의존도 70%)
- 태그만으로 검색 범위 판단 불가 (예: "네온" 태그 → 전세계? 우크라이나만?)

**해결책**: 온톨로지 레이어로 LLM에게 필요한 메타데이터와 배경 지식 제공
- 메타데이터: DB 구조, JOIN 경로, 검색 전략
- 도메인 지식: 배경 정보 및 조건부 힌트 (강제 아님)
- LLM이 뉴스 내용 + 태그 + 도메인 지식을 종합하여 검색 전략 수립

---

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────┐
│   기존 공급망 DB (supply_chain.db)    │  ← 변경 없음
│  ─────────────────────────────────  │
│  • SUPPLIER_MASTER (120개)          │
│  • SITE_MASTER (250개)              │
│  • MATERIAL_MASTER (400개)          │
│  • RAW_MATERIAL_MASTER (114개)      │
│  • SITE_MATERIAL_MAP                │
│  • MATERIAL_RAW_MATERIAL_MAP        │
│  • SUPPLIER_RAW_MATERIAL_MAP        │
└─────────────────────────────────────┘
            ↕ ATTACH로 참조
┌─────────────────────────────────────┐
│ 온톨로지 레이어 (ontology_layer.db)   │  ← 신규
│  ─────────────────────────────────  │
│  1. DB_TABLE_METADATA               │
│  2. DB_COLUMN_METADATA              │
│  3. DB_TABLE_RELATIONSHIP           │
│  4. SEARCH_STRATEGY_TEMPLATE        │
│  5. TAG_SEARCH_STRATEGY_MAP         │
│  6. DOMAIN_KNOWLEDGE_RULES          │
│  7. V_ENTITY_HIERARCHY (뷰)         │
└─────────────────────────────────────┘
            ↓ 정보 제공
┌─────────────────────────────────────┐
│      LLM (Text-to-SQL 생성)         │
└─────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
뉴스: "중국의 희토류 수출 규제 강화"
  ↓
태그 추출: ["RAW_SEMICONDUCTOR_METAL", "CHINA"]
  ↓
온톨로지 조회:
  ├─ TABLE_METADATA: RAW_MATERIAL_MASTER, SITE_MASTER 정보
  ├─ COLUMN_METADATA: country, name_kor 컬럼 정보
  ├─ RELATIONSHIP: RAW_MATERIAL → MATERIAL → SITE 경로
  ├─ STRATEGY: "원자재-지역 영향 추적" 전략
  └─ DOMAIN_RULE: "희토류 중국 의존도 80%" 규칙
  ↓
LLM 프롬프트:
  """
  뉴스: 중국의 희토류 수출 규제 강화
  태그: RAW_SEMICONDUCTOR_METAL, CHINA
  
  [테이블 정보]
  RAW_MATERIAL_MASTER: 소재 마스터, name_kor LIKE 검색 가능
  SITE_MASTER: 생산지 마스터, country = 'China' 필터 가능
  
  [JOIN 경로]
  RAW_MATERIAL → MATERIAL_RAW_MATERIAL_MAP → MATERIAL 
  → SITE_MATERIAL_MAP → SITE → SUPPLIER
  
  [도메인 지식]
  희토류 배경:
  - 중국 생산 비중: 약 80%
  - 리스크 레벨: 매우 높음 (의존도 80%)
  
  영향 범위:
  - 중국 공급 차질 → 글로벌 반도체 공급망 전체 영향
  - 대체 공급원: 미국 (5%), 호주 (10%) - 규모 부족
  
  검색 대상:
  1) 희토류 소재 조회
  2) 희토류 포함 자재 조회
  3) 그 자재 사용 협력사 조회 (전세계, 필터 없음)
  4) 중국 Site 조회 (영향 범위 확인용)
  
  위 정보를 참고하여 SQL을 생성하세요.
  """
  ↓
LLM이 생성한 SQL:
  SELECT 
      sup.name_kor as 협력사,
      m.name_kor as 영향받는_자재,
      s.country as 생산지_국가
  FROM RAW_MATERIAL_MASTER sub
  JOIN MATERIAL_RAW_MATERIAL_MAP msm ON sub.substance_code = msm.substance_code
  JOIN MATERIAL_MASTER m ON msm.material_code = m.material_code
  JOIN SITE_MATERIAL_MAP smm ON m.material_code = smm.material_code
  JOIN SITE_MASTER s ON smm.site_code = s.site_code
  JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
  WHERE sub.name_kor LIKE '%희토류%'
    AND s.country = 'China'
```

---

## 3. 테이블 설계

### 3.1 DB_TABLE_METADATA (테이블 메타데이터)

**목적**: 각 테이블의 역할과 용도를 LLM에게 설명

**주요 컬럼**:
- `table_name`: 실제 테이블명 (예: "SUPPLIER_MASTER")
- `table_type`: "MASTER" / "MAPPING"
- `llm_description`: LLM에게 제공할 자연어 설명
- `primary_entity_type`: 태그 유형과 매핑 ("SUPPLIER", "MATERIAL", "RAW_MATERIAL", "SITE", null)
- `search_priority`: 검색 우선순위 (1: 최우선 ~ 5: 보조)
- `typical_join_path`: 전형적인 JOIN 경로

**예시**:
```sql
INSERT INTO DB_TABLE_METADATA VALUES (
    'TBL_SUPPLIER_MASTER',
    'SUPPLIER_MASTER',
    'MASTER',
    '협력사 마스터 테이블',
    '협력사(법인) 기본 정보를 관리하는 테이블입니다. 협력사명, 국가, 지역 등의 정보를 포함합니다. 협력사의 생산 거점은 SITE_MASTER 테이블에서 관리됩니다.',
    'SUPPLIER',
    1,
    'SUPPLIER_MASTER → SITE_MASTER → SITE_MATERIAL_MAP → MATERIAL_MASTER',
    120,
    1
);
```

---

### 3.2 DB_COLUMN_METADATA (컬럼 메타데이터)

**목적**: 각 컬럼의 의미와 검색 방법을 LLM에게 안내

**주요 컬럼**:
- `column_name`: 컬럼명 (예: "name_kor")
- `semantic_type`: 의미론적 분류 (예: "ENTITY_NAME", "LOCATION", "TYPE_CATEGORY")
- `llm_description`: LLM에게 제공할 설명
- `search_operator`: 권장 검색 연산자 ("=", "LIKE", "IN")
- `search_hint`: 검색 팁
- `sample_values`: 샘플 값 (JSON 배열)
- `is_foreign_key`, `references_table`: FK 정보

**semantic_type 분류**:
| 값 | 의미 | 예시 컬럼 |
|---|------|----------|
| ENTITY_NAME | 엔티티 명칭 | name_kor, name_eng |
| ENTITY_CODE | 엔티티 코드 (PK) | supplier_code, material_code |
| LOCATION | 위치 정보 | country, region |
| TYPE_CATEGORY | 분류/유형 | raw_material_type, material_type |
| QUANTITY | 수량/비율 | supply_ratio, inclusion_ratio |
| FLAG | 불린 플래그 | is_active, is_main_supplier |

**예시**:
```sql
INSERT INTO DB_COLUMN_METADATA VALUES (
    'COL_SUPPLIER_NAME_KOR',
    'TBL_SUPPLIER_MASTER',
    'name_kor',
    'TEXT',
    0,
    'ENTITY_NAME',
    '협력사 한글 명칭',
    '협력사의 한글 정식 명칭입니다. LIKE 연산자로 부분 매칭을 권장하며, name_eng 컬럼도 함께 검색하는 것이 좋습니다.',
    1, 0,
    'LIKE',
    'WHERE name_kor LIKE ''%키워드%'' OR name_eng LIKE ''%키워드%''',
    '["삼성전자", "SK하이닉스", "한화정밀화학"]',
    120,
    0, 0, null, null
);
```

---

### 3.3 DB_TABLE_RELATIONSHIP (테이블 간 관계)

**목적**: JOIN 경로와 관계 유형을 명시

**주요 컬럼**:
- `from_table`, `to_table`: 관계 양끝 테이블
- `relationship_type`: "1:N", "N:M", "1:1"
- `join_condition`: JOIN SQL (예: "SUPPLIER_MASTER.supplier_code = SITE_MASTER.supplier_code")
- `llm_join_hint`: LLM에게 제공할 힌트
- `avg_cardinality`: 평균 카디널리티 (예: "1:2" - 1개 협력사당 평균 2개 Site)

**예시**:
```sql
INSERT INTO DB_TABLE_RELATIONSHIP VALUES (
    'REL_SUPPLIER_SITE',
    'TBL_SUPPLIER_MASTER',
    'TBL_SITE_MASTER',
    '1:N',
    'SUPPLIER_MASTER.supplier_code = SITE_MASTER.supplier_code',
    'INNER',
    '협력사의 생산 거점(Site)을 찾으려면 SITE_MASTER를 JOIN하세요. 1개 협력사는 평균 2개의 Site를 가집니다.',
    '협력사별 생산지 추적',
    1,
    '1:2'
);
```

---

### 3.4 SEARCH_STRATEGY_TEMPLATE (검색 전략 템플릿)

**목적**: 태그 조합별 검색 전략을 사전 정의

**주요 컬럼**:
- `strategy_name`: 전략명 (예: "원자재-지역 영향 추적")
- `required_tag_types`: 필수 태그 유형 (JSON: `["RAW_MATERIAL", "SITE"]`)
- `optional_tag_types`: 선택 태그 유형 (JSON: `["SUPPLIER"]`)
- `sql_template`: SQL 템플릿 (Jinja2 스타일, `{{변수}}` 사용)
- `strategy_description`: 전략 설명
- `example_scenario`: 예시 시나리오

**예시**:
```sql
INSERT INTO SEARCH_STRATEGY_TEMPLATE VALUES (
    'STRAT_RAW_MATERIAL_SITE_IMPACT',
    '원자재-지역 영향 추적',
    '["RAW_MATERIAL", "SITE"]',
    '["SUPPLIER"]',
    '
SELECT 
    sup.name_kor as 협력사,
    m.name_kor as 영향받는_자재,
    s.country as 생산지_국가,
    sub.name_kor as 원자재,
    smm.supply_ratio as 공급비중
FROM RAW_MATERIAL_MASTER sub
JOIN MATERIAL_RAW_MATERIAL_MAP msm ON sub.substance_code = msm.substance_code
JOIN MATERIAL_MASTER m ON msm.material_code = m.material_code
JOIN SITE_MATERIAL_MAP smm ON m.material_code = smm.material_code
JOIN SITE_MASTER s ON smm.site_code = s.site_code
JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
WHERE sub.name_kor LIKE ''%{{raw_material_keyword}}%''
  AND s.country = ''{{site_country}}''
ORDER BY smm.supply_ratio DESC
    ',
    '특정 국가의 특정 원자재 공급 차질이 발생했을 때, 영향받는 자재와 협력사를 추적합니다.',
    '예시: 중국의 희토류 수출 규제 → 희토류를 사용하는 자재 → 중국에서 생산하는 Site → 해당 협력사',
    '결과는 영향받는 협력사와 자재 목록입니다. supply_ratio가 높을수록 해당 Site의 공급 의존도가 큽니다.',
    1
);
```

---

### 3.5 TAG_SEARCH_STRATEGY_MAP (태그-전략 매핑)

**목적**: 각 태그에 적용 가능한 검색 전략 연결

**주요 컬럼**:
- `tag_id`, `target_region`: 태그 식별자
- `strategy_id`: 연결된 전략 ID
- `condition_description`: 전략 적용 조건
- `requires_other_tags`: 함께 필요한 다른 태그 유형 (JSON)

**예시**:
```sql
INSERT INTO TAG_SEARCH_STRATEGY_MAP (tag_id, target_region, strategy_id, condition_description, requires_other_tags)
VALUES (
    'RAW_SPECIAL_GAS',
    'KR',
    'STRAT_RAW_MATERIAL_SITE_IMPACT',
    '특수가스 태그와 국가/지역 태그가 함께 나타나면 이 전략을 우선 사용',
    '["SITE"]'
);
```

---

### 3.6 DOMAIN_KNOWLEDGE_RULES (도메인 지식 규칙)

**목적**: 리스크 중요도 평가와 영향 범위 이해를 돕는 배경 지식 저장

**역할**:
- **리스크 중요도** 평가 기준 (의존도, 집중도)
- **영향 범위** 판단 (글로벌 vs 지역적)
- **검색 대상** 정의 (무엇을 조회해야 하는가)
- **대체 가능 여부** 정보

**비역할** (하지 않는 것):
- ✗ 검색 범위 제한 (country = 'Ukraine'만 조회하라 등)
- ✗ WHERE 조건 강제

**주요 컬럼**:
- `rule_category`: 규칙 분류 (예: "GEOGRAPHIC_RISK", "MATERIAL_DEPENDENCY")
- `rule_name`, `rule_description`: 규칙명과 설명
- `background_knowledge`: 배경 지식 (의존도, 생산 비중 등)
- `impact_assessment`: 리스크 중요도 평가 기준
- `search_targets`: 조회해야 할 대상 (자재? 협력사? Site?)
- `alternative_sources`: 대체 공급원 정보
- `applicable_tags`: 적용 대상 태그 (JSON)
- `applicable_scenarios`: 적용 시나리오 (JSON)
- `verified_by`, `verification_date`: 검증 정보

**rule_category 분류**:
| 카테고리 | 설명 | 예시 |
|---------|------|------|
| GEOGRAPHIC_RISK | 지역별 리스크 특성 | 네온가스 우크라이나 의존도, 대만 지진 리스크 |
| MATERIAL_DEPENDENCY | 자재/소재 의존 관계 | EUV 장비 ASML 독점, MLCC 일본 의존도 |
| SUPPLY_CHAIN_PATH | 공급망 경로 특성 | 희토류 → 자석 → 모터 |
| REGULATORY_PATTERN | 규제 패턴 | ECCN 분류, Entity List 영향 |

**예시 1: 희토류 중국 의존도**:
```sql
INSERT INTO DOMAIN_KNOWLEDGE_RULES VALUES (
    'RULE_RARE_EARTH_CHINA',
    'GEOGRAPHIC_RISK',
    '희토류 중국 의존도',
    '희토류는 전세계 생산량의 약 80%가 중국에서 생산됩니다.',
    -- background_knowledge
    '희토류는 전세계 생산량의 약 80%가 중국에서 생산됩니다.',
    -- impact_assessment
    '의존도 80% → 높은 리스크. 중국의 수출 규제는 글로벌 반도체 공급망 전체에 영향을 미칩니다.',
    -- search_targets
    '1) 희토류 소재 조회 (RAW_MATERIAL_MASTER), 2) 희토류를 포함하는 자재 조회 (MATERIAL_RAW_MATERIAL_MAP → MATERIAL_MASTER), 3) 그 자재를 사용하는 협력사 조회 (전세계, 필터 없음), 4) 중국 소재 Site 조회 (영향 범위 확인용)',
    -- alternative_sources
    '미국 (5%), 호주 (10%). 대체 가능하나 규모 부족하여 중국 공급 차질 시 전세계적 영향 불가피.',
    '["RAW_SEMICONDUCTOR_METAL", "RARE_EARTH", "CHINA"]',
    '["수출규제", "무역전쟁"]',
    null, null, null,
    1, 1
);
```

**예시 2: 네온가스 우크라이나 의존도**:
```sql
INSERT INTO DOMAIN_KNOWLEDGE_RULES VALUES (
    'RULE_NEON_UKRAINE',
    'GEOGRAPHIC_RISK',
    '네온가스 우크라이나 의존도',
    '네온가스는 전세계 공급량의 약 70%가 우크라이나에서 생산됩니다.',
    -- background_knowledge
    '네온가스는 전세계 공급량의 약 70%가 우크라이나에서 생산됩니다.',
    -- impact_assessment
    '의존도 70% → 높은 리스크. 우크라이나 공급 차질 시 글로벌 반도체 산업 전체에 영향을 미칩니다.',
    -- search_targets
    '1) 네온가스 소재 조회 (RAW_MATERIAL_MASTER), 2) 네온가스를 포함하는 자재 조회 (포토레지스트 등), 3) 그 자재를 사용하는 협력사 조회 (전세계, 필터 없음), 4) 우크라이나 소재 Site 조회 (영향 범위 확인용)',
    -- alternative_sources
    '일본 (20%), 미국 (10%). 대체 가능하나 우크라이나 공급 차질 시 전세계적 공급 부족 예상.',
    '["RAW_SPECIAL_GAS", "NEON", "UKRAINE"]',
    '["전쟁", "공급차질"]',
    null, null, null,
    1, 1
);
```

---

### 3.6.1 도메인 지식 규칙의 역할

**목적**: 리스크 중요도와 영향 범위 판단을 돕는 배경 지식 제공

#### 역할

1. **리스크 중요도 평가**: 의존도 → 리스크 레벨 판단
2. **영향 범위 판단**: 글로벌 vs 지역적 영향
3. **검색 대상 정의**: 무엇을 조회해야 하는가
4. **대체 가능 여부**: 공급원 다변화 가능성

#### 비역할 (하지 않는 것)

- ✗ 검색 범위 제한 (특정 country로 필터링 지시)
- ✗ WHERE 조건 강제
- ✗ SQL 로직 결정

#### 올바른 동작 방식

```
뉴스: "우크라이나 전쟁으로 네온가스 부족"
태그: ["NEON", "UKRAINE"]
도메인 규칙: "네온가스 우크라이나 의존도 70%"

도메인 규칙이 알려주는 것:
  - 의존도 70% → 높은 리스크
  - 우크라이나 문제 = 글로벌 영향 (70%라서)
  - 검색 대상: 네온가스 포함 자재 → 그 자재 쓰는 협력사 (전세계)
  - 추가 조회: 우크라이나 Site (영향 범위 확인)

LLM이 생성하는 검색:
  1. 네온가스 포함 자재 조회 (필터 없음)
  2. 그 자재 사용 협력사 조회 (전세계, 필터 없음)
  3. 우크라이나 Site 조회 (영향 확인용)
```

#### 케이스별 예시

**케이스 1: 우크라이나 네온가스**

| 항목 | 내용 |
|------|------|
| 뉴스 | "우크라이나 전쟁으로 네온가스 공급 차질" |
| 태그 | NEON, UKRAINE |
| 도메인 규칙 | "네온 우크라이나 70% → 높은 리스크" |
| 검색 대상 | 1) 네온가스 포함 자재<br>2) 그 자재 쓰는 협력사 (전세계)<br>3) 우크라이나 Site (영향 확인) |
| 검색 범위 | 1,2번은 필터 없음<br>3번만 country = 'Ukraine' |

**케이스 2: 일본 MLCC 지진**

| 항목 | 내용 |
|------|------|
| 뉴스 | "일본 규슈 지진으로 MLCC 공장 가동 중단" |
| 태그 | MLCC, JAPAN, 규슈 |
| 도메인 규칙 | "MLCC 일본 집중도 60% → 중간 리스크" |
| 검색 대상 | 1) MLCC 자재<br>2) MLCC 쓰는 협력사 (전세계)<br>3) 일본 규슈 Site (영향 확인) |
| 검색 범위 | 1,2번은 필터 없음<br>3번만 country = 'Japan' AND region LIKE '%규슈%' |

**케이스 3: 희토류 중국 규제**

| 항목 | 내용 |
|------|------|
| 뉴스 | "중국, 희토류 수출 규제 강화" |
| 태그 | RARE_EARTH, CHINA |
| 도메인 규칙 | "희토류 중국 80% → 매우 높은 리스크" |
| 검색 대상 | 1) 희토류 소재<br>2) 희토류 포함 자재<br>3) 그 자재 쓰는 협력사 (전세계)<br>4) 중국 Site (영향 확인) |
| 검색 범위 | 1,2,3번은 필터 없음<br>4번만 country = 'China' |

---

### 3.7 V_ENTITY_HIERARCHY (계층 관계 뷰)

**목적**: 자재-소재 등 계층 관계를 자동으로 동기화

**구조**: supply_chain.db의 매핑 테이블을 참조하여 뷰 생성
- 자재 → 소재 (CONTAINS)
- 협력사 → 생산지 (HAS_SITE)
- 생산지 → 자재 (PRODUCES)

**예시**:
```sql
CREATE VIEW V_ENTITY_HIERARCHY AS
SELECT 
    'HIE_M2S_' || msm.mapping_id as hierarchy_id,
    'MATERIAL' as parent_entity_type,
    m.material_code as parent_entity_id,
    m.name_kor as parent_name,
    'RAW_MATERIAL' as child_entity_type,
    sub.substance_code as child_entity_id,
    sub.name_kor as child_name,
    'CONTAINS' as relationship_type,
    msm.inclusion_ratio as weight,
    m.name_kor || '은(는) ' || sub.name_kor || '을(를) 포함합니다.' as llm_relationship_hint
FROM MATERIAL_RAW_MATERIAL_MAP msm
JOIN MATERIAL_MASTER m ON msm.material_code = m.material_code
JOIN RAW_MATERIAL_MASTER sub ON msm.substance_code = sub.substance_code
WHERE msm.is_active = 1;
```

---

## 4. 데이터 생성 전략

### 4.1 자동 생성 (메타데이터)

**대상**: DB_TABLE_METADATA, DB_COLUMN_METADATA, DB_TABLE_RELATIONSHIP

**방법**:
1. `PRAGMA table_info()` 로 테이블 구조 추출
2. `PRAGMA foreign_key_list()` 로 FK 관계 추출
3. 템플릿 기반으로 `llm_description` 자동 생성

**스크립트**: `populate_metadata.py`

### 4.2 반자동 생성 (검색 전략, 태그 매핑)

**대상**: SEARCH_STRATEGY_TEMPLATE, TAG_SEARCH_STRATEGY_MAP

**SEARCH_STRATEGY_TEMPLATE (수동 작성)**:
- 검색 전략 템플릿: 초기 9~13개
- 스크립트: `populate_strategies.py`

**TAG_SEARCH_STRATEGY_MAP (자동 생성)**:
- Agent_2 출력에서 태그 추출
- 태그 타입 패턴 기반 자동 매핑 (RAW_* → RAW_MATERIAL_SITE_IMPACT, etc.)
- 스크립트: `populate_metadata.py` (Step 6)
- 효과: Fallback 전략 사용 59.1% → 0%

### 4.3 수동 작성 (도메인 규칙)

**대상**: DOMAIN_KNOWLEDGE_RULES

**초기 작성**:
- 도메인 지식 규칙: 5~10개 (임시)
- 스크립트: `populate_domain_rules.py`

**추후 보강**: 도메인 전문가 검토 후 추가

---

## 5. LLM 프롬프트 통합

### 5.1 프롬프트 구조

```python
def build_llm_prompt_with_ontology(news_text, extracted_tags):
    """
    온톨로지 정보를 포함한 LLM 프롬프트 생성
    """
    
    # 1. 관련 테이블 메타데이터
    table_info = get_relevant_tables(extracted_tags)
    
    # 2. 검색 전략 템플릿
    strategies = get_search_strategies(extracted_tags)
    
    # 3. 도메인 지식 규칙
    rules = get_domain_rules(extracted_tags)
    
    # 4. 계층 관계
    hierarchies = get_entity_hierarchies(extracted_tags)
    
    prompt = f"""
# 공급망 DB 검색 전략 수립

## 뉴스 내용
{news_text}

## 추출된 태그
{json.dumps(extracted_tags, ensure_ascii=False, indent=2)}

## 관련 테이블 스키마
{format_table_metadata(table_info)}

## 권장 검색 전략
{format_strategies(strategies)}

## 도메인 지식
다음은 리스크 평가와 검색 대상 정의에 도움을 주는 배경 지식입니다.

{format_rules(rules)}

## 엔티티 계층 관계
{format_hierarchies(hierarchies)}

## 요청사항
위 정보를 참고하여 SQLite 쿼리를 생성하세요.
- 도메인 지식의 "검색 대상"을 참고하여 무엇을 조회할지 결정하세요.
- 의존도/집중도는 리스크 중요도 판단에 활용하세요.
- Site는 영향 범위 확인용으로만 별도 조회하세요 (자재/협력사 조회에는 필터 적용 안 함).
- JOIN 경로는 테이블 관계 정보를 참고하세요.
"""
    
    return prompt
```

### 5.2 예시 출력

**입력**:
- 뉴스: "중국의 희토류 수출 규제 강화"
- 태그: `["RAW_SEMICONDUCTOR_METAL", "CHINA"]`

**LLM 프롬프트**:
```
# 공급망 DB 검색 전략 수립

## 뉴스 내용
중국의 희토류 수출 규제 강화

## 추출된 태그
[
  {"tag_id": "RAW_SEMICONDUCTOR_METAL", "target_region": "KR", "confidence": 0.95},
  {"tag_id": "CHINA", "target_region": "KR", "confidence": 1.0}
]

## 관련 테이블 스키마
### RAW_MATERIAL_MASTER (소재 마스터)
- 설명: 소재/원자재 정보를 관리하는 테이블
- 주요 컬럼:
  * name_kor (TEXT): 소재 한글 명칭, LIKE 검색 권장
  * name_eng (TEXT): 소재 영문 명칭
  * raw_material_type (TEXT): 소재 유형 분류

### SITE_MASTER (생산지 마스터)
- 설명: 생산 거점 정보
- 주요 컬럼:
  * country (TEXT): 국가명, = 또는 IN 연산자 사용
  * region (TEXT): 지역명

## 권장 검색 전략
### 전략: 원자재-지역 영향 추적
- 적용 조건: RAW_MATERIAL + SITE 태그 조합
- SQL 템플릿:
  ```sql
  SELECT sup.name_kor, m.name_kor, s.country
  FROM RAW_MATERIAL_MASTER sub
  JOIN MATERIAL_RAW_MATERIAL_MAP msm ...
  WHERE sub.name_kor LIKE '%{{keyword}}%'
    AND s.country = '{{country}}'
  ```

## 도메인 지식
### 규칙: 희토류 중국 의존도

**배경 지식**:
- 희토류는 전세계 생산량의 약 80%가 중국에서 생산
- 리스크 레벨: 매우 높음 (의존도 80%)

**영향 범위**:
- 중국 공급 차질 → 글로벌 반도체 공급망 전체 영향
- 대체 공급원: 미국 (5%), 호주 (10%) - 규모 부족

**검색 대상**:
  1) RAW_MATERIAL_MASTER에서 희토류 소재 조회
  2) MATERIAL_RAW_MATERIAL_MAP으로 희토류 포함 자재 조회
  3) 그 자재를 사용하는 협력사 조회 (전세계, 필터 없음)
  4) 중국 소재 Site 조회 (영향 범위 확인용, country = 'China')

## 엔티티 계층 관계
- ArF 포토레지스트 → 폴리머 (CONTAINS, 40%)
- ArF 포토레지스트 → PGMEA (CONTAINS, 30%)
- 한화정밀화학 → 청주공장 (HAS_SITE)

## 요청사항
위 정보를 바탕으로 SQLite 쿼리를 생성하세요.
```

**LLM 생성 SQL**:
```sql
SELECT 
    sup.name_kor as 협력사,
    m.name_kor as 영향받는_자재,
    s.country as 생산지_국가,
    s.name as 생산지명,
    smm.supply_ratio as 공급비중
FROM RAW_MATERIAL_MASTER sub
JOIN MATERIAL_RAW_MATERIAL_MAP msm ON sub.substance_code = msm.substance_code
JOIN MATERIAL_MASTER m ON msm.material_code = m.material_code
JOIN SITE_MATERIAL_MAP smm ON m.material_code = smm.material_code
JOIN SITE_MASTER s ON smm.site_code = s.site_code
JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
WHERE (sub.name_kor LIKE '%희토류%' OR sub.name_eng LIKE '%Rare Earth%')
  AND s.country = 'China'
  AND sub.is_active = 1
ORDER BY smm.supply_ratio DESC;
```

---

## 6. 임베딩 활용 (보조 역할)

온톨로지는 Text-to-SQL 생성을 돕고, 임베딩은 다음 2가지 보조 역할:

### 6.1 SQL 결과 랭킹

```
SQL 실행 결과: 35개 중국 소재 생산지

문제: 어떤 생산지가 뉴스와 가장 관련 있는가?

[랭킹]
뉴스 임베딩: embed("중국 쓰촨성 지진")

각 Site 설명 임베딩:
  Site A: "청두(쓰촨성) 소재, MLCC 생산" → 유사도 0.92 ⭐
  Site B: "상하이 소재, 포토레지스트" → 유사도 0.61
  Site C: "베이징 소재, 웨이퍼" → 유사도 0.58

→ Site A를 최우선 리스크로 판단
```

### 6.2 SQL 품질 검증

```
LLM이 생성한 SQL:
  SELECT * FROM RAW_MATERIAL_MASTER WHERE name_kor LIKE '%ASML%'

[검증]
뉴스 임베딩 vs 테이블 description 임베딩:
  - RAW_MATERIAL_MASTER: 유사도 0.32 ❌
  - SUPPLIER_MASTER: 유사도 0.89 ✅

→ 잘못된 테이블 → LLM에게 재생성 요청
```

---

## 7. OpenSearch 적용 권장

### 7.1 필수 적용

**TAG_KEYWORD_MAP (뉴스 인텔리전스 DB)**
- 목적: 2,620개 키워드 역인덱스
- 효과: 태그 정확 매칭 성능 10~50배 향상

### 7.2 선택 적용 (Phase 2)

**SUPPLIER_MASTER, MATERIAL_MASTER (공급망 DB)**
- 목적: name_kor/name_eng 텍스트 검색 최적화
- 적용 시점: 데이터 1,000개 이상 또는 검색 속도 불만족 시

---

## 8. 구현 순서

### Phase 1: 온톨로지 기반 구축

1. ✅ 온톨로지 DB 스키마 생성 (`create_ontology_layer.py`)
2. ✅ 메타데이터 자동 생성 (`populate_metadata.py`)
   - Step 1-5: 테이블/컬럼/관계 메타데이터
   - Step 6: TAG_SEARCH_STRATEGY_MAP 자동 생성 (신규)
3. ✅ 검색 전략 템플릿 작성 (`populate_strategies.py`)
4. ✅ 도메인 규칙 초기 작성 (`populate_domain_rules.py`)
5. ✅ LLM 프롬프트 빌더 구현 (`ontology_prompt_builder.py`)

### Phase 2: 성능 최적화

6. ⏳ TAG_KEYWORD_MAP → OpenSearch 마이그레이션
7. ⏳ 임베딩 기반 결과 랭킹 구현
8. ⏳ 공급망 DB → OpenSearch 확장 (선택)

### Phase 3: 지속 개선

9. ⏳ 쿼리 패턴 학습 시스템 구축
10. ⏳ 도메인 전문가 검토 및 규칙 보강

---

## 9. 파일 구조

```
poc-a/
├── data/
│   ├── SUPPLY_CHAIN/
│   │   └── supply_chain.db              # 기존 공급망 DB (변경 없음)
│   └── ONTOLOGY/
│       └── ontology_layer.db            # 온톨로지 레이어 (신규)
├── models/
│   ├── supply_chain_db.py               # 기존 모델
│   └── ontology_db.py                   # 온톨로지 모델 (신규)
├── scripts/
│   ├── create_ontology_layer.py         # 온톨로지 DB 생성
│   ├── populate_metadata.py             # 메타데이터 자동 생성
│   ├── populate_strategies.py           # 검색 전략 작성
│   ├── populate_domain_rules.py         # 도메인 규칙 작성
│   └── ontology_prompt_builder.py       # LLM 프롬프트 빌더
└── Markdown/
    ├── DB_SUPPLY MAP_Ontology_Docs.md   # 본 문서
    └── DB_SUPPLY MAP_Docs.md            # 공급망 DB 설계 문서
```

---

## 10. 예상 효과

### 10.1 Text-to-SQL 품질 향상

**Before (온톨로지 없음)**:
- SQL 생성 성공률: ~60%
- 잘못된 테이블 선택: 20%
- 잘못된 JOIN 경로: 15%
- 도메인 지식 누락: 25%

**After (온톨로지 적용)**:
- SQL 생성 성공률: ~90%
- 테이블 메타데이터로 올바른 테이블 선택
- 관계 정보로 정확한 JOIN 경로
- 도메인 규칙으로 전문 지식 반영

### 10.2 개발 효율 향상

- LLM 프롬프트 자동 생성 (수동 작성 불필요)
- 신규 테이블 추가 시 메타데이터만 업데이트
- 도메인 전문가가 SQL 몰라도 규칙 작성 가능

### 10.3 유지보수 편의성

- DB 구조 변경 시 온톨로지만 업데이트
- 검색 전략 템플릿 재사용
- 도메인 규칙 버전 관리

---

## 11. 제약사항 및 고려사항

### 11.1 초기 작업 부담

- 메타데이터 작성: 7개 테이블 × 평균 10개 컬럼 = 70개 컬럼 설명
- 검색 전략: 초기 5~10개 템플릿 작성
- 도메인 규칙: 초기 5~10개 규칙 작성

**해결책**: 자동 생성 스크립트 + 점진적 보강

### 11.2 도메인 지식 검증

- 초기 규칙은 임시 작성 (예: GPT-4 기반)
- 도메인 전문가 검토 필요
- 검증 전까지는 `is_active = 0` 또는 낮은 `priority` 설정

### 11.3 LLM 프롬프트 길이

- 온톨로지 정보를 모두 주입하면 프롬프트 길이 증가
- 태그 기반 필터링으로 관련 정보만 선택적 제공
- 우선순위 기반 정보 정렬

---

## 12. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-06-26 | 초기 설계 문서 작성<br>- 7개 테이블/뷰 정의<br>- 메타데이터 레이어, 검색 전략, 도메인 규칙<br>- LLM 프롬프트 통합 방안<br>- 임베딩 및 OpenSearch 역할 정의 |
| 1.1 | 2026-06-26 | 도메인 지식 규칙 역할 재정의 (1차)<br>- llm_instruction → background_knowledge + search_consideration 분리<br>- 강제 로직 → 참고 정보로 변경<br>- 3.6.1절 추가: 도메인 규칙의 역할 및 케이스별 예시<br>- LLM 프롬프트에 "참고용" 명시 추가 |
| 1.2 | 2026-06-26 | 도메인 지식 규칙 역할 재정의 (2차 - 최종)<br>- 역할: 리스크 중요도 평가, 영향 범위 판단, 검색 대상 정의<br>- 비역할: 검색 범위 제한, WHERE 조건 강제 (명확히 금지)<br>- 컬럼 구조 변경: background_knowledge + impact_assessment + search_targets + alternative_sources<br>- 검색 대상 명확화: 자재/협력사는 전세계 조회, Site는 영향 확인용 별도 조회<br>- 예시 추가: 네온가스 우크라이나, 희토류 중국 사례 |
| 1.3 | 2026-07-14 | TAG_SEARCH_STRATEGY_MAP 자동 생성 추가<br>- 4.2절 개정: 태그 매핑을 수동 → 반자동으로 변경<br>- 패턴 기반 자동 매핑 규칙 추가 (RAW_*, MAT_*, SUP_*, SITE_*, EVT_*)<br>- Fallback 전략 사용 최소화 (59.1% → 0% 목표)<br>- 누락된 13개 태그 자동 처리 방안 명시 |

---

**작성자**: Claude Code (Sonnet 4.5)  
**최종 수정**: 2026-06-26  
**승인**: 사용자 승인 완료 (메타데이터 레이어, 검색 전략, 도메인 규칙, 계층 명시화)
