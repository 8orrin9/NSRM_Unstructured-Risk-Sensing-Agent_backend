# Agent_4_Risk_Evaluator 모듈 개요

**버전**: 1.0 (초기 구현 완료)  
**최종 업데이트**: 2026-07-04  
**작성자**: PoC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [워크플로우 구조](#2-워크플로우-구조)
3. [Risk 평가 로직](#3-risk-평가-로직)
4. [이벤트 시점 분류](#4-이벤트-시점-분류)
5. [이슈 타입 결정](#5-이슈-타입-결정)
6. [State 정의](#6-state-정의)
7. [파일 구조](#7-파일-구조)
8. [실행 방법](#8-실행-방법)
9. [설정 가이드](#9-설정-가이드)
10. [성능 지표](#10-성능-지표)
11. [LLM 프롬프트 전략](#11-llm-프롬프트-전략)
12. [Fallback 전략](#12-fallback-전략)

---

## 1. 개요

### 1.1 목적

**Agent_4_Risk_Evaluator**는 뉴스 이벤트가 삼성전자 DS 반도체 공급망에 실질적인 **Risk**를 발생시키는지 판단하고, 이벤트 시점을 분류하여 최종 **이슈 타입**을 결정하는 모듈입니다.

### 1.2 주요 기능

- ✅ **Risk 관련성 평가**: 뉴스와 DB 검색 결과 간 논리적 인과 관계 분석
- ✅ **이벤트 시점 분류**: 진행형(ONGOING) vs 예정형(SCHEDULED) 구분
- ✅ **이슈 타입 결정**: ISSUE / SMD / NONE 마킹
- ✅ **고성능 LLM 활용**: gpt-5.5 모델 (추론 특화)
- ✅ **병렬 처리**: ThreadPoolExecutor로 뉴스별 독립 처리

### 1.3 처리 결과

**입력**: `data/Dev_Data/news_db_search_results.json` (Agent_3 출력)  
**출력**: `data/Dev_Data/news_risk_evaluation_results.json` (Risk 평가 결과)

**이슈 타입 분류**:
- `ISSUE`: 진행형 + Risk → **즉시 대응 필요**
- `SMD`: 예정형 → **예정형 모니터링**
- `NONE`: 진행형 + Risk 없음 → 무관

---

## 2. 워크플로우 구조

### 2.1 LangGraph 파이프라인 (조건부 분기 지원)

```
┌──────────────────────────────┐
│  입력: Agent_3 DB 검색 결과   │
│  - risk_scenarios (다중)     │
│  - generated_sqls (다중)     │
│  - search_results_multi      │
│  - mapped_tags               │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ [1] validate_input           │
│  입력 검증                    │
│  - risk_scenarios 존재 확인   │
│  - mapped_tags 최소 1개       │
└──────────────┬───────────────┘
               │
               ▼ [조건부 분기]
       ┌───────┴───────┐
       │               │
   [단일 시나리오]   [다중 시나리오]
       │               │
       ▼               ▼
┌──────────────┐  ┌──────────────────────┐
│ [2a]         │  │ [2b]                 │
│ evaluate_    │  │ evaluate_multi_      │
│ risk_        │  │ scenarios            │
│ relevance    │  │  각 시나리오 독립 평가│
└──────┬───────┘  └──────┬───────────────┘
       │                 │
       │                 ▼
       │          ┌──────────────────┐
       │          │ [2c]             │
       │          │ aggregate_risk_  │
       │          │ decision         │
       │          │  통합 판정        │
       │          └──────┬───────────┘
       │                 │
       └────────┬────────┘
                │
                ▼
┌──────────────────────────────┐
│ [3] classify_event_timing    │
│  이벤트 시점 분류 (LLM)       │
│  - event_timing              │
│    (ONGOING | SCHEDULED)     │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ [4] determine_issue_type     │
│  이슈 타입 결정 (조건부 로직) │
│  - issue_type                │
│    (ISSUE | SMD | NONE)      │
└──────────────┬───────────────┘
               │
               ▼
            [END]
```

### 2.2 파이프라인 특징

**조건부 분기 지원** (v1.1):
- **단일 시나리오**: 기존 단일 Risk 평가 경로
- **다중 시나리오**: 2-4개 시나리오 각각 독립 평가 → 통합 판정
- 시나리오 개수에 따라 자동 분기 (`route_by_scenario_count`)

**다중 시나리오 평가 로직**:
1. 각 시나리오별 독립 Risk 평가 (LLM)
2. 통합 판정 규칙:
   - **하나라도 Risk=True → 최종 Risk=True**
   - **risk_score = 개별 risk_score 최댓값**
   - 주도 시나리오 자동 선정

**에러 전파 메커니즘**:
```python
# 각 노드 시작 시 에러 체크
if state.get("error"):
    return state  # 이전 노드 에러 → 현재 노드 건너뛰기
```

---

## 3. Risk 평가 로직

### 3.1 평가 기준

**핵심 질문**: 뉴스 이벤트가 삼성전자 DS 반도체 공급망에 **실질적인 Risk**를 발생시키는가?

**판단 기준**:
1. **논리적 인과 관계**: 뉴스 이벤트 → DB 엔티티 → 삼성전자 공급망 영향
2. **도메인 지식 활용**: 반도체 공급망 특성, 의존도, 집중도
3. **구체적 근거**: "~할 수 있음" 금지, 구체적 Risk 요인 명시

**제외 사항**:
- 추상적/일반적 Risk (구체적 연결 부재)
- 뉴스-DB 검색 결과 간 관계 없음
- 단순 뉴스 보도 (실질적 영향 없음)

### 3.2 컨텍스트 제공

**LLM에게 제공하는 정보**:

```python
context = {
    "news": {
        "title": state["title_ko"],
        "summary": state["summary_ko"],
        "content": state["content_ko"][:500]  # 500자 제한
    },
    "keywords": [kw["keyword"] for kw in state["keywords"]],
    "tags": [tag["tag_name"] for tag in state["mapped_tags"]],
    "risk_scenario": state["risk_scenario"],
    "db_search": {
        "sql": state.get("generated_sql"),
        "explanation": state.get("sql_explanation", ""),
        "target_entities": state.get("search_target_entities", [])
    },
    "domain_rules": state.get("domain_rules", [])
}
```

**각 정보의 역할**:
- **뉴스 원문**: 이벤트 내용 파악
- **키워드/태그**: Agent_1, Agent_2의 분석 결과 활용
- **Risk 시나리오**: Agent_3가 생성한 Risk 가설
- **DB 검색 결과**: 공급망 엔티티와의 연결 관계
- **도메인 규칙**: 온톨로지 기반 도메인 지식

### 3.3 평가 결과 구조

```python
{
    "is_risk": bool,                  # Risk 여부 (True/False)
    "risk_score": float,              # Risk 점수 (0.0-1.0)
    "risk_justification": str,        # 판정 근거 (2-3문장, 구체적)
    "risk_factors": List[str]         # 식별된 Risk 요인들
}
```

**예시**:
```json
{
    "is_risk": true,
    "risk_score": 0.85,
    "risk_justification": "중국이 희토류 70% 생산하며, 미국 생산지에서 희토류를 사용하므로 공급 차질 예상됨",
    "risk_factors": ["공급 집중도 (중국 70%)", "지정학적 리스크", "소재 단일 공급"]
}
```

---

## 4. 이벤트 시점 분류

### 4.1 분류 기준

**ONGOING (진행형)**:
- 이미 발생, 현재 진행 중, 완료됨
- 키워드: "발생", "시행", "중단됨", "완료", "발표됨" (과거형/현재형)
- 예시: "화재가 발생하여 공장 가동 중단됨"

**SCHEDULED (예정형)**:
- 예정, 예상, 계획, 가능성
- 키워드: "예정", "계획", "할 것으로 예상", "가능성", "~될 전망"
- 예시: "내년 규제 시행 예정"

### 4.2 판단 원칙

1. **뉴스 제목과 본문의 시제(時制) 우선 고려**
2. **과거형/현재형** → ONGOING
3. **미래형/추측** → SCHEDULED

### 4.3 분류 결과 구조

```python
{
    "event_timing": str,                     # "ONGOING" | "SCHEDULED"
    "event_timing_confidence": float,        # 0.0-1.0
    "event_timing_justification": str        # 판정 근거 (2-3문장)
}
```

**예시**:
```json
{
    "event_timing": "ONGOING",
    "event_timing_confidence": 0.92,
    "event_timing_justification": "뉴스 제목과 본문에서 '발생했다', '중단됨'과 같은 과거형 표현이 사용되어 이미 발생한 사건임"
}
```

---

## 5. 이슈 타입 결정

### 5.1 조건부 로직 (LLM 호출 없음)

**분류 규칙**:

```python
if is_risk == True and event_timing == "ONGOING":
    issue_type = "ISSUE"
    issue_priority = impact_level  # "HIGH" | "MEDIUM" | "LOW"

elif event_timing == "SCHEDULED":
    issue_type = "SMD"  # Scheduled Monitoring Data
    issue_priority = impact_level if is_risk else "LOW"

else:  # is_risk == False and event_timing == "ONGOING"
    issue_type = "NONE"
    issue_priority = "NONE"
```

### 5.2 이슈 타입 의미

| 이슈 타입 | 조건 | 의미 | 대응 방식 |
|-----------|------|------|----------|
| **ISSUE** | Risk=True + ONGOING | 현재 발생 중인 Risk | **즉시 대응 필요** |
| **SMD** | SCHEDULED (Risk 무관) | 미래 예정 이벤트 | **예정형 모니터링** |
| **NONE** | Risk=False + ONGOING | Risk 없는 진행형 | 무관 (추가 조치 불필요) |

### 5.3 우선순위 (issue_priority)

**ISSUE 타입**:
- Agent_3의 `impact_level` 상속 (HIGH / MEDIUM / LOW)

**SMD 타입**:
- Risk=True → `impact_level` 상속
- Risk=False → "LOW" (낮은 우선순위 모니터링)

**NONE 타입**:
- "NONE" (우선순위 없음)

---

## 6. State 정의

**파일**: `dev/Agent_4_Risk_Evaluator/nodes/__init__.py`

```python
from typing import TypedDict, List, Dict, Optional

class RiskEvaluationState(TypedDict):
    """
    Risk 평가 상태 (Agent_4)
    
    Agent_3 결과를 상속받아 Risk 판정 및 이벤트 시점 분류 추가
    """
    # ===== Agent_3 입력 (상속) =====
    news_id: str
    title_ko: str
    summary_ko: str
    content_ko: str
    keywords: List[Dict]                   # [{"keyword": str, "score": float}, ...]
    mapped_tags: List[Dict]                # [{"tag_id": str, "tag_name": str, ...}, ...]
    
    # Agent_3 Risk 시나리오
    risk_scenario: str                     # LLM 생성 시나리오
    risk_scenario_entities: List[str]      # 추출 엔티티
    risk_scenario_confidence: float        # 시나리오 신뢰도
    impact_level: str                      # "HIGH" | "MEDIUM" | "LOW"
    
    # Agent_3 DB 검색 결과
    generated_sql: Optional[str]           # 생성된 SQL
    sql_explanation: str                   # SQL 설명
    search_target_entities: List[str]      # 검색 대상 엔티티
    domain_rules: List[Dict]               # 도메인 규칙
    
    # ===== Agent_3 다중 시나리오 입력 (v1.1) =====
    risk_scenarios: List[Dict]             # Agent_3 다중 시나리오
    generated_sqls: List[Dict]             # Agent_3 다중 SQL
    search_results_multi: List[Dict]       # Agent_3 다중 검색 결과
    
    original_language: str                 # 원본 언어
    is_relevant: bool                      # Agent_1 필터링 결과
    relevance_score: float                 # 관련성 점수
    mapping_quality_score: float           # Agent_2 매핑 품질
    
    # ===== Agent_4 Risk 평가 결과 =====
    is_risk: bool                          # Risk 여부 (True/False)
    risk_score: float                      # Risk 점수 (0.0-1.0)
    risk_justification: str                # Risk 판정 근거 (LLM 생성)
    risk_factors: List[str]                # 식별된 Risk 요인들
    
    # ===== Agent_4 다중 시나리오 평가 (v1.1) =====
    scenario_evaluations: List[Dict]       # 시나리오별 Risk 평가 결과
    final_risk_decision: Dict              # 통합 판정 결과
    
    # ===== Agent_4 이벤트 시점 분류 =====
    event_timing: str                      # "ONGOING" | "SCHEDULED"
    event_timing_confidence: float         # 시점 분류 신뢰도 (0.0-1.0)
    event_timing_justification: str        # 시점 판정 근거 (LLM 생성)
    
    # ===== Agent_4 최종 이슈 타입 =====
    issue_type: str                        # "ISSUE" | "SMD" | "NONE"
    issue_priority: str                    # "HIGH" | "MEDIUM" | "LOW" | "NONE"
    
    # ===== 그룹 추적 정보 (v1.1) =====
    original_news_ids: List[str]           # 원본 뉴스 ID 목록 (그룹인 경우)
    is_grouped: bool                       # 그룹 문서 여부
    
    # ===== 에러 처리 =====
    error: Optional[str]                   # 에러 메시지
```

**필드 계층 구조**:

```
[Agent_1 필드]
  ├─ news_id, title_ko, summary_ko, content_ko
  ├─ keywords
  ├─ is_relevant, relevance_score
  └─ original_language

[Agent_2 필드]
  ├─ mapped_tags
  └─ mapping_quality_score

[Agent_3 필드]
  ├─ risk_scenario, risk_scenario_entities, risk_scenario_confidence
  ├─ impact_level
  ├─ generated_sql, sql_explanation
  └─ search_target_entities, domain_rules

[Agent_4 필드] ← 이 모듈에서 추가
  ├─ is_risk, risk_score, risk_justification, risk_factors
  ├─ event_timing, event_timing_confidence, event_timing_justification
  └─ issue_type, issue_priority
```

---

## 7. 파일 구조

```
poc-a/dev/Agent_4_Risk_Evaluator/
│
├── __init__.py                           # 모듈 진입점
│   ├── create_risk_evaluator_graph()    # 그래프 생성 함수
│   └── RiskEvaluationState              # State 정의
│
├── graph.py                              # LangGraph 워크플로우 정의
│   └── create_risk_evaluator_graph()    # 그래프 생성 함수
│
├── config.py                             # 설정 파일
│   ├── RISK_EVALUATION_MODEL            # Risk 평가 모델 (gpt-5.5)
│   ├── EVENT_CLASSIFICATION_MODEL       # 이벤트 분류 모델 (gpt-5.5)
│   ├── RISK_EVALUATION_TIMEOUT          # Risk 평가 타임아웃 (60초)
│   ├── EVENT_CLASSIFICATION_TIMEOUT     # 이벤트 분류 타임아웃 (30초)
│   ├── AGENT3_OUTPUT_FILE               # Agent_3 출력 경로
│   └── AGENT4_OUTPUT_FILE               # Agent_4 출력 경로
│
├── prompts.py                            # LLM 프롬프트 중앙 관리
│   ├── RISK_EVALUATION_SYSTEM_PROMPT    # Risk 평가 시스템 프롬프트
│   ├── RISK_EVALUATION_USER_PROMPT      # Risk 평가 유저 프롬프트
│   ├── EVENT_CLASSIFICATION_SYSTEM_PROMPT  # 이벤트 분류 시스템 프롬프트
│   └── EVENT_CLASSIFICATION_USER_PROMPT    # 이벤트 분류 유저 프롬프트
│
├── nodes/                                # 워크플로우 노드
│   ├── __init__.py                       # RiskEvaluationState 정의
│   ├── validate_input.py                 # [노드 1] 입력 검증
│   ├── evaluate_risk_relevance.py        # [노드 2a] Risk 평가 (LLM, 단일)
│   ├── evaluate_multi_scenarios.py       # [노드 2b] 다중 시나리오 평가 (v1.1)
│   ├── aggregate_risk_decision.py        # [노드 2c] 통합 판정 (v1.1)
│   ├── classify_event_timing.py          # [노드 3] 이벤트 시점 분류 (LLM)
│   └── determine_issue_type.py           # [노드 4] 이슈 타입 결정 (로직)
│
├── utils/                                # LLM 호출 유틸리티
│   ├── __init__.py                       # 유틸 모듈 설명
│   ├── llm_risk_evaluator.py             # Risk 평가 LLM 호출
│   └── llm_event_classifier.py           # 이벤트 시점 분류 LLM 호출
│
├── scripts/                              # 실행 스크립트
│   └── run_full_pipeline.py              # 전체 파이프라인 (병렬)
│
└── tests/                                # 테스트
    └── test_risk_evaluation.py           # 단위 테스트
```

**핵심 파일 설명**:

### 7.1 graph.py
- LangGraph 순차 파이프라인 정의
- 4개 노드 연결 (validate → evaluate → classify → determine)
- 조건부 분기 없음 (에러 전파 메커니즘)

### 7.2 nodes/
- **validate_input**: Agent_3 출력 검증
- **evaluate_risk_relevance**: LLM 기반 Risk 평가 (단일 시나리오)
- **evaluate_multi_scenarios** (v1.1): 다중 시나리오 독립 평가
- **aggregate_risk_decision** (v1.1): 시나리오별 결과 통합 판정
- **classify_event_timing**: LLM 기반 이벤트 시점 분류
- **determine_issue_type**: 조건부 로직으로 issue_type 결정

### 7.3 utils/
- **llm_risk_evaluator.py**: Risk 평가 LLM 호출
  - 모델: gpt-5.5
  - JSON 응답 강제 (`response_format={"type": "json_object"}`)
- **llm_event_classifier.py**: 이벤트 시점 분류 LLM 호출
  - 모델: gpt-5.5
  - JSON 응답 강제

### 7.4 scripts/run_full_pipeline.py
- Agent_3 출력 로드 (`news_db_search_results.json`)
- 병렬 처리 (ThreadPoolExecutor, max_workers=5)
- 결과 저장 (`news_risk_evaluation_results.json`)
- 통계 출력 (ISSUE/SMD/NONE 분포)

---

## 8. 실행 방법

### 8.1 전체 파이프라인 실행 (병렬)

```bash
cd C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a
python dev/Agent_4_Risk_Evaluator/scripts/run_full_pipeline.py
```

**전제 조건**:
- Agent_3 실행 완료 (`news_db_search_results.json` 존재)
- `.env` 파일에 `OPENAI_API_KEY` 설정

**처리 과정**:
1. Agent_3 출력 로드 (`news_db_search_results.json`)
2. LangGraph 워크플로우 생성
3. 병렬 처리 실행 (max_workers=5)
4. 결과를 `news_risk_evaluation_results.json`에 저장
5. 통계 출력 (ISSUE/SMD/NONE 분포)

**출력 예시**:
```
================================================================================
Agent_4_Risk_Evaluator 실행
================================================================================

[1/4] Agent_3 출력 로드: ...
  ✓ 총 12개 뉴스

[2/4] Agent_4 그래프 생성
  ✓ 워크플로우: validate → risk_evaluate → event_classify → issue_determine

[3/4] Risk 평가 실행 (총 12개, 병렬 처리)
  🔴 [1/12] ISSUE  | Risk: 0.85 | Timing: ONGOING
  🟡 [2/12] SMD    | Risk: 0.70 | Timing: SCHEDULED
  ⚪ [3/12] NONE   | Risk: 0.30 | Timing: ONGOING
  ...

[4/4] 결과 저장
  ✓ 저장 완료: ...

================================================================================
실행 결과 요약
================================================================================
  총 처리: 12개
  평균 Risk 점수: 0.65
  평균 시점 신뢰도: 0.88

  이슈 타입 분포:
    🔴 ISSUE: 5개 (41.7%)
    🟡 SMD: 4개 (33.3%)
    ⚪ NONE: 3개 (25.0%)

  Risk 분포:
    Risk=True: 9개 (75.0%)
    Risk=False: 3개 (25.0%)

  이벤트 시점 분포:
    ONGOING: 8개 (66.7%)
    SCHEDULED: 4개 (33.3%)
================================================================================
```

### 8.2 출력 JSON 구조

**파일**: `data/Dev_Data/news_risk_evaluation_results.json`

```json
{
  "extraction_date": "2026-07-04T10:00:00",
  "agent3_input_file": "news_db_search_results.json",
  "total_articles": 12,
  
  "statistics": {
    "issue_count": 5,
    "smd_count": 4,
    "none_count": 3,
    
    "risk_distribution": {
      "is_risk_true": 9,
      "is_risk_false": 3
    },
    
    "event_timing_distribution": {
      "ONGOING": 8,
      "SCHEDULED": 4
    },
    
    "average_risk_score": 0.65,
    "average_event_timing_confidence": 0.88
  },
  
  "results": [
    {
      // Agent_3 필드 (모두 상속)
      "news_id": "NEWS_001",
      "title_ko": "중국 희토류 수출 규제 강화",
      "risk_scenario": "중국의 희토류 수출 규제로 미국 생산지에 공급 차질 예상",
      "generated_sql": "SELECT * FROM supplier WHERE material_type='희토류'",
      
      // Agent_4 추가 필드
      "is_risk": true,
      "risk_score": 0.85,
      "risk_justification": "중국이 희토류 70% 생산, 미국 생산지에 공급 차질 예상",
      "risk_factors": ["공급 집중도", "지정학적 리스크"],
      
      "event_timing": "ONGOING",
      "event_timing_confidence": 0.90,
      "event_timing_justification": "규제가 이미 시행되었음 (과거형)",
      
      "issue_type": "ISSUE",
      "issue_priority": "HIGH",
      
      "error": null
    }
  ],
  
  "errors": []
}
```

---

## 9. 설정 가이드

**파일**: `dev/Agent_4_Risk_Evaluator/config.py`

### 9.1 LLM 모델 설정

```python
# ===== LLM 모델 설정 =====
RISK_EVALUATION_MODEL = "gpt-5.5"       # Risk 평가용 (추론 특화)
EVENT_CLASSIFICATION_MODEL = "gpt-5.5"  # 이벤트 분류용 (추론 특화)
```

**권장 모델**:
- **gpt-5.5**: 추론 특화 모델 (논리적 관계성 평가에 최적)
- 대안: gpt-4o (비용 절감 시)

**주의 사항**:
- gpt-5.5는 `temperature` 파라미터를 지원하지 않음 (기본값 1 고정)
- JSON 응답 강제 (`response_format={"type": "json_object"}`) 필수

### 9.2 타임아웃 설정

```python
# ===== 타임아웃 설정 =====
RISK_EVALUATION_TIMEOUT = 60               # Risk 평가 타임아웃 (초)
EVENT_CLASSIFICATION_TIMEOUT = 30          # 이벤트 분류 타임아웃 (초)
```

**권장값**:
- Risk 평가: 60초 (복잡한 추론 필요)
- 이벤트 분류: 30초 (단순 시제 분석)

### 9.3 입출력 파일 경로

```python
# ===== 입출력 파일 =====
AGENT3_OUTPUT_FILE = PROJECT_ROOT / "data" / "Dev_Data" / "news_db_search_results.json"
AGENT4_OUTPUT_FILE = PROJECT_ROOT / "data" / "Dev_Data" / "news_risk_evaluation_results.json"
```

**Agent_3와의 연결**:
- `AGENT3_OUTPUT_FILE`: Agent_3의 출력 JSON 경로
- Agent_3 실행 완료 후 Agent_4 실행 필요

---

## 10. 성능 지표

### 10.1 처리 속도

**측정 환경**:
- 뉴스 개수: 12개
- LLM 모델: gpt-5.5 (추론 모델)
- 병렬 처리: max_workers=5

**결과**:
- **뉴스 1개당 평균 처리 시간**: ~10초
  - Risk 평가 LLM 호출: ~6초
  - 이벤트 분류 LLM 호출: ~3초
  - 나머지 노드: ~1초
- **병렬 처리 (5 workers)**: ~30초 (12개 뉴스 전체)

**처리 속도 비교**:
| 뉴스 개수 | 직렬 처리 | 병렬 처리 (5 workers) | 개선 배수 |
|-----------|-----------|----------------------|----------|
| 12개 | ~120초 (2분) | ~30초 | **4배** |
| 35개 | ~350초 (6분) | ~80초 (1분 20초) | **4배** |
| 100개 | ~1000초 (17분) | ~240초 (4분) | **4배** |

### 10.2 비용 추정 (OpenAI API)

**모델**: gpt-5.5

| 작업 | 입력 토큰 | 출력 토큰 | 비용 (뉴스 1개) |
|------|-----------|-----------|----------------|
| Risk 평가 | ~2000 | ~300 | $0.0046 |
| 이벤트 분류 | ~800 | ~150 | $0.0019 |
| **합계** | ~2800 | ~450 | **$0.0065** |

**35개 뉴스 처리 비용**: ~$0.23 (약 300원)

**비용 절감 팁**:
- content_ko 길이 제한 (500자)
- gpt-4o 모델 사용 (정확도 약간 감소, 비용 50% 절감)

### 10.3 정확도 목표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| Risk 평가 정확도 | >= 85% | 수동 검증 (샘플 20개) |
| 이벤트 시점 정확도 | >= 90% | 수동 검증 (샘플 20개) |
| 이슈 타입 정확도 | >= 85% | 최종 분류 검증 |
| 에러 발생률 | <= 5% | LLM 호출 실패 비율 |

---

## 11. LLM 프롬프트 전략

### 11.1 Risk 평가 프롬프트 (핵심 원칙)

**파일**: `dev/Agent_4_Risk_Evaluator/prompts.py`

**System Prompt 핵심**:
```
당신은 삼성전자 DS 반도체 공급망 Risk 분석 전문가입니다.

**판단 기준**:
- 논리적 인과 관계: 뉴스 이벤트 → DB 엔티티 → 삼성전자 공급망 영향
- 도메인 지식 활용: 반도체 공급망 특성, 의존도, 집중도
- 구체성: "~할 수 있음" 금지, 구체적 Risk 요인 명시

**제외 사항**:
- 추상적/일반적 Risk
- 뉴스-DB 검색 결과 간 관계 없음
- 단순 뉴스 보도 (실질적 영향 없음)
```

**User Prompt 구조**:
1. **뉴스 원문**: 제목, 요약, 본문 일부 (500자)
2. **추출된 정보**: 키워드, 매핑 태그
3. **Risk 시나리오**: Agent_3 생성 시나리오
4. **DB 검색 결과**: SQL, 설명, 대상 엔티티
5. **도메인 규칙**: 온톨로지 조회 결과

**출력 형식 강제**:
```json
{
  "is_risk": <bool>,
  "risk_score": <float>,
  "risk_justification": "<string>",
  "risk_factors": ["<요인1>", "<요인2>", ...]
}
```

### 11.2 이벤트 시점 분류 프롬프트

**System Prompt 핵심**:
```
당신은 뉴스 이벤트 시점 분류 전문가입니다.

**분류 기준**:
1. ONGOING (진행형): 이미 발생, 현재 진행 중, 완료됨
   - 키워드: "발생", "시행", "중단됨", "완료", "발표됨" (과거형/현재형)
   
2. SCHEDULED (예정형): 예정, 예상, 계획, 가능성
   - 키워드: "예정", "계획", "할 것으로 예상", "가능성", "~될 전망"

**판단 원칙**:
- 뉴스 제목과 본문의 시제(時制)를 우선 고려
- 과거형/현재형 → ONGOING
- 미래형/추측 → SCHEDULED
```

**User Prompt 구조**:
1. **뉴스 원문**: 제목, 요약, 본문 일부 (500자)
2. **Risk 시나리오**: Agent_3 생성 시나리오

**출력 형식 강제**:
```json
{
  "event_timing": "<ONGOING | SCHEDULED>",
  "event_timing_confidence": <float>,
  "event_timing_justification": "<string>"
}
```

---

## 12. Fallback 전략

### 12.1 보수적 판단 원칙

**False Negative 방지 우선**:
- LLM 실패 시 Risk가 있는 것으로 간주 (보수적 판단)
- 진행형으로 간주하여 즉시 대응 가능하도록 처리

### 12.2 노드별 Fallback 동작

#### 12.2.1 evaluate_risk_relevance 노드

```python
except Exception as e:
    # Fallback: 보수적 판단 (Risk로 간주)
    state["is_risk"] = True
    state["risk_score"] = 0.5
    state["risk_justification"] = f"LLM 평가 실패, 보수적 판단: {str(e)}"
    state["risk_factors"] = ["평가 실패"]
    return state
```

**근거**: Risk를 놓치는 것(False Negative)이 무관한 뉴스를 포함하는 것(False Positive)보다 위험함

#### 12.2.2 classify_event_timing 노드

```python
except Exception as e:
    # Fallback: ONGOING (보수적 판단)
    state["event_timing"] = "ONGOING"
    state["event_timing_confidence"] = 0.5
    state["event_timing_justification"] = f"LLM 분류 실패, 보수적 판단: {str(e)}"
    return state
```

**근거**: 예정형을 진행형으로 오판하면 즉시 대응 가능 (안전)

#### 12.2.3 determine_issue_type 노드

```python
except Exception as e:
    # 예외 발생 시 NONE 처리
    state["error"] = f"이슈 타입 결정 실패: {str(e)}"
    state["issue_type"] = "NONE"
    state["issue_priority"] = "NONE"
    return state
```

**근거**: 조건부 로직이므로 에러 발생 시 안전하게 NONE 처리

### 12.3 에러 로깅

**모든 노드에서 에러 출력**:
```python
print(f"[ERROR] {노드명} 실패: {str(e)}")
```

**State에 에러 기록**:
```python
state["error"] = f"{노드명} 실패: {str(e)}"
```

**최종 JSON에 에러 누적**:
```python
output_data = {
    ...
    "results": results,
    "errors": [r.get("error") for r in results if r.get("error")]
}
```

---

## 13. 멀티 에이전트 연계

### 13.1 전체 파이프라인 구조

```
[뉴스 수집 (크롤러)]
         ↓
[Agent_1: News Analyzer]
    - 번역 → 요약 → 키워드 → 필터링
    - 결과: news_full_pipeline.json
         ↓
[Agent_2: Tag Mapper]
    - Risk Factor 태깅
    - 결과: news_tagged.json
         ↓
[Agent_3: DB Searcher]
    - Risk 시나리오 생성
    - SQL 쿼리 생성
    - 결과: news_db_search_results.json
         ↓
[Agent_4: Risk Evaluator] ← 현재 모듈
    - Risk 관련성 평가
    - 이벤트 시점 분류
    - 이슈 타입 결정
    - 결과: news_risk_evaluation_results.json
         ↓
    [최종 결과]
```

### 13.2 Agent_3 → Agent_4 연결

**입력**: Agent_3의 `news_db_search_results.json`

**State 변환**:
```python
state = RiskEvaluationState(
    # Agent_3 필드 복사
    news_id=article.get("news_id", ""),
    title_ko=article.get("title_ko", ""),
    summary_ko=article.get("summary_ko", ""),
    content_ko=article.get("content_ko", ""),
    keywords=article.get("keywords", []),
    mapped_tags=article.get("mapped_tags", []),
    risk_scenario=article.get("risk_scenario", ""),
    risk_scenario_entities=article.get("risk_scenario_entities", []),
    risk_scenario_confidence=article.get("risk_scenario_confidence", 0.0),
    impact_level=article.get("impact_level", "MEDIUM"),
    generated_sql=article.get("generated_sql"),
    sql_explanation=article.get("sql_explanation", ""),
    search_target_entities=article.get("search_target_entities", []),
    domain_rules=article.get("domain_rules", []),
    original_language=article.get("original_language", "korean"),
    is_relevant=article.get("is_relevant", True),
    relevance_score=article.get("relevance_score", 0.0),
    mapping_quality_score=article.get("mapping_quality_score", 0.0),
    # Agent_4 필드 초기화
    is_risk=False,
    risk_score=0.0,
    risk_justification="",
    risk_factors=[],
    event_timing="ONGOING",
    event_timing_confidence=0.0,
    event_timing_justification="",
    issue_type="NONE",
    issue_priority="NONE",
    error=None
)
```

### 13.3 Agent_4 출력 활용 (다음 단계)

**출력**: `news_risk_evaluation_results.json`

**활용 방안**:
1. **ISSUE 타입**: 즉시 대응 대시보드에 표시
2. **SMD 타입**: 예정형 모니터링 목록에 추가
3. **NONE 타입**: 아카이브 (추가 조치 불필요)

**필터링 기준**:
```python
# ISSUE 타입만 추출
issues = [r for r in results if r["issue_type"] == "ISSUE"]

# HIGH 우선순위만 추출
high_priority_issues = [r for r in issues if r["issue_priority"] == "HIGH"]

# SMD 타입만 추출
scheduled_events = [r for r in results if r["issue_type"] == "SMD"]
```

---

## 14. 문의 및 이슈

- **프로젝트 경로**: `C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a`
- **모듈 경로**: `dev/Agent_4_Risk_Evaluator`
- **데이터 경로**: `data/Dev_Data`
- **설정 파일**: `dev/Agent_4_Risk_Evaluator/config.py`

---

---

## 15. 변경 이력

### v1.0 (2026-07-04)
- ✅ **LangGraph 통합**: validate → evaluate → classify → determine
- ✅ **Risk 평가**: LLM 기반 논리적 인과 관계 분석
- ✅ **이벤트 시점 분류**: ONGOING vs SCHEDULED 구분
- ✅ **이슈 타입 결정**: ISSUE / SMD / NONE 자동 분류
- ✅ **병렬 처리**: ThreadPoolExecutor (5 workers)
- ✅ **Fallback 전략**: 보수적 판단 (False Negative 방지)

### v1.1 (2026-07-08)
- ✅ **다중 시나리오 독립 평가**: 2-4개 시나리오 각각 독립 Risk 평가
- ✅ **통합 판정 로직**: 하나라도 Risk=True → 최종 Risk=True
- ✅ **조건부 분기**: 단일/다중 시나리오 자동 선택
- ✅ **그룹 정보 추적**: original_news_ids, is_grouped 필드 추가
- ✅ **DB 검색 결과 활용**: Agent_3 다중 검색 결과 수신 및 평가
- 📊 **통합 파이프라인**: Phase 4 → Agent_3 → Agent_4 전체 흐름 연결

**주요 개선사항**:
- 다중 시나리오 평가로 False Negative 감소
- 주도 시나리오 추적으로 판정 근거 명확화
- 그룹 문서 처리 지원 (9개 뉴스 통합 문서)

---

**문서 버전**: 1.1  
**최종 업데이트**: 2026-07-08  
**작성자**: PoC-A 개발팀  
**상태**: 다중 시나리오 평가 완료, 통합 파이프라인 테스트 완료
