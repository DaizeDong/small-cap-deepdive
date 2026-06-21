# B — Point-in-Time Backtest Harness (spec, 2026-06)

> Validate the rubric's predictive value with a **survivorship-safe, free** point-in-time (PIT)
> replay over a **2020–2024 panel**. Answers the campaign's deepest open question: *the skill is
> robust (0 false BUYs across 70+ themes), but does it actually avoid losers / would its rare BUYs
> have worked?* Free EDGAR-PIT + yfinance (user-approved). Build the machinery first, verify look-ahead
> correctness on one natural-experiment cell, then run the panel.

## Why free EDGAR makes this survivorship-safe
SEC EDGAR is point-in-time and immutable: a filing's `filing_date` and original `accession` never
change. So for any as-of date T we can (a) reconstruct fundamentals from only filings with
`filing_date ≤ T` (no look-ahead, no restatement contamination), and (b) reconstruct the **universe of
filers as-of T** — *including companies that later delisted* (their filings persist). yfinance cannot
do (b); EDGAR can. Delisted/blown-up names get a realized return ≈ −100% from their last/delisting
price — exactly the outcome a de-risk scanner must be graded on *avoiding*.

## Architecture (additive — the live default `latest-filing` path is untouched)
1. **As-of data layer** — `tools/_deepdive_concepts.py`: add `concept_series_asof(cik, concept, asof)`
   that returns the value series using only filings with `filing_date ≤ asof` (join companyconcept
   values to their accession's filing date via the submissions index; pick the latest ≤ T per period).
   `deepdive_data.pull(..., as_of=T)` threads it through. Default (as_of=None) = current behavior, byte-identical.
2. **PIT universe** — `tools/_pit_universe.py`: enumerate EDGAR filers in a theme's dedicated SIC
   (reuse `filter_by_sic` SIC floors) restricted to entities with a 10-K/10-Q `filing_date ≤ T`
   (survivorship-safe; includes later-delisted). Fall back to FTS-as-of where no SIC floor.
3. **Returns** — `tools/backtest_returns.py`: entry market cap from price as-of T; forward total
   return T→T+horizon (yfinance, dividend-adjusted); delisted → last available close / delisting
   price as the realized (near −100% for blowups). Benchmark IWM same window.
4. **Harness** — `tools/backtest.py`: for each (as_of, theme) cell → reconstruct PIT universe →
   cheap_pass + deepdive(as_of) + valuation + `buy_eligible` → bucket each name
   {BUY-eligible / WATCH / AVOID / abstain} → join forward returns → per-bucket stats. Writes a
   per-cell JSON + an aggregate.

## Metrics (the de-risk thesis, finally measured)
- Per bucket: mean/median forward return, **excess vs IWM**, win-rate.
- **Blowup-avoidance**: of names that suffered a >40% drawdown over the horizon, what fraction did the
  scanner put in AVOID/abstain (higher = the scanner earns its name).
- **Downside capture**: AVOID/abstain bucket return in down-markets.
- **Ordering**: did WATCH out-return AVOID? did BUY-eligible (rare) out-return the theme mean?
- All with a **look-ahead audit** line per cell (max filing_date used ≤ T; entry/benchmark dates).

## Panel (user: multi-date 2020–2024)
- **as-of dates** (12-month horizon, all matured before 2026-06): 2020-06-30, 2021-06-30,
  2022-06-30, 2023-06-30, 2024-06-30.
- **themes** (SIC-floored for a clean survivorship-safe universe; chosen for natural experiments):
  - `water-utilities` (4941) — defensive/dividend baseline
  - `deathcare` (7200) — defensive baseline
  - `regional-gaming` (7990/7011) — **2020 COVID crash** natural experiment
  - `oilsvc` (energy) — **2020 oil crash** natural experiment
  - `regbank` (60xx) — **2023 regional-bank crisis** natural experiment (financial-SIC routing → mostly abstain/nav; tests whether it dodged SVB-era blowups)
  - 5 as-of × 5 themes = **25 cells** (tunable). Full data per cell (no sampling); EDGAR-heavy.
- **Cost**: comparable to the coverage test, ~10–15M tokens / ~15–25h, background + resumable.

## Look-ahead controls (validity is the whole point)
- Only filings with `filing_date ≤ T`; original accession (no restated data).
- Market cap + entry price as-of T; forward return T→T+12mo; IWM same window.
- No current SIC / current data anywhere in a cell. Per-cell audit asserts `max(filing_date) ≤ T`.

## Honest limitations
yfinance delisted-price is approximate (gaps; some names un-fetchable → flagged, conservatively
treated as the worst observed); foreign/IFRS names stay un-valuable (carried abstain); BUY-eligible
bucket N is small (small-cap clean BUYs are rare) → the strong signal is on the **AVOID/abstain +
blowup-avoidance** axis, which is the de-risk thesis anyway; companyconcept→filing-date mapping drops
concepts it can't cleanly date (conservative).

## Execution plan
1. **Build** the 4 machinery pieces (as-of data, PIT universe, returns, harness) — additive; verify
   the live default path stays byte-identical (all selftests) + a one-cell smoke (regional-gaming
   as-of 2020-06-30) proving the look-ahead audit holds. [controller verifies + commits]
2. **Run** the 25-cell panel (throttled waves, like the coverage test). Background + resumable.
3. **Aggregate** — per-bucket excess-return + blowup-avoidance across the panel → `_aggregate.md`;
   the first real evidence on whether the rubric has edge (or honestly, where it doesn't).

## Acceptance
Reproducible per-bucket forward-return + blowup-avoidance stats with a passing look-ahead audit on
every cell; a clear verdict on (a) does AVOID/abstain avoid blowups, (b) does WATCH>AVOID, (c) the
(few) BUY-eligible outcomes — stated honestly even if the answer is "no measurable edge."
