# 가짜 Risk 뉴스 및 그룹화 테스트 뉴스 생성 가이드

## 1. 개요

### 1.1 목적

본 문서는 **삼성전자 반도체 공급망 Risk 판단 Agent**의 성능 검증을 위한 가짜 뉴스 생성 방법론을 설명합니다.

**생성 대상:**
1. **가짜 Risk 뉴스**: Agent가 Risk로 판정할 수 있는 테스트 뉴스 (40개)
2. **가짜 그룹화 테스트 뉴스**: 뉴스 그룹화 기능 검증용 뉴스 (13개)

**활용 목적:**
- Agent 파이프라인 (News Analyzer → Tag Mapper → DB Searcher → Risk Evaluator) 정확도 검증
- 뉴스 그룹화 알고리즘 (방법 1: 직접 공유, 방법 2: hop 연결) 검증
- 실제 Risk 사례 부족 문제 보완

### 1.2 핵심 원칙

1. **현실성**: 실제 뉴스 형식 유지 (제목, 본문, 출처, 발행일)
2. **정합성**: 공급망 DB의 **실제 데이터만** 사용 (협력사, 생산지, 자재, 소재)
3. **검증 가능성**: Agent가 정확히 Risk로 판단할 수 있는 논리적 인과관계 포함
4. **구분 가능성**: `source_type` 필드로 실제 뉴스와 명확히 구분

### 1.3 전제 조건

- 공급망 DB 존재: `data/SUPPLY_CHAIN/supply_chain.db`
  - SUPPLIER_MASTER (협력사 123개)
  - SITE_MASTER (생산지 250개)
  - MATERIAL_MASTER (자재 400개)
  - RAW_MATERIAL_MASTER (소재 114개)
- 기존 뉴스 데이터: `data/Dev_Data/news_data_vF.json`
- Python 환경: sqlite3, json, pathlib, datetime, random

---

## 2. 전체 프로세스

```
Phase 1: Risk 뉴스 생성
  ↓
Phase 2: 그룹화 테스트 뉴스 생성
  ↓
Phase 3: 기존 뉴스와 통합
  ↓
Phase 4: 검증
  ↓
Phase 5: Agent 테스트
```

---

## 3. Phase 1: 가짜 Risk 뉴스 생성

### 3.1 스크립트 개요

**파일**: `dev/Evaluation_Golden Dataset Creation/generate_fake_risk_news.py`

**기능**:
- 8개 Risk 카테고리별 시나리오 템플릿 정의
- 공급망 DB에서 실제 데이터 샘플링
- 시나리오 기반 뉴스 본문 자동 생성

**출력**: `temp/fake_risk_news.json` (40개)

### 3.2 8개 Risk 카테고리 및 시나리오

| Risk 카테고리 | 시나리오 예시 | 핵심 엔티티 |
|--------------|---------------|-------------|
| **지정학&규제** | 미국, 일본 반도체 소재 수출 규제 강화 | 일본(SITE), ArF 포토레지스트(RAW_MATERIAL), 신에쓰화학(SUPPLIER) |
| **원자재&희소물질** | 우크라이나 네온가스 생산 중단 | 네온(RAW_MATERIAL), 우크라이나(SITE) |
| **공급집중&단일소싱** | 일본 모리타화학 생산 중단 | 모리타화학(SUPPLIER), 특정 소재 |
| **물류&인프라** | 싱가포르 항만 파업, 덕산화학 물류 마비 | 싱가포르(SITE), 덕산화학(SUPPLIER) |
| **기술&지식재산** | 한화정밀화학, 미국 ITC 특허 소송 | 한화정밀화학(SUPPLIER), ITC 조사 |
| **사이버&데이터** | 솔루스첨단소재 랜섬웨어 공격 | 솔루스첨단소재(SUPPLIER), 랜섬웨어 |
| **재무&신용** | 텍셀넷컴 신용등급 하락 | 텍셀넷컴(SUPPLIER), 신용등급 |
| **ESG&Compliance** | 간토화학 화학물질 유출 사고 | 간토화학(SUPPLIER), 화학사고 |

**카테고리별 5개씩 생성 = 총 40개**

### 3.3 시나리오 템플릿 구조

