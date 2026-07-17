# Coverage Test, Enterprise SaaS (InfoTech)

- **Slug:** `enterprise-saas` | **Run dir:** `reports/smallcap/2026-06-21_cov-enterprise-saas/`
- **Skill:** v0.3.0 (commit `f12fef5`, dirty) | **Date:** 2026-06-21
- **Keywords (FTS):** `enterprise software, SaaS, cloud platform`
- **Code-path focus:** V-shape veto on decelerators (`peak_contamination_flag` / `fundamental_decline_flag`)
- **Headline:** **0 BUY** (clean). All 18 deep-band theme-survivors rate WATCH. Every survivor has a
  **negative or null margin of safety**, the canonical hot-theme outcome. The V-shape veto did not
  need to fire to produce 0 BUY (MoS alone blocked everything), but the decelerator code-paths were
  exercised and behaved correctly: `fundamental_decline_flag` fired on HCKT, `peak_contamination_flag`
  correctly did **not** over-fire on the three sub-0.8 contamination-ratio names.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw recall (union of 3 keywords) | 677 | enterprise software 334, SaaS 223, cloud platform 310; deduped 677 |
| Small-cap candidates (< $2.0B, post liquidity/SPAC scrub) | 84 deep + 21 watch | discover output (mktcap via yfinance) |
| cheap_pass input | 76 | small-cap survivors fed to mechanical kill-flags |
| cheap_pass survivors | 46 | hard kill-flags (going-concern / death-spiral / material-weakness) applied |
| SIC gate (keep + review) | 46 | keep 18, review 28 (0 hard-dropped) |
| **Deep band (band="deep", < $2B)** | **29** | the over-recall pool sent to Gate 2 |
| **Gate 2 theme-fit survivors (deep-dived)** | **18** | 12 pure_play + 6 partial |
| Gate 2 misrecall (resolved, not deep-dived) | 11 | banks/BDCs/utilities/used-car/towing/space-imagery |
| Reports written | 18 | 0 missing (finalize_run asserts) |
| Valuations run | 18 | all exit 0; `--json` + `--ticker` both supplied |
| **Mechanical BUY** | **0** | every survivor MoS < 30 (negative or null) |
| **Clean BUY (post-adversarial)** | **0** | nothing to adversarially confirm |

This is a precision-gate stress test on a hot theme. "enterprise software," "SaaS," and "cloud
platform" are extremely generic 10-K phrases, banks, BDCs, used-car retailers, towing-equipment
makers, water utilities, and space-imagery firms all surfaced in the raw 677 because they describe
their own IT spend or carry one of the keywords incidentally. The deep band of 29 included 11 clear
misrecalls that Gate 2 resolved without a deep-dive.

## 2. Gate 2 theme-fit (LLM judgment from 10-K blurbs)

**Survivors deep-dived (18):**

| Ticker | Name | SIC | Mkt cap | Fit | Rationale |
|---|---|---|---|---|---|
| LPSN | LivePerson | 7372 | $24M | pure_play | Digital customer-conversation SaaS. |
| NTWK | NetSol Technologies | 7372 | $50M | partial | Enterprise software for asset finance/leasing OEMs. |
| SKIL | Skillsoft | 7372 | $67M | pure_play | Cloud corporate-learning SaaS platform. |
| DOMO | Domo | 7372 | $109M | pure_play | Cloud BI / AI data-products platform. |
| SMRT | SmartRent | 7373 | $218M | pure_play | Enterprise real-estate SaaS platform. |
| UIS | Unisys | 7373 | $258M | partial | IT services + cloud/infrastructure (services-heavy). |
| HCKT | The Hackett Group | 8742 | $262M | partial | Consulting + benchmarking, emerging AI SaaS (AI XPLR). |
| RMNI | Rimini Street | 7389 | $385M | partial | Third-party enterprise-software support/managed services (not own SaaS). |
| TBRG | TruBridge | 7371 | $391M | pure_play | Healthcare-IT SaaS for community hospitals. |
| RPD | Rapid7 | 7372 | $450M | pure_play | Cybersecurity-operations SaaS platform. |
| AIOT | Powerfleet | 3669 | $534M | partial | AIoT SaaS (hardware + SaaS hybrid). |
| IIIV | i3 Verticals | 7389 | $554M | pure_play | Mission-critical public-sector enterprise SaaS. |
| PD | PagerDuty | 7372 | $654M | pure_play | Digital-operations / incident-response SaaS. |
| SIFY | Sify Technologies | 7370 | $1,100M | partial | Indian ICT / data-center / cloud-infra services. |
| CXM | Sprinklr | 7372 | $1,181M | pure_play | Unified-CXM SaaS platform. |
| PRGS | Progress Software | 7372 | $1,249M | pure_play | Enterprise application/infrastructure software. |
| APPN | Appian | 7372 | $1,538M | pure_play | Low-code process-automation SaaS platform. |
| ASAN | Asana | 7372 | $1,595M | pure_play | Work-management SaaS. |

