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
> export SMALLCAP_RUN=$(python tools/new_run.py --label <theme-or-event>)
> # → all outputs now land in reports/smallcap/<date>_<label>/ with a _run.json manifest
> #   (records date, skill git commit, and the valuation config snapshot)
> ```
> Leaving `SMALLCAP_RUN` unset writes flat to `reports/smallcap/` (legacy behaviour).
>
> **Concurrency isolation.** Theme runs execute concurrently (the coverage harness fans out dozens
> of agents at once), so the two shared paths are namespaced per run rather than clobbered: the
> run-state file is **PID-unique / per-`SMALLCAP_RUN`**, the SIC-reverse-recall sidecar goes **under
> the active run/slug**. Full statement, war-story and file list: "Sidecar isolation" under
> "Two-Stage Precision Gate".

### Entry 1, `theme <主题>` (thematic universe screen)

**Use when:** you have an investment theme and want a ranked shortlist of small-cap pure-plays.

**Natural-language orchestration (primary path, works in any Claude Code session):**

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
   marks `rejected` on any name with a hard kill-flag (`going_concern`, `death_spiral`,
   `material_weakness` in the most recent filing period), two or more kill-flags, a cash-burn
   rejection, or a `kill` concentration. Rejected names never reach Gate 1 or the deep-dive.

   1c. **Gate 1, SIC coarse review.** Applied **inline by `run_theme.py`**, which imports
   `filter_by_sic.sic_classify` as a library and tags each survivor `sic_tier`.
   **`tools/filter_by_sic.py` is not a pipeline step and cannot be invoked as one, its only CLI is
   `--selftest`**, which runs the unit assertions and exits. Use `python tools/filter_by_sic.py
   --selftest` to verify the SIC logic, never to filter a candidate list.

2. **Gate 2, LLM theme-fit (mandatory, see next section).** Run the LLM theme-fit gate on every
   Gate 1 survivor (both `sic_tier="keep"` and `sic_tier="review"`) to classify each as
   `pure_play / partial / misrecall`. Drop `misrecall`. Retain `pure_play` and `partial` for
   deep-dive. Gate 2 is the only gate in the theme flow that removes a company for theme-fit.

3. **Deep-dive.** For surviving candidates, run `tools/deepdive_data.py --ticker <T>` to retrieve
   the full financial series, insider trade record, and disclosure timeline. Spawn one Agent per
   candidate, instructing it to apply the 7-dimension scorecard from `reference/judgment-rubric.md`,
   preamble first (base-rate anchor + disconfirmation search + staleness check + the
   `tools/valuation.py` run) before any scoring.

4. **Rank.** Run `tools/rank.py` on the scored outputs to produce the ranked shortlist.
   Report includes: gate survival counts, kill-flag eliminations, score distribution,
   top candidates with dimension scores, and explicit coverage gaps.

**Optional accelerator:** when the Workflow tool is available in the session, `workflows/theme-fit-gate.js`
automates Gate 2 fan-out and `workflows/deepdive-fanout.js` automates the parallel deep-dive step.
These are convenience wrappers, the natural-language orchestration above is the primary and always-runnable path.

---

### Entry 2, `ticker <代码> [--theme X]` (single-company deep-dive)

**Use when:** you have a specific ticker and want a rigorous, falsifiable deep-dive report.
Optionally pass `--theme X` to anchor the theme-fit scoring.

**Natural-language orchestration:**

1. **Mechanical de-risk first.** Run `tools/cheap_pass.py --ticker <代码>`. If any hard kill-flag
   fires, report the flag and stop, do not proceed to full deep-dive.

2. **Data pull.** Run `tools/deepdive_data.py --ticker <代码>` to retrieve financial series,
   insider trades, filing timeline, and kill-flag detail.

3. **Judgment pass.** Apply the 7-dimension scorecard from `reference/judgment-rubric.md` in full.
   Required preamble, all four steps: (a) state the reference-class base rates from
   `reference/cognitive-priors.md`; (b) run disconfirmation WebSearch; (c) check data staleness;
   (d) run `python tools/valuation.py --json <deepdive_json> --ticker <代码>` and record `mos_basis`,
   the MoS fields, `buy_eligible` and `buy_ineligible_reasons`. Nothing else in the pipeline runs
   it, and a rating without it has no margin of safety.

4. **Output.** Single-company report with dimension scores, evidence tier per claim, kill-flag
   detail, disconfirmation findings, and a composite rating with the hard-rule ceilings applied
   (`reference/judgment-rubric.md §Rating Hard-Rules`).

**Optional accelerator:** `workflows/deepdive-fanout.js` supports single-ticker mode.

---

### Entry 3, `rank` (re-rank existing scored outputs)

**Use when:** you have already run a theme screen and want to re-sort or re-weight an existing
scored candidate set without re-running discovery or deep-dive.

**Natural-language orchestration:**

1. Locate the existing scored output directory from a prior `theme` run.
2. Run `tools/rank.py [--slug <slug>] [--input <dir>]` to produce a ranked table.
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
   Output: `reports/smallcap/candidates_event_<mode>_<date>.json`, same shape as
   theme-mode `candidates_<slug>.json`.

2. **Kill-flag scan (mandatory).** Run `tools/cheap_pass.py --universe <candidates_json>`.
   Kill-flags (`going_concern`, `death_spiral`, `material_weakness`) apply identically to
   event candidates.  A compelling catalyst does not excuse a going-concern filing.

3. **Deep-dive data pull.** Run `tools/deepdive_data.py --candidates <candidates_json>`.
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
   precision replaces keyword precision; every record is a valid event by construction.

5. **Output.** Ranked shortlist per `tools/rank.py --slug event_<mode>`.

---

## Two-Stage Precision Gate (Mandatory in Theme Flow)

> Full spec: `reference/discovery-engine.md`. This section is a navigational summary only.

Single-keyword FTS over-recalls severely. Measured production result: 192 raw candidates for
"AI agent" → 13 true theme members after the gate (6.8% precision; 94% false-positives).

**The canonical cautionary case:** the keyword `refractory` was used for a railcar insulation
theme. In oncology, "refractory" means treatment-resistant cancer, the single-keyword search
swept the entire biotech sector. Zero of these were railcar companies. Gate 1 did not cut them:
a pharma SIC is in the hard-exclude list, so Gate 1 tags those names `review` and forwards them.
**Gate 2 is what cleared the field**, and skipping it would have sent the entire biotech sector to
the deep-dive queue. This is the case that shows why Gate 2 can never be skipped or merged into
Gate 1: Gate 1 has no power to remove a keyword hit.

**Gate 1, SIC coarse review + reverse-recall floor** (`filter_by_sic.sic_classify`, applied inline
by `tools/run_theme.py`). **Gate 1 never drops a company.** `sic_classify` is tri-state and returns
only two of its three values in the current configuration:
- `keep`, the SIC is not in the hard-exclude list. Passes to Gate 2 normally.
- `review`, the SIC **is** in the hard-exclude list (pharma, medical devices, finance, retail,
  toys; the blocks are listed in `discovery-engine.md §Gate 1`). The company is tagged
  `sic_tier="review"` and **still passes to Gate 2**, because a hard-exclude SIC on a company that
  already matched the theme keywords is a question for the LLM, not a verdict. TITN (SIC 5990,
  a farm-equipment dealer) and SNFCA (SIC 6199, a real deathcare segment) are why.
- `drop` is reserved for future explicit-drop logic and **`sic_classify` never returns it**. The
  `sic_tier != "drop"` filter in `run_theme.py` is therefore a no-op today.

Companies with no SIC on file: **keep** for Gate 2, do not auto-exclude. The hard-exclude list is
the config key **`sic_hard_exclude`** (a `string[]` of SIC prefixes; there is no key named
`sic_exclusion_blocks`). It is global, not per-theme: to run a theme against a different list, point
`$SMALL_CAP_DEEPDIVE_CONFIG_DIR` at a second config dir whose `config.json` sets its own
`sic_hard_exclude`. See `CONFIG.md`.

**Caller contract.** `sic_classify` does not itself check theme-keyword membership, so `review` is
safe to forward only because `run_theme.py` calls it on a post-FTS universe where every company is
already a keyword hit. A caller that skips the FTS pre-filter reopens the over-recall hole.

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

# 2. Configure the tool — OUTSIDE the repo.
# Your SEC User-Agent is your real name + email. It is yours, so it lives in the private config
# dir, never in the working tree. A "just fill in reference/config.json" step is how a real
# contact address once got committed here; the config now resolves from outside by design.
mkdir -p ~/.small-cap-deepdive-config
cp reference/config.example.json ~/.small-cap-deepdive-config/config.json
# Edit ~/.small-cap-deepdive-config/config.json: set "sec_user_agent" to "Your Name you@example.com".
# EDGAR requires a valid User-Agent on every request (format: "Name email"); omission causes 403.
# (Override the location with $SMALL_CAP_DEEPDIVE_CONFIG_DIR. The in-repo reference/config.json
#  fallback is GONE: discovery never lands in the repo, init_config.py refuses to write there, and
#  verify_config.py reports NOT INITIALIZED instead of pointing at a repo path.)
```

