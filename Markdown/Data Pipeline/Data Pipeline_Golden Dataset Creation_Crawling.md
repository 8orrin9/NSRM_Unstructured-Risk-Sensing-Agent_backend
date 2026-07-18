# Data Pipeline - Golden Dataset Creation (News Crawling)

> 평가용 Golden Dataset 생성을 위한 뉴스 수집 파이프라인 문서

**작성일**: 2026-07-01  
**목적**: 뉴스 분석 Agent 성능 평가용 실제 뉴스 데이터 수집

---

## 1. 개요

### 1.1 배경

뉴스 분석 Agent 개발 완료 후, 실제 성능을 평가하기 위해서는 **Golden Dataset**(정답이 레이블링된 평가용 데이터셋)이 필요합니다. 이 문서는 34개 글로벌 뉴스 소스에서 최근 뉴스를 자동으로 수집하는 파이프라인을 설명합니다.

### 1.2 수집 소스

**총 34개 글로벌 뉴스 소스**:
- **미국** (7개): 백악관, 국무부, 재무부, 상무부, 국방부, CSIS, AP News, CNN
- **중국** (6개): NDRC, MOFCOM, MOD, MIIT(2), Global Times, SCMP
- **일본** (3개): MOFA, METI, JETRO
- **유럽** (2개): 유럽 의회, EU 집행위원회
- **기타** (16개): Reuters, CNBC, Edelman, Zhong Lun, OECD, KOTRA 등

### 1.3 수집 방식

| 방식 | 소스 개수 | 특징 | 예상 성공률 |
|------|----------|------|-------------|
| **RSS** | 12개 | 가장 안정적이고 빠름 | 95%+ |
| **HTML 스크래핑** | 20개 | CSS 선택자 기반 추출 | 70-80% |
| **Selenium** | 2개 | 동적 렌더링 (현재 스킵) | N/A |

---

## 2. RSS 피드 분석 결과

### 2.1 RSS 지원 소스 (12개)

| # | 소스 | RSS URL | 타입 |
|---|------|---------|------|
| 1 | 백악관 | https://www.whitehouse.gov/feed/ | RSS 2.0 |
| 2 | 미 상무부 | https://www.commerce.gov/feeds/latest-news | RSS 2.0 |
| 4 | 미 국무부 | https://www.state.gov/feeds/rss/latest-news/ | RSS 2.0 |
| 5 | 미 재무부 | https://home.treasury.gov/feeds/rss/latest-news | RSS 2.0 |
| 7 | CSIS | https://www.csis.org/rss | RSS 2.0 |
| 8 | AP News | https://apnews.com/hub/ap-top-news | RSS 2.0 |
| 9 | CNN | http://feeds.cnn.com/rss/cnn_topstories.rss | RSS 2.0 |
| 10 | Reuters | https://www.reuters.com/news/archivedate/ | RSS 2.0 |
| 11 | CNBC | https://www.cnbc.com/id/100003114/device/rss/rss.html | RSS 2.0 |
| 27 | 유럽 의회 | https://www.europarl.europa.eu/news/en/rss.html | RSS 2.0 |
| 33 | FinTech Global | https://fintech.global/category/fintech-news/feed/ | RSS 2.0 |
| 34 | OECD | https://www.oecd.org/rss/ | RSS 2.0 |

### 2.2 지역별 RSS 지원률

| 지역/기관 유형 | RSS 지원 | 총계 | 지원률 |
|---------------|----------|------|--------|
| 미국 뉴스 매체 | 5 | 5 | **100%** |
| 미국 정부 기관 | 4 | 6 | **66.7%** |
| 유럽 정부/기관 | 1 | 2 | **50.0%** |
| 기타 (법률/컨설팅) | 2 | 6 | **33.3%** |
| 소셜 미디어 | 0 | 2 | **0%** |
| 일본 정부/기관 | 0 | 5 | **0%** |
| 중국 정부/기관 | 0 | 8 | **0%** |

**주요 발견**:
- 미국 뉴스 매체는 100% RSS 지원
- 아시아 정부 기관은 RSS 미지원 (HTML 스크래핑 필요)
- 소셜 미디어는 RSS 미지원 (API 또는 Selenium 필요)

### 2.3 RSS 분석 원본 데이터

**파일**: `data/NEWS/RSS_Feed_Analysis.csv`

