# 공급망 DB (SUPPLYMAP) 설계 문서

## 1. 개요

### 목적
삼성전자 DS 반도체 공급망의 협력사, 생산지, 자재, 소재 관계를 체계적으로 관리하고, 공급망 리스크 분석을 지원하기 위한 정규화된 관계형 데이터베이스입니다.

### 주요 특징
- **정규화된 구조**: 마스터 테이블과 매핑 테이블 명확 분리
- **다중 생산지 지원**: 동일 자재가 여러 지역에서 생산되는 케이스 표현 (리스크 분석용)
- **SQLite 기반**: 경량화되어 PoC 및 로컬 분석에 최적화

### 데이터 규모
- 협력사: 120개
- 생산지: 250개
- 자재: 400개
- 소재: 114개

---

## 2. 테이블 구조

### 2.1 마스터 테이블 (4개)

#### SUPPLIER_MASTER (협력사 마스터)
협력사(법인) 기본 정보를 관리하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 (자동 증가) |
| supplier_code | TEXT | UNIQUE NOT NULL | 협력사 코드 (예: KR0001, JP0001) |
| name_kor | TEXT | NOT NULL | 업체명(한글) |
| name_eng | TEXT | NOT NULL | 업체명(영문) |
| abbreviation_kor | TEXT | | 약어(한글) |
| abbreviation_eng | TEXT | | 약어(영문) |
| business_id | TEXT | | 기업식별코드 (사업자번호 등) |
| country | TEXT | | 국가/지역 (예: South Korea, Japan, United States) |
| region | TEXT | | 행정구역 (예: 경기도, Osaka, California) |
| address | TEXT | | 주소 |
| latitude | REAL | | 위도 |
| longitude | REAL | | 경도 |
| is_active | INTEGER | DEFAULT 1 | 활성여부 (1: 활성, 0: 비활성) |
| created_at | TEXT | NOT NULL | 생성일시 (ISO8601 형식) |
| updated_at | TEXT | NOT NULL | 수정일시 (ISO8601 형식) |

**인덱스:**
- `idx_supplier_code` ON supplier_code
- `idx_supplier_country` ON country

**코드 생성 규칙:**
- 형식: 국가코드(2자) + 순번(4자리 숫자)
- 예: KR0001, JP0012, US0003

---

#### SITE_MASTER (생산지 마스터)
협력사 산하 생산 거점(Site, Plant, 창고 등) 정보를 관리하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 |
| site_code | TEXT | UNIQUE NOT NULL | Site 코드 (예: S00001) |
| supplier_code | TEXT | NOT NULL, FK | 협력사 코드 → SUPPLIER_MASTER.supplier_code |
| name | TEXT | NOT NULL | 생산지명 (예: "OO Plant 1", "OO 청주공장") |
| country | TEXT | | 국가/지역 (협력사 본사와 다를 수 있음) |
| region | TEXT | | 행정구역 |
| address | TEXT | | 주소 |
| latitude | REAL | | 위도 |
| longitude | REAL | | 경도 |
| is_supplier_registered | INTEGER | DEFAULT 0 | 협력사 등록 여부 |
| is_factory | INTEGER | DEFAULT 0 | Factory Information 여부 |
| is_supply_tree | INTEGER | DEFAULT 0 | Supply Tree 여부 |
| is_original_maker | INTEGER | DEFAULT 0 | 원 메이커 여부 |
| is_active | INTEGER | DEFAULT 1 | 활성여부 |
| created_at | TEXT | NOT NULL | 생성일시 |
| updated_at | TEXT | NOT NULL | 수정일시 |

**인덱스:**
- `idx_site_code` ON site_code
- `idx_site_supplier` ON supplier_code
- `idx_site_country` ON country

**코드 생성 규칙:**
- 형식: S + 5자리 숫자
- 예: S00001, S00253

**주요 특징:**
- 1개 협력사는 1~3개 Site를 가짐 (평균 2개)
- 협력사 본사와 동일 국가: 60%, 해외 생산기지: 40%

---

#### MATERIAL_MASTER (자재 마스터)
반도체 제조에 사용되는 자재 정보를 관리하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 |
| material_code | TEXT | UNIQUE NOT NULL | 자재 코드 (예: MAT00001) |
| name_kor | TEXT | NOT NULL | 자재명(한글) |
| name_eng | TEXT | NOT NULL | 자재명(영문) |
| material_type | TEXT | | 자재유형 (예: 웨이퍼, 포토레지스트, 타겟, 패키지기판) |
| is_active | INTEGER | DEFAULT 1 | 활성여부 |
| created_at | TEXT | NOT NULL | 생성일시 |
| updated_at | TEXT | NOT NULL | 수정일시 |

