# Track-Forward Calibration, Phase 6

> The epistemic spine of the skill's feedback loop.
> Without this, the rubric is "confident garbage" risk: outputs are internally consistent but
> never checked against realized outcomes.

---

## Why This Exists

A verdict stream with few BUY decisions can reflect either sound selectivity or a
miscalibrated rubric. Forward outcome tracking is needed to distinguish them:

**(A) Correct**, the market is efficient for small-caps; real mis-pricings are genuinely rare
and the rubric correctly identifies them; or

**(B) Miscalibrated**, the rubric is too strict (or too loose in the AVOID direction), producing
systematically biased verdicts that do not reflect actual return distributions.

This ambiguity cannot be resolved by narrative argument, by examining the rubric for internal
consistency, or by debating the efficient market hypothesis. **It can only be resolved by tracking
verdicts forward against realized returns and computing a calibration measure.**

The Brier score + calibration table is the instrument. Without a populated verdict log the skill is
running blind on its own judgment quality.

**Where the verdict log lives.** It is real-run output, so it is written **outside this repo**, never
into it. `guards/tools/datadir.py:resolve_data_dir("small-cap-deepdive")` resolves the private store in
order: `$SMALL_CAP_DEEPDIVE_DATA_DIR` → `~/.small-cap-deepdive-config/data/` →
`~/.small-cap-deepdive-data/` → nothing, which raises `DataDirNotInitialized` with setup
instructions. The two files are `<private data dir>/metrics/verdicts.jsonl` and
`<private data dir>/metrics/scorecard.md`. There is deliberately **no in-repo fallback**.
Real observations belong in the versioned PRIVATE companion. The repo's own metrics directory
holds only the generated synthetic examples `verdicts.jsonl.example` and
`scorecard.md.example`, which are the shape you are expected to produce. Every bare `metrics/...`
path below is shorthand for the private path above.

---

## `verdicts.jsonl` Schema

Append-only. One JSON object per line. Fields:

| Field | Type | Description |
|---|---|---|
| `verdict_date` | `string` (YYYY-MM-DD) | Date the deep-dive verdict was produced |
| `ticker` | `string` | Exchange ticker |
| `cik` | `string\|null` | SEC CIK |
| `theme` | `string\|null` | Theme slug (e.g., `aeromro`, `agequip`) or `null` for single-ticker DDs |
| `rating` | `string` | `买入` / `观察` / `避开`, must match rubric enumeration |
| `mos_pct` | `number\|null` | Margin of safety pct from valuation.py; null if `mos_basis=nav` or `abstain` |
| `mos_basis` | `string` | `fcf_cap` / `nav` / `abstain` |
| `kill_flags` | `array[string]` | Active kill flags at verdict time (empty list = none) |
| `catalyst` | `string\|null` | T1-evidenced catalyst string or null |
| `confidence` | finite `number\|null` (0 to 100) | Model confidence at verdict time. Untagged input preserves the supplied units: [0, 1] is a fraction and (1, 100] is a percentage; 1 means 100%. JSON input tagged `confidence_unit: percent` is normalized to a fraction before recording. Finalizer output always carries that tag because report confidence is an integer percentage. `null` uses the fixed `RATING_PROB` convention. |
| `implied_prob` | `number` (0 to 1) | Model probability the thesis resolves favorably (stock beats benchmark over horizon). Derived from `confidence` mapped by rating direction; falls back to `RATING_PROB` when `confidence` is null. |
| `horizon_months` | `integer` | Default 12. Forward tracking period in months. |
| `entry_price` | `number\|null` | Stock **dividend-adjusted** closing price on/near verdict_date (yfinance `auto_adjust=True`). Total-return basis, dividends + splits back-adjusted. |
| `entry_date` | `string` (YYYY-MM-DD) | Date entry_price was fetched |
| `benchmark` | `string` | Default `IWM` (Russell 2000). The correct small-cap universe benchmark. |
| `benchmark_entry_price` | `number\|null` | Benchmark dividend-adjusted closing price on/near verdict_date |
| `scored` | `boolean` | False until horizon has elapsed and prices are fetched. Always False for `data_false_positive` rows (never price-scored). |
| `stock_return_pct` | `number\|null` | Stock dividend-adjusted total return over horizon (absolute, %), rounded to two decimals for display. Null until scored. |
| `realized_excess_pct` | `number\|null` | Stock total return minus benchmark total return over horizon; null until scored. **Dividend-adjusted total return on both legs.** |
| `stock_return_pct_unrounded` | `number` | Newly scored stock return before display rounding; used for drawdown thresholds. |
| `realized_excess_pct_unrounded` | `number` | Newly scored excess return before display rounding; used for sign comparisons. |
| `favorable` | `boolean` | Newly scored strict excess > 0 outcome, retained alongside precise return evidence. Exact zero is unfavorable. |
| `brier` | `number\|null` | `(implied_prob - favorable)^2`; null until scored |
| `adjudication` | `string\|null` | Claimed review disposition. Only `data_verified_clean` or `data_false_positive` with a valid verdict-bound receipt counts as reviewed. Legacy labels alone remain pending. Every FP label stays outside price scoring. |
| `adjudication_evidence` | `object\|null` | Versioned review receipt described below; absent for unreviewed records. |
| `fp_cause` | `string\|null` | Reviewer annotation of a claimed data defect; text alone does not establish completed review. |
| `notes` | `string\|null` | Free-text annotation |

