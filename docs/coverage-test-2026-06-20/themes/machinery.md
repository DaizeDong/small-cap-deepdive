# Coverage Test, Theme: Machinery (Industrial Machinery / Capital Equipment)

- **Skill version:** v0.3.0 (commit f12fef5)
- **Run batch:** `2026-06-21_cov-machinery` (`reports/smallcap/2026-06-21_cov-machinery/`)
- **Theme keywords:** `industrial machinery, capital equipment`
- **Sector:** Industrials
- **Code-path focus:** cyclical normalization / EBIT-cascade
- **Date:** 2026-06-21 (run-tool date; coverage-test cohort 2026-06-20)
- **Headline result:** **0 mechanical BUYs. 0 BUYs after adversarial verification. Honest, defensible 0-BUY.**

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery (FTS + SIC reverse-recall, small-cap band) | 103 | `universe_machinery_2026-06-21.csv` |
| Cheap_pass survivors (mechanical de-risk) | 61 | going-concern / death-spiral / material-weakness scan |
| After SIC Gate 1 | 61 | keep=47, review=14 (review routed to LLM gate) |
| **LLM theme-fit Gate 2 survivors (deep-band, deep-dived)** | **18** | I judged true membership; 27 misrecalls dropped |
| Deep-dive data pulls (no ERROR files) | 18 | every deep-band survivor; 0 crashes |
| Valuations (`--json` + `--ticker`) | 18 | all exit 0 |
| **Mechanical BUYs** | **0** | none clear the v0.3.0 BUY rule |
| **BUYs surviving adversarial verification** | **0** |, |

**Gate-2 drops (27 misrecalls, not deep-dived) and why:**
- Mining/metals **producers** (not machinery makers): DC, NEXA, URG, CHNR, SND, TMC*, PPTA*, CGAU*, SID (steel).
- Pharma / biotech: PAHC, BBOT.
- Medical devices (SIC 384x): PROF, ENOV, STXS, ELMD, CNMD, POCI, OMCL (pharmacy-dispensing automation, medical, not industrial).
- Semiconductor **foundry** (makes chips, not equipment): SKYT.
- Banks / BDCs / ETF-trusts / financial services: PFIS, PPLT, MSB, WHF, CGBD, BBDC, PFLT, MFIC, OCSL, CICB, plus `nan`-SIC BDC cluster.
- Construction shell / IT reseller / education / services: FGL, PLUS*, DXPE*, UTI*, G*, GLTR*, BNL*, VGNT*, PHIN*, AMPX*, IOSP*, ICHR*, LASR*, CECO* (`*` = watch-band, out-of-scope by size anyway).

**Theme-fit survivors deep-dived (18):** CVV, ERII, ASYS, GHM, AP, PRLB, NPK, CYD, FET, DAIO, ESP, MLAB, NPWR, BLDP, ELVA, NNDM, PACK, TITN.

> The canonical theme-fit risk (keyword sweeping an adjacent sector) materialized exactly as the SKILL warns: `industrial machinery / capital equipment` FTS swept mining producers, medical-device makers, banks and BDCs. SIC Gate 1 + LLM Gate 2 cleared them. Skipping either gate would have dumped ~27 false positives into the deep-dive queue.

---

## 2. Ranked shortlist (full cohort, finalize_run RANKING)

Non-sunk (观察 / watch), clean (buy_eligible, 0 buy-ineligible reasons), but none cheap enough to BUY:

| # | Ticker | Name | Rating | MoS basis | MoS% | Rev | NI | Note |
|---|---|---|---|---|---|---|---|---|
| 1 | AP | Ampco-Pittsburgh | 观察 | nav | -100% | $416M | -$66M | forged rolls + air handling; deep losses |
| 7 | ERII | Energy Recovery | 观察 | nav | -71.5% | $135M | +$23M | pressure-exchanger; profitable but rich |
| 9 | GHM | Graham Corp | 观察 | fcf_cap | -96.7% | $245M | +$12M | best quality, but 57x EV/EBITDA |
| 10 | PRLB | Proto Labs | 观察 | nav | -83.0% | $533M | +$21M | digital mfg; profitable, expensive |
| 8 | FET | Forum Energy Tech | 观察 | fcf_cap | -89.6% | $792M | -$10M | oilfield capital equipment |
| 3 | CVV | CVD Equipment | 观察 | fcf_cap | None | $26M | -$2M | neg normalized FCF -> abstain |
| 5 | DAIO | Data I/O | 观察 | fcf_cap | None | $22M | -$5M | neg normalized FCF -> abstain |
| 2/4/6 | BLDP / CYD / ELVA | Ballard / China Yuchai / Electrovaya | 观察 | fcf_cap | None | n/a | n/a | foreign filers (20-F), financials unparseable |

