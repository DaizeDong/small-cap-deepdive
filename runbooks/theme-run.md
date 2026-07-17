# Runbook: Theme Run

> Entry mode 1, `theme <主题>`. Use when you have an investment theme and want a ranked
> shortlist of small-cap pure-plays from the full SEC-filing universe.

---

## Prerequisites

Complete this once before any run:

```bash
pip install -r tools/requirements.txt
mkdir -p ~/.small-cap-deepdive-config
cp reference/config.example.json \
   ~/.small-cap-deepdive-config/config.json
```

Open `~/.small-cap-deepdive-config/config.json` (the private config dir, never the repo) and set
`"sec_user_agent"` to your real name and email:

```json
"sec_user_agent": "Jane Smith user1@example.com"
```

EDGAR requires a valid `User-Agent` header on every request. Omission causes 403 errors.
This is the only required field, all other keys have defaults.

---

## Open a run batch (do this at the start of every run)

```bash
export SMALLCAP_RUN=$(python tools/new_run.py --label <theme>)   # e.g. --label aginput
```

All outputs for this run then land together in `reports/smallcap/<date>_<label>/`, with a
`_run.json` manifest (date, skill git commit, config snapshot) so runs stay comparable across
skill versions. Unset `SMALLCAP_RUN` → flat `reports/smallcap/` (legacy).

---

## Recommended: One-Command Theme Run

The easiest way to run the full mechanical pipeline (discover → cheap_pass → SIC filter):

```bash
python tools/run_theme.py --theme "railcar,railcar leasing" --slug railcar
```

This runs Steps 1 to 3 below automatically and prints the "Next steps" handoff.
Use `--micro` flag to apply the micro-cap ($500M) ceiling instead of the default small-cap ($2B).

---

## Step 1, Universe Enumeration

```bash
python tools/discover.py --theme "railcar leasing" --out-slug railcar
```

Output: `reports/smallcap/universe_railcar_<date>.csv`

Expected output:

```
[1/3] SEC FTS 召回 (主题: ['railcar leasing'], forms: 10-K,10-Q)...
  'railcar leasing': 214 家
  去重后 187 家
[2/3] yfinance 补市值+流动性...
[3/3] 过滤去噪...

=== 发现结果 ===
总召回 187 家 | 小盘候选 42 家 (市值<$2.0B, 已剔SPAC/低流动性)
...
清单: reports/smallcap/universe_railcar_<date>.csv
```

**What to expect:** Over-recall is intentional. 150 to 300 candidates for a niche theme;
500+ for a broad theme like "AI infrastructure". The precision gate below clears the field.

**Token magnitude:** Negligible, pure HTTP to `efts.sec.gov`, no LLM calls.

**If zero hits:** FTS keyword is too restrictive. Try shorter terms (`railcar` instead of
`railcar leasing`), or two separate runs on each word, then union the results.

---

## Step 2, Gate 1: SIC Coarse Exclusion

Gate 1 is applied automatically by `run_theme.py` (via `filter_by_sic.sic_ok`).
`filter_by_sic.py` is a library module, not a standalone pipeline step.

To verify the SIC logic:

```bash
python tools/filter_by_sic.py --selftest
```

**What it does:** Drops companies whose SIC code definitively places them outside plausible
theme membership. Companies with no SIC on file are kept, not dropped, do not over-exclude.

**Token magnitude:** Negligible, deterministic lookup against SEC company data.

---

## Step 3, Mechanical De-Risk (cheap_pass)

```bash
python tools/cheap_pass.py --universe reports/smallcap/universe_railcar_<date>.csv \
  --out-slug railcar
```

Output: `reports/smallcap/cheappass_railcar_<date>.csv`

Expected output:

```
对 42 家小盘候选做机械体检...
...
=== Cheap pass 结果 ===
体检 42 家 | 淘汰 8 家 | 幸存 34 家
...
清单: reports/smallcap/cheappass_railcar_<date>.csv
```

**What it checks (hard kill-flags):**

| Flag | Trigger | Action |
|---|---|---|
| `going_concern` | Both "going concern" + "substantial doubt" in most recent 10-K | Eliminate |
| `death_spiral` | Variable-rate convertible in most recent filings | Eliminate |
| `material_weakness` | ICFR material weakness in most recent annual filing | Eliminate if killflag_count >= 2 |

**Do not deepdive eliminated candidates.** The kill-flag verdict stands.

**Token magnitude:** Negligible for deterministic guards.

---

## Step 4, Gate 2: LLM Theme-Fit Classification

After `run_theme.py` writes `reports/smallcap/candidates_<slug>.json`, run the theme-fit gate.

**Natural-language path (works in any Claude Code session):**

In your Claude Code session, instruct the agent:

```
For each ticker in reports/smallcap/candidates_railcar.json, read the company's most recent 10-K
business description from EDGAR and classify it as:
  pure_play   — primary business is directly in the theme
  partial     — theme exposure is real but not primary
  misrecall   — incidental keyword match, no real theme exposure

Use the prompt template in reference/discovery-engine.md §Gate 2.
Write results to reports/smallcap/railcar_gate2.json (include ticker, cik, name, classification,
one-sentence rationale). Drop all misrecalls before the next step.
```

