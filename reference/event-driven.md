# Event-Driven Discovery, Phase 5

> This document is the design and rationale reference for `tools/discover_events.py`.
> Entry workflow: see `SKILL.md §Entry 4 — events`.
> For the theme-driven discovery engine (keyword FTS), see `discovery-engine.md`.

---

## Event-Driven Discovery as a Hypothesis

Event filings offer a separate route for finding candidates whose ownership or trading
conditions have recently changed. Whether that route adds useful candidates or improves
outcomes is a hypothesis to test with dated inputs, comparable coverage and forward results.

The historical theme screens returned no BUY decisions under their selection rules,
data coverage and conservative valuation policy. That observation does not establish
efficient pricing above any market-cap threshold, absence of theme opportunities, or
superior event-driven performance. Selected themes, incomplete coverage and interventions
limit what can be inferred from those runs.

The event types below suggest possible mechanisms for temporary mispricing. A plausible
mechanism is a research rationale, not measured effectiveness of this implementation.
Prospective comparisons must report candidate denominators, failed work, eligibility and
outcomes for both discovery routes.

1. **Spinoffs, Form 10-12B**, forced index-fund selling creates supply overhang.
2. **Cluster open-market insider buys, Form 4**, insiders buying at market price with
   personal capital is the hardest management-conviction signal available.

Both are already enumerated as qualifying catalyst categories (a) and (b) in
`reference/judgment-rubric.md §Catalyst / Forced-Trading Modifier`.  Phase 5 adds a
discovery axis that systematically enumerates these events at the source, feeding the
same downstream deep-dive and rating engine.

---

## Axis 1, Spinoffs: Form 10-12B

### What 10-12B Is

Form 10-12B ("General Form for Registration of Securities") is the SEC registration
statement filed by a company that is being **spun off from or carved out of a larger parent**.
The form registers the spinoff's securities under the Exchange Act, establishing it as an
independent public entity.

A **10-12B/A** is an amendment to an existing 10-12B filing (typically updating disclosures
or responding to SEC comments).

EDGAR full-text search endpoint:
```
https://efts.sec.gov/LATEST/search-index?forms=10-12B&dateRange=custom&startdt=YYYY-MM-DD&enddt=YYYY-MM-DD
```
Returns both `10-12B` and `10-12B/A` when `forms=10-12B` is specified.

### Why Spinoffs Create Mis-Pricing

The forced-selling mechanism is structurally documented:

1. **Index-fund mandate mismatch.** When a company is spun off, it is initially not
   included in the major indices (S&P 500, Russell 2000, etc.) because it has not yet
   satisfied seasoning requirements.  Passive ETFs and index funds that hold the parent
   must sell the spinoff shares they receive in the distribution, their mandates do not
   permit holding non-index securities.

2. **Supply overhang.** This forced selling creates a temporary supply overhang with no
   corresponding natural buyer.  Retail holders may also sell because the spinoff is small,
   unfamiliar, or does not fit their stated strategy.

3. **Price correction window.** Over the 1-3 months after the spinoff effective date,
   forced sellers clear.  If the spinoff's fundamentals are solid, the price stabilizes
   and potentially re-rates upward as the company builds its own analyst coverage.

This mechanism is studied empirically: Cusatis, Miles & Woolridge (1993) documented
significant spinoff outperformance in the first three years.  The anomaly has partially
decayed with wider institutional awareness, but remains a legitimate mis-pricing source
in the small/micro-cap band where index-fund pressure is largest relative to float.

### Parsing Notes

`discover_events.py --spinoffs` uses the EDGAR EFTS response with no keyword query,
only the `forms=10-12B` filter.  This is structurally high-precision by definition.

EFTS `display_names` entries have two variants:
- `"Company Inc.  (TICK)  (CIK 0001234567)"`, ticker already assigned
- `"Company Inc.  (CIK 0001234567)"`, no ticker yet (common for very new registrations)

Both are handled.  Deduplication by CIK keeps the most informative record (prefers the
variant with a ticker; preserves earliest file date).

### Catalyst Record