**Append-only discipline:** lines are never deleted. Scores are rewritten in place when
`python tools/track_forward.py --score` runs. The file is the source of truth; do not edit manually.

---


### Review receipt protocol

A completed review uses `schema_version: 1` and `protocol: smallcap-data-review-v1`.
Its `disposition` must match the row's completed label. The `verdict` object repeats exactly
the original `ticker`, `cik`, `verdict_date`, `rating` and `report_sha256`. A missing original
report hash leaves the review pending; do not invent a hash while migrating historical rows.

The receipt also requires a `review_date` no earlier than the verdict date, a nonempty
`sources` list of `reference` and SHA-256 pairs, and a nonempty `checks` list. Each check
names a `field`, a declared `source_sha256`, and a `result` of `matches` or `mismatch`.
A clean disposition requires all checks to match and must cover `issuer_identity`,
`total_debt`, `operating_cash_flow`, `capital_expenditures` and `verdict_inputs` (the remaining
material inputs to the original verdict). An FP disposition requires a mismatch.
The report itself cannot serve as its own independent source. Validation establishes
structure and verdict identity. It does not authenticate source bytes or a reviewer's claims.

Keep evidence and the receipt in the initialized private companion. After completing the
review, attach its receipt to one existing verdict with
`python tools/track_forward.py --adjudicate "${METRICS_ROOT}/review-receipt.json"`.
This command preserves existing labels, refuses conflicting replacements, and uses the
ledger's lock and snapshot checks. A new JSON record may carry the same
`adjudication` / `adjudication_evidence` pair. New completed claims without valid receipts
are rejected. Unrecognized workflow labels remain unfinished reviews.

Historical labels are preserved as recorded claims. They are not automatically promoted,
removed, or supplied with synthetic evidence. Synthetic examples and regression inputs are
generated by `tools/make_fixtures.py`; they say nothing about historical review coverage.

## Diagnostic signal snapshot

Finalization captures the selected deepdive JSON bytes once and retains its descriptor with
the diagnostic signals. Recording accepts this snapshot as a standalone record: it checks
the claimed ticker, CIK and verdict date against the verdict, checks the signal payload
digest, and preserves the diagnostic firewall. It does not reopen the referenced artifact
or independently prove that the source descriptor or provider claim is authentic.

Every normalized version-1 snapshot carries `source_verification: retained_unverified`.
Legacy snapshots without that field receive the same label. A claim of verified source
bytes is rejected; syntactically valid edits to the source filename, byte count or SHA256
remain unverified metadata. Signals never change the rating, implied probability or score.
This label does not certify the truth of the signal payload; its digest detects changes
relative to the included digest only.

The finalizer's `report_sha256` is calculated from the same raw report bytes used to parse
the analyst decision. It identifies that captured snapshot; it does not claim the file
stayed unchanged after capture.

