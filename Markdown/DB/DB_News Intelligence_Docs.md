# 뉴스 인텔리전스 DB 설계 문서

## 1. 개요 및 목적

### 1.1 배경

공급망 리스크 뉴스 분석 시스템을 위한 데이터베이스 구축이 필요합니다. 기존에는:
- **공급망 마스터 DB** (`supply_chain.db`): 협력사, 자재, 소재, 생산지 정보 (880개 엔티티)
- **뉴스 수집 모듈**: 국내(Naver API) 및 글로벌(RSS/스크래핑) 뉴스 수집 코드 완료
- **태그 시스템**: 224개 태그, 2,620개 키워드 생성 완료 (CSV 형식)

하지만 **뉴스 및 태그 데이터를 저장할 데이터베이스가 없는 상태**였습니다.

### 1.2 목적

`news_intelligence.db` 생성을 통해:
1. 수집된 뉴스 원문 저장
2. 태그 시스템 DB 마이그레이션 (CSV → SQLite)
3. 뉴스-태그 매핑 파이프라인 구현 기반 구축
4. 공급망 DB와 분리된 운영 DB 확보

---

## 2. DB 설계 원칙

### 2.1 분리 전략: 공급망 DB와 완전 분리

| 구분 | 공급망 DB (supply_chain.db) | 뉴스 DB (news_intelligence.db) |
|------|----------------------------|--------------------------------|
| **데이터 특성** | 정적 마스터 데이터 | 동적 운영 데이터 |
| **업데이트 빈도** | 월/분기 단위 | 시간/일 단위 |
| **용량 증가** | 안정적 (엔티티 수 기반) | 급격한 증가 (뉴스 누적) |
| **역할** | 읽기 전용 참조 | 빈번한 쓰기 |
| **백업 전략** | 주기적 풀백업 | 증분 백업 + 아카이빙 |

### 2.2 분리 근거

1. **데이터 특성 차이**:
   - 공급망 DB: 협력사, 자재 등 변동이 적은 마스터 데이터
   - 뉴스 DB: 매일 수집되는 대량의 텍스트 데이터

2. **용량 증가 패턴**:
   - 공급망 DB: 880개 엔티티 → 연간 10% 내외 증가
   - 뉴스 DB: 일 100건 × 원문 5KB × 365일 = **180MB/년**

3. **파이프라인 설계**:
   - `DB_TAG_News Mapping Pipeline.md`에서 이미 분리를 전제
   - 태그 정보(뉴스 DB) → SQL 생성 → 공급망 DB 조회

4. **향후 확장성**:
   - OpenSearch 도입 시: 뉴스 DB만 마이그레이션
   - 분석 결과 웨어하우스 확장: 뉴스 DB만 분리

---

## 3. 테이블 구조

### 3.1 ER 다이어그램

```
┌─────────────────┐
│  NEWS_MASTER    │
│  ─────────────  │
│  news_id (PK)   │◄───┐
│  source         │    │
│  title          │    │ 1
│  content        │    │
│  pub_date       │    │
└─────────────────┘    │
                       │
                       │ N
                 ┌─────┴────────────────┐
                 │  NEWS_TAG_MAP        │
                 │  ──────────────────  │
                 │  mapping_id (PK)     │
                 │  news_id (FK)        │
                 │  tag_id (FK)         │
                 │  confidence          │
                 └─────┬────────────────┘
                       │
                       │ N
                       │
                       │ 1
┌─────────────────┐◄───┤
│  TAG_MASTER     │    │
│  ─────────────  │    │
│  tag_id (PK)    │◄───┤
│  target_region  │    │
│  tag_type       │    │
│  name           │    │
│  description    │    │
└─────────────────┘    │
        │              │
        │ 1            │
        │              │
        │ N            │
┌─────┴────────────┐   │
│ TAG_KEYWORD_MAP  │   │
│ ──────────────── │   │
│ mapping_id (PK)  │   │
│ tag_id (FK)      ├───┘
│ keyword          │
│ normalized       │
└──────────────────┘

┌──────────────────────┐
│ NEWS_KEYWORD_        │
│ EXTRACTION           │
│ ──────────────────   │
│ extraction_id (PK)   │
│ news_id (FK)         ├───┐
│ keyword              │   │
│ extraction_method    │   │
└──────────────────────┘   │
                           │ N
                           │
                           │ 1
          ┌────────────────┘
          │
     (NEWS_MASTER)
```

