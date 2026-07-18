# 태그 레이어 (`news_intelligence.db`) 생성 방법 및 결과

> **문서 목적**: 운영 공급망 DB(`supply_chain.db`)에 맞춰 `news_intelligence.db`의 태그 체계(TAG_MASTER / TAG_KEYWORD_MAP)를 어떻게 재생성했는지(방법)와 무엇이 만들어졌는지(결과)를 기록한다.
>
> **최종 갱신**: 2026-07-15 · **대상 브랜치**: `poc-a_operation`

---

## 1. 개요

### 1.1 태그 레이어란

태그 레이어는 뉴스 → 키워드 추출 → **태그 정규화** → LLM 검색전략 → Text-to-SQL → DB 검색 파이프라인에서, 뉴스에서 뽑힌 키워드를 표준 태그로 매핑하는 어휘 사전이다. `news_intelligence.db`의 두 테이블에 저장된다.

- **TAG_MASTER**: 태그 마스터(태그 정의·유형·도메인·조회 대상 컬럼)
- **TAG_KEYWORD_MAP**: 태그별 키워드(뉴스에 등장하는 다양한 표기)
- **소비 주체**: Agent_2 (Tag_Mapper) — 키워드 → 태그 매핑

### 1.2 태그 유형

| tag_type | 성격 | DB 대응 엔티티 |
|----------|------|----------------|
| **RAW_MATERIAL** | 원소재 (개별 + 희토류 그룹) | 있음 (조회 대상) |
| **MATERIAL** | 자재/부품 | 있음 (조회 대상) |
| **SUPPLIER** | 협력사 | 있음 (조회 대상) |
| **SITE** | 생산 거점(국가) | 있음 (조회 대상) |
| **EVENT** | 리스크 이벤트(수출규제·화재 등) | 없음 (DB 독립적, 검색전략 힌트) |

- **엔티티 태그 4종**(RAW_MATERIAL/MATERIAL/SUPPLIER/SITE)은 공급망 DB의 실제 엔티티에 대응한다.
- **EVENT 태그**는 대응 DB 엔티티가 없고 검색 전략 힌트로만 쓰이므로 이번 재생성 대상에서 제외했다(기존 유지).

### 1.3 재생성 배경

`supply_chain.db`가 운영 데이터로 **전면 재구축**되면서, 기존 태그 체계가 구(舊) 엔티티(구 원소재/자재/협력사/거점명)를 참조하게 되어 불일치 상태가 되었다. 엔티티 태그 4종을 운영 DB 기준으로 재생성해 매핑 대상을 최신화했다.

- **원본 불변**: `supply_chain.db`는 읽기만 하고 수정하지 않는다. 소스 오타/중복은 태그 키워드 레벨에서만 보정한다.
- **EVENT 보존**: EVENT 태그는 DB 독립적이고 기존 키워드셋(vF)과 일치하므로 손대지 않는다.

---

## 2. 소스 데이터

### 2.1 운영 공급망 DB (`data/SUPPLY_CHAIN/supply_chain.db`)

| 마스터 테이블 | 레코드 수 | 태그화 결과 |
|---------------|-----------|-------------|
| RAW_MATERIAL_MASTER | 34 | 개별 34 + 희토류 그룹 1 = **35 태그** |
| MATERIAL_MASTER | 10 | **10 태그** |
| SUPPLIER_MASTER | 14 | **14 태그** |
| SITE_MASTER | 14 (국가 6종) | 국가 단위 **6 태그** |

- **국가(SITE)**: 한국·중국·대만·미국·인도·인도네시아 (6개국) → 국가별 1개 태그로 집계
- **원소재 유형**: `희토류` 그룹(흑연·갈륨·네오디뮴·텅스텐 4종) + 일반 30종

### 2.2 키워드/리스크팩터 소스 (`data/TAG/DB_TAG_Risk Factor Pool_vF.xlsx`)