Each spinoff candidate carries:
```json
{
  "catalyst": "spinoff: Form 10-12B filed 2026-03-15",
  "event_type": "spinoff"
}
```
This is an unverified discovery hint for the rubric's spinoff catalyst category.
The downstream agent must independently verify the T1 filing, the specific forced-selling
mechanism, and every item in the rubric's five-requirement checklist. A form match alone
does not satisfy the catalyst requirement or waive any rating gate.

---

## Axis 2, Cluster Open-Market Insider Buys

### What the openinsider Cluster-Buy Table Is

`http://openinsider.com/latest-cluster-buys` aggregates Form 4 filings where **multiple
insiders at the same company purchased shares in the open market within a recent window**.
The page is already filtered to cluster events, every row represents a company where
≥1 insiders bought, and the "Ins" column shows the count.

`discover_events.py --insider-clusters` parses this HTML table using the same
`HTMLParser` pattern as `deepdive_data.insider_trades` and filters to:
- Trade Type "P - Purchase" (open-market only; no grants, option exercises, or RSU vesting)
- `Ins` column ≥ min_insiders (tool default = **2**, the rubric floor)

Note on the openinsider table: every row in the `/latest-cluster-buys` page represents a
company where openinsider has observed at least one insider buy in their raw aggregation;
the `Ins` column shows the cluster count. The tool applies `--min-insiders 2` (default)
to enumerate at the rubric floor, the `n_insiders` field is surfaced per record so the
deep-dive agent or human analyst can prefer clusters of 3+ for higher conviction.
Set `--min-insiders 3` if you want the tool itself to pre-filter to the higher bar.

### Why Cluster Insider Buys Signal Mis-Pricing

An insider purchasing shares at market price with personal capital is qualitatively
different from any other ownership increase:
- It is **voluntarily funded** (unlike RSU vesting or option exercise).
- It signals that the insider believes the current market price is **below intrinsic value**.
- When **multiple** insiders buy within a short window, the signal strength compounds,
  the probability that all of them are miscalibrated simultaneously is lower.

The Form 4 filing requirement ensures **T1-sourced, audited evidence** of the purchase.

The empirical record is mixed: Seyhun (1986) and Lakonishok & Lee (2001) documented
significant positive returns following insider purchases, particularly for small-caps and
cluster events.  The anomaly has decayed as institutional awareness increased, but the
small-cap / micro-cap cluster-buy signal retains some predictive content where information
diffusion is slowest.

### Column Layout (Empirically Verified)

The `latest-cluster-buys` table has 17 columns (0-indexed):

| Col | Name | Description |
|---|---|---|
| 0 | X | Flags (D=delay, M=multiple days, etc.) |
| 1 | Filing Date | Form 4 filing date (YYYY-MM-DD HH:MM:SS) |
| 2 | Trade Date | Actual trade date |
| 3 | Ticker | Company ticker |
| 4 | Company Name | Full company name |
| 5 | Industry | openinsider industry classification |
| 6 | Ins | Number of insiders in cluster |
| 7 | Trade Type | "P - Purchase" for open-market buys |
| 8 | Price | Share price |
| 9 | Qty | Shares purchased |
| 10 | Owned | Total shares owned post-purchase |
| 11 | %Own | Ownership change percentage |
| 12 | Value | Total dollar value of cluster purchase |
| 13-16 | 1d/1w/1m/6m | Price change since filing |

Column indices are detected from a recognized, unambiguous header row. A missing or
ambiguous required header makes the observation unavailable; the parser does not use
hardcoded column positions to manufacture a successful observation.

### Catalyst Record

Each cluster-buy candidate carries these fields:

| Field | Meaning |
|---|---|
| `catalyst` | Unverified source description of the cluster |
| `event_type` | `insider_cluster` for this discovery path |
| `n_insiders` | Parsed count, subject to independent filing verification |
| `value_usd` | Parsed purchase value, subject to independent filing verification |
This is an unverified cluster-buy discovery hint. Independently verify the relevant Form 4
filings, open-market purchase classification, insider count, and timing against the rubric.
The source label alone does not establish a verified catalyst or permit a BUY.

