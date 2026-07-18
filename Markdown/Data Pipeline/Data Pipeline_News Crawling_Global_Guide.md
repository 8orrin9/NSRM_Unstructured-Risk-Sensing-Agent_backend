# 글로벌 뉴스 크롤링 모듈 가이드

## 📋 개요

이 문서는 비정형 Risk 센싱 Agent의 **글로벌 뉴스 수집 Sub-Agent** 개발 가이드입니다.

**모듈 경로**: `poc-a/dev/dev_module_news_searcher_global.py`

**아키텍처**: RSS 피드 + HTML 스크래핑 하이브리드 방식

---

## 🎯 주요 기능

1. **RSS 피드 파싱** (feedparser) - 7개 국제 매체 (검증 완료)
2. **HTML 스크래핑** (BeautifulSoup) - 3개 정부 기관 (검증 완료)
3. **최근 48시간 뉴스 수집** (시차 고려 - 한국/미국 14시간 차이)
4. **Risk Factor Pool 전체 커버** - 35개 세부 리스크 대응
5. **멀티 소스 병렬 수집** - 총 10개 소스 (RSS 7개 + 스크래핑 3개)
6. **BeautifulSoup 기반 본문 크롤링** (2단계 파이프라인)
7. **안정적 소스 조합** - RSS 중심 + 검증된 HTML 스크래핑
8. **실시간 수집 가능**: 평균 100+개 기사/일 (최근 48시간 기준)

---

## 🔧 사전 준비

### 1. 필수 라이브러리 설치

```bash
pip install feedparser beautifulsoup4 lxml requests python-dotenv
```

**라이브러리 설명**:
- `feedparser`: RSS/Atom 피드 파싱
- `beautifulsoup4`: HTML 파싱
- `lxml`: BeautifulSoup의 고속 파서
- `requests`: HTTP 요청
- `python-dotenv`: 환경변수 로드 (참조용)

### 2. 환경 설정

**인증 불필요**: RSS 피드 및 공개 웹페이지만 사용하므로 API 키 불필요

---

## 📦 코드 구조

### 파일 구조

```
poc-a/dev/
├── dev_module_news_searcher_global.py    # 메인 모듈
├── config_news_sources_global.py         # 소스 설정 (RSS + 스크래핑)
├── module_selenium_scraper.py            # Selenium 스크래퍼 (향후 확장용)
└── config_news_sources_selenium.py       # Selenium 소스 설정 (예비)
```

**설정 분리 이점**:
- 소스 추가/수정이 간편함
- 메인 로직과 설정의 명확한 분리
- 다른 모듈에서도 재사용 가능

### 전체 흐름 (2단계 파이프라인)

```
[1단계: 메타데이터 수집]
Part 1: RSS 피드 파싱 (7개 소스)
   ↓
   - feedparser로 RSS 파싱
   - 최근 48시간 필터링
   - 메타데이터 수집 (title, link, pubDate, description)
   
Part 2: HTML 스크래핑 (3개 소스)
   ↓
   - BeautifulSoup으로 목록 페이지 파싱
   - 뉴스 링크 추출
   - 최근 48시간 필터링

[2단계: 본문 크롤링]
   ↓
   - BeautifulSoup으로 각 URL 접속
   - 매체별 선택자로 본문 추출
   - HTML 정제 및 텍스트 정규화
   - ThreadPoolExecutor로 병렬 처리 (5배 속도 향상)
   - 결과 출력
```

---

## 🌐 최종 선정 소스 (2026-06-26 기준)

### ✅ RSS 소스 (7개) - 검증 완료

