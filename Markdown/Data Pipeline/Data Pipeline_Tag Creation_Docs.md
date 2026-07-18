# 공급망 Risk 태그(Tag) 설계 방법론
### LLM 기반 태그 생성을 위한 가이드라인

---

## 1. 태그란 무엇인가

태그(Tag)는 뉴스에서 추출된 다양한 표현(동의어, 약어, 외래어 표기 등)을 **하나의 표준 검색 키로 정규화한 것**입니다. 태그는 새로운 분류체계를 만드는 것이 아니라, 공급망 DB에 이미 존재하는 개체(소재, 자재, 협력사, 위치)를 가리키는 여러 표현을 하나로 묶는 작업입니다.

**예시**: "아르곤", "Argon", "아르곤가스" → 태그 **AR**

태그는 다음 파이프라인에서 핵심 연결 고리 역할을 합니다.

```
뉴스 수집 → 키워드 추출 → 태그 정규화 → [LLM: 검색 전략 수립] → [LLM: Text-to-SQL] → DB Search
```

이 파이프라인에서 중요한 점은, 태그가 **사람이 보기 좋은 분류명이 아니라 LLM이 DB 구조를 추론하는 근거(스키마 힌트)** 로 쓰인다는 것입니다. 따라서 태그 설계는 두 가지 역할을 동시에 만족해야 합니다.

1. **정규화 사전 역할**: 표현이 달라도 동일 대상이면 하나의 태그로 수렴
2. **LLM 스키마 힌트 역할**: LLM이 어떤 테이블/컬럼을 조회하고, 무엇과 결합(JOIN)해야 하는지 추론할 수 있는 메타데이터 제공

---

## 2. 태그의 구조

태그는 다음 계층 구조 안에 위치합니다.

```
대분류 (Domain)
  └─ Risk Factor (리스크 요인)
        └─ Tag (정규화된 검색 키)
              └─ Keyword (뉴스 원문 표현, 동의어)
```

- **대분류 / Risk Factor**: 분류·카테고리 역할 전담. 태그는 분류 기능을 갖지 않음
- **Tag**: 정규화 사전 + LLM 스키마 힌트 역할만 전담 (역할 단일화)
- **Keyword**: 태그에 매핑되는 동의어 표현 (N:1 관계, 1개 태그 ← N개 키워드)

---

## 3. 태그 유형 분류

태그는 "어떤 DB 엔티티에 대응하는가"를 기준으로 5가지 유형으로 나뉩니다.

| 태그 유형 | 대응 DB 엔티티 | 단독 검색 가능 여부 | 계층 관계 |
|---|---|---|---|
| RAW_MATERIAL (소재) | 소재 마스터 (RAW_MATERIAL_MASTER) | 가능 | 원소재 (예: 아르곤, 희토류, 텅스텐) |
| MATERIAL (자재) | 자재 마스터 (MATERIAL_MASTER) | 가능 | **상위 개념** - 소재를 포함 (예: MLCC, 포토레지스트, 타겟) |
| SUPPLIER (협력사) | 협력사 마스터 (SUPPLIER_MASTER) | 가능 | 법인 단위 |
| SITE (위치) | Site/지역 마스터 (SITE_MASTER) | 가능 | 생산 거점 단위 |
| EVENT (이벤트/현상) | 직접 대응 엔티티 없음 | **불가 — 검색 전략 힌트 제공** | 규제, 재해, 파업 등 |

**계층 구조**:
```
자재 (MATERIAL) ⊃ 소재 (RAW_MATERIAL)
  예: "ArF 포토레지스트" (자재) ⊃ "폴리머", "PGMEA", "광산발생제" (소재)
  예: "텅스텐 타겟" (자재) ⊃ "텅스텐(W)", "티타늄(Ti)" (소재)
```

**DB 매핑 관계**:
```
MATERIAL_MASTER ←→ MATERIAL_RAW_MATERIAL_MAP ←→ RAW_MATERIAL_MASTER
    (자재)                (N:M 매핑)          (소재 - RAW_MATERIAL)
```

### 3.1 유형별 LLM 스키마 힌트 동작 예시

| 태그 유형 | 태그 예시 | LLM에게 제공되는 힌트 | LLM의 추론 동작 |
|---|---|---|---|
| RAW_MATERIAL | AR | `RAW_MATERIAL_MASTER.name_kor` 또는 `name_eng`과 매칭 | 소재명으로 WHERE → MATERIAL_RAW_MATERIAL_MAP → MATERIAL → SITE → SUPPLIER로 JOIN 확장 |
| MATERIAL | MLCC | `MATERIAL_MASTER.name_kor` 또는 `material_type`과 매칭 | 자재명/유형 필터 → SITE_MATERIAL_MAP → SITE → SUPPLIER로 JOIN |
| SUPPLIER | ASML | `SUPPLIER_MASTER.supplier_code`와 매칭 (또는 `name_kor`/`name_eng` 참조) | 단일 테이블 직접 조회 또는 SITE로 확장 |
| SITE | CHINA | `SITE_MASTER.country`와 매칭 (ISO 코드 아님, 국가명 텍스트) | 위치 필터, 단독 또는 EVENT 태그의 결합 조건으로 사용 |
| EVENT | EXPORT_CTRL_CN | 대응 테이블 없음 → **검색 전략 힌트 제공** | LLM에게 "중국(SITE) + 희토류(RAW_MATERIAL) 관련 영향 추적" 같은 전략 수립 정보 제공 |

