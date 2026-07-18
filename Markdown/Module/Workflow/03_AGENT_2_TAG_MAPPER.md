# Agent_2: Tag Mapper (태그 매핑 모듈)

## 목차
- [개요](#개요)
- [워크플로우](#워크플로우)
- [State 구조](#state-구조)
- [기능별 상세 설명](#기능별-상세-설명)

---

## 개요

### 모듈 역할
Agent_2는 **Agent_1이 추출한 키워드를 태그 DB와 매핑**하고, 매칭 실패한 키워드는 신규 EVENT 태그로 제안하는 모듈입니다.

### 파이프라인 위치
```
Agent_1 (News Analyzer) → [Agent_2: Tag Mapper] → Agent_3 (DB Searcher)
```

### 주요 기능 (7개)
1. **입력 검증** (`validate_input`)
2. **키워드 컨텍스트 분석** (`analyze_keyword_context`) - LLM 태그 타입 예측
3. **정확 매칭** (`exact_match_tags`) - Jaccard >= 0.95
4. **매핑 품질 검증** (`verify_mapping_quality`) - LLM 의미적 검증
5. **미매칭 분류** (`classify_unmatched_keywords`) - EVENT/ENTITY/UNCLEAR 분류
6. **EVENT 제안 검토** (`review_event_proposals`) - 규칙+LLM 하이브리드 검토
7. **결과 통합** (`aggregate_results`) - HITL 판단

---

## 워크플로우

```
validate_input
    ↓
analyze_keyword_context
    ↓
exact_match_tags
    ↓
verify_mapping_quality
    ↓
classify_unmatched_keywords
    ↓
review_event_proposals
    ↓
aggregate_results
    ↓
END
```

---

## State 구조

### 입력 필드 (Agent_1로부터)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `news_id` | str | 뉴스 ID |
| `title_ko` | str | 제목 (한글) |
| `summary_ko` | str | 요약 (한글) |
| `keywords` | List[Dict] | Agent_1 추출 키워드 |

### 출력 필드 (Agent_2 생성)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `mapped_tags` | List[Dict] | 최종 매핑된 태그 |
| `mapping_quality_score` | float | 매핑 품질 (0.0~1.0) |
| `requires_hitl` | bool | HITL 필요 여부 |
| `hitl_reason` | str | HITL 필요 이유 |
| `keyword_tag_hints` | List[Dict] | LLM 예상 태그 타입 |
| `exact_matched_tags` | List[Dict] | 정확 매칭 결과 |
| `rejected_mappings` | List[Dict] | 검증 실패 매칭 |
| `unmatched_keywords` | List[str] | 미매칭 키워드 |
| `potential_event_tags` | List[Dict] | 신규 EVENT 태그 제안 |

---

## 기능별 상세 설명

### 1. validate_input (입력 검증)

#### 📋 설명
키워드 입력을 검증하고 정규화합니다.

#### 🤖 사용 모델
LLM 호출 없음

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `keywords` | List[Dict] | Agent_1 추출 키워드 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `keywords` | List[Dict] | 정규화된 키워드 (중복 제거) |

#### 정규화 규칙
- 소문자 변환
- 공백 제거
- 중복 제거 (정규화된 값 기준)

#### 📝 예시

**입력**:
```json
{
  "keywords": [
    {"keyword": " 희토류 ", "score": 0.95},
    {"keyword": "희토류", "score": 0.90},  // 중복
    {"keyword": "TSMC", "score": 0.88}
  ]
}
```

**출력**:
```json
{
  "keywords": [
    {"keyword": "희토류", "score": 0.95},
    {"keyword": "TSMC", "score": 0.88}
  ]
}
```

---

### 2. analyze_keyword_context (키워드 컨텍스트 분석)

#### 📋 설명
LLM을 사용하여 각 키워드의 **예상 태그 타입**을 분석합니다 (검색 범위 제한용).

#### 🤖 사용 모델
- **모델**: `gpt-4o-mini`
- **온도**: 0.2 (매우 낮음)
- **타임아웃**: 30초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `keywords` | List[str] | 키워드 배열 |
| `title_ko` | str | 뉴스 제목 |
| `summary_ko` | str | 뉴스 요약 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `keyword_tag_hints` | List[Dict] | 키워드별 예상 태그 타입 |

**keyword_tag_hints 구조**:
```json
[
  {
    "keyword": "희토류",
    "predicted_tag_types": ["MATERIAL"],
    "confidence": 0.95,
    "reason": "반도체 제조 핵심 소재"
  }
]
```

#### 태그 타입 (5개)

| 타입 | 설명 | 예시 |
|------|------|------|
| `SUPPLIER` | 협력사/제조사 | TSMC, 삼성전자, ASML |
| `MATERIAL` | 반도체 소재 | 실리콘 웨이퍼, 포토레지스트, 희토류 |
| `SITE` | 제조 공장/지역/국가 | 대만, 평택 공장, 중국 |
| `EVENT` | 공급망 사건/규제/정책 | OFAC 제재, 지진, 파업 |
| `RAW_MATERIAL` | 1차 원자재 | 구리, 금, 희토류 광석 |

#### 💬 프롬프트

**System**:
```
당신은 반도체 공급망 분석 전문가입니다.
```

**User**:
```
다음 뉴스에서 추출된 키워드들을 분석하여 각 키워드가 어떤 태그 타입일지 예측해주세요.

**뉴스 제목**: {title_ko}
**뉴스 요약**: {summary_ko}
**키워드 목록**: {keywords}

**사용 가능한 태그 타입**:
1. SUPPLIER: 반도체 협력사/제조사 (TSMC, 삼성전자, ASML)
2. MATERIAL: 반도체 소재 (실리콘 웨이퍼, 포토레지스트, 희토류)
3. SITE: 제조 공장/지역/국가 (대만, 평택 공장, 중국)
4. EVENT: 공급망 사건/규제/정책 (OFAC 제재, 지진, 파업)
5. RAW_MATERIAL: 1차 원자재 (구리, 금, 희토류 광석)

**분석 지침**:
- 키워드 단독이 아닌 뉴스 컨텍스트를 함께 고려
- 하나의 키워드가 여러 타입에 해당할 수 있음 (우선순위 순)
- 지역명/국가명 → SITE
- 기업명/조직명 → SUPPLIER
- 사건/정책명 → EVENT
- 소재명/물질명 → MATERIAL

**출력 형식 (JSON)**:
{
  "keyword_hints": [
    {
      "keyword": "희토류",
      "predicted_tag_types": ["MATERIAL", "RAW_MATERIAL"],
      "confidence": 0.95,
      "reason": "반도체 제조 핵심 소재"
    }
  ]
}
```

#### 📝 예시

**입력**:
```json
{
  "title_ko": "중국, 희토류 대미 수출 중단",
  "summary_ko": "중국 정부가 미국에 대한 희토류 수출을 전면 중단...",
  "keywords": ["희토류", "중국", "수출 규제"]
}
```

**출력**:
```json
{
  "keyword_tag_hints": [
    {
      "keyword": "희토류",
      "predicted_tag_types": ["MATERIAL", "RAW_MATERIAL"],
      "confidence": 0.95,
      "reason": "반도체 제조 핵심 소재"
    },
    {
      "keyword": "중국",
      "predicted_tag_types": ["SITE"],
      "confidence": 0.92,
      "reason": "국가명, 생산지 관련"
    },
    {
      "keyword": "수출 규제",
      "predicted_tag_types": ["EVENT"],
      "confidence": 0.98,
      "reason": "정책/규제 사건"
    }
  ]
}
```

---

### 3. exact_match_tags (정확 매칭)

#### 📋 설명
키워드와 태그 DB를 **Jaccard 유사도**로 정확 매칭합니다 (>= 0.95).

#### 🤖 사용 모델
LLM 호출 없음 (Jaccard 유사도)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `keywords` | List[str] | 키워드 배열 |
| `keyword_tag_hints` | List[Dict] | LLM 예상 태그 타입 (검색 범위 제한) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `exact_matched_tags` | List[Dict] | 정확 매칭 결과 |
| `unmatched_keywords` | List[str] | 미매칭 키워드 |

**exact_matched_tags 구조**:
```json
[
  {
    "keyword": "희토류",
    "tag_id": "MAT_RARE_EARTH",
    "tag_name": "희토류",
    "tag_type": "MATERIAL",
    "jaccard_score": 0.98,
    "matched_tag_keyword": "희토류"
  }
]
```

#### Jaccard 유사도 계산

```python
def jaccard_similarity(a: str, b: str) -> float:
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0
```

#### 설정

| 항목 | 값 | 설명 |
|------|-----|------|
| `EXACT_MATCH_THRESHOLD` | 0.95 | Jaccard 임계값 (매우 엄격) |
| `target_region` | "KR" | 한글 태그만 대상 |

#### 📝 예시

**입력**:
```json
{
  "keywords": ["희토류", "수출 규제"],
  "keyword_tag_hints": [
    {"keyword": "희토류", "predicted_tag_types": ["MATERIAL"]},
    {"keyword": "수출 규제", "predicted_tag_types": ["EVENT"]}
  ]
}
```

**태그 DB**:
```json
{
  "MAT_RARE_EARTH": {
    "tag_name": "희토류",
    "tag_type": "MATERIAL",
    "keywords": ["희토류", "레어어스"]
  },
  "EVT_EXPORT_CONTROL": {
    "tag_name": "수출 규제",
    "tag_type": "EVENT",
    "keywords": ["수출규제", "수출 통제"]
  }
}
```

**출력**:
```json
{
  "exact_matched_tags": [
    {
      "keyword": "희토류",
      "tag_id": "MAT_RARE_EARTH",
      "tag_name": "희토류",
      "tag_type": "MATERIAL",
      "jaccard_score": 1.0,
      "matched_tag_keyword": "희토류"
    },
    {
      "keyword": "수출 규제",
      "tag_id": "EVT_EXPORT_CONTROL",
      "tag_name": "수출 규제",
      "tag_type": "EVENT",
      "jaccard_score": 0.96,
      "matched_tag_keyword": "수출규제"
    }
  ],
  "unmatched_keywords": []
}
```

---

### 4. verify_mapping_quality (매핑 품질 검증)

#### 📋 설명
정확 매칭 결과의 **의미적 타당성**을 LLM으로 검증합니다 (부분 문자열 오류 방지).

#### 🤖 사용 모델
- **모델**: `gpt-5.5` (복잡한 추론 필요: 의미적 관련성, 컨텍스트 일치, 부분 문자열 오류 감지)
- **온도**: 0.2
- **타임아웃**: 60초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `exact_matched_tags` | List[Dict] | 정확 매칭 결과 |
| `title_ko` | str | 뉴스 제목 |
| `content_ko` | str | 뉴스 본문 (2000자 제한) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `exact_matched_tags` | List[Dict] | 검증 통과 매칭 |
| `rejected_mappings` | List[Dict] | 검증 실패 매칭 |

#### 검증 기준

1. **의미적 관련성**: 키워드 ↔ 태그가 의미적으로 관련
2. **컨텍스트 일치**: 뉴스 내용에서 태그 언급 가능성
3. **태그 타입 일치**: SUPPLIER/MATERIAL/SITE/EVENT 적합성
4. **부분 문자열 오류 방지**: "온두라스 공화국" → "라스가스" (부분 매칭) 거부

#### 💬 프롬프트

**System**:
```
당신은 반도체 공급망 태그 매핑 품질 검증 전문가입니다.
```

**User**:
```
다음 뉴스에서 추출된 키워드-태그 매칭 결과를 검토하여 의미적으로 타당한지 판단해주세요.

**뉴스 제목**: {title_ko}

**뉴스 본문**:
{content_ko}

**매칭 결과**:
{mappings}

**검증 기준**:
1. 의미적 관련성: 키워드와 태그가 의미적으로 관련이 있는가?
2. 컨텍스트 일치: 뉴스 제목/본문 컨텍스트에서 해당 매칭이 타당한가?
3. 태그 타입 일치: 키워드의 성격과 태그 타입이 일치하는가?
4. 부분 문자열 오류: 부분 문자열 우연 매칭이 아닌가?

**출력 형식 (JSON)**:
{
  "verified_mappings": [
    {
      "original_mapping": {...},
      "decision": "APPROVE",
      "reason": "semantically_valid",
      "detail": "설명"
    }
  ]
}
```

#### 📝 예시

**입력**:
```json
{
  "exact_matched_tags": [
    {
      "keyword": "온두라스 공화국",
      "tag_id": "SUPPLIER_LASGAS",
      "tag_name": "라스가스",
      "matched_tag_keyword": "라스"  // 부분 매칭!
    }
  ],
  "title_ko": "온두라스 공화국, 대만과 외교 단절",
  "content_ko": "중미 국가 온두라스가 대만과의 외교 관계를 단절하고 중국과 수교한다고 발표했다. 온두라스 정부는 '하나의 중국' 원칙을 인정하며..."
}
```

**출력**:
```json
{
  "exact_matched_tags": [],
  "rejected_mappings": [
    {
      "keyword": "온두라스 공화국",
      "tag_id": "SUPPLIER_LASGAS",
      "decision": "REJECT",
      "reason": "semantic_mismatch",
      "detail": "'온두라스 공화국'은 중미 국가명(SITE)인데 'SUPPLIER_라스가스'(카타르 가스 기업)와 매칭됨. 부분 문자열 '라스' 우연 일치. 의미적 관련성 없음"
    }
  ]
}
```

---

### 5. classify_unmatched_keywords (미매칭 키워드 분류)

#### 📋 설명
미매칭 키워드를 **EVENT/ENTITY/UNCLEAR**로 LLM 분류합니다.

#### 🤖 사용 모델
- **모델**: `gpt-4o-mini`
- **온도**: 0.3
- **타임아웃**: 30초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `unmatched_keywords` | List[str] | 미매칭 키워드 |
| `title_ko` | str | 뉴스 제목 |
| `summary_ko` | str | 뉴스 요약 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `potential_event_tags` | List[Dict] | EVENT 분류 결과 (신규 태그 제안) |

**potential_event_tags 구조**:
```json
[
  {
    "keyword": "수출 규제 강화",
    "category": "EVENT",
    "confidence": 0.95,
    "reason": "정책적 사건으로 공급망 영향",
    "suggested_tag_name": "EVT_수출규제"
  }
]
```

#### 분류 기준

| 카테고리 | 설명 | 처리 |
|----------|------|------|
| **EVENT** | 수출 규제, 지진, 파업, 제재 등 | 신규 태그 제안 |
| **ENTITY** | 기업명, 소재명, 지역명 | DB 추가 필요 (제안 안 함) |
| **UNCLEAR** | 범용 단어 또는 부적절 | 무시 |

#### 💬 프롬프트

**System**:
```
당신은 공급망 리스크 분석 전문가입니다.
```

**User**:
```
다음 뉴스에서 추출된 키워드들이 기존 태그 DB와 매칭되지 않았습니다.
각 키워드를 EVENT(이벤트), ENTITY(엔티티명), UNCLEAR(불명확)로 분류해주세요.

**뉴스 제목**: {title_ko}
**뉴스 요약**: {summary_ko}
**미매칭 키워드**: {unmatched_keywords}

**분류 기준**:
1. EVENT: 수출 규제, 지진, 파업, 제재 등 사건/현상/규제
2. ENTITY: 기업명, 소재명, 지역명 (DB에 먼저 추가 필요)
3. UNCLEAR: 범용 단어 또는 태그로 부적절

**출력 형식 (JSON)**:
{
  "classifications": [
    {
      "keyword": "수출 규제 강화",
      "category": "EVENT",
      "confidence": 0.95,
      "reason": "정책적 사건",
      "suggested_tag_name": "EVT_수출규제"
    }
  ]
}
```

#### 📝 예시

**입력**:
```json
{
  "unmatched_keywords": ["수출 규제 강화", "ABC회사", "증가"],
  "title_ko": "중국, 수출 규제 강화 발표",
  "summary_ko": "..."
}
```

**출력**:
```json
{
  "potential_event_tags": [
    {
      "keyword": "수출 규제 강화",
      "category": "EVENT",
      "confidence": 0.95,
      "reason": "정책적 사건으로 공급망 영향",
      "suggested_tag_name": "EVT_수출규제"
    }
  ]
}
```

---

### 6. review_event_proposals (EVENT 제안 검토)

#### 📋 설명
EVENT 태그 제안을 **규칙+LLM 하이브리드 검토**로 승인/거부합니다.

#### 🤖 사용 모델
- **모델**: `gpt-5.5` (복잡한 추론 필요: 키워드 중복 검사, 의미적 중복, 조합 가능성 판단)
- **온도**: 0.2
- **타임아웃**: 60초
- **방법**: `hybrid` (규칙 기반 필터 → LLM 검토)
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `potential_event_tags` | List[Dict] | EVENT 분류 결과 |
| `existing_event_tags` | List[Dict] | 기존 EVENT 태그 전체 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `potential_event_tags` | List[Dict] | 최종 승인된 제안 |
| `rejected_event_proposals` | List[Dict] | 거부된 제안 |

#### 검토 단계

**1단계: 규칙 기반 필터**

| 규칙 | 설명 | 예시 (거부) |
|------|------|-------------|
| 추상 단어 블랙리스트 | "제재", "규제", "리스크" 등 | "제재" → 너무 광범위 |
| Confidence < 0.85 | 신뢰도 부족 | confidence=0.6 |
| 기존 키워드 완전 일치 | 이미 존재 | "OFAC 제재" 이미 있음 |
| 기존 태그 높은 유사도 | 유사도 >= 0.7 | "경제 제재" ≈ "OFAC 제재" |

**2단계: LLM 검토** (규칙 통과한 것만)

| 검토 항목 | 설명 |
|-----------|------|
| 키워드 중복 | 기존 태그의 keywords 배열에 이미 존재? |
| 의미적 중복 | 기존 태그와 의미적으로 중복? |
| 너무 광범위? | 상위 개념? |
| 일회성 사건? | 재사용 가능성 낮음? |
| 기존 조합 가능? | 여러 태그 조합으로 표현 가능? |

#### 💬 프롬프트

**System**:
```
당신은 공급망 태그 관리 전문가입니다.
```

**User**:
```
LLM이 제안한 EVENT 태그 후보들을 비판적으로 검토하여 승인/거부를 결정하세요.

**뉴스 컨텍스트**:
제목: {title_ko}
요약: {summary_ko}

**기존 EVENT 태그 (총 {count}개)**:
{existing_tags}

**LLM 제안 태그**:
{proposals}

**검토 기준**:
1. 키워드 중복: 기존 태그의 keywords에 이미 포함?
2. 의미적 중복: 기존 태그와 의미 유사?
3. 너무 광범위?: 상위 개념?
4. 일회성 사건?: 재사용 가능성 낮음?
5. 기존 조합 가능?: 여러 태그 조합으로 표현 가능?

**출력 형식 (JSON)**:
{
  "reviewed_proposals": [
    {
      "keyword": "대만 지진",
      "decision": "APPROVE",
      "reason": "new_specific_event",
      "detail": "기존 태그에 자연재해 없음. 재사용 가능."
    }
  ]
}
```

#### 📝 예시

**입력**:
```json
{
  "potential_event_tags": [
    {"keyword": "APT 공격", "suggested_tag_name": "EVT_APT_공격"},
    {"keyword": "대만 지진", "suggested_tag_name": "EVT_대만지진"}
  ],
  "existing_event_tags": [
    {"tag_id": "EVT_APT_공격", "keywords": ["APT 공격", "사이버 공격"]}
  ]
}
```

**출력**:
```json
{
  "potential_event_tags": [
    {
      "keyword": "대만 지진",
      "decision": "APPROVE",
      "reason": "new_specific_event",
      "suggested_tag_name": "EVT_대만지진"
    }
  ],
  "rejected_event_proposals": [
    {
      "keyword": "APT 공격",
      "decision": "REJECT",
      "reason": "keyword_already_exists",
      "detail": "EVT_APT_공격의 keywords에 'APT 공격' 이미 존재"
    }
  ]
}
```

---

### 7. aggregate_results (결과 통합)

#### 📋 설명
최종 결과를 통합하고 **HITL 필요 여부**를 판단합니다.

#### 🤖 사용 모델
LLM 호출 없음 (조건부 로직)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `exact_matched_tags` | List[Dict] | 검증 통과 매칭 |
| `keywords` | List[Dict] | 원본 키워드 |
| `rejected_mappings` | List[Dict] | 검증 실패 매칭 |
| `potential_event_tags` | List[Dict] | 최종 승인된 EVENT 제안 |
| `unmatched_keywords` | List[str] | 미매칭 키워드 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `mapped_tags` | List[Dict] | 최종 매핑된 태그 |
| `mapping_quality_score` | float | 매핑 품질 (0.0~1.0) |
| `requires_hitl` | bool | HITL 필요 여부 |
| `hitl_reason` | str | HITL 필요 이유 |
| `high_score_event_proposals` | List[Dict] | HITL 대상 고점수 EVENT 제안 |

#### HITL 필요 조건 (단일 조건)

**고점수 키워드 중 EVENT 태그로 분류된 것만 HITL 대상**

| 조건 | 임계값 | 설명 |
|------|--------|------|
| **고점수 EVENT 제안** | `score >= 0.8` | Agent_1이 중요하다고 판단한 키워드(score >= 0.8)가 EVENT 태그로 분류되었을 때만 사용자 확인 필요 |

**HITL 필요 이유**:
- EVENT 태그는 **시간성 사건/정책/규제**를 나타내며, 잘못 추가하면 향후 뉴스 수집에 노이즈 발생
- 고점수 키워드는 **뉴스의 핵심 주제**이므로, 이 둘이 겹치면 신중한 검토 필요
- 예: "WBG 반도체 수출 규제" (score 0.92) → EVENT 태그 제안 → HITL

**HITL 불필요 케이스**:
- 저점수 EVENT 제안 (score < 0.8): 부차적 키워드이므로 무시 가능
- SUPPLIER/MATERIAL/SITE 미매칭: 태그 DB에 추가하면 되므로 HITL 불필요
- 매핑 품질 낮음: 전체적으로 키워드 추출이 부실한 경우이지 개별 태그 검토 불필요

#### 매핑 품질 계산

```python
mapping_quality_score = len(mapped_tags) / len(keywords)
```

**high_score_event_proposals 구조**:
```json
[
  {
    "keyword": "WBG 반도체 수출 규제",
    "score": 0.92,
    "suggested_tag_name": "EVT_WBG반도체수출규제",
    "confidence": 0.88
  }
]
```

#### 📝 예시

**예시 1: HITL 필요 (고점수 EVENT 제안)**

**입력**:
```json
{
  "exact_matched_tags": [
    {"keyword": "희토류", "tag_id": "MAT_RARE_EARTH"}
  ],
  "keywords": [
    {"keyword": "희토류", "score": 0.95},
    {"keyword": "WBG 반도체 수출 규제", "score": 0.92},
    {"keyword": "중국", "score": 0.75}
  ],
  "potential_event_tags": [
    {
      "keyword": "WBG 반도체 수출 규제",
      "category": "EVENT",
      "confidence": 0.88,
      "suggested_tag_name": "EVT_WBG반도체수출규제"
    }
  ]
}
```

**출력**:
```json
{
  "mapped_tags": [
    {"keyword": "희토류", "tag_id": "MAT_RARE_EARTH", "tag_name": "희토류"}
  ],
  "mapping_quality_score": 0.33,
  "requires_hitl": true,
  "hitl_reason": "고점수 EVENT 태그 제안 1개 (score >= 0.8)",
  "high_score_event_proposals": [
    {
      "keyword": "WBG 반도체 수출 규제",
      "score": 0.92,
      "suggested_tag_name": "EVT_WBG반도체수출규제",
      "confidence": 0.88
    }
  ]
}
```

**예시 2: HITL 불필요 (저점수 EVENT 제안)**

**입력**:
```json
{
  "exact_matched_tags": [
    {"keyword": "희토류", "tag_id": "MAT_RARE_EARTH"},
    {"keyword": "중국", "tag_id": "SITE_CHINA"}
  ],
  "keywords": [
    {"keyword": "희토류", "score": 0.95},
    {"keyword": "중국", "score": 0.88},
    {"keyword": "발표", "score": 0.55}
  ],
  "potential_event_tags": [
    {
      "keyword": "발표",
      "category": "EVENT",
      "confidence": 0.60,
      "suggested_tag_name": "EVT_발표"
    }
  ]
}
```

**출력**:
```json
{
  "mapped_tags": [
    {"keyword": "희토류", "tag_id": "MAT_RARE_EARTH"},
    {"keyword": "중국", "tag_id": "SITE_CHINA"}
  ],
  "mapping_quality_score": 0.67,
  "requires_hitl": false,
  "hitl_reason": null,
  "high_score_event_proposals": []
}
```
→ "발표" (score 0.55 < 0.8)는 저점수이므로 HITL 불필요

---

## 문서 네비게이션

- **이전**: [Agent_5: News Grouper](02_AGENT_5_NEWS_GROUPER.md)
- **다음**: [Agent_3: DB Searcher](04_AGENT_3_DB_SEARCHER.md)
- **개요**: [시스템 개요 (00_OVERVIEW.md)](00_OVERVIEW.md)

---

**작성일**: 2026-07-12  
**버전**: 1.0