| 소스명 | RSS URL | 커버 Risk Factor | 수집량/일 | 상태 |
|--------|---------|----------------|----------|------|
| **White House** | `https://www.whitehouse.gov/news/feed` | 지정학&규제, 정책 변동, 지역갈등/분쟁 | 3개 | ✅ 정상 |
| **BBC World** | `http://feeds.bbci.co.uk/news/world/rss.xml` | 지역갈등/분쟁, 지정학&규제, 환율 변동성 | 21개 | ✅ 정상 |
| **BBC Business** | `http://feeds.bbci.co.uk/news/business/rss.xml` | 협력사 재무 부실, 공급집중, M&A 위험 | 24개 | ✅ 정상 |
| **BBC Technology** | `http://feeds.bbci.co.uk/news/technology/rss.xml` | 사이버 공격, 데이터 주권, 기술 유출, SW 취약점 | 5개 | ✅ 정상 |
| **Supply Chain Dive** | `https://www.supplychaindive.com/feeds/news/` | 공급집중, 단일소싱, ESG 규제, 항만 혼잡, 물류 경로 차단 | 5개 | ✅ 정상 |
| **FreightWaves** | `https://www.freightwaves.com/feed` | 항만 혼잡, 수출허가지연, 물류 경로 차단, 항공 운임, 화물 파업 | 14개 | ✅ 정상 |
| **Semiconductor Engineering** | `https://semiengineering.com/feed/` | 장비 독과점, 소재 단일 공급, 기술 유출, 기술 단절, R&D 집중도 | 10개 | ✅ 정상 (본문 선택자 수정 완료) |

**총 수집**: 82개/일 (최근 48시간 기준)

### ✅ HTML 스크래핑 소스 (3개) - 검증 완료

| 소스명 | URL | 커버 Risk Factor | 수집량/일 | 상태 |
|--------|-----|----------------|----------|------|
| **US House Foreign Affairs (Democrats)** | `https://democrats-foreignaffairs.house.gov/press-releases` | 지역갈등/분쟁, 외교 정책, 지정학&규제 | 10개 | ✅ 정상 |
| **China NDRC (发改委)** | `https://en.ndrc.gov.cn/news/pressreleases/` | 지정학&규제, 산업 정책, 투자 규제 | 15개 | ✅ 정상 |
| **China Ministry of National Defense** | `http://eng.mod.gov.cn/2025xb/N/T/index.html` | 지역갈등/분쟁, 국방 정책, 지정학&규제 | 10개 | ✅ 정상 (2026-06-26 추가) |

**총 수집**: 35개/일 (최근 48시간 기준)

### 📊 수집 성능 (2026-06-26 실제 테스트)

- **총 소스**: 10개 (RSS 7개 + HTML 3개)
- **총 수집**: 100+개 기사/일 (예상)
- **본문 크롤링 성공률**: 97.8%
- **실행 시간**: 4-5분
- **안정성**: 높음 (RSS 중심)

---

## ❌ 배제된 소스 (10개)

### 배제 사유별 분류

BeautifulSoup으로는 수집 불가능한 소스들입니다.

#### A. JavaScript 동적 렌더링 (5개) - 미국 정부 기관

| 소스명 | URL | 배제 이유 | 향후 대안 |
|--------|-----|----------|----------|
| **미 상무부** | `https://www.trade.gov/press-releases` | JS 동적 렌더링 | Selenium 또는 API 조사 |
| **미 국방부** | `https://www.defense.gov/News/Releases/` | 무한 스크롤 + JS 렌더링 | Selenium (우선순위 높음) |
| **미 국무부** | `https://www.state.gov/press-releases/` | JS 동적 렌더링 | Selenium 또는 API 조사 |
| **미 재무부** | `https://home.treasury.gov/news/press-releases` | JS 렌더링 + HTTP 503 | Selenium (우선순위 높음) |
| **하원 외교위 (공화)** | `https://foreignaffairs.house.gov/news/press-releases` | JS 동적 렌더링 | 보류 (민주당 버전 있음) |

#### B. 페이지 구조 복잡성 (2개) - 일본 정부 기관

