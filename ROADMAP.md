# Roadmap

Current: **v0.3.3**. Every released version has a shipped section below, newest first; anything not
yet released sits under "Planned" or "Next". Per-change detail lives in `CHANGELOG.md`, this file
carries only the shape of each release and what remains open.

## v0.3.4, Planned (not released)

- **Demote `cross_source_mismatch` and `debt_truncation_suspected` from `buy_eligible` blockers to
  advisory data-quality labels.** The v0.3.3 backtest measured both as anti-predictive: they fire on
  66% and 48% of the universe respectively, at blowup lifts of 0.86x and 0.67x, so they shrink
  eligibility on healthy names while carrying no downside signal. This is the one open item
  `CHANGELOG.md` defers to v0.3.4. Both are currently still ANDed into `buy_eligible`; changing that
  changes ratings, so it ships as its own version with a regression pass.

## v0.3.3, Out-of-sample backtest and the CORE-4 distress kill-flag (2026-06-24) ✓ SHIPPED

A 25-cell survivorship-safe point-in-time backtest (5 themes × 5 as-of dates 2020 to 2024, 12mo
horizon) tested the skill's claims on held-out data. Write-up:
`docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md`.

- **The honest negative ✓** No durable alpha. The Margin-of-Safety cheapness signal is a 2020 to 21
  post-COVID-recovery regime artifact: it vanishes on the 2023 to 24 holdout (permutation p=0.72)
  and on a drop-2020 re-test (p=0.35). The skill does not pick market-beaters and no longer implies
  it can.
- **CORE-4 PIT distress kill-flag ✓** (`_deepdive_flags.distress_core4`) `distress_score` = count of
  `neg_ocf`, `neg_margin`, `accum_deficit`, `low_altman` (Altman Z″ < 1.1); `distress_kill` at
  `score >= 3` counts in `killflag_count`, so a distressed name routes to AVOID in both the live
  rating and the backtest grader, regardless of cheapness. At that shipped cutoff: blowup precision
  35.4% vs 13.3% base (lift 2.65x) at recall 62%. At the separate per-year top-quintile cutoff: lift
  2.56x at recall 51%, ticker-cluster bootstrap 95% CI [1.73, 3.00], P(lift≤1)=0. Banks and insurers
  are out of scope.
- **Reproducible study artifacts ✓** under `docs/backtest-2026-06/`, adversarially reviewed by a
  second model, caveats honored in the write-up rather than dropped.

## v0.3.2, Coverage-test backlog cleanup (2026-06-20) ✓ SHIPPED

- **Lessor NAV routing ✓ (#8)** `lessor_asset_heavy` (leasing/rental SIC, lease-income concept, or a
  high PP&E / lease-fleet ratio with rental revenue) forces the NAV basis **even below the 0.62
  debt/assets threshold**, so GBX (0.41) and RAIL (0.35) are valued on lease-fleet NAV instead of
  trough-cycle FCF.
