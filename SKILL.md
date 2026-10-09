---
name: small-cap-deepdive
description: "Use to research neglected small-cap/microcap US equities by THEME or TICKER: SEC-filing universe, de-risk, falsifiable deep-dive DD, rank. NOT large-cap/quant/trading."
allowed-tools: Read, Glob, Grep, Bash, Agent, Skill, WebSearch, WebFetch
---

# small-cap-deepdive

Research neglected small-cap equities through deterministic SEC retrieval, mechanical risk
checks and evidence-based judgment. Choose an entry below and use its runbook for commands.
Outputs are company reports or ranked candidates for human due diligence.

---

## World-View (read before interpreting any output)

Read [cognitive priors](reference/cognitive-priors.md) before interpreting results. Low coverage
does not establish undervaluation; theme popularity does not establish a return opportunity.
The cited thematic-ETF findings and base-rate table require population-matched verification
before use. Consistent screening is a design objective, not proof of predictive performance.
Report the observed scope and missing work even when no candidate reaches score 4.

[PHILOSOPHY.md](PHILOSOPHY.md) defines the data/judgment boundary and reference ownership.
The user makes the investment decision.

---

## Four Entry Workflows

> **Open a batch for research entries.** Before the first acquisition call, open a
> timestamped batch so this run's candidates / cheappass / deepdive / valuation / report files
> stay together and runs stay comparable across skill versions:
> ```bash
> SMALLCAP_RUN="$(python tools/new_run.py --label "Synthetic research")" || exit 1
> export SMALLCAP_RUN
> REPORTS_ROOT="$(python -c 'import sys; sys.path.insert(0, "tools"); from _common import reports_dir; print(reports_dir())')" || exit 1
> export REPORTS_ROOT
> # Outputs use this absolute PRIVATE directory with a _run.json manifest.
> ```
> Leaving `SMALLCAP_RUN` unset uses the unbatched PRIVATE reports root. Expand `REPORTS_ROOT` to its absolute value before handing any output path to another agent.
>
> Concurrency and SIC sidecar ownership: [discovery contract](reference/discovery-engine.md#sidecar-isolation).

### Entry 1, `theme <主题>` (thematic universe screen)

**Use when:** you have an investment theme and want a ranked shortlist of small-cap pure-plays.

**Natural-language orchestration (requires a configured Workflow host for bound stage completion):**

1. **Stages 1 to 3 in one driver.** Run `tools/run_theme.py --theme "<逗号分隔关键词>" --slug <slug>`.
   It shells `discover.py`, then `cheap_pass.py`, then applies Gate 1 inline, and writes
   `candidates_<slug>.json`. Run the three by hand only when you need to vary a stage; the
   sub-steps below describe what each one does and what it is allowed to do.

   1a. **Universe enumeration.** `tools/discover.py --theme "<关键词>" --out-slug <slug>` queries SEC
   EDGAR full-text search and returns candidate tickers. This over-recalls by design, expect
   hundreds of results. **The SIC reverse-recall floor is opt-in and `run_theme.py` does NOT
   request it:** pass `--sic-reverse` to `discover.py` yourself for a theme that has dedicated SIC
   code(s) in `filter_by_sic.THEME_SIC`, and the FTS recall is UNIONed with a full EDGAR
   browse-by-SIC enumeration of those codes (P8). For a theme with no dedicated SIC the flag is a
   no-op.

   1b. **Mechanical de-risk.** `tools/cheap_pass.py --universe <universe_csv> --out-slug <slug>`
   marks `rejected` for a connected current going-concern and substantial-doubt assertion,
   two or more counted kill-flags, a cash-burn rejection, or a `kill` concentration.
   A lone death-spiral or material-weakness flag survives this screen but blocks BUY under
   the judgment rubric. Rejected names never reach Gate 1 or the deep-dive.

   1c. **Gate 1, SIC coarse review.** Applied **inline by `run_theme.py`**, which imports
   `filter_by_sic.sic_classify` as a library and tags each survivor `sic_tier`.
   **`tools/filter_by_sic.py` is not a pipeline step and cannot be invoked as one, its only CLI is
   `--selftest`**, which runs the unit assertions and exits. Use `python tools/filter_by_sic.py
   --selftest` to verify the SIC logic, never to filter a candidate list.

2. **Gate 2, LLM theme-fit (mandatory, see next section).** Run the LLM theme-fit gate on every
   Gate 1 survivor (both `sic_tier="keep"` and `sic_tier="review"`) to classify each as
   `pure_play / partial / misrecall`. Drop `misrecall`. Retain `pure_play` and `partial` for
   deep-dive. Gate 2 is the only gate in the theme flow that removes a company for theme-fit.

3. **Deep-dive.** Ingest the bound Gate-2 host result with `run_theme.py --gate2-request`
   and `--gate2-result`, then run `tools/deepdive_data.py --candidates <candidates_gate2_survivors.json>` to retrieve
   the full financial series, insider trade record, and disclosure timeline. Spawn one Agent per
   candidate, instructing it to apply the 7-dimension scorecard from `reference/judgment-rubric.md`,
   preamble first (base-rate anchor + disconfirmation search + staleness check + the
   `tools/valuation.py` run) before any scoring.

4. **Rank.** Run `tools/rank.py` on the scored outputs to produce the ranked shortlist.
   Report includes: gate survival counts, kill-flag eliminations, score distribution,
   top candidates with dimension scores, and explicit coverage gaps.

**Workflow request contract:** `run_theme.py` emits `gate2_request.json`; use
`--prepare-gate2 <candidates>` only when preparing an existing artifact without a request.
Pass the request as `args` through the configured Workflow host, preserve its full result,
and ingest it with `--gate2-request <request> --gate2-result <result>`.
After data pull, `deepdive_data.py --prepare-fanout <survivors> --verdict-date <YYYY-MM-DD>`
prepares `deepdive_request.json`. Run that request through the host and ingest its result
with `--fanout-request <request> --fanout-result <result>`. Keep all artifacts and receipts.
The JavaScript files require host functions and cannot run as direct Node scripts.
Without a host result the stage remains incomplete. See `runbooks/theme-run.md`.

---

### Entry 2, `ticker <代码> [--theme X]` (single-company deep-dive)

**Use when:** you have a specific ticker and want a rigorous, falsifiable deep-dive report.
Optionally pass `--theme X` to anchor the theme-fit scoring.

**Natural-language orchestration:**

1. **Mechanical de-risk first.** Save a one-company universe in the private run directory, then run
   `tools/cheap_pass.py --universe <path-to-json-or-csv>`. JSON must be a list of objects with
   `ticker`, `cik` and `name` keys; CSV also requires boolean `smallcap_candidate`. Event rows may
   retain blank ticker/CIK values; optional `mktcap` and `price` values must be numeric. Use the
   returned `rejected` field: if true, report the reason and stop before full deep-dive; a single
   risk flag does not necessarily reject a company. Exit 0 means the requested work is
   complete; exit 2 means partial, unavailable or invalid, so inspect coverage before proceeding.
   Nonempty manual input without its `<artifact>.stage.json` completion receipt remains partial;
   empty input without completion evidence is unavailable. Keep each artifact with its receipt,
   and use a new run output when a paired receipt already exists.

2. **Data pull.** Run `tools/deepdive_data.py --ticker <代码> --cik <verified-CIK>` to retrieve
   financial series, insider trades, filing timeline and kill-flag detail. Standalone input
   retains `unbound_single_input`; inspect its partial status and exit code rather than
   counting it as a completed theme pipeline.

3. **Judgment pass.** Apply the 7-dimension scorecard from `reference/judgment-rubric.md` in full.
   Required preamble, all four steps: (a) state the reference-class base rates from
   `reference/cognitive-priors.md`; (b) run disconfirmation WebSearch; (c) check data staleness;
   (d) run `python tools/valuation.py --json <deepdive_json> --ticker <代码>` and record `mos_basis`,
   the MoS fields, `buy_eligible` and `buy_ineligible_reasons`. Nothing else in the pipeline runs
   it, and a rating without it has no margin of safety.

4. **Output.** Single-company report with dimension scores, evidence tier per claim, kill-flag
   detail, disconfirmation findings, and a composite rating with the hard-rule ceilings applied
   (`reference/judgment-rubric.md §Rating Hard-Rules`).

**Optional Workflow host:** one company may use the same bound survivor/request/result
contract as a batch. A raw one-row candidate array is not an accepted request.
See `runbooks/single-deepdive.md` for the standalone boundary.

---

### Entry 3, `rank` (re-rank existing scored outputs)

**Use when:** you have scored company reports and want to re-sort them without repeating
discovery or deep-dive. Ranking is optional for a single-company report.

**Natural-language orchestration:**

1. Select the existing scored report directory and its active run or explicit `--input`.
   Re-ranking uses that directory and does not require allocating a new research batch.
2. Run `tools/rank.py [--slug <slug>] [--input <dir>] --output <fresh-ranking-name>.md` to produce a ranked table. Choose a new basename for every re-rank; existing artifacts are preserved.
3. Report the ranking with kill-flag eliminations and explicit coverage gaps.

---

### Entry 4, `events <spinoffs|insider-clusters>` (event-driven discovery)

**Use when:** you want to hunt for mis-priced small-caps via a structural catalyst rather than a
theme keyword.  Two event axes are supported; both are structurally high-precision (no
theme-fit gate needed, form-type enumeration replaces keyword over-recall):

- `spinoffs`, enumerate recent **Form 10-12B / 10-12B/A** registrations (spinoff / carve-out).
  Catalyst: passive index-fund holders of the parent are forced to sell the spun-off child if it
  falls outside their index mandate.  This forced-selling window is the mis-pricing mechanism.

- `insider-clusters`, enumerate recent **cluster open-market insider buys** from
  openinsider.com.  Catalyst: multiple insiders buying at market price within a short window
  is the strongest available management-conviction signal (Form 4, open-market cash only).

**Rationale and honest caveats:** `reference/event-driven.md`.

**Natural-language orchestration:**

1. **Enumerate the event.** Run `tools/discover_events.py --spinoffs` or
   `tools/discover_events.py --insider-clusters`.
   Output: `${REPORTS_ROOT}/candidates_event_<mode>_<date>.json`, same shape as
   theme-mode `candidates_<slug>.json`.

2. **Kill-flag scan (mandatory).** Run `tools/cheap_pass.py --universe <candidates_json>`.
   Kill-flags (`going_concern`, `death_spiral`, `material_weakness`) apply identically to
   event candidates.  A compelling catalyst does not excuse a going-concern filing.

3. **Deep-dive data pull.** Cheap-pass writes `candidates_event_admitted.json` and a receipt binding the event source, every input identity/band and its screening decision. Run `tools/deepdive_data.py --candidates <run>/candidates_event_admitted.json`. Missing source, identity or kill-scan evidence remains partial; only explicit, observed exclusions resolve an input.
   **Band guard (four explicit bands, C3):**
   - `band="deep"` (mktcap < market_cap_max): **process**, full deep-dive.
   - `band="watch"` (market_cap_max..watch_band_max): **skip**, surfaced separately for human review only; not deep-dived.
   - `band="large"` (> watch_band_max): **skip**, out of scope.
   - `band="unknown"` (mktcap unavailable / pre-listing): **process**, likely a pre-listing spinoff, highest-catalyst cohort; worth the deep-dive.

4. **Rank and rate.** Spawn one Agent per `band="deep"` or `band="unknown"` survivor, applying
   `reference/judgment-rubric.md` in full (including preamble: base-rate anchor +
   disconfirmation search + valuation + MoS check).
   The catalyst field in each record is pre-populated, the rubric's catalyst modifier
   (categories a and b) maps directly to spinoff and insider-cluster events respectively.
   **Catalyst re-verify (mandatory):** the pre-populated `catalyst` field is a
   discovery-stage hint (T2), NOT rubric-compliant evidence.  The agent MUST independently
   verify the forced-trading mechanism + T1 source (EDGAR 10-12B / Form 4) and re-populate
   the rubric catalyst field per `judgment-rubric.md`'s five-requirement checklist.
   **Catalyst MoS-waiver is FROZEN:** even a fully re-verified catalyst yields
   **WATCH-with-catalyst, not BUY**; it does not waive the MoS threshold. A BUY here still
   requires the MoS / NAV path AND `buy_eligible == true`. The freeze is deliberate and lifts only
   once catalyst mechanism-verification and a per-category Brier score exist.
   **No theme-fit gate:** skip Gate 1 (SIC) and Gate 2 (LLM theme-fit), form-type
   precision replaces keyword precision. Event admission still validates source evidence and mandatory cheap-pass outcomes; a discovered record alone does not prove completed screening.

5. **Output.** Ranked shortlist per `tools/rank.py --slug event_<mode>`.

---

## Two-Stage Precision Gate (Mandatory in Theme Flow)

Theme runs must complete both stages in order. Gate 1 tags SIC context and forwards every
`keep` and `review` candidate; Gate 2 classifies the selected annual filing's business as
`pure_play`, `partial` or `misrecall`. Only `misrecall` is excluded for theme fit. Stop if a
hard-excluded SIC disappears before Gate 2.

[Discovery engine](reference/discovery-engine.md) owns SIC defaults, the opt-in reverse-recall
union, the 1000-hit FTS cap, sidecar isolation, keyword design and coverage limits. Use the
bound request/host/result sequence in [theme-run.md](runbooks/theme-run.md); an unbound
classification list does not complete the stage. Ticker and event entries do not use these
theme gates.

---

## Rating Hard-Rules

> **`reference/judgment-rubric.md` is the single source of truth for every rating rule.** It holds
> the required preamble, the 7-dimension scorecard, the `buy_eligible` mechanical gate, the CORE-4
> PIT distress kill-flag, the three-way `mos_basis` decision tree, the catalyst modifier, the
> 35-row hard-rules table, the evidence tiers, and the report output template. Read it before
> rating anything; do not rate from a summary.

The rating is mechanical: **rating = f(MoS / NAV MoS, kill-flags, hard-ceilings, `buy_eligible`)**.
The 7-dimension scorecard does not by itself produce the rating. Its total is a plain unweighted sum
of the 7 dimension scores (no per-dimension weights exist in the repo), reported as a /35 diagnostic
summary or rescaled 1 to 5 with one decimal, with ties broken by Dimension 1 (financial quality).

---

## Environment Prerequisites

Follow [CONFIG.md setup](CONFIG.md#first-time-setup-e3) before running tools. The selected
PRIVATE companion must have a committed HEAD and current visibility proof. Set its
`sec_user_agent`, then run `python scripts/verify_config.py --json`; blank or example identity
is NOT READY. This checks local prerequisites, not live provider or model availability.

Configuration and tracking use the same resolver. Alternate profiles require separate
PRIVATE worktree roots. The runtime accepts the documented configuration keys and scalar
environment overrides; it has no generic `--config` flag or inline JSON configuration.
Keep configuration and DATA versioned privately. [CONFIG.md](CONFIG.md) also defines output
artifact ownership and retention.

---

## Data-Source Reuse

Full routing guide, rate-limit discipline, blind spots, and anti-recursion rule:
`reference/data-sources.md`.

**Key routing decisions summarized:**

- **EDGAR** (EFTS + XBRL + Form 4): primary for all filing-derived data. `edgartools` wrapper
  handles rate discipline. Max 10 req/s, include User-Agent on every request.

- **market-intel catalog (optional read-only reuse):** when installed, read its source catalog
  for qualitative context such as competitor pricing, ticker sentiment, and industry news.
  Discover the available underlying tools in the current session and call them directly.
  Do not invoke `market-intel` as a skill. Record unavailable optional sources.

- **X sentiment:** consult the optional market-intel catalog's X/Twitter shard when available.
  Use a configured source only after checking current capability and credentials; otherwise
  use an available search source and label the coverage limitation. See
  `reference/data-sources.md` for catalog reuse and the no-recursion rule.

- **yfinance / openinsider:** convenience layers for market data and insider trades respectively.
  Both are free but fragile, label sources accordingly in reports.

---

## Track-forward (Phase 6, Calibration Feedback Loop)

Record every deep-dive verdict in the initialized PRIVATE companion. Follow
[track-forward.md](reference/track-forward.md) for recording, scoring, scorecards, review
receipts and the IWM benchmark. The resolver must never fall back to this public source.

Score only after each verdict's own horizon matures. The existing minimum of approximately
20 matured verdicts before considering rubric tuning is not evidence of adequate sample
size or predictive performance. Include scored, pending, unavailable and unreviewed coverage;
the full calibration conditions are in the reference.

Final recall and discovery recall measure different losses. Report their scope, historical
eligibility gaps, FTS caps and failed pages. Diagnostic `signals_snapshot` records retain their issuer, verdict
and artifact identities but do not change ratings, probabilities or scoring. Finalization
treats an observed Gate-2 `misrecall` exclusion as resolved; it requires neither manual
re-banding nor `--allow-missing`. Missing work must remain visible.
