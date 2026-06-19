# Roadmap

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

### Track-forward Brier scoring of verdicts

**Status:** The skill produces ranked verdicts (score 1–5 with dimension breakdown) but there
is no mechanism to track whether verdicts are predictive.

**Work:** Implement a lightweight track-forward loop:

1. At verdict time, write `metrics/verdicts.jsonl` (ticker, composite, dimension scores,
   kill-flags, run date, theme).
2. At review time (90d / 180d / 1Y), pull the subsequent price performance and fundamental
   updates (next 10-K/10-Q XBRL pull), and compute a Brier-style score comparing the
   predicted directional outcome (score-4+ = positive) to the realized outcome.
3. Aggregate by dimension: which of the 7 dimensions has the best predictive validity?
   Which is anti-predictive (suggests removing it or inverting it)?

This is the only honest mechanism for improving the rubric — empirical feedback, not
subjective intuition.

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

**P2 — Valuation module (`tools/valuation.py`).** Mechanical layer emits no valuation, so
agents hand-compute multiples with inconsistent conventions. Add reverse-DCF (implied growth
from current EV + correct revenue/OCF — depends on P1), EV/EBITDA·FCF multiples, and same-
industry percentile. For cyclicals, force normalized/trough EBITDA (the UAN report already
demonstrates this reasoning). This is the prerequisite for P3.

**P3 — Symmetric BUY trigger + catalyst axis (calibration fix).** The rubric has downward
hard-ceilings but no upward BUY rule, so even valuation-4/5 + zero-kill-flag names default to
WATCH. Add: `margin of safety ≥ 30% (vs conservative intrinsic-value band) + 0 kill-flag + no
T3-load-bearing → BUY` (confidence capped by valuation robustness). Add a catalyst /
forced-trading dimension so a "fairly priced today but with an un-priced catalyst" name can
score BUY. Guardrails: BUY must rest on T1 valuation only; cyclicals use trough EBITDA; still
requires pre-mortem + forced reverse-search. WLFC and CSV are the run-3 likely false-negatives
to re-test once this lands.

**P4 — Recall improvements (several cheap).** (a) FTS window → 2yr + `max_pages` deeper
(run-3 likely missed ASLE — same SIC/cap/theme as survivor WLFC, pure keyword/window miss);
(b) add `20-F`/`40-F` forms (foreign-filer blind spot — see discovery-engine Coverage Caveat);
(c) SIC hard-exclude → **downgrade-to-partial-review, not drop**, when a 5xxx/6xxx company hits
theme keywords (would have rescued TITN SIC-5990, SNFCA SIC-6199); (d) dual market-cap band
(<$2B deep-dive + $2-5B lightweight watch — captures flagships UNF/VSEC without polluting the
small-cap ranking); (e) per-theme keyword sets (run-3 `crop inputs` too academic → missed
LXU/IPI/AVD; `facility services`/`engine` too broad → noise).

**P5 — Event-driven discovery pivot (strategic; biggest build, best shot at a real BUY).**
The hunting-grounds audit's core finding: theme/industry hunting in the >$200M band is
efficiently priced; capturable mispricing is overwhelmingly event-driven. Add discovery axes
that enumerate by EDGAR **form type** (structurally high-precision, no keyword over-recall, no
theme-fit gate needed): **spinoffs** (Form `10-12B`) and **cluster open-market insider buys**
(Form 4, 3+ insiders / 30d / incl. ≥1 independent director, opportunistic not routine). Keep
the deep-dive engine unchanged. Honest caveat: index-effect and PEAD anomalies are largely
arbitraged away; spinoff + insider signals persist but are decaying and liquidity eats much of
the gross edge — validate with track-forward before believing any edge.

**P6 — material_weakness false-positive fix.** 4/4 flagged True in run-3 were boilerplate
keyword collisions the agent overturned every time. Tighten to Item 9A section match, or
downgrade to a hint that does not count as a kill-flag.

**P7 — theme-fit gate redundancy.** `run_theme.py` candidates JSON omits `json_path`, so the
gate always WebSearches, then deepdive re-judges `theme_fit` anyway. Either pass `json_path`
through, or fold theme-fit into the deep-dive and drop the separate gate for the single-pass
path.

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
