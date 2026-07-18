# 뉴스 → 태그 매핑 파이프라인
### 공급망 리스크 뉴스 분석을 위한 태그 추출 및 활용 가이드

---

## 1. 개요

이 문서는 수집된 뉴스 원문에서 공급망 DB 검색을 위한 태그를 추출하고, 추출된 태그 조합을 분석하여 검색 전략을 수립하는 운영 파이프라인을 정의합니다.

**전제조건**: [Data Pipeline_Tag Creation_Docs.md](./Data%20Pipeline_Tag%20Creation_Docs.md)에 따라 태그가 이미 생성되어 있어야 합니다.

**태그 구조 요약**:
- **5가지 유형**: SUBSTANCE(소재), MATERIAL(자재), SUPPLIER(협력사), SITE(위치), EVENT(이벤트)
- **예상 태그 수**: 70~100개 (Risk Factor 기반 154개 키워드에서 정규화)
- **역할**: 정규화 사전 + LLM 스키마 힌트

---

## 2. 전체 파이프라인

```
[준비 단계] - 1회 실행
Risk Factor 키워드셋(154개)
  ↓
태그 생성(70-100개)
  ↓
태그 메타데이터 저장 (tag_id, tag_type, keywords, embeddings, target_table_column 등)

[운영 단계] - 뉴스마다 반복
뉴스 수집
  ↓
[1] 키워드 추출 (LLM + NER)
  ↓
[2] 정확 매칭 (OpenSearch 역인덱스)
  ↓
[3] 유사도 기반 매칭 (임베딩 벡터 유사도)
  ↓
[4] 신규 태그 후보 판별 (LLM)
  ↓
[5] Human-in-the-loop (태그 추가 승인)
  ↓
[6] 태그 조합 분석 (고위험 패턴 감지)
  ↓
[7] 검색 전략 수립 (LLM이 태그 메타데이터 기반으로 SQL 생성)
  ↓
[8] 공급망 DB 조회 → 영향 분석 결과 생성
```

---

## 3. 하이브리드 키워드 추출 및 태그 매핑

### 3.1 전체 프로세스 개요

```
뉴스 원문
  ↓
[단계 1] 키워드 추출 (LLM + NER)
  ↓
추출된 키워드 리스트
  ↓
[단계 2] 정확 매칭 (OpenSearch 역인덱스) ← 매칭 성공 → 태그 확정
  ↓
매칭 실패 키워드
  ↓
[단계 3] 유사도 기반 매칭 (임베딩) ← 유사도 ≥ 0.85 → 자동 태그 매핑
  ↓
매칭 실패 키워드
  ↓
[단계 4] LLM 태그 후보 판별 ← 태그로 부적절 → 폐기
  ↓                         태그로 적절 ↓
[단계 5] Human-in-the-loop (신규 태그 추가 승인)
```

---

### 3.2 단계별 세부 설명

#### 단계 1: 키워드 추출 (LLM + NER)

**목적**: 뉴스 원문에서 공급망 리스크 관련 키워드 추출

**방법**: LLM과 NER을 병행하여 상호 보완
- **LLM**: 맥락 이해, 복합 명사, 도메인 특화 용어 추출
- **NER**: 고유명사(협력사명, 지역명) 빠른 추출

**LLM 프롬프트 예시**:
```python
llm_prompt = f"""
뉴스 원문: {news_text}

공급망 리스크 분석을 위해 다음 유형의 키워드를 추출하세요:
1. 소재/자재 (예: 희토류, 네온, MLCC, 포토레지스트)
2. 협력사명 (예: ASML, JSR, SK하이닉스)
3. 위치 (예: 중국, 대만, 청주)
4. 이벤트 (예: 수출규제, 지진, 파업)

출력 형식:
{{
  "keywords": [
    {{"text": "희토류", "type": "SUBSTANCE"}},
    {{"text": "중국", "type": "SITE"}},
    {{"text": "수출규제", "type": "EVENT"}}
  ]
}}
"""
```

**NER 병행 실행**:
```python
# spaCy, Hugging Face 등으로 엔티티 추출
ner_entities = ner_model(news_text)
# 출력: [{"text": "ASML", "label": "ORG"}, {"text": "대만", "label": "LOC"}]
```

**통합**:
```python
# LLM과 NER 결과 병합 (중복 제거)
extracted_keywords = merge_and_deduplicate(llm_keywords, ner_entities)
# 결과: ["희토류", "중국", "수출규제", "ASML", "대만"]
```

**특징**:
- ✅ LLM: 맥락 이해, "ArF 포토레지스트" 같은 복합 명사 감지
- ✅ NER: 빠르고 비용 효율적, 고유명사 정확도 높음
- ✅ 병행: 상호 보완으로 재현율(recall) 극대화

---

#### 단계 2: 정확 매칭 (OpenSearch 역인덱스)

**목적**: 추출된 키워드를 기존 태그 DB와 정확히 일치하는지 검색

**방법**: OpenSearch 역인덱스 활용

**역인덱스란?**

일반적인 인덱싱(정인덱스, forward index)은 **"문서 → 단어 목록"** 형태입니다:
```
문서1: ["사과", "바나나", "포도"]
문서2: ["바나나", "딸기"]
```
이 방식으로는 "사과가 들어간 문서는?"을 찾으려면 모든 문서를 처음부터 끝까지 스캔해야 합니다. 문서가 수백만 개라면 매우 비효율적입니다.

**역인덱스(inverted index)는 이를 뒤집어 "단어 → 문서 목록" 형태로 저장**합니다:
```
"사과"   → [문서1]
"바나나" → [문서1, 문서2]
"포도"   → [문서1]
"딸기"   → [문서2]
```

이제 "사과"를 검색하면 역인덱스에서 "사과" 항목만 찾아가면 끝입니다. **책 뒤에 있는 "찾아보기(색인)"와 동일한 원리**입니다.

본 프로젝트의 경우:
```
키워드 → 태그 ID
"아르곤"    → AR
"Argon"     → AR
"희토류"    → REE
"Rare Earth" → REE
```

뉴스에서 "희토류"가 나오면 역인덱스에서 "희토류" 항목을 바로 찾아 `REE` 태그를 즉시 반환합니다. 70~100개 태그 × 평균 5개 키워드 = 500개 항목을 순회할 필요 없이 매우 짧은 시간에 검색이 완료됩니다.

---

