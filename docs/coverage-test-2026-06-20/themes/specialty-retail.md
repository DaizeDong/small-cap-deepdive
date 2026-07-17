# Coverage Test, Specialty Retail (ConsDisc)

- **Run batch:** `2026-06-21_cov-specialty-retail`
- **Skill version:** v0.3.0, commit `f12fef5`
- **Theme:** slug=`specialty-retail`, sector=ConsDisc, keywords=`specialty retail,retail stores`
- **Code-path focus:** cyclical / lease-heavy retailers
- **Result headline:** **0 BUY** (clean, honest). 13 WATCH, 9 AVOID. 0-BUY is a *true negative*, not a recall failure, see adversarial section.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discover (universe CSV) | 111 | FTS recall + market-cap filter; 1 unresolved (RVYL "Company not found") |
| After cheap_pass (mechanical health) | 88 survivors | 23 rejected; no going-concern/death-spiral kills among survivors |
| After SIC gate | 88 candidates | keep=61, review=27 (review passed to LLM gate) |
| Band split | deep=65, watch=23 | watch band (>market_cap_max) surfaced separately, not deep-dived |
| **LLM theme-fit gate (deep band)** | **22 survivors** | 43 deep-band names dropped as misrecall (store-operator test) |
| Deep-dived (data + valuation) | **22 / 22** | EVERY theme-fit survivor; 0 ERROR files, all attempt-1 |
| **Mechanical BUY** | **0** | no name clears `buy_eligible==true AND MoS>=30 AND basis∈{fcf_cap,nav}` |

**Theme-fit gate reasoning.** The theme is *operating retail stores selling specialty merchandise*.
I kept only store-operating specialty retailers (pure_play + partial). Dropped as misrecall:
- **BDCs / closed-end funds (financial)**, NMFC, SLRC, KBDC, GSBD, MSDL, BCIC, PFLT, MFIC, OCSL ("specialty *finance*", not specialty retail).
- **REITs**, OLP, WSR, GNL, GTY (net-lease landlords of retail real estate, not retailers).
- **Brands / manufacturers / wholesalers** (sell through third-party retail, do not operate a store base as the model), FTLF, VRA, CLAR, FOSL, WEYS, OXM, OLPX, ODC, CRI, LZB, SPB, GOOS, MOV, CAL, WWW, JVA.
- **Other off-theme**, RVYL (payments/consulting), CDLX (ad-tech), WFCF (food verification SaaS), TRAK (SaaS), AMRN (pharma), GTBIF/SNDL/OGI (cannabis cultivation/MSO), HITI (Canadian cannabis retail, foreign), LYTS (lighting mfr), VYX (commerce tech), BYRN (self-defense tech), RDGT (shell).

The 22 retained: CATO, TLF, TLYS, BBW, BBBY, MNRO, CTRN, NGVC, DBI, HVT, DXLG, CWH, GRWG, ARKO, SVV, EYE, UPBD, BSET, WINA, JILL, REAL, LVLU.

---

## 2. Ranked shortlist (full RANKING in `reports/smallcap/2026-06-21_cov-specialty-retail/RANKING.md`)

WATCH tier (non-sunk), ranked alphabetically by the tool (all conf 50%, all 0-BUY):
ARKO, BBW, BSET, CTRN, EYE, HVT, JILL, MNRO, NGVC, SVV, TLF, UPBD, WINA, 13 names.

AVOID / sunk tier (9): BBBY, CWH, REAL, DXLG, GRWG, DBI, LVLU, CATO, TLYS.

### BUY-rule outcome for every survivor