**EVENT 태그의 역할 재정의**:

EVENT 태그는 단독으로 WHERE/JOIN을 생성할 수 없지만, **LLM이 DB 조회 전략을 수립할 때 핵심 힌트**를 제공합니다.

**예시 1: 대만 지진 (TAIWAN_EQ)**
- EVENT 태그: "대만 지진"
- LLM 전략: "대만(SITE) 소재 생산 거점 → 영향받는 자재(MATERIAL) → 공급하는 협력사(SUPPLIER) 추적"
- 생성 쿼리:
  ```sql
  SELECT sup.name_kor, m.name_kor, s.region
  FROM SITE_MASTER s
  JOIN SITE_MATERIAL_MAP smm ON s.site_code = smm.site_code
  JOIN MATERIAL_MASTER m ON smm.material_code = m.material_code
  JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
  WHERE s.country = 'Taiwan';  -- EVENT 태그가 SITE 조건 유도
  ```

**예시 2: 미국의 중국 희토류 수출규제 (EXPORT_CTRL_CN_REE)**
- EVENT 태그: "중국 수출규제 + 희토류"
- LLM 전략: "희토류(RAW_MATERIAL) → 포함 자재(MATERIAL) 추적 + 중국(SITE) 생산 거점 필터"
- 생성 쿼리:
  ```sql
  SELECT sup.name_kor, m.name_kor, s.country, sub.name_kor
  FROM RAW_MATERIAL_MASTER sub
  JOIN MATERIAL_RAW_MATERIAL_MAP msm ON sub.substance_code = msm.substance_code
  JOIN MATERIAL_MASTER m ON msm.material_code = m.material_code
  JOIN SITE_MATERIAL_MAP smm ON m.material_code = smm.material_code
  JOIN SITE_MASTER s ON smm.site_code = s.site_code
  JOIN SUPPLIER_MASTER sup ON s.supplier_code = sup.supplier_code
  WHERE sub.name_eng LIKE '%Rare Earth%'  -- EVENT가 RAW_MATERIAL 조건 유도
    AND s.country = 'China';              -- EVENT가 SITE 조건 유도
  ```

**핵심 원칙**: EVENT 태그는 "무엇을(RAW_MATERIAL/MATERIAL)" + "어디서(SITE)" + "누가(SUPPLIER)"를 결합하여 영향 범위를 추적하는 **검색 전략의 설계도** 역할을 합니다.

**DB 스키마 주의사항**:
- 실제 DB는 `MATERIAL_MASTER.name_kor/name_eng/material_type`, `RAW_MATERIAL_MASTER.name_kor/name_eng` 컬럼 사용
- `SUPPLIER_MASTER.supplier_code`가 PK (supplier_id 아님)
- `SITE_MASTER.country`는 ISO 코드가 아닌 텍스트 ("South Korea", "China" 등)

---

## 4. 태그 설계 필요조건 (Design Requirements)

태그를 설계하거나 LLM에게 태그 생성을 위임할 때, 아래 조건을 반드시 만족해야 합니다.

1. **유일성(Uniqueness)**: 태그 하나는 단일 지시체만 가져야 함 (동음이의어 금지)
2. **상호배타성(Mutual Exclusivity)**: 동일 키워드가 두 개 이상의 태그에 중복 매핑되지 않아야 함
3. **계층 일관성(Hierarchy Consistency)**: 모든 태그는 1개 이상의 Risk Factor에 귀속되어야 함 (N:M 여부는 사전 정의)
4. **세분화 일관성(Granularity Consistency)**: 같은 유형 내에서는 비슷한 세분화 수준을 유지 (예: 소재를 "반도체" 단위로 묶을지 "DRAM/NAND" 단위로 나눌지 일관되게 적용)
5. **엔티티 매칭 가능성(Entity Mappability)**: MATERIAL/PART/SUPPLIER/SITE 태그는 반드시 실제 DB 테이블·컬럼 값과 매칭되어야 함
6. **결합 규칙 명시(Join Rule Explicitness)**: EVENT 태그는 반드시 결합이 필요한 태그 유형(주로 SITE, 때로 MATERIAL)을 명시해야 함
7. **확장성(Extensibility)**: 신규 표현 발견 시 기존 태그에 편입할지, 신규 태그를 만들지 판단 기준을 보유해야 함

---

## 5. LLM 기반 태그 생성 방법론

### 5.1 생성 절차 (Pipeline)

본 프로젝트는 Risk Factor 기반으로 이미 키워드셋(154개)이 구성되어 있으므로, **5.4절 "Risk Factor 기반 키워드셋에서 태그 생성"**을 참조하세요.

뉴스 수집 후 태그를 활용하여 공급망 DB를 검색하는 운영 파이프라인은 **[DB_TAG_News Mapping Pipeline.md](./DB_TAG_News%20Mapping%20Pipeline.md)**를 참조하세요.

**참고: 뉴스에서 직접 키워드를 추출하는 경우의 일반적인 절차** (본 프로젝트에는 해당 없음):

