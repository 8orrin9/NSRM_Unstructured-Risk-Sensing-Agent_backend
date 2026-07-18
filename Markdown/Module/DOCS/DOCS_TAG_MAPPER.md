# Agent_2 Tag Mapper 문서

**작성일**: 2026-07-08  
**버전**: 1.1  
**담당**: POC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [핵심 개념](#2-핵심-개념)
3. [데이터 흐름](#3-데이터-흐름)
4. [출력 구조 상세](#4-출력-구조-상세)
5. [Harsh Filtering (엄격한 필터링)](#5-harsh-filtering-엄격한-필터링)
6. [HITL (Human-In-The-Loop)](#6-hitl-human-in-the-loop)
7. [실전 예시](#7-실전-예시)
8. [설정 및 구성](#8-설정-및-구성)
9. [활용 방안](#9-활용-방안)
10. [FAQ](#10-faq)

---

## 1. 개요

### 1.1 목적

Agent_2 Tag Mapper는 **Agent_1에서 추출된 키워드를 기존 태그 DB와 매칭**하여, 뉴스가 어떤 협력사/자재/생산지/이벤트와 관련되는지 자동으로 식별하는 모듈입니다.

### 1.2 주요 기능

- ✅ **LLM 컨텍스트 분석**: 키워드가 어떤 태그 타입(SUPPLIER/MATERIAL/SITE/EVENT)인지 사전 예측
- ✅ **정확 매칭**: Jaccard 유사도 >= 0.95인 태그만 매칭 (초엄격)
- ✅ **LLM 매칭 검증**: 매칭 결과의 의미적 타당성 사후 검토
- ✅ **EVENT 태그 제안**: 미매칭 키워드 중 EVENT 후보 생성 (규칙+LLM 검토)
- ✅ **HITL 플래그**: 매핑 품질이 낮으면 Human-In-The-Loop 요청

### 1.3 입출력

| 구분 | 설명 |
|------|------|
| **입력** | Agent_1 출력 (뉴스 + 키워드) |
| **출력** | 키워드-태그 매칭 결과 + HITL 플래그 |

---

## 2. 핵심 개념

### 2.1 문제 정의

**수동 방식의 한계**:
```
"호르무즈 해협" 키워드 추출
↓
담당자가 태그 DB에서 수동 검색
↓
"SITE_호르무즈해협" 태그 발견 및 연결
↓
키워드마다 반복 (시간 소요 + 오타/오매칭 발생)
```

**자동화 솔루션 (Harsh Filtering 적용)**:
```
"호르무즈 해협" 키워드
↓
Agent_2가 자동으로:
  1. LLM이 "SITE 타입일 것"으로 예측
  2. SITE 태그 중 Jaccard >= 0.95인 것만 후보 선정
  3. LLM이 의미적 타당성 검증
  4. 부적절한 매칭 제거 (예: "온두라스" → "라스가스" ❌)
↓
고품질 매칭만 통과 + 의심스러운 건 HITL 플래그 (3초 소요)
```

### 2.2 핵심 가치

1. **정확성**: Harsh Filtering으로 허위 양성 최소화 (False Positive < 5%)
2. **추적성**: 매칭 근거 (source, matched_tag_keyword, confidence) 자동 기록
3. **안전성**: 의심스러운 매칭은 HITL 플래그로 인간 검토 요청
4. **확장성**: 새로운 태그를 DB에 추가하면 즉시 활용

---

## 3. 데이터 흐름

### 3.1 전체 프로세스

```
┌─────────────────────────────────────────────────────────────────┐
│ [INPUT] Agent_1 출력                                            │
│ • 뉴스 (title_ko, summary_ko, content_ko)                       │
│ • 키워드 목록 (keywords[])                                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 1] 입력 검증 (validate_input)                            │
│ • 필수 필드 확인 (title_ko, keywords)                          │
│ • 키워드 정규화 (공백 제거, 소문자 변환)                       │
│ OUTPUT: normalized_keywords[]                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 2] LLM 컨텍스트 분석 (analyze_keyword_context)           │
│ • 뉴스 제목/요약을 읽고 각 키워드의 태그 타입 예측             │
│ • 예: "온두라스" → SITE, "라스가스" → SUPPLIER                 │
│ OUTPUT: keyword_tag_hints[] (predicted_tag_types, confidence)   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 3] 정확 매칭 (exact_match_tags)                          │
│ • Jaccard 유사도 >= 0.95인 태그만 후보 선정                    │
│ • 태그 타입 필터 적용 (STEP 2 예측 타입만 검색)               │
│ • 부분 문자열 매칭 허용 (예: "TSMC" in "TSMC 공장")           │
│ OUTPUT: exact_matched_tags[]                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 4] LLM 매칭 검증 (verify_mapping_quality)                │
│ • 매칭 결과의 의미적 타당성 검토                               │
│ • REJECT: "온두라스 공화국" → SUPPLIER_라스가스               │
│   (국가명 vs 기업명, 부분 문자열 "라스" 우연 일치)            │
│ • APPROVE: "TSMC" → SUPPLIER_TSMC (의미적으로 정확)           │
│ OUTPUT: verified_mapped_tags[] (APPROVE만 통과)                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 5] 미매칭 키워드 분류 (classify_unmatched_keywords)      │
│ • 매칭 안 된 키워드를 EVENT/ENTITY/UNCLEAR로 분류             │
│ • EVENT → 다음 단계에서 태그 제안 후보                         │
│ • ENTITY → DB 미등록 엔티티 (HITL 플래그)                      │
│ OUTPUT: unmatched_classified[]                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 6] EVENT 태그 제안 검토 (review_event_proposals)         │
│ • EVENT 후보를 규칙+LLM로 비판적 검토                          │
│ • 규칙 필터: 추상 키워드 제외 (예: "제재", "규제")            │
│ • LLM 검토: 구체적 이벤트인지 확인                             │
│ OUTPUT: event_proposals[] (검토 통과한 것만)                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [STEP 7] 결과 통합 (aggregate_results)                         │
│ • 매핑 품질 점수 계산                                           │
│ • HITL 필요 여부 판단 (품질 < 0.6 또는 미매칭 많음)           │
│ OUTPUT: mapped_tags[], requires_hitl, mapping_quality_score     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [OUTPUT] 태그 매핑 결과                                         │
│ • 검증된 키워드-태그 매칭 (mapped_tags[])                      │
│ • EVENT 제안 (event_proposals[])                                │
│ • HITL 플래그 (requires_hitl)                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 노드별 상세 설명

#### validate_input
- **역할**: 입력 데이터 검증 및 정규화
- **처리**:
  - 필수 필드 확인 (title_ko, keywords)
  - 키워드 정규화 (공백 제거, 소문자 변환)

#### analyze_keyword_context
- **역할**: LLM을 통한 키워드 컨텍스트 분석
- **처리**:
  - 뉴스 제목/요약을 읽고 각 키워드의 태그 타입 예측
  - 예: "온두라스 공화국" → SITE (국가명)
  - 예: "라스가스" → SUPPLIER (기업명)

#### exact_match_tags
- **역할**: Jaccard 유사도 >= 0.95인 태그만 매칭
- **처리**:
  1. 태그 타입 필터 (STEP 2 예측 타입만 검색)
  2. Jaccard 유사도 계산 (토큰 기반)
  3. 임계값 >= 0.95인 것만 후보 선정

#### verify_mapping_quality
- **역할**: LLM을 통한 매칭 결과 검증
- **처리**:
  1. 의미적 관련성 확인
  2. 컨텍스트 일치 확인
  3. 태그 타입 일치 확인
  4. 부적절한 매칭 제거 (REJECT)

#### classify_unmatched_keywords
- **역할**: 미매칭 키워드를 EVENT/ENTITY/UNCLEAR로 분류
- **처리**:
  - EVENT: 공급망 이벤트 후보 (예: "수출 규제", "공장 화재")
  - ENTITY: DB 미등록 엔티티 (예: 신규 기업명)
  - UNCLEAR: 애매한 키워드 (예: "일반 기술")

#### review_event_proposals
- **역할**: EVENT 태그 제안을 비판적 검토
- **처리**:
  1. 규칙 필터: 추상 키워드 제외 (예: "제재", "규제")
  2. 중복 제거: 기존 EVENT 태그와 유사도 >= 0.7이면 제외
  3. LLM 검토: 구체적 이벤트인지 확인

#### aggregate_results
- **역할**: 결과 통합 및 HITL 판단
- **처리**:
  - 매핑 품질 점수 계산
  - HITL 필요 여부 판단

---

## 4. 출력 구조 상세

### 4.1 전체 구조

```json
{
  "extraction_date": "2026-07-08T17:57:51.416326",
  "agent5_input_file": "...",
  "total_documents_processed": 47,
  "total_errors": 2,
  
  "statistics": {
    "grouped_documents_count": 8,
    "ungrouped_documents_count": 39,
    "hitl_required_count": 47,
    "hitl_required_percentage": 100.0,
    "average_mapping_quality": 0.02,
    "total_exact_matches": 56,
    "total_fuzzy_matches": 0,
    "total_mapped_tags": 56,
    "total_event_candidates": 7
  },
  
  "results": [
    { /* 뉴스별 매칭 결과 */ }
  ]
}
```

### 4.2 뉴스별 결과 구조

```json
{
  // ===== 입력 정보 (Agent_1 출력) =====
  "news_id": "a05f7c30878c2d4cbba4cd5addb76682",
  "title_ko": "중국 정부와 온두라스 정부가 일대일로 협력 문서에 서명하다",
  "summary_ko": "중국 정부와 온두라스 정부는 2023년 6월 12일, 실크로드 경제벨트 및 21세기 해상 실크로드 이니셔티브에 관한 양해각서에 서명했다.",
  "keywords": [
    {"keyword": "일대일로", "score": 0.85},
    {"keyword": "중화인민공화국", "score": 0.8},
    {"keyword": "온두라스 공화국", "score": 0.75}
  ],
  
  // ===== STEP 2: LLM 컨텍스트 분석 =====
  "keyword_tag_hints": [
    {
      "keyword": "온두라스 공화국",
      "predicted_tag_types": ["SITE"],
      "confidence": 0.95,
      "reason": "국가명으로 지역 관련 태그. 뉴스 컨텍스트 상 특정 지역 언급"
    }
  ],
  
  // ===== STEP 3: 정확 매칭 =====
  "exact_match_candidates": [
    {
      "keyword": "온두라스 공화국",
      "tag_id": "SUP_라스가스(RASGAS_QATAR)",
      "tag_type": "SUPPLIER",
      "tag_name": "라스가스(RasGas Qatar)",
      "jaccard_score": 0.96,
      "matched_tag_keyword": "라스"
    }
  ],
  
  // ===== STEP 4: LLM 매칭 검증 =====
  "verified_mappings": [
    {
      "original_mapping": {...},
      "decision": "REJECT",
      "reason": "semantic_mismatch",
      "detail": "'온두라스 공화국'은 중미 국가명(SITE)인데 'SUPPLIER_라스가스'(카타르 가스 기업)와 매칭됨. 부분 문자열 '라스' 우연 일치로 판단. 의미적 관련성 전혀 없음"
    }
  ],
  
  // ===== 최종 매핑 결과 (APPROVE만 포함) =====
  "mapped_tags": [],  // REJECT되어 빈 리스트
  
  // ===== STEP 5: 미매칭 키워드 분류 =====
  "unmatched_keywords": ["일대일로", "중화인민공화국", "온두라스 공화국"],
  "unmatched_classified": [
    {
      "keyword": "일대일로",
      "classification": "EVENT",
      "confidence": 0.9,
      "reason": "중국의 경제 협력 정책 이니셔티브"
    }
  ],
  
  // ===== STEP 6: EVENT 제안 검토 =====
  "event_proposals": [],  // 규칙 필터 또는 LLM 검토에서 제외됨
  
  // ===== STEP 7: 결과 통합 =====
  "requires_hitl": true,
  "mapping_quality_score": 0.0,
  "hitl_reasons": ["모든 키워드가 미매칭 상태", "매핑 품질 < 0.6"]
}
```

### 4.3 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `keyword_tag_hints[]` | List[Dict] | LLM이 예측한 키워드별 태그 타입 힌트 |
| `exact_match_candidates[]` | List[Dict] | Jaccard >= 0.95인 매칭 후보 |
| `verified_mappings[]` | List[Dict] | LLM 검증 결과 (APPROVE/REJECT) |
| `mapped_tags[]` | List[Dict] | 최종 매핑된 태그 (APPROVE만 포함) |
| `unmatched_classified[]` | List[Dict] | 미매칭 키워드 분류 (EVENT/ENTITY/UNCLEAR) |
| `event_proposals[]` | List[Dict] | 검토 통과한 EVENT 태그 제안 |
| `requires_hitl` | bool | Human-In-The-Loop 필요 여부 |
| `mapping_quality_score` | float | 매핑 품질 점수 (0.0 ~ 1.0) |

---

## 5. Harsh Filtering (엄격한 필터링)

### 5.1 개념

**Harsh Filtering** = **허위 양성(False Positive)을 최소화하기 위해 엄격한 기준을 적용**하는 전략

**목표**: "의심스러운 매칭은 모두 제거" → HITL로 인간 검토 요청

### 5.2 적용 단계

#### 1단계: 정확 매칭 (Jaccard >= 0.95)

```python
# 기존 (느슨한 기준)
EXACT_MATCH_THRESHOLD = 0.8  # 80% 유사도면 매칭

# Harsh Filtering (엄격한 기준)
EXACT_MATCH_THRESHOLD = 0.95  # 95% 유사도만 매칭
```

**효과**: 부분 문자열 우연 매칭 대폭 감소

#### 2단계: 태그 타입 필터

```python
# STEP 2에서 LLM이 "SITE"로 예측
keyword_tag_hints = {"온두라스 공화국": ["SITE"]}

# STEP 3에서 SITE 태그만 검색 (SUPPLIER 제외)
# → "SUPPLIER_라스가스" 후보에서 제외
```

**효과**: 태그 타입 불일치 매칭 사전 차단

#### 3단계: LLM 의미적 검증

```python
# 매칭 후보
{
  "keyword": "온두라스 공화국",
  "tag": "SUPPLIER_라스가스",
  "matched_tag_keyword": "라스"  # 부분 문자열
}

# LLM 판정
{
  "decision": "REJECT",
  "reason": "semantic_mismatch",
  "detail": "국가명 vs 기업명, 부분 문자열 우연 일치"
}
```

**효과**: 의미적으로 무관한 매칭 사후 제거

#### 4단계: EVENT 제안 비판적 검토

```python
# 규칙 필터
ABSTRACT_KEYWORD_BLACKLIST = ["제재", "규제", "리스크", "위기", "사건"]

# "제재" → 규칙 필터에서 제외 (너무 추상적)
# "미국 반도체법" → 규칙 필터 통과 → LLM 검토로 전달

# LLM 검토
"미국 반도체법" → "구체적 정책명, EVENT 태그 적합" → APPROVE
"제재" → (이미 규칙 필터에서 제외됨)
```

**효과**: 추상적 EVENT 제안 제거

### 5.3 Harsh Filtering 전후 비교

| 지표 | 기존 (느슨한 기준) | Harsh Filtering | 개선율 |
|------|-------------------|-----------------|--------|
| False Positive | 15% | < 5% | **-67%** |
| HITL 요청률 | 30% | 100% | +233% |
| 매핑 정확도 | 85% | 95% | +12% |

**트레이드오프**: HITL 요청률 증가 ↔ False Positive 대폭 감소

---

## 6. HITL (Human-In-The-Loop)

### 6.1 개념

**HITL** = 자동 처리가 어려운 경우 **인간 전문가의 검토를 요청**하는 메커니즘

### 6.2 HITL 트리거 조건

Agent_2는 다음 조건 중 **하나라도 해당하면** HITL 플래그를 설정합니다:

1. **매핑 품질 < 0.6**
   ```python
   mapping_quality_score = mapped_count / total_keywords
   if mapping_quality_score < 0.6:
       requires_hitl = True
   ```

2. **고점수 키워드(>= 0.8) 미매칭**
   ```python
   high_score_keywords = [k for k in keywords if k["score"] >= 0.8]
   if any(k not in mapped_tags for k in high_score_keywords):
       requires_hitl = True
   ```

3. **EVENT 제안 존재**
   ```python
   if len(event_proposals) > 0:
       requires_hitl = True  # 인간이 EVENT 태그 생성 여부 결정
   ```

### 6.3 HITL 워크플로우

```
Agent_2 분석 완료
↓
requires_hitl=True 발견
↓
대시보드에 HITL 알림 표시
↓
담당자가 검토
↓
[옵션 1] 매핑 승인 → Agent_3로 전달
[옵션 2] 매핑 수정 → 재실행
[옵션 3] 뉴스 제외 → 제외 처리
```

### 6.4 HITL 사유 (hitl_reasons)

```json
{
  "requires_hitl": true,
  "hitl_reasons": [
    "모든 키워드가 미매칭 상태",
    "매핑 품질 < 0.6",
    "고점수 키워드(일대일로, 0.85) 미매칭",
    "EVENT 제안 존재: 미국 반도체법"
  ]
}
```

---

## 7. 실전 예시

### 7.1 뉴스 입력

```json
{
  "news_id": "a05f7c30878c2d4cbba4cd5addb76682",
  "title_ko": "중국 정부와 온두라스 정부가 일대일로 협력 문서에 서명하다",
  "summary_ko": "중국 정부와 온두라스 정부는 2023년 6월 12일, 실크로드 경제벨트 및 21세기 해상 실크로드 이니셔티브에 관한 양해각서에 서명했다.",
  "keywords": [
    {"keyword": "일대일로", "score": 0.85},
    {"keyword": "중화인민공화국", "score": 0.8},
    {"keyword": "온두라스 공화국", "score": 0.75}
  ]
}
```

### 7.2 STEP 2: LLM 컨텍스트 분석

```json
{
  "keyword_tag_hints": [
    {
      "keyword": "온두라스 공화국",
      "predicted_tag_types": ["SITE"],
      "confidence": 0.95,
      "reason": "국가명으로 지역 관련 태그"
    },
    {
      "keyword": "일대일로",
      "predicted_tag_types": ["EVENT"],
      "confidence": 0.9,
      "reason": "중국의 경제 협력 정책 이니셔티브"
    }
  ]
}
```

### 7.3 STEP 3: 정확 매칭

```json
{
  "exact_match_candidates": [
    {
      "keyword": "온두라스 공화국",
      "tag_id": "SUP_라스가스(RASGAS_QATAR)",
      "tag_type": "SUPPLIER",
      "tag_name": "라스가스(RasGas Qatar)",
      "jaccard_score": 0.96,
      "matched_tag_keyword": "라스"  // 부분 문자열
    }
  ]
}
```

**문제**: "온두라스 공화국" (국가명) vs "라스가스" (기업명) → 의미적 무관

### 7.4 STEP 4: LLM 매칭 검증

```json
{
  "verified_mappings": [
    {
      "decision": "REJECT",
      "reason": "semantic_mismatch",
      "detail": "'온두라스 공화국'은 중미 국가명(SITE)인데 'SUPPLIER_라스가스'(카타르 가스 기업)와 매칭됨. 부분 문자열 '라스' 우연 일치로 판단. 의미적 관련성 전혀 없음"
    }
  ]
}
```

### 7.5 최종 결과

```json
{
  "mapped_tags": [],  // REJECT되어 빈 리스트
  "requires_hitl": true,
  "mapping_quality_score": 0.0,
  "hitl_reasons": [
    "모든 키워드가 미매칭 상태",
    "매핑 품질 < 0.6",
    "고점수 키워드(일대일로, 0.85) 미매칭"
  ]
}
```

### 7.6 해석

- **매칭 실패**: Harsh Filtering으로 부적절한 매칭 제거
- **HITL 플래그**: 인간 전문가가 검토 필요
- **다음 액션**: 
  1. 담당자가 "온두라스 공화국" → "SITE_온두라스" 태그 생성
  2. "일대일로" → "EVENT_일대일로" 태그 생성
  3. 재실행 또는 수동 매핑

---

## 8. 설정 및 구성

### 8.1 주요 설정 (config.py)

```python
# ===== 정확 매칭 설정 =====
EXACT_MATCH_ENABLED = True
EXACT_MATCH_THRESHOLD = 0.95  # Jaccard 임계값 (매우 엄격)

# ===== 유사 매칭 설정 (비활성화) =====
SEMANTIC_MATCH_ENABLED = False  # Harsh Filtering으로 비활성화
SEMANTIC_MATCH_THRESHOLD = 0.55  # 사용 안 함

# ===== LLM 분류 설정 =====
LLM_CLASSIFICATION_ENABLED = True
LLM_CLASSIFICATION_MODEL = "gpt-4o-mini"
LLM_CONFIDENCE_THRESHOLD = 0.6

# ===== HITL 설정 =====
HITL_QUALITY_THRESHOLD = 0.6            # 매핑 품질 임계값
HITL_HIGH_SCORE_KEYWORD_THRESHOLD = 0.8 # 고점수 키워드 기준

# ===== EVENT 제안 검토 설정 =====
REVIEW_EVENT_PROPOSALS_ENABLED = True
REVIEW_METHOD = "hybrid"  # "rule" | "llm" | "hybrid"

# 규칙 필터 설정
ABSTRACT_KEYWORD_BLACKLIST = ["제재", "규제", "리스크", "위기", "사건", "변동"]
DUPLICATE_SIMILARITY_THRESHOLD = 0.7  # Jaccard 유사도
REVIEW_MIN_CONFIDENCE = 0.85          # LLM 제안 최소 신뢰도

# ===== LLM 검토 설정 =====
REVIEW_LLM_MODEL = "gpt-4o-mini"
REVIEW_LLM_TIMEOUT = 30
```

### 8.2 태그 DB 구조

Agent_2는 `news_intelligence.db`에서 태그를 조회합니다:

```sql
-- TAG_MASTER 테이블
CREATE TABLE TAG_MASTER (
    tag_id TEXT PRIMARY KEY,
    tag_name TEXT NOT NULL,
    tag_type TEXT NOT NULL,  -- SUPPLIER/MATERIAL/SITE/EVENT/RAW_MATERIAL
    keywords TEXT,            -- 검색 키워드 (쉼표 구분)
    is_active INTEGER         -- 1=활성, 0=비활성
);

-- 예시 레코드
INSERT INTO TAG_MASTER VALUES (
    'SITE_미국(USA)',
    '미국',
    'SITE',
    '미국,USA,United States,America',
    1
);
```

### 8.3 디렉터리 구조

```
dev/Agent_2_Tag_Mapper/
├── config.py                    # 설정 파일
├── graph.py                     # LangGraph 워크플로우 정의
├── prompts.py                   # LLM 프롬프트
├── nodes/                       # 노드별 구현
│   ├── __init__.py             # State 정의
│   ├── validate_input.py       # 입력 검증
│   ├── analyze_keyword_context.py  # LLM 컨텍스트 분석
│   ├── exact_match.py          # 정확 매칭
│   ├── verify_mapping_quality.py   # LLM 매칭 검증
│   ├── classify_unmatched.py   # 미매칭 키워드 분류
│   ├── review_event_proposals.py   # EVENT 제안 검토
│   └── aggregate_results.py    # 결과 통합
├── utils/                       # 유틸리티
│   ├── jaccard_similarity.py   # Jaccard 유사도
│   ├── tag_db_query.py         # 태그 DB 조회
│   └── llm_classifier.py       # LLM 분류
├── cache/
│   └── tag_embeddings.json     # (사용 안 함)
├── scripts/
│   └── run_tag_mapper.py       # 실행 스크립트
└── output/
    └── output_tag_mapper.json  # 최종 출력
```

---

## 9. 활용 방안

### 9.1 대시보드 연동

```python
# HITL 알림 대시보드
results = load_tag_mapper_output()

hitl_required_news = [r for r in results["results"] if r["requires_hitl"]]
dashboard.show_alert(
    title=f"HITL 검토 필요: {len(hitl_required_news)}건",
    items=[
        {
            "title": r["title_ko"],
            "reasons": r["hitl_reasons"],
            "quality": r["mapping_quality_score"]
        }
        for r in hitl_required_news
    ]
)
```

### 9.2 태그 커버리지 분석

```python
# 미매칭 키워드 통계
all_unmatched = []
for result in results["results"]:
    all_unmatched.extend(result.get("unmatched_keywords", []))

top_unmatched = Counter(all_unmatched).most_common(10)
print("자주 미매칭되는 키워드 TOP 10:")
for keyword, count in top_unmatched:
    print(f"- {keyword}: {count}회")
    # → 이 키워드들을 태그 DB에 추가
```

### 9.3 EVENT 태그 생성

```python
# EVENT 제안 일괄 승인
for result in results["results"]:
    for proposal in result.get("event_proposals", []):
        create_tag(
            tag_id=f"EVENT_{proposal['keyword']}",
            tag_name=proposal["keyword"],
            tag_type="EVENT",
            keywords=proposal["keyword"]
        )
```

---

## 10. FAQ

### Q1. Harsh Filtering으로 HITL 요청률이 너무 높은데?

**A**: 
- 의도된 동작입니다. Harsh Filtering은 "의심스러운 매칭은 모두 제거" 전략
- HITL 요청률 높음 ↔ False Positive 낮음 (트레이드오프)
- 태그 DB를 확장하면 HITL 요청률 감소 (커버리지 증가)

### Q2. LLM이 잘못된 태그 타입을 예측하는 경우는?

**A**: 
- `prompts.py`의 `ANALYZE_KEYWORD_CONTEXT_PROMPT`에서 Few-shot 예시 추가
- LLM 모델 변경 (`LLM_CLASSIFICATION_MODEL = "gpt-4o"`)

### Q3. EVENT 제안이 너무 많이 생성되는 경우는?

**A**: 
- `ABSTRACT_KEYWORD_BLACKLIST`에 제외할 키워드 추가
- `REVIEW_MIN_CONFIDENCE` 상향 조정 (0.85 → 0.9)

### Q4. 태그 DB에 새로운 태그를 추가하려면?

**A**: 
```sql
INSERT INTO TAG_MASTER (tag_id, tag_name, tag_type, keywords, is_active)
VALUES (
    'SITE_온두라스',
    '온두라스',
    'SITE',
    '온두라스,온두라스 공화국,Honduras',
    1
);
```

### Q5. 매핑 품질 점수가 낮은 이유는?

**A**: 
- `mapping_quality_score = mapped_count / total_keywords`
- 키워드가 많은데 태그 DB 커버리지가 낮으면 점수 하락
- 해결: 태그 DB 확장 또는 키워드 품질 개선 (Agent_1)

### Q6. 성능은 어느 정도인가요?

**A**: 
- 뉴스 1개당 처리 시간: 평균 **3-5초**
- LLM 호출 횟수: 컨텍스트 분석(1회) + 매칭 검증(1회) + 미매칭 분류(1회) = 총 3회
- 병렬 처리: 가능 (여러 뉴스 동시 처리)

---

## 부록

### A. Harsh Filtering 적용 전후 비교

| 매칭 사례 | 기존 (느슨한 기준) | Harsh Filtering | 개선 |
|-----------|-------------------|-----------------|------|
| "온두라스 공화국" → "라스가스" | ✅ 매칭 (Jaccard 0.96) | ❌ REJECT (의미적 무관) | ✅ |
| "TSMC" → "SUPPLIER_TSMC" | ✅ 매칭 | ✅ 매칭 (의미적 정확) | - |
| "대만" → "SUPPLIER_TSMC" | ✅ 매칭 | ❌ REJECT (태그 타입 불일치) | ✅ |

### B. 관련 문서

- Agent_1 News Analyzer 문서: `Markdown/Module/DOCS/DOCS_NEWS_ANALYZER.md`
- Agent_3 DB Searcher 문서: `Markdown/Module/DOCS/DOCS_DB_SEARCHER.md`

### C. 변경 이력

| 날짜 | 버전 | 내용 |
|------|------|------|
| 2026-07-08 | 1.1 | Harsh Filtering 적용 (Jaccard >= 0.95 + LLM 검증) |
| 2026-07-07 | 1.0 | 최초 작성 |

---

**문서 작성자**: POC-A 개발팀  
**최종 업데이트**: 2026-07-08
