# 온톨로지 레이어 DB (`ontology_layer.db`) 생성 방법 및 결과

> **문서 목적**: 재구축된 운영 데이터(`supply_chain.db`)와 갱신된 태그 체계(`news_intelligence.db`)에 맞춰 온톨로지 레이어 DB를 어떻게 생성했는지(방법)와 무엇이 만들어졌는지(결과)를 기록한다.
>
> **최종 갱신**: 2026-07-15 · **대상 브랜치**: `poc-a_operation`

---

## 1. 개요

### 1.1 온톨로지 레이어란

`ontology_layer.db`는 공급망 DB(`supply_chain.db`)의 구조·의미·검색 전략·도메인 지식을 담은 **메타데이터 레이어**다. 원본 공급망 DB는 건드리지 않고, LLM이 뉴스 → 태그 → Text-to-SQL → DB 검색 파이프라인에서 올바른 테이블·JOIN·검색 전략을 고르도록 돕는다.

- **소비 주체**: Agent_3 (DB_Searcher) — 검색 전략 결정 및 도메인 규칙 조회
- **원본 불변**: `supply_chain.db`는 읽기만 하고 수정하지 않는다.
- **메타데이터 분리**: 온톨로지 정보는 별도 파일(`data/ONTOLOGY/ontology_layer.db`)에 저장한다.

### 1.2 재생성 배경

`supply_chain.db`가 운영 데이터로 **전면 재구축**되고, 그에 맞춰 `news_intelligence.db`의 태그 체계(TAG_MASTER / TAG_KEYWORD_MAP)도 **갱신**되었다. 이로 인해 온톨로지 레이어의 다음 두 축이 구(舊) 데이터와 불일치 상태가 되어 재생성이 필요했다.

| 축 | 구 상태 | 문제 |
|----|---------|------|
| **TAG_SEARCH_STRATEGY_MAP** | 구 그룹 태그(`RAW_SPECIAL_GAS`, `MAT_PVD_타겟` 등) 하드코딩 | 새 개별 태그(`RAW_GALLIUM`, `SITE_TW` 등)와 매칭 실패 → fallback 남발 |
| **DOMAIN_KNOWLEDGE_RULES** | LLM이 생성한 구 도메인(네온·우크라이나·일본 등 재구축 DB에 없는 대상) | 재구축 DB에 존재하지 않는 엔티티 참조 → 규칙이 죽은 지식 |

반면 **메타데이터 3종**(테이블/컬럼/관계)은 `supply_chain.db`를 런타임에 분석해 자동 생성되므로, 재구축 DB만 있으면 항상 최신으로 채워진다.

---

## 2. 대상 데이터 현황 (재구축 후)

### 2.1 공급망 DB (`supply_chain.db`)

| 구분 | 테이블 | 레코드 수 |
|------|--------|-----------|
| **MASTER** | RAW_MATERIAL_MASTER (원소재) | 34 |
| | MATERIAL_MASTER (자재) | 10 |
| | SUPPLIER_MASTER (협력사) | 14 |
| | SITE_MASTER (생산지) | 14 |
| **MAPPING** | SUPPLIER_RAW_MATERIAL_MAP | 121 |
| | MATERIAL_RAW_MATERIAL_MAP | 49 |
| | SITE_MATERIAL_MAP | 28 |

- **국가**: 한국·중국·미국·대만·인도·인도네시아 (6개국)
- **원소재 유형**: `희토류` 그룹(네오디뮴·갈륨·흑연·텅스텐 4종) + `일반` 30종
- 구 도메인에 있던 네온/크립톤/제논/HF/폴리실리콘, 우크라이나/러시아/일본/네덜란드 등은 **없음**

### 2.2 태그 체계 (`news_intelligence.db` TAG_MASTER)

| tag_type | 태그 수 | 매핑 대상 여부 |
|----------|---------|----------------|
| EVENT | 132 | 제외 (대응 조회 엔티티 없음) |
| RAW_MATERIAL | 70 | 매핑 |
| SUPPLIER | 28 | 매핑 |
| MATERIAL | 20 | 매핑 |
| SITE | 12 | 매핑 |
| **합계** | **262** | |

