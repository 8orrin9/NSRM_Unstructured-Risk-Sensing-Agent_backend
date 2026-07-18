# Agent_3_DB_Searcher 모듈 개요

## 1. 개요

### 목적
Agent_2_Tag_Mapper에서 생성한 매핑된 태그를 기반으로 Risk 시나리오를 생성하고, 공급망 DB를 검색할 수 있는 SQL 쿼리를 생성합니다.

### 핵심 역할
- **Risk 시나리오 생성**: LLM을 활용하여 뉴스와 태그를 자연어 Risk 시나리오로 변환
- **온톨로지 레이어 조회**: 도메인 규칙과 검색 전략을 자동 매칭
- **Text-to-SQL 생성**: 전체 컨텍스트를 종합하여 LLM이 최적의 SQL 쿼리 생성

---

## 2. 워크플로우

### 2.1 프로세스
```
[Agent_2 출력]
    ↓
validate_input (입력 검증)
    ↓
generate_risk_scenario (Risk 시나리오 생성 + 온톨로지 조회)
    ↓
generate_sql (SQL 생성 + 검증 + 재시도)
    ↓
search_db (DB 검색 실행)
    ↓
END (검색 결과 출력)
```

### 2.2 각 단계별 상세

#### 1) validate_input
- Agent_2 출력 검증 (mapped_tags 유무)
- 빈 태그 배열 체크
- 검증 실패 시 error 필드 설정

#### 2) generate_risk_scenario
**3가지 하위 작업을 순차 수행**:

1. **LLM Risk 시나리오 생성**:
   - 입력: 뉴스 제목, 요약, 매핑된 태그
   - LLM 모델: gpt-4o-mini
   - 출력: 
     - `risk_scenario`: 자연어 시나리오 (예: "SK하이닉스 생산지에서 화재사고가 발생하여 특수가스 공급에 차질이 예상됨")
     - `risk_scenario_entities`: 추출된 엔티티 목록 (예: ["SK하이닉스", "화재사고", "특수가스"])
     - `risk_scenario_confidence`: 신뢰도 (0.0-1.0)
     - `impact_level`: "HIGH" | "MEDIUM" | "LOW"
   - Fallback: LLM 실패 시 태그 기반 간단한 시나리오 생성

2. **온톨로지 레이어 조회**:
   - DB: `ontology_layer.db`의 `DOMAIN_KNOWLEDGE_RULES` 테이블
   - 매칭 전략:
     1. 완전 매칭 (모든 tag_id 포함)
     2. 부분 매칭 (일부 tag_id 포함)
     3. 타입 매칭 (tag_type 조합)
   - 출력:
     - `domain_rules`: 매칭된 도메인 규칙들
     - `search_target_entities`: 검색 대상 테이블 (예: ["SUPPLIER_MASTER", "SITE_MASTER"])
     - `impact_scope`: 영향 범위 설명
   - Fallback: 태그 타입 기반 기본 검색 대상

3. **검색 전략 결정**:
   - DB: `ontology_layer.db`의 `TAG_SEARCH_STRATEGY_MAP`, `SEARCH_STRATEGY_TEMPLATE`
   - 매칭 전략:
     1. 태그별 전략 조회
     2. 우선순위 정렬 및 중복 제거
     3. 전략 템플릿 조회
   - 출력:
     - `search_strategy_id`: 전략 ID (있을 경우)
     - `search_strategy`: SQL 템플릿, 파라미터, 우선순위
     - `fallback_strategy_used`: fallback 전략 사용 여부
   - Fallback: 기본 FULL_CHAIN 쿼리

#### 3) generate_sql
**LLM 기반 Text-to-SQL 생성 - 모든 컨텍스트를 종합**:

**입력 컨텍스트** (LLM에 전달):
1. **뉴스 원문**: `title_ko`, `summary_ko`, `content_ko` (500자 제한)
2. **추출된 키워드**: Agent_1 출력
3. **매핑된 태그**: Agent_2 출력
4. **Risk 시나리오**: `risk_scenario`, `risk_scenario_entities`, `impact_level`
5. **온톨로지 조회 결과**: `domain_rules`, `search_target_entities`, `impact_scope`
6. **전략 템플릿** (참고용): `search_strategy["sql_template"]` - 힌트로만 활용, 정답 아님
7. **DB 스키마 메타데이터**: `DB_TABLE_METADATA`, `DB_COLUMN_METADATA`, `DB_TABLE_RELATIONSHIP`

**LLM 프롬프트 핵심 원칙**:
- 뉴스 원문의 맥락을 최우선으로 고려
- 주어진 테이블과 컬럼만 사용
- WHERE 절에 is_active = 1 필터 추가
- 결과는 최대 100건 제한 (LIMIT 100)
- 컬럼 별칭은 한글로 (예: name_kor AS 협력사명)
- **참고 템플릿은 힌트일 뿐, 정답이 아님** - 전체 컨텍스트를 고려하여 최적의 쿼리 생성

**출력**:
- `generated_sql`: 생성된 SQL 쿼리
- `sql_explanation`: SQL이 뉴스를 어떻게 반영했는지 2-3문장 설명

---

## 3. State 구조

```python
class DBSearchState(TypedDict):
    # ===== Agent_2 입력 (상속) =====
    news_id: str
    title_ko: str
    summary_ko: str
    content_ko: str
    keywords: List[Dict]                # [{"keyword": str, "score": float, "normalized": str}, ...]
    mapped_tags: List[Dict]             # [{"tag_id": str, "tag_name": str, "tag_type": str, "confidence": float, "source": str, "target_region": str}, ...]
    mapping_quality_score: float
    is_relevant: bool
    relevance_score: float
    original_language: str
    
    # ===== Risk 시나리오 생성 결과 =====
    risk_scenario: str                  # 자연어 시나리오 (LLM 생성)
    risk_scenario_entities: List[str]   # 추출된 엔티티 목록
    risk_scenario_confidence: float     # 시나리오 신뢰도 (0.0-1.0)
    impact_level: str                   # "HIGH" | "MEDIUM" | "LOW"
    
    # ===== 온톨로지 레이어 조회 결과 =====
    domain_rules: List[Dict]            # 매칭된 도메인 규칙들
    search_target_entities: List[str]   # 검색 대상 엔티티 타입
    impact_scope: str                   # 영향 범위
    
    # ===== 검색 전략 결정 결과 =====
    search_strategy_id: Optional[str]   # 전략 ID (있을 경우)
    search_strategy: Dict               # {"sql_template": str, "params": dict, "priority": int}
    fallback_strategy_used: bool        # fallback 전략 사용 여부
    
    # ===== SQL 생성 결과 =====
    generated_sql: Optional[str]        # 생성된 SQL 쿼리
    sql_explanation: str                # SQL이 뉴스를 어떻게 반영했는지 설명
    
    # ===== 에러 처리 =====
    error: Optional[str]
```

---

## 4. 설정 (config.py)

| 설정 | 값 | 설명 |
|------|----|----|
| `RISK_SCENARIO_MODEL` | gpt-4o-mini | Risk 시나리오 생성용 (빠르고 저렴) |
| `RISK_SCENARIO_TIMEOUT` | 30 | Risk 시나리오 생성 타임아웃 (초) |
| `OPENAI_MODEL` | gpt-4o-mini | SQL 생성용 |
| `ONTOLOGY_DB_PATH` | data/ONTOLOGY/ontology_layer.db | 온톨로지 DB 경로 |
| `SUPPLY_CHAIN_DB_PATH` | data/SUPPLY_CHAIN/supply_chain.db | 공급망 DB 경로 |
| `AGENT2_OUTPUT_FILE` | data/Dev_Data/news_tag_mapped.json | Agent_2 입력 파일 |
| `AGENT3_OUTPUT_FILE` | data/Dev_Data/news_db_search_results.json | Agent_3 출력 파일 |
| `MIN_CONFIDENCE_THRESHOLD` | 0.5 | Risk 시나리오 신뢰도 최소값 |
| `ENABLE_MULTI_SCENARIO` | True | 다중 시나리오 생성 활성화 |
| `MAX_SCENARIOS_PER_NEWS` | 4 | 뉴스당 최대 시나리오 수 |
| `MIN_TAGS_PER_CLUSTER` | 2 | 클러스터링 최소 태그 수 |
| `ENABLE_KG_PATH_ENRICHMENT` | True | KG 경로 기반 시나리오 강화 |

