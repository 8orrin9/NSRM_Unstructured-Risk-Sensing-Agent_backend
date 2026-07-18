# Golden Dataset 평가 방법론 (Evaluation Methodology)

공급망 Risk-Sensing 5-Agent 파이프라인을 [Golden Dataset](vF_GoldenDataset_Fake-News.md)으로 평가하는 방법론을 정의한다. 각 모듈별 지표의 정의·계산식·정답 매칭 기준과, 지표가 사용하는 Golden Dataset 필드 매핑을 정리한다.

- **평가 대상 파이프라인**: News Analyzer → Tag Mapper → DB Searcher → Risk Evaluator (+ News Grouper)
- **정답 데이터**: `data/NEWS/golden_dataset.json` (48건)
- **최종 갱신**: 2026-07-15

---

## 0. 핵심 개념: Isolated vs Cascaded

모든 후속 모듈 지표는 **두 가지 방식**으로 측정한다.

| 구분 | 입력 | 측정 목적 |
|------|------|-----------|
| **Isolated** | 직전 단계의 **정답(Ground Truth)** 을 주입 | 해당 모듈 **자체 성능** (절대적 관점) |
| **Cascaded** | 직전 단계의 **실제 출력** 을 주입 | 실제 파이프라인 흐름에서의 성능 (상대적 관점) |

- **Propagation Loss = Isolated − Cascaded**
  - 값이 클수록 **직전 모듈의 성능 영향**을 크게 받음 → 직전 모듈이 상대적으로 약함을 의미.
  - 프로세스 후반으로 갈수록 Loss는 누적되어 커지는 경향 → **절대값이 아닌 모듈 간 증가량**을 비교해 병목 모듈을 식별한다.
  - **상대적 관점**(LLM 추론 난이도 스토리텔링)은 Cascaded로, **절대적 관점**(모듈 순수 성능)은 Isolated로 커버한다.

> Isolated 측정을 위해 Golden Dataset은 각 단계의 정답 라벨(`gt_keywords`, `gt_tags`, `gt_entities`, `gt_event_timing` 등)을 모두 보유한다. FP 뉴스도 하위 정답을 공집합/음성으로 보유하여 **FP 누출의 전파 효과**를 Cascaded에서 측정할 수 있다.

---

## 1. 뉴스 수집 모듈 (News Analyzer)

### 1.1 False Positive 구별 성능
FP = 반도체 공급망 리스크와 무관한 뉴스(`is_false_positive=True`, Golden Dataset의 Block 1 = 10건).

| 지표 | 계산식 |
|------|--------|
| **FP Precision** | FP로 판별된 것 중 실제 FP 수 / FP로 판별된 뉴스 수 |
| **FP Recall** | FP 뉴스 중 FP로 판별한 수 / 전체 FP 뉴스 수 |

- **정답 필드**: `is_false_positive`
- 혼동행렬 기준: "FP로 판별" = News Analyzer가 `is_relevant=False`로 필터링한 건.

### 1.2 키워드 추출 성능
| 지표 | 계산식 |
|------|--------|
| **Must Keyword Precision** | 추출 키워드 중 정답 키워드 수 / 추출된 키워드 수 |
| **Must Keyword Recall** | 정답 키워드 중 추출된 수 / 전체 정답 키워드 수 |

- **정답 필드**: `gt_keywords` (각 태그의 primary keyword)
- 집합(set) 기반 P/R. FP 뉴스는 `gt_keywords=[]`.

---

## 2. 태그 매핑 모듈 (Tag Mapper)

키워드 → 태그 매핑의 정확도. **키워드 단위**로 계산한다.

| 지표 | 입력 | 계산식 |
|------|------|--------|
| **Isolated Tag Accuracy** | 뉴스별 **정답 키워드**(`gt_keywords`) | 정답 태그와 매핑된 키워드 수 / 전체 키워드 수 |
| **Cascaded Tag Accuracy** | 뉴스별 **실제 추출 키워드**(News Analyzer 출력) | 상동 |
| **Propagation Loss** | — | Isolated Tag Accuracy − Cascaded Tag Accuracy |

- **정답 필드**: `gt_tags`
- 분모(전체 키워드 수)가 Isolated는 정답 키워드, Cascaded는 실제 추출 키워드로 달라짐에 유의.

---

## 3. DB 검색 모듈 (DB Searcher)

### 3.1 공급망 관련성 식별 성능
**엔티티 집합**(suppliers/sites/materials/raw_materials) 기준. Accuracy는 **태그 단위**, Precision/Recall은 **엔티티 단위**로 정의됨에 유의.

| 지표 | 계산식 |
|------|--------|
| **Accuracy** | 정답 엔티티와 매핑된 태그 수 / 전체 태그 수 |
| **Precision** | 매핑된 엔티티 중 정답 엔티티 수 / 매핑된 엔티티 수 |
| **Recall** | 정답 엔티티와 매핑된(=정답에 포함된) 엔티티 수 / 전체 정답 엔티티 수 |

- **Isolated**: 뉴스별 **정답 태그**(`gt_tags`) 주입
- **Cascaded**: 뉴스별 **실제 추출 태그**(Tag Mapper 출력) 주입
- **Propagation Loss** = Isolated − Cascaded (Accuracy 기준)
- **정답 필드**: `gt_entities` (BOM 전개 결과), `has_db_match`
- DB O/X 통제: 엔티티 태그(SUP/SITE/MAT/RAW)는 항상 매칭, EVENT 태그만 있으면 `gt_entities` 공집합. Block 2d/2e는 `has_db_match=False`.

