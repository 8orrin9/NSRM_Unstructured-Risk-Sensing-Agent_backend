# 네이버 뉴스 크롤링 모듈 가이드

## 📋 개요

이 문서는 비정형 Risk 센싱 Agent의 국내 뉴스 수집 Sub-Agent 개발을 위한 네이버 뉴스 검색 API 활용 가이드입니다.

**모듈 경로**: `poc-a/dev/dev_module_news-searcher_domestic.py`

---

## 🎯 주요 기능

1. **네이버 뉴스 검색 API 연동** (메타데이터 수집)
2. **오늘 날짜 뉴스 자동 필터링**
3. **최신순 정렬 및 대량 검색 (최대 100건/요청)**
4. **환경변수 기반 인증 관리**
5. **BeautifulSoup 기반 본문 크롤링** (2단계 파이프라인)

---

## 🔧 사전 준비

### 1. 네이버 Open API 신청

1. [네이버 개발자 센터](https://developers.naver.com/apps/#/register) 접속
2. "애플리케이션 등록" 클릭
3. "검색" API 선택
4. Client ID와 Client Secret 발급받기

### 2. 환경 설정

**프로젝트 루트 `.env` 파일 작성** (`poc-a/.env`):

```env
NAVER_CLIENT_ID=your_client_id_here
NAVER_CLIENT_SECRET=your_client_secret_here
```

**주의사항**:
- 등호(`=`) 앞뒤에 공백 없이 작성
- `.env` 파일은 `.gitignore`에 포함되어야 함 (보안)

### 3. 필수 라이브러리 설치

```bash
pip install python-dotenv beautifulsoup4 lxml requests
```

**라이브러리 설명**:
- `python-dotenv`: 환경변수 로드
- `beautifulsoup4`: HTML 파싱
- `lxml`: BeautifulSoup의 고속 파서
- `requests`: HTTP 요청

---

## 📦 코드 구조

### 전체 흐름 (2단계 파이프라인)

```
[1단계: 메타데이터 수집]
1. 환경변수 로드 (.env)
   ↓
2. API 인증 정보 확인
   ↓
3. 검색 파라미터 설정 (키워드, 정렬, 결과수)
   ↓
4. 네이버 API 요청
   ↓
5. JSON 응답 파싱
   ↓
6. 오늘 날짜 뉴스 필터링

[2단계: 본문 크롤링]
7. BeautifulSoup으로 각 뉴스 URL 접속
   ↓
8. HTML 파싱 및 본문 추출
   ↓
9. 결과 출력 (제목 + 본문)
```

---

## 🔍 상세 설명

### 1. Setting (환경변수 로드)

```python
from dotenv import load_dotenv

# 상위 디렉터리의 .env 파일 로드
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

client_id = os.getenv("NAVER_CLIENT_ID")
client_secret = os.getenv("NAVER_CLIENT_SECRET")

# 인증 정보 검증
if not client_id or not client_secret:
    print("Error: NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 환경변수를 설정해주세요.")
    sys.exit(1)
```

**핵심 포인트**:
- `load_dotenv()`는 `.env` 파일의 변수를 환경변수로 로드
- 모듈이 `dev/` 하위에 있으므로 상위 디렉터리(`..`)의 `.env` 참조
- 인증 정보 누락 시 명확한 에러 메시지 출력 후 종료

---

### 2. Parameters & Request (API 요청 설정)

```python
test_word = "딜로이트 컨설팅"   # 검색어(키워드)
encText = urllib.parse.quote(test_word) # URL 인코딩 (한글 처리)
display_range = 100 # 검색 결과수 (min:1, max:100)
sort_order = "date" # 정렬 옵션 (sim:유사도순, date:날짜순)

# API 엔드포인트 구성
url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display={display_range}&sort={sort_order}"

# HTTP 요청 헤더 설정
request = urllib.request.Request(url)
request.add_header("X-Naver-Client-Id", client_id)
request.add_header("X-Naver-Client-Secret", client_secret)
```

**파라미터 설명**:

| 파라미터 | 설명 | 값 범위 | 기본값 |
|---------|------|---------|--------|
| `query` | 검색어 (URL 인코딩 필수) | UTF-8 문자열 | 필수 |
| `display` | 한 번에 가져올 검색 결과 개수 | 1~100 | 10 |
| `start` | 검색 시작 위치 (페이징) | 1~1000 | 1 |
| `sort` | 정렬 방식 | `sim` (유사도), `date` (날짜) | `sim` |

**주의사항**:
- 네이버 API는 **최대 1000건**까지만 조회 가능 (`start` 제약)
- **날짜 필터링 파라미터는 제공되지 않음** → 후처리 필요

---

### 3. Response & Parsing (응답 처리 및 파싱)

```python
response = urllib.request.urlopen(request)
rescode = response.getcode()

if rescode == 200:
    response_body = response.read()
    data = json.loads(response_body.decode('utf-8'))  # JSON 파싱
    
    items = data.get('items', [])  # 뉴스 기사 리스트
    total = data.get('total', 0)   # 전체 검색 결과 수
```

**응답 JSON 구조**:

```json
{
  "lastBuildDate": "Wed, 24 Jun 2026 15:44:33 +0900",
  "total": 21705,
  "start": 1,
  "display": 10,
  "items": [
    {
      "title": "KT의 팔란티어 사업, '업무 파트너' AI 에이전트 시대로",
      "originallink": "https://www.thelec.kr/news/articleView.html?idxno=58545",
      "link": "https://www.thelec.kr/news/articleView.html?idxno=58545",
      "description": "그는 24일 '<b>딜로이트</b> 커넥트 코리아...",
      "pubDate": "Wed, 24 Jun 2026 15:28:00 +0900"
    }
  ]
}
```

**주요 필드**:

| 필드 | 설명 | 타입 |
|-----|------|------|
| `total` | 전체 검색 결과 수 | int |
| `items` | 뉴스 기사 배열 | list |
| `items[].title` | 기사 제목 (검색어 `<b>` 태그 포함) | str |
| `items[].link` | 네이버 뉴스 링크 | str |
| `items[].originallink` | 원본 언론사 링크 | str |
| `items[].description` | 기사 본문 일부 (검색어 강조) | str |
| `items[].pubDate` | 발행 날짜 (RFC 822 형식) | str |

---

### 4. 오늘 날짜 필터링

```python
from datetime import datetime

today = datetime.now().strftime("%Y-%m-%d")  # 예: "2026-06-24"
today_items = []

for item in items:
    pub_date = item.get('pubDate', '')
    # pubDate 형식: "Wed, 24 Jun 2026 15:28:00 +0900"
    
    try:
        # RFC 822 형식 날짜 파싱
        date_obj = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
        item_date = date_obj.strftime("%Y-%m-%d")
        
        if item_date == today:
            today_items.append(item)
    except:
        pass  # 날짜 파싱 실패 시 무시
```

**왜 필터링이 필요한가?**
- 네이버 뉴스 검색 API는 **날짜 범위 지정 파라미터를 제공하지 않음**
- `sort=date`로 최신순 정렬은 가능하나, 특정 날짜만 추출 불가
- **해결책**: 많은 결과를 받아온 후 Python에서 날짜 필터링

**날짜 형식 변환**:
```
API 응답:  "Wed, 24 Jun 2026 15:28:00 +0900"  (RFC 822)
           ↓ strptime 파싱
Python:    datetime(2026, 6, 24, 15, 28, 0, tzinfo=...)
           ↓ strftime 변환
비교용:    "2026-06-24"
```

---

### 5. 본문 크롤링 (BeautifulSoup)

```python
import requests
from bs4 import BeautifulSoup

def crawl_article_content(url):
    """단일 기사 URL의 본문을 크롤링"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # verify=False: 회사 인증서 문제 우회
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    soup = BeautifulSoup(response.text, 'lxml')
    
    # 네이버 뉴스 본문 선택자 (여러 패턴 시도)
    article_body = soup.select_one('#dic_area')  # 패턴 1: 네이버 뉴스 (가장 일반적)
    if not article_body:
        article_body = soup.select_one('#articeBody')  # 패턴 2: 구 네이버 뉴스
    if not article_body:
        article_body = soup.select_one('article')  # 패턴 3: 일반 article 태그
    if not article_body:
        article_body = soup.select_one('.article_body, .news_article')  # 패턴 4: 클래스명
    
    if article_body:
        # script, style 태그 제거
        for tag in article_body(['script', 'style', 'iframe', 'noscript']):
            tag.decompose()
        
        text = article_body.get_text(separator='\n', strip=True)
        # 연속된 공백/줄바꿈 정리
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
    
    return None
```

**핵심 포인트**:
- **User-Agent 설정**: 봇 차단 우회
- **verify=False**: 회사 네트워크의 자체 서명 인증서 문제 해결
- **다중 선택자**: 네이버 뉴스, 원본 언론사 등 다양한 HTML 구조 대응
- **노이즈 제거**: `script`, `style` 등 불필요한 태그 삭제
- **텍스트 정제**: 연속된 공백/줄바꿈 정리

**네이버 뉴스 선택자 패턴**:
| 선택자 | 적용 사이트 | 우선순위 |
|--------|------------|---------|
| `#dic_area` | 네이버 뉴스 (현재) | 1 |
| `#articeBody` | 네이버 뉴스 (구버전) | 2 |
| `article` | 일반 뉴스 사이트 | 3 |
| `.article_body`, `.news_article` | 기타 언론사 | 4 |

---

## 🚀 실행 방법

### VS Code에서 실행

1. **가상환경 활성화 확인**:
   ```bash
   # 터미널에서 확인 (.venv가 활성화되어야 함)
   python -c "import sys; print(sys.executable)"
   # 출력: .../.venv/Scripts/python.exe
   ```

2. **Python 인터프리터 선택**:
   - `Ctrl + Shift + P` → "Python: Select Interpreter"
   - `.venv (Python 3.11.x)` 선택

3. **실행**:
   ```bash
   # 일반 실행
   python dev/dev_module_news-searcher_domestic.py
   
   # 또는 디버거 (F5)
   ```

**실행 결과 예시**:
```
총 검색 결과: 21705개
현재 페이지 결과: 100개
오늘(2026-06-24) 발행 뉴스: 15개
==================================================

본문 크롤링 시작...
  [1/15] 크롤링 중: https://n.news.naver.com/article/138/000...
  [2/15] 크롤링 중: https://n.news.naver.com/article/011/000...
  ...
본문 크롤링 완료: 14/15개 성공
==================================================

[1] KT의 팔란티어 사업, '업무 파트너' AI 에이전트 시대로
    날짜: Wed, 24 Jun 2026 15:28:00 +0900
    링크: https://www.thelec.kr/news/articleView.html?idxno=58545
    본문 미리보기: KT가 팔란티어와 협력해 국내 AI 에이전트 시장을 개척한다. 딜로이트 컨설팅 관계자는 "AI 에이전트는 단순 업무 자동화를 넘어...
    본문 길이: 1523자
```

---

## 🔄 확장 가능성

### 1. 페이징 구현 (더 많은 뉴스 수집)

```python
def fetch_all_today_news(keyword, max_results=1000):
    """오늘 날짜 뉴스 전체 수집 (페이징)"""
    all_items = []
    display = 100  # 한 번에 100개씩
    
    for start in range(1, max_results, display):
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display={display}&start={start}&sort=date"
        # ... (API 요청 코드)
        all_items.extend(items)
        
        # 오늘 날짜가 아닌 뉴스가 나오면 중단
        if not has_today_news(items):
            break
    
    return filter_today(all_items)
```

### 2. 멀티 키워드 검색

```python
keywords = ["딜로이트 컨설팅", "맥킨지 컨설팅", "BCG"]

for keyword in keywords:
    news_items = search_news(keyword)
    # ... (처리)
```

### 3. 데이터베이스 저장

```python
import sqlite3

def save_to_db(news_items):
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY,
            title TEXT,
            link TEXT UNIQUE,
            description TEXT,
            pub_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    for item in news_items:
        cursor.execute('''
            INSERT OR IGNORE INTO news (title, link, description, pub_date)
            VALUES (?, ?, ?, ?)
        ''', (item['title'], item['link'], item['description'], item['pubDate']))
    
    conn.commit()
    conn.close()
```

### 4. Agent 통합 예시 (의사코드)

```python
class NewsCollectorAgent:
    def __init__(self, keywords):
        self.keywords = keywords
        self.client_id = os.getenv("NAVER_CLIENT_ID")
        self.client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    def collect_daily_news(self):
        """오늘 뉴스 수집 (모든 키워드)"""
        all_news = []
        
        for keyword in self.keywords:
            news = self._search_naver_news(keyword)
            today_news = self._filter_today(news)
            all_news.extend(today_news)
        
        return self._deduplicate(all_news)
    
    def _search_naver_news(self, keyword):
        # dev_module_news-searcher.py 로직 활용
        pass
    
    def _filter_today(self, news_items):
        # 오늘 날짜 필터링 로직
        pass
    
    def _deduplicate(self, news_items):
        # 중복 제거 (같은 기사가 여러 키워드에서 검색될 수 있음)
        seen = set()
        unique_news = []
        
        for item in news_items:
            if item['link'] not in seen:
                seen.add(item['link'])
                unique_news.append(item)
        
        return unique_news
```

---

## ⚠️ 제약사항 및 주의사항

### API 제약

| 항목 | 제약 |
|-----|------|
| 호출 제한 | 25,000회/일 |
| 최대 조회 | 1,000건 (`start` 1~1000) |
| 결과 개수 | 100건/요청 (`display` 최대값) |
| 날짜 필터 | ❌ 지원 안 함 (후처리 필요) |

### HTML 태그 처리

API 응답의 `title`과 `description`에는 HTML 태그가 포함됩니다:
- `<b>검색어</b>`: 검색어 강조
- `&quot;`, `&amp;` 등: HTML 엔티티

**정제 방법**:
```python
import re
from html import unescape

def clean_html(text):
    """HTML 태그 및 엔티티 제거"""
    text = re.sub(r'<[^>]+>', '', text)  # 태그 제거
    text = unescape(text)  # 엔티티 디코딩 (&quot; → ")
    return text

# 사용 예
clean_title = clean_html(item['title'])
```

### 인증 정보 보안

**절대 금지**:
```python
# ❌ 코드에 직접 하드코딩
client_id = "en851iXsE7AqLY_zDIIj"
```

**권장**:
```python
# ✅ 환경변수 사용
client_id = os.getenv("NAVER_CLIENT_ID")
```

- `.env` 파일을 `.gitignore`에 추가
- Git에 인증 정보 커밋 금지

---

## 🐛 트러블슈팅

### 1. `ModuleNotFoundError: No module named 'dotenv'`

**원인**: `python-dotenv`가 설치되지 않았거나, 잘못된 가상환경에서 실행

**해결**:
```bash
# 가상환경 활성화 확인
python -c "import sys; print(sys.executable)"

# 올바른 환경에 설치
pip install python-dotenv
```

### 2. `client_id`와 `client_secret`이 `None`

**원인**: `.env` 파일 형식 오류 또는 경로 문제

**체크리스트**:
- [ ] `.env` 파일이 `poc-a/` 루트에 있는가?
- [ ] 등호 앞뒤에 공백이 없는가? (`KEY=value` ✅, `KEY = value` ❌)
- [ ] `load_dotenv()` 경로가 올바른가?

**디버깅**:
```python
print(os.path.join(os.path.dirname(__file__), '..', '.env'))
print(f"CLIENT_ID: {client_id}")
```

### 3. `TypeError: expected string or bytes-like object, got 'NoneType'`

**원인**: HTTP 헤더에 `None` 값 전달 (인증 정보 미설정)

**해결**: 위 **2번** 해결 후 재시도

### 4. 오늘 날짜 뉴스가 0건

**원인**:
- 해당 키워드로 오늘 발행된 뉴스가 실제로 없음
- `display_range`가 너무 작아서 오늘 뉴스가 포함되지 않음

**해결**:
```python
display_range = 100  # 최대값으로 설정
```

### 5. 본문 크롤링 실패 (full_content가 None)

**원인**:
- 네이버 뉴스가 아닌 외부 언론사 사이트의 HTML 구조가 다름
- 사이트의 봇 차단
- 타임아웃 (응답 느린 사이트)

**해결**:
```python
# 1. 선택자 추가 (특정 언론사용)
article_body = soup.select_one('.article-content, #main-content')

# 2. 타임아웃 늘리기
response = requests.get(url, headers=headers, verify=False, timeout=30)

# 3. 실패한 URL 로그 확인
if not content:
    print(f"실패한 URL: {url}")
```

### 6. SSL 인증서 에러 (회사 네트워크)

**원인**: 회사 방화벽의 자체 서명 인증서

**해결**: 이미 코드에 `verify=False`로 적용됨
```python
response = requests.get(url, headers=headers, verify=False)
```

**경고 메시지 무시**:
```python
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
```

---

## 📚 참고 자료

- [네이버 뉴스 검색 API 문서](https://developers.naver.com/docs/serviceapi/search/news/news.md)
- [네이버 개발자 센터](https://developers.naver.com/)
- [python-dotenv 문서](https://pypi.org/project/python-dotenv/)
- [BeautifulSoup 공식 문서](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [requests 공식 문서](https://requests.readthedocs.io/)

---

## 📝 변경 이력

| 날짜 | 버전 | 내용 |
|-----|------|------|
| 2026-06-24 | 1.0.0 | 초기 문서 작성 (1단계: Naver API만) |
| 2026-06-24 | 2.0.0 | **2단계 파이프라인 추가**: BeautifulSoup 기반 본문 크롤링, crawl4ai → BeautifulSoup 전환 (회사 네트워크 인증서 문제 해결) |

---

## 💡 추가 개선 아이디어

### 1. 병렬 크롤링으로 속도 개선
현재는 순차 크롤링이지만, `concurrent.futures`로 병렬화 가능:

```python
from concurrent.futures import ThreadPoolExecutor

def crawl_all_articles_parallel(news_items, max_workers=5):
    """병렬 크롤링 (속도 5배 향상)"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        urls = [item.get('link', '') for item in news_items]
        contents = list(executor.map(crawl_article_content, urls))
        
        for item, content in zip(news_items, contents):
            item['full_content'] = content
    
    return news_items
```

### 2. 크롤링 실패 재시도
일시적 네트워크 오류 대응:

```python
import time

def crawl_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            return crawl_article_content(url)
        except:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 지수 백오프
            else:
                return None
```

### 3. 캐싱으로 중복 크롤링 방지
같은 URL을 다시 크롤링하지 않도록:

```python
import hashlib
import json
from pathlib import Path

CACHE_DIR = Path('cache/')
CACHE_DIR.mkdir(exist_ok=True)

def get_cached_content(url):
    """캐시에서 본문 가져오기"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{url_hash}.json"
    
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)['content']
    return None

def save_to_cache(url, content):
    """본문 캐시에 저장"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{url_hash}.json"
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({'url': url, 'content': content}, f, ensure_ascii=False)
```

---

**작성자**: NSRM Risk-Sensing Team  
**최종 수정**: 2026-06-24
