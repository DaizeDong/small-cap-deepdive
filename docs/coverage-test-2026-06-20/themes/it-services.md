# Coverage Test, IT Services (InfoTech)

- **slug:** `it-services`
- **sector:** InfoTech
- **keywords:** `IT services, managed services, consulting`
- **run batch:** `reports/smallcap/2026-06-21_cov-it-services/`
- **skill version:** v0.3.0 (commit `f12fef5`, dirty)
- **code-path focus:** mature / clean-FCF candidate
- **date:** 2026-06-21
- **verdict (skeptical PM):** USABLE. The scanner did its job, it eliminated the entire
  field down to zero clean BUYs and the eliminations are individually defensible. This is a
  correct "nothing here" answer, not a tool failure.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw FTS universe (marketcap-resolved) | 829 | EDGAR full-text search on the 3 keywords across 10-K/10-Q/20-F/40-F. **Under the 1000-hit FTS cap → no truncation.** |
| Small-caps to cheap_pass | 41 | After market-cap ceiling ($2.0B small-cap band; watch-band $2 to 5B surfaced separately) |
| cheap_pass survivors | 26 | Hard kill-flags (going_concern / death_spiral / material_weakness) eliminated the rest; e.g. GLOB, ACHV killed |
| After SIC coarse gate (Gate 1) | 26 | keep=14, review=12 (review forwarded to LLM gate). No names dropped at Gate 1. |
| Candidates written | 26 | 21 `band=deep` + 5 `band=watch` |
| **Gate 2 (LLM theme-fit), deep-band retained** | **9** | CXDO, NABL, ASGN, DXC, RXT, CNXC, TBRG, DAVA, CSPI |
| Gate 2 deep-band misrecalls (gated, resolved) | 12 | 6 BDCs + auto-finance + hospital + nuclear-fuel + Argentine RE + online gambling + used-car |
| Deep-dived (every retained survivor) | 9 | full deepdive_data + valuation, no sampling |
| Valuated | 9 | all with `--json` AND `--ticker` |
| **Mechanical BUYs** | **0** | none clears MoS≥30% AND buy_eligible AND zero kill-flags |
| **Clean BUYs (post-adversarial)** | **0** | nothing to verify; honest 0-BUY |

**Discovery-floor note (relevant coverage finding):** `it-services` has **no dedicated single
SIC code** and therefore **no SIC reverse-recall floor** in this run, discovery was FTS-keyword
only. IT services spans SIC 7370 to 7379, 7389, 7363, 4813 etc.; no clean single-SIC enumeration
backstops the FTS arm. Recall here rests entirely on keyword recall. The FTS arm did **not** hit
the 1000-hit cap (829 hits), so recall did not collapse, but a true member with an unlucky
keyword phrasing in a fragmented SIC could in principle be missed with no SIC floor to catch it.

---

## 2. Gate-2 theme-fit reasoning (the high-leverage step)

The raw FTS over-recall behaved exactly as the SKILL.md cautionary tale predicts. The single
biggest false-positive cluster was **business development companies (BDCs)**, KBDC, GSBD, MSDL,
BCIC, PFLT, MFIC, closed-end specialty-finance lenders whose 10-Ks say "consulting" / "services"
/ "middle-market" but are financial entities, not IT firms. All 6 dropped at Gate 2. Other
misrecalls: VRM (used-car e-commerce), CPSS (auto-loan finance), ARDT (hospital operator), LTBR
(nuclear fuel tech), IRS (Argentine real estate), CDRO (online gambling).

**Retained (true IT-services members):**

| Ticker | Fit | Why |
|---|---|---|
| ASGN | pure_play | IT/professional staffing + consulting (Apex Systems / consulting), SIC 7363 |
| DXC | pure_play | Managed infrastructure + IT outsourcing, SIC 7374 |
| RXT | pure_play | Hybrid cloud + managed services operator, SIC 7370 |
| DAVA | pure_play | IT/software-engineering services & digital consulting (Endava, 20-F), SIC 7371 |
| CSPI | pure_play | IT integration + managed IT + security products, SIC 7373 |
| CXDO | pure_play | UCaaS + managed IT services (Crexendo), SIC 4813 |
| CNXC | partial | CX/digital-operations + tech services (BPO-heavy), SIC 7389 |
| TBRG | partial | Healthcare IT solutions + RCM services (TruBridge), SIC 7371 |
| NABL | partial | IT-management / cybersecurity SaaS for MSPs (N-able), SIC 7372 |

---

## 3. Ranked shortlist (all WATCH, see RANKING.md)

