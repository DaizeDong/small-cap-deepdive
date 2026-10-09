---
name: small-cap-deepdive
description: "Use to research neglected small-cap/microcap US equities by THEME or TICKER: SEC-filing universe, de-risk, falsifiable deep-dive DD, rank. NOT large-cap/quant/trading."
allowed-tools: Read, Glob, Grep, Bash, Agent, Skill, WebSearch, WebFetch
---

# small-cap-deepdive

A disciplined orchestration layer for neglected small-cap equity research. It does **only what no
plain web-search or LLM narrative pass can do**: enumerate the SEC-filing universe for a theme,
apply hard mechanical kill-flags before any qualitative judgment begins, run forced disconfirmation,
and produce a scored, ranked shortlist of candidates worth genuine attention.

---

## World-View (read before interpreting any output)

Four commitments govern every run. Full exposition and empirical citations: `reference/cognitive-priors.md`.

**1. 被忽视 ≠ 被低估 (Neglected does not equal undervalued).**
A company receiving zero analyst coverage has cleared a necessary but not sufficient condition.
Neglect is priced into small-caps efficiently, what creates inefficiency is delayed information
diffusion around a real fundamental change. Every output of this skill is a shortlist of companies
worth investigating, not a buy list.

**2. 热点主题 = 赌场 (Hot themes are the casino, not the edge).**
By the time a theme has a branded ETF and retail attention, the alpha has been captured.
Thematic ETF data (Ben-David et al. 2023) shows approximately -6% risk-adjusted annual returns
in the 5 years post-launch for themes that entered at peak popularity. The skill's value in a hot
theme is separating the handful of true industrial beneficiaries from the concept-players who
mentioned the theme keyword once in their investor-day deck.

**3. Edge = 纪律，不是叙事 (Edge is mechanical discipline, not narrative synthesis).**
The skill's advantage is systematic coverage (more companies than any human can read in the time
budget), consistent kill-flag application across all candidates, and elimination of human attention
bias. It has no advantage in judging founding teams, predicting market narrative resonance, or
forecasting macro catalysts. Do not ask it to do those things.

**4. 产出是避雷扫描器，不是买入清单 (Output is a landmine-scanner, not a buy list).**
A score-5 company at the top of the ranked output means it survived all kill flags, has real theme
exposure, and warrants full human due diligence. It does not mean buy it. The primary value of
this skill is in what it eliminates, the going-concern candidates, the death-spiral diluters, the
disclosure non-filers, before any analyst time is spent.

---

## Four Entry Workflows

> **Open a run batch first (all entries).** Before the first tool call of any run, open a
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
> **Concurrency isolation.** Theme runs execute concurrently (the coverage harness fans out dozens
> of agents at once), so the two shared paths are namespaced per run rather than clobbered: the
> run-state file is **PID-unique / per-`SMALLCAP_RUN`**, the SIC-reverse-recall sidecar goes **under
> the active run/slug**. Full statement, war-story and file list: "Sidecar isolation" under
> "Two-Stage Precision Gate".

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

**Use when:** you have already run a theme screen and want to re-sort or re-weight an existing
scored candidate set without re-running discovery or deep-dive.

**Natural-language orchestration:**

1. Locate the existing scored output directory from a prior `theme` run.
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

> Full spec: `reference/discovery-engine.md`. This section is a navigational summary only.

A full-text keyword hit does not establish theme membership. A filing can mention a term
in risk factors, customer industries, or logistics while its core business belongs elsewhere.
SIC provides a coarse review hint; the bound theme-fit stage must adjudicate each candidate.
Read the gate contract in `reference/discovery-engine.md` before choosing keywords.

**Gate 1, SIC coarse review + reverse-recall floor** (`filter_by_sic.sic_classify`, applied inline
by `tools/run_theme.py`).

RULE, and the only part of Gate 1 you need loaded to run one:

- **Gate 1 never drops a company.** It only tags `sic_tier`. Every survivor of Gate 1, `keep` and
  `review` alike, goes to Gate 2. If a run removes a name at Gate 1, that run is wrong.
- **Test:** a name whose SIC is hard-excluded must still appear in the Gate 2 input set. If it does
  not, stop and read `discovery-engine.md` §Gate 1 before continuing.
- Which SIC blocks are hard-excluded, why `review` is not a verdict, the caller contract that makes
  `review` safe to forward, and the `sic_hard_exclude` config key: `discovery-engine.md` §Gate 1.

**SIC reverse-recall floor (P8).** For a theme that maps to dedicated SIC code(s), SIC is not used
*only* as a precision coarse-review, it is also a recall **FLOOR**. `discover.py --sic-reverse`
enumerates every registrant in the theme's dedicated SIC code(s) (`filter_by_sic.THEME_SIC`) via
EDGAR browse-by-SIC, and UNIONs that set with the FTS keyword recall, tagging each row
`recall_channel` as `fts` / `sic_reverse` / `both`. A true member with the right SIC but an unlucky
keyword phrasing therefore cannot be lost by FTS recall alone. The union is the deep-dive universe,
still passed through Gate 2 for theme-fit. The floor is **opt-in** (the theme needs a `THEME_SIC`
entry and `discover.py` needs the flag) so a giant generic SIC is not enumerated on every run.
**FTS top-1000 cap warning:** EDGAR full-text search caps at 1000 hits, so on a broad keyword the
FTS arm may be truncated; the SIC reverse-recall arm is the floor that keeps recall from collapsing
under that cap, and `track_forward` warns when the FTS arm hit the cap.

