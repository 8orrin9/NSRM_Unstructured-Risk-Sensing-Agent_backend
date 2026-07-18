# OpenSearch 정확 매칭 구현 가이드

## 현재 태그 정보 평가

### ✅ OpenSearch 적합성

현재 태그 데이터는 **OpenSearch 정확 매칭에 최적화**되어 있습니다:

1. **구조화된 키워드**: `keywords_full` 필드에 `|` 구분자로 명확히 분리
2. **다국어 분리**: `target_region` (KR/GLOBAL)로 한국어/영어 키워드 분리됨
3. **메타데이터 완비**: tag_id, tag_type, domain, risk_factor 등 검색/필터링에 필요한 모든 정보 포함
4. **키워드 품질**: 평균 20~30개/태그, 동의어·약어·변형 포함

---

## OpenSearch 인덱스 설계

### 1. 인덱스 스키마

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "korean_analyzer": {
          "type": "custom",
          "tokenizer": "nori_tokenizer",
          "filter": ["lowercase", "nori_readingform"]
        },
        "english_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "stop", "snowball"]
        },
        "keyword_exact": {
          "type": "custom",
          "tokenizer": "keyword",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "tag_id": {
        "type": "keyword"
      },
      "target_region": {
        "type": "keyword"
      },
      "tag_type": {
        "type": "keyword"
      },
      "name": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "domain": {
        "type": "keyword"
      },
      "risk_factor": {
        "type": "text",
        "analyzer": "korean_analyzer"
      },
      "keywords": {
        "type": "text",
        "analyzer": "keyword_exact",
        "fields": {
          "analyzed": {
            "type": "text",
            "analyzer": "korean_analyzer"
          }
        }
      },
      "description": {
        "type": "text",
        "analyzer": "korean_analyzer"
      },
      "target_table_column": {
        "type": "keyword"
      },
      "db_matched_count": {
        "type": "integer"
      }
    }
  }
}
```

### 2. 핵심 설계 포인트

#### A. `keywords` 필드 이중 분석기

```json
"keywords": {
  "type": "text",
  "analyzer": "keyword_exact",    // 정확 매칭용 (토크나이징 없음)
  "fields": {
    "analyzed": {
      "type": "text",
      "analyzer": "korean_analyzer"  // 유사 매칭용 (형태소 분석)
    }
  }
}
```

**정확 매칭**: `keywords` 필드 사용 (소문자 변환만 수행)
**유사 매칭**: `keywords.analyzed` 필드 사용 (형태소 분석)

#### B. 다국어 처리

- **KR 태그**: `korean_analyzer` (Nori 형태소 분석기)
- **GLOBAL 태그**: `english_analyzer` (Snowball stemmer)

하지만 **정확 매칭에서는 analyzer가 중요하지 않음** (keyword_exact 사용)

---

## 정확 매칭 쿼리

### 방법 1: Term Query (가장 정확)

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "term": {
            "target_region": "KR"
          }
        },
        {
          "terms": {
            "keywords": ["네온가스", "네온 부족", "우크라이나 네온"]
          }
        }
      ]
    }
  }
}
```

**장점**:
- 가장 빠름 (inverted index 직접 조회)
- 100% 정확 (토크나이징 없음)
- False positive 없음

**단점**:
- 대소문자 구분 (해결: analyzer에서 lowercase 필터 적용)
- 공백/구두점 민감 (해결: 사전에 정규화)

### 방법 2: Match Query with AND operator (준정확)

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "term": {
            "target_region": "KR"
          }
        },
        {
          "match": {
            "keywords": {
              "query": "네온가스 공급 부족",
              "operator": "and"
            }
          }
        }
      ]
    }
  }
}
```

**장점**:
- 구문 내 단어 순서 무관
- 형태소 분석 후 매칭 (더 유연)

**단점**:
- 완전 정확 매칭은 아님 (토큰 단위 매칭)

### 방법 3: Multi-Match (여러 필드 동시 검색)

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "term": {
            "target_region": "KR"
          }
        }
      ],
      "should": [
        {
          "terms": {
            "keywords": ["네온가스"],
            "boost": 3.0
          }
        },
        {
          "match": {
            "name": {
              "query": "네온가스",
              "boost": 2.0
            }
          }
        },
        {
          "match": {
            "description": {
              "query": "네온가스",
              "boost": 1.0
            }
          }
        }
      ],
      "minimum_should_match": 1
    }
  }
}
```

