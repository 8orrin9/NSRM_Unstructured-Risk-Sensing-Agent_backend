# TextRank 알고리즘과 LLM 기반 키워드 추출 비교

**작성일:** 2026-07-01  
**모듈:** Agent_1_News_Analyzer  
**파일:** `dev/Agent_1_News_Analyzer/utils/textrank.py`

---

## 1. TextRank 알고리즘 개요

TextRank는 Google의 PageRank 알고리즘을 텍스트 분석에 적용한 그래프 기반 키워드 추출 방법입니다.

### 1.1 전체 흐름

```
입력 텍스트
  ↓
전처리 & 토크나이징 (명사 추출)
  ↓
후보 키워드 선정 (빈도 ≥ 1)
  ↓
그래프 구성 (윈도우 기반 동시 출현)
  - 노드: 각 키워드
  - 엣지: 윈도우 내 동시 출현 (가중치 = 출현 횟수)
  ↓
PageRank 계산 (반복적으로 중요도 점수 계산)
  ↓
상위 키워드 선정
  ↓
중복/유사 키워드 제거 (Jaccard similarity)
  ↓
Top K 키워드 반환
```

---

## 2. TextRank 구현 상세

### 2.1 후보 키워드 생성

```python
tokens = tokenize_korean(cleaned_text)  # 명사 추출
token_counts = Counter(tokens)
candidates = [word for word, count in token_counts.items() if count >= 1]
```

- 1번 이상 등장한 모든 단어를 후보로 선정
- 실제로는 빈도 필터링이 거의 없는 상태

### 2.2 그래프 구성 - 윈도우 기반 동시 출현

**핵심 개념:** 슬라이딩 윈도우 내에서 함께 등장하는 단어들 간에 엣지를 생성

```python
for i in range(len(tokens)):
    window = tokens[i:i + WINDOW_SIZE]  # 예: 5개 단어 윈도우
    window_candidates = [w for w in window if w in candidates]
    
    # 윈도우 내 모든 단어 쌍에 대해 엣지 추가
    for j in range(len(window_candidates)):
        for k in range(j + 1, len(window_candidates)):
            word1, word2 = window_candidates[j], window_candidates[k]
            edge_weights[(word1, word2)] += 1  # 동시 출현 횟수 카운트
```

**예시:**
```
텍스트: "북한 미사일 발사 북한 군사 도발"
윈도우 크기: 3

윈도우 1: [북한, 미사일, 발사]
  - (북한, 미사일) +1
  - (북한, 발사) +1
  - (미사일, 발사) +1

윈도우 2: [미사일, 발사, 북한]
  - (미사일, 발사) +1  ← 중복 카운트
  - (미사일, 북한) +1
  - (발사, 북한) +1
```

### 2.3 PageRank 계산

```python
scores = nx.pagerank(
    graph,
    alpha=DAMPING_FACTOR,  # 보통 0.85 (댐핑 계수)
    max_iter=MAX_ITER,     # 최대 반복 횟수
    tol=1e-6               # 수렴 허용 오차
)
```

**PageRank 직관:**
- 많은 단어와 연결된 단어 = 중요한 키워드
- 중요한 단어와 연결된 단어 = 더 중요한 키워드
- 엣지 가중치가 높을수록 중요도 전파가 강함

**수식 (단순화):**
```
PR(단어A) = (1-d) + d × Σ (PR(단어B) × weight(B→A) / Σweight(B→*))
```
- `d`: 댐핑 계수 (DAMPING_FACTOR)
- 반복 계산하여 수렴할 때까지 진행

### 2.4 중복 키워드 제거

**Jaccard Similarity 기반 필터링:**

```python
def _string_similarity(s1: str, s2: str) -> float:
    # 1. 부분 문자열 포함 관계
    if s1 in s2 or s2 in s1:
        return 1.0  # "북한" vs "북한군" → 1.0
    
    # 2. Jaccard similarity (문자 집합 기반)
    set1 = set(s1)  # {'북', '한'}
    set2 = set(s2)  # {'중', '국'}
    
    intersection = len(set1 & set2)  # 교집합
    union = len(set1 | set2)         # 합집합
    
    return intersection / union  # 0.0 ~ 1.0
```

**필터링 과정:**
- 유사도가 `SIMILARITY_THRESHOLD` (보통 0.7-0.8)를 초과하면 중복으로 판단하고 제외

### 2.5 핵심 파라미터