---

### 3.2 테이블 상세

#### 3.2.1 NEWS_MASTER (뉴스 마스터 테이블)

**목적**: 수집된 뉴스 원문 저장

**데이터 소스**:
- `dev/dev_module_news_searcher_domestic.py` (Naver API)
- `dev/dev_module_news_searcher_global.py` (RSS/스크래핑)

**스키마**:
```sql
CREATE TABLE NEWS_MASTER (
    news_id TEXT PRIMARY KEY,              -- 고유 식별자 (hash 기반)
    source TEXT NOT NULL,                  -- 출처 (예: "NAVER_NEWS", "BBC News - World")
    source_type TEXT NOT NULL,             -- "DOMESTIC" | "GLOBAL_RSS" | "GLOBAL_SCRAPE"
    category TEXT,                         -- 카테고리 (글로벌만 보유)
    
    title TEXT NOT NULL,                   -- 제목 (HTML 태그 제거)
    description TEXT,                      -- 요약
    content TEXT,                          -- 본문 (full_content)
    url TEXT NOT NULL UNIQUE,              -- 원문 URL (중복 방지)
    
    pub_date TEXT NOT NULL,                -- 발행 날짜 (ISO 8601 정규화)
    collected_at TEXT NOT NULL,            -- 수집 시간
    
    is_active INTEGER DEFAULT 1,           -- 활성 여부
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_news_source ON NEWS_MASTER(source);
CREATE INDEX idx_news_pub_date ON NEWS_MASTER(pub_date);
CREATE INDEX idx_news_collected_at ON NEWS_MASTER(collected_at);
```

**컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| news_id | TEXT (PK) | 고유 식별자 (hash 기반) | `"news_20260626_abc123"` |
| source | TEXT | 뉴스 출처 | `"NAVER_NEWS"`, `"BBC News - World"` |
| source_type | TEXT | 출처 유형 | `"DOMESTIC"`, `"GLOBAL_RSS"`, `"GLOBAL_SCRAPE"` |
| category | TEXT | 카테고리 (글로벌만) | `"world"`, `"business"`, `"scraped"` |
| title | TEXT | 제목 (HTML 태그 제거) | `"중국 정부, 희토류 수출 통제 강화"` |
| description | TEXT | 요약 (글로벌만) | `"China tightens export controls..."` |
| content | TEXT | 본문 | 크롤링된 전문 |
| url | TEXT (UNIQUE) | 원문 URL | `"https://..."` |
| pub_date | TEXT | 발행 날짜 (ISO 8601) | `"2026-06-26T15:30:00"` |
| collected_at | TEXT | 수집 시간 | `"2026-06-26T16:00:00"` |

**인덱스 전략**:
- `source`: 출처별 조회 최적화
- `pub_date`: 기간별 조회 최적화
- `collected_at`: 수집 이력 추적

---

#### 3.2.2 TAG_MASTER (태그 마스터 테이블)

**목적**: 공급망 리스크 분석을 위한 태그 정의

**데이터 소스**: `data/TAG/DB_TAG_Generated_Tags_v1.0.csv`

**스키마**:
```sql
CREATE TABLE TAG_MASTER (
    tag_id TEXT NOT NULL,                  -- 태그 식별자 (예: "RAW_SPECIAL_GAS")
    target_region TEXT NOT NULL,           -- "KR" | "GLOBAL"
    tag_type TEXT NOT NULL,                -- "RAW_MATERIAL" | "MATERIAL" | "SUPPLIER" | "SITE" | "EVENT"
    
    name TEXT NOT NULL,                    -- 표시명 (언어별)
    description TEXT,                      -- 설명 (임베딩용)
    
    domain TEXT,                           -- 대분류 (8개)
    risk_factor TEXT,                      -- 리스크 요인 (35개)
    
    target_table_column TEXT,              -- DB 매핑 정보
    db_matched_count INTEGER,              -- 매칭된 엔티티 개수
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (tag_id, target_region)
);

CREATE INDEX idx_tag_type ON TAG_MASTER(tag_type);
CREATE INDEX idx_tag_region ON TAG_MASTER(target_region);
```

**컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| tag_id | TEXT (PK) | 태그 식별자 | `"RAW_SPECIAL_GAS"` |
| target_region | TEXT (PK) | 대상 지역 | `"KR"`, `"GLOBAL"` |
| tag_type | TEXT | 태그 유형 | `"RAW_MATERIAL"`, `"MATERIAL"`, `"SUPPLIER"`, `"SITE"`, `"EVENT"` |
| name | TEXT | 표시명 | `"특수가스"` (KR), `"Special Gas"` (GLOBAL) |
| description | TEXT | 설명 (임베딩용) | `"특수가스. 대표 소재: 아르곤, 네온..."` |
| domain | TEXT | 대분류 | `"원자재&희소물질"` |
| risk_factor | TEXT | 리스크 요인 | `"특수가스 수급 리스크"` |
| target_table_column | TEXT | DB 매핑 정보 | `"RAW_MATERIAL_MASTER.raw_material_type = '특수가스'"` |
| db_matched_count | INTEGER | 매칭된 엔티티 개수 | `23` |

**특징**:
- **1개 태그 → 2개 레코드** (target_region = KR/GLOBAL 분리)
- 현재: 224개 태그 × 2 = **448개 레코드**

**태그 유형별 분포**:
| tag_type | 레코드 수 | 설명 |
|----------|-----------|------|
| SUPPLIER | 246 | 협력사 (123개 × 2) |
| EVENT | 120 | 이벤트 (60개 × 2) |
| MATERIAL | 46 | 자재 (23개 × 2) |
| RAW_MATERIAL | 20 | 소재 (10개 × 2) |
| SITE | 16 | 위치 (8개 × 2) |

---

#### 3.2.3 TAG_KEYWORD_MAP (태그-키워드 매핑 테이블)

**목적**: 각 태그에 속하는 키워드 관리

**데이터 소스**: CSV의 `keywords_full` 컬럼 (파이프 구분)

**스키마**:
```sql
CREATE TABLE TAG_KEYWORD_MAP (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id TEXT NOT NULL,
    target_region TEXT NOT NULL,
    keyword TEXT NOT NULL,
    
    normalized TEXT NOT NULL,              -- 정규화 키워드 (소문자, 공백 제거)
    is_primary INTEGER DEFAULT 0,          -- 주요 키워드 여부
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (tag_id, target_region) REFERENCES TAG_MASTER(tag_id, target_region),
    UNIQUE (tag_id, target_region, keyword)
);

CREATE INDEX idx_keyword_normalized ON TAG_KEYWORD_MAP(normalized);
CREATE INDEX idx_keyword_tag ON TAG_KEYWORD_MAP(tag_id, target_region);
```

**컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| mapping_id | INTEGER (PK) | 매핑 ID (자동 증가) | `1`, `2`, `3`... |
| tag_id | TEXT (FK) | 태그 ID | `"RAW_SPECIAL_GAS"` |
| target_region | TEXT (FK) | 대상 지역 | `"KR"` |
| keyword | TEXT | 키워드 원본 | `"희토류"`, `"Rare Earth"` |
| normalized | TEXT | 정규화 키워드 | `"희토류"`, `"rareearth"` |
| is_primary | INTEGER | 주요 키워드 여부 | `1` (첫 번째 키워드), `0` (나머지) |

**현재 통계**:
- 총 레코드: **2,517개**
- 평균 키워드/태그: **~5.6개** (2,517 / 448)

