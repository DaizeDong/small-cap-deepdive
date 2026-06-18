# Runbook: Theme Run

> Entry mode 1 — `theme <主题>`. Use when you have an investment theme and want a ranked
> shortlist of small-cap pure-plays from the full SEC-filing universe.

---

## Prerequisites

Complete this once before any run:

```bash
pip install -r tools/requirements.txt
cp skills/small-cap-deepdive/reference/config.example.json \
   skills/small-cap-deepdive/reference/config.json
```

Open `config.json` and set `"sec_user_agent"` to your real name and email:

```json
"sec_user_agent": "Jane Smith jane@example.com"
```

EDGAR requires a valid `User-Agent` header on every request. Omission causes 403 errors.
This is the only required field — all other keys have defaults.

---

## Step 1 — Universe Enumeration

```bash
python tools/discover.py --theme "railcar leasing" --out reports/railcar_raw.json
```

Expected output:

```
[discover] FTS query: "railcar leasing"
[discover] Raw hits: 214 candidates
[discover] After dedup/filing-type filter: 187 unique tickers
[discover] Written → reports/railcar_raw.json
```

**What to expect:** Over-recall is intentional. 150–300 candidates for a niche theme;
500+ for a broad theme like "AI infrastructure". The precision gate below clears the field.

**Token magnitude:** Negligible — pure HTTP to `efts.sec.gov`, no LLM calls.

**If zero hits:** FTS keyword is too restrictive. Try shorter terms (`railcar` instead of
`railcar leasing`), or two separate runs on each word, then union the results.

---

## Step 2 — Gate 1: SIC Coarse Exclusion

```bash
python tools/filter_by_sic.py \
  --input reports/railcar_raw.json \
  --out reports/railcar_gate1.json
```

Expected output:

```
[filter_by_sic] Input: 187 tickers
[filter_by_sic] Hard-excluded (SIC match): 89 tickers
  pharma/biotech: 52, finance: 21, retail: 10, software: 6
[filter_by_sic] No SIC on file (kept for Gate 2): 4 tickers
[filter_by_sic] Survivors: 98 tickers → reports/railcar_gate1.json
```

**What it does:** Drops companies whose SIC code definitively places them outside plausible
theme membership. Companies with no SIC on file are kept, not dropped — do not over-exclude.

**Token magnitude:** Negligible — deterministic lookup against SEC company data.

**Per-theme SIC override:** Add `sic_exclusion_blocks` to `config.json` if defaults are
too aggressive for your theme (e.g., a theme that spans both pharma and industrial sectors).

---

## Step 3 — Gate 2: LLM Theme-Fit Classification

**Natural-language path (works in any Claude Code session):**

In your Claude Code session, instruct the agent:

```
For each ticker in reports/railcar_gate1.json, read the company's most recent 10-K
business description from EDGAR and classify it as:
  pure_play   — primary business is directly in the theme
  tangential  — theme exposure is real but not primary
  false_positive — incidental keyword match, no real theme exposure

Use the prompt template in reference/discovery-engine.md §Gate 2.
Write results to reports/railcar_gate2.json (include ticker, cik, name, classification,
one-sentence rationale). Drop all false_positives before the next step.
```

**Optional accelerator:** If the Workflow tool is available in your session, run:

```bash
node workflows/theme-fit-gate.js \
  --input reports/railcar_gate1.json \
  --out reports/railcar_gate2.json \
  --theme "railcar leasing"
```

Expected output (either path):

```
Gate 2 complete: 98 evaluated
  pure_play:      8
  tangential:     14
  false_positive: 76
Retained for deep-dive: 22 tickers → reports/railcar_gate2.json
```

**Token magnitude:** ~800–1 200 tokens per candidate (10-K business section read + classification).
For 98 candidates expect ~90k–120k tokens of input, ~10k output. Budget ~$0.10–0.20 at Sonnet pricing.

**Why this gate is mandatory:** The canonical failure: keyword `refractory` for a railcar insulation
theme swept the entire oncology biotech sector (zero railcar companies among them). See
`reference/discovery-engine.md` for the documented case.

---

## Step 4 — Mechanical De-Risk (cheap_pass)

```bash
python tools/cheap_pass.py \
  --input reports/railcar_gate2.json \
  --out reports/railcar_alive.json
```

Or run per-ticker:

```bash
python tools/cheap_pass.py --ticker RAIL
```

Expected output:

```
[cheap_pass] Processing 22 candidates...
  GATO — going_concern detected → ELIMINATED
  MRGN — death_spiral convertible → ELIMINATED
  XYZ  — material_weakness (ICFR) → ELIMINATED
[cheap_pass] Eliminated: 3 | Surviving: 19
[cheap_pass] Written → reports/railcar_alive.json
```

**What it checks (hard kill-flags):**

| Flag | Trigger | Action |
|---|---|---|
| `going_concern` | Auditor going-concern paragraph in most recent 10-K or 10-Q | Eliminate |
| `death_spiral` | Variable-rate convertible note with no floor in most recent filings | Eliminate |
| `material_weakness` | ICFR material weakness disclosed in most recent annual filing | Dim 5 capped; continues |

**Do not deepdive eliminated candidates.** The kill-flag verdict stands.

**Token magnitude:** Negligible for deterministic guards. If the agent re-reads full 10-K text
to confirm a going-concern paragraph, budget ~2k tokens per confirmation.

---

## Step 5 — Deep-Dive Data Pull

