# small-cap-deepdive

Mechanically de-risk the SEC small-cap universe for a theme or ticker, kill the landmines, then deep-dive the survivors.

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange?style=flat)](https://docs.anthropic.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![De-risk Scanner](https://img.shields.io/badge/De--risk-Scanner-green?style=flat)](#-read-this-first--the-design-philosophy)
[![Depends](https://img.shields.io/badge/depends-edgartools%20MIT-green?style=flat)](https://github.com/dgunning/edgartools)
[![Languages](https://img.shields.io/badge/Languages-EN%20%2F%20CN-blue?style=flat)](#languages)
[![Roadmap](https://img.shields.io/badge/Roadmap-v0.3.3-purple?style=flat)](ROADMAP.md)

[English](README.md) | [中文版](README_CN.md)

---

## ⭐ Read this first, the design philosophy

**Being neglected is not the same as being undervalued.**

Why that is true, and what it takes for a neglected name to also be mis-priced:
[`reference/cognitive-priors.md`](reference/cognitive-priors.md) §1.

**The output is a landmine-scanner, not a buy list.**

What a top-ranked name does and does not entitle you to conclude:
[`reference/cognitive-priors.md`](reference/cognitive-priors.md) §5.

**An empty result is limited to the observed screen.**

If no candidate reaches score 4 or higher, report that result with the retrieved population, missing
work, coverage limits and rating policy. It does not establish that the theme has no clean
beneficiaries or investment opportunities. Incomplete retrieval and model abstention must
remain visible alongside the candidate count.

The one-sentence version: **the tool's edge is mechanical discipline applied consistently
across the full candidate set, not narrative synthesis on any individual company.** Every tool,
invariant, and hard rule in this repo exists because of four principles, root-cause design (not
symptom patching), Hybrid-not-thin (the data layer earns its keep), discipline-as-moat, and a
single source of truth in `reference/`.

📜 **[Read the full design philosophy → PHILOSOPHY.md](PHILOSOPHY.md)**

---

## What it is (and isn't)

Given an investment theme or a single ticker, the skill enumerates the SEC-filing universe,
applies hard mechanical kill-flags, runs falsifiable deep-dive due diligence with forced
disconfirmation, and ranks surviving candidates. What it does, step by step:

0. **Open a run batch** (`new_run.py`): every run writes into the initialized PRIVATE companion's
   `reports/smallcap/<date>_<label>/` directory
   with a `_run.json` manifest (skill git commit + valuation config snapshot) so runs stay
   comparable across versions. Stop if allocation fails, then export the returned selector:

   ```bash
   SMALLCAP_RUN="$(python tools/new_run.py --label "Synthetic research")" || exit 1
   export SMALLCAP_RUN
   ```

1. **Enumerates the SEC universe** for a theme using EDGAR full-text search (FTS), optionally
   UNIONed with a **SIC reverse-recall floor** (`discover.py --sic-reverse`, which calls into
   `filter_by_sic.py`): for a theme with a dedicated SIC code, every registrant in that SIC is
   enumerated so low-keyword-density true members are not missed. The floor is opt-in per theme.
   Market cap is resolved with a fallback chain (SEC shares×price when yfinance is null); names that
   still can't be priced flow through as `band="unknown"` instead of being silently dropped.

2. **Mechanical de-risk** (`cheap_pass.py`): hard kill-flags from SEC filings, going-concern
   auditor paragraphs, death-spiral convertibles, ICFR material weaknesses, magnitude-based
   customer/government-program concentration. Eliminated companies do not proceed to judgment.

3. **Two-stage precision gate (mandatory).** Gate 1 (`filter_by_sic.sic_classify`, applied inline by
   `run_theme.py`): a coarse SIC **review tier**, not an exclusion. A hard-excluded SIC tags the
   company `sic_tier="review"` and it still passes to Gate 2; Gate 1 never drops anything. Gate 2
   (LLM) reads each company's 10-K business description and classifies it `pure_play / partial /
   misrecall`, and dropping `misrecall` is the only theme-fit removal in the pipeline. The canonical
   failure mode without Gate 2: keyword `refractory` for a railcar insulation theme swept the entire
   oncology biotech sector, zero railcar companies, and Gate 1 forwarded every one of them because a
   pharma SIC only earns `review`. Recall is *measured* via `recall@gold` against hand-built
   true-member lists, not assumed.

4. **Deep-dive data pull** (`deepdive_data.py`): XBRL financials (with EBIT concept cascade, debt
   and shares fallbacks), Form 4 insider trades, shelf/ATM status, dilution history, material event
   timeline. Data-integrity guards: debt-truncation, wrong-entity, low-revenue-loss, and a
   **second-source cross-check** (SEC vs yfinance, a >2.5× disagreement is flagged and blocks BUY).

5. **Valuation + mechanical `buy_eligible` gate** (`valuation.py`): reverse-DCF (normalized FCF),
   EV/EBITDA multiples, cyclical-trough EBITDA, and asset-heavy NAV path. A BUY requires
   `mos_basis∈{fcf_cap,nav}` AND margin of safety ≥ 30% AND **`buy_eligible == true`** AND 0
   kill-flags AND no T3 thesis. `buy_eligible` ANDs in every guard, extreme-MoS, large-cap-ceiling,
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

8. **Track-forward calibration** (`track_forward.py`): verdicts logged to
   `<private data dir>/metrics/verdicts.jsonl` (resolved **outside** this repo by `guards/tools/datadir.py`,
   never into it; the repo carries only `metrics/verdicts.jsonl.example` as the schema),
   Brier-scored vs IWM at maturity, with de-risk-native metrics (blowup-avoidance / downside-capture).

9. **Diagnostic signals, firewalled** (`signals.py`): a strictly diagnostic side-channel that
   measures the *delayed-information-diffusion* thesis, **price-divergence** (fundamental trajectory
   vs trailing price return → `unpriced_improvement` / `melting_ice_cube_priced` / `aligned`) and
   **ownership** (13D/13G + short interest). It **never** touches `buy_eligible` or the BUY decision;
   it is recorded for future per-signal calibration only.

**What it does not do:**

- Factor/quant screening or backtesting, empirical evidence that factor alpha evaporates
  net of transaction costs is baked into the design; that decision space is out of scope.
- Trading signals, execution, or portfolio management.
- Real-time data, all data is from SEC filings (1 to 4 day lag typical).
- Large-cap or sell-side coverage; the tool targets micro/small-cap names with
  no or minimal analyst coverage.
- Automated buy recommendations, every output ends with "merits human diligence," not "buy."

### Evidence and evaluation

Real-run observations and research reports belong in the initialized, versioned PRIVATE
companion. The public tool contains generic methodology and generated synthetic fixtures.
See [evidence status](docs/evidence-status.md) for the limits of review, synthetic controls,
current execution, and historical research.

CORE-4 is a policy sum of four binary distress flags, with range 0 to 4. A fixed score
threshold, a per-year ranking, and a train/test logistic model are different evaluations.
Predictive performance requires a dated eligible population, complete scope and provenance,
and a freshly executed evaluation. A zero-BUY output does not establish market efficiency
or the absence of investment opportunities.

---

## Install

```
/plugin install github:DaizeDong/small-cap-deepdive
```

Or clone manually:

```bash
git clone --recurse-submodules https://github.com/DaizeDong/small-cap-deepdive.git ~/.claude/plugins/small-cap-deepdive
```

Then install the data-layer dependencies and configure once:

```bash
cd ~/.claude/plugins/small-cap-deepdive
pip install -r tools/requirements.txt
gh repo create small-cap-deepdive-config --private
gh repo clone small-cap-deepdive-config ~/.small-cap-deepdive-config
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config"
python scripts/init_config.py
```

Open `~/.small-cap-deepdive-config/config.json` and set `"sec_user_agent"` to your real name and email:

```json
"sec_user_agent": "AcmeCorp user1@example.com"
```

This is the only required field. EDGAR requires a valid `User-Agent` header on every request
(SEC policy). Omitting it or using a fake value causes 403 errors from `efts.sec.gov`.

Note the config lives **outside** the repo. That is deliberate: `sec_user_agent` is your real name
and email, and this is a public repo. There is no in-repo config location any more, and the tools
refuse to create one.

To use the skill from Claude Code via a junction (Windows) or symlink instead of `/plugin install`:

```powershell
# Run from the clone directory in an ordinary user PowerShell session.
$repoRoot = (Resolve-Path -LiteralPath (git rev-parse --show-toplevel)).Path
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'SKILL.md'))) { throw 'SKILL.md missing' }
$skillAlias = Join-Path $env:USERPROFILE '.claude/skills/small-cap-deepdive'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $skillAlias) | Out-Null
New-Item -ItemType Junction -Path $skillAlias -Target $repoRoot | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $skillAlias 'SKILL.md'))) { throw 'Skill alias failed' }
```

```bash
# macOS / Linux, from the clone directory
repo_root="$(git rev-parse --show-toplevel)"
test -f "$repo_root/SKILL.md" || exit 1
mkdir -p "$HOME/.claude/skills"
skill_alias="$HOME/.claude/skills/small-cap-deepdive"
ln -s "$repo_root" "$skill_alias"
test -f "$skill_alias/SKILL.md" || exit 1
```

---

## Config

`small-cap-deepdive` is **config-bearing**, every tool reads its tuning parameters and the one
required EDGAR identity (`sec_user_agent`) from a JSON config. Full field-by-field contract:
[CONFIG.md](CONFIG.md).

- **Config discovery:** the pinned `guards/tools/datadir.py` resolver selects the companion.
  `SMALL_CAP_DEEPDIVE_CONFIG_DIR` or `SMALL_CAP_DEEPDIVE_CONFIG` takes priority;
  the resolver also supports its sibling-companion and home-directory conventions.
  The selected directory must belong to a verified PRIVATE Git repository and contain
  `config.json`. Missing configuration or unproved visibility fails without selecting another output home.
- **First time:**
  ```bash
  python scripts/init_config.py      # verify the existing PRIVATE companion, then initialize
  # edit that config.json: set "sec_user_agent" to your real name + email (the only hard requirement)
  python scripts/verify_config.py --json  # local config, PRIVATE root and dependency checks
  ```
- **Switch configs (hot-swap):** point the env var at another config dir, configs are self-contained
  (`output_dir` relative to the resolved PRIVATE companion). Each selected directory must be within an existing PRIVATE Git worktree.
- **Secrets / PII:** Mode B, your `config.json` lives outside this repo; `config.json`, `*.env`, and
  `secrets/*` are also gitignored as a backstop. `init_config.py` refuses to write inside the repo
  and `verify_config.py` FAILs on an in-repo `--config-dir`. Commit and push configuration and runtime DATA in the PRIVATE companion. Initialization verifies every remote fetch and push destination before writing; PUBLIC or unknown visibility is refused. The synthetic identity above is illustrative and must be replaced privately before live use.

---

## Quick start

Allocate a batch with `python tools/new_run.py --label <name> [--input-hash <SHA256>]` and set `SMALLCAP_RUN` to its stdout. Each call creates an exclusive directory beneath the PRIVATE reports root, using a date, encoded label and random identifier. Repeated labels never overwrite an earlier run. With no active run, reports use the unbatched root.

Resume explicitly with `--resume <RUN_ID> --input-hash <SHA256>`. The manifest's input hash, run identity and configured reports root must match before any mutation; successful resume preserves existing bytes. For compatible allocations without a supplied hash, the tool hashes canonical JSON containing the label, note and nonsecret valuation config snapshot; `tools/new_run.py` documents the exact encoding.

Reports, backtests and run state belong in a verified PRIVATE Git companion. Relative `output_dir` values resolve against that companion; absolute values and `SMALLCAP_OUTPUT_DIR` pass the same proof. `make_report.py --out` may select a different verified PRIVATE companion. The doctor checks local configuration and dependencies; it does not establish live SEC, market or model readiness.

SSH companion origins can use an alias declared by ordinary `Host` and `HostName github.com` rules in `~/.ssh/config`. Verification reads that file locally, respects the first matching `HostName`, and never runs SSH or configured commands. This also checks local rewrites of the literal `github.com` host. SSH configurations using `Include`, `Match`, or hostname canonicalization are refused; use a literal HTTPS GitHub origin for these configurations. HTTPS origins must name `github.com` directly. Every effective fetch and push destination must pass the PRIVATE visibility check. Existing hardlinked output files are refused.

There are four entry modes.

### 1. Theme run, full universe screen

For a ranked shortlist of small-cap pure-plays in a theme:

```
/small-cap-deepdive theme "railcar leasing"
```

Full step-by-step: **[runbooks/theme-run.md](runbooks/theme-run.md)**

Expected token budget: ~300k tokens, ~$0.30, 1 to 3 hours for a niche theme.

### 2. Single-ticker deep-dive

For a rigorous report on a company you already know:

```
/small-cap-deepdive ticker <ticker>
/small-cap-deepdive ticker <ticker> --theme "SaaS for regulated industries"
```

Full step-by-step: **[runbooks/single-deepdive.md](runbooks/single-deepdive.md)**

Expected token budget: ~10k to 15k tokens per company, <$0.02.

### 3. Re-rank existing scores

To re-sort or re-weight a prior run's outputs without re-running discovery:

```bash
python tools/rank.py --output RANKING-rerun-01.md
python tools/rank.py --slug railcar --output RANKING-railcar-rerun-01.md
python tools/rank.py --input "<private-companion>/reports/smallcap/<run>" --output RANKING-rerun-02.md
```

Choose a fresh output basename for each re-rank. Existing ranking artifacts are preserved.

The default uses the configured PRIVATE companion and active run. Explicit inputs must
also belong to a separate PRIVATE GitHub worktree. Git and `gh` verify the canonical
destination before output is written; unknown visibility is refused.

Full step-by-step: **[runbooks/batch-rank.md](runbooks/batch-rank.md)**

Expected token budget: Zero, deterministic, no LLM calls.

### 4. Event-driven discovery, spinoffs or insider clusters

For theme-independent discovery via structural catalysts (forced trading):

```bash
# Enumerate recent spinoff registrations (Form 10-12B)
python tools/discover_events.py --spinoffs

# Enumerate cluster open-market insider buys (openinsider)
python tools/discover_events.py --insider-clusters
```

Both axes hunt a forced-trading or conviction catalyst rather than a keyword. The mechanism
behind each one, and the honest caveats on both, are stated once in
[`reference/event-driven.md`](reference/event-driven.md).

No theme-fit gate needed, form-type enumeration is structurally precise. Kill-flag scan
still mandatory (`cheap_pass.py --universe <candidates_event_*.json>`). Pre-listing spinoffs
(no ticker yet) are processed via CIK, in the `band="unknown"` cohort.

Expected token budget: ~300k tokens for a full event-mode run with deep-dives.

---

## How to invoke

Use the slash command in any mode, e.g. `/small-cap-deepdive theme "railcar leasing"` or
`/small-cap-deepdive ticker <ticker>`. Or trigger it with natural language in any Claude Code
session:

```
Run small-cap-deepdive on the theme "railcar leasing"
Deep-dive <ticker> as a small-cap with small-cap-deepdive
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
| 4 to 5 | Survived all gates, real theme exposure, no structural red flags | Merits full human diligence |
| 3 | Borderline, one weak dimension | Read dimension detail before deciding |
| 1 to 2 | Hard-rule ceiling applied | Named structural problem; do not invest without resolving it |
| Eliminated | Kill-flag fired at `cheap_pass` | Stop, do not re-examine |

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
  tools/filter_by_sic.py — Gate 1 SIC review tier + SIC reverse-recall floor (LIBRARY; CLI is --selftest only)
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
firewalled, `valuation.py` / `buy_eligible` / the BUY trigger contain **zero** references to any
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
invoked as a skill at runtime, the catalog is read as documentation. Full anti-recursion
design: `reference/data-sources.md §market-intel`.

**Insider-source availability:** The default `insider_source` uses OpenInsider.
A failed or incomplete observation remains unavailable with its reason. EDGAR Form 4 mode
is an unsupported stub (`available: false`); there is no implemented automatic EDGAR fallback.
See `reference/data-sources.md` for the current source contract.

**Workflow host requirement:** `workflows/theme-fit-gate.js` and
`workflows/deepdive-fanout.js` consume bound requests through a configured Workflow host.
Natural-language orchestration can prepare those requests, but each stage remains incomplete
until its bound host result is ingested. The JavaScript files are not direct Node entry points.

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
