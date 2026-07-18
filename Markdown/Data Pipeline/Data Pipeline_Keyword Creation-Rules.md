# 태그 DB 키워드 생성 원칙

## 문서 개요
- **목적**: 삼성전자DS 반도체 공급망 Risk Factor별 뉴스 수집용 키워드셋 작성 가이드라인
- **적용 대상**: 태그DB_Risk Factor Pool의 35개 Risk Factor
- **생성 결과**: 148개 키워드 레코드 (한글 76개 + 영문 72개)
- **평균 키워드 수**: 3.2개/레코드 (적지만 정확)
- **작성일**: 2026-06-25

---

## 📋 핵심 원칙

### 1. **keyword_group_name 중심 설계**

키워드는 **Risk Factor**가 아닌 **keyword_group_name**에 집중하여 생성합니다.

- **Risk Factor**: 넓은 범주 (예: "수출입규제")
- **keyword_group_name**: 구체적 하위 항목 (예: "ECCN", "수출규제", "Entity List")
- **키워드**: keyword_group_name을 중심으로 구체화

**예시:**
```
Risk Factor: 수출입규제
  ├─ keyword_group_name: ECCN
  │   └─ 키워드: ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"]
  │
  ├─ keyword_group_name: 수출규제
  │   └─ 키워드: ["수출규제", "반도체 수출규제", "칩 수출통제", "첨단반도체 수출제한"]
  │
  └─ keyword_group_name: Entity List
      └─ 키워드: ["Entity List", "Entity List 반도체", "BIS 제재리스트"]
```

**❌ 나쁜 예 (Risk Factor 중심):**
```json
{
  "risk_factor": "수출입규제",
  "keyword_group_name": "ECCN",
  "keyword": ["수출규제", "반도체", "장비", "중국", "미국"]
}
```
→ "반도체", "중국" 등 일반 용어로 노이즈 발생

**✅ 좋은 예 (keyword_group_name 중심):**
```json
{
  "risk_factor": "수출입규제",
  "keyword_group_name": "ECCN",
  "keyword": ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"]
}
```
→ ECCN에만 집중하여 정확한 뉴스 수집

### 2. **MECE 원칙 (Mutually Exclusive, Collectively Exhaustive)**

같은 Risk Factor 내에서 keyword_group_name 간 **키워드 중복을 최소화**합니다.

- 각 keyword_group_name은 **고유한 키워드**만 보유
- Risk Factor의 일반 용어는 **모든 그룹에 중복 포함하지 않음**

**예시:**
```
❌ 중복 많음 (MECE 위반):
  ECCN: ["ECCN", "반도체", "수출", "중국"]
  수출규제: ["수출규제", "반도체", "수출", "중국"]
  Entity List: ["Entity List", "반도체", "중국"]
  → "반도체", "수출", "중국"이 모든 그룹에 중복

✅ MECE 적용:
  ECCN: ["ECCN", "ECCN 반도체", "ECCN 수출통제"]
  수출규제: ["수출규제", "반도체 수출규제", "칩 수출통제"]
  Entity List: ["Entity List", "Entity List 반도체", "BIS 제재리스트"]
  → 각 그룹이 고유한 키워드만 보유
```

### 3. **노이즈 최소화: 단독 일반 용어 금지**

"반도체", "중국", "공급" 같은 단독 일반 용어는 **절대 사용하지 않습니다**.

**금지 키워드 (단독 사용 시):**
- 지역명: 중국, 미국, 유럽, 일본, 대만
- 산업 일반: 반도체, 칩, 장비, 소재, 공급, 수출, 제조

**허용:**
- 고유명사: ASML, TSMC, BIS, CFIUS (회사명, 기관명)
- 구체적 구문: "반도체 수출규제", "ECCN 반도체", "중국향 반도체 수출"

### 4. **적은 키워드, 높은 정확도**

- 평균 3~4개 키워드면 충분
- 많은 키워드보다 **확실한 관련 뉴스만 검색**하는 것이 목표

### 5. **언어별 완전 분리**

- **KR 레코드 (target_region='KR')**: 한글 키워드만 (고유명사 제외)
- **GLOBAL 레코드 (target_region='GLOBAL')**: 영문 키워드만

---

## 🎯 키워드 생성 방법

### Step 1: keyword_group_name 분석

keyword_group_name의 **핵심 의미**를 파악합니다.

**예시:**
- "ECCN" → 미국 수출통제 품목 분류
- "랜섬웨어" → 랜섬웨어 사이버 공격
- "대만해협" → 대만해협 지역 긴장
- "CMP Slurry" → CMP 연마 슬러리 소재

### Step 2: keyword_group_name + 반도체 맥락 결합

keyword_group_name에 반도체 공급망 맥락을 결합합니다.

**패턴:**
1. keyword_group_name 자체
2. keyword_group_name + "반도체" / "semiconductor"
3. keyword_group_name + 구체적 액션 (예: "공급", "수출", "제재")

**예시:**

```
keyword_group_name: ECCN
→ ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"]

keyword_group_name: 랜섬웨어
→ ["랜섬웨어", "반도체 공장 랜섬웨어", "팹 랜섬웨어", "공급사 랜섬웨어"]

keyword_group_name: 대만해협
→ ["대만해협", "대만해협 반도체", "TSMC 대만해협"]

keyword_group_name: CMP Slurry
→ ["CMP Slurry", "CMP 슬러리", "CMP 연마", "Fujimi CMP"]
```

### Step 3: 검증

생성한 키워드를 검증합니다:

1. **단독 일반 용어 체크**: "반도체", "중국" 등 단독 사용 금지
2. **MECE 체크**: 같은 Risk Factor 내 다른 keyword_group과 중복 확인
3. **구체성 체크**: 뉴스 검색 시 관련 없는 뉴스가 나올 가능성 확인

---

## 📌 적용 예시

### 예시 1: 수출입규제

| keyword_group_name | 키워드 (KR) | 키워드 (GLOBAL) |
|-------------------|------------|----------------|
| ECCN | ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"] | ["ECCN", "ECCN semiconductor", "ECCN export control", "CCL semiconductor"] |
| 수출규제 | ["수출규제", "반도체 수출규제", "칩 수출통제", "첨단반도체 수출제한"] | ["export control", "semiconductor export ban", "chip export restriction", "advanced semiconductor export"] |

**MECE 확인**: ✅ "ECCN"과 "수출규제"가 고유 키워드만 보유

### 예시 2: 사이버 공격

| keyword_group_name | 키워드 (KR) |
|-------------------|-----------|
| 랜섬웨어 | ["랜섬웨어", "반도체 공장 랜섬웨어", "팹 랜섬웨어", "공급사 랜섬웨어"] |
| OT 보안 | ["OT 보안", "반도체 OT 보안", "팹 제조시스템 해킹", "SCADA 취약점"] |

**MECE 확인**: ✅ "랜섬웨어"와 "OT 보안"이 명확히 구분됨

### 예시 3: 소재 공급

| keyword_group_name | 키워드 (KR) |
|-------------------|-----------|
| CMP Slurry | ["CMP Slurry", "CMP 슬러리", "CMP 연마", "Fujimi CMP"] |
| 포토레지스트 | ["포토레지스트", "포토레지스트 공급", "JSR 포토레지스트", "TOK 포토레지스트"] |
| HF (불산) | ["불산", "불산 공급", "HF 수출", "초고순도 불산"] |

**MECE 확인**: ✅ 각 소재가 고유 키워드만 보유

---

## 🔄 exclude_keyword (제외 키워드)

뉴스 수집 시 제외할 키워드를 설정하여 오탐을 사전 차단합니다.

### 전역 제외 키워드

**한글 (KR):**
```json
["소설", "영화", "드라마", "게임", "애니메이션",
 "스마트폰", "갤럭시", "아이폰",
 "주가", "코스피", "증권",
 "요리", "여행", "관광"]
```

**영문 (GLOBAL):**
```json
["novel", "movie", "film", "drama", "game",
 "smartphone", "Galaxy", "iPhone",
 "stock price", "KOSPI",
 "cooking", "travel", "tourism"]
```

### Risk Factor별 추가 제외 (선택)

필요시 Risk Factor 특성에 맞는 제외 키워드 추가:

```
네온가스 → ["네온사인", "형광등", "조명"]
사이버 공격 → ["게임 해킹", "SNS 해킹"]
```

---

## 🛠️ 데이터 구조

### 스키마

```python
{
    'risk_category_code': str,        # 대분류 영문 코드
    'risk_category_name': str,        # 대분류 한글명
    'risk_factor': str,               # Risk Factor (35개)
    'keyword_group_name': str,        # 키워드 그룹명 (핵심!)
    'keyword': str,                   # JSON 배열 (한글 or 영문)
    'exclude_keyword': str,           # JSON 배열 (한글 or 영문)
    'target_region': str,             # 'KR' or 'GLOBAL'
    'is_active': int,                 # 1 (활성)
    'description': str                # 설명
}
```

### 뉴스 매칭 로직

```python
def check_news_match(news_text, record):
    """뉴스가 키워드 레코드와 매칭되는지 확인"""
    keywords = json.loads(record['keyword'])
    
    # OR 조건: 하나라도 매칭되면 True
    has_keyword = any(kw.lower() in news_text.lower() for kw in keywords)
    
    if not has_keyword:
        return False
    
    # 제외 키워드 체크
    exclude_keywords = json.loads(record['exclude_keyword'])
    has_exclude = any(ex.lower() in news_text.lower() for ex in exclude_keywords)
    
    return not has_exclude
```

---

## 📊 최종 통계

| 항목 | 값 |
|------|-----|
| 총 레코드 | 148개 |
| KR 레코드 | 76개 |
| GLOBAL 레코드 | 72개 |
| 평균 키워드 수 | 3.2개 |
| Risk Factor 커버리지 | 35개 (100%) |
| 단독 일반 용어 | 0개 ✅ |
| MECE 원칙 | ✅ 적용 |

---

## ⚠️ 주의사항

### 하지 말아야 할 것

1. ❌ Risk Factor의 일반 용어를 모든 keyword_group에 중복 포함
2. ❌ "반도체", "중국", "공급" 같은 단독 일반 용어 사용
3. ❌ keyword_group_name 무시하고 Risk Factor만 보고 키워드 생성
4. ❌ 키워드 개수를 늘리려고 관련 없는 키워드 추가

### 해야 할 것

1. ✅ keyword_group_name의 의미를 정확히 파악
2. ✅ keyword_group_name + 반도체 맥락 결합
3. ✅ MECE 원칙으로 그룹 간 중복 최소화
4. ✅ 적은 키워드로 높은 정확도 추구

---

## 🔗 참고 문서

- `DB_TAG_Risk Factor Pool.xlsx` - Risk Factor 정의
- `DB_TAG_Keyword Docs.md` - 상세 문서
- 삼성전자DS 반도체 공급망 Risk 분류 체계