```python
{
    "title_template": "{country} 정부, {supplier}에 대한 수출 규제 강화",
    "content_template": """
{date}일, {country} 정부는 {supplier}에 대한 {material} 수출 규제를 추가로 강화한다고 발표했다.

이번 규제는 {country}의 반도체 기술 유출 방지 정책의 일환으로, 삼성전자를 포함한 한국 반도체 업체들이 {material}을(를) 사용하는 생산 공정에 직접적인 영향을 받을 것으로 예상된다.

{supplier}는 {material} 공급에서 높은 시장 점유율을 차지하고 있으며, 이번 규제로 인해 대체 공급처 확보가 시급한 상황이다. 업계는 최소 3-6개월간 공급 차질이 발생할 것으로 전망하고 있다.

삼성전자 관계자는 "공급망 다변화를 적극 추진 중"이라며 "단기적 영향을 최소화하기 위해 재고 확보에 나섰다"고 밝혔다.
""",
    "expected_risk": True,
    "expected_issue_type": "ISSUE"
}
```

**템플릿 변수**:
- `{supplier}`: 공급망 DB의 실제 협력사 이름 (예: "한화정밀화학")
- `{site}`: 실제 생산지 이름 (예: "한화정밀화학 본사")
- `{material}`: 실제 자재 이름 (예: "ArF 포토레지스트")
- `{raw_material}`: 실제 소재 이름 (예: "아르곤")
- `{country}`: 국가 (예: "미국", "중국", "일본", "한국")
- `{date}`: 발행 날짜 (최근 1-2개월 내)

### 3.4 뉴스 데이터 구조

```json
{
  "news_id": "FAKE_RISK_001",
  "title": "미국 정부, 신에쓰화학코리아에 대한 수출 규제 강화",
  "content": "2026년 6월 15일, 미국 정부는...",
  "source": "생성 (테스트용)",
  "published_date": "2026-06-15",
  "source_type": "FAKE_RISK",
  "is_relevant": true,
  "original_language": "korean",
  "_scenario_template": "geopolitical_regulation",
  "_expected_risk": true,
  "_expected_issue_type": "ISSUE",
  "_entities": {
    "supplier": "신에쓰화학코리아",
    "site": "신에쓰화학코리아 Plant 1",
    "material": "ArF 포토레지스트",
    "raw_material": "아르곤",
    "country": "미국"
  }
}
```

**필수 필드**:
- `news_id`: `FAKE_RISK_NNN` 형식 (001부터 순차)
- `source_type`: **"FAKE_RISK"** (실제 뉴스와 구분)
- `is_relevant`: **true** (Agent_1 필터링 통과)
- `_expected_risk`: true (검증용)
- `_expected_issue_type`: "ISSUE" 또는 "SMD"

### 3.5 실행 방법

```bash
cd "C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a"
python "dev/Evaluation_Golden Dataset Creation/generate_fake_risk_news.py"
```

**실행 결과**:
```
============================================================
가짜 Risk 뉴스 생성
============================================================

[1단계] 공급망 DB 데이터 로드
  협력사: 30개
  생산지: 30개
  자재: 30개
  소재: 29개

[2단계] Risk 뉴스 생성
  총 40개 생성

[카테고리별 분포]
  geopolitical_regulation: 5개
  raw_material_scarcity: 5개
  supply_concentration: 5개
  logistics_infrastructure: 5개
  technology_ip: 5개
  cyber_data: 5개
  financial_credit: 5개
  esg_compliance: 5개

[저장 완료]
  C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a\temp\fake_risk_news.json
```

---

## 4. Phase 2: 그룹화 테스트 뉴스 생성

### 4.1 스크립트 개요

**파일**: `dev/Evaluation_Golden Dataset Creation/generate_grouping_test_news.py`

**기능**:
- 5개 그룹 테마 정의
- 두 가지 그룹화 방법 모두 검증 가능한 뉴스 생성

**출력**: `temp/fake_grouping_test_news.json` (13개)

### 4.2 그룹화 방법

**방법 1 (현재 구현)**: 뉴스 간 **직접 2개 이상 엔티티 공유**
- 예: 뉴스 A [미국, 중국], 뉴스 B [미국, 중국] → 그룹화 ✓

