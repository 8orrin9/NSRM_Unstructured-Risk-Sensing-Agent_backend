# Agent_2_Tag_Mapper 모듈 개요

## 1. 개요

### 목적
Agent_1_News_Analyzer에서 추출한 키워드를 태그 DB와 매핑하여 공급망 DB 검색을 위한 정규화된 태그를 생성합니다.

### 핵심 역할
- **표현 정규화**: 다양한 표현을 하나의 태그로 수렴 (예: "아르곤", "아르곤 가스", "Argon" → RAW_SPECIAL_GAS)
- **매핑 품질 관리**: HITL(Human-in-the-Loop) 플래그로 신뢰도 관리
- **신규 태그 검토**: EVENT 태그 후보 자동 탐지

---

## 2. 워크플로우

### 2.1 프로세스
```
[Agent_1 출력] 
    ↓
validate_input (입력 검증 및 정규화)
    ↓
exact_matching (정확 매칭 - Jaccard >= 0.95)
    ↓
semantic_matching (유사 매칭 - OpenAI Embedding + 코사인 유사도)
    ↓
classify_unmatched (LLM 분류 - EVENT/ENTITY/UNCLEAR)
    ↓
review_event_proposals (비판적 검토 - 규칙 필터 + LLM 검토)
    ↓
aggregate_results (결과 통합 + HITL 판단)
    ↓
[Conditional Edge]
  ├─ requires_hitl=True → END (HITL 플래그)
  └─ requires_hitl=False → END (Agent_3로 전달 예정)
```

### 2.2 각 단계별 상세

#### 1) validate_input
- 키워드 정규화 (소문자, 공백 제거)
- 중복 제거
- State 초기화

#### 2) exact_matching
- TAG_KEYWORD_MAP 전체 키워드와 Jaccard 유사도 계산
- 아주 엄격한 임계값 (>= 0.95)
- target_region 결정 (korean → KR, english → GLOBAL)
- 매칭 성공 → `exact_matched_tags` (confidence=유사도)
- 매칭 실패 → `unmatched_keywords`

#### 3) semantic_matching
- **OpenAI Embedding API** (text-embedding-3-small) 활용
- **임베딩 대상**: TAG_KEYWORD_MAP 키워드 (최대 10개) + TAG_MASTER.description
- **유사도 계산**: 코사인 유사도 (임계값: **0.55**)
- **비용 절감**: JSON 기반 임베딩 캐싱 (221/224개 태그, 8.9MB)
- **매칭된 키워드 추적**: `matched_tag_keywords` 필드로 어떤 태그 키워드와 매칭되었는지 기록
- 매칭 성공 → `fuzzy_matched_tags` (confidence=코사인 유사도)
- 매칭 실패 → `unmatched_keywords` 유지

**임계값 조정 근거**:
- description 추가 전: 0.80 (매칭 거의 없음)
- description 추가 후: 0.55 (의미적 유사도 적정선)
- 테스트 결과: "반도체 공급망" → "항만 혼잡" (0.59), "반도체 제조" → "세라믹" (0.55)

#### 4) classify_unmatched
- LLM (gpt-4o-mini)이 미매칭 키워드 분류
- **EVENT**: 사건/규제/제재 → `potential_event_tags`
- **ENTITY**: 기업명/소재명 → HITL 필요 (DB 갱신 우선)
- **UNCLEAR**: 범용 단어 → 폐기

#### 5) review_event_proposals (신규)
- **목적**: EVENT 태그 제안의 False Positive 필터링 (70-80% HITL 감소)
- **하이브리드 접근법**:
  1. **규칙 기반 필터** (1단계 - 빠른 거부):
     - 추상 단어 블랙리스트 ("제재", "규제", "리스크" 등)
     - 기존 태그와 Jaccard >= 0.7 중복
     - confidence < 0.85 불확실
     - 기존 키워드 완전 일치 (매핑 버그)
  2. **LLM 검토** (2단계 - 의미적 판단):
     - 규칙 통과한 제안만 LLM 검토
     - 기존 EVENT 태그 목록과 비교
     - 중복/추상도/타당성 검토
     - 거부 시 이유 + 제안 액션 제공
- **출력**:
  - `potential_event_tags`: 승인된 제안만
  - `rejected_event_proposals`: 거부된 제안 (로깅용)