---

## 5. 재사용 컴포넌트

### 5.1 유틸리티 함수

1. **`utils/llm_risk_scenario.py`**
   - `generate_risk_scenario_llm(title_ko, summary_ko, mapped_tags)`: LLM 기반 Risk 시나리오 생성
   - OpenAI API 호출, JSON 응답 강제, 필수 필드 검증

2. **`utils/llm_sql_generator.py`**
   - `fetch_schema_metadata(db_path, target_entities)`: 온톨로지 DB에서 스키마 메타데이터 조회
   - `generate_sql_with_llm(...)`: LLM 기반 SQL 생성 (전체 컨텍스트 통합)

3. **`utils/ontology_query.py`**
   - `query_domain_rules(mapped_tags, db_path)`: 도메인 규칙 조회
   - `parse_search_targets(search_targets_str)`: 검색 대상 테이블 파싱
   - `get_default_entities_by_type(tag_types)`: 태그 타입 기반 기본 검색 대상

4. **`utils/strategy_utils.py`**
   - `determine_search_strategy(mapped_tags, ontology_result, db_path)`: 검색 전략 결정
   - `query_tag_strategies(cursor, tag_id, target_region)`: 태그별 전략 조회
   - `get_default_strategy(search_target_entities)`: 기본 전략 (fallback)

### 5.2 DB 구조

**온톨로지 DB** (`ontology_layer.db`):
- **DOMAIN_KNOWLEDGE_RULES**: 도메인 규칙 (applicable_tags, search_targets, impact_assessment, priority)
- **TAG_SEARCH_STRATEGY_MAP**: 태그-전략 매핑 (tag_id, strategy_id, priority)
- **SEARCH_STRATEGY_TEMPLATE**: 검색 전략 템플릿 (strategy_id, sql_template, strategy_description)
- **DB_TABLE_METADATA**: 테이블 메타데이터 (table_name, llm_description, primary_entity_type)
- **DB_COLUMN_METADATA**: 컬럼 메타데이터 (column_name, llm_description, is_searchable, search_hint, sample_values)
- **DB_TABLE_RELATIONSHIP**: 테이블 관계 (from_table, to_table, join_condition)

**공급망 DB** (`supply_chain.db`):
- **SUPPLIER_MASTER**: 협력사 마스터
- **SITE_MASTER**: 생산지 마스터
- **MATERIAL_MASTER**: 자재 마스터
- **RAW_MATERIAL_MASTER**: 원자재 마스터
- **SITE_MATERIAL_MAP**: 생산지-자재 매핑

---

## 6. 테스트 결과

### 6.1 전체 파이프라인 테스트 (12개 뉴스)
**실행 일자**: 2026-07-03  
**입력**: Agent_2 출력 (news_tag_mapped.json) - 21개 중 12개 태그 매핑 뉴스

**통계**:
- **총 처리**: 12개 뉴스
- **에러 발생**: 0개
- **평균 Risk 신뢰도**: 0.92
- **SQL 생성 성공률**: 100% (12/12개)
- **Fallback 전략 사용**: 3개 (25.0%)

**영향 수준 분포**:
- HIGH: 12개 (100%)

