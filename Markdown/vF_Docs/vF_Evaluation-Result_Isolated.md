# Isolated 평가 결과 — Golden Dataset

> 생성: 2026-07-18 19:54 · 정답 51건 (GOLDEN_GROUND_TRUTH)
> run_id: Tag=`isolated_tag_20260716` · DB=`isolated_db_20260716` · Risk=`isolated_risk_20260716` · News Analyzer=`golden_eval_20260715`(Isolated=Cascaded)
> Cascaded 비교 기준: `golden_eval_20260715` · 지표 정의: [`vF_GoldenDataset_Evaluation-Methodology.md`](./vF_GoldenDataset_Evaluation-Methodology.md)
> 그룹 판정 정책: `individual_first` (Isolated 산출물은 전부 개별행 → 그룹 펼침 no-op)

---

## 0. Isolated 평가란

대상 모듈 B를 평가할 때 **직전 모듈 A가 완벽했다고 가정**하고, A가 생산해야 할 정답(`gt_*`)만 B에 주입해 실행한 결과를 B의 정답과 대조한다. A의 오류 전파가 제거되므로 **B 자체의 순수 성능**을 측정한다.

- **Propagation Loss = Isolated − Cascaded**. 값이 클수록 직전 모듈의 실제 출력 품질에 크게 의존(=전파 취약)함을 의미한다.
- **News Analyzer**는 입력이 원문 뉴스라 Isolated=Cascaded로 동일 → Loss=0 (측정 대상 아님).
- 주입 정답: Tag Mapper←`gt_keywords`, DB Searcher←`gt_tags`, Risk Evaluator←`gt_entities`.

## 1. Isolated vs Cascaded — Propagation Loss

| 모듈 | 지표 | Isolated | Cascaded | Loss (I−C) |
|------|------|---:|---:|---:|
| Tag Mapper | Tag Accuracy | 0.982 | 0.267 | +0.715 |
| Tag Mapper | Tag Recall | 0.806 | 0.657 | +0.149 |
| DB Searcher | Entity Precision | 0.822 | 0.568 | +0.254 |
| DB Searcher | Entity Recall | 0.242 | 0.309 | -0.068 |
| DB Searcher | Entity P (DB매칭 only) | 0.955 | 0.587 | +0.367 |
| DB Searcher | Entity R (DB매칭 only) | 0.242 | 0.309 | -0.068 |
| DB Searcher | Error Rate | 0.000 | 0.000 | +0.000 |
| Risk Evaluator | Specificity | 1.000 | 1.000 | +0.000 |
| Risk Evaluator | Timing Accuracy | 0.829 | 0.610 | +0.220 |
| Risk Evaluator | Routing Accuracy | 0.843 | 0.725 | +0.118 |
| Risk Evaluator | Critical Miss Rate | 0.000 | 0.077 | -0.077 |

> Loss 부호 해석: Accuracy/Precision/Recall/Specificity/Timing/Routing은 **양(+)일수록 Cascaded 손실 큼**. Critical Miss Rate·Error Rate는 낮을수록 좋은 지표라 **음(−)일수록 Cascaded가 나쁨**.

**엔티티 타입별 P/R (Isolated)**

| 타입 | Isolated P | Isolated R | Cascaded P | Cascaded R |
|------|---:|---:|---:|---:|
| suppliers | 0.779 | 0.444 | 0.464 | 0.519 |
| sites | 0.686 | 0.356 | 0.472 | 0.496 |
| materials | 0.974 | 0.289 | 0.743 | 0.430 |
| raw_materials | 0.978 | 0.115 | 0.847 | 0.130 |

## 2. Isolated 혼동행렬

**Routing (정답 vs 예측)**

| 정답＼예측 | ISSUE | SMD | NONE |
|---|---|---|---|
| **ISSUE** | 13 | 0 | 0 |
| **SMD** | 0 | 16 | 8 |
| **NONE** | 0 | 0 | 14 |

**Risk 판정 (비리스크 정답 대상)**: TN=20, FP=0
**Critical Miss**: ISSUE 정답 13건 중 0건 미판별

## 3. 커버리지 (Isolated vs Cascaded)