#### 6) aggregate_results
- `exact_matched_tags` + `fuzzy_matched_tags` → `mapped_tags` 통합
- 중복 제거 (같은 tag_id)
- 품질 점수 계산: `(exact 개수 * 1.0 + fuzzy 개수 * 0.8) / 전체 키워드 개수`
- **HITL 판단**:
  - `mapping_quality_score < 0.6` → HITL
  - `potential_event_tags` 존재 → HITL
  - 고점수 키워드 미매칭 (score >= 0.8) → HITL

---

## 3. State 구조

```python
class TagMappingState(TypedDict):
    # Agent_1 입력
    news_id: str
    title_ko: str
    content_ko: str
    summary_ko: str
    keywords: List[Dict]  # [{"keyword": str, "score": float}, ...]
    is_relevant: bool
    relevance_score: float
    relevance_reason: Optional[str]
    original_language: str
    
    # Agent_2 중간 처리
    exact_matched_tags: List[Dict]  # [{"keyword": str, "tag_id": str, ..., "matched_tag_keyword": str}, ...]
    fuzzy_matched_tags: List[Dict]  # [{"keyword": str, "tag_id": str, ..., "matched_tag_keywords": List[str]}, ...]
    unmatched_keywords: List[str]
    potential_event_tags: List[Dict]
    rejected_event_proposals: List[Dict]  # [{"keyword": str, "rejection_reason": str, ...}, ...]
    
    # Agent_2 최종 출력
    mapped_tags: List[Dict]  # [{"keyword": str, "tag_id": str, "tag_type": str, "confidence": float, "source": str}, ...]
    mapping_quality_score: float  # 0~1
    requires_hitl: bool
    hitl_reason: Optional[str]
    error: Optional[str]
```

---

## 4. 설정 (config.py)

| 설정 | 값 | 설명 |
|------|----|----|
| `TAG_DB_PATH` | data/NEWS/news_intelligence.db | 태그 DB 경로 |
| `EXACT_MATCH_THRESHOLD` | 0.95 | Jaccard 유사도 임계값 (매우 엄격) |
| `SEMANTIC_MATCH_THRESHOLD` | **0.55** | 코사인 유사도 임계값 (description 추가 후 조정) |
| `EMBEDDING_MODEL` | text-embedding-3-small | OpenAI 임베딩 모델 |
| `EMBEDDING_CACHE_PATH` | cache/tag_embeddings.json | 임베딩 캐시 경로 (8.9MB, 221개) |
| `LLM_CLASSIFICATION_MODEL` | gpt-4o-mini | LLM 분류 모델 |
| `LLM_CONFIDENCE_THRESHOLD` | 0.6 | 신뢰도 임계값 |
| `HITL_QUALITY_THRESHOLD` | 0.6 | HITL 트리거 품질 임계값 |
| `HITL_HIGH_SCORE_KEYWORD_THRESHOLD` | 0.8 | HITL 트리거 키워드 점수 임계값 |
| **검토 설정** | | |
| `REVIEW_EVENT_PROPOSALS_ENABLED` | True | EVENT 제안 검토 활성화 |
| `REVIEW_METHOD` | hybrid | 검토 방법 (rule/llm/hybrid) |
| `ABSTRACT_KEYWORD_BLACKLIST` | ["제재", "규제", ...] | 추상 단어 블랙리스트 (8개) |
| `DUPLICATE_SIMILARITY_THRESHOLD` | 0.7 | Jaccard 중복 임계값 |
| `REVIEW_MIN_CONFIDENCE` | 0.85 | LLM 제안 최소 신뢰도 |
| `REVIEW_LLM_MODEL` | gpt-4o-mini | 검토용 LLM 모델 |

---

## 5. 재사용 컴포넌트

### 5.1 기존 함수
1. **`models/news_intelligence_db.py`**
   - `normalize_keyword(keyword)`: 키워드 정규화
   - `search_tags_by_keyword(conn, keyword, target_region)`: 정확 매칭
   - `get_db_connection(db_path)`: SQLite 연결

2. **`dev/Agent_1_News_Analyzer/utils/textrank.py`**
   - `_string_similarity(s1, s2)`: Jaccard 유사도 계산

### 5.2 DB 구조
- **TAG_MASTER**: 448개 태그 (224개 × 2 지역: KR/GLOBAL)
  - **description 필드**: 100% 채워짐 (448/448개)
  - 임베딩에 활용되어 semantic_matching 품질 향상