**전략 ID 분포**:
- STRAT_RAW_MATERIAL_SITE_IMPACT: 4개 (33.3%)
- None (Fallback): 3개 (25.0%)
- STRAT_SITE_COUNTRY_LIST: 3개 (25.0%)
- STRAT_MATERIAL_MULTI_SITE_RISK: 1개 (8.3%)
- STRAT_RAW_MATERIAL_REVERSE_TRACE: 1개 (8.3%)

### 6.2 샘플 결과

**예시 1: ASML EUV 장비 납품 지연**
- **제목**: "ASML, EUV 장비 납품 지연 발표...글로벌 반도체 생산 차질"
- **Risk 시나리오**: "ASML의 EUV 장비 납품 지연으로 인해 삼성전자, TSMC, 인텔의 반도체 생산에 차질이 예상됨"
- **신뢰도**: 0.90
- **영향 수준**: HIGH
- **전략**: Fallback (템플릿 없음)
- **생성된 SQL**: 
  ```sql
  SELECT sup.name_kor AS 협력사명, sup.country AS 국가, 
         'EUV 장비' AS 자재, '납품 지연' AS 이벤트
  FROM SUPPLIER_MASTER sup
  WHERE sup.name_kor IN ('삼성전자', 'TSMC', '인텔', 'ASML')
    AND sup.is_active = 1
  ORDER BY sup.name_kor
  LIMIT 100
  ```

**예시 2: 미국 반도체 장비 수출 규제**
- **제목**: "미국, 중국 반도체 장비 수출 규제 추가 강화"
- **Risk 시나리오**: "미국의 반도체 제조 장비 수출 규제로 인해 한국 및 일본의 반도체 소재·부품 업체들이 생산 라인 재편과 매출 감소를 겪을 것으로 예상됨"
- **신뢰도**: 0.90
- **영향 수준**: HIGH
- **전략**: STRAT_SITE_COUNTRY_LIST
- **생성된 SQL**: 
  ```sql
  SELECT s.name AS 생산지, s.country AS 국가, 
         sup.name_kor AS 협력사명, COUNT(DISTINCT s.site_code) AS 생산지수
  FROM SUPPLIER_MASTER sup
  JOIN SITE_MASTER s ON sup.supplier_code = s.supplier_code
  WHERE s.country IN ('한국', '일본')
    AND sup.is_active = 1
    AND s.is_active = 1
  GROUP BY s.country, sup.supplier_code
  ORDER BY s.country, sup.name_kor
  LIMIT 100
  ```

**예시 3: JSR 포토레지스트 공장 화재**
- **제목**: "일본 포토레지스트 공장 화재, 글로벌 반도체 업계 비상"
- **Risk 시나리오**: "일본 군마현 JSR 포토레지스트 공장에서 화재가 발생하여 ArF 및 EUV 포토레지스트 생산에 차질이 예상되며, 이는 삼성전자와 TSMC의 반도체 생산 라인에 영향을 미칠 수 있음"
- **신뢰도**: 0.95
- **영향 수준**: HIGH
- **전략**: STRAT_MATERIAL_MULTI_SITE_RISK
- **생성된 SQL**: 
  ```sql
  SELECT sup.name_kor AS 협력사명, m.name_kor AS 자재명,
         COUNT(DISTINCT s.site_code) AS 생산지수
  FROM SUPPLIER_MASTER sup
  JOIN SITE_MASTER s ON sup.supplier_code = s.supplier_code
  JOIN SITE_MATERIAL_MAP smm ON s.site_code = smm.site_code
  JOIN MATERIAL_MASTER m ON smm.material_code = m.material_code
  WHERE sup.name_kor IN ('삼성전자', 'TSMC', 'JSR', '신에쓰화학', 'TOK')
    AND m.name_kor LIKE '%포토레지스트%'
    AND sup.is_active = 1
    AND s.is_active = 1
  GROUP BY sup.supplier_code, m.material_code
  ORDER BY COUNT(DISTINCT s.site_code) DESC
  LIMIT 100
  ```

