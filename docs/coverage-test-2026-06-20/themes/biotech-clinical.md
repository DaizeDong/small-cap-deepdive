# Coverage Test, Theme: biotech-clinical (clinical-stage biotech / drug development)

- **Run batch:** `reports/smallcap/2026-06-21_cov-biotech-clinical/`
- **Skill version:** v0.3.0 (commit `f12fef5`, dirty working tree)
- **Sector:** HealthCare
- **Keywords (FTS):** `clinical stage biotech, drug development`
- **Code-path focus:** pre-revenue binary / going-concern / abstain routing
- **Date:** 2026-06-21
- **Result headline:** **0 BUY** across 42 deep-dived survivors, the correct landmine-scanner answer for a pre-revenue clinical-biotech universe.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Discover (FTS + mktcap filter, small-cap ≤ $2.0B) | 142 | EDGAR full-text search on the two keywords, market-cap resolved |
| cheap_pass mechanical scan | 142 scanned | hard kill-flag screen (going-concern / death-spiral / material-weakness) |
| cheap_pass survivors | 52 | ~90 eliminated by kill-flags / data |
| SIC gate (Gate 1) | 52 | keep=3, review=49 (review → LLM theme-fit). No SIC reverse-recall floor exists for biotech (no dedicated single SIC) |
| Candidates JSON | 52 | bands: **deep=42**, watch=10 |
| **Deep-band deep-dived** | **42** | every deep-band survivor, NO sampling |
| Watch band (>$2B, skipped) | 10 | BCRX, ADPT, QURE, IDYA, ACAD, CPRX, NKTR, DNLI, ELVN, VKTX |
| deepdive ERRORs | 0 | no `deepdive_*_ERROR.json` written |
| valuations computed | 42 | each with `--json` AND `--ticker` |
| **Mechanical BUYs** | **0** | |

> Note: `RANKING.md`'s prose funnel line reads "43 家逐一 deep dive", an off-by-one cosmetic count in `rank.py`'s narration; the ranked table contains exactly 42 rows and 42 reports/verdicts were emitted. Flagged under data-quality (§6).

SIC composition of the 42 deep band: 2834 pharma-prep (dominant), 2836 biological products, plus a handful of tool/service SIC (3841 device, 7372/7373 software, 8731/8734 research-services, 3826 instruments, 100 agriculture).

---

## 2. mos_basis distribution (the code-path-of-interest)

| mos_basis | count | meaning |
|---|---|---|
| `fcf_cap` | 24 | FCF intrinsic path attempted; **22 returned `intrinsic_band_unavailable`** (normalized FCF ≤ 0 → no tradeable MoS) |
| `nav` | 18 | asset-heavy / `fcf_cap_model_unsuitable` → NAV path; all 18 returned deeply negative or ~0 NAV MoS |
| `abstain` | 0 | every name routed to a basis (NAV always available because equity was present) |

This is exactly the **pre-revenue binary** signature: a clinical biotech has no positive normalized FCF (cash-burning R&D) and trades on pipeline option value, not book equity. The FCF path therefore yields a null intrinsic band (no MoS), and the NAV path yields a hugely negative MoS (market cap ≫ tangible equity). Neither path can manufacture a ≥30% margin of safety from the financials, which is the correct, honest output. The tool does not hallucinate a DCF on a company with no revenue.

`mos_null_reason` breakdown: `intrinsic_band_unavailable` ×22, `fcf_cap_model_unsuitable_use_nav` ×18.

---

## 3. BUY rule application

BUY requires: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric MoS ≥ 30 **AND** `buy_eligible == true` **AND** zero kill-flags.

**No name satisfies the MoS ≥ 30 leg.** The two largest positive MoS magnitudes in the entire set:
- `SBFM` (NAV +2.5%), also `buy_eligible=False` (extreme_mos_review + peak_contamination).
- `BCYC` (NAV +0.6%), `buy_eligible=True` but MoS 0.6 ≪ 30.

The single positive-equity-FCF name, `CERT` (Certara), routed `fcf_cap`, `buy_eligible=True`, but MoS = **−0.4%** (priced at intrinsic, no margin). Every other `fcf_cap` `buy_eligible=True` name has MoS = null.

**Adversarial check on the 0-BUY:** Is the no-BUY a real result or a model artifact suppressing a genuine opportunity? Verdict: **genuine.** The closest near-miss to the BUY trigger is more than 29 MoS-points away (BCYC +0.6 vs threshold 30). There is no name where a guard wrongly vetoed an otherwise-qualifying ≥30 MoS, the MoS leg itself fails universally because pre-revenue biotech has no FCF/NAV anchor. The 0-BUY is the structurally-correct landmine-scanner answer, not an over-aggressive guard. `n_buy_clean = 0`.

---

## 4. Which code-paths fired (the point of this coverage test)

**buy_eligible guard firings (15 distinct names gated, several multi-gated):**

| Guard | Count | Tickers |
|---|---|---|
| `cross_source_mismatch` | 15 | AAPG, ACRV, ALEC, ALLR, BBOT, CPIX, CRMD, FDMT, MGNX, NERV, SCYX, SDGR, TNYA, TYRA, VNDA |
| `debt_truncation_suspected` | 3 | ALEC, CPIX, NERV |
| `low_revenue_loss_ratio_extreme` | 2 | UNCY, ALLR |
| `extreme_mos_review_required` | 2 | CRMD, SBFM |
| `financial_sic_forced_unsuitable` | 1 | ALLR |
| `insurance_concepts_present` | 1 | ALLR |
| `peak_contamination_flag` | 1 | SBFM |

Plus the **pre-rev/abstain routing** path: 22× `intrinsic_band_unavailable` (FCF path correctly declines to value a cash-burner) and 18× NAV-fallback. This is the going-concern / pre-rev / abstain machinery the test targeted, and it exercised cleanly.

