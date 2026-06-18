# Data Sources — Invariant E

> This is the routing guide for the data layer. It covers what free sources can provide, what they cannot, and how to use them responsibly.
> It also covers the market-intel read-only catalog reuse pattern, the X sentiment route, and the anti-recursion rule.
>
> See `mechanical-checks.md` for the five Python guards that govern how these sources are used in `tools/*.py`.
> See `judgment-rubric.md` + `disclosure-discipline.md` for how the data retrieved here feeds judgment.

---

## Primary Free Sources

### EDGAR (SEC) — Authoritative, No Key Required

**What it provides:**
- Full-text of all SEC filings since 2001 (`efts.sec.gov` FTS endpoint)
- Structured XBRL financial data (`data.sec.gov/api/xbrl/companyfacts/` and `companyconcept/`)
- Form 4 insider transactions (full filing history)
- DEF 14A proxy statements (compensation, share ownership)
- 8-K material events (earnings, secondary offerings, going-concern disclosures)
- S-3 / 424B5 shelf and ATM offering documents
- SC 13D/13G significant ownership disclosures

**Rate limit discipline (mandatory):**
- Maximum 10 requests/second across all EDGAR endpoints from a single IP
- Every request must include `User-Agent: <name> <email>` header — omission causes 403 errors
- Target ~150ms between requests in normal operation
- On 429 response: exponential backoff starting at 2 seconds, maximum 4 retries
- Never parallelize more than 5 concurrent EDGAR requests from a single session

**Tools:** `edgartools` (MIT license) is the primary wrapper. It handles authentication, retry, and XBRL parsing. Do not build a direct `requests`-based EDGAR client without adding the rate discipline that `edgartools` already provides.