The `sec_user_agent` field is the only hard requirement. All other config keys have defaults
documented in `config.example.json`. Theme-specific overrides (SIC exclusion blocks, keyword
sets, market-cap ceiling) are set per-run via the `--config` flag or inline JSON.

---

## Data-Source Reuse

Full routing guide, rate-limit discipline, blind spots, and anti-recursion rule:
`reference/data-sources.md`.

**Key routing decisions summarized:**

- **EDGAR** (EFTS + XBRL + Form 4): primary for all filing-derived data. `edgartools` wrapper
  handles rate discipline. Max 10 req/s, include User-Agent on every request.

- **market-intel skill (read-only catalog reuse):** for commercial/market data that complements
  SEC filings, competitor pricing, X/Twitter sentiment on a specific company, industry news
  volume, invoke the `market-intel` skill rather than re-implementing source detection.
  This skill does not duplicate the market-intel source matrix; it reuses it.

- **X sentiment route (twitterapi.io ② route):** when X investor sentiment is needed for a
  specific ticker, use the market-intel skill's X-twitter domain shard (`reference/domains/x-twitter.md`
  in the market-intel repo). The twitterapi.io route ② is the recommended resale source when
  direct API access is not connected. See `reference/data-sources.md §X Sentiment` for the
  anti-recursion guardrail (do not re-invoke this skill from within market-intel).