- 시트 `2. Keyword Set_ai` — C열 = risk_factor, E열 = 키워드 리스트
- 엔티티 태그의 추가 키워드는 이 키워드셋에서 **DB에 실재하는 소재/부품에만** 병합했다.

---

## 3. 생성 방법

### 3.1 파이프라인 (3단계 스크립트)

```
1. temp/generate_operation_tags.py
   운영 supply_chain.db 조회 → 엔티티 태그 4종 생성
   → temp/generated_operation_tags.json (검수용)
   verify: 유형별 태그 수 · 검수 플래그 목록 출력

2. temp/load_operation_tags.py
   generated_operation_tags.json → news_intelligence.db 재적재
   (EVENT 보존, 엔티티 4종만 교체)
   verify: 적재 전/후 TAG_MASTER 카운트 · 고아 키워드 = 0

3. temp/update_excel_3tag_ai.py
   news_intelligence.db → vF 엑셀 '3_Tag_ai' 시트만 갱신
   verify: 유형×지역 분포 출력
```

### 3.2 핵심 설계 규칙

**(1) KR / GLOBAL 2개 레코드 분리**
각 태그는 `target_region`으로 KR(한글 키워드)·GLOBAL(영문 키워드) 2개 레코드로 나뉜다. 뉴스 수집 지역에 따라 상이한 키워드셋을 태우기 위함이다.

**(2) RAW_MATERIAL — 개별 + 희토류 그룹 병존**
Agent_3의 4-사분면 희토류 라우팅 규칙은 **희토류 그룹 태그와 개별 원소재 태그를 모두** 요구한다. 따라서 개별 34개(`name_kor` 매칭) + 희토류 그룹 1개(`raw_material_type='희토류'` 매칭) = 35개를 모두 생성했다.

**(3) 키워드 웹 리서치 (MATERIAL / SUPPLIER)**
MATERIAL·SUPPLIER는 뉴스에 어떻게 등장하는지 인터넷 리서치를 거쳐 한글/영문/약어/중문명을 키워드로 보강했다. 신뢰도가 낮거나 동명이인 위험이 있는 항목은 `_review_note`로 검수 플래그를 달았다(아래 §5).

**(4) 소스 오타 보정 (원본 불변)**
운영 DB의 `name_eng` 오타는 DB를 고치지 않고 태그 키워드에서만 정정했다.
- `Tungstem` → `Tungsten` (텅스텐)
- `Betanediol` → `Butanediol` (1,3-부탄다이올)

**(5) risk_category_9 = NULL (엔티티 태그)**
기존 관례상 엔티티 태그는 `risk_category_9`를 NULL로 두고, EVENT 태그만 8대 리스크 카테고리를 채운다.

**(6) NEWS_TAG_MAP 미변경**
뉴스 재수집 + 전체 Agent 재실행이 예정되어 있어, 구 태그를 참조하는 NEWS_TAG_MAP은 이번에 건드리지 않았다.

---

## 4. 결과

### 4.1 TAG_MASTER (유형 × 지역)

| tag_type | KR | GLOBAL | 태그 수 | 처리 |
|----------|----|--------|---------|------|
| EVENT | 66 | 66 | 66 | 보존 |
| RAW_MATERIAL | 35 | 35 | 35 | 재생성 |
| SUPPLIER | 14 | 14 | 14 | 재생성 |
| MATERIAL | 10 | 10 | 10 | 재생성 |
| SITE | 6 | 6 | 6 | 재생성 |
| **합계** | **131** | **131** | **131** | |

- **총 TAG_MASTER 레코드**: 262 (태그 131개 × KR/GLOBAL)
- **엔티티 태그**: 65개(RAW 35 + MAT 10 + SUP 14 + SITE 6) 재생성, **EVENT 66개** 보존

### 4.2 TAG_KEYWORD_MAP (유형별 키워드 수)