### 6.3 환경 변수 로딩 패턴 (병렬 처리 대응)

**문제**: ThreadPoolExecutor 병렬 처리 시 OpenAI API 인증 실패
- 증상: "Could not resolve authentication method", "Missing credentials"
- 원인: Worker thread에서 working directory 컨텍스트가 ambiguous

**해결 방법**: 각 유틸리티 모듈이 독립적으로 .env 로드
```python
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드 (명시적 경로 지정)
project_root = Path(__file__).parent.parent.parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# OpenAI 클라이언트 생성
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

**핵심**: 
- 스크립트 레벨에서 load_dotenv() 호출 금지
- 각 유틸리티 모듈이 `__file__` 기준 절대 경로로 .env 로드
- Agent_1, Agent_2와 동일한 패턴 적용

---

## 7. 파일 구조

```
dev/Agent_3_DB_Searcher/
├── __init__.py
├── config.py
├── graph.py
├── prompts.py
├── nodes/
│   ├── __init__.py (DBSearchState)
│   ├── validate_input.py
│   ├── generate_risk_scenario.py
│   └── generate_sql.py
├── utils/
│   ├── __init__.py
│   ├── llm_risk_scenario.py (LLM Risk 시나리오 생성)
│   ├── llm_sql_generator.py (LLM Text-to-SQL 생성)
│   ├── ontology_query.py (온톨로지 레이어 조회)
│   └── strategy_utils.py (검색 전략 결정)
└── scripts/
    └── run_full_pipeline.py (Agent_2 + Agent_3 통합)
```

---

## 8. 향후 확장 사항 (Phase 2)

### 8.1 SQL 실행 노드 추가
```python
# nodes/execute_sql.py
def execute_sql(state: DBSearchState) -> DBSearchState:
    """
    공급망 DB에서 SQL 실행
    
    처리:
    1. generated_sql 실행
    2. 결과를 state["search_results"]에 저장
    3. 에러 시 state["error"] 설정
    """
    pass
```

### 8.2 결과 통합 노드 추가
```python
# nodes/aggregate_results.py
def aggregate_results(state: DBSearchState) -> DBSearchState:
    """
    검색 결과 통합 및 최종 출력 생성
    
    처리:
    1. search_results 가공
    2. risk_scenario와 연결
    3. 영향 범위 요약
    """
    pass
```

### 8.3 조건부 분기 추가
```python
# graph.py
def should_execute_sql(state: DBSearchState) -> str:
    """SQL 실행 가능 여부 판단"""
    if state.get("error") or not state.get("generated_sql"):
        return "skip"
    return "execute"

workflow.add_conditional_edges(
    "generate_sql",
    should_execute_sql,
    {
        "execute": "execute_sql",
        "skip": END
    }
)
```

### 8.4 온톨로지 메타데이터 캐싱
- **현재**: 매번 DB 조회
- **Phase 2**: 스키마 메타데이터 캐싱으로 성능 개선

---

## 9. 성능 지표

| 지표 | 목표 | 실제 (12개 뉴스) |
|------|------|------------------|
| SQL 생성 성공률 | 95% | 100% (12/12개) |
| 평균 Risk 신뢰도 | >= 0.8 | 0.92 |
| Fallback 전략 비율 | <= 30% | 25.0% (3/12개) |
| 처리 속도 (병렬) | 3초/뉴스 (LLM 포함) | ~3초/뉴스 (5 workers) |
| 에러 발생률 | <= 5% | 0% (0/12개) |

**성과**:
- ✅ SQL 생성 성공률 100% 달성
- ✅ 평균 Risk 신뢰도 0.92 (목표 초과)
- ✅ Fallback 전략 비율 25% (목표 달성)
- ✅ 에러 발생률 0% (목표 초과)

---

## 10. 사용 예시

```python
from dev.Agent_3_DB_Searcher import create_db_searcher_graph, DBSearchState
import json

