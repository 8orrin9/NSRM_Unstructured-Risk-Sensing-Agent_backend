# Agent_1 News Analyzer 문서

**작성일**: 2026-07-08  
**버전**: 1.0  
**담당**: POC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [핵심 개념](#2-핵심-개념)
3. [데이터 흐름](#3-데이터-흐름)
4. [출력 구조 상세](#4-출력-구조-상세)
5. [False Positive 필터링](#5-false-positive-필터링)
6. [키워드 추출 방식](#6-키워드-추출-방식)
7. [실전 예시](#7-실전-예시)
8. [설정 및 구성](#8-설정-및-구성)
9. [활용 방안](#9-활용-방안)
10. [FAQ](#10-faq)

---

## 1. 개요

### 1.1 목적

Agent_1 News Analyzer는 **공급망 리스크 감지 파이프라인의 첫 번째 관문**으로, 원시 뉴스 데이터를 분석하여 공급망과 관련된 뉴스만 선별하는 모듈입니다.

### 1.2 주요 기능

- ✅ **다국어 번역**: 영어 뉴스를 한글로 자동 번역
- ✅ **자동 요약 생성**: 뉴스 본문을 3-5문장으로 요약
- ✅ **LLM 키워드 추출**: 공급망 리스크 관점에서 핵심 키워드 추출
- ✅ **False Positive 필터링**: 34개 Risk Factor 기준으로 관련성 판정
- ✅ **배치 처리**: 대량의 뉴스를 효율적으로 처리

### 1.3 입출력

| 구분 | 설명 |
|------|------|
| **입력** | 원시 뉴스 데이터 (title, summary, content) |
| **출력** | 분석 완료된 뉴스 (한글 번역 + 요약 + 키워드 + 관련성 점수) |

---

## 2. 핵심 개념

### 2.1 문제 정의

**수동 방식의 한계**:
```
151개 뉴스 수집
↓
담당자가 하나씩 읽으며 공급망 관련 여부 판단
↓
키워드 수동 추출 및 분류
↓
하루 종일 소요 + 주관적 판단 + 놓치는 뉴스 발생
```

**자동화 솔루션**:
```
151개 뉴스 입력
↓
Agent_1이 자동으로:
  1. 한글 번역 (영어 → 한글)
  2. 요약 생성 (핵심 3-5문장)
  3. 키워드 추출 (공급망 관점)
  4. 관련성 판정 (34개 Risk Factor 기준)
↓
85개 관련 뉴스 자동 선별 (56.3%) + 66개 무관 뉴스 제외 (2분 소요)
```

### 2.2 핵심 가치

1. **효율성**: 수동 검토 → 자동 필터링 (시간 단위 → 분 단위)
2. **객관성**: 34개 Risk Factor 기준으로 일관된 판정
3. **확장성**: 하루 수천 개 뉴스도 자동 처리 가능
4. **추적성**: 각 뉴스의 관련성 판정 근거 자동 기록

---

## 3. 데이터 흐름

### 3.1 전체 프로세스

```
┌─────────────────────────────────────────────────────────────────┐
│ [INPUT] 원시 뉴스 데이터                                        │
│ • title (영어 또는 한글)                                        │
│ • summary (있는 경우)                                           │
│ • content (본문)                                                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 1] 한글 번역 (translate_to_korean)                       │
│ • 영어 뉴스 감지 (original_language: "english")                │
│ • LLM 번역 (title, summary, content → 한글)                    │
│ • 기술 용어 보존 (NF3, SF6, TSMC 등)                           │
│ OUTPUT: title_ko, summary_ko, content_ko                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 2] 요약 생성 (generate_summary)                          │
│ • LLM을 통한 뉴스 본문 요약 (3-5문장, 최대 150자)             │
│ • 객관적 사실 중심 요약 (판단은 다음 단계로 유보)             │
│ • 핵심 정보 보존: 기업명, 소재명, 지역, 이벤트               │
│ OUTPUT: summary_ko (summary가 없던 뉴스도 자동 생성)           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 3] 키워드 추출 (extract_keywords)                        │
│ • LLM 기반 키워드 추출 (공급망 리스크 관점)                    │
│ • 6개 카테고리: 소재/부품, 기업/기관, 지정학/규제,             │
│                물류거점, 리스크이벤트, 산업/제품               │
│ • 키워드별 신뢰도(score), 추출 이유(reason) 포함              │
│ OUTPUT: keywords[] (최대 10개)                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 4] False Positive 필터링 (filter_false_positive)         │
│ • 34개 Risk Factor 기준 관련성 판정                            │
│ • LLM이 요약문을 읽고 0.0~1.0 점수 산출                        │
│ • 임계값(0.5) 기준 TRUE/FALSE 결정                             │
│ OUTPUT: is_relevant, relevance_score, relevance_reason          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [OUTPUT] 분석 완료된 뉴스                                       │
│ • 한글 번역 + 요약 + 키워드 + 관련성 판정                      │
│ • is_relevant=True → Agent_2로 전달                            │
│ • is_relevant=False → 제외 (로그 보관)                         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 노드별 상세 설명

#### translate_to_korean
- **역할**: 영어 뉴스를 한글로 번역
- **조건**:
  - 제목이 한글이면 스킵 (`original_language: "korean"`)
  - 제목이 영어면 LLM 번역 (`original_language: "english"`)
- **특징**: 기술 용어 보존 (NF3, TSMC, H2O2 등)

#### generate_summary
- **역할**: 뉴스 본문을 3-5문장으로 요약
- **중요**: **객관적 사실 요약**이 핵심
  - "이 뉴스가 공급망과 관련이 있는지"는 다음 단계에서 판단
  - 이 단계에서는 기사 내용을 왜곡 없이 있는 그대로 요약
- **출력**: 최대 150자 한글 요약문

#### extract_keywords
- **역할**: 공급망 리스크 관점에서 핵심 키워드 추출
- **추출 카테고리**:
  1. 소재/부품/화학물질 (예: NF3, 네온, 희토류)
  2. 기업/기관 (예: TSMC, 상무부)
  3. 지정학/규제 (예: 대중 수출통제, 반도체법)
  4. 물류거점/경로 (예: 호르무즈 해협)
  5. 리스크 이벤트 (예: 공장 화재, 항만 파업)
  6. 산업/제품 카테고리 (예: 차량용 반도체)
- **제외 기준**: 범용 경제 용어 (교통, 수출, 생산 등)

#### filter_false_positive
- **역할**: 34개 Risk Factor 기준으로 관련성 판정
- **판정 기준**:
  - **TRUE**: Risk Factor 중 하나 이상이 **명시적으로** 언급됨
  - **FALSE**: Risk Factor와 **직접 관련 없음**
- **출력**: 
  - `relevance_score`: 0.0 ~ 1.0
  - `relevance_reason`: 판정 근거 (어떤 Risk Factor와 관련되는지)

---

## 4. 출력 구조 상세

### 4.1 전체 구조

```json
{
  "extraction_date": "2026-07-08T12:20:33.141091",
  "total_articles": 151,
  "relevant_count": 85,          // 관련 뉴스 (is_relevant=True)
  "irrelevant_count": 66,        // 무관 뉴스 (is_relevant=False)
  "threshold": 0.5,              // False Positive 임계값
  "total_errors": 0,
  "results": [
    { /* 뉴스별 분석 결과 */ }
  ]
}
```

### 4.2 뉴스별 결과 구조

```json
{
  // ===== 입력 정보 (원본) =====
  "news_id": "19d6b590086c81142e4d17371546c619",
  "title": "China's rare missile test will push wary Pacific countries to close ranks",
  "summary": "",
  "content": "China's rare launch of a ballistic missile...",
  
  // ===== STEP 1: 한글 번역 =====
  "title_ko": "중국의 드문 미사일 시험 발사는 경계하는 태평양 국가들을 결속시킬 것이다",
  "summary_ko": "중국이 핵 잠수함에서 태평양으로 탄도 미사일을 발사했다. 이 시험은 중국의 군사력 증가에 대한 지역 국가들의 방어 관계 강화를 촉진할 것으로 예상된다...",
  "content_ko": "중국이 핵 잠수함에서 태평양으로 발사한 드문 탄도 미사일은...",
  "original_language": "english",
  
  // ===== STEP 3: 키워드 추출 =====
  "keywords": [
    {
      "keyword": "중국",
      "score": 0.95
    },
    {
      "keyword": "호주",
      "score": 0.9
    },
    {
      "keyword": "일본",
      "score": 0.9
    },
    {
      "keyword": "ICBM",
      "score": 0.85
    },
    {
      "keyword": "군사 현대화",
      "score": 0.8
    }
  ],
  
  // ===== STEP 4: False Positive 필터링 =====
  "is_relevant": true,
  "relevance_score": 0.85,
  "relevance_reason": "[지정학 & 규제 > 지역갈등/분쟁]과 관련. 중국의 미사일 시험 발사는 지역 국가들 간의 방어 관계 강화를 촉진하며, 이는 지정학적 긴장과 갈등을 나타내는 사례로 볼 수 있음.",
  
  // ===== 메타데이터 =====
  "error": null,
  "_source": "CNBC",
  "_url": "https://www.cnbc.com/...",
  "_pub_date": "43 Min Ago",
  "_article_idx": 1
}
```

### 4.3 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `title_ko` | str | 한글 번역된 제목 (영어 → 한글) |
| `summary_ko` | str | LLM이 생성한 요약 (3-5문장, 최대 150자) |
| `content_ko` | str | 한글 번역된 본문 |
| `original_language` | str | "korean" 또는 "english" |
| `keywords[]` | List[Dict] | 추출된 키워드 (최대 10개) |
| `keywords[].keyword` | str | 키워드 텍스트 |
| `keywords[].score` | float | 키워드 신뢰도 (0.0 ~ 1.0) |
| `is_relevant` | bool | 공급망 관련성 여부 (True/False) |
| `relevance_score` | float | 관련성 점수 (0.0 ~ 1.0) |
| `relevance_reason` | str | 판정 근거 (어떤 Risk Factor와 관련되는지) |

---

## 5. False Positive 필터링

### 5.1 개념

**False Positive** = 공급망 리스크와 **무관한** 뉴스가 **관련 있는 것처럼 보이는** 현상

**예시**:
- ❌ "트럼프 주식 매입" → 반도체 기업 주식이라도 공급망 리스크 아님
- ❌ "AI 도입 후 인력 재고용" → 일반 고용 이슈, 공급망 무관
- ✅ "중국 희토류 수출 제한" → [원자재&희소물질] Risk Factor 해당

### 5.2 34개 Risk Factor (8개 대분류)

Agent_1은 다음 34개 Risk Factor 중 **하나 이상이 명시적으로 언급된 경우에만** 관련 뉴스로 판정합니다:

#### 1. 지정학 & 규제
- 수출입규제, 기업제재, 무역분쟁&관세, 수출허가지연, 외국인 투자규제, 역외적용, 지역갈등/분쟁

#### 2. 공급집중 & 단일소싱
- 장비 독과점, 소재 단일 공급, 지역 집중

#### 3. 원자재 & 희소물질
- 희토류 공급, 네온/크립톤/크세논, 팔라듐/코발트, 특수가스(WF6, NF3 등), 원자재 가격 변동성

#### 4. 기술 & 지식재산
- 기술 유추/탈취, 특허분쟁, 기술 단절(EOL), R&D 집중도

#### 5. 물류 & 인프라
- 항만 혼잡, 항공 운임 급등, 물류 경로 차단, 화물 운송 파업, 전력 인프라

#### 6. 사이버 & 데이터
- 공급사 사이버 공격, OT/ICS 보안, 공급망 소프트웨어 취약점, 데이터 주권 규제

#### 7. ESG & Compliance
- 분쟁광물 규제, 탄소 규제, 인권/노동 규제, 환경 규제

#### 8. 재무 & 신용 Risk
- 협력사 재무 부실, 환율 변동성, 보험/신용 위축

### 5.3 판정 프로세스

```python
# LLM에게 전달되는 정보
{
  "title": "트럼프 애플·엔비디아 주식 매입",
  "summary": "트럼프가 애플, 엔비디아 주식을 매입했다."
}

# LLM 판정
{
  "relevance_score": 0.05,  # 0.5 미만 → FALSE
  "reason": "주식 매입은 Risk Factor와 무관. 추상적 연결만 존재."
}

# 결과
is_relevant = False  # Agent_2로 전달 안 함
```

### 5.4 판정 기준

| 판정 | 조건 | 예시 |
|------|------|------|
| **TRUE** | relevance_score >= 0.5 | "중국 희토류 수출 제한" (원자재&희소물질) |
| **FALSE** | relevance_score < 0.5 | "트럼프 주식 매입" (Risk Factor 해당 없음) |

---

## 6. 키워드 추출 방식

### 6.1 LLM vs TextRank

Agent_1은 두 가지 키워드 추출 방식을 지원합니다:

| 방식 | 장점 | 단점 | 현재 설정 |
|------|------|------|-----------|
| **LLM** | 의미적 이해 (공급망 관점) | API 비용 | ✅ 기본값 |
| **TextRank** | 빠르고 저렴 | 의미 파악 불가 | 비활성화 |

### 6.2 LLM 키워드 추출 특징

#### 카테고리별 추출
```json
{
  "keyword": "호르무즈 해협",
  "category": "물류거점/경로",
  "score": 0.95,
  "reason": "호르무즈 해협 봉쇄는 [물류&인프라 > 물류 경로 차단]과 직접 관련. 추적 가능한 구체적 지점."
}
```

#### 범용 용어 제외
- ❌ "교통", "수출", "산업", "공급" (너무 범용적)
- ✅ "호르무즈 해협", "네온가스 수출통제", "대만 TSMC 공장"

#### 중복 제거
- "TSMC", "대만 TSMC", "TSMC 공장" → 가장 구체적인 "대만 TSMC 공장" 하나만 선택

### 6.3 키워드 검증 테스트

키워드를 추출할 때 스스로에게 물어보는 질문:

> "이 키워드만 보고 검색했을 때, 공급망 리스크 모니터링 담당자가 이걸 추적 대상으로 등록할 만한가?"

- ❌ "교통" → 너무 범용적, 추적 불가
- ✅ "호르무즈 해협 통항 제한" → 구체적, 추적 가능

---

## 7. 실전 예시

### 7.1 뉴스 입력 (영어)

```json
{
  "title": "China's rare missile test will push wary Pacific countries to close ranks",
  "summary": "",
  "content": "China's rare launch of a ballistic missile from a nuclear submarine into the Pacific..."
}
```

### 7.2 STEP 1: 한글 번역

```json
{
  "title_ko": "중국의 드문 미사일 시험 발사는 경계하는 태평양 국가들을 결속시킬 것이다",
  "summary_ko": "중국이 핵 잠수함에서 태평양으로 탄도 미사일을 발사했다. 이 시험은 중국의 군사력 증가에 대한 지역 국가들의 방어 관계 강화를 촉진할 것으로 예상된다. 전문가들은 호주, 뉴질랜드, 일본, 필리핀 간의 협력이 확대될 것이라고 전망하고 있다.",
  "content_ko": "중국이 핵 잠수함에서 태평양으로 발사한 드문 탄도 미사일은...",
  "original_language": "english"
}
```

### 7.3 STEP 3: 키워드 추출

```json
{
  "keywords": [
    {"keyword": "중국", "score": 0.95},
    {"keyword": "호주", "score": 0.9},
    {"keyword": "일본", "score": 0.9},
    {"keyword": "필리핀", "score": 0.9},
    {"keyword": "뉴질랜드", "score": 0.9},
    {"keyword": "ICBM", "score": 0.85},
    {"keyword": "군사 현대화", "score": 0.8}
  ]
}
```

### 7.4 STEP 4: False Positive 필터링

```json
{
  "is_relevant": true,
  "relevance_score": 0.85,
  "relevance_reason": "[지정학 & 규제 > 지역갈등/분쟁]과 관련. 중국의 미사일 시험 발사는 지역 국가들 간의 방어 관계 강화를 촉진하며, 이는 지정학적 긴장과 갈등을 나타내는 사례로 볼 수 있음."
}
```

### 7.5 해석

- **판정**: 공급망 관련 뉴스 (is_relevant=True)
- **근거**: [지정학 & 규제 > 지역갈등/분쟁] Risk Factor 해당
- **다음 단계**: Agent_2로 전달하여 태그 매핑 수행

---

## 8. 설정 및 구성

### 8.1 주요 설정 (config.py)

```python
# ===== 키워드 추출 =====
KEYWORD_EXTRACTION_METHOD = "llm"          # "llm" | "textrank"
TOP_K_KEYWORDS = 10                        # 최대 키워드 수
MIN_KEYWORD_LENGTH = 2                     # 최소 문자 수
SIMILARITY_THRESHOLD = 0.8                 # 중복 제거 임계값

# ===== LLM 모델 =====
TRANSLATION_MODEL = "gpt-4o-mini"          # 번역용
SUMMARY_MODEL = "gpt-4o-mini"              # 요약용
FALSE_POSITIVE_MODEL = "gpt-4o-mini"       # False Positive 필터용

# ===== 요약 생성 =====
SUMMARY_GENERATION_ENABLED = True          # 요약 생성 활성화
SUMMARY_MAX_LENGTH = 150                   # 최대 문자 수

# ===== False Positive 필터링 =====
FALSE_POSITIVE_FILTER_ENABLED = True       # 필터링 활성화
FALSE_POSITIVE_THRESHOLD = 0.5             # 관련성 임계값

# ===== 타임아웃 =====
TRANSLATION_TIMEOUT = 30                   # 번역 타임아웃 (초)
SUMMARY_TIMEOUT = 30                       # 요약 타임아웃 (초)
FALSE_POSITIVE_TIMEOUT = 30                # 필터링 타임아웃 (초)
```

### 8.2 디렉터리 구조

```
dev/Agent_1_News_Analyzer/
├── config.py                    # 설정 파일
├── graph.py                     # LangGraph 워크플로우 정의
├── prompts.py                   # LLM 프롬프트
├── nodes/                       # 노드별 구현
│   ├── __init__.py             # State 정의
│   ├── translator.py           # 번역
│   ├── summary_generator.py    # 요약 생성
│   ├── keyword_extractor.py    # 키워드 추출
│   └── false_positive_filter.py # False Positive 필터링
├── utils/                       # 유틸리티 (TextRank 등)
├── scripts/
│   └── run_news_analyzer.py    # 실행 스크립트
└── output/
    └── output_news_analyzer.json # 최종 출력
```

---

## 9. 활용 방안

### 9.1 대시보드 연동

```python
# 일일 뉴스 요약 대시보드
results = load_news_analyzer_output()

relevant_news = [r for r in results["results"] if r["is_relevant"]]
dashboard.show_metrics({
    "total_news": results["total_articles"],
    "relevant_news": results["relevant_count"],
    "relevance_rate": f"{results['relevant_count'] / results['total_articles'] * 100:.1f}%"
})
```

### 9.2 알림 시스템

```python
# 고위험 키워드 발견 시 알림
CRITICAL_KEYWORDS = ["희토류", "네온", "수출 제한", "TSMC"]

for result in results["results"]:
    if result["is_relevant"]:
        for kw in result["keywords"]:
            if kw["keyword"] in CRITICAL_KEYWORDS:
                send_alert(
                    title=result["title_ko"],
                    keyword=kw["keyword"],
                    relevance=result["relevance_reason"]
                )
```

### 9.3 트렌드 분석

```python
# 이번 주 공급망 리스크 트렌드
from collections import Counter

all_keywords = []
for result in results["results"]:
    if result["is_relevant"]:
        all_keywords.extend([kw["keyword"] for kw in result["keywords"]])

top_keywords = Counter(all_keywords).most_common(10)
print("이번 주 TOP 10 키워드:")
for keyword, count in top_keywords:
    print(f"- {keyword}: {count}회")
```

---

## 10. FAQ

### Q1. 번역 품질이 낮은 경우는?

**A**: 
- 기술 용어가 잘못 번역되는 경우: `prompts.py`의 `TRANSLATION_USER_PROMPT_TEMPLATE`에 보존할 용어 추가
- 전체적으로 품질이 낮은 경우: `TRANSLATION_MODEL`을 "gpt-4o"로 변경 (비용 증가)

### Q2. False Positive가 많이 발생하는 경우는?

**A**: 
1. `FALSE_POSITIVE_THRESHOLD` 상향 조정 (0.5 → 0.6)
2. `prompts.py`의 34개 Risk Factor 목록 재검토
3. LLM 모델 변경 (`FALSE_POSITIVE_MODEL = "gpt-4o"`)

### Q3. 키워드 추출이 너무 범용적인 경우는?

**A**: 
- `prompts.py`의 `KEYWORD_USER_PROMPT_TEMPLATE`에서 "제외 기준" 강화
- 예: "다음 단어는 절대 추출하지 마세요: 교통, 수출, 생산, 공급, 운송"

### Q4. 요약이 너무 짧거나 긴 경우는?

**A**: 
- `SUMMARY_MAX_LENGTH` 조정 (150 → 200 또는 100)
- `prompts.py`에서 "3-5문장" → "4-6문장"으로 변경

### Q5. 영어 뉴스가 한글로 감지되는 경우는?

**A**: 
- `translator.py`의 언어 감지 로직 확인
- 제목 첫 글자가 한글이면 `original_language: "korean"`으로 판정
- 필요 시 더 정교한 언어 감지 라이브러리 사용 (langdetect)

### Q6. 성능은 어느 정도인가요?

**A**: 
- 뉴스 1개당 처리 시간: 평균 **5-8초**
- LLM 호출 횟수: 번역(1회) + 요약(1회) + 키워드(1회) + 필터링(1회) = 총 4회
- 병렬 처리: 가능 (여러 뉴스 동시 처리)
- 151개 뉴스 처리: 약 **2분 소요** (병렬 처리 시)

### Q7. TextRank 키워드 추출을 사용하고 싶은데?

**A**: 
```python
# config.py
KEYWORD_EXTRACTION_METHOD = "textrank"  # "llm" → "textrank"
```

**장점**: 빠르고 API 비용 없음  
**단점**: 의미 파악 불가 (범용 단어 많이 추출)

---

## 부록

### A. 관련 문서

- Agent_2 Tag Mapper 문서: `Markdown/Module/DOCS/DOCS_TAG_MAPPER.md`
- Agent_5 News Grouper 문서: `Markdown/Module/DOCS/DOCS_NEWS_GROUPER.md`

### B. 변경 이력

| 날짜 | 버전 | 내용 |
|------|------|------|
| 2026-07-08 | 1.0 | 최초 작성 |

---

**문서 작성자**: POC-A 개발팀  
**최종 업데이트**: 2026-07-08