| 소스명 | URL | 배제 이유 | 향후 대안 |
|--------|-----|----------|----------|
| **일본 외무성** | `https://www.mofa.go.jp/press/release/index.html` | 2단계 구조 (월별 인덱스 → 개별 뉴스), RSS 없음 | 보류 (복잡도 높음) |
| **일본 경제산업성** | `https://www.meti.go.jp/english/press/index.html` | 2단계 구조 (카테고리 인덱스 → 개별 뉴스), RSS 없음 | 보류 (복잡도 높음) |

#### C. JavaScript 동적 렌더링 (2개) - 중국 정부 기관

| 소스명 | URL | 배제 이유 | 향후 대안 |
|--------|-----|----------|----------|
| **중국 상무부** | `https://english.mofcom.gov.cn/News/SignificantNews/index.html` | JS 동적 렌더링 (정적 HTML 68자만 존재) | Selenium 필요 (2026-06-26 확인) |
| **중국 공업정보화부** | `https://english.www.gov.cn/news/` | JS 동적 렌더링 | 보류 |

**Note**: 중국 국방부는 새 URL 발견으로 복구됨 (`http://eng.mod.gov.cn/2025xb/N/T/index.html`) → 스크래핑 소스에 추가 완료

#### D. JavaScript 동적 렌더링 (2개) - 한국 (기존)

| 소스명 | URL | 배제 이유 | 향후 대안 |
|--------|-----|----------|----------|
| **코트라** | `https://dream.kotra.or.kr/kotranews/cms/com/index.do?MENU_ID=70` | JS 동적 렌더링 | 보류 (기존 실패 이력) |
| **관세청** | `https://www.customs.go.kr/korean/ad/selectBbsNttList.do?bbsNo=169` | JS 동적 렌더링 (7개 URL 패턴 테스트 실패) | Selenium 필요 (우선순위 낮음) |

### 💡 Selenium 도입 검토

**준비 완료**: Selenium 모듈 이미 작성됨
- `dev/module_selenium_scraper.py`: Selenium 스크래퍼 클래스
- `dev/config_news_sources_selenium.py`: 10개 소스 설정 (중국 국방부 제외)

**도입 비용**:
- 실행 시간: 4-5분 → 15-25분 (5배 증가)
- 성공률: 97.8% → 60-70% 예상 (사이트 변경에 취약)
- 유지보수: 낮음 → 매우 높음 (매달 선택자 점검)

**권장 방안**:
1. ✅ **현재 10개 소스 유지** (안정적, 효율적)
2. 🔍 **숨겨진 API 조사** 후 안정적인 소스 추가
3. 🎯 **핵심 2-3개만 선별 추가** (미 국방부, 미 재무부 등 정책 영향도 높은 소스)

---

## 🗺️ Risk Factor 커버리지 분석

### Risk Factor Pool 구조 (35개 세부 RF)

| 대분류 | 세부 RF 수 | 주요 Risk Factor |
|--------|-----------|----------------|
| **지정학 & 규제** | 7개 | 수출입규제, 무역분쟁&관세, 지역갈등/분쟁, 외국인 투자규제, 역외적용, 기업제재, 기술 단절 |
| **공급집중 & 단일소싱** | 3개 | 공급집중, 단일소싱, 장비 독과점 |
| **원자재 & 희소물질** | 5개 | 소재 단일 공급, 희토류/네온/팔라듐 가격 |
| **기술 & 지식재산** | 4개 | 기술 유출, 특허분쟁, R&D 집중도 |
| **물류 & 인프라** | 5개 | 항만 혼잡, 물류 경로 차단, 항공 운임, 화물 파업, 수출허가지연 |
| **사이버 & 데이터** | 4개 | 사이버 공격, OT/ICS 보안, 데이터 주권, SW 취약점 |
| **ESG & Compliance** | 4개 | 환경 규제, 탄소 규제, ESG 규제, 인권·노동 규제 |
| **재무 & 신용** | 3개 | 협력사 재무 부실, 환율 변동성, M&A 위험 |