| Ticker | MktCap $M | MoS basis | MoS % | buy_eligible | buy_ineligible_reasons |
|---|---|---|---|---|---|
| CATO | 66 | fcf_cap | -49.5 | True |, (overvalued vs intrinsic) |
| TLF | 19 | nav | **+93.6** | False | debt_truncation_suspected |
| TLYS | 135 | nav | -53.9 | True |, |
| BBW | 406 | fcf_cap | -25.0 | True |, |
| BBBY | 442 | nav | -72.7 | True |, |
| MNRO | 467 | fcf_cap | **+92.3** | False | fundamental_decline_flag, cross_source_mismatch |
| CTRN | 505 | nav | -80.4 | False | cross_source_mismatch |
| NGVC | 694 | nav | -74.7 | False | debt_truncation_suspected, cross_source_mismatch |
| DBI | 321 | fcf_cap | **+174.2** | False | extreme_mos_review_required, fcf_sustainability_uncertain, peak_contamination_flag, cross_source_mismatch |
| HVT | 392 | nav | -37.4 | False | debt_truncation_suspected, wrong_entity_suspected |
| DXLG | 39 | nav | **+109.7** | False | extreme_mos_review_required, debt_truncation_suspected, peak_contamination_flag, cross_source_mismatch |
| CWH | 493 | fcf_cap | -87.2 | False | fcf_sustainability_uncertain, cross_source_mismatch |
| GRWG | 96 | nav | -26.2 | True |, |
| ARKO | 840 | fcf_cap | -103.5 | False | extreme_mos_review_required, cross_source_mismatch |
| SVV | 1563 | fcf_cap | -115.3 | False | extreme_mos_review_required |
| EYE | 1344 | fcf_cap | -70.3 | False | cross_source_mismatch |
| UPBD | 1068 | nav | -83.0 | False | cross_source_mismatch |
| BSET | 135 | nav | -11.1 | False | debt_truncation_suspected |
| WINA | 1432 | nav | -100.0 | True |, |
| JILL | 222 | fcf_cap | **+84.0** | False | cross_source_mismatch |
| REAL | 1500 | nav | -100.0 | False | low_revenue_loss_ratio_extreme, debt_truncation_suspected, cross_source_mismatch |
| LVLU | 22 | nav | -100.0 | False | peak_contamination_flag, cross_source_mismatch |

**The decisive structural fact:** the two conditions for BUY are *disjoint* in this theme.
- Every name with a positive MoS ≥ 30% (TLF, MNRO, DBI, DXLG, JILL) is `buy_eligible == False`.
- Every `buy_eligible == True` name (CATO, TLYS, BBW, BBBY, GRWG, WINA) has a *negative* MoS (priced above intrinsic / NAV).

There is no intersection → **0 BUY**, mechanically.

---

## 3. Honest 0-BUY adversarial verdict

There were zero mechanical BUYs, so the adversarial question is at the theme level:
**were any of the high-MoS names real opportunities wrongly suppressed by the guards, or are they artifacts?**

The five names with MoS ≥ 30% are all artifacts of one root cause, **ASC 842 operating-lease liabilities**, which is precisely the cyclical/lease-heavy code-path this theme was built to stress.

- **The mechanism.** SEC-XBRL `DebtCurrent`/`LongTermDebt` tags exclude capitalized operating-lease liabilities; yfinance's `totalDebt` includes them. For a store-operating specialty retailer the lease liability dwarfs funded debt, so the two sources disagree by far more than 2.5×, tripping `cross_source_mismatch`; where yfinance is unavailable, the same gap surfaces as `debt_truncation_suspected` (reported_debt ≈ 0 but liabilities − equity is large).
  - **MNRO:** SEC debt $60M vs yf $486M (8.1×). ~$425M is leases. The FCF-cap intrinsic was built on a net-debt that omits ~$425M of obligations → MoS overstated. Additionally `fundamental_decline_flag` fired (declining comps in a structurally shrinking tire/auto-repair box), the canonical lease-heavy value trap.
  - **JILL:** SEC $72.9M vs yf $218.5M (3.0×), leases. Lease-adjusted EV is far higher; the 84% MoS evaporates.
  - **DBI (DSW):** SEC $6.8M vs yf $1,226.5M (181.7×), almost the entire balance-sheet liability is leases. Also `peak_contamination` (latest NI −$8.4M, below the normalization average) and `extreme_mos_review_required` (174% > 100% is itself a red flag). Triple-blocked, correctly.
  - **DXLG:** implied lease debt $263.6M vs reported $16.8M; `peak_contamination` (NI −$35.9M), `extreme_mos`. Tiny $39M microcap. Correctly blocked.
  - **TLF (Tandy Leather):** NAV basis, MoS 93.6% from tangible book ($46M) vs $19M cap. Blocked by `debt_truncation_suspected`, reported debt $0 but implied liabilities $35M (leases). The NAV uses book equity that does not net the lease ROU/liability symmetrically for a going-concern store operator, and it is a sub-$20M illiquid microcap. Not a clean net-net.

**Verdict: the guards fired as designed, true positives, not false blocks.** Every high-MoS figure is an artifact of a lease-understated net-debt / EV. The firewall held: `buy_eligible` is composed only from the documented v0.3.0 guards; the diagnostic `signals` side-channel was not emitted into the run directory and never touched valuation. **0-BUY is the honest answer.**

The `buy_eligible==True` names are not opportunities either, they are simply WATCH-grade businesses trading *above* their filing-derived intrinsic/NAV (negative MoS). Nothing was lost by passing on them.

---

## 4. Which code-paths fired (coverage value of this theme)

This theme exercised an unusually broad slice of the v0.3.0 guard surface, strong coverage signal:

| buy_ineligible reason | # of 22 | role |
|---|---|---|
| cross_source_mismatch | 12 | DATA-INTEGRITY gate (SEC-vs-yf >2.5×), dominated by lease liabilities |
| debt_truncation_suspected | 6 | reported-debt ≈ 0 but liab−equity large (leases) |
| extreme_mos_review_required | 4 | MoS > 100% (implausible-discount tripwire) |
| peak_contamination_flag | 3 | V-shape / latest-below-normalized value-trap veto |
| fcf_sustainability_uncertain | 2 | OCF-proxy / capex-light caution |
| fundamental_decline_flag | 1 | downgrade veto (MNRO declining comps) |
| wrong_entity_suspected | 1 | HVT |
| low_revenue_loss_ratio_extreme | 1 | REAL (>20× |NI|/rev tail) |

Other paths exercised: financial-SIC routing and BDC/REIT exclusion (at the theme-fit gate, 18 financial/REIT/non-retail misrecalls dropped before deep-dive); NAV vs fcf_cap routing (13 nav / 9 fcf_cap); material_weakness surfacing (CWH, GRWG, SVV); concentration_unquantified (4, advisory only). The gate2-misrecall resolution path was exercised (43 deep-band names resolved as off-theme via `candidates_gate2_survivors.json`, finalize reported 0 missing).

---

## 5. Data-quality issues

- **cross_source_mismatch on 12 of 22 (>50%).** This is structurally expected for store-operating retailers (lease liabilities). It is the *correct* behavior of the integrity gate, but it also means the FCF-cap / NAV MoS numbers for lease-heavy names are not directly trustworthy without a lease-adjusted EV. A future enhancement worth noting: net the operating-lease liability into net-debt symmetrically (it is partly offset by the ROU asset) rather than gating outright, which would let a genuinely cheap lease-heavy retailer surface on a lease-adjusted basis.
- **debt_stale (>18 months) on TLF, DXLG**, fiscal-year XBRL lag for small retailers.
- **fcf_cap_blocked_by_c1_data_quality_guard on 10**, capex/dep-amort gaps force the abstain/NAV path.
- **Unit anomaly in `derived` net-income for JILL ($27,900M shown) and REAL ($41,799M)**, these are clearly scaling glitches in the derived-series display (JILL real NI ≈ $0 to 30M; REAL is loss-making). Did not affect the valuation block (valuation MoS used the proper market_cap and band) but it does pollute the RANKING net-income column (REAL shows "$41799M NI" while being a known loss-maker). Flagging as a display/units bug in the derived layer.
- **1 unresolved ticker at discovery (RVYL).**
- No going-concern / death-spiral kill-flags among the 22 (cheap_pass clean); 3 material_weakness.

---

## 6. recall@gold

**n/a.** `specialty-retail` is not in `THEME_GOLD` (the gold cohorts are water-utilities, railcar-leasing, regional-gaming, deathcare/funeral/cemetery). `track_forward.py --recall-gold` returned *"no gold list for theme 'specialty-retail', not measurable."* No recall floor to record for this theme.

---

## 7. T2 market-intel / Trends context

**Not available this run.** TrendsMCP daily + monthly request quota was exhausted (5/5 daily, 100/100 monthly) at run time, so no T2 search-volume / news-sentiment overlay was pulled. This is labeled-context only and by design never drives `buy_eligible`, so its absence does not affect any verdict. General sector backdrop (analyst priors, not tool-sourced): US specialty-retail small-caps remain a cyclical, lease-heavy, comp-driven cohort under secular online-share pressure, consistent with the funnel's lean toward declining-comp value traps (MNRO) and loss-making turnarounds (BBBY, DXLG, LVLU, REAL).

---

## 8. Skeptical-PM usable verdict

**Usable. Yes.** As a landmine-scanner the run did its job cleanly:
- It enumerated the SEC universe, correctly separated 22 true store-operating specialty retailers from 43 financial/REIT/brand/cannabis misrecalls, and deep-dived every one with zero crashes.
- It produced a defensible **0-BUY** by catching, via independent guards, the single trap that defines this theme: lease-understated net-debt inflating MoS on cyclical retailers.
- No artifact slipped through to a BUY; no clean compounder was wrongly buried (the buy_eligible names are simply expensive, not hidden gems).

A PM should treat this as "no actionable mispricing in small-cap specialty retail right now, and here are the 13 names to revisit if they sell off." The one caveat a PM should hold: because the lease-driven `cross_source_mismatch` gate currently *blocks* rather than *lease-adjusts*, a genuinely cheap lease-heavy retailer would also be gated, so the 0-BUY is "0 BUY at the current guard resolution," not a claim that lease-heavy retail can never be cheap. That is a known, honest limitation, not a silent miss.