- **Concurrency isolation ✓ (#10)** the SIC-floor sidecar is run/slug-namespaced and kept out of the
  `candidates_*.json` glob; run-state is per-`SMALLCAP_RUN` / PID-unique. No cross-theme
  contamination when many agents run at once.
- **Foreign-filer IFRS cascade ✓ (#11)** the XBRL concept cascade covers `ifrs-full` as well as
  `us-gaap`, recovering some 20-F/40-F filers; when a foreign filer is still empty after the
  cascade, `foreign_filer_unvaluable` labels the abstain explicitly instead of leaving a silent null.
- **Docs ✓** Skill Repo Spec v1 structure, philosophy-first README order, 1:1 EN/CN sections,
  `.claude-plugin/plugin.json`, single-sourced version across plugin.json / README badges / ROADMAP
  / CHANGELOG.

## v0.3.1, Full-coverage-test remediation (2026-06-20) ✓ SHIPPED

Driven by the v0.3.0 full-coverage test (53 themes across all GICS sectors plus niche; report in
`docs/coverage-test-2026-06-20/`). The test confirmed 0 false BUYs leaked but found one critical
mechanical hole plus precision and recall bugs.

- **Degenerate-base hole ✓ (#1, CRITICAL)** `normalization_masks_current_loss` blocks
  `buy_eligible` when `normalized_fcf > 0` while current OCF/FCF is negative or
  `contamination_ratio < 0`. Closes the TUSK +55.1% phantom BUY that only the human adversarial
  layer had caught.
- **SEC debt truncation ✓ (#2, CRITICAL)** `total_debt` is summed across the standard debt concepts,
  falling back to implied (liabilities − equity) when the sum still under-reads the balance sheet.
- **Null-MoS guard ✓ (#9)** `buy_eligible` can no longer be True with a null MoS; the absence emits
  `not_assessable_no_intrinsic_band`.
- **Precision and recall ✓** ASC842 lease adjustment on the cross-source comparison (#3); insurance
  precision requires a financial SIC or ≥2 insurance concepts (#4); SIC recall floors for ~30 more
  themes (#5); `recall@gold` measures against the universe set, not the post-filter file (#6);
  concentration segment-vs-customer guard (#7); mktcap fallback fires before size-exclusion (#12);
  banner off-by-one and `mos_pct` percent display (#13).

## v0.3.0, Optimization campaign (2026-06-20) ✓ SHIPPED

A 5-iteration, subagent-driven, test-driven campaign (reflect → design → implement → test →
iterate). Closed all four top structural diagnoses from a 10-lens reflection. Full write-up:
`docs/optimization-campaign-2026-06/2026-06-20-campaign-final-report.md`.

- **Decision layer ✓** `buy_eligible` mechanical gate (guards now block, not advise); magnitude
  concentration kill-flag; V-shape value-trap vetoes (`fundamental_decline_flag` +
  `peak_contamination_flag`); financial-SIC + insurance-holdco exclusion; second-source
  cross-check gate; extreme-MoS / large-cap / FCF-sustainability gates.
- **Data/robustness ✓** debt-truncation / wrong-entity / low-revenue-loss / degenerate-base guards;
  EBIT concept cascade; market-cap fallback + `band=unknown` flow-through (recall 0→271 regbank,
  12→219 shipping); `form_used` provenance; deepdive crash-surfacing.
- **Recall ✓** SIC reverse-recall floor (UNION with FTS) + `recall@gold` metric (deathcare = 100%).
- **Calibration ✓** confidence-as-probability + dividend-adjusted total return + de-risk metrics +
  19 backfilled false-positive BUYs.
- **Ergonomics ✓** `new_run.py` batch outputs + `_run.json` manifests; `finalize_run.py`
  deterministic reports/verdicts/RANKING + trust banner; `make_report.py`; `rank.py` front-matter.
- **Diagnostic alpha ✓** firewalled `signals.py` side-channel, price-divergence (P16) + ownership
  (P17), strictly diagnostic, never touches `buy_eligible` (P15 alt-data agent-gathered). The
  delayed-information-diffusion thesis is now *measured* (diagnostically), not just asserted.

### Forward roadmap (deferred, non-blocking for real-world-usable)

- **P14, forensic spine:** Sloan accruals, diluted-share CAGR, SBC%, NI−FCF gap from XBRL with
  hard-ceiling triggers, move the highest-halo rubric dimensions onto T1 ground.
- **P11-full, catalyst-mechanism verification:** `{mechanism_verified, trigger_date,
  days_remaining}` per catalyst. The MoS-waiver is currently **frozen to WATCH**; un-freeze only
  after per-category Brier exists.
- **Signals per-signal Brier calibration:** score the recorded `signals_snapshot` once verdicts
  mature (~2027-06). Only then could a signal ever be considered for a non-diagnostic role, a
  fresh human decision.
- **P15 alt-data automation:** wire TrendsMCP / news into automated T2 capture (today agent-gathered).
- **recall@gold expansion:** build gold true-member lists beyond deathcare.

---

## v0.2.0, Phase 2 to 7 buildout (2026-06-19) ✓ SHIPPED

- **P2 ✓** Valuation engine (`tools/valuation.py`): reverse-DCF, EV/EBITDA multiples,
  cyclical-trough EBITDA normalization, asset-heavy NAV path.
- **P3 ✓** Symmetric BUY trigger (MoS ≥ 30% + 0 kill-flags + no T3) + closed-list catalyst
  axis (four qualifying forced-trading categories) + cyclical-turn perpetual-veto prohibition.
- **P4 ✓** 20-F/40-F fallback, SIC review-tier (downgrade not drop), dual market-cap band,
  per-theme keyword guidance.
- **P5 ✓** Event-driven discovery (`discover_events.py`): spinoffs (Form 10-12B) +
  cluster insider buys (openinsider). Four entry modes: theme / ticker / rank / events.
  CIK-first processing for pre-listing spinoffs.
- **P6-buildout ✓** Track-forward calibration (`tools/track_forward.py`): the verdict log at
  `<private data dir>/metrics/verdicts.jsonl` (out-of-repo, see `reference/track-forward.md`),
  Brier scoring vs IWM, 40 seeded verdicts (none mature until 2027-06, calibration unknown).
  Not to be confused with **P6-audit** (the run-3 `material_weakness` false-positive fix) or with
  **P6** in `SKILL.md` / the rubric (the `fundamental_decline_flag` veto): the three numbering
  schemes are independent, which is why each is prefixed here.
- **P7 integration fixes ✓** (see CHANGELOG v0.2.0 for detail):
  - C1: config.json gitignored + setup instructions clarified.
  - C2: material_weakness → Dim 1 ceiling fix (was incorrectly capping Dim 5).
  - I1: cheap_pass.py JSON input branch for event-mode candidates.
  - I2: discover_events.py --min-insiders default = 2 (rubric floor).
  - M1/M3/M4/M5: SKILL/rubric/rank/deepdive_data minor fixes.

---

## v0.1.0, Initial release (2026-06-18)

- Hybrid architecture: deterministic `tools/*.py` data layer + thin LLM judgment layer.
- Three entry modes: `theme` (full universe screen), `ticker` (single deep-dive), `rank` (re-rank).
- Two-stage precision gate: `filter_by_sic.py` (Gate 1) + LLM theme-fit classification (Gate 2).
- Mechanical kill-flags: going-concern, death-spiral convertibles, ICFR material weakness.
- 7-dimension scorecard with hard ceiling rules and evidence tier tagging.
- 5 methodology invariants in `reference/*.md` as single source of truth.
- Optional accelerators: `theme-fit-gate.js` + `deepdive-fanout.js` for parallel fan-out.
- Public-ready: MIT license, edgartools dependency, config abstracted, keys gitignored.
- market-intel read-only catalog reuse (anti-recursion structural guarantee).

---

## Next

Open work only. A completed item moves to its version's shipped section above, it does not stay
here with a checkmark.

### edgartools Form 4 direction parser hardening

**Status:** `insider_source: openinsider` is the current default; `insider_source: edgar` is
the public-ready mode but relies on a custom `transactionCode` parser that has not been tested
against the full range of Form 4 XML variants.

**Work:** Audit the custom direction parser against the EDGAR Form 4 XML schema variants,
including derivative transactions, gift transactions (`G`), and transactions with amended
filings (`/A`). Add an exhaustive fixture set to `tools/cheap_pass.py --selftest` covering
the edge cases. Once validated, flip the `config.example.json` default to `insider_source:
edgar` and deprecate the openinsider path.

**Trigger for landing:** 3 production runs with `insider_source: edgar` produce no direction
parsing errors.

### More themes and sector-specific precision gates

The two-stage precision gate is calibrated for general industrial/SaaS themes. Certain sectors
require specialized Gate 1 expansions:

- **Biotech/pharma:** when the theme is explicitly biotech (e.g., "RNA delivery vehicles"),
  the default SIC exclusion blocks biotech, the wrong direction. Need per-theme gate inversion
  support: `sic_inclusion_override: ["2836", "8731"]` to restrict to biotech SICs.
- **Energy transition:** SIC codes for legacy energy vs. emerging clean-energy overlap in
  ways the default hard-exclusion list handles poorly. Need a curated SIC allow-list for
  specific energy transition themes.
- **Financial-adjacent thematic plays:** companies that have financial SIC codes but are
  substantially operating businesses (e.g., specialty finance in an infrastructure theme).

### theme-scout (deferred, human alpha)

**Deferred by design.** Automated theme discovery, finding investment themes from news, X,
earnings call transcripts, is a tractable LLM task. It is deferred because the alpha in
theme selection is human: knowing which themes are at the right stage of the adoption cycle,
which are already over-indexed by retail, and which have an identifiable small-cap beneficiary
pool. Automating that selection would optimize for novelty, not investment merit.

When to revisit: if a systematic evidence base emerges that LLM-selected themes produce
better outcomes than human-selected themes in this context. Prerequisite: matured track-forward
Brier scores, which ship in v0.2.0 but cannot be computed until 2027-06.

---

## Run-3 audit synthesis (2026-06-18), prioritized

Four parallel audits (recall / rubric-calibration / hunting-grounds / pipeline) on the
4-theme run. Prioritized; the first was a **bug**, the rest improvements. Honest caveat
up front: three runs / ~40 deep dives produced **0 BUY**; part is genuine market efficiency,
part is the calibration gap below. None of this is guaranteed to surface a BUY.

**This section has its own P-numbering, independent of the v0.2.0 phase numbering above and of the
P-numbers in `SKILL.md` / `reference/judgment-rubric.md`.** The same label means three different
things across the three schemes, so items here are prefixed `P<n>-audit`. Only `P7-audit` is still
open.

**P1-audit ✓ DONE (mostly), Mechanical data-correctness bug.** `concept_series`'s 350-380-day
annual window mis-handled fiscal-year≠calendar-year filers → wrong revenue anchors in run-3 (BUKS
revenue stuck at FY2018 $48M vs real ~$84M; WLFC unit leakage 730 vs real $569M; LNN $659M vs
$676M). Shipped: the annual test keys on the XBRL fiscal-period tags
(`is_annual_tagged = fp == "FY" and form.startswith("10-K")`, with the day-span test only as a
fallback for untagged facts) in `tools/_deepdive_concepts.py` on both the live and the PIT path;
**BUKS and WLFC regression selftests** in `tools/deepdive_data.py`; and the shares fallback chain
`us-gaap:CommonStockSharesOutstanding` → `dei:EntityCommonStockSharesOutstanding` → diluted WANSO in
`_deepdive_concepts.py`. **Two sub-items of the original P1 are still open:** `fy` is carried
through from the XBRL fact rather than recomputed from `end`, and discover's `avg_dollar_vol` is
still not passed through to the deepdive JSON as `liquidity_adv` (that field name appears nowhere in
the codebase). Neither affects the revenue-anchor defect this item was raised for.

**P2-audit ✓ DONE (v0.2.0)**, Valuation engine (`tools/valuation.py`): reverse-DCF, EV/EBITDA,
cyclical-trough EBITDA, NAV path.

**P3-audit ✓ DONE (v0.2.0)**, Symmetric BUY trigger (MoS ≥ 30%) + closed-list catalyst axis
(four forced-trading categories) + perpetual-veto prohibition.

**P4-audit ✓ DONE (v0.2.0)**, 20-F/40-F fallback, SIC downgrade-to-review (not drop), dual
market-cap band, per-theme keyword guidance.

**P5-audit ✓ DONE (v0.2.0)**, Event-driven discovery: spinoffs (Form 10-12B) + cluster insider
buys (openinsider). Four entry modes: theme / ticker / rank / events. CIK-first for
pre-listing spinoffs.

**P6-audit ✓ DONE (v0.2.0)**, material_weakness false-positive fix: affirmative ICFR finding
required; bare risk-factor boilerplate does not fire the flag.

**P7-audit (theme-fit gate redundancy, STILL OPEN)**, run_theme.py candidates JSON omits `json_path`, so the
gate always WebSearches, then deepdive re-judges `theme_fit` anyway. Either pass `json_path`
through, or fold theme-fit into the deep-dive and drop the separate gate for the single-pass
path. (Deferred to future release.)

---

## Triggered Work (deferred, gated by external conditions)

### edgartools XBRL coverage improvement

**Trigger:** `edgartools` releases native support for partial-XBRL fallback to inline XBRL
(iXBRL) parsing for the micro-cap companies that do not tag all financial concepts. Action:
remove the manual `confidence_cap: 40%` ceiling for Dim 1 when XBRL is partial; rely on
the library fallback instead.

### Workflow-native parallel fan-out

**Trigger:** Claude Code's Workflow tool reaches general availability in the user's plan
and is confirmed stable for >100 concurrent fan-out invocations. Action: promote
`workflows/theme-fit-gate.js` and `workflows/deepdive-fanout.js` from "optional accelerator"
to the recommended path for theme runs with >30 candidates. The natural-language orchestration
path remains for sessions without the Workflow tool.

### Sector deep-dives (non-industrial themes)

**Trigger:** A real research run on a non-industrial theme (e.g., specialty healthcare,
defense subcontractors, agri-tech) exposes a gap in the current methodology invariants that
cannot be covered by per-theme config overrides. Action: extend `reference/judgment-rubric.md`
with sector-specific dimension adjustments (e.g., R&D pipeline valuation for biotech,
backlog-to-revenue ratio for defense).

---

## Maintenance Notes

`reference/*.md` is the single source of truth for all methodology invariants. Changes to
scoring logic, kill-flag definitions, evidence tiers, or cognitive priors go there first.
`SKILL.md` and `workflows/*.js` are downstream consumers.

When a production bug is discovered, the fix pattern is:
1. Fix the deterministic data layer (`tools/*.py`).
2. Add an explicit `--selftest` fixture for the edge case.
3. Document the invariant in the relevant `reference/*.md` section.
4. The bug is now part of the institutional knowledge crystallized in the tool.