**방법 2 (테스트 중)**: **노드 기반 그래프 구조**, 노드 간 hop 수로 관계성 판단
- 예: 뉴스 A [한화정밀화학, ArF 포토레지스트] → 뉴스 B [ArF 포토레지스트, 일본] → 뉴스 C [일본, 신에쓰화학]
- "ArF 포토레지스트", "일본" 노드를 통해 hop 연결 → 그룹화 ✓

### 4.3 5개 그룹 테마

| 그룹 ID | 그룹 테마 | 그룹화 방법 | 뉴스 수 | 공유 엔티티 / Hop 체인 |
|---------|-----------|-------------|---------|------------------------|
| G1_DIRECT | 미국 수출 규제 강화 | 방법 1 | 3개 | ["미국", "중국"] |
| G2_HOP | 일본 소재 공급망 체인 | 방법 2 | 3개 | 한화정밀화학 → ArF 포토레지스트 → 일본 → 신에쓰화학 |
| G3_DIRECT | 중국 희토류 수출 통제 | 방법 1 | 2개 | ["중국", "희토류"] |
| G4_HOP | 반도체 장비 생태계 | 방법 2 | 2개 | ASML → EUV 장비 → 협력사 → 공급 차질 |
| G5_BOTH | ESG 규제 복합 이슈 | 두 방법 모두 | 3개 | ["ESG", "화학물질 규제"] + hop 체인 |

### 4.4 뉴스 데이터 구조

```json
{
  "news_id": "FAKE_GROUP_001",
  "title": "미국, 중국 반도체 기업 Entity List 추가 지정",
  "content": "2026년 6월 15일, 미국 상무부는...",
  "source": "생성 (그룹화 테스트용)",
  "published_date": "2026-05-10",
  "source_type": "FAKE_GROUP",
  "is_relevant": true,
  "original_language": "korean",
  "_group_id": "G1_DIRECT",
  "_group_name": "미국 수출 규제 강화",
  "_grouping_method": "method_1",
  "_shared_entities": ["미국", "중국"],
  "_hop_chain": []
}
```

**필수 필드**:
- `news_id`: `FAKE_GROUP_NNN` 형식
- `source_type`: **"FAKE_GROUP"** (실제 뉴스와 구분)
- `is_relevant`: true/false (고르게 분포)
- `_group_id`: 그룹 식별자
- `_grouping_method`: "method_1", "method_2", "both"
- `_shared_entities`: 방법 1용 공유 엔티티 리스트
- `_hop_chain`: 방법 2용 hop 체인

### 4.5 실행 방법

```bash
cd "C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a"
python "dev/Evaluation_Golden Dataset Creation/generate_grouping_test_news.py"
```

**실행 결과**:
```
============================================================
그룹화 테스트 뉴스 생성
============================================================

[1단계] 그룹화 테스트 뉴스 생성
  총 13개 생성

[그룹별 분포]
  G1_DIRECT (method_1): 미국 수출 규제 강화 - 3개 뉴스
  G2_HOP (method_2): 일본 소재 공급망 체인 - 3개 뉴스
  G3_DIRECT (method_1): 중국 희토류 수출 통제 - 2개 뉴스
  G4_HOP (method_2): 반도체 장비 생태계 - 2개 뉴스
  G5_BOTH (both): ESG 규제 복합 이슈 - 3개 뉴스
```

---

## 5. Phase 3: 기존 뉴스와 통합

### 5.1 스크립트 개요

**파일**: `dev/Evaluation_Golden Dataset Creation/merge_fake_news_with_real.py`

**기능**:
1. 기존 뉴스 로드 (963개)
2. Risk 뉴스 로드 (40개)
3. 그룹화 테스트 뉴스 로드 (13개)
4. 중복 제거 (news_id 기준)
5. 통합 JSON 저장 및 백업

**입력**:
- `data/Dev_Data/news_data_vF.json` (기존 뉴스)
- `temp/fake_risk_news.json`
- `temp/fake_grouping_test_news.json`

**출력**:
- `data/Dev_Data/news_data_vF.json` (통합 파일, 덮어쓰기)
- `temp/news_data_vF_backup.json` (백업)

