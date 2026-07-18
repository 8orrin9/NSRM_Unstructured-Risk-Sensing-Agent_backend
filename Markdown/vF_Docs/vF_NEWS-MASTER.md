# NEWS_MASTER 재구성 및 뉴스 수집·적재

> 공급망 Risk-Sensing 5-Agent 파이프라인 평가용 golden dataset 기반 데이터 구축 기록
> 작업일: 2026-07-15

---

## 1. 개요

기존 `NEWS_MASTER`(1,235행)는 저품질 뉴스가 다수 섞여 있고 컬럼이 과도하게 많아(`category`, `title_ko/summary_ko/content_ko`, `agent1~5_processed_at` 등) **아예 새로 시작**하기로 결정했다.

본 작업은 다음 순서로 진행했다.

1. `NEWS_MASTER`를 슬림한 스키마로 재구성하고 기존 테이블은 `NEWS_MASTER_OLD`로 보존
2. 하위 결과 테이블 7개를 전부 비움
3. risk factor 기반 **국내 뉴스**를 새로 수집·적재
4. `risk_category_name` 컬럼 추가 및 매핑

> **참고**: 해외 뉴스(`GLOBAL_SCRAPE`)도 수집했으나 품질 문제(정부/언론 사이트 봇 차단, JS 렌더링, 메뉴·랜딩 페이지 혼입)로 **최종적으로 제외**했다. 현재 NEWS_MASTER는 국내 뉴스만 포함한다.
>
> `backend/agents` 소스코드가 스키마 변경으로 발생시키는 에러는 **추후 별도 해결** 대상이며 본 작업 범위 밖이다.

---

## 2. 최종 NEWS_MASTER 스키마 (15컬럼)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `news_id` | TEXT PK | URL MD5 해시 |
| `source` | TEXT NOT NULL | 출처 (국내=`NAVER_NEWS`) |
| `source_type` | TEXT NOT NULL | `DOMESTIC` |
| `risk_factor` | TEXT | 39개 risk factor 중 하나 |
| `keyword` | TEXT | 수집에 사용한 대표 키워드 |
| `title` | TEXT NOT NULL | 기사 제목 |
| `description` | TEXT | 요약(네이버 API description) |
| `content` | TEXT | 크롤링 본문 |
| `url` | TEXT NOT NULL UNIQUE | 기사 URL |
| `pub_date` | TEXT NOT NULL | 발행일 |
| `collected_at` | TEXT NOT NULL | 수집 시각 |
| `is_active` | INTEGER DEFAULT 1 | 활성 여부 |
| `created_at` | TEXT | 생성 시각 |
| `updated_at` | TEXT | 수정 시각 |
| `risk_category_name` | TEXT | 9개 상위 risk category (아래 매핑) |

> `risk_category_name`은 SQLite `ALTER TABLE ADD COLUMN` 특성상 테이블 맨 끝에 위치한다.

### 재생성 DDL

```sql
CREATE TABLE NEWS_MASTER (
    news_id      TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    risk_factor  TEXT,
    keyword      TEXT,
    title        TEXT NOT NULL,
    description  TEXT,
    content      TEXT,
    url          TEXT NOT NULL UNIQUE,
    pub_date     TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    is_active    INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_news_source       ON NEWS_MASTER(source);
CREATE INDEX idx_news_pub_date      ON NEWS_MASTER(pub_date);
CREATE INDEX idx_news_collected_at ON NEWS_MASTER(collected_at);

-- 이후 컬럼 추가
ALTER TABLE NEWS_MASTER ADD COLUMN risk_category_name TEXT;
```

---

## 3. 작업 과정

모든 명령은 프로젝트 루트에서 `.venv` 활성 + `PYTHONIOENCODING=utf-8`, Windows `python` 기준.

### Step 0 — DB 백업

- **스크립트**: `scripts/db/backup_news_db.py`
- `shutil.copy2`로 `data/NEWS/news_intelligence.db` → `backup/data/NEWS/news_intelligence_<YYYYMMDD_HHMMSS>.db` 복사
- 검증: 복사본 존재 + `PRAGMA integrity_check`=ok + `NEWS_MASTER` 1,235행
- 결과 백업 파일: `backup/data/NEWS/news_intelligence_20260715_183730.db`

### Step 1 — 테이블 마이그레이션

