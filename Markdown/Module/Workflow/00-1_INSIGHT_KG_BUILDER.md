# Insight Knowledge Graph 구축 (사전 단계)

## 목차
- [개요](#개요)
- [KG 구축 프로세스](#kg-구축-프로세스)
- [기능별 상세 설명](#기능별-상세-설명)
- [엔티티 타입 및 관계 카테고리](#엔티티-타입-및-관계-카테고리)
- [실행 방법](#실행-방법)

---

## 개요

### 역할
Agent_5 (News Grouper)가 사용하는 **Knowledge Graph (KG)**를 사전에 구축하는 프로세스입니다. 6개의 글로벌 공급망 인사이트 레포트를 입력으로 하여 **LightRAG** 기반 KG를 생성합니다.

### 파이프라인 위치
```
[사전 단계: KG 구축] → Agent_1 → Agent_5 (KG 활용) → ...
```

### 입출력
| 구분 | 내용 |
|------|------|
| **입력** | INSIGHT_REPORT_MASTER.description_refined (6개 레포트) |
| **출력** | `graph_chunk_entity_relation_normalized.graphml` (정규화된 KG) |
| **도구** | LightRAG + OpenAI GPT-4o-mini |
| **DB** | news_intelligence.db |

---

## KG 구축 프로세스

### 전체 흐름

```
1. 레포트 로드 (DB)
    ↓
2. 레포트 통합
    ↓
3. LightRAG KG 구축 (엔티티 추출 + 관계 추출)
    ↓
4. 엔티티 정규화 테이블 생성
    ↓
5. 정규화 적용 (GRAPHML 업데이트)
    ↓
6. 관계 카테고리 분류
    ↓
7. 최종 KG 저장
```

### 주요 파일

| 파일명 | 역할 |
|--------|------|
| `insight_kg_builder.py` | KG 구축 메인 스크립트 (Step 1-3) |
| `insight_kg_entity_normalizer_builder.py` | 엔티티 정규화 테이블 생성 (Step 4) |
| `insight_kg_entity_normalizer_applier.py` | 정규화 적용 (Step 5) |
| `insight_kg_relation_categorizer.py` | 관계 카테고리 분류 (Step 6) |
| `lightrag_entity_extraction_prompt.txt` | 엔티티 추출 프롬프트 |
| `lightrag_relation_extraction_prompt.txt` | 관계 추출 프롬프트 |

---

## 기능별 상세 설명

### 1. insight_kg_builder.py (KG 구축)

#### 📋 설명
6개의 글로벌 공급망 인사이트 레포트를 LightRAG로 처리하여 Knowledge Graph를 구축합니다.

#### 🤖 사용 모델
- **엔티티 추출**: `gpt-4o-mini`
- **관계 추출**: `gpt-4o-mini`
- **임베딩**: `text-embedding-3-small`
- **타임아웃**: 60초
- **Retry**: Rate Limit 발생 시 3회 재시도 (3초, 6초, 9초 대기)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `description_refined` | str | INSIGHT_REPORT_MASTER 테이블의 정제된 레포트 본문 |

#### 📤 출력값
| 필드명 | 파일명 | 설명 |
|--------|--------|------|
| Graph | `graph_chunk_entity_relation.graphml` | KG (GRAPHML 형식) |
| Embeddings | `vdb_chunks.json` | 청크 벡터 임베딩 |
| Key-Value Store | `kv_store_full_docs.json` | 문서 원본 저장소 |

**출력 경로**: `poc-a/data/NEWS/insight_kg/`

#### 💬 프롬프트

**엔티티 추출 프롬프트** (`lightrag_entity_extraction_prompt.txt`):
```
# 엔티티 추출 가이드라인

## 엔티티 타입 정의 (8개)
1. Country (국가 및 지역): 중국, 미국, 일본, 한국, 대만, EU
2. Company (기업 및 조직): TSMC, 삼성전자, 인텔, ASML, 애플
3. Material (원자재 및 소재): 희토류, 코발트, 갈륨, 네온가스, 실리콘 웨이퍼
4. Policy (정책 및 규제): 수출통제, Entity List, CHIPS법, CBAM
5. Event (이벤트): 제재, 파업, 사이버공격, 지진, 공장 중단
6. Location (장소 및 시설): 공장, 항만, 광산, 신주, 평택
7. Technology (기술): EUV, 파운드리, 3나노 공정, AI 반도체
8. Organization (기관): KOTRA, BIS, OFAC, EU 집행위원회

## 추출 규칙
- 명확한 타입 분류: 반드시 위 8개 중 하나
- 고유명사 우선: 구체적 이름이 있는 엔티티 우선
- 정규 표기: 한글 공식 명칭 우선
- 중복 제거: 동일 엔티티의 이형은 하나로 통일

## 출력 형식
엔티티명 | 타입
예: 중국 | Country
예: TSMC | Company
```

**관계 추출 프롬프트** (`lightrag_relation_extraction_prompt.txt`):
```
# 관계 추출 가이드라인

## 관계 카테고리 정의 (5개)
1. CAUSAL (인과관계): 원인-결과, 직접적 영향 (가중치 1.0)
   예: "중국의 수출통제로 인해 일본의 갈륨 공급이 중단"
   
2. POLICY_REGULATION (정책규제): 정부/기관의 규제 행위 (가중치 1.0)
   예: "미국 BIS가 SMIC를 Entity List에 등재"
   
3. SUPPLY (공급관계): 공급, 의존, 소싱 관계 (가중치 1.0)
   예: "민주콩고가 전 세계 코발트의 70%를 공급"
   
4. GEOGRAPHIC (지리관계): 지리적 위치, 소속 (가중치 0.5)
   예: "TSMC 본사는 대만 신주에 위치"
   
5. DESCRIPTIVE (서술관계): 단순 언급, 동시 출현 (가중치 0.2)
   예: "레포트에서 중국과 반도체를 언급"

## 카테고리 우선순위
CAUSAL > POLICY_REGULATION > SUPPLY > GEOGRAPHIC > DESCRIPTIVE

## 출력 형식
[CATEGORY:카테고리명] 관계 설명
예: [CATEGORY:CAUSAL] 수출통제로 인한 공급 중단
```

#### 📝 예시

**입력 (INSIGHT_REPORT_MASTER)**:
```json
[
  {
    "report_id": "RPT_001",
    "title": "중국 희토류 공급망 리스크",
    "description_refined": "중국이 전 세계 희토류의 70%를 생산하며, 2023년 수출 쿼터제를 강화했다. 이로 인해 일본과 미국의 반도체 제조 기업들이 조달 어려움을 겪고 있다..."
  },
  {
    "report_id": "RPT_002",
    "title": "미국 반도체 수출통제",
    "description_refined": "미국 BIS가 2024년 1월 SMIC를 Entity List에 추가하여 EUV 장비 수출을 금지했다. 이는 중국의 첨단 반도체 생산 능력을 제약하기 위한 조치다..."
  }
]
```

**출력 (graph_chunk_entity_relation.graphml 일부)**:
```xml
<node id="중국">
  <data key="entity_type">Country</data>
</node>

<node id="희토류">
  <data key="entity_type">Material</data>
</node>

<node id="SMIC">
  <data key="entity_type">Company</data>
</node>

<edge source="중국" target="희토류">
  <data key="description">[CATEGORY:SUPPLY] 전 세계 희토류의 70%를 생산</data>
  <data key="weight">1.0</data>
</edge>

<edge source="중국" target="일본">
  <data key="description">[CATEGORY:CAUSAL] 수출 쿼터제 강화로 조달 어려움 유발</data>
  <data key="weight">1.0</data>
</edge>

<edge source="미국" target="SMIC">
  <data key="description">[CATEGORY:POLICY_REGULATION] Entity List 추가로 EUV 장비 수출 금지</data>
  <data key="weight">1.0</data>
</edge>
```

---

### 2. insight_kg_entity_normalizer_builder.py (정규화 테이블 생성)

#### 📋 설명
LightRAG가 생성한 KG의 엔티티 이름을 정규화하기 위한 **매핑 테이블**을 생성합니다. 동일 엔티티의 이형(異形)을 표준 표기로 통일합니다.

#### 🤖 사용 모델
- **모델**: `gpt-4o-mini`
- **온도**: 0.2
- **타임아웃**: 60초
- **응답 형식**: JSON

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `graph_entities` | List[str] | KG의 모든 엔티티 이름 |

#### 📤 출력값
| 필드명 | 파일명 | 설명 |
|--------|--------|------|
| Normalization Table | `entity_normalization_lookup.json` | 이형 → 표준 표기 매핑 |

**entity_normalization_lookup.json 구조**:
```json
{
  "TSMC": "대만반도체제조회사",
  "Taiwan Semiconductor": "대만반도체제조회사",
  "台积电": "대만반도체제조회사",
  "SK하이닉스": "에스케이하이닉스",
  "SK Hynix": "에스케이하이닉스",
  "美国": "미국",
  "United States": "미국",
  "美國": "미국"
}
```

#### 💬 프롬프트

**System**:
```
당신은 엔티티 정규화 전문가입니다.
```

**User**:
```
다음 엔티티 목록에서 동일한 실체를 가리키는 이형(異形)들을 찾아 표준 표기로 통일하는 매핑 테이블을 생성해주세요.

**엔티티 목록** (1,234개):
{entity_list}

**정규화 규칙**:
1. 국가명: 한글 공식 명칭 (예: "美国" / "United States" → "미국")
2. 기업명: 한글 정식 명칭 우선 (예: "TSMC" / "台积电" → "대만반도체제조회사")
3. 소재명: 한글 명칭 (예: "Cobalt" / "钴" → "코발트")
4. 약어 확장: 정식 명칭으로 (예: "SK하이닉스" / "SK Hynix" → "에스케이하이닉스")
5. 영문 → 한글 우선

**출력 형식 (JSON)**:
{
  "TSMC": "대만반도체제조회사",
  "台积电": "대만반도체제조회사",
  "美国": "미국"
}
```

#### 📝 예시

**입력 (graph_entities)**:
```json
[
  "TSMC",
  "Taiwan Semiconductor",
  "台积电",
  "SK하이닉스",
  "SK Hynix",
  "미국",
  "美国",
  "United States",
  "희토류",
  "Rare Earth"
]
```

**출력 (entity_normalization_lookup.json)**:
```json
{
  "TSMC": "대만반도체제조회사",
  "Taiwan Semiconductor": "대만반도체제조회사",
  "台积电": "대만반도체제조회사",
  "SK하이닉스": "에스케이하이닉스",
  "SK Hynix": "에스케이하이닉스",
  "美国": "미국",
  "United States": "미국",
  "Rare Earth": "희토류"
}
```

---

### 3. insight_kg_entity_normalizer_applier.py (정규화 적용)

#### 📋 설명
생성된 정규화 테이블을 KG에 적용하여 모든 엔티티 이름을 표준 표기로 변환합니다.

#### 🤖 사용 모델
LLM 호출 없음 (문자열 치환)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `graph_original` | GRAPHML | 원본 KG |
| `normalization_table` | JSON | 정규화 매핑 |

#### 📤 출력값
| 필드명 | 파일명 | 설명 |
|--------|--------|------|
| Normalized Graph | `graph_chunk_entity_relation_normalized.graphml` | 정규화된 KG |

#### 처리 로직

```python
# 1. GRAPHML 로드
graph = nx.read_graphml("graph_chunk_entity_relation.graphml")

# 2. 정규화 테이블 로드
with open("entity_normalization_lookup.json", 'r') as f:
    norm_table = json.load(f)

# 3. 노드 ID 변경
mapping = {}
for node in graph.nodes():
    if node in norm_table:
        mapping[node] = norm_table[node]

graph = nx.relabel_nodes(graph, mapping)

# 4. 저장
nx.write_graphml(graph, "graph_chunk_entity_relation_normalized.graphml")
```

#### 📝 예시

**입력 (원본 GRAPHML)**:
```xml
<node id="TSMC">
  <data key="entity_type">Company</data>
</node>

<node id="台积电">
  <data key="entity_type">Company</data>
</node>

<edge source="TSMC" target="애플">
  <data key="description">A17 칩 공급</data>
</edge>

<edge source="台积电" target="삼성전자">
  <data key="description">파운드리 경쟁</data>
</edge>
```

**출력 (정규화 후)**:
```xml
<node id="대만반도체제조회사">
  <data key="entity_type">Company</data>
</node>

<edge source="대만반도체제조회사" target="애플">
  <data key="description">A17 칩 공급</data>
</edge>

<edge source="대만반도체제조회사" target="삼성전자">
  <data key="description">파운드리 경쟁</data>
</edge>
```

---

### 4. insight_kg_relation_categorizer.py (관계 카테고리 분류)

#### 📋 설명
KG 엣지의 `description` 필드에서 `[CATEGORY:타입]` 태그를 추출하여 `category` 속성으로 추가합니다.

#### 🤖 사용 모델
LLM 호출 없음 (정규표현식 파싱)

#### 📥 입력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `graph_normalized` | GRAPHML | 정규화된 KG |

#### 📤 출력값
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `category` | str | 관계 카테고리 (5개 중 하나) |
| `weight` | float | 신뢰도 가중치 |

**카테고리별 가중치**:
```python
CATEGORY_WEIGHTS = {
    "CAUSAL": 1.0,
    "POLICY_REGULATION": 1.0,
    "SUPPLY": 1.0,
    "GEOGRAPHIC": 0.5,
    "DESCRIPTIVE": 0.2
}
```

#### 처리 로직

```python
import re

# 1. GRAPHML 로드
graph = nx.read_graphml("graph_chunk_entity_relation_normalized.graphml")

# 2. 각 엣지의 description에서 [CATEGORY:타입] 추출
for u, v, data in graph.edges(data=True):
    description = data.get('description', '')
    
    # 정규표현식: [CATEGORY:타입]
    match = re.search(r'\[CATEGORY:([A-Z_]+)\]', description)
    
    if match:
        category = match.group(1)
        weight = CATEGORY_WEIGHTS.get(category, 0.2)
        
        # 속성 추가
        data['category'] = category
        data['weight'] = weight
    else:
        # 태그 없음 → DESCRIPTIVE로 간주
        data['category'] = "DESCRIPTIVE"
        data['weight'] = 0.2

# 3. 저장
nx.write_graphml(graph, "graph_chunk_entity_relation_normalized.graphml")
```

#### 📝 예시

**입력 (엣지 description)**:
```
[CATEGORY:CAUSAL] 중국의 수출통제로 인해 일본의 갈륨 공급이 중단되었다
```

**출력 (엣지 속성 추가)**:
```xml
<edge source="중국" target="일본">
  <data key="description">[CATEGORY:CAUSAL] 중국의 수출통제로 인해 일본의 갈륨 공급이 중단되었다</data>
  <data key="category">CAUSAL</data>
  <data key="weight">1.0</data>
</edge>
```

---

## 엔티티 타입 및 관계 카테고리

### 엔티티 타입 (8개)

| 타입 | 설명 | 예시 |
|------|------|------|
| **Country** | 국가, 지역, 경제권 | 중국, 미국, 일본, EU, 대만 |
| **Company** | 기업, 조직 | TSMC, 삼성전자, ASML, SK하이닉스 |
| **Material** | 원자재, 소재 | 희토류, 코발트, 갈륨, 네온가스, 실리콘 웨이퍼 |
| **Policy** | 정책, 규제 | 수출통제, Entity List, CHIPS법, CBAM |
| **Event** | 사건, 위기 | 제재, 파업, 사이버공격, 지진 |
| **Location** | 장소, 시설 | 공장, 항만, 광산, 신주, 평택 |
| **Technology** | 기술, 공정 | EUV, 파운드리, 3나노 공정, AI 반도체 |
| **Organization** | 기관, 단체 | KOTRA, BIS, OFAC, EU 집행위원회 |

### 관계 카테고리 (5개)

| 카테고리 | 가중치 | 설명 | 예시 |
|----------|--------|------|------|
| **CAUSAL** | 1.0 | 인과관계 | "중국의 수출통제로 일본의 공급 중단" |
| **POLICY_REGULATION** | 1.0 | 정책규제 | "미국 BIS가 SMIC를 Entity List 등재" |
| **SUPPLY** | 1.0 | 공급관계 | "민주콩고가 전 세계 코발트 70% 공급" |
| **GEOGRAPHIC** | 0.5 | 지리관계 | "TSMC 본사는 대만 신주에 위치" |
| **DESCRIPTIVE** | 0.2 | 서술관계 | "레포트에서 중국과 반도체 언급" |

---

## 실행 방법

### 최초 1회 실행 (KG 구축)

```powershell
# 1. insight_kg 폴더로 이동
cd C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a\dev\insight_kg

# 2. KG 구축 (Step 1-3)
python insight_kg_builder.py

# 3. 엔티티 정규화 테이블 생성 (Step 4)
python insight_kg_entity_normalizer_builder.py

# 4. 정규화 적용 (Step 5)
python insight_kg_entity_normalizer_applier.py

# 5. 관계 카테고리 분류 (Step 6)
python insight_kg_relation_categorizer.py
```

### 실행 결과 확인

```powershell
# KG 파일 확인
Get-ChildItem "C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a\data\NEWS\insight_kg"
```

**출력 파일**:
- `graph_chunk_entity_relation.graphml` (원본 KG)
- `graph_chunk_entity_relation_normalized.graphml` (정규화 + 카테고리 분류 완료)
- `entity_normalization_lookup.json` (정규화 테이블)
- `kv_store_full_docs.json` (문서 원본)
- `vdb_chunks.json` (벡터 임베딩)

### Agent_5에서 활용

Agent_5의 `match_entities_string` 노드가 `graph_chunk_entity_relation_normalized.graphml`을 로드하여 뉴스 엔티티 매칭에 사용합니다.

```python
# Agent_5: match_entities_string 노드
import networkx as nx

# KG 로드
kg_path = "data/NEWS/insight_kg/graph_chunk_entity_relation_normalized.graphml"
kg = nx.read_graphml(kg_path)

# 뉴스 엔티티 매칭
news_entities = ["TSMC", "대만", "희토류"]
matched = []

for entity in news_entities:
    # 1. 정확 매칭
    if entity in kg.nodes:
        matched.append({"entity": entity, "match_method": "exact"})
    else:
        # 2. Fuzzy 매칭 (부분 문자열)
        for node in kg.nodes:
            if entity.lower() in node.lower() or node.lower() in entity.lower():
                matched.append({"entity": entity, "match_method": "fuzzy", "kg_node": node})
                break

print(f"매칭 결과: {len(matched)}개")
```

---

## 설정

### LightRAG 설정

| 항목 | 값 | 설명 |
|------|-----|------|
| `working_dir` | `poc-a/data/NEWS/insight_kg` | KG 저장 경로 |
| `llm_model` | `gpt-4o-mini` | 엔티티/관계 추출 모델 |
| `embedding_model` | `text-embedding-3-small` | 임베딩 모델 |
| `chunk_size` | 1200 토큰 | 청크 크기 |
| `max_async` | 4 | 동시 API 호출 수 |
| `max_token_size` | 4096 | LLM 최대 토큰 |

### 프롬프트 경로

| 파일명 | 경로 |
|--------|------|
| `lightrag_entity_extraction_prompt.txt` | `poc-a/config/` |
| `lightrag_relation_extraction_prompt.txt` | `poc-a/config/` |

---

## 통계 예시

### KG 규모 (6개 레포트 기준)

| 항목 | 개수 |
|------|------|
| **엔티티 (정규화 전)** | 1,234개 |
| **엔티티 (정규화 후)** | 856개 |
| **관계 (엣지)** | 2,089개 |
| **CAUSAL 엣지** | 487개 (23.3%) |
| **POLICY_REGULATION 엣지** | 312개 (14.9%) |
| **SUPPLY 엣지** | 598개 (28.6%) |
| **GEOGRAPHIC 엣지** | 423개 (20.2%) |
| **DESCRIPTIVE 엣지** | 269개 (12.9%) |

### 주요 엔티티 (degree 순)

| 엔티티 | 타입 | Degree | 설명 |
|--------|------|--------|------|
| 중국 | Country | 342 | 가장 많이 연결된 국가 |
| 희토류 | Material | 189 | 핵심 원자재 |
| 미국 | Country | 156 | 규제 주체 |
| TSMC | Company | 143 | 핵심 반도체 기업 |
| 코발트 | Material | 98 | 배터리 핵심 소재 |

---

## 문서 네비게이션

- **다음**: [Agent_1: News Analyzer](01_AGENT_1_NEWS_ANALYZER.md)
- **활용**: [Agent_5: News Grouper](02_AGENT_5_NEWS_GROUPER.md)
- **개요**: [시스템 개요 (00_OVERVIEW.md)](00_OVERVIEW.md)

---

**작성일**: 2026-07-12  
**버전**: 1.0
