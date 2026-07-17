# Coverage Test, Theme: Semiconductors (InfoTech)

- **Slug:** `semiconductors`
- **Sector:** InfoTech
- **Keywords:** `semiconductor, chip design, fabless`
- **Skill version:** v0.3.0 (commit `f12fef5`, run manifest records `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-semiconductors/` (env `SMALLCAP_RUN=2026-06-21_cov-semiconductors`; tool date stamped 2026-06-21)
- **Code-path focus:** cyclical / V-shape (peak-contamination) veto
- **Headline:** **0 BUYs.** 19 deep-band survivors deep-dived in full, all rated WATCH (观察). This is an honest 0-BUY hot-theme result, not a coverage failure.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw recall (de-duped) | 200 | `semiconductor` 144 + `chip design` 69 + `fabless` 100 → 200 unique |
| After mktcap/listing resolution | 200 priced; 87 deep (<\$2.0B) + 17 watch (\$2.0 to 5.0B) | yfinance; several delisted tickers dropped (IVAC, INFN, LAZRQ, ALTR, ANSS, etc.) |
| Into cheap_pass | 88 | small-cap band |
| cheap_pass + SIC gate survivors | 32 | SIC filter: 26 keep + 6 review → all 32 retained for Gate 2 |
|, of which band=deep | 25 | (7 of the 32 are band=watch, surfaced not deep-dived) |
| Gate 2 (LLM theme-fit) drops | 6 misrecall | AIRG, CRNT, DQ, HYSR, AZTA, MOB |
| **Deep-band survivors deep-dived** | **19** | full deepdive + valuation on every one; 0 ERROR files |
| Mechanical BUYs | **0** | none reach MoS ≥ +30% on any basis |
| BUYs surviving adversarial review | **0** | n/a, nothing to adversarially confirm |

`finalize_run` audit: deep-band candidates 25, reports 19, gate2-misrecall (resolved, not deep-dived) 6, **missing 0**. Clean.

**Note on RANKING.md funnel line:** the auto-generated banner reads "20 家 deep dive", an off-by-one in `rank.py`'s own stage counter (it counts the candidates file differently). The authoritative count is **19 reports / 19 verdicts**, confirmed by `finalize_run` and the verdicts file.

---

## 2. Gate 2 theme-fit (judged from 10-K/20-F blurbs)

**Dropped as misrecall (6, band=deep):**

| Ticker | Why dropped |
|---|---|
| AIRG (Airgain) | Wireless antennas / connectivity (SIC 3663), not a chip company |
| CRNT (Ceragon) | Wireless backhaul radio systems (SIC 3663), not a chip company |
| DQ (Daqo New Energy) | Polysilicon for **solar PV** (mis-SIC 3674), not a chip company |
| HYSR (SunHydrogen) | Green-hydrogen nanoparticle cells (mis-SIC 3674), not a chip company |
| AZTA (Azenta) | Life-sciences sample management; exited semiconductor (legacy SIC 3559) |
| MOB (Mobilicom) | Cyber/comms for drones (SIC 3721), not a chip company |

These illustrate the canonical SIC-3674-is-not-destiny problem: solar polysilicon (DQ) and hydrogen nano-cells (HYSR) both carry the semiconductor SIC but are not chip businesses; the LLM blurb gate is what removes them.

**Retained for deep-dive (19): pure_play / partial**, SELX, CVV, VLN, MRAM, CEVA, AOSL, LWLG, DAIO, ICG, HUHU, LTRX, ASYS, INDI, KOPN, SKYT, QNC, BTQ, PXLW, SVCO. (`gate2_results.json` written with explicit per-row verdicts; `candidates_gate2_survivors.json` is the deep-dive universe.)

---

## 3. Ranked shortlist (all WATCH, research output, not a buy list)

`mos_basis` distribution across the 19: **fcf_cap 15, nav 4, abstain 0.** Every effective MoS is deeply negative (overvalued), none anywhere near the +30% trigger.

| # | Ticker | Name | mos_basis | eff. MoS | buy_eligible | conf | kill-flags |
|---|---|---|---|---|---|---|---|
| 1 | BTQ | BTQ Technologies | fcf_cap | null (no FCF) | true | 55 | 0 |
| 2 | CEVA | Ceva | fcf_cap | null | true | 55 | 0 |
| 3 | CVV | CVD Equipment | fcf_cap | null | true | 55 | 0 |
| 4 | DAIO | Data I/O | fcf_cap | null | true | 55 | 1 (MW) |
| 5 | INDI | indie Semiconductor | fcf_cap | null | true | 55 | 1 (MW) |
| 6 | LTRX | Lantronix | fcf_cap | −87% | true | 55 | 1 (MW) |
| 7 | LWLG | Lightwave Logic | fcf_cap | null | false | 55 | 0 |
| 8 | MRAM | Everspin | fcf_cap | −85% | true | 55 | 0 |
| 9 | PXLW | Pixelworks | nav | −24% | false | 55 | 0 |
| 10 | QNC | Quantum eMotion | fcf_cap | null | true | 55 | 0 |
| 11 | SVCO | Silvaco | nav | −92% | true | 55 | 1 (MW) |
| 12 | AOSL | Alpha & Omega Semi | fcf_cap | −84% | **false** | 35 | 0 |
| 13 | ASYS | Amtech Systems | nav | −89% | false | 35 | 1 (MW) |
| 14 | HUHU | HuhuTech | fcf_cap | null | false | 35 | 1 (MW) |
| 15 | ICG | Intchains | fcf_cap | −20% | false | 35 | 1 (MW) |
| 16 | KOPN | Kopin | fcf_cap | null | false | 35 | 1 (MW) |
| 17 | SELX | Semilux | nav | −97% | false | 35 | 0 |
| 18 | SKYT | SkyWater | fcf_cap | null | false | 35 | 1 (MW) |
| 19 | VLN | Valens Semiconductor | fcf_cap | null | false | 35 | 0 |

(Confidence cut to 35 where `cross_source_mismatch` fired, the input numbers themselves are not trustworthy.) **0 sunk** (no AVOID, no kill-flag ≥ 2).

---

## 4. BUYs

**None.** Honest 0-BUY theme.

The mechanical BUY rule (`mos_basis ∈ {fcf_cap, nav}` AND numeric MoS ≥ +30 AND `buy_eligible` AND zero kill-flags) was applied to all 19 and **failed at the MoS step for every name**, this theme is uniformly expensive. The closest any name comes is ICG at **−20% NAV/FCF MoS** and PXLW at **−24% NAV MoS**, both still negative and both `buy_eligible == false` anyway. So even if a guard were toggled off, there is no name within reach of +30%. This is the world-view's "热点主题 = 赌场" outcome rendered numerically: a hot, AI-fuelled sector trades at prices that leave no mechanical margin of safety in the neglected small-cap tail.

Because there are 0 mechanical BUYs, there is nothing to adversarially confirm or refute. `n_buy_clean = 0`.

---

## 5. Code-paths exercised (focus: cyclical / V-shape veto)

| Path | Fired on | Detail |
|---|---|---|
| **cyclical normalization** (trailing-5yr-avg) | 14 / 19 | `cyclical == true` → reverse-DCF / MoS computed off normalized EBITDA/FCF, not trough/peak latest |
| **peak_contamination_flag (V-shape veto, P-A)** | **1, AOSL** | `contamination_ratio = 0.3503` (in 0<cr<0.8), `latest_below_avg = true`, `latest_net_income = −\$96.98M`, `rev_slope_sign = −1` |
| **fundamental_decline_flag (P6)** | **1, AOSL** | same name; `rev_slope_sign < 0` AND `0 < cr < 1.0` AND `latest_below_avg` |
| degenerate-base guard (A1, `0 < cr`) | passive | no name fired a veto on a negative/degenerate base; SELX/CEVA/ICG carry negative `contamination_ratio` and correctly did **not** trip either veto |
| cross_source_mismatch (P7) | **8** | SELX, VLN, AOSL, ICG, HUHU, ASYS, KOPN, SKYT |
| low_revenue_loss_ratio_extreme (A4) | **2** | LWLG, PXLW |
| wrong_entity_suspected | 1 | SELX (also revenue cross-source 31.7×) |
| insurance_concepts / large_cap / financial_sic | 0 | none in scope |

### The headline V-shape catch: AOSL

Alpha & Omega Semiconductor is the textbook exercise of this run's focus path. It is a genuinely **cyclical** power-MOSFET maker (cv_ebitda 0.70) whose latest year shows a trough net loss (−\$97M) below the 5-year normalized base, while the whole-window revenue fit still slopes downward. **Both** mechanical vetoes fire:
- `fundamental_decline_flag = true` (rev_slope_sign −1 path), and
- `peak_contamination_flag = true` (the V-shape sibling that catches the trough-below-average + negative-latest pattern independent of slope sign).

Critically, AOSL was already over-valued (MoS −83.8%), so the veto is **belt-and-suspenders** here, not the decisive factor, the name would be a non-BUY on MoS alone. The veto path is nonetheless properly exercised, and `buy_eligible` is forced `false` with `buy_ineligible_reasons = [fundamental_decline_flag, peak_contamination_flag, cross_source_mismatch]`. This is the intended behaviour: the machine downgrades the cyclical trough on measured data rather than on analyst narrative.

The degenerate-base guard (A1) was confirmed to behave: names with a **negative** `contamination_ratio` (SELX −0.1, CEVA −0.6, ICG −3.7) did **not** falsely trip the `< 0.8` test, exactly the BWIN regression the `0 <` lower bound was added to fix.

---

## 6. Data-quality issues

1. **cross_source_mismatch on 8 of 19 (42%)**, a high rate. The P7 SEC-vs-yfinance second-source band flagged gross (>2.5×) disagreements, almost all on `total_debt` (SEC and yfinance disagree on what counts as debt vs. lease/finance-lease for these small caps), plus two revenue cases (SELX 31.7×; ICG). This is the gate working as designed, it correctly refuses to let an unverifiable single-source SEC number back a tradeable MoS, but the **high hit rate signals the underlying small-cap XBRL/yfinance debt taxonomies are noisy**, and confidence on those 8 names is appropriately capped at 35. For a real analyst these 8 need a manual 10-K balance-sheet read before any number is trusted.
2. **Mis-SIC contamination in discovery**, SIC 3674 swept in solar (DQ) and hydrogen (HYSR) names; the Gate 2 LLM blurb gate is load-bearing here, not optional.
3. **Thin/TOC-only business blurbs** for several foreign filers (SELX, ICG, HUHU, CRNT, DAIO partial, QNC, BTQ, CVV, LWLG returned table-of-contents text rather than the business overview). Gate 2 fit for those leaned on company name + SIC + analyst domain knowledge rather than the captured blurb. A blurb-extraction improvement (skip the TOC, seek the "Overview"/"Business" section) would harden the gate.
4. **Process artifact (mine, not the skill's):** my batch valuation `> valuation_<t>.json` stdout-redirect collided with the path `valuation.py` writes to, overwriting those sidecar JSONs with the human summary text. **No impact on results**, the authoritative valuation block is embedded inside each `deepdive_<t>.json` (which `make_report`/`finalize_run` read), and that is what every downstream number came from. The sidecar `valuation_*.json` files in the run dir should be treated as junk.
5. **`theme` field null in verdicts**, `deepdive_verdicts.json` rows carry `theme: null` (finalize_run did not stamp the slug). Cosmetic; track_forward still recorded all 19.

---

## 7. recall@gold

**n/a.** `semiconductors` has no hand-built gold true-member list in `track_forward.THEME_GOLD` (only deathcare, water-utilities, railcar-leasing, regional-gaming are defined). Ran `python tools/track_forward.py --recall-gold <candidates> --theme semiconductors` → *"no gold list for theme 'semiconductors', not measurable."* No SIC recall-floor gold check applies to this theme.

---

## 8. T2 diagnostic signals (context only, NOT used in any rating)

The firewalled side-channel was emitted for all 19 (present under `deepdive.signals`, never read by `valuation.py` or `buy_eligible`, verified). P16 price↔fundamentals divergence labels across the 19:
- `aligned` 10, `melting_ice_cube_priced` 6, `unclear` 2, `unpriced_improvement` 1.

The 6 `melting_ice_cube_priced` names (incl. **AOSL**, price +96 to 140% over 12m while fundamentals decline) are the classic value-trap shape, fundamentals down, tape up, no informational edge. This is **diagnostic only**; it did not and cannot move any rating, and with 0 BUYs there is no firewall concern. Signals are snapshotted for future per-signal Brier calibration.

---

## 9. Market-intel / Trends (T2 analyst context)

TrendsMCP was **rate-exhausted** (5/5 daily, 100/100 monthly) at run time, so no live alt-data was pulled. This is an optional enrichment layer and **never feeds buy_eligible**, so the absence has zero effect on the mechanical result. Qualitatively, semiconductors in mid-2026 is a peak-attention, AI-driven theme, precisely the branded-ETF "casino" the skill's world-view flags as where alpha has already been captured. The uniformly negative MoS across all 19 small-cap survivors is consistent with that: even the neglected tail of a hot sector is priced for growth, leaving no mechanical margin of safety.

---

## 10. Skeptical-PM verdict: USABLE

**Yes, usable as a landmine-scanner, exactly as designed.**

- The pipeline ran end-to-end synchronously: 200 raw → 19 full deep-dives → 0 BUYs, with **0 crash/ERROR files** and **0 missing reports**.
- The two gates earned their keep: Gate 1 SIC + Gate 2 LLM removed 6 clear misrecalls (solar, hydrogen, antennas, drone-comms, life-sci) that would otherwise have burned analyst time.
- The **cyclical/V-shape veto path (this run's focus) is demonstrably live**, AOSL trips both `fundamental_decline_flag` and `peak_contamination_flag`, and the A1 degenerate-base guard correctly suppresses false vetoes on negative-`contamination_ratio` names.
- The honest 0-BUY output is the *correct* answer for a hot theme: a disciplined PM would not expect a free lunch in mid-2026 semis, and the tool refuses to manufacture one. The value delivered is the elimination, 6 misrecalls + 8 untrustworthy-data names flagged + every name's overvaluation made explicit, not a buy ticket.
- One genuine caution for the human: the 42% cross_source_mismatch rate means small-cap debt/revenue XBRL here is noisy; trust no individual number on those 8 names without a manual filing read.

**Bottom line:** a skeptical PM gets a clean, auditable "nothing to buy here, and here is exactly why", which is a usable result.