```
[1단계] 원천 데이터 확인
   - 소재/자재/협력사/Site 마스터 테이블 스키마 확보
   - 기존 사내 용어사전, 코드체계 확보

[2단계] 키워드 군집화 (Clustering)
   - 뉴스에서 추출된 키워드를 의미 단위로 LLM이 군집화
   - 동일 지시체로 판단되는 표현들을 하나의 후보 태그로 묶음

[3단계] 태그 유형 판별 (Type Classification)
   - LLM이 각 군집에 대해 RAW_MATERIAL/MATERIAL/SUPPLIER/SITE/EVENT 중 유형을 판별
   - 판별 기준: 마스터 테이블에 직접 대응하는 컬럼이 있는가? (있으면 엔티티형, 없으면 EVENT형)

[4단계] 메타데이터 부여 (Metadata Assignment)
   - 엔티티형: 대응 테이블.컬럼 지정
   - EVENT형: 결합이 필요한 태그 유형과 결합 조건(JOIN 경로) 명시

[5단계] 계층 연결 (Hierarchy Mapping)
   - 생성된 태그를 상위 Risk Factor / 대분류에 연결

[6단계] 검증 (Validation)
   - 4장의 필요조건(유일성, 상호배타성 등) 자동/수동 점검
   - 사람 검수자(Human-in-the-loop) 승인
```

### 5.2 LLM 프롬프트 설계 가이드

LLM에게 태그 생성을 위임할 때, 프롬프트에는 다음 정보가 반드시 포함되어야 합니다.

- **DB 스키마 정보**: 소재/자재/협력사/Site 마스터 테이블의 컬럼명과 데이터 타입
- **태그 유형 정의**: 위 5가지 유형의 정의와 판별 기준
- **기존 태그 목록**: 중복 생성을 피하기 위해 이미 존재하는 태그와 키워드 풀
- **출력 형식(Schema)**: 아래 6장의 표준 출력 구조를 명시하여 일관된 형식으로 생성하도록 강제
- **결합 규칙 작성 예시**: EVENT 태그가 결합 규칙을 어떻게 표현해야 하는지 few-shot 예시 제공

### 5.3 LLM 출력 검증 체크리스트

LLM이 생성한 태그는 사람이 다음을 검증해야 합니다.

- [ ] 태그명이 기존 태그와 중복되지 않는가
- [ ] 키워드가 다른 태그와 중복 매핑되지 않는가 (상호배타성)
- [ ] 엔티티형 태그가 실제 존재하는 테이블.컬럼을 가리키는가
- [ ] EVENT형 태그에 결합 규칙이 누락되지 않았는가
- [ ] Risk Factor 연결이 비어있지 않은가

### 5.4 Risk Factor 기반 키워드셋에서 태그 생성

**본 프로젝트의 실제 상황**: 이미 35개 Risk Factor 기반 154개 키워드 레코드가 생성되어 있으므로, 기존 5.1절의 "뉴스 추출 → 군집화" 대신 다음 절차를 따릅니다.

#### 5.4.1 입력 데이터 구조

```
키워드셋 파일: data/TAG/DB_TAG_Risk Factor Pool.xlsx (2. Keyword Set 시트)
레코드 수: 154개 (한글 82개 KR + 영문 72개 GLOBAL)
구조:
  - risk_category_name (8개 대분류)
  - risk_factor (35개 Risk Factor)
  - keyword_group_name (154개 - 태그 후보)
  - keyword (JSON 배열 - 동의어 리스트)
  - target_region (KR / GLOBAL)
```

#### 5.4.2 태그 생성 절차 (범용 방법론)

**범용 원칙: DB 스키마 독립적 설계**

새로운 공급망 DB에도 적용 가능하도록 설계된 절차입니다.