```
정답(GT)         Isolated 51건        Cascaded 51건
  → 태그 부여       31건             29건
  → AGENT4 판정     37건             29건
```

- Isolated는 정답 태그를 직접 주입하므로 gt_tags 보유 **31건**이 그대로 태그 단계를 통과한다(Agent_1 FP 필터·Tag 손실 없음). Cascaded는 실제 파이프라인에서 29건까지 감소했다.
- **역매핑**: Isolated search_results 값 중 마스터 미등록 0건 skip (Cascaded와 동일 화이트리스트·통합 lookup 사용).

## 4. 해석

- **Isolated 최약 모듈**: Entity Recall = 0.242. 직전 단계 정답을 받고도 이 값이면 해당 모듈 자체의 개선 여지다.
- **최대 Propagation Loss**: Tag Accuracy = +0.715. 이 지표에서 Cascaded가 Isolated 대비 가장 크게 하락 → 직전 모듈 출력 품질 의존도가 높다.
- **주의(프레임)**: 두 평가 모두 GT 51건 전체를 순회하고 미처리 뉴스는 기본값(is_risk=0/routing=NONE)으로 둔다. Isolated는 gt_tags 없는 14건(FP 10 + 무엔티티 4)을 모듈에 태우지 않으나, 이들의 정답이 비리스크·NONE이라 기본값과 일치해 지표 왜곡이 없다.

## 5. 부록 — news_id별 Isolated 예측

| news_id | cell | GT routing | ISO routing | GT timing | ISO timing | 커버 |
|---|---|---|---|---|---|---|
| GD_1a_001 | 1a | NONE | NONE | - | - | — |
| GD_1a_002 | 1a | NONE | NONE | - | - | — |
| GD_1a_003 | 1a | NONE | NONE | - | - | — |
| GD_1a_004 | 1a | NONE | NONE | - | - | — |
| GD_1a_005 | 1a | NONE | NONE | - | - | — |
| GD_1b_006 | 1b | NONE | NONE | - | - | — |
| GD_1b_007 | 1b | NONE | NONE | - | - | — |
| GD_1b_008 | 1b | NONE | NONE | - | - | — |
| GD_1b_009 | 1b | NONE | NONE | - | - | — |
| GD_1b_010 | 1b | NONE | NONE | - | - | — |
| GD_2a_011 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_012 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_013 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_014 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_015 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_016 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_017 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_018 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_019 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_020 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_021 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_022 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2a_049 | 2a | ISSUE | ISSUE | ONGOING | ONGOING | ✓ |
| GD_2b_023 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_024 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_025 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_026 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_027 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_028 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_029 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2b_030 | 2b | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2c_031 | 2c | SMD | SMD | ONGOING | SCHEDULED | ✓ |
| GD_2c_032 | 2c | SMD | SMD | ONGOING | ONGOING | ✓ |
| GD_2c_033 | 2c | SMD | SMD | ONGOING | ONGOING | ✓ |
| GD_2c_034 | 2c | SMD | SMD | ONGOING | ONGOING | ✓ |
| GD_2c_035 | 2c | SMD | SMD | ONGOING | ONGOING | ✓ |
| GD_2c_036 | 2c | SMD | SMD | ONGOING | ONGOING | ✓ |
| GD_2d_037 | 2d | SMD | SMD | ONGOING | ONGOING | ✓ |
| GD_2d_038 | 2d | SMD | NONE | ONGOING | SCHEDULED | ✓ |
| GD_2d_039 | 2d | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_040 | 2d | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_041 | 2d | SMD | NONE | SCHEDULED | ONGOING | ✓ |
| GD_2d_042 | 2d | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_043 | 2d | SMD | NONE | SCHEDULED | SCHEDULED | ✓ |
| GD_2d_044 | 2d | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_050 | 2d | SMD | NONE | ONGOING | ONGOING | ✓ |
| GD_2d_051 | 2d | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2e_045 | 2e | NONE | NONE | ONGOING | - | — |
| GD_2e_046 | 2e | NONE | NONE | ONGOING | - | — |
| GD_2e_047 | 2e | NONE | NONE | ONGOING | - | — |
| GD_2e_048 | 2e | NONE | NONE | ONGOING | - | — |