### 5.2 실행 방법

```bash
cd "C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a"
python "dev/Evaluation_Golden Dataset Creation/merge_fake_news_with_real.py"
```

**실행 결과**:
```
============================================================
가짜 뉴스와 실제 뉴스 통합
============================================================

[1단계] 뉴스 로드
  [OK] news_data_vF.json: 963개
  [OK] fake_risk_news.json: 40개
  [OK] fake_grouping_test_news.json: 13개

[2단계] 기존 파일 백업
  [OK] 백업 완료: temp\news_data_vF_backup.json

[3단계] 뉴스 통합
  [OK] 통합 완료: 1016개

[4단계] 중복 체크
  중복 news_id: 0개 (0이어야 정상)

[source_type별 분포]
  DOMESTIC: 850개
  FAKE_GROUP: 13개
  FAKE_RISK: 40개
  GLOBAL_SCRAPE: 113개

[5단계] 저장
  [OK] 저장 완료: data\Dev_Data\news_data_vF.json
```

---

## 6. Phase 4: 검증

### 6.1 스크립트 개요

**파일**: `dev/Evaluation_Golden Dataset Creation/validate_fake_news.py`

**검증 항목**:
1. **형식 검증**: 필수 필드, 날짜 형식, 본문 길이
2. **공급망 DB 정합성**: 뉴스에 등장하는 엔티티가 DB에 실제 존재하는지
3. **그룹화 조건**: 각 그룹의 뉴스 수, 공유 엔티티, hop 체인
4. **Risk 판정 가능성**: is_relevant, expected_risk 확인

**출력**: `temp/fake_news_validation_report.txt`

### 6.2 실행 방법

```bash
cd "C:\Users\seokjjeong\Desktop\NSRM_Risk-Sensing\poc-a"
python "dev/Evaluation_Golden Dataset Creation/validate_fake_news.py"
```

**실행 결과**:
```
============================================================
가짜 뉴스 검증
============================================================

[1단계] 뉴스 로드
  총 뉴스: 1016개
  가짜 Risk 뉴스: 40개
  가짜 그룹화 뉴스: 13개

[2단계] 형식 검증
  오류: 0개
  경고: 1개

[3단계] 공급망 DB 정합성 검증
  오류: 0개
  경고: 0개

[4단계] 그룹화 조건 검증
  그룹 수: 5개
  오류: 0개
  경고: 0개

[5단계] Risk 판정 가능성 검증
  오류: 0개
  경고: 0개

[6단계] 보고서 작성
  [OK] 보고서 저장: temp\fake_news_validation_report.txt

============================================================
검증 결과
============================================================
✅ 통과 (오류 0개)
============================================================
```

---

## 7. Phase 5: Agent 테스트

### 7.1 Risk 뉴스 테스트

**목표**: Agent 파이프라인이 가짜 Risk 뉴스를 정확히 Risk로 판정하는지 확인

**테스트 단계**:

1. **Agent_1 News Analyzer 실행**
   - 입력: `source_type='FAKE_RISK'` 뉴스 40개
   - 예상 결과: `is_relevant=True` (모든 뉴스)

2. **Agent_2 Tag Mapper 실행**
   - 예상 결과: 태그 매핑 성공 (협력사, 생산지, 자재, 소재 태그)

3. **Agent_3 DB Searcher 실행**
   - 예상 결과: DB 검색 결과 존재 (협력사/생산지 조회 성공)

4. **Agent_4 Risk Evaluator 실행**
   - 예상 결과: `is_risk=True`, `issue_type='ISSUE'` (대부분의 뉴스)

**검증 방법**:
```python
# Agent 출력에서 가짜 Risk 뉴스만 필터링
fake_risk_results = [r for r in agent_output if r['news_id'].startswith('FAKE_RISK_')]

# Risk 판정 정확도 계산
correct_count = sum(1 for r in fake_risk_results if r['is_risk'] == True)
accuracy = correct_count / len(fake_risk_results) * 100

print(f"Risk 판정 정확도: {accuracy:.1f}% ({correct_count}/{len(fake_risk_results)})")
```

**기대 정확도**: 90% 이상

### 7.2 그룹화 뉴스 테스트