```
[1단계] DB 엔티티 분석 (스키마 조사)
   목적: 태그 생성 대상 테이블 파악
   
   1-1. 마스터 테이블 식별
      - 소재/원자재 테이블 (예: RAW_MATERIAL_MASTER, SUBSTANCE_MASTER 등)
      - 자재/부품 테이블 (예: MATERIAL_MASTER, PART_MASTER 등)
      - 협력사 테이블 (예: SUPPLIER_MASTER, VENDOR_MASTER 등)
      - 거점/위치 테이블 (예: SITE_MASTER, LOCATION_MASTER 등)
   
   1-2. 그룹화 컬럼 파악
      - type/category 컬럼 존재 여부 확인
      - 있으면: type별 그룹 태그 생성 (예: raw_material_type별)
      - 없으면: 개별 엔티티 태그 생성 또는 수동 분류
   
   1-3. 다국어 컬럼 확인
      - name_kor/name_eng 또는 name_local/name_global 등
      - 없으면: 번역 API 활용 또는 단일 언어 운영

[2단계] 태그 생성 전략 수립
   
   2-1. 세분화 수준 결정
      - 개별 엔티티 태그: 각 레코드 = 1개 태그 (예: 협력사별)
      - 그룹 태그: type/category별 = 1개 태그 (예: 소재 유형별)
      - 혼합: 테이블별로 다른 전략 적용
   
   2-2. target_region 분리 기준 설정
      - 국내/글로벌 파이프라인 분리 필요 여부 판단
      - 필요 시: KR/GLOBAL 레코드 분리
      - 불필요 시: 단일 레코드 유지
   
   2-3. EVENT 태그 정의
      - DB에 대응 엔티티가 없는 현상/이벤트 추출
      - 키워드셋 또는 리스크 요인 기반으로 생성

[3단계] 키워드 추출 및 확장
   
   3-1. DB 자동 추출
      - 엔티티명: name_kor, name_eng, abbreviation 등
      - type/category명: raw_material_type, material_type 등
      
   3-2. 동의어 생성 규칙
      - 기본형 + 수식어: "{name} 소재", "{name} 공급", "반도체 {name}"
      - 회사명 변형: 전체명 → 약어, 부분명 (예: "한화정밀화학" → "한화")
      - 언어별 변형: 한영 표기 차이 (예: "ASML" / "에이에스엠엘")
   
   3-3. 외부 키워드셋 병합 (선택)
      - 기존 리스크 키워드셋이 있는 경우
      - 관련 키워드를 태그에 매핑

[4단계] target_region 분리 (선택)
   
   IF 국내/글로벌 파이프라인 분리:
      - 키워드를 언어별로 분류 (is_korean() 함수 활용)
      - 1개 태그 → 2개 레코드 생성
      - KR: name_kor + 한국어 keywords + description_kor
      - GLOBAL: name_eng + 영어 keywords + description_eng
   ELSE:
      - 단일 레코드 유지
      - name, keywords에 다국어 혼재 가능

[5단계] 메타데이터 생성
   
   필수 필드:
      - tag_id: 영문 고유 식별자 (prefix + name)
      - tag_type: 엔티티 유형 (RAW_MATERIAL, MATERIAL, SUPPLIER, SITE, EVENT)
      - name: 표시명 (target_region 있으면 언어별)
      - keywords: 매칭용 키워드 리스트
      - keyword_count: 키워드 개수
   
   선택 필드:
      - target_region: 'KR' 또는 'GLOBAL' (파이프라인 분리 시)
      - description: 임베딩용 설명
      - target_table_column: DB 매핑 정보
      - db_matched_count: 매칭된 엔티티 개수
      - domain, risk_factor: 분류 정보

[6단계] 검증 및 저장
   
   6-1. 품질 검증
      - tag_id 유일성 (target_region별)
      - 필수 필드 완결성
      - 키워드 비중복 (같은 region 내)
   
   6-2. 출력 형식
      - JSON: 파이프라인 직접 사용
      - CSV: 검토 및 수동 편집용
      - Simple/Detail 버전 제공
```

#### 5.4.3 현재 구현 예시 (반도체 공급망 DB)

**적용 DB**: RAW_MATERIAL_MASTER, MATERIAL_MASTER, SUPPLIER_MASTER, SITE_MASTER

| 단계 | 실제 적용 내용 |
|------|----------------|
| 1. DB 분석 | - 4개 마스터 테이블 식별<br>- raw_material_type, material_type 그룹 컬럼 확인<br>- name_kor/name_eng 다국어 컬럼 확인 |
| 2. 전략 수립 | - RAW_MATERIAL/MATERIAL: type별 그룹 태그 (10개 + 23개)<br>- SUPPLIER: 개별 엔티티 태그 (123개)<br>- SITE: 국가별 그룹 태그 (8개)<br>- EVENT: 키워드셋 기반 (60개)<br>- target_region: KR/GLOBAL 분리 |
| 3. 키워드 추출 | - DB 자동: 소재명, 자재명, 협력사명<br>- 동의어: "특수가스 소재", "한화정밀"<br>- 키워드셋: 148개 레코드 병합 |
| 4. 분리 | - 1개 태그 → 2개 레코드<br>- 총 224개 태그 → 448개 레코드 |
| 5. 메타데이터 | - target_table_column: "RAW_MATERIAL_MASTER.raw_material_type = '특수가스'"<br>- db_matched_count: 각 type의 엔티티 개수 |
| 6. 검증 | - tag_id 유일성: ✓<br>- 필수 필드: ✓<br>- 키워드 중복: 제거 완료 |

**생성 결과**:
- 총 레코드: 448개 (KR 224개 + GLOBAL 224개)
- 총 키워드: 2,620개
- DB 매칭: 164개 엔티티 태그 100% 매칭

#### 5.4.3 태그 유형 판별 프롬프트 예시

```
당신은 공급망 리스크 분석을 위한 태그 분류 전문가입니다.
다음 keyword_group_name을 RAW_MATERIAL/MATERIAL/SUPPLIER/SITE/EVENT 중 하나로 분류하세요.

DB 스키마:
- RAW_MATERIAL_MASTER (소재 - 원소재, 태그 유형: RAW_MATERIAL): name_kor, name_eng 
  예: "네온", "Neon", "희토류", "Rare Earth", "아르곤", "텅스텐"
- MATERIAL_MASTER (자재 - 소재를 포함하는 상위 개념): name_kor, name_eng, material_type
  예: "MLCC", "포토레지스트", "텅스텐 타겟", "ArF PR", "웨이퍼"
- SUPPLIER_MASTER (협력사): supplier_code, name_kor, name_eng
  예: "ASML", "JSR", "TOK", "Lam Research"
- SITE_MASTER (위치): country, region
  예: "South Korea", "China", "Taiwan", "경기도", "청주"

분류 기준:
1. 원소재(원소, 가스, 금속, 화합물) → RAW_MATERIAL
2. 자재/부품/완제품 → MATERIAL (RAW_MATERIAL를 포함하는 상위 개념)
3. 협력사명 → SUPPLIER
4. 국가/지역명 → SITE
5. 위 모두 아님 (규제, 현상, 사건) → EVENT (검색 전략 힌트 제공)

keyword_group_name: "수출규제"
출력:
{
  "tag_type": "EVENT",
  "reason": "수출규제는 현상/정책이며 DB 엔티티에 직접 대응하지 않음",
  "search_strategy": "규제 대상 RAW_MATERIAL/MATERIAL + 규제 지역 SITE를 결합하여 영향받는 SUPPLIER 추적"
}

keyword_group_name: "희토류"
출력:
{
  "tag_type": "RAW_MATERIAL",
  "reason": "희토류는 원소재 카테고리",
  "target_table_column": "RAW_MATERIAL_MASTER.name_kor",
  "search_strategy": "RAW_MATERIAL → MATERIAL_RAW_MATERIAL_MAP → MATERIAL → SITE_MATERIAL_MAP → SITE → SUPPLIER 경로로 확장"
}
```