**Sidecar isolation.** The SIC-floor sidecar file (the enumerated SIC candidate set the floor writes
alongside the FTS recall) is namespaced under the **active run/slug**, written into the current
`SMALLCAP_RUN` batch dir, slug-prefixed, never a fixed cross-theme path, and kept out of the
`candidates_*.json` glob. Without that namespacing a stale cross-theme `candidates_<other-theme>.json`
could land in the wrong run dir (a machinery run dir once picked up a 63-name
`candidates_railcar_leasing.json`, which `finalize_run` would then have falsely demanded reports
for). Each concurrent agent's floor output is isolated to its own run, and the run-state file is
per-`SMALLCAP_RUN` / PID-unique rather than a shared `/tmp` path that concurrent agents clobber.
Files: `tools/filter_by_sic.py` + `tools/_common.py` / `tools/new_run.py`.

**Gate 2, LLM Theme-Fit Gate**
For each Gate 1 survivor, prompt an LLM subagent with the company's 10-K business description.
Classify: `pure_play` / `partial` / `misrecall`. Use the prompt template in
`reference/discovery-engine.md §Gate 2`. Drop `misrecall` before any deep-dive computation.

Both gates are mandatory. Neither can be skipped or merged into a single pass.

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

Before running any tool, complete setup once:

```bash
# 1. Install Python dependencies
pip install -r tools/requirements.txt

# 2. Create or clone a PRIVATE companion before entering personal configuration.
gh repo create small-cap-deepdive-config --private
gh repo clone small-cap-deepdive-config "$HOME/.small-cap-deepdive-config"
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config"
python scripts/init_config.py
# After successful PRIVATE verification, set sec_user_agent in the private config.
python scripts/verify_config.py --json
# Commit and push config and runtime DATA in this PRIVATE companion.
```

Initialize the PRIVATE companion before running the tools. Set `sec_user_agent` there and
use the supported configuration keys and scalar environment overrides in `CONFIG.md`.
The runtime does not accept a generic `--config` flag or inline JSON configuration.

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

After any deep-dive run, log all verdicts so they can be scored against realized returns when
the horizon matures. This is the only way to determine if the rubric is correctly calibrated.

**Where the verdict log lives (read this before citing a path).** RULE: verdicts and the generated
scorecard are real-run output, so they are written **outside this repo**, never into it. Never write
a verdict to a repo-relative path, and never add an in-repo fallback if the resolver refuses.
**Test:** if a path you are about to write starts with this repo's directory, you have the wrong
path. The resolver, its exact search order, what it raises when uninitialized, and why the
no-fallback rule exists: `reference/track-forward.md` §Where the verdict log lives.

**Operational steps:**

1. **After each deep-dive run:** record verdicts from the output JSON:
   ```bash
   python tools/track_forward.py --record "${REPORTS_ROOT}/deepdive_verdicts.json"
   ```
   Or record a single verdict via CLI flags:
   ```bash
   python tools/track_forward.py --record --ticker "$TICKER" --rating 观察 --theme "$THEME" \
       --mos-pct null --mos-basis abstain --catalyst null
   ```

2. **Monthly (or ad hoc):** score matured verdicts (horizon elapsed) against realized prices:
   ```bash
   python tools/track_forward.py --score
   ```

3. **Generate calibration scorecard:**
   ```bash
   python tools/track_forward.py --scorecard   # writes <private data dir>/metrics/scorecard.md
   python tools/track_forward.py --status      # quick count summary
   ```

4. **Tune the rubric ONLY when ≥~20 verdicts have matured.** Before that threshold the
   calibration table is statistically meaningless. See `reference/track-forward.md` for
   the full Brier / calibration methodology and the benchmark choice rationale (IWM, not SPY).

5. **Recall@gold, keep final and discovery coverage separate.** `recall@gold` measures
   eligible gold members retained in the final candidate set. `discovery_recall_at_gold`
   measures eligible gold members surfaced by the observed discovery union. A final miss
   can come from discovery, market-evidence availability, or a downstream gate; use the
   reported loss attribution instead of labeling every miss a discovery failure.
   Unresolved historical eligibility remains unresolved and must not be counted as proven
   exclusion. Report FTS caps, failed pages, and any opt-in SIC reverse-recall coverage
   alongside both measures; neither measure proves an uncapped population census.

6. **Diagnostic signals remain inert.** Finalization writes a versioned
   `signals_snapshot` containing the diagnostic namespace, issuer and verdict
   identity, and the selected deepdive artifact's byte digest. Recording validates
   and retains that snapshot for future calibration. It never changes the rating,
   implied probability, or current scoring. Missing signals remain absent.

**Calibration remains unknown until supported outcomes exist.** Each verdict has its own
entry date and horizon. Report scored, pending, unavailable and unreviewed coverage from
the current private ledger; do not assume a cohort date or a fixed scorecard result.

**Run finalization, a Gate-2 misrecall is resolved, not missing.** `finalize_run` reads the run's
`gate2_results.json` and treats names in the Gate-2 misrecall set as **resolved**, not "missing." A
`band=deep` candidate dropped at Gate 2 for theme-fit is an intentional, auditable exclusion, not a
forgotten deep-dive, so it does not count toward the "N missing" warning. The coverage denominator
is therefore genuine deep-dive coverage rather than the raw `band=deep` row count, and no manual
re-band or `--allow-missing` step is needed.

Configuration and retention: [CONFIG.md](CONFIG.md). Shared DATA/CONFIG discovery, root-only profiles and required SEC identity readiness; output writers enforce source artifact ownership.