**OpenSearch 스키마**:
```json
// 인덱스: tag_keywords
{
  "mappings": {
    "properties": {
      "tag_id": {"type": "keyword"},
      "keyword": {"type": "text", "analyzer": "standard"},
      "tag_type": {"type": "keyword"},
      "normalized": {"type": "keyword"}  // 정규화된 키워드 (소문자, 공백 제거)
    }
  }
}

// 문서 예시
{"tag_id": "AR", "keyword": "아르곤", "normalized": "아르곤"}
{"tag_id": "AR", "keyword": "Argon", "normalized": "argon"}
{"tag_id": "AR", "keyword": "아르곤가스", "normalized": "아르곤가스"}
{"tag_id": "REE", "keyword": "희토류", "normalized": "희토류"}
{"tag_id": "REE", "keyword": "Rare Earth", "normalized": "rareearth"}
```

**검색 쿼리**:
```python
from opensearchpy import OpenSearch

def exact_match_tags(keywords, opensearch_client):
    """
    OpenSearch 역인덱스로 정확 매칭
    """
    matched_tags = {}
    
    for keyword in keywords:
        # 정규화 (소문자 변환, 공백 제거)
        normalized = keyword.lower().replace(" ", "")
        
        # OpenSearch 쿼리
        query = {
            "query": {
                "term": {"normalized": normalized}
            }
        }
        
        result = opensearch_client.search(index="tag_keywords", body=query)
        
        if result["hits"]["total"]["value"] > 0:
            tag_id = result["hits"]["hits"][0]["_source"]["tag_id"]
            matched_tags[keyword] = tag_id
    
    return matched_tags

# 사용 예시
keywords = ["희토류", "중국", "수출규제", "ASML"]
matched = exact_match_tags(keywords, opensearch_client)
# 결과: {"희토류": "REE", "중국": "CHINA", "ASML": "ASML"}
# "수출규제"는 매칭 실패 → 다음 단계로
```

**장점** (Aho-Corasick 대비):
- ✅ **확장성**: 태그 수 증가해도 성능 일정 (인덱스 기반)
- ✅ **유연성**: fuzzy matching, n-gram 검색 확장 가능
- ✅ **운영 효율**: 태그 DB 업데이트 시 재색인만 하면 됨 (코드 수정 불필요)
- ✅ **분산 처리**: 대량 뉴스 배치 처리 시 OpenSearch 클러스터 활용
- ✅ **통합 관리**: 공급망 DB와 동일한 검색 엔진 활용 (인프라 통합)

**특징**:
- ✅ 속도 빠름 (O(log n), n = 태그 수)
- ✅ 비용 없음
- ✅ False Positive 최소화
- ❌ 동의어 변형 감지 불가 ("고순도 희토류" 같은 신규 표현 누락)

---

#### 단계 3: 유사도 기반 매칭 (임베딩 벡터)

**목적**: 정확 매칭에 실패한 키워드를 기존 태그와 의미적 유사도로 매핑

**방법**: 임베딩 벡터 코사인 유사도 계산

**사전 준비** (1회만):
```python
from sentence_transformers import SentenceTransformer

# 태그별 임베딩 벡터 생성
model = SentenceTransformer('distiluse-base-multilingual-cased-v1')

for tag_id, tag_data in tags_db.items():
    # 태그의 모든 키워드를 하나의 텍스트로 결합
    text = " ".join(tag_data["keywords"])
    tag_data["embedding"] = model.encode(text)
```

**실시간 매칭**:
```python
def similarity_match_tags(unmatched_keywords, tags_db, model, threshold=0.85):
    """
    임베딩 유사도 기반 태그 매칭
    """
    matched_tags = {}
    still_unmatched = []
    
    for keyword in unmatched_keywords:
        # 키워드 임베딩
        keyword_embedding = model.encode(keyword)
        
        # 모든 태그와 유사도 계산
        similarities = {
            tag_id: cosine_similarity(keyword_embedding, tag_data["embedding"])
            for tag_id, tag_data in tags_db.items()
        }
        
        best_tag = max(similarities, key=similarities.get)
        best_score = similarities[best_tag]
        
        if best_score >= threshold:
            # 자동 매핑
            matched_tags[keyword] = {
                "tag_id": best_tag,
                "similarity": best_score,
                "action": "auto_add_keyword"
            }
        else:
            # 다음 단계로
            still_unmatched.append(keyword)
    
    return matched_tags, still_unmatched

# 사용 예시
unmatched = ["수출규제", "고순도 아르곤"]
matched, still_unmatched = similarity_match_tags(unmatched, tags_db, model)
# 결과:
# matched = {"고순도 아르곤": {"tag_id": "AR", "similarity": 0.89}}
# still_unmatched = ["수출규제"]  # 유사도 < 0.85
```

**특징**:
- ✅ 동의어 변형 감지 ("고순도 아르곤" → "AR")
- ✅ 비용 낮음 (로컬 모델)
- ✅ 자동 처리 (threshold 이상이면 사람 개입 불필요)
- ⚠️ Threshold 조정 필요 (0.85가 적절한지 운영 중 검증)

---

#### 단계 4: LLM 태그 후보 판별

**목적**: 유사도 매칭에도 실패한 키워드가 태그로 적절한지 판단

**방법**: [DB_TAG_Tag Creation Methodology.md](./DB_TAG_Tag%20Creation%20Methodology.md) 5.4.3절의 태그 유형 판별 프롬프트 활용

**프롬프트 예시**:
```python
llm_prompt = f"""
당신은 공급망 리스크 분석을 위한 태그 적합성 판단 전문가입니다.

키워드: "{keyword}"
뉴스 맥락: {news_context}

기존 태그 DB 개요:
- SUBSTANCE: 소재 (예: 네온, 희토류, 아르곤)
- MATERIAL: 자재 (예: MLCC, 포토레지스트)
- SUPPLIER: 협력사 (예: ASML, JSR)
- SITE: 위치 (예: 중국, 대만, 일본)
- EVENT: 이벤트 (예: 수출규제, 지진, 파업)

질문:
1. 이 키워드는 공급망 리스크 분석에 유용한 태그가 될 수 있는가?
2. 유용하다면 어느 태그 유형인가?
3. 유용하지 않다면 왜 그런가?

출력 형식:
{{
  "is_valid_tag": true/false,
  "tag_type": "SUBSTANCE" | "MATERIAL" | "SUPPLIER" | "SITE" | "EVENT" | null,
  "reason": "...",
  "proposed_tag_id": "..." (옵션)
}}
"""
```

**판단 결과**:
```python
# 예시 1: 태그로 적절
{
  "is_valid_tag": true,
  "tag_type": "EVENT",
  "reason": "수출규제는 공급망에 직접 영향을 주는 이벤트",
  "proposed_tag_id": "EXPORT_CTRL"
}
→ Human-in-the-loop로 전달

# 예시 2: 태그로 부적절
{
  "is_valid_tag": false,
  "tag_type": null,
  "reason": "일반 명사로 공급망 리스크와 직접 관련 없음",
  "proposed_tag_id": null
}
→ 폐기
```