| 파라미터 | 설명 | 일반적인 값 |
|---------|------|------------|
| `WINDOW_SIZE` | 동시 출현을 판단할 윈도우 크기 | 3-5 |
| `DAMPING_FACTOR` | PageRank 댐핑 계수 | 0.85 |
| `SIMILARITY_THRESHOLD` | 중복 판단 임계값 | 0.7-0.8 |
| `TOP_K_KEYWORDS` | 최종 추출할 키워드 개수 | 5-10 |
| `MAX_ITER` | PageRank 최대 반복 횟수 | 100 |

---

## 3. LLM 기반 키워드 추출의 우위

### 3.1 의미 이해 (Semantic Understanding)

| 방식 | 특징 | 예시 |
|-----|------|------|
| **TextRank** | 단순 동시 출현 패턴만 관찰 | "북한 미사일" → (북한, 미사일) 엣지 가중치 +1 |
| **LLM** | 실제 의미를 이해하고 추론 | "북한이 미사일을 발사했다" → "군사 도발", "안보 위협", "한반도 긴장" (명시되지 않은 개념도 추출 가능) |

**구체적 예시:**
- **텍스트:** "중앙은행이 기준금리를 0.5%p 인상했다"
- **TextRank:** "중앙은행", "기준금리", "인상"
- **LLM:** "통화정책 긴축", "금리 인상", "인플레이션 대응" (의미를 추론)

### 3.2 문맥 이해 (Context Awareness)

**TextRank:**
- 지역적 윈도우(3-5단어)만 고려
- "사과" → 주변 단어와의 동시 출현만 관찰

**LLM:**
- 전체 문서 맥락 이해
- 문서 A: "삼성이 애플에 사과했다" → "사과" = 사죄
- 문서 B: "사과 가격이 폭등했다" → "사과" = 과일

**중의성 해소 예시:**
- "배" → 과일? 탈것? 신체부위?
- "제재" → 경제제재? 징계?
- TextRank는 구분 불가, LLM은 문맥으로 판단

### 3.3 도메인 지식 활용

**TextRank:**
- 사전 지식 전혀 없음
- "FOMC" → 그냥 자주 등장하는 단어

**LLM:**
- 학습된 세계 지식 활용
- "FOMC" → Federal Open Market Committee → 미국 연방준비제도 금리 결정 기구 → "미국 통화정책" 키워드와 연결

**뉴스 도메인 예시:**
- **텍스트:** "KOSPI가 2% 하락했다"
- **TextRank:** "KOSPI", "하락"
- **LLM:** "한국 증시 급락", "주식시장 변동성", "투자 리스크"

### 3.4 복합 개념 추출

**TextRank:**
- 단일 명사 위주
- `tokens = ["핵", "확산", "금지", "조약"]` → 각각 독립적인 키워드로 추출 가능성

**LLM:**
- 의미적으로 하나인 개념을 하나로
- "핵 확산 금지 조약" → 하나의 키워드
- "탄소 중립 정책" → 하나의 키워드

### 3.5 목적 지향적 추출

**TextRank:**
- 통계적으로 중요한 단어
- 빈도 높음 + 다른 단어와 많이 연결 = 중요

**LLM:**
- 사용자 의도에 맞는 키워드
- 프롬프트: "이 뉴스에서 리스크 요인을 추출하세요"
- → 리스크와 관련된 키워드만 선별적으로 추출

**Agent_1_News_Analyzer의 경우:**
- **TextRank:** "기자", "보도", "관계자" 같은 뉴스 boilerplate도 키워드로 추출
- **LLM:** "공급망 차질", "규제 리스크", "지정학적 긴장" 등 리스크 관련 키워드만 추출

### 3.6 추상화 수준 조절

**TextRank:**
- 텍스트에 있는 단어만
- "애플", "삼성", "LG" → 개별 기업명만

**LLM:**
- 상위 개념으로 추상화 가능
- "애플", "삼성", "LG" → "빅테크 기업", "전자업계"
- 또는 구체적인 키워드도 유지 가능 (프롬프트로 제어)

### 3.7 다국어 처리

**TextRank:**
- 한국어 형태소 분석 의존
- `tokenize_korean(text)` → 형태소 분석기 성능에 좌우

**LLM:**
- 다국어 이해
- 영어 뉴스 → 한국어 키워드 추출 가능
- "Federal Reserve raises rates" → "미국 기준금리 인상", "연준 통화정책"

---

## 4. 실제 비교 예시

**뉴스 텍스트:**
> "중국 정부가 반도체 기업에 대한 수출 제한 조치를 강화하면서 삼성전자와 SK하이닉스의 실적 악화가 우려된다. 업계는 공급망 재편이 불가피할 것으로 전망했다."

