# Coverage Test, Cannabis (slug=`cannabis`, sector=Cross)

- **Skill version:** v0.3.0 @ commit `f12fef5` (run manifest records `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-cannabis/`
- **Keywords:** `cannabis,marijuana,hemp`
- **Code-path focus:** regulatory limbo / going-concern / dilution
- **Date:** 2026-06-21 (run executed under `SMALLCAP_RUN=2026-06-21_cov-cannabis`)
- **Headline:** **0 BUY** (0 mechanical, 0 adversarially-survived). 13 观察 (watch), 6 避开 (avoid). Usable to a skeptical PM: **YES**, as a landmine scanner the run did exactly its job (eliminated every concept-player and every data-artifact "cheap" name before any capital decision).

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery (EDGAR FTS + SIC, small-cap ≤$2.0B) | 132 | cheap_pass universe (small-cap candidates) |
| Watch-band (≤$5.0B, theme-fit only, no deep-dive) | 13 | e.g. CURLF $2.76B, PAYO, BUSE, over the small-cap cap |
| cheap_pass survivors (after hard kill-flags) | 72 | written to `candidates_cannabis.json` |
| SIC gate | 72 → keep 33 / review 39 | review routed to LLM theme-fit |
| **Deep band (band=`deep`)** | **59** | the population finalize_run requires reports/resolution for |
| LLM theme-fit survivors (pure_play + partial) | **19** | deep-dived 1-for-1 (no sampling) |
| LLM theme-fit misrecalls (resolved via `gate2_results.json`) | 40 | NOT deep-dived; recorded as resolved-by-gating |
| Deepdive_data completed | 19 / 19 | **0 ERROR files**, 0 silent skips |
| Valuation completed (`--json` + `--ticker`) | 19 / 19 | all exit 0 |
| **Mechanical BUYs** | **0** | no candidate reached MoS≥30 with buy_eligible |
| **Adversarially-survived BUYs (n_buy_clean)** | **0** | n/a, no mechanical BUY to verify |

Funnel object: `{ raw: 132, deepdived: 19, survivors: 19 }` (survivors = deep-band theme-fit members that received a full deep-dive; all 19 then carried through valuation + verdict).

### LLM theme-fit (Gate 2), how the 40 misrecalls were judged

The deep band was dominated by SIC-collision noise. The single biggest false-recall cluster was **community/regional banks** (SIC 60xx): BWFG, QCRH, TCBK, BCBP, TSBK, PKBK, BSRR, FISI, NBBK, TRST, HBT, HNVR, PNBK, 13 banks recalled because "cannabis banking" / "cannabis-related risk factors" appear in their 10-Ks. None operate in cannabis; all dropped. Other misrecall clusters: biopharma (SRPT, KMDA, CRDL, BTMD), REITs (OZ, ALX), and one-off keyword hits (SAM beer, NGVC grocer, GAIA streaming, POWW ammunition, EU uranium, ARRY solar, etc.). Full per-ticker rationale persisted in `gate2_results.json`.

`finalize_run` reconciled cleanly: **deep-band 59, reports 19, gate2-misrecall (resolved) 40, missing 0.**

---

## 2. Theme-fit survivors (the 19 deep-dived)

**Pure-play cannabis operators (13):** GRUSF (Grown Rogue), TSNDF (TerrAscend), CRON (Cronos), GTBIF (Green Thumb), TCNNF (Trulieve), CWBHF (Charlotte's Web, hemp/CBD), CRLBF (Cresco Labs), TLRY (Tilray), ACB (Aurora), HITI (High Tide), SNDL (SNDL), OGI (Organigram), VFF (Village Farms).

**Ancillary / picks-and-shovels (partial, 6):** GRWG (GrowGeneration, hydroponics retail), IPW (iPower, grow supplies e-comm), ISPR (Ispire, cannabis+nicotine vape hardware), REFI (Chicago Atlantic, cannabis mortgage REIT), NLCP (NewLake, cannabis-dedicated REIT), TPB (Turning Point Brands, Zig-Zag rolling papers + tobacco).

**Deliberately excluded as theme-fit misrecall (borderline):** RVYL/RYVYL, payments/fintech processor (ex-GreenBox POS) that *serves* high-risk merchants including cannabis but is not itself a cannabis business; classified misrecall.

---

## 3. Ranked shortlist (from RANKING.md)

Top non-sunk (观察) names, by rank:

| # | Ticker | Rating | Rev | NI | OCF | Growth | Dilution | Insider | KF | Theme-fit |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ACB | 观察 | $0M* | $0M* | $0M* |, | +3% | neutral | 0 | pure |
| 2 | CRON | 观察 | $147M | -$3M | $26M | +25% | -1% | neutral | 0 | pure |
| 3 | GRUSF | 观察 | $32M | $3M | $4M | +22% | +0% | neutral | 0 | pure |
| 4 | GRWG | 观察 | $162M | -$24M | -$9M | -14% | +0% | net_buy | 1 | partial |
| 5 | GTBIF | 观察 | $311M*| $83M | $295M | +7% | +0% | neutral | 0 | pure |
| 6 | HITI | 观察 | $0M* | $0M* | $0M* |, | +8% | neutral | 0 | pure |
| 7 | NLCP | 观察 | $50M | $26M | $42M | +1% | +0% | net_sell | 0 | partial |
| 8 | OGI | 观察 | $0M* | $0M* | $0M* |, | -64% | neutral | 1 | pure |
| 9 | REFI | 观察 | $49M | $36M | $29M | +341%| +1% | net_buy | 0 | partial |
| 10| SNDL | 观察 | $0M* | $0M* | $0M* |, | +0% | neutral | 0 | pure |
| 11| TLRY | 观察 | $821M | -$2,187M | -$95M | +4% | +0% | net_buy | 0 | pure |
| 12| TSNDF| 观察 | $261M | -$81M | $22M | -3% | +0% | net_sell | 0 | pure |
| 13| VFF | 观察 | $216M | $32M | $10M | +10% | +0% | net_buy | 1 | pure |

Sunk (避开): CRLBF, CWBHF, IPW, ISPR, TCNNF, TPB.
`*` = data-artifact / extraction gap, see §6.

---

## 4. BUYs

**There are zero BUYs.** This is an honest 0-BUY outcome, not a tooling failure. The decisive mechanics:

The BUY rule = `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30%` AND `buy_eligible == true` AND zero kill-flags. Applied to all 19:

- **No survivor reached MoS ≥ 30%.** Of the 19, only one (IPW, +1054% NAV-MoS) was even *above* 30, and it is a transparent data artifact (a $1.7M-mktcap shell whose NAV/market-cap ratio is meaningless), correctly blocked by the `extreme_mos_review_required` guard (buy_eligible=False).
- Every numeric MoS that *was* computed was **negative or trivially small**: CRLBF -78%, CWBHF -100%, TPB -80%, TCNNF -86%, GRWG -26%, REFI -0.5%, NLCP -5%, TLRY +9%, GTBIF +12%. None ≥30%.
- The pure-play Canadian operators (ACB, HITI, SNDL, OGI) returned **MoS = null** (`intrinsic_band_unavailable`) because their financials never populated (20-F/40-F filers, see §6). Null MoS → cannot satisfy the rule. The model correctly **abstained** rather than fabricate a BUY on missing data.

So: **0 mechanical BUYs → 0 to adversarially verify → n_buy_clean = 0.**

### Why this is the *right* answer (skeptical-PM lens)

Cannabis in mid-2026 is the textbook "热点主题 = 赌场" case the skill's world-view warns about (PHILOSOPHY commitment #2): a branded-ETF theme riding a binary regulatory catalyst (DEA Schedule III hearing opens June 29, 2026). The genuine industrial winners are either (a) above the small-cap cap, (b) bleeding cash with negative intrinsic value at current prices, or (c) foreign filers whose financials don't extract cleanly. A disciplined value screen producing zero BUYs here is the system working, not failing.

---

## 5. Which code-paths fired (the test's focus: regulatory limbo / going-concern / dilution)

**Going-concern path (soft-flag handling), FIRED, and this is the most interesting observation.**
The cheap_pass keyword scanner detected `kf_going_concern=1` on **ISPR, NLCP, TLRY, VFF** and `kf_material_weakness=1` on **IPW, GRWG, ISPR, CRLBF, VFF, OGI, TPB**, yet `reject_going_concern=False` / `reject_killflags=False` for all of them, so they were *not* hard-killed and reached deep band. This is the going-concern code-path doing the nuanced thing: the phrase "...substantial doubt about our ability to continue as a going concern" appears as a *forward-looking risk factor* in these filings (boilerplate for sub-scale cannabis names), not as an actual auditor going-concern opinion, so the scanner flags-but-does-not-reject. The deep-dive then carries `killflag_count` forward (visible in RANKING). **Net effect on BUY: none**, they all failed on MoS anyway, but the path is exercised and behaves correctly.

**Dilution path, FIRED.** OGI shows -64% share-count change (heavy dilution), IPW +198% (extreme), both surfaced in RANKING's dilution column. Dilution did not need to be the binding constraint because MoS already excluded everything.

**Cross-source-mismatch guard (debt/dilution-structure firewall), FIRED on 8 names.** This is the dilution/balance-sheet-complexity guard and it was the single most-active buy_eligible blocker:
- GTBIF: revenue SEC=$311.1M vs yfinance=$1,195.9M (**3.8x**, SEC XBRL pulled a partial/segment figure; true rev ≈$1.1B). buy_eligible→False. **This guard prevented a materially wrong valuation.**
- TCNNF: total_debt SEC=$1.9M vs yf=$629.8M (336x), TSNDF 26x, CRON 36.8x, ISPR 18.8x, TLRY 5.4x, NLCP 3.4x, REFI 2.7x, all dual-listed Canadian/OTC names whose US-GAAP XBRL debt tags don't reconcile with the consolidated balance sheet vendors report. Guard correctly distrusts the cheap-looking number.

**fundamental_decline_flag, FIRED on CRLBF** (revenue/margin deterioration) → buy_eligible False, sunk to 避开.

**financial_sic_forced_unsuitable, FIRED on REFI, NLCP** (mortgage/equity REITs in SIC 67xx), FCF-cap model forced unsuitable, fell back to NAV; combined with cross_source_mismatch, both buy-ineligible.

**extreme_mos_review_required, FIRED on IPW** (the +1054% NAV-MoS micro-shell), the single most important guard here, since IPW was the *only* name numerically above the MoS threshold. Without it, IPW would have been a spurious mechanical BUY. This is precisely the v0.2.0-era "every BUY was a data artifact" failure mode the guard was built to stop.

**Signals side-channel, emitted, firewalled.** Each deepdive carries a `signals` block (`price_divergence`, `ownership`, `signals_meta`) marked diagnostic-only; `buy_eligible` is computed solely from fundamental guards in `valuation.py` and never reads signals. Confirmed no signal influenced any verdict.

---

## 6. Data-quality issues

1. **Foreign-private-issuer financial-extraction gaps (material).** ACB (40-F), HITI (40-F), OGI (40-F), SNDL (20-F) returned **empty financial series** (revenue/NI/OCF all $0M in RANKING). These are real, sizeable Canadian cannabis LPs; the $0 figures are extraction failures, not genuine zeros. Correct downstream behavior: valuation produced MoS=null and abstained, but a PM reading RANKING must not mistake "$0M rev" for "no revenue." Flagged.
2. **Cross-source revenue/debt disagreements on 8 dual-listed names** (see §5). The GTBIF 3.8x revenue gap is the most consequential, it means the SEC-side intrinsic inputs for GTBIF are unreliable, and the guard rightly blocked a BUY that would otherwise have looked plausible.
3. **CRLBF and ACB blurbs were empty** at theme-fit time; membership judged from known company identity (both unambiguous cannabis MSOs/LPs). Low risk.
4. **RVYL blurb empty + SIC 8742 (consulting)**; resolved by known-identity judgment (payments fintech) → misrecall. Borderline; a stricter reading could retain it as cannabis-ancillary fintech.
5. `openinsider` header-row warning on insider scrape (fell back to hardcoded column indices), non-fatal, consistent across run.

---

## 7. recall@gold

**n/a.** Cannabis has no hand-curated gold list in `THEME_GOLD` (only deathcare, water-utilities, railcar-leasing, regional-gaming exist). `track_forward.py --recall-gold ... --theme cannabis` returned: *"no gold list for theme 'cannabis', not measurable."* Recorded as a no-op, as designed.

---

## 8. Market-intel / T2 analyst context (does NOT drive buy_eligible)

Labeled T2 context for narrative only. TrendsMCP was rate-exhausted (5/5 daily, 100/100 monthly); substituted with regulatory web research.

The cannabis theme sits in acute **regulatory limbo** as of June 2026, which is exactly why the code-path focus is apt:
- A DEA final order (effective **April 28, 2026**) moved *FDA-approved* and *state-licensed medical* marijuana from Schedule I to **Schedule III**, delivering **280E tax relief** to medical operators, a real fundamental tailwind for MSO cash flows.
- But it is **partial**: recreational marijuana and bulk/unlicensed product remain Schedule I. A broader DEA rescheduling hearing **opens June 29, 2026** (concludes by July 15), with active litigation (SAM, drug-testing interests) creating delay risk.
- **SAFER Banking has still not passed** (Senate Banking Committee 14-9, July 2025; no floor vote). Analysts are unanimous: rescheduling alone will **not** re-rate cannabis equities durably without banking reform + balance-sheet repair. "The true catalyst for investors in 2026 is not the headline of rescheduling but the fundamental transformation of balance sheets."

This T2 backdrop *corroborates* the mechanical 0-BUY: the sector's value is gated on a binary, litigated, partially-completed regulatory event, while the underlying small-cap balance sheets are (per this run) cash-burning with negative intrinsic value. A value screen should abstain here, and it did.

Sources: [DEA Marijuana Rescheduling](https://www.dea.gov/marijuana-rescheduling-regulatory-actions), [Federal Register 2026-08177](https://www.federalregister.gov/documents/2026/04/28/2026-08177/schedules-of-controlled-substances-rescheduling-of-marijuana), [Gibson Dunn, DEA downschedules to Schedule III](https://www.gibsondunn.com/dea-downschedules-state-medical-marijuana-to-schedule-iii-expedited-hearing-set-to-consider-broader-rescheduling/), [MJBizDaily, what cannabis investors can expect in 2026](https://mjbizdaily.com/news/what-cannabis-investors-should-watch-for-in-2026-after-marijuana-rescheduling/613802/), [Regulatory Oversight, partial rescheduling status](https://www.regulatoryoversight.com/2026/05/partial-marijuana-rescheduling-where-things-stand/).

---

## 9. Adversarial verdict

There were no mechanical BUYs, so the adversarial pass is vacuous-by-construction. The adversarially-relevant question instead is: **did the pipeline suppress a real opportunity, or correctly abstain?** Spot-checks:

- **GTBIF** (the largest, healthiest-looking pure-play: $83M NI, $295M OCF, +12% FCF-MoS, KF=0): would have been the most tempting BUY candidate. It was correctly held at 观察, not promoted, because (a) +12% MoS < 30% threshold, and (b) cross_source_mismatch on revenue (3.8x) makes its intrinsic inputs untrustworthy. Adversarial read: **correct abstention**, promoting GTBIF would have been a BUY on a value figure the system itself flagged as unreliable.
- **IPW** (only name above 30% MoS): adversarially, this is the canonical data-artifact trap, blocked by extreme_mos_review_required. **Correctly killed.**

Conclusion: **0 real opportunities suppressed; 0 data artifacts let through.**

---

## 10. Skeptical-PM usable verdict

**USABLE, YES.** The run delivered systematic coverage (132 raw → disciplined 19 deep-dives, 0 crashes, 0 silent skips), eliminated 40 keyword-collision misrecalls (13 of them banks) with persisted rationale, exercised all three focus code-paths (going-concern soft-flag, dilution, debt/cross-source firewall), and produced an honest 0-BUY with each rejection traceable to a specific guard. For a PM, the deliverable is the *elimination*, confirmation that there is no mispriced small-cap cannabis pure-play hiding in the SEC universe at current prices, and a clean watchlist (GTBIF, CRON, GRUSF, REFI, NLCP) to revisit if/when the June-29 DEA hearing + SAFER Banking change the fundamentals. The one caveat a PM must carry forward: the four Canadian LPs (ACB/HITI/SNDL/OGI) show $0 financials due to 20-F/40-F extraction gaps, they were abstained-on, not analyzed, and would need a manual pull before any decision.
