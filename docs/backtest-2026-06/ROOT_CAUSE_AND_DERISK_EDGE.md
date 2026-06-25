# Root-cause of the "no edge vs random" result — and a cluster-robust de-risk edge

*self-evolve run, 2026-06-24. Methodology: reflect → propose → evaluate → judge, with
truth-isolation (out-of-sample holdout) and a deterministic code judge. LLM proposes; the
backtest + cluster-robust statistics decide. Adversarially reviewed by a second model (codex).*

## TL;DR

- **No durable alpha (winner-picking).** The engine's cheapness signal (Margin-of-Safety) is
  monotone in-sample but it is a **2020–21 post-COVID-recovery regime artifact**: it vanishes
  on the 2023–24 holdout (stratified within-cell permutation **p = 0.72**) and on a drop-2020
  re-test (**p = 0.35**). The skill cannot pick market-beaters, and we do **not** claim it can.
- **A real, out-of-sample, cluster-robust DE-RISK edge (blowup avoidance — the tool's actual
  mission).** A point-in-time fundamental **distress rank** concentrates forward-12mo blowups
  (return < −40%) far above base rate: top-quintile **lift 2.56×**, recall 51%, **ticker-cluster
  bootstrap 95% CI on lift = [1.73, 3.00]**, P(lift ≤ 1) = 0.000 over 5,000 ticker resamples,
  robust across leave-one-year-out folds. This is the "significantly better than random" result —
  on the metric a de-risk scanner exists for.

## 1. Root cause: the engine computes a usable signal; the decision layer throws it away

Over the 25-cell survivorship-safe PIT panel (5 themes × 5 as-of dates 2020–2024, 12mo horizon,
~936 priceable names):

- **0 BUY across all 25 cells.** The mechanical BUY needs `mos_basis == fcf_cap` AND MoS ≥ 30 AND
  `buy_eligible`. But the **median MoS is −45.6 %** (p25 −88.7, p75 −18.3); only ~7 % of names
  even reach +30, and the few that do are knocked out by data-quality gates. The valuation model
  finds almost nothing "cheap," so the BUY trigger is effectively dead.
- **Two data-quality gates fire on half-to-two-thirds of the universe and are anti-predictive:**
  `cross_source_mismatch` (fires 66 %, blowup lift **0.86×**, flagged names *beat* IWM 55 %) and
  `debt_truncation_suspected` (fires 48 %, blowup lift **0.67×**). They were ANDed into
  `buy_eligible`, so they kill eligibility on good names while carrying no downside signal.
- Net: the prior verdict ("≈ random, danger calls below base rate") was correct **about the
  decision layer** — but the underlying MoS signal and the genuine distress flags were being
  discarded, not absent.

## 2. No durable alpha (the honest negative)

MoS deciles on pooled data look monotone (top decile beats IWM 65 % vs 38 % in decile 3). That
monotonicity **does not generalize**:

| split | rule beat-rate | base | perm p |
|---|---|---|---|
| TRAIN 2020–22 | 0.545 | 0.482 | **0.017** ✓ |
| TEST 2023–24 | 0.570 | 0.579 | **0.72** ✗ |
| drop-2020 | 0.556 | 0.539 | **0.35** ✗ |

Per-year edge: +10.5 pt (2020), +7.3 pt (2021), +3.2 pt (2022), **−0.4 pt (2023), −1.1 pt (2024)**.
The edge lives entirely in the COVID crash-and-recovery. **There is no winner-picking alpha to
implement.** (This is exactly the failure self-evolve's holdout is designed to expose — and the
opposite of the de-risk result below, which *does* survive the same scrutiny.)

## 3. The de-risk edge: a PIT fundamental distress rank predicts blowups OOS

**Scope:** non-financial operating companies with core fundamentals (banks excluded — bank
distress is NIM/NPL/deposit-flight, a different model; they already route to abstain). n = 412
name-years, 55 blowups, **93 unique tickers**, 36 unique blowup tickers.

**Distress flags** (point-in-time only — XBRL facts filed ≤ as-of, annual, latest-filed-per-end;
all mechanism-grounded in distress theory, none data-mined):

