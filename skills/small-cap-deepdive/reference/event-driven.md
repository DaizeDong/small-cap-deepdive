# Event-Driven Discovery — Phase 5

> This document is the design and rationale reference for `tools/discover_events.py`.
> Entry workflow: see `SKILL.md §Entry 4 — events`.
> For the theme-driven discovery engine (keyword FTS), see `discovery-engine.md`.

---

## Why Event-Driven, Not Theme-Driven

The run-3 hunting-grounds audit established a key empirical result:

> Theme/industry discovery is efficiently priced in the >$200M market-cap band.
> The mispricing that small capital can still capture is overwhelmingly **event-driven /
> forced-trading** — not static "cheap neglected value" within a sector.

This is not a theoretical claim.  The run-3 evidence was:
- Three full theme runs (~40 deep dives) across industrials, deathcare, ag inputs, and AI.
- BUY count across all runs: **0**.
- The WATCH ratings were mostly correct — efficiently priced cyclicals with no margin of safety.
- The rubric's BUY trigger (Phase 3, `margin_of_safety_pct ≥ 30%`) is conservative by design
  (12% cap rate on normalized FCF), but even at that bar, no theme company cleared it.

The implication: the structural alpha remaining in small-cap equities is concentrated in
**temporary mis-pricings created by forced trading or information asymmetry around specific
filing events**, not in "undiscovered value" within identifiable sectors.

Two event types have theoretical and empirical backing as sources of persistent (if decaying)
structural mis-pricing:

1. **Spinoffs — Form 10-12B** — forced index-fund selling creates supply overhang.
2. **Cluster open-market insider buys — Form 4** — insiders buying at market price with
   personal capital is the hardest management-conviction signal available.

Both are already enumerated as qualifying catalyst categories (a) and (b) in
`reference/judgment-rubric.md §Catalyst / Forced-Trading Modifier`.  Phase 5 adds a
discovery axis that systematically enumerates these events at the source, feeding the
same downstream deep-dive and rating engine.

---

## Axis 1 — Spinoffs: Form 10-12B

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
   must sell the spinoff shares they receive in the distribution — their mandates do not
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

`discover_events.py --spinoffs` uses the EDGAR EFTS response with no keyword query —
only the `forms=10-12B` filter.  This is structurally high-precision by definition.

EFTS `display_names` entries have two variants:
- `"Company Inc.  (TICK)  (CIK 0001234567)"` — ticker already assigned
- `"Company Inc.  (CIK 0001234567)"` — no ticker yet (common for very new registrations)

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
This directly satisfies the rubric's catalyst category (a):
> "(a) Spinoff filings: Form 10-12B or 15-12B on file, with a documented index-fund /
> mandate forced-selling mechanism."

The downstream agent must still verify and populate the `catalyst` field with the
specific forced-selling mechanism per the rubric's five-requirement checklist.

---

## Axis 2 — Cluster Open-Market Insider Buys

### What the openinsider Cluster-Buy Table Is

`http://openinsider.com/latest-cluster-buys` aggregates Form 4 filings where **multiple
insiders at the same company purchased shares in the open market within a recent window**.
The page is already filtered to cluster events — every row represents a company where
≥1 insiders bought, and the "Ins" column shows the count.

`discover_events.py --insider-clusters` parses this HTML table using the same
`HTMLParser` pattern as `deepdive_data.insider_trades` and filters to:
- Trade Type "P - Purchase" (open-market only; no grants, option exercises, or RSU vesting)
- `Ins` column ≥ min_insiders (tool default = **2**, the rubric floor)

Note on the openinsider table: every row in the `/latest-cluster-buys` page represents a
company where openinsider has observed at least one insider buy in their raw aggregation;
the `Ins` column shows the cluster count. The tool applies `--min-insiders 2` (default)
to enumerate at the rubric floor — the `n_insiders` field is surfaced per record so the
deep-dive agent or human analyst can prefer clusters of 3+ for higher conviction.
Set `--min-insiders 3` if you want the tool itself to pre-filter to the higher bar.