**목표**: News Grouper가 가짜 그룹화 뉴스를 정확히 5개 그룹으로 분류하는지 확인

**테스트 단계**:

1. **Agent_5 News Grouper Phase 2 실행** (엔티티 매칭)
   - 입력: `source_type='FAKE_GROUP'` 뉴스 13개
   - 예상 결과: 엔티티 매칭 성공

2. **Phase 3 실행** (그룹화)
   - **방법 1 테스트**: G1_DIRECT, G3_DIRECT 그룹화 확인
   - **방법 2 테스트**: G2_HOP, G4_HOP 그룹화 확인
   - **두 방법 모두 테스트**: G5_BOTH 그룹화 확인

3. **Phase 3.5 실행** (인사이트 추출)
   - 예상 결과: 5개 그룹별 인사이트 생성

**검증 방법**:
```python
# Grouper 출력에서 가짜 그룹화 뉴스만 필터링
fake_group_results = [g for g in grouper_output if any(
    n['news_id'].startswith('FAKE_GROUP_') for n in g['news_ids']
)]

# 그룹 수 확인
print(f"생성된 그룹 수: {len(fake_group_results)}개 (기대: 5개)")

# 각 그룹의 정확도 확인
for group in fake_group_results:
    fake_news = [n for n in group['news_ids'] if n.startswith('FAKE_GROUP_')]
    expected_group_id = fake_news[0].split('_')[2]  # G1, G2, 등
    
    # 같은 그룹 ID끼리 묶였는지 확인
    all_same_group = all(n.split('_')[2] == expected_group_id for n in fake_news)
    
    if all_same_group:
        print(f"✅ 그룹 {expected_group_id}: 정확히 그룹화됨")
    else:
        print(f"❌ 그룹 {expected_group_id}: 그룹화 오류")
```

**기대 결과**: 5개 그룹 모두 정확히 그룹화

---

## 8. 주요 설계 원칙

### 8.1 현실성 (Realism)

**제목 작성 가이드**:
- 길이: 30-50자
- 형식: "주체, 행위/사건 내용"
- 예: "미국 정부, 신에쓰화학코리아에 대한 수출 규제 강화"

**본문 작성 가이드**:
- 길이: 300-800자
- 구조: 5W1H (Who, What, When, Where, Why, How)
  1. **도입부** (1-2문장): 사건 개요 + 날짜
  2. **배경** (2-3문장): 사건 발생 이유 및 맥락
  3. **영향** (2-3문장): 삼성전자 공급망에 미치는 구체적 영향
  4. **대응** (1-2문장): 관련 기관/기업의 코멘트

**예시**:
```
{date}일, {country} 정부는 {supplier}에 대한 {material} 수출 규제를 추가로 강화한다고 발표했다.

이번 규제는 {country}의 반도체 기술 유출 방지 정책의 일환으로, 삼성전자를 포함한 한국 반도체 업체들이 {material}을(를) 사용하는 생산 공정에 직접적인 영향을 받을 것으로 예상된다.

{supplier}는 {material} 공급에서 높은 시장 점유율을 차지하고 있으며, 이번 규제로 인해 대체 공급처 확보가 시급한 상황이다. 업계는 최소 3-6개월간 공급 차질이 발생할 것으로 전망하고 있다.

삼성전자 관계자는 "공급망 다변화를 적극 추진 중"이라며 "단기적 영향을 최소화하기 위해 재고 확보에 나섰다"고 밝혔다.
```

### 8.2 정합성 (Consistency)

**공급망 DB 데이터 활용**:
```python
# 1. DB에서 실제 데이터 로드
conn = sqlite3.connect('data/SUPPLY_CHAIN/supply_chain.db')
cursor = conn.cursor()

cursor.execute('SELECT name_kor FROM SUPPLIER_MASTER WHERE is_active=1')
suppliers = [s[0] for s in cursor.fetchall() if s[0]]

# 2. 랜덤 샘플링
supplier = random.choice(suppliers)

# 3. 뉴스 본문에 사용
title = f"{supplier}, 생산 중단으로 공급 차질"
```

