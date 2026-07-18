# 공급망 Risk 판단 Agent 개발용 Golden Dataset 생성 가이드

## 1. 개요

### 1.1 목적

공급망 Risk 판단 Agent 개발 과정에서 활용할 **정답 뉴스 데이터(Golden Dataset)**를 생성하는 방법론과 프로세스를 정의합니다. 이 데이터는 다음 목적으로 사용됩니다:

- **Agent 개발 단계**: 각 모듈(뉴스 수집, 태그 매핑, DB Search, Risk 평가)의 기능 검증
- **평가 단계**: Agent 성능 평가를 위한 Ground Truth 제공
- **디버깅**: 파이프라인 각 단계의 문제점 진단 및 개선

### 1.2 Golden Dataset이란?

Golden Dataset은 다음 조건을 만족하는 "정답" 데이터셋입니다:

1. **정합성**: 실제 공급망 DB의 협력사/자재/소재 데이터와 일치
2. **현실성**: 실제 산업 뉴스와 유사한 구조와 톤
3. **메타데이터**: 예상 태그, 예상 DB 조회 결과, Risk 카테고리 포함
4. **커버리지**: 9개 Risk 카테고리 전체 커버
5. **태그 정확성**: 실제 태그 데이터(엑셀)에 존재하는 태그 ID만 사용

### 1.3 Agent 파이프라인 개요

```
1. 뉴스 수집 모듈
   - 뉴스에서 키워드 추출
   - 뉴스 요약 생성
   - False Positive 필터링

2. 태그 매핑 모듈
   - 태그와 키워드 매핑 (정확 매칭 + 유사도 검색)
   - 매핑 실패 시 신규 태그 편입 여부 판단 (HITL)

3. DB Search 모듈
   - Risk 시나리오 생성
   - 공급망 Ontology 레이어 조회
   - Text-to-SQL 기반 DB 조회

4. Risk 평가 모듈
   - Risk 여부 평가
   - 발현 시점 진단
```

---

## 2. 데이터 구조

### 2.1 뉴스 JSON 스키마

```json
{
  "news_id": "NEWS_001",
  "title": "미국, 중국 반도체 장비 수출 규제 추가 강화",
  "content": "6월 15일, 미국 상무부는 중국에 대한 반도체 제조 장비 수출 규제를 추가로 강화한다고 발표했다...",
  "source": "생성 (테스트용)",
  "published_date": "2026-06-15",
  "expected_tags": ["SITE_CN", "EVT_ENTITY_LIST"],
  "expected_db_results": {
    "affected_sites": ["S00018", "S00022", "S00035"],
    "affected_suppliers": ["JP0001", "JP0003", "TW0003"],
    "risk_level": "높음",
    "impact_timeframe": "중기",
    "risk_category": "지정학 & 규제"
  }
}
```

### 2.2 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `news_id` | string | ✓ | 뉴스 고유 ID (예: NEWS_001) |
| `title` | string | ✓ | 뉴스 제목 |
| `content` | string | ✓ | 뉴스 본문 (300-800자 권장) |
| `source` | string | ✓ | 뉴스 출처 (생성 데이터는 "생성 (테스트용)") |
| `published_date` | string | ✓ | 발행일자 (YYYY-MM-DD 형식) |
| `expected_tags` | array | ✓ | 예상 태그 ID 리스트 |
| `expected_db_results` | object | ✓ | 예상 DB 조회 결과 |
| `expected_db_results.affected_sites` | array | | 영향받는 생산지 코드 리스트 |
| `expected_db_results.affected_suppliers` | array | | 영향받는 협력사 코드 리스트 |
| `expected_db_results.affected_materials` | array | | 영향받는 자재 코드 리스트 |
| `expected_db_results.affected_raw_materials` | array | | 영향받는 소재 코드 리스트 |
| `expected_db_results.risk_level` | string | | Risk 레벨 (낮음/중간/높음/매우 높음) |
| `expected_db_results.impact_timeframe` | string | | 영향 발현 시점 (즉각/단기/중기/장기) |
| `expected_db_results.risk_category` | string | ✓ | Risk 카테고리 (8개 중 1개) |

### 2.3 태그 유형

