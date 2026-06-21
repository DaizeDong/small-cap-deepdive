# Coverage Test — Theme `oilsvc` (Oilfield Services / Drilling / Well Completion)

- **Run batch:** `reports/smallcap/2026-06-21_cov-oilsvc/`
- **Skill version:** v0.3.0 @ commit `f12fef5` (run manifest records `skill_dirty: true` — workspace had uncommitted gate2 helper files written during the run; the tool code itself was unmodified)
- **Sector classification:** REGRESSION
- **Keywords:** `oilfield services, drilling, well completion`
- **Code-path focus:** cyclical consistency
- **Date:** 2026-06-21 (run executed) / coverage-test-2026-06-20 cohort
- **Skeptical-PM bottom line:** **USABLE.** The pipeline produced a disciplined, fully-covered OFS shortlist, correctly stripped 21 of 40 deep-band names as theme misrecalls, and surfaced exactly one mechanical BUY — which adversarial review then correctly identified as a normalization artifact. **Net: 0 clean BUYs, which is the right answer for this theme in this cycle.** The run also exposed a genuine, reportable blind spot in the cyclical-consistency guard (see §Code-paths).

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery (FTS ∪ SIC reverse-recall, pre-mktcap) | 78 | per RANKING banner |
| Small-cap universe written | 90 | `universe_oilsvc_2026-06-21.csv` (cheap_pass scanned 90) |
| cheap_pass survivors | 59 | 4 rejected pre-list (PROP, ULBI, EP, NINE — going-concern+substantial-doubt / concentration kill) |
| SIC gate (keep+review) | 59 | keep=55, review=4 |
| Candidates JSON | 59 | band: deep=40, watch=18, unknown=1 |
| **Deep band (band=deep)** | **40** | the deep-dive-eligible cohort |
| **Gate 2 LLM theme-fit survivors** | **19** | 16 pure_play + 3 partial; **21 dropped as misrecall** |
| Deep-dived (deepdive_data + valuation) | 19 | every survivor, no sampling; 0 ERROR files |
| **Mechanical BUYs** | **1** | TUSK |
| **Clean BUYs (post-adversarial)** | **0** | TUSK rejected as artifact |

Structured funnel: `{raw: 78, deepdived: 19, survivors: 19}` (survivors = the 19 that earned a full deep-dive; "deepdived" identical here because all 19 survivors were deep-dived).

### Gate 2 theme-fit detail (the precision win)
21 deep-band names were dropped as **misrecall** — the FTS keyword "oilfield services / drilling / well completion" over-recalled the entire upstream oil & gas complex plus several off-theme names:

- **Pure E&P producers (not service providers):** BATL, PNRG, VTS, REPX, HPK, KOS, AMPY, INR, REI, GPRK, EGY
- **Royalty / trusts:** KRP, MVO, VOC
- **Off-theme entirely:** NRIM (bank), STEL (bank), MH (McGraw Hill — education publisher), ACTG (Acacia — patent/value acquirer), IPI (Intrepid Potash — potash/ag), APC (ARKO Petroleum — wholesale fuel distributor, downstream), FURY (gold miner)

This is the canonical Gate-2 value: SIC alone keeps E&P (1311) and miners in the net; only the LLM blurb read separates true OFS (services/equipment vendors to E&P) from the producers they serve. **19/40 = 47.5% precision after Gate 2** — typical for a broad commodity keyword.

---

## 2. Ranked shortlist (all 观察 / WATCH — no BUY)

Top of `RANKING.md` (rank-ordered alphabetically within the tied WATCH tier; confidence 40% except TUSK 30%):

