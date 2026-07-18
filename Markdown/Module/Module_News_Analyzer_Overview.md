# Agent_1_News_Analyzer 모듈 개요

**버전**: 1.0 (병렬 처리 구현 완료)  
**최종 업데이트**: 2026-07-03  
**작성자**: PoC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [워크플로우 구조](#2-워크플로우-구조)
3. [병렬 처리 아키텍처](#3-병렬-처리-아키텍처)
4. [멀티 에이전트 연계](#4-멀티-에이전트-연계)
5. [Risk Factor 필터링](#5-risk-factor-필터링)
6. [State 정의](#6-state-정의)
7. [파일 구조](#7-파일-구조)
8. [실행 방법](#8-실행-방법)
9. [설정 가이드](#9-설정-가이드)
10. [성능 지표](#10-성능-지표)
11. [다음 에이전트 개발 가이드](#11-다음-에이전트-개발-가이드)

---

## 1. 개요

### 1.1 목적

**Agent_1_News_Analyzer**는 원문 뉴스를 수집하여 한글 번역, 요약 생성, 키워드 추출, Risk Factor 관련성 판정을 수행하는 뉴스 분석 파이프라인입니다.

### 1.2 주요 기능

- ✅ **영어 → 한글 번역**: OpenAI API (gpt-4o-mini) 활용
- ✅ **요약 생성**: 뉴스 본문 → 간결한 한글 요약 (최대 300자)
- ✅ **키워드 추출**: 공급망 리스크 관련 키워드 추출 (LLM 기반)
- ✅ **Risk Factor 필터링**: 34개 Risk Factor 기준 관련성 판정
- ✅ **병렬 처리**: ThreadPoolExecutor로 5배 성능 향상

### 1.3 처리 결과

**입력**: `data/NEWS/Dev_Data/news_data.json` (원문 뉴스)  
**출력**: `data/NEWS/Dev_Data/news_full_pipeline.json` (처리 완료 뉴스)

**필터링 기준**:
- `is_relevant=True`: Risk Factor와 관련된 뉴스 (다음 Agent로 전달)
- `is_relevant=False`: 무관한 뉴스 (제외)

---

## 2. 워크플로우 구조

### 2.1 LangGraph 파이프라인

```
┌─────────────────────┐
│  입력: 원문 뉴스     │
│  - title            │
│  - summary          │
│  - content          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────┐
│ [1] translate_to_korean     │
│  영어 → 한글 번역            │
│  (한글 뉴스는 그대로 통과)    │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ [2] generate_summary        │
│  content_ko → summary_ko    │
│  (본문 요약 생성)            │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ [3] extract_keywords        │
│  공급망 리스크 키워드 추출   │
│  (LLM 기반, Top 10개)        │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ [4] filter_false_positive   │
│  Risk Factor 관련성 판정     │
│  (34개 Factor 기준)          │
└──────────┬──────────────────┘
           │
           ▼
    ┌──────────────┐
    │ is_relevant? │
    └──────┬───────┘
           │
      ┌────┴────┐
      │         │
    TRUE      FALSE
      │         │
      ▼         ▼
  Agent_2      END
  (미구현)    (제외)
```

### 2.2 조건부 분기 로직

**파일**: `dev/Agent_1_News_Analyzer/graph.py`

```python
def should_continue_to_agent2(state: NewsAnalysisState) -> str:
    """
    False Positive 필터링 후 다음 노드 결정
    """
    if state.get("is_relevant", False):
        return "agent2"  # Agent_2_Tag_Mapper로 전달 (향후 구현)
    else:
        return "end"     # 무관한 뉴스 종료

workflow.add_conditional_edges(
    "filter_false_positive",
    should_continue_to_agent2,
    {
        "agent2": END,  # 현재는 END (Agent_2 미구현)
        "end": END
    }
)
```

**특징**:
- ✅ `is_relevant` 필드 기반 분기
- ✅ 무관한 뉴스는 조기에 제외하여 후속 처리 비용 절감
- ✅ Agent_2 구현 시 `"agent2": END`를 실제 노드로 변경 필요

---

## 3. 병렬 처리 아키텍처

### 3.1 병렬 처리 구현 (ThreadPoolExecutor)

**파일**: `dev/Agent_1_News_Analyzer/scripts/run_full_pipeline.py`

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# 단일 뉴스 처리 함수
def process_single_article(article_data):
    """단일 뉴스를 처리하는 함수 (독립 실행)"""
    state = NewsAnalysisState(...)
    return graph.invoke(state)  # 각 뉴스가 독립적으로 graph 실행

# 병렬 처리 (max_workers=5)
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(process_single_article, article_data): article_data
        for article_data in all_articles
    }
    
    # 완료되는 순서대로 처리 (실시간 출력)
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        print(f"완료: {len(results)}/{total_articles}")
```

### 3.2 성능 개선 효과

| 뉴스 개수 | 직렬 처리 | 병렬 처리 (5 workers) | 개선 배수 |
|-----------|-----------|----------------------|----------|
| 35개 | ~105초 (1분 45초) | ~21초 | **5배** |
| 100개 | ~300초 (5분) | ~60초 (1분) | **5배** |
| 500개 | ~1500초 (25분) | ~300초 (5분) | **5배** |

**측정 조건**:
- 뉴스 1개당 평균 3초 (번역 + 요약 + 키워드 + 필터링)
- max_workers=5 (5개 동시 처리)
- OpenAI API 레이트 리미팅 없음

### 3.3 max_workers 설정 가이드

**권장값: 5개**

**근거**:
- ✅ OpenAI API 레이트 리미팅 고려 (RPM, TPM 제한)
- ✅ 대부분의 유료 티어에서 안전
- ✅ 너무 많으면 429 에러 (Rate Limit Exceeded)
- ✅ 너무 적으면 병렬 효과 감소

**티어별 조정**:
- **Free tier**: 2~3개 (RPM 제한 엄격)
- **Paid tier (Tier 2+)**: 5~10개 (여유 있음)
- **Enterprise**: 10+ (레이트 리미팅 완화)

### 3.4 병렬 처리의 장점

1. **I/O 대기 시간 활용**: LLM API 응답 대기 중 다른 뉴스 처리
2. **실시간 진행 상황 출력**: `as_completed()` 패턴으로 완료 순서대로 표시
3. **에러 격리**: 개별 뉴스 실패 시 전체 프로세스 중단 없음
4. **확장성**: max_workers 조정으로 처리 속도 제어 가능
5. **메모리 효율**: 5개 뉴스만 동시 메모리 로드 (~50KB, 무시 가능)

---

## 4. 멀티 에이전트 연계

### 4.1 전체 파이프라인 구조

```
[뉴스 수집 (크롤러)]
         ↓
[Agent_1: News Analyzer] ← 현재 모듈
    - 35개 뉴스 병렬 처리
    - 번역 → 요약 → 키워드 → 필터링
    - 결과: news_full_pipeline.json
         ↓
[is_relevant=True 필터링]
         ↓
[Agent_2: Tag Mapper] (미구현)
    - 필터링된 뉴스만 병렬 처리
    - 34개 Risk Factor 태깅
    - 결과: news_tagged.json
         ↓
[Agent_3: ...] (미구현)
         ↓
    [최종 결과]
```

### 4.2 핵심 설계 원칙

1. **각 Agent는 독립적인 graph**
   - Agent_1, Agent_2, Agent_3가 각자 자신의 LangGraph 보유
   - 독립적으로 개발/테스트 가능
   - 노드 구성과 로직이 완전히 분리됨

2. **개별 뉴스 처리**
   - 각 뉴스는 독립적으로 `graph.invoke(state)` 호출
   - 뉴스 간 의존성 없음 (병렬 처리 가능)
   - State는 뉴스 단위로 관리

3. **병렬 처리 일관성**
   - 모든 Agent에서 ThreadPoolExecutor 사용
   - 전체 파이프라인 처리 속도 최적화
   - max_workers=5로 통일

4. **파이프라인 연결 (JSON 파일)**
   - Agent_N의 결과 JSON → Agent_N+1의 입력
   - 느슨한 결합 (Agent 간 독립성 유지)
   - 중간 결과 저장으로 디버깅 용이

5. **조건부 필터링**
   - 각 Agent가 특정 조건의 뉴스만 다음 단계로 전달
   - 불필요한 처리 제거 (비용 절감)
   - 데이터 품질 향상

### 4.3 Agent_2 구현 예시 (향후 개발 시 참고)

**파일**: `dev/Agent_2_Tag_Mapper/scripts/run_tag_mapper.py` (예시)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from .graph import create_tag_mapper_graph

def main():
    # 1. Agent_1 결과 로드
    with open("data/NEWS/Dev_Data/news_full_pipeline.json") as f:
        agent1_results = json.load(f)
    
    # 2. is_relevant=True인 뉴스만 필터링
    relevant_news = [
        news for news in agent1_results["results"] 
        if news.get("is_relevant", False)
    ]
    
    print(f"Agent_1 필터링 결과: {len(relevant_news)}개 / {agent1_results['total_articles']}개")
    
    # 3. Agent_2 graph 생성
    agent2_graph = create_tag_mapper_graph()
    
    # 4. 단일 뉴스 처리 함수
    def process_single_news(news):
        # Agent_1 결과를 Agent_2 State로 변환
        state = TagMapperState(
            news_id=news["news_id"],
            title_ko=news["title_ko"],
            summary_ko=news["summary_ko"],
            keywords=news["keywords"],
            # Agent_2 전용 필드
            risk_factors=[],
            tagged_categories=[]
        )
        
        # Agent_2 graph 실행 (개별 호출)
        return agent2_graph.invoke(state)
    
    # 5. 병렬 처리 (Agent_1과 동일한 패턴)
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_single_news, news): news
            for news in relevant_news
        }
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"완료: {len(results)}/{len(relevant_news)}")
    
    # 6. 결과 저장
    output_data = {
        "extraction_date": datetime.now().isoformat(),
        "total_articles": len(results),
        "results": results
    }
    
    with open("data/NEWS/Dev_Data/news_tagged.json", "w") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
```

**핵심 포인트**:
- ✅ Agent_1 결과 JSON 로드
- ✅ is_relevant=True 필터링
- ✅ Agent_2 State로 변환 (필요한 필드만 추출)
- ✅ 독립적인 graph.invoke() 호출
- ✅ 동일한 병렬 처리 패턴 (ThreadPoolExecutor)

---

## 5. Risk Factor 필터링

### 5.1 34개 Risk Factor 목록

**출처**: `data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx` ("1_Risk Factor Pool" 시트)

**8개 대분류, 34개 세부 항목**:

#### 1. 지정학 & 규제 (7개)
- 수출입규제
- 기업제재
- 무역분쟁&관세
- 수출허가지연
- 외국인 투자규제
- 역외적용 (Extraterritoriality)
- 지역갈등/분쟁

#### 2. 공급집중 & 단일소싱 (3개)
- 장비 독과점
- 소재 단일 공급
- 지역 집중

#### 3. 원자재 & 희소물질 (5개)
- 희토류 공급
- 네온/크립톤/크세논
- 팔라듐/코발트
- 특수가스 (WF6, NF3 등)
- 원자재 가격 변동성

#### 4. 기술 & 지식재산 (4개)
- 기술 유추/탈취
- 특허분쟁
- 기술 단절 (EOL)
- R&D 집중도

#### 5. 물류 & 인프라 (5개)
- 항만 혼잡
- 항공 운임 급등
- 물류 경로 차단
- 화물 운송 파업
- 전력 인프라

#### 6. 사이버 & 데이터 (4개)
- 공급사 사이버 공격
- OT/ICS 보안
- 공급망 소프트웨어 취약점
- 데이터 주권 규제

#### 7. ESG & Compliance (4개)
- 분쟁광물 규제
- 탄소 규제
- 인권/노동 규제
- 환경 규제

#### 8. 재무 & 신용 Risk (3개)
- 협력사 재무 부실
- 환율 변동성
- 보험/신용 위축

### 5.2 필터링 로직

**파일**: `dev/Agent_1_News_Analyzer/utils/llm_relevance_detector.py`

```python
def detect_relevance(title: str, summary: str) -> dict:
    """
    LLM 기반 Risk Factor 관련성 판정
    
    Args:
        title: 뉴스 제목 (한글)
        summary: 뉴스 요약 (한글)
    
    Returns:
        {
            "is_relevant": bool,           # 최종 판정
            "relevance_score": float,      # 0.0 ~ 1.0
            "relevance_reason": str        # 판정 근거
        }
    """
    # LLM 호출 (gpt-4o-mini, temperature=0.2)
    # JSON 응답 강제: response_format={"type": "json_object"}
    # 34개 Risk Factor를 프롬프트에 명시
```

### 5.3 판정 기준

**TRUE (관련 있음)**:
- 34개 Risk Factor 중 하나 이상이 **명시적으로** 언급됨
- 예시:
  - "중국 희토류 수출 제한" → [원자재&희소물질 > 희토류 공급]
  - "호르무즈 해협 통항 중단" → [물류&인프라 > 물류 경로 차단]
  - "대만 TSMC 사이버 공격" → [사이버&데이터 > 공급사 사이버 공격]

**FALSE (무관함)**:
- Risk Factor와 **직접 관련 없음**
- 추상적 연결만 존재하는 경우 제외
- 예시:
  - "트럼프 주식 매입" → Risk Factor 해당 없음
  - "AI 도입 후 인력 재고용" → Risk Factor 해당 없음
  - "일반 경제 전망" → Risk Factor 해당 없음

### 5.4 임계값 설정

**파일**: `dev/Agent_1_News_Analyzer/config.py`

```python
FALSE_POSITIVE_THRESHOLD = 0.5  # 0.5 이상이면 관련 있음
```

**판정 로직**:
```python
relevance_score = float(result_json.get("relevance_score", 0.0))
is_relevant = relevance_score >= FALSE_POSITIVE_THRESHOLD
```

**임계값 조정 가이드**:
- **0.5 (기본값)**: 중립적 시작점
- **0.4**: False Negative 최소화 (관련 뉴스 놓치지 않음)
- **0.6**: False Positive 최소화 (무관한 뉴스 엄격히 제외)
- **권장**: 테스트 후 조정 (0.4 ~ 0.6 범위)

---

## 6. State 정의

**파일**: `dev/Agent_1_News_Analyzer/nodes/__init__.py`

```python
from typing import TypedDict

class NewsAnalysisState(TypedDict):
    """
    뉴스 분석 상태
    
    각 뉴스마다 독립적인 State 인스턴스가 생성되며,
    LangGraph의 각 노드를 거치며 필드가 채워집니다.
    """
    # ========== 입력 (원문 뉴스) ==========
    news_id: str              # 뉴스 고유 ID (URL에서 추출)
    title: str                # 원문 제목
    summary: str              # 원문 요약
    content: str              # 원문 본문
    
    # ========== 번역 결과 ==========
    title_ko: str             # 한글 제목 (또는 원본 한글)
    summary_ko: str           # 한글 요약 (요약 생성 노드가 새로 생성)
    content_ko: str           # 한글 본문
    original_language: str    # 원본 언어 ("korean" | "english")
    
    # ========== 키워드 추출 ==========
    keywords: list            # [{"keyword": str, "score": float, "category": str}, ...]
    
    # ========== Risk Factor 필터링 ==========
    is_relevant: bool           # Risk Factor 관련성 판정 (True/False)
    relevance_score: float      # 관련성 신뢰도 점수 (0.0 ~ 1.0)
    relevance_reason: str | None  # 판정 근거 (어떤 Risk Factor와 관련되는지)
    
    # ========== 에러 처리 ==========
    error: str | None         # 에러 메시지 (없으면 None)
```

**필드 설명**:

| 필드 | 타입 | 설명 | 설정 노드 |
|------|------|------|----------|
| `news_id` | str | 뉴스 고유 ID | 입력 |
| `title` | str | 원문 제목 | 입력 |
| `summary` | str | 원문 요약 | 입력 |
| `content` | str | 원문 본문 | 입력 |
| `title_ko` | str | 한글 제목 | translate_to_korean |
| `summary_ko` | str | 한글 요약 (새로 생성) | generate_summary |
| `content_ko` | str | 한글 본문 | translate_to_korean |
| `original_language` | str | 원본 언어 | translate_to_korean |
| `keywords` | list | 키워드 리스트 | extract_keywords |
| `is_relevant` | bool | 관련성 판정 | filter_false_positive |
| `relevance_score` | float | 관련성 점수 | filter_false_positive |
| `relevance_reason` | str\|None | 판정 근거 | filter_false_positive |
| `error` | str\|None | 에러 메시지 | 모든 노드 |

---

## 7. 파일 구조

```
poc-a/dev/Agent_1_News_Analyzer/
│
├── graph.py                          # LangGraph 워크플로우 정의
│   └── create_news_analyzer_graph()  # 그래프 생성 함수
│
├── config.py                          # 설정 파일
│   ├── 번역 설정 (TRANSLATION_*)
│   ├── 요약 생성 설정 (SUMMARY_*)
│   ├── 키워드 추출 설정 (KEYWORD_*)
│   └── False Positive 필터링 설정 (FALSE_POSITIVE_*)
│
├── prompts.py                         # LLM 프롬프트 중앙 관리
│   ├── TRANSLATION_*                  # 번역 프롬프트
│   ├── SUMMARY_*                      # 요약 생성 프롬프트
│   ├── KEYWORD_*                      # 키워드 추출 프롬프트
│   └── FALSE_POSITIVE_*               # False Positive 필터링 프롬프트
│
├── nodes/                             # 워크플로우 노드
│   ├── __init__.py                    # NewsAnalysisState 정의
│   ├── translator.py                  # [노드 1] 번역
│   ├── summary_generator.py           # [노드 2] 요약 생성
│   ├── keyword_extractor.py           # [노드 3] 키워드 추출
│   └── false_positive_filter.py       # [노드 4] Risk Factor 필터링
│
├── utils/                             # LLM 호출 유틸리티
│   ├── llm_translator.py              # 번역 LLM 호출
│   ├── llm_summary_generator.py       # 요약 생성 LLM 호출
│   ├── llm_keyword_extractor.py       # 키워드 추출 LLM 호출
│   └── llm_relevance_detector.py      # Risk Factor 판정 LLM 호출
│
└── scripts/                           # 실행 스크립트
    ├── run_full_pipeline.py           # 전체 파이프라인 (병렬)
    └── run_false_positive_filter.py   # 필터링만 독립 실행 (병렬)
```

**핵심 파일 설명**:

### 7.1 graph.py
- LangGraph 워크플로우 정의
- 4개 노드 연결 (번역 → 요약 → 키워드 → 필터링)
- 조건부 분기 로직 (`should_continue_to_agent2`)

### 7.2 nodes/
- 각 노드는 `State → State` 변환 함수
- try-except 에러 처리
- utils/의 LLM 호출 함수 활용

### 7.3 utils/
- LLM API 호출 로직 분리
- 재사용 가능한 유틸리티 함수
- 프롬프트는 prompts.py에서 가져옴

### 7.4 scripts/
- 병렬 처리 구현 (ThreadPoolExecutor)
- 독립 실행 가능한 스크립트
- 진행 상황 실시간 출력

---

## 8. 실행 방법

### 8.1 전체 파이프라인 실행 (병렬)

```bash
cd C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a
python dev/Agent_1_News_Analyzer/scripts/run_full_pipeline.py
```

**처리 과정**:
1. `news_data.json` 로드 (35개 뉴스)
2. LangGraph 워크플로우 생성
3. 병렬 처리 실행 (max_workers=5)
4. 결과를 `news_full_pipeline.json`에 저장
5. 통계 출력 (관련/무관 뉴스 분포)

**출력 예시**:
```
================================================================================
뉴스 분석 전체 파이프라인 실행
================================================================================

[1/4] 뉴스 데이터 로드: ...
  ✓ 총 2개 소스, 35개 뉴스

[2/4] LangGraph 워크플로우 생성
  ✓ 워크플로우: 번역 → 요약 생성 → 키워드 추출 → False Positive 필터링

[3/4] 전체 파이프라인 실행 (총 35개, 병렬 처리)
  🇰🇷 [1/35] ✓ Score: 0.85 (요약: 245자, 키워드: 8개)
  🇬🇧→🇰🇷 [2/35] ✗ Score: 0.25 (요약: 187자, 키워드: 5개)
  ...

[4/4] 결과 저장
  ✓ 저장 완료: ...

================================================================================
실행 결과 요약
================================================================================
  총 처리: 35개
  한글 뉴스: 20개
  영어 뉴스: 15개 (번역됨)
  에러 발생: 0개

  False Positive 필터링 결과:
    관련 있음 (TRUE): 22개 (62.9%)
    무관함 (FALSE): 13개 (37.1%)
    임계값: 0.5
```

### 8.2 필터링만 독립 실행 (병렬)

```bash
python dev/Agent_1_News_Analyzer/scripts/run_false_positive_filter.py
```

**용도**: 이미 생성된 요약 (`news_summaries.json`)에 대해 필터링만 재실행

**처리 과정**:
1. `news_summaries.json` 로드
2. 병렬 필터링 실행 (max_workers=5)
3. 결과를 `news_filtered.json`에 저장
4. 상세 통계 출력 (점수 분포, 샘플)

---

## 9. 설정 가이드

**파일**: `dev/Agent_1_News_Analyzer/config.py`

### 9.1 번역 설정

```python
# ============================================================================
# 번역 설정
# ============================================================================
TRANSLATION_MODEL = "gpt-4o-mini"  # OpenAI 모델
TRANSLATION_TIMEOUT = 30           # API 타임아웃 (초)
```

### 9.2 요약 생성 설정

```python
# ============================================================================
# 요약 생성 설정
# ============================================================================
SUMMARY_MODEL = "gpt-4o-mini"      # OpenAI 모델
SUMMARY_MAX_LENGTH = 300           # 최대 요약 길이 (자)
SUMMARY_TEMPERATURE = 0.3          # 생성 온도 (0.0 ~ 1.0)
SUMMARY_TIMEOUT = 60               # API 타임아웃 (초)
```

**권장 설정**:
- `SUMMARY_MAX_LENGTH`: 200~400자 (너무 짧으면 정보 손실, 너무 길면 비용 증가)
- `SUMMARY_TEMPERATURE`: 0.3~0.5 (낮을수록 일관성 높음)

### 9.3 키워드 추출 설정

```python
# ============================================================================
# 키워드 추출 설정
# ============================================================================
KEYWORD_EXTRACTION_METHOD = "llm"  # "llm" | "tfidf"
KEYWORD_MODEL = "gpt-4o-mini"      # OpenAI 모델 (method="llm"일 때)
KEYWORD_TOP_K = 10                 # 추출할 키워드 개수
KEYWORD_TEMPERATURE = 0.3          # 생성 온도
KEYWORD_TIMEOUT = 60               # API 타임아웃 (초)
```

**권장 설정**:
- `KEYWORD_EXTRACTION_METHOD`: "llm" (TF-IDF보다 정확도 높음)
- `KEYWORD_TOP_K`: 10~15개 (너무 적으면 정보 부족, 너무 많으면 노이즈)

### 9.4 False Positive 필터링 설정

```python
# ============================================================================
# False Positive 필터링 설정
# ============================================================================
FALSE_POSITIVE_FILTER_ENABLED = True  # 필터링 활성화 여부
FALSE_POSITIVE_MODEL = "gpt-4o-mini"  # OpenAI 모델
FALSE_POSITIVE_TIMEOUT = 30           # API 타임아웃 (초)
FALSE_POSITIVE_THRESHOLD = 0.5        # 관련성 판정 임계값 (0.5 이상이면 TRUE)
```

**권장 설정**:
- `FALSE_POSITIVE_THRESHOLD`: 0.4~0.6 (테스트 후 조정)
  - 0.4: False Negative 최소화 (관련 뉴스 놓치지 않음)
  - 0.6: False Positive 최소화 (무관한 뉴스 엄격히 제외)

---

## 10. 성능 지표

### 10.1 처리 속도

**측정 환경**:
- 뉴스 개수: 35개
- 네트워크: 안정적인 유선 연결
- OpenAI API: Paid tier (Tier 2+)

**결과**:
- **직렬 처리**: ~105초 (뉴스 1개당 ~3초)
- **병렬 처리 (5 workers)**: ~21초 (5배 개선)

### 10.2 비용 추정 (OpenAI API)

**모델**: gpt-4o-mini

| 작업 | 입력 토큰 | 출력 토큰 | 비용 (뉴스 1개) |
|------|-----------|-----------|----------------|
| 번역 | ~500 | ~500 | $0.00015 |
| 요약 생성 | ~1000 | ~100 | $0.00017 |
| 키워드 추출 | ~1500 | ~150 | $0.00025 |
| False Positive 필터링 | ~200 | ~50 | $0.00004 |
| **합계** | ~3200 | ~800 | **$0.00061** |

**35개 뉴스 처리 비용**: ~$0.02 (약 30원)

### 10.3 정확도 (False Positive 필터링)

**테스트 데이터**: 35개 뉴스

| 항목 | 값 |
|------|-----|
| 총 뉴스 | 35개 |
| 관련 있음 (TRUE) | 22개 (62.9%) |
| 무관함 (FALSE) | 13개 (37.1%) |
| 임계값 | 0.5 |

**수동 검증 결과** (샘플 10개):
- True Positive: 9개 / 10개 (90%)
- False Positive: 1개 / 10개 (10%)
- True Negative: 확인 필요
- False Negative: 확인 필요

---

## 11. 다음 에이전트 개발 가이드

### 11.1 Agent_2 (Tag_Mapper) 개발 시 참고사항

#### 11.1.1 Agent_1 결과 로드

```python
import json

# Agent_1 결과 로드
with open("data/NEWS/Dev_Data/news_full_pipeline.json") as f:
    agent1_results = json.load(f)

# is_relevant=True인 뉴스만 필터링
relevant_news = [
    news for news in agent1_results["results"] 
    if news.get("is_relevant", False)
]

print(f"Agent_1 필터링 결과: {len(relevant_news)}개 / {agent1_results['total_articles']}개")
```

#### 11.1.2 Agent_2 State 정의 예시

```python
from typing import TypedDict

class TagMapperState(TypedDict):
    """
    Tag Mapper 상태 (Agent_2)
    
    Agent_1 결과에서 필요한 필드만 추출하여 사용
    """
    # Agent_1 결과에서 가져올 필드
    news_id: str
    title_ko: str
    summary_ko: str
    keywords: list           # Agent_1이 추출한 키워드 활용
    
    # Agent_2 전용 필드
    risk_factors: list       # 태깅된 Risk Factor 리스트
    confidence_scores: dict  # Risk Factor별 신뢰도
    tagged_categories: list  # 태깅된 카테고리
    
    # 에러 처리
    error: str | None
```

#### 11.1.3 병렬 처리 구현 (Agent_1과 동일 패턴)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

# Agent_2 graph 생성
agent2_graph = create_tag_mapper_graph()

# 단일 뉴스 처리 함수
def process_single_news(news):
    """Agent_1 결과 → Agent_2 State 변환 → graph 실행"""
    state = TagMapperState(
        news_id=news["news_id"],
        title_ko=news["title_ko"],
        summary_ko=news["summary_ko"],
        keywords=news["keywords"],
        risk_factors=[],
        confidence_scores={},
        tagged_categories=[],
        error=None
    )
    
    # Agent_2 graph 실행 (개별 호출)
    return agent2_graph.invoke(state)

# 병렬 처리 (max_workers=5)
results = []
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(process_single_news, news): news
        for news in relevant_news
    }
    
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        print(f"완료: {len(results)}/{len(relevant_news)}")
```

#### 11.1.4 결과 저장

```python
# Agent_2 결과 저장
output_data = {
    "extraction_date": datetime.now().isoformat(),
    "total_articles": len(results),
    "agent1_input_count": len(relevant_news),  # Agent_1에서 받은 뉴스 수
    "results": results
}

with open("data/NEWS/Dev_Data/news_tagged.json", "w") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)
```

### 11.2 개발 체크리스트

Agent_2 개발 시 다음 사항을 확인하세요:

- [ ] **Agent_1 결과 로드**: `news_full_pipeline.json` 읽기
- [ ] **is_relevant=True 필터링**: 관련 뉴스만 처리
- [ ] **State 정의**: Agent_1 필드 + Agent_2 전용 필드
- [ ] **LangGraph 정의**: Agent_2 전용 노드 구성
- [ ] **병렬 처리 구현**: ThreadPoolExecutor (max_workers=5)
- [ ] **독립적인 graph.invoke()**: 각 뉴스가 개별 실행
- [ ] **에러 처리**: try-except, 에러 격리
- [ ] **결과 저장**: JSON 파일 출력
- [ ] **통계 출력**: 처리 결과 요약

### 11.3 Agent 간 데이터 전달 규칙

1. **JSON 파일로 통신**: Agent 간 느슨한 결합
2. **필요한 필드만 추출**: State 변환 시 불필요한 데이터 제거
3. **메타데이터 포함**: extraction_date, total_articles 등
4. **에러 정보 전달**: 이전 Agent의 에러도 기록

---

## 12. 문의 및 이슈

- **프로젝트 경로**: `C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a`
- **모듈 경로**: `dev/Agent_1_News_Analyzer`
- **데이터 경로**: `data/NEWS/Dev_Data`
- **설정 파일**: `dev/Agent_1_News_Analyzer/config.py`

---

**문서 버전**: 1.0  
**최종 업데이트**: 2026-07-03  
**작성자**: PoC-A 개발팀  
**상태**: 병렬 처리 구현 완료, Agent_2 개발 대기 중