- **스크립트**: `scripts/db/migrate_news_master_slim.py`
- 단일 트랜잭션 로직:
  1. `PRAGMA legacy_alter_table=ON` (RENAME이 하위 테이블 FK의 `REFERENCES NEWS_MASTER`를 `_OLD`로 자동 재작성하는 것을 방지)
  2. `DROP INDEX IF EXISTS` 3개 (RENAME 후 인덱스 이름 충돌 방지)
  3. `ALTER TABLE NEWS_MASTER RENAME TO NEWS_MASTER_OLD` (1,235행 보존)
  4. 새 `NEWS_MASTER`(14컬럼) + 인덱스 3개 재생성
  5. 하위 **7개** 테이블 `DELETE FROM` + `sqlite_sequence` 리셋
- 비운 하위 테이블: `NEWS_TAG_MAP`, `NEWS_RISK_EVALUATION`, `NEWS_KEYWORD_EXTRACTION`, `NEWS_ENTITY_EXTRACTION`, `NEWS_GROUP_MEMBERSHIP`, `AGENT_DB_SEARCH_LOG`, `NEWS_GROUP`

### Step 2 — 국내 뉴스 수집

- **스크립트**: `dev/data_pipeline/data_pipeline_news_collector_domestic.py`
- **입력**: `data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx` — `2. Keyword Set_ai` 시트, `target_region=KR`
- **키워드 선정**: 각 `risk_factor`가 처음 등장하는 행의 `keyword` 배열 첫 원소를 대표 키워드로 선정 → **risk_factor당 1개, 총 39개** (9개 risk category 전체 커버)
- **수집 방법**: Naver News Search API (`sort=date`, 키워드당 최신 3건) → 본문은 BeautifulSoup으로 크롤링
- **품질 검증**: OFF (수집만, 정제는 추후 별도) — `--validate` 플래그 미사용
- **실행**:
  ```bash
  python dev/data_pipeline/data_pipeline_news_collector_domestic.py --limit 3
  ```
- **출력**: `temp/news_domestic_collected.json` (115건, 39×3=117 중 중복 URL 2건 제외)

### Step 3 — 적재

- **스크립트**: `scripts/db/load_news_master.py`
- `temp/news_domestic_collected.json`을 읽어 `INSERT OR IGNORE`(news_id PK / url UNIQUE 중복 스킵)로 NEWS_MASTER에 적재
- `_`로 시작하는 크롤러 디버깅 메타 필드는 제거 후 삽입
- **실행**:
  ```bash
  python scripts/db/load_news_master.py
  ```

### Step 4 — risk_category_name 추가

- `ALTER TABLE NEWS_MASTER ADD COLUMN risk_category_name TEXT`
- Excel `2. Keyword Set_ai` 시트의 `risk_factor → risk_category_name` 매핑(39개, DB 값과 100% 일치) 적용
- 115행 전부 매핑 완료 (누락 0건)

---

## 4. 최종 결과

| 항목 | 값 |
|---|---|
| NEWS_MASTER 총 행수 | **115** |
| source_type | `DOMESTIC` 115 |
| content 보유 | 114 / 115 (99%) |
| distinct risk_factor | 39 |
| risk_category_name 매핑 누락 | 0 |
| NEWS_MASTER_OLD (보존) | 1,235 |
| 하위 7개 테이블 | 전부 0행 |

### risk_category_name 분포 (9개 카테고리)

| risk_category_name | 건수 |
|---|---|
| 지정학 & 규제 | 21 |
| 원자재&희소물질 | 21 |
| 물류&인프라 | 14 |
| 사이버&데이터 | 12 |
| 기술&지식재산 | 12 |
| ESG & Compliance | 12 |
| 재무&신용 Risk | 9 |
| 공급집중&단일소싱 | 8 |
| 자연재해&기후 | 6 |

---

## 5. 관련 파일

| 구분 | 경로 |
|---|---|
| 백업 스크립트 | `scripts/db/backup_news_db.py` |
| 마이그레이션 스크립트 | `scripts/db/migrate_news_master_slim.py` |
| 국내 수집기 | `dev/data_pipeline/data_pipeline_news_collector_domestic.py` |
| 적재 스크립트 | `scripts/db/load_news_master.py` |
| 키워드/카테고리 소스 | `data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx` (`2. Keyword Set_ai`) |
| 수집 결과 JSON | `temp/news_domestic_collected.json` |
| DB | `data/NEWS/news_intelligence.db` |
| DB 백업 | `backup/data/NEWS/news_intelligence_20260715_183730.db` |

---

## 6. 남은 작업 (후속)

- **본문 정제**: 현재 "수집만" 상태로 footer / 기자 정보 / 비기사 콘텐츠가 정제되지 않음
- **`backend/agents` 스키마 대응**: 컬럼 변경(category 제거, risk_factor/keyword/risk_category_name 추가)에 따른 소스코드 수정
- **golden dataset 병합**: 가짜 뉴스(`data/NEWS/golden_dataset.json`, 48건)와의 통합
