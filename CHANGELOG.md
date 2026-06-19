# Changelog

## v0.2.0 — 2026-06-19

Phase 2–7 buildout on top of the v0.1.0 architecture. Remains a de-risk scanner:
0 BUY is a valid and correct output.

### What shipped

**P2 — Valuation engine (`tools/valuation.py`)**

Mechanical valuation layer so agents stop hand-computing multiples with inconsistent
conventions. Implements: reverse-DCF (implied growth from EV + normalized FCF),
EV/EBITDA and EV/Sales multiples, cyclical-trough EBITDA normalization, and an
asset-heavy NAV path (tangible equity - net debt). Three-way `mos_basis` output:
`fcf_cap` / `nav` / `abstain`.

**P3 — Symmetric BUY trigger + closed-list catalyst axis + guardrails**

Added a positive BUY rule to complement the existing downward hard-ceilings:
`margin_of_safety_pct ≥ 30%` AND 0 kill-flags AND no T3-load-bearing claim → BUY
(confidence adjusted by valuation robustness). Catalyst modifier: closed enumerated
list of four qualifying forced-trading categories (spinoff 10-12B, cluster insider buy
Form 4, court-ordered asset sale, exchange deficiency event). Organic-growth narratives
explicitly do not qualify. Cyclical-turn perpetual-veto prohibition added.

**P4 — Recall improvements**

- 20-F / 40-F fallback in `cheap_pass.py` and `deepdive_data.py` (foreign-domiciled
  filers: shipping, mining, Canadian cross-listed).
- SIC review-tier: downgrade to partial-review rather than hard-drop for 5xxx/6xxx
  companies that hit theme keywords.
- Dual market-cap band: `band="deep"` (<$2B, full deep-dive) + `band="watch"` ($2-5B,
  surface for human review) + `band="large"` (>$5B, skip) + `band="unknown"` (process).
- Per-theme keyword guidance documented in `reference/discovery-engine.md`.

**P5 — Event-driven discovery (four entry modes: theme / ticker / rank / events)**

New entry mode `events` with two axes:

- `--spinoffs`: enumerate Form 10-12B / 10-12B/A registrations from EDGAR EFTS.
  Catalyst: passive index-fund forced selling of the spun-off entity.
- `--insider-clusters`: enumerate cluster open-market insider buys from openinsider.
  Catalyst: multiple insiders purchasing at market price = management conviction signal.

No theme-fit gate required — form-type enumeration replaces keyword precision.
Kill-flag scan (`cheap_pass.py`) still mandatory. CIK-first deep-dive for pre-listing
spinoffs (no ticker yet). Band tagging carried through to deepdive and rank steps.

**P6 — Track-forward calibration loop (`tools/track_forward.py`)**

`metrics/verdicts.jsonl` records all deep-dive verdicts with composite, dimension
scores, kill-flags, run date, theme. `--score` pulls realized prices and computes
Brier-style score vs IWM benchmark at maturity (90d / 180d / 1Y horizons).
`--scorecard` writes `metrics/scorecard.md`. 40 seeded verdicts from 2026-06 runs
committed; none mature until 2027-06 — correct state is "calibration unknown."

**P7 — Bug fixes**

- C1: `skills/small-cap-deepdive/reference/config.json` untracked from git; setup
  instructions now clearly state a fresh clone has no config.json and directs user
  to copy `config.example.json`.
- C2: `material_weakness` in ICFR correctly caps Dim 1 (financial quality), not
  Dim 5 (theme fit / timing). ICFR failure is a financial-quality signal. Fixed in
  `judgment-rubric.md` and `SKILL.md`. The concept-player ceiling (no theme revenue
  → Dim 5 capped at 2) is unchanged and correct.
- I1: `cheap_pass.py --universe <json>` now handles JSON input from `discover_events.py`
  without `pd.read_csv` ParserError. JSON path detected by `.json` extension; builds
  DataFrame from records; applies max-mcap filter with `band="unknown"` passthrough.
- I2: `discover_events.py --min-insiders` default changed from 3 to 2 (the rubric
  floor). Discovery enumerates at the floor; `n_insiders` is surfaced per record so
  deep-dive agent can prefer ≥3 for higher conviction. `event-driven.md §Axis 2`
  clarified.
- M1: SKILL.md heading and CHANGELOG updated to "four entry modes".
- M3: `judgment-rubric.md` hard-rules table now includes the quantitative threshold
  for the Dim 4 ceiling: dilution rate ≥ 15%/yr (from `disclosure-discipline.md`).
