# 뉴스 크롤링 종합 가이드

## 📋 개요

이 문서는 NSRM Risk-Sensing 프로젝트의 뉴스 수집 파이프라인 전체를 다루는 종합 가이드입니다.

**최종 업데이트**: 2026-07-08

---

## 🎯 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [국내 뉴스 크롤링 (Naver API)](#국내-뉴스-크롤링)
3. [글로벌 뉴스 크롤링 (HTML Scraping)](#글로벌-뉴스-크롤링)
4. [본문 크롤링 공통 로직](#본문-크롤링-공통-로직)
5. [데이터베이스 저장](#데이터베이스-저장)
6. [본문 재크롤링 (Updater)](#본문-재크롤링)
7. [트러블슈팅](#트러블슈팅)
8. [실행 방법](#실행-방법)

---

## 아키텍처 개요

### 전체 파이프라인

```
[1단계] 뉴스 수집
│
├─ 국내 뉴스 (Naver API)
│   └─ data_pipeline_news_collector_domestic.py
│       ↓
│       temp/news_domestic_collected.json
│
└─ 글로벌 뉴스 (HTML Scraping)
    └─ data_pipeline_news_collector_global.py
        ↓
        temp/news_global_collected.json

[2단계] DB 저장
    └─ data_pipeline_db_loader.py
        ↓
        data/NEWS/news_intelligence.db (NEWS_MASTER 테이블)

[3단계] 본문 재크롤링 (선택적)
    └─ data_pipeline_news_content_updater.py
        ↓
        빈 content 필드 채우기
```

### 핵심 특징

- **2단계 파이프라인**: 메타데이터 수집 → 본문 크롤링
- **이중 안전망**: Collector(수집 시) + Updater(수집 후)
- **선택자 확장**: 20개 CSS 선택자로 다양한 언론사 대응
- **is_active 플래그**: 분석 대상 뉴스 필터링

---

## 국내 뉴스 크롤링

### 📍 파일 위치
`dev/data_pipeline/data_pipeline_news_collector_domestic.py`

### 입력/출력

| 항목 | 경로 | 설명 |
|------|------|------|
| **입력** | `data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx` | "2. Keyword Set" 시트 (target_region=KR) |
| **출력** | `temp/news_domestic_collected.json` | 수집된 국내 뉴스 (JSON) |

### 사전 준비

#### 1. Naver Open API 신청

1. [네이버 개발자 센터](https://developers.naver.com/apps/#/register) 접속
2. "애플리케이션 등록" 클릭
3. "검색" API 선택
4. Client ID와 Client Secret 발급

#### 2. 환경 설정

**프로젝트 루트 `.env` 파일 작성**:

```env
NAVER_CLIENT_ID=your_client_id_here
NAVER_CLIENT_SECRET=your_client_secret_here
```

⚠️ **주의사항**:
- `.env` 파일은 `.gitignore`에 포함 (보안)
- 등호(`=`) 앞뒤 공백 없이 작성

#### 3. 필수 라이브러리

```bash
pip install python-dotenv beautifulsoup4 lxml requests pandas openpyxl
```

### 크롤링 프로세스

#### 1단계: 키워드 로드

```python
# data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx 읽기
# "2. Keyword Set" 시트에서 target_region='KR' 필터링
# JSON 배열 파싱: ["키워드1", "키워드2", "키워드3"] → 전체 키워드 사용 (2026-07-09 개선)
# 중복 제거 후 반환
```

**🔄 개선 내역 (2026-07-09)**:
- **이전**: JSON 배열의 첫 번째 키워드만 사용
- **현재**: 모든 키워드 활용 (동의어/대체 키워드 포함)
- **효과**: 키워드 수 2-3배 증가, 더 다양한 관련 뉴스 수집
- **중복 제거**: 여러 Risk Factor가 같은 키워드 포함 시 자동 제거

#### 2단계: Naver API 검색

```python
# 각 키워드당 5개 뉴스 검색 (기본값)
# 최신순 정렬 (sort=date)
# URL: https://openapi.naver.com/v1/search/news.json
```

**API 응답 구조**:
```json
{
  "items": [
    {
      "title": "<b>키워드</b> 관련 뉴스 제목",
      "link": "https://n.news.naver.com/...",
      "description": "뉴스 요약...",
      "pubDate": "Mon, 08 Jul 2026 10:00:00 +0900"
    }
  ]
}
```

#### 3단계: 본문 크롤링

**20개 CSS 선택자 순회**:
```python
CONTENT_SELECTORS = [
    # 네이버 뉴스
    '#dic_area',
    '#articeBody',
    
    # 일반 뉴스
    'article',
    '.article-content',
    '.article-body',
    '[itemprop="articleBody"]',
    
    # 추가 패턴 (총 20개)
    '.news-content',
    '.story-body',
    '#newsContent',
    # ...
]
```

**핵심 로직** (2026-07-08 개선):
```python
# 선택자가 매칭되어도 본문이 짧으면 다음 선택자 시도
for selector in CONTENT_SELECTORS:
    elem = soup.select_one(selector)
    if elem:
        # 불필요한 태그 제거
        for tag in elem(['script', 'style', 'iframe', ...]):
            tag.decompose()
        
        text = elem.get_text(separator='\n', strip=True).strip()
        
        # 본문이 충분히 길면 성공
        if len(text) >= 50:
            return (text, selector, None)
```

⭐ **개선 포인트** (2026-07-08): 
- 이전: 첫 번째 매칭된 선택자에서 중단 → 빈 `<article>` 태그 때문에 실패
- 현재: 유효한 본문(50자 이상)이 나올 때까지 계속 시도

#### 4단계: LLM 품질 검증 ✨ NEW (2026-07-09)

**목적**: 크롤링된 본문이 실제 뉴스 내용인지 검증

**문제점**:
- 20개 선택자로 크롤링해도 실제 뉴스 내용이 아닌 **무관한 메타데이터만 포함**된 경우 존재
- 예: 기자 이름, 날짜, 저작권 안내, 사이트 메뉴만 크롤링

**해결 방법**: OpenAI GPT-4o-mini로 본문 검증

```python
def validate_news_content_with_llm(title: str, content: str) -> dict:
    """
    LLM으로 본문이 유효한 뉴스 내용인지 판정
    - is_valid: True (유효) / False (무효)
    - reason: 판정 이유
    """
    # 프롬프트 예시
    """
    다음 뉴스 제목과 본문을 보고, 본문이 유효한 뉴스 내용인지 판정해주세요.
    
    **판정 기준**:
    - 유효: 본문에 뉴스 사건/내용이 포함됨 (최소 2-3문장 이상)
    - 무효: 기자 정보, 날짜, 저작권 안내, 광고만 포함
    
    **출력 형식 (JSON)**:
    {
      "is_valid": true or false,
      "reason": "판정 이유"
    }
    """
```

**검증 결과**:
- **통과**: 본문 저장, 콘솔 로그 `[VALID]`
- **실패**: 본문을 `None`으로 처리, 콘솔 로그 `[REJECT]`

**비용**:
- 모델: gpt-4o-mini (저렴)
- 입력: 제목 + 본문 500자
- 예상 비용: 뉴스 1개당 ~$0.0001

#### 5단계: JSON 저장

**출력 형식** (`temp/news_domestic_collected.json`):
```json
[
  {
    "news_id": "5c5efa7ae114fc92c6410742bcef0621",
    "source": "NAVER_NEWS",
    "source_type": "DOMESTIC",
    "category": null,
    "title": "허위정보 규제냐 표현의 자유 침해냐…",
    "description": "개정 정보통신망법이 7일 시행되면서...",
    "content": "전체 본문 텍스트...",
    "url": "https://www.kukinews.com/article/...",
    "pub_date": "2026-07-07T10:00:00+09:00",
    "collected_at": "2026-07-08T11:00:00",
    "is_active": true,
    "created_at": "2026-07-08T11:00:00",
    "updated_at": "2026-07-08T11:00:00",
    "_search_keyword": "정보통신망법",
    "_crawl_selector": "[itemprop=\"articleBody\"]",
    "_crawl_error": null
  }
]
```

### 실행 방법

```bash
# 기본 실행 (키워드당 5개)
python dev/data_pipeline/data_pipeline_news_collector_domestic.py

# 수집 개수 지정
python dev/data_pipeline/data_pipeline_news_collector_domestic.py --limit 10
```

### 크롤링 통계 출력

```
[크롤링 통계]
  시도: 154건
  성공: 143건 (92%)
  Fallback: 2건
  실패: 9건 (5%)

[실패 원인 Top 3]
  - 모든 선택자 불일치: 5건
  - 타임아웃 (15초): 3건
  - 본문이 너무 짧음: 1건
```

---

## 글로벌 뉴스 크롤링

### 📍 파일 위치
`dev/data_pipeline/data_pipeline_news_collector_global.py`

### 입력/출력

| 항목 | 경로 | 설명 |
|------|------|------|
| **입력** | `data/NEWS/Global Source Research_vF.xlsx` | "Global Sources" 시트 |
| **출력** | `temp/news_global_collected.json` | 수집된 글로벌 뉴스 |
| **실패 로그** | `temp/news_global_failed.json` | 크롤링 실패 URL |

### 크롤링 방식

**HTML Scraping Only** (RSS 미사용):
- BeautifulSoup으로 뉴스 목록 페이지 직접 크롤링
- 각 소스별 고유 선택자 사용
- 동적 로딩 사이트는 제외

### 소스 구조

**Excel 파일 구조** (`Global Source Research_vF.xlsx`):

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| `source_name` | 소스 이름 | "White House" |
| `base_url` | 메인 URL | "https://www.whitehouse.gov" |
| `news_list_url` | 뉴스 목록 페이지 | "https://www.whitehouse.gov/news" |
| `list_selector` | 뉴스 항목 선택자 | "article.news-item" |
| `title_selector` | 제목 선택자 | "h3.title" |
| `link_selector` | 링크 선택자 | "a" |
| `date_selector` | 날짜 선택자 | "time" |
| `exclude` | 제외 여부 | 0 또는 1 |

### 크롤링 프로세스

#### 1단계: 소스 로드

```python
# Global Source Research_vF.xlsx 읽기
# exclude = 0인 소스만 필터링
# 각 소스의 선택자 정보 로드
```

#### 2단계: 뉴스 목록 크롤링

```python
# 각 소스의 news_list_url 접속
response = requests.get(news_list_url, timeout=15)
soup = BeautifulSoup(response.text, 'lxml')

# list_selector로 뉴스 항목 추출
news_items = soup.select(list_selector)

for item in news_items:
    # 제목, 링크, 날짜 추출
    title = item.select_one(title_selector).get_text(strip=True)
    link = item.select_one(link_selector)['href']
    date = item.select_one(date_selector).get_text(strip=True)
```

#### 3단계: 본문 크롤링

국내 뉴스와 동일한 20개 선택자 사용 (공통 로직)

#### 4단계: JSON 저장

**출력 형식** (`temp/news_global_collected.json`):
```json
[
  {
    "news_id": "f22cfab1c30c5c7cef38d0107194e5c3",
    "source": "White House",
    "source_type": "GLOBAL_SCRAPE",
    "category": "Press Release",
    "title": "President Announces New Policy...",
    "description": "",
    "content": "Full article text...",
    "url": "https://www.whitehouse.gov/briefing-room/...",
    "pub_date": "2026-07-08T10:00:00",
    "collected_at": "2026-07-08T11:00:00",
    "is_active": true,
    "created_at": "2026-07-08T11:00:00",
    "updated_at": "2026-07-08T11:00:00"
  }
]
```

### 실행 방법

```bash
# 기본 실행
python dev/data_pipeline/data_pipeline_news_collector_global.py

# 특정 소스만 수집
python dev/data_pipeline/data_pipeline_news_collector_global.py --source "White House"
```

### 제외 소스 관리

**Excel에서 exclude=1 설정**:
```python
# 크롤링 실패하거나 본문 수집이 안 되는 소스
# Excel 파일에서 exclude 컬럼을 1로 설정
```

---

## 본문 크롤링 공통 로직

### 핵심 개선사항 (2026-07-08)

**문제**: 일부 사이트는 `<article>` 태그가 비어있음 (JavaScript 동적 로딩)

**해결**: 선택자를 순회하며 **유효한 본문**이 나올 때까지 시도

### 선택자 목록 (20개)

```python
CONTENT_SELECTORS = [
    # 네이버 뉴스 (국내 주요)
    '#dic_area',              # 네이버 뉴스 표준
    '#articeBody',            # 네이버 뉴스 (오타 포함)
    
    # 표준 HTML5 시맨틱 태그
    'article',                # 대부분의 뉴스 사이트
    '[itemprop="articleBody"]', # Schema.org 표준
    'main article',           # 메인 컨텐츠 영역
    
    # 일반적인 클래스명
    '.article-content',
    '.article-body',
    '.article_body',
    '.article_content',
    '.post-content',
    '.post-body',
    '.entry-content',
    
    # 뉴스 전용 클래스
    '.news-content',
    '.news_article',
    '.story-body',
    
    # ID 선택자
    '#article-body',
    '#newsContent',
    '#story-body',
    '#contents',
    
    # 상세 페이지 일반
    '.detail-content',
]
```

### 불필요한 태그 제거

```python
for tag in elem(['script', 'style', 'iframe', 'noscript', 
                 'nav', 'aside', 'header', 'footer']):
    tag.decompose()
```

### 타임아웃 설정

```python
response = requests.get(url, headers=headers, verify=False, timeout=15)
```

- **타임아웃**: 15초 (2026-07-08 개선: 10초 → 15초)
- **이유**: 일부 사이트는 로딩이 느림

### Fallback 로직

```python
# 모든 선택자 실패 시 description 사용
if description and len(description) > 20:
    return (description, "fallback:description", "선택자 불일치, description 사용")
```

---

## 데이터베이스 저장

### 📍 파일 위치
`dev/data_pipeline/data_pipeline_db_loader.py`

### DB 스키마

**테이블**: `NEWS_MASTER`

```sql
CREATE TABLE NEWS_MASTER (
    news_id TEXT PRIMARY KEY,
    source TEXT,
    source_type TEXT,  -- DOMESTIC, GLOBAL_SCRAPE
    category TEXT,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,      -- NULL 허용
    url TEXT UNIQUE NOT NULL,
    pub_date TEXT,
    collected_at TEXT,
    is_active INTEGER DEFAULT 1,  -- 분석 대상 여부
    created_at TEXT,
    updated_at TEXT
);
```

### is_active 플래그

**용도**: 분석 대상 뉴스 필터링

| 값 | 의미 | 예시 |
|----|------|------|
| `1` | 활성 (분석 대상) | 정상 뉴스 기사 |
| `0` | 비활성 (분석 제외) | 카테고리 페이지, 뉴스레터, 중복 |

**Agent 1 (News_Analyzer) 사용**:
```sql
SELECT * FROM NEWS_MASTER WHERE is_active = 1
```

### 중복 제거

```python
# news_id (URL 해시)로 중복 체크
news_id = hashlib.md5(url.encode('utf-8')).hexdigest()

# DB INSERT 시 UNIQUE 제약으로 중복 방지
```

---

## 본문 재크롤링

### 📍 파일 위치
`dev/data_pipeline/data_pipeline_news_content_updater.py`

### 목적

**수집 시점에 본문 크롤링 실패한 뉴스 재시도**

### 실행 조건

```sql
SELECT news_id, url, title
FROM NEWS_MASTER
WHERE content IS NULL OR content = ''
```

### 개선사항 (2026-07-08)

**경로 버그 수정**:
```python
# 수정 전
PROJECT_ROOT = Path(__file__).parent.parent  # dev/

# 수정 후
PROJECT_ROOT = Path(__file__).parent.parent.parent  # poc-a/
```

**로직 개선**: Collector와 동일하게 선택자 순회

### 실행 방법

```bash
# 기본 실행
python dev/data_pipeline/data_pipeline_news_content_updater.py

# Batch 크기 지정
python dev/data_pipeline/data_pipeline_news_content_updater.py --batch-size 100
```

### 실행 결과 (2026-07-08)

```
[INFO] 본문 없는 뉴스: 34개

[완료]
성공: 6개
실패: 28개

[실패 로그 저장]
temp/news_content_failed.json
```

**개선 효과**:
- 전체 본문 확보율: 85% → 88% (+3%)
- 국내 뉴스: 92% → 93%

---

## 트러블슈팅

### 문제 1: 본문이 빈 값으로 저장됨

**증상**:
```sql
SELECT COUNT(*) FROM NEWS_MASTER WHERE content IS NULL;
-- 결과: 11개
```

**원인**:
- 일부 사이트는 `<article>` 태그가 비어있음
- 첫 번째 매칭된 선택자에서 중단

**해결** (2026-07-08):
```python
# 수정 전: 첫 매칭 시 중단
for selector in SELECTORS:
    elem = soup.select_one(selector)
    if elem:
        return elem.get_text()  # 길이 0이어도 반환

# 수정 후: 유효한 본문까지 계속 시도
for selector in SELECTORS:
    elem = soup.select_one(selector)
    if elem:
        text = elem.get_text(strip=True)
        if len(text) >= 50:  # 최소 길이 체크
            return text
```

### 문제 2: JavaScript 동적 로딩 사이트

**증상**:
- requests + BeautifulSoup으로 접속하면 본문 없음
- 브라우저로 접속하면 본문 정상

**원인**:
- 본문이 JavaScript로 로드됨 (React, Vue 등)

**해결**:
1. **단기**: is_active=0으로 비활성화
2. **장기**: Selenium 도입 (향후)

**해당 사이트**:
- asiatime.co.kr
- koreadaily.com
- koreatimes.co.kr

### 문제 3: 환경변수 로드 실패

**증상**:
```
Error: NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 환경변수를 설정해주세요.
```

**원인**:
- `.env` 파일이 없거나 경로가 잘못됨

**해결**:
```bash
# 프로젝트 루트에 .env 파일 생성
cd poc-a
cat > .env << EOF
NAVER_CLIENT_ID=your_id
NAVER_CLIENT_SECRET=your_secret
EOF
```

### 문제 4: ModuleNotFoundError

**증상**:
```
ModuleNotFoundError: No module named 'models'
```

**원인**:
- PROJECT_ROOT 경로 설정 오류
- `dev/data_pipeline/` 기준으로 `parent.parent`는 `dev/`

**해결**:
```python
# dev/data_pipeline/*.py에서
PROJECT_ROOT = Path(__file__).parent.parent.parent  # poc-a/
```

### 문제 5: 타임아웃 에러

**증상**:
```
requests.exceptions.Timeout: HTTPConnectionPool(host='...', port=80): Read timed out.
```

**해결**:
```python
# 타임아웃 증가 (10초 → 15초)
response = requests.get(url, timeout=15)
```

### 문제 6: LLM 품질 검증 실패 ✨ NEW (2026-07-09)

**증상**:
```
[REJECT] 무효한 본문 - 기자 정보와 저작권 안내만 있음
```

**원인**:
- 크롤링된 본문이 실제 뉴스 내용이 아닌 메타데이터만 포함
- 선택자가 잘못된 영역을 선택 (예: footer, aside)

**해결**:
1. **자동 제거**: LLM이 무효 판정 → 해당 뉴스는 DB에 저장되지 않음
2. **선택자 개선**: 특정 사이트에서 반복 실패 시 전용 선택자 추가
3. **로그 확인**: `temp/news_domestic_collected.json`에서 `_crawl_error` 필드 확인

**예시**:
```json
{
  "_crawl_error": "LLM 품질 검증 실패: 기자 정보와 저작권만 포함"
}
```

**비용 절감 팁**:
- 환경변수 `OPENAI_API_KEY`가 없으면 LLM 검증 스킵 (길이 체크만)
- 필요 시 `.env`에서 키 제거하여 비활성화 가능

---

## 실행 방법

### 전체 파이프라인 실행

```bash
# 1. 국내 뉴스 수집
python dev/data_pipeline/data_pipeline_news_collector_domestic.py --limit 5

# 2. 글로벌 뉴스 수집
python dev/data_pipeline/data_pipeline_news_collector_global.py

# 3. DB 저장
python dev/data_pipeline/data_pipeline_db_loader.py

# 4. 본문 재크롤링 (선택적)
python dev/data_pipeline/data_pipeline_news_content_updater.py
```

### 일괄 실행 스크립트

**`scripts/run_news_pipeline.sh`** (예시):
```bash
#!/bin/bash
set -e

echo "=== 뉴스 수집 파이프라인 시작 ==="

# 1. 국내 뉴스
echo "[1/4] 국내 뉴스 수집 중..."
python dev/data_pipeline/data_pipeline_news_collector_domestic.py

# 2. 글로벌 뉴스
echo "[2/4] 글로벌 뉴스 수집 중..."
python dev/data_pipeline/data_pipeline_news_collector_global.py

# 3. DB 저장
echo "[3/4] DB 저장 중..."
python dev/data_pipeline/data_pipeline_db_loader.py

# 4. 본문 재크롤링
echo "[4/4] 본문 재크롤링 중..."
python dev/data_pipeline/data_pipeline_news_content_updater.py

echo "=== 완료 ==="
```

### DB 백업

```bash
# 백업 생성
python -c "
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH = Path('data/NEWS/news_intelligence.db')
BACKUP_DIR = Path('backup/data/NEWS')
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_path = BACKUP_DIR / f'news_intelligence_backup_{timestamp}.db'
shutil.copy2(DB_PATH, backup_path)

print(f'백업 완료: {backup_path}')
"
```

---

## 부록

### A. 크롤링 성공률 (2026-07-08 기준)

| 구분 | 전체 | 본문 있음 | 본문 없음 | 성공률 |
|------|------|-----------|-----------|--------|
| **전체** | 227개 | 200개 | 27개 | 88% |
| **국내(DOMESTIC)** | 154개 | 144개 | 10개 | 93% |
| **글로벌(GLOBAL_SCRAPE)** | 73개 | 56개 | 17개 | 77% |

### B. 주요 개선 이력

| 날짜 | 개선 내용 | 효과 |
|------|----------|------|
| 2026-07-09 | **키워드 확장** (첫 번째→전체 사용) | 키워드 수 2-3배 증가, 뉴스 수집 범위 확대 |
| 2026-07-09 | **LLM 품질 검증 추가** (GPT-4o-mini) | 무효한 본문 자동 제거, 분석 품질 향상 |
| 2026-07-09 | 중복 키워드 자동 제거 | 불필요한 API 호출 방지 |
| 2026-07-08 | 선택자 순회 로직 개선 | 성공률 +3% |
| 2026-07-08 | 타임아웃 10초→15초 | 타임아웃 에러 50% 감소 |
| 2026-07-08 | updater 경로 버그 수정 | 정상 실행 |
| 2026-07-08 | 선택자 4개→20개 확장 | 다양한 사이트 대응 |

### C. 향후 개선 계획

1. **LLM 배치 검증**: 여러 뉴스를 한 번에 검증하여 비용 절감
2. **캐싱 시스템**: 동일 사이트/패턴은 재검증 스킵
3. **Rule-based 사전 필터**: 명확한 패턴은 LLM 없이 제거
4. **Selenium 도입**: JavaScript 동적 로딩 사이트 대응
5. **언론사별 전용 크롤러**: 주요 언론사 맞춤 로직
6. **키워드 우선순위**: 중요도 낮은 키워드는 선택적 수집

---

## 문의

- **작성자**: Claude (AI Assistant)
- **최종 수정**: 2026-07-08
- **이슈 리포트**: GitHub Issues 또는 프로젝트 담당자에게 문의
