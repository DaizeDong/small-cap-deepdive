# Coverage Test — Theme: spac-derived-micro

- **Run batch:** `2026-06-21_cov-spac-derived-micro`
- **Skill version:** v0.3.0 (commit `f12fef5`, dirty=true per `_run.json`)
- **Theme keywords:** `de-SPAC, special purpose acquisition company`  | **Sector:** Cross
- **Cap band:** micro (`--micro`, $500M ceiling; watch band to $5.0B)
- **Code-path focus:** cross-source / wrong-entity / data-quality
- **Date:** 2026-06-21
- **Independent verdict (skeptical PM):** **USABLE. Clean 0-BUY.** This is arguably the single best
  stress of the v0.3.0 data-integrity guards in the whole coverage test. The de-SPAC cohort is, by
  construction, the dirtiest-financials corner of the small-cap universe (fresh shell→operating-co
  transitions, foreign private issuers, restated/proxy numbers, stale yfinance), and every targeted
  guard fired: `cross_source_mismatch` on 4 of 5, `debt_truncation` on 2, `low_revenue_loss_ratio_extreme`
  on 1, an LLM theme-fit **misrecall** correctly identified (MVIS), and a buy_eligible-True-but-unvaluable
  pre-revenue de-SPAC (NUCL) correctly stopped by the numeric-MoS requirement. Zero false BUYs.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Discover (FTS + mktcap fallback) raw universe | 563 rows | de-SPAC: 281, SPAC: 401, deduped 563 |
| Band breakdown | 128 deep / 8 watch / 3 large / 424 unknown | discover bands |
| `flag_spac` (pre-merger blank-check shells excluded) | 291 | the load-bearing exclusion (see below) |
| Cheap-pass-eligible (priced, non-SPAC, liquid) | 40 | 33 deep + 7 watch/large |
| Cheap-pass survivors | 8 | 32 rejected (kill-flag ≥2 / cash-burn) |
| SIC gate (tri-state) | 8 | keep=7, review=1 → LLM |
| Candidates JSON | **5 deep + 3 watch** | deep band is the deep-dive-eligible cohort |
| LLM theme-fit gate (Gate 2) | 4 true de-SPAC + 1 misrecall | MVIS = misrecall (kept in deep-dive, flagged) |
| Deep-dived (EVERY deep-band survivor) | **5** | SLGB, YOUL, SDA, MVIS, NUCL |
| Valuated (`--json` + `--ticker`) | 5 | all 5 |
| **Mechanical BUYs** | **0** | |
| **BUYs surviving adversarial check** | **0** | |

Watch-band names (DFIN, GFR, BBOT) are surfaced theme-fit-only and not deep-dived, per band rules.

### The load-bearing exclusion: `flag_spac`