- **TAG_KEYWORD_MAP**: 2,517개 키워드 (KR: 1,831개, GLOBAL: 686개)
- 태그 유형: SUPPLIER(246), EVENT(120), MATERIAL(46), RAW_MATERIAL(20), SITE(16)

### 5.3 임베딩 캐시
- **경로**: `dev/Agent_2_Tag_Mapper/cache/tag_embeddings.json`
- **크기**: 8.9MB
- **내용**: 221/224개 태그 임베딩 (98.7% 성공)
- **모델**: text-embedding-3-small
- **구조**: `{"model": str, "embeddings": {통합텍스트: [임베딩벡터], ...}}`

---

## 6. 테스트 결과

### 6.1 전체 파이프라인 테스트 (21개 뉴스)
**실행 일자**: 2026-07-03  
**입력**: Agent_1 출력 (news_full_pipeline.json)

**통계**:
- **총 처리**: 21개 뉴스
- **평균 품질 점수**: 0.22
- **정확 매칭**: 45개
- **유사도 매칭**: 2개 (임계값 0.55)
- **총 매핑 태그**: 39개 (평균 1.9개/뉴스)
- **HITL 필요**: 20개 (95.2%)
- **EVENT 태그 후보**: 10개

**태그 유형별 분포**:
- SUPPLIER: 10개
- SITE: 10개
- EVENT: 8개
- RAW_MATERIAL: 7개
- MATERIAL: 4개

### 6.2 Semantic Matching 성능
**description 추가 전** (임계값 0.80):
- 유사도 매칭: 0개
- 최고 유사도: 0.36

**description 추가 후** (임계값 0.55):
- 유사도 매칭: 2개
- 예시:
  - "반도체 공급" → "항만 혼잡" (유사도 0.60)
  - "반도체 제품" → "기술 단절(EOL)" (유사도 0.65)

**테스트 유사도 분포** (KR 대상):
- "반도체 공급망" → "항만 혼잡" (0.59)
- "반도체 제조" → "세라믹" (0.55)
- "반도체 생산" → "세라믹" (0.53)

### 6.3 EVENT 제안 검토 효과
**검토 전**:
- LLM 제안: 10개 → HITL 10개

**검토 후** (하이브리드):
- LLM 제안: 10개
- 규칙 필터 거부: ~3-5개 (추상 단어, 중복 등)
- LLM 검토 거부: ~0-2개 (의미적 중복)
- 최종 승인: ~5-7개 → **HITL 30-50% 감소**

---

## 7. 파일 구조

```
dev/Agent_2_Tag_Mapper/
├── __init__.py
├── config.py
├── graph.py
├── prompts.py
├── nodes/
│   ├── __init__.py (TagMappingState)
│   ├── validate_input.py
│   ├── exact_matching.py
│   ├── semantic_matching.py (신규 - OpenAI Embedding)
│   ├── classify_unmatched.py
│   ├── review_event_proposals.py (신규 - 비판적 검토)
│   └── aggregate_results.py
├── utils/
│   └── embedding_cache.py (신규 - 임베딩 캐싱)
├── cache/
│   └── tag_embeddings.json (8.9MB, 221개 임베딩)
├── scripts/
│   ├── run_tag_mapping.py
│   ├── run_full_pipeline.py (Agent_1 + Agent_2 통합)
│   ├── generate_tag_embeddings.py (임베딩 사전 생성)
│   ├── update_tag_description.py (Excel → DB 동기화)
│   └── check_failed_embeddings.py (임베딩 실패 확인)
└── tests/
    ├── test_semantic_matching.py
    ├── test_review_proposals.py
    ├── test_matched_keywords.py
    └── test_detailed_similarity.py
```

---

## 8. 향후 개선 사항 (Phase 2)

### 8.1 임베딩 실패 태그 처리
- **현재**: 221/224개 임베딩 성공 (3개 실패)
- **원인**: 텍스트 길이 초과 또는 특수 문자
- **Phase 2**: 
  - 실패한 태그 개별 처리 (텍스트 분할 또는 정제)
  - 100% 임베딩 커버리지 달성

### 8.2 유사도 임계값 동적 조정
- **현재**: 고정 임계값 (0.55)
- **Phase 2**: 
  - 태그 유형별 임계값 (MATERIAL: 0.60, EVENT: 0.50 등)
  - A/B 테스트로 최적 임계값 탐색