#### 5.4.4 실제 태그 분포 (DB 엔티티 기반)

| 태그 유형 | 생성 개수 | 비율 | 예시 | 생성 기준 |
|-----------|-----------|------|------|----------|
| RAW_MATERIAL | 10개 | 4.5% | 특수가스, 반도체금속, 유기용제, 에천트 | raw_material_type별 그룹 |
| MATERIAL | 23개 | 10.3% | PVD 타겟, 패키지 기판, 몰딩 컴파운드, 본딩 와이어 | material_type별 그룹 |
| SUPPLIER | 123개 | 54.9% | 한화정밀화학, 덕산화학, 솔루스첨단소재 (한국 61개, 해외 62개) | 개별 협력사 |
| SITE | 8개 | 3.6% | 한국, 일본, 미국, 대만, 독일, 중국, 싱가포르, 카타르 | 국가별 |
| EVENT | 60개 | 26.8% | 수출규제, Entity List, 항만 파업, 관세, 제재, 지진 | 키워드셋 기반 |

**총 생성 태그**: 224개
**총 레코드**: 448개 (각 태그당 KR/GLOBAL 2행으로 분리)

**계층 예시**:
- RAW_MATERIAL "아르곤" ⊂ MATERIAL "아르곤 가스 (99.999%)"
- RAW_MATERIAL "텅스텐" ⊂ MATERIAL "텅스텐 타겟"
- RAW_MATERIAL "폴리머", "PGMEA" ⊂ MATERIAL "ArF 포토레지스트"

---

## 6. 표준 출력 구조 (Tag Schema)

태그는 **target_region** 기준으로 분리되어 저장됩니다.
**1개 태그 = 2개 레코드** (KR + GLOBAL)

### RAW_MATERIAL 태그 예시

**KR 레코드** (국내 뉴스 파이프라인용):
```json
{
  "tag_id": "RAW_SPECIAL_GAS",
  "target_region": "KR",
  "tag_type": "RAW_MATERIAL",
  "name": "특수가스",
  "description": "아르곤, 네온, 크립톤, 크세논, NF3, SF6, WF6 등 반도체 제조 공정에 사용되는 특수가스...",
  "keywords": ["특수가스", "아르곤", "네온", "크립톤", "NF3", ...],
  "keyword_count": 30,
  "domain": "원자재&희소물질",
  "risk_factor": "특수가스 수급 리스크",
  "target_table_column": "RAW_MATERIAL_MASTER.raw_material_type = '특수가스'",
  "db_matched_count": 23
}
```

**GLOBAL 레코드** (글로벌 뉴스 파이프라인용):
```json
{
  "tag_id": "RAW_SPECIAL_GAS",
  "target_region": "GLOBAL",
  "tag_type": "RAW_MATERIAL",
  "name": "Special Gas",
  "description": "Semiconductor manufacturing special gases including argon, neon, krypton, xenon, NF3, SF6, WF6...",
  "keywords": ["special gas", "argon", "neon", "krypton", "NF3", ...],
  "keyword_count": 35,
  "domain": "원자재&희소물질",
  "risk_factor": "특수가스 수급 리스크",
  "target_table_column": "RAW_MATERIAL_MASTER.raw_material_type = '특수가스'",
  "db_matched_count": 23
}
```

### EVENT 태그 예시

**KR 레코드**:
```json
{
  "tag_id": "EVT_EXPORT_CTRL",
  "target_region": "KR",
  "tag_type": "EVENT",
  "name": "수출규제",
  "description": "반도체 관련 수출 통제 및 규제 조치...",
  "keywords": ["수출규제", "수출통제", "반도체 규제", ...],
  "keyword_count": 5,
  "domain": "지정학",
  "risk_factor": "무역 규제 리스크",
  "target_table_column": null,
  "db_matched_count": 0
}
```

**GLOBAL 레코드**:
```json
{
  "tag_id": "EVT_EXPORT_CTRL",
  "target_region": "GLOBAL",
  "tag_type": "EVENT",
  "name": "Export Control",
  "description": "Semiconductor export control and regulatory measures...",
  "keywords": ["export control", "export restriction", "semiconductor regulation", ...],
  "keyword_count": 6,
  "domain": "지정학",
  "risk_factor": "무역 규제 리스크",
  "target_table_column": null,
  "db_matched_count": 0
}
```

### 파이프라인 활용

**국내 뉴스 파이프라인**:
```python
kr_tags = tags[tags['target_region'] == 'KR']
# 한국어 키워드만 매칭
```

**글로벌 뉴스 파이프라인**:
```python
global_tags = tags[tags['target_region'] == 'GLOBAL']
# 영어 키워드만 매칭
```