Sunk (避开 / avoid, buy-ineligible or kill-flag): ASYS, ESP, MLAB, NNDM, NPK, NPWR, PACK, TITN.

Full per-name DD: `report_<ticker>.md` in the run dir.

---

## 3. BUY analysis, honest 0-BUY

The v0.3.0 BUY rule requires **ALL** of: `mos_basis in {fcf_cap, nav}` AND numeric `MoS >= 30%` AND `buy_eligible == true` AND zero kill-flags. **No candidate satisfied it.** Distribution of why:

- **Negative MoS (overvalued vs intrinsic), 6:** AP (-100%), ERII (-71.5%), GHM (-96.7%), PRLB (-83%), FET (-89.6%), ESP (-84.6%). These are richly-valued or loss-making industrials; the FCF-cap / NAV intrinsic band sits far below market cap.
- **MoS = None (correct abstain), 6:** CVV, DAIO, NPWR (negative normalized FCF -> no intrinsic band can be built); CYD, BLDP, ELVA (foreign 20-F filers, `ev_is_market_cap_only`, financials unavailable). The model abstains rather than fabricating a band, the desired behavior.
- **buy_eligible == false (guard fired), 8:** ASYS, ESP, MLAB, NPWR, NNDM, NPK, TITN (`cross_source_mismatch`); PACK (`extreme_mos_review_required` + `fundamental_decline_flag` + `peak_contamination_flag`).
- **Closest near-miss, TITN, +13.1% MoS:** still below 30, AND buy-ineligible (see adversarial below).

There is no BUY to defend. Per the task's adversarial mandate I instead stress-tested the 0-BUY for a *false negative*, a real cheap cyclical wrongly suppressed by a data/model artifact.

### Adversarial verification of the 0-BUY (false-negative hunt)

**TITN (Titan Machinery), the only positive MoS.** Verdict: **correctly excluded, not a missed opportunity.**
- MoS +13.1% is below the 30% bar regardless of eligibility.
- `cross_source_mismatch` fired on total_debt: SEC = $176.6M vs yfinance = $858.3M (4.9x gap). TITN is an ag/construction-equipment **dealer** carrying heavy floorplan financing; the debt figure that drives EV (and therefore the FCF-cap MoS) is ambiguous by ~$680M. A +13% MoS computed on an unreliable EV is not investable. The guard is firing on a genuine data hazard, exactly as designed.
- At ~16.6x EV/EBITDA with reverse-DCF implied growth of **-4.3%** on a cyclical dealer near top-of-cycle, even the optimistic (SEC-debt) read gives no margin of safety.

**GHM (Graham Corp), highest-quality survivor.** Verdict: **correctly 观察, not BUY.** Only name with both positive growth (+17%) and net insider buying, but 57x EV/EBITDA, 104x P/E, ~0% FCF yield, normalized-FCF MoS -96.7%. This is an expensive momentum industrial, the opposite of a neglected-value candidate. No artifact; the valuation is simply rich.

**Foreign-filer abstains (CYD, BLDP, ELVA).** Verdict: **honest data gap, not a suppressed BUY.** 20-F XBRL did not parse into the financial series, so MoS is None. The model correctly does not guess. These are flagged as data-quality limitations, not eliminated as bad businesses, but they cannot be BUYs without parseable fundamentals.

**Conclusion:** the 0-BUY is real. No cheap cyclical was lost to a model artifact; the cohort is genuinely either richly valued, structurally loss-making, or unparseable.

---

## 4. Code-paths exercised

- **Discovery + SIC reverse-recall floor** (`run_theme` -> `discover` -> `cheap_pass` -> `filter_by_sic`). The SIC floor enumerated dedicated machinery SICs and unioned with FTS recall; it also emitted a sidecar railcar-SIC candidate set (see data-quality note 1).
- **Two-stage precision gate:** SIC Gate 1 (keep/review/exclude) + my LLM theme-fit Gate 2 (pure_play / partial / misrecall). 27 misrecalls dropped.
- **Cyclical normalization / EBIT-cascade:** `cyclical=true` and 5-yr trailing-average normalization fired across the cohort (e.g. GHM `cv_ebitda=0.46`, TITN `cv_ebitda=0.71`, both above the 0.25 cyclical threshold -> `normalization_note: cyclical:trailing_5yr_avg`). The EBIT cascade fed `normalized_ebitda` / `normalized_fcf` -> intrinsic band -> MoS. **This is the focus code-path and it ran as intended on every candidate with parseable financials.**
- **v0.3.0 buy-eligibility guards that fired:** `cross_source_mismatch` (7 names), `extreme_mos_review_required`, `fundamental_decline_flag`, `peak_contamination_flag` (all on PACK). No financial-SIC/insurance, concentration-kill, large-cap, debt-truncation, wrong-entity, or low-revenue-loss-extreme exclusions were needed at the BUY gate (those were handled upstream by Gate 2 dropping the financials/BDCs).
- **Abstain path:** `mos_null_reason = intrinsic_band_unavailable` for negative-FCF and foreign-filer names, the model declined to fabricate a band.
- **finalize_run:** completeness assert (18 deep-band == 18 reports, 0 missing), verdict block (`deepdive_verdicts.json`, 18 verdicts), RANKING rebuild, trust banner injected into every report.
- **Signals side-channel:** emitted as a diagnostic field inside the deepdive JSONs, firewalled, it did not feed `buy_eligible` (verified: no BUYs, and the guards are the only inputs to eligibility).
- **track_forward calibration:** 15 verdicts recorded to `metrics/verdicts.jsonl` (3 duplicates skipped).