| Ticker | Name | Gate2 | mos_basis | eff MoS | buy_eligible | ineligible_reasons | Note |
|---|---|---|---|---|---|---|---|
| TUSK | Mammoth Energy Svcs | pure_play | fcf_cap | **+55.1%** | true | none | **mechanical BUY → adversarial-rejected (artifact)** |
| BOOM | DMC Global | partial | fcf_cap | +24.8% | true | none | near-miss, below +30% |
| HLX | Helix Energy | pure_play | fcf_cap | +2.1% | false | fcf_sustainability_uncertain | |
| OIS | Oil States Intl | pure_play | fcf_cap | -25.7% | true | none | |
| RNGR | Ranger Energy | pure_play | fcf_cap | -44.3% | true | none | |
| RES | RPC Inc | pure_play | fcf_cap | -62.6% | false | cross_source_mismatch (P7) | |
| SND | Smart Sand | partial | fcf_cap | -44.5% | false | cross_source_mismatch (P7) | |
| CLB | Core Laboratories | pure_play | fcf_cap | -77.1% | true | none | |
| PUMP | ProPetro | pure_play | fcf_cap | -82.5% | true | none | |
| FET | Forum Energy Tech | pure_play | fcf_cap | -89.6% | true | none | soft going-concern kw, no substantial doubt |
| TTI | TETRA Technologies | pure_play | fcf_cap | -98.5% | true | none | |
| ACDC | ProFrac | pure_play | fcf_cap | -127.6% | false | extreme_mos_review_required, peak_contamination_flag | |
| WBI | WaterBridge Infra | partial | fcf_cap | -140.5% | false | extreme_mos_review_required, fcf_sustainability_uncertain | |
| BORR | Borr Drilling | pure_play | fcf_cap | -189.9% | false | extreme_mos_review_required, fcf_sustainability_uncertain | |
| NCSM | NCS Multistage | pure_play | nav | -36.7% | true | none | NAV basis negative |
| XPRO | Expro Group | pure_play | nav | -52.7% | true | none | NAV basis negative |
| INVX | Innovex Intl | pure_play | nav | -59.4% | true | none | **material_weakness (kf=1)** — Dim1 cap |
| KLXE | KLX Energy Svcs | pure_play | nav | -100.0% | false | peak_contamination_flag | soft going-concern kw |
| PDS | Precision Drilling | pure_play | fcf_cap | null | true | none | **40-F foreign filer — revenue XBRL = $0M (data gap)** |

**The OFS cycle context explains the wall of negative MoS:** 2025 was a trough/declining year for North American completion activity (rig counts down, frac fleet utilization soft). With fcf_cap MoS measured against a normalized FCF that includes recent weak years, most names trade ABOVE conservative intrinsic value (negative MoS) — i.e. the market is NOT mispricing the sector cheaply. This is the skill working as designed: a hot/known commodity theme yields few or no genuine bargains.

---

## 3. The single mechanical BUY — TUSK (adversarial verdict: REJECT / ARTIFACT)

**Mechanical record (all guards passed):** `mos_basis=fcf_cap`, `margin_of_safety_pct=+55.1%`, `buy_eligible=true`, `buy_ineligible_reasons=[]`, `killflag_count=0`, `concentration_flag=null`, `peak_contamination_flag=false`, `fundamental_decline_flag=false`, `cross_source_mismatch=false`. By the v0.3.0 BUY rule this is a clean mechanical BUY.

**buy_eligible composite — why every guard passed:**
- not extreme_mos_review (MoS +55%, within band) ✓
- not large_cap (mktcap $146M) ✓
- not fcf_sustainability_uncertain ✓ (but see below — this is the false-negative)
- not financial_sic / not insurance_concepts ✓ (SIC 1389)
- not debt_truncation / not wrong_entity ✓ (`total_debt=0`, shares OK, ticker in registry)
- concentration_flag != kill ✓ (text flag true but XBRL magnitude null → `concentration_unquantified`, advisory only)
- not fundamental_decline_flag ✓ **← see artifact analysis**
- not peak_contamination_flag ✓ **← see artifact analysis**
- not low_revenue_loss_ratio_extreme ✓
- not cross_source_mismatch ✓ (yfinance within 2.5x — but second source agrees on the SAME corrupted continuing-ops figures)

**Adversarial verdict: this is a DATA/MODEL ARTIFACT, not a real opportunity.**