**특징**:
- ✅ 태그 생성 방법론의 필요조건 자동 검증
- ✅ 노이즈 키워드 필터링 (폐기 처리)
- ⚠️ LLM 비용 발생 (배치 처리로 최적화 필요)

---

#### 단계 5: Human-in-the-loop (신규 태그 추가 승인)

**목적**: LLM이 "태그로 적절"하다고 판단한 키워드를 사람이 최종 승인

**인터페이스**:
```python
# 검토 대기열
review_queue = [
    {
        "keyword": "수출규제",
        "news_context": "미국 정부가 중국 반도체 수출규제...",
        "llm_suggestion": {
            "tag_type": "EVENT",
            "proposed_tag_id": "EXPORT_CTRL",
            "reason": "공급망에 직접 영향을 주는 규제 이벤트"
        },
        "similar_existing_tags": [
            {"tag_id": "ENTITY_LIST", "similarity": 0.72},
            {"tag_id": "SANCTIONS", "similarity": 0.68}
        ]
    }
]

# 검토자 판단 옵션
# [승인] → 신규 태그 EXPORT_CTRL 생성
# [기존 태그에 병합] → "수출규제"를 ENTITY_LIST에 키워드로 추가
# [거부] → 폐기
```

**특징**:
- ✅ 태그 품질 보장 (사람 최종 검수)
- ✅ 매칭 실패 케이스만 개입 (운영 부담 최소화)
- ✅ 배치 검토 가능 (예: 주 1회 누적 분 일괄 검토)

---

### 3.3 통합 알고리즘

```python
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
from typing import List, Dict

class NewsToTagPipeline:
    """
    뉴스 → 키워드 추출 → 태그 매핑 통합 파이프라인
    """
    
    def __init__(
        self,
        tags_db: Dict,
        opensearch_client: OpenSearch,
        embedding_model: SentenceTransformer,
        ner_model,
        llm_client
    ):
        self.tags_db = tags_db
        self.opensearch = opensearch_client
        self.embedding_model = embedding_model
        self.ner_model = ner_model
        self.llm_client = llm_client
        self.similarity_threshold = 0.85
    
    def process_news(self, news_text: str) -> Dict:
        """
        전체 파이프라인 실행
        
        Returns:
            {
                "matched_tags": ["AR", "REE", "CHINA"],
                "auto_added_keywords": [{"tag_id": "AR", "keyword": "고순도 아르곤"}],
                "pending_review": [{"keyword": "수출규제", "llm_suggestion": {...}}],
                "discarded": ["일반 명사"]
            }
        """
        result = {
            "matched_tags": [],
            "auto_added_keywords": [],
            "pending_review": [],
            "discarded": []
        }
        
        # [단계 1] 키워드 추출 (LLM + NER)
        keywords = self.extract_keywords(news_text)
        
        # [단계 2] 정확 매칭 (OpenSearch)
        exact_matched, unmatched = self.exact_match(keywords)
        result["matched_tags"].extend(exact_matched.values())
        
        if not unmatched:
            return result
        
        # [단계 3] 유사도 기반 매칭
        similarity_matched, still_unmatched = self.similarity_match(unmatched)
        
        for keyword, match_info in similarity_matched.items():
            result["matched_tags"].append(match_info["tag_id"])
            result["auto_added_keywords"].append({
                "tag_id": match_info["tag_id"],
                "keyword": keyword,
                "similarity": match_info["similarity"]
            })
        
        if not still_unmatched:
            return result
        
        # [단계 4] LLM 태그 후보 판별
        for keyword in still_unmatched:
            llm_verdict = self.llm_judge_tag_candidate(keyword, news_text)
            
            if llm_verdict["is_valid_tag"]:
                # [단계 5] Human-in-the-loop 대기열
                result["pending_review"].append({
                    "keyword": keyword,
                    "llm_suggestion": llm_verdict,
                    "news_context": news_text[:200]
                })
            else:
                # 폐기
                result["discarded"].append(keyword)
        
        return result
    
    def extract_keywords(self, news_text: str) -> List[str]:
        """
        단계 1: LLM + NER로 키워드 추출
        """
        # LLM 키워드 추출
        llm_keywords = self.llm_client.extract_keywords(news_text)
        
        # NER 엔티티 추출
        ner_entities = self.ner_model.extract(news_text)
        
        # 병합 및 중복 제거
        all_keywords = set(llm_keywords + [e["text"] for e in ner_entities])
        
        return list(all_keywords)
    
    def exact_match(self, keywords: List[str]) -> tuple[Dict, List]:
        """
        단계 2: OpenSearch 역인덱스 정확 매칭
        
        Returns:
            (matched: {keyword: tag_id}, unmatched: [keyword])
        """
        matched = {}
        unmatched = []
        
        for keyword in keywords:
            # 정규화
            normalized = keyword.lower().replace(" ", "")
            
            # OpenSearch 쿼리
            query = {
                "query": {
                    "term": {"normalized": normalized}
                }
            }
            
            result = self.opensearch.search(
                index="tag_keywords",
                body=query,
                size=1
            )
            
            if result["hits"]["total"]["value"] > 0:
                tag_id = result["hits"]["hits"][0]["_source"]["tag_id"]
                matched[keyword] = tag_id
            else:
                unmatched.append(keyword)
        
        return matched, unmatched
    
    def similarity_match(
        self,
        keywords: List[str]
    ) -> tuple[Dict, List]:
        """
        단계 3: 임베딩 유사도 기반 매칭
        
        Returns:
            (matched: {keyword: {tag_id, similarity}}, unmatched: [keyword])
        """
        matched = {}
        unmatched = []
        
        for keyword in keywords:
            # 키워드 임베딩
            keyword_emb = self.embedding_model.encode(keyword)
            
            # 모든 태그와 유사도 계산
            best_tag = None
            best_score = 0
            
            for tag_id, tag_data in self.tags_db.items():
                similarity = self._cosine_similarity(
                    keyword_emb,
                    tag_data["embedding"]
                )
                
                if similarity > best_score:
                    best_score = similarity
                    best_tag = tag_id
            
            if best_score >= self.similarity_threshold:
                matched[keyword] = {
                    "tag_id": best_tag,
                    "similarity": best_score
                }
            else:
                unmatched.append(keyword)
        
        return matched, unmatched
    
    def llm_judge_tag_candidate(
        self,
        keyword: str,
        news_context: str
    ) -> Dict:
        """
        단계 4: LLM으로 신규 태그 후보 적합성 판단
        """
        prompt = f"""
당신은 공급망 리스크 분석을 위한 태그 적합성 판단 전문가입니다.

키워드: "{keyword}"
뉴스 맥락: {news_context[:300]}

기존 태그 유형:
- SUBSTANCE: 소재 (예: 네온, 희토류, 아르곤)
- MATERIAL: 자재 (예: MLCC, 포토레지스트)
- SUPPLIER: 협력사 (예: ASML, JSR)
- SITE: 위치 (예: 중국, 대만, 일본)
- EVENT: 이벤트 (예: 수출규제, 지진, 파업)

질문:
1. 이 키워드는 공급망 리스크 분석에 유용한 태그가 될 수 있는가?
2. 유용하다면 어느 태그 유형인가?

출력 형식 (JSON):
{{
  "is_valid_tag": true/false,
  "tag_type": "SUBSTANCE|MATERIAL|SUPPLIER|SITE|EVENT" or null,
  "reason": "...",
  "proposed_tag_id": "..." (옵션)
}}
"""
        
        return self.llm_client.generate_json(prompt)
    
    def _cosine_similarity(self, vec1, vec2):
        """코사인 유사도 계산"""
        import numpy as np
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# 사용 예시
pipeline = NewsToTagPipeline(
    tags_db=tags_db,
    opensearch_client=opensearch_client,
    embedding_model=SentenceTransformer('distiluse-base-multilingual-cased-v1'),
    ner_model=ner_model,
    llm_client=llm_client
)

news = "중국 정부가 희토류 수출 통제를 강화하면서 국내 반도체 업체들이 타격을 받고 있다."

result = pipeline.process_news(news)

# 출력:
# {
#   "matched_tags": ["REE", "CHINA"],
#   "auto_added_keywords": [],
#   "pending_review": [
#     {
#       "keyword": "수출통제",
#       "llm_suggestion": {"is_valid_tag": true, "tag_type": "EVENT", ...}
#     }
#   ],
#   "discarded": []
# }
    llm_response = llm_client.match_entities_to_tags(
        news_text=news_text,
        entities=unmatched_entities,
        tags_db=tags_db
    )
    
    for mapping in llm_response["mappings"]:
        if mapping["confidence"] >= 0.85:  # 자동 처리 임계값
            results["matched_tags"].append(mapping["tag_id"])
            results["new_keywords"].append({
                "tag_id": mapping["tag_id"],
                "keyword": mapping["entity"]
            })
        else:
            # 매핑 실패 → Human-in-the-loop
            results["unmapped_entities"].append(mapping["entity"])
    
    return results
```