**정규화 규칙**:
```python
def normalize_keyword(keyword: str) -> str:
    """소문자 변환 + 공백 제거"""
    return keyword.lower().replace(" ", "").replace("　", "")  # 전각 공백도 제거
```

---

#### 3.2.4 NEWS_TAG_MAP (뉴스-태그 매핑 테이블)

**목적**: 뉴스에서 추출된 태그 저장

**생성**: 추후 뉴스-태그 매핑 파이프라인 구현 시 사용

**스키마**:
```sql
CREATE TABLE NEWS_TAG_MAP (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    target_region TEXT NOT NULL,
    
    confidence REAL,                       -- 매핑 신뢰도 (0.0-1.0)
    extraction_method TEXT,                -- "EXACT" | "SIMILARITY" | "LLM"
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id),
    FOREIGN KEY (tag_id, target_region) REFERENCES TAG_MASTER(tag_id, target_region),
    UNIQUE (news_id, tag_id, target_region)
);

CREATE INDEX idx_news_tag_news ON NEWS_TAG_MAP(news_id);
CREATE INDEX idx_news_tag_tag ON NEWS_TAG_MAP(tag_id, target_region);
```

**컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| mapping_id | INTEGER (PK) | 매핑 ID (자동 증가) | `1`, `2`, `3`... |
| news_id | TEXT (FK) | 뉴스 ID | `"news_20260626_abc123"` |
| tag_id | TEXT (FK) | 태그 ID | `"RAW_SPECIAL_GAS"` |
| target_region | TEXT (FK) | 대상 지역 | `"KR"` |
| confidence | REAL | 매핑 신뢰도 | `0.95` (정확 매칭), `0.85` (유사도 매칭) |
| extraction_method | TEXT | 추출 방법 | `"EXACT"`, `"SIMILARITY"`, `"LLM"` |

**extraction_method 값**:
- `"EXACT"`: OpenSearch 역인덱스 정확 매칭
- `"SIMILARITY"`: 임베딩 유사도 기반 매칭 (≥0.85)
- `"LLM"`: LLM 판별 후 사람 승인

**참고**: `DB_TAG_News Mapping Pipeline.md` 3.2절 참조

---

#### 3.2.5 NEWS_KEYWORD_EXTRACTION (뉴스 키워드 추출 이력 테이블)

**목적**: 뉴스에서 추출된 키워드 이력 저장

**생성**: 추후 뉴스-태그 매핑 파이프라인 구현 시 사용

**스키마**:
```sql
CREATE TABLE NEWS_KEYWORD_EXTRACTION (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    
    extraction_method TEXT,                -- "LLM" | "NER"
    keyword_type TEXT,                     -- LLM이 제안한 유형
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id)
);

CREATE INDEX idx_extraction_news ON NEWS_KEYWORD_EXTRACTION(news_id);
CREATE INDEX idx_extraction_keyword ON NEWS_KEYWORD_EXTRACTION(keyword);
```

**컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| extraction_id | INTEGER (PK) | 추출 ID (자동 증가) | `1`, `2`, `3`... |
| news_id | TEXT (FK) | 뉴스 ID | `"news_20260626_abc123"` |
| keyword | TEXT | 추출된 키워드 | `"희토류"`, `"중국"` |
| extraction_method | TEXT | 추출 방법 | `"LLM"`, `"NER"` |
| keyword_type | TEXT | LLM 제안 유형 | `"SUBSTANCE"`, `"SITE"` |

**참고**: `DB_TAG_News Mapping Pipeline.md` 3.2절 단계 1 참조

---

## 4. 데이터 소스 매핑

### 4.1 뉴스 수집기 → NEWS_MASTER

#### 4.1.1 국내 뉴스 (Naver API)

**소스 파일**: `dev/dev_module_news_searcher_domestic.py`

**출력 형식**:
```python
{
    'title': '중국 정부, 희토류 수출 통제 강화',  # HTML 태그 포함
    'link': 'https://...',
    'pubDate': 'Wed, 24 Jun 2026 15:28:00 +0900',  # RFC 2822 형식
    'full_content': '본문 내용...'
}
```

