# Cascaded 평가 결과 — `golden_eval_20260715`

> 생성: 2026-07-16 00:04 · 정답 51건 (GOLDEN_GROUND_TRUTH)
> 지표 정의: [`vF_GoldenDataset_Evaluation-Methodology.md`](./vF_GoldenDataset_Evaluation-Methodology.md) · 실행: [`vF_Execution_Golden-Data.md`](./vF_Execution_Golden-Data.md)  
> 평가용 script: [`evaluate_cascaded.py`](../../scripts\db\evaluate_cascaded.py)
> 그룹 판정 정책: `individual_first` (개별행 우선)

---

## 1. 지표 요약

| 모듈 | 지표 | 값 |
|------|------|---:|
| News Analyzer | FP Precision | 0.588 |
| News Analyzer | FP Recall | 1.000 |
| News Analyzer | Keyword Precision (micro) | 0.054 |
| News Analyzer | Keyword Recall (micro) | 0.269 |
| Tag Mapper | Tag Accuracy | 0.267 |
| Tag Mapper | Tag Recall | 0.657 |
| DB Searcher | Entity Precision | 0.568 |
| DB Searcher | Entity Recall | 0.309 |
| DB Searcher | Entity P (DB매칭 only) | 0.587 |
| DB Searcher | Entity R (DB매칭 only) | 0.309 |
| DB Searcher | Error Rate | 0.000 |
| Risk Evaluator | Specificity | 1.000 |
| Risk Evaluator | Timing Accuracy | 0.634 |
| Risk Evaluator | Routing Accuracy | 0.725 |
| Risk Evaluator | Critical Miss Rate | 0.000 |

**엔티티 타입별 P/R (DB Searcher)**

| 타입 | Precision | Recall |
|------|---:|---:|
| suppliers | 0.464 | 0.519 |
| sites | 0.472 | 0.496 |
| materials | 0.743 | 0.430 |
| raw_materials | 0.847 | 0.130 |

## 2. 혼동행렬

**FP 구별 (positive = FP로 판별)**

| | 예측 FP | 예측 관련 |
|---|---|---|
| **실제 FP** | 10 (TP) | 0 (FN) |
| **실제 관련** | 7 (FP) | 34 (TN) |

**Routing (정답 vs 예측)**

| 정답＼예측 | ISSUE | SMD | NONE |
|---|---|---|---|
| **ISSUE** | 13 | 0 | 0 |
| **SMD** | 3 | 10 | 11 |
| **NONE** | 0 | 0 | 14 |

**Risk 판정 (비리스크 정답 대상)**: TN=20, FP=0

## 3. 커버리지 · 전파 인사이트

**단계별 생존 news_id**

```
정답(GT)           51건
  → is_relevant     34건  (FP 필터 통과)
  → 태그 부여        29건
  → AGENT4 판정      29건
```

- **FP 누출**: 0건 (실제 FP를 관련으로 오판). 누출이 없으므로 하위 Cascaded 손실의 주원인은 FP 필터가 아니다.
- **AGENT4 미커버 22건**: FP 필터 제거 17건 + Tag/DB 단계 탈락 5건. 후자가 Cascaded 전파손실의 실체이며, ISSUE 정답이 여기 포함되면 Critical Miss로 관측된다.
- **가장 약한 모듈**: Tag Mapper (Tag Accuracy) = 0.267.
- **역매핑**: search_results 값 중 마스터 미등록 36건 skip (통계행·국가명 등은 화이트리스트에서 애초 제외). 엔티티 코드는 값 기반 통합 lookup(타입 충돌 0)으로 결정론적 변환.

<details><summary>역매핑 실패 상위 (디버깅용)</summary>

- `희토류` × 36

</details>

## 4. 부록 — news_id별 정답 vs 예측

| news_id | cell | FP정답 | relevant | GT routing | 예측 routing | GT timing | 예측 timing | 커버 |
|---|---|---|---|---|---|---|---|---|
| GD_1a_001 | 1a | 1 | 0 | NONE | NONE | - | - | — |
| GD_1a_002 | 1a | 1 | 0 | NONE | NONE | - | - | — |
| GD_1a_003 | 1a | 1 | 0 | NONE | NONE | - | - | — |
| GD_1a_004 | 1a | 1 | 0 | NONE | NONE | - | - | — |
| GD_1a_005 | 1a | 1 | 0 | NONE | NONE | - | - | — |
| GD_1b_006 | 1b | 1 | 0 | NONE | NONE | - | - | — |
| GD_1b_007 | 1b | 1 | 0 | NONE | NONE | - | - | — |
| GD_1b_008 | 1b | 1 | 0 | NONE | NONE | - | - | — |
| GD_1b_009 | 1b | 1 | 0 | NONE | NONE | - | - | — |
| GD_1b_010 | 1b | 1 | 0 | NONE | NONE | - | - | — |
| GD_2a_011 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_012 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_013 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_014 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_015 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_016 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_017 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_018 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_019 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_020 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_021 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_022 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_049 | 2a | 0 | 1 | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2b_023 | 2b | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_024 | 2b | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_025 | 2b | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_026 | 2b | 0 | 1 | SMD | ISSUE | SCHEDULED | ONGOING | ✓ |
| GD_2b_027 | 2b | 0 | 1 | SMD | NONE | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_028 | 2b | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_029 | 2b | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_030 | 2b | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2c_031 | 2c | 0 | 1 | SMD | SMD | ONGOING | SCHEDULED | ✓ |
| GD_2c_032 | 2c | 0 | 0 | SMD | NONE | ONGOING | - | — |
| GD_2c_033 | 2c | 0 | 0 | SMD | NONE | ONGOING | - | — |
| GD_2c_034 | 2c | 0 | 1 | SMD | NONE | ONGOING | - | — |
| GD_2c_035 | 2c | 0 | 0 | SMD | NONE | ONGOING | - | — |
| GD_2c_036 | 2c | 0 | 1 | SMD | NONE | ONGOING | - | — |
| GD_2d_037 | 2d | 0 | 1 | SMD | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2d_038 | 2d | 0 | 1 | SMD | NONE | ONGOING | - | — |
| GD_2d_039 | 2d | 0 | 1 | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_040 | 2d | 0 | 1 | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_041 | 2d | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2d_042 | 2d | 0 | 1 | SMD | NONE | ONGOING | - | — |
| GD_2d_043 | 2d | 0 | 1 | SMD | NONE | SCHEDULED | - | — |
| GD_2d_044 | 2d | 0 | 1 | SMD | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2d_050 | 2d | 0 | 1 | SMD | SMD | ONGOING | SCHEDULED | ✓ |
| GD_2d_051 | 2d | 0 | 1 | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2e_045 | 2e | 0 | 0 | NONE | NONE | ONGOING | - | — |
| GD_2e_046 | 2e | 0 | 0 | NONE | NONE | ONGOING | - | — |
| GD_2e_047 | 2e | 0 | 0 | NONE | NONE | ONGOING | - | — |
| GD_2e_048 | 2e | 0 | 0 | NONE | NONE | ONGOING | - | — |
