# Changelog

All notable changes to this project are documented here (Keep a Changelog style).

## v0.3.2 — 2026-06-20

### Docs
- Unify repo structure (Skill Repo Spec v1) — philosophy-first README section order, standardized top block (tagline + badges + bilingual switch), 1:1 EN/CN sections, added `.claude-plugin/plugin.json`, single-sourced version across plugin.json / README badges / ROADMAP / CHANGELOG.


Coverage-test backlog cleanup (the MEDIUM items deferred from v0.3.1):
- **#8 lessor NAV routing** — `lessor_asset_heavy` (leasing SIC / lease-income concept / high
  PP&E) routes asset-heavy lessors to the NAV basis **even below the 0.62 debt/assets threshold**.
  GBX/RAIL are now valued on lease-fleet NAV, not trough-cycle FCF.
- **#10 concurrency isolation** — the SIC-floor sidecar is run/slug-namespaced
  (`_sic_floor_<slug>.json`, kept out of the `candidates_*.json` glob) and run-state is
  per-`SMALLCAP_RUN` / PID-unique (the shared `/tmp/smallcap_run.txt` is gone). No more
  cross-theme contamination when many agents run concurrently.
- **#11 foreign-filer** — IFRS concept cascade (us-gaap + ifrs-full) recovers some 20-F/40-F
  filers; when still empty, `foreign_filer_unvaluable` labels the graceful abstain (no silent null).

All 9 tool selftests + both workflows pass; regression (TUSK/SIGA/INVA) unchanged.

## v0.3.1 — 2026-06-20

Remediation round driven by the v0.3.0 full-coverage test (53 themes across all GICS sectors +
niche; report in `docs/coverage-test-2026-06-20/`). The test confirmed **0 false BUYs leaked**
but found one CRITICAL mechanical hole plus precision/recall bugs — all fixed here and re-verified
on real data.

- **#1 (CRITICAL) degenerate-base hole** — new `normalization_masks_current_loss`: when
  `normalized_fcf>0` while current `latest_ocf<0`/`latest_fcf<0` or `contamination_ratio<0` (the
  trailing-average masking current cash burn / a divested-segment stub), `buy_eligible` is now
  blocked (downgrade BUY→WATCH). Closes the **TUSK +55.1% phantom BUY** that previously only the
  human adversarial layer caught (the mechanical vetoes were silenced by the A1 0<cr guard).
- **#2 (CRITICAL) SEC debt truncation** — `total_debt` is now SUMMED across the standard debt
  concepts; when still `< 0.5 × implied (liabilities − equity)`, the implied figure is used for EV.
  HRI now reflects ~$9.768B (was a single-tag $11M). Cuts false `cross_source_mismatch` blocks.
- **#3** ASC842 operating-lease adjustment on the SEC side of the cross-source comparison.
- **#4** insurance-precision: `insurance_concepts_present` requires financial SIC (63/64) OR ≥2
  distinct insurance concepts — kills SPB/ASTE/SKIL/ALLR/TOPP false positives.
- **#7** concentration segment-vs-customer guard (robust to collapsed whitespace / curly
  apostrophe) — saves DSGR, a real $1.32B distributor previously killed pre-deep-dive.
- **#9** `buy_eligible=False` (`not_assessable_no_intrinsic_band`) when there is no intrinsic band
  / null MoS — `buy_eligible` can no longer be True with a null MoS.
- **#5** SIC reverse-recall floors added for ~30 more themes. **#6** `recall@gold` now measures
  against the universe set, not the post-filter file (deathcare 5/6, not the 33% artifact).
- **#12** SEC shares×price mktcap fallback fires before the small-cap size-exclusion (saves
  SJW/HI-class names). **#13** deep-dive banner off-by-one + `mos_pct` percent display.

All 9 tool selftests + both workflows pass; regression (SIGA double-blocked, NRP peak veto, INVA
clean) unchanged. Still a de-risk scanner — 0-BUY remains the common, correct output.

## v0.3.0 — 2026-06-20