---

## 4. 신규 표현 처리 정책

### 4.1 원칙

**자동 처리 우선, 매핑 실패 시에만 사람 개입**

```
┌─────────────────────────────────────┐
│  3단계 LLM 동의어 판별              │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      │  confidence ≥ 0.85?  │
      └────────┬────────┘
          Yes  │  No
      ┌────────┴────────┐
      │                 │
   [자동 처리]      [Human-in-the-loop]
   - 기존 태그에      - 검토자 확인
     동의어 추가      - 신규 태그 생성 여부 판단
```

### 4.2 자동 처리 기준

**조건**:
- LLM confidence ≥ 0.85
- 또는 임베딩 유사도 ≥ 0.85 (LLM 대신 벡터 유사도 사용 가능)

**동작**:
1. 신규 키워드를 해당 태그의 `keywords` 배열에 추가
2. 태그 DB 업데이트
3. 로그 기록 (추후 검토용)

**예시**:
```json
// 변경 전
{
  "tag_id": "AR",
  "keywords": ["아르곤", "Argon", "아르곤가스"]
}

// "고순도 아르곤" 자동 추가 (confidence 0.92)
{
  "tag_id": "AR",
  "keywords": ["아르곤", "Argon", "아르곤가스", "고순도 아르곤"]
}
```

### 4.3 Human-in-the-loop 기준

**조건**:
- 모든 기존 태그와 confidence < 0.85
- 또는 LLM이 "신규 태그 필요" 제안

**동작**:
1. 검토 대기열에 추가
2. 검토자에게 알림
3. 검토자 판단:
   - **기존 태그에 추가**: 수동으로 특정 태그에 매핑
   - **신규 태그 생성**: 새로운 tag_id 생성 (예: `HFPO` - High Frequency Polymer Oxide)
   - **무시**: 태그 시스템에 포함 불필요 (예: 일반 명사)

**예시**:
```json
// Human-in-the-loop 대기열
{
  "entity": "HFPO",
  "news_context": "HFPO 공급 중단으로...",
  "llm_suggestion": {
    "action": "create_new_tag",
    "reason": "기존 태그 중 유사한 것 없음. 새로운 화합물로 판단",
    "proposed_tag_type": "SUBSTANCE"
  },
  "top_similar_tags": [
    {"tag_id": "HF", "similarity": 0.65},
    {"tag_id": "POLYMER", "similarity": 0.58}
  ]
}

// 검토자 판단 → "신규 태그 생성" 승인
{
  "tag_id": "HFPO",
  "tag_type": "SUBSTANCE",
  "keywords": ["HFPO", "High Frequency Polymer Oxide"],
  "target_table_column": "SUBSTANCE_MASTER.name_eng"
}
```

### 4.4 배치 검토 프로세스

**주기적 검토** (예: 주 1회):
1. 자동 추가된 키워드 리스트 확인
2. 오분류 발견 시 수정 (예: "JSR社" → JSR 태그 매핑이 맞는지 확인)
3. 고빈도 unmapped_entities 분석 → 신규 태그 필요 여부 판단

---

## 5. 태그 조합 패턴 분석

### 5.1 목적

뉴스 하나에서 여러 태그가 추출되면, 태그 간 조합을 분석하여:
- **고위험 패턴 감지** (예: 희소물질 + 단일 국가 + 수출규제)
- **검색 전략 우선순위 결정** (어떤 태그 조합을 먼저 DB에서 조회할지)

### 5.2 태그 조합의 의미

**예시 1: 단일 엔티티 추적**
```
뉴스: "ASML의 EUV 장비 공급 지연"
추출 태그: [ASML (SUPPLIER)]
→ 검색 전략: SUPPLIER 단독 조회
```

**예시 2: 소재 → 협력사 역추적**
```
뉴스: "우크라이나 전쟁으로 네온 가스 공급 중단"
추출 태그: [NEON (SUBSTANCE), UKRAINE (SITE), WAR (EVENT)]
→ 검색 전략: 
   1. NEON(SUBSTANCE) → MATERIAL_SUBSTANCE_MAP → MATERIAL
   2. SITE(UKRAINE) 필터
   3. MATERIAL → SITE → SUPPLIER 역추적
```

