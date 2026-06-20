---
name: small-cap-deepdive
description: >-
  Use when researching neglected SMALL-CAP US equities for a given investment THEME or a single
  TICKER — enumerate the theme's small-cap universe from SEC filings, mechanically de-risk
  (going-concern / death-spiral / material-weakness), then run disciplined, falsifiable
  deep-dive due diligence with forced disconfirmation and base-rate priors, and rank. Triggers
  on small-cap/microcap value research, thematic stock screening, single-company deep DD.
  NOT for large-cap/sell-side coverage, factor/quant screening, trading signals, or execution.
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
Neglect is priced into small-caps efficiently — what creates inefficiency is delayed information
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
this skill is in what it eliminates — the going-concern candidates, the death-spiral diluters, the
disclosure non-filers — before any analyst time is spent.

---

## Four Entry Workflows

### Entry 1 — `theme <主题>` (thematic universe screen)

**Use when:** you have an investment theme and want a ranked shortlist of small-cap pure-plays.

**Natural-language orchestration (primary path, works in any Claude Code session):**

1. **Universe enumeration.** Run `tools/discover.py --theme "<主题>"` to query SEC EDGAR full-text
   search and return candidate tickers. This over-recalls by design — expect hundreds of results.

2. **Two-stage precision gate (mandatory — see next section).** Pass the raw list through
   `tools/filter_by_sic.py` (Gate 1, coarse SIC exclusion), then run the LLM theme-fit gate
   (Gate 2) on surviving candidates to classify each as `pure_play / partial / misrecall`.
   Drop `misrecall`. Retain `pure_play` and `partial` for deep-dive.

3. **Mechanical de-risk.** For each retained candidate, run `tools/cheap_pass.py --ticker <T>`.
   Any candidate that returns a hard kill-flag (`going_concern`, `death_spiral`, `material_weakness`
   in the most recent filing period) is eliminated. Do not deepdive eliminated candidates.

4. **Deep-dive.** For surviving candidates, run `tools/deepdive_data.py --ticker <T>` to retrieve
   the full financial series, insider trade record, and disclosure timeline. Spawn one Agent per
   candidate, instructing it to apply the 7-dimension scorecard from `reference/judgment-rubric.md`
   — preamble (base-rate anchor + disconfirmation search + staleness check) before any scoring.

5. **Rank.** Run `tools/rank.py` on the scored outputs to produce the ranked shortlist.
   Report includes: gate survival counts, kill-flag eliminations, score distribution,
   top candidates with dimension scores, and explicit coverage gaps.

**Optional accelerator:** when the Workflow tool is available in the session, `workflows/theme-fit-gate.js`
automates Gate 2 fan-out and `workflows/deepdive-fanout.js` automates the parallel deep-dive step.
These are convenience wrappers — the natural-language orchestration above is the primary and always-runnable path.

---

### Entry 2 — `ticker <代码> [--theme X]` (single-company deep-dive)

**Use when:** you have a specific ticker and want a rigorous, falsifiable deep-dive report.
Optionally pass `--theme X` to anchor the theme-fit scoring.

**Natural-language orchestration:**

1. **Mechanical de-risk first.** Run `tools/cheap_pass.py --ticker <代码>`. If any hard kill-flag
   fires, report the flag and stop — do not proceed to full deep-dive.

2. **Data pull.** Run `tools/deepdive_data.py --ticker <代码>` to retrieve financial series,
   insider trades, filing timeline, and kill-flag detail.

3. **Judgment pass.** Apply the 7-dimension scorecard from `reference/judgment-rubric.md` in full.
   Required preamble: (a) state the reference-class base rates from `reference/cognitive-priors.md`;
   (b) run disconfirmation WebSearch; (c) check data staleness.

4. **Output.** Single-company report with dimension scores, evidence tier per claim, kill-flag
   detail, disconfirmation findings, and a composite rating with the hard-rule ceiling applied
   (see Rating Hard-Rules below).

**Optional accelerator:** `workflows/deepdive-fanout.js` supports single-ticker mode.

---

### Entry 3 — `rank` (re-rank existing scored outputs)

**Use when:** you have already run a theme screen and want to re-sort or re-weight an existing
scored candidate set without re-running discovery or deep-dive.

**Natural-language orchestration:**

1. Locate the existing scored output directory from a prior `theme` run.
2. Run `tools/rank.py [--slug <slug>] [--input <dir>]` to produce a ranked table.
3. Report the ranking with kill-flag eliminations and explicit coverage gaps.

---

### Entry 4 — `events <spinoffs|insider-clusters>` (event-driven discovery)

**Use when:** you want to hunt for mis-priced small-caps via a structural catalyst rather than a
theme keyword.  Two event axes are supported; both are structurally high-precision (no
theme-fit gate needed — form-type enumeration replaces keyword over-recall):