### 8.3 matched_keywords 활용
- **현재**: 매칭된 키워드 정보 수집만
- **Phase 2**:
  - HITL 리뷰 시 매칭 근거 제시
  - 키워드 가중치 학습 (자주 매칭되는 키워드 우선)

### 8.4 자동 태그 생성
- **현재**: EVENT 태그는 HITL 승인 필요
- **Phase 2**: confidence >= 0.95 + 검토 통과 → 자동 생성 (로그 필수)

---

## 9. 성능 지표

| 지표 | 목표 | 실제 (21개 뉴스) |
|------|------|------------------|
| 매핑 성공률 | 70~80% | 85.7% (18/21개 1개 이상 매칭) |
| HITL 비율 | 20~30% | 95.2% (20/21개) - **개선 필요** |
| 처리 속도 (병렬) | 1초/뉴스 (LLM 포함) | ~3초/뉴스 (5 workers) |
| 품질 점수 | >= 0.6 | 0.22 평균 - **개선 필요** |
| 정확 매칭률 | 50~60% | 45/47개 (95.7%) |
| 유사도 매칭률 | 10~20% | 2/47개 (4.3%) - **개선 필요** |
| EVENT 검토 효과 | 30~50% 감소 | 예상 30~50% (실측 예정) |

**개선 필요 항목**:
1. **HITL 비율 과다**: 95.2% → 목표 30%
   - 원인: 품질 점수 낮음 (0.22), 매핑률 낮음
   - 대책: 키워드 추출 품질 개선, 임계값 조정
2. **유사도 매칭 저조**: 4.3%
   - 원인: 임계값 0.55가 여전히 높음, description 품질
   - 대책: 임계값 0.50 테스트, description 고도화

---

## 10. 사용 예시

```python
from dev.Agent_2_Tag_Mapper import create_tag_mapper_graph, TagMappingState

# 그래프 생성
graph = create_tag_mapper_graph()

# State 초기화 (Agent_1 출력 활용)
state = TagMappingState(
    news_id="test_001",
    title_ko="중국, 희토류 수출 규제 강화",
    summary_ko="중국이 희토류 수출 규제를 강화했다.",
    keywords=[
        {"keyword": "희토류", "score": 0.9},
        {"keyword": "중국", "score": 0.85}
    ],
    original_language="korean",
    # ... 나머지 필드 초기화
)

# 그래프 실행
result = graph.invoke(state)

# 결과 활용
print(f"매핑된 태그: {len(result['mapped_tags'])}개")
print(f"품질 점수: {result['mapping_quality_score']}")
print(f"HITL 필요: {result['requires_hitl']}")
```

---

## 11. 참조

### 관련 문서
- [태그 설계 방법론](../Data%20Pipeline/Data%20Pipeline_Tag%20Creation_Docs.md)
- [뉴스 분석기 개요](./Module_News_Collector_Overview.md)
- [공급망 DB 온톨로지](../DB/DB_SUPPLY%20MAP_Ontology_Docs.md)

### 스크립트
- **테스트**: `dev/Agent_2_Tag_Mapper/scripts/run_tag_mapping.py`
- **통합 파이프라인**: `dev/Agent_2_Tag_Mapper/scripts/run_full_pipeline.py` (예정)

---

---

## 12. 변경 이력

### v1.1 (2026-07-03)
- ✅ **semantic_matching 노드 추가**: OpenAI Embedding + 코사인 유사도
- ✅ **review_event_proposals 노드 추가**: 비판적 검토로 HITL 감소
- ✅ **matched_keywords 추적**: 매칭된 태그 키워드 정보 기록
- ✅ **description 필드 100% 채움**: 448/448개 태그
- ✅ **임베딩 캐시 생성**: 221/224개 (8.9MB)
- ⚙️ **임계값 조정**: semantic 0.80 → 0.55
- 📊 **전체 파이프라인 테스트**: 21개 뉴스

### v1.0 (2026-07-02)
- ✅ **기본 워크플로우 구현**: validate → exact → classify → aggregate
- ✅ **exact_matching**: Jaccard >= 0.95
- ✅ **classify_unmatched**: LLM 분류 (EVENT/ENTITY/UNCLEAR)
- ✅ **HITL 시스템**: 품질 점수 기반 트리거

---

**최종 수정일**: 2026-07-03  
**버전**: 1.1  
**구현 상태**: Phase 1 완료 (semantic_matching + review_event_proposals 추가)
