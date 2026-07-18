# Agent_5 News Grouper 문서

**작성일**: 2026-07-08  
**버전**: 1.1  
**담당**: POC-A 개발팀

---

## 목차

1. [개요](#1-개요)
2. [핵심 개념](#2-핵심-개념)
3. [데이터 흐름](#3-데이터-흐름)
4. [출력 구조 상세](#4-출력-구조-상세)
5. [Insight KG 매칭](#5-insight-kg-매칭)
6. [그룹 인사이트 추출](#6-그룹-인사이트-추출)
7. [실전 예시](#7-실전-예시)
8. [설정 및 구성](#8-설정-및-구성)
9. [활용 방안](#9-활용-방안)
10. [FAQ](#10-faq)

---

## 1. 개요

### 1.1 목적

Agent_5 News Grouper는 **여러 뉴스를 Insight Knowledge Graph(KG)를 통해 그룹화**하여, 단일 뉴스로는 보이지 않던 **복합 위험 패턴**을 발견하는 모듈입니다.

### 1.2 주요 기능

- ✅ **LLM 엔티티 추출**: 뉴스에서 공급망 관련 엔티티 추출 (Country, Company, Material 등)
- ✅ **Insight KG 매칭**: 추출된 엔티티를 Insight KG와 문자열 기반 매칭
- ✅ **KG Hop 거리 기반 그룹화**: 공통 엔티티가 KG에서 실제로 연결된 경우에만 그룹화 (MAX_HOP=2)
- ✅ **커뮤니티 탐지**: Louvain 알고리즘으로 관련 뉴스 클러스터링
- ✅ **그룹 인사이트 추출**: 그룹화된 뉴스에서 다층적 위험 관점 발견

### 1.3 입출력

| 구분 | 설명 |
|------|------|
| **입력** | Agent_1 출력 (뉴스 + 키워드) |
| **출력** | 그룹화된 뉴스 + 그룹 인사이트 + KG 경로 |

---

## 2. 핵심 개념

### 2.1 문제 정의

**수동 방식의 한계**:
```
뉴스 A: "중국 NDRC, 콩고 대사 회동"
뉴스 B: "중국 NDRC, 콩고 외무장관 회담"
뉴스 C: "중국 히타치 그룹 CEO 회동"
↓
담당자가 수동으로 "이 뉴스들이 관련 있는지" 판단
↓
시간 소요 + 놓치는 연결고리 발생
```

**자동화 솔루션**:
```
뉴스 A, B, C 입력
↓
Agent_5가 자동으로:
  1. 공통 엔티티 발견 ("중국 NDRC")
  2. Insight KG를 통해 뉴스 간 관계 파악
  3. 관련 뉴스 그룹화 (group_002)
  4. 그룹 인사이트 추출 (다층적 위험 관점)
↓
"중국 NDRC가 콩고, 히타치와 협력 강화 중" 패턴 발견 (5초 소요)
```

### 2.2 핵심 가치

1. **복합 위험 발견**: 단일 뉴스로는 보이지 않던 연쇄 효과 파악
2. **맥락 이해**: 뉴스 간 인과관계, 시간적 선후관계 발견
3. **중복 제거**: 동일 이슈를 다룬 뉴스들을 하나로 통합
4. **우선순위**: 여러 뉴스가 관련된 이슈는 더 중요

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
│ [PHASE 2] 뉴스 → Insight KG 엔티티 매칭                        │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 1: 입력 검증 (validate_input)                        │  │
│ │ • 필수 필드 확인 (title_ko, keywords)                     │  │
│ └───────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 2: LLM 엔티티 추출 (extract_entities_llm)           │  │
│ │ • 뉴스에서 공급망 관련 엔티티 추출                        │  │
│ │ • 엔티티 타입: Country, Company, Material, Technology,   │  │
│ │                Policy, Event, Location, Organization      │  │
│ │ OUTPUT: extracted_entities[]                              │  │
│ └───────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 3: 문자열 매칭 (match_entities_string)              │  │
│ │ • 추출된 엔티티를 Insight KG와 문자열 기반 매칭          │  │
│ │ • Exact Match: 정확 일치                                  │  │
│ │ • Fuzzy Match: 부분 문자열 + 유사도 (Levenshtein)       │  │
│ │ OUTPUT: matched_kg_entities[]                             │  │
│ └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [PHASE 3] KG Hop 거리 기반 뉴스 그룹화                          │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 1: 뉴스 쌍 간 공통 엔티티 확인                       │  │
│ │ • 공통 엔티티 ≥ 2개 조건 확인                             │  │
│ └───────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 2: 공통 엔티티 KG 연결성 검증                        │  │
│ │ • are_common_entities_connected() 호출                    │  │
│ │ • 공통 엔티티들이 KG에서 연결된 서브그래프를 형성하는지    │  │
│ │   확인 (MAX_HOP=2 이내)                                   │  │
│ └───────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 3: Louvain 커뮤니티 탐지                             │  │
│ │ • 연결된 뉴스들로 유사도 그래프 생성                       │  │
│ │ • 가중치 = 공통 엔티티 개수                               │  │
│ │ • resolution=2.0으로 커뮤니티 탐지                        │  │
│ └───────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 4: 크기 기반 필터링                                  │  │
│ │ • MIN_GROUP_SIZE=7: 너무 작은 그룹 제외                   │  │
│ │ • MAX_GROUP_SIZE=20: 허브 엔티티 오그룹화 제거            │  │
│ │ • 필터링된 뉴스는 ungrouped로 처리                        │  │
│ └───────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│ OUTPUT: groups[] (각 그룹의 news_ids, shared_entities)         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [PHASE 3.5] 그룹 인사이트 추출                                  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ LLM 인사이트 추출 (extract_group_insight)                 │  │
│ │                                                            │  │
│ │ • 그룹 주제 (Group Theme): 공통 주제 한 문장 요약         │  │
│ │ • 다층적 위험 관점 (Risk Perspectives):                  │  │
│ │   - EVENT_SUPPLIER: 이벤트-협력사 관점                   │  │
│ │   - MATERIAL_DEPENDENCY: 소재 의존성 관점                │  │
│ │   - POLICY_REGULATION: 정책/규제 관점                    │  │
│ │   - REGIONAL_FOCUS: 지역별 영향 관점                     │  │
│ │   - TEMPORAL_CHAIN: 시간적 연쇄 효과 관점                │  │
│ │                                                            │  │
│ │ • 복합 위험 패턴 (Compound Risk Pattern):                │  │
│ │   단일 뉴스로는 보이지 않던 복합 위험                     │  │
│ │                                                            │  │
│ │ • 숨은 연관성 (Hidden Connections):                       │  │
│ │   뉴스들 간 인과관계, 시간적 선후관계                     │  │
│ │                                                            │  │
│ │ • 검색 우선순위 (Search Priority):                        │  │
│ │   Agent_3가 가장 먼저 검색해야 할 엔티티                 │  │
│ │                                                            │  │
│ │ OUTPUT: group_insight                                      │  │
│ └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [PHASE 4] Scenario Group 생성                                   │
│                                                                  │
│ • 공유 엔티티 기준 클러스터링 (Louvain/Leiden)                 │
│ • 그룹 서사 생성 (LLM)                                          │
│ • 그룹별 통합 문서 생성 (title, summary, keywords 통합)       │
│ OUTPUT: grouped_news[], ungrouped_news[]                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ [OUTPUT] 그룹화된 뉴스                                          │
│ • 그룹화된 뉴스 (grouped_news[])                                │
│ • 그룹 인사이트 (group_insight)                                 │
│ • KG 경로 (kg_paths[])                                          │
│ • 미그룹화 뉴스 (ungrouped_news[])                              │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 노드별 상세 설명

#### validate_input
- **역할**: 입력 데이터 검증
- **처리**: 필수 필드 확인 (title_ko, keywords)

#### extract_entities_llm
- **역할**: LLM을 통한 엔티티 추출
- **처리**:
  - 뉴스 제목/요약/본문에서 공급망 관련 엔티티 추출
  - 8개 타입: Country, Company, Material, Technology, Policy, Event, Location, Organization
- **출력**: extracted_entities[] (엔티티명 + 타입)

#### match_entities_string
- **역할**: 추출된 엔티티를 Insight KG와 매칭
- **처리**:
  1. Exact Match: 정확 일치 (대소문자 무시)
  2. Fuzzy Match: 부분 문자열 + Levenshtein 거리 < 3
- **출력**: matched_kg_entities[] (엔티티명 + 매칭 방법)

#### extract_group_insight
- **역할**: 그룹화된 뉴스에서 인사이트 추출
- **처리**:
  - LLM이 그룹 내 뉴스들을 분석
  - 다층적 위험 관점, 복합 위험 패턴, 숨은 연관성, 검색 우선순위 추출

---

## 4. 출력 구조 상세

### 4.1 전체 구조

```json
{
  "processing_date": "2026-07-08T16:41:32.515576",
  "processing_time_seconds": 96.12,
  "batch_settings": {
    "batch_size": 5,
    "batch_delay_seconds": 3.0,
    "max_concurrent": 5,
    "total_batches": 17
  },
  "total_news": 85,
  "success_count": 82,
  "error_count": 3,
  
  "statistics": {
    "matched_news_count": 74,
    "total_matched_entities": 191,
    "total_groups": 9,
    "ungrouped_news_count": 39,
    "group_insight_enabled": true,
    "groups_with_insights": 8
  },
  
  "phase2_results": [
    { /* 뉴스별 KG 매칭 결과 */ }
  ]
}
```

### 4.2 뉴스별 결과 구조 (Phase 2)

```json
{
  // ===== 입력 정보 (Agent_1 출력) =====
  "news_id": "19d6b590086c81142e4d17371546c619",
  "title_ko": "중국의 드문 미사일 시험 발사는 경계하는 태평양 국가들을 결속시킬 것이다",
  "summary_ko": "중국이 핵 잠수함에서 태평양으로 탄도 미사일을 발사했다. 이 시험은 중국의 군사력 증가에 대한 지역 국가들의 방어 관계 강화를 촉진할 것으로 예상된다...",
  "keywords": [
    {"keyword": "중국", "score": 0.95},
    {"keyword": "호주", "score": 0.9},
    {"keyword": "일본", "score": 0.9}
  ],
  
  // ===== STEP 2: LLM 엔티티 추출 =====
  "extracted_entities": [
    {"entity": "중국", "type": "Country"},
    {"entity": "호주", "type": "Country"},
    {"entity": "일본", "type": "Country"},
    {"entity": "필리핀", "type": "Country"},
    {"entity": "뉴질랜드", "type": "Country"}
  ],
  
  // ===== STEP 3: Insight KG 매칭 =====
  "matched_kg_entities": [
    {"entity": "중국", "type": "Country", "match_method": "exact"},
    {"entity": "호주", "type": "Country", "match_method": "exact"},
    {"entity": "일본", "type": "Country", "match_method": "exact"},
    {"entity": "필리핀", "type": "Country", "match_method": "exact"}
  ]
}
```

### 4.3 그룹화된 뉴스 구조 (Phase 4)

```json
{
  "news_id": "group_002",
  "title_ko": "[그룹 group_002] 국가발전개혁위원회(NDRC) 외자 및 해외투자국 DDG가 중국 주 콩고 민주공화국 대사와 만나다 외 3건",
  "content_ko": "[뉴스 1/4] ...\n[뉴스 2/4] ...\n[뉴스 3/4] ...\n[뉴스 4/4] ...",
  "summary_ko": "- 4월 27일, 중국 국가발전개혁위원회(NDRC) 외자 및 해외투자국 부국장 DDG가 콩고 민주공화국 대사와 만나 양국의 광업 협력 가능성을 논의했다...",
  
  // 그룹 내 모든 뉴스의 키워드 통합
  "keywords": [
    {"keyword": "콩고민주공화국", "score": 0.95, "normalized": "콩고민주공화국"},
    {"keyword": "중국 히타치 그룹", "score": 0.95, "normalized": "중국히타치그룹"},
    {"keyword": "일대일로", "score": 0.85, "normalized": "일대일로"}
  ],
  
  // ===== Phase 3.5: 그룹 인사이트 =====
  "group_insight": {
    "group_theme": "중국 NDRC가 콩고, 히타치와 자원 투자 및 인프라 협력 강화",
    
    "risk_perspectives": [
      {
        "perspective_type": "MATERIAL_DEPENDENCY",
        "description": "콩고의 희토류 및 광물 자원 의존성 증가로 공급망 리스크 발생 가능",
        "key_entities": ["콩고민주공화국", "희토류", "광업협력"],
        "recommended_search_targets": ["RAW_MATERIAL_MASTER", "SUPPLIER_MASTER"],
        "confidence": 0.9
      },
      {
        "perspective_type": "REGIONAL_FOCUS",
        "description": "아프리카-중국 간 협력 강화로 지역별 공급망 재편 가능성",
        "key_entities": ["콩고민주공화국", "중국", "아프리카"],
        "recommended_search_targets": ["SITE_MASTER"],
        "confidence": 0.85
      }
    ],
    
    "compound_risk_pattern": "중국 NDRC가 콩고(자원 확보) + 히타치(기술 협력)를 동시에 강화하는 전략적 움직임. 단일 뉴스로는 보이지 않던 자원-기술 연계 패턴.",
    
    "hidden_connections": [
      {
        "news_id_from": "news_001",
        "news_id_to": "news_002",
        "relationship": "temporal",
        "description": "4월 27일 콩고 대사 회동 → 5월 23일 콩고 외무장관 회담 (관계 심화)"
      }
    ],
    
    "search_priorities": [
      {
        "priority_rank": 1,
        "entity": "콩고민주공화국",
        "reason": "희토류 주요 생산국, 공급망 집중도 높음"
      },
      {
        "priority_rank": 2,
        "entity": "히타치",
        "reason": "기술 협력 파트너, 반도체 장비 공급 가능성"
      }
    ],
    
    "aggregate_confidence": 0.88
  },
  
  // 그룹 메타데이터
  "group_id": "group_002",
  "group_size": 4,
  "shared_entities": ["중국", "국가발전개혁위원회"],
  "is_relevant": true,
  "relevance_score": 0.9,
  "relevance_reason": "grouped_unified_document"
}
```

### 4.4 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `extracted_entities[]` | List[Dict] | LLM이 추출한 엔티티 (entity, type) |
| `matched_kg_entities[]` | List[Dict] | Insight KG와 매칭된 엔티티 (match_method) |
| `group_insight` | Dict | 그룹화된 뉴스의 인사이트 |
| `group_insight.risk_perspectives[]` | List[Dict] | 다층적 위험 관점 |
| `group_insight.compound_risk_pattern` | str | 복합 위험 패턴 |
| `group_insight.hidden_connections[]` | List[Dict] | 뉴스 간 숨은 연관성 |
| `group_insight.search_priorities[]` | List[Dict] | 검색 우선순위 |

---

## 5. Insight KG 매칭

### 5.1 Insight KG란?

**Insight Knowledge Graph** = 과거 뉴스 데이터에서 추출한 **엔티티-관계 그래프**

- **노드**: Country, Company, Material, Technology, Policy, Event, Location, Organization
- **엣지**: CAUSAL, POLICY_REGULATION, SUPPLY, GEOGRAPHIC, DESCRIPTIVE

### 5.2 매칭 방식

#### 1단계: LLM 엔티티 추출

```python
# 입력
news = {
    "title_ko": "중국의 미사일 시험 발사",
    "summary_ko": "중국이 핵 잠수함에서 태평양으로 탄도 미사일을 발사..."
}

# LLM 추출
extracted_entities = [
    {"entity": "중국", "type": "Country"},
    {"entity": "호주", "type": "Country"},
    {"entity": "일본", "type": "Country"}
]
```

#### 2단계: Insight KG 매칭

```python
# Insight KG에 존재하는 엔티티
kg_entities = ["중국", "호주", "일본", "필리핀", "TSMC", "희토류", ...]

# Exact Match
matched_entities = []
for entity in extracted_entities:
    if entity["entity"] in kg_entities:
        matched_entities.append({
            "entity": entity["entity"],
            "type": entity["type"],
            "match_method": "exact"
        })

# Fuzzy Match (Levenshtein 거리 < 3)
for entity in extracted_entities:
    if entity not in matched_entities:
        for kg_entity in kg_entities:
            if levenshtein_distance(entity["entity"], kg_entity) < 3:
                matched_entities.append({
                    "entity": entity["entity"],
                    "type": entity["type"],
                    "match_method": "fuzzy"
                })
```

### 5.3 매칭 결과

```json
{
  "matched_kg_entities": [
    {"entity": "중국", "type": "Country", "match_method": "exact"},
    {"entity": "호주", "type": "Country", "match_method": "exact"},
    {"entity": "일본", "type": "Country", "match_method": "exact"}
  ]
}
```

---

## 6. 그룹 인사이트 추출

### 6.1 개념

**그룹 인사이트** = 그룹화된 뉴스들을 분석하여 **단일 뉴스로는 보이지 않던 복합 위험**을 발견

### 6.2 다층적 위험 관점 (Risk Perspectives)

Agent_5는 5가지 위험 관점을 자동 탐지합니다:

1. **EVENT_SUPPLIER**: 이벤트와 협력사/생산지 관련 관점
   - 예: "SK하이닉스 공장 화재 → 협력사 공급 차질"

2. **MATERIAL_DEPENDENCY**: 소재 의존성 관점
   - 예: "우크라이나 전쟁 → 네온가스 공급 중단"

3. **POLICY_REGULATION**: 정책/규제 관점
   - 예: "미국 반도체법 → 중국 기업 제재"

4. **REGIONAL_FOCUS**: 지역별 영향 관점
   - 예: "대만 지진 → 아시아 생산지 집중도 위험"

5. **TEMPORAL_CHAIN**: 시간적 연쇄 효과 관점
   - 예: "뉴스 A 규제 → 뉴스 B 대응 전략 → 뉴스 C 시장 변화"

### 6.3 인사이트 추출 프로세스

```python
# 그룹 정보
group = {
    "group_id": "group_002",
    "news_count": 4,
    "shared_entities": ["중국", "국가발전개혁위원회"],
    "news_summaries": [
        "뉴스 1: 중국 NDRC, 콩고 대사 회동...",
        "뉴스 2: 중국 NDRC, 콩고 외무장관 회담...",
        "뉴스 3: 중국 NDRC, 히타치 CEO 회동...",
        "뉴스 4: 중국 NDRC, 히타치 CEO 회담..."
    ]
}

# LLM에게 전달
insight = extract_group_insight(group)

# 출력
{
    "group_theme": "중국 NDRC가 콩고, 히타치와 자원 투자 및 인프라 협력 강화",
    "risk_perspectives": [
        {
            "perspective_type": "MATERIAL_DEPENDENCY",
            "description": "콩고의 희토류 및 광물 자원 의존성 증가",
            "key_entities": ["콩고민주공화국", "희토류"],
            "recommended_search_targets": ["RAW_MATERIAL_MASTER"]
        }
    ],
    "compound_risk_pattern": "자원 확보 + 기술 협력의 전략적 연계",
    "hidden_connections": [
        {
            "news_id_from": "news_001",
            "news_id_to": "news_002",
            "relationship": "temporal",
            "description": "4월 → 5월, 관계 심화"
        }
    ]
}
```

### 6.4 Agent_3 활용

Agent_3 DB Searcher는 **그룹 인사이트**를 활용하여 더 정교한 검색을 수행합니다:

```python
# Agent_5 출력
group_insight = {
    "risk_perspectives": [
        {
            "perspective_type": "MATERIAL_DEPENDENCY",
            "key_entities": ["콩고민주공화국", "희토류"],
            "recommended_search_targets": ["RAW_MATERIAL_MASTER"]
        }
    ],
    "search_priorities": [
        {"priority_rank": 1, "entity": "콩고민주공화국"}
    ]
}

# Agent_3가 활용
# 1. recommended_search_targets → 검색 테이블 결정
# 2. key_entities → 검색 키워드 우선순위
# 3. search_priorities → 검색 순서 결정
```

---

## 7. 실전 예시

### 7.1 뉴스 입력

```json
[
  {
    "news_id": "news_001",
    "title_ko": "국가발전개혁위원회(NDRC) 외자 및 해외투자국 DDG가 중국 주 콩고 민주공화국 대사와 만나다",
    "keywords": ["콩고민주공화국", "중국 국가발전개혁위원회", "광업 협력"]
  },
  {
    "news_id": "news_002",
    "title_ko": "중국 국가발전개혁위원회 위원장 정산제, 콩고민주공화국 부총리 겸 외무장관 크리스토프 루툰둘라와 회담",
    "keywords": ["콩고민주공화국", "중국 국가발전개혁위원회", "일대일로"]
  },
  {
    "news_id": "news_003",
    "title_ko": "국제협력부 차관보, 중국 히타치 그룹 아케타 아츠히로 CEO와 회동",
    "keywords": ["중국 히타치 그룹", "국가발전개혁위원회", "경제 및 기술 교류"]
  }
]
```

### 7.2 STEP 2: LLM 엔티티 추출

```json
{
  "news_001": {
    "extracted_entities": [
      {"entity": "콩고민주공화국", "type": "Country"},
      {"entity": "중국", "type": "Country"},
      {"entity": "국가발전개혁위원회", "type": "Organization"}
    ]
  },
  "news_002": {
    "extracted_entities": [
      {"entity": "콩고민주공화국", "type": "Country"},
      {"entity": "중국", "type": "Country"},
      {"entity": "국가발전개혁위원회", "type": "Organization"},
      {"entity": "일대일로", "type": "Policy"}
    ]
  },
  "news_003": {
    "extracted_entities": [
      {"entity": "히타치", "type": "Company"},
      {"entity": "중국", "type": "Country"},
      {"entity": "국가발전개혁위원회", "type": "Organization"}
    ]
  }
}
```

### 7.3 STEP 3: Insight KG 매칭

```json
{
  "news_001": {
    "matched_kg_entities": [
      {"entity": "콩고민주공화국", "match_method": "exact"},
      {"entity": "중국", "match_method": "exact"}
    ]
  },
  "news_002": {
    "matched_kg_entities": [
      {"entity": "콩고민주공화국", "match_method": "exact"},
      {"entity": "중국", "match_method": "exact"}
    ]
  },
  "news_003": {
    "matched_kg_entities": [
      {"entity": "히타치", "match_method": "exact"},
      {"entity": "중국", "match_method": "exact"}
    ]
  }
}
```

### 7.4 Phase 3: KG Hop 거리 기반 그룹화

```python
# STEP 1: 공통 엔티티 확인
news_001_entities = {"콩고민주공화국", "중국", "국가발전개혁위원회"}
news_002_entities = {"콩고민주공화국", "중국", "국가발전개혁위원회", "일대일로"}
news_003_entities = {"히타치", "중국", "국가발전개혁위원회"}

# STEP 2: 뉴스 001-002 간 공통 엔티티 KG 연결성 검증
common_001_002 = {"중국", "국가발전개혁위원회", "콩고민주공화국"}  # 3개
if are_common_entities_connected(kg_graph, common_001_002, max_hop=2):
    # 공통 엔티티들이 KG에서 연결됨 → 그룹화 가능
    similarity_graph.add_edge("news_001", "news_002", weight=3)

# STEP 3: 뉴스 002-003 간 공통 엔티티 KG 연결성 검증
common_002_003 = {"중국", "국가발전개혁위원회"}  # 2개
if are_common_entities_connected(kg_graph, common_002_003, max_hop=2):
    # 공통 엔티티들이 KG에서 연결됨 → 그룹화 가능
    similarity_graph.add_edge("news_002", "news_003", weight=2)

# STEP 4: Louvain 커뮤니티 탐지
communities = louvain_communities(similarity_graph, resolution=2.0)
# → [{"news_001", "news_002", "news_003"}]

# STEP 5: 크기 필터링 (MIN_GROUP_SIZE=7, MAX_GROUP_SIZE=20)
if 7 <= len(community) <= 20:
    group_002 = {
        "news_ids": ["news_001", "news_002", "news_003"],
        "shared_entities": ["중국", "국가발전개혁위원회", "콩고민주공화국"]
    }
else:
    # 필터링 → ungrouped 처리
    pass
```

### 7.5 Phase 3.5: 그룹 인사이트 추출

```json
{
  "group_theme": "중국 NDRC가 콩고, 히타치와 자원 투자 및 인프라 협력 강화",
  
  "risk_perspectives": [
    {
      "perspective_type": "MATERIAL_DEPENDENCY",
      "description": "콩고의 희토류 및 광물 자원 의존성 증가로 공급망 리스크 발생 가능",
      "key_entities": ["콩고민주공화국", "희토류", "광업협력"],
      "recommended_search_targets": ["RAW_MATERIAL_MASTER", "SUPPLIER_MASTER"],
      "confidence": 0.9
    },
    {
      "perspective_type": "REGIONAL_FOCUS",
      "description": "아프리카-중국 간 협력 강화로 지역별 공급망 재편 가능성",
      "key_entities": ["콩고민주공화국", "중국", "아프리카"],
      "recommended_search_targets": ["SITE_MASTER"],
      "confidence": 0.85
    }
  ],
  
  "compound_risk_pattern": "중국 NDRC가 콩고(자원 확보) + 히타치(기술 협력)를 동시에 강화하는 전략적 움직임. 단일 뉴스로는 보이지 않던 자원-기술 연계 패턴.",
  
  "hidden_connections": [
    {
      "news_id_from": "news_001",
      "news_id_to": "news_002",
      "relationship": "temporal",
      "description": "4월 27일 콩고 대사 회동 → 5월 23일 콩고 외무장관 회담 (관계 심화)"
    }
  ],
  
  "search_priorities": [
    {
      "priority_rank": 1,
      "entity": "콩고민주공화국",
      "reason": "희토류 주요 생산국, 공급망 집중도 높음"
    },
    {
      "priority_rank": 2,
      "entity": "히타치",
      "reason": "기술 협력 파트너, 반도체 장비 공급 가능성"
    }
  ]
}
```

### 7.6 해석

- **발견**: 3개 뉴스가 모두 "중국 NDRC"를 공유하고, 이들 엔티티가 KG에서 연결되어 있음 → 하나의 그룹으로 묶임
- **인사이트**: 
  - 자원(콩고) + 기술(히타치) 동시 강화 패턴 발견
  - 시간적 선후관계 (4월 → 5월, 관계 심화)
- **품질 보장**: 단순 엔티티 중복이 아닌 KG 연결성 기반 → 허위 그룹화 방지
- **다음 액션**: Agent_3가 콩고, 히타치 관련 공급망 엔티티 우선 검색

---

## 8. 설정 및 구성

### 8.1 주요 설정 (config.py)

```python
# ===== Phase 2: 엔티티 매칭 =====
ENTITY_EXTRACTION_MODEL = "gpt-4o-mini"
EXACT_MATCH_ENABLED = True
FUZZY_MATCH_ENABLED = True
FUZZY_MATCH_MIN_LENGTH = 2

# ===== Phase 3: KG Hop 기반 그룹화 =====
MAX_HOP = 2  # 그룹화 시 KG 경로 탐색 최대 거리
             # 1 = 직접 연결, 2 = 1개 중간 노드

# 크기 기반 필터링
MIN_GROUP_SIZE = 7   # 최소 그룹 크기
MAX_GROUP_SIZE = 20  # 최대 그룹 크기 (허브 엔티티 오그룹화 방지)

# ===== Phase 3.5: 그룹 인사이트 =====
GROUP_INSIGHT_ENABLED = True
GROUP_MIN_NEWS_COUNT = 2
GROUP_INSIGHT_MODEL = "gpt-4o"
GROUP_INSIGHT_TEMPERATURE = 0.4
GROUP_INSIGHT_MAX_TOKENS = 1500
GROUP_INSIGHT_TIMEOUT = 90

# ===== Phase 4: 클러스터링 =====
CLUSTERING_ALGORITHM = "louvain"  # "louvain" | "leiden"
MIN_NEWS_IN_GROUP = 2
```

### 8.2 Insight KG 구조

```
insight_kg/
├── graph_chunk_entity_relation_normalized.graphml  # 메인 KG
├── vdb_entities.json                                # 엔티티 벡터 인덱스
├── vdb_relationships.json                           # 관계 벡터 인덱스
└── vdb_chunks.json                                  # 청크 벡터 인덱스
```

### 8.3 디렉터리 구조

```
dev/Agent_5_News_Grouper/
├── config.py                    # 설정 파일
├── graph.py                     # LangGraph 워크플로우 정의 (Phase 2)
├── prompts.py                   # LLM 프롬프트
├── nodes/                       # 노드별 구현
│   ├── phase2_validate_input.py
│   ├── phase2_extract_entities_llm.py
│   └── phase2_match_entities_string.py
├── utils/                       # 유틸리티
│   ├── kg_loader.py            # KG 로딩
│   ├── kg_path_finder.py       # 경로 탐색
│   └── group_insight_extractor.py  # 인사이트 추출
├── scripts/
│   ├── run_phase2.py           # Phase 2 실행
│   ├── run_phase3.py           # Phase 3 실행
│   └── run_phase4.py           # Phase 4 실행
└── output/
    ├── output_news_grouper.json     # Phase 2 출력
    ├── output_phase3_groups.json    # Phase 3 출력
    └── output_phase4_tags.json      # Phase 4 출력
```

---

## 9. 활용 방안

### 9.1 Agent_3 연동

```python
# Agent_5 출력
grouped_news = load_news_grouper_output()

for group in grouped_news["results"]:
    if group.get("group_insight"):
        # Agent_3에 전달
        agent3_input = {
            "news_id": group["news_id"],
            "title_ko": group["title_ko"],
            "summary_ko": group["summary_ko"],
            "keywords": group["keywords"],
            "group_insight": group["group_insight"]  # 핵심!
        }
        # Agent_3가 group_insight를 활용하여 더 정교한 검색 수행
```

### 9.2 대시보드 연동

```python
# 그룹 요약 대시보드
for group in grouped_news["results"]:
    if group.get("group_insight"):
        dashboard.show_group_card({
            "title": group["title_ko"],
            "theme": group["group_insight"]["group_theme"],
            "risk_perspectives": group["group_insight"]["risk_perspectives"],
            "compound_risk": group["group_insight"]["compound_risk_pattern"]
        })
```

### 9.3 트렌드 분석

```python
# 주간 Risk 트렌드
all_perspectives = []
for group in grouped_news["results"]:
    if group.get("group_insight"):
        all_perspectives.extend(
            p["perspective_type"]
            for p in group["group_insight"]["risk_perspectives"]
        )

top_perspectives = Counter(all_perspectives).most_common(5)
print("이번 주 TOP 5 위험 관점:")
for perspective, count in top_perspectives:
    print(f"- {perspective}: {count}회")
```

---

## 10. FAQ

### Q1. Insight KG는 어떻게 구축되나요?

**A**: 
- 과거 뉴스 데이터에서 엔티티-관계 추출
- NetworkX 기반 그래프 생성
- GraphML 포맷으로 저장

### Q2. 그룹 인사이트가 생성되지 않는 경우는?

**A**: 
- 그룹 크기 < 2 (MIN_NEWS_IN_GROUP)
- GROUP_INSIGHT_ENABLED = False
- LLM 타임아웃 (TIMEOUT 증가 필요)

### Q3. Fuzzy Match는 언제 사용되나요?

**A**: 
- Exact Match 실패 시
- Levenshtein 거리 < 3
- 최소 문자 수 >= 2

### Q4. 그룹화 알고리즘은 어떻게 작동하나요?

**A**: 
- **1단계**: 공통 엔티티 ≥ 2개 확인
- **2단계**: 공통 엔티티들이 KG에서 연결되어 있는지 검증 (MAX_HOP=2)
- **3단계**: Louvain 커뮤니티 탐지로 클러스터링 (resolution=2.0)
- **4단계**: 크기 필터링 (MIN_GROUP_SIZE=7, MAX_GROUP_SIZE=20)
- **핵심**: 단순 엔티티 중복이 아닌 **KG 연결성 기반** 그룹화로 허위 그룹화 방지

### Q5. Agent_3는 그룹 인사이트를 어떻게 활용하나요?

**A**: 
- `recommended_search_targets` → 검색 테이블 결정
- `key_entities` → 검색 키워드 우선순위
- `search_priorities` → 검색 순서 결정
- 다중 시나리오 생성 시 `risk_perspectives` 활용

### Q6. 성능은 어느 정도인가요?

**A**: 
- 뉴스 1개당 처리 시간: 평균 **1-2초** (Phase 2)
- 그룹 인사이트 추출: 그룹당 **5-8초** (Phase 3.5)
- LLM 호출 횟수: 엔티티 추출(1회) + 인사이트 추출(그룹별 1회)

---

## 부록

### A. 엔티티 타입

| 타입 | 설명 | 예시 |
|------|------|------|
| Country | 국가 및 지역 | 중국, 미국, 대만 |
| Company | 기업 및 조직 | TSMC, 삼성전자, SK하이닉스 |
| Material | 원자재 및 소재 | 희토류, 네온가스, 실리콘 웨이퍼 |
| Technology | 기술 | EUV, 3nm 공정, AI |
| Policy | 정책 및 규제 | 반도체법, 수출 통제, CHIPS Act |
| Event | 이벤트 | 지진, 화재, 파업 |
| Location | 장소 및 시설 | 평택 공장, 호르무즈 해협 |
| Organization | 기관 | NDRC, ITC, 상무부 |

### B. 관련 문서

- Agent_1 News Analyzer 문서: `Markdown/Module/DOCS/DOCS_NEWS_ANALYZER.md`
- Agent_3 DB Searcher 문서: `Markdown/Module/DOCS/DOCS_DB_SEARCHER.md`

### C. 변경 이력

| 날짜 | 버전 | 내용 |
|------|------|------|
| 2026-07-08 | 1.0 | 최초 작성 (그룹 인사이트 추출 포함) |
| 2026-07-09 | 1.1 | Phase 3 그룹화 로직 업데이트: 단순 엔티티 중복 → KG Hop 거리 기반 그룹화 |

---

**문서 작성자**: POC-A 개발팀  
**최종 업데이트**: 2026-07-09
