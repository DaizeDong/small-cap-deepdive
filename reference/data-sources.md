# Data Sources, Invariant E

> This is the routing guide for the data layer. It covers what free sources can provide, what they cannot, and how to use them responsibly.
> It also covers the market-intel read-only catalog reuse pattern, the X sentiment route, and the anti-recursion rule.
>
> See `mechanical-checks.md` for the five Python guards that govern how these sources are used in `tools/*.py`.
> See `judgment-rubric.md` + `disclosure-discipline.md` for how the data retrieved here feeds judgment.

---

## Primary Free Sources

### EDGAR (SEC), Authoritative, No Key Required

**What it provides:**
- Full-text of all SEC filings since 2001 (`efts.sec.gov` FTS endpoint)
- Structured XBRL financial data (`data.sec.gov/api/xbrl/companyfacts/` and `companyconcept/`)
- Form 4 insider transactions (full filing history)
- DEF 14A proxy statements (compensation, share ownership)
- 8-K material events (earnings, secondary offerings, going-concern disclosures)
- S-3 / 424B5 shelf and ATM offering documents
- SC 13D/13G significant ownership disclosures

**Rate limit discipline (mandatory):**
- Maximum 10 requests/second across all EDGAR endpoints from a single IP (SEC policy)
- Every request must include `User-Agent: <name> <email>` header, omission causes 403 errors
- Target ~150ms between requests: each `tools/*.py` script sleeps between consecutive EDGAR calls
- On 429/500 response: exponential backoff via `_common.http_get` (start 1.5s × 2^attempt, 4 retries)

**Implementation:** `_common.http_get` provides the UA header + retry/backoff wrapper for all
EDGAR `requests.get` calls in the data layer. Every `tools/*.py` script must route EDGAR HTTP
calls through `http_get`, not raw `requests.get`. Per-tool `time.sleep` between calls adds
a second layer of inter-request spacing. There is no semaphore or central rate limiter ,
discipline is maintained via per-tool sleep + `http_get` retry.

**Tools:** `edgartools` (MIT license) is the primary wrapper for structured parsing (XBRL,
Form 4, full-text). Do not build a direct `requests`-based EDGAR client without adding the
rate discipline above.