### 3.2 Text-to-SQL 안정성
| 지표 | 계산식 |
|------|--------|
| **DB Search Error Rate** | Exception Error 수(검색 실패·타임아웃·예외) / 검색 전체 호출 건수 |

- Golden Dataset 전체 평가 실행 중 발생한 예외 기준. 정답 라벨과 무관한 **런타임 안정성** 지표.

---

## 4. 리스크 평가 모듈 (Risk Evaluator)

### 4.1 리스크 식별 성능 — Specificity
Risk가 **아닌** 뉴스를 얼마나 잘 걸러내는지(오탐 억제).

| 지표 | 계산식 |
|------|--------|
| **Specificity** | Risk 없는 뉴스를 Risk 없다고 판단한 수 / 전체 Risk 아닌 뉴스 수 (TN / (TN+FP)) |

- **Isolated**: 뉴스별 **정답 엔티티**(`gt_entities`, DB 검색 결과) 주입
- **Cascaded**: 뉴스별 **실제 검색 엔티티**(DB Searcher 출력) 주입
- **Propagation Loss** = Isolated − Cascaded
- **정답 필드**: `gt_is_risk` (Risk 아님 = `gt_is_risk=False` → Block 2c, 2e)
- 원문의 "1−Recall" 표기는 Specificity의 통상 정의(TN 기반)를 뜻한다.

### 4.2 리스크 발생 시점 판별 성능 — "Severity"
> ⚠️ **명칭 주의**: 지표 이름은 "Severity"이나, **실제 측정 대상은 리스크 발생 "시점(timing)"** 이다(심각도 아님). 정답은 `gt_event_timing`(ONGOING=진행형 / SCHEDULED=예정형)이다. Golden Dataset의 `gt_severity`(high/medium/low) 필드는 이 지표와 **무관**하며 frontend 표시·routing 보조용이다.

| 지표 | 계산식 |
|------|--------|
| **Accuracy** | 정답 시점을 맞춘 뉴스 수 / 전체 뉴스 수 |

- **Isolated**: 정답 엔티티 주입 / **Cascaded**: 실제 검색 엔티티 주입
- **Propagation Loss** = Isolated − Cascaded
- **정답 필드**: `gt_event_timing`

### 4.3 최종 라우팅 판별 성능 — Routing
| 지표 | 계산식 |
|------|--------|
| **Accuracy** | 정답 Routing(ISSUE / SMD / DROP=NONE) 맞춘 뉴스 수 / 전체 뉴스 수 |
| **Critical Miss Rate** | ISSUE 대상 중 미판별 뉴스 수 / 전체 ISSUE 대상 뉴스 수 |

- **Isolated**: 뉴스별 **정답 엔티티 + 정답 시점**(`gt_entities`, `gt_event_timing`) 주입
- **Cascaded**: **실제 검색 엔티티 + 실제 판별 시점** 주입
- **Propagation Loss** = Isolated − Cascaded
- **정답 필드**: `gt_routing`
- **Critical Miss Rate**는 ISSUE(=즉시 대응 필요, Block 2a·12건)를 놓치는 비율로, 가장 치명적인 오류를 별도 추적한다.

---

## 5. 지표 ↔ Golden Dataset 필드 매핑 요약

| 모듈 | 지표 | 정답 필드 | Isolated 입력 | Cascaded 입력 |
|------|------|-----------|---------------|---------------|
| News Analyzer | FP P/R | `is_false_positive` | (원문 뉴스) | (원문 뉴스) |
| News Analyzer | Must Keyword P/R | `gt_keywords` | (원문 뉴스) | (원문 뉴스) |
| Tag Mapper | Tag Accuracy | `gt_tags` | `gt_keywords` | 실제 추출 키워드 |
| DB Searcher | Accuracy/P/R | `gt_entities`, `has_db_match` | `gt_tags` | 실제 추출 태그 |
| DB Searcher | Error Rate | (실행 예외) | — | — |
| Risk Evaluator | Specificity | `gt_is_risk` | `gt_entities` | 실제 검색 엔티티 |
| Risk Evaluator | Severity(=시점) | `gt_event_timing` | `gt_entities` | 실제 검색 엔티티 |
| Risk Evaluator | Routing / Critical Miss | `gt_routing` | `gt_entities`+`gt_event_timing` | 실제 엔티티+실제 시점 |

---

## 6. 평가 실행 시 유의사항

1. **News Grouper 미포함**: 그룹화는 우선 평가 대상이 아니며, 정답(`group` G1~G3)은 insight_kg 갱신 후 재정합 예정. 그룹 증거 배수·우선순위 상향 효과는 재정합 이후 반영한다.
2. **FP 누출 처리**: FP가 필터를 통과하면(FP Recall 하락) 하위 모듈이 공집합 정답과 비교되어 Cascaded 지표가 하락한다 — 이것이 Propagation Loss로 관측된다.
3. **Cascaded 해석 원칙**: Loss는 상대값이다. 후반 모듈일수록 커지므로 **절대 크기가 아닌 모듈 간 증가량**으로 병목을 판단한다. 절대 성능은 항상 Isolated로 확인한다.
4. **DB O/X 통제 신뢰성**: EVENT 태그(db_matched_count=0) vs 엔티티 태그(>0)로 DB 매칭이 결정론적으로 통제되므로, DB Searcher 지표의 정답(`gt_entities`)은 실제 SQL 결과와 정합한다.
5. **"Severity" 명칭**: §4.2 참조 — 이 지표는 시점(timing) 정확도이며 심각도가 아니다. 혼동 금지.