A 5-iteration, subagent-driven, test-driven optimization campaign (10-lens reflection →
design → implement → test on real data → iterate). It transformed the engine **from a
value-trap generator into a calibrated landmine scanner with an operationalized (diagnostic)
alpha thesis**, and closed all four top structural diagnoses. Full write-up:
`docs/optimization-campaign-2026-06/2026-06-20-campaign-final-report.md`. Still a de-risk scanner — 0-BUY
is the common, correct output; calibration matures ~2027.

The root finding the campaign fixed: `MoS` and `reverse_dcf_implied_growth` were algebraically
identical, so every mechanical BUY priced *decline* by construction, and the stated edge
(delayed information diffusion) was measured nowhere.

**Decision layer — guards now BLOCK, not advise (`tools/valuation.py`, `reference/judgment-rubric.md`)**
- **`buy_eligible` mechanical gate (P1):** the previously-advisory guards are now a single boolean the
  BUY trigger ANDs in. A BUY requires `mos_basis∈{fcf_cap,nav}` AND MoS ≥ 30% AND `buy_eligible` AND
  zero kill-flags. VSNT/ARDT (large-cap) and the rest no longer slip through.
- **Concentration magnitude kill-flag (P3):** top-customer / single-government-program % from XBRL
  segment members (>40% customer / >60% program → kill), replacing the old English substring. Catches
  SIGA's 75% BARDA dependence.
- **Trajectory + peak-contamination V-shape vetoes (P6 / P-A):** `fundamental_decline_flag` (monotone
  decline) and `peak_contamination_flag` (trough→peak→rollover, independent of slope: contamination
  < 0.8 AND latest-below-avg AND latest NI < 0) downgrade a static-MoS BUY → WATCH at the fundamentals.
  Kills the SIGA and NRP melting-ice-cubes; 0 false fires across 22 fast-growth test names.
- **Financial-sector + insurance-holdco exclusion (C2 / A3):** financial SICs (60/61/63/64/67) and any
  issuer with insurance XBRL concepts (e.g. SIC-65 holdcos) route to NAV/abstain, never fcf_cap.
- **Second-source sanity gate (P7):** SEC-XBRL debt/revenue/shares cross-checked against yfinance;
  a > 2.5× disagreement (`cross_source_mismatch`) blocks BUY. HRI now double-caught.
- **Defense-in-depth:** extreme-MoS (>100%), large-cap-ceiling, FCF-sustainability gates all bite.

**Data / robustness (`tools/deepdive_data.py`)**
- XBRL guards: debt-truncation, wrong-entity (now strictly unit-mistag / wrong-CIK), low-revenue-loss
  ratio (tiered; `_extreme` gates), degenerate-base guard (a negative contamination ratio can't trip
  a veto). `concentration_unquantified` advisory for text-only / pre-XBRL filers.
- **EBIT concept cascade (P9):** recovers EV/EBITDA on the ~47% of names where the single concept was null.
- **Market-cap fallback + `band=unknown` flow-through (P5):** SEC shares×price fallback when yfinance is
  null; unresolved names flow through as `band=unknown` instead of being silently dropped. Recall
  recovered from ~0→271 (regbank) and ~12→219 (shipping) candidates.
- `form_used` provenance (10-K/20-F/40-F incl. foreign filers); deepdive crash-surfacing
  (`deepdive_<ticker>_ERROR.json`, no more silent skips).

**Recall (`tools/discover.py`, `tools/filter_by_sic.py`, `tools/track_forward.py`)**
- **SIC reverse-recall floor (P8):** for a theme with dedicated SIC code(s), enumerate all registrants
  in that SIC and UNION with FTS (`recall_channel` tagged) — turns SIC from a precision-only exclude
  into a recall floor. **`recall@gold` metric** measures recall against hand-built gold lists
  (deathcare = 100%, with SCI+CSV recovered via the SIC floor). Recall is now measured, not assumed.

**Calibration (`tools/track_forward.py`, `metrics/`)**
- **P12:** confidence-as-probability by rating direction, dividend-adjusted total return, de-risk-native
  metrics (blowup-avoidance / downside-capture), and the 19 v0.2.0 false-positive BUYs backfilled as a
  distinct `adjudication=data_false_positive` class so the BUY arm of the calibration table isn't empty.