| tag_type | 키워드 수 |
|----------|-----------|
| EVENT | 398 |
| RAW_MATERIAL | 111 |
| MATERIAL | 110 |
| SUPPLIER | 83 |
| SITE | 15 |
| **합계** | **717** |

- **고아 키워드**(마스터 없는 키워드): **0** ✅
- 각 태그의 첫 키워드는 `is_primary=1`로 지정.

### 4.3 산출물 반영 위치

| 산출물 | 위치 | 비고 |
|--------|------|------|
| 태그 재적재 | `data/NEWS/news_intelligence.db` | 사전 백업: `backup/data/NEWS/` |
| 엑셀 갱신 | `DB_TAG_Risk Factor Pool_vF.xlsx` → **`3_Tag_ai` 시트만** | 250 레코드, `3_Tag` 등 타 시트 불변 |
| 검수용 중간 산출물 | `temp/generated_operation_tags.json` | |

---

## 5. 검수 필요 항목 (`_review_note`)

MATERIAL·SUPPLIER 중 신뢰도가 낮거나 동명이인 위험이 있어 태그 오탐 가능성이 있는 항목이다. 뉴스 재수집·매핑 결과를 보며 확인이 필요하다.

| 유형 | 태그 | 이슈 |
|------|------|------|
| MATERIAL | `MAT_NOZZLE_ASSY` | 정체 불명확 — SMT 마운터 노즐(설비 소모품) 추정, 제품 내장 노즐 가능성도 있음 |
| SUPPLIER | `SUP_BHUE` (TSI) | 'TSI'는 흔한 약어로 동명이인 다수 → 단독 태그 오탐 위험 |
| SUPPLIER | `SUP_BIII` (멀텍) | 별개 회사 'Multech(선전)'와 혼동 주의 |
| SUPPLIER | `SUP_BYOX` (쿤샨 TL) | 뉴스 노출 거의 없음, 중문명 미확인 |
| SUPPLIER | `SUP_DTEP` (넥스트솔루션) | 흔한 상호로 무관 법인 다수 → 오탐 위험 |
| SUPPLIER | `SUP_DXBJ` (피노 솔루션) | 유효 정보 확보 실패, FINO Payments Bank 등과 혼동 소지 |
| SUPPLIER | `SUP_E0AE` (타이저우 후이진) | 복수 법인 가능성, 뉴스 노출 낮음 |
| SUPPLIER | `SUP_EBCS` (저장 쥐화 한정 신소재) | 그룹/상장사 '巨化(Juhua)'로 더 자주 언급될 수 있음 |
| SUPPLIER | `SUP_EBQW` (JV 오스타) | 유효 정보 없음, 'JV=Joint Venture' 일반명사와 매칭 위험 |
| SUPPLIER | `SUP_EBUV` (에버파워) | 흔한 상호로 복수 엔티티 가능, 미확정 |

---

## 6. 임베딩 캐시 처리

Agent_2_Tag_Mapper의 **semantic_matching은 의도적으로 비활성**(false positive 방지)이다. 현재 활성 파이프라인은 `exact_matching`(Jaccard ≥ 0.95) → `classify_unmatched`(LLM)만 돈다.

- `config.py`: `SEMANTIC_MATCH_ENABLED = False`
- `graph.py`: `semantic_match_tags` 노드 제거 → 엣지 `exact_match_tags → verify_mapping_quality` 직결

임베딩 캐시(`cache/tag_embeddings.json`)를 소비하는 유일한 지점이 semantic_matching이므로, 태그를 교체·재적재해도 **임베딩 캐시 재생성은 불필요**하다(활성 파이프라인이 캐시를 읽지 않음). 향후 semantic_matching을 다시 켜려면 그때 재생성한다.

---

## 7. 후속 작업

- 뉴스 재수집 → 전체 Agent 재실행 (NEWS_TAG_MAP은 이 시점에 새 태그 기준으로 재구성됨)
- §5 검수 항목은 매핑 결과 모니터링 후 키워드 조정