### Why Cluster Insider Buys Signal Mis-Pricing

An insider purchasing shares at market price with personal capital is qualitatively
different from any other ownership increase:
- It is **voluntarily funded** (unlike RSU vesting or option exercise).
- It signals that the insider believes the current market price is **below intrinsic value**.
- When **multiple** insiders buy within a short window, the signal strength compounds —
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

Column indices are detected dynamically from the header row to guard against layout changes.
Hardcoded fallback indices are used if the header row is absent.

### Catalyst Record

Each cluster-buy candidate carries:
```json
{
  "catalyst": "cluster insider buy: 3 insiders, $2,038,036, trade date 2026-06-15",
  "event_type": "insider_cluster",
  "n_insiders": 3,
  "value_usd": 2038036
}
```
This directly satisfies the rubric's catalyst category (b):
> "(b) Cluster open-market insider purchases: Form 4 filings showing ≥2–3 insiders
> purchasing shares at market prices within any rolling 90-day window."

---

## Why No Theme-Fit Gate Is Needed

The two-stage precision gate (SIC coarse filter + LLM theme-fit gate) in the theme
discovery flow exists because **keyword FTS over-recalls severely** — a term like
"refractory" matches every oncology filing.  The gate is the precision restoration
mechanism for a fundamentally noisy input channel.

Event discovery uses a **structurally different input channel**:
- A Form 10-12B is definitionally a spinoff registration filing.  There is no false
  positive class: every 10-12B hit is a spinoff or carve-out, by SEC definition.
- A row in openinsider's cluster-buy table is definitionally a multi-insider open-market
  purchase cluster.  The page is already filtered; no keyword matching is involved.

The form-type filter replaces keyword precision.  Applying a theme-fit gate on top of
these results would be incorrect: it would drop spinoffs and insider-cluster companies
that happen not to fit any currently active theme, which is exactly the set of
under-covered companies the event mode is designed to surface.

**Practical consequence:** downstream, skip Gate 1 (SIC filter) and Gate 2 (LLM
theme-fit) for event candidates.  The mechanical kill-flag scan (`cheap_pass.py`) still
runs — a compelling catalyst does not excuse a going-concern filing.

---

## Connection to judgment-rubric.md Catalyst Axis

The Phase 3 symmetric BUY trigger in `judgment-rubric.md` includes a **catalyst modifier**:

> If all five requirements are met [category match, T1-evidenced, dated trigger,
> forced-trading mechanism, catalyst field populated], the MoS threshold is waived and
> BUY is permissible even at MoS < 30%, subject to the same zero-kill-flag guardrails.

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
   for small clusters (2–4 insiders, not 15–20) and for micro-caps where the purchase
   is large relative to float.

3. **Liquidity eats gross edge.**  Even when the signal is correct, the spread and
   market impact for a micro-cap position can consume a significant fraction of the
   theoretical alpha.  Net edge after realistic transaction costs is substantially
   lower than gross signal.

4. **Track-forward before trusting any edge.**  Per `cognitive-priors.md`, all
   ratings from this skill are structured hypotheses until validated by a multi-year
   track-forward record.  Event-mode ratings carry the same caveat.  **0 BUY may still
   be the correct output** after running the full event discovery pipeline — a strong
   catalyst does not override zero margin of safety or active kill-flags.

5. **openinsider data quality.**  openinsider aggregates SEC Form 4 filings but is not
   the authoritative source.  Verify any large-dollar cluster buy directly in EDGAR
   Form 4 filings before treating it as T1 evidence.

---

## Cross-References

- `SKILL.md §Entry 4` — workflow orchestration for event-driven runs
- `judgment-rubric.md §Catalyst / Forced-Trading Modifier` — rubric integration for
  categories (a) spinoff and (b) cluster insider buy
- `cognitive-priors.md §5` — run-3 audit finding that event-driven is where remaining
  edge lives; honest caveat that anomalies are decaying (one line below)
- `discovery-engine.md` — for event-driven discovery see this document (event-driven.md)
- `mechanical-checks.md` — kill-flag scan still mandatory for event candidates
