# small-cap-deepdive, Optimization Campaign Final Report (2026-06-20)

> A multi-iteration, subagent-driven, test-driven optimization run. Goal: reflect across every
> angle → design → implement → test on real data → iterate until real-world-usable, then
> aggregate. Fully autonomous after one human approval gate; quality-first; doc-tracked.

## 1. Executive summary

The campaign transformed the engine **from a value-trap generator into a calibrated landmine
scanner with an operationalized (diagnostic) alpha thesis**, and closed **all four** of the top
structural diagnoses surfaced by a 10-lens independent reflection.

Starting point (v0.2.1, commit `1a94a6b`): a self-contained skill whose v0.2.0 validation had
shown every mechanical BUY was a data-layer false positive. The reflection then found the deeper
truth: **`MoS` and `reverse_dcf_implied_growth` were algebraically identical, so 19/19 BUYs priced
decline by construction**, and the skill's stated edge ("delayed information diffusion") was
**measured nowhere**.

Five iterations later: the BUY trigger is a mechanical eligibility gate that the v0.2.x guards
actually bite on; value traps (monotone *and* V-shape) are killed at the fundamentals; financials
route to NAV/abstain; recall is measured (recall@gold 100% on the deathcare gold list); data
integrity is cross-checked against a second source; and the diffusion thesis is operationalized as
a strictly firewalled diagnostic (price-divergence) that **never** touches the BUY decision.

## 2. The four original top-diagnoses → closed

| # | Diagnosis (reflection) | Closure | Evidence |
|---|---|---|---|
| 1 | **Thesis never measured**, no trajectory/price/divergence term; `MoS≡reverse_dcf` | iter4 `price_divergence` (P16), firewalled diagnostic | MGPI → `unpriced_improvement` (rev +1, price −40%); SIGA → `aligned`. `buy_eligible` byte-identical with/without signals |
| 2 | **Guards advisory, not blocking**, VSNT/ARDT cleared BUY | iter1 `buy_eligible` mechanical gate (P1) | VSNT/ARDT/SIGA all `buy_eligible=False`; INVA (clean) `True` |
| 3 | **Calibration inert & disjoint**, 40 verdicts all abstain | iter1 P12: confidence-as-prob + total-return + de-risk metrics + backfilled 19 BUYs | `verdicts.jsonl` 19 `data_false_positive` rows; auto verdict emission |
| 4 | **No second source**, robustness was internal-consistency on one corrupted feed | iter5 P7 cross-source band | HRI double-caught (SEC debt $11.2M vs yfinance $9.6B = 861×) |