**인덱스:**
- `idx_material_code` ON material_code
- `idx_material_type` ON material_type

**코드 생성 규칙:**
- 형식: MAT + 5자리 숫자
- 예: MAT00001, MAT00512

**자재 분류 (반도체 공정별):**
- **전공정 자재 (60%)**:
  - 웨이퍼: 실리콘 웨이퍼, SOI 웨이퍼, SiC 웨이퍼
  - 포토: 포토마스크, 레티클, 포토레지스트
  - 박막: PVD 타겟, CVD 전구체, ALD 전구체
  - CMP: 슬러리, 패드, 컨디셔너
  - 세정: 에천트, 린스액, 세정액
- **후공정 자재 (40%)**:
  - 리드프레임
  - 패키지 기판 (BGA, CSP, QFN)
  - 본딩 와이어 (Au, Cu, Ag)
  - 다이 어태치 필름
  - 몰딩 컴파운드
  - 언더필, 접착제
  - 테스트 소켓

---

#### SUBSTANCE_MASTER (소재 마스터)
자재를 구성하는 원소재 정보를 관리하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 |
| substance_code | TEXT | UNIQUE NOT NULL | 소재 코드 (예: SUB00001) |
| name_kor | TEXT | NOT NULL | 소재명(한글) |
| name_eng | TEXT | NOT NULL | 소재명(영문) |
| substance_type | TEXT | | 소재 유형 (예: 특수가스, 에천트, 반도체금속, 포토레지스트) |
| is_active | INTEGER | DEFAULT 1 | 활성여부 |
| created_at | TEXT | NOT NULL | 생성일시 |
| updated_at | TEXT | NOT NULL | 수정일시 |

**인덱스:**
- `idx_substance_code` ON substance_code
- `idx_substance_type` ON substance_type

**코드 생성 규칙:**
- 형식: SUB + 5자리 숫자
- 예: SUB00001, SUB00089

**소재 분류:**
- **특수가스**: 헬륨(He), 네온(Ne), 아르곤(Ar), NF₃, SF₆, NH₃
- **에천트**: HF, HCl, H₂SO₄, HNO₃, NH₄OH, H₂O₂
- **반도체금속**: 텅스텐(W), 티타늄(Ti), 구리(Cu), 알루미늄(Al), 금(Au)
- **포토레지스트**: ArF PR, KrF PR, i-line PR, EUV PR
- **유기용제**: PGMEA, PGME, IPA, 아세톤
- **연마재**: 실리카, 세리아, 알루미나
- **폴리머**: 폴리이미드, 에폭시, 실리콘

---

### 2.2 매핑 테이블 (3개)

#### SITE_MATERIAL_MAP (생산지-자재 매핑)
어느 생산지(Site)가 어느 자재를 공급하는지를 매핑하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 |
| mapping_id | TEXT | UNIQUE NOT NULL | 매핑 ID (예: SM-00001) |
| site_code | TEXT | NOT NULL, FK | Site 코드 → SITE_MASTER.site_code |
| material_code | TEXT | NOT NULL, FK | 자재 코드 → MATERIAL_MASTER.material_code |
| supply_ratio | REAL | | 공급 비중(%) - 0~100 사이 값 |
| is_main_supplier | INTEGER | DEFAULT 0 | 주공급여부 (1: 주공급, 0: 부공급) |
| is_active | INTEGER | DEFAULT 1 | 활성여부 |
| created_at | TEXT | NOT NULL | 생성일시 |
| updated_at | TEXT | NOT NULL | 수정일시 |

**인덱스:**
- `idx_sitematmap_mapping` ON mapping_id
- `idx_sitematmap_site` ON site_code
- `idx_sitematmap_material` ON material_code

**코드 생성 규칙:**
- 형식: SM-{5자리 숫자}
- 예: SM-00001, SM-12345

**중요 특징:**
- **동일 자재가 여러 Site에서 생산되는 케이스를 30% 이상 포함**
- 예: material_code 'MAT00001'이 site_code 'S00012' (한국)와 'S00045' (일본)에서 각각 생산
- 리스크 분석 시나리오: "한국 공장이 멈추면 일본 공장에서 대체 공급 가능한가?"
- supply_ratio는 동일 자재를 공급하는 모든 Site의 합이 ~100%가 되도록 조정

---