34개 소스별 RSS URL, 지원 여부, 타입이 정리되어 있습니다.

---

## 3. 크롤링 파이프라인 아키텍처

### 3.1 디렉터리 구조

```
poc-a/
├── dev/
│   └── Evaluation_Golden Dataset Creation_Crawling/
│       ├── __init__.py
│       ├── README.md
│       ├── config_sources.py          # 34개 소스 설정
│       ├── news_collector.py          # 크롤링 메인 로직
│       ├── save_results.py            # 결과 저장 및 검증
│       └── run_collection.py          # 실행 스크립트
├── data/
│   └── NEWS/
│       ├── crawled/
│       │   ├── golden_dataset_news.json      # 수집 결과
│       │   └── validation_report.json        # 검증 리포트
│       └── RSS_Feed_Analysis.csv             # RSS 분석 결과
└── Markdown/
    └── Data Pipeline_Golden Dataset Creation_Crawling.md  # 이 문서
```

### 3.2 모듈 구성

#### config_sources.py

34개 소스를 RSS, HTML 스크래핑, Selenium 방식으로 분류합니다.

```python
RSS_SOURCES = {
    "whitehouse": {
        "name": "백악관",
        "rss_url": "https://www.whitehouse.gov/feed/",
        "method": "rss",
        "type": "RSS 2.0"
    },
    # ... 11개 더
}

SCRAPING_SOURCES = {
    "ndrc_china": {
        "name": "중 국가발전개혁위원회",
        "url": "https://en.ndrc.gov.cn/news/pressreleases/",
        "method": "beautifulsoup",
        "selectors": {
            "list": ".TRS_Editor li, article",
            "title": "h1, .title",
            "link": "a",
            "content": ".TRS_Editor, .content, article"
        }
    },
    # ... 19개 더
}
```

#### news_collector.py

`NewsCollector` 클래스가 모든 크롤링 로직을 처리합니다.

**주요 메서드**:
- `collect_all_rss()`: RSS 소스 수집
- `collect_all_scraping()`: HTML 스크래핑 소스 수집
- `collect_all_selenium()`: Selenium 소스 수집 (현재 스킵)

#### save_results.py

`ResultSaver` 클래스가 결과 저장 및 검증을 처리합니다.

**주요 메서드**:
- `save_json()`: JSON 파일 저장
- `validate_results()`: 데이터 검증
- `print_report()`: 검증 리포트 출력

#### run_collection.py

커맨드라인에서 실행 가능한 메인 스크립트입니다.

**옵션**:
- `--limit N`: 소스당 N개 수집 (기본 5)
- `--rss-only`: RSS 소스만 수집
- `--quiet`: 상세 로그 숨김
- `--filename`: 결과 파일명 지정

---

## 4. 실행 방법

### 4.1 환경 준비

```bash
# 1. poc-a 디렉터리로 이동
cd "C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a"

# 2. 가상 환경 활성화
.venv\Scripts\activate

# 3. 의존성 확인
pip list | findstr "requests beautifulsoup4 feedparser"
```

### 4.2 기본 실행 (전체 수집)

```bash
python "dev/Evaluation_Golden Dataset Creation_Crawling/run_collection.py"
```

**예상 결과**:
- RSS 12개 소스: 약 60개 뉴스 (1-2분)
- HTML 20개 소스: 약 75개 뉴스 (5-7분)
- 총 실행 시간: 약 8-12분

### 4.3 RSS 소스만 수집 (빠른 테스트)

```bash
python "dev/Evaluation_Golden Dataset Creation_Crawling/run_collection.py" --rss-only
```

**예상 결과**:
- RSS 12개 소스: 약 60개 뉴스
- 실행 시간: 약 1-2분

### 4.4 소스당 2개만 수집 (테스트용)

```bash
python "dev/Evaluation_Golden Dataset Creation_Crawling/run_collection.py" --limit 2
```

---

## 5. 출력 데이터 구조

### 5.1 golden_dataset_news.json