### 출력 파일

- **JSON**: `data/TAG/DB_TAG_Generated_Tags.json` (448개 레코드)
- **CSV**: 
  - `DB_TAG_Generated_Tags.csv` (메인, 11개 컬럼)
  - `DB_TAG_Generated_Tags_simple.csv` (간단, 6개 컬럼)
  - `DB_TAG_Generated_Tags_detail.csv` (상세, keywords_full 포함)

---

## 7. 예시 세트 (대분류 > Risk Factor > 태그 > 키워드)

### 7.1 일반 예시 (개념 설명용)

| 대분류 | Risk Factor | 태그 | 유형 | 키워드 | 대응 테이블.컬럼 | 검색 전략 |
|---|---|---|---|---|---|---|
| 원자재 | 원자재 수급 리스크 | AR | RAW_MATERIAL | 아르곤, Argon, 아르곤가스 | RAW_MATERIAL_MASTER.name_kor | RAW_MATERIAL → MATERIAL → SITE → SUPPLIER 확장 |
| 원자재 | 원자재 수급 리스크 | REE | RAW_MATERIAL | 희토류, Rare Earth | RAW_MATERIAL_MASTER.name_eng | RAW_MATERIAL → MATERIAL → SITE → SUPPLIER 확장 |
| 원자재 | 핵심부품 단종/공급 리스크 | MLCC | MATERIAL | MLCC, 적층세라믹콘덴서 | MATERIAL_MASTER.material_type | MATERIAL → SITE → SUPPLIER 확장 |
| 협력사 | 협력사 재무/경영 리스크 | ASML | SUPPLIER | ASML | SUPPLIER_MASTER.name_eng | 단독 조회 또는 SITE로 확장 |
| 지역 | 지정학·물류 리스크 | CHINA | SITE | 중국, China | SITE_MASTER.country | 단독 조회 또는 EVENT 결합 조건으로 사용 |
| 지정학 | 무역 규제 리스크 | EXPORT_CTRL_CN | EVENT | 중국 수출통제, China export control | 없음 | RAW_MATERIAL/MATERIAL + SITE(China) 결합 전략 힌트 |
| 물류 | 운송·물류 차질 리스크 | PORT_STRIKE | EVENT | 항만 파업, dock strike | 없음 | SITE(항만) 중심으로 MATERIAL → SUPPLIER 역추적 |
| 자연재해 | 생산시설 가동중단 리스크 | TAIWAN_EQ | EVENT | 대만 지진, Taiwan earthquake | 없음 | SITE(Taiwan) 중심으로 영향 범위 추적 |

### 7.2 실제 키워드셋 기반 예시

본 프로젝트의 154개 키워드 레코드에서 추출한 실제 예시:

| Risk Factor | Keyword Group (원본) | 추출 키워드 샘플 | 태그 유형 | 생성된 태그 | 대응 테이블.컬럼 | 검색 전략 |
|-------------|---------------------|------------------|-----------|-------------|------------------|----------|
| 수출입규제 | ECCN | ECCN, 반도체, 수출, BIS, CCL | EVENT | EXPORT_CTRL_ECCN | 없음 | RAW_MATERIAL/MATERIAL + SITE 결합 전략 |
| 수출입규제 | 수출규제 | 수출규제, 반도체, 장비, 중국 | EVENT | EXPORT_CONTROL | 없음 | RAW_MATERIAL/MATERIAL + SITE 결합 전략 |
| 희토류 공급 | 희토류 | 희토류, Rare Earth, REE | RAW_MATERIAL | REE | RAW_MATERIAL_MASTER.name_kor | RAW_MATERIAL → MATERIAL → SITE → SUPPLIER |
| 네온, 크립톤, 크세논 | 네온 | 네온, Neon, Ne | RAW_MATERIAL | NEON | RAW_MATERIAL_MASTER.name_eng | RAW_MATERIAL → MATERIAL → SITE → SUPPLIER |
| 소재 단일 공급 | 포토레지스트 | 포토레지스트, photoresist, PR | MATERIAL | PHOTORESIST | MATERIAL_MASTER.material_type | MATERIAL → SITE → SUPPLIER |
| 장비 독과점 | ASML | ASML, EUV, 노광장비 | SUPPLIER | ASML | SUPPLIER_MASTER.name_eng | 단독 조회 또는 SITE로 확장 |
| 장비 독과점 | Lam Research | Lam Research, LAM, 에칭장비 | SUPPLIER | LAM_RESEARCH | SUPPLIER_MASTER.name_eng | 단독 조회 또는 SITE로 확장 |
| 지역 집중 | 중국 | 중국, China | SITE | CHINA | SITE_MASTER.country | 단독 조회 또는 EVENT 결합 조건 |
| 지역 집중 | 대만 | 대만, Taiwan | SITE | TAIWAN | SITE_MASTER.country | 단독 조회 또는 EVENT 결합 조건 |
| 기업제재 | Entity List | Entity List, BIS, 제재 | EVENT | ENTITY_LIST | 없음 | SUPPLIER + SITE 결합 전략 |
| 항만 혼잡 | 항만혼잡 | 항만 혼잡, port congestion | EVENT | PORT_CONGESTION | 없음 | SITE(항만) → MATERIAL → SUPPLIER |
| 화물 운송 파업 | 파업 | 파업, strike, 운송중단 | EVENT | LOGISTICS_STRIKE | 없음 | SITE → MATERIAL → SUPPLIER |