**매핑**:
| 뉴스 수집기 필드 | DB 컬럼 | 변환 |
|-----------------|---------|------|
| - | news_id | hash(source + link) 생성 |
| - | source | "NAVER_NEWS" 고정 |
| - | source_type | "DOMESTIC" 고정 |
| title | title | HTML 태그 제거 |
| link | url | - |
| pubDate | pub_date | ISO 8601 변환 |
| - | collected_at | 현재 시간 |
| full_content | content | - |

#### 4.1.2 글로벌 뉴스 (RSS/스크래핑)

**소스 파일**: `dev/dev_module_news_searcher_global.py`

**출력 형식**:
```python
{
    'source': 'BBC News - World',
    'category': 'world',
    'title': 'China tightens export controls...',  # HTML 태그 제거됨
    'link': 'https://...',
    'pubDate': '2026-06-24T15:28:00Z',
    'description': 'Summary...',
    'full_content': 'Full content...'
}
```

**매핑**:
| 뉴스 수집기 필드 | DB 컬럼 | 변환 |
|-----------------|---------|------|
| - | news_id | hash(source + link) 생성 |
| source | source | - |
| - | source_type | "GLOBAL_RSS" 또는 "GLOBAL_SCRAPE" |
| category | category | - |
| title | title | - |
| description | description | - |
| link | url | - |
| pubDate | pub_date | ISO 8601 변환 |
| - | collected_at | 현재 시간 |
| full_content | content | - |

---

### 4.2 CSV → TAG_MASTER / TAG_KEYWORD_MAP

**소스 파일**: `data/TAG/DB_TAG_Generated_Tags_v1.0.csv`

**CSV 구조**:
```csv
tag_id,target_region,tag_type,name,domain,risk_factor,keyword_count,keywords_full,description,target_table_column,db_matched_count
RAW_SPECIAL_GAS,KR,RAW_MATERIAL,특수가스,원자재&희소물질,특수가스 수급 리스크,30,아르곤 | 네온 | 희토류 | ...,특수가스. 대표 소재: 아르곤...,RAW_MATERIAL_MASTER.raw_material_type = '특수가스',23
```

**매핑**:

**TAG_MASTER**:
| CSV 컬럼 | DB 컬럼 |
|----------|---------|
| tag_id | tag_id |
| target_region | target_region |
| tag_type | tag_type |
| name | name |
| description | description |
| domain | domain |
| risk_factor | risk_factor |
| target_table_column | target_table_column |
| db_matched_count | db_matched_count |

**TAG_KEYWORD_MAP**:
| CSV 컬럼 | DB 컬럼 | 변환 |
|----------|---------|------|
| tag_id | tag_id | - |
| target_region | target_region | - |
| keywords_full | keyword | 파이프(`|`) 분리 후 각각 레코드 생성 |
| - | normalized | normalize_keyword() 적용 |
| - | is_primary | 첫 번째 키워드만 1, 나머지 0 |

---

## 5. 사용 예시

### 5.1 DB 연결

```python
from models.news_intelligence_db import get_db_connection

# DB 연결
db_path = "data/NEWS/news_intelligence.db"
conn = get_db_connection(db_path)
cursor = conn.cursor()
```

### 5.2 뉴스 삽입

```python
from models.news_intelligence_db import NewsMaster, insert_news
import hashlib
from datetime import datetime

# 뉴스 객체 생성
news = NewsMaster(
    news_id=hashlib.md5("BBC_https://...".encode()).hexdigest(),
    source="BBC News - World",
    source_type="GLOBAL_RSS",
    category="world",
    title="China tightens export controls on rare earth metals",
    description="China announces new export restrictions...",
    content="Full article content...",
    url="https://bbc.com/news/...",
    pub_date="2026-06-26T15:30:00",
    collected_at=datetime.now().isoformat()
)

# DB 삽입
insert_news(conn, news)
```

### 5.3 태그 검색 (키워드 기반)

