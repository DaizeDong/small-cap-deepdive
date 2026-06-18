# Judgment Rubric — Invariant C

> This is the single source of truth for the deep-dive judgment layer.
> Every deep-dive subagent must score all 7 dimensions and produce the output template below.
> Deviating from this rubric — omitting dimensions, skipping the output template, substituting narrative for scores — renders the report invalid.
>
> Source disciplines: `disclosure-discipline.md` (bias controls) + `cognitive-priors.md` (base rates).
> Mechanical inputs: `deepdive_data.py` JSON (financial series, kill-flags, insider trades).

---

## Before Scoring: Required Preamble

Before touching the 7-dim scorecard, the subagent must complete these in order:

1. **Base rate anchor** — state the reference class and its base rates (see `cognitive-priors.md`)
2. **Disconfirmation search** — run WebSearch for `<company> short report OR fraud OR dilution OR lawsuit OR going concern`; record what was found or explicitly state "searched, nothing found"
3. **Data staleness check** — if any mechanical field has `data_may_be_stale: true`, use WebSearch to verify current values before scoring

Only then open the 7-dim scorecard.

---

## 7-Dimension Scorecard

Each dimension: **score 1–5** + **evidence Tier** (T1/T2/T3) + **one-line basis**.

### Dimension 1 — Financial Quality

Covers: revenue growth quality, profitability path, cash flow, runway, dilution history.

**What to score:**
- Revenue growth: organic vs. acquisition-driven; revenue vs. accounts-receivable growth rate (AR growing faster = receivables stuffing red flag)
- Cash flow: OCF vs. net income divergence; sustained OCF negative with positive net income = red flag
- Runway: see `mechanical-checks.md` Guard 5 for `null` interpretation
- Dilution: share count history (S-3/ATM/death-spiral convertibles in SEC filings)
- Profitability path: clear GAAP breakeven visibility vs. perpetual "adjusted EBITDA"

**Score anchors:**
- 5: Cash-flow positive, organic growth, no dilution, clear profitability
- 3: Mixed signals; one structural concern but not fatal
- 1: Serial dilution, negative OCF, runway < 2 quarters, no path to profitability

**Hard ceiling:** If `has_death_spiral = True`, cap this dimension at 1. If net income is substantially driven by one-time items (e.g., deferred tax release), note it and score on OCF only.

### Dimension 2 — Business Model and Moat

Covers: revenue repeatability, defensibility against large competitors.

**What to score:**
- Revenue model: subscription/contract (recurring) vs. one-time/project-based
- Moat test: "If Microsoft or Google entered this space, would this company survive? Why?"
- Network effects, switching costs, patents, regulatory licenses, scale advantages
- For small-cap: "first-mover advantage" is not a moat answer unless paired with lock-in mechanism

**Score anchors:**
- 5: Demonstrable switching costs or regulatory moat; FANG-entry test passed convincingly
- 3: Niche position with some stickiness but attackable
- 1: No moat; revenue is one-time; product is commodity; FANG-entry would likely eliminate the company

### Dimension 3 — Growth and Unit Economics

Covers: revenue growth decomposition, customer concentration, margin trends.

**What to score:**
- Growth decomposition: volume vs. price vs. M&A contribution
- Customer concentration: any single customer >20% of revenue (search 10-K for "accounted for" percentage disclosures)
- Net retention or churn (SaaS companies: from earnings call transcripts or 10-K)
- Gross margin trend: expanding = operating leverage; shrinking during growth = subsidized growth

**Hard ceiling:** If single customer >40% of revenue, cap this dimension at 2 regardless of growth rate.

### Dimension 4 — Management

Covers: insider trading signals, dilution behavior, track record, guidance accuracy.

**Bias control: this dimension is the highest-risk halo-bias zone. See `disclosure-discipline.md` for mandatory halo de-bias rules.**

**What to score — only evidence independent of stock price performance:**
- Insider trades (openinsider.com or edgartools Form 4): net buy or net sell over past 12 months; cluster selling during fundraising = negative signal
- Historical guidance accuracy: did management hit guidance in the past 4–6 quarters?
- Founder/CEO prior company outcome: what happened to the last company they ran?
- Capital allocation: are buybacks/dividends funded by cash flow or debt? Is compensation aligned with shareholder returns (DEF 14A)?
- Salary vs. company performance: executives drawing large salaries at cash-burning micro-caps is a red flag

**Prohibited sources for this dimension:** Any narrative based on press interviews, conference presentations, LinkedIn profiles, or subjective impressions of "vision" or "execution ability."

**Hard ceiling:** If `insider_net_sell` is materially negative (strong cluster selling) AND dilution rate is high, cap this dimension at 2.

### Dimension 5 — Theme Fit and Timing

Covers: real revenue exposure to the stated theme vs. keyword-only association.

**What to score:**
- Revenue already derived from theme vs. only mentioned in PR/earnings calls
- Time to meaningful theme revenue: already happening vs. 3+ years out
- Whether the theme exposure is already priced in (compare to peers; check if the stock re-rated on AI/theme narrative)
- Crowdedness of the thesis: is this a widely discussed "hidden gem" that is no longer hidden?

**Hard ceiling:** If the company has zero current revenue from the theme and the theme connection appears only in PR/call transcripts (no 10-K business description evidence), cap this dimension at 2. This is the "pure-concept-playing" ceiling.

**Note:** This dimension maps to Gate 2 of `discovery-engine.md`. A company that barely passed Gate 2 as `partial` should score 2–3 here, not 4–5.

### Dimension 6 — Valuation

Covers: current price reasonableness relative to fundamentals and implied assumptions.