- M4: `rank.py load_hard_data()` reads `killflag_count` field directly with int()
  fallback to the 3-boolean sum; resilient to new kill-flag types.
- M5: `deepdive_data.py` emits `data_quality_warn` field when `|net_income| > revenue
  × 50` (XBRL unit mis-tag anomaly, e.g. SNFCA $32B vs real $32M). Value unaltered;
  valuation uses OCF so it is unaffected; flag surfaces anomaly to reader only.

---

## v0.1.0 — 2026-06-18

Initial release.

### What shipped

**Architecture**

Hybrid data+judgment split: deterministic Python data layer (`tools/*.py`) strictly separated
from the LLM judgment layer (`SKILL.md` + `reference/*.md` + `workflows/*.js`). The boundary
was forced by 10 production bugs encountered during the daily-alpha development run — all in
the data layer, all prevented from contaminating judgment output by the architectural boundary.

**Tools (deterministic data layer)**

- `tools/_common.py` — shared config loader, EDGAR session with rate discipline (per-tool
  sleep ~150ms inter-request, exponential backoff on 429 via http_get retry wrapper).
- `tools/discover.py` — EDGAR FTS universe enumeration with zero-hit guard and FTS retry.
- `tools/filter_by_sic.py` — Gate 1 SIC coarse exclusion with per-theme override support.
- `tools/cheap_pass.py` — mechanical kill-flags: going-concern (double-confirmation required),
  death-spiral convertibles, ICFR material weaknesses; amendment (`10-K/A`) exclusion.
- `tools/deepdive_data.py` — XBRL financials (revenue, OCF, EV series), Form 4 insider trades,
  S-3/ATM shelf status, dilution history, 8-K material event timeline.
- `tools/rank.py` — deterministic composite scoring with hard ceiling rule enforcement,
  weight override support, funnel summary output.
- `tools/run_theme.py` — end-to-end theme driver orchestrating the above tools.

**Reference methodology (single source of truth)**

Five methodology invariant documents in `skills/small-cap-deepdive/reference/`:

- `discovery-engine.md` — FTS over-recall design, two-stage precision gate, 10 production
  cautionary cases (including the `refractory`-oncology failure mode).
- `mechanical-checks.md` — 5 Python guards corresponding to patched production bugs.
- `judgment-rubric.md` — 7-dimension scorecard, evidence tier definitions (T1–T3), hard
  ceiling rules, output template.
- `disclosure-discipline.md` — base-rate anchoring, forced disconfirmation, halo de-biasing,
  evidence tier usage, and 9 disclosure disciplines.
- `cognitive-priors.md` — world-view and base-rate prior table (被忽视≠被低估; 热点=赌场;
  edge=纪律不是叙事; 产出是避雷扫描器).
- `data-sources.md` — EDGAR rate discipline, openinsider fragility, market-intel read-only
  catalog reuse pattern, anti-recursion rule, X sentiment route, blind spots table.

**Workflows (optional accelerators)**

- `workflows/theme-fit-gate.js` — parallel Gate 2 LLM fan-out (Workflow tool required).
- `workflows/deepdive-fanout.js` — parallel deep-dive agent fan-out (Workflow tool required).

Both are optional: the natural-language orchestration in `SKILL.md` is the primary path and
works in any Claude Code session without the Workflow tool.

**Skill entrypoint**

- `skills/small-cap-deepdive/SKILL.md` — entry modes (theme / ticker / rank, events added in v0.2.0),
  two-stage precision gate documentation, rating hard-rules quick reference, environment
  prerequisites, data-source routing summary.

**User-facing docs**

- `README.md` + `README_CN.md` — what/why, install, entry modes (three at v0.1.0), honest framing.
- `ROADMAP.md` — next items including Form 4 direction parser hardening and track-forward
  Brier scoring; deferred items (theme-scout); triggered items gated on external conditions.
- `PHILOSOPHY.md` — four design principles: root-cause vs symptom (P1), Hybrid vs thin (P2),
  discipline as moat (P3), single source of truth (P4).
- `CHANGELOG.md` — this file.
- `runbooks/theme-run.md` — step-by-step for full theme universe screen with token budgets.
- `runbooks/single-deepdive.md` — step-by-step for single-ticker deep-dive.
- `runbooks/batch-rank.md` — step-by-step for re-ranking existing scored outputs.

**Configuration**

- `skills/small-cap-deepdive/reference/config.example.json` — all config keys with defaults;
  `sec_user_agent` is the only required field.
- `.gitignore` — excludes `config.json`, `reports/`, `*.env` from version control.