- `neg_ocf` — operating cash flow < 0
- `neg_margin` — operating income < 0
- `accum_deficit` — retained earnings < 0
- `low_altman` — Altman Z″ = 6.56·WC/TA + 3.26·RE/TA + 6.72·EBIT/TA + 1.05·Equity/Liab < 1.1

**CORE-4 distress rank** = unweighted sum of the four. Monotone dose-response (blowup rate by
score, pooled): score 0–2 ≈ 6–7 % (= base), score 4 = 21.6 %, score 5 = 45.5 %.

**Out-of-sample, cluster-robust results** (per-year top-quintile, pooled across all 5 years):

| score | top-quintile lift | recall | ticker-cluster bootstrap lift, median [95% CI] | P(lift ≤ 1) |
|---|---|---|---|---|
| 8-flag composite | 2.28× | 0.45 | 2.10× [1.48, 2.77] | 0.000 |
| **CORE-4 rank** | **2.56×** | **0.51** | **2.36× [1.73, 3.00]** | **0.000** |

Leave-one-year-out CV (refit logistic per fold, pooled OOS): lift 2.19×, **pooled OOS AUC 0.680**.
The unweighted CORE-4 rank ≈ the fitted logistic, so the result does not depend on fragile weights.

## 4. Adversarial review (codex) — caveats honored, not hidden

A second model was tasked solely with breaking the claim. Its valid caveats and our responses:

1. **Outcome-based `|return| ≤ 5` cap** (a forward filter that drops big winners) → **removed**;
   priceability is now entry-price (penny) only. Effect was immaterial here (1 name) but the cap is
   gone on principle.
2. **Fisher p treats 412 rows as independent** but they cluster in 93 tickers / 20 cells / 5 years
   → headline inference is now the **ticker-cluster bootstrap**, not Fisher. The edge survives
   (95% CI lower bound 1.73).
3. **"Pre-registered" was not credible** (a script comment after a failed alpha study) → reframed as
   an **a-priori, theory-grounded spec validated OOS, reported with its forking-path exposure**. The
   garden of forking paths (flag set, quintile, −40% threshold, scope, the pivot itself) is real and
   acknowledged; the OOS + cluster robustness + theory-grounding mitigate but do not eliminate it.
4. **`high_lev` is directionally wrong** (negative logistic weight) → dropped; **CORE-4 is the
   honest signal** and is cleaner/stronger than the 8-flag composite.
5. **Survivorship**: ~32 names dropped for no entry price; bounding shows lift stays ~2.08–2.11×
   either way — does not invalidate the edge, but the estimand is "priceable names."
6. **"Operating losers blow up more"** — yes, largely. That is a *feature*: a known, mechanism-grounded
   distress signal is more trustworthy than a data-mined one, and it is exactly what a de-risk
   kill-flag should encode.

**codex verdict:** ACCEPT-WITH-CAVEATS. Ours after the corrections: the CORE-4 distress rank is a
genuine, cluster-robust, out-of-sample blowup predictor; the overstated `p<1e-4`/"pre-registered"/
"robust 8-flag" framing is retracted in favor of the cluster-bootstrap CI above.

## 5. What this means for the skill (implementation)

- **Wire the CORE-4 distress rank in as a graded de-risk kill-flag** (score ≥ 3 → AVOID), so both the
  live rating and the backtest bucket route distressed names to AVOID regardless of cheapness.
- **Demote `cross_source_mismatch` and `debt_truncation_suspected`** from `buy_eligible` blockers to
  advisory data-quality labels (anti-predictive, fire on half the universe).
- **Reframe the docs honestly:** the validated value is **downside avoidance, not alpha**; 0-BUY
  remains valid; the risk layer now has measured, OOS, cluster-robust power.

## 6. Reproduce

```
python docs/backtest-2026-06/distress_features_fast.py validate   # companyfacts == trusted puller
python docs/backtest-2026-06/distress_features_fast.py run        # (re)build distress_features.json
python docs/backtest-2026-06/distress_oos_validate2.py            # cluster-robust OOS verdict
```

Caveat on the data artifact: `distress_features.json` stores `{end,val}` only (filing dates
stripped), so PIT correctness is inherited from the trusted `_deepdive_concepts` code path
(validated byte-equivalent), not self-audited from the artifact alone.