- 각 태그는 KR/GLOBAL 두 region으로 존재(262 = 131 distinct × 2 region).
- `tag_id`는 region 간 공유되므로, DOMAIN 규칙의 `applicable_tags`에는 한 번만 넣어도 양 region이 매칭된다.

---

## 3. 온톨로지 레이어 스키마 (6개 테이블)

`create_ontology_layer.py`가 정의하는 6개 테이블. (V_ENTITY_HIERARCHY 뷰는 `populate_metadata.py`에서 생성)

| # | 테이블 | 역할 | 채우는 스크립트 |
|---|--------|------|-----------------|
| 1 | `DB_TABLE_METADATA` | 테이블별 LLM 설명·유형·행수 | populate_metadata.py |
| 2 | `DB_COLUMN_METADATA` | 컬럼별 의미유형·검색연산자·샘플값 | populate_metadata.py |
| 3 | `DB_TABLE_RELATIONSHIP` | 테이블 간 FK 관계·JOIN 조건·카디널리티 | populate_metadata.py |
| 4 | `SEARCH_STRATEGY_TEMPLATE` | tag_type별 SQL 검색 전략 템플릿 | populate_strategies.py |
| 5 | `TAG_SEARCH_STRATEGY_MAP` | 개별 태그 → 검색 전략 매핑 | populate_strategies.py |
| 6 | `DOMAIN_KNOWLEDGE_RULES` | 태그별 도메인 지식(배경·영향·검색대상) | populate_domain_rules.py |

- 모든 테이블은 새로 생성 시 기존 `.db`를 unlink 후 재생성한다 → PK 충돌 원천 차단.
- WAL 저널 모드, FK 활성화.

---

## 4. 생성 방법 (재생성 파이프라인)

### 4.1 실행 전제 (Windows / poc-a)

- 인터프리터: `.venv/Scripts/python.exe` (프로젝트 가상환경 필수)
- 인코딩: `PYTHONIOENCODING=utf-8`
- 명령어: `python3`가 아닌 `python` (MS Store 리다이렉터 회피)

### 4.2 실행 순서

`poc-a` 디렉터리 기준으로 아래 5단계를 순서대로 실행한다. (스키마 생성 → 메타데이터 → 도메인 규칙 → 전략 → 검증)

```bash
python scripts/create_ontology_layer.py    # ① 스키마 재생성 (기존 db 삭제 후 6테이블 생성)
python scripts/populate_metadata.py         # ② 테이블·컬럼·관계 메타데이터 (supply_chain.db 분석)
python scripts/populate_domain_rules.py     # ③ 도메인 규칙 29개
python scripts/populate_strategies.py       # ④ 전략 13개 + 태그매핑 248개
python scripts/verify_ontology.py           # ⑤ 최종 검증
```

### 4.3 각 단계 설명

**① `create_ontology_layer.py`** — 6개 테이블 스키마와 인덱스를 정의한다. 기존 `.db`가 있으면 삭제 후 새로 만든다.

**② `populate_metadata.py`** — `supply_chain.db`를 런타임에 분석(`PRAGMA table_info`, `foreign_key_list`)하여 테이블/컬럼/관계 메타데이터를 자동 생성한다. semantic_type·search_operator·샘플값·카디널리티를 추론한다. **재구축 DB만 있으면 항상 최신 값이 채워지므로 수작업 없음.**

**③ `populate_domain_rules.py`** — 29개 도메인 규칙을 하드코딩 리스트(`get_domain_rules()`)로 INSERT한다. 규칙은 **실세계 반도체 공급망 지식 + 이 DB의 실제 집중 구조**를 결합해 재작성했다(§5.3).

**④ `populate_strategies.py`** — 13개 전략 템플릿(`get_strategies()`)을 INSERT하고, `news_intelligence.db`의 TAG_MASTER를 읽어 **tag_type × 전략 세트를 곱해** TAG_SEARCH_STRATEGY_MAP을 자동 생성한다(`get_tag_strategy_mappings(news_db_path)`). EVENT 타입은 제외.

**⑤ `verify_ontology.py`** — 6개 테이블의 레코드 수를 기대값과 대조 검증한다.

---

## 5. 생성 결과

### 5.1 최종 레코드 수 (검증 통과)