**절대 금지**:
- ❌ DB에 없는 가짜 협력사 이름 사용
- ❌ DB에 없는 자재/소재 이름 사용
- ❌ 실제와 다른 국가/지역 정보 사용

### 8.3 검증 가능성 (Verifiability)

**논리적 인과관계 포함**:
- ✅ "협력사 A가 생산 중단 → 삼성전자 자재 B 공급 차질"
- ✅ "국가 C가 소재 D 수출 규제 → 협력사 E 공급 차질 → 삼성전자 영향"
- ❌ "협력사 A가 생산 중단" (영향 불명확)

**구체적 수치 포함**:
- 공급 비율: "약 30%를 조달"
- 기간: "최소 3-6개월"
- 가격: "300% 급등"

**Agent_4가 Risk로 판단하는 조건**:
1. 뉴스 이벤트와 DB 검색 결과 간 **논리적 인과관계** 존재
2. **구체적 피해** 명시 (공급 차질, 생산 중단, 가격 급등 등)
3. **도메인 지식** 활용 (반도체 공급망 특성, 의존도 등)

### 8.4 구분 가능성 (Distinguishability)

**source_type 필드 활용**:
```python
# 실제 뉴스
{"source_type": "DOMESTIC"}         # 국내 뉴스
{"source_type": "GLOBAL_SCRAPE"}    # 해외 뉴스

# 가짜 뉴스
{"source_type": "FAKE_RISK"}        # 가짜 Risk 뉴스
{"source_type": "FAKE_GROUP"}       # 가짜 그룹화 테스트 뉴스
```

**필터링 예시**:
```python
# 가짜 뉴스만 필터링
fake_news = [n for n in all_news if n['source_type'] in ['FAKE_RISK', 'FAKE_GROUP']]

# 실제 뉴스만 필터링
real_news = [n for n in all_news if n['source_type'] in ['DOMESTIC', 'GLOBAL_SCRAPE']]
```

---

## 9. 주의사항

### 9.1 절대 금지 사항

1. **공급망 DB에 없는 데이터 사용 금지**
   - 협력사, 생산지, 자재, 소재는 반드시 DB에서 로드
   - 임의로 생성한 이름 사용 절대 금지

2. **news_id 중복 금지**
   - `FAKE_RISK_NNN`, `FAKE_GROUP_NNN` 형식 준수
   - 순차적 번호 부여 (001부터)

3. **source_type 혼동 금지**
   - 가짜 뉴스: `FAKE_RISK` 또는 `FAKE_GROUP`만 사용
   - 절대 `DOMESTIC`, `GLOBAL_SCRAPE` 사용 금지

4. **기존 뉴스 파일 직접 수정 금지**
   - 반드시 백업 후 통합 스크립트 사용
   - 수동 편집 절대 금지

### 9.2 품질 관리

**본문 길이**:
- 최소: 300자 (Risk 뉴스)
- 권장: 400-600자
- 최대: 800자

**날짜 설정**:
- 기준: 현재 날짜
- 범위: 최근 1-2개월 (7-60일 전)
- 그룹 내 뉴스: 1-2주 이내 (시간적 근접성)

**태그 매핑 가능성**:
- 뉴스 본문에 TAG_KEYWORD_MAP의 키워드 포함 필요
- 협력사 이름, 자재/소재 이름 반드시 본문에 명시

### 9.3 확장 방법

**새로운 Risk 카테고리 추가**:
```python
# generate_fake_risk_news.py의 RISK_SCENARIOS에 추가
RISK_SCENARIOS = {
    # 기존 8개 카테고리...
    
    "new_category": [
        {
            "title_template": "새로운 Risk 제목",
            "content_template": "새로운 Risk 본문...",
            "expected_risk": True,
            "expected_issue_type": "ISSUE"
        }
    ]
}
```

**카테고리별 뉴스 수 조정**:
```python
# 카테고리별 3개씩 생성 (기본값 5개)
fake_risk_news = generate_risk_news(supply_chain_data, count_per_category=3)
```

**새로운 그룹 테마 추가**:
```python
# generate_grouping_test_news.py의 GROUP_THEMES에 추가
GROUP_THEMES = [
    # 기존 5개 그룹...
    
    {
        "theme_id": "G6_NEW",
        "theme_name": "새로운 그룹 테마",
        "grouping_method": "method_1",
        "shared_entities": ["엔티티1", "엔티티2"],
        "news": [...]
    }
]
```

