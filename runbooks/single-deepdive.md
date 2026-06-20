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
cp reference/config.example.json \
   reference/config.json
```

Set `"sec_user_agent"` in `config.json` to your real name and email.
EDGAR blocks requests with a missing or obviously fake User-Agent.

Then open a run batch (start of every run) so outputs stay grouped and version-comparable:

```bash
export SMALLCAP_RUN=$(python tools/new_run.py --label <ticker>)   # e.g. --label EGAN
```

→ outputs land in `reports/smallcap/<date>_<label>/` with a `_run.json` manifest. Unset → flat (legacy).

---

## Step 1 — Mechanical De-Risk First

Always run `cheap_pass` before any qualitative work. If the company fails a hard kill-flag,
stop — do not spend judgment budget on a structurally disqualified candidate.

```bash
python tools/cheap_pass.py --universe <any_universe_csv_containing_EGAN>
```

Or run the selftest to verify the tool works:

```bash
python tools/cheap_pass.py --selftest
```

Expected output — pass (no going-concern, no death spiral, no material weakness in latest 10-K):

```
[cheap_pass] EGAN (eGain Corp, CIK 1066194)
  going_concern:     False
  death_spiral:      False
  material_weakness: False
RESULT: PASS — proceed to deep-dive
```

Expected output — eliminated:

```
[cheap_pass] GATO
  going_concern: True
    "going concern" + "substantial doubt" found in 10-K 2025-03-15
RESULT: ELIMINATED — do not deepdive
```

**If eliminated:** Report the kill-flag and stop. The hard-rule is not an invitation to
argue — it is a floor. A company with an auditor going-concern opinion has a >50% base-rate
probability of either restructuring, being acquired at distressed valuation, or delisting
within 24 months.

**Token magnitude:** Negligible — deterministic EDGAR filing fetch and parse, no LLM calls.
Runtime: 30–90 seconds.

---

## Step 2 — Data Pull

```bash
python tools/deepdive_data.py --ticker EGAN
```

Output: `reports/smallcap/deepdive_EGAN_<date>.json`

Expected output:

```
深度尽调数据拉取: EGAN (CIK 1066194)
  拉财务序列...
  拉内部人交易...
  拉 10-K 章节...

=== EGAN 数据摘要 ===
  营收: $xxx.xM (增速 x.x%)
  净利: $x.xM | OCF: $x.xM
  现金: $x.xM | runway: None 期
  ...
数据: reports/smallcap/deepdive_EGAN_<date>.json
```

**What it pulls:**

| Data | Source | Notes |
|---|---|---|
| Revenue, OCF, cash | EDGAR XBRL | Partial XBRL common for micro-caps |
| Insider trades | Form 4 via openinsider | Direction: P=purchase, S=sale |
| Dilution history | Shares outstanding series from XBRL | |
| 10-K text excerpt | edgartools (amendments=False) | risk_excerpt + kill-flag recheck |

**Token magnitude:** Negligible — deterministic fetch, no LLM calls.
Runtime: 2–8 minutes (EDGAR rate limit: ~150ms between requests).

---

## Step 3 — Judgment Pass

In your Claude Code session, instruct the agent:

```
Deep-dive report for EGAN (eGain Corp, CIK 1066194) using data from
reports/smallcap/deepdive_EGAN_<date>.json.
Theme context (if any): "SaaS for regulated industries" [omit if no theme].

Required preamble before scoring:
  a. Open reference/cognitive-priors.md. State the applicable base-rate priors
     for a ~$150M revenue-positive SaaS company. Note which priors apply.
  b. Run WebSearch: "eGain Corp EGAN fraud lawsuit SEC investigation short seller
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
node workflows/deepdive-fanout.js '[{"ticker":"EGAN","cik":"1066194","name":"eGain Corp","theme":"SaaS for regulated industries","horizon":"12-18M","theme_slug":"saas","mktcap":150000000,"health_score":75,"killflag_count":0}]'
```

**Token magnitude:** ~8k–15k tokens per company.

Cost: <$0.02 per company at Sonnet pricing.

---

## Step 4 — Reading the Output

A well-formed single-company output follows the template from `reference/judgment-rubric.md`:

```
# EGAN Deep Dive — 2026-06-18 (timestamp-locked)

Rating: WATCH   Confidence: 68%   Holding period: 12-18M