#### MATERIAL_SUBSTANCE_MAP (자재-소재 매핑)
어느 자재가 어느 소재를 포함하는지를 매핑하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 |
| mapping_id | TEXT | UNIQUE NOT NULL | 매핑 ID (예: MS-00001) |
| material_code | TEXT | NOT NULL, FK | 자재 코드 → MATERIAL_MASTER.material_code |
| substance_code | TEXT | NOT NULL, FK | 소재 코드 → SUBSTANCE_MASTER.substance_code |
| inclusion_ratio | REAL | | 포함 비중(%) - 해당 자재 내 소재의 비중 |
| is_included | INTEGER | DEFAULT 1 | 포함여부 (비중 정보가 없을 경우 최소한 포함 여부는 표시) |
| is_active | INTEGER | DEFAULT 1 | 활성여부 |
| created_at | TEXT | NOT NULL | 생성일시 |
| updated_at | TEXT | NOT NULL | 수정일시 |

**인덱스:**
- `idx_matsubmap_mapping` ON mapping_id
- `idx_matsubmap_material` ON material_code
- `idx_matsubmap_substance` ON substance_code

**코드 생성 규칙:**
- 형식: MS-{5자리 숫자}
- 예: MS-00001, MS-45678

**매핑 예시:**
- 자재 "ArF 포토레지스트" → 소재 ["폴리머", "PGMEA", "광산발생제", "첨가제"]
- 자재 "텅스텐 타겟" → 소재 ["텅스텐(W)", "티타늄(Ti)", "질소(N₂)"]
- 자재 "CMP 슬러리" → 소재 ["실리카", "세리아", "과산화수소", "계면활성제"]

**특징:**
- 1개 자재당 평균 2~5개 소재 포함
- inclusion_ratio는 주요 소재 위주로 기재 (전체 합 ~100%)

---

#### SUPPLIER_SUBSTANCE_MAP (협력사-소재 매핑)
어느 협력사가 어느 소재를 공급하는지를 매핑하는 테이블입니다.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| no | INTEGER | PRIMARY KEY | 순번 |
| mapping_id | TEXT | UNIQUE NOT NULL | 매핑 ID (예: SS-00001) |
| supplier_code | TEXT | NOT NULL, FK | 협력사 코드 → SUPPLIER_MASTER.supplier_code |
| substance_code | TEXT | NOT NULL, FK | 소재 코드 → SUBSTANCE_MASTER.substance_code |
| is_active | INTEGER | DEFAULT 1 | 활성여부 |
| created_at | TEXT | NOT NULL | 생성일시 |
| updated_at | TEXT | NOT NULL | 수정일시 |

**인덱스:**
- `idx_supsubmap_mapping` ON mapping_id
- `idx_supsubmap_supplier` ON supplier_code
- `idx_supsubmap_substance` ON substance_code

**코드 생성 규칙:**
- 형식: SS-{5자리 숫자}
- 예: SS-00001, SS-23456

**특징:**
- 1개 협력사당 평균 3~10개 소재 공급
- srm.db의 materials.related_suppliers 정보 활용

---

## 3. 테이블 관계도

```
SUPPLIER_MASTER (1)
    ├─< (N) SITE_MASTER
    └─< (N) SUPPLIER_RAW_MATERIAL_MAP >─ (N) RAW_MATERIAL_MASTER

SITE_MASTER (N)
    └─< SITE_MATERIAL_MAP >─ (N) MATERIAL_MASTER

MATERIAL_MASTER (N)
    └─< MATERIAL_RAW_MATERIAL_MAP >─ (N) RAW_MATERIAL_MASTER
```

---

## 4. 데이터 생성 규칙

### 4.1 기존 데이터 활용 (srm.db)

**srm.db → SUPPLIER_MASTER 변환**
- srm.db의 partners 테이블 43개를 그대로 변환
- 매핑 규칙:
  - id → supplier_code (형식 변경: sp-001 → KR0001)
  - name → name_kor
  - nameEng → name_eng (빈 값은 name_kor를 영문 번역)
  - country → country
  - region → region
  - lat → latitude
  - lon → longitude
  - isActive → is_active
  - createdAt → created_at
  - updatedAt → updated_at

**srm.db → SUBSTANCE_MASTER 변환**
- srm.db의 materials 테이블 27개를 그대로 변환
- 매핑 규칙:
  - id → substance_code (형식 변경: MAT_HE_001 → SUB00001)
  - name_kor → name_kor
  - name_eng → name_eng
  - material_type → substance_type
  - created_at → created_at
  - updated_at → updated_at

### 4.2 데이터 생성 순서