---

## Why No Theme-Fit Gate Is Needed

The two-stage precision gate (SIC coarse filter + LLM theme-fit gate) in the theme
discovery flow exists because **keyword FTS over-recalls severely**, a term like
"refractory" matches every oncology filing.  The gate is the precision restoration
mechanism for a fundamentally noisy input channel.

Event discovery uses filing-type and source-table filters instead of theme keywords.
Those filters identify observations for review; they do not prove that every hit is a
qualifying spinoff or purchase cluster. A registration filing can require further event
classification, and a source-table row still needs transaction and issuer verification.

Event admission replaces theme-fit decisions for this entry mode because an event need not
belong to an active theme. Preserve the bound event-admission evidence and independently
verify the catalyst mechanism with T1 support. The catalyst freeze and all valuation,
completion, and rating gates continue to apply.

**Practical consequence:** downstream, skip Gate 1 (SIC filter) and Gate 2 (LLM
theme-fit) for event candidates.  The mechanical kill-flag scan (`cheap_pass.py`) still
runs, a compelling catalyst does not excuse a going-concern filing.

---

## Connection to judgment-rubric.md Catalyst Axis

The catalyst MoS waiver in `judgment-rubric.md` is **frozen**. A supported event may
justify WATCH with a catalyst. It does not waive the active MoS threshold, eligibility
requirements or zero-kill-flag rule for BUY. Discovery admission is separate from a rating.

Categories (a) and (b) of the rubric's closed catalyst list map directly to the two
axes enumerated here:
- Category (a) spinoff = Form 10-12B = `--spinoffs` mode
- Category (b) cluster open-market insider purchases = Form 4 cluster = `--insider-clusters` mode

The `catalyst` field in each event candidate record is pre-populated with the dated
trigger.  The downstream agent's job is to verify the forced-trading mechanism claim
(for spinoffs: confirm the index-exclusion mechanics; for insider clusters: confirm
open-market purchase type from Form 4) and populate the rubric's catalyst field.

---

## Honest Caveats

The anomalies documented here are **real but decaying**:

1. **Spinoff signal is partially arbitraged.**  Spinoff-focused hedge funds (GAMCO,
   Third Point, and others) now systematically monitor 10-12B filings.  In the large-cap
   band, the forced-selling window is shorter and the re-rating is faster.  The signal
   persists most strongly in the micro-cap band (<$300M) where institutional arbitrage
   capital is insufficient to clear the overhang quickly.

2. **Cluster insider signal has weakened.**  Post-2010 academic replication finds the
   Seyhun / Lakonishok result substantially reduced in magnitude.  The signal is strongest
   for small clusters (2 to 4 insiders, not 15 to 20) and for micro-caps where the purchase
   is large relative to float.

3. **Liquidity eats gross edge.**  Even when the signal is correct, the spread and
   market impact for a micro-cap position can consume a significant fraction of the
   theoretical alpha.  Net edge after realistic transaction costs is substantially
   lower than gross signal.

4. **Track-forward before trusting any edge.**  Per `cognitive-priors.md`, all
   ratings from this skill are structured hypotheses until validated by a multi-year
   track-forward record.  Event-mode ratings carry the same caveat.  **0 BUY may still
   be the correct output** after running the full event discovery pipeline, a strong
   catalyst does not override zero margin of safety or active kill-flags.

5. **openinsider data quality.**  openinsider aggregates SEC Form 4 filings but is not
   the authoritative source.  Verify any large-dollar cluster buy directly in EDGAR
   Form 4 filings before treating it as T1 evidence.

---

## Cross-References

- `SKILL.md §Entry 4`, workflow orchestration for event-driven runs
- `judgment-rubric.md §Catalyst / Forced-Trading Modifier`, rubric integration for
  categories (a) spinoff and (b) cluster insider buy
- `cognitive-priors.md §5`, limits of the historical zero-BUY observation and the
  evidence needed to test event-driven discovery
- `discovery-engine.md`, for event-driven discovery see this document (event-driven.md)
- `mechanical-checks.md`, kill-flag scan still mandatory for event candidates