- **yfinance / openinsider:** convenience layers for market data and insider trades respectively.
  Both are free but fragile, label sources accordingly in reports.

---

## Track-forward (Phase 6, Calibration Feedback Loop)

After any deep-dive run, log all verdicts so they can be scored against realized returns when
the horizon matures. This is the only way to determine if the rubric is correctly calibrated.

**Where the verdict log lives (read this before citing a path).** Verdicts and the generated
scorecard are **real-run output, so they are written OUTSIDE this repo**, never into it.
`tools/datadir.py:resolve_data_dir("small-cap-deepdive")` resolves the private store in this order:
`$SMALL_CAP_DEEPDIVE_DATA_DIR` → `~/.small-cap-deepdive-config/data/` → `~/.small-cap-deepdive-data/`
→ nothing, which raises `DataDirNotInitialized` with setup instructions. The files are
`<private data dir>/metrics/verdicts.jsonl` and `<private data dir>/metrics/scorecard.md`. There is
deliberately **no in-repo fallback**: an in-repo `metrics/verdicts.jsonl` is how hundreds of real
positions (ticker, entry date, entry price) once accumulated in a public repo, and a fallback into
the repo is not a convenience, it is the leak. The repo's own `metrics/` directory carries only the
two schema files `verdicts.jsonl.example` and `scorecard.md.example`, which are the shape you are
expected to produce.

**Operational steps:**

1. **After each deep-dive run:** record verdicts from the output JSON:
   ```bash
   python tools/track_forward.py --record reports/smallcap/deepdive_verdicts.json
   ```
   Or record a single verdict via CLI flags:
   ```bash
   python tools/track_forward.py --record --ticker EGAN --rating 观察 --theme aeromro \
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

5. **Recall@gold (P8), measure discovery recall, not just precision.** Precision at Gate 2 is
   directly observable (the 6.8%-precision FTS over-recall problem above); recall is not, and a
   manual blurb re-scan is not a measurement. `track_forward` computes **`recall@gold`** for any
   theme that has a hand-built gold true-member list: the fraction of gold members the discovery
   union (FTS ∪ SIC reverse-recall) actually recalled. Example gold list, deathcare:
   `{SCI, CSV, MATW, HI, STON, SNFCA}`. A miss in `recall@gold` is a direct discovery-floor failure,
   a true member the union never surfaced. `track_forward` **warns when the FTS arm hit the
   top-1000 cap**, because a capped FTS arm is the most likely cause of a sub-1.0 `recall@gold` and
   means the SIC reverse-recall floor should be carrying more of the load.

6. **Signals snapshot, track-forward-gated, NOT a calibration input.** When a verdict is recorded,
   `track_forward` snapshots the diagnostic `signals` into the verdict row under `signals_snapshot`
   (the P16 `divergence_label` plus a P17 ownership summary). The snapshot exists purely so
   per-signal predictive value can be calibrated later. It is **diagnostic-gated**: it does not
   change `implied_prob` or the rating, and no signal gates anything until it has accumulated its
   own Brier score. The firewall holds end-to-end, signals enter the record only as a
   future-calibration snapshot, never as a driver of the verdict they are stored alongside.

**Note:** Verdicts from 2026-06 runs mature in 2027-06. The correct scorecard state until then
is "0 scored, N pending, calibration unknown." This is not a bug; it is the honest state.

**Run finalization, a Gate-2 misrecall is resolved, not missing.** `finalize_run` reads the run's
`gate2_results.json` and treats names in the Gate-2 misrecall set as **resolved**, not "missing." A
`band=deep` candidate dropped at Gate 2 for theme-fit is an intentional, auditable exclusion, not a
forgotten deep-dive, so it does not count toward the "N missing" warning. The coverage denominator
is therefore genuine deep-dive coverage rather than the raw `band=deep` row count, and no manual
re-band or `--allow-missing` step is needed.