**ALLR (Allarity Therapeutics)** is the most-gated name, it tripped four guards simultaneously (financial-SIC, insurance-concepts, low_revenue_loss_extreme, cross_source_mismatch). A precision-medicine biotech being flagged `insurance_concepts_present` is a guard over-fire worth noting (false-positive insurance detection on a biotech XBRL), but since ALLR also fails MoS and three other guards, it has no effect on the BUY outcome.

---

## 5. Data-quality issues (T1/T2 observations)

1. **`cross_source_mismatch` dominates (15/42 = 36%).** Every instance is a **total_debt** disagreement between SEC XBRL and yfinance, not a shares or revenue mismatch. Examples:
   - VNDA: SEC $152.8M vs yf $13.1M (11.7×)
   - MGNX: SEC $196.7M vs yf $36.5M (5.4×)
   - SDGR: SEC $320.6M vs yf $107.0M (3.0×)
   - CRMD: SEC $378.6M vs yf $147.4M (2.6×)
   This is a **systematic definitional gap**: SEC full XBRL liabilities/debt (incl. operating leases, convertibles, deferred items) vs yfinance's narrower "total debt." It is endemic to biotech balance sheets (lease- and convertible-heavy). The >2.5× gate is firing on a definitional artifact rather than a true data corruption, it correctly blocks BUY here (conservative, no harm since 0 BUY), but if a biotech ever did clear the MoS leg, this guard would likely produce a **false BUY-block**. Recommend a debt-definition-aware comparison (compare like-for-like SEC short+long-term borrowings vs yf) before the next biotech-heavy run.
2. **`debt_truncation_suspected` ×3 + `debt_stale` banners**, common in biotech where the latest debt XBRL lags the latest balance-sheet assets period.
3. **`insurance_concepts_present` false-positive on ALLR** (a clinical oncology biotech), guard over-fire; non-load-bearing here.
4. **Signals side-channel:** `price_divergence` returned `None` for all 42 (no usable trailing price series matched in the diagnostic layer). Firewalled, did not touch any BUY decision. Noted as a side-channel coverage gap for this universe.
5. **`MSLE` and `TYRA` had empty `business_blurb`** at the candidate stage (Item-1 extraction miss), did not block deep-dive; both still deep-dived and valued.
6. **RANKING prose off-by-one** ("43" vs 42), cosmetic narration bug in `rank.py`.

---

## 6. LLM theme-fit (true membership judged from blurbs)

The deep band is overwhelmingly genuine clinical-stage / drug-development biopharma (pure-play): NERV, ABCL, TNYA, UNCY, ALEC, MGNX, FDMT, BCYC, NMRA, TYRA, ORIC, BBOT, AVXL, IKT, ACRV, IMUX, WHWK, OVID, CRDL, SCYX, AAPG, ENTA, LXRX, VNDA, CRMD, ZVRA, VALN, PULM, MSLE, SBFM, CPIX.

**Partial / tool-or-service members (enable drug development but are not themselves clinical-stage drug developers):** OABI (antibody-discovery licensor), SDGR (computational drug-discovery software + pipeline), CERT (biosimulation software/consulting), SLP (biopharma simulation software), NAUT (proteomics instruments), TLSI (drug-device combination), NEO (oncology lab/diagnostics services), KRMD (subcutaneous infusion **device**, SIC 3841).

**Likely misrecall for "clinical-stage biotech":** CWBHF (Charlotte's Web, CBD/hemp consumer products, SIC 100 agriculture). It mentions "development" but is a consumer-goods company. None of the misrecalls/partials reached BUY, so membership precision did not affect the outcome, but for a strict theme run, CWBHF and the pure-software vendors (SLP, CERT) would be dropped at Gate 2.

---

## 7. Market-intel / TrendsMCP context (T2, analyst color only, never drives buy_eligible)

TrendsMCP enrichment was **unavailable this session** (daily + monthly request quota exhausted). No T2 trend series was attached. This is purely advisory context and has zero bearing on the mechanical 0-BUY result. For a future refresh, attach Google-News-volume / news-sentiment growth on "clinical stage biotech" as labeled T2 color only.

---

## 8. recall@gold

**n/a**, `biotech-clinical` is not one of the four gold-list themes (water-utilities / railcar-leasing / regional-gaming / deathcare) registered in `track_forward.THEME_GOLD`. `track_forward.py --recall-gold` was therefore not run (it is a no-op for themes without a hand-built gold cohort).

---

## 9. Skeptical-PM usable verdict

**Usable: YES.** The run is a clean, correct demonstration of the pre-revenue binary / abstain machinery:

- It enumerated 142 small-cap names, mechanically de-risked to 52, and deep-dived all 42 deep-band survivors with **zero crashes and zero silent skips**.
- It returned **0 BUY**, the honest answer for a clinical-biotech universe that has no FCF or NAV anchor capable of producing a ≥30% margin of safety. A scanner that produced a BUY here would be a narrative generator, not a landmine scanner.
- The guard stack fired as designed (cross_source, debt-truncation, extreme-MoS, peak-contamination, financial-SIC/insurance, low_revenue_loss_extreme), and the MoS-basis routing correctly split fcf_cap (null intrinsic) vs nav (deeply negative).
- The one **actionable defect** a PM should care about: the `cross_source_mismatch` debt-definition false-positive pattern (36% of names) would block a legitimate BUY in a future biotech run that did clear MoS. It is harmless this run but should be fixed before relying on the BUY path for any leverage-light biotech.

No mechanical BUYs survived to adversarial review; **n_buy_clean = 0**. This is the expected and correct output, and the run is usable as a coverage-test pass for the pre-rev/going-concern/abstain code paths.
