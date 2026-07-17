# Coverage Test, Theme: ipp-renewables

- **Slug:** `ipp-renewables`  |  **Sector:** Utilities  |  **Keywords:** `independent power producer, renewable energy generation`
- **Skill version:** v0.3.0, commit `f12fef5` (manifest records `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-ipp-renewables/`
  (note: tooling system date stamped the run `2026-06-21`; coverage-test campaign date is 2026-06-20)
- **Code-path focus:** capital-intensive / project-finance valuation routing (asset-heavy NAV, OCF-proxy FCF, cross-source data integrity, foreign-filer/ADR handling)
- **Headline result: 0 BUY (clean). Honest "nothing found."** 9 WATCH / 12 AVOID / 0 BUY.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw discovery (FTS + SIC reverse-recall floor, UNIONed) | ~193 | `universe_ipp_renewables_2026-06-21.csv` (37 KB, 193 names) |
| Small-cap candidates entering cheap_pass | 83 | after band + liquidity tagging |
| cheap_pass survivors | 42 | hard kill-flag scan (going-concern / death-spiral / material-weakness / concentration) |
| SIC gate (Gate 1) survivors | 42 | keep=35, review=7 → routed to LLM Gate 2 |
| **Deep-band (band="deep") survivors** | **19** | every one deep-dived (no sampling) |
| Unknown-band (mktcap unresolved) | 2 | TVC, NRUC, also deep-dived (band="unknown" → PROCESS per C3) |
| Watch-band (2.0B to 5.0B, surfaced only) | 21 | not deep-dived by design |
| Deep-dives completed | **21 / 21** | **0 ERROR files** |
| Valuations completed | 19 / 21 | TVC + NRUC error `yfinance_returned_null`, no tradeable common equity (correct abstain) |
| **Mechanical BUYs** | **0** | |
| **Clean BUYs (post-adversarial)** | **0** | |

Structured funnel: `raw=83` (small-cap entrants to cheap_pass), `deepdived=21`, `survivors=21`.

> Note: there is **no SIC reverse-recall floor** wired for `ipp-renewables` in `filter_by_sic.theme_sics`
> (only water/railcar/gaming/deathcare have floors). Recall here rests on FTS keyword recall + the
> coarse Gate-1 SIC keep/review split, see Data-Quality §6 for the implication.

### Deep-band + unknown-band roster (21), with Gate-2 theme-fit judgment

| Ticker | SIC | Mcap | Gate-2 theme fit | Rating |
|---|---|---:|---|---|
| SUUN SolarBank | 4931 | $68M | **pure_play**, solar + BESS independent power producer/developer | 观察 WATCH |
| HNRG Hallador Energy | 4911 | $917M | **pure_play**, coal miner vertically integrated into IPP electricity sales | 观察 WATCH |
| CSIQ Canadian Solar | 3674 | $1105M | partial, solar PV manufacturer + Recurrent Energy IPP arm | 观察 WATCH |
| NPWR Net Power | 3620 | $162M | partial, oxy-combustion clean-power generation tech + project dev (pre-rev) | 观察 WATCH |
| ARRY Array Technologies | 3990 | $1231M | partial/adjacent, solar tracker hardware (equipment, not generation) | 观察 WATCH |
| LTBR Lightbridge | 8742 | $323M | adjacent, next-gen nuclear *fuel* developer (not a power producer), pre-rev | 观察 WATCH |
| EDN Edenor | 4911 | $1325M | partial, Argentine electricity *distribution* utility (foreign 20-F) | 观察 WATCH |
| GNE Genie Energy | 4931 | $369M | partial, retail energy + small Genie Renewables solar arm | 观察 WATCH |
| STEM Stem Inc | 3690 | $74M | adjacent, AI energy-storage software (pivoted from battery resale) | 观察 WATCH |
| BATL Battalion Oil | 1311 | $26M | **misrecall**, oil & gas E&P (Delaware Basin) | 避开 AVOID |
| VTS Vitesse Energy | 1311 | $668M | **misrecall**, oil & gas E&P | 避开 AVOID |
| OBE Obsidian Energy | 1311 | $618M | **misrecall**, oil & gas E&P | 避开 AVOID |
| MAKO Mako Mining | 1040 | $710M | **misrecall**, gold mining | 避开 AVOID |
| SID National Steel (CSN) | 3310 | $1370M | **misrecall**, steelmaker (Brazil) | 避开 AVOID |
| TRC Tejon Ranch | 6500 | $499M | **misrecall**, diversified real estate developer | 避开 AVOID |
| FPI Farmland Partners | 6798 | $433M | **misrecall**, farmland REIT | 避开 AVOID |
| IGIC Intl General Insurance | 6399 | $1058M | **misrecall**, specialty insurer (financial) | 避开 AVOID |
| AGM Farmer Mac | 6111 | $1990M | **misrecall**, agricultural mortgage GSE (financial) | 避开 AVOID |
| VINP Vinci Compass | 6282 | $639M | **misrecall**, asset manager (financial) | 避开 AVOID |
| TVC Tennessee Valley Authority | 4911 | n/a | **misrecall (equity)**, federal corp / debt-only issuer, NO common stock | 避开 AVOID |
| NRUC Natl Rural Util Coop Finance | 6159 | n/a | **misrecall**, cooperative finance corp (financial), no public equity | 避开 AVOID |

Gate-2 verdict: 2 pure-plays (SUUN, HNRG), 7 partials/adjacent (CSIQ, NPWR, ARRY, LTBR, EDN, GNE, STEM),
12 misrecalls. The misrecall set is the expected single-keyword FTS over-recall: "independent power"
and "renewable energy generation" appear in the filings of oil & gas E&Ps (BATL/VTS/OBE, they discuss
"power" and "renewable" in risk factors), a steelmaker, a gold miner, two REITs, three financials, and
two non-equity utility-debt issuers. **Every one of the 12 misrecalls is neutralized by the v0.3.0
guards** (financial-SIC forced-unsuitable, fundamental_decline, extreme-MoS, cross_source, or the
no-equity abstain), none reaches a BUY.

---

## 2. Ranked shortlist (non-sunk = WATCH candidates)

1. **SUUN** SolarBank, pure-play solar/BESS IPP; buy_eligible=true; fcf_cap MoS **null** (intrinsic band unavailable; early-stage, OCF-proxy, no capex/debt detail)
2. **ARRY** Array Technologies, solar trackers (equipment); buy_eligible=true; fcf_cap MoS **−55.3%** (trades above intrinsic band)
3. **HNRG** Hallador Energy, coal→IPP; buy_eligible=**false** (cross_source_mismatch debt 4.8×); fcf_cap MoS −94%
4. **CSIQ** Canadian Solar, solar mfr + IPP; buy_eligible=**false** (extreme_mos + debt_truncation + cross_source); nav MoS +103% (data pathology)
5. **EDN** Edenor, Argentine electric *distribution*; buy_eligible=**false** (cross_source_mismatch shares 44× ADR-vs-ordinary)
6. **GNE** Genie Energy, retail + small solar; buy_eligible=**false** (financial_sic + insurance_concepts + cross_source); nav MoS −48.6%
7. **LTBR** Lightbridge, nuclear fuel dev (pre-rev); buy_eligible=true; nav MoS −46.1%
8. **NPWR** Net Power, oxy-combustion power tech (pre-rev); buy_eligible=**false** (cross_source_mismatch); negative FCF
9. **STEM** Stem, storage software; buy_eligible=true; nav MoS −100%

Sunk (避开): AGM, BATL, FPI, IGIC, MAKO, NRUC, OBE, SID, TRC, TVC, VINP, VTS.

---

## 3. BUY analysis, honest 0-BUY

**No candidate satisfies the BUY rule** (`mos_basis ∈ {fcf_cap, nav}` AND numeric MoS ≥ 30 AND
`buy_eligible == true` AND zero kill-flags). The full table, with exactly why each fails:

| Ticker | basis | numeric MoS | buy_eligible | kill-flags | Fails on |
|---|---|---:|---|---:|---|
| ARRY | fcf_cap | −55.3% | true | 0 | MoS far below +30 (trades above intrinsic) |
| LTBR | nav | −46.1% | true | 0 | MoS far below +30 (pre-rev fuel dev priced above book) |
| STEM | nav | −100.0% | true | 0 | MoS far below +30 (negative tangible equity) |
| SUUN | fcf_cap | **null** | true | 0 | no numeric MoS, intrinsic band unavailable (early-stage data gap) |
| MAKO | fcf_cap | **null** | true | 0 | no numeric MoS, intrinsic band unavailable |
| OBE | fcf_cap | **null** | true | 0 | no numeric MoS, intrinsic band unavailable |
| VINP | fcf_cap | **null** | true | 0 | no numeric MoS, foreign-filer XBRL gap |
| BATL | fcf_cap | +986.2% | **false** | 0 | extreme_mos (data pathology) + fcf_sustainability, vetoed |
| SID | fcf_cap | +377.9% | **false** | 0 | extreme_mos (data pathology), vetoed |
| CSIQ | nav | +103.3% | **false** | 0 | extreme_mos + debt_truncation + cross_source, vetoed |
| HNRG | fcf_cap | −94.0% | **false** | 0 | cross_source_mismatch (debt 4.8×); MoS<30 anyway |
| EDN | fcf_cap | null | **false** | 0 | cross_source_mismatch (shares 44×) |
| NPWR | fcf_cap | null | **false** | 0 | cross_source_mismatch; negative FCF |
| GNE | nav | −48.6% | **false** | 0 | financial_sic + insurance_concepts + cross_source |
| AGM/FPI/IGIC | nav | −31% / −100% / −46% | **false** | 0 | financial_sic_forced_unsuitable |
| TRC | nav | −23.9% | **false** | 0 | fundamental_decline_flag |
| VTS | fcf_cap | +10.4% | **false** | 0 | fcf_sustainability_uncertain; MoS<30 anyway |
| TVC / NRUC | abstain | n/a | n/a |, | no tradeable common equity (un-valuable) |

**Two failure clusters, both economically correct:**

1. **The buy_eligible names all fail on MoS.** Three (ARRY, LTBR, STEM) have deeply negative MoS, they
   trade *above* their intrinsic band. Four (SUUN, MAKO, OBE, VINP) have *null* MoS because the fcf_cap
   intrinsic band cannot be built (early-stage / OCF-proxy with no capex+debt detail, or foreign-filer
   XBRL gaps). Honest null beats a fabricated number.

2. **Every positive-MoS name is buy_eligible=false**, and adversarially, each is a *data artifact*, not
   a real opportunity (see §5). The extreme-MoS guard (|MoS|>100%) caught BATL (+986%), SID (+378%), and
   CSIQ (+103%); the cross-source-mismatch gate caught HNRG/EDN/NPWR/GNE.

This is the correct economic answer for the small-cap IPP/renewables universe: **the genuine
power-generation pure-plays at this cap range are either early-stage developers with negative or
un-modelable FCF (SUUN, NPWR), foreign-filer/ADR names whose SEC XBRL collides with yfinance
(EDN, CSIQ), or equipment/fuel adjacencies (ARRY, LTBR) trading above intrinsic.** No clean,
profitable, fairly-cheap small-cap IPP exists in this cohort today.

---

## 4. Code-paths exercised (v0.3.0 mechanisms that fired)

| Code-path | Fired on | Behaved correctly? |
|---|---|---|
| **SIC keep/review split → Gate-1** | 35 keep / 7 review | Yes, routed 7 ambiguous (incl. REIT/financial SICs) to LLM Gate-2 |
| **Asset-heavy NAV routing** (`fcf_cap_model_unsuitable`) | AGM, CSIQ, FPI, GNE, IGIC, LTBR, STEM, TRC | Yes, capital/asset-heavy + financials routed to NAV basis |
| **OCF-proxy FCF + fcf_sustainability_uncertain** | VTS, BATL (and proxy on SUUN) | Yes, capex-unavailable → OCF proxy flagged, BUY blocked |
| **extreme_mos_review_required (G1, \|MoS\|>100%)** | BATL (+986%), SID (+378%), CSIQ (+103%) | Yes, the headline guard; all three vetoed |
| **cross_source_mismatch (P7, >2.5× SEC-vs-yfinance)** | HNRG, EDN, CSIQ, NPWR, GNE | Yes, fired heavily on foreign filers/ADRs (see §6) |
| **debt_truncation_suspected (C1)** | CSIQ | Yes |
| **financial_sic_forced_unsuitable (A3)** | AGM, FPI, GNE, IGIC | Yes, ag-mortgage GSE, farmland REIT, insurer, retail-energy holdco |
| **insurance_concepts_present (A3)** | GNE, IGIC | Yes, IGIC is an insurer; GNE carries insurance concepts |
| **fundamental_decline_flag (P6)** | TRC | Yes |
| **abstain on no-equity issuer** (yfinance null, no override possible) | TVC, NRUC | Yes, federal corp + coop finance corp, no common stock; honestly un-valuable |
| **band="unknown" → PROCESS (C3)** | TVC, NRUC | Yes, not silently dropped; deep-dived as the spec requires |
| **mktcap fallback (SEC shares×price)** | broad universe | Yes, universe priced; only 2 truly-null (no-equity) names |
| **signals firewall (P16/P17 diagnostic)** | all 21 reports | Yes, emitted in T2 section; `buy_eligible` byte-independent of it |

**Not exercised / not applicable here:** SIC reverse-recall floor (none wired for this slug), recall@gold
(no gold list), low_revenue_loss_ratio_extreme (NPWR/LTBR are pre-rev loss-makers but did not trip the
>20× extreme tier), peak_contamination_flag (no trough→peak→rollover name surfaced).

---

## 5. Adversarial verification

There are **0 mechanical BUYs**, so there is nothing to promote. The adversarial question instead is the
inverse: *did a guard suppress a real opportunity?* Checked the three positive-MoS vetoes and the
buy_eligible-true names:

- **BATL +986% MoS**, Battalion is an O&G E&P with a **−15% FCF yield** (negative normalized FCF). The
  cap-rate model divides a tiny/negative FCF base, manufacturing an absurd intrinsic. **Artifact, not
  opportunity.** Guard correct.
- **SID +378% MoS**, CSN/National Steel, a Brazilian steelmaker, **−65% FCF yield**. Same pathology.
  Also a theme misrecall. **Artifact.** Guard correct.
- **CSIQ +103% nav MoS**, debt_truncation flagged (SEC debt $179M vs yfinance $7.08B, a 39.6× gap):
  the SEC XBRL pulled a partial/parent-only debt figure, collapsing EV and inflating NAV MoS.
  **Artifact** driven by a foreign-filer (20-F) consolidation-scope mismatch. Guard correct.
- **ARRY −55% / LTBR −46% / STEM −100%** (buy_eligible=true), all genuinely trade above intrinsic; the
  negative MoS is real, not a guard suppressing cheapness. No opportunity masked.
- **SUUN / MAKO / OBE / VINP** (null MoS), un-modelable, not suppressed-cheap. SUUN is the one genuine
  pure-play worth human follow-up *if* it reaches positive, modelable FCF, but today there is no number
  to underwrite.

**Adversarial verdict: the 0-BUY is correct.** No real opportunity was suppressed by a guard; every
positive-MoS name was a verifiable data/model artifact.

---

## 6. Data-quality issues found (→ v0.3.1 backlog candidates)

1. **Foreign-filer / ADR cross-source collisions are the dominant data risk for this theme.** 5 of 19
   valued names tripped `cross_source_mismatch`, almost all foreign filers or ADRs:
   - **EDN** shares_outstanding SEC 906.5M (ordinary) vs yfinance 20.6M (ADR) = **44×**, ADR-ratio, not
     an error, but the guard correctly blocks until reconciled.
   - **CSIQ** total_debt SEC $179M vs yfinance $7.08B = **39.6×**, 20-F XBRL scope (parent-only) vs full
     consolidation. Also tripped debt_truncation.
   - **HNRG** total_debt SEC $29.7M vs yfinance $6.2M = 4.8×; **NPWR** debt 7.0×; **GNE** revenue 4.2×.
   - *Backlog idea:* an ADR-ratio normalizer (detect ADR vs ordinary share-count discrepancy and divide
     out the ratio) would convert several false cross-source blocks into clean comparisons. Until then,
     the guard is doing its job (blocking BUY on unreconciled data), but it depresses theme recall for
     foreign IPPs.

2. **Early-stage / pre-revenue developers yield null fcf_cap intrinsic bands** (SUUN, MAKO, OBE, VINP).
   This is honest (no capex+debt detail → no band), but it means the genuine *development-stage* IPP
   pure-play (SUUN) is structurally un-rateable by the current valuation paths. A NAV-on-project-pipeline
   path would be the right tool for project-finance developers, *backlog candidate* (capital-intensive
   code-path focus is under-served for pre-FCF developers).

3. **No-equity utility-debt issuers swept in by FTS** (TVC = Tennessee Valley Authority, NRUC = coop
   finance corp). These are 4911/6159 SIC but have *no tradeable common stock*. They are correctly
   abstained (yfinance_returned_null with no valid mktcap override), but they consumed two deep-dive
   slots. *Backlog idea:* a "no public equity" pre-filter (security-type check) at discovery would drop
   debt-only filers before deep-dive.

4. **No SIC reverse-recall floor for ipp-renewables.** Power generation spans 4911/4931/4900 plus solar
   manufacturers (3674), and there is no dedicated SIC the way water (4941) has. Recall therefore rests
   on FTS + Gate-1; a true low-keyword-density small-cap IPP could be missed. Without a gold list this is
   unmeasured. *Backlog idea:* consider a 4911/4931 floor (accepting it will pull in distributors/retail
   like EDN/GNE that Gate-2 then demotes).

5. Minor: edgartools `_tcache` WinError 5 (access denied clearing stale cache) logged repeatedly, cosmetic,
   did not affect output.

---

## 7. recall@gold

**n/a**, `ipp-renewables` has no `recall@gold` gold list (only water-utilities, railcar-leasing,
regional-gaming, deathcare are wired into `THEME_GOLD`). `track_forward.py --recall-gold` was therefore
not run for this theme.

---

## 8. Market-intel / T2 analyst context (labeled, never drives buy_eligible)

> Firewalled context only. None of the below touched discovery, valuation, `buy_eligible`, or any rating.

- **TrendsMCP:** quota exhausted at run time (5/5 daily, 100/100 monthly), no fresh search/news-volume
  pull available. Recorded as unavailable rather than fabricated.
- **Qualitative macro (analyst knowledge, T2, non-load-bearing):** the IPP/renewables small-cap cohort
  through 2025 to 26 has been a *capital-cost-rate story*, utility-scale solar/storage economics are
  rate-sensitive (higher-for-longer rates compress project IRRs and developer NAVs), and module/equipment
  names (ARRY, CSIQ) carry tariff/oversupply overhangs. This is *consistent with* (but did not cause) the
  mechanical result: the equipment names trade above intrinsic, the developers run negative/early FCF, and
  the one Argentine utility (EDN) is a macro/FX story orthogonal to the US small-cap thesis. The signals
  T2 section in each report (e.g. SUUN price_return_12m −53.8%, divergence_label `unclear`) is snapshotted
  for future per-signal calibration only.

---

## 9. Skeptical-PM usable verdict

**Usable: YES, as a landmine-scanner, exactly as designed.** A skeptical PM gets a decision-ready answer:
*the small-cap IPP/renewables universe contains no clean, cheap, profitable pure-play right now.* The tool
correctly: (a) enumerated a broad universe and surfaced the 2 genuine pure-plays (SUUN, HNRG) plus 7
adjacencies; (b) eliminated 12 misrecalls (O&G, steel, gold, REITs, financials, no-equity issuers) via
named guards; (c) refused to manufacture a BUY from three eye-catching positive-MoS names that are all
verifiable data artifacts; (d) reported null MoS honestly rather than fabricating one for early-stage
developers. The single follow-up a PM might queue is **SUUN**, the only true development-stage solar/BESS
IPP, but only *if/when* it reaches modelable positive FCF; today there is no number to underwrite, and the
tool says so. The main yield is the **foreign-filer/ADR cross-source data-quality cluster** (item §6.1),
which is a real v0.3.1 backlog item, not a false BUY.