## Rating → Implied Probability Convention

**Primary (P12a): confidence-as-probability mapped by rating DIRECTION.** When a verdict carries
a valid model `confidence`, `implied_prob` is derived from its normalized fraction by the rating's directional sign
(`tools/track_forward.py::_implied_prob_from_confidence`):

```
d = +1 (买入) | 0 (观察) | -1 (避开)
fraction = confidence / 100 if confidence > 1 else confidence
implied_prob = 0.5 + d * (fraction - 0.5)       # clamped to [0.001, 0.999]
```

| Rating | direction `d` | example confidence | `implied_prob` |
|---|---|---|---|
| `买入` | +1 | 0.70 | **0.70** |
| `买入` | +1 | 0.90 | **0.90** |
| `观察` |  0 | any valid confidence | **0.50** (neutral by construction) |
| `避开` | -1 | 0.70 | **0.30** |
| `避开` | -1 | 0.90 | **0.10** |

This replaces the old fixed three-point map as the live path: a high-conviction BUY and a
low-conviction BUY no longer share one probability, so the calibration table can finally
distinguish them. Inputs must be finite numbers from 0 to 100: values in [0, 1] are fractions,
and values in (1, 100] are percentages (e.g. `70` maps to `0.70`). A value of `1` means 100%
confidence. Booleans, nonfinite values, invalid text and out-of-range numbers are rejected before
quote retrieval or ledger writes, including when an invalid row appears later in a JSON batch.
Omitted values, JSON null, and the CLI omission strings `null`, `none` or an empty string use
the fallback. The stored confidence retains its supplied units.

**Fallback (no confidence): fixed `RATING_PROB` convention** (`tools/track_forward.py::RATING_PROB`):

| Rating | `implied_prob` | Interpretation |
|---|---|---|
| `买入` | **0.65** | Model predicts 65% probability stock outperforms benchmark over horizon |
| `观察` | **0.50** | Model is neutral, no directional edge predicted |
| `避开` | **0.35** | Model predicts 35% probability of outperformance (i.e., 65% UNDERperformance) |

**Why these fallback numbers:**
- 0.65 / 0.35 are modest, non-overconfident departures from 0.5. A well-calibrated analyst
  should rarely exceed ±20pp of base rate.
- `避开` at 0.35 means AVOID actively predicts underperformance, not just neutrality. This is
  the correct interpretation: if AVOID is uninformative it should converge to 0.50 over time;
  if calibrated it should show realized favorable freq < 0.35.

**Overriding:** pass `--confidence` to `--record` (or a `confidence` field in JSON ingestion) to
drive the directional mapping. With no confidence, the fixed `RATING_PROB` defaults apply.

At scoring time, a stored `implied_prob` must be a finite numeric value in [0, 1]. Missing/null
probabilities remain unscored with `score_unavailable_reason="missing_implied_prob"`; other
invalid probabilities use `invalid_implied_prob`. Neither case fetches return snapshots or
substitutes a probability. This validation does not rescore or migrate already-scored history.

---

## Seeded Verdicts Backfill

When verdicts are seeded in bulk (e.g., from a prior run without live yfinance calls), they may
have `entry_price: null` and `benchmark_entry_price: null`. These rows cannot be scored until
prices are filled in.

**The correct fix is `--backfill`, not `--record`:**

```bash
python tools/track_forward.py --backfill
```

This fetches historical closes at each verdict's `verdict_date` for both the stock and IWM,
fills null prices in-place, and saves atomically. It is **idempotent**, rows already filled
are skipped. Re-running `--backfill` is always safe.

**Why not `--record`?** The `--record` command checks for duplicate `(ticker, verdict_date)` pairs
and skips them with a warning. Using `--record` for tickers already in `verdicts.jsonl` would
not update the existing row, it would just warn and skip. `--backfill` correctly fills the
existing row without creating a duplicate.

A backfill can resolve an entry quote only when the provider supplies matching dated evidence.
Thinly traded, delisted, malformed or unavailable records may remain unresolved. Report which
rows were filled and which failed, including reasons. A partial backfill does not establish
complete quote coverage or make an unresolved row eligible for scoring.