| 태그 유형 | 설명 | 예시 |
|-----------|------|------|
| RAW_MATERIAL | 소재 (원소재) | RAW_SPECIAL_GAS (특수가스) |
| MATERIAL | 자재 (소재를 포함하는 상위 개념) | MAT_PVD_타겟 |
| SUPPLIER | 협력사 (법인 단위) | SUP_KR0001 (한화정밀화학) |
| SITE | 위치 (생산 거점) | SITE_TW (대만), SITE_JP (일본) |
| EVENT | 이벤트/현상 (검색 전략 힌트) | EVT_수출규제, EVT_지진 |

---

## 3. 생성 프로세스

### 3.1 전체 흐름

```
Phase 1: DB 데이터 분석
  ↓
Phase 2: 뉴스 생성
  ↓
Phase 3: 검증
  ↓
Phase 4: 문서화 (본 문서)
```

### 3.2 Phase 1: DB 데이터 분석

**스크립트**: `dev/Evaluation_Golden Dataset Creation/analyze_supply_chain_for_news.py`

**목적**: 실제 DB 데이터를 조회하여 뉴스 생성에 필요한 정보 추출

**출력**: `supply_chain_summary.json`

**주요 기능**:

1. **테이블별 데이터 추출**:
   - SUPPLIER_MASTER: 협력사 목록 (국가별 분류)
   - SITE_MASTER: 생산지 목록 (협력사별, 국가별 분류)
   - MATERIAL_MASTER: 자재 목록 (유형별 분류)
   - RAW_MATERIAL_MASTER: 소재 목록 (유형별 분류)

2. **관계 매핑**:
   - 소재 → 자재 (MATERIAL_RAW_MATERIAL_MAP)
   - 생산지 → 자재 (SITE_MATERIAL_MAP)
   - 협력사 → 생산지 (SUPPLIER_MASTER ← SITE_MASTER)

3. **시나리오 후보 추출**:
   - 지역 리스크: 국가별 주요 생산지 + 협력사
   - 소재 리스크: 소재별 영향받는 자재 + 협력사
   - 협력사 리스크: 협력사별 생산지 + 자재

**실행 방법**:

```bash
cd "dev/Evaluation_Golden Dataset Creation"
python analyze_supply_chain_for_news.py
```

**출력 예시**:

```
=== 분석 요약 ===
협력사: 123개 (국가: 9개)
생산지: 250개 (국가: 10개)
자재: 400개 (유형: 23개)
소재: 114개 (유형: 11개)

시나리오 후보:
  - 지역 리스크: 9개
  - 소재 리스크: 10개
  - 협력사 리스크: 95개
```

### 3.3 Phase 2: 뉴스 생성

**스크립트**: `dev/Evaluation_Golden Dataset Creation/generate_ground_truth_news_v3.py`

**목적**: Phase 1 분석 결과를 기반으로 8개 Risk 카테고리별 현실적인 뉴스 데이터 생성

**출력**: `data/NEWS/ground_truth_news.json`

**주요 변경사항 (v3)**:
- **자연재해 시나리오 완전 제거** (지진, 태풍, 한파 등)
- **8개 Risk 카테고리 기반** 시나리오 생성
- **실제 태그 ID 사용** (엑셀 파일 `DB_TAG_Risk Factor Pool_vF.xlsx`에서 로드)
- **risk_category 필드 추가** (모든 뉴스에 Risk 카테고리 명시)

**주요 기능**:

1. **시나리오 정의 (12-15개)**:
   - **8개 Risk 카테고리별 시나리오** (각 카테고리 최소 1개):
     1. **지정학 & 규제** (2개): 수출규제, Entity List, 무역분쟁
     2. **원자재&희소물질** (2개): 특수가스 공급 차질, 희토류 수출규제
     3. **공급집중&단일소싱** (2개): ASML EUV 독과점, 일본 소재 의존도
     4. **물류&인프라** (1개): 항만 파업, 물류 대란
     5. **기술&지식재산** (1개): 특허 분쟁, ITC 조사
     6. **사이버&데이터** (1개): 랜섬웨어 공격, APT 공격
     7. **재무&신용 Risk** (2개): 협력사 신용등급 하락, M&A
     8. **ESG & Compliance** (1개): 화학물질 유출 사고, 환경규제

2. **뉴스 본문 생성**:
   - 실제 협력사명, 자재명, 생산지명 활용
   - 2024-2026년 실제 유사 사건 참고 (자연재해 제외)
   - 산업 뉴스 톤 및 구조 모방