**태그 생성 후 통계** (실제):
- 총 키워드 레코드: 148개 (KR 76개 + GLOBAL 72개)
- 생성된 태그: 224개 (DB 엔티티 기반)
- target_region 분리: 448개 레코드 (각 태그당 KR/GLOBAL 2행)
- 태그 유형 분포: RAW_MATERIAL 4.5%, MATERIAL 10.3%, SUPPLIER 54.9%, SITE 3.6%, EVENT 26.8%
- 총 키워드: 2,620개 (KR 1,849개 + GLOBAL 771개)

---

## 8. 신규 DB 적용 가이드

새로운 공급망 DB에 태그 생성을 적용할 때 참고할 가이드입니다.

### 8.1 사전 준비

**1. DB 스키마 문서화**
```sql
-- 마스터 테이블 구조 파악
DESCRIBE raw_material_master;  -- 또는 해당 DB의 테이블명
DESCRIBE material_master;
DESCRIBE supplier_master;
DESCRIBE site_master;

-- 주요 컬럼 확인사항
-- ✓ name_kor/name_eng 존재 여부
-- ✓ type/category 그룹 컬럼 존재 여부
-- ✓ 다국어 지원 여부
-- ✓ 매핑 테이블 구조 (N:M 관계)
```

**2. 태그 생성 범위 결정**
- 전체 엔티티 vs 주요 엔티티만
- 그룹 태그 vs 개별 태그
- target_region 분리 필요 여부

**3. 키워드셋 준비 (선택)**
- 기존 리스크 요인 키워드가 있는 경우
- 뉴스 추출 키워드가 있는 경우

### 8.2 스크립트 재사용 방법

**현재 구현 스크립트 위치**: `poc-a/temp/`

재사용 가능한 스크립트:

1. **`analyze_db_for_tags.py`** - DB 구조 분석
   - 수정 필요: DB 경로, 테이블명
   - 출력: 엔티티 개수, type 분포, 예상 태그 개수

2. **`generate_db_based_tags.py`** - 태그 생성
   - 수정 필요:
     ```python
     # DB 경로
     conn = sqlite3.connect('../data/SUPPLY_CHAIN/supply_chain.db')
     
     # 테이블명 및 컬럼명
     cursor.execute("""
         SELECT raw_material_type, ...
         FROM RAW_MATERIAL_MASTER  -- 여기를 새 테이블명으로
         GROUP BY raw_material_type
     """)
     
     # tag_id 매핑 (영문명 수동 정의)
     type_eng_map = {
         '특수가스': 'SPECIAL_GAS',  -- DB type → 영문 tag_id
         ...
     }
     ```

3. **`expand_keywords.py`** - 키워드 확장
   - 수정 필요: 키워드셋 파일 경로
   - 선택 사용: 키워드셋이 없으면 스킵 가능

4. **`boost_supplier_keywords.py`** - 협력사 키워드 확장
   - 수정 필요: 업종 추론 규칙
     ```python
     # 화학 관련
     if any(x in name_kor for x in ['화학', '케미칼']):
         keywords.extend(['화학', '화학소재'])
     
     # 신규 업종 추가
     if any(x in name_kor for x in ['전자', '일렉트로닉스']):
         keywords.extend(['전자부품', '전자소재'])
     ```

5. **`split_by_region.py`** - target_region 분리
   - 수정 불필요 (언어 자동 감지)
   - 선택 사용: 파이프라인 분리가 필요한 경우만

6. **`validate_tags.py`** - 검증
   - 수정 불필요 (범용)

### 8.3 실행 순서

```bash
# 1. DB 분석
python analyze_db_for_tags.py

# 2. 태그 생성 (DB 기반)
python generate_db_based_tags.py
# → DB_TAG_Generated_Tags_v2.json 생성

# 3. 키워드 확장 (선택)
python expand_keywords.py

# 4. 협력사 키워드 부스트 (선택)
python boost_supplier_keywords.py

# 5. target_region 분리 (선택)
python split_by_region.py

# 6. 검증
python validate_tags.py

# 7. CSV 생성
python generate_csv.py
```

### 8.4 커스터마이징 체크리스트

신규 DB 적용 시 수정해야 할 사항:

- [ ] DB 경로 변경
- [ ] 테이블명 변경 (RAW_MATERIAL_MASTER → ?)
- [ ] 컬럼명 변경 (raw_material_type → ?)
- [ ] 다국어 컬럼명 확인 (name_kor/name_eng → ?)
- [ ] tag_id 영문 매핑 정의 (type → 영문명)
- [ ] 태그 유형 분류 기준 조정 (RAW_MATERIAL/MATERIAL 구분 등)
- [ ] 협력사 업종 추론 규칙 추가
- [ ] target_region 분리 필요 여부 결정

### 8.5 예상 산출물

**JSON**:
- 통합 버전: `DB_TAG_Generated_Tags.json` (N개 태그)
- 분리 버전: `DB_TAG_Generated_Tags_split.json` (2N개 레코드)

**CSV**:
- 메인: 11개 컬럼 (tag_id, target_region, name, keywords, ...)
- Simple: 6개 컬럼 (빠른 확인용)
- Detail: keywords_full 포함 (전체 키워드)