# 그래프 생성
graph = create_db_searcher_graph()

# Agent_2 출력 로드
with open("data/Dev_Data/news_tag_mapped.json") as f:
    agent2_output = json.load(f)

# 단일 뉴스 처리
article = agent2_output["results"][0]

# State 초기화 (Agent_2 출력 활용)
state = DBSearchState(
    news_id=article["news_id"],
    title_ko=article["title_ko"],
    summary_ko=article["summary_ko"],
    content_ko=article["content_ko"],
    keywords=article["keywords"],
    mapped_tags=article["mapped_tags"],
    mapping_quality_score=article["mapping_quality_score"],
    is_relevant=article["is_relevant"],
    relevance_score=article["relevance_score"],
    original_language=article["original_language"],
    # Agent_3 필드는 자동 초기화됨
)

# 그래프 실행
result = graph.invoke(state)

# 결과 활용
print(f"Risk 시나리오: {result['risk_scenario']}")
print(f"영향 수준: {result['impact_level']}")
print(f"신뢰도: {result['risk_scenario_confidence']}")
print(f"\n생성된 SQL:\n{result['generated_sql']}")
print(f"\nSQL 설명:\n{result['sql_explanation']}")
```

---

## 11. 참조

### 관련 문서
- [태그 매핑 개요](./Module_Tag_Mapper_Overview.md)
- [뉴스 분석기 개요](./Module_News_Collector_Overview.md)
- [공급망 DB 온톨로지](../DB/DB_SUPPLY%20MAP_Ontology_Docs.md)

### 스크립트
- **통합 파이프라인**: `dev/Agent_3_DB_Searcher/scripts/run_full_pipeline.py`

---

## 12. 변경 이력

### v1.0 (2026-07-03)
- ✅ **LangGraph 통합**: validate → generate_risk_scenario → generate_sql
- ✅ **Risk 시나리오 생성**: LLM 기반 (gpt-4o-mini)
- ✅ **온톨로지 레이어 조회**: 도메인 규칙, 검색 전략 매칭
- ✅ **Text-to-SQL 생성**: LLM 기반 (전체 컨텍스트 통합)
- ✅ **병렬 처리 지원**: ThreadPoolExecutor (5 workers)
- ✅ **환경 변수 로딩 패턴**: 각 유틸리티 모듈 독립 로딩
- ✅ **Fallback 전략**: LLM/온톨로지/전략 실패 시 기본 전략 사용
- 📊 **전체 파이프라인 테스트**: 12개 뉴스, 100% 성공률

### v1.1 (2026-07-08)
- ✅ **SQL 검증 및 재시도**: 구문 검증 (max_retries=2), 에러 피드백 기반 재생성
- ✅ **Fallback SQL**: 검증 실패 시 안전한 대체 쿼리 자동 생성
- ✅ **다중 시나리오 생성**: 태그 클러스터링 → 2-4개 시나리오 생성
- ✅ **KG 경로 활용**: Insight KG 경로 기반 시나리오 강화
- ✅ **DB 검색 노드 추가**: SQL 실행 및 결과 조회 (search_db 노드)
- ✅ **다중 SQL 생성**: 시나리오별 독립 SQL 생성 및 실행
- 📊 **통합 파이프라인 테스트**: 13개 문서, SQL 검증 성공률 100%

**주요 개선사항**:
- SQL 생성 품질 향상 (구문 검증 + 재시도)
- 다중 시나리오로 Risk 분석 다양성 증가
- KG 경로 활용으로 엔티티 간 관계 강화
- DB 검색 결과를 Agent_4에 전달

---

**최종 수정일**: 2026-07-08  
**버전**: 1.1  
**구현 상태**: Phase 2 완료 (SQL 검증 + 다중 시나리오 + DB 검색)