```
[OK] DB_TABLE_METADATA:        7 records
[OK] DB_COLUMN_METADATA:      59 records
[OK] DB_TABLE_RELATIONSHIP:    7 records
[OK] SEARCH_STRATEGY_TEMPLATE: 13 records
[OK] TAG_SEARCH_STRATEGY_MAP: 248 records
[OK] DOMAIN_KNOWLEDGE_RULES:  29 records
[OK] Total:                  363 records
```

### 5.2 TAG_SEARCH_STRATEGY_MAP (248개) — tag_type 패턴 자동 생성

구 하드코딩을 폐기하고, TAG_MASTER를 소스로 tag_type별 전략 세트를 곱해 자동 생성했다. EVENT(132)는 대응 조회 엔티티가 없어 제외한다.

| tag_type | 태그 수 | 전략 수 | 매핑 | 연결 전략 |
|----------|---------|---------|------|-----------|
| RAW_MATERIAL | 70 | 2 | 140 | SITE_IMPACT(우선) / FULL_CHAIN |
| SUPPLIER | 28 | 2 | 56 | SITE_LIST / RAW_MATERIAL_LIST |
| MATERIAL | 20 | 2 | 40 | SITE_TRACE / COMPOSITION |
| SITE | 12 | 1 | 12 | COUNTRY_LIST |
| **합계** | **130** | | **248** | (KR/GLOBAL 각 124 대칭) |

- 엔티티 태그는 이제 fallback 없이 적절한 검색 전략에 연결된다.
- EVENT만 매핑된 뉴스는 fallback 처리되고, 실제 검색은 함께 매핑된 엔티티 태그로 수행된다.

### 5.3 DOMAIN_KNOWLEDGE_RULES (29개) — 실세계 + DB 결합 재작성

`applicable_tags`에는 재구축 DB/태그에 **실재하는 tag_id만** 사용했고, 배경지식·영향평가는 실세계 지식과 이 DB의 실제 집중 구조를 결합해 기술했다.

| rule_category | 개수 | 주요 규칙 |
|---------------|------|-----------|
| GEOGRAPHIC_RISK | 13 | 희토류 그룹·갈륨·네오디뮴·텅스텐·흑연 중국 집중, 구리·니켈·규소·주석, 인듐 한국 단일소싱, 대만/중국 생산집중, 물류 요충지 |
| MATERIAL_DEPENDENCY | 5 | 배터리셀 핵심광물, MLCC, 홀센서 단일생산지, 노즐 텅스텐, PCB |
| REGULATORY_PATTERN | 4 | 수출규제, 관세·무역분쟁, 분쟁광물(3TG/UFLPA), 환경규제(REACH/RoHS) |
| SUPPLY_CHAIN_PATH | 3 | 원소재↔생산지↔자재 추적 경로 |
| SITE_EVENT | 2 | 생산지 재해·인프라, 생산지 지정학 |
| SUPPLIER_EVENT | 2 | 협력사 사이버공격, 협력사 재무부실 |

**희토류 그룹 반영**: `희토류`는 개별 원소재 행이 아니라 `raw_material_type='희토류'` 그룹(네오디뮴·갈륨·흑연·텅스텐)이다. 관련 규칙의 `applicable_tags`에 그룹 대표 태그(`RAW_RARE_EARTH`)와 4종 개별 태그를 함께 등재해, 개별 원소재명으로 와도 희토류 리스크로 연결되게 했다.

---

## 6. Agent_3의 온톨로지 소비 메커니즘

문서화된 검색 파이프라인이 온톨로지를 어떻게 쓰는지(규칙 작성 시 반드시 정합해야 하는 부분).

### 6.1 도메인 규칙 조회 — `query_domain_rules` 3단계 캐스케이드

`applicable_tags`는 `json_extract(applicable_tags,'$') LIKE '%{tag_id}%'`로 매칭한다.

1. **Step1 — 완전 매칭**: 모든 tag_id를 AND로 결합해 매칭 (priority ASC, LIMIT 5)
2. **Step2 — 부분 매칭**: 일부 tag_id를 OR로 결합
3. **Step3 — 타입 fallback**: tag_type 조합으로 `rule_category` 매칭
   - EVENT + SUPPLIER → `SUPPLIER_EVENT`
   - EVENT + SITE → `SITE_EVENT`
   - RAW_MATERIAL → `MATERIAL_DEPENDENCY`

