# Changelog

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

- `skills/small-cap-deepdive/SKILL.md` — three entry modes (theme / ticker / rank),
  two-stage precision gate documentation, rating hard-rules quick reference, environment
  prerequisites, data-source routing summary.

**User-facing docs**

- `README.md` + `README_CN.md` — what/why, install, three entry modes, honest framing.
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
