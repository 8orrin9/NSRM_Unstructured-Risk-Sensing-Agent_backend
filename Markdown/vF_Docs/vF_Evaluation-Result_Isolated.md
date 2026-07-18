# Isolated 평가 결과 — Golden Dataset

> 생성: 2026-07-16 01:04 · 정답 51건 (GOLDEN_GROUND_TRUTH)
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
| Risk Evaluator | Timing Accuracy | 0.805 | 0.634 | +0.171 |
| Risk Evaluator | Routing Accuracy | 0.863 | 0.725 | +0.137 |
| Risk Evaluator | Critical Miss Rate | 0.000 | 0.000 | +0.000 |

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
| **SMD** | 0 | 17 | 7 |
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

- **최대 Propagation Loss: Tag Accuracy = +0.715** (Isolated 0.982 vs Cascaded 0.267). Tag Mapper는 정답 키워드만 받으면 거의 완벽하게(0.982) 태그를 매핑하지만, 실제 파이프라인에서는 News Analyzer가 뽑은 잡음 키워드(Keyword Precision 0.054)까지 매핑을 시도해 정밀도가 0.267로 폭락한다. **즉 Tag Mapper 자체는 건강하며, Cascaded 손실의 실체는 직전 News Analyzer의 키워드 과다추출이다.** 이는 방법론 §3(Loss는 직전 모듈 약함을 지시)의 전형적 사례다.

- **Entity Recall Loss = −0.068** (Isolated 0.242 < Cascaded 0.309, **음수**): 버그가 아니라 precision-recall 트레이드오프의 반영이다. 분모(정답 엔티티 합 782)는 양쪽 동일하나,
  - **Isolated**: 정답 태그만 받아 **좁고 정확하게** 검색 → pred 230건 중 inter 189 → **Precision 0.822**, Recall 0.242.
  - **Cascaded**: 실제 파이프라인이 태그를 과다 추출하고 그룹 통합(4건)으로 검색을 넓혀 pred 426건까지 확장 → 정답 엔티티를 **더 많이 우연히 포착**(inter 242) → Recall 0.309, 대신 Precision 0.568로 하락.
  - 해석: Cascaded의 높은 Recall은 "넓게 훑어" 얻은 것으로 실제 성능 우위가 아니다. **DB매칭 only Precision Loss +0.367**(Isolated 0.955 vs Cascaded 0.587)이 이를 뒷받침한다 — 정답 태그 기반 검색이 훨씬 정밀하다.

- **Isolated 관점 최약 지표**: Entity Recall = 0.242. 정답 태그를 받고도 낮은데, 이는 gt_entities가 BOM 전개된 대량 엔티티(뉴스당 평균 29개)인 반면 Isolated 입력의 search_results가 suppliers/sites 위주로 재구성돼(materials/raw_materials 미포함) 구조적으로 낮게 나온다. **DB Searcher 로직 문제가 아니라 Isolated 입력 재구성 범위의 한계**이므로, materials/raw_materials까지 채우면 개선될 여지가 있다(실행 계획 §주의 참조).

- **Risk Routing Loss +0.137 / Timing Loss +0.171**: Risk Evaluator는 정답 엔티티를 받으면 Routing 0.863·Timing 0.805로 안정적이며, Critical Miss는 Isolated·Cascaded 모두 0(ISSUE 13건 전건 포착). 후반 모듈의 Loss는 앞선 Tag/DB 손실이 누적 전파된 결과로, 절대 크기보다 **모듈 간 증가량**으로 병목(Tag Accuracy)을 지목하는 게 타당하다(방법론 §6-3).

- **주의(프레임)**: 두 평가 모두 GT 51건 전체를 순회하고 미처리 뉴스는 기본값(is_risk=0/routing=NONE)으로 둔다. Isolated는 gt_tags 없는 14건(FP 10 + 비매칭 4)을 모듈에 태우지 않으나, 이들의 정답이 비리스크·NONE이라 기본값과 일치해 지표 왜곡이 없다.

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
| GD_2d_050 | 2d | SMD | SMD | ONGOING | SCHEDULED | ✓ |
| GD_2d_051 | 2d | SMD | SMD | SCHEDULED | SCHEDULED | ✓ |
| GD_2e_045 | 2e | NONE | NONE | ONGOING | - | — |
| GD_2e_046 | 2e | NONE | NONE | ONGOING | - | — |
| GD_2e_047 | 2e | NONE | NONE | ONGOING | - | — |
| GD_2e_048 | 2e | NONE | NONE | ONGOING | - | — |