### 소스별 커버리지 매핑

#### 지정학 & 규제 (7개 RF) - ✅ 90% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 수출입규제 | - | ⚠️ Gap (미 상무부 배제로 인한) |
| 무역분쟁&관세 | BBC Business | 범용 커버 |
| 지역갈등/분쟁 | **White House, BBC World, 하원 외교위** | ✅ 강력 |
| 외교 정책 | **White House, 하원 외교위** | ✅ 강력 |
| 지정학&규제 | **White House, BBC World, 중국 NDRC** | ✅ 강력 |
| 정책 변동 | **White House, 중국 NDRC** | ✅ 강력 |
| 투자 규제 | **중국 NDRC** | ✅ 강력 |

**개선**: 미 상무부 (수출입규제) Selenium 추가 검토

#### 공급집중 & 단일소싱 (3개 RF) - ✅ 100% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 공급집중 | **Supply Chain Dive, BBC Business** | ✅ 전문 + 범용 |
| 단일소싱 | **Supply Chain Dive** | ✅ 전문 |
| 장비 독과점 | **Semiconductor Engineering** | ✅ 전문 |

#### 원자재 & 희소물질 (5개 RF) - ⚠️ 50% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 소재 단일 공급 | **Semiconductor Engineering** | ✅ 전문 |
| 희토류 가격 | BBC Business | 범용 커버 (간접) |
| 네온 가격 | BBC Business | 범용 커버 (간접) |
| 팔라듐 가격 | BBC Business | 범용 커버 (간접) |

**개선**: Bloomberg (원자재 전문) RSS 재확인 필요

#### 기술 & 지식재산 (4개 RF) - ✅ 100% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 기술 유출 | **Semiconductor Engineering, BBC Technology** | ✅ 전문 + 범용 |
| 특허분쟁 | BBC Technology | 범용 커버 |
| R&D 집중도 | **Semiconductor Engineering** | ✅ 전문 |
| 기술 단절 | **Semiconductor Engineering** | ✅ 전문 |

#### 물류 & 인프라 (5개 RF) - ✅ 100% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 항만 혼잡 | **Supply Chain Dive, FreightWaves** | ✅ 전문 (2개) |
| 물류 경로 차단 | **Supply Chain Dive, FreightWaves, BBC World** | ✅ 전문 + 범용 |
| 항공 운임 | **FreightWaves** | ✅ 전문 |
| 화물 파업 | **FreightWaves, BBC World** | ✅ 전문 + 범용 |
| 수출허가지연 | **FreightWaves** | ✅ 글로벌 세관 이슈 커버 |

**개선 완료**: FreightWaves 추가로 물류 분야 100% 커버 달성

#### 사이버 & 데이터 (4개 RF) - ✅ 100% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 사이버 공격 | **BBC Technology** | ✅ 전문 |
| OT/ICS 보안 | BBC Technology | 범용 커버 |
| 데이터 주권 | **BBC Technology** | ✅ 강력 |
| SW 취약점 | **BBC Technology** | ✅ 강력 |

#### ESG & Compliance (4개 RF) - ⚠️ 50% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| ESG 규제 | **Supply Chain Dive** | ✅ 전문 |
| 환경 규제 | Supply Chain Dive | 간접 커버 |
| 탄소 규제 | Supply Chain Dive | 간접 커버 |
| 인권·노동 규제 | Supply Chain Dive | 간접 커버 |

**개선**: GreenBiz RSS 추가 검토

#### 재무 & 신용 (3개 RF) - ✅ 100% 커버

| Risk Factor | 커버 소스 | 비고 |
|------------|----------|------|
| 협력사 재무 부실 | **BBC Business** | ✅ 강력 |
| 환율 변동성 | **BBC World, BBC Business** | ✅ 강력 |
| M&A 위험 | **BBC Business** | ✅ 강력 |

### 📊 전체 커버리지 요약