---

## Historical Adjudication Is Not a Backfill Input

The former `--backfill-validation-fp` route is retired and rejects before any ledger write.
The public tool no longer contains historical verdict tuples. Historical reports remain
unvalidated audit material; their labels cannot automatically become reviewed calibration
observations or establish an integrity rate.

Preserve original observations, analyst interventions and their provenance in the versioned
private companion. Any future adjudication must have a separate, documented review protocol
and traceable evidence. The explicit receipt command above transports a completed review;
it neither imports history automatically nor independently approves a review. A repair,
fixture or preserved report is not a substitute for that review.


## Brier Score Methodology

**Favorable outcome definition:** stock total return **> benchmark total return** over the horizon.

Scoring keeps unrounded return percentages and the favorable outcome. Display rounding never
changes the outcome used by Brier, individual rows, hit rates, or calibration frequencies. Risk
metrics use the same precise return comparisons for sign and drawdown thresholds.

Legacy rows remain untouched. A two-decimal legacy return represents a rounding interval; if
that interval contains the decision threshold, the outcome is unknown. In particular, rounded
zero does not establish either a loss or an exact tie. Scorecards show outcome coverage and
exclude unknown results from outcome rates. Calibration means use that same observed subset.
Stored Brier averages retain all eligible stored scores and state that separate population.
Risk metrics likewise report observed and missing comparisons. No private ledger migration or
outcome reconstruction from a historical Brier score is performed.

**Total-return basis (P12b):** Both legs use yfinance `auto_adjust=True` closes, which adjust for splits and cash dividends. Compute the return from the adjusted horizon and entry closes on the same basis. This avoids comparing a price-only stock return with a dividend-adjusted benchmark; missing quote evidence remains unavailable.

**Per-verdict Brier score:**

```
o = 1 if (stock_total_return > benchmark_total_return) else 0
brier = (implied_prob - o)^2
```

Properties:
- Brier = 0: perfect prediction
- Brier = 0.25: uninformative (equivalent to always predicting p = 0.5)
- Brier = 1.0: perfectly wrong predictions

**Average Brier** across N verdicts: simple arithmetic mean over the **price-scorable** population
only. A verdict must be scored and have neither an FP label nor an unsupported adjudication
claim. Requiring evidence for review metrics never admits legacy FP labels to price scoring.
Unlabeled forward records remain eligible for price scoring once their price evidence matures.

**Skill score** (optional future extension): `1 - (Brier / 0.25)`, positive = better than
uninformative, negative = worse than uninformative.

---

## De-Risk-Native Metrics (P12c)

Brier-vs-IWM measures relative price outcomes. The scorecard also reports review coverage
and outcomes among WATCH/AVOID names. These describe different populations and should
not all be interpreted as evidence that losses were avoided:

| Metric | Definition | Why |
|---|---|---|
| **BUY data-integrity** | `receipt_backed_clean_BUYs / receipt_backed_reviewed_BUYs` | Report review coverage and pending BUYs separately. With no valid review receipts the rate is N/A, even if legacy rows carry clean or FP labels. |
| **Above-threshold outcome rate** | fraction of scored `观察`/`避开` names whose horizon total return stayed **above −40%** | Describes returns in the flagged cohort. A high value means fewer flagged names crossed the loss threshold; it does not prove the scanner correctly avoided craters. |
| **Downside-capture** | fraction of scored `避开` names that **underperformed the benchmark AND** drew down past −40% | Tests whether AVOID genuinely flags losers (vs. crying wolf). |

The blowup threshold (`BLOWUP_DRAWDOWN_THRESHOLD = -0.40`) is encoded in `track_forward.py`. All
three return `None` until their underlying population exists; the scorecard prints `—` for those.

---

## Calibration Table

Groups verdicts by `implied_prob` bucket and compares predicted probability to realized favorable
frequency. A well-calibrated model has `realized_freq ≈ mean implied_prob of bucket members`.