**Deep-band misrecalls (11, resolved in `gate2_results.json`, not deep-dived):**

| Ticker | Name | SIC | Why misrecall |
|---|---|---|---|
| CRMT | America's Car-Mart | 5500 | Used-car retailer + finance; "enterprise" incidental. |
| DAIO | Data I/O | 3825 | Programming-systems *hardware* maker. |
| BYRN | Byrna Technologies | 3690 | Less-lethal self-defense weapons. |
| RWAY | Runway Growth Finance | n/a | BDC / closed-end fund (lends to tech, isn't SaaS). |
| IMXI | Intermex | 7389 | Money-remittance services. |
| YORW | York Water | 4941 | Water utility (also a water-utilities gold name). |
| MLR | Miller Industries | 3713 | Towing/recovery-equipment manufacturer. |
| NMFC | New Mountain Finance | n/a | BDC. |
| BTQ | BTQ Technologies | 7370 | Post-quantum / quantum tech, not enterprise SaaS. |
| TRNS | Transcat | 3825 | Calibration *services* co; CMMS software incidental. |
| BKSY | BlackSky Technology | 3663 | Space-based geospatial imagery/analytics. |

Watch-band (band="watch", $2.0 to 5.0B; theme-fit only, no deep-dive): 17 names incl. AVPT, RAMP,
WK, RNG, ZETA, NICE, BB, QLYS, EXTR (the canonical small-mid SaaS cohort sits just above the
$2.0B small-cap ceiling, note how many true pure-plays are size-excluded).

## 3. recall@gold

**n/a**, `enterprise-saas` is not in `THEME_GOLD` (`tools/track_forward.py`); `theme_gold("enterprise-saas")`
returns `[]`. The four gold-list themes are water-utilities / railcar-leasing / regional-gaming /
deathcare. `track_forward.py --recall-gold` was therefore not run for this theme.

## 4. Deep-dive survivors, full BUY-rule reasoning

BUY rule: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric `MoS ≥ 30%` **AND** `buy_eligible == true`
**AND** zero kill-flags. **All 18 FAIL.** None has a positive MoS ≥ 30; not one survivor clears the
single most important gate. The MoS column is the whole story for this theme.

| Ticker | basis | MoS% | EV/S | EV/EBITDA | FCF yield | buy_eligible | BUY blocked by |
|---|---|---|---|---|---|---|---|
| LPSN | nav | −100.0 | 1.78 |, | −173.8% | True | MoS≪30 (NAV equity wiped; deeply FCF-negative) |
| NTWK | fcf_cap | −19.4 | 0.54 | 7.13 | −1.9% | True | MoS<30 (closest of all, still negative) |
| SKIL | nav | −100.0 | 1.03 |, | 34.6% | False | MoS≪30 + `financial_sic_forced_unsuitable`, `insurance_concepts_present` |
| DOMO | nav | −100.0 | 0.21 |, | −1.8% | False | MoS≪30 + `debt_truncation_suspected` |
| SMRT | fcf_cap | null | 1.24 |, | −11.5% | False | MoS null + `cross_source_mismatch` |
| UIS | nav | −100.0 | 0.05 | 0.91 | −65.9% | False | MoS≪30 + `cross_source_mismatch` |
| HCKT | fcf_cap | −24.6 | 4.42 | 23.48 | 12.4% | False | MoS<30 + **`fundamental_decline_flag`** + `cross_source_mismatch` |
| RMNI | fcf_cap | −21.6 | 0.73 | 4.85 | 15.6% | False | MoS<30 + `fcf_sustainability_uncertain` |
| TBRG | fcf_cap | −71.8 | 1.50 |, | 9.1% | True | MoS≪30; **also killflag_count=1 (material_weakness)** |
| RPD | nav | −100.0 | 0.14 | 2.17 | 32.5% | False | MoS≪30 + `debt_truncation_suspected`, `cross_source_mismatch` |
| AIOT | fcf_cap | null | 1.65 | 9.19 | 1.7% | True | MoS null; **also killflag_count=1 (material_weakness)** |
| IIIV | fcf_cap | −63.3 | 2.94 | 21.36 | 0.7% | True | MoS≪30 |
| PD | fcf_cap | −56.0 | 1.76 | 45.66 | 17.1% | True | MoS≪30 (45x EV/EBITDA) |
| SIFY | fcf_cap | null |, |, |, | False | MoS null + `cross_source_mismatch` (EV/multiples unavailable) |
| CXM | nav | −70.3 | 1.19 | 17.15 | 13.4% | False | MoS≪30 + `debt_truncation_suspected` |
| PRGS | fcf_cap | −69.7 | 2.53 | 15.53 | 18.4% | True | MoS≪30 (best fundamentals of the cohort, still −70% MoS) |
| APPN | fcf_cap | null | 2.24 | 157.67 | 3.9% | True | MoS null (normalized FCF nonpositive; 158x EV/EBITDA) |
| ASAN | nav | −93.1 | 1.82 |, | 5.4% | False | MoS≪30 + `debt_truncation_suspected`, `cross_source_mismatch` |

**Why every MoS is negative:** the reverse-DCF / FCF-cap intrinsic band uses normalized (trailing
5yr) equity FCF against current market cap. Small-cap enterprise-SaaS names trade at premium
revenue multiples (EV/Sales 1 to 4x typical, EV/EBITDA 15 to 158x where EBITDA is even positive) precisely
because the market prices forward growth, not trailing FCF. The deterministic model, which refuses
to extrapolate optimistic growth, therefore returns deeply negative margins of safety across the
board. This is exactly World-View commitment #2 (*hot themes are the casino, not the edge*) and #1
(*neglected ≠ undervalued*) rendered mechanically: the SaaS cohort is neither neglected nor cheap.

**Six survivors are `buy_eligible=True` but still not BUY**, the firewall demonstration:
- AIOT, APPN, `buy_eligible=True` but **MoS is null** (normalized FCF nonpositive → no intrinsic
  band). The null-MoS gate blocks the BUY: `buy_eligible` alone is never sufficient (matches the
  RVSN pattern from railcar). AIOT additionally carries a material_weakness kill-flag.
- IIIV, PD, PRGS, TBRG, `buy_eligible=True` with **numeric but deeply negative MoS** (−56% to
  −72%). The MoS≥30 clause blocks them. TBRG additionally carries a material_weakness kill-flag,
  which would block BUY under the "zero kill-flags" clause even if MoS had been positive.

No adversarial verification was required: there is no mechanical BUY to interrogate. The honest
result is **0 BUY**, and it is the *correct* result for a premium-priced hot theme, not a coverage
failure (18 true pure-plays/partials were found, deep-dived, and valued).

## 5. Code-paths exercised (focus: V-shape veto on decelerators)

The decelerator vetoes are the focus path. Both sibling flags were exercised:

- **`fundamental_decline_flag` FIRED on HCKT**, `rev_slope_sign = −1` (whole-window revenue
  declining), latest NI positive but the trailing trend is down. Correctly added
  `fundamental_decline_flag` to `buy_ineligible_reasons` → `buy_eligible=False`. This is the
  straightforward decelerator catch (down-sloping revenue over the full window).

- **`peak_contamination_flag` (the V-shape value-trap veto) FIRED on NOBODY, and correctly so.**
  This is the instructive part. Three survivors had `contamination_ratio < 0.8` (the V-shape
  trigger band): IIIV (0.159), NTWK (0.093), SMRT (0.548). On a naive reading these look like
  trough→peak→rollover candidates. But `peak_contamination_flag` additionally requires
  `latest_net_income < 0` **AND** `latest_below_avg`. IIIV and NTWK both report **positive** latest
  net income, so the V-shape trap criteria are not met and the flag stayed False, exactly the
  designed behavior (a low contamination ratio with positive, at-or-above-average latest earnings is
  *not* a rollover). The veto is armed and discriminating, not trigger-happy. HCKT (cratio 0.874)
  was instead caught by the `fundamental_decline_flag` sibling. **Net: the two decelerator paths are
  complementary, and neither over-fired in a 29-name InfoTech pool.**

Other paths that fired:
- **`cross_source_mismatch`** (P7 second-source sanity band) gated 6 names (SMRT, UIS, HCKT, RPD,
  SIFY, ASAN), a corrupted single-source number cannot back a tradeable MoS.
- **`debt_truncation_suspected`** gated 4 NAV-basis names (DOMO, RPD, CXM, ASAN).
- **`financial_sic_forced_unsuitable` + `insurance_concepts_present`** gated SKIL (its 10-K narrates
  the Churchill Capital SPAC heritage, "insurance"/"financial" concept language tripped the guard;
  arguably a false-positive on the financial-SIC heuristic for a learning-SaaS company, noted below).
- **NAV vs fcf_cap routing:** 7 names routed to NAV (`fcf_cap_model_unsuitable` on debt/assets or
  financial-SIC), 11 to fcf_cap. NAV produced −93% to −100% MoS everywhere (these are
  asset-light SaaS firms with little tangible equity, NAV is structurally unflattering, as expected).

## 6. Data-quality issues

- **SKIL financial-SIC false-positive (candidate model artifact, correctly harmless):**
  `financial_sic_forced_unsuitable` + `insurance_concepts_present` fired on Skillsoft, a corporate-
  learning SaaS company, almost certainly because its 10-K business section recounts its SPAC
  (Churchill Capital / "Software Luxembourg") merger history with financial/insurance concept words.
  It did not produce a spurious BUY (MoS was −100% anyway), so the firewall held, but it is a noted
  precision wart in the SIC/insurance guard.
- **SIFY data sparsity:** EV, EV/Sales, EV/EBITDA, FCF yield all null (foreign private issuer, 20-F;
  the XBRL financial series did not populate). MoS null, `cross_source_mismatch` set. Correctly not
  a BUY; flagged as a coverage gap for non-domestic filers.
- **Material weakness on AIOT and TBRG:** both carry `killflag_count=1 (material_weakness)` from the
  cheap_pass/deepdive layer. Neither was eliminated pre-deep-dive (material_weakness is a BUY-blocker,
  not an AVOID-forcing going-concern), but both are correctly non-BUY.
- **Null/negative normalized FCF is pervasive:** AIOT, APPN, SMRT, SIFY returned null MoS because
  normalized FCF was nonpositive, endemic to growth-stage SaaS and the reason the fcf_cap model
  abstains rather than fabricates a band.
- **yfinance delisting noise at discovery:** ~25 tickers (CFLT, OLO, INFA, ZUO, etc.) returned "no
  price data / delisted" during the mktcap pass, recall was not harmed (these are genuinely
  delisted/renamed or large-cap), but worth noting the FTS recall surfaces stale tickers.