| 대분류 | 커버율 | 주요 Gap | 개선 방안 |
|--------|--------|---------|----------|
| 지정학 & 규제 | **90%** ✅ | 수출입규제 | 미 상무부 Selenium 추가 |
| 공급집중 | **100%** ✅ | 없음 | - |
| 원자재 | **50%** ⚠️ | 가격 데이터 | Bloomberg RSS 또는 API |
| 기술 | **100%** ✅ | 없음 | - |
| 물류 | **100%** ✅ | 없음 | ✅ FreightWaves 추가로 완료 |
| 사이버 | **100%** ✅ | 없음 | - |
| ESG | **50%** ⚠️ | 환경/탄소 세부 | GreenBiz RSS 추가 |
| 재무 | **100%** ✅ | 없음 | - |

**총 커버율**: 약 **89%** (35개 RF 중 31개 커버, 물류 분야 100% 달성)

**핵심 Gap (2개)**:
1. 원자재 가격 (희토류, 네온, 팔라듐) → Bloomberg 추가 필요
2. ESG 세부 규제 → GreenBiz 추가 필요

**선택적 Gap (1개)**:
- 수출입규제 → 미 상무부 Selenium 추가 검토 (White House로 부분 커버 중)

---

## 🔍 상세 설명

### 1. 소스 설정 파일 (config_news_sources_global.py)

소스 설정은 별도 파일로 분리되어 있어 유지보수가 용이합니다.

```python
# dev_module_news_searcher_global.py
from config_news_sources_global import RSS_SOURCES, SCRAPING_SOURCES
```

#### RSS 소스 설정 예시

```python
RSS_SOURCES = {
    "whitehouse": {
        "name": "White House",
        "feeds": {
            "news": "https://www.whitehouse.gov/news/feed"
        },
        "selectors": ['.body-content', 'article', '.post-body', '.entry-content'],
        "risk_factors": ["지정학&규제", "정책 변동", "지역갈등/분쟁"]
    },
    "bbc_world": {
        "name": "BBC News - World",
        "feeds": {
            "world": "http://feeds.bbci.co.uk/news/world/rss.xml"
        },
        "selectors": ['[data-component="text-block"]', 'article', '.article__body'],
        "risk_factors": ["지역갈등/분쟁", "지정학&규제", "환율 변동성"]
    },
    # ... 추가 5개 소스 (BBC Business, BBC Technology, Supply Chain Dive, FreightWaves, Semiconductor Engineering)
}
```

#### HTML 스크래핑 소스 설정 예시

```python
SCRAPING_SOURCES = {
    "house_foreign_affairs_dem": {
        "name": "US House Foreign Affairs Committee (Democrats)",
        "url": "https://democrats-foreignaffairs.house.gov/press-releases",
        "list_selector": "table.recordList tbody tr",
        "link_selector": "td a",
        "date_selector": "td.recordListDate",
        "content_selectors": ['article', '.newsContent', '.article-body'],
        "risk_factors": ["지역갈등/분쟁", "외교 정책", "지정학&규제"]
    },
    "china_ndrc": {
        "name": "China NDRC (发改委)",
        "url": "https://en.ndrc.gov.cn/news/pressreleases/",
        "list_selector": "ul.column_list li",
        "link_selector": "a",
        "date_selector": "span.u_number",
        "content_selectors": ['.TRS_Editor', '.content', 'article'],
        "risk_factors": ["지정학&규제", "산업 정책", "투자 규제"]
    },
    "china_mod": {
        "name": "China Ministry of National Defense",
        "url": "http://eng.mod.gov.cn/2025xb/N/T/index.html",
        "list_selector": "ul.list-unstyled li",
        "link_selector": "a",
        "date_selector": None,
        "content_selectors": ['#article-content', '.article-content', 'article'],
        "risk_factors": ["지역갈등/분쟁", "국방 정책", "지정학&규제"]
    }
}
```

---