**용도**: keywords에서 매칭 실패 시 name/description에서도 검색

---

## Python 클라이언트 구현

### 1. 인덱스 생성 및 데이터 색인

```python
"""
OpenSearch 인덱스 생성 및 태그 색인
"""
from opensearchpy import OpenSearch
import csv
import json

class TagIndexer:
    def __init__(self, host='localhost', port=9200):
        """OpenSearch 클라이언트 초기화"""
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False
        )
        self.index_name = 'supply_chain_tags'
    
    def create_index(self):
        """인덱스 생성"""
        index_body = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "analysis": {
                    "analyzer": {
                        "korean_analyzer": {
                            "type": "custom",
                            "tokenizer": "nori_tokenizer",
                            "filter": ["lowercase", "nori_readingform"]
                        },
                        "keyword_exact": {
                            "type": "custom",
                            "tokenizer": "keyword",
                            "filter": ["lowercase"]
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "tag_id": {"type": "keyword"},
                    "target_region": {"type": "keyword"},
                    "tag_type": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}}
                    },
                    "domain": {"type": "keyword"},
                    "risk_factor": {"type": "text", "analyzer": "korean_analyzer"},
                    "keywords": {
                        "type": "text",
                        "analyzer": "keyword_exact",
                        "fields": {
                            "analyzed": {
                                "type": "text",
                                "analyzer": "korean_analyzer"
                            }
                        }
                    },
                    "description": {"type": "text", "analyzer": "korean_analyzer"},
                    "target_table_column": {"type": "keyword"},
                    "db_matched_count": {"type": "integer"}
                }
            }
        }
        
        # 기존 인덱스 삭제 (있으면)
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            print(f'✓ 기존 인덱스 삭제: {self.index_name}')
        
        # 인덱스 생성
        self.client.indices.create(index=self.index_name, body=index_body)
        print(f'✓ 인덱스 생성: {self.index_name}')
    
    def index_tags(self, csv_file):
        """CSV 파일에서 태그 색인"""
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            indexed_count = 0
            for row in reader:
                # keywords_full을 배열로 변환
                keywords_str = row['keywords_full']
                keywords_list = [kw.strip() for kw in keywords_str.split('|')]
                
                # 문서 생성
                doc = {
                    'tag_id': row['tag_id'],
                    'target_region': row['target_region'],
                    'tag_type': row['tag_type'],
                    'name': row['name'],
                    'domain': row['domain'],
                    'risk_factor': row['risk_factor'],
                    'keywords': keywords_list,
                    'description': row['description'],
                    'target_table_column': row['target_table_column'],
                    'db_matched_count': int(row['db_matched_count']) if row['db_matched_count'] else 0
                }
                
                # 색인
                doc_id = f"{row['tag_id']}_{row['target_region']}"
                self.client.index(
                    index=self.index_name,
                    id=doc_id,
                    body=doc,
                    refresh=True
                )
                
                indexed_count += 1
                if indexed_count % 50 == 0:
                    print(f'  색인 진행: {indexed_count}개...')
        
        print(f'✓ 색인 완료: {indexed_count}개 문서')
        return indexed_count


def main():
    print('=' * 60)
    print('OpenSearch 태그 인덱스 생성')
    print('=' * 60)
    
    # 인덱서 생성
    indexer = TagIndexer(host='localhost', port=9200)
    
    # 인덱스 생성
    print('\n[Step 1] 인덱스 생성...')
    indexer.create_index()
    
    # 태그 색인
    print('\n[Step 2] 태그 색인...')
    count = indexer.index_tags('../data/TAG/DB_TAG_Generated_Tags_v1.0.csv')
    
    print(f'\n완료! {count}개 태그가 OpenSearch에 색인되었습니다.')


if __name__ == '__main__':
    main()
```

