# Coverage Test, Theme: space-economy

- **Run batch:** `2026-06-21_cov-space-economy`
- **Skill version:** v0.3.0 (commit `f12fef5`, dirty=true per `_run.json`)
- **Theme keywords:** `space, satellite, launch services`  | **Sector:** Cross
- **Code-path focus:** pre-rev / de-SPAC / low_revenue_loss
- **Date:** 2026-06-21
- **Independent verdict (skeptical PM):** USABLE. Clean 0-BUY. The scanner did its job, it
  enumerated the small-cap space universe, killed the over-recall, and refused to manufacture a
  BUY in a hot, cash-burning theme. Exactly the "nothing found is a feature" outcome.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Discover (FTS + SIC-floor + mktcap fallback) raw universe | 623 rows | all bands |
| Small-cap candidates (band breakdown) | 359 deep / 68 watch / 152 large / 43 unknown | discover bands |
| Cheap-pass health check | 342 processed | mechanical kill-flag scan |
| Cheap-pass survivors | 212 | 130 rejected (kill-flag>=3 / cash-burn) |
| SIC gate (tri-state) | 212 | keep=92, review=120, drop=0 |
| Candidates JSON (deep band) | **163 deep** | the deep-dive-eligible cohort |
| LLM theme-fit gate (Gate 2), true members | **8** | 155 misrecalls dropped |
| Deep-dived (every deep-band survivor) | **8** | SIDU, BKSY, GILT, GOGO, KVHI, GHM, ODYS, POCI |
| Valuated | 8 | all `--json` + `--ticker` |
| **Mechanical BUYs** | **0** | |
| **BUYs surviving adversarial check** | **0** | |

The theme-fit gate is the load-bearing precision step here. `space` is a catastrophic keyword for
over-recall: it matched dozens of REITs ("office space", "retail space"), every Invesco
CurrencyShares / commodity / crypto ETF trust, biotech ("satellite trial sites", "LEO" / "GEO" /
"payload" as substrings in genetics text), restaurants, gold miners, and broadcast media. Of 163
deep-band names, only 8 are genuine space-economy industrial participants (4.9% gate-2 precision ,
consistent with the documented ~7% precision base rate for hot single-keyword themes).

---

## 2. Ranked shortlist (all WATCH, see RANKING.md)

| # | Ticker | Name | Fit | Mktcap | Rating | Why not BUY |
|---|---|---|---|---|---|---|
| 1 | BKSY | BlackSky Technology | pure_play | $1,076M | 观察 | buy_eligible but MoS null (FCF-negative -$28M OCF; intrinsic band uncomputable) |
| 2 | GHM | Graham Corp | partial | $1,295M | 观察 | buy_eligible but MoS -96.7% (trades ~25x conservative FCF-cap intrinsic) |
| 3 | GILT | Gilat Satellite Networks | pure_play | $995M | 观察 | buy_eligible=False (debt_truncation + cross_source_mismatch); NAV MoS -77.8% |
| 4 | GOGO | Gogo Inc. | partial | $461M | 观察 | buy_eligible but MoS -100% (NAV band $0) + **material_weakness** kill-flag |
| 5 | KVHI | KVH Industries | partial | $188M | 观察 | buy_eligible but NAV MoS -45.8% (~1.5x tangible book, no margin) |
| 6 | ODYS | Odysight.ai | partial | $68M | 观察 | buy_eligible=False (cross_source_mismatch); MoS null; low_revenue_loss flag |
| 7 | POCI | Precision Optics | partial | $63M | 观察 | buy_eligible=False (cross_source_mismatch); MoS null (FCF-negative) |
| 8 | SIDU | Sidus Space | pure_play | $314M | 观察 | buy_eligible=False (cross_source_mismatch); MoS null; **+408% dilution**, rev -54% |

No name sank to AVOID and none reached BUY. All eight are landmine-scanner WATCH outputs warranting
human DD, not buy signals.

---

## 3. BUY analysis, honest 0-BUY

**There are zero mechanical BUYs.** Per the BUY rule a BUY needs `mos_basis in {fcf_cap,nav}` AND
numeric `MoS >= 30` AND `buy_eligible == true` AND zero kill-flags. The candidate set splits into
two failure modes, both correct:

**Mode A, blocked by a v0.3.0 guard (`buy_eligible == false`):**
- **SIDU**: `cross_source_mismatch`, shares_outstanding SEC=24.7M vs yfinance=97.2M (3.9x). A
  corrupted share count cannot back a tradeable MoS. (Independently: de-SPAC with revenue collapsing
  $6.25M→$1.78M while NI worsens to -$29.5M, and **+408% dilution**, the death-spiral signature.
  This is the pre-rev/de-SPAC/low_revenue_loss focus path firing exactly as designed:
  `low_revenue_loss_ratio=True`.)
- **GILT**: `debt_truncation_suspected` + `cross_source_mismatch` (total_debt SEC=2.0M vs yf=7.5M,
  3.7x). FCF-cap model marked unsuitable → routed to NAV; NAV MoS -77.8% anyway.
- **ODYS**: `cross_source_mismatch`; tiny $3M revenue vs -$17M loss → `low_revenue_loss_ratio=True`.
- **POCI**: `cross_source_mismatch`; FCF-negative, intrinsic band unavailable.

**Mode B, `buy_eligible == true` but no margin of safety (the true test of the valuation layer):**
- **BKSY**: MoS null. OCF -$28M, NI -$70M; no conservative intrinsic band is computable for a
  cash-burning name (`mos_null_reason=intrinsic_band_unavailable`). Trades ~10x sales.
- **GHM**: MoS **-96.7%** (fcf_cap). Conservative 5yr-trailing-avg normalized FCF = $5.95M (the
  window includes the FY21 to 22 acquisition-integration trough with negative OCF), capitalized at
  9 to 12% → equity band $43 to 60M vs $1,295M market cap. ~100x P/E. No artifact, the cyclical
  normalizer is deliberately refusing to extrapolate the recent $24 to 28M OCF peak.
- **GOGO**: MoS **-100%** (NAV band $0 after goodwill/intangible deduction, heavy net debt) AND a
  `material_weakness` kill-flag detected at deep-dive, fails the BUY rule on two independent counts.
- **KVHI**: NAV MoS **-45.8%**; $188M cap vs $102 to 134M tangible-NAV band (~1.5x tangible book).

---

## 4. Adversarial verification (for every name that came closest to BUY)

The four `buy_eligible==true` names (BKSY, GHM, GOGO, KVHI) are the ones where a data/model artifact
*could* have either created a false BUY or suppressed a real one. Verdicts:

- **GHM, correct rejection, not artifact.** The low intrinsic band traces to honest cyclical
  normalization (trough years in the 5yr window), not a parsing bug. A skeptical PM agrees a
  ~100x-P/E, ~25x-intrinsic space/defense industrial is not a value BUY. Reverse-DCF implied growth
  9.5%, reasonable embedded expectation, zero margin of safety. **Real opportunity? No.**
- **BKSY, correct rejection.** Richly-valued, FCF-negative de-SPAC; null MoS is the right answer
  (you cannot compute a conservative intrinsic floor for sustained cash burn). Growth is real
  ($21M→$107M) but that is a momentum/story case, not a MoS case. **Real opportunity? No (on this
  framework).**
- **GOGO, correct rejection, doubly.** Negative NAV + material_weakness. Even setting aside MoS,
  the kill-flag alone disqualifies. **Real opportunity? No.**
- **KVHI, correct rejection.** Trades above tangible book with no margin; the post-pivot
  asset-light maritime-VSAT model is interesting but not cheap. **Real opportunity? No.**

No suppressed BUY found; no artifact BUY found. `n_buy_clean = 0`.

---

## 5. Code-paths exercised

- **discover.py**, FTS multi-keyword union + mktcap fallback + band assignment (deep/watch/large/unknown).
- **cheap_pass.py**, mechanical kill-flag health check on 342 small-caps (130 rejected).
- **filter_by_sic.sic_classify**, tri-state SIC gate (keep/review/drop); review→LLM gate.
- **LLM theme-fit gate (Gate 2)**, 163→8; recorded in `gate2_results.json` +
  `candidates_gate2_survivors.json`.