```json
{
  "collection_date": "2026-07-01T15:30:00Z",
  "sources": [
    {
      "source_name": "백악관",
      "source_url": "https://www.whitehouse.gov/feed/",
      "method": "rss",
      "articles": [
        {
          "title": "President Biden Announces...",
          "url": "https://www.whitehouse.gov/...",
          "published_date": "2026-07-01T10:00:00",
          "content": "Full article text here...",
          "summary": "Article summary...",
          "extraction_status": "success"
        }
        // ... 4개 더 (총 5개)
      ],
      "article_count": 5
    }
    // ... 25-30개 소스
  ],
  "failed_sources": [
    {
      "name": "Reuters",
      "url": "https://www.reuters.com/...",
      "method": "rss",
      "reason": "HTTP 401 Unauthorized"
    }
    // ... 실패한 소스들
  ],
  "statistics": {
    "total_sources": 34,
    "successful_sources": 27,
    "failed_sources": 7,
    "total_articles": 135
  }
}
```

### 5.2 validation_report.json

```json
{
  "validation_date": "2026-07-01T15:35:00Z",
  "total_sources": 34,
  "successful_sources": 27,
  "failed_sources": 7,
  "total_articles": 135,
  "success_rate": 79.4,
  "issue_count": 12,
  "issues": [
    "백악관 - 기사 3: 본문 크롤링 실패",
    "NDRC - 기사 1: URL 누락",
    // ... 기타 이슈
  ]
}
```

---

## 6. 크롤링 전략 상세

### 6.1 RSS 우선 전략

RSS 피드는 HTML 스크래핑보다 **안정적이고 빠르며 구조화**되어 있습니다.

**장점**:
- 파싱 속도 빠름 (feedparser 라이브러리)
- 사이트 구조 변경에 영향 받지 않음
- 날짜, 제목, 링크, 요약이 표준화됨

**단점**:
- 본문이 포함되지 않은 경우 많음 → 별도 크롤링 필요

**구현**:
```python
def collect_rss_source(self, source_id, config, limit=5):
    entries = feedparser.parse(config['rss_url']).entries
    recent_entries = entries[:limit]
    
    for entry in recent_entries:
        article = {
            "title": entry.get('title', ''),
            "url": entry.get('link', ''),
            "content": entry.get('content', [{}])[0].get('value', '')
        }
```

### 6.2 HTML 스크래핑 (BeautifulSoup)

RSS를 지원하지 않는 소스는 CSS 선택자로 직접 추출합니다.

**장점**:
- 거의 모든 사이트에 적용 가능
- 본문까지 한 번에 수집 가능

**단점**:
- 사이트 구조 변경 시 선택자 수정 필요
- 속도가 RSS보다 느림

**구현**:
```python
def scrape_news_list(self, url, list_selector):
    response = requests.get(url, headers={'User-Agent': '...'})
    soup = BeautifulSoup(response.text, 'lxml')
    
    list_items = soup.select(list_selector)
    for item in list_items:
        link = item.find('a').get('href')
        title = item.get_text(strip=True)
```

### 6.3 Selenium (동적 렌더링)

JavaScript로 렌더링되는 소셜 미디어는 Selenium이 필요하지만, **현재는 스킵**합니다.

**사유**:
- Truth Social, X/Twitter는 API 제한이 엄격
- Selenium은 실행 시간이 길고 리소스 소모가 큼
- Golden Dataset에는 정부/뉴스 매체 소스만으로도 충분

---

## 7. 성능 최적화

### 7.1 병렬 처리

본문 크롤링은 `ThreadPoolExecutor`로 병렬 처리합니다.

```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(crawl_article, url) for url in urls]
    results = [f.result() for f in as_completed(futures)]
```

**효과**:
- 단일 스레드: 약 20-30분
- 병렬 처리 (5 workers): 약 8-12분

### 7.2 Rate Limiting

과도한 요청으로 IP 차단되지 않도록 워커 수를 5개로 제한합니다.

### 7.3 타임아웃 설정

각 요청은 10초 타임아웃을 설정하여 무한 대기를 방지합니다.

```python
requests.get(url, timeout=10)
```

---

## 8. 에러 처리

### 8.1 접근 불가 사이트

일부 사이트는 HTTP 403/401 오류를 반환합니다.

**대응**:
- `failed_sources`에 기록
- 나머지 소스는 정상 진행

**예시**:
- Reuters: HTTP 401 (인증 필요)
- 일본 외무성: HTTP 403 (지역 차단)

### 8.2 본문 크롤링 실패

CSS 선택자가 맞지 않거나 페이지 구조가 변경된 경우입니다.

**대응**:
- `extraction_status`를 `partial`로 표시
- 제목과 URL은 저장, 본문은 "(본문 크롤링 실패)"