```python
from models.news_intelligence_db import search_tags_by_keyword

# "희토류" 키워드로 태그 검색
tags = search_tags_by_keyword(conn, keyword="희토류", target_region="KR")

for tag in tags:
    print(f"Tag ID: {tag['tag_id']}")
    print(f"Name: {tag['name']}")
    print(f"Type: {tag['tag_type']}")
    print(f"Description: {tag['description'][:50]}...")
    print()
```

**출력 예시**:
```
Tag ID: RAW_SEMICONDUCTOR_METAL
Name: 반도체금속
Type: RAW_MATERIAL
Description: 반도체금속. 대표 소재: 하프늄, 게르마늄, 몰리브덴, 루테늄...
```

### 5.4 특정 태그의 모든 키워드 조회

```python
from models.news_intelligence_db import get_keywords_by_tag

# RAW_SPECIAL_GAS 태그의 키워드 조회
keywords = get_keywords_by_tag(conn, tag_id="RAW_SPECIAL_GAS", target_region="KR")

for kw in keywords:
    print(f"Keyword: {kw['keyword']}")
    print(f"Normalized: {kw['normalized']}")
    print(f"Primary: {bool(kw['is_primary'])}")
    print()
```

### 5.5 직접 SQL 쿼리

```python
# 최근 7일간 수집된 뉴스 개수 (출처별)
cursor.execute("""
    SELECT source, COUNT(*) as count
    FROM NEWS_MASTER
    WHERE DATE(collected_at) >= DATE('now', '-7 days')
    GROUP BY source
    ORDER BY count DESC
""")

results = cursor.fetchall()
for row in results:
    print(f"{row['source']}: {row['count']}개")
```

---

## 6. 구현 파일

### 6.1 DB 모델

**파일**: `models/news_intelligence_db.py`

**내용**:
- dataclass 정의 (NewsMaster, TagMaster, TagKeywordMap 등)
- DB 생성 함수 (`create_news_intelligence_db()`)
- 기본 CRUD 유틸리티 (`insert_news()`, `search_tags_by_keyword()` 등)

**참조**: 기존 `models/supply_chain_db.py` 패턴 재사용

### 6.2 마이그레이션 스크립트

**파일**: `scripts/migrate_tags_to_db.py`

**기능**:
1. CSV 읽기 (`data/TAG/DB_TAG_Generated_Tags_v1.0.csv`)
2. TAG_MASTER 삽입 (448개 레코드)
3. TAG_KEYWORD_MAP 삽입 (2,517개 키워드)
   - `keywords_full` 컬럼 파싱 (파이프 구분)
   - 정규화 처리 (`normalize_keyword()`)

**실행**:
```bash
python scripts/migrate_tags_to_db.py
```

**출력 예시**:
```
[TAG MIGRATION] Starting...
============================================================
Input CSV: C:\...\data\TAG\DB_TAG_Generated_Tags_v1.0.csv
Output DB: C:\...\data\NEWS\news_intelligence.db

[INFO] Database already exists. Appending data.

[INFO] CSV loaded: 448 records

[SUCCESS] Migration completed!
   - TAG_MASTER: 448 records
   - TAG_KEYWORD_MAP: 2517 records

[VERIFICATION] Checking migration results
============================================================
TAG_MASTER: 448 records
TAG_KEYWORD_MAP: 2517 records

target_region distribution:
  - GLOBAL: 224 records
  - KR: 224 records

tag_type distribution:
  - SUPPLIER: 246 records
  - EVENT: 120 records
  - MATERIAL: 46 records
  - RAW_MATERIAL: 20 records
  - SITE: 16 records

Foreign key integrity: 0 orphaned records

[SUCCESS] Verification completed: Data integrity OK
```

---

## 7. 데이터 통계

### 7.1 현재 상태 (2026-06-26 기준)

| 테이블 | 레코드 수 | 설명 |
|--------|-----------|------|
| NEWS_MASTER | 0 | 뉴스 수집 전 |
| TAG_MASTER | 448 | 224 tags × 2 regions |
| TAG_KEYWORD_MAP | 2,517 | 평균 ~5.6개/태그 |
| NEWS_TAG_MAP | 0 | 파이프라인 구현 전 |
| NEWS_KEYWORD_EXTRACTION | 0 | 파이프라인 구현 전 |