**예시 3: 복합 리스크 (고위험)**
```
뉴스: "중국 정부, 희토류 수출 통제 강화"
추출 태그: [REE (SUBSTANCE), CHINA (SITE), EXPORT_CTRL (EVENT)]
→ 검색 전략:
   1. REE(SUBSTANCE) 포함 MATERIAL 추출
   2. SITE(CHINA) 필터
   3. EXPORT_CTRL(EVENT) 메타데이터의 search_strategy 참조
   4. 영향받는 SUPPLIER 추출
→ 우선순위: HIGH (희소물질 + 단일 국가 + 규제)
```

### 5.3 검색 전략 수립 로직

```python
def determine_search_strategy(tags, tags_db):
    """
    추출된 태그 조합에서 검색 전략 수립
    
    Returns:
        {
            "priority": "HIGH" | "MEDIUM" | "LOW",
            "query_plan": [...],
            "risk_factors": [...]
        }
    """
    strategy = {
        "priority": "MEDIUM",
        "query_plan": [],
        "risk_factors": []
    }
    
    # 태그 유형별 분류
    substances = [t for t in tags if tags_db[t]["tag_type"] == "SUBSTANCE"]
    materials = [t for t in tags if tags_db[t]["tag_type"] == "MATERIAL"]
    suppliers = [t for t in tags if tags_db[t]["tag_type"] == "SUPPLIER"]
    sites = [t for t in tags if tags_db[t]["tag_type"] == "SITE"]
    events = [t for t in tags if tags_db[t]["tag_type"] == "EVENT"]
    
    # 패턴 1: 고위험 - 희소물질 + 단일 국가 + 규제/재해 EVENT
    if substances and sites and events:
        substance_info = tags_db[substances[0]]
        if substance_info.get("is_critical"):  # 희소물질 여부
            strategy["priority"] = "HIGH"
            strategy["risk_factors"].append("희소물질 + 지역 집중 + 이벤트 발생")
    
    # 패턴 2: 독과점 협력사 + 경영 위기 EVENT
    if suppliers and events:
        supplier_info = tags_db[suppliers[0]]
        if supplier_info.get("is_monopoly"):  # 독과점 여부
            strategy["priority"] = "HIGH"
            strategy["risk_factors"].append("독과점 협력사 경영 위기")
    
    # 쿼리 계획 수립
    if substances:
        # SUBSTANCE → MATERIAL → SITE → SUPPLIER 확장
        strategy["query_plan"].append({
            "step": 1,
            "action": "JOIN",
            "tables": ["SUBSTANCE_MASTER", "MATERIAL_SUBSTANCE_MAP", "MATERIAL_MASTER"],
            "condition": f"SUBSTANCE_MASTER.name_kor = '{substance_info['keywords'][0]}'"
        })
    
    if sites:
        # SITE 필터 추가
        strategy["query_plan"].append({
            "step": 2,
            "action": "FILTER",
            "condition": f"SITE_MASTER.country = '{tags_db[sites[0]]['keywords'][0]}'"
        })
    
    if events:
        # EVENT 메타데이터의 search_strategy 참조
        event_info = tags_db[events[0]]
        strategy["query_plan"].append({
            "step": 3,
            "action": "APPLY_STRATEGY",
            "strategy": event_info["search_strategy"]
        })
    
    return strategy
```

---

## 6. 고위험 패턴 감지

### 6.1 사전 정의 패턴

```python
HIGH_RISK_PATTERNS = [
    {
        "id": "CRITICAL_SUBSTANCE_CONCENTRATED",
        "pattern": {
            "required_types": ["SUBSTANCE", "SITE"],
            "required_tags": ["EVENT"],
            "conditions": [
                "SUBSTANCE.is_critical == True",  # 희소물질
                "len(SITE) <= 2"  # 2개국 이하 집중
            ]
        },
        "example": ["REE", "CHINA", "EXPORT_CTRL"],
        "action": "즉각 SUPPLIER 영향 분석 + 대체 공급망 점검",
        "risk_score": 9.5
    },
    {
        "id": "MONOPOLY_SUPPLIER_CRISIS",
        "pattern": {
            "required_types": ["SUPPLIER", "EVENT"],
            "conditions": [
                "SUPPLIER.is_monopoly == True",
                "EVENT.category in ['경영위기', '생산중단', '파산']"
            ]
        },
        "example": ["ASML", "BANKRUPTCY"],
        "action": "긴급 대체 공급처 확보 + 재고 확인",
        "risk_score": 9.0
    },
    {
        "id": "GEOPOLITICAL_SUPPLY_DISRUPTION",
        "pattern": {
            "required_types": ["SITE", "EVENT"],
            "required_count": {"SITE": ">=1", "MATERIAL": ">=1"},
            "conditions": [
                "EVENT.category in ['전쟁', '제재', '무역분쟁']"
            ]
        },
        "example": ["UKRAINE", "NEON", "WAR"],
        "action": "지역별 재고 확인 + 우회 공급망 검토",
        "risk_score": 8.5
    },
    {
        "id": "NATURAL_DISASTER_SITE",
        "pattern": {
            "required_types": ["SITE", "EVENT"],
            "conditions": [
                "EVENT.category in ['지진', '홍수', '태풍']"
            ]
        },
        "example": ["TAIWAN", "EARTHQUAKE"],
        "action": "해당 지역 SITE → MATERIAL → SUPPLIER 역추적",
        "risk_score": 7.5
    }
]
```

### 6.2 패턴 매칭 알고리즘

```python
def detect_high_risk_patterns(tags, tags_db, patterns=HIGH_RISK_PATTERNS):
    """
    추출된 태그가 고위험 패턴에 해당하는지 검사
    
    Returns:
        [
            {
                "pattern_id": "CRITICAL_SUBSTANCE_CONCENTRATED",
                "matched_tags": ["REE", "CHINA", "EXPORT_CTRL"],
                "risk_score": 9.5,
                "action": "..."
            }
        ]
    """
    matched_patterns = []
    
    for pattern in patterns:
        # 필수 태그 유형 확인
        tag_types = {tags_db[t]["tag_type"] for t in tags}
        required_types = set(pattern["pattern"]["required_types"])
        
        if not required_types.issubset(tag_types):
            continue  # 필수 유형 미충족
        
        # 조건 검사
        conditions_met = True
        for condition in pattern["pattern"].get("conditions", []):
            # 조건 평가 (실제 구현 시 안전한 평가 방식 사용)
            if not eval_condition(condition, tags, tags_db):
                conditions_met = False
                break
        
        if conditions_met:
            matched_patterns.append({
                "pattern_id": pattern["id"],
                "matched_tags": tags,
                "risk_score": pattern["risk_score"],
                "action": pattern["action"]
            })
    
    # 리스크 점수 내림차순 정렬
    matched_patterns.sort(key=lambda x: x["risk_score"], reverse=True)
    return matched_patterns
```