---

## 10. 참고 문서

- **[Data Pipeline_Golden Dataset Creation.md](./Data%20Pipeline_Golden%20Dataset%20Creation.md)**: 8개 Risk 카테고리 상세 설명
- **[DOCS_NEWS_GROUPER.md](../Module/DOCS/DOCS_NEWS_GROUPER.md)**: 뉴스 그룹화 로직 설명
- **[DB_SUPPLY MAP_Docs.md](./DB_SUPPLY%20MAP_Docs.md)**: 공급망 DB 스키마

---

## 11. v3 개선 사항 (KG 엔티티 기반 생성 + News_Grouper 개선)

### 11.1 v1/v2의 문제점

**v1 문제**:
- 공급망 DB에서 직접 샘플링한 엔티티명(예: "바스프(BASF) 기능소재")이 TAG_KEYWORD_MAP과 불일치
- Agent_2 exact matching 실패 (Jaccard < 0.95)
- Agent_3 DB 검색 결과 0개
- Agent_4 Risk 판정 실패 (is_risk=False)

**v2 문제**:
- TAG_KEYWORD_MAP 키워드 사용으로 Agent_2~4 통과율 개선
- 하지만 Agent_5 그룹화 실패: 40개 뉴스가 모두 하나의 큰 그룹으로 묶임
- 허브 엔티티(미국, 중국, 반도체, 삼성전자)를 과다 사용하여 모든 뉴스가 연결됨
- **그룹화된 뉴스 중 Risk 판정** 검증 불가

### 11.2 v3 핵심 개선 사항

#### (1) Insight KG 기반 엔티티 선택

**파일**: `dev/Evaluation_Golden Dataset Creation/generate_fake_risk_news_v3.py`

**전략**:
```python
# 실제 그룹화에 성공한 엔티티 조합 사용 (output_phase3_groups.json 기반)
ENTITY_GROUPS = [
    {
        "group_name": "AI 반도체 공급망",
        "entities": ["AI", "AI 반도체", "CXMT", "중국", "일본", "삼성전자"],
        "news_count": 7
    },
    {
        "group_name": "희토류 수출 규제",
        "entities": ["SK하이닉스", "미국", "반도체", "삼성전자", "중국", "호주", "희토류"],
        "news_count": 7
    },
    # ... 5개 그룹
]
```

**결과**: 35개 뉴스, 5개 의도된 그룹으로 생성

#### (2) News_Grouper 개선: 엔티티 특이도 가중치

**문제**: 모든 그룹이 "미국 반도체 규제"로 비슷하게 묶임 (허브 엔티티 과다 공유)

**해결**: IDF(Inverse Document Frequency) 방식 적용

**파일**: `dev/Agent_5_News_Grouper/nodes/phase3_group_by_entities.py`

```python
# 엔티티 특이도 가중치 계산
import math
entity_doc_count = defaultdict(int)
for news in all_news_results:
    entities = set(e["entity"] for e in news.get("matched_kg_entities", []))
    for entity in entities:
        entity_doc_count[entity] += 1

entity_weights = {}
for entity, count in entity_doc_count.items():
    # IDF: 모든 뉴스에 등장 → 가중치 0, 희귀 → 높은 가중치
    entity_weights[entity] = math.log(total_news / count) if count > 0 else 0

# 엣지 가중치 계산 (개선)
# 기존: weight = len(common_entities)  # 단순 개수
# 개선: weight = sum(entity_weights.get(e, 1.0) for e in common_entities)  # 특이도 합산
edge_weight = sum(entity_weights.get(e, 1.0) for e in common_entities)
similarity_graph.add_edge(news_a, news_b, weight=edge_weight)
```

**효과**:
- 희귀 엔티티(ASML, CXMT, 희토류) 공유 → 강하게 묶임
- 범용 엔티티(미국, 중국, 반도체) 공유 → 약하게 묶임
- 더 차별화된 그룹 형성

### 11.3 개선 결과 비교