- **deepdive_data.py**, full financial/insider/timeline pull for all 8; signals side-channel emitted
  (firewalled sibling namespace, never read by buy_eligible).
- **valuation.py** guards that FIRED:
  - `cross_source_mismatch` (DATA-INTEGRITY gate) → SIDU, GILT, ODYS, POCI
  - `debt_truncation_suspected` → GILT
  - `low_revenue_loss_ratio` (advisory label, focus path) → SIDU, ODYS
  - `fcf_cap_model_unsuitable` → routed GILT/GOGO/KVHI to NAV basis
  - `mos_null_reason=intrinsic_band_unavailable` (FCF-negative) → BKSY, SIDU, ODYS, POCI
  - NAV-basis MoS computation → GILT, GOGO, KVHI
- **deepdive material_weakness kill-flag** → GOGO (killflag_count=1).
- **finalize_run.py**, completeness assert (163 deep / 8 reports / 155 gate2-resolved / **0 missing**),
  verdict block, RANKING rebuild, trust banner.
- **NOT exercised:** SIC reverse-recall floor (no dedicated single SIC for "space economy", the
  theme spans 3663/3812/4812/4899/3560/3827/3845, so no recall floor applies); `concentration_kill`;
  `peak_contamination_veto`; `fundamental_decline_veto`; `low_revenue_loss_ratio_extreme`;
  `insurance`/`financial-SIC` gates; `large_cap`/`extreme_mos` gates.

---

## 6. Data-quality issues

- **Pipeline hang (operational):** the chained `run_theme.py` cheap-pass loop hung at ticker ~320/342
  (edgartools network call with no enforced timeout; log stalled 27 min). Resolved by killing the
  process and re-running `cheap_pass.py` standalone (idempotent), then running the inline SIC-filter
  stage. No data lost, all 342 reprocessed cleanly. Suggests a hard per-ticker timeout wrapper for
  cheap_pass.health_check.
- **cross_source_mismatch on 4 of 8** (SIDU shares 3.9x, GILT debt 3.7x, ODYS, POCI), SEC-vs-yfinance
  disagreement >2.5x. For small/illiquid de-SPACs and foreign filers (20-F) this is common; it
  correctly blocks buy_eligible rather than trusting a corrupted single source.
- **GILT/KVHI/KMDA filed as 20-F / foreign issuers**, XBRL tag coverage thinner; valuation routed to
  NAV where FCF-cap was unsuitable.
- **GHM fiscal-year offset** (FYE March) handled correctly; FY label drift in the raw series
  (`fy:2026` repeated) is cosmetic.

---

## 7. recall@gold

**n/a.** No gold list exists for `space-economy` (gold lists cover water-utilities, railcar-leasing,
regional-gaming, deathcare only). `track_forward.py --recall-gold ... --theme space-economy` returns
"no gold list for theme 'space-economy', not measurable."

---

## 8. Market-intel / Trends (T2 analyst context, does NOT drive buy_eligible)

TrendsMCP quota was exhausted for the day (5/5 daily, 100/100 monthly), so no live trend pull was
captured this run. T2 enrichment is firewalled from the BUY decision by design, so its absence does
not affect any verdict. Qualitative T2 context: the space-economy theme is a textbook "hot theme =
casino" case, branded space/defense ETFs, heavy retail attention, and a wave of 2021-vintage
de-SPACs (SIDU, BKSY) now in the post-hype cash-burn phase. This is precisely the environment where
the skill's edge is *elimination*, and the 0-BUY result is the expected, correct signal.

---

## 9. Skeptical-PM usable verdict

**USABLE.** The funnel is coherent (623→212→163→8), the theme-fit gate correctly stripped a 95%
false-positive keyword recall, every deep-band survivor was deep-dived and valuated (no sampling, no
silent skips, no ERROR files), and the BUY rule produced an honest, well-reasoned 0-BUY. The two
"closest call" cohorts (FCF-negative de-SPACs with null MoS; profitable-but-expensive industrials
with deeply negative MoS) were each rejected for the right mechanical reason and confirmed by
adversarial review as genuine non-opportunities rather than artifacts. The only blemish is
operational (the cheap-pass hang), not analytical.