3. **메타데이터 생성**:
   - `expected_tags`: 엑셀 파일의 실제 태그 ID 사용 (CSV 아님)
   - `expected_db_results`: SQL 실행 결과 (영향받는 협력사/자재/생산지)
   - `risk_category`: 8개 Risk 카테고리 중 1개 명시

**실행 방법**:

```bash
cd "dev/Evaluation_Golden Dataset Creation"
python generate_ground_truth_news_v3.py
```

**생성 시나리오 예시**:

| 시나리오 | 태그 조합 | Risk 카테고리 |
|----------|-----------|-----------|
| 미국 중국 수출규제 | SITE_CN + EVT_ENTITY_LIST | 지정학 & 규제 |
| 중국 희토류 수출규제 | RAW_SEMICONDUCTOR_METAL + SITE_CN + EVT_관세 | 지정학 & 규제 |
| 우크라이나 네온가스 | RAW_SPECIAL_GAS + EVT_항만 | 원자재&희소물질 |
| ASML EUV 납품 지연 | EVT_ASML_EUV | 공급집중&단일소싱 |
| 미국 항만 파업 | SITE_US + EVT_항만 | 물류&인프라 |
| DRAM 특허 분쟁 | EVT_ITC_조사사건 + EVT_특허소송 | 기술&지식재산 |
| 랜섬웨어 공격 | EVT_랜섬웨어 | 사이버&데이터 |
| 협력사 신용등급 하락 | EVT_신용도 | 재무&신용 Risk |
| 화학물질 유출 사고 | EVT_화재안전_사고 | ESG & Compliance |

### 3.4 Phase 3: 검증

**스크립트**: `dev/Evaluation_Golden Dataset Creation/validate_ground_truth_news.py`

**목적**: 생성된 뉴스 데이터의 품질 검증

**출력**: `validation_report.txt`

**검증 항목**:

1. **형식 검증**:
   - 필수 필드 존재 여부 (news_id, title, content, expected_tags, expected_db_results)
   - 날짜 형식 (YYYY-MM-DD)
   - 본문 길이 (300-800자 권장)
   - risk_category 필드 존재 및 유효성

2. **태그 정합성**:
   - `expected_tags`의 모든 태그 ID가 실제 태그 데이터에 존재하는지
   - **중요**: 엑셀 파일(`DB_TAG_Risk Factor Pool_vF.xlsx`)의 태그 ID와 일치 확인

3. **DB 정합성**:
   - `expected_db_results`의 협력사/자재/생산지가 실제 DB에 존재하는지

4. **커버리지 검증**:
   - **8개 Risk 카테고리별 최소 1개 이상** 뉴스 존재 확인
   - 모든 태그 유형이 최소 2회 이상 등장하는지
   - 주요 국가/소재가 골고루 분포하는지

**실행 방법**:

```bash
cd "dev/Evaluation_Golden Dataset Creation"
python validate_ground_truth_news.py
```

**검증 보고서 예시**:

```
[전체 요약]
- 총 뉴스 개수: 7개
- 오류: 0건
- 경고: 0건

[커버리지]
- 태그 유형별 빈도:
  · RAW_MATERIAL: 3회 (OK)
  · MATERIAL: 0회 (부족 - 최소 2회 필요)
  · SUPPLIER: 1회 (부족 - 최소 2회 필요)
  · SITE: 6회 (OK)
  · EVENT: 13회 (OK)

[검증 결과] 통과
```

### 3.5 Phase 4: 문서화

본 문서가 Phase 4의 산출물입니다.

---

## 4. 주요 함수 및 로직

### 4.1 Phase 1: DB 분석

**`analyze_supply_chain_db()` 함수**:

```python
def analyze_supply_chain_db(db_path: str, output_path: str):
    """공급망 DB를 분석하여 뉴스 생성에 필요한 정보를 추출합니다."""
    
    # 1. 테이블별 데이터 추출
    # 2. 관계 매핑 (N:M)
    # 3. 시나리오 후보 추출
    #    - 지역 리스크: 생산지가 3개 이상인 국가
    #    - 소재 리스크: 소재가 2개 이상인 유형
    #    - 협력사 리스크: 생산지가 2개 이상인 협력사
    
    return result
```

**핵심 로직**:

- **국가별 생산지 집계**: `GROUP BY country` → 지역 리스크 시나리오 후보
- **소재 유형별 영향 추적**: RAW_MATERIAL → MATERIAL → SITE → SUPPLIER 경로
- **협력사별 자재 생산**: SUPPLIER → SITE → MATERIAL 경로

### 4.2 Phase 2: 뉴스 생성

**`NewsGenerator` 클래스**:

```python
class NewsGenerator:
    def execute_query(self, scenario_type: str, filters: Dict) -> List[Dict]:
        """DB 조회 (expected_db_results 생성용)"""
        
        if scenario_type == 'region_risk':
            # 특정 국가의 생산지 조회
            # SQL: SELECT s.*, sup.* FROM SITE_MASTER s JOIN SUPPLIER_MASTER sup ...
        
        elif scenario_type == 'raw_material_risk':
            # 특정 소재를 포함하는 자재 및 협력사 조회
            # SQL: SELECT ... FROM RAW_MATERIAL_MASTER → MATERIAL → SUPPLIER
        
        elif scenario_type == 'supplier_risk':
            # 특정 협력사의 생산지 및 자재 조회
            # SQL: SELECT ... FROM SITE_MASTER WHERE supplier_code = ?
        
        return results
```

**시나리오별 뉴스 생성**:

- **`_create_region_risk_scenarios()`**: 대만 지진, 일본 태풍, 미국 한파 등
- **`_create_raw_material_risk_scenarios()`**: 네온가스 부족, 희토류 수출규제, 포토레지스트 화재 등
- **`_create_supplier_risk_scenarios()`**: 협력사 화학사고, 재무악화 등
- **`_create_complex_scenarios()`**: 미·중 기술 갈등, 공급망 재편 등

### 4.3 Phase 3: 검증

**`NewsValidator` 클래스**:

```python
class NewsValidator:
    def validate_format(self):
        """필수 필드, 날짜 형식, 본문 길이 검증"""
    
    def validate_tag_consistency(self):
        """태그 ID가 실제 태그 데이터에 존재하는지 검증"""
    
    def validate_db_consistency(self):
        """협력사/자재/생산지 코드가 실제 DB에 존재하는지 검증"""
    
    def validate_coverage(self):
        """태그 유형별 커버리지 검증 (최소 2회 이상)"""
```

---

## 5. 품질 검증 기준

### 5.1 필수 조건 (Critical)

- ✓ 모든 필수 필드 존재
- ✓ 날짜 형식 정확 (YYYY-MM-DD)
- ✓ `expected_tags`의 태그 ID가 실제 태그 데이터에 존재
- ✓ `expected_db_results`의 코드가 실제 DB에 존재

### 5.2 권장 조건 (Recommended)

- ✓ 본문 길이 300-800자
- ✓ 태그 유형별 최소 2회 이상 등장
- ✓ 주요 국가 (한국, 일본, 중국, 미국) 포함
- ✓ **8개 Risk 카테고리별 최소 1개 이상** 뉴스 포함
- ✓ risk_category 필드가 모든 뉴스에 명시되어 있음
- ✓ 자연재해 관련 시나리오 제외 (지진, 태풍, 한파, 홍수 등)

### 5.3 검증 프로세스

```
1. 자동 검증 (validate_ground_truth_news.py)
   ↓
2. 검증 보고서 확인 (validation_report.txt)
   ↓
3. 오류 수정 (태그 ID, 코드 정합성 등)
   ↓
4. 재검증
   ↓
5. 최종 승인
```

---

## 6. 확장 가능성

### 6.1 추가 뉴스 생성

**방법 1: 스크립트 재실행**

```python
# generate_ground_truth_news.py 수정
# _create_XXX_scenarios() 함수에 시나리오 추가

scenarios.append({
    'news_id': 'NEWS_009',
    'title': '...',
    'content': '...',
    ...
})
```

**방법 2: 시나리오 템플릿 활용**

```python
# 템플릿 정의
SCENARIO_TEMPLATES = {
    'region_risk': {
        'template': '{}에서 {}로 {} 생산 차질',
        'variables': ['country', 'event', 'material']
    },
    ...
}

# 변수 조합으로 자동 생성
```

### 6.2 Agent 평가용 활용

Golden Dataset을 Agent 평가용으로 활용하는 방법:

1. **End-to-End 평가**:
   - 뉴스 입력 → Agent 실행 → 출력 비교
   - `expected_tags` vs 실제 추출 태그 (Precision, Recall)
   - `expected_db_results` vs 실제 DB 조회 결과 (Accuracy)

2. **모듈별 평가**:
   - 뉴스 수집 모듈: 키워드 추출 정확도
   - 태그 매핑 모듈: 태그 매핑 정확도
   - DB Search 모듈: SQL 생성 정확도
   - Risk 평가 모듈: Risk 레벨/발현 시점 일치도

3. **성능 메트릭**:
   ```python
   def evaluate_agent(agent_output, ground_truth):
       # 태그 매핑 정확도
       tag_precision = len(set(agent_output['tags']) & set(ground_truth['expected_tags'])) / len(agent_output['tags'])
       tag_recall = len(set(agent_output['tags']) & set(ground_truth['expected_tags'])) / len(ground_truth['expected_tags'])
       
       # DB 조회 정확도
       db_accuracy = len(set(agent_output['suppliers']) & set(ground_truth['affected_suppliers'])) / len(ground_truth['affected_suppliers'])
       
       return {
           'tag_precision': tag_precision,
           'tag_recall': tag_recall,
           'db_accuracy': db_accuracy
       }
   ```

### 6.3 자동화 파이프라인

**목표**: 뉴스 생성 → 검증 → 저장을 자동화

```python
# auto_generate_golden_dataset.py

def auto_generate(scenario_count: int, min_quality_score: float):
    # 1. DB 분석
    summary = analyze_supply_chain_db()
    
    # 2. 뉴스 생성
    news_list = []
    while len(news_list) < scenario_count:
        news = generate_news_scenario(summary)
        
        # 3. 즉시 검증
        validation_result = validate_news(news)
        
        if validation_result['quality_score'] >= min_quality_score:
            news_list.append(news)
    
    # 4. 저장
    save_golden_dataset(news_list)
    
    return news_list
```

---

## 7. 8개 Risk 카테고리 상세

이 프로젝트에서 다루는 공급망 Risk 유형은 다음 8개 카테고리로 구성됩니다 (자연재해 제외):

### 7.1 지정학 & 규제
- **정의**: 국가 간 무역 분쟁, 수출 규제, 제재, 관세 등 정치·외교적 요인으로 인한 Risk
- **예시 EVENT 태그**: 
  - `EVT_ENTITY_LIST` (Entity List 지정)
  - `EVT_관세` (관세 부과)
  - `EVT_수출통제법` (수출통제)
  - `EVT_무역전쟁` (무역 분쟁)

### 7.2 원자재&희소물질
- **정의**: 특수가스, 반도체금속, 희토류 등 핵심 원자재 공급 부족 또는 가격 급등
- **예시 EVENT 태그**:
  - `EVT_원재료_공급난` (원자재 공급 차질)
  - `EVT_일본_소재_공급난` (일본 소재 공급 부족)
  - `EVT_ASML_EUV` (장비 공급 차질)

### 7.3 공급집중&단일소싱
- **정의**: 특정 지역, 협력사, 소재에 대한 과도한 의존으로 인한 공급망 취약성
- **예시 EVENT 태그**:
  - `EVT_ASML_EUV` (EUV 장비 독과점)
  - `EVT_일본_소재_공급난` (일본 소재 의존도)

### 7.4 물류&인프라
- **정의**: 항만 파업, 물류 대란, 컨테이너 부족 등 물류 인프라 차질
- **예시 EVENT 태그**:
  - `EVT_항만` (항만 파업, 물류 차질)
  - `EVT_운임급등` (해운비 급등)
  - `EVT_컨테이너_부족` (컨테이너 부족)

### 7.5 기술&지식재산
- **정의**: 특허 분쟁, 기술 유출, R&D 리스크 등 지식재산권 관련 Risk
- **예시 EVENT 태그**:
  - `EVT_ITC_조사사건` (ITC 특허 소송)
  - `EVT_특허소송` (특허 분쟁)
  - `EVT_기술유출` (기술 유출)
  - `EVT_제품단종` (제품 단종)

### 7.6 사이버&데이터
- **정의**: 사이버 공격, 랜섬웨어, 데이터 유출 등 사이버 보안 Risk
- **예시 EVENT 태그**:
  - `EVT_랜섬웨어` (랜섬웨어 공격)
  - `EVT_APT_공격` (지능형 지속 공격)
  - `EVT_사이버공격` (사이버 공격)
  - `EVT_OT_공격` (OT/ICS 공격)