### 2. 정확 매칭 검색 엔진

```python
"""
OpenSearch 정확 매칭 검색
"""
from opensearchpy import OpenSearch
import re

class ExactMatcher:
    def __init__(self, host='localhost', port=9200):
        """OpenSearch 클라이언트 초기화"""
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False
        )
        self.index_name = 'supply_chain_tags'
    
    def extract_keywords_from_text(self, text):
        """
        텍스트에서 키워드 추출 (간단한 토크나이징)
        실제로는 더 정교한 NER/키워드 추출 로직 필요
        """
        # 공백/구두점 기준 토큰화
        tokens = re.findall(r'\b[\w가-힣]+\b', text)
        
        # 2-gram, 3-gram도 추가 (구문 매칭용)
        keywords = set(tokens)
        for i in range(len(tokens) - 1):
            keywords.add(tokens[i] + ' ' + tokens[i+1])
        for i in range(len(tokens) - 2):
            keywords.add(tokens[i] + ' ' + tokens[i+1] + ' ' + tokens[i+2])
        
        return list(keywords)
    
    def exact_match(self, text, region='KR', top_k=5):
        """
        정확 매칭 검색
        
        Args:
            text: 뉴스 텍스트
            region: 'KR' 또는 'GLOBAL'
            top_k: 반환할 최대 태그 수
        
        Returns:
            [
                {
                    'tag_id': 'RAW_SPECIAL_GAS',
                    'name': '특수가스',
                    'score': 15.3,
                    'matched_keywords': ['네온가스', '네온 부족'],
                    'tag_type': 'RAW_MATERIAL',
                    'risk_factor': '특수가스 수급 리스크'
                },
                ...
            ]
        """
        # 키워드 추출
        keywords = self.extract_keywords_from_text(text)
        
        if not keywords:
            return []
        
        # OpenSearch 쿼리
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "target_region": region
                            }
                        },
                        {
                            "terms": {
                                "keywords": keywords
                            }
                        }
                    ]
                }
            },
            "size": top_k,
            "_source": ["tag_id", "name", "tag_type", "risk_factor", "keywords", "domain"]
        }
        
        # 검색 실행
        response = self.client.search(
            index=self.index_name,
            body=query
        )
        
        # 결과 파싱
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            
            # 실제 매칭된 키워드 찾기
            matched_kws = [kw for kw in keywords if kw.lower() in [k.lower() for k in source['keywords']]]
            
            results.append({
                'tag_id': source['tag_id'],
                'name': source['name'],
                'score': hit['_score'],
                'matched_keywords': matched_kws,
                'tag_type': source['tag_type'],
                'risk_factor': source['risk_factor'],
                'domain': source['domain']
            })
        
        return results
    
    def exact_match_with_highlight(self, text, region='KR', top_k=5):
        """
        하이라이트 포함 정확 매칭 (매칭된 키워드 강조)
        """
        keywords = self.extract_keywords_from_text(text)
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"target_region": region}},
                        {"terms": {"keywords": keywords}}
                    ]
                }
            },
            "size": top_k,
            "_source": ["tag_id", "name", "tag_type", "risk_factor", "keywords"],
            "highlight": {
                "fields": {
                    "keywords": {
                        "type": "plain",
                        "fragment_size": 150,
                        "number_of_fragments": 3
                    }
                }
            }
        }
        
        response = self.client.search(index=self.index_name, body=query)
        
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            
            # 하이라이트된 키워드
            highlighted = hit.get('highlight', {}).get('keywords', [])
            
            results.append({
                'tag_id': source['tag_id'],
                'name': source['name'],
                'score': hit['_score'],
                'highlighted_keywords': highlighted,
                'tag_type': source['tag_type'],
                'risk_factor': source['risk_factor']
            })
        
        return results


def demo():
    """테스트"""
    print('=' * 60)
    print('OpenSearch 정확 매칭 테스트')
    print('=' * 60)
    
    matcher = ExactMatcher(host='localhost', port=9200)
    
    # 테스트 케이스
    test_cases = [
        {
            'text': '우크라이나 전쟁으로 네온가스 공급이 중단되면서 반도체 업계가 비상이다.',
            'region': 'KR'
        },
        {
            'text': 'ASML의 EUV 장비 납품 지연이 삼성전자 파운드리 사업에 악재로 작용할 전망이다.',
            'region': 'KR'
        },
        {
            'text': 'Neon gas shortage from Ukraine war impacts semiconductor production globally.',
            'region': 'GLOBAL'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f'\n[테스트 {i}] ({case["region"]})')
        print(f'뉴스: {case["text"]}')
        
        results = matcher.exact_match(case['text'], case['region'], top_k=3)
        
        if results:
            print(f'\n매칭된 태그 ({len(results)}개):')
            for j, result in enumerate(results, 1):
                print(f'\n  {j}. [{result["tag_id"]}] {result["name"]}')
                print(f'     - 점수: {result["score"]:.2f}')
                print(f'     - 매칭 키워드: {", ".join(result["matched_keywords"])}')
                print(f'     - 유형: {result["tag_type"]}')
                print(f'     - 리스크: {result["risk_factor"]}')
        else:
            print('  ✗ 매칭 실패')


if __name__ == '__main__':
    demo()
```