- `spinoffs` — enumerate recent **Form 10-12B / 10-12B/A** registrations (spinoff / carve-out).
  Catalyst: passive index-fund holders of the parent are forced to sell the spun-off child if it
  falls outside their index mandate.  This forced-selling window is the mis-pricing mechanism.

- `insider-clusters` — enumerate recent **cluster open-market insider buys** from
  openinsider.com.  Catalyst: multiple insiders buying at market price within a short window
  is the strongest available management-conviction signal (Form 4, open-market cash only).

**Rationale and honest caveats:** `reference/event-driven.md`.

**Natural-language orchestration:**

1. **Enumerate the event.** Run `tools/discover_events.py --spinoffs` or
   `tools/discover_events.py --insider-clusters`.
   Output: `reports/smallcap/candidates_event_<mode>_<date>.json` — same shape as
   theme-mode `candidates_<slug>.json`.

2. **Kill-flag scan (mandatory).** Run `tools/cheap_pass.py --universe <candidates_json>`.
   Kill-flags (`going_concern`, `death_spiral`, `material_weakness`) apply identically to
   event candidates.  A compelling catalyst does not excuse a going-concern filing.

3. **Deep-dive data pull.** Run `tools/deepdive_data.py --candidates <candidates_json>`.
   **Band guard (four explicit bands — C3):**
   - `band="deep"` (mktcap < market_cap_max): **process** — full deep-dive.
   - `band="watch"` (market_cap_max..watch_band_max): **skip** — surfaced separately for human review only; not deep-dived.
   - `band="large"` (> watch_band_max): **skip** — out of scope.
   - `band="unknown"` (mktcap unavailable / pre-listing): **process** — likely a pre-listing spinoff, highest-catalyst cohort; worth the deep-dive.

4. **Rank and rate.** Spawn one Agent per `band="deep"` or `band="unknown"` survivor, applying
   `reference/judgment-rubric.md` in full (including preamble: base-rate anchor +
   disconfirmation search + valuation + MoS check).
   The catalyst field in each record is pre-populated — the rubric's catalyst modifier
   (categories a and b) maps directly to spinoff and insider-cluster events respectively.
   **Catalyst re-verify (mandatory):** the pre-populated `catalyst` field is a
   discovery-stage hint (T2), NOT rubric-compliant evidence.  The agent MUST independently
   verify the forced-trading mechanism + T1 source (EDGAR 10-12B / Form 4) and re-populate
   the rubric catalyst field per `judgment-rubric.md`'s five-requirement checklist before
   the catalyst BUY modifier may apply.
   **No theme-fit gate:** skip Gate 1 (SIC) and Gate 2 (LLM theme-fit) — form-type
   precision replaces keyword precision; every record is a valid event by construction.

5. **Output.** Ranked shortlist per `tools/rank.py --slug event_<mode>`.

---

## Two-Stage Precision Gate (Mandatory in Theme Flow)

> Full spec: `reference/discovery-engine.md`. This section is a navigational summary only.

Single-keyword FTS over-recalls severely. Measured production result: 192 raw candidates for
"AI agent" → 13 true theme members after the gate (6.8% precision; 94% false-positives).

**The canonical cautionary case:** the keyword `refractory` was used for a railcar insulation
theme. In oncology, "refractory" means treatment-resistant cancer — the single-keyword search
swept the entire biotech sector. Zero of these were railcar companies. Only the SIC coarse gate
and LLM theme-fit gate cleared the field. Skipping either gate would have sent the entire biotech
sector to the deep-dive queue.

**Gate 1 — SIC Coarse Exclusion** (`tools/filter_by_sic.py`)
Drops companies whose SIC code definitively places them outside plausible theme membership.
Hard-coded default exclusion blocks (pharma, medical devices, finance, retail, toys) are in
`discovery-engine.md §Gate 1`. Override per-theme via `sic_exclusion_blocks` in `config.json`.
Companies with no SIC on file: **keep** for Gate 2 — do not auto-exclude.

**Gate 2 — LLM Theme-Fit Gate**
For each Gate 1 survivor, prompt an LLM subagent with the company's 10-K business description.
Classify: `pure_play` / `partial` / `misrecall`. Use the prompt template in
`reference/discovery-engine.md §Gate 2`. Drop `misrecall` before any deep-dive computation.

Both gates are mandatory. Neither can be skipped or merged into a single pass.

---

## Rating Hard-Rules Quick Reference

> Full scoring rubric, evidence-tier definitions, and output template: `reference/judgment-rubric.md`.
> Authoritative source for all rules below is `reference/judgment-rubric.md`; this section is a navigational subset.

### Symmetric BUY Trigger (Phase 3) — three-way `mos_basis` handling

Run `python tools/valuation.py` before rating; read `mos_basis`, `margin_of_safety_pct`, `nav_margin_of_safety_pct`.