**Calibration error definition:** `realized_freq − mean(implied_prob of verdicts in that bucket)`.
This uses the actual mean implied_prob of members, NOT the bucket geometric midpoint. For the
`观察` bucket where all verdicts sit at exactly p=0.50, the error is `realized_freq − 0.50`.
Using the bucket midpoint (0.475) would be incorrect and would introduce a spurious 2.5pp bias.
The implementation in `cmd_scorecard` and the selftest both verify this behavior.

Buckets used (encoded in `CALIB_BUCKETS`):

| p bucket | Expected rating |
|---|---|
| 0.00 to 0.40 | Primarily 避开 |
| 0.40 to 0.55 | Primarily 观察 |
| 0.55 to 0.70 | Primarily 买入 |
| 0.70 to 1.01 | High-conviction 买入 (rare) |

**Interpretation:** If the 避开 bucket shows realized favorable freq = 0.60, the model's AVOID
verdicts are not actually predicting underperformance, the AVOID threshold is too aggressive.
If 买入 shows realized freq = 0.40, the BUY trigger (MoS ≥ 30%) is overconfident.

---

## Horizon Convention

**Default horizon: 12 months.**

Rationale:
- Short enough to accumulate data within a reasonable operational timeframe.
- Long enough for the thesis to begin resolving (not just momentum effects).
- Consistent with typical small-cap research hold horizon.

Override per-record via `horizon_months` field. The `--score` command uses the per-record value.

---

## Benchmark Choice: IWM (Russell 2000), Not SPY

The correct benchmark for small-cap research is **IWM (iShares Russell 2000 ETF)**, not SPY.

**Why not SPY:**
- SPY tracks the S&P 500 (large-cap). Small-caps have different factor exposures (size premium,
  liquidity discount, higher beta in downturns).
- Comparing a micro-cap to SPY confounds the research outcome with the large-cap/small-cap
  performance differential (which can be 5 to 15% annually in either direction).
- The question being answered is: "does this specific small-cap outperform the small-cap
  universe?", not "does it outperform the market?"

**Consistent comparison:** both entry_price and benchmark_entry_price are fetched on the same
date; both horizon prices are fetched at the same horizon end date. The excess is:

```
realized_excess_pct = stock_total_return - IWM_total_return
```

---

## Scorecard Cadence

1. **After each deep-dive run:** run `python tools/track_forward.py --record <verdicts_json>` to
   log all verdicts (pass `--confidence` for the directional probability mapping). ~1 minute.

2. **Review coverage:** keep unreviewed verdicts pending. Do not seed the BUY arm with
   historical labels; the retired backfill command cannot establish a reviewed observation.

3. **Monthly:** run `python tools/track_forward.py --score` to price-score eligible verdicts
   whose individual horizons have elapsed. Report observed, pending and unavailable outcomes.
   Review coverage remains a separate measure.

4. **When outcomes are available:** run `--scorecard` and examine sample composition,
   uncertainty, missing coverage and de-risk metrics. A fixed number of matured verdicts
   alone does not justify rubric tuning or establish predictive performance.

---

## Honest Note: Until Verdicts Mature, Calibration is Unknown

Each verdict matures according to its recorded date and horizon. A fresh ledger has no
realized calibration. An unscored cohort must report calibration as unknown; a partially
scored cohort must disclose both the observed subset and the missing coverage. Do not assign
a maturity date, price-Brier score or tuning justification from a historical run narrative.

BUY integrity and review coverage are separate quantities. If no verdict has a supported
adjudication, the integrity rate is unavailable. Historical seeded labels do not prove a
current rate or live performance; retain their provenance for private review.


---

## Cross-References

- **`tools/track_forward.py`**, implementation (record, score, scorecard, status, selftest)
- **`<private data dir>/metrics/verdicts.jsonl`**, the append-only verdict log (out-of-repo; schema
  in the repo at `metrics/verdicts.jsonl.example`)
- **`<private data dir>/metrics/scorecard.md`**, generated calibration report (out-of-repo; schema
  in the repo at `metrics/scorecard.md.example`)
- **`reference/cognitive-priors.md`**, epistemic priors that this calibration loop is designed to test
- **`reference/judgment-rubric.md`**, the rubric whose outputs populate verdicts.jsonl
- **`SKILL.md §Track-forward`**, operational instructions for running the loop
