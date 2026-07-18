# 실행 예시 (Full Pipeline)

## 목차
- [개요](#개요)
- [시나리오 1: 전체 파이프라인 (Case 1: DB O + Risk O + 진행형)](#시나리오-1-전체-파이프라인-case-1-db-o--risk-o--진행형)
- [시나리오 2: 관련성 필터링 (is_relevant=False)](#시나리오-2-관련성-필터링-is_relevantfalse)
- [시나리오 3: 다중 시나리오 모드 (Agent_3/4)](#시나리오-3-다중-시나리오-모드-agent_34)
- [시나리오 4: HITL 케이스 (Agent_2 매핑 품질 낮음)](#시나리오-4-hitl-케이스-agent_2-매핑-품질-낮음)
- [시나리오 5: 신규 키워드 제안 (Agent_4)](#시나리오-5-신규-키워드-제안-agent_4)

---

## 개요

이 문서는 **비정형 Risk 센싱 Agent**의 5개 모듈(Agent_1, Agent_5, Agent_2, Agent_3, Agent_4)을 거치는 전체 파이프라인 실행 예시를 제공합니다.

각 시나리오는 **입력 뉴스 → 각 모듈 통과 → 최종 출력**의 State 변화를 단계별로 보여줍니다.

---

## 시나리오 1: 전체 파이프라인 (Case 1: DB O + Risk O + 진행형)

### 입력 뉴스

```json
{
  "news_id": "news_20260712_001",
  "title": "China Halts Rare Earth Exports to US",
  "summary": "Chinese government announced immediate halt on rare earth exports to United States effective July 1, 2026.",
  "content": "The Chinese Ministry of Commerce issued an emergency order on June 30, 2026, prohibiting all exports of rare earth materials to the United States. This measure affects 17 rare earth elements critical for semiconductor manufacturing, including neodymium, dysprosium, and terbium. Industry analysts warn that US semiconductor manufacturers may face severe supply chain disruptions. Major affected companies include Intel, Micron, and several smaller chip makers that rely on Chinese rare earth supplies for advanced packaging processes."
}
```

---

### Agent_1: News Analyzer

#### 입력
```json
{
  "news_id": "news_20260712_001",
  "title": "China Halts Rare Earth Exports to US",
  "content": "The Chinese Ministry of Commerce issued..."
}
```

#### 출력
```json
{
  "title_ko": "중국, 희토류 대미 수출 전면 중단",
  "summary_ko": "중국 정부가 2026년 7월 1일부터 미국에 대한 희토류 수출을 전면 중단한다고 발표했다. 이 조치는 네오디뮴, 디스프로슘, 테르븀 등 반도체 제조에 필수적인 17개 희토류 원소에 영향을 미친다. 인텔, 마이크론 등 미국 반도체 제조사들의 공급망 차질이 우려된다.",
  "content_ko": "중국 상무부가 2026년 6월 30일 긴급 명령을 발표하며...",
  "original_language": "english",
  "keywords": [
    {
      "keyword": "희토류",
      "score": 0.98,
      "category": "소재/부품/화학물질",
      "reason": "반도체 제조 핵심 원자재"
    },
    {
      "keyword": "중국",
      "score": 0.95,
      "category": "물류거점/경로",
      "reason": "희토류 주요 생산국"
    },
    {
      "keyword": "미국",
      "score": 0.92,
      "category": "물류거점/경로",
      "reason": "수출 중단 대상국"
    },
    {
      "keyword": "수출 중단",
      "score": 0.90,
      "category": "리스크 이벤트",
      "reason": "공급망 차질 유발 사건"
    },
    {
      "keyword": "인텔",
      "score": 0.85,
      "category": "기업/기관",
      "reason": "영향받는 미국 반도체 기업"
    },
    {
      "keyword": "마이크론",
      "score": 0.82,
      "category": "기업/기관",
      "reason": "영향받는 미국 반도체 기업"
    },
    {
      "keyword": "네오디뮴",
      "score": 0.78,
      "category": "소재/부품/화학물질",
      "reason": "희토류 원소"
    }
  ],
  "is_relevant": true,
  "relevance_score": 0.96,
  "relevance_reason": "[원자재&희소물질 > 희토류 공급] 중국의 희토류 수출 중단은 반도체 제조 핵심 원자재 공급에 직접 영향"
}
```

---

### Agent_5: News Grouper

#### 입력
```json
{
  "title_ko": "중국, 희토류 대미 수출 전면 중단",
  "summary_ko": "중국 정부가 2026년 7월 1일부터...",
  "keywords": [...]
}
```

#### 출력
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
      "entity": "인텔",
      "type": "Company"
    },
    {
      "entity": "마이크론",
      "type": "Company"
    },
    {
      "entity": "중국 상무부",
      "type": "Organization"
    }
  ],
  "matched_kg_entities": [
    {
      "entity": "중국",
      "type": "Country",
      "match_method": "exact",
      "kg_node": "중국"
    },
    {
      "entity": "미국",
      "type": "Country",
      "match_method": "exact",
      "kg_node": "미국"
    },
    {
      "entity": "희토류",
      "type": "Material",
      "match_method": "exact",
      "kg_node": "희토류"
    },
    {
      "entity": "인텔",
      "type": "Company",
      "match_method": "fuzzy",
      "kg_node": "인텔"
    }
  ]
}
```

---

### Agent_2: Tag Mapper

#### 입력
```json
{
  "keywords": [
    {"keyword": "희토류", "score": 0.98},
    {"keyword": "중국", "score": 0.95},
    {"keyword": "수출 중단", "score": 0.90}
  ]
}
```

#### 출력
```json
{
  "keyword_tag_hints": [
    {
      "keyword": "희토류",
      "predicted_tag_types": ["MATERIAL", "RAW_MATERIAL"],
      "confidence": 0.98
    },
    {
      "keyword": "중국",
      "predicted_tag_types": ["SITE"],
      "confidence": 0.95
    },
    {
      "keyword": "수출 중단",
      "predicted_tag_types": ["EVENT"],
      "confidence": 0.92
    }
  ],
  "exact_matched_tags": [
    {
      "keyword": "희토류",
      "tag_id": "MAT_RARE_EARTH",
      "tag_name": "희토류",
      "tag_type": "MATERIAL",
      "jaccard_score": 1.0
    },
    {
      "keyword": "중국",
      "tag_id": "SITE_CHINA",
      "tag_name": "중국",
      "tag_type": "SITE",
      "jaccard_score": 1.0
    }
  ],
  "unmatched_keywords": ["수출 중단"],
  "potential_event_tags": [
    {
      "keyword": "수출 중단",
      "category": "EVENT",
      "confidence": 0.92,
      "suggested_tag_name": "EVT_수출중단"
    }
  ],
  "mapped_tags": [
    {"tag_id": "MAT_RARE_EARTH", "tag_name": "희토류", "tag_type": "MATERIAL"},
    {"tag_id": "SITE_CHINA", "tag_name": "중국", "tag_type": "SITE"}
  ],
  "mapping_quality_score": 0.67,
  "requires_hitl": true,
  "hitl_reason": "신규 EVENT 태그 제안 존재 (1개)"
}
```

---

### Agent_3: DB Searcher

#### 입력
```json
{
  "mapped_tags": [
    {"tag_id": "MAT_RARE_EARTH", "tag_name": "희토류"},
    {"tag_id": "SITE_CHINA", "tag_name": "중국"}
  ]
}
```

#### 출력
```json
{
  "risk_scenario": "중국의 희토류 수출 중단으로 삼성전자 협력사 5곳(ABC Materials, XYZ Corp, DEF Industries, GHI Tech, JKL Supplies)의 조달에 차질이 예상됨. 해당 협력사들은 반도체 제조 핵심 부품을 공급하고 있어 생산 차질 우려.",
  "risk_scenario_entities": ["희토류", "중국", "ABC Materials", "XYZ Corp", "DEF Industries"],
  "impact_level": "HIGH",
  "risk_scenario_confidence": 0.94,
  "domain_rules": [
    {
      "rule_id": "RULE_MAT_001",
      "rule_name": "소재 공급 차단 시 협력사 조회",
      "search_strategy": "material_supplier_lookup"
    }
  ],
  "search_target_entities": ["희토류"],
  "generated_sql": "SELECT DISTINCT s.supplier_id, s.supplier_name, s.country, m.material_name FROM SUPPLIER_MASTER s INNER JOIN SUPPLIER_MATERIAL sm ON s.supplier_id = sm.supplier_id INNER JOIN MATERIAL_MASTER m ON sm.material_id = m.material_id WHERE m.material_name LIKE '%희토류%' AND s.country = '중국' LIMIT 100",
  "sql_explanation": "중국 소재 협력사 중 희토류를 공급하는 업체 조회",
  "search_results": [
    {
      "supplier_id": "SUP_001",
      "supplier_name": "ABC Materials",
      "country": "중국",
      "material_name": "희토류"
    },
    {
      "supplier_id": "SUP_005",
      "supplier_name": "XYZ Corp",
      "country": "중국",
      "material_name": "희토류"
    },
    {
      "supplier_id": "SUP_012",
      "supplier_name": "DEF Industries",
      "country": "중국",
      "material_name": "희토류"
    },
    {
      "supplier_id": "SUP_023",
      "supplier_name": "GHI Tech",
      "country": "중국",
      "material_name": "희토류"
    },
    {
      "supplier_id": "SUP_034",
      "supplier_name": "JKL Supplies",
      "country": "중국",
      "material_name": "희토류"
    }
  ]
}
```

---

### Agent_4: Risk Evaluator

#### 입력
```json
{
  "risk_scenario": "중국의 희토류 수출 중단으로 삼성전자 협력사 5곳...",
  "search_results": [5개 협력사]
}
```

#### 출력
```json
{
  "is_risk": true,
  "risk_score": 0.94,
  "risk_justification": "중국이 희토류 수출을 전면 중단했으며, DB에서 5개 협력사가 중국산 희토류에 의존하는 것으로 확인됨. 해당 협력사들은 삼성전자에 핵심 부품을 공급하므로 공급망 차질 불가피. 네오디뮴, 디스프로슘 등 대체 불가 소재로 단기 대응 어려움.",
  "risk_factors": [
    "희토류 공급 차단",
    "중국 수출통제",
    "협력사 조달 위험",
    "단일 소싱 의존"
  ],
  "event_timing": "ONGOING",
  "event_timing_confidence": 0.98,
  "event_timing_justification": "뉴스 제목에 '전면 중단' 키워드, '7월 1일부터'라는 확정 시점 명시. 이미 시행된 조치로 판단.",
  "issue_type": "ISSUE",
  "issue_priority": "HIGH",
  "classification_reason": "DB 검색 결과 존재 (5개 협력사) + Risk 판정 (is_risk=True) + 진행형 이벤트 (ONGOING) → Case 1",
  "recommended_keywords": [],
  "requires_keyword_hitl": false
}
```

---

### 최종 출력 요약

| 항목 | 값 | 설명 |
|------|-----|------|
| **이슈 타입** | ISSUE | 즉시 대응 필요 |
| **우선순위** | HIGH | 최우선 처리 |
| **Risk 점수** | 0.94 | 매우 높음 |
| **Risk 요인** | 4개 | 희토류 공급 차단, 중국 수출통제, 협력사 조달 위험, 단일 소싱 의존 |
| **영향받는 협력사** | 5개 | ABC Materials, XYZ Corp, DEF Industries, GHI Tech, JKL Supplies |
| **이벤트 시점** | ONGOING | 진행형 |
| **HITL 필요** | Yes | Agent_2 (신규 EVENT 태그 "수출 중단") |

---

## 시나리오 2: 관련성 필터링 (is_relevant=False)

### 입력 뉴스

```json
{
  "news_id": "news_20260712_002",
  "title": "트럼프 전 대통령, 자사 주식 추가 매입",
  "summary": "도널드 트럼프가 자신의 회사 주식을 100만 달러 규모로 추가 매입했다고 밝혔다.",
  "content": "도널드 트럼프 전 미국 대통령이 7월 10일 자신의 미디어 회사 주식을 100만 달러 규모로 추가 매입했다. 트럼프는 소셜 미디어를 통해 '회사의 미래를 믿는다'고 밝혔다. 시장 전문가들은 이번 매입이 주가 부양을 위한 상징적 제스처로 보고 있다."
}
```

---

### Agent_1: News Analyzer

#### 입력
```json
{
  "news_id": "news_20260712_002",
  "title": "트럼프 전 대통령, 자사 주식 추가 매입",
  "content": "도널드 트럼프 전 미국 대통령이..."
}
```

#### 출력
```json
{
  "title_ko": "트럼프 전 대통령, 자사 주식 추가 매입",
  "summary_ko": "도널드 트럼프가 자신의 미디어 회사 주식을 100만 달러 규모로 추가 매입했다고 밝혔다. 시장 전문가들은 주가 부양을 위한 상징적 제스처로 평가.",
  "content_ko": "...",
  "original_language": "korean",
  "keywords": [
    {
      "keyword": "트럼프",
      "score": 0.88,
      "category": "기업/기관",
      "reason": "인물명"
    },
    {
      "keyword": "주식 매입",
      "score": 0.75,
      "category": "리스크 이벤트",
      "reason": "금융 이벤트"
    }
  ],
  "is_relevant": false,
  "relevance_score": 0.05,
  "relevance_reason": "개인 주식 매입 뉴스로 8개 Risk Factor와 무관함. 반도체 공급망과 직접적 연관성 없음."
}
```

---

### 파이프라인 종료

**`is_relevant=False`로 판정되어 Agent_5, Agent_2, Agent_3, Agent_4로 전달되지 않음.**

**최종 상태**: 필터링 (DROP)

---

## 시나리오 3: 다중 시나리오 모드 (Agent_3/4)

### 입력 뉴스

```json
{
  "news_id": "news_20260712_003",
  "title": "대만 지진으로 TSMC 공장 일부 중단, 중국 희토류 수출 규제 강화 동시 발생",
  "summary": "대만에서 규모 6.5 지진이 발생하여 TSMC 신주 공장 일부가 중단되었으며, 동시에 중국 정부가 희토류 수출 규제를 강화한다고 발표했다.",
  "content": "..."
}
```

---

### Agent_1 → Agent_5 → Agent_2 (생략)

**매핑 태그**:
- `TAG_SITE_TAIWAN` (대만)
- `TAG_COMPANY_TSMC` (TSMC)
- `TAG_EVENT_EARTHQUAKE` (지진)
- `TAG_MATERIAL_RARE_EARTH` (희토류)
- `TAG_SITE_CHINA` (중국)

---

### Agent_3: DB Searcher (다중 시나리오 생성)

#### 출력
```json
{
  "risk_scenarios": [
    {
      "scenario_id": "cluster_001",
      "scenario_text": "대만 지진으로 TSMC 신주 공장 일부 중단, 삼성전자 파운드리 조달 차질 예상",
      "entities": ["대만", "TSMC", "지진"],
      "impact_level": "HIGH",
      "confidence": 0.92
    },
    {
      "scenario_id": "cluster_002",
      "scenario_text": "중국 희토류 수출 규제 강화로 협력사 3곳 조달 차질 우려",
      "entities": ["중국", "희토류"],
      "impact_level": "MEDIUM",
      "confidence": 0.88
    }
  ],
  "generated_sqls": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "sql": "SELECT DISTINCT s.supplier_id, s.supplier_name FROM SUPPLIER_MASTER s WHERE s.supplier_name LIKE '%TSMC%' AND s.country = '대만' LIMIT 100"
    },
    {
      "sql_id": "sql_cluster_002",
      "scenario_id": "cluster_002",
      "sql": "SELECT DISTINCT s.supplier_id, s.supplier_name, m.material_name FROM SUPPLIER_MASTER s INNER JOIN SUPPLIER_MATERIAL sm ON s.supplier_id = sm.supplier_id INNER JOIN MATERIAL_MASTER m ON sm.material_id = m.material_id WHERE m.material_name LIKE '%희토류%' AND s.country = '중국' LIMIT 100"
    }
  ],
  "search_results_multi": [
    {
      "sql_id": "sql_cluster_001",
      "scenario_id": "cluster_001",
      "result_count": 1,
      "results": [
        {"supplier_id": "SUP_TSMC_001", "supplier_name": "TSMC", "country": "대만"}
      ]
    },
    {
      "sql_id": "sql_cluster_002",
      "scenario_id": "cluster_002",
      "result_count": 3,
      "results": [
        {"supplier_id": "SUP_001", "supplier_name": "ABC Materials", "material_name": "희토류"},
        {"supplier_id": "SUP_005", "supplier_name": "XYZ Corp", "material_name": "희토류"},
        {"supplier_id": "SUP_012", "supplier_name": "DEF Industries", "material_name": "희토류"}
      ]
    }
  ]
}
```

---

### Agent_4: Risk Evaluator (다중 시나리오 통합 평가)

#### 단계 1: 시나리오별 독립 평가

**cluster_001 평가**:
```json
{
  "scenario_id": "cluster_001",
  "is_risk": true,
  "risk_score": 0.90,
  "risk_justification": "TSMC 공장 중단으로 파운드리 조달 차질 불가피. DB에서 TSMC 의존도 확인.",
  "risk_factors": ["TSMC 생산 중단", "파운드리 공급 부족", "지진 영향"]
}
```

**cluster_002 평가**:
```json
{
  "scenario_id": "cluster_002",
  "is_risk": true,
  "risk_score": 0.85,
  "risk_justification": "희토류 공급 협력사 3곳 확인. 수출 규제 강화로 조달 비용 상승 및 차질 우려.",
  "risk_factors": ["희토류 공급 차단", "중국 수출규제"]
}
```

#### 단계 2: 통합 판정

```json
{
  "is_risk": true,
  "risk_score": 0.90,
  "risk_justification": "[cluster_001] TSMC 공장 중단으로 파운드리 조달 차질 불가피. DB에서 TSMC 의존도 확인.",
  "risk_factors": [
    "TSMC 생산 중단",
    "파운드리 공급 부족",
    "지진 영향",
    "희토류 공급 차단",
    "중국 수출규제"
  ],
  "final_risk_decision": {
    "leading_scenario_id": "cluster_001",
    "total_scenarios_evaluated": 2,
    "risk_scenarios_count": 2
  },
  "event_timing": "ONGOING",
  "issue_type": "ISSUE",
  "issue_priority": "HIGH"
}
```

---

### 최종 출력 요약

| 항목 | 값 |
|------|-----|
| **시나리오 개수** | 2개 |
| **Risk 시나리오** | 2개 (모두 Risk) |
| **최종 Risk 점수** | 0.90 (cluster_001 기준) |
| **이슈 타입** | ISSUE |
| **우선순위** | HIGH |
| **Risk 요인** | 5개 (통합) |

---

## 시나리오 4: HITL 케이스 (Agent_2 매핑 품질 낮음)

### 입력 뉴스

```json
{
  "news_id": "news_20260712_004",
  "title": "온두라스 공화국, 대만과 외교 단절 선언",
  "summary": "중미 국가 온두라스가 대만과의 외교 관계를 단절하고 중국과 수교한다고 발표했다.",
  "content": "..."
}
```

---

### Agent_1 출력 (생략)

**키워드**:
- "온두라스 공화국"
- "대만"
- "외교 단절"
- "중국"

**is_relevant**: True (지정학&규제 Risk Factor)

---

### Agent_2: Tag Mapper

#### 정확 매칭 결과

```json
{
  "exact_matched_tags": [
    {
      "keyword": "온두라스 공화국",
      "tag_id": "SUPPLIER_LASGAS",
      "tag_name": "라스가스",
      "matched_tag_keyword": "라스",
      "jaccard_score": 0.96
    },
    {
      "keyword": "대만",
      "tag_id": "SITE_TAIWAN",
      "tag_name": "대만",
      "jaccard_score": 1.0
    }
  ]
}
```

#### 매핑 품질 검증 (LLM)

```json
{
  "exact_matched_tags": [
    {
      "keyword": "대만",
      "tag_id": "SITE_TAIWAN",
      "tag_name": "대만"
    }
  ],
  "rejected_mappings": [
    {
      "keyword": "온두라스 공화국",
      "tag_id": "SUPPLIER_LASGAS",
      "decision": "REJECT",
      "reason": "semantic_mismatch",
      "detail": "'온두라스 공화국'은 중미 국가명(SITE)인데 'SUPPLIER_라스가스'(카타르 가스 기업)와 매칭됨. 부분 문자열 '라스' 우연 일치. 의미적 관련성 없음"
    }
  ],
  "mapped_tags": [
    {"tag_id": "SITE_TAIWAN", "tag_name": "대만"}
  ],
  "mapping_quality_score": 0.25,
  "requires_hitl": true,
  "hitl_reason": "거부된 매칭 존재 (1개), 매핑 품질 낮음 (0.25 < 0.6)"
}
```

---

### HITL 제안 내용

**사용자에게 표시되는 메시지**:
```
[HITL 필요] Agent_2 태그 매핑 품질이 낮습니다 (0.25).

거부된 매칭:
- "온두라스 공화국" → SUPPLIER_라스가스 (REJECT)
  근거: 의미적 관련성 없음. 부분 문자열 '라스' 우연 일치.

제안:
1. 뉴스 무관하게 처리 (NONE)
2. 매핑된 태그만으로 진행 (대만)
3. 수동 태그 추가

선택하세요:
```

---

### 최종 출력

**HITL 승인 후 파이프라인 계속 진행** 또는 **DROP**

---

## 시나리오 5: 신규 키워드 제안 (Agent_4)

### 전제 조건

- Risk로 판정된 뉴스 100개 존재
- 공통 키워드: "WBG 반도체", "탄소 배출권", "IRA 법안" 등
- 기존 Risk Factor 키워드셋에 **미등록**

---

### Agent_4: recommend_keywords 노드 실행

#### DB 집계 쿼리

```sql
SELECT kw.keyword, COUNT(*) as count
FROM NEWS_KEYWORD_EXTRACTION kw
INNER JOIN NEWS_RISK_EVALUATION risk ON kw.news_id = risk.news_id
WHERE risk.is_risk = 1
GROUP BY kw.keyword
ORDER BY count DESC
```

#### 집계 결과 (일부)

| keyword | count |
|---------|-------|
| 희토류 | 87 |
| 중국 | 76 |
| WBG 반도체 | 12 |
| 탄소 배출권 | 8 |
| IRA 법안 | 7 |
| 수출 규제 | 65 |

#### 기존 키워드셋 로드

**Excel**: `DB_TAG_Risk Factor Pool_vF.xlsx` → 시트 `2. Keyword Set_ai` → target_region='KR'

**로드된 키워드** (일부):
```
희토류, 중국, 수출 규제, CHIPS법, Entity List, ...
```

#### 필터링 로직

```python
KEYWORD_THRESHOLD = 5

# 1. 5회 이상 출현
filtered = [kw for kw in aggregated if kw['count'] >= KEYWORD_THRESHOLD]

# 2. 기존 키워드셋에 없음
new_keywords = [kw for kw in filtered if kw['keyword'] not in existing_keywords]
```

#### 결과

```json
{
  "recommended_keywords": [
    {
      "keyword": "WBG 반도체",
      "count": 12,
      "related_news_ids": ["news_045", "news_067", "news_089"],
      "sample_contexts": [
        "차세대 WBG 반도체 공급 부족 우려로 전력 반도체 시장 불안정...",
        "WBG 반도체 핵심 기업 투자 확대 발표...",
        "WBG 반도체 시장 급성장, 2030년까지 연평균 25% 성장 전망..."
      ]
    },
    {
      "keyword": "탄소 배출권",
      "count": 8,
      "related_news_ids": ["news_023", "news_056", "news_091"],
      "sample_contexts": [
        "EU 탄소 배출권 규제 강화로 반도체 기업 비용 부담 증가...",
        "탄소 배출권 가격 급등으로 공급망 전환 압력 가중...",
        "탄소 배출권 제도 변경, 반도체 업계 대응 방안 논의..."
      ]
    },
    {
      "keyword": "IRA 법안",
      "count": 7,
      "related_news_ids": ["news_034", "news_078", "news_099"],
      "sample_contexts": [
        "미국 IRA 법안으로 반도체 보조금 조건 강화...",
        "IRA 법안 세부 규정 발표, 국내 기업 영향 분석...",
        "IRA 법안 적용 기업 리스트 공개, 공급망 재편 예상..."
      ]
    }
  ],
  "requires_keyword_hitl": true
}
```

---

### HITL 제안 내용

**사용자에게 표시되는 메시지**:
```
[키워드 제안] 다음 키워드를 뉴스 수집용 Risk Factor 키워드로 추가하시겠습니까?

1. WBG 반도체 (12회 출현)
   관련 뉴스 예시:
   - news_045: "차세대 WBG 반도체 공급 부족 우려..."
   - news_067: "WBG 반도체 핵심 기업 투자 확대..."
   - news_089: "WBG 반도체 시장 급성장, 2030년까지..."

2. 탄소 배출권 (8회 출현)
   관련 뉴스 예시:
   - news_023: "EU 탄소 배출권 규제 강화..."
   - news_056: "탄소 배출권 가격 급등..."
   - news_091: "탄소 배출권 제도 변경..."

3. IRA 법안 (7회 출현)
   관련 뉴스 예시:
   - news_034: "미국 IRA 법안으로 반도체 보조금..."
   - news_078: "IRA 법안 세부 규정 발표..."
   - news_099: "IRA 법안 적용 기업 리스트..."

[선택]
- 전체 승인
- 개별 선택
- 거부
```

---

### 사용자 승인 후

**Excel 파일 업데이트** (`DB_TAG_Risk Factor Pool_vF.xlsx`):
- 시트 `2. Keyword Set_ai`에 3개 키워드 추가
- 다음 뉴스 수집 시 해당 키워드로 검색

---

## 문서 네비게이션

- **이전**: [Agent_4: Risk Evaluator](05_AGENT_4_RISK_EVALUATOR.md)
- **개요**: [시스템 개요 (00_OVERVIEW.md)](00_OVERVIEW.md)

---

**작성일**: 2026-07-12  
**버전**: 1.0
