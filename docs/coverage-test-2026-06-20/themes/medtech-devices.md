# Coverage Test — Theme: medtech-devices (Medical Devices / Surgical Instruments)

- **Sector:** HealthCare
- **Keywords:** `medical devices, surgical instruments`
- **Run batch:** `reports/smallcap/2026-06-21_cov-medtech-devices/`
- **Skill version:** v0.3.0 (commit `f12fef5`, run manifest `skill_dirty=true`)
- **Code-path focus:** EBIT cascade (`ebit_source`)
- **Date:** 2026-06-21 (run executed under cov label)
- **Verdict in one line:** **0 mechanical BUYs. Correct "nothing found."** The small-cap
  medical-device universe is dominated by pre-profit, cash-burning growth-stage names whose
  negative normalized FCF makes a DCF intrinsic band — and therefore a margin of safety —
  uncomputable. The handful that are FCF-positive trade well above intrinsic value.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery (universe CSV) | 345 rows | EDGAR FTS on keywords UNION SIC reverse-recall + mktcap fallback |
| Small-cap deep band (mktcap < $2.0B) | 37 | watch-band ($2.0B–$5.0B) = 8, surfaced separately, no deep-dive |
| cheap_pass survivors | 45 | kill-flag scan (going-concern / death-spiral / ICFR / concentration) |
| After SIC Gate 1 | 45 | keep=5, review=40 (review → LLM Gate 2) |
| Candidates JSON (deep+watch) | 45 | 37 deep, 8 watch |
| **Deep-dived (every deep-band survivor)** | **37 / 37** | **0 ERROR files, 0 silent-skips** |
| Valuated (`--json` + `--ticker`) | 37 / 37 | all produced a `mos_basis` |
| LLM theme-fit (Gate 2, my judgment) | 27 members / 10 misrecall | recorded in `gate2_results.json` |
| **Mechanical BUYs** | **0** | none satisfy MoS≥30 ∧ buy_eligible ∧ basis∈{fcf_cap,nav} ∧ 0 kill-flags |
| Reports + verdicts (finalize_run) | 37 reports, 0 missing | RANKING.md rebuilt, 10 gate2-misrecall resolved |

**Funnel for the structured object:** raw=345, deepdived=37, survivors=37 (all deep-band
survivors that reached deep-dive; none eliminated post-deepdive by the pipeline, the BUY gate
simply produced zero buys).

---

## 2. Code-paths fired (coverage evidence)

### EBIT concept cascade (focus)
`ebit_source` distribution across 37 valuations — all three rungs exercised:

| `ebit_source` | Count | Tickers |
|---|---|---|
| `OperatingIncomeLoss` (tier 1, direct XBRL) | 34 | majority |
| `pretax+interest_addback` (tier 3 fallback) | 1 | **WOK** |
| `None` (no resolvable EBIT) | 2 | **GHRS, SOPH** (pre-revenue / shell-like) |

The cascade fell through from the primary XBRL concept to the pretax + interest add-back
reconstruction (WOK) and to a clean null (GHRS, SOPH) where no operating-income concept exists.
The focus code-path is fully covered.

### Valuation basis routing (`mos_basis`)
- `fcf_cap` = 29, `nav` = 8, `abstain` = 0. Every name got a basis; 8 were routed FCF→NAV
  via `fcf_cap_model_unsuitable_use_nav`.

### `buy_eligible` guards that fired (16 ineligible names, 6 distinct guard families)
| Guard | Count | Tickers |
|---|---|---|
| `cross_source_mismatch` | 11 | AVNS, BNR, LNSR, MYO, NVEC, POCI, QSI, STAA, SY, TNDM, WOK |
| `extreme_mos_review_required` | 4 | BVS, ENOV, RDGT, TNDM |
| `low_revenue_loss_ratio_extreme` | 2 | PLSE, QSI |
| `fcf_sustainability_uncertain` | 1 | AVNS |
| `wrong_entity_suspected` | 1 | BNR |
| `fundamental_decline_flag` | 1 | EMBC |

### Other guards observed in data_quality (not all gating)
debt-truncation proxy (8: `debt_is_total_liabilities_proxy`), `low_revenue_loss_ratio` (2),
`lumpy_ocf_normalization_suspect` (6), `peak_contamination` evaluated (0 fired),
`debt_stale` (4), NAV path with goodwill/intangibles unavailable (6).