| Rank | Ticker | Rating | Conf | mos_basis | eff MoS | buy_eligible | kill | Primary block |
|---:|---|---|---:|---|---:|---|---:|---|
| 1 | CNXC | 观察 WATCH | 55 | fcf_cap | −142% | false | 0 | extreme_mos_review + fcf_sustainability_uncertain |
| 2 | NABL | 观察 WATCH | 55 | fcf_cap | −39% | **true** | 0 | MoS < 30% (no positive MoS) |
| 3 | RXT | 观察 WATCH | 55 | nav | −100% | false | 0 | fundamental_decline + peak_contamination (V-shape) |
| 4 | TBRG | 观察 WATCH | 55 | fcf_cap | −72% | **true** | 1 | MoS < 30% |
| 5 | DAVA | 观察 WATCH | 50 | fcf_cap | None | **true** | 0 | MoS=None (20-F, financials unavailable) |
| 6 | ASGN | 观察 WATCH | 45 | nav | −100% | false | 0 | wrong_entity_suspected (ticker absent from company_tickers) |
| 7 | DXC | 观察 WATCH | 45 | fcf_cap | +543% | false | 0 | extreme_mos_review + fcf_sustainability + fundamental_decline |
| 8 | CSPI | 观察 WATCH | 40 | fcf_cap | −76% | false | 1 | cross_source_mismatch (debt SEC 25.3M vs yf 2.1M, 12.2x) |
| 9 | CXDO | 观察 WATCH | 40 | nav | −94% | false | 0 | cross_source_mismatch (rev SEC 18.1M vs yf 68.2M, 3.8x) |

> MoS is stored as a ratio (1.0 = 100%). The BUY threshold MoS≥30% = ratio ≥ 0.30.

---

## 4. BUYs, none. Why each near-miss is correctly NOT a BUY (adversarial)

There are **zero mechanical BUYs**, so there is no BUY to adversarially defend. The discipline
here is to confirm the 0-BUY is genuine (no candidate was wrongly suppressed) AND that the three
`buy_eligible == true` names are genuinely below the bar rather than artificially blocked. They
are:

- **NABL (buy_eligible=true, MoS −39%):** the closest thing to a candidate. Negative net income,
  fcf_cap MoS deeply negative → no MoS BUY. Its firewalled T2 signal `price_divergence =
  unpriced_improvement` (−60% trailing price vs improving fundamentals) is exactly the kind of
  signal the design forbids from originating a BUY, and it correctly did NOT. Adversarial check:
  is the −39% MoS a data artifact? No, market cap $576M vs a normalized-FCF intrinsic well below
  it; the company is loss-making on a GAAP basis. Genuine WATCH.
- **TBRG (buy_eligible=true, MoS −72%, kill=1):** marginally profitable ($4M NI on $347M rev),
  fcf_cap MoS −72%. No artifact; richly priced vs normalized FCF. Genuine WATCH.
- **DAVA (buy_eligible=true, MoS=None):** **buy_eligible=true is misleading here**, as a 20-F
  foreign filer almost every financial is unavailable (cash/debt/dep_amort/capex/normalized_fcf
  all null), so the `buy_eligible` guards had no data to fire on, and MoS=None means there is no
  tradeable basis at all. A PM must treat this as "not assessable," not "eligible." This is a
  legitimate coverage-test data-quality finding about 20-F handling (see §6).

And the blocked-eligibility names confirm the v0.3.0 guards bite correctly:

- **DXC** posted a nominal +543% fcf_cap MoS, exactly the artifact the `extreme_mos_review_required`
  guard exists to catch (`mos=543.3%_exceeds_100pct`), reinforced by `fcf_sustainability_uncertain`
  (reverse-DCF implied growth −72.7%) and `fundamental_decline_flag`. Without these guards this
  would have been a spurious headline BUY. **The guards converted a data artifact into a WATCH ,
  this is the test passing.**
- **CSPI / CXDO** were blocked by the **P7 cross-source sanity band** (the only external,
  non-SEC-internal check): CSPI debt SEC $25.3M vs yfinance $2.1M (12.2x), CXDO revenue SEC
  $18.1M vs yfinance $68.2M (3.8x). A corrupted single-source input cannot back a tradeable MoS.
  Correct gate.
- **RXT** fired both `fundamental_decline_flag` AND `peak_contamination_flag` (V-shape value
  trap: contamination_ratio 0.6395, latest NI −$225.8M), the melting-ice-cube defense.
- **ASGN** fired `wrong_entity_suspected` (`ticker_absent_from_sec_company_tickers`). This is a
  data-layer integrity catch worth a human look (ASGN is a real, well-known IT staffer), but it
  correctly blocks BUY on an entity-resolution doubt rather than trusting a possibly-mistagged
  filing.

---

## 5. Code-paths exercised (the point of the coverage test)

This theme is a strong stress of the v0.3.0 `buy_eligible` composite, **8 distinct guard
terms fired across the 9 survivors**:

- `extreme_mos_review_required`, CNXC (−142%), DXC (+543%)
- `fcf_sustainability_uncertain`, CNXC, DXC
- `fundamental_decline_flag` (P6 melting-ice-cube veto), DXC, RXT
- `peak_contamination_flag` (P-A V-shape veto), RXT
- `cross_source_mismatch` (P7 second-source sanity band), CSPI, CXDO
- `wrong_entity_suspected` (refined: ticker-absent path), ASGN
- `fcf_cap_model_unsuitable` (debt/assets > 0.62), RXT (0.979)
- financial-SIC / BDC routing at Gate 2 (12 misrecalls incl. 6 BDCs), discovery-level
- concentration: `concentration_unquantified` (advisory, did NOT gate), CNXC, CSPI, CXDO, DXC, DAVA
- 20-F foreign-filer path (`form_used=20-F`), DAVA
- Firewalled T2 `signals` side-channel populated for all 9 (price_divergence + ownership),
  **confirmed sibling of `derived`, never inside it → cannot reach BUY path.** NABL's
  `unpriced_improvement` did not create a BUY.

Guards NOT exercised this theme (no candidate triggered): `low_revenue_loss_ratio_extreme`,
`insurance_concepts_present`, `large_cap_out_of_scope` (watch-band names skipped pre-deepdive),
`debt_truncation_suspected`, concentration `kill`.

---

## 6. Data-quality issues

1. **20-F foreign-filer financials sparse (DAVA):** cash, debt, dep_amort, capex, normalized
   EBITDA and normalized FCF all unavailable → intrinsic band null, MoS=None, yet
   `buy_eligible=true`. The eligibility flag is **true-by-absence-of-data**, which is misleading.
   A PM should read this as "not assessable," and a future hardening could route MoS=None +
   pervasive-null to a `data_insufficient` ineligibility reason rather than letting `buy_eligible`
   read true.
2. **Cross-source mismatches (CSPI, CXDO)**, large SEC-vs-yfinance disagreements (debt 12.2x;
   revenue 3.8x). P7 correctly gated both; flagged for human reconciliation. CSPI's debt is also
   a `Liabilities_proxy` (total-liabilities stand-in), part of why the SEC figure diverges.
3. **wrong_entity_suspected on ASGN**, ASGN absent from `company_tickers.json` at lookup
   (deepdive had to be re-run with explicit `--cik 890564`). Real company; entity-resolution
   gap worth fixing.
4. **`concentration_unquantified` pervasive (5/9)**, text concentration flag true but XBRL
   magnitude null; advisory only (did not gate), per A2. Analyst must read the 10-K footnote.
5. **No SIC reverse-recall floor** for it-services (fragmented SIC space), discovery rests on
   FTS keyword recall alone (see §1).
6. **TrendsMCP quota exhausted**, could not pull alt-data trend context this run (optional T2,
   never drives BUY; noted for completeness).

---

## 7. recall@gold

**n/a.** `it-services` has no hand-built gold true-member list in `track_forward.py`
(`recall@gold: no gold list for theme 'it-services' — not measurable`). The gold lists exist only
for water-utilities, railcar-leasing, regional-gaming, and deathcare.

---

## 8. Market-intel / T2 context (does NOT drive buy_eligible)

- TrendsMCP daily+monthly quota was exhausted at run time, no fresh alt-data trend series.
- Sector framing (analyst context, not filing-derived): the listed IT-services group splits
  cleanly into (a) **secular-decliner legacy outsourcers** (DXC, RXT) whose reverse-DCF implied
  growth is steeply negative and whose mechanical vetoes (fundamental_decline / peak_contamination)
  fired, the market is pricing in melt, and the model agrees it is not a clean trough buy; and
  (b) **smaller niche/vertical players** (CXDO, TBRG, NABL, CSPI) that are loss-making or
  marginally profitable with no MoS cushion. None is a neglected-and-undervalued industrial
  beneficiary at current prices. The firewalled `price_divergence` signals (NABL/CSPI
  `unpriced_improvement`; RXT `melting_ice_cube_priced`) are diagnostic context only and are
  recorded for future per-signal Brier calibration; they changed no rating.

---

## 9. Skeptical-PM usable verdict

**USABLE, and a textbook "nothing found" outcome.** The scanner enumerated 829 raw hits,
eliminated the entire BDC/finance/off-theme false-positive cloud at Gate 2 (12 deep-band
misrecalls), and then mechanically blocked every remaining name from BUY, most importantly
catching DXC's +543% MoS artifact and two cross-source data corruptions that a single-source
screen would have trusted. Zero BUYs is the correct answer: the small-cap IT-services universe
right now is legacy melt + sub-scale unprofitables, with no clean-FCF undervalued pure-play.
The one place a PM must override the machine's optimism is **DAVA**, where `buy_eligible=true` is
an artifact of missing 20-F data, not a genuine pass.
