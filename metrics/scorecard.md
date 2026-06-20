# Track-Forward Calibration Scorecard

> Generated: 2026-06-20
> Verdicts file: `metrics/verdicts.jsonl`
> Benchmark: IWM (Russell 2000 small-cap ETF)
> Returns: dividend-adjusted total return (yfinance auto_adjust=True)

## De-Risk-Native Metrics

*(A de-risk scanner's job is blowup AVOIDANCE, not beating IWM by a hair. These measure that.)*

| Metric | Value | N | Notes |
|---|---|---|---|
| BUY data-integrity (clean / all BUY) | 0.0% | 19 | measurable today; 19 adjudicated data_false_positive |
| Blowup-avoidance (观察/避开 avoided <= -40% total return) | — | 0 | needs matured price verdicts |
| Downside-capture (避开 underperformed AND blew up) | — | 0 | needs matured 避开 verdicts |

## BUY Data-Integrity (validation false-positive cohort)

19 BUY-eligible (MoS>=30%) names from the 2026-06-19 validation campaign, each adjudicated `data_false_positive` by balance-sheet cross-check. Kept OUT of the price-Brier (no forward horizon); they populate the BUY-data-integrity metric so the BUY arm is not permanently empty.

| Ticker | MoS% | fp_cause |
|---|---|---|
| CISS | 2355% | micro-cap collapse + debt=total-liabilities proxy |
| AII | 290% | material_weakness + cash unavailable -> EV excludes cash |
| GRNT | 209% | material_weakness + cash unavailable -> EV understated |
| QFIN | 190% | debt=total-liabilities proxy + OCF-proxy + China VIE |
| ARDT | 168% | OCF-proxy FCF (no capex) + large-cap out of scope |
| VSNT | 153% | large-cap scope leak + structural decline + linear terminal value |
| SNFCA | 129% | NI unit anomaly from DEF 14A (32B vs 344M rev); wrong form |
| DAC | 128% | OCF-proxy FCF (no capex) |
| HCI | 118% | insurer financial-structure mismatch; FCF/EV model invalid |
| FSBW | 104% | debt truncation (stale 2022) -> false fcf_cap routing |
| GSL | 102% | total_debt=None -> EV collapses to market cap; ZERO flags raised |
| GNE | 97% | over-normalized FCF; multiple kill-flags |
| ESEA | 87% | going_concern + IFRS capex gaps |
| FVRR | 82% | material_weakness |
| SIGA | 76% | ~90% single-customer BARDA concentration; lumpy/over-normalized OCF |
| GIII | 73% | material_weakness |
| RYAM | 63% | debt truncation 779M -> 21.5M -> false MoS |
| TUSK | 55% | FEMA one-time OCF inflates 5yr avg; revenue collapsed |
| CMRE | 45% | OCF-proxy FCF (no capex) |

## Status: 0 Scored / 40 Pending

**Calibration unknown until verdicts mature.**

Earliest maturity date: **2027-06-18**

No rubric tuning is justified yet. Run `python tools/track_forward.py --score` periodically; once ~20 verdicts mature, calibration becomes statistically meaningful.

This is the correct honest state. The epistemic spine of the skill (market-efficient vs. rubric-miscalibrated) cannot be resolved until forward data accumulates.

## Pending Verdicts

| Ticker | Theme | Rating | p_implied | Verdict Date | Maturity Date |
|---|---|---|---|---|---|
| UIS | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| CMRC | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| EGAN | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| RCMT | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| ARCT | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| KLTR | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| USIO | ai_agent | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| SOAR | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| BRR | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| INUV | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| IQST | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| LPSN | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| DOMO | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| EGHT | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| HCKT | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| LTRN | ai_agent | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| KOP | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| MSEX | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| ARTNA | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| YORW | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| SHIM | boring_themes | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| NWPX | boring_themes | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| GBX | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| RAIL | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| NL | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| VHI | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| KRO | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| TROX | boring_themes | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| EAF | boring_themes | 避开 | 0.35 | 2026-06-18 | 2027-06-18 |
| CSV | deathcare | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| ALG | agequip | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| TWI | agequip | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| UAN | agequip | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| LNN | agequip | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| AEBI | agequip | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| CMP | agequip | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| EVI | uniform | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| VSTS | uniform | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| WLFC | aeromro | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
| BUKS | aeromro | 观察 | 0.50 | 2026-06-18 | 2027-06-18 |
