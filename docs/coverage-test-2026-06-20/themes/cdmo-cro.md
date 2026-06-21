# Coverage Test - Theme: CDMO / CRO (HealthCare)

- slug: cdmo-cro
- sector: HealthCare
- keywords: contract drug manufacturing, CDMO, CRO
- run: reports/smallcap/2026-06-21_cov-cdmo-cro/
- skill version: v0.3.0 (commit f12fef5)
- code-path focus: customer-concentration kill
- date: 2026-06-21

> Research output, NOT investment advice. This skill is a landmine-scanner, not a buy list.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery union (FTS keywords + SIC reverse-recall floor, mktcap-resolved) | **485** | 327 deep (<$2B), 41 watch ($2-5B). No FTS top-1000 cap warning. |
| cheap_pass run | 295 | small-cap subset with resolvable inputs |
| cheap_pass survivors | **127** | going_concern / death_spiral eliminations applied |
| SIC gate (Gate 1) | 127 | 5 keep + 122 review; SIC kept all survivors |
| candidates emitted | 127 | 97 deep band + 30 watch band |
| **Gate-2 LLM theme-fit (deep band)** | 97 -> **3** | 1 pure_play + 2 partial; **94 misrecall** |
| Deep-dived (every deep-band survivor) | **3** | LFCR, NEO, MRVI - full deepdive + valuation |
| Mechanical BUY | **0** | honest 0-BUY |
| BUY surviving adversarial verification | **0** | |

**Gate-2 is the whole story of this theme.** The keywords CDMO, CRO, and contract-drug-manufacturing
appear in nearly every clinical-stage biopharma 10-K (they describe reliance on third-party
CDMOs/CROs), so FTS over-recalled the entire small-cap biotech/pharma sector plus a large block of
community banks (SIC 60xx that slipped Gate 1) and a reinsurer/REIT. 94 of 97 deep-band names are
companies that USE CDMOs/CROs, not companies that ARE one. This is the canonical over-recall pattern
documented in SKILL.md (the refractory railcar->oncology case), reproduced cleanly.

## 2. Gate-2 survivors (true theme members)

| Ticker | Name | Fit | Why a member |
|---|---|---|---|
| LFCR | Lifecore Biomedical | pure_play | Self-described fully-integrated CDMO; cGMP fill-finish of sterile injectables + HA manufacturing |
| NEO | NeoGenomics | partial | Oncology diagnostics lab WITH a Pharma Services (clinical-trial central-lab / CRO-adjacent) segment |
| MRVI | Maravai LifeSciences | partial | Nucleic-acid bioprocessing (CleanCap, GMP oligos) - contract input-supplier to biopharma |

## 3. Ranked shortlist (all WATCH)

| Rank | Ticker | Rating | Conf | Rev | NI | OCF | MoS | basis | buy_eligible | kill-flags |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MRVI | WATCH | 50% | $186M | -$131M | -$58M | -30.9% | fcf_cap | true | material_weakness |
| 2 | NEO | WATCH | 50% | $727M | -$108M | +$5M | null | fcf_cap | true | none |
| 3 | LFCR | WATCH | 45% | $76M | -$18M | +$7M | -100% (NAV) | nav | false | material_weakness |

(rank.py combined ordering; none sink.)

## 4. BUY analysis - honest 0-BUY

No candidate satisfies the BUY rule (mos_basis in {fcf_cap,nav} AND numeric MoS>=30 AND
buy_eligible==true AND zero kill-flags). Each fails on at least one hard count:

- **LFCR** - fails THREE ways: (a) buy_eligible=False, reason debt_truncation_suspected (XBRL
  reported total_debt=$1.0M vs balance-sheet-implied ~$233M, a 233x truncation - a genuine data
  artifact, confirmed in data_quality); (b) NAV MoS = -100% (normalized FCF -$12.1M and tangible
  equity $0 - no valuation basis exists); (c) material_weakness kill-flag (10-K ICFR), killflag>=1.
- **NEO** - buy_eligible=True and zero kill-flags, but mos_basis=fcf_cap with MoS=**null** (no
  positive normalized FCF: -$108M GAAP loss, +$5M OCF). A null MoS cannot meet >=30. Routes to
  rank-on-multiples / abstain, not BUY.
- **MRVI** - buy_eligible=True, but MoS = **-30.9%** (price ~31% ABOVE reverse-DCF fair value) AND a
  material_weakness kill-flag. Negative MoS is the opposite of the +30 threshold.

There is no mechanical BUY, hence no per-BUY adversarial verdict is owed. See section 6 for the
adversarial check on the closest-to-BUY name (LFCR) confirming nothing real was wrongly suppressed.

## 5. Code-paths exercised (focus: customer-concentration kill)

- **Concentration KILL path - exercised, fired NEGATIVE on all 3.** concentration_flag = null for
  LFCR (top_customer/program null), NEO (top_customer_pct=10.0), MRVI (top_customer_pct=20.8). None
  reached the kill thresholds (top_customer>40 / top_program>60) or the 40-60 watch band. The kill
  path correctly did NOT gate any buy_eligible. This is the requested focus path: it ran and produced
  a clean negative - no false kill, no missed kill at the magnitudes the XBRL exposed.
- **A2 concentration_unquantified advisory - fired POSITIVE on all 3.** Each carries
  concentration_text_flag=True but concentration_flag=null -> concentration_unquantified=True
  (advisory only; does NOT gate buy_eligible). Honest: MRVI has real post-COVID single-customer
  (CleanCap) concentration that a 20.8% point read understates; LFCR is genuinely concentrated in a
  few injectable customers. The advisory flag is the correct read-the-footnote signal where XBRL
  magnitude extraction failed.