```bash
python tools/deepdive_data.py \
  --input reports/railcar_alive.json \
  --out reports/railcar_deepdive_data.json
```

Or per-ticker:

```bash
python tools/deepdive_data.py --ticker RAIL --out reports/RAIL_data.json
```

Expected output:

```
[deepdive_data] 19 tickers to process
  RAIL — OK (financials: 12Q, insider: 23 transactions, filings: 31)
  GBX  — OK (financials: 8Q, insider: 9 transactions, filings: 18)
  ...
[deepdive_data] Warnings: 2 tickers had partial XBRL (logged)
[deepdive_data] Written → reports/railcar_deepdive_data.json
```

**What it pulls:** Revenue/OCF/EV series (XBRL), Form 4 insider trades (12-month net
buy/sell), S-3 / ATM shelf status, dilution history, 8-K material events.

**Token magnitude:** Negligible — deterministic EDGAR + yfinance fetch, no LLM calls.
Runtime 5–20 minutes for 19 tickers (EDGAR rate discipline: ~150ms between requests).

---

## Step 6 — Deep-Dive Judgment (per candidate)

In your Claude Code session:

```
For each candidate in reports/railcar_deepdive_data.json, spawn one Agent.
Each Agent must:
1. Open reference/cognitive-priors.md and state the base-rate priors for this company class.
2. Run a disconfirmation WebSearch: "<company name> fraud lawsuit SEC investigation short seller".
3. Check data staleness: is the most recent filing period within 90 days?
4. Apply the 7-dimension scorecard from reference/judgment-rubric.md.
5. Apply all Rating Hard-Rules from SKILL.md.
6. Write the score JSON (dimensions + composite + kill-flag detail + evidence tiers +
   disconfirmation findings) to reports/railcar_scores/<TICKER>.json.
```

**Optional accelerator:** If the Workflow tool is available:

```bash
node workflows/deepdive-fanout.js \
  --input reports/railcar_deepdive_data.json \
  --scores-dir reports/railcar_scores/ \
  --theme "railcar leasing"
```

**Token magnitude:** ~8k–15k tokens per candidate (data read + rubric application +
disconfirmation search). For 19 candidates: ~150k–280k tokens total. Budget ~$0.15–0.30.

---

## Step 7 — Rank

```bash
python tools/rank.py \
  --scores-dir reports/railcar_scores/ \
  --out reports/railcar_ranked.md
```

Expected output:

```
Rank  Ticker  Composite  Dim1  Dim2  Dim3  Dim4  Dim5  Dim6  Dim7  Kill-flags
1     GBX     4.1        4     5     4     3     4     4     4     none
2     RAIL    3.8        4     4     3     4     4     3     4     none
...
12    XCC     2.1        2     2     3     2     2     2     2     material_weakness
---
Gate survival: 187 → 98 (Gate 1) → 22 (Gate 2) → 19 (cheap_pass) → 19 (deep-dive) → 19 ranked
Kill-flag eliminations: 3 (going_concern: 1, death_spiral: 1, material_weakness+eliminate: 1)
Coverage gaps: 2 tickers had partial XBRL — Dim 1 confidence capped at 40%
```

**Token magnitude:** Negligible — deterministic sort + Markdown table generation.

---

## Total Run Summary

| Phase | Time | Tokens | Cost (est.) |
|---|---|---|---|
| discover + filter_by_sic | 3–8 min | ~0 LLM | $0.00 |
| theme-fit gate (Gate 2) | 15–40 min | ~100k | ~$0.10 |
| cheap_pass (deterministic) | 8–25 min | ~0 LLM | $0.00 |
| deepdive_data pull | 10–30 min | ~0 LLM | $0.00 |
| deep-dive judgment | 20–60 min | ~200k | ~$0.20 |
| rank | <1 min | ~0 LLM | $0.00 |
| **Total** | **~1–3 hr** | **~300k** | **~$0.30** |

Costs shown at Claude Sonnet input-token pricing. Actual cost depends on candidate count
and filing length. Large themes (500+ raw candidates) scale linearly with Gate 2 + judgment.

---

## Interpreting the Output

- **Score 4–5:** Survived all gates, real theme exposure, no structural red flags. Merits full
  human diligence — this is the output the tool is designed to surface.
- **Score 3:** Borderline. Check dimension breakdown; often one weak dimension (e.g., insider
  selling) dragging an otherwise solid profile.
- **Score 1–2:** Hard-rule ceiling applied (dilution, weakness, weak fundamentals). Do not buy
  without understanding and explicitly accepting the specific flag.
- **0-buy is a feature, not a bug.** If a theme produces zero score-4+ candidates, the tool is
  telling you the theme's small-cap universe does not have clean industrial beneficiaries at this
  time. That is correct and useful information.

---

## Troubleshooting

**EDGAR 403 error:** `sec_user_agent` in `config.json` is missing or malformed. Must be
`"Name email@domain.com"` format.

**Zero FTS hits:** Keyword too specific. Try the single most distinctive word of the theme.

**Gate 2 stalls:** LLM hitting rate limit or filing not available in EDGAR FTS. The workflow
runner retries with exponential backoff; natural-language path: skip that ticker and note in
coverage gaps.

**deepdive_data partial XBRL:** Common for micro-caps. The tool logs which concepts are missing;
judgment rubric Dimension 1 confidence auto-caps at 40% when revenue or OCF is unavailable.