### 8.3 RSS 파싱 오류

RSS 피드가 malformed되거나 비어있는 경우입니다.

**대응**:
- HTML 스크래핑으로 자동 전환 (fallback)
- 실패 시 `failed_sources`에 기록

---

## 9. 검증 방법

### 9.1 자동 검증

`ResultSaver.validate_results()`가 자동으로 검증합니다.

**검증 항목**:
- 필수 필드 존재 여부 (title, url, content)
- 본문 크롤링 성공 여부
- 소스별 기사 개수

### 9.2 수동 검증

Golden Dataset은 최종적으로 **수동 레이블링**이 필요합니다.

**절차**:
1. `golden_dataset_news.json` 열기
2. 각 기사를 읽고 리스크 태그 레이블링
3. 레이블링된 데이터를 Agent 평가에 사용

---

## 10. 문제 해결 가이드

### 10.1 ImportError: No module named 'feedparser'

```bash
pip install feedparser
```

### 10.2 SSL 인증서 오류

스크립트에서 자동으로 SSL 검증을 비활성화합니다 (`verify=False`).

### 10.3 한글 깨짐

```python
sys.stdout.reconfigure(encoding='utf-8')
```
이미 스크립트에 포함되어 있습니다.

### 10.4 특정 소스만 수집하고 싶을 때

`config_sources.py`에서 해당 소스만 활성화합니다.

```python
RSS_SOURCES = {
    "whitehouse": {...},  # 이것만 남기고 나머지 주석 처리
}
```

---

## 11. 다음 단계

### 11.1 Agent 개발 완료 후

1. 이 크롤링 스크립트로 최신 뉴스 수집
2. 수집된 뉴스를 Agent가 분석
3. Agent의 분석 결과를 수동 검증
4. 정확도, 재현율, F1 점수 계산

### 11.2 정기 수집 자동화

Golden Dataset은 주기적으로 업데이트가 필요할 수 있습니다.

**방법**:
- Windows 작업 스케줄러 사용
- 매주 월요일 오전 9시 실행
- 결과를 날짜별 폴더에 저장

```bash
python run_collection.py --filename "golden_dataset_2026_07_01.json"
```

### 11.3 RSS 모니터링 우선

RSS 소스(12개)는 가장 효율적이므로 우선 모니터링합니다.

---

## 12. 참고 자료

### 12.1 관련 문서

- **기존 크롤링 모듈**: `dev/dev_module_news_searcher_global.py`
- **RSS 분석 결과**: `data/NEWS/RSS_Feed_Analysis.csv`
- **프로젝트 가이드라인**: `CLAUDE.md`

### 12.2 기술 스택

- **Python**: 3.11.9
- **RSS 파싱**: feedparser
- **HTML 파싱**: BeautifulSoup4 + lxml
- **HTTP 요청**: requests
- **병렬 처리**: concurrent.futures

### 12.3 버전 히스토리

- **v0.1.0** (2026-07-01): 초기 버전
  - RSS 12개 소스 지원
  - HTML 스크래핑 20개 소스 지원
  - Selenium 2개 소스 스킵

---

## 부록: 전체 소스 목록

### A. RSS 지원 (12개)

1. 백악관
2. 미 상무부
3. 미 국무부
4. 미 재무부
5. CSIS
6. AP News
7. CNN
8. Reuters
9. CNBC
10. 유럽 의회
11. FinTech Global
12. OECD

### B. HTML 스크래핑 (20개)

1. 미 국방부
2. 미 하원 외교위원회
3. 일 외무성 (MOFA)
4. 일 경제산업성 (METI)
5. 일본무역진흥기구 (JETRO)
6. Edelman Global Advisory (1)
7. Edelman Global Advisory (2)
8. 중 국가발전개혁위원회 (NDRC)
9. 중 상무부 (MOFCOM)
10. 중 국방부 (MOD)
11. 중 공업정보화부 (MIIT) - 뉴스
12. 중 공업정보화부 (MIIT) - 산업
13. Zhong Lun Law Firm
14. Global Times
15. South China Morning Post (SCMP)
16. 유럽 연합 집행위원회 (EC)
17. Bizpando
18. Osborne Clarke (Law Firm)
19. KOTRA
20. Allianz Commercial

### C. Selenium (2개, 스킵)

1. Truth Social
2. X (Twitter) - Donald Trump

---

**문서 끝**