For *this* theme the precision work happens at discovery, not at Gate 2. Raw FTS for "special
purpose acquisition company" returns the entire **pre-merger** SPAC shell population — 291 of 563
rows are blank-check shells ("X Acquisition Corp", "Churchill Capital Corp IX", "Live Oak Acquisition
Corp. V", etc.). The theme is **de-SPAC = post-merger operating companies**, not the shells. The
discover-stage `flag_spac` correctly strips all 291, leaving the operating-company cohort. Without
this, the deep band would be ~90% empty shells with $0 revenue and no business to valuate. This is
the SPAC-theme analogue of the "refractory → oncology" Gate-2 failure, caught one stage earlier.

---

## 2. Ranked shortlist (all AVOID — see RANKING.md)

| # | Ticker | Name | Theme-fit | Mktcap | Rating | Why not BUY (mechanical) |
|---|---|---|---|---|---|---|
| 1 | MVIS | MicroVision | **MISRECALL** | $126M | 避开 | NOT a de-SPAC (1993, traditional listing); + `low_revenue_loss_ratio_extreme` (78.6x) + `debt_truncation` + `cross_source_mismatch`; NAV MoS -85.9% |
| 2 | SDA | SunCar Technology | pure_play | $78M | 避开 | `debt_truncation_suspected` (1.4M vs implied 132.6M) + `cross_source_mismatch` (60.5x); NAV MoS -66.6% |
| 3 | SLGB | Smart Logistics Global | partial | $31M | 避开 | `cross_source_mismatch` (rev 7.0x, debt 4.0x); FCF MoS null (neg normalized FCF) |
| 4 | YOUL | Youlife Group | pure_play | $38M | 避开 | `cross_source_mismatch` (rev 7.0x); FCF MoS -7.2% (<30) |
| 5 | NUCL | Eagle Nuclear Energy | pure_play | $333M | 避开 | `buy_eligible=True` BUT MoS **null** (pre-revenue, normalized FCF -$5M, no intrinsic band) → fails numeric MoS≥30 |

No name reached WATCH or BUY. Confidence ordering reflects strength of the disqualifying evidence,
not attractiveness.

---

## 3. BUY analysis — honest 0-BUY

**There are zero mechanical BUYs.** The BUY rule requires `mos_basis ∈ {fcf_cap, nav}` AND numeric
`MoS ≥ 30` AND `buy_eligible == true` AND zero kill-flags AND no T3 thesis. The five survivors split
into three correct failure modes:

**Mode A — blocked by a v0.3.0 data-integrity guard (`buy_eligible == false`), 4 of 5:**

- **MVIS** — three independent guards fire: `low_revenue_loss_ratio_extreme` (latest NI −$95.0M vs
  revenue $1.2M → |NI|/rev = 78.6x, EXTREME >20x tier), `debt_truncation_suspected` (reported
  total_debt $1.6M vs implied $31.1M), and `cross_source_mismatch` (SEC total_debt $1.6M vs yfinance
  $53.4M, 33.9x). The data layer even self-flagged a likely XBRL unit mis-tag on net income. NAV MoS
  −85.9%. **Also a theme misrecall** (see §5).
- **SDA** (SunCar) — `debt_truncation_suspected` (reported $1.4M vs implied liab−equity $132.6M,
  ratio 0.01) + `cross_source_mismatch` (debt SEC $1.4M vs yf $85.5M = 60.5x — the largest
  disagreement in the cohort). FCF-cap routed to NAV (C1 data-quality block); NAV MoS −66.6%.
- **SLGB** (Smart Logistics) — `cross_source_mismatch` on two fields at once: revenue SEC $89.9M vs
  yf $628.5M (7.0x) and total_debt $8.7M vs $35.0M (4.0x). Normalized FCF negative → FCF intrinsic
  band null → no tradeable MoS. A corrupted single source cannot back a MoS.
- **YOUL** (Youlife) — `cross_source_mismatch` revenue SEC $265.2M vs yf $1,854.3M (7.0x). Even
  taking the SEC number at face value, FCF MoS is −7.2% (< 30). Two reasons to reject.

**Mode B — passes every guard but is unvaluable (`buy_eligible == true`, MoS null), 1 of 5:**

- **NUCL** (Eagle Nuclear Energy) — the most instructive case. `buy_eligible == true` (no guard
  trips: no cross-source second source available, no debt truncation, non-financial SIC). **But the
  BUY rule's numeric-MoS≥30 leg stops it:** normalized FCF is −$5M, so there is no FCF intrinsic
  band and `margin_of_safety_pct = null` (`intrinsic_band_unavailable`). A null MoS is not ≥30, so
  no BUY. This is exactly the guard-vs-rule division of labor working as designed — `buy_eligible`
  is necessary but not sufficient; the rule's MoS gate catches the pre-revenue de-SPAC that the
  boolean guards have no basis to block.

**Adversarial check:** Not required — there are zero mechanical BUYs to falsify. The closest call,
NUCL, was examined adversarially anyway: it is a uranium-resource + SMR **development-stage** company
that closed its SPAC merger (Spring Valley Acquisition Corp. II) on 2026-02-24, ~$0 revenue, burning
cash. Treating it as a "buy" would be a pure narrative bet on uranium/SMR with no fundamentals to
anchor a margin of safety — precisely the artifact the tool is built to refuse. **n_buy_clean = 0.**

---

## 4. Code-paths exercised (the point of this theme)

| Code-path | Fired on | Verdict |
|---|---|---|
| `cross_source_mismatch` (>2.5x SEC vs yfinance, gates buy_eligible) | SLGB, YOUL, SDA, MVIS (4/5) | ✅ Core target — fired hard; de-SPAC stale-yfinance is the canonical trigger |
| `debt_truncation_suspected` (reported debt ≪ implied liab−equity) | SDA, MVIS | ✅ Fired; correctly routes FCF→NAV / forces abstain |
| `low_revenue_loss_ratio_extreme` (|NI|/rev >20x, gates buy_eligible) | MVIS | ✅ Fired at 78.6x |
| LLM theme-fit **misrecall** (wrong-entity at the semantic level) | MVIS | ✅ Caught — non-SPAC swept in by SPAC-competitor text |
| `flag_spac` pre-merger-shell exclusion (discovery) | 291 shells | ✅ Load-bearing precision; kept funnel on operating cos |
| `buy_eligible=True` ∧ MoS null → no BUY (numeric-MoS rule leg) | NUCL | ✅ Rule correctly overrides a clean boolean |
| NAV-path routing for FCF-unsuitable | SDA, MVIS | ✅ Routed; negative NAV MoS |
| Signals firewall (diagnostic side-channel never touches buy_eligible) | all 5 | ✅ `signals` namespace emitted in deepdive JSONs; grep-verified zero refs in valuation.py |

The "wrong-entity" focus manifested two ways here: the hard `debt_truncation`/`cross_source` entity-
mismatch guards (the deepdive pulled mismatched parent/sub or shell/operating-co numbers, exactly the
de-SPAC failure mode), AND the semantic wrong-entity (MVIS misrecall). Both were caught.

---

## 5. Theme-fit / misrecall detail

- **SDA (SunCar)** — textbook de-SPAC: 10-K/20-F states "incorporated… solely for the purpose of
  effectuating the Business Combination, which was consummated on May 17, 2023." pure_play.
- **YOUL (Youlife)** — FPI (20-F) education group, de-SPAC operating company. pure_play.
- **SLGB (Smart Logistics)** — Cayman FPI logistics; de-SPAC structure. partial/pure (blurb was a
  TOC fragment, but corporate form and the entity-mismatch guards confirm a real operating de-SPAC).
- **NUCL (Eagle Nuclear)** — de-SPAC closed 2026-02 (Spring Valley Acq. Corp. II); uranium/SMR
  development stage. pure_play, but pre-revenue.
- **MVIS (MicroVision)** — **MISRECALL.** Founded 1993, NASDAQ since the late 1990s; never a SPAC.
  FTS matched SPAC references in its filings (it discusses SPAC-funded lidar competitors such as
  Luminar, whose assets it later bought out of bankruptcy). Correctly excluded on theme membership —
  and, redundantly, blocked by three mechanical guards regardless.

This 4-true / 1-misrecall split (80% Gate-2 precision) is much higher than hot single-keyword themes
(~7%), because `flag_spac` already removed the dominant noise class (shells) at discovery.

---

## 6. Data-quality issues observed

- **yfinance is systematically wrong for fresh de-SPACs / FPIs.** Every cross_source_mismatch was a
  yfinance revenue/debt figure inflated ~4–60x vs SEC — yfinance appears to carry pre-merger shell
  trust figures, ADR-level aggregates, or stale data for these names. The >2.5x guard is doing real
  work; without it, three of these would have produced spurious "cheap" multiples.
- **Debt truncation** on SDA and MVIS: XBRL `total_debt` tag captured a tiny line item while
  liabilities−equity implied 50–95x more — the guard correctly distrusts the single tag.
- **MVIS net-income unit mis-tag** self-flagged by the data layer (NI −$95M vs revenue $1.2M
  implausible); valuation correctly fell back to OCF.
- **NUCL** is information-poor by nature (just-closed merger): cash unavailable, D&A/capex
  unavailable, FCF = OCF proxy, no second source for cross-check. The tool routes it to "unvaluable"
  rather than inventing a number — correct.
- Encoding: tool stdout is GBK-mojibake under this Windows shell (cosmetic); JSON artifacts are
  valid UTF-8.

---

## 7. recall@gold

**n/a** — `spac-derived-micro` has no hand-built gold list in `THEME_GOLD` (only deathcare,
water-utilities, railcar-leasing, regional-gaming do). `track_forward.py --recall-gold` returns
"no gold list for theme 'spac-derived-micro' → not measurable", as expected. De-SPAC is a structural
cohort, not a fixed-membership industry, so a static gold list is not meaningful here.

---

## 8. Market-intel / TrendsMCP context (T2 — never drives buy_eligible)

TrendsMCP daily+monthly quota was exhausted at run time, so no fresh search-trend series was
retrievable. This is immaterial to the verdict: the BUY decision is anchored entirely to T1
SEC-filing valuation + mechanical guards, and T2/T3 evidence is firewalled from `buy_eligible` by
construction. General context (analyst priors, not a data pull): the 2020–21 de-SPAC class has a
well-documented poor base rate — a large majority traded materially below $10 within 24 months of
merger, with heavy dilution and going-concern attrition. That prior is consistent with this run's
outcome (negative MoS / unvaluable / data-corrupt across the board) and reinforces the 0-BUY.

---

## 9. Skeptical-PM bottom line

USABLE, and a high-signal coverage test. The scanner enumerated the de-SPAC operating universe,
stripped 291 empty shells at the right stage, deep-dived all five deep-band survivors, and produced
a disciplined, honest 0-BUY in the dirtiest financial-data cohort in the market — with every
targeted data-integrity guard (`cross_source_mismatch`, `debt_truncation`, `low_revenue_loss_extreme`),
the semantic misrecall catch (MVIS), and the buy_eligible-vs-numeric-MoS rule division (NUCL) all
firing correctly and independently. No false BUYs. This is the "nothing found is a feature" outcome,
and here it is also the correct one.
