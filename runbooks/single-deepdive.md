# Runbook: Single-Ticker Deep-Dive

> Entry mode 2 — `ticker <代码> [--theme X]`. Use when you have a specific company and want
> a rigorous, falsifiable deep-dive report without running a full theme screen.

This is the highest-frequency entry point. You know the ticker; you want to know if it is worth
owning. The tool mechanically eliminates it if it fails the kill-flags, and gives you a
scored report if it survives.

---

## Prerequisites

Complete this once before any run:

```bash
pip install -r tools/requirements.txt
cp skills/small-cap-deepdive/reference/config.example.json \
   skills/small-cap-deepdive/reference/config.json
```

Set `"sec_user_agent"` in `config.json` to your real name and email.
EDGAR blocks requests with a missing or obviously fake User-Agent.

---

## Step 1 — Mechanical De-Risk First

Always run `cheap_pass` before any qualitative work. If the company fails a hard kill-flag,
stop — do not spend judgment budget on a structurally disqualified candidate.

```bash
python tools/cheap_pass.py --ticker EGAN
```

Expected output — pass:

```
[cheap_pass] EGAN
  going_concern:     False
  death_spiral:      False
  material_weakness: False
  Market cap:        $148M (within small-cap ceiling)
  Avg daily vol:     $320k (above $100k floor)
RESULT: PASS — proceed to deep-dive
```

Expected output — eliminated:

```
[cheap_pass] GATO
  going_concern: True
    Source: 10-K 2025-03-15 — "substantial doubt about the company's ability
            to continue as a going concern" + "going concern" (both triggers present)
RESULT: ELIMINATED — do not deepdive
```

**If eliminated:** Report the kill-flag and stop. The hard-rule is not an invitation to
argue — it is a floor. A company with an auditor going-concern opinion has a >50% base-rate
probability of either restructuring, being acquired at distressed valuation, or delisting
within 24 months. That base rate is priced into the mechanics, not the narrative.

**Token magnitude:** Negligible — deterministic EDGAR filing fetch and parse, no LLM calls.
Runtime: 30–90 seconds.

---

## Step 2 — Data Pull

```bash
python tools/deepdive_data.py --ticker EGAN --out reports/EGAN_data.json
```

Expected output:

```
[deepdive_data] EGAN (CIK: 0000031235)
  Financials: 20 quarters (2020Q1 – 2025Q1), OCF available: True
  Insider trades (L12M): 3 purchases $142k / 2 sales $38k → net BUY
  S-3 / ATM: None active
  Diluted share count trend: +3.2% CAGR (L5Y)
  Recent 8-Ks: 3 (earnings, partnership announcement, debt refinancing)
  Filing timeliness: On time (all 10-Ks/10-Qs within 45 days of period end)
Written → reports/EGAN_data.json
```

**What it pulls:**

| Data | Source | Notes |
|---|---|---|
| Revenue, OCF, EV | EDGAR XBRL | Partial XBRL common for micro-caps |
| Insider trades | Form 4 via EDGAR / openinsider | Direction: P=purchase, S=sale |
| Shelf / ATM status | S-3, 424B5 filings | ATM = at-the-money equity offering program |
| Dilution history | Shares outstanding series from XBRL | |
| Material events | 8-K filing summaries | |
| Filing timeliness | Filing date vs period end | Late filer = governance yellow flag |

**Token magnitude:** Negligible — deterministic fetch, no LLM calls.
Runtime: 2–8 minutes (EDGAR rate limit: ~150ms between requests).

**Partial XBRL warning:** If EGAN has incomplete XBRL tags, the tool logs which fields are
missing. When OCF or revenue are missing, Dimension 1 confidence is automatically capped at 40%
in the judgment step.

---

## Step 3 — Judgment Pass

In your Claude Code session, instruct the agent:

```
Deep-dive report for EGAN using data from reports/EGAN_data.json.
Theme context (if any): "SaaS for regulated industries" [omit if no theme].

Required preamble before scoring:
  a. Open reference/cognitive-priors.md. State the applicable base-rate priors
     for a ~$150M revenue-positive SaaS company. Note which priors apply.
  b. Run WebSearch: "EGAN Enghouse Systems fraud lawsuit SEC investigation short seller
     bear thesis". Read and summarize what you find. If nothing material, say so explicitly.
  c. Confirm data staleness: most recent 10-K and 10-Q period dates vs today.
     Flag any data older than 180 days as stale.

Then apply the 7-dimension scorecard from reference/judgment-rubric.md in full.
Apply all Rating Hard-Rules from SKILL.md. No dimension may be skipped.

Output: structured report with dimension scores (1–5), evidence tier per major claim,
composite score, kill-flag detail, disconfirmation findings, and data gaps.
```