---

## 성능 최적화

### 1. 쿼리 캐싱

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(text_hash, region):
    """자주 검색되는 텍스트 캐싱"""
    return matcher.exact_match(text, region)
```

### 2. Bulk 검색

```python
def bulk_match(texts, region='KR'):
    """여러 뉴스 한번에 검색"""
    queries = []
    for text in texts:
        keywords = extract_keywords_from_text(text)
        queries.append({
            "query": {
                "bool": {
                    "must": [
                        {"term": {"target_region": region}},
                        {"terms": {"keywords": keywords}}
                    ]
                }
            }
        })
    
    # Multi-search API
    response = client.msearch(
        body=queries,
        index=index_name
    )
    
    return [parse_response(r) for r in response['responses']]
```

### 3. 인덱스 워밍업

```python
def warmup_index():
    """자주 사용되는 키워드로 인덱스 워밍업"""
    common_keywords = ['네온가스', 'ASML', '희토류', 'EUV']
    
    for kw in common_keywords:
        client.search(
            index=index_name,
            body={"query": {"term": {"keywords": kw}}}
        )
```

---

## 다음 단계: 유사 매칭과 통합

```python
class HybridMatcher:
    def __init__(self):
        self.exact_matcher = ExactMatcher()
        self.similarity_matcher = SimilarityMatcher()  # 임베딩 기반
    
    def match(self, text, region='KR'):
        """하이브리드 매칭"""
        # 1단계: 정확 매칭
        exact_results = self.exact_matcher.exact_match(text, region, top_k=1)
        
        if exact_results and exact_results[0]['score'] > 10.0:
            return {
                'method': 'exact',
                'results': exact_results,
                'confidence': 1.0
            }
        
        # 2단계: 유사 매칭 (OpenSearch vector search 또는 외부 임베딩)
        sim_results = self.similarity_matcher.match(text, region)
        
        return {
            'method': 'similarity',
            'results': sim_results,
            'confidence': 0.7
        }
```

---

## 요약

### ✅ 현재 태그 데이터 평가

| 항목 | 상태 | 비고 |
|------|------|------|
| 키워드 구조 | ✅ 우수 | `\|` 구분자로 명확히 분리 |
| 키워드 품질 | ✅ 우수 | 평균 20~30개, 동의어 포함 |
| 다국어 분리 | ✅ 완벽 | target_region으로 KR/GLOBAL 분리 |
| 메타데이터 | ✅ 완비 | 모든 필수 필드 존재 |
| **OpenSearch 적합성** | ✅ 최적 | 추가 전처리 불필요 |

### 구현 순서

1. **OpenSearch 설치** (Docker 권장)
2. **인덱스 생성** (`create_index_and_bulk_load.py`)
3. **정확 매칭 엔진** (`exact_matcher.py`)
4. **성능 테스트** (뉴스 샘플로 매칭률 측정)
5. **유사 매칭 통합** (정확 매칭 실패 시 백업)

코드를 실제로 작성해드릴까요?