Evidence (T1 filing + corroborating reporting):
1. **Mammoth dismantled itself in 2025.** It sold its infrastructure subsidiaries (Apr, ~$108.7M, ~9x EBITDA), hydraulic-fracturing equipment (Jun, $15M), natural-sand proppant (Sep), and the Aquawolf engineering business (Dec, ~$30M) — >$150M cash proceeds, ALL reclassified as **discontinued operations for every period presented**. The remaining "continuing operations" are a stub (FY2025 revenue $44.3M, Q4 revenue $9.5M).
2. **Every current metric is negative:** latest OCF -$18.6M, latest EBITDA -$29.7M, latest FCF -$89.1M, continuing-ops Adjusted EBITDA -$17.4M, Q4 2025 EPS -$0.26 (missed -$0.08).
3. **The +55% MoS is normalized off a contaminated trailing-5yr OCF series:** OCF history = 2018 $386.7M, 2019 -$95.3M, 2024 $180.7M (PREPA settlement-driven, not operating), 2025 -$18.6M. `cv_ebitda=0.8587` (3.4x the 0.25 cyclical threshold). `lumpy_ocf_normalization_suspect=true` ("peak_year_ocf=15.3M>2x median 6.4M"). The model's `normalized_fcf=$16.0M` is an average across a regime that no longer exists (divested units + a one-time legal settlement).
4. **EV anomaly:** EV $53M vs market cap $146M (net cash ~$93M post-divestitures, `total_debt=0`). The +55% MoS is partly the cash pile, not operating value — and the business consuming that cash (pivot to aviation leasing + fiber) is a different company than the OFS trailing average implies.

**Conclusion:** TUSK is a melting-ice-cube / restructuring-discontinuity that the cyclical guard structurally cannot see (next section). Mechanically eligible, fundamentally not a buy. **n_buy_clean = 0.**

T2 corroboration (NOT used in the decision): the firewalled diagnostic `signals.price_divergence.divergence_label = "melting_ice_cube_priced"` independently tagged TUSK as a priced-in melting ice cube. This is consistent with the adversarial verdict but did NOT and must NOT drive it — the rejection stands entirely on T1 filing fundamentals + the discontinued-ops disclosure.

---

## 4. Code-paths exercised (cyclical-consistency focus)

This theme is a cyclical sector by construction (OFS revenue tracks rig count / oil price), so the cyclical-normalization and the two cyclical vetoes were heavily exercised:

- **`cyclical=true` / trailing-5yr-avg normalization** — fired on most names (high cv_ebitda). This is the core path under test.
- **`peak_contamination_flag` (V-shape veto, P-A)** — FIRED on ACDC and KLXE (forced `buy_eligible=false`, downgraded to WATCH). Working as designed.
- **`fundamental_decline_flag` (melting-ice-cube veto, P6)** — evaluated on all; fired on none of the survivors (most had `rev_slope_sign>=0` or a degenerate base).
- **A1 degenerate-base guard (`0 < contamination_ratio`)** — **THIS IS THE KEY FINDING.** On TUSK, `contamination_ratio = -0.4889` (negative normalization base). The A1 guard, by design, makes BOTH `peak_contamination_flag` and `fundamental_decline_flag` ABSTAIN on a negative base (the `0<` lower bound). Intended to stop BWIN-style false-positive vetoes on negative bases — but here it produced a **false NEGATIVE**: a genuinely contaminated cyclical name slipped through because its base was negative, while the trailing-average normalization still computed a *positive* $16M normalized FCF and a +55% MoS from the same lumpy series. The two cyclical guards and the normalization disagree about whether the base is trustworthy, and only the guards abstained — the MoS did not.
- **`lumpy_ocf_normalization_suspect`** — FIRED on TUSK (data_quality only; advisory, does NOT gate). It caught the problem descriptively but has no mechanical bite.
- **`cross_source_mismatch` (P7 second-source band)** — FIRED on RES and SND (forced `buy_eligible=false`). This is the first external (yfinance) integrity check biting in production. Note it did NOT fire on TUSK because yfinance reports the same corrupted continuing-ops figures (both sources agree on a wrong number → P7 is blind to it, as documented).
- **`extreme_mos_review_required`** — FIRED on ACDC, BORR, WBI (MoS < -100%).
- **`concentration_unquantified`** — advisory on TUSK (text concentration flag true, XBRL magnitude null).
- **Soft going-concern keyword vs substantial-doubt qualifier** — FET, BORR, KLXE carry `kf_going_concern=1` but `kf_substantial_doubt=0`; cheap_pass correctly did NOT hard-reject them (only gc+substantial-doubt rejects, as PROP/EP/NINE were). Sensible: avoids killing on boilerplate risk-factor language.
- **`material_weakness`** — INVX (kf=1); caps Dim1, surfaced, does not auto-AVOID.
- **40-F / foreign-filer XBRL gap** — PDS (Precision Drilling) returned `revenue=$0M` (40-F revenue concept didn't map). `form_used` provenance present but the financial series is empty → MoS null. Data-quality issue, not a model error.
- **finalize_run A5 misrecall resolution** — 21 gate2 misrecalls correctly counted as "resolved, not missing"; missing=0 with no `--allow-missing` needed.
- **Firewall (iter4)** — verified: deepdive carries top-level `signals` (price_divergence, ownership, signals_meta); `valuation.py` output has NO `signals` key; `buy_eligible` did not read it. Firewall intact.

**Recommended fix (reportable, not applied):** when `contamination_ratio < 0` (degenerate/negative base) AND the trailing-average normalization nonetheless yields a positive `normalized_fcf`, the cyclical path should treat the normalization itself as untrustworthy — either route to `fcf_sustainability_uncertain=true` (which would have flipped TUSK to ineligible) or escalate `lumpy_ocf_normalization_suspect` from advisory to gating. Right now a negative base silences the vetoes but not the MoS, which is the exact gap TUSK exploited.

---

## 5. Data-quality issues

1. **TUSK revenue/OCF series mistagged & contaminated** — the `end`/`fy` labels are misaligned and the series mixes pre-divestiture consolidated figures with post-divestiture continuing-ops; produced the phantom +55% MoS. Primary artifact of the run.
2. **PDS (Precision Drilling) — 40-F foreign filer, revenue XBRL = $0M.** Financial series empty; MoS null. Recall floor caught the name (good) but the financials did not load.
3. **RES, SND — `cross_source_mismatch` (P7)** between SEC XBRL and yfinance on debt/revenue/shares (>2.5x). Correctly gated to ineligible; flagged as data integrity, not necessarily corporate distress.
4. **VTS, HPK, REPX, KOS, BORR, PDS blurbs empty/TOC-only** in the candidates file — Gate 2 had to lean on SIC + name for a few (VTS/HPK/REPX/KOS were misrecall E&P anyway; BORR/PDS are clearly drillers by name and were retained correctly).
5. **`concentration_unquantified` widespread** — many OFS names disclose customer concentration in 10-K text but the XBRL `RevenueFromContractWithCustomer` segment members are null, so the magnitude-based `concentration_flag` stays null. Advisory only; analyst must read the footnote.

---

## 6. Recall@gold

**n/a.** `oilsvc` is not one of the four gold-list themes (water-utilities / railcar-leasing / regional-gaming / deathcare). `track_forward.py --theme oilsvc --recall-gold <candidates>` returns: *"no gold list for theme 'oilsvc' — not measurable."* No recall floor can be quantified for this theme.

---

## 7. Market-intel / T2 analyst context (does NOT drive any BUY)

- **TrendsMCP:** rate-exhausted for the day (5/5 daily, 100/100 monthly) — no fresh trends pull available this run.
- **Web/news context (T2):** North American OFS was in a cyclical soft patch through 2025 (declining completion activity, soft frac utilization), consistent with the wall of negative fcf_cap MoS across the shortlist — the market is pricing the sector at or above conservative intrinsic value, not at a bargain. The one name that screened "cheap" (TUSK) was cheap only because of a corporate breakup, not a cyclical mispricing.
- **Firewalled diagnostic signal (context only):** TUSK `price_divergence = melting_ice_cube_priced` — corroborates the adversarial reject. Reminder: this is diagnostic-only and gated nothing.

---

## 8. Skeptical-PM verdict

**USABLE.** A PM can act on this run: the universe was fully enumerated and theme-filtered with no sampling, every survivor was deep-dived (0 errors), the misrecall set is auditable and correct, and the single mechanical BUY was caught and correctly killed by adversarial review before it could reach a buy list. The honest output is **0 clean BUYs for OFS in this cycle** — which is the disciplined, expected answer for a known cyclical commodity theme at a non-trough valuation. The run additionally produced one genuinely actionable engineering finding (the negative-contamination-base blind spot in the cyclical guard) that strengthens, rather than undermines, trust in the framework: the failure mode was visible in `lumpy_ocf_normalization_suspect`, `cv_ebitda`, and the firewalled `melting_ice_cube_priced` signal, so a careful analyst is never blindsided.
