# v0.3.x Point-in-Time Backtest — Cross-Panel Verdict (updated, regbank populated + penny-guarded)

> Synthesis by the controller (the agent synthesis step hit transient gateway 530s; the numbers
> below are computed deterministically from the 25 on-disk cell JSONs). Source:
> `reports/smallcap/backtest/*_*.json`. 25/25 cells, **all non-vacuous, look-ahead audit clean on
> every cell** (max filing_date ≤ asof, n_filing_dates_observed > 0). Survivorship-safe EDGAR-PIT
> (filer universe as-of T incl. later-delisted via `dei:TradingSymbol`) + yfinance forward returns.
> Penny guard active: 8 sub-$0.10 names excluded (kills the earlier GNOLF $0.00001→$0.01 +999×).

## 1. By bucket (pooled across 25 cells; priceable, |return| ≤ 5)

| bucket | n | mean excess vs IWM | **median excess** | win-rate |
|---|---|---|---|---|
| buy_eligible (flag) | 37 | +0.056 | **−0.078** | 43% |
| WATCH | 817 | +0.030 | −0.001 | 50% |
| AVOID | 63 | +0.212 | **+0.148** | 63% |
| abstain | 42 | +0.004 | +0.042 | 60% |

- **Actual BUYs fired across the entire 5-year × 5-theme panel = 0** (no name cleared eligible AND
  MoS≥30 AND clean in any cell). The "buy_eligible (flag)" row is the weaker eligibility-flag superset
  (mostly sub-MoS, cell-bucketed WATCH) — and even it **lags IWM at the median (−0.078)**.
- **The de-risk gradient is INVERTED**: AVOID (median +0.148, win 63%) is the *best* bucket; WATCH ≈
  market; the eligibility-flagged names are worst. The labels do not order forward returns as a
  de-risk scanner intends.

## 2. By regime (median excess vs IWM)

| regime | buy_elig | WATCH | AVOID | abstain |
|---|---|---|---|---|
| V-bottom 2020 | −0.58 (n5, w20%) | −0.09 (n141, w40%) | +0.07 (n25, w68%) | −0.17 (n8) |
| normal 2021 | +0.04 (w71%) | +0.17 (n163, w75%) | +0.32 (w86%) | +0.21 |
| **bear 2022** | −0.02 | **−0.17 (w24%)** | **−0.22 (w27%)** | −0.10 |
| **stress 2023 (incl SVB)** | −0.10 (w0%) | −0.01 | **+0.23 (w71%)** | +0.09 |
| normal 2024 | +0.07 | +0.05 | +0.19 | +0.16 (w88%) |

- **2022 broad bear = NO protection**: every bucket negative at the median, AVOID worst. The rubric
  did not de-risk the one true bear.
- **2020 V-bottom**: the rubric was cautious at the bottom (BUY-flagged names −0.58!), i.e. it is
  pro-cyclically late — it missed the recovery's biggest movers.

## 3. Blowup-avoidance (>40% drawdown over the horizon)

Pooled: **4 / 72 = 5.6%** of blowups were in AVOID/abstain (63 in WATCH, 5 in buy_eligible-flag).
Overall weak — the rubric over-routes nearly everything to WATCH, so blowups concentrate there.

## 4. regbank-2023 (SVB regional-bank crisis) — the key new natural experiment, and a genuine WIN

- universe 100 (capped), buckets {WATCH 83, AVOID 10, abstain 7, **BUY 0**}, IWM +9.8%.
- **Blowup-avoidance = 1.0 (1/1): PNBK — the one bank that cratered >40% — was correctly in AVOID.**
- AVOID median excess **+0.23 (win 80%)**, abstain +0.25, WATCH +0.08. In a real sector crisis the
  kill-flag / abstain routing *did* identify and side-step the failing bank and outperformed.

## 5. Verdict (honest, nuanced)

**As a return-predictive bucket gradient, the rubric is NOT validated — and is mildly inverted.**
- The BUY signal has **no demonstrated edge**: it literally never fired a real BUY in 5 years × 5
  themes, and the eligibility-flagged superset lags IWM at the median. Extreme conservatism is the
  empirical norm (consistent with "0-BUY is valid", now taken to the limit).
- The **AVOID label does not broadly identify losers** (AVOID *outperforms* in 4 of 5 regimes) —
  i.e. names the model flags as risky mostly do fine; the gradient is inverted, not monotone.
- Overall **blowup-avoidance is weak (5.6%)** because almost everything is routed to WATCH.

**But there is one real, narrow de-risk signal:** in the **targeted SVB regional-bank crisis
(regbank-2023)** the rubric put the single >40% crasher (PNBK) in AVOID (blowup-avoidance 1.0) and
its AVOID/abstain buckets out-returned WATCH. The kill-flag / financial-abstain machinery works in a
genuine sector crisis — it just doesn't generalize into a return gradient across normal/bear regimes.

**Bottom line:** the skill is a *disciplined refuse-to-overpay + don't-buy-the-obviously-broken*
screen whose **forward-return edge is unproven (BUY) and inverted (AVOID) on this panel**, with a
**narrow, real crisis-detection competence** (SVB). Treat the bucket labels as NOT validated for
return prediction; the demonstrated value is mechanical discipline and avoiding data-artifact BUYs,
not alpha.

## 7. Formal significance test (stratified within-cell label permutation, B=20000)

`significance_test.py` (reproducible, seed=42). The honest null shuffles bucket labels *within each
cell* (respects IWM/regime clustering; treating all 959 names as independent — as Kruskal-Wallis
does — is anti-conservative).

| test | result | reading |
|---|---|---|
| **omnibus** — any bucket structure beyond random? | **p = 0.122** | NOT significant — the 4-bucket scheme *as a whole* is statistically **indistinguishable from random labeling** |
| buy_eligible underperforms WATCH | **p = 0.61** | NOT significant — the BUY signal is noise / no-edge (CI [−0.23, +0.04] includes 0) |
| AVOID outperforms WATCH (the inversion) | **p = 0.006** | **significant** (survives Bonferroni ×3); AVOID CI [+0.005, +0.32] excludes 0 — the inversion is REAL |

Cluster-bootstrap 95% CIs of median excess: **only AVOID excludes 0** (+0.005..+0.324);
buy_eligible / WATCH / abstain all include 0. Clustering-naive references (anti-conservative):
Kruskal-Wallis p=0.024, Mann-Whitney AVOID>WATCH p=0.0017.

**Conclusion:** the BUY signal and the overall bucketing are statistically **indistinguishable from
random**. The *only* effect that survives a proper clustering-aware test is the **AVOID inversion**
(p=0.006) — significant and in the WRONG direction: AVOID-labeled names reliably *outperformed*. The
SVB save (PNBK→AVOID) is a real tail case, but on average AVOID over-flags healthy names. Net: as a
return/risk signal the rubric is random-or-backwards; its demonstrated value is mechanical discipline
(refuse to overpay, no artifact BUYs, rare genuine crisis flags), not statistical edge.

## 6. Caveats
regbank/oilsvc universes capped at 100 (not full); single 12-mo horizon + one 06-30 entry/year (no
path robustness); AVOID/abstain n are small (63/42 pooled) → noisy; yfinance delisted prices
approximate (penny guard mitigates the worst); means are skewed by a few multibaggers → medians are
the honest central tendency; small-cap value broadly lagged IWM 2020-24 (a factor headwind the rubric
operated within).