**순서가 중요한 이유**: FK 무결성을 위해 참조되는 테이블을 먼저 생성해야 합니다.

```
1. SUPPLIER_MASTER (120개)
   → srm.db 43개 + 추가 생성 77개

2. SITE_MASTER (250개)
   → SUPPLIER_MASTER 참조 (supplier_code FK)
   → 각 협력사당 1~3개 Site 생성 (평균 2개)

3. SUBSTANCE_MASTER (114개)
   → srm.db 27개 + 추가 생성 87개

4. MATERIAL_MASTER (400개)
   → 반도체 공정별 자재 생성 (전공정 60%, 후공정 40%)

5. SUPPLIER_SUBSTANCE_MAP (789건)
   → SUPPLIER_MASTER와 SUBSTANCE_MASTER 참조
   → 각 협력사당 3~10개 소재 매핑

6. SITE_MATERIAL_MAP (625건)
   → SITE_MASTER와 MATERIAL_MASTER 참조
   → 동일 자재 다중 Site 매핑 30% 이상 포함

7. MATERIAL_SUBSTANCE_MAP (1,400건)
   → MATERIAL_MASTER와 SUBSTANCE_MASTER 참조
   → 각 자재당 2~5개 소재 포함
```

### 4.3 위도/경도 생성 규칙

국가별 실제 좌표 범위 내에서 무작위 생성:

| 국가 | 위도 범위 | 경도 범위 |
|------|-----------|-----------|
| South Korea | 33.0 ~ 38.6 | 124.6 ~ 131.9 |
| Japan | 24.0 ~ 45.5 | 122.9 ~ 153.9 |
| United States | 24.5 ~ 49.4 | -125.0 ~ -66.9 |
| Taiwan | 21.9 ~ 25.3 | 120.0 ~ 122.0 |
| China | 18.2 ~ 53.6 | 73.5 ~ 135.1 |
| Germany | 47.3 ~ 55.1 | 5.9 ~ 15.0 |

### 4.4 날짜 생성 규칙

- **created_at**: 2020-01-01 ~ 2025-12-31 사이 무작위 날짜
- **updated_at**: created_at 이후 날짜 (수정 이력이 있는 경우만)
- **매핑 테이블**: 참조하는 마스터 테이블의 created_at 이후 날짜

---

## 5. 데이터 무결성 검증

### 5.1 FK 무결성 (100%)
```sql
-- SITE_MASTER의 supplier_code가 SUPPLIER_MASTER에 존재하는지
SELECT COUNT(*) FROM SITE_MASTER s
WHERE NOT EXISTS (
    SELECT 1 FROM SUPPLIER_MASTER sup
    WHERE sup.supplier_code = s.supplier_code
);
-- 결과: 0건이어야 함

-- 매핑 테이블들도 동일하게 검증
```

### 5.2 동일 자재 다중 Site 매핑 (≥30%)
```sql
-- 2개 이상 Site에서 생산되는 자재 비율
SELECT 
    COUNT(DISTINCT CASE WHEN site_count > 1 THEN material_code END) * 100.0 / COUNT(DISTINCT material_code) as multi_site_ratio
FROM (
    SELECT material_code, COUNT(DISTINCT site_code) as site_count
    FROM SITE_MATERIAL_MAP
    GROUP BY material_code
);
-- 결과: ≥ 30%
```

### 5.3 supply_ratio 합계 검증
```sql
-- 동일 자재 기준 supply_ratio 합계가 95~105% 범위인지
SELECT material_code, SUM(supply_ratio) as total_ratio
FROM SITE_MATERIAL_MAP
WHERE supply_ratio IS NOT NULL
GROUP BY material_code
HAVING total_ratio < 95 OR total_ratio > 105;
-- 결과: 0건 또는 소수 건
```

---

## 6. 활용 시나리오

### 6.1 리스크 분석 쿼리

**동일 자재를 여러 국가에서 생산하는 케이스**
```sql
SELECT 
    m.material_code,
    m.name_kor,
    m.name_eng,
    GROUP_CONCAT(DISTINCT s.country) as countries,
    COUNT(DISTINCT sm.site_code) as site_count
FROM MATERIAL_MASTER m
JOIN SITE_MATERIAL_MAP sm ON m.material_code = sm.material_code
JOIN SITE_MASTER s ON sm.site_code = s.site_code
WHERE sm.is_active = 1
GROUP BY m.material_code
HAVING site_count > 1
ORDER BY site_count DESC;
```