## 0. One-line thesis + base-rate anchor
eGain Corp provides AI-powered customer engagement SaaS to regulated industries (banking,
insurance, telecom); revenue is growing modestly but the company remains pre-GAAP-profit.
Reference class: revenue-positive micro-cap SaaS with AI positioning — base rates: ~30-40%
zero/wipeout within 5 years, ~40% mediocre, ~20-30% acquisition/upside.

## 1. Scorecard

| Dimension | Score (1–5) | Tier | Basis (one line) |
|---|---|---|---|
| 1. Financial quality | 3 | T1 | OCF positive 3 of last 4 quarters; modest growth |
| 2. Business model / moat | 3 | T1 | Contract-based SaaS; switching costs exist but not deep |
| 3. Growth / unit economics | 3 | T1 | Low-double-digit growth; no customer >20% concentration |
| 4. Management | 3 | T1 | Form 4: net neutral last 12M; guidance accuracy moderate |
| 5. Theme fit / timing | 4 | T1 | Core business IS AI-assisted customer service — real revenue, not PR |
| 6. Valuation | 3 | T1 | EV/Sales ~2.5x; in-line with small-cap SaaS peers |
| 7. Risk / counterargument | 3 | T2 | Competition from Salesforce/Zendesk is real; no short reports found |
| **Weighted total** | **22/35** | | |

Kill-flag count: 0

## 2. Bull case (falsifiable)
- Claim: eGain will reach consistent OCF-positive by Q3 2026.
  Trigger to flip: if OCF does not reach >$0 by Q3 2026 earnings, financial quality thesis fails.

## 3. Bear case (falsifiable) + disconfirmation search results
- Claim: Salesforce enters the regulated-industry AI engagement space directly, eroding eGain's niche.
  Trigger to flip: if Salesforce announces targeted regulated-industry feature set by Q2 2026, revisit.

Disconfirmation search: no short reports, fraud allegations, or material litigation found as of 2026-06-18.

## 4. Pre-mortem: most likely path to -80%
The key contract with a top-5 banking customer is not renewed in Q1 2026; revenue drops 20%.
The company draws on its credit facility; covenant triggers an accelerated repayment demand.
A dilutive offering at -50% is announced. Existing holders sell, compounding the decline.

## 5. Kill-flag review
- has_going_concern: False
- has_material_weakness: False
- has_death_spiral: False
- customer_concentration_flag: True — one customer ~15% of revenue per 10-K Item 7

## 6. Valuation: implied assumptions
Current EV/Sales: ~2.5x   Peer median: ~3.0x
Reverse DCF implied growth (5-yr): ~12%   Actual trailing growth: ~14%
Assessment: credible — slight discount to peers

## 7. Monitor triggers
- Next earnings: if gross margin < 65%, WATCH → AVOID
- Form 4 cluster buying by insiders > $200k in next quarter → re-evaluate upward

## 8. Known gaps and unverified items
- EV/EBITDA not computable (XBRL depreciation not tagged); EV/Sales used as substitute
- openinsider returned 12M data; older Form 4 history not verified
```

---

## Interpreting the Score

**Score 4–5:** No structural red flags. Real business, real cash flow, insider alignment.
This is what the tool exists to surface — a candidate worth actual human research time.

**Score 3:** Borderline. One dimension is weak. Read the specific dimension note to decide
if the weakness is temporary or structural. Do not infer "buy" from a 3.0 score.

**Score 1–2:** Hard-rule ceiling in effect. A specific structural problem is capping the
score. The report names it. Do not invest without independently resolving the named issue.

**0 or eliminated:** The kill-flag fired in Step 1. Stop. Do not re-examine.

---

## Common Patterns

**"The financials look great but the score is a 2"**

Check Dimension 4 (management) and the kill-flag detail. A heavy net-sell pattern
concurrent with secondary offerings is a hard cap, regardless of reported financial quality.

**"The company just reported great earnings but cheap_pass flagged going concern"**

Read the actual going-concern disclosure. It may have been in a prior-period 10-K and
subsequently cured. `cheap_pass` only reads the most recent 10-K (`amendments=False`).
If the latest 10-K has no going-concern language, the flag will not appear.

---

## Troubleshooting

**EDGAR 403:** Set `sec_user_agent` to `"Name email@domain.com"` in `config.json`.

**CIK not found:** Try `python tools/discover.py --theme <ticker>` to confirm the ticker maps
to a known CIK. Micro-caps occasionally file under a parent CIK rather than the ticker symbol.

**openinsider timeout:** The tool falls back to direct EDGAR Form 4 fetch automatically (note:
EDGAR Form 4 direction parsing is a roadmap item; the report will note data unavailability).