### TextRank 결과:
```json
[
  {"keyword": "중국", "score": 0.15},
  {"keyword": "반도체", "score": 0.14},
  {"keyword": "삼성전자", "score": 0.12},
  {"keyword": "수출", "score": 0.11},
  {"keyword": "제한", "score": 0.10}
]
```

### LLM 결과:
```json
[
  {"keyword": "중국 수출 규제", "score": 0.95},
  {"keyword": "반도체 공급망 리스크", "score": 0.92},
  {"keyword": "삼성전자 실적 악화 우려", "score": 0.88},
  {"keyword": "미중 기술 패권 경쟁", "score": 0.85},
  {"keyword": "글로벌 공급망 재편", "score": 0.82}
]
```

**주목할 점:**
- LLM은 "미중 기술 패권 경쟁"처럼 명시적으로 언급되지 않았지만 문맥상 관련된 개념도 추출
- TextRank는 텍스트에 명시된 단어만 추출

---

## 5. 두 방식의 장단점 비교

| 측면 | TextRank | LLM |
|------|----------|-----|
| **속도** | 매우 빠름 (밀리초) | 느림 (초 단위) |
| **비용** | 무료 | API 비용 발생 |
| **재현성** | 완벽 (동일 입력 = 동일 출력) | 낮음 (temperature > 0) |
| **설명 가능성** | 명확 (그래프 시각화 가능) | 블랙박스 |
| **오프라인 사용** | 가능 | 어려움 (API 의존) |
| **의미 이해** | 없음 (통계적 패턴만) | 우수 |
| **문맥 이해** | 제한적 (윈도우 크기 내) | 전체 문서 맥락 이해 |
| **도메인 지식** | 없음 | 학습된 세계 지식 활용 |
| **복합 개념** | 단일 명사 위주 | 복합 개념 추출 가능 |
| **목적 지향** | 불가 | 프롬프트로 제어 가능 |

---

## 6. Agent_1_News_Analyzer에서 LLM 방식을 선택한 이유

본 프로젝트에서 LLM 기반 키워드 추출이 유리한 이유:

### 6.1 도메인 특화
- 일반 키워드가 아닌 **"리스크 요인" 추출이 목적**
- 금융/안보/경제 리스크라는 특수한 관점 필요

### 6.2 정확도 중시
- 속도보다 **정확한 리스크 분석이 중요**
- False Positive 최소화 필요

### 6.3 다국어 뉴스 처리
- 영어 뉴스도 처리해야 할 가능성
- 다국어 통합 처리 용이

### 6.4 복합 개념 필요
- "지정학적 리스크", "공급망 차질" 같은 복합 개념
- 단일 명사만으로는 리스크 파악 어려움

### 6.5 False Positive 필터링
- `llm_relevance_detector.py`로 관련 없는 뉴스 제거
- LLM의 판단력 활용

### 6.6 확장성
- 향후 감정 분석, 영향도 평가 등으로 확장 가능
- LLM 기반 파이프라인으로 일관성 유지

---

## 7. 사용 시나리오별 권장 방식

### TextRank가 적합한 경우:
- 대량 문서 1차 필터링
- 빠른 프로토타이핑
- 실시간 처리 필요
- 비용 제약이 큰 경우
- 오프라인 환경

### LLM이 적합한 경우:
- 도메인 특화 분석
- 복합 개념 추출 필요
- 의미/문맥 이해 중요
- 다국어 처리 필요
- 최종 품질이 중요한 분석

---

## 8. 결론

TextRank는 빠르고 효율적인 통계 기반 방법이지만, **의미와 문맥을 이해하지 못하는 한계**가 있습니다.

LLM 기반 키워드 추출은 비용과 속도 측면에서 불리하지만, **리스크 분석처럼 정확도가 중요한 도메인**에서는 압도적인 우위를 보입니다.

**Agent_1_News_Analyzer**는 금융 리스크 감지라는 특수 목적을 위해 LLM 방식을 채택하여, 단순 키워드 추출을 넘어 **맥락을 이해하고 의미 있는 리스크 요인을 추출**하는 것을 목표로 합니다.

---

## 참고 자료

- TextRank 논문: [TextRank: Bringing Order into Texts](https://web.eecs.umich.edu/~mihalcea/papers/mihalcea.emnlp04.pdf)
- 구현 파일: `dev/Agent_1_News_Analyzer/utils/textrank.py`
- 설정 파일: `dev/Agent_1_News_Analyzer/config.py`
- LLM 관련성 탐지기: `dev/Agent_1_News_Analyzer/utils/llm_relevance_detector.py`
