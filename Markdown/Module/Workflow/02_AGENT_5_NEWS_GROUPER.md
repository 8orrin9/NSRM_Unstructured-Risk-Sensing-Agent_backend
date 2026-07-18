# Agent_5: News Grouper (뉴스 그룹화 모듈)

## 목차
- [개요](#개요)
- [워크플로우](#워크플로우)
- [State 구조](#state-구조)
- [기능별 상세 설명](#기능별-상세-설명)

---

## 개요

### 모듈 역할
Agent_5는 **뉴스에서 엔티티를 추출하고 Knowledge Graph와 매칭**하여 뉴스-KG 연결을 수행하는 모듈입니다.

### 파이프라인 위치
```
Agent_1 (News Analyzer) → [Agent_5: News Grouper] → Agent_3 (DB Searcher)
                       ↘ [Agent_2: Tag Mapper] ↗
```

### 주요 기능 (6개)
**Phase 2 (개별 뉴스 처리)**:
1. **입력 검증** (`validate_input`)
2. **엔티티 추출** (`extract_entities_llm`) - LLM 기반 엔티티 추출
3. **KG 매칭** (`match_entities_string`) - 정확 매칭 + Fuzzy 매칭

**Phase 3 (그룹화 및 통합)**:
4. **뉴스 그룹화** (`group_news_by_kg_hop_distance`) - KG 경로 기반 그룹화
5. **그룹 인사이트 추출** (`extract_group_insight`) - LLM 기반 복합 Risk 분석
6. **통합 문서 생성** (`create_unified_document`) - 그룹 내 뉴스 통합

---

## 워크플로우

### Phase 2 (개별 뉴스)
```
validate_input
    ↓
extract_entities_llm
    ↓
match_entities_string
    ↓
(Phase 2 결과 저장)
```

### Phase 3 (그룹화)
```
[모든 Phase 2 결과]
    ↓
group_news_by_kg_hop_distance (KG 경로 기반 그룹화)
    ↓
extract_group_insight (그룹별 인사이트 추출, LLM)
    ↓
create_unified_document (통합 문서 생성)
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
| `content_ko` | str | 본문 (한글) |
| `keywords` | List[Dict] | Agent_1 추출 키워드 |
| `is_relevant` | bool | Agent_1 관련성 필터 |

### 출력 필드 (Agent_5 생성)
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `extracted_entities` | List[Dict] | LLM 추출 엔티티 |
| `matched_kg_entities` | List[Dict] | KG 매칭 결과 |
| `error` | Optional[str] | 에러 메시지 |

---

## 기능별 상세 설명

### 1. validate_input (입력 검증)

#### 📋 설명
Agent_1 출력을 검증하고 Phase 2 필드를 초기화합니다.

#### 🤖 사용 모델
LLM 호출 없음 (조건부 로직)

#### 📥 입력값
| 필드명 | 필수/선택 | 설명 |
|--------|-----------|------|
| `news_id` | ✅ 필수 | 뉴스 ID |
| `content_ko` | ✅ 필수 | 한글 본문 (최소 50자) |
| `is_relevant` | ✅ 필수 | Agent_1 필터링 통과 (True) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `extracted_entities` | List | 빈 배열로 초기화 |
| `matched_kg_entities` | List | 빈 배열로 초기화 |
| `error` | Optional[str] | 검증 실패 시 에러 메시지 |

#### 📝 예시

**입력 (검증 실패)**:
```json
{
  "news_id": "news_001",
  "content_ko": "짧은 본문",  // 50자 미만
  "is_relevant": true
}
```

**출력**:
```json
{
  "error": "content_ko가 너무 짧음 (최소 50자)"
}
```

---

### 2. extract_entities_llm (엔티티 추출)

#### 📋 설명
LLM을 사용하여 뉴스에서 **공급망 관련 엔티티**를 추출합니다.

#### 🤖 사용 모델
- **모델**: `gpt-4o-mini`
- **온도**: 0.3
- **타임아웃**: 60초
- **최대 토큰**: 500
- **개수**: 3~7개 (핵심만)
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `title_ko` | str | 제목 (한글) |
| `content_ko` | str | 원문 (한글) |
| `keywords` | List[Dict] | Agent_1 키워드 (힌트) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `extracted_entities` | List[Dict] | 추출된 엔티티 배열 |

**extracted_entities 구조**:
```json
[
  {
    "entity": "TSMC",
    "type": "Company"
  },
  {
    "entity": "대만",
    "type": "Country"
  }
]
```

#### 엔티티 타입 (8개)

| 타입 | 설명 | 예시 |
|------|------|------|
| `Country` | 국가 | 중국, 미국, 대만 |
| `Company` | 기업/조직 | TSMC, 삼성전자, SK하이닉스 |
| `Material` | 소재/물질 | 희토류, 네온가스, 실리콘 웨이퍼 |
| `Technology` | 기술 | EUV, AI 반도체, 3nm 공정 |
| `Policy` | 정책/규제 | CHIPS법, OFAC 제재 |
| `Event` | 사건 | 대만 지진, 항만 파업 |
| `Location` | 지역/장소 | 평택 공장, 호르무즈 해협 |
| `Organization` | 기관 | 중국 상무부, 미국 상무부 |

#### 💬 프롬프트

**System**:
```
당신은 공급망 엔티티 추출 전문가입니다.
```

**User**:
```
다음 뉴스에서 공급망 관련 엔티티를 추출해주세요.

**뉴스 제목**: {title_ko}
**뉴스 요약**: {summary_ko}
**키워드 힌트**: {keywords}

**엔티티 타입 (8개)**:
- Country: 국가 (중국, 미국, 대만)
- Company: 기업/조직 (TSMC, 삼성전자, SK하이닉스)
- Material: 소재/물질 (희토류, 네온가스, 실리콘 웨이퍼)
- Technology: 기술 (EUV, AI 반도체, 3nm 공정)
- Policy: 정책/규제 (CHIPS법, OFAC 제재)
- Event: 사건 (대만 지진, 항만 파업)
- Location: 지역/장소 (평택 공장, 호르무즈 해협)
- Organization: 기관 (중국 상무부, 미국 상무부)

**추출 원칙**:
1. 한글 우선 (영문은 한글로 변환)
2. 구체적 엔티티만 (추상 명사 제외)
3. 핵심만 3~7개 선택
4. 정식 명칭 사용 (약칭 지양)
   - 예: "SK하이닉스" ○, "하이닉스" ×
   - 예: "대만반도체제조회사(TSMC)" ○, "대만 파운드리" ×

**출력 형식 (JSON)**:
{
  "entities": [
    {
      "entity": "TSMC",
      "type": "Company"
    },
    {
      "entity": "대만",
      "type": "Country"
    }
  ]
}
```

#### 📝 예시

**입력**:
```json
{
  "title_ko": "중국, 희토류 대미 수출 전면 중단",
  "summary_ko": "중국 정부가 7월 1일부터 미국에 대한 희토류 수출을 전면 중단...",
  "keywords": [
    {"keyword": "희토류", "score": 0.95},
    {"keyword": "중국", "score": 0.90}
  ]
}
```

**출력**:
```json
{
  "extracted_entities": [
    {
      "entity": "중국",
      "type": "Country"
    },
    {
      "entity": "미국",
      "type": "Country"
    },
    {
      "entity": "희토류",
      "type": "Material"
    },
    {
      "entity": "중국 정부",
      "type": "Organization"
    }
  ]
}
```

---

### 3. match_entities_string (KG 매칭)

#### 📋 설명
추출된 엔티티를 Knowledge Graph 노드와 **문자열 기반으로 매칭**합니다.

#### 🤖 사용 모델
LLM 호출 없음 (문자열 매칭)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `extracted_entities` | List[Dict] | LLM 추출 엔티티 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `matched_kg_entities` | List[Dict] | KG 매칭 결과 |

**matched_kg_entities 구조**:
```json
[
  {
    "entity": "TSMC",
    "type": "Company",
    "match_method": "exact"
  },
  {
    "entity": "대만",
    "type": "Country",
    "match_method": "fuzzy"
  }
]
```

#### 매칭 방식

**1단계: 정규화 적용**
```json
// entity_normalization_lookup.json
{
  "TSMC": "대만반도체제조회사",
  "SK하이닉스": "에스케이하이닉스"
}
```

**2단계: 정확 매칭 (EXACT_MATCH)**
- 정규화된 엔티티가 KG 노드에 정확히 존재하는지 확인
- 대소문자 무시

**3단계: Fuzzy 매칭 (FUZZY_MATCH)**
- 부분 문자열 매칭 (양방향)
- 최소 길이: 2자 이상
- 대소문자 무시
- 예: "대만" ⊂ "대만반도체제조회사"

#### 설정

| 항목 | 값 | 설명 |
|------|-----|------|
| `EXACT_MATCH_ENABLED` | True | 정확 매칭 활성화 |
| `FUZZY_MATCH_ENABLED` | True | Fuzzy 매칭 활성화 |
| `FUZZY_MATCH_MIN_LENGTH` | 2 | Fuzzy 최소 문자 수 |
| `GRAPHML_PATH` | `graph_chunk_entity_relation_normalized.graphml` | KG 파일 경로 |

#### 📝 예시

**입력**:
```json
{
  "extracted_entities": [
    {"entity": "TSMC", "type": "Company"},
    {"entity": "대만", "type": "Country"},
    {"entity": "희토류", "type": "Material"},
    {"entity": "XYZ Corp", "type": "Company"}  // KG에 없음
  ]
}
```

**KG 노드 (예시)**:
```
- "대만반도체제조회사(TSMC)" (Company)
- "대만" (Country)
- "희토류" (Material)
```

**출력**:
```json
{
  "matched_kg_entities": [
    {
      "entity": "TSMC",
      "type": "Company",
      "match_method": "exact",
      "kg_node": "대만반도체제조회사(TSMC)"
    },
    {
      "entity": "대만",
      "type": "Country",
      "match_method": "exact",
      "kg_node": "대만"
    },
    {
      "entity": "희토류",
      "type": "Material",
      "match_method": "exact",
      "kg_node": "희토류"
    }
    // "XYZ Corp"는 매칭 실패로 제외
  ]
}
```

---

## Knowledge Graph 구축 (사전 단계)

Agent_5가 사용하는 Knowledge Graph는 **사전에 구축**되어 있어야 합니다.

### KG 구축 프로세스

1. **입력**: INSIGHT_REPORT_MASTER.description_refined (6개 글로벌 공급망 인사이트 레포트)
2. **도구**: LightRAG + OpenAI GPT-4o-mini
3. **엔티티 타입**: 8개 (Country, Company, Material, Technology, Policy, Event, Location, Organization)
4. **관계 카테고리**: 5개 (CAUSAL, POLICY_REGULATION, SUPPLY, GEOGRAPHIC, DESCRIPTIVE)
5. **출력**: `graph_chunk_entity_relation_normalized.graphml`

### KG 구축 스크립트

```bash
# 최초 1회 실행
python dev/insight_kg/insight_kg_builder.py

# 정규화 테이블 생성
python dev/insight_kg/insight_kg_entity_normalizer_builder.py

# 정규화 적용
python dev/insight_kg/insight_kg_entity_normalizer_applier.py
```

**자세한 내용**: [00-1_INSIGHT_KG_BUILDER.md](00-1_INSIGHT_KG_BUILDER.md) 참조

---

## Phase 3: 그룹화 및 통합 문서 생성

### 4. group_news_by_kg_hop_distance (뉴스 그룹화)

#### 📋 설명
KG 경로 기반으로 **관련 뉴스들을 자동 그룹화**합니다. 같은 그룹 내 뉴스는 Agent_3/4에서 하나의 통합 문서로 처리됩니다.

#### 🤖 사용 모델
LLM 호출 없음 (NetworkX 그래프 알고리즘)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `all_news_results` | List[Dict] | Phase 2 전체 결과 |
| `max_hop` | int | 최대 KG 경로 거리 (기본값: 1) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `groups` | List[Dict] | 그룹 배열 |

**groups 구조**:
```json
[
  {
    "group_id": "group_001",
    "news_ids": ["news_001", "news_002", "news_003"],
    "shared_entities": ["중국", "희토류", "TSMC"],
    "news_count": 3
  },
  {
    "group_id": "ungrouped",
    "news_ids": ["news_010", "news_015"],
    "shared_entities": [],
    "news_count": 2
  }
]
```

#### 그룹화 조건

두 뉴스가 같은 그룹에 속하려면:
1. **공통 엔티티 ≥ 2개**
2. **KG 경로 존재** (max_hop=1, 즉 직접 연결 or 1개 노드 경유)

#### 그룹화 알고리즘

1. **엔티티 특이도 계산** (IDF 방식):
   ```python
   entity_weight = log(total_news / doc_count)
   ```
   - 모든 뉴스에 등장하는 엔티티 (예: "중국") → 낮은 가중치
   - 희귀한 엔티티 (예: "WBG 반도체") → 높은 가중치

2. **뉴스 유사도 그래프 생성**:
   - 노드: 각 뉴스
   - 엣지: 공통 엔티티 ≥ 2 AND KG 경로 존재
   - 엣지 가중치: 공통 엔티티의 특이도 합

3. **Louvain 커뮤니티 탐지**:
   - NetworkX의 `community.louvain_communities()` 사용
   - 모듈러리티 최대화로 자동 그룹화

#### 설정

| 항목 | 값 | 설명 |
|------|-----|------|
| `MAX_HOP` | 1 | KG 최대 경로 거리 |
| `MIN_COMMON_ENTITIES` | 2 | 최소 공통 엔티티 개수 |

#### 📝 예시

**입력 (Phase 2 결과 3개)**:
```json
[
  {
    "news_id": "news_001",
    "title_ko": "중국 희토류 수출 중단",
    "matched_kg_entities": [
      {"entity": "중국", "type": "Country"},
      {"entity": "희토류", "type": "Material"},
      {"entity": "미국", "type": "Country"}
    ]
  },
  {
    "news_id": "news_002",
    "title_ko": "희토류 가격 급등",
    "matched_kg_entities": [
      {"entity": "희토류", "type": "Material"},
      {"entity": "중국", "type": "Country"},
      {"entity": "가격", "type": "Event"}
    ]
  },
  {
    "news_id": "news_003",
    "title_ko": "TSMC 3나노 공정 발표",
    "matched_kg_entities": [
      {"entity": "TSMC", "type": "Company"},
      {"entity": "대만", "type": "Country"}
    ]
  }
]
```

**출력**:
```json
{
  "groups": [
    {
      "group_id": "group_001",
      "news_ids": ["news_001", "news_002"],
      "shared_entities": ["중국", "희토류"],
      "news_count": 2
    },
    {
      "group_id": "ungrouped",
      "news_ids": ["news_003"],
      "shared_entities": [],
      "news_count": 1
    }
  ]
}
```

**설명**:
- news_001 ↔ news_002: 공통 엔티티 2개 ("중국", "희토류") → 그룹화 ✅
- news_001 ↔ news_003: 공통 엔티티 0개 → 그룹화 안 됨 ❌
- news_002 ↔ news_003: 공통 엔티티 0개 → 그룹화 안 됨 ❌

---

### 5. extract_group_insight (그룹 인사이트 추출)

#### 📋 설명
그룹화된 뉴스들의 **숨은 연관성과 복합 Risk 패턴**을 LLM으로 분석하여, Agent_3 DB Searcher가 활용할 인사이트를 제공합니다.

#### 🤖 사용 모델
- **모델**: `gpt-5.5` (복잡한 추론 특화)
- **온도**: 0.4
- **타임아웃**: 90초
- **최대 토큰**: 1500
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `group` | Dict | 그룹 정보 |
| `all_news_data` | List[Dict] | Phase 2 전체 결과 |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `group_id` | str | 그룹 ID |
| `group_theme` | str | 그룹 주제 (한 문장) |
| `risk_perspectives` | List[Dict] | Risk 관점 배열 |
| `compound_risk_pattern` | str | 복합 Risk 패턴 설명 |
| `hidden_connections` | List[Dict] | 숨은 연관성 |
| `search_priorities` | List[Dict] | DB 검색 우선순위 |
| `aggregate_confidence` | float | 종합 신뢰도 |

**risk_perspectives 구조**:
```json
[
  {
    "perspective": "공급망 단절",
    "description": "중국 희토류 수출 중단으로 협력사 조달 차질",
    "affected_entities": ["중국", "희토류", "협력사"],
    "confidence": 0.92
  }
]
```

#### 💬 프롬프트 (요약)

```
다음 그룹화된 뉴스들의 복합 Risk 패턴을 분석해주세요.

[그룹 내 뉴스 목록]
- news_001: 중국 희토류 수출 중단
- news_002: 희토류 가격 급등

[공통 엔티티]
중국, 희토류

[분석 요청]
1. 그룹 주제 (한 문장)
2. Risk 관점 (2-4개)
3. 복합 Risk 패턴
4. 숨은 연관성
5. DB 검색 우선순위

출력 형식: JSON
```

#### 📝 예시

**입력**:
```json
{
  "group": {
    "group_id": "group_001",
    "news_ids": ["news_001", "news_002"],
    "shared_entities": ["중국", "희토류"]
  },
  "all_news_data": [...]
}
```

**출력**:
```json
{
  "group_id": "group_001",
  "group_theme": "중국 희토류 수출 규제로 인한 공급망 불안정",
  "risk_perspectives": [
    {
      "perspective": "공급망 단절",
      "description": "중국 희토류 수출 중단으로 협력사 조달 차질 예상",
      "affected_entities": ["중국", "희토류", "협력사"],
      "confidence": 0.92
    },
    {
      "perspective": "가격 변동성",
      "description": "희토류 가격 급등으로 조달 비용 증가",
      "affected_entities": ["희토류", "가격"],
      "confidence": 0.88
    }
  ],
  "compound_risk_pattern": "수출 규제 → 공급 부족 → 가격 급등 → 조달 비용 증가의 연쇄 Risk",
  "hidden_connections": [
    {
      "connection": "중국 → 희토류 → 협력사",
      "path_type": "SUPPLY",
      "explanation": "중국이 희토류의 70%를 생산하며 다수 협력사가 의존"
    }
  ],
  "search_priorities": [
    {
      "entity": "희토류",
      "reason": "핵심 소재로 공급 차단 시 즉시 영향",
      "priority": 1
    },
    {
      "entity": "중국",
      "reason": "주요 생산지로 정책 변화 모니터링 필요",
      "priority": 2
    }
  ],
  "aggregate_confidence": 0.90
}
```

---

### 6. create_unified_document (통합 문서 생성)

#### 📋 설명
그룹 내 뉴스들을 **하나의 통합 문서**로 생성하여 Agent_2/3/4에 전달합니다.

#### 🤖 사용 모델
LLM 호출 없음 (텍스트 병합)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `group` | Dict | 그룹 정보 |
| `all_news_data` | List[Dict] | Phase 2 전체 결과 |
| `group_insight` | Dict | 그룹 인사이트 (선택) |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `news_id` | str | 그룹 ID (예: "group_001") |
| `title_ko` | str | 대표 제목 |
| `content_ko` | str | 통합 본문 (뉴스별 구분) |
| `summary_ko` | str | 통합 요약 (bullet list) |
| `keywords` | List[Dict] | 통합 키워드 (중복 제거) |
| `original_news_ids` | List[str] | 원본 뉴스 ID 배열 |
| `shared_entities` | List[str] | 공통 엔티티 |
| `group_insight` | Dict | 그룹 인사이트 (있을 경우) |
| `is_grouped` | bool | True |

#### 통합 규칙

1. **제목**: `[그룹 {group_id}] {첫 번째 뉴스 제목} 외 {n}건`
2. **본문**: 뉴스별로 `---` 구분자로 연결
3. **요약**: bullet list 형식 (`-` 접두사)
4. **키워드**: 중복 제거, score 최대값 유지

#### 📝 예시

**입력**:
```json
{
  "group": {
    "group_id": "group_001",
    "news_ids": ["news_001", "news_002"],
    "shared_entities": ["중국", "희토류"]
  },
  "all_news_data": [
    {
      "news_id": "news_001",
      "title_ko": "중국 희토류 수출 중단",
      "content_ko": "중국 정부가...",
      "summary_ko": "중국이 미국에 희토류 수출 중단",
      "keywords": [
        {"keyword": "희토류", "score": 0.95},
        {"keyword": "중국", "score": 0.90}
      ]
    },
    {
      "news_id": "news_002",
      "title_ko": "희토류 가격 급등",
      "content_ko": "희토류 가격이...",
      "summary_ko": "수출 중단 발표 후 가격 급등",
      "keywords": [
        {"keyword": "희토류", "score": 0.92},
        {"keyword": "가격", "score": 0.85}
      ]
    }
  ]
}
```

**출력**:
```json
{
  "news_id": "group_001",
  "title_ko": "[그룹 group_001] 중국 희토류 수출 중단 외 1건",
  "content_ko": "[뉴스 1/2] 중국 희토류 수출 중단\n\n중국 정부가...\n\n---\n\n[뉴스 2/2] 희토류 가격 급등\n\n희토류 가격이...",
  "summary_ko": "- 중국이 미국에 희토류 수출 중단\n- 수출 중단 발표 후 가격 급등",
  "keywords": [
    {"keyword": "희토류", "score": 0.95},
    {"keyword": "중국", "score": 0.90},
    {"keyword": "가격", "score": 0.85}
  ],
  "original_news_ids": ["news_001", "news_002"],
  "shared_entities": ["중국", "희토류"],
  "is_grouped": true
}
```

---

## 다음 Agent로 데이터 전달

### 전달 규칙

Agent_5는 다음 Agent(Agent_2, Agent_3, Agent_4)에 **두 종류의 문서**를 전달합니다:

1. **그룹화된 뉴스의 통합 문서** (`is_grouped=True`)
2. **모든 개별 뉴스 원본** (그룹화 여부 관계없이)

### 전달 이유

- **통합 문서**: 그룹 내 뉴스들의 복합 Risk 패턴 분석
- **개별 뉴스**: 각 뉴스의 고유한 Risk 요소 분석

### 예시

**Phase 2 결과**: news_001, news_002, news_003 (3개 뉴스)

**Phase 3 그룹화**:
- group_001: [news_001, news_002] (2개 묶임)
- ungrouped: [news_003] (단독)

**다음 Agent 전달 문서** (총 4개):
1. `group_001` (통합 문서) ← news_001 + news_002 병합
2. `news_001` (개별)
3. `news_002` (개별)
4. `news_003` (개별)

### 출력 JSON 구조

```json
{
  "phase2_results": [...],           // Phase 2 개별 뉴스 원본
  "groups": [...],                   // Phase 3 그룹 목록
  "group_insights": [...],           // Phase 3.5 그룹 인사이트
  "unified_documents": [...],        // Phase 4 통합 문서
  "documents_for_next_agents": [     // ★ 다음 Agent가 사용할 필드
    {통합 문서 1},
    {통합 문서 2},
    {개별 뉴스 1},
    {개별 뉴스 2},
    ...
  ]
}
```

---

## 문서 네비게이션

- **이전**: [Agent_1: News Analyzer](01_AGENT_1_NEWS_ANALYZER.md)
- **다음**: [Agent_2: Tag Mapper](03_AGENT_2_TAG_MAPPER.md)
- **KG 구축**: [Insight KG Builder](00-1_INSIGHT_KG_BUILDER.md)
- **개요**: [시스템 개요 (00_OVERVIEW.md)](00_OVERVIEW.md)

---

**작성일**: 2026-07-12  
**버전**: 1.0