> Step3 fallback 경로를 살리기 위해 `SUPPLIER_EVENT`·`SITE_EVENT`·`MATERIAL_DEPENDENCY` 세 카테고리를 실제 규칙으로 채웠다.

최상위 규칙(priority 최소)의 `search_targets`를 파싱해 `search_target_entities`와 `impact_scope`를 뽑는다.

### 6.2 검색 대상 파싱 — `parse_search_targets`

`search_targets` 문자열에서 정규식으로 `*_MASTER` 테이블명을 추출한다. 그래서 각 규칙의 `search_targets` 문장에는 대상 `*_MASTER` 테이블명을 반드시 포함시켰다.

> **파서 버그 수정(부수)**: 기존 정규식 `\b[A-Z_]+_MASTER\b`는 `SITE_MASTER에서`처럼 한글이 바로 붙으면 뒤 경계(`\b`)가 성립하지 않아 매칭에 실패했다(한글도 단어 문자로 취급). 뒤쪽 `\b`를 제거해 근본 원인을 해결했다. `_MAP` 테이블은 `_MASTER`로 끝나지 않아 오검출되지 않는다.

### 6.3 검색 전략 결정 — `determine_search_strategy`

태그별로 `TAG_SEARCH_STRATEGY_MAP`을 `(tag_id, target_region)` 정확 매칭으로 조회 → priority 정렬 → 최상위 전략의 `SEARCH_STRATEGY_TEMPLATE`를 가져온다. 매칭 실패 시에만 기본 FULL_CHAIN fallback.

---

## 7. 검증 (재생성 후 스모크 테스트)

- **레코드 수/무결성**: 6개 테이블 총 363건, 전부 `[OK]`. TAG_SEARCH_STRATEGY_MAP FK 고아 0건, distinct strategy 7종.
- **`query_domain_rules` 발화 확인**: 희토류·갈륨·배터리셀·협력사+랜섬웨어·물류 케이스 모두 규칙 발화 + `search_target_entities` 채워짐. 예) 희토류 → `['SITE_MASTER','MATERIAL_MASTER','SUPPLIER_MASTER','RAW_MATERIAL_MASTER']`
- **fallback 확인**: 대응 규칙 없는 EVENT 단독(예: `EVT_GDPR`)은 정상적으로 타입 기반 fallback 반환.
- **전략 매핑 확인**: RAW_MATERIAL(KR) 태그 → 전략 2건, min priority=1, `fallback_strategy_used == False`.

---

## 8. 함께 반영된 변경 (희토류 판단 보완)

DB Searcher와 별개로, **Agent_4 (Risk_Evaluator)** 의 리스크 판단 프롬프트(`prompts.py`)에도 희토류 지침을 보완했다.

- `희토류`는 개별 원소재가 아니라 `raw_material_type='희토류'` 그룹(네오디뮴·갈륨·흑연·텅스텐)임을 명시.
- DB 검색 결과가 개별 원소재명(갈륨 등)으로 와도, '희토류' 단어가 없어도 **희토류 그룹 리스크로 간주**하도록 지시.
- 중국 집중도(채굴 ~70% / 정제 ~90%)와 수출통제 이력(갈륨 2023, 흑연 2023)을 판단 근거로 제공.

---

## 9. 관련 파일

| 구분 | 경로 |
|------|------|
| 스키마 정의 | `scripts/create_ontology_layer.py` |
| 메타데이터 생성 | `scripts/populate_metadata.py` |
| 도메인 규칙 | `scripts/populate_domain_rules.py` |
| 검색 전략 | `scripts/populate_strategies.py` |
| 최종 검증 | `scripts/verify_ontology.py` |
| 규칙 조회 로직 | `backend/agents/Agent_3_DB_Searcher/utils/ontology_query.py` |
| 전략 결정 로직 | `backend/agents/Agent_3_DB_Searcher/utils/strategy_utils.py` |
| 리스크 판단 프롬프트 | `backend/agents/Agent_4_Risk_Evaluator/prompts.py` |
| 출력 DB | `data/ONTOLOGY/ontology_layer.db` |
| 백업 | `backup/data/ONTOLOGY/ontology_layer.db` |