### 7.7 재무&신용 Risk
- **정의**: 협력사 재무악화, 부도, 신용등급 하락, M&A 등 재무 건전성 Risk
- **예시 EVENT 태그**:
  - `EVT_재무악화` (재무 악화)
  - `EVT_신용도` (신용등급 하락)
  - `EVT_인수` (M&A, 기업 인수)
  - `EVT_부도위기` (부도 위기)

### 7.8 ESG & Compliance
- **정의**: 환경규제, 화학사고, 컴플라이언스 위반 등 ESG 관련 Risk
- **예시 EVENT 태그**:
  - `EVT_화재안전_사고` (화재, 화학물질 유출 사고)
  - `EVT_REACH` (환경규제)
  - `EVT_ROHS` (환경규제)
  - `EVT_EU_CBAM` (탄소 국경세)
  - `EVT_UFLPA` (강제노동 이슈)

**중요**: 자연재해(지진, 태풍, 한파, 홍수, 산불 등)는 **대상 Risk 범위에 포함되지 않습니다**.

---

## 8. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-07-01 | 초기 문서 작성<br>- 4 Phase 프로세스 정의<br>- 스크립트 3개 작성 (분석, 생성, 검증)<br>- 뉴스 7개 생성 (지역 3개, 소재 2개, 협력사 1개, 복합 1개)<br>- 검증 보고서 생성 |
| 2.0 | 2026-07-01 | **8개 Risk 카테고리 기반으로 전면 개편**<br>- **자연재해 시나리오 완전 제거** (지진, 태풍, 한파 등)<br>- `generate_ground_truth_news_v3.py` 작성 (엑셀 기반 태그 로드)<br>- 뉴스 12개 재생성 (8개 Risk 카테고리별 최소 1개씩)<br>- risk_category 필드 추가<br>- 실제 태그 ID 매핑 (엑셀 파일 기준)<br>- 문서 업데이트 (Risk 카테고리, 시나리오 예시 변경) |

---

## 9. 참고 문서

- **[Data Pipeline_Tag Creation_Docs.md](./Data%20Pipeline_Tag%20Creation_Docs.md)**: 태그 구조 및 생성 방법론
- **[DB_SUPPLY MAP_Docs.md](./DB_SUPPLY%20MAP_Docs.md)**: 공급망 DB 스키마 및 구조
- **[DB_SUPPLY MAP_Ontology_Docs.md](./DB_SUPPLY%20MAP_Ontology_Docs.md)**: 온톨로지 레이어 설계
- **`data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx`**: 실제 태그 데이터 (3_Tag 시트)
- **`data/TAG/risk_categories.csv`**: 8개 Risk 카테고리 정의

---

## 10. 알려진 이슈 및 향후 작업

### 10.1 알려진 이슈
1. **태그 ID 정확성**: 일부 뉴스의 `expected_tags`가 엑셀 파일의 실제 태그 ID와 불일치
   - 원인: v3 스크립트에서 생성한 태그 ID가 엑셀 파일의 실제 태그 ID와 다름
   - 해결 방안: 엑셀 파일의 실제 태그 ID로 수동 매핑 필요

2. **검증 스크립트 참조 파일**: `validate_ground_truth_news.py`가 CSV 파일을 참조하지만, 실제 태그는 엑셀 파일에 존재
   - 원인: CSV 파일과 엑셀 파일의 태그 ID 불일치
   - 해결 방안: 검증 스크립트를 엑셀 기반으로 수정하거나, 엑셀에서 CSV 재생성

### 10.2 향후 작업
1. **태그 ID 매핑 완료**: 모든 뉴스의 `expected_tags`를 엑셀 파일의 실제 태그 ID로 수정
2. **검증 스크립트 수정**: 엑셀 파일 기반 검증으로 전환
3. **커버리지 검증**: 8개 Risk 카테고리별 최소 1개 이상 뉴스 확인
4. **최종 검증 통과**: 모든 검증 항목 통과 확인

---

**작성자**: Claude Code (Sonnet 4.5)  
**최종 수정**: 2026-07-01  
**문서 위치**: `poc-a/Markdown/Data Pipeline_Golden Dataset Creation.md`