---

## 5. Data-quality issues

1. **Stale railcar-SIC sidecar in the run dir.** The SIC reverse-recall floor wrote `candidates_railcar_leasing.json` (63 names: FreightCar, Greenbrier, ethanol producers, banks) and `universe_railcar_leasing_2026-06-21.csv` into this machinery run. They share machinery-adjacent SIC ranges (e.g. 3743 railroad equipment) but are a different theme and have **no deepdive JSONs**. I moved them to `_sic_floor_sidecar/` so finalize_run's deep-band universe = my 18 theme-fit survivors only. If left in place they would have falsely demanded 40+ railcar reports. **Action item for the skill: the SIC floor should namespace its sidecar files under the active slug or a `_sicfloor/` subdir, not write sibling `candidates_<otherslug>.json` that finalize_run globs as deep-band.**
2. **Foreign-filer financial parsing (CYD, BLDP, ELVA).** 20-F XBRL did not populate revenue / cash / debt / D&A / capex -> `ev_is_market_cap_only`, MoS None. Three of 18 (17%) unusable for valuation. Honest abstain, but a recall gap for ADR-listed machinery names.
3. **cross_source_mismatch is doing heavy lifting (7/18).** Several are genuine hazards (TITN floorplan debt 4.9x), but a high mismatch rate suggests the SEC-vs-yfinance debt reconciliation is noisy for dealers/lessors and foreign filers; worth a per-source confidence weighting rather than a binary kill.
4. **RANKING funnel header cosmetic count** ("19 家逐一 deep dive" vs actual 18), display-only, does not affect verdicts.
5. **No gold list for machinery** -> recall@gold not measurable (expected; only water-utilities / railcar-leasing / regional-gaming / deathcare have gold cohorts).

---

## 6. recall@gold

**n/a**, machinery has no hand-curated gold true-member list in `THEME_GOLD`. `track_forward.py --recall-gold ... --theme machinery` returns "no gold list ... not measurable". Recall floor is therefore unquantified for this theme.

---

## 7. Market-intel / Trends context (T2, analyst color only, does NOT drive buy_eligible)

- **Search interest, "industrial machinery" (Google):** +63.6% YoY (22 -> 36 on 0-100 scale) but **-40% over the last 3 months** (60 -> 36).
- **Search interest, "capital equipment" (Google):** +73.3% YoY (15 -> 26) but **-62.9% over the last 3 months** (70 -> 26).

Both keywords show attention that rose over the year then rolled over this quarter, a late-cycle / cooling-attention signature consistent with the deep-dive's picture (negative MoS across the cohort, declining trailing growth in TITN/FET/ERII, peak-contamination flag on PACK). This corroborates *avoiding* the cohort at current prices; it is context, not an input to any rating.

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** The run did the one thing a web-search/LLM pass cannot: it enumerated the SEC small-cap universe for the theme, mechanically de-risked it, applied a consistent two-stage precision gate that correctly rejected the mining/medical/banking false positives the keyword swept in, and ran the cyclical EBIT-cascade valuation on every survivor, then returned a disciplined **0-BUY** with an auditable reason for each name. A PM gets: (a) a clean watchlist of 10 real industrial-machinery small-caps that survived the guards (GHM, ERII, PRLB, FET, AP the most substantive), none currently cheap; (b) explicit elimination of 8 names on data/fundamental hazards; and (c) an honest flag that 3 foreign filers are unvaluable from EDGAR alone. The landmine-scanner worked. The only build issues are housekeeping (the stale railcar sidecar) and a recall gap on ADR filers, neither produced a false BUY. A skeptical PM would trust the negative and use the watchlist as the starting point for a price-drawdown trigger list.
