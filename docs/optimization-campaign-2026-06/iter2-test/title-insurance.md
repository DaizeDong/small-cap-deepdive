# iter2-test: title-insurance (NEW THEME full synchronous run)

- Batch: 2026-06-20_title-insurance
- Theme: "title insurance, specialty insurance underwriting" | slug: title-insurance
- Skill commit under test: post-2599d66 (peak_contamination_flag V-shape veto, low_revenue_loss_ratio label, hygiene)
- Focus: tricky financial sector. Stress: financial-SIC exclusion + SIC-absent fallback must route to nav/abstain and NEVER produce an fcf_cap BUY (the HCI failure mode).
- Date run: 2026-06-20 | independent report, full pipeline executed synchronously.

---

## 1. Funnel (raw -> survivors -> deep-dived)

| Stage | Count | Notes |
|---|---|---|
| SEC FTS recall (marketcap-filtered universe) | 326 | over-recall by design; banks/REITs/homebuilders/retail all mention title insurance |
| Small-cap deep band (mktcap < 2B) | 185 | + 50 watch, 63 large, 28 unknown |
| cheap_pass survivors (no going_concern/death_spiral/material_weakness) | 138 | 47 rejected by mechanical kill-flags |
| After SIC coarse gate (Gate 1) | 138 | keep=55, review=83; financial SICs NOT hard-excluded at Gate 1, excluded later in valuation by design |
| Deep-band candidates (band=deep) | 98 | the set finalize_run requires resolved |
| Gate 2 (LLM theme-fit) survivors -> deep-dived | 5 | 93 classified misrecall (gate2_results.json) |
| Genuine theme members | ITIC TIPT BWIN SLQT BOC | 1 pure_play + 4 partial |

Gate-2 precision: 5 / 98 deep-band = ~5% true theme members; 95% keyword over-recall (consistent with the documented AI-agent 6.8% benchmark). Over-recall dominated by banks (SIC 602x) and homebuilders (SIC 1531) mentioning title insurance as a closing-cost line item, and REITs (6798) for specialty. All 93 are recorded in gate2_results.json with per-row theme_fit=misrecall + reason, so finalize_run reports 0 missing (resolved-by-gating, not forgotten). Every one of the 5 genuine members was deep-dived. No silent skips; no ERROR.json (no crashes).

## 2. Ranked shortlist

| Rank | Ticker | Name | Rating | Conf | mos_basis | MoS | buy_eligible | kill | Why |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ITIC | Investors Title Co | WATCH | 45% | nav | NAV -57.0% | false | 0 | Pure-play title underwriter; debt-free quality compounder but NO discount; financial-SIC blocks BUY |
| 2 | BOC | Boston Omaha | WATCH | 40% | fcf_cap | null | true | 0 | SIC-65 escapes financial-SIC guard, but null MoS (neg FCF) blocks BUY; cluster insider buys |
| 3 (sink) | BWIN | Baldwin Insurance Grp | AVOID | 42% | nav | NAV -100% | false | 0 | Blue Orca short + losses + insider selling; triple mechanical block |
| 4 (sink) | SLQT | SelectQuote | AVOID | 40% | nav | NAV +62.6% | false | 0 | DOJ FCA suit + class actions + dilution; financial-SIC saves a value-trap BUY |
| 5 (sink) | TIPT | Tiptree | AVOID | 35% | nav | NAV -75.3% | false | 0 | Sold its insurer (Fortegra); discontinued-ops reclass distorts all signals; exited theme |

## 3. BUY decision: honest 0-BUY

ZERO BUYs. This is the correct, mechanically-enforced outcome.

iter2 BUY rule requires: mos_basis in {fcf_cap, nav} AND numeric MoS >= 30 AND buy_eligible == true AND zero kill-flags (and buy_eligible now also requires NOT peak_contamination_flag). No name cleared all four:

- ITIC: mos_basis=nav, NAV MoS -57.0% (fails >=30), buy_eligible=false (financial_sic_forced_unsuitable). Two independent fails. WATCH.
- BOC: mos_basis=fcf_cap, buy_eligible=true, BUT MoS null (negative normalized FCF -> intrinsic_band_unavailable). The numeric-MoS clause fails. WATCH.
- BWIN: buy_eligible=false (financial_sic + debt_truncation + peak_contamination); NAV MoS -100%. AVOID.
- SLQT: buy_eligible=false (financial_sic). NAV MoS = +62.6% >= 30, the ONLY name to clear the MoS bar, yet buy_eligible=false correctly downgrades it. THE KEY SAVE (see Section 4).
- TIPT: buy_eligible=false (4 reasons); data distorted by Fortegra discontinued-ops reclass. AVOID/abstain.

## 4. Stress-test verdict: did the financial-SIC machinery hold?

YES. The HCI failure mode (an fcf_cap BUY on a financial company) did not occur. Two layers of defense were exercised:

1. Financial-SIC exclusion (primary). All four insurance-SIC names routed to mos_basis=nav with financial_sic_forced_unsuitable firing and buy_eligible=false:
   - ITIC sic=6361 (title insurance) -> nav. The canonical test case: a profitable, clean title underwriter a naive FCF model would mis-value. Correctly excluded.
   - TIPT sic=6331, BWIN sic=6411, SLQT sic=6411 -> all nav, all blocked.
   - SLQT is the marquee save: NAV MoS +62.6% would have been a NAV-BUY candidate, but financial_sic_forced_unsuitable forces buy_eligible=false -> WATCH/AVOID, not BUY. Disconfirmation independently confirmed a value trap (DOJ False Claims Act suit, securities class actions, dilutive Bain raise). Guard and qualitative evidence agreed.

2. SIC-absent / SIC-65 fallback edge (BOC). Boston Omaha is SIC 6510 (real-estate operator); prefix 65 is NOT in the financial-SIC list (60/61/63/64/67), even though BOC owns a surety insurance subsidiary. It routed to mos_basis=fcf_cap with buy_eligible=true. It did NOT produce a false fcf_cap BUY only because normalized FCF is negative -> MoS null (intrinsic_band_unavailable). The financial-SIC gate did NOT catch BOC; the null-MoS second line of defense did. A hypothetical future BOC with positive FCF + an insurance sub would slip the SIC gate; flagged as a maintainer item. (The SIC-absent fallback at valuation.py:252-261, catching no-SIC investment companies via revenue-absent/OCF-present, did not trigger; no member had a missing SIC.)

Net: never an fcf_cap BUY on a financial; the one fcf_cap-routed name (BOC) was a non-financial holdco by SIC and was blocked by null MoS anyway. Stress passed.

## 5. Data-quality observations (which flags fired, and edges)

- financial_sic_fcf_unsuitable: fired on ITIC (6361), TIPT (6331), BWIN (6411), SLQT (6411). Working exactly as designed.
- peak_contamination_flag (V-shape veto): fired on BWIN with contamination_ratio = -2.4618 (NEGATIVE). Fires correctly in spirit (loss-making + latest below avg), but a negative contamination ratio is a degenerate input (negative FCF normalization base) and the magnitude is not interpretable. EDGE TO LOG: the contamination_ratio < 0.8 test passes trivially for any negative ratio; consider guarding against negative/degenerate bases so the flag semantics (latest base well below a POSITIVE 5yr avg) hold.
- fundamental_decline_flag: fired on TIPT (rev_slope -1, contamination 0.7328, latest_below_avg). Mechanically correct but semantically an artifact: the revenue collapse 341.5M -> 0.5M is the Fortegra discontinued-ops RECLASSIFICATION, not an organic melting-ice-cube. The flag did its job (downgrade), but read it as "the business was SOLD," not "the business is declining."
- low_revenue_loss_ratio (new iter2 label): fired on TIPT (abs(NI)/rev = 71.6x). Surfaced in data_quality only; did not gate buy_eligible. Behaved per spec.
- wrong_entity_suspected (P-B refinement under test): STILL fired on TIPT because abs(NI)/rev = 71.6 > the 50x genuine-unit-anomaly threshold. P-B was meant to stop this misfiring on real producers; here it trips on the RIGHT entity because the discontinued-ops reclass produced a genuine ratio anomaly. Borderline P-B case worth logging: not the early/pre-revenue producer pattern P-B targeted (now low_revenue_loss_ratio), but a reclassification artifact exceeding the unit-anomaly bar. Both labels co-fired on TIPT.
- debt_truncation_suspected: fired on TIPT and BWIN (XBRL debt tag captures a sliver vs implied liab-equity). For BWIN a real load-bearing gap (reported 16M vs implied 3.4B leverage); both correctly block buy_eligible.
- ITIC revenue tag: 40.9M understates true gross title premiums (title insurers report net premiums + escrow + investment income); EV/Sales 13.4x is a tagging artifact. Flagged in ITIC trust banner.