### Signals firewall (P16/P17)
Verified: 0 valuation files contain a `signals` key; the diagnostic side-channel is present on
the deepdive JSONs only (e.g. `deepdive_AORT` has `signals`). `buy_eligible` is byte-isolated
from signals — the firewall holds. The signals channel did NOT touch any BUY decision (there
were none to touch).

---

## 3. Ranked shortlist (non-floor, top tier)

All 27 non-floor names are rated **观察 / WATCH** (no BUY qualifies). Top by RANKING order:

| Rank | Ticker | Name | Rev | NI | OCF | Growth | Kill-flags | Theme-fit |
|---|---|---|---|---|---|---|---|---|
| 1 | AORT | Artivion (aortic/cardiac surgical devices) | $441M | +$10M | +$40M | +14% | 0 | pure_play |
| 2 | AVNS | Avanos Medical | $701M | -$73M | +$75M | +2% | 0 | pure_play |
| 3 | BVS | Bioventus (musculoskeletal) | $568M | +$23M | +$75M | -1% | 0 | pure_play |
| 9 | IRMD | IRADIMED (MRI-compatible devices) | $84M | +$22M | +$25M | +14% | 0 | pure_play |
| 20 | PRCT | PROCEPT BioRobotics (urology robotics) | $308M | ~$0 | -$49M | +37% | 0 | pure_play |
| 27 | TNDM | Tandem Diabetes (insulin pumps) | $290M | -$1M | -$10M | +3% | 0 | pure_play |

Profitable members (positive NI + OCF): **AORT, BVS, IRMD**. These are the only names where a
DCF band was computable AND positive cash flow exists — yet IRMD's MoS = -88% (overvalued),
and AORT/BVS land in `intrinsic_band_unavailable` (normalized FCF still net negative across the
window). None clears the 30% MoS threshold.

Full per-ticker due-diligence scaffolds: `reports/smallcap/2026-06-21_cov-medtech-devices/report_<ticker>.md`.

---

## 4. BUY analysis — honest 0-BUY

**There are no mechanical BUYs, so there is no adversarial-verification target.** `n_buy_clean = 0`.

Why zero, mechanically (the BUY rule: `mos_basis∈{fcf_cap,nav}` ∧ numeric MoS≥30 ∧
`buy_eligible==true` ∧ 0 kill-flags):

- **21 names are `buy_eligible==true`** but every one fails on MoS:
  - 16 have **MoS = None** (`intrinsic_band_unavailable` — negative normalized FCF → no
    reverse-DCF band can be built). This is the structural signature of cash-burning,
    growth-stage medical-device companies (LUNG, CVRX, SGHT, KIDS, NVCR, PRCT, SIBN, STIM, …).
  - 5 have a numeric but **negative** MoS — overvalued vs intrinsic: IRMD -88%, KRMD -93%,
    OSUR -31%, PSNL -82%, SKIN -100%.
- **16 names are `buy_eligible==false`**, blocked by the guards above. The only positive-MoS
  name in the entire run — **RDGT at +1690.9%** — is a $1M reverse-merger shell (SIC 5912 drug
  stores) and is correctly killed by `extreme_mos_review_required`. This is exactly the data
  artifact the extreme-MoS guard exists to catch; had the guard been absent, RDGT would have
  been a spurious BUY.

This is a **correct and useful "nothing found."** The neglected small-cap medical-device
universe right now is structurally pre-profit; neglect here is efficiently priced, and the few
profitable names are not cheap. A scanner that returned a BUY here would be a narrative generator.

### Mini-adversarial on the near-misses (would any be a real opportunity if the gate were looser?)
- **RDGT (+1690% MoS):** artifact, not opportunity. $1M shell, reverse merger, SIC = drug
  stores, NAV driven by a tiny tangible-equity base vs a near-zero market cap. Correctly killed.
- **IRMD (FCF-positive, -88% MoS):** real, high-quality niche business (MRI-compatible IV
  pumps), but priced at ~21x EV/EBITDA equivalent — genuinely expensive, not a data error. The
  negative MoS is a true valuation signal, not an artifact.