### 6.3 우선순위 기반 알림

```python
def process_news_with_priority(news_text, tags_extraction_result, high_risk_patterns):
    """
    뉴스 분석 결과를 우선순위에 따라 처리
    """
    if not high_risk_patterns:
        # 일반 뉴스 - 배치 처리
        queue_for_batch_analysis(news_text, tags_extraction_result)
    
    elif high_risk_patterns[0]["risk_score"] >= 9.0:
        # 긴급 - 즉각 알림
        send_urgent_alert(
            title=f"긴급 공급망 리스크 감지: {high_risk_patterns[0]['pattern_id']}",
            news=news_text,
            tags=high_risk_patterns[0]["matched_tags"],
            action=high_risk_patterns[0]["action"]
        )
        # DB 조회 즉시 실행
        execute_supply_chain_analysis(tags_extraction_result)
    
    elif high_risk_patterns[0]["risk_score"] >= 7.0:
        # 주의 - 우선 처리 대기열
        queue_for_priority_analysis(news_text, tags_extraction_result, high_risk_patterns)
    
    else:
        # 일반 - 일괄 처리
        queue_for_batch_analysis(news_text, tags_extraction_result)
```

---

## 7. Text-to-SQL 생성 (LLM 활용)

### 7.1 입력: 태그 + 메타데이터

```python
def generate_sql_from_tags(tags, tags_db, news_context):
    """
    LLM에게 (태그, 태그 메타데이터, 뉴스 맥락)을 제공하고 SQL 쿼리 생성
    """
    # 태그 메타데이터 수집
    tag_metadata = []
    for tag_id in tags:
        tag_info = tags_db[tag_id]
        tag_metadata.append({
            "tag_id": tag_id,
            "tag_type": tag_info["tag_type"],
            "target_table_column": tag_info.get("target_table_column"),
            "search_strategy": tag_info.get("search_strategy"),
            "join_with_tag_types": tag_info.get("join_with_tag_types", [])
        })
    
    # LLM 프롬프트
    llm_prompt = f"""
당신은 공급망 DB 검색을 위한 SQL 생성 전문가입니다.

뉴스: {news_context}
추출된 태그: {json.dumps(tag_metadata, ensure_ascii=False, indent=2)}

DB 스키마:
- SUBSTANCE_MASTER (substance_code, name_kor, name_eng)
- MATERIAL_MASTER (material_code, name_kor, name_eng, material_type)
- SUPPLIER_MASTER (supplier_code, name_kor, name_eng)
- SITE_MASTER (site_code, country, region, supplier_code)
- MATERIAL_SUBSTANCE_MAP (material_code, substance_code)
- SITE_MATERIAL_MAP (site_code, material_code)
- SUPPLIER_MATERIAL_MAP (supplier_code, material_code)

태그 유형별 검색 전략:
- SUBSTANCE: SUBSTANCE_MASTER → MATERIAL_SUBSTANCE_MAP → MATERIAL_MASTER → SITE_MATERIAL_MAP → SITE_MASTER → SUPPLIER_MASTER 경로
- MATERIAL: MATERIAL_MASTER → SITE_MATERIAL_MAP → SITE_MASTER → SUPPLIER_MASTER 경로
- SUPPLIER: SUPPLIER_MASTER 직접 조회
- SITE: SITE_MASTER 직접 조회 → SUPPLIER_MASTER로 확장
- EVENT: 메타데이터의 search_strategy 참조, 다른 태그와 결합

요구사항:
1. 추출된 태그를 기반으로 공급망 영향 분석 SQL을 생성하세요.
2. EVENT 태그가 있으면 해당 태그의 search_strategy를 반영하세요.
3. 최종 SELECT는 협력사(SUPPLIER), 자재(MATERIAL), 위치(SITE), 소재(SUBSTANCE) 정보를 포함해야 합니다.

출력 형식:
{{
  "sql": "SELECT ... FROM ... WHERE ...",
  "explanation": "이 쿼리는 ... 를 추적합니다."
}}
"""
    
    llm_response = llm_client.generate(llm_prompt)
    return llm_response
```

### 7.2 출력 예시

**입력**:
- 뉴스: "중국 정부, 희토류 수출 통제 강화"
- 태그: `[REE (SUBSTANCE), CHINA (SITE), EXPORT_CTRL (EVENT)]`

**LLM 출력**:
```json
{
  "sql": "
    SELECT 
      sup.name_kor AS 협력사명,
      m.name_kor AS 자재명,
      s.country AS 생산국가,
      s.region AS 생산지역,
      sub.name_kor AS 소재명
    FROM SUBSTANCE_MASTER sub
    JOIN MATERIAL_SUBSTANCE_MAP msm ON sub.substance_code = msm.substance_code
    JOIN MATERIAL_MASTER m ON msm.material_code = m.material_code
    JOIN SITE_MATERIAL_MAP smm ON m.material_code = smm.material_code
    JOIN SITE_MASTER s ON smm.site_code = s.site_code
    JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
    WHERE sub.name_kor LIKE '%희토류%'
      AND s.country = 'China';
  ",
  "explanation": "이 쿼리는 희토류(REE) 소재를 포함하는 자재를 생산하는 중국 내 생산 거점과 해당 협력사를 추적합니다. EXPORT_CTRL 이벤트는 중국(SITE) + 희토류(SUBSTANCE) 결합 조건으로 반영되었습니다."
}
```

---

## 8. 구현 예시 (전체 파이프라인)