**Blind spots:**
- No real-time data; filings have typical 1–4 day lag after company submits
- XBRL data quality varies by company size — micro-caps often have incomplete or malformed concept tags
- Form 4 direction parsing in `edgartools` was found unreliable in production (DATA_ISSUES #3); use `openinsider` as the primary Form 4 source (see below)

### openinsider.com — Insider Trades, Public Tables

**What it provides:** Parsed Form 4 insider transactions with buy/sell direction (P/S code), transaction type, and price. The static HTML tables are scrape-able without authentication.

**How to use:** Fetch the company's insider transaction page by ticker or CIK. Parse the `P` (purchase) and `S` (sale) codes in the transaction table. Compute net buy/sell balance over the past 12 months.

**Fragility note:** `openinsider.com` is a third-party service scraping SEC data. Its availability is not guaranteed. Its terms of service are not explicitly open for automated access. In the public version of this skill, `edgartools Form 4` with custom direction parsing is the default; `openinsider` is an optional enhancement. Label it as such in reports: "(source: openinsider — public, fragility noted)".

**Fallback:** If `openinsider` is unavailable, fetch Form 4 filings directly from EDGAR for the target CIK and parse the transaction code from the XML. The direction parsing was previously unreliable (`edgartools` bug), but a custom parser for the `transactionCode` field (`P`=purchase, `S`=sale) in the Form 4 XML is straightforward and reliable.

### yfinance — Convenience Layer for Market Data

**What it provides:** Current price, market cap, EV, basic financial ratios, earnings calendar.

**Known limitations for micro-caps:**
- Many fields are missing or `NaN` for micro-caps (EV, float, revenue)
- Data freshness is not guaranteed; fields may lag by days
- Do not use as the primary source for any metric that can be computed from EDGAR; use yfinance only as a quick-check or when EDGAR computation would be disproportionately expensive

**When to use:** Initial market cap screening (cheap_pass.py uses it to confirm the company is still in the target market cap band). Current price for reverse-DCF calculation.

### Finnhub / FMP / Alpha Vantage — Optional Free APIs

**Availability:** These services require API keys with rate limits. They are listed here for completeness; `config.json` has slots for these keys. The skill runs without them — EDGAR + yfinance is the baseline.

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
| Smart money / 13F institutional flows | 13F filings are public but parsing 3-month lag; sector aggregation services are paid | Cannot get real-time institutional positioning |
| On-chain / crypto asset valuations | Not applicable to traditional small-caps; specialized chain data is paid | N/A for standard theme deepdives |
| Credit default swap / bond spreads | Paid data vendor | Cannot assess credit market signal for distressed names |
| Alternative data (card spend, web traffic, job postings) | Paid vendors (Bloomberg 2nd Party, Similarweb, LinkUp) | Cannot independently verify revenue trajectory between quarters |
| Glassdoor employee sentiment | Anti-scraping measures + litigation risk as of 2026 | Use insider trades + compensation instead |
| LinkedIn data | Anti-scraping enforcement | Use Form 4 + DEF 14A instead |

---

## market-intel Read-Only Catalog Reuse

This is the pattern for accessing qualitative research sources (X sentiment, Reddit, web scraping, finance news).

**Core design:** The skill does not call `market-intel` as a skill at runtime. Instead, it reads `market-intel`'s reference catalog to learn which MCP tools or search queries to use for a given information need — then directly calls those tools.

**What to read:**
- `the market-intel sources catalog` — master index of sources by category
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

**Why this is structurally not recursive:** The market-intel catalog provides routing knowledge (which tool to use for which query), not runtime execution. The tools themselves (MCP servers) are session-level and available directly. Reading a catalog file to decide which tool to call is equivalent to reading documentation — it does not create a runtime dependency.

**Graceful degradation (market-intel not installed):**
If `~/.claude/skills/market-intel/` does not exist:
- Use EDGAR as the primary source for all financial data (already covered above)
- Use WebSearch for X sentiment, news, and web presence (acceptable quality for most use cases)
- Use `openinsider` for insider trades (already covered above)
- Document in the report that market-intel catalog was not used and WebSearch was substituted

The skill is fully functional without market-intel. Market-intel is an enhancement that provides access to curated, higher-quality sources with better routing logic.

---

## X Sentiment Route — twitterapi.io Resale (Route ②)

When X/Twitter sentiment is needed for a ticker:

**Default route: twitterapi.io resale (②)**

This is a resale API that uses the provider's own account pool and proxy infrastructure. The user's personal X/Twitter account is never involved. This eliminates account suspension risk entirely.

**Availability:** The API key for `twitterapi.io` is stored in `market-intel`'s configuration (`the market-intel secrets env` — not in this repo). The hosted MCP for this key is registered in `~/.claude.json`. Access is via the market-intel catalog read pattern above.

**Pricing:** Approximately $0.15 per 1,000 tweets retrieved. Suitable for targeted ticker searches (expect 50–500 tweets per ticker, cost < $0.10 per company).

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

## EDGAR Rate Discipline — Enforcement Summary

This table summarizes the rate discipline from the "Primary Free Sources" section above for quick reference in code review:

| Rule | Value | Enforcement |
|---|---|---|
| Max requests/sec | 10 (total, all endpoints) | `_common.py` rate limiter |
| Required header | `User-Agent: <name> <email>` | `_common.py` default headers |
| Target inter-request delay | ~150ms | `_common.py` sleep between calls |
| Retry on 429 | Exponential backoff, start 2s, max 4 retries | `_common.py` retry wrapper |
| Max parallel requests | 5 concurrent | Semaphore in `_common.py` |

Every `tools/*.py` script must use `_common.py`'s EDGAR session object. Direct `requests.get()` to EDGAR endpoints without the rate discipline is forbidden — it risks IP blocking that would affect all concurrent tool invocations.

---

## Cross-references

- `discovery-engine.md` — FTS calls to `efts.sec.gov` are subject to the EDGAR rate discipline above; the two-stage precision gate design accounts for FTS over-recall
- `mechanical-checks.md` — the five Python guards govern how EDGAR data is parsed once retrieved; openinsider fragility is Guard 2's fallback case
- `judgment-rubric.md` — data-gap disclosures required when blind spots affect a scoring dimension
- `disclosure-discipline.md` — Discipline 8 (machine data may be stale) governs when WebSearch verification is mandatory; Discipline 9 covers honest data-gap acknowledgment
