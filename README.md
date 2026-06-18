# small-cap-deepdive

A disciplined orchestration skill for neglected small-cap US equity research. Given an investment
theme or a single ticker, it enumerates the SEC-filing universe, applies hard mechanical kill-flags,
runs falsifiable deep-dive due diligence with forced disconfirmation, and ranks surviving candidates.

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange?style=flat)](https://docs.anthropic.com/en/docs/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Depends on](https://img.shields.io/badge/depends-edgartools%20MIT-green?style=flat)](https://github.com/dgunning/edgartools)
[![Version](https://img.shields.io/badge/version-0.1.0-purple?style=flat)](CHANGELOG.md)

[English](README.md) | [中文版](README_CN.md)

---

## Read this first: what this tool is and is not

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

📜 **[Read the design philosophy → PHILOSOPHY.md](PHILOSOPHY.md)**

---

## What it does

1. **Enumerates the SEC universe** for a theme using EDGAR full-text search (FTS). Over-recall
   is intentional — the precision gate that follows clears the field.

2. **Two-stage precision gate (mandatory).** Gate 1 (`filter_by_sic.py`): coarse SIC-code
   exclusion of definitively off-theme sectors. Gate 2 (LLM): reads each company's 10-K
   business description and classifies it as `pure_play / partial / misrecall`. The
   canonical failure mode without this gate: keyword `refractory` for a railcar insulation
   theme swept the entire oncology biotech sector. Zero railcar companies.

3. **Mechanical de-risk** (`cheap_pass.py`): hard kill-flags from SEC filings — going-concern
   auditor paragraphs, death-spiral convertibles, ICFR material weaknesses. Eliminated companies
   do not proceed to judgment, regardless of narrative quality.

4. **Deep-dive data pull** (`deepdive_data.py`): XBRL financials, Form 4 insider trades,
   shelf/ATM status, dilution history, material event timeline.

5. **Forced-disconfirmation judgment**: base-rate priors anchored before scoring, mandatory
   disconfirmation WebSearch for each candidate, 7-dimension scorecard with hard ceiling rules.
   Evidence is tier-tagged (T1 first-party SEC filings / T2 independent third-party / T3 company-sourced); T3 evidence cannot support
   a buy recommendation.

6. **Rank** (`rank.py`): scored candidates sorted by composite, with funnel counts,
   kill-flag eliminations, and explicit coverage gaps.

---

## What it does not do

- Factor/quant screening or backtesting — empirical evidence that factor alpha evaporates
  net of transaction costs is baked into the design; that decision space is out of scope.
- Trading signals, execution, or portfolio management.
- Real-time data — all data is from SEC filings (1–4 day lag typical).
- Large-cap or sell-side coverage — the tool is calibrated for micro/small-cap names with
  no or minimal analyst coverage.
- Automated buy recommendations — every output ends with "merits human diligence," not "buy."

---

## Install

```bash
git clone https://github.com/DaizeDong/small-cap-deepdive.git
cd small-cap-deepdive
pip install -r tools/requirements.txt
```

Then configure once:

```bash
cp skills/small-cap-deepdive/reference/config.example.json \
   skills/small-cap-deepdive/reference/config.json
```

Open `config.json` and set `"sec_user_agent"` to your real name and email:

```json
"sec_user_agent": "Jane Smith jane@example.com"
```

This is the only required field. EDGAR requires a valid `User-Agent` header on every request
(SEC policy). Omitting it or using a fake value causes 403 errors from `efts.sec.gov`.

To use the skill from Claude Code, add a junction (Windows) or symlink:

```bash
# Windows (run as Administrator)
cmd /c mklink /J "%USERPROFILE%\.claude\skills\small-cap-deepdive" "skills\small-cap-deepdive"

# macOS / Linux
ln -s "$(pwd)/skills/small-cap-deepdive" "$HOME/.claude/skills/small-cap-deepdive"
```

---

## Three Entry Modes

### 1. Theme run — full universe screen

For a ranked shortlist of small-cap pure-plays in a theme:

```
/small-cap-deepdive theme "railcar leasing"
```

Or in natural language in any Claude Code session:

```
Run small-cap-deepdive on the theme "railcar leasing"
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

---

## Architecture

```
bundled data layer (deterministic Python — never makes investment judgments)
  tools/_common.py     — config, EDGAR session, per-tool sleep + http_get retry/backoff
  tools/discover.py    — EDGAR FTS universe enumeration
  tools/filter_by_sic.py — Gate 1 coarse SIC exclusion
  tools/cheap_pass.py  — mechanical kill-flags from SEC filings
  tools/deepdive_data.py — XBRL + Form 4 + shelf status data pull
  tools/rank.py        — deterministic scoring and ranking
  tools/run_theme.py   — end-to-end theme driver (calls the above)

thin judgment layer (LLM — reads JSON, applies rubric, never computes financials)
  skills/small-cap-deepdive/SKILL.md          — orchestration + world-view + hard rules
  skills/small-cap-deepdive/reference/*.md    — methodology invariants (single source of truth)
  workflows/theme-fit-gate.js  — optional: parallel Gate 2 fan-out accelerator
  workflows/deepdive-fanout.js — optional: parallel deep-dive accelerator
```

**The boundary is firm:** `tools/*.py` never produces investment judgments (only data). The
judgment layer never computes financials (only reads JSON). This split was validated on 10
real production bugs, all of which were in the data layer — the architectural boundary
prevented them from contaminating judgment outputs.

---

## Dependencies

| Package | License | Purpose |
|---|---|---|
| [edgartools](https://github.com/dgunning/edgartools) | MIT | EDGAR FTS, XBRL parsing, Form 4 retrieval |
| yfinance | Apache 2.0 | Market cap / price convenience layer |
| pandas | BSD | Data processing |
| requests | Apache 2.0 | HTTP with EDGAR rate discipline |

No proprietary dependencies. No API keys required for the core data layer.

**market-intel (optional read-only reuse):** When the `market-intel` skill is installed, the
judgment layer reads its source catalog to route qualitative research (X sentiment, industry
news, competitor web presence) to the best available MCP tool. The market-intel skill is never
invoked as a skill at runtime — the catalog is read as documentation. Full anti-recursion
design: `reference/data-sources.md §market-intel`.

---

## Public-Ready Notes

**openinsider fragility:** The default `insider_source` config uses `openinsider.com` for
Form 4 direction parsing. This is a third-party service with no explicit automated-access
terms. The tool automatically falls back to direct EDGAR Form 4 parsing when openinsider is
unavailable. Reports label the source accordingly.

To default to EDGAR Form 4 from the start (no openinsider dependency):

```json
"insider_source": "edgar"
```

The `edgar` mode is a **roadmap stub — not yet implemented** (returns `available: false`).
The tested default is `openinsider`. See `reference/data-sources.md` for the fallback
behaviour when openinsider is unavailable.

**workflow .js files are optional:** `workflows/theme-fit-gate.js` and
`workflows/deepdive-fanout.js` accelerate fan-out steps when Claude Code's Workflow tool is
available in the session. They are not required — the natural-language orchestration in
`SKILL.md` is the primary path and works in any Claude Code session. The `.js` files are
convenience wrappers, not dependencies.

**X sentiment routing:** When X/Twitter sentiment is requested for a ticker, the skill routes
to twitterapi.io (resale API, route ②) if the key is configured via the market-intel companion
config. If unavailable, it falls back to search-engine-indexed X posts. The user's personal
X/Twitter account is never used (route ③ is permanently excluded — account suspension risk).

---

## Scorecard Quick Reference

| Score | Meaning | Action |
|---|---|---|
| 4–5 | Survived all gates, real theme exposure, no structural red flags | Merits full human diligence |
| 3 | Borderline — one weak dimension | Read dimension detail before deciding |
| 1–2 | Hard-rule ceiling applied | Named structural problem; do not invest without resolving it |
| Eliminated | Kill-flag fired at `cheap_pass` | Stop — do not re-examine |

Composite = weighted average of 7 dimensions. Hard ceiling rules override narrative quality.
Full rubric: `skills/small-cap-deepdive/reference/judgment-rubric.md`.

---

## Contributing

See the design spec at `docs/` for architectural invariants. The core invariant: the data
layer (`tools/*.py`) never produces investment judgment; the judgment layer never computes
financials. Changes that blur this boundary require explicit justification in `PHILOSOPHY.md`.