No crashes, no ERROR.json files. All valuations ran with --json AND --ticker.

## 6. Market-intel T2 analyst context (does NOT drive buy_eligible/BUY)

Source: TrendsMCP get_growth (Google Search interest), labeled T2. Title insurance is a derivative of US home-sale + refi transaction volume.

- "title insurance" search interest: +23.8% YoY (recovering off the 2025 housing-volume trough) but -54% over the trailing 3 months (seasonal + rate-driven pullback). Volume 9,296 recent vs 7,508 year-ago.
- "mortgage refinance" interest: +71% YoY but -43% QoQ.

T2 read: title-underwriter demand (ITIC) is cyclically off the bottom YoY, a modest tailwind if a rate-cut-driven refi/turnover recovery sustains, but the sharp QoQ rollback flags fragility, consistent with ITIC full valuation (no MoS) and the dead-money-at-a-full-multiple bear case. Informs the WATCH framing only; did not and may not move any buy_eligible/BUY decision.

## 7. Skeptical-PM usable verdict

Title insurance was a deliberate financial-sector trap, and the machine did not step in it. Of 326 recalled names, the two-stage gate found exactly 5 genuine insurance plays and the financial-SIC guard routed all four insurance-SIC carriers to NAV with buy_eligible=false, including SLQT, which screened at NAV +62.6% and would have been a value-trap BUY on a naive NAV screen but is in fact a DOJ False Claims Act defendant. Zero BUYs, correctly. The one name that escaped the SIC guard (BOC, classified real estate) was caught by the null-MoS backstop, not the SIC gate; note that as a latent hole: a profitable holdco with an insurance sub but a non-financial SIC could still route to fcf_cap.

Actionable for a PM: ITIC is the only quality name, a debt-free dividend-paying pure-play title underwriter, but fully valued (NAV MoS -57%); watch-list to buy near ~1.0x tangible book if a housing slump de-rates it (the NAV path would then mechanically permit a BUY). BOC is a watch-with-catalyst on the Dec-2025 insider cluster but needs a SOTP + Sky Harbour mark first. BWIN/SLQT/TIPT are passes: short report, federal litigation, and a sold-off insurer respectively. The report is honest about its own data edges (BWIN negative contamination ratio, TIPT reclass artifacts), which is what a landmine-scanner should be.

Bottom line for the iter2 commit: the post-2599d66 financial-SIC + peak_contamination machinery performed correctly on a financial-sector stress theme. One real product bug surfaced (peak_contamination_flag fires on degenerate negative contamination ratios) and one borderline P-B case (wrong_entity_suspected co-firing with low_revenue_loss_ratio on a discontinued-ops reclass); both logged for the maintainer; neither caused a wrong BUY. The SIC-65/holdco-with-insurance-sub gap is a latent (not realized) hole worth a coarse-gate override.

---

### Artifacts (all under reports/smallcap/2026-06-20_title-insurance/)
- candidates_title_insurance.json (138), gate2_results.json (98 rows), candidates_gate2_survivors.json (5)
- deepdive_{ITIC,TIPT,BWIN,SLQT,BOC}_2026-06-20.json + valuation_* (merged) + report_*.md
- deepdive_verdicts.json, RANKING.md, _run.json, run_theme.log