- **AORT (profitable, MoS None):** real business; the None is because 5-yr normalized FCF is
  still net-negative (recent turn to profit). Merits human diligence as a WATCH, not a BUY.

---

## 5. Data-quality issues (material for a skeptical PM)

| Issue | Count / 37 | Read |
|---|---|---|
| `cross_source_mismatch` (yfinance vs SEC > 2.5×) | 11 | **Highest-impact.** Mostly total_debt and revenue disagreements on recently-IPO'd or foreign-filer (ADR) medtech. yfinance frequently reports a TTM/consolidated figure vs SEC's filed annual — e.g. TNDM revenue SEC $290M vs yf $1027M (3.5×), BNR SEC $77M vs yf $514M (6.7×), SY revenue 7.6×. The guard correctly blocks BUY rather than trust a possibly-stale second source. |
| `net_income_nonpositive_pe_null` | 31 | Universe is overwhelmingly loss-making — expected for growth medtech. |
| `intrinsic_band_null` | 30 | Negative normalized FCF → no DCF band. This is *the* reason for 0 BUY. |
| `ebitda_nonpositive` / partial EBITDA series | 18 / 15 | EV/EBITDA undefined for most; multiples sparse. |
| `concentration_unquantified` (text flag, no XBRL magnitude) | 15 | Concentration language present but unquantified; advisory only, did not kill. |
| `debt_is_total_liabilities_proxy` | 8 | Debt fallback used (no clean debt concept) — inflates NAV liabilities conservatively. |
| `wrong_entity_suspected` | 1 (BNR) | China VIE / ADR structure — second-source check flagged entity mismatch. |
| `low_revenue_loss_ratio_extreme` | 2 (PLSE, QSI) | PLSE rev ≈ $0 with large loss; QSI similar — pre-commercial. |

Foreign filers / ADRs (BNR, SY, EDAP, GHRS, SOPH, WOK) are the main source of cross-source and
wrong-entity noise. A PM should treat any yfinance-derived figure on these names as unreliable;
the SEC-filed numbers are authoritative and the guard's instinct to block is correct.

---

## 6. recall@gold

**n/a.** There is no gold cohort for `medtech-devices` (gold lists exist only for
water-utilities, railcar-leasing, regional-gaming, deathcare — confirmed via
`track_forward.theme_gold('medtech-devices') == []`). `track_forward.py --recall-gold` was not
applicable and not run for a score.

---

## 7. Market-intel / Trends (T2 analyst context)

**Not available this run.** TrendsMCP daily and monthly quota were exhausted (5/5 daily,
100/100 monthly) before a medtech query could be issued; no cached medtech report exists in the
local market-intel repo (`/c/Users/dzdon/CodesSelf/market-intel/reports/` has no med/device/surg
file). T2 context is labeled-optional and **never drives `buy_eligible`**, so its absence does
not affect the mechanical result. Qualitatively (analyst prior, not data): small-cap medtech in
2026 remains a capital-intensive, FDA-gated, pre-profit cohort — consistent with the funnel's
30/37 "no intrinsic band" outcome.

---

## 8. Skeptical-PM usable verdict

**USABLE — and the answer it gives is the correct one: do nothing here.**

The pipeline executed cleanly end-to-end on a 37-name deep band with zero crashes and zero
silent-skips, exercised the EBIT cascade across all three rungs, fired six distinct
`buy_eligible` guard families, and correctly killed the single positive-MoS artifact (RDGT
shell). The 0-BUY outcome is mechanically explained (pre-profit universe → no DCF band → no
MoS) rather than a coverage failure. The biggest caveat for a PM is the 11/37
cross-source-mismatch rate, concentrated in ADRs/recent IPOs — but the tool handles it the
conservative way (block, don't guess). I would trust this run's "nothing to buy" and would use
the WATCH list (AORT, IRMD, BVS as the profitable trio) as a human-diligence queue, not a buy
list.

---

### Artifacts
- Run dir: `C:\Users\dzdon\CodesSelf\small-cap-deepdive\reports\smallcap\2026-06-21_cov-medtech-devices\`
- RANKING: `…\RANKING.md`
- Verdicts: `…\deepdive_verdicts.json` (27 观察 / 10 避开, 0 买入)
- Theme-fit: `…\gate2_results.json` (24 pure_play / 3 partial / 10 misrecall)
