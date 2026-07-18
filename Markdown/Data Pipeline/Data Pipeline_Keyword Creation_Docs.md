# 태그 DB 키워드 상세 문서

## 📋 목차
1. [개요](#개요)
2. [설계 철학](#설계-철학)
3. [키워드 생성 전략](#키워드-생성-전략)
4. [MECE 원칙 적용](#mece-원칙-적용)
5. [언어별 처리](#언어별-처리)
6. [실전 예시](#실전-예시)
7. [품질 관리](#품질-관리)

---

## 개요

### 목적
삼성전자DS 반도체 공급망 리스크 관련 뉴스를 **높은 정밀도**로 수집하기 위한 키워드셋 설계 및 관리

### 핵심 목표
- **노이즈 최소화**: 관련 없는 뉴스 수집 방지
- **정밀도 극대화**: Risk Factor와 직접 관련된 뉴스만 수집
- **유지보수 용이**: MECE 원칙으로 그룹 간 간섭 최소화

### 현황
- **총 레코드**: 148개
- **Risk Factor**: 35개 (100% 커버리지)
- **평균 키워드 수**: 3.2개/레코드
- **노이즈 위험 키워드**: 0개

---

## 설계 철학

### 1. keyword_group_name 중심 설계

**핵심 인사이트:**
> Risk Factor는 **넓은 범주**이고, keyword_group_name이 **실제 뉴스 토픽**입니다.

**구조:**
```
Risk Factor (카테고리)
  └─ keyword_group_name (구체적 토픽) ← 키워드 생성의 기준
       └─ 키워드 (뉴스 검색어)
```

**예시:**
```
Risk Factor: 수출입규제 (범주가 넓음)
  ├─ ECCN (미국 수출통제 품목 분류)
  │   → 키워드: ECCN 중심
  │
  ├─ 수출규제 (일반 수출규제)
  │   → 키워드: 수출규제 중심
  │
  └─ Entity List (BIS 제재리스트)
      → 키워드: Entity List 중심
```

### 2. 적은 키워드, 높은 정확도

**전략:**
- 많은 키워드로 넓게 수집 ❌
- 적은 키워드로 정확하게 수집 ✅

**근거:**
- 평균 3.2개 키워드로도 충분한 뉴스 수집 가능
- 키워드가 많을수록 노이즈 증가 위험
- 정밀도 > 재현율 (precision over recall)

### 3. MECE 원칙

**정의:**
- **Mutually Exclusive**: 그룹 간 상호 배타적
- **Collectively Exhaustive**: 전체를 빠짐없이 커버

**적용:**
- 같은 Risk Factor 내 keyword_group_name 간 키워드 중복 최소화
- Risk Factor의 일반 용어를 모든 그룹에 반복하지 않음

---

## 키워드 생성 전략

### 전략 1: keyword_group_name 자체를 핵심 키워드로

keyword_group_name이 이미 구체적이므로 **그 자체가 가장 중요한 키워드**입니다.

**예시:**
```
keyword_group_name: ECCN
→ 키워드[0]: "ECCN"

keyword_group_name: Entity List
→ 키워드[0]: "Entity List"

keyword_group_name: 랜섬웨어
→ 키워드[0]: "랜섬웨어"
```

### 전략 2: keyword_group_name + 반도체 맥락

keyword_group_name에 반도체 공급망 맥락을 결합합니다.

**패턴:**
```
keyword_group_name + "반도체" / "semiconductor"
keyword_group_name + "공급" / "supply"
keyword_group_name + 구체적 동작 (수출, 제재, 공격 등)
```

**예시:**
```
ECCN
→ ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"]

랜섬웨어
→ ["랜섬웨어", "반도체 공장 랜섬웨어", "팹 랜섬웨어", "공급사 랜섬웨어"]

대만해협
→ ["대만해협", "대만해협 반도체", "TSMC 대만해협"]
```

### 전략 3: 회사명/기관명 포함 (필요시)

keyword_group_name이 특정 회사/기관과 관련 있으면 포함합니다.

**예시:**
```
CMP Slurry
→ ["CMP Slurry", "CMP 슬러리", "CMP 연마", "Fujimi CMP"]
   (Fujimi는 주요 CMP 슬러리 공급사)

포토레지스트
→ ["포토레지스트", "포토레지스트 공급", "JSR 포토레지스트", "TOK 포토레지스트"]
   (JSR, TOK는 주요 포토레지스트 공급사)

ASML EUV
→ ["ASML EUV", "ASML 리소그래피", "ASML 수출"]
```

### 전략 4: 일반 용어 절대 금지

**금지 키워드 (단독 사용 시):**

| 유형 | 금지 키워드 |
|------|-----------|
| 지역명 | 중국, 미국, 유럽, 일본, 대만, 한국 |
| 산업 일반 | 반도체, 칩, 장비, 소재 |
| 공급망 | 공급, 수출, 제조, 생산 |

**허용:**
- ✅ "중국 수출규제" (구체적 구문)
- ✅ "ECCN 반도체" (고유명사 + 맥락)
- ✅ "ASML" (회사명)
- ❌ "중국" (단독)
- ❌ "반도체" (단독)

---

## MECE 원칙 적용

### 문제 상황 (Before)

```json
Risk Factor: 수출입규제

keyword_group_name: ECCN
→ ["ECCN", "반도체", "수출", "장비", "중국"]

keyword_group_name: 수출규제
→ ["수출규제", "반도체", "수출", "장비", "중국"]

keyword_group_name: Entity List
→ ["Entity List", "반도체", "제재", "중국"]
```

**문제점:**
1. "반도체", "수출", "중국"이 모든 그룹에 중복
2. 각 그룹의 **고유성** 없음
3. 뉴스 수집 시 어떤 그룹이 매칭되었는지 불명확

### 해결 (After - MECE 적용)

```json
Risk Factor: 수출입규제

keyword_group_name: ECCN
→ ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"]

keyword_group_name: 수출규제
→ ["수출규제", "반도체 수출규제", "칩 수출통제", "첨단반도체 수출제한"]

keyword_group_name: Entity List
→ ["Entity List", "Entity List 반도체", "BIS 제재리스트", "반도체 기업 Entity List"]
```

**개선점:**
1. ✅ 각 그룹이 **고유한 키워드**만 보유
2. ✅ 뉴스 매칭 시 어떤 그룹인지 명확히 식별
3. ✅ 그룹 간 간섭 없음

### MECE 검증 방법

```python
def verify_mece(risk_factor_df):
    """같은 Risk Factor 내 keyword_group 간 중복 체크"""
    
    all_keywords = {}
    
    for idx, row in risk_factor_df.iterrows():
        group_name = row['keyword_group_name']
        keywords = json.loads(row['keyword'])
        
        for kw in keywords:
            if kw not in all_keywords:
                all_keywords[kw] = []
            all_keywords[kw].append(group_name)
    
    # 중복 키워드 출력
    duplicates = {kw: groups for kw, groups in all_keywords.items() if len(groups) > 1}
    
    if duplicates:
        print("⚠️ MECE 위반:")
        for kw, groups in duplicates.items():
            print(f"  '{kw}' → {groups}")
    else:
        print("✅ MECE 원칙 준수")
```

---

## 언어별 처리

### 원칙

| target_region | 키워드 언어 | exclude_keyword 언어 | 고유명사 |
|---------------|------------|---------------------|---------|
| KR | 한글 | 한글 | 영문 허용 (ASML, BIS 등) |
| GLOBAL | 영문 | 영문 | 영문만 |

### KR 레코드

**키워드:**
```json
{
  "target_region": "KR",
  "keyword": ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"],
  "exclude_keyword": ["소설", "영화", "드라마", "게임"]
}
```

**특징:**
- 한글 키워드 중심
- 고유명사는 영문 그대로 (ECCN, BIS, ASML 등)

### GLOBAL 레코드

**키워드:**
```json
{
  "target_region": "GLOBAL",
  "keyword": ["ECCN", "ECCN semiconductor", "ECCN export control", "CCL semiconductor"],
  "exclude_keyword": ["novel", "movie", "film", "drama", "game"]
}
```

**특징:**
- 100% 영문
- 한글 0개

---

## 실전 예시

### 예시 1: 수출입규제

#### keyword_group_name: ECCN

**KR:**
```json
{
  "risk_factor": "수출입규제",
  "keyword_group_name": "ECCN",
  "keyword": ["ECCN", "ECCN 반도체", "ECCN 수출통제", "CCL 반도체"],
  "target_region": "KR"
}
```

**GLOBAL:**
```json
{
  "risk_factor": "수출입규제",
  "keyword_group_name": "ECCN",
  "keyword": ["ECCN", "ECCN semiconductor", "ECCN export control", "CCL semiconductor"],
  "target_region": "GLOBAL"
}
```

**뉴스 매칭 예시:**
- ✅ "미국 BIS, 반도체 ECCN 분류 강화"
- ✅ "ECCN 수출통제 품목에 첨단 칩 추가"
- ❌ "반도체 수출 증가" (ECCN 없음)
- ❌ "중국 반도체 시장" (ECCN 없음)

#### keyword_group_name: 수출규제

**KR:**
```json
{
  "keyword_group_name": "수출규제",
  "keyword": ["수출규제", "반도체 수출규제", "칩 수출통제", "첨단반도체 수출제한"]
}
```

**뉴스 매칭 예시:**
- ✅ "미국, 중국향 반도체 수출규제 강화"
- ✅ "첨단 칩 수출통제 대상 확대"
- ❌ "수출 실적 발표" (수출규제 아님)

### 예시 2: 사이버 공격

#### keyword_group_name: 랜섬웨어

**KR:**
```json
{
  "risk_factor": "공급사 사이버 공격",
  "keyword_group_name": "랜섬웨어",
  "keyword": ["랜섬웨어", "반도체 공장 랜섬웨어", "팹 랜섬웨어", "공급사 랜섬웨어"]
}
```

**뉴스 매칭 예시:**
- ✅ "대만 반도체 공장, 랜섬웨어 공격으로 생산 중단"
- ✅ "공급사 랜섬웨어 피해, 납기 지연 우려"
- ❌ "랜섬웨어 일반 뉴스" (반도체 맥락 없음)

#### keyword_group_name: OT 보안

**KR:**
```json
{
  "keyword_group_name": "OT 보안",
  "keyword": ["OT 보안", "반도체 OT 보안", "팹 제조시스템 해킹", "SCADA 취약점"]
}
```

**MECE 확인:**
- ✅ "랜섬웨어"와 "OT 보안"이 명확히 구분
- ✅ 키워드 중복 없음

### 예시 3: 소재 공급

#### keyword_group_name: CMP Slurry

**KR:**
```json
{
  "risk_factor": "소재 단일 공급",
  "keyword_group_name": "CMP Slurry",
  "keyword": ["CMP Slurry", "CMP 슬러리", "CMP 연마", "Fujimi CMP"]
}
```

**뉴스 매칭 예시:**
- ✅ "Fujimi, CMP 슬러리 공급 차질"
- ✅ "CMP 연마 소재 부족 우려"
- ❌ "반도체 소재 일반" (CMP Slurry 특정 없음)

#### keyword_group_name: 포토레지스트

**KR:**
```json
{
  "keyword_group_name": "포토레지스트",
  "keyword": ["포토레지스트", "포토레지스트 공급", "JSR 포토레지스트", "TOK 포토레지스트"]
}
```

**MECE 확인:**
- ✅ "CMP Slurry"와 "포토레지스트"가 완전히 다른 소재
- ✅ 키워드 중복 0개

---

## 품질 관리

### 검증 체크리스트

#### 1. 단독 일반 용어 체크

```python
PROHIBITED_TERMS = {
    '중국', 'China', '미국', 'US', '반도체', 'semiconductor',
    '칩', 'chip', '공급', 'supply', '수출', 'export'
}

def check_prohibited_terms(keywords):
    """단독 일반 용어 체크"""
    violations = [kw for kw in keywords if kw in PROHIBITED_TERMS]
    return violations
```

**기준:**
- 위반 0개여야 함
- 발견 시 즉시 수정

#### 2. MECE 체크

같은 Risk Factor 내 keyword_group_name 간 중복 확인

**허용 기준:**
- 중복 키워드 < 10%
- 핵심 키워드는 중복 불가

#### 3. 언어 순수성 체크

```python
def check_language_purity(df):
    """언어 순수성 검증"""
    violations = []
    
    for idx, row in df.iterrows():
        if row['target_region'] == 'GLOBAL':
            kws = json.loads(row['keyword'])
            for kw in kws:
                if has_korean(kw):
                    violations.append((idx, kw))
    
    return violations
```

**기준:**
- GLOBAL 레코드: 한글 0개
- KR 레코드: 고유명사 제외 영문 최소화

#### 4. 키워드 수 체크

**기준:**
- 평균: 3~4개
- 최소: 2개
- 최대: 5개

**예외:**
- 1개: 고유명사만 있는 경우 (예: FIPA)
- 6개 이상: 정당한 이유 필요

### 주기적 검토

**월 1회:**
- 실제 뉴스 수집 결과 분석
- 노이즈율 측정
- 누락된 뉴스 확인

**분기 1회:**
- 새로운 Risk Factor 추가 여부 확인
- keyword_group_name 재검토
- 키워드 업데이트

---

## 🔗 관련 문서

- `DB_TAG_Keyword Creation Rules.md` - 키워드 생성 원칙
- `DB_TAG_Risk Factor Pool.xlsx` - Risk Factor 정의 및 키워드셋
- 삼성전자DS 반도체 공급망 Risk 분류 체계