**특정 국가 의존도가 높은 자재 추출**
```sql
SELECT 
    m.material_code,
    m.name_kor,
    s.country,
    SUM(sm.supply_ratio) as country_supply_ratio
FROM MATERIAL_MASTER m
JOIN SITE_MATERIAL_MAP sm ON m.material_code = sm.material_code
JOIN SITE_MASTER s ON sm.site_code = s.site_code
WHERE sm.is_active = 1
GROUP BY m.material_code, s.country
HAVING country_supply_ratio > 70
ORDER BY country_supply_ratio DESC;
```

**특정 소재가 포함된 자재 추적**
```sql
SELECT 
    m.material_code,
    m.name_kor,
    sub.name_kor as substance_name,
    msm.inclusion_ratio
FROM MATERIAL_MASTER m
JOIN MATERIAL_SUBSTANCE_MAP msm ON m.material_code = msm.material_code
JOIN SUBSTANCE_MASTER sub ON msm.substance_code = sub.substance_code
WHERE sub.name_eng LIKE '%Neon%'
ORDER BY msm.inclusion_ratio DESC;
```

### 6.2 공급망 추적 쿼리

**협력사 → Site → 자재 → 소재 전체 경로**
```sql
SELECT 
    sup.name_kor as supplier_name,
    s.name as site_name,
    s.country as site_country,
    m.name_kor as material_name,
    sub.name_kor as substance_name,
    sm.supply_ratio,
    msm.inclusion_ratio
FROM SUPPLIER_MASTER sup
JOIN SITE_MASTER s ON sup.supplier_code = s.supplier_code
JOIN SITE_MATERIAL_MAP sm ON s.site_code = sm.site_code
JOIN MATERIAL_MASTER m ON sm.material_code = m.material_code
JOIN MATERIAL_SUBSTANCE_MAP msm ON m.material_code = msm.material_code
JOIN SUBSTANCE_MASTER sub ON msm.substance_code = sub.substance_code
WHERE sup.supplier_code = 'KR0001'
ORDER BY sm.supply_ratio DESC, msm.inclusion_ratio DESC;
```

---

## 7. 파일 구조

```
poc-a/
├── data/
│   └── supply_chain.db              # SQLite DB 파일
├── models/
│   ├── __init__.py
│   └── supply_chain_db.py           # Python dataclass 정의
├── scripts/
│   ├── create_supply_chain_db.py    # DB 생성 및 스키마 정의
│   ├── generate_sample_data.py      # 샘플 데이터 생성 메인
│   └── data_generators/
│       ├── __init__.py
│       ├── supplier_generator.py    # 협력사 데이터 생성
│       ├── site_generator.py        # 생산지 데이터 생성
│       ├── material_generator.py    # 자재 데이터 생성
│       ├── substance_generator.py   # 소재 데이터 생성
│       └── mapping_generator.py     # 매핑 테이블 데이터 생성
└── Markdown/
    ├── DB_SUPPLYMAP_Docs.md         # 본 설계 문서
    └── DB_SUPPLYMAP_Data Creation Guide.md  # 데이터 생성 가이드
```

---

## 8. 참고사항

### 8.1 SQLite 타입 매핑

| Python dataclass | SQLite | 비고 |
|------------------|--------|------|
| int | INTEGER | |
| str | TEXT | |
| float / Decimal | REAL | |
| bool | INTEGER | 0/1로 저장 |
| date | TEXT | ISO8601 형식 (YYYY-MM-DD) |
| datetime | TEXT | ISO8601 형식 (YYYY-MM-DDTHH:MM:SS.sss) |

### 8.2 인덱스 전략

- **PK 컬럼**: 자동으로 UNIQUE INDEX 생성됨
- **FK 컬럼**: JOIN 성능을 위해 명시적으로 INDEX 생성
- **검색 빈도 높은 컬럼**: country, material_type, substance_type 등

### 8.3 성능 고려사항

- **PRAGMA foreign_keys = ON**: FK 제약 조건 활성화
- **PRAGMA journal_mode = WAL**: 동시성 향상
- **트랜잭션 사용**: 대량 INSERT 시 BEGIN ~ COMMIT으로 묶어서 실행
- **인덱스 재생성**: 대량 INSERT 후 `ANALYZE` 실행

---

## 9. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0 | 2026-06-24 | Claude | 초기 작성 |
| 1.1 | 2026-06-24 | Claude | 카테고리 테이블 제거 (CATEGORY_MASTER, MATERIAL_CATEGORY_MAP) - 7개 테이블로 최종 확정 |

---

**작성일**: 2026년 6월 24일  
**문서 위치**: `poc-a/Markdown/DB_SUPPLYMAP_Docs.md`