**What to score:**
- For revenue-positive, pre-profit companies: EV/Sales vs. comparable peers
- Reverse DCF: what revenue growth rate does the current EV/Sales imply over 5 years? Is that credible given current growth rate and TAM?
- Use fully diluted share count (include options, warrants, convertible debt)
- For asset-heavy businesses: EV/EBITDA, Price/Book if applicable

**Score anchors:**
- 5: Implied growth rate is below current growth rate; trading at discount to peers
- 3: Fair value; priced in line with fundamentals
- 1: Implied growth rate requires heroic assumptions; priced for perfection; EV/Sales >10x with no path to margin

### Dimension 7 — Risk and Counterargument

Covers: the best argument against ownership; zero-path scenarios.

**What to score:**
- Strength of the bear case (can it be falsified, or is it structural?)
- Zero/wipeout scenarios: shelf offering exhausts market demand → bankruptcy; customer concentration → loss of contract → revenue cliff; going-concern finding followed by bank covenant breach
- Short-seller research (if found in mandatory disconfirmation search)
- Regulatory risk, litigation, audit changes
- Liquidity risk: average daily volume — can you exit without moving the price significantly?

**Score anchors:**
- 5: Bear case is weak; main risk is general market downturn; no structural zero path
- 3: Meaningful risks exist but are manageable or partially hedged by business model
- 1: Multiple independent zero paths; short research exists and is factually grounded; kill-flags cluster

---

## Output Template

Every deep-dive report must produce this structure exactly. No field may be omitted; write "N/A — [reason]" if genuinely unavailable.

```
# [TICKER] Deep Dive — <date> (timestamp-locked)

Rating: [BUY / WATCH / AVOID]   Confidence: __%   Holding period: __

## 0. One-line thesis + base-rate anchor
<One sentence stating the core thesis.>
Reference class: <e.g., "pre-revenue micro-cap with AI exposure"> — base rates: ~X% zero/wipeout within 5 years, ~Y% mediocre outcomes, ~Z% acquisition/upside.

## 1. Scorecard

| Dimension | Score (1–5) | Tier | Basis (one line) |
|---|---|---|---|
| 1. Financial quality | | | |
| 2. Business model / moat | | | |
| 3. Growth / unit economics | | | |
| 4. Management | | | |
| 5. Theme fit / timing | | | |
| 6. Valuation | | | |
| 7. Risk / counterargument | | | |
| **Weighted total** | **/35** | | |

Kill-flag count: __ (from mechanical-checks layer)

## 2. Bull case (falsifiable)
- Claim: <specific claim>
  Trigger to flip: <if X does not happen by Q__ , this argument is falsified>

## 3. Bear case (falsifiable) + disconfirmation search results
- Claim: <specific claim>
  Trigger to flip: <if X happens by Q__ , this argument is falsified>

Disconfirmation search: [results or "searched, nothing found"]

## 4. Pre-mortem: most likely path to -80%
<Two or three sentences. Assume you are already wrong — what happened?>

## 5. Kill-flag review
- has_going_concern: [True/False] — <one line on auditor context>
- has_material_weakness: [True/False] — <one line>
- has_death_spiral: [True/False] — <one line on instrument terms>
- customer_concentration_flag: [True/False] — <one line on largest customer %>

## 6. Valuation: implied assumptions
Current EV/Sales: __x   Peer median: __x
Reverse DCF implied growth (5-yr): __%   Actual trailing growth: __%
Assessment: <credible / stretched / heroic>

## 7. Monitor triggers (which 8-Ks / data points change the rating)
- <trigger 1: e.g., "next earnings: if gross margin < X%, WATCH → AVOID">
- <trigger 2: e.g., "Form 4 cluster buying by insiders → re-evaluate rating upward">

## 8. Known gaps and unverified items
- <data point that could not be obtained, with reason>
- <assumption that is load-bearing but unverified>
```

---

## Rating Hard-Rules

These rules override scorecard totals. A high aggregate score does not rescue a report from a hard-rule violation.

| Condition | Hard consequence |
|---|---|
| Any key claim rests solely on T3 evidence | Cannot rate BUY |
| `kill-flag count ≥ 2` (going concern, death spiral, or material weakness) | Default AVOID |
| `insider_net_sell` strongly negative AND dilution rate high | Management dimension capped at 2 |
| Critical data unavailable (runway, revenue, insider trades all null) | Confidence capped at 40% |
| Company has no current revenue from the stated theme (pure concept-playing) | Theme-fit dimension capped at 2; cannot rate BUY solely on theme story |
| Rating is AVOID OR kill-flag count ≥ 3 | Company sinks to bottom of ranking regardless of aggregate score |

---

## Evidence Tier Definitions

- **T1 — Primary / audited:** SEC filings (10-K, 10-Q, Form 4, DEF 14A, 8-K), audited financial statements, court records
- **T2 — Independent third-party:** Analyst reports from non-affiliated firms, short-seller research (reputable), academic studies, verified news reporting with named sources
- **T3 — Company-sourced / unverified:** Press releases, earnings call transcripts without third-party verification, company websites, LinkedIn, unverified social media

T3 evidence may be used as a lead for investigation. It may not be the load-bearing evidence for a BUY rating.

---

## Cross-references

- `disclosure-discipline.md` — mandatory disciplines that govern how this rubric is applied (base-rate-first, forced disconfirmation, halo de-bias, pre-mortem procedure, honest data-gap)
- `cognitive-priors.md` — base-rate prior table (microcap zero rates, de-SPAC median, going-concern correlation) used in Section 0 of the output template
- `mechanical-checks.md` — kill-flag counts and data fields that feed into the hard-rules above
- `discovery-engine.md` — theme-fit score (dim 5) reflects Gate 2 classification