- **Watch-band exclusion of true pure-plays:** many of the cleanest enterprise-SaaS pure-plays
  (WK, RNG, ZETA, NICE, QLYS, AVPT, RAMP) sit at $2.2 to 5.0B and are size-excluded from deep-dive by
  the $2.0B small-cap ceiling. Not a defect, but the actionable small-cap SaaS universe is thin and
  skewed toward the troubled/declining end of the cohort.

## 7. Market-intel / T2 analyst context

- **TrendsMCP: unavailable this run**, daily and monthly request quota exhausted (5/5 daily, 100/100
  monthly). No search/news-momentum series could be pulled. Per design this is **immaterial to any
  BUY**: the signals/trends side-channel is firewalled (`diagnostic_only: true`,
  `never_affects_buy: true` in every deepdive `signals.signals_meta`) and never enters `buy_eligible`.
- **Qualitative T2 read (no tool, analyst note):** enterprise SaaS in mid-2026 is a mature,
  AI-repositioning narrative, nearly every survivor's 10-K blurb now leads with "AI-powered" /
  "agentic" framing (ASAN "Agentic Enterprise," PRGS "responsible AI," CALX "agentic AI," HCKT
  "AI XPLR"). This is the late-cycle theme tell: the keyword has fully diffused, consistent with the
  0-BUY / all-WATCH valuation result. The edge here, if any, is single-name turnaround
  (e.g., a decliner whose AI re-platforming actually re-accelerates), which is a narrative bet the
  skill explicitly disclaims (World-View #3).

## 8. Skeptical-PM usable verdict

**Usable: YES (as a landmine-scanner and watchlist seed, not a buy list).** A disciplined PM gets
real value from this run: it enumerated 677 filings, mechanically resolved 11 deep-band misrecalls
(BDCs, utilities, towing makers, space imagery) that a human skimming the keyword list would have
wasted time on, deep-dived and valued 18 genuine pure-plays/partials, and returned a defensible
**0 BUY** with the reason stated per-name (premium pricing → negative MoS). The decelerator
code-path focus is validated: `fundamental_decline_flag` fired correctly (HCKT), and the V-shape
`peak_contamination_flag` correctly *withheld* on three sub-threshold contamination ratios where
latest earnings were positive, i.e., it does not over-fire. The honest 0-BUY on a hot theme is the
intended product. The main caveats a PM should carry forward: (a) the cleanest SaaS pure-plays are
size-excluded above $2.0B, so the small-cap subset is adversely selected toward decliners; (b) the
SKIL financial-SIC false-positive is a (harmless here) precision wart; (c) NTWK at −19.4% MoS is the
single closest-to-eligible name and the only one a PM might re-underwrite manually if they disagree
with the trailing-FCF normalization.