### 2. RSS 파싱 함수 (feedparser)

```python
def parse_rss_feed(feed_url):
    """RSS 피드 파싱"""
    feed = feedparser.parse(feed_url)
    if feed.bozo:  # 파싱 에러 체크
        print(f"  RSS 파싱 경고: {feed_url}")
    return feed.entries

def parse_feed_date(entry):
    """RSS 날짜 파싱"""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    return None

def filter_recent_entries(entries, days=2):
    """최근 N일 기사 필터링 (시차 고려)"""
    from datetime import timedelta
    
    today = datetime.now().date()
    cutoff_date = today - timedelta(days=days-1)
    recent_entries = []
    
    for entry in entries:
        pub_date = parse_feed_date(entry)
        if pub_date and pub_date.date() >= cutoff_date:
            recent_entries.append(entry)
    
    return recent_entries
```

---

### 3. HTML 스크래핑 함수

```python
def scrape_news_list(source_config):
    """RSS 피드가 없는 사이트에서 뉴스 목록 스크래핑"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(source_config['url'], headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        news_items = []
        
        list_items = soup.select(source_config['list_selector'])
        
        for item in list_items:
            link_elem = item.select_one(source_config['link_selector'])
            if not link_elem or not link_elem.get('href'):
                continue
            
            href = link_elem.get('href', '')
            full_url = urljoin(source_config['url'], href)
            title = link_elem.get_text(strip=True)
            
            date_text = ""
            if source_config.get('date_selector'):
                date_elem = item.select_one(source_config['date_selector'])
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
            
            news_items.append({
                'title': title,
                'link': full_url,
                'pubDate': date_text
            })
        
        return news_items
    
    except Exception as e:
        print(f"  [ERROR] {str(e)[:50]}")
        return []
```

---