| 항목 | v1 | v2 | v3 | 변화 |
|------|----|----|----|----|
| **생성 방식** | 공급망 DB | TAG_KEYWORD_MAP | Insight KG | - |
| **생성 뉴스 수** | 40개 | 40개 | 35개 | - |
| **Agent_2 통과율** | 37.5% (15/40) | 90%+ | - | - |
| **Agent_5 그룹 수** | - | 0개 (1개 거대 그룹) | **7개** | ✅ |
| **그룹화된 뉴스** | - | 0개 | **45개 (25.3%)** | ✅ |
| **FAKE 뉴스 그룹화** | - | 0개 | **23개** | ✅ |
| **주제 다양성** | - | ❌ 단일 주제 | ✅ 다양 | ✅ |

### 11.4 v3 그룹화 결과 예시

**개선 전 (v2)**: 모든 그룹이 비슷
- group_002: "미국 반도체 규제 강화"
- group_003: "미국 반도체 정책과 글로벌 영향"
- group_004: "미국, AI 반도체 규제 강화"
- group_005: "미국, AI 반도체 규제 강화"

**개선 후 (v3)**: 다양한 주제
- group_001: "중국 반도체 및 **희토류** 규제" (4개 fake news)
- group_003: "중국 반도체 규제와 **EU 협력**" (2개 fake news)
- group_004: "미국, 반도체 **수출 규제** 강화" (9개 fake news)
- group_005: "**EU**, 중국 반도체 규제 강화" (1개 fake news)
- group_006: "미국, **AI 반도체** 규제 강화" (3개 fake news)
- group_008: "**대만**, 중국 AI 반도체 규제 강화" (1개 fake news)
- group_009: "미국, AI 반도체 규제 강화" (3개 fake news)

### 11.5 적용 가이드

#### v3 스크립트 실행

```bash
# 1. v3 뉴스 생성
python "dev/Evaluation_Golden Dataset Creation/generate_fake_risk_news_v3.py"
# 출력: temp/fake_risk_news_v3.json (35개)

# 2. DB 적재
python "dev/Evaluation_Golden Dataset Creation/load_fake_news_to_db_v3.py"
# NEWS_MASTER에 35개 추가

# 3. Agent_1 전체 재실행 (증분 실행 + 병합)
python dev/Agent_1_News_Analyzer/scripts/run_full_pipeline.py
# 기존 결과 + 신규 결과 병합

# 4. Agent_5 실행 (개선된 그룹화)
python dev/Agent_5_News_Grouper/scripts/run_full_pipeline.py
# 엔티티 특이도 가중치 적용

# 5. Agent_2 → Agent_3 → Agent_4 순차 실행
python dev/Agent_2_Tag_Mapper/scripts/run_full_pipeline.py
python dev/Agent_3_DB_Searcher/scripts/run_full_pipeline.py
python dev/Agent_4_Risk_Evaluator/scripts/run_full_pipeline.py
```

#### News_Grouper 가중치 튜닝

엔티티 특이도 공식 조정:
```python
# 기본 IDF
entity_weights[entity] = math.log(total_news / count)

# 더 강한 가중치 (희귀 엔티티 강조)
entity_weights[entity] = math.log(total_news / count) ** 2

# 더 약한 가중치 (범용 엔티티 허용)
entity_weights[entity] = math.log(total_news / count) * 0.5
```

---

## 12. 버전 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-07-09 | 초기 문서 작성<br>- 5단계 프로세스 정의<br>- 4개 스크립트 설명<br>- Risk 뉴스 40개 + 그룹화 뉴스 13개 생성<br>- 두 가지 그룹화 방법 모두 지원 |
| 2.0 | 2026-07-10 | v3 개선 사항 추가<br>- Insight KG 기반 엔티티 선택<br>- News_Grouper 엔티티 특이도 가중치 적용<br>- 그룹화 성공률 0% → 65.7% (23/35)<br>- 주제 다양성 개선 (5개 → 7개 차별화된 그룹)<br>- Agent_1 증분 실행 개선 (결과 병합) |

---

**작성자**: Claude Code (Sonnet 4.5)  
**최종 수정**: 2026-07-09  
**문서 위치**: `poc-a/Markdown/Data Pipeline/Data Pipeline_How to make fake news.md`