```python
from typing import List, Dict
import json

class NewsTaggingPipeline:
    """
    뉴스 → 태그 추출 → 고위험 감지 → SQL 생성 통합 파이프라인
    """
    
    def __init__(self, tags_db, ner_model, llm_client):
        self.tags_db = tags_db
        self.ner_model = ner_model
        self.llm_client = llm_client
        self.high_risk_patterns = HIGH_RISK_PATTERNS
    
    def process_news(self, news_text: str) -> Dict:
        """
        뉴스 하나를 처리하는 전체 파이프라인
        
        Returns:
            {
                "news": "...",
                "tags": ["REE", "CHINA", "EXPORT_CTRL"],
                "new_keywords": [...],
                "risk_patterns": [...],
                "priority": "HIGH",
                "sql_query": "...",
                "unmapped_entities": [...]
            }
        """
        result = {"news": news_text}
        
        # [1] 하이브리드 태그 추출
        tag_extraction = self.extract_tags(news_text)
        result["tags"] = tag_extraction["matched_tags"]
        result["new_keywords"] = tag_extraction["new_keywords"]
        result["unmapped_entities"] = tag_extraction["unmapped_entities"]
        
        # [2] 신규 키워드 자동 추가
        self.auto_add_keywords(tag_extraction["new_keywords"])
        
        # [3] 고위험 패턴 감지
        risk_patterns = detect_high_risk_patterns(
            result["tags"], 
            self.tags_db, 
            self.high_risk_patterns
        )
        result["risk_patterns"] = risk_patterns
        result["priority"] = "HIGH" if risk_patterns and risk_patterns[0]["risk_score"] >= 9.0 else "MEDIUM"
        
        # [4] Text-to-SQL 생성
        if result["tags"]:
            sql_result = self.generate_sql(result["tags"], news_text)
            result["sql_query"] = sql_result["sql"]
            result["explanation"] = sql_result["explanation"]
        
        # [5] Human-in-the-loop 필요 시 대기열 추가
        if result["unmapped_entities"]:
            self.queue_for_review(result["unmapped_entities"], news_text)
        
        return result
    
    def extract_tags(self, news_text: str) -> Dict:
        """3.2절의 하이브리드 방식 구현"""
        return extract_tags_from_news(
            news_text, 
            self.tags_db, 
            self.ner_model, 
            self.llm_client
        )
    
    def auto_add_keywords(self, new_keywords: List[Dict]):
        """4.2절의 자동 처리 구현"""
        for item in new_keywords:
            tag_id = item["tag_id"]
            keyword = item["keyword"]
            
            if keyword not in self.tags_db[tag_id]["keywords"]:
                self.tags_db[tag_id]["keywords"].append(keyword)
                
                # 로그 기록
                self.log_keyword_addition(tag_id, keyword)
    
    def generate_sql(self, tags: List[str], news_context: str) -> Dict:
        """7.1절의 Text-to-SQL 생성 구현"""
        return generate_sql_from_tags(tags, self.tags_db, news_context)
    
    def queue_for_review(self, unmapped_entities: List[str], news_context: str):
        """4.3절의 Human-in-the-loop 대기열 구현"""
        # 검토 대기열 DB에 저장
        for entity in unmapped_entities:
            review_queue.add({
                "entity": entity,
                "news_context": news_context,
                "timestamp": datetime.now()
            })
    
    def log_keyword_addition(self, tag_id: str, keyword: str):
        """자동 추가된 키워드 로그"""
        audit_log.append({
            "action": "auto_add_keyword",
            "tag_id": tag_id,
            "keyword": keyword,
            "timestamp": datetime.now()
        })


# 사용 예시
pipeline = NewsTaggingPipeline(tags_db, ner_model, llm_client)

news = "중국 정부가 희토류 수출 통제를 강화하면서 국내 반도체 업체들의 우려가 커지고 있다."

result = pipeline.process_news(news)

print(json.dumps(result, ensure_ascii=False, indent=2))
# 출력:
# {
#   "news": "중국 정부가 희토류 수출 통제를...",
#   "tags": ["REE", "CHINA", "EXPORT_CTRL"],
#   "new_keywords": [],
#   "risk_patterns": [
#     {
#       "pattern_id": "CRITICAL_SUBSTANCE_CONCENTRATED",
#       "risk_score": 9.5,
#       "action": "즉각 SUPPLIER 영향 분석 + 대체 공급망 점검"
#     }
#   ],
#   "priority": "HIGH",
#   "sql_query": "SELECT sup.name_kor, m.name_kor, s.country FROM ...",
#   "explanation": "이 쿼리는 희토류 소재를 포함하는...",
#   "unmapped_entities": []
# }
```

---

## 9. 성능 최적화 고려사항

### 9.1 OpenSearch 역인덱스 활용 ⭐ 핵심

**정확 매칭은 이미 최적화 완료** (3.2절의 OpenSearch 방식 채택)

**장점 요약**:
- ✅ **확장성**: 태그 수 증가해도 성능 일정 (O(log n))
- ✅ **유연성**: 향후 fuzzy matching, n-gram 확장 가능
- ✅ **운영 효율**: 태그 DB 업데이트 시 재색인만
- ✅ **분산 처리**: 대량 뉴스 처리 시 클러스터 활용
- ✅ **인프라 통합**: 공급망 DB 검색 엔진 재사용

**Aho-Corasick 대비 우위**:
```
┌─────────────────┬──────────────────┬─────────────────┐
│                 │ Aho-Corasick     │ OpenSearch      │
├─────────────────┼──────────────────┼─────────────────┤
│ 확장성          │ 메모리 증가      │ 인덱스 분산     │
│ 태그 업데이트   │ 코드 재배포      │ 재색인만        │
│ fuzzy matching  │ 불가             │ 가능            │
│ 분산 처리       │ 불가             │ 가능            │
│ 운영 복잡도     │ 낮음             │ 중간            │
└─────────────────┴──────────────────┴─────────────────┘
```

**추가 최적화 옵션** (필요 시):
```json
// OpenSearch 인덱스 설정 - fuzzy matching 추가
{
  "mappings": {
    "properties": {
      "keyword": {
        "type": "text",
        "analyzer": "standard",
        "fields": {
          "exact": {"type": "keyword"},        // 정확 매칭용
          "fuzzy": {"type": "text", "fuzziness": "AUTO"}  // 오타 허용
        }
      }
    }
  }
}

// 검색 쿼리 - 정확 매칭 + fuzzy fallback
{
  "query": {
    "bool": {
      "should": [
        {"term": {"keyword.exact": "희토류"}},      // 1순위: 정확 매칭
        {"match": {"keyword.fuzzy": {"query": "희토류", "fuzziness": 1}}}  // 2순위: 오타 1자 허용
      ]
    }
  }
}
```

---

### 9.2 LLM 호출 최소화

**전략**:

#### 1. 배치 처리
```python
# 나쁜 예: 키워드마다 LLM 호출
for keyword in unmatched_keywords:
    llm_judge_tag_candidate(keyword, news_text)  # N번 호출

# 좋은 예: 배치 처리
llm_judge_tag_candidates_batch(unmatched_keywords, news_text)  # 1번 호출
```

**배치 프롬프트 예시**:
```python
prompt = f"""
다음 키워드들이 공급망 리스크 태그로 적합한지 판단하세요:

뉴스: {news_text}

키워드 리스트:
1. "수출규제"
2. "고순도 아르곤"
3. "일반 명사"

각 키워드에 대해 출력:
[
  {{"keyword": "수출규제", "is_valid_tag": true, "tag_type": "EVENT", ...}},
  {{"keyword": "고순도 아르곤", "is_valid_tag": true, "tag_type": "SUBSTANCE", ...}},
  {{"keyword": "일반 명사", "is_valid_tag": false, ...}}
]
"""
```