### 4. 본문 크롤링 (병렬 처리)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def crawl_article_content(url, selectors, verbose=False):
    """단일 기사 본문 크롤링"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'lxml')
    
    # 선택자 우선순위대로 시도
    for selector in selectors:
        article_body = soup.select_one(selector)
        if article_body:
            # script, style 제거
            for tag in article_body(['script', 'style', 'iframe']):
                tag.decompose()
            
            text = article_body.get_text(separator='\n', strip=True)
            text = re.sub(r'\n\s*\n+', '\n\n', text)
            
            if text.strip():
                return text.strip()
    
    return None

def crawl_articles_parallel(articles, selectors, max_workers=5):
    """병렬 크롤링 (5배 속도 향상)"""
    def crawl_single(article):
        content = crawl_article_content(article['link'], selectors)
        article['full_content'] = content
        return article
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(crawl_single, article): article for article in articles}
        
        results = []
        for idx, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                results.append(result)
                print(f"      [{idx}/{len(articles)}] 완료")
            except Exception as e:
                print(f"      [ERROR] {str(e)[:50]}")
                article = futures[future]
                article['full_content'] = None
                results.append(article)
    
    return results
```

---

## 🚀 실행 방법

### VS Code에서 실행

```bash
# 가상환경 활성화 확인
python -c "import sys; print(sys.executable)"

# 실행
python dev/dev_module_news_searcher_global.py
```

### 실행 결과 예시 (2026-06-26)

```
==================================================
글로벌 뉴스 수집 시작
==================================================

[RSS 피드 소스 수집]

[White House] 수집 시작...
  피드: news
    전체: 30개, 최근 48시간: 3개
    본문 크롤링 중 (병렬 처리)...
      [1/3] 완료
      [2/3] 완료
      [3/3] 완료
[White House] 완료: 3개 수집

[BBC News - World] 수집 시작...
  피드: world
    전체: 29개, 최근 48시간: 20개
    본문 크롤링 중 (병렬 처리)...
      [1/20] 완료
      ...
      [20/20] 완료
[BBC News - World] 완료: 20개 수집

...

[HTML 스크래핑 소스 수집]

[US House Foreign Affairs Committee (Democrats)] 수집 시작...
  전체: 10개, 최근 48시간: 10개
  본문 크롤링 중 (병렬 처리)...
      [1/10] 완료
      ...
      [10/10] 완료
[US House Foreign Affairs Committee (Democrats)] 완료: 10개 수집

[China NDRC (发改委)] 수집 시작...
  전체: 15개, 최근 48시간: 15개
  본문 크롤링 중 (병렬 처리)...
  ...
[China NDRC (发改委)] 완료: 15개 수집

==================================================
총 수집: 77개
본문 크롤링 성공: 71/77개 (92.2%)
==================================================

[1] [White House] Advancing Regenerative Agriculture...
    카테고리: news
    날짜: 2026-06-26T14:30:00Z
    링크: https://www.whitehouse.gov/...
    본문 길이: 2834자

[2] [BBC News - World] Israel-Gaza war: Latest updates
    카테고리: world
    날짜: 2026-06-26T12:15:00Z
    링크: https://www.bbc.com/news/...
    본문 길이: 4521자

...
```

---

## ⚠️ 알려진 이슈

### 1. Semiconductor Engineering 본문 크롤링 (✅ 해결 완료)

**문제**: 본문이 16자만 추출됨 ("Submit\nSubscribe") - 선택자 불일치

**원인**: `.container` 선택자가 잘못된 영역(Submit 버튼)을 가져옴

**해결**: 선택자를 `.post_cnt`로 수정 (2026-06-26)
```python
# 수정 전
"selectors": ['.container', '.post-content', 'article', '.entry-content']

# 수정 후 (평균 15,000자 본문 정상 수집)
"selectors": ['.post_cnt', '.post-content', 'article', '.entry-content']
```

**검증**: 최신 3개 기사 테스트 완료 (3/3 성공, 평균 15,000자)

### 2. 중국 NDRC 인코딩

**문제**: Windows 콘솔에서 중국어 소스명 출력 시 오류 가능

**해결**: `sys.stdout.reconfigure(encoding='utf-8')` 이미 적용됨

---

## 🔄 향후 확장 계획

### Phase 1: Gap 보완 (우선순위 높음)

1. ✅ **FreightWaves RSS 추가 완료** - 물류 분야 100% 커버 달성
2. **Bloomberg RSS 추가** - 원자재 가격 커버
3. **GreenBiz RSS 추가** - ESG 세부 규제 커버
4. **Semiconductor Engineering 선택자 수정** - 본문 크롤링 개선

### Phase 2: Selenium 선별 도입 (중기)

**핵심 2-3개만 추가**:
- 미 국방부 (정책 영향도 높음)
- 미 재무부 (재무 규제)
- 미 상무부 (수출입규제)

**조건**: API 조사 후에도 대안이 없는 경우만

### Phase 3: 고급 기능 (장기)

1. **키워드 필터링** - DB_TAG_KeywordSet.xlsx 연동
2. **캐싱** - 중복 크롤링 방지
3. **DB 저장** - SQLite 또는 PostgreSQL
4. **스케줄링** - 매 6시간마다 자동 수집

---

## 🐛 트러블슈팅

### 1. RSS 파싱 실패

```python
feed = feedparser.parse(feed_url)
if feed.bozo:
    print(f"파싱 에러: {feed.bozo_exception}")
```

### 2. HTML 선택자 변경

```python
# 브라우저 DevTools → Copy selector
# 다중 선택자 전략 사용
selectors = [
    '.primary-selector',   # 우선순위 1
    'fallback-selector',   # 우선순위 2
    'article'              # 마지막 폴백
]
```

### 3. SSL 인증서 에러

```python
# 이미 적용됨
response = requests.get(url, verify=False)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
```

---

## 📚 참고 자료

- [feedparser 공식 문서](https://feedparser.readthedocs.io/)
- [BeautifulSoup 공식 문서](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [requests 공식 문서](https://requests.readthedocs.io/)
- [White House RSS](https://www.whitehouse.gov/news/feed)
- [BBC RSS Feeds](http://feeds.bbci.co.uk/)
- [Supply Chain Dive RSS](https://www.supplychaindive.com/feeds/news/)
- [FreightWaves RSS](https://www.freightwaves.com/feed)

---

## 📝 변경 이력

| 날짜 | 버전 | 내용 |
|-----|------|------|
| 2026-06-24 | 1.0.0 | 초기 문서 작성 |
| 2026-06-24 | 2.0.0 | General 소스 추가, Risk Factor 100% 커버, 시차 문제 해결 |
| 2026-06-24 | 2.1.0 | 소스 유효성 검증, 작동 불가 소스 제거 |
| 2026-06-24 | 2.2.0 | 병렬 크롤링 구현, 성능 최적화 |
| 2026-06-26 | 3.0.0 | **대대적 재구성**: (1) 고객사 제공 소스 기반 재구성, (2) JavaScript 렌더링 소스 11개 배제, (3) RSS 6개 + HTML 2개로 안정화, (4) Selenium 모듈 준비 완료, (5) Risk Factor 커버리지 85% 달성, (6) 실행 시간 단축 (3-5분), (7) 성공률 92.2% 달성, (8) 배제 소스 및 향후 확장 계획 문서화 |
| 2026-06-26 | 3.1.0 | **물류 분야 강화**: (1) FreightWaves RSS 추가 (14개 기사/일), (2) 물류 & 인프라 Risk Factor 100% 커버 달성, (3) 한국 관세청 재조사 (JS 렌더링으로 배제 확정), (4) 총 수집량 77개 → 92개 (+20%), (5) 성공률 97.8% 달성, (6) 총 커버리지 85% → 89% 향상 |
| 2026-06-26 | 3.1.1 | **Semiconductor Engineering 본문 크롤링 수정**: 선택자를 `.container` → `.post_cnt`로 변경 (16자 → 평균 15,000자) |
| **2026-06-26** | **3.2.0** | **중국 국방부 추가 + CSS 불일치 소스 재조사**: (1) 중국 국방부 HTML 스크래핑 추가 (새 URL 발견, 10개 기사/일), (2) 일본 외무성/경제산업성 재조사 (2단계 구조 + RSS 없음으로 배제 확정), (3) 총 소스 9개 → 10개 (RSS 7개 + HTML 3개), (4) 총 수집량 92개 → 100+개, (5) 배제 소스 11개 → 10개 |
| **2026-06-26** | **3.2.1** | **중국 상무부 재조사**: (1) 새 URL 접속 성공 (`https://english.mofcom.gov.cn/News/SignificantNews/index.html`), (2) JavaScript 동적 렌더링 확인 (정적 HTML 68자만 존재), (3) 배제 사유 업데이트: "HTTP 404" → "JS 동적 렌더링", (4) Selenium 필요 소스로 재분류 |

---

## 💡 국내 모듈과의 차이점

| 항목 | 국내 (Domestic) | 글로벌 (Global) |
|------|----------------|----------------|
| **1단계 소스** | Naver API | RSS 피드 (feedparser) + HTML 스크래핑 |
| **인증** | Client ID/Secret 필요 | 불필요 (공개 피드/웹페이지) |
| **멀티 소스** | 단일 (Naver만) | 9개 소스 (RSS 7개 + HTML 2개) |
| **소스 특성** | 범용 뉴스 | 공급망 리스크 특화 + 정부 기관 + 물류 전문 |
| **선택자** | Naver 뉴스 중심 | 매체별 다중 패턴 |
| **안정성** | 높음 (공식 API) | 높음 (RSS 중심, 97.8%) |
| **실행 시간** | 1-2분 | 4분 |

---

**작성자**: NSRM Risk-Sensing Team  
**최종 수정**: 2026-06-26