### 7.2 TAG_MASTER 통계

**target_region별 분포**:
| target_region | 레코드 수 |
|---------------|-----------|
| KR | 224 |
| GLOBAL | 224 |

**tag_type별 분포**:
| tag_type | 레코드 수 | 비율 |
|----------|-----------|------|
| SUPPLIER | 246 | 54.9% |
| EVENT | 120 | 26.8% |
| MATERIAL | 46 | 10.3% |
| RAW_MATERIAL | 20 | 4.5% |
| SITE | 16 | 3.6% |

### 7.3 용량 추정

**현재 DB 크기**: ~500KB (태그 데이터만)

**예상 증가율** (뉴스 수집 후):
- 일 100건 뉴스 × 평균 5KB/건 = **500KB/일**
- 월 3만 건 × 5KB = **15MB/월**
- 년 36만 건 × 5KB = **180MB/년**

**권장 관리 전략**:
- 6개월 이상 뉴스: 아카이빙 (별도 DB 이동)
- 분석 결과만 유지 (원문 삭제 가능)

---

## 8. 향후 확장

### 8.1 추가 예정 테이블 (현재 보류)

다음 테이블은 **추후 구현** 예정:
- `RISK_PATTERN_DETECTION`: 고위험 패턴 감지 결과
- `SUPPLY_CHAIN_IMPACT_ANALYSIS`: 공급망 영향 분석 결과
- `KEYWORD_REVIEW_QUEUE`: Human-in-the-loop 대기열

### 8.2 OpenSearch 도입 (계획 단계)

**목적**: 태그 정확 매칭 성능 향상

**대상 테이블**: TAG_KEYWORD_MAP

**참조**: `DB_TAG_News Mapping Pipeline.md` 3.2절 단계 2

**역인덱스 구조**:
```json
// OpenSearch 인덱스: tag_keywords
{
  "mappings": {
    "properties": {
      "tag_id": {"type": "keyword"},
      "keyword": {"type": "text", "analyzer": "standard"},
      "normalized": {"type": "keyword"}
    }
  }
}
```

### 8.3 임베딩 벡터 추가 (계획 단계)

**목적**: 유사도 기반 매칭 성능 향상

**대상 테이블**: TAG_MASTER

**추가 컬럼**:
```sql
ALTER TABLE TAG_MASTER ADD COLUMN embedding_vector BLOB;
```

**사용 모델**: `distiluse-base-multilingual-cased-v1`

**참조**: `DB_TAG_News Mapping Pipeline.md` 3.2절 단계 3

---

## 9. 참조 문서

### 9.1 관련 문서

- **`DB_TAG_News Mapping Pipeline.md`**: 뉴스-태그 매핑 파이프라인 전체 흐름
- **`Data Pipeline_Tag Creation_Docs.md`**: 태그 생성 방법론 (5가지 유형, 생성 전략)
- **`DB_SUPPLY MAP_Docs.md`**: 공급망 DB 설계 (7개 테이블, ER 다이어그램)

### 9.2 소스 코드

- **뉴스 수집**:
  - `dev/dev_module_news_searcher_domestic.py` (Naver API)
  - `dev/dev_module_news_searcher_global.py` (RSS/스크래핑)
- **DB 모델**:
  - `models/news_intelligence_db.py` (뉴스 인텔리전스 DB)
  - `models/supply_chain_db.py` (공급망 DB - 참조용)
- **스크립트**:
  - `scripts/migrate_tags_to_db.py` (태그 마이그레이션)

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-06-26 | 초기 버전 작성<br>- news_intelligence.db 생성<br>- 5개 테이블 정의<br>- 태그 CSV → DB 마이그레이션 완료 (448 tags, 2,517 keywords)<br>- 문서화 |

---

**작성자**: Claude Code (Sonnet 4.5)  
**최종 수정**: 2026-06-26