- **debt_truncation_suspected (LFCR)** - fired correctly on a 233x debt truncation; forced
  buy_eligible=False. Genuinely implausible magnitude, not a real low-debt balance sheet.
- **material_weakness hard-ceiling** - tenk/has_material_weakness=True on LFCR and MRVI; surfaced as
  a kill-flag by the verdict builder (caps Dim 1 at 2; counts toward killflag_count). NOT a cheap_pass
  elimination (only going_concern is), so both correctly proceeded to deep-dive carrying the ceiling.
  NEO clean.
- **P7 cross-source sanity band** - cross_source_checked=True, cross_source_mismatch=False on all 3
  (within 2.5x on all comparable fields). Limit: P7 did NOT catch LFCR debt truncation because the
  independent (yfinance) debt figure was also low/absent - the internal magnitude guard carried it.
  A useful documented blind spot of the second-source gate.
- **A1 degenerate-base guard** - contamination_ratio negative for all 3 (LFCR -1.4521, NEO -0.3173,
  MRVI -0.2935), so fundamental_decline_flag and peak_contamination_flag were correctly suppressed
  (a negative normalization base is uninterpretable). NOTE for MRVI: the melting-ice-cube decline-veto
  could NOT evaluate even though MRVI is a textbook decliner (rev -28.3%, rev_slope_sign=-1,
  latest_below_avg=True) - the negative MoS independently blocks the BUY, but the suppressed
  decline-veto is a known blind spot worth flagging.
- **Firewall (signals side-channel)** - signals present as a top-level sibling of derived (NOT inside
  it) on all 3; no valuation/buy_eligible field reads it. Diagnostic labels: LFCR unpriced_improvement,
  NEO aligned, MRVI melting_ice_cube_priced. With 0 BUYs the firewall is trivially intact; notably
  LFCR unpriced_improvement did NOT and could NOT lift it past the debt/material-weakness blocks.

## 6. Adversarial verification (closest-to-BUY = LFCR)

Question: is LFCR a real opportunity the machine wrongly killed, or correctly suppressed?
**Verdict: correctly suppressed - not an artifact masking a real buy.** Three independent grounds:
(1) debt truncation is a confirmed 233x XBRL artifact (data_quality logs reported_total_debt=1.0M,
implied_debt(liab-equity)=233.2M); (2) even ignoring debt, normalized FCF is -$12.1M and tangible
equity is $0, so NO positive valuation basis exists for a BUY on either path; (3) a real
material_weakness ICFR disclosure independently bars BUY. The +772% revenue line is a fiscal-
transition artifact (Landec FY change), not growth. Nothing here is a wrongly-killed bargain.

## 7. Data-quality issues

- LFCR debt truncation ($1.0M vs ~$233M implied) -> NAV unreliable; normalized FCF/EBITDA both
  negative; tangible equity $0; revenue +772% is a fiscal-calendar discontinuity.
- All 3: concentration magnitude unextractable from XBRL (concentration_unquantified).
- All 3: large GAAP-loss-vs-OCF gaps (intangible amortization, SBC) -> fcf_cap MoS null/negative.
- MRVI decline-veto suppressed by degenerate (negative) contamination base - known blind spot.
- TrendsMCP T2 enrichment unavailable this run (daily+monthly quota exhausted by parallel coverage
  runs). T2 is firewalled and never drives buy_eligible, so the 0-BUY conclusion is unaffected.

## 8. recall@gold

**n/a** - cdmo-cro has no hand-built gold true-member list in THEME_GOLD (only deathcare,
water-utilities, railcar-leasing, regional-gaming do). track_forward --recall-gold --theme cdmo-cro
returns: no gold list for theme cdmo-cro - not measurable. Not measurable, not a miss.

## 9. Market-intel / T2 context

TrendsMCP request quota was exhausted at run time (5/5 daily, 100/100 monthly), so no alt-data
momentum series was pulled. Qualitative T2 context (analyst, non-gating): the small-cap CDMO/CRO
cohort post-COVID is in a destocking/normalization down-cycle - MRVI -28% revenue and
melting_ice_cube_priced are consistent with the sector CleanCap/COVID-vaccine air pocket; LFCR
fill-finish franchise is mid-turnaround (unpriced_improvement hints fundamentals may be improving
faster than price, but the filing data is too corrupted to act on). None of this moves any
buy_eligible verdict - recorded as context only.

## 10. Skeptical-PM usable verdict

**Usable: YES (as a scanner).** The pipeline did exactly its job: it enumerated a 485-name universe,
mechanically eliminated the going-concern/death-spiral cohort, and - most importantly - the LLM
theme-fit gate stripped 94 of 97 deep-band false positives (the entire biotech/bank over-recall),
leaving the 3 genuine CDMO/CRO names. It then refused to manufacture a BUY: all 3 are either
data-corrupted (LFCR), un-valuable on FCF (NEO), or expensive + declining (MRVI), and two carry
material-weakness ceilings. A skeptical PM gets a clean, honest nothing-actionable-here-today plus the
precise reasons - and a short watchlist (LFCR if the debt/fiscal data cleans up; NEO if losses turn
GAAP-positive). The output is trustworthy and the kill-flags bit correctly. **0 clean BUYs.**