#### 2. 캐싱
```python
# Redis 캐시 활용
import redis

cache = redis.Redis()

def llm_judge_with_cache(keyword, news_context):
    # 캐시 확인
    cache_key = f"tag_verdict:{keyword}"
    cached = cache.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # 캐시 미스 → LLM 호출
    verdict = llm_client.judge_tag_candidate(keyword, news_context)
    
    # 캐시 저장 (TTL 7일)
    cache.setex(cache_key, 604800, json.dumps(verdict))
    
    return verdict
```

#### 3. 단계별 필터링으로 LLM 호출 최소화

```
뉴스 → 키워드 추출 (LLM) → 100개 키워드
  ↓
OpenSearch 정확 매칭 → 70개 매칭 성공, 30개 실패
  ↓
임베딩 유사도 → 20개 매칭 성공 (유사도 ≥ 0.85), 10개 실패
  ↓
LLM 태그 후보 판별 → 10개만 LLM 호출 (원래 100개 대비 90% 감소)
```

---

### 9.3 임베딩 유사도 최적화

**현재 방식** (3.2절):
```python
# 매 키워드마다 모든 태그와 유사도 계산
for keyword in keywords:
    for tag_id, tag_data in tags_db.items():
        similarity = cosine_similarity(...)  # O(n * m), n=키워드 수, m=태그 수
```

**최적화 방식**: **FAISS 벡터 검색**

```python
import faiss
import numpy as np

# 사전 준비: 태그 임베딩을 FAISS 인덱스에 추가 (1회만)
def build_faiss_index(tags_db, embedding_model):
    tag_ids = list(tags_db.keys())
    embeddings = np.array([
        tags_db[tag_id]["embedding"] 
        for tag_id in tag_ids
    ]).astype('float32')
    
    # FAISS 인덱스 생성 (코사인 유사도용)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner Product (코사인 유사도)
    
    # 정규화 (코사인 유사도 = 정규화된 벡터의 내적)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    
    return index, tag_ids

# 실시간 검색: O(log n) 복잡도
def fast_similarity_search(keyword, embedding_model, faiss_index, tag_ids, k=1, threshold=0.85):
    # 키워드 임베딩
    keyword_emb = embedding_model.encode([keyword]).astype('float32')
    faiss.normalize_L2(keyword_emb)
    
    # FAISS 검색 (top-k 유사 태그)
    similarities, indices = faiss_index.search(keyword_emb, k)
    
    best_similarity = similarities[0][0]
    best_tag_id = tag_ids[indices[0][0]]
    
    if best_similarity >= threshold:
        return best_tag_id, best_similarity
    else:
        return None, best_similarity

# 사용 예시
faiss_index, tag_ids = build_faiss_index(tags_db, embedding_model)

# 100개 태그 중 유사도 계산 → FAISS는 밀리초 단위
result = fast_similarity_search("고순도 아르곤", embedding_model, faiss_index, tag_ids)
# ("AR", 0.89)
```

**성능 비교**:
```
┌─────────────────┬────────────────┬────────────────┐
│                 │ Naive 방식     │ FAISS 방식     │
├─────────────────┼────────────────┼────────────────┤
│ 복잡도          │ O(n * m)       │ O(log n)       │
│ 100개 태그 검색 │ ~50ms          │ ~2ms           │
│ 1000개 태그     │ ~500ms         │ ~3ms           │
└─────────────────┴────────────────┴────────────────┘
```

---

### 9.4 전체 파이프라인 병렬 처리

**대량 뉴스 배치 처리** (예: 1시간마다 100건 뉴스):

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def process_news_batch(news_list, pipeline):
    """
    뉴스 배치를 병렬 처리
    """
    with ThreadPoolExecutor(max_workers=10) as executor:
        loop = asyncio.get_event_loop()
        
        # 모든 뉴스를 병렬로 처리
        tasks = [
            loop.run_in_executor(executor, pipeline.process_news, news)
            for news in news_list
        ]
        
        results = await asyncio.gather(*tasks)
    
    return results

# 사용 예시
news_batch = load_recent_news()  # 100건
results = asyncio.run(process_news_batch(news_batch, pipeline))

# 100건 처리 시간:
# - 순차 처리: ~200초 (뉴스당 2초)
# - 병렬 처리 (10 workers): ~20초 (10배 빠름)
```

---

### 9.5 최적화 우선순위

```
[이미 완료] OpenSearch 역인덱스 (3.2절) ← 가장 큰 성능 향상
  ↓
[필수] 임베딩 FAISS 인덱스 (9.3절) ← 100개 이상 태그 시 필수
  ↓
[필수] LLM 배치 처리 (9.2절) ← 비용 절감
  ↓
[선택] LLM 캐싱 (9.2절) ← 반복 뉴스 많을 때 유용
  ↓
[선택] 배치 병렬 처리 (9.4절) ← 실시간 아닌 배치 처리 시
```

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-06-25 | 초기 버전 작성<br>- 하이브리드 매핑 방식 (Option A) 정의<br>- 신규 표현 자동 처리 정책<br>- 고위험 패턴 감지 메커니즘<br>- Text-to-SQL 생성 가이드 |
| 1.1 | 2026-06-25 | **파이프라인 구조 개편 및 OpenSearch 도입**<br>- 전체 파이프라인을 5단계로 재구성:<br>  ① 키워드 추출 (LLM + NER)<br>  ② 정확 매칭 (OpenSearch 역인덱스)<br>  ③ 유사도 기반 매칭 (임베딩)<br>  ④ LLM 태그 후보 판별<br>  ⑤ Human-in-the-loop<br>- 3.1절: 단계별 프로세스 개요 추가<br>- 3.2절: OpenSearch 역인덱스 방식 도입 (Aho-Corasick 대체)<br>  · 확장성, 유연성, 운영 효율성 우수<br>  · fuzzy matching 확장 가능<br>  · 분산 처리 및 인프라 통합<br>- 3.3절: 통합 알고리즘 클래스 구현 (`NewsToTagPipeline`)<br>- 3.4절: 신규 표현 처리 정책 명확화<br>  · 유사도 ≥ 0.85: 자동 태그 매핑<br>  · LLM 판별 → 태그 부적절: 폐기<br>  · LLM 판별 → 태그 적절: Human-in-the-loop<br>- 9절: 성능 최적화 재작성<br>  · OpenSearch가 이미 최적 솔루션임을 명시<br>  · FAISS 벡터 검색 추가 (임베딩 유사도 최적화)<br>  · LLM 배치 처리 및 캐싱 전략<br>  · 병렬 처리 방안 |

---

*본 문서는 [DB_TAG_Tag Creation Methodology.md](./DB_TAG_Tag%20Creation%20Methodology.md)에서 정의한 태그 구조를 활용하는 운영 파이프라인입니다.*
