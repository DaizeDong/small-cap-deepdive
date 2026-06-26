# small-cap-deepdive

Mechanically de-risk the SEC small-cap universe for a theme or ticker — kill the landmines, then deep-dive the survivors.

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange?style=flat)](https://docs.anthropic.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![De-risk Scanner](https://img.shields.io/badge/De--risk-Scanner-green?style=flat)](#-read-this-first--the-design-philosophy)
[![Depends](https://img.shields.io/badge/depends-edgartools%20MIT-green?style=flat)](https://github.com/dgunning/edgartools)
[![Languages](https://img.shields.io/badge/Languages-EN%20%2F%20CN-blue?style=flat)](#languages)
[![Roadmap](https://img.shields.io/badge/Roadmap-v0.3.3-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## ⭐ Read this first — the design philosophy

**Being neglected is not the same as being undervalued.**

Small-caps with zero analyst coverage have cleared a necessary but not sufficient condition.
Neglect is efficiently priced. What creates exploitable inefficiency is delayed information
diffusion around a real fundamental change. This tool exists to find companies where that
condition might hold — and to mechanically eliminate the ones where it cannot, before any
analyst time is spent.

**The output is a landmine-scanner, not a buy list.**

A company at the top of the ranked output means it survived all kill-flags, has genuine theme
exposure, and warrants full human due diligence. It does not mean buy it. The primary value is
in what the tool eliminates — going-concern candidates, death-spiral diluters, disclosure
non-filers — before any judgment begins.

**Zero buys is a feature, not a bug.**

If a theme produces no score-4+ candidates, the tool is telling you the small-cap universe
for that theme does not contain clean industrial beneficiaries at this time. That is a correct
and useful answer. A scanner that cannot say "nothing found" is not a scanner; it is a
narrative generator.

The one-sentence version: **the tool's edge is mechanical discipline applied consistently
across the full candidate set, not narrative synthesis on any individual company.** Every tool,
invariant, and hard rule in this repo exists because of four principles — root-cause design (not
symptom patching), Hybrid-not-thin (the data layer earns its keep), discipline-as-moat, and a
single source of truth in `reference/`.

📜 **[Read the full design philosophy → PHILOSOPHY.md](PHILOSOPHY.md)**

---

## What it is (and isn't)

Given an investment theme or a single ticker, the skill enumerates the SEC-filing universe,
applies hard mechanical kill-flags, runs falsifiable deep-dive due diligence with forced
disconfirmation, and ranks surviving candidates. What it does, step by step:

0. **Open a run batch** (`new_run.py`): every run writes into `reports/smallcap/<date>_<label>/`
   with a `_run.json` manifest (skill git commit + valuation config snapshot) so runs stay
   comparable across versions. `export SMALLCAP_RUN=$(python tools/new_run.py --label <theme>)`.

1. **Enumerates the SEC universe** for a theme using EDGAR full-text search (FTS), UNIONed with a
   **SIC reverse-recall floor** (`discover.py` + `filter_by_sic.py`) — for themes with a dedicated SIC
   code, every registrant in that SIC is enumerated so low-keyword-density true members aren't missed.
   Market cap is resolved with a fallback chain (SEC shares×price when yfinance is null); names that
   still can't be priced flow through as `band="unknown"` instead of being silently dropped.

2. **Two-stage precision gate (mandatory).** Gate 1 (`filter_by_sic.py`): coarse SIC-code
   exclusion of definitively off-theme sectors. Gate 2 (LLM): reads each company's 10-K
   business description and classifies it as `pure_play / partial / misrecall`. The
   canonical failure mode without this gate: keyword `refractory` for a railcar insulation
   theme swept the entire oncology biotech sector. Zero railcar companies. Recall is *measured*
   via `recall@gold` against hand-built true-member lists, not assumed.

3. **Mechanical de-risk** (`cheap_pass.py`): hard kill-flags from SEC filings — going-concern
   auditor paragraphs, death-spiral convertibles, ICFR material weaknesses, magnitude-based
   customer/government-program concentration. Eliminated companies do not proceed to judgment.

4. **Deep-dive data pull** (`deepdive_data.py`): XBRL financials (with EBIT concept cascade, debt
   and shares fallbacks), Form 4 insider trades, shelf/ATM status, dilution history, material event
   timeline. Data-integrity guards: debt-truncation, wrong-entity, low-revenue-loss, and a
   **second-source cross-check** (SEC vs yfinance — a >2.5× disagreement is flagged and blocks BUY).

5. **Valuation + mechanical `buy_eligible` gate** (`valuation.py`): reverse-DCF (normalized FCF),
   EV/EBITDA multiples, cyclical-trough EBITDA, and asset-heavy NAV path. A BUY requires
   `mos_basis∈{fcf_cap,nav}` AND margin of safety ≥ 30% AND **`buy_eligible == true`** AND 0
   kill-flags AND no T3 thesis. `buy_eligible` ANDs in every guard — extreme-MoS, large-cap-ceiling,
   FCF-sustainability, financial-SIC / insurance exclusion, debt-truncation, cross-source-mismatch,
   concentration-kill, and the **V-shape value-trap vetoes** (`fundamental_decline_flag` for monotone
   decline + `peak_contamination_flag` for trough→peak→rollover). Closed-list catalyst modifier
   (currently frozen to WATCH pending mechanism calibration).

6. **Forced-disconfirmation judgment**: base-rate priors anchored before scoring, mandatory
   disconfirmation WebSearch for each candidate, 7-dimension scorecard with hard ceiling rules.
   Evidence is tier-tagged (T1 first-party SEC filings / T2 independent third-party / T3 company-sourced); T3 evidence cannot support
   a buy recommendation.

7. **Finalize + rank** (`finalize_run.py`, `make_report.py`, `rank.py`): deterministic per-ticker
   reports with a data-quality **trust banner** under each rating, an auto-emitted verdict fed into the
   track-forward loop, and `RANKING.md` with funnel counts, kill-flag eliminations, and coverage gaps.

8. **Track-forward calibration** (`track_forward.py`): verdicts logged to `metrics/verdicts.jsonl`,
   Brier-scored vs IWM at maturity, with de-risk-native metrics (blowup-avoidance / downside-capture).

9. **Diagnostic signals — firewalled** (`signals.py`): a strictly diagnostic side-channel that
   measures the *delayed-information-diffusion* thesis — **price-divergence** (fundamental trajectory
   vs trailing price return → `unpriced_improvement` / `melting_ice_cube_priced` / `aligned`) and
   **ownership** (13D/13G + short interest). It **never** touches `buy_eligible` or the BUY decision;
   it is recorded for future per-signal calibration only.

**What it does not do:**

- Factor/quant screening or backtesting — empirical evidence that factor alpha evaporates
  net of transaction costs is baked into the design; that decision space is out of scope.
- Trading signals, execution, or portfolio management.
- Real-time data — all data is from SEC filings (1–4 day lag typical).
- Large-cap or sell-side coverage — the tool is calibrated for micro/small-cap names with
  no or minimal analyst coverage.
- Automated buy recommendations — every output ends with "merits human diligence," not "buy."

### Validated out-of-sample (2026-06)

A 25-cell survivorship-safe point-in-time backtest (5 themes × 5 as-of dates 2020–2024, 12mo
horizon) tested the skill's claims on held-out data. Honest result — write-up in
[`docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md`](docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md):

- **No durable alpha.** Cheapness (Margin-of-Safety) beats the market in-sample but it is a
  2020–21 recovery-regime artifact and vanishes out-of-sample (holdout permutation p=0.72). The
  tool **cannot pick market-beaters and does not claim to** — this is *why* it never issues a "buy."
- **A real downside-avoidance edge** (its actual mission). The OOS-validated **CORE-4 distress
  kill-flag** (operating-cash-flow loss, operating loss, accumulated deficit, Altman Z″ < 1.1)
  routes distressed names to AVOID with top-quintile blowup **lift 2.56×**, recall 62%, and a
  ticker-cluster bootstrap 95% CI on the lift of **[1.73, 3.00]** (P(lift≤1)=0). A 0-BUY scan is
  still valid; the value is in the landmines you *don't* step on.

---

## Install

```
/plugin install github:DaizeDong/small-cap-deepdive
```

Or clone manually:

```bash
git clone https://github.com/DaizeDong/small-cap-deepdive.git ~/.claude/plugins/small-cap-deepdive
```

Then install the data-layer dependencies and configure once:

```bash
cd ~/.claude/plugins/small-cap-deepdive
pip install -r tools/requirements.txt
cp reference/config.example.json reference/config.json
```

Open `config.json` and set `"sec_user_agent"` to your real name and email:

```json
"sec_user_agent": "Jane Smith jane@example.com"
```

This is the only required field. EDGAR requires a valid `User-Agent` header on every request
(SEC policy). Omitting it or using a fake value causes 403 errors from `efts.sec.gov`.

To use the skill from Claude Code via a junction (Windows) or symlink instead of `/plugin install`:

```bash
# Windows (run as Administrator)
cmd /c mklink /J "%USERPROFILE%\.claude\skills\small-cap-deepdive" "skills\small-cap-deepdive"

# macOS / Linux
ln -s "$(pwd)" "$HOME/.claude/skills/small-cap-deepdive"
```

---

## Config

`small-cap-deepdive` is **config-bearing** — every tool reads its tuning parameters and the one
required EDGAR identity (`sec_user_agent`) from a JSON config. Full field-by-field contract:
[CONFIG.md](CONFIG.md).

- **Mount (discovery order):** `$SMALL_CAP_DEEPDIVE_CONFIG_DIR/config.json` → `$SMALL_CAP_DEEPDIVE_CONFIG/config.json`
  → `~/.small-cap-deepdive-config/config.json` → `~/.config/small-cap-deepdive-config/config.json` →
  in-repo `reference/config.json` (zero-config default). First that exists wins; effective config =
  `config.example.json` defaults ◁ your `config.json` ◁ `SMALLCAP_*` env overrides.
- **First time:**
  ```bash
  python scripts/init_config.py      # stamp config.json from the example template (deterministic)
  # edit config.json: set "sec_user_agent" to your real name + email (the only hard requirement)
  python scripts/verify_config.py    # doctor: PASS/FAIL per field, names what is missing
  ```
- **Switch configs (hot-swap):** point the env var at another config dir — configs are self-contained
  (repo-relative `output_dir`, no hardcoded paths): `export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/configs/A` ↔ `~/configs/B`.
- **Secrets / PII:** Mode B — `config.json`, `*.env`, and `secrets/*` are gitignored and never enter
  git. Point `$SMALL_CAP_DEEPDIVE_CONFIG_DIR` at a dir **outside** this repo for full repo separation.

---

## Quick start

> **Open a run batch first** (any mode): `export SMALLCAP_RUN=$(python tools/new_run.py --label <name>)`
> routes all outputs into `reports/smallcap/<date>_<name>/` with a `_run.json` manifest (skill commit +
> config) so runs are reproducible and comparable across versions. Unset = flat (legacy).

There are four entry modes.

### 1. Theme run — full universe screen

For a ranked shortlist of small-cap pure-plays in a theme:

```
/small-cap-deepdive theme "railcar leasing"
```

Full step-by-step: **[runbooks/theme-run.md](runbooks/theme-run.md)**

Expected token budget: ~300k tokens, ~$0.30, 1–3 hours for a niche theme.

### 2. Single-ticker deep-dive

For a rigorous report on a company you already know:

```
/small-cap-deepdive ticker EGAN
/small-cap-deepdive ticker EGAN --theme "SaaS for regulated industries"
```

Full step-by-step: **[runbooks/single-deepdive.md](runbooks/single-deepdive.md)**

Expected token budget: ~10k–15k tokens per company, <$0.02.

### 3. Re-rank existing scores

To re-sort or re-weight a prior run's outputs without re-running discovery:

```bash
python tools/rank.py
python tools/rank.py --slug railcar
python tools/rank.py --input reports/railcar_scores/
```

Full step-by-step: **[runbooks/batch-rank.md](runbooks/batch-rank.md)**

Expected token budget: Zero — deterministic, no LLM calls.

### 4. Event-driven discovery — spinoffs or insider clusters

For theme-independent discovery via structural catalysts (forced trading):

```bash
# Enumerate recent spinoff registrations (Form 10-12B)
python tools/discover_events.py --spinoffs

# Enumerate cluster open-market insider buys (openinsider)
python tools/discover_events.py --insider-clusters
```

Spinoff catalyst: passive index-fund holders of the parent are forced to sell the spun-off
child if it falls outside their index mandate — temporary supply overhang, no natural buyer.

Insider-cluster catalyst: multiple insiders purchasing at market price with personal capital
is the strongest available management-conviction signal (Form 4, open-market cash only).

No theme-fit gate needed — form-type enumeration is structurally precise. Kill-flag scan
still mandatory (`cheap_pass.py --universe <candidates_event_*.json>`). Pre-listing spinoffs
(no ticker yet) are processed via CIK, in the `band="unknown"` cohort.

Expected token budget: ~300k tokens for a full event-mode run with deep-dives.

---

## How to invoke

Use the slash command in any mode, e.g. `/small-cap-deepdive theme "railcar leasing"` or
`/small-cap-deepdive ticker EGAN`. Or trigger it with natural language in any Claude Code
session:

```
Run small-cap-deepdive on the theme "railcar leasing"
Deep-dive EGAN as a small-cap with small-cap-deepdive
Screen the small-cap SEC universe for "industrial water treatment"
```

The skill triggers on small-cap / microcap value research, thematic stock screening, and
single-company deep DD. It does **not** trigger for large-cap / sell-side coverage,
factor/quant screening, trading signals, or execution.

---

## Example output

Each candidate is rated mechanically. The scorecard quick reference:

| Score | Meaning | Action |
|---|---|---|
| 4–5 | Survived all gates, real theme exposure, no structural red flags | Merits full human diligence |
| 3 | Borderline — one weak dimension | Read dimension detail before deciding |
| 1–2 | Hard-rule ceiling applied | Named structural problem; do not invest without resolving it |
| Eliminated | Kill-flag fired at `cheap_pass` | Stop — do not re-examine |

The rating is mechanical: `rating = f(MoS / NAV-MoS, kill-flags, hard-ceilings, buy_eligible)`. The
7-dimension scorecard is a diagnostic `/35` summary (no hidden weights), not the rating driver; hard
ceiling rules override narrative quality. Full rubric: `reference/judgment-rubric.md`.

A theme run finalizes into deterministic per-ticker reports plus a `RANKING.md` with funnel
counts, kill-flag eliminations, and coverage gaps.

### Architecture

```
bundled data layer (deterministic Python — never makes investment judgments)
  tools/_common.py       — config, EDGAR session, per-tool sleep + http_get retry/backoff, batch routing
  tools/new_run.py       — open a timestamped run batch + _run.json manifest
  tools/discover.py      — EDGAR FTS enumeration + SIC reverse-recall + mktcap fallback
  tools/filter_by_sic.py — Gate 1 coarse SIC exclusion + SIC reverse-recall floor
  tools/cheap_pass.py    — mechanical kill-flags from SEC filings (incl. concentration)
  tools/deepdive_data.py — XBRL + Form 4 + shelf status + data-integrity guards + second-source check
  tools/valuation.py     — reverse-DCF / NAV / EV-EBITDA + the buy_eligible mechanical gate
  tools/discover_events.py — event-driven discovery (spinoffs / insider clusters)
  tools/finalize_run.py  — deterministic run-finalizer (reports + verdicts + RANKING)
  tools/make_report.py   — deterministic report scaffolder + data-quality trust banner
  tools/rank.py          — deterministic scoring and ranking
  tools/track_forward.py — verdict log, Brier vs IWM, de-risk metrics, recall@gold
  tools/run_theme.py     — end-to-end theme driver (calls the above)

diagnostic side-channel (firewalled — recorded, never drives BUY)
  tools/signals.py       — price-divergence (P16) + ownership (P17); measures the diffusion thesis

thin judgment layer (LLM — reads JSON, applies rubric, never computes financials)
  SKILL.md          — orchestration + world-view + hard rules
  reference/*.md    — methodology invariants (single source of truth)
  workflows/theme-fit-gate.js  — optional: parallel Gate 2 fan-out accelerator
  workflows/deepdive-fanout.js — optional: parallel deep-dive accelerator
```

**Two firm boundaries.** (1) `tools/*.py` never produces investment judgments (only data); the
judgment layer never computes financials (only reads JSON). (2) The diagnostic `signals` layer is
firewalled — `valuation.py` / `buy_eligible` / the BUY trigger contain **zero** references to any
signal (`buy_eligible` is byte-identical with vs without signals). The data/judgment split was
validated across two production-bug rounds (all bugs were in the data layer, contained by the
boundary); the signals firewall was grep-verified each iteration.

---

## Limitations

**Dependencies.** No proprietary dependencies; no API keys required for the core data layer.

| Package | License | Purpose |
|---|---|---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | EDGAR FTS, XBRL parsing, Form 4 retrieval |
| yfinance | Apache 2.0 | Market cap / price convenience layer |
| pandas | BSD | Data processing |
| requests | Apache 2.0 | HTTP with EDGAR rate discipline |

**market-intel (optional read-only reuse):** When the `market-intel` skill is installed, the
judgment layer reads its source catalog to route qualitative research (X sentiment, industry
news, competitor web presence) to the best available MCP tool. The market-intel skill is never
invoked as a skill at runtime — the catalog is read as documentation. Full anti-recursion
design: `reference/data-sources.md §market-intel`.

**openinsider fragility:** The default `insider_source` config uses `openinsider.com` for
Form 4 direction parsing. This is a third-party service with no explicit automated-access
terms. The tool automatically falls back to direct EDGAR Form 4 parsing when openinsider is
unavailable. Reports label the source accordingly. To default to EDGAR Form 4 from the start,
set `"insider_source": "edgar"` — but note that mode is a **roadmap stub, not yet implemented**
(returns `available: false`); the tested default is `openinsider`. See
`reference/data-sources.md` for the fallback behaviour.

**workflow .js files are optional:** `workflows/theme-fit-gate.js` and
`workflows/deepdive-fanout.js` accelerate fan-out steps when Claude Code's Workflow tool is
available in the session. They are not required — the natural-language orchestration in
`SKILL.md` is the primary path and works in any Claude Code session.

**X sentiment routing:** When X/Twitter sentiment is requested for a ticker, the skill routes
to twitterapi.io (resale API) if the key is configured via the market-intel companion
config. If unavailable, it falls back to search-engine-indexed X posts. The user's personal
X/Twitter account is never used (account suspension risk).

---

## Languages

English (`README.md`, authoritative) · 中文 ([`README_CN.md`](README_CN.md))

---

## Roadmap · Contributing · License

See [ROADMAP.md](ROADMAP.md) · [PHILOSOPHY.md](PHILOSOPHY.md) · [CHANGELOG.md](CHANGELOG.md) · [LICENSE](LICENSE) (MIT).

Contributing: see the design spec in `docs/` for architectural invariants. The core invariant
is the data/judgment boundary: the data layer (`tools/*.py`) never produces investment judgment;
the judgment layer never computes financials. Changes that blur this boundary require explicit
justification in [PHILOSOPHY.md](PHILOSOPHY.md).