**Optional accelerator:** If the Workflow tool is available in your session, run:

```bash
node workflows/theme-fit-gate.js candidates_railcar.json
```

Expected output (either path):

```
Gate 2 complete: 34 evaluated
  pure_play:  8
  partial:    14
  misrecall:  12
Retained for deep-dive: 22 tickers
```

**Token magnitude:** ~800 to 1 200 tokens per candidate (10-K business section read + classification).
For 34 candidates expect ~30k to 40k tokens of input, ~4k output. Budget ~$0.05 at Sonnet pricing.

**Why this gate is mandatory:** The canonical failure: keyword `refractory` for a railcar insulation
theme swept the entire oncology biotech sector (zero railcar companies among them). See
`reference/discovery-engine.md` for the documented case.

---

## Step 5, Deep-Dive Data Pull

```bash
python tools/deepdive_data.py --candidates reports/smallcap/candidates_railcar.json
```

Or per-ticker:

```bash
python tools/deepdive_data.py --ticker RAIL
```

Output: `reports/smallcap/deepdive_<ticker>_<date>.json` (one file per ticker)

**What it pulls:** Revenue/OCF/EV series (XBRL), Form 4 insider trades (12-month net
buy/sell), S-3 / ATM shelf status, dilution history, 8-K material events.

**Token magnitude:** Negligible, deterministic EDGAR + yfinance fetch, no LLM calls.
Runtime 5 to 20 minutes for 22 tickers (EDGAR rate discipline: ~150ms between requests).

---

## Step 6, Deep-Dive Judgment (per candidate)

In your Claude Code session:

```
For each pure_play/partial company in reports/smallcap/railcar_gate2.json, spawn one Agent.
Each Agent must:
1. Open reference/cognitive-priors.md and state the base-rate priors for this company class.
2. Run a disconfirmation WebSearch: "<company name> fraud lawsuit SEC investigation short seller".
3. Check data staleness: is the most recent filing period within 90 days?
4. Apply the 7-dimension scorecard from reference/judgment-rubric.md.
5. Apply all Rating Hard-Rules from SKILL.md.
6. Write the full report to reports/smallcap/report_<TICKER>.md.
```

**Optional accelerator:** If the Workflow tool is available:

```bash
node workflows/deepdive-fanout.js candidates_railcar.json
```

**Token magnitude:** ~8k to 15k tokens per candidate (data read + rubric application +
disconfirmation search). For 22 candidates: ~180k to 330k tokens total. Budget ~$0.20 to 0.35.

---

## Step 7, Rank

```bash
python tools/rank.py --slug railcar
```

Expected output: `reports/smallcap/RANKING.md`

**Token magnitude:** Negligible, deterministic sort + Markdown table generation.

---

## Total Run Summary

| Phase | Time | Tokens | Cost (est.) |
|---|---|---|---|
| discover + SIC filter | 3 to 8 min | ~0 LLM | $0.00 |
| theme-fit gate (Gate 2) | 15 to 40 min | ~40k | ~$0.05 |
| cheap_pass (deterministic) | 8 to 25 min | ~0 LLM | $0.00 |
| deepdive_data pull | 10 to 30 min | ~0 LLM | $0.00 |
| deep-dive judgment | 20 to 60 min | ~200k | ~$0.20 |
| rank | <1 min | ~0 LLM | $0.00 |
| **Total** | **~1 to 3 hr** | **~240k** | **~$0.25** |

Costs shown at Claude Sonnet input-token pricing. Actual cost depends on candidate count
and filing length. Large themes (500+ raw candidates) scale linearly with Gate 2 + judgment.

---

## Interpreting the Output

- **Score 4 to 5:** Survived all gates, real theme exposure, no structural red flags. Merits full
  human diligence, this is the output the tool is designed to surface.
- **Score 3:** Borderline. Check dimension breakdown; often one weak dimension (e.g., insider
  selling) dragging an otherwise solid profile.
- **Score 1 to 2:** Hard-rule ceiling applied (dilution, weakness, weak fundamentals). Do not buy
  without understanding and explicitly accepting the specific flag.
- **0-buy is a feature, not a bug.** If a theme produces zero score-4+ candidates, the tool is
  telling you the theme's small-cap universe does not have clean industrial beneficiaries at this
  time. That is correct and useful information.

---

## Troubleshooting

**EDGAR 403 error:** `sec_user_agent` in `~/.small-cap-deepdive-config/config.json` (private config dir) is missing or malformed. Must be
`"Name email@domain.com"` format.

**Zero FTS hits:** Keyword too specific. Try the single most distinctive word of the theme.

**Gate 2 stalls:** LLM hitting rate limit or filing not available in EDGAR FTS. The workflow
runner retries with exponential backoff; natural-language path: skip that ticker and note in
coverage gaps.

**deepdive_data partial XBRL:** Common for micro-caps. The tool logs which concepts are missing;
judgment rubric Dimension 1 confidence auto-caps at 40% when revenue or OCF is unavailable.