Plus the concentration blind spot (P3 magnitude kill, catches SIGA's 75% customer), the V-shape
value-trap (iter2 P-A, catches NRP), recall never measured (iter3 P8, recall@gold), and a long
tail of robustness/hygiene fixes.

## 3. Per-iteration log

- **Reflection** (workflow `wtndselbs`, 10 lenses + synth, 1.7M tok). Diagnosis above. Notes in `.git/sdd/reflection/`.
- **Design + the one human gate** (`acf16d9`). Approved: operationalize thesis; build firewalled side-channel; freeze catalyst MoS-waiver.
- **Iter 1, trust spine** (`e0f0039`; test `0877b99`). P1 buy_eligible · P2 OCF-proxy · P3 concentration · P4 finalize_run/verdicts · P5 mktcap (recall 0→271 regbank, 12→219 shipping) · P6 trajectory veto · P9 EBIT cascade · P12 calibration · P13 honest composite · P11-freeze. **Review caught & fixed a P6 contaminated-series bug the unit test masked.** Verdict: usable for core mission.
- **Iter 2, harden core** (`2599d66`; test `c88fb60`). P-A `peak_contamination_flag` (V-shape veto, independent of slope), kills NRP by machine, not judgment; P-B label fix; P-C…H hygiene. **0 false fires across 22 fast-growth names** (ESOA spared by the NI<0 guard). Verdict: defensible real-world-usable.
- **Iter 3, gaps + recall** (`b28245a`). A1 degenerate-base guard (BWIN negative ratio) · A2 concentration_unquantified · A3 insurance-holdco (BOC) · A4 wrong_entity refine · A5 Gate-2 denominator · **P8 SIC reverse-recall + recall@gold = 100% (6/6) on deathcare**.
- **Iter 4, operationalize thesis** (`223b0a4`). Firewalled diagnostic side-channel: `signals.py` (P16 price-divergence + P17 ownership) + integration + P-G. **Firewall verified** (valuation/finalize/rank: 0 signals references).
- **Iter 5, second source** (`d4ae2e8`). P7 SEC-XBRL vs yfinance cross-check gating buy_eligible.

## 4. Final validated state (real data)

| Name | Before (v0.2.0) | After | Mechanism |
|---|---|---|---|
| SIGA | clean +76% BUY | 避开 | concentration_kill + fundamental_decline_flag |
| VSNT | 153% BUY | not BUY | large_cap + extreme_mos + fcf_sustainability + fundamental_decline |
| ARDT | 168% BUY | not BUY | large_cap |
| NRP | clean +36.8% BUY | 避开 | peak_contamination_flag (V-shape, iter2) |
| HRI | +43% false positive | not BUY | debt_truncation **and** cross_source_mismatch (iter5) |
| HCI/WHF/ABR | financial pseudo-BUYs | nav/abstain | financial_sic / BDC-fallback / insurance_concepts |
| INVA | (grower) | 买入 BUY (clean) | the one defensible BUY, not over-blocked |
| MGPI | below threshold | WATCH + `unpriced_improvement` diagnostic | thesis measured |

Acceptance bars (design §6) all met on real new data: zero data-artifact BUYs survive; every
deep candidate gets a deterministic report + verdict; recall recovered and measured; vetoes
downgrade traps while sparing growers/troughs; financial path never fcf_cap-BUYs.

## 5. What the test-driven loop bought

Every iteration's test/review caught a **real defect the prior selftest masked**, and the
controller adjudicated a genuine reviewer disagreement:
- iter1: P6 slope inverted by a contaminated front-of-series (9-month stub + mislabeled FY), two reviewers disagreed; controller ruled it a bug; fixed with annualize + trailing-5.
- iter2: V-shape value traps (NRP) pass the monotone-decline veto → P-A.
- iter3: `peak_contamination_flag` fired on a degenerate negative ratio (BWIN) → 0< guard.
- iter4: latent EFTS bug (`q=%22%22` → 0 hits for every CIK).

## 6. Forward roadmap (deferred, non-blocking for real-world-usable)

- **P14** forensic spine (Sloan accruals, diluted-share CAGR, SBC%, NI−FCF gap), move halo dimensions onto T1 ground.
- **P11-full** catalyst-mechanism verification (`{mechanism_verified, trigger_date, days_remaining}`), currently safely **frozen** to WATCH; un-freeze only after per-category Brier exists.
- **Signals calibration**, per-signal Brier on `signals_snapshot` once verdicts mature (~2027-06); only then could any signal ever be considered for a non-diagnostic role (a fresh human decision).
- **P15 automation**, wire TrendsMCP/news into an automated T2 capture (today agent-gathered).
- **recall@gold expansion**, build gold true-member lists beyond deathcare.

## 7. Honest limitations

- **Calibration is unmeasurable until verdicts mature** (entry 2027-06), an honest unknown, not a failure. The edge claim rests on logic + backtested false-positive elimination, not yet on realized forward returns.
- **Signals are diagnostic-only** by design; the thesis is *operationalized* (measured) but not *load-bearing*.
- The skill remains a **de-risk scanner, not a stock picker**: **0-BUY is the common, correct output**; across the entire iter1-2 test corpus exactly one clean BUY (INVA) appeared, and every mechanical BUY still demands human balance-sheet verification.

## 8. Artifacts
- Design + gate: `docs/optimization-campaign-2026-06/2026-06-20-smallcap-optimization-design.md`
- Reflection notes: `.git/sdd/reflection/` (10 lenses + `_synthesis.md`)
- Test reports: `docs/optimization-campaign-2026-06/iter1-test/` , `iter2-test/`
- Progress tracker: `docs/optimization-campaign-2026-06/2026-06-20-optimization-campaign-progress.md`
- Per-run batches (local, gitignored): `reports/smallcap/2026-06-*/` each with a `_run.json` manifest (skill commit + config) for cross-version comparison.