**Blind spots:**
- No real-time data; filings have typical 1 to 4 day lag after company submits
- XBRL data quality varies by company size, micro-caps often have incomplete or malformed concept tags
- Form 4 direction parsing in `edgartools` was found unreliable in production (fix #3); use `openinsider` as the primary Form 4 source (see below)

### openinsider.com, Insider Trades, Public Tables

**What it provides:** Parsed Form 4 insider transactions with buy/sell direction (P/S code), transaction type, and price. The static HTML tables are scrape-able without authentication.

**How to use:** Fetch the company's insider transaction page by ticker or CIK. Parse the `P` (purchase) and `S` (sale) codes in the transaction table. Compute net buy/sell balance over the past 12 months.

**Fragility note:** `openinsider.com` is a third-party service scraping SEC data. Its availability is not guaranteed. Its terms of service are not explicitly open for automated access. In the public version of this skill, `edgartools Form 4` with custom direction parsing is the default; `openinsider` is an optional enhancement. Label it as such in reports: "(source: openinsider, public, fragility noted)".

**Fallback:** If `openinsider` is unavailable, fetch Form 4 filings directly from EDGAR for the target CIK and parse the transaction code from the XML. The direction parsing was previously unreliable (`edgartools` bug), but a custom parser for the `transactionCode` field (`P`=purchase, `S`=sale) in the Form 4 XML is straightforward and reliable.

### yfinance, Convenience Layer for Market Data

**What it provides:** Current price, market cap, EV, basic financial ratios, earnings calendar.

**Known limitations for micro-caps:**
- Many fields are missing or `NaN` for micro-caps (EV, float, revenue)
- Data freshness is not guaranteed; fields may lag by days
- Do not use as the primary source for any metric that can be computed from EDGAR; use yfinance only as a quick-check or when EDGAR computation would be disproportionately expensive

**When to use:** Initial market cap screening (cheap_pass.py uses it to confirm the company is still in the target market cap band). Current price for reverse-DCF calculation. **And, as of iteration 5, the P7 second-source sanity band** (below), the one place yfinance is read as an INDEPENDENT cross-check on SEC-XBRL fundamentals rather than only for the mktcap denominator.

#### P7, Second-Source Sanity Band (debt / revenue / shares cross-check)

Until iteration 5, every financial datum in the decision path was SEC XBRL and every data-integrity guard (the C1a/C1b/C1c internal-consistency checks) operated on that *same* feed, so all of them were structurally blind to a corruption that looks internally reasonable but is externally wrong (HCI's plausible $246M revenue behind a failed SIC fetch → +118% pseudo-BUY; AL's sub-entity $331M revenue + 200-share tag; HRI's truncated $11M debt). P7 adds the FIRST external check.

- **What it does.** On **survivors only** (at the deepdive level, after `cheap_pass`, to respect EDGAR/yfinance rate limits), `deepdive_data.py` fetches a SECOND, INDEPENDENT source for `total_debt` / `revenue` / `shares_outstanding` from yfinance (`Ticker(t).info` totalDebt / totalRevenue / sharesOutstanding, falling back to `.balance_sheet` / `.financials` / `.get_shares_full`, newest non-null) and compares it to the SEC-XBRL-derived `latest_total_debt` / `latest_revenue` / `latest_shares`.
- **What it emits** (into the deepdive `derived` block, read by `valuation.py`, NOT the firewalled `signals` namespace):
  - `cross_source_checked` (bool), True if at least one field had BOTH a SEC and a yfinance value.
  - `cross_source_mismatch` (bool), True if, for ANY field where both values are present and non-trivial (`abs > $1M` floor), `max(a,b)/min(a,b) > 2.5` (a gross disagreement that means the single SEC value cannot be trusted).
  - `cross_source_detail` (str), which field(s) disagreed + both values + the ratio.
- **It is a DATA-INTEGRITY gate, and that is the point.** `valuation.py` ANDs `(not cross_source_mismatch)` into `buy_eligible`; a mismatch forces `buy_eligible = false`, adds `cross_source_mismatch` to `buy_ineligible_reasons`, and downgrades a would-be static-MoS BUY → WATCH/abstain. This is deliberately DIFFERENT from the firewalled diagnostic side-channel below (P15/P16/P17): those are between-filings *market* signals that may NEVER originate or up-weight a BUY and are firewalled out of the decision path. P7 is about *trusting the input numbers themselves*, blocking BUY when the SEC input is grossly contradicted by an independent source is exactly what a data-integrity gate should do, so it lives in `derived` (the decision path), not in `signals`.
- **It NEVER blocks on an absent second source.** The fetch is guarded end-to-end (returns None on any failure, no ticker, import error, network error, all-null `.info`; never raises) and `_cross_source_check` is a pure comparator. If yfinance is unavailable or yields no comparable field (one-sided or sub-floor), `cross_source_checked = false` and `cross_source_mismatch = false`, and the name flows through the gates exactly as before P7. The diagnostic check can never take down the T1 pipeline or false-block a name on missing data.

### Finnhub / FMP / Alpha Vantage, Optional Free APIs

**Availability:** These services require API keys with rate limits. They are listed here for completeness; `config.json` has slots for these keys. The skill runs without them, EDGAR + yfinance is the baseline.

| Service | Free tier | Useful for |
|---|---|---|
| Finnhub | 60 req/min | Earnings call transcripts (partial), real-time quotes |
| Financial Modeling Prep (FMP) | 250 req/day | Peer group comparison, analyst estimates |
| Alpha Vantage | 25 req/day | Alternative financial data, news sentiment |

**Do not use if not configured.** Missing keys should produce a warning, not a crash. The skill degrades gracefully to EDGAR + yfinance.

---

## What Free Sources Cannot Provide (Blind Spots)

These are explicitly out of scope for the free-source tier. If a judgment requires this data, note it as a data gap in Section 8 of the output template.

| Data type | Why unavailable free | Impact |
|---|---|---|
| New address additions / store openings | Requires geo-data or satellite imagery services | Cannot mechanically track physical expansion |
| Smart money / 13F institutional flows | 13F filings are public but parsing 3-month lag; sector aggregation services are paid | Cannot get real-time institutional positioning. *Partially addressed diagnostically:* the firewalled side-channel (P17, `signals.py`) enumerates 13D/13G (lower lag) + best-effort FINRA short interest as labeled, staleness-tagged positioning context, never a trigger |
| On-chain / crypto asset valuations | Not applicable to traditional small-caps; specialized chain data is paid | N/A for standard theme deepdives |
| Credit default swap / bond spreads | Paid data vendor | Cannot assess credit market signal for distressed names |
| Premium alternative data (card-spend panels, full clickstream/web-traffic panels, job-posting feeds) | Paid vendors (Bloomberg 2nd Party, Similarweb, LinkUp) for the high-resolution panels | Cannot get panel-grade revenue reconstruction. **But free coarse proxies DO exist**, see note below; this row covers only the paid high-resolution tier |
| Glassdoor employee sentiment | Anti-scraping measures + litigation risk as of 2026 | Use insider trades + compensation instead |
| LinkedIn data | Anti-scraping enforcement | Use Form 4 + DEF 14A instead |

**Correction, free coarse alt-data exists (philosophy-neutral note).** The blind-spots table above
is about *panel-grade* paid alt-data. It is NOT true that all between-quarters demand signal is
paid-vendors-only. Free, session-level sources of coarse demand/attention proxies exist and are live:

- **TrendsMCP** (free tier), growth-rate (not just level) across Google Search / News / Shopping /
  YouTube / Wikipedia / TikTok / Amazon / app-downloads / Steam / npm / news-sentiment / news-volume.
- **GDELT**, global news tone and volume, ~15-minute cadence, free.
- **google-news-trends-mcp** and free app/play-store scrapers, coarse rank/review/volume signal.

These are coarse and noisy relative to paid panels, but they exist for free. **Stating that they
exist is philosophy-neutral and is corrected here.** The firewalled diagnostic side-channel that
consumes between-filings signal (corroboration-only, never originates or up-weights a BUY,
track-forward-gated until it has its own Brier) was **APPROVED in iteration 1 (§5-Q2) and is now
BUILT in iteration 4**, see "The Firewalled Diagnostic Side-Channel" below. It does NOT change
the firewall: the mechanical decision layer (valuation.py + `buy_eligible` + the BUY trigger)
remains strictly T1-only (EDGAR/XBRL + the mktcap denominator). The side-channel lives in a
SEPARATE top-level `signals` namespace and is read only as labeled T2 context. See
`PHILOSOPHY.md` ("Operationalizing the diffusion thesis") for the conservative/expansive split.

---

## The Firewalled Diagnostic Side-Channel (iteration 4, §5-Q2 approved)

> The between-filings signal layer. **DIAGNOSTIC-ONLY.** This is the single most important
> invariant of the layer: every signal here lives in a SEPARATE top-level `signals` namespace in
> the deepdive output (a sibling of `derived`, NEVER inside it). `valuation.py`, the `buy_eligible`
> composite, and the BUY trigger **MUST NOT read any `signals.*` field.** A BUY stays anchored to
> T1 filing-derived valuation + zero kill-flags + `buy_eligible`. Signals may be READ by an
> analyst/agent as labeled T2 context and snapshotted by `track_forward` for FUTURE per-signal
> Brier calibration, they can NEVER originate or up-weight a BUY. This is how the diffusion thesis
> gets operationalized WITHOUT rebuilding the confident-but-wrong narrative engine.

The layer has three signals. Two are **programmatic** (computed in `tools/signals.py`, written under
the deepdive's top-level `signals` key by `tools/deepdive_data.py`). One is **agent-gathered** (the
MCP sources are not callable from Python; the agent reads them at analysis time).

### P16, Fundamental-vs-Price divergence (programmatic, `tools/signals.py`)

The most direct operationalization of the thesis: it compares the T1 fundamental trajectory against
the trailing price move and labels the divergence.

- **Source:** `yfinance` trailing 6m / 12m total return (dividend-adjusted close where available).
  This is the ONE place price-return is treated as in-scope, and it is quarantined to this
  diagnostic namespace, never the mktcap denominator or any gate.
- **Trajectory leg is READ, not recomputed.** `signals.py` reads `rev_slope_sign`,
  `contamination_ratio`, and `fundamental_decline_flag` from the deepdive `derived` block (the
  same deterministic T1 fields `valuation.py` uses). It only adds the price leg and the label.
- **`divergence_label` ∈ {`unpriced_improvement`, `melting_ice_cube_priced`, `aligned`, `unclear`}:**
  fundamentals improving (`rev_slope > 0`, no decline flag) AND price flat/down ⇒
  `unpriced_improvement` (THE diffusion thesis, a real change the market may not have priced);
  fundamentals declining AND price up/elevated ⇒ `melting_ice_cube_priced` (SIGA-shaped: the
  decline is already in the tape, no edge); trajectory and tape agreeing ⇒ `aligned`; missing
  price or a flat/mixed configuration ⇒ `unclear`.
- **Output:** `signals.price_divergence = {price_return_6m, price_return_12m, price_source,
  fundamental_trajectory{…, read_from}, divergence_label, note}`. The label is a hypothesis to
  weigh, not a trigger.

### P17, Ownership / short-interest positioning (programmatic, `tools/signals.py`)

Free positioning context that hardens both sides of the thesis: activist/institutional accumulation
precedes re-rating; rising short interest + an active shelf telegraphs dilution before the next 10-Q.

- **13D/13G, EDGAR EFTS.** `signals.py` enumerates recent SC 13D / SC 13G (and `/A`) filings for
  the subject CIK via the same `efts.sec.gov` endpoint `discover_events.py` uses for 10-12B
  (overlaps P11's 13D catalyst category by design, shared enumeration, subject to the EDGAR rate
  discipline below). 13D specifically is the canonical small-cap catalyst (Brav/Jiang ~+7%
  abnormal return). Output is newest-first `{form, file_date, filer}` rows.
- **Short interest, FINRA, best-effort.** Bi-monthly, free, no key. If reachable it is recorded;
  if not (no contractually-stable free endpoint), `short_interest_pct` / `short_trend` are `null`
  with an explicit `staleness_note`. Even when present, FINRA short interest is ALWAYS stale
  relative to today (bi-monthly cadence), the staleness is labeled explicitly per the
  positioning-never-a-trigger rule (cf. the 13F 3-month-lag blind spot in the table above).
- **Output:** `signals.ownership = {recent_13d_13g[], recent_13d_13g_count, short_interest_pct,
  short_trend, staleness_note}`. Positioning context only, never a trigger.

### P15, Alt-data corroboration (AGENT-gathered T2 context, NOT in `signals.py`)

The free coarse alt-data sources catalogued just above (TrendsMCP / GDELT / news-volume /
news-sentiment) are **session-level MCP tools, not callable from Python**, so they are NOT computed
in `signals.py`. They are gathered **by the analyst/agent at analysis time** as labeled T2 evidence
that may CORROBORATE a between-filings fundamental-change hypothesis (e.g. an `unpriced_improvement`
divergence backed by rising search/news-volume on the company's product). Same firewall: gate hard
to business-model fit, read as T2 context only, **never originate or up-weight a BUY**, and
track-forward-gated until the alt-data has earned its own Brier. The agent records what it pulled in
the report's T2 diagnostic section so the snapshot can be calibrated later.

### Robustness + the namespace contract

- `signals.compute_signals(ticker, cik, deepdive_derived)` NEVER raises: on any failure it returns a
  partial dict plus `signals_error`. `deepdive_data.py` guards the call again and sets `signals_error`
  rather than crashing the deepdive, the diagnostic layer can never take down the T1 pipeline.
- `signals.signals_meta` carries the firewall flags (`diagnostic_only: true`,
  `never_affects_buy: true`, `sources`, `notes`) so the invariant is machine-readable.
- The deepdive writes this under a TOP-LEVEL `signals` key (sibling of `derived`). Nothing in the
  decision path (`valuation.py`, `buy_eligible`, the BUY trigger) references the `signals` namespace.

> All three signals are strictly diagnostic. They exist to let an analyst weigh between-filings
> evidence and to let `track_forward` accumulate per-signal predictive value for FUTURE calibration.
> Until each signal has its own Brier score, none of them gates anything.

---

## market-intel Read-Only Catalog Reuse

This is the pattern for accessing qualitative research sources (X sentiment, Reddit, web scraping, finance news).

**Core design:** The skill does not call `market-intel` as a skill at runtime. Instead, it reads `market-intel`'s reference catalog to learn which MCP tools or search queries to use for a given information need, then directly calls those tools.

**What to read:**
- your `market-intel` skill install's `reference/sources-index.md`, master index of sources by category
- Relevant shards: `x-twitter.md`, `reddit.md`, `web-scraping.md`, `finance-markets.md`

**How to use:**
1. Identify the information need (e.g., "X sentiment on ticker $RAIL")
2. Read the relevant market-intel shard to find the appropriate tool or query pattern
3. Use that tool directly in the current session (it is a session-level MCP tool, already available)

**No back-edge rule (structural, mandatory):**
- `market-intel` may not call `small-cap-deepdive` at any point
- `small-cap-deepdive` reads market-intel's catalog (read-only pointer) and uses the underlying tools directly
- This is not a skill-to-skill call; it is a routing lookup followed by a direct tool call
- There is no call graph edge from `market-intel` back to `small-cap-deepdive`

**Why this is structurally not recursive:** The market-intel catalog provides routing knowledge (which tool to use for which query), not runtime execution. The tools themselves (MCP servers) are session-level and available directly. Reading a catalog file to decide which tool to call is equivalent to reading documentation, it does not create a runtime dependency.

**Graceful degradation (market-intel not installed):**
If a `market-intel` skill install is not present:
- Use EDGAR as the primary source for all financial data (already covered above)
- Use WebSearch for X sentiment, news, and web presence (acceptable quality for most use cases)
- Use `openinsider` for insider trades (already covered above)
- Document in the report that market-intel catalog was not used and WebSearch was substituted

The skill is fully functional without market-intel. Market-intel is an enhancement that provides access to curated, higher-quality sources with better routing logic.

---

## X Sentiment Route, twitterapi.io Resale (Route ②)

When X/Twitter sentiment is needed for a ticker:

**Default route: twitterapi.io resale (②)**

This is a resale API that uses the provider's own account pool and proxy infrastructure. The user's personal X/Twitter account is never involved. This eliminates account suspension risk entirely.

**Availability:** The `twitterapi.io` key lives in your `market-intel` install's private secrets directory (path per that skill's own config), and its hosted MCP is registered in your local Claude config. This repo neither stores nor duplicates it, and does not depend on a fixed location for it.

**Pricing:** Approximately $0.15 per 1,000 tweets retrieved. Suitable for targeted ticker searches (expect 50 to 500 tweets per ticker, cost < $0.10 per company).

**Zero additional configuration required:** The key was provisioned and tested as part of the market-intel skill setup. This skill reuses it via read-only catalog; no key duplication, no additional `.env` files in this repo.

**Why not route ③ (user's own X account via twikit/playwright):**
Route ③ involves automated login to the user's personal X account. X's terms of service prohibit automated access. In practice, this approach results in account suspension within days to weeks of heavy use. It is permanently excluded from this skill.

**Fallback when twitterapi.io is unavailable or not configured:**
Use search engine indexing of X posts:
```
site:twitter.com OR site:x.com <ticker> OR "<company name>"
```
This captures top-linked posts but misses reply threads and low-follower accounts. Note the degradation in the report.

---

## EDGAR Rate Discipline, Enforcement Summary

This table summarizes the rate discipline from the "Primary Free Sources" section above for quick reference in code review:

| Rule | Value | Enforcement |
|---|---|---|
| Max requests/sec | 10 (total, all endpoints) | Per-tool `time.sleep` |
| Required header | `User-Agent: <name> <email>` | `_common.UA` dict in all http_get calls |
| Target inter-request delay | ~150ms | `time.sleep(0.15)` in each tool |
| Retry on 429/500 | Exponential backoff, start 1.5s, max 4 retries | `_common.http_get` |

Every `tools/*.py` script must route EDGAR `requests.get` calls through `_common.http_get`.
Direct `requests.get()` to EDGAR endpoints without the UA header and retry wrapper is
forbidden, it risks IP blocking.

---

## Cross-references

- `judgment-rubric.md`, P7 second-source sanity band: `cross_source_mismatch` is a DATA-INTEGRITY term of the `buy_eligible` composite (distinct from the firewalled diagnostic `signals` layer above, which never gates); full gate semantics and Hard-Rules row live there
- `discovery-engine.md`, FTS calls to `efts.sec.gov` are subject to the EDGAR rate discipline above; the two-stage precision gate design accounts for FTS over-recall
- `mechanical-checks.md`, the five Python guards govern how EDGAR data is parsed once retrieved; openinsider fragility is Guard 2's fallback case
- `judgment-rubric.md`, data-gap disclosures required when blind spots affect a scoring dimension
- `disclosure-discipline.md`, Discipline 8 (machine data may be stale) governs when WebSearch verification is mandatory; Discipline 9 covers honest data-gap acknowledgment
