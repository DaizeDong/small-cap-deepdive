# Roadmap

Current: **v0.3.3**

## v0.3.0 — Optimization campaign (2026-06-20) ✓ SHIPPED

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
- **Diagnostic alpha ✓** firewalled `signals.py` side-channel — price-divergence (P16) + ownership
  (P17), strictly diagnostic, never touches `buy_eligible` (P15 alt-data agent-gathered). The
  delayed-information-diffusion thesis is now *measured* (diagnostically), not just asserted.

### Forward roadmap (deferred — non-blocking for real-world-usable)

- **P14 — forensic spine:** Sloan accruals, diluted-share CAGR, SBC%, NI−FCF gap from XBRL with
  hard-ceiling triggers — move the highest-halo rubric dimensions onto T1 ground.
- **P11-full — catalyst-mechanism verification:** `{mechanism_verified, trigger_date,
  days_remaining}` per catalyst. The MoS-waiver is currently **frozen to WATCH**; un-freeze only
  after per-category Brier exists.
- **Signals per-signal Brier calibration:** score the recorded `signals_snapshot` once verdicts
  mature (~2027-06). Only then could a signal ever be considered for a non-diagnostic role — a
  fresh human decision.
- **P15 alt-data automation:** wire TrendsMCP / news into automated T2 capture (today agent-gathered).
- **recall@gold expansion:** build gold true-member lists beyond deathcare.

---

## v0.2.0 — Phase 2–7 buildout (2026-06-19) ✓ SHIPPED

- **P2 ✓** Valuation engine (`tools/valuation.py`): reverse-DCF, EV/EBITDA multiples,
  cyclical-trough EBITDA normalization, asset-heavy NAV path.
- **P3 ✓** Symmetric BUY trigger (MoS ≥ 30% + 0 kill-flags + no T3) + closed-list catalyst
  axis (four qualifying forced-trading categories) + cyclical-turn perpetual-veto prohibition.
- **P4 ✓** 20-F/40-F fallback, SIC review-tier (downgrade not drop), dual market-cap band,
  per-theme keyword guidance.
- **P5 ✓** Event-driven discovery (`discover_events.py`): spinoffs (Form 10-12B) +
  cluster insider buys (openinsider). Four entry modes: theme / ticker / rank / events.
  CIK-first processing for pre-listing spinoffs.
- **P6 ✓** Track-forward calibration (`tools/track_forward.py`): `metrics/verdicts.jsonl`,
  Brier scoring vs IWM, 40 seeded verdicts (none mature until 2027-06 — calibration unknown).
- **P7 integration fixes ✓** (see CHANGELOG v0.2.0 for detail):
  - C1: config.json gitignored + setup instructions clarified.
  - C2: material_weakness → Dim 1 ceiling fix (was incorrectly capping Dim 5).
  - I1: cheap_pass.py JSON input branch for event-mode candidates.
  - I2: discover_events.py --min-insiders default = 2 (rubric floor).
  - M1/M3/M4/M5: SKILL/rubric/rank/deepdive_data minor fixes.

---

## v0.1.0 — Initial release (2026-06-18)

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

### Track-forward Brier scoring of verdicts ✓ DONE (v0.2.0 / P6)

`tools/track_forward.py` ships in v0.2.0. Verdicts logged to `metrics/verdicts.jsonl`;
`--score` pulls realized prices at maturity; `--scorecard` writes `metrics/scorecard.md`.
Benchmark: IWM (not SPY). 40 seeded verdicts from 2026-06 runs; none mature until 2027-06.
Rubric tuning gated on ≥20 matured verdicts — see `reference/track-forward.md`.

### More themes and sector-specific precision gates

The two-stage precision gate is calibrated for general industrial/SaaS themes. Certain sectors
require specialized Gate 1 expansions:

- **Biotech/pharma:** when the theme is explicitly biotech (e.g., "RNA delivery vehicles"),
  the default SIC exclusion blocks biotech — the wrong direction. Need per-theme gate inversion
  support: `sic_inclusion_override: ["2836", "8731"]` to restrict to biotech SICs.
- **Energy transition:** SIC codes for legacy energy vs. emerging clean-energy overlap in
  ways the default hard-exclusion list handles poorly. Need a curated SIC allow-list for
  specific energy transition themes.
- **Financial-adjacent thematic plays:** companies that have financial SIC codes but are
  substantially operating businesses (e.g., specialty finance in an infrastructure theme).

### theme-scout (deferred — human alpha)

**Deferred by design.** Automated theme discovery — finding investment themes from news, X,
earnings call transcripts — is a tractable LLM task. It is deferred because the alpha in
theme selection is human: knowing which themes are at the right stage of the adoption cycle,
which are already over-indexed by retail, and which have an identifiable small-cap beneficiary
pool. Automating that selection would optimize for novelty, not investment merit.

When to revisit: if a systematic evidence base emerges that LLM-selected themes produce
better outcomes than human-selected themes in this context (requires the track-forward
Brier scoring above as a prerequisite).

---

## Run-3 audit synthesis (2026-06-18) — prioritized

Four parallel audits (recall / rubric-calibration / hunting-grounds / pipeline) on the
4-theme run. Prioritized; the first is a **bug**, the rest are improvements. Honest caveat
up front: three runs / ~40 deep dives produced **0 BUY**; part is genuine market efficiency,
part is the calibration gap below. None of this is guaranteed to surface a BUY.

**P1 — Mechanical data-correctness bug (highest; this is a defect, not a feature).**
`concept_series`'s 350-380-day annual window mis-handles fiscal-year≠calendar-year filers →
wrong revenue anchors in run-3 (BUKS revenue stuck at FY2018 $48M vs real ~$84M; WLFC unit
leakage 730 vs real $569M; LNN $659M vs $676M). Agents caught these via WebSearch but should
not have to. Fix: use XBRL `fp`/`frame` (fiscal period) not a day-count window; recompute `fy`
from `end`; add **BUKS + WLFC regression selftests** (current selftest only covers EGAN, which
passes while these fail); shares fallback chain (`CommonStockSharesOutstanding` →
`dei:EntityCommonStockSharesOutstanding` → diluted WANSO); pass discover's `avg_dollar_vol`
through to the deepdive JSON (`liquidity_adv`). ~1 day, single file (`deepdive_data.py`).

**P2 ✓ DONE (v0.2.0)** — Valuation engine (`tools/valuation.py`): reverse-DCF, EV/EBITDA,
cyclical-trough EBITDA, NAV path.

**P3 ✓ DONE (v0.2.0)** — Symmetric BUY trigger (MoS ≥ 30%) + closed-list catalyst axis
(four forced-trading categories) + perpetual-veto prohibition.

**P4 ✓ DONE (v0.2.0)** — 20-F/40-F fallback, SIC downgrade-to-review (not drop), dual
market-cap band, per-theme keyword guidance.

**P5 ✓ DONE (v0.2.0)** — Event-driven discovery: spinoffs (Form 10-12B) + cluster insider
buys (openinsider). Four entry modes: theme / ticker / rank / events. CIK-first for
pre-listing spinoffs.

**P6 ✓ DONE (v0.2.0)** — material_weakness false-positive fix: affirmative ICFR finding
required; bare risk-factor boilerplate does not fire the flag.

**P7 (theme-fit gate redundancy)** — run_theme.py candidates JSON omits `json_path`, so the
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