**Optional accelerator:** If the Workflow tool is available:

```bash
node workflows/deepdive-fanout.js \
  --ticker EGAN \
  --data reports/EGAN_data.json \
  --theme "SaaS for regulated industries" \
  --out reports/EGAN_scored.json
```

**Token magnitude:** ~8k–15k tokens per company:

| Component | Tokens |
|---|---|
| Data JSON read | ~2k–4k |
| Reference docs (rubric + priors) | ~3k–5k |
| Disconfirmation WebSearch | ~1k–2k |
| Scoring + report generation | ~2k–4k |
| **Total** | **~8k–15k** |

Cost: <$0.02 per company at Sonnet pricing.

---

## Step 4 — Reading the Output

A well-formed single-company output includes:

```
EGAN — eGain Corporation
Theme: SaaS for regulated industries
Composite: 3.8 / 5.0

Dimension scores:
  1. Financial quality:    4  (OCF positive 8 consecutive quarters; EV/OCF ~22x, reasonable)
  2. Theme fit:            4  (Tier-1: 10-K primary business; not pure hype)
  3. Balance sheet:        4  (Net cash positive, no debt maturities <2Y)
  4. Insider behavior:     4  (Net buy $104k L12M; no large sells concurrent with raises)
  5. Governance:           3  (Material weakness: none; one related-party lease — yellow)
  6. Catalyst timeline:    4  (Identifiable Q3 contract renewal cycle; not speculative)
  7. Valuation:            3  (Fair-to-rich vs sector median; no distress discount)

Kill-flags: none
Hard-rules applied: none
Evidence tiers: Dim 1 — T1 XBRL; Dim 2 — T1 10-K text; Dim 4 — T1 Form 4

Disconfirmation search: No short reports, SEC investigations, or fraud allegations found.
  One negative: 2023 customer churn disclosure in 8-K — addressed in Q2 2024 10-Q.

Data gaps: EV/EBITDA not computable (XBRL depreciation not tagged for this CIK).
  Dim 1 uses EV/OCF as substitute; confidence maintained.

Verdict: Survives gates. Merits full human diligence on contract concentration risk
  (top-3 customers = 34% of revenue per most recent 10-K §7).
```

---

## Interpreting the Score

**Score 4–5:** No structural red flags. Real business, real cash flow, insider alignment.
This is what the tool exists to surface — a candidate worth actual human research time.

**Score 3:** Borderline. One dimension is weak. Read the specific dimension note to decide
if the weakness is temporary (e.g., a one-quarter OCF dip) or structural (e.g., persistent
dilution). Do not infer "buy" from a 3.0 score.

**Score 1–2:** Hard-rule ceiling in effect. A specific structural problem is capping the
score. The report names it. Do not invest without independently resolving the named issue.

**0 or eliminated:** The kill-flag fired in Step 1. Stop. Do not re-examine.

---

## Common Patterns

**"The financials look great but the score is a 2"**

Check Dimension 4 (insider behavior) and the kill-flag detail. A heavy net-sell pattern
concurrent with secondary offerings is a hard cap, regardless of reported financial quality.
Management selling into raises is a structural red flag that narrative cannot overcome.

**"The company just reported great earnings but cheap_pass flagged going concern"**

Read the actual going-concern disclosure. It may have been in a prior-period 10-K and
subsequently cured in an amendment or subsequent filing. Run:

```bash
python tools/cheap_pass.py --ticker XXXX --verbose
```

The `--verbose` flag shows the exact filing, period, and paragraph where the flag was found.
If it was cured (audit report in subsequent 10-K has no going-concern language), the flag
will not appear in the most recent filing — `cheap_pass` only reads the most recent period.

**"deepdive_data returned partial XBRL"**

Common for micro-caps with poor XBRL compliance. The tool logs which concepts are missing.
You can manually retrieve the data from the 10-K income statement and input it as context
to the judgment agent. The rubric will then score normally. Note the manual intervention in
the evidence tier (T2 instead of T1 for that dimension).

---

## Troubleshooting

**EDGAR 403:** Set `sec_user_agent` to `"Name email@domain.com"` in `config.json`.

**CIK not found:** Try `python tools/discover.py --ticker XXXX` to confirm the ticker maps
to a known CIK. Micro-caps occasionally file under a parent CIK rather than the ticker symbol.

**openinsider timeout:** The tool falls back to direct EDGAR Form 4 fetch automatically.
The report will note "(source: EDGAR Form 4 direct, openinsider unavailable)".