| `mos_basis` | BUY condition | Notes |
|---|---|---|
| `fcf_cap` | `margin_of_safety_pct ≥ 30%` AND kill-flags = 0 AND no T3 thesis | Full confidence weight 1.0; capped by data_quality flags |
| `nav` | `nav_margin_of_safety_pct ≥ 30%` AND kill-flags = 0 AND no T3 thesis | Multiply raw conviction by 0.6 before recording `confidence` field; surface as "asset-heavy / NAV basis" |
| `abstain` | No MoS BUY/AVOID trigger; rank on EV/EBITDA + EV/Sales only | Never penalize for model mismatch |

**Catalyst modifier (closed enumerated list — no other types qualify):** (a) spinoff filing Form 10-12B/15-12B with documented index-fund forced-selling mechanism; (b) cluster open-market insider purchases Form 4 ≥2–3 insiders within 90 days, cash purchases only — not option exercises/grants; (c) court-ordered asset sale or special distribution per 8-K with scheduled completion date; (d) exchange delisting-avoidance / deficiency event per 8-K creating forced selling. Each requires a dated trigger. Earnings guidance, product launches, customer wins, and any organic-growth narrative do NOT qualify. Populate `catalyst` field with category, T1 source, and dated trigger; null otherwise.

**Perpetual-veto prohibition:** "cyclical turn not yet realized in T1" may NOT veto a BUY when MoS ≥ 30%. Normalized FCF already accounts for cycle conservatism.

### Downward Hard-Ceilings

These are hard ceilings and floors — they override dimension scores and cannot be argued away
by narrative quality or management explanation:

| Condition | Hard rule |
|---|---|
| `going_concern` flag in most recent 10-K or 10-Q | **Eliminate before deep-dive** (cheap_pass gate) |
| `death_spiral` convertible detected | **Dim 1 capped at 1**, composite max = 2 |
| `material_weakness` in ICFR | **Dim 1 (financial quality) capped at 2** |
| Net income driven by deferred tax release (not OCF) | **Score Dim 1 on OCF only**; note the driver |
| AR growing faster than revenue | **Required red flag note** in Dim 1 basis |
| S-3 shelf / ATM program active with < 4Q runway | **Dim 1 score = 1** |
| Single customer > 40% of revenue | **Dim 3 capped at 2** |
| `insider_net_sell` strongly negative AND dilution rate ≥ 15%/yr | **Dim 4 capped at 2** |
| Critical data unavailable (runway, revenue, insider trades all null) | **Confidence capped at 40%** |
| Company has no current theme revenue (pure concept-playing) | **Theme-fit dimension capped at 2**; cannot rate BUY |
| Rating is AVOID OR kill-flag count ≥ 3 | **Sinks to bottom of ranking** |

Full hard-rule source of truth: `reference/judgment-rubric.md §Rating Hard-Rules`.

Composite score = weighted average of 7 dimensions (weights in `reference/judgment-rubric.md`).
Final composite is reported as 1–5 with one decimal. Ties broken by Dimension 1 (financial quality).

---

## Environment Prerequisites

Before running any tool, complete setup once:

```bash
# 1. Install Python dependencies
pip install -r tools/requirements.txt

# 2. Configure the tool
# A fresh clone has NO config.json — copy the example and fill in your details:
cp reference/config.example.json reference/config.json
# Edit config.json: set "sec_user_agent" to your real name and email address.
# EDGAR requires a valid User-Agent header on every request (format: "Name email@domain.com").
# Omission causes 403 errors. This is the only required config field.
# config.json is gitignored — it stays local and is never committed to the repo.
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
  SEC filings — competitor pricing, X/Twitter sentiment on a specific company, industry news
  volume — invoke the `market-intel` skill rather than re-implementing source detection.
  This skill does not duplicate the market-intel source matrix; it reuses it.

- **X sentiment route (twitterapi.io ② route):** when X investor sentiment is needed for a
  specific ticker, use the market-intel skill's X-twitter domain shard (`reference/domains/x-twitter.md`
  in the market-intel repo). The twitterapi.io route ② is the recommended resale source when
  direct API access is not connected. See `reference/data-sources.md §X Sentiment` for the
  anti-recursion guardrail (do not re-invoke this skill from within market-intel).

- **yfinance / openinsider:** convenience layers for market data and insider trades respectively.
  Both are free but fragile — label sources accordingly in reports.

---

## Track-forward (Phase 6 — Calibration Feedback Loop)

After any deep-dive run, log all verdicts so they can be scored against realized returns when
the horizon matures. This is the only way to determine if the rubric is correctly calibrated.

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
   python tools/track_forward.py --scorecard   # writes metrics/scorecard.md
   python tools/track_forward.py --status      # quick count summary
   ```

4. **Tune the rubric ONLY when ≥~20 verdicts have matured.** Before that threshold the
   calibration table is statistically meaningless. See `reference/track-forward.md` for
   the full Brier / calibration methodology and the benchmark choice rationale (IWM, not SPY).

**Note:** Verdicts from 2026-06 runs mature in 2027-06. The correct scorecard state until then
is "0 scored, N pending — calibration unknown." This is not a bug; it is the honest state.