**예상 처리 시간**:
- DB 분석: ~1초
- 태그 생성: ~5-10초 (엔티티 개수에 비례)
- 키워드 확장: ~10-30초
- target_region 분리: ~1초

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-06-24 (이전) | 초기 버전 작성 (뉴스 기반 태그 생성 방법론) |
| 2.0 | 2026-06-24 | **DB 스키마 정합성 업데이트 (v1)**<br>- PART 유형 제거, MATERIAL 유형으로 통합<br>- 실제 DB 컬럼명 수정<br>- 5.4절 추가: "Risk Factor 기반 키워드셋에서 태그 생성"<br>- 7.2절 추가: 실제 키워드셋(154개) 기반 예시<br>- 태그 유형 5가지 → 4가지로 단순화 |
| 2.1 | 2026-06-25 | **소재/자재 구분 복원 및 EVENT 역할 재정의**<br>- SUBSTANCE(소재) / MATERIAL(자재) 유형 분리 (자재가 상위 개념)<br>- 태그 유형 4가지 → 5가지로 복원<br>- EVENT 태그 역할: "WHERE/JOIN 불가" → "검색 전략 힌트 제공"으로 재정의<br>- 3.1절: EVENT 태그 SQL 생성 예시 추가 (대만 지진, 중국 희토류 수출규제)<br>- 계층 구조 명시: MATERIAL ⊃ SUBSTANCE (자재가 소재를 포함)<br>- 5.4.3절: 태그 유형 판별 프롬프트에 SUBSTANCE/MATERIAL 구분 기준 추가<br>- 6장, 7장: 모든 예시에 search_strategy 필드 추가 |
| 2.2 | 2026-06-25 | **뉴스 매핑 파이프라인 분리**<br>- 5.1절: 뉴스 기반 파이프라인을 참고용으로 축소, 새 문서로 링크 추가<br>- 신규 문서 생성: [DB_TAG_News Mapping Pipeline.md](./DB_TAG_News%20Mapping%20Pipeline.md)<br>  · 하이브리드 태그 추출 방식 (정확 매칭 + NER + LLM)<br>  · 신규 표현 자동 처리 정책 (자동 우선, 매핑 실패 시만 Human-in-the-loop)<br>  · 고위험 패턴 감지 메커니즘<br>  · Text-to-SQL 생성 가이드<br>- 역할 분리: 본 문서는 "태그 설계", 새 문서는 "태그 활용" 담당 |
| 2.3 | 2026-06-26 | **DB 엔티티 기반 태그 생성 완료 및 target_region 분리 (최종)**<br>- 소재 태그 유형 변경: SUBSTANCE → RAW_MATERIAL<br>- DB 테이블명 변경: SUBSTANCE_MASTER → RAW_MATERIAL_MASTER<br>- **태그 생성 방식**: DB 엔티티 기반 (키워드셋 군집화 방식 폐기)<br>  · RAW_MATERIAL: raw_material_type별 10개<br>  · MATERIAL: material_type별 23개<br>  · SUPPLIER: 개별 협력사 123개<br>  · SITE: 국가별 8개<br>  · EVENT: 키워드셋 기반 60개<br>- **target_region 분리**: 1개 태그 → 2개 레코드 (KR/GLOBAL)<br>  · 총 224개 태그 → 448개 레코드<br>  · KR: 한국어 name + keywords + description (국내 파이프라인용)<br>  · GLOBAL: 영어 name + keywords + description (글로벌 파이프라인용)<br>- 키워드 통계: 총 2,620개 (KR 1,849개, GLOBAL 771개)<br>- DB 매칭: 164개 엔티티 태그 100% 매칭 (880개 DB 엔티티)<br>- 출력 파일:<br>  · JSON: DB_TAG_Generated_Tags.json (448개 레코드)<br>  · CSV: 3종 (메인 11컬럼, simple 6컬럼, detail 전체 키워드) |

---

## 10. 참조

### 관련 문서
- **[DB_TAG_News Mapping Pipeline.md](./DB_TAG_News%20Mapping%20Pipeline.md)**: 태그 활용 파이프라인 (뉴스 매핑, Text-to-SQL)
- **[DB_TAG_Keyword Docs.md](./DB_TAG_Keyword%20Docs.md)**: 키워드셋 문서

### 출력 파일 위치
- **JSON**: `data/TAG/DB_TAG_Generated_Tags.json`
- **CSV**: `data/TAG/DB_TAG_Generated_Tags.csv` (+ simple, detail)
- **스크립트**: `temp/generate_db_based_tags.py` 외 6개

### 주요 스크립트
| 스크립트 | 용도 | 재사용 가능 |
|----------|------|-------------|
| `analyze_db_for_tags.py` | DB 구조 분석 | ✓ (경로/테이블명만 수정) |
| `generate_db_based_tags.py` | 태그 생성 | ✓ (컬럼명, tag_id 매핑 수정) |
| `expand_keywords.py` | 키워드 확장 | ✓ (키워드셋 경로 수정) |
| `boost_supplier_keywords.py` | 협력사 키워드 부스트 | ✓ (업종 규칙 추가) |
| `split_by_region.py` | target_region 분리 | ✓ (수정 불필요) |
| `validate_tags.py` | 품질 검증 | ✓ (범용) |
| `generate_csv.py` | CSV 생성 | ✓ (수정 불필요) |

---

*본 문서는 LLM 기반 태그 자동 생성 파이프라인 구축 및 신규 DB 적용을 위한 설계 가이드라인입니다.*