**Ergonomics (new tools)**
- **`tools/new_run.py`** — open a timestamped run batch; all outputs land in
  `reports/smallcap/<date>_<label>/` with a `_run.json` manifest (skill git commit + config snapshot)
  for cross-version comparison. Set `SMALLCAP_RUN` to route; unset = flat (legacy).
- **`tools/finalize_run.py`** — deterministic run-finalizer: asserts every deep candidate has a report +
  verdict, rebuilds `RANKING.md`, auto-emits verdicts into the track-forward loop, and is Gate-2-aware
  (misrecalls counted resolved, not missing).
- **`tools/make_report.py`** — deterministic report scaffolder with a **data-quality TRUST BANNER**
  under each rating (the flags must be visible at the decision point).
- `rank.py` gained a fenced front-matter rating contract + `--selftest`.

**Diagnostic alpha — firewalled side-channel (`tools/signals.py`)**
- **`signals.py`** emits a top-level `signals` namespace (sibling of `derived`): **price-divergence
  (P16)** — fundamental trajectory vs trailing 6m/12m price return → `{unpriced_improvement |
  melting_ice_cube_priced | aligned | unclear}` (directly measures "a real change the market hasn't
  priced"; MGPI → `unpriced_improvement`) — and **ownership (P17)** — EDGAR 13D/13G + short interest.
- **THE FIREWALL:** signals are strictly **diagnostic** — `valuation.py` / `buy_eligible` / the BUY
  trigger contain **zero** references to any signal; `buy_eligible` is byte-identical with vs without
  signals. `track_forward` records a `signals_snapshot` (recorded-but-inert) for future per-signal
  Brier calibration. P15 alt-data (TrendsMCP / news) stays agent-gathered T2 context (MCP isn't
  callable from Python). This operationalizes the thesis as a measurement without letting it originate
  or up-weight a BUY.

## v0.2.1 — 2026-06-19

Remediation round driven by the full real-data validation campaign (21 subagents:
8 themes + 3 trigger-diagnostics + 3 event-driven + 4 robustness + 2 precision +
synthesis; report in `docs/2026-06-19-validation-report.md`). The campaign confirmed
the BUY trigger is **reachable, not logically dead** (SIGA fired mechanically), but
that on real data **every BUY was a false positive** rooted in data-layer
pathologies. Guards added:

- **C1 — XBRL balance-sheet guards** (`tools/deepdive_data.py`): debt-truncation
  cross-check (reported_debt vs liabilities−equity), debt-staleness (>18mo), and
  wrong-entity detection (ticker absent from company_tickers.json / absurd
  financials) → force `abstain`. Kills RYAM/FTAI/HRI/FSBW false positives and
  AL/GOGL/EGLE wrong-entity resolution.
- **C2 — financial-sector exclusion** (`tools/valuation.py`): SIC 60/61/63/64/67 →
  `fcf_cap_model_unsuitable` → NAV/abstain; plus a SIC-absent fallback that detects
  the BDC/closed-end-fund signature (no GAAP revenue + OCF present) for issuers SEC
  omits a SIC for (e.g. WHF). Kills HCI/WHF/ABR pseudo-BUYs.
- **I1 — FCF sustainability guard** (`tools/valuation.py`): reverse-DCF implied
  growth < −15% or capital-intensive OCF-proxy → BUY downgraded to WATCH
  (VSNT/SIGA/shippers).
- **I3 — data-quality propagation** (`tools/valuation.py`): deepdive
  `data_quality_warn` + C1 flags now surface in valuation's `data_quality` (SNFCA
  unit anomaly visible at the decision layer).
- **I4 — burn check uses OCF** (`tools/cheap_pass.py`): `reject_burn` keys on
  operating cash flow, not GAAP net income, so non-cash impairments don't kill real
  members (MATW).
- **G1/G2 — defense-in-depth** (`tools/valuation.py`): |MoS|>100% and
  market_cap>watch_band_max never auto-BUY.

Verdict: v0.2.0 produced real mechanical signal and was honest about 0-BUY, but its
robustness could not be trusted before these guards. Still a de-risk scanner, not a
stock picker.

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
