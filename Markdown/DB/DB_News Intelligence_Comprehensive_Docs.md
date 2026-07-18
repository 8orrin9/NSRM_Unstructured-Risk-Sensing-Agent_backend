# 뉴스 인텔리전스 DB 종합 문서
## News Intelligence Database - Comprehensive Documentation

> **목적**: 프론트엔드 개발 시 데이터 연동을 위한 완전한 DB 참조 문서  
> **최종 업데이트**: 2026-07-10  
> **DB 파일**: `data/NEWS/news_intelligence.db`

---

## 📋 목차

1. [DB 개요](#1-db-개요)
2. [테이블 목록 및 관계도](#2-테이블-목록-및-관계도)
3. [테이블 상세 스키마](#3-테이블-상세-스키마)
4. [데이터 현황 통계](#4-데이터-현황-통계)
5. [프론트엔드 연동 가이드](#5-프론트엔드-연동-가이드)
6. [주요 쿼리 예제](#6-주요-쿼리-예제)
7. [Agent 처리 흐름](#7-agent-처리-흐름)

---

## 1. DB 개요

### 1.1 데이터베이스 정보

| 항목 | 값 |
|------|-----|
| **DB 유형** | SQLite 3 |
| **파일 경로** | `C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a\data\NEWS\news_intelligence.db` |
| **DB 크기** | ~4.6 MB |
| **문자 인코딩** | UTF-8 |
| **Foreign Key** | 활성화 (PRAGMA foreign_keys = ON) |

### 1.2 DB 역할

**공급망 리스크 뉴스 분석 시스템**의 운영 데이터베이스로:
- 수집된 뉴스 원문 저장
- 태그 시스템 (224개 태그, 2,620개 키워드)
- 뉴스-태그 매핑 결과
- Agent 분석 결과 (키워드 추출, 리스크 평가, 그룹화, 엔티티 추출)
- DB 검색 로그

### 1.3 데이터 분리 전략

| 구분 | 공급망 DB (supply_chain.db) | 뉴스 DB (news_intelligence.db) |
|------|----------------------------|--------------------------------|
| **데이터 특성** | 정적 마스터 데이터 | 동적 운영 데이터 |
| **업데이트 빈도** | 월/분기 단위 | 시간/일 단위 |
| **역할** | 읽기 전용 참조 | 빈번한 쓰기 |
| **백업 전략** | 주기적 풀백업 | 증분 백업 + 아카이빙 |

---

## 2. 테이블 목록 및 관계도

### 2.1 테이블 목록 (11개)

| 테이블명 | 레코드 수 | 역할 | 데이터 소스 |
|---------|----------|------|------------|
| **NEWS_MASTER** | 1,223 | 뉴스 원문 | 뉴스 수집 모듈 |
| **TAG_MASTER** | 448 | 태그 정의 | CSV 마이그레이션 |
| **TAG_KEYWORD_MAP** | 2,517 | 태그-키워드 매핑 | CSV 마이그레이션 |
| **NEWS_KEYWORD_EXTRACTION** | 0 | 뉴스 키워드 추출 | Agent 1 |
| **NEWS_TAG_MAP** | 0 | 뉴스-태그 매핑 | Agent 2 |
| **AGENT_DB_SEARCH_LOG** | 105 | DB 검색 로그 | Agent 3 |
| **NEWS_RISK_EVALUATION** | 90 | 리스크 평가 | Agent 4 |
| **NEWS_GROUP** | 6 | 그룹 메타데이터 | Agent 5 |
| **NEWS_GROUP_MEMBERSHIP** | 213 | 뉴스-그룹 관계 | Agent 5 |
| **NEWS_ENTITY_EXTRACTION** | 1,121 | 엔티티 추출 | Agent 5 |
| **INSIGHT_REPORT_MASTER** | 47 | 인사이트 리포트 | 외부 |

### 2.2 ER 다이어그램

```
┌─────────────────────┐
│  NEWS_MASTER (1223) │◄────────────┐
│  ─────────────────  │             │
│  news_id (PK)       │             │
│  source, title      │             │ 1
│  content, url       │             │
│  pub_date           │             │
│  agent1~5_*_at      │             │
└─────────────────────┘             │
         │                          │
         │ 1                        │
         │                          │
         ├──────────┬────────┬──────┴────────────┬───────────────┐
         │          │        │                   │               │
         │ N        │ N      │ N                 │ N             │ N
         │          │        │                   │               │
┌────────┴──────┐ ┌┴────────┴───┐ ┌─────────────┴──────┐ ┌──────┴─────────────┐
│ NEWS_KEYWORD_ │ │ NEWS_TAG_MAP│ │ AGENT_DB_SEARCH_LOG│ │ NEWS_RISK_         │
│ EXTRACTION(0) │ │ (0)         │ │ (105)              │ │ EVALUATION (90)    │
└───────────────┘ └─────────────┘ └────────────────────┘ └────────────────────┘
                  │                                       
                  │ N                                     
                  │                                       
                  │ 1                                     
         ┌────────┴──────┐                               
         │  TAG_MASTER   │                               
         │  (448)        │                               
         │  ─────────    │                               
         │  tag_id (PK)  │                               
         │  target_region│                               
         │  tag_type     │                               
         └───────┬───────┘                               
                 │ 1                                     
                 │                                       
                 │ N                                     
         ┌───────┴──────────┐                            
         │ TAG_KEYWORD_MAP  │                            
         │ (2,517)          │                            
         └──────────────────┘                            

┌─────────────────┐
│ NEWS_GROUP (6)  │
│ ───────────     │
│ group_id (PK)   │
│ group_theme     │
│ status          │
│ last_news_added │
└────────┬────────┘
         │ 1
         │
         │ N
┌────────┴──────────────┐
│ NEWS_GROUP_MEMBERSHIP │
│ (213)                 │
│ ─────────────────     │
│ group_id (FK)         │
│ news_id (FK) ─────────┼────► NEWS_MASTER
│ shared_entities       │
└───────────────────────┘

┌──────────────────────┐
│ NEWS_ENTITY_         │
│ EXTRACTION (1,121)   │
│ ──────────────       │
│ news_id (FK) ────────┼────► NEWS_MASTER
│ entity, entity_type  │
│ match_method         │
│ matched_kg_entity    │
└──────────────────────┘
```

---

## 3. 테이블 상세 스키마

### 3.1 NEWS_MASTER (뉴스 마스터)

**목적**: 수집된 뉴스 원문 및 Agent 처리 상태 추적

```sql
CREATE TABLE NEWS_MASTER (
    news_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    category TEXT,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    url TEXT NOT NULL UNIQUE,
    pub_date TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Agent 처리 타임스탬프 (다른 Agent가 추가)
    agent1_analyzer_processed_at TEXT,
    agent2_tagger_processed_at TEXT,
    agent3_searcher_processed_at TEXT,
    agent4_evaluator_processed_at TEXT,
    agent5_grouper_processed_at TEXT
);

CREATE INDEX idx_news_source ON NEWS_MASTER(source);
CREATE INDEX idx_news_pub_date ON NEWS_MASTER(pub_date);
CREATE INDEX idx_news_collected_at ON NEWS_MASTER(collected_at);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| news_id | TEXT (PK) | 고유 식별자 (MD5 hash) | `"aa7a8e2dcabbb2a5..."` |
| source | TEXT | 뉴스 출처 | `"NAVER_NEWS"`, `"BBC News"` |
| source_type | TEXT | 출처 유형 | `"DOMESTIC"`, `"GLOBAL_RSS"`, `"GLOBAL_SCRAPE"` |
| title | TEXT | 제목 (HTML 태그 제거됨) | `"중국 정부, 희토류 수출 통제 강화"` |
| content | TEXT | 본문 전문 | 크롤링된 전체 내용 |
| url | TEXT (UNIQUE) | 원문 URL | `"https://..."` |
| pub_date | TEXT | 발행 날짜 (ISO 8601) | `"2026-06-26T15:30:00"` |
| agent1_analyzer_processed_at | TEXT | Agent 1 처리 시각 | `"2026-07-10T04:11:00"` |
| agent2_tagger_processed_at | TEXT | Agent 2 처리 시각 | `NULL` (미처리) |
| agent3_searcher_processed_at | TEXT | Agent 3 처리 시각 | `"2026-07-10T04:12:00"` |
| agent4_evaluator_processed_at | TEXT | Agent 4 처리 시각 | `"2026-07-10T04:13:00"` |
| agent5_grouper_processed_at | TEXT | Agent 5 처리 시각 | `"2026-07-10T04:14:00"` |

**현재 데이터 통계**:
- 총 레코드: 1,223개
- source_type별:
  - DOMESTIC: 960개
  - GLOBAL_SCRAPE: 140개
  - FAKE_RISK: 75개
  - FAKE_RISK_V4: 35개
  - FAKE_GROUP: 13개

---

### 3.2 TAG_MASTER (태그 마스터)

**목적**: 공급망 리스크 분석을 위한 태그 정의

```sql
CREATE TABLE TAG_MASTER (
    tag_id TEXT NOT NULL,
    target_region TEXT NOT NULL,
    tag_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    domain TEXT,
    risk_factor TEXT,
    target_table_column TEXT,
    db_matched_count INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tag_id, target_region)
);

CREATE INDEX idx_tag_type ON TAG_MASTER(tag_type);
CREATE INDEX idx_tag_region ON TAG_MASTER(target_region);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| tag_id | TEXT (PK) | 태그 식별자 | `"RAW_SPECIAL_GAS"` |
| target_region | TEXT (PK) | 대상 지역 | `"KR"`, `"GLOBAL"` |
| tag_type | TEXT | 태그 유형 | `"RAW_MATERIAL"`, `"MATERIAL"`, `"SUPPLIER"`, `"SITE"`, `"EVENT"` |
| name | TEXT | 표시명 | `"특수가스"` (KR), `"Special Gas"` (GLOBAL) |
| description | TEXT | 설명 | `"특수가스. 대표 소재: 아르곤, 네온..."` |
| domain | TEXT | 대분류 | `"원자재&희소물질"` |
| risk_factor | TEXT | 리스크 요인 | `"특수가스 수급 리스크"` |

**현재 데이터 통계**:
- 총 레코드: 448개 (224 tags × 2 regions)
- tag_type별:
  - SUPPLIER: 246개
  - EVENT: 120개
  - MATERIAL: 46개
  - RAW_MATERIAL: 20개
  - SITE: 16개

---

### 3.3 TAG_KEYWORD_MAP (태그-키워드 매핑)

**목적**: 각 태그에 속하는 키워드 관리

```sql
CREATE TABLE TAG_KEYWORD_MAP (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id TEXT NOT NULL,
    target_region TEXT NOT NULL,
    keyword TEXT NOT NULL,
    normalized TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tag_id, target_region) REFERENCES TAG_MASTER(tag_id, target_region),
    UNIQUE (tag_id, target_region, keyword)
);

CREATE INDEX idx_keyword_normalized ON TAG_KEYWORD_MAP(normalized);
CREATE INDEX idx_keyword_tag ON TAG_KEYWORD_MAP(tag_id, target_region);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| keyword | TEXT | 키워드 원본 | `"희토류"`, `"Rare Earth"` |
| normalized | TEXT | 정규화 키워드 (소문자, 공백 제거) | `"희토류"`, `"rareearth"` |
| is_primary | INTEGER | 주요 키워드 여부 (1=주요, 0=일반) |

**현재 데이터**: 2,517개 키워드 (평균 5.6개/태그)

---

### 3.4 NEWS_KEYWORD_EXTRACTION (뉴스 키워드 추출)

**목적**: Agent 1이 뉴스에서 추출한 키워드 저장

```sql
CREATE TABLE NEWS_KEYWORD_EXTRACTION (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    extraction_method TEXT,
    keyword_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id)
);

CREATE INDEX idx_extraction_news ON NEWS_KEYWORD_EXTRACTION(news_id);
CREATE INDEX idx_extraction_keyword ON NEWS_KEYWORD_EXTRACTION(keyword);
```

**주요 컬럼 설명**:

| 컬럼명 | 값 | 설명 |
|--------|-----|------|
| extraction_method | `"LLM"`, `"NER"` | 추출 방법 |
| keyword_type | `"PRIMARY"`, `"SECONDARY"` | 키워드 중요도 (score >= 0.9: PRIMARY) |

**현재 데이터**: 0개 (이미 처리 완료, 274개 뉴스)

---

### 3.5 NEWS_TAG_MAP (뉴스-태그 매핑)

**목적**: Agent 2가 뉴스에 매핑한 태그 저장

```sql
CREATE TABLE NEWS_TAG_MAP (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    target_region TEXT NOT NULL,
    confidence REAL,
    extraction_method TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id),
    FOREIGN KEY (tag_id, target_region) REFERENCES TAG_MASTER(tag_id, target_region),
    UNIQUE (news_id, tag_id, target_region)
);

CREATE INDEX idx_news_tag_news ON NEWS_TAG_MAP(news_id);
CREATE INDEX idx_news_tag_tag ON NEWS_TAG_MAP(tag_id, target_region);
```

**주요 컬럼 설명**:

| 컬럼명 | 값 | 설명 |
|--------|-----|------|
| confidence | 0.0~1.0 | 매핑 신뢰도 |
| extraction_method | `"EXACT"`, `"SIMILARITY"`, `"LLM"` | 추출 방법 |

**현재 데이터**: 0개 (태그 매핑 없음)

---

### 3.6 AGENT_DB_SEARCH_LOG (DB 검색 로그)

**목적**: Agent 3의 DB 검색 실행 로그

```sql
CREATE TABLE AGENT_DB_SEARCH_LOG (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    search_strategy_id TEXT,
    fallback_strategy_used INTEGER DEFAULT 0,
    generated_sql TEXT,
    sql_explanation TEXT,
    search_result_count INTEGER DEFAULT 0,
    search_results TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id)
);

CREATE INDEX idx_db_search_news ON AGENT_DB_SEARCH_LOG(news_id);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| search_strategy_id | TEXT | 사용된 검색 전략 ID | `"STRAT_SITE_COUNTRY_LIST"` |
| fallback_strategy_used | INTEGER | Fallback 전략 사용 여부 (0=아니오, 1=예) |
| generated_sql | TEXT | 생성된 SQL 쿼리 |
| search_results | TEXT | 검색 결과 (JSON) |

**현재 데이터**: 105개 로그
- Fallback 미사용: 55개
- Fallback 사용: 50개

---

### 3.7 NEWS_RISK_EVALUATION (리스크 평가)

**목적**: Agent 4의 뉴스 리스크 평가 결과

```sql
CREATE TABLE NEWS_RISK_EVALUATION (
    evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    is_risk INTEGER DEFAULT 0,
    risk_score REAL DEFAULT 0.0,
    risk_justification TEXT,
    risk_factors TEXT,
    event_timing TEXT CHECK(event_timing IN ('ONGOING', 'SCHEDULED', 'PAST')),
    event_timing_confidence REAL,
    event_timing_justification TEXT,
    issue_type TEXT,
    issue_priority TEXT CHECK(issue_priority IN ('HIGH', 'MEDIUM', 'LOW')),
    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id),
    UNIQUE (news_id)
);

CREATE INDEX idx_risk_score ON NEWS_RISK_EVALUATION(risk_score DESC);
CREATE INDEX idx_event_timing ON NEWS_RISK_EVALUATION(event_timing);
CREATE INDEX idx_issue_type ON NEWS_RISK_EVALUATION(issue_type);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입/값 | 설명 |
|--------|---------|------|
| is_risk | INTEGER | 리스크 여부 (0=아니오, 1=예) |
| risk_score | REAL | 리스크 점수 (0.0~1.0) |
| risk_factors | TEXT | 리스크 요인 목록 (JSON) |
| event_timing | TEXT | 이벤트 시점 (`ONGOING`, `SCHEDULED`, `PAST`) |
| issue_type | TEXT | 이슈 유형 (`ISSUE`, `SMD`, `NONE`) |
| issue_priority | TEXT | 우선순위 (`HIGH`, `MEDIUM`, `LOW`) |

**현재 데이터**: 90개 평가
- Risk: 84개
- No Risk: 6개
- Event timing:
  - ONGOING: 76개
  - SCHEDULED: 14개
- 평균 risk_score: 0.82

---

### 3.8 NEWS_GROUP (뉴스 그룹)

**목적**: 그룹화된 뉴스의 메타데이터 및 생명주기 관리

```sql
CREATE TABLE NEWS_GROUP (
    group_id TEXT PRIMARY KEY,
    group_theme TEXT,
    risk_perspectives TEXT,
    compound_risk_pattern TEXT,
    hidden_connections TEXT,
    search_priorities TEXT,
    aggregate_confidence REAL,
    status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'DISSOLVED')),
    last_news_added_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    dissolved_at TEXT
);

CREATE INDEX idx_group_status ON NEWS_GROUP(status);
CREATE INDEX idx_group_last_news ON NEWS_GROUP(last_news_added_at);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| group_id | TEXT | 그룹 식별자 | `"group_001"` |
| group_theme | TEXT | 그룹 주제 | `"중국 반도체 공급망 제재 강화"` |
| risk_perspectives | TEXT | 리스크 관점 목록 (JSON) | `["EVENT_SUPPLIER", "POLICY_REGULATION"]` |
| compound_risk_pattern | TEXT | 복합 리스크 패턴 |
| hidden_connections | TEXT | 숨은 연관성 (JSON) |
| search_priorities | TEXT | 검색 우선순위 (JSON) |
| aggregate_confidence | REAL | 그룹 신뢰도 (0.0~1.0) |
| status | TEXT | 그룹 상태 (`ACTIVE`, `DISSOLVED`) |
| last_news_added_at | TEXT | 마지막 뉴스 추가 시각 (7일 규칙 적용) |

**현재 데이터**: 6개 그룹 (모두 ACTIVE 상태)

---

### 3.9 NEWS_GROUP_MEMBERSHIP (뉴스-그룹 멤버십)

**목적**: 뉴스와 그룹 간의 다대다 관계

```sql
CREATE TABLE NEWS_GROUP_MEMBERSHIP (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL,
    news_id TEXT NOT NULL,
    shared_entities TEXT,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES NEWS_GROUP(group_id) ON DELETE CASCADE,
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id),
    UNIQUE (group_id, news_id)
);

CREATE INDEX idx_membership_group ON NEWS_GROUP_MEMBERSHIP(group_id);
CREATE INDEX idx_membership_news ON NEWS_GROUP_MEMBERSHIP(news_id);
```

**주요 컬럼 설명**:

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| shared_entities | TEXT | 공유 엔티티 목록 (JSON) | `["중국", "반도체", "AI"]` |

**현재 데이터**: 213개 멤버십 (평균 35.5개 뉴스/그룹)

**Trigger**: `update_group_last_news` - 멤버십 추가 시 자동으로 `NEWS_GROUP.last_news_added_at` 업데이트

---

### 3.10 NEWS_ENTITY_EXTRACTION (엔티티 추출)

**목적**: Agent 5가 추출한 엔티티 및 Knowledge Graph 매칭

```sql
CREATE TABLE NEWS_ENTITY_EXTRACTION (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_type TEXT,
    match_method TEXT CHECK(match_method IN ('exact', 'fuzzy', 'none')),
    matched_kg_entity TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES NEWS_MASTER(news_id)
);

CREATE INDEX idx_entity_news ON NEWS_ENTITY_EXTRACTION(news_id);
CREATE INDEX idx_entity_type ON NEWS_ENTITY_EXTRACTION(entity_type);
CREATE INDEX idx_entity_text ON NEWS_ENTITY_EXTRACTION(entity);
```

**주요 컬럼 설명**:

| 컬럼명 | 값 | 설명 |
|--------|-----|------|
| entity | TEXT | 추출된 엔티티 | `"중국"`, `"삼성전자"` |
| entity_type | TEXT | 엔티티 유형 | `"Country"`, `"Company"`, `"Material"` 등 |
| match_method | TEXT | KG 매칭 방법 | `"exact"` (정확), `"fuzzy"` (유사), `"none"` (미매칭) |
| matched_kg_entity | TEXT | 매칭된 KG 엔티티 | `"China"` (영문명) |

**현재 데이터**: 1,121개 엔티티
- entity_type별:
  - Company: 287개
  - Country: 240개
  - Material: 177개
  - Event: 100개
  - Organization: 99개
- match_method별:
  - exact: 465개
  - none: 656개

---

### 3.11 INSIGHT_REPORT_MASTER (인사이트 리포트)

**목적**: 외부 인사이트 리포트 메타데이터

```sql
CREATE TABLE INSIGHT_REPORT_MASTER (
    report_id TEXT PRIMARY KEY,
    source_name TEXT,
    title TEXT,
    url TEXT,
    report_type TEXT,
    description TEXT,
    published_date TEXT,
    ...
);
```

**현재 데이터**: 47개 리포트

---

## 4. 데이터 현황 통계

### 4.1 전체 테이블 현황

| 테이블 | 레코드 수 | 비고 |
|-------|----------|------|
| NEWS_MASTER | 1,223 | 뉴스 원문 |
| TAG_MASTER | 448 | 태그 정의 (224 × 2 regions) |
| TAG_KEYWORD_MAP | 2,517 | 태그 키워드 |
| NEWS_KEYWORD_EXTRACTION | 0 | Agent 1 처리 완료 (274개) |
| NEWS_TAG_MAP | 0 | 태그 매핑 없음 |
| AGENT_DB_SEARCH_LOG | 105 | DB 검색 로그 |
| NEWS_RISK_EVALUATION | 90 | 리스크 평가 |
| NEWS_GROUP | 6 | 뉴스 그룹 |
| NEWS_GROUP_MEMBERSHIP | 213 | 그룹 멤버십 |
| NEWS_ENTITY_EXTRACTION | 1,121 | 추출된 엔티티 |
| INSIGHT_REPORT_MASTER | 47 | 인사이트 리포트 |

### 4.2 Agent 처리 현황

| Agent | 처리된 뉴스 수 | 처리율 | 비고 |
|-------|---------------|--------|------|
| **Agent 1** (News Analyzer) | 274 | 22.4% | 키워드 추출 완료 |
| **Agent 2** (Tag Mapper) | 0 | 0% | 태그 매핑 없음 |
| **Agent 3** (DB Searcher) | 105 | 8.6% | DB 검색 로그 |
| **Agent 4** (Risk Evaluator) | 90 | 7.4% | 리스크 평가 |
| **Agent 5** (News Grouper) | 213 | 17.4% | 그룹화 + 엔티티 추출 |

**전체 처리율 쿼리**:
```sql
SELECT 
    COUNT(*) as total_news,
    SUM(CASE WHEN agent1_analyzer_processed_at IS NOT NULL THEN 1 ELSE 0 END) as agent1_done,
    SUM(CASE WHEN agent2_tagger_processed_at IS NOT NULL THEN 1 ELSE 0 END) as agent2_done,
    SUM(CASE WHEN agent3_searcher_processed_at IS NOT NULL THEN 1 ELSE 0 END) as agent3_done,
    SUM(CASE WHEN agent4_evaluator_processed_at IS NOT NULL THEN 1 ELSE 0 END) as agent4_done,
    SUM(CASE WHEN agent5_grouper_processed_at IS NOT NULL THEN 1 ELSE 0 END) as agent5_done
FROM NEWS_MASTER;
```

---

## 5. 프론트엔드 연동 가이드

### 5.1 DB 연결 (Python)

```python
import sqlite3

# DB 연결
def get_db_connection(db_path="data/NEWS/news_intelligence.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # dict-like access
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# 사용 예
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM NEWS_MASTER LIMIT 10")
news_list = cursor.fetchall()
conn.close()
```

### 5.2 주요 API 엔드포인트 설계 예시

#### 5.2.1 뉴스 목록 조회

**Endpoint**: `GET /api/news`

**Query Parameters**:
- `page`: 페이지 번호 (default: 1)
- `limit`: 페이지 크기 (default: 20)
- `source_type`: 출처 유형 필터 (`DOMESTIC`, `GLOBAL_RSS` 등)
- `is_risk`: 리스크 여부 (`true`, `false`)
- `has_group`: 그룹 소속 여부 (`true`, `false`)

**SQL**:
```sql
SELECT 
    nm.news_id,
    nm.title,
    nm.source,
    nm.pub_date,
    nre.is_risk,
    nre.risk_score,
    ng.group_id,
    ng.group_theme
FROM NEWS_MASTER nm
LEFT JOIN NEWS_RISK_EVALUATION nre ON nm.news_id = nre.news_id
LEFT JOIN NEWS_GROUP_MEMBERSHIP ngm ON nm.news_id = ngm.news_id
LEFT JOIN NEWS_GROUP ng ON ngm.group_id = ng.group_id
WHERE nm.is_active = 1
ORDER BY nm.pub_date DESC
LIMIT ? OFFSET ?;
```

#### 5.2.2 뉴스 상세 조회

**Endpoint**: `GET /api/news/:news_id`

**Response 구조**:
```json
{
  "news": {
    "news_id": "abc123",
    "title": "...",
    "content": "...",
    "source": "NAVER_NEWS",
    "pub_date": "2026-07-09T12:00:00",
    "url": "https://..."
  },
  "keywords": [
    {"keyword": "희토류", "type": "PRIMARY"},
    {"keyword": "중국", "type": "SECONDARY"}
  ],
  "tags": [
    {"tag_id": "RAW_SPECIAL_GAS", "name": "특수가스", "confidence": 0.95}
  ],
  "risk_evaluation": {
    "is_risk": true,
    "risk_score": 0.85,
    "event_timing": "ONGOING",
    "risk_factors": ["원자재 공급 차질", "지정학적 리스크"]
  },
  "entities": [
    {"entity": "중국", "type": "Country", "matched_kg": "China"},
    {"entity": "희토류", "type": "Material", "matched_kg": "Rare Earth"}
  ],
  "group": {
    "group_id": "group_001",
    "group_theme": "중국 반도체 공급망 제재 강화",
    "shared_entities": ["중국", "반도체", "미국"]
  }
}
```

**SQL** (여러 쿼리 조합):
```sql
-- 1. 뉴스 기본 정보
SELECT * FROM NEWS_MASTER WHERE news_id = ?;

-- 2. 키워드
SELECT keyword, keyword_type FROM NEWS_KEYWORD_EXTRACTION WHERE news_id = ?;

-- 3. 태그
SELECT tm.tag_id, tm.name, ntm.confidence
FROM NEWS_TAG_MAP ntm
JOIN TAG_MASTER tm ON ntm.tag_id = tm.tag_id AND ntm.target_region = tm.target_region
WHERE ntm.news_id = ?;

-- 4. 리스크 평가
SELECT * FROM NEWS_RISK_EVALUATION WHERE news_id = ?;

-- 5. 엔티티
SELECT entity, entity_type, matched_kg_entity
FROM NEWS_ENTITY_EXTRACTION WHERE news_id = ?;

-- 6. 그룹 정보
SELECT ng.*, ngm.shared_entities
FROM NEWS_GROUP_MEMBERSHIP ngm
JOIN NEWS_GROUP ng ON ngm.group_id = ng.group_id
WHERE ngm.news_id = ?;
```

#### 5.2.3 그룹 목록 조회

**Endpoint**: `GET /api/groups`

**Query Parameters**:
- `status`: 그룹 상태 (`ACTIVE`, `DISSOLVED`)

**SQL**:
```sql
SELECT 
    ng.group_id,
    ng.group_theme,
    ng.aggregate_confidence,
    ng.status,
    ng.last_news_added_at,
    COUNT(DISTINCT ngm.news_id) as news_count,
    AVG(nre.risk_score) as avg_risk_score
FROM NEWS_GROUP ng
LEFT JOIN NEWS_GROUP_MEMBERSHIP ngm ON ng.group_id = ngm.group_id
LEFT JOIN NEWS_RISK_EVALUATION nre ON ngm.news_id = nre.news_id
WHERE ng.status = ?
GROUP BY ng.group_id
ORDER BY ng.last_news_added_at DESC;
```

#### 5.2.4 그룹 상세 조회

**Endpoint**: `GET /api/groups/:group_id`

**Response 구조**:
```json
{
  "group": {
    "group_id": "group_001",
    "group_theme": "...",
    "risk_perspectives": ["EVENT_SUPPLIER", "POLICY_REGULATION"],
    "compound_risk_pattern": "...",
    "hidden_connections": [...],
    "search_priorities": [...],
    "aggregate_confidence": 0.85,
    "status": "ACTIVE",
    "news_count": 24
  },
  "news_list": [
    {
      "news_id": "abc123",
      "title": "...",
      "pub_date": "...",
      "risk_score": 0.9
    },
    ...
  ]
}
```

**SQL**:
```sql
-- 1. 그룹 정보
SELECT * FROM NEWS_GROUP WHERE group_id = ?;

-- 2. 그룹 내 뉴스 목록
SELECT 
    nm.news_id,
    nm.title,
    nm.pub_date,
    nre.risk_score
FROM NEWS_GROUP_MEMBERSHIP ngm
JOIN NEWS_MASTER nm ON ngm.news_id = nm.news_id
LEFT JOIN NEWS_RISK_EVALUATION nre ON nm.news_id = nre.news_id
WHERE ngm.group_id = ?
ORDER BY nm.pub_date DESC;
```

#### 5.2.5 리스크 대시보드

**Endpoint**: `GET /api/dashboard/risk`

**Response 구조**:
```json
{
  "total_news": 1223,
  "risk_news_count": 84,
  "risk_percentage": 93.3,
  "average_risk_score": 0.82,
  "event_timing": {
    "ONGOING": 76,
    "SCHEDULED": 14
  },
  "top_risk_news": [
    {
      "news_id": "...",
      "title": "...",
      "risk_score": 0.95,
      "pub_date": "..."
    }
  ]
}
```

**SQL**:
```sql
-- 통계
SELECT 
    COUNT(*) as total_evaluated,
    SUM(is_risk) as risk_count,
    AVG(risk_score) as avg_score
FROM NEWS_RISK_EVALUATION;

-- 최근 고위험 뉴스
SELECT nm.news_id, nm.title, nm.pub_date, nre.risk_score
FROM NEWS_RISK_EVALUATION nre
JOIN NEWS_MASTER nm ON nre.news_id = nm.news_id
WHERE nre.is_risk = 1
ORDER BY nre.risk_score DESC, nm.pub_date DESC
LIMIT 10;
```

---

## 6. 주요 쿼리 예제

### 6.1 뉴스 검색

#### 제목/내용 검색 (Full-text search)
```sql
SELECT * FROM NEWS_MASTER
WHERE title LIKE '%반도체%' OR content LIKE '%반도체%'
ORDER BY pub_date DESC
LIMIT 20;
```

#### 날짜 범위 검색
```sql
SELECT * FROM NEWS_MASTER
WHERE DATE(pub_date) BETWEEN '2026-07-01' AND '2026-07-10'
ORDER BY pub_date DESC;
```

#### 출처별 검색
```sql
SELECT source, COUNT(*) as count
FROM NEWS_MASTER
WHERE source_type = 'DOMESTIC'
GROUP BY source
ORDER BY count DESC;
```

### 6.2 리스크 분석

#### 고위험 뉴스 (risk_score >= 0.8)
```sql
SELECT nm.title, nre.risk_score, nre.event_timing
FROM NEWS_RISK_EVALUATION nre
JOIN NEWS_MASTER nm ON nre.news_id = nm.news_id
WHERE nre.risk_score >= 0.8
ORDER BY nre.risk_score DESC;
```

#### 진행 중인 이벤트
```sql
SELECT nm.title, nre.risk_score, nre.risk_justification
FROM NEWS_RISK_EVALUATION nre
JOIN NEWS_MASTER nm ON nre.news_id = nm.news_id
WHERE nre.event_timing = 'ONGOING'
  AND nre.is_risk = 1
ORDER BY nre.risk_score DESC;
```

### 6.3 그룹 관리

#### 활성 그룹 조회 (7일 이내 업데이트)
```sql
SELECT * FROM NEWS_GROUP
WHERE status = 'ACTIVE'
  AND datetime(last_news_added_at) > datetime('now', '-7 days')
ORDER BY last_news_added_at DESC;
```

#### 해체 대상 그룹 조회 (7일 이상 경과)
```sql
SELECT 
    group_id,
    group_theme,
    last_news_added_at,
    CAST((julianday('now') - julianday(last_news_added_at)) AS INT) as days_since_last_news
FROM NEWS_GROUP
WHERE status = 'ACTIVE'
  AND julianday('now') - julianday(last_news_added_at) > 7;
```

#### 그룹별 뉴스 수
```sql
SELECT 
    ng.group_id,
    ng.group_theme,
    COUNT(DISTINCT ngm.news_id) as news_count
FROM NEWS_GROUP ng
LEFT JOIN NEWS_GROUP_MEMBERSHIP ngm ON ng.group_id = ngm.group_id
GROUP BY ng.group_id
ORDER BY news_count DESC;
```

### 6.4 엔티티 분석

#### 가장 많이 언급된 엔티티 TOP 10
```sql
SELECT entity, entity_type, COUNT(*) as mention_count
FROM NEWS_ENTITY_EXTRACTION
WHERE match_method = 'exact'
GROUP BY entity, entity_type
ORDER BY mention_count DESC
LIMIT 10;
```

#### 특정 엔티티가 언급된 뉴스
```sql
SELECT DISTINCT nm.news_id, nm.title, nm.pub_date
FROM NEWS_ENTITY_EXTRACTION nee
JOIN NEWS_MASTER nm ON nee.news_id = nm.news_id
WHERE nee.entity = '중국'
ORDER BY nm.pub_date DESC;
```

### 6.5 Agent 처리 상태

#### 미처리 뉴스 확인
```sql
SELECT 
    news_id,
    title,
    pub_date,
    CASE 
        WHEN agent1_analyzer_processed_at IS NULL THEN 'Agent 1 pending'
        WHEN agent2_tagger_processed_at IS NULL THEN 'Agent 2 pending'
        WHEN agent3_searcher_processed_at IS NULL THEN 'Agent 3 pending'
        WHEN agent4_evaluator_processed_at IS NULL THEN 'Agent 4 pending'
        WHEN agent5_grouper_processed_at IS NULL THEN 'Agent 5 pending'
        ELSE 'Fully processed'
    END as processing_status
FROM NEWS_MASTER
WHERE agent1_analyzer_processed_at IS NULL
   OR agent2_tagger_processed_at IS NULL
   OR agent3_searcher_processed_at IS NULL
   OR agent4_evaluator_processed_at IS NULL
   OR agent5_grouper_processed_at IS NULL
ORDER BY pub_date DESC;
```

---

## 7. Agent 처리 흐름

### 7.1 데이터 파이프라인 흐름도

```
[뉴스 수집 모듈]
    ↓
┌───────────────────┐
│  NEWS_MASTER      │ ← 1,223개 뉴스 적재
│  (뉴스 원문)       │
└─────────┬─────────┘
          │
          ├─────────► [Agent 1: News Analyzer]
          │           ↓
          │           NEWS_KEYWORD_EXTRACTION (274개 처리)
          │           agent1_analyzer_processed_at 업데이트
          │
          ├─────────► [Agent 2: Tag Mapper]
          │           ↓
          │           NEWS_TAG_MAP (0개 - 태그 없음)
          │           agent2_tagger_processed_at 업데이트
          │
          ├─────────► [Agent 3: DB Searcher]
          │           ↓
          │           AGENT_DB_SEARCH_LOG (105개 검색 로그)
          │           agent3_searcher_processed_at 업데이트
          │
          ├─────────► [Agent 4: Risk Evaluator]
          │           ↓
          │           NEWS_RISK_EVALUATION (90개 평가)
          │           agent4_evaluator_processed_at 업데이트
          │
          └─────────► [Agent 5: News Grouper]
                      ↓
                      NEWS_GROUP (6개 그룹)
                      NEWS_GROUP_MEMBERSHIP (213개 멤버십)
                      NEWS_ENTITY_EXTRACTION (1,121개 엔티티)
                      agent5_grouper_processed_at 업데이트
```

### 7.2 Agent별 처리 규칙

#### Agent 1 (News Analyzer)
- **입력**: NEWS_MASTER (agent1_analyzer_processed_at IS NULL)
- **출력**: NEWS_KEYWORD_EXTRACTION
- **타임스탬프 업데이트**: agent1_analyzer_processed_at = CURRENT_TIMESTAMP

#### Agent 2 (Tag Mapper)
- **입력**: NEWS_MASTER (agent2_tagger_processed_at IS NULL)
- **출력**: NEWS_TAG_MAP
- **타임스탬프 업데이트**: agent2_tagger_processed_at = CURRENT_TIMESTAMP

#### Agent 3 (DB Searcher)
- **입력**: NEWS_MASTER (agent3_searcher_processed_at IS NULL)
- **출력**: AGENT_DB_SEARCH_LOG
- **타임스탬프 업데이트**: agent3_searcher_processed_at = CURRENT_TIMESTAMP

#### Agent 4 (Risk Evaluator)
- **입력**: NEWS_MASTER (agent4_evaluator_processed_at IS NULL)
- **출력**: NEWS_RISK_EVALUATION
- **타임스탬프 업데이트**: agent4_evaluator_processed_at = CURRENT_TIMESTAMP

#### Agent 5 (News Grouper)
- **입력**: NEWS_MASTER (agent5_grouper_processed_at IS NULL)
- **출력**: 
  - NEWS_GROUP
  - NEWS_GROUP_MEMBERSHIP
  - NEWS_ENTITY_EXTRACTION
- **타임스탬프 업데이트**: agent5_grouper_processed_at = CURRENT_TIMESTAMP

### 7.3 그룹 생명주기 관리

#### 7일 규칙
```sql
-- 자동 해체 쿼리 (스케줄러에서 실행)
UPDATE NEWS_GROUP
SET status = 'DISSOLVED',
    dissolved_at = CURRENT_TIMESTAMP
WHERE status = 'ACTIVE'
  AND julianday('now') - julianday(last_news_added_at) >= 7;
```

#### Trigger: 자동 last_news_added_at 업데이트
```sql
CREATE TRIGGER update_group_last_news
AFTER INSERT ON NEWS_GROUP_MEMBERSHIP
BEGIN
    UPDATE NEWS_GROUP
    SET last_news_added_at = (
        SELECT MAX(nm.pub_date)
        FROM NEWS_GROUP_MEMBERSHIP ngm
        JOIN NEWS_MASTER nm ON ngm.news_id = nm.news_id
        WHERE ngm.group_id = NEW.group_id
    )
    WHERE group_id = NEW.group_id;
END;
```

---

## 8. 부록

### 8.1 참고 문서

- **DB 설계 문서**: `Markdown/DB/DB_News Intelligence_Docs.md`
- **태그 생성 방법론**: `Markdown/Data Pipeline/Data Pipeline_Tag Creation_Docs.md`
- **뉴스 수집 가이드**: `Markdown/Data Pipeline/Data Pipeline_News Crawling_Comprehensive_Guide.md`
- **공급망 DB 설계**: `Markdown/DB/DB_SUPPLY MAP_Docs.md`

### 8.2 데이터 백업

```bash
# 백업
cp data/NEWS/news_intelligence.db data/NEWS/news_intelligence.db.backup_$(date +%Y%m%d_%H%M%S)

# 복원
cp data/NEWS/news_intelligence.db.backup_20260710_041059 data/NEWS/news_intelligence.db
```

### 8.3 DB 최적화

```sql
-- 인덱스 재구축
REINDEX;

-- 통계 업데이트
ANALYZE;

-- 빈 공간 정리
VACUUM;
```

### 8.4 연락처

- **DB 관리자**: Claude Code (Sonnet 4.5)
- **프로젝트**: NSRM Risk-Sensing (poc-a)
- **문서 버전**: v2.0 (2026-07-10)

---

**END OF DOCUMENT**
