# Track-Forward Calibration, Phase 6

> The epistemic spine of the skill's feedback loop.
> Without this, the rubric is "confident garbage" risk: outputs are internally consistent but
> never checked against realized outcomes.

---

## Why This Exists

Three real runs of this skill produced 40 deep-dives and **0 BUY verdicts**. We cannot know
whether that conservatism is:

**(A) Correct**, the market is efficient for small-caps; real mis-pricings are genuinely rare
and the rubric correctly identifies them; or

**(B) Miscalibrated**, the rubric is too strict (or too loose in the AVOID direction), producing
systematically biased verdicts that do not reflect actual return distributions.

This ambiguity cannot be resolved by narrative argument, by examining the rubric for internal
consistency, or by debating the efficient market hypothesis. **It can only be resolved by tracking
verdicts forward against realized returns and computing a calibration measure.**

The Brier score + calibration table is the instrument. Without a populated `metrics/verdicts.jsonl`,
the skill is running blind on its own judgment quality.

---

## `metrics/verdicts.jsonl` Schema

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
| `confidence` | `number\|null` (0 to 1) | Model confidence at verdict time. Mapped to `implied_prob` by rating direction (see Rating → Implied Probability). `null` → fixed `RATING_PROB` convention is used. |
| `implied_prob` | `number` (0 to 1) | Model probability the thesis resolves favorably (stock beats benchmark over horizon). Derived from `confidence` mapped by rating direction; falls back to `RATING_PROB` when `confidence` is null. |
| `horizon_months` | `integer` | Default 12. Forward tracking period in months. |
| `entry_price` | `number\|null` | Stock **dividend-adjusted** closing price on/near verdict_date (yfinance `auto_adjust=True`). Total-return basis, dividends + splits back-adjusted. |
| `entry_date` | `string` (YYYY-MM-DD) | Date entry_price was fetched |
| `benchmark` | `string` | Default `IWM` (Russell 2000). The correct small-cap universe benchmark. |
| `benchmark_entry_price` | `number\|null` | Benchmark dividend-adjusted closing price on/near verdict_date |
| `scored` | `boolean` | False until horizon has elapsed and prices are fetched. Always False for `data_false_positive` rows (never price-scored). |
| `stock_return_pct` | `number\|null` | Stock dividend-adjusted total return over horizon (absolute, %). Feeds the de-risk-native metrics. Null until scored. |
| `realized_excess_pct` | `number\|null` | Stock total return minus benchmark total return over horizon; null until scored. **Dividend-adjusted total return on both legs.** |
| `brier` | `number\|null` | `(implied_prob - favorable)^2`; null until scored |
| `adjudication` | `string\|null` | `data_false_positive` for the backfilled validation BUY cohort (kept OUT of the price-Brier; adjudicated by balance-sheet cross-check). `null` for ordinary forward-tracked verdicts. |
| `fp_cause` | `string\|null` | For `data_false_positive` rows: the validated structural pathology (debt truncation, wrong-entity, OCF-proxy, concentration, etc.). `null` otherwise. |
| `notes` | `string\|null` | Free-text annotation |

**Append-only discipline:** lines are never deleted. Scores are rewritten in place when
`python tools/track_forward.py --score` runs. The file is the source of truth; do not edit manually.

---

## Rating → Implied Probability Convention

**Primary (P12a): confidence-as-probability mapped by rating DIRECTION.** When a verdict carries
a model `confidence` (0..1), `implied_prob` is derived from it by the rating's directional sign
(`tools/track_forward.py::_implied_prob_from_confidence`):

```
d = +1 (买入) | 0 (观察) | -1 (避开)
implied_prob = 0.5 + d * (confidence - 0.5)     # clamped to (0.001, 0.999)
```

| Rating | direction `d` | example confidence | `implied_prob` |
|---|---|---|---|
| `买入` | +1 | 0.70 | **0.70** |
| `买入` | +1 | 0.90 | **0.90** |
| `观察` |  0 | any  | **0.50** (neutral by construction) |
| `避开` | -1 | 0.70 | **0.30** |
| `避开` | -1 | 0.90 | **0.10** |

This replaces the old fixed three-point map as the live path: a high-conviction BUY and a
low-conviction BUY no longer share one probability, so the calibration table can finally
distinguish them. Confidence given as a percentage (e.g. `70`) is normalized to `0.70`.

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

**Expected outcome after backfill:** verdict_date=2026-06-18 is historical data, yfinance can
fetch these closes. Some thin/delisted tickers may legitimately fail; `--backfill` logs which
ones failed and why. A partial backfill is still useful, even if 2 of 40 tickers fail, the
other 38 can be scored when their horizons mature.

---

## Validation BUY False-Positive Backfill (P12d)

**The problem:** the live ledger held 40 `观察`/`避开` verdicts and **zero BUY**, so the BUY arm
of calibration was permanently unobservable. Yet the 2026-06-19 validation campaign produced
**19 BUY-eligible (MoS ≥ 30%) names, every one a false positive with an identified XBRL/model
cause** (see `docs/2026-06-19-validation-report.md` and
`reports/smallcap/2026-06-19_validation-v0.2.0/`). None were in the ledger. The calibration
instrument was blind to the exact failure it was built to detect.

**The fix:** backfill those 19 as a distinct adjudication class:

```bash
python tools/track_forward.py --backfill-validation-fp
```

Each row is logged with `rating=买入`, `adjudication="data_false_positive"`, and an `fp_cause`
string. The cohort (ticker, MoS%, cause) is encoded deterministically in
`tools/track_forward.py::VALIDATION_FP`. The command is **idempotent**, re-running skips rows
already present.

**Why a separate class, and why OUT of the price-Brier:** these were adjudicated **today** by a
balance-sheet cross-check, not by a 12-month forward price. They have null entry prices and are
never `--score`d. Counting them in the price-Brier would conflate a data-integrity failure with a
return-prediction error. Instead they feed exactly one metric, **BUY data-integrity**, which is
`clean_BUYs / all_BUYs = 0 / 19 = 0.0%`. That single number is the most decision-relevant output
the loop can produce right now: *every BUY this engine has ever fired was a data artifact.*

This converts the validation campaign from a one-off doc into a permanent calibration asset and
gives the BUY arm 19 observations instead of zero.

---

## Brier Score Methodology

**Favorable outcome definition:** stock total return **> benchmark total return** over the horizon.

**Total-return basis (P12b):** both legs use yfinance `auto_adjust=True` closes, which back-adjust
for **both splits AND cash dividends**. `(horizon_close - entry_close) / entry_close` is therefore
the dividend-adjusted total return, not price-only. This removes the prior systematic bias that
mislabeled every high-dividend WATCH name (MLPs/utilities, UAN, ARTNA, MSEX, YORW) as an
underperformer. No per-verdict dividend annotation is required anymore.

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
only, `scored == True AND adjudication != "data_false_positive"`. The backfilled validation BUY
false-positives (next section) are deliberately excluded; they have no forward price horizon.

**Skill score** (optional future extension): `1 - (Brier / 0.25)`, positive = better than
uninformative, negative = worse than uninformative.

---

## De-Risk-Native Metrics (P12c)

Brier-vs-IWM measures stock-picking. This skill is a **de-risk scanner**: its job is blowup
AVOIDANCE, not beating IWM by a hair. Three metrics measure that directly, reported in the
scorecard alongside (and ahead of) the price-Brier:

| Metric | Definition | Why |
|---|---|---|
| **BUY data-integrity** | `clean_BUYs / all_BUYs` = fraction of BUY verdicts NOT adjudicated `data_false_positive` | The only one **measurable today**. With the 19 validation FPs and zero clean BUYs, it is 0.0%, the honest, decision-relevant headline. |
| **Blowup-avoidance** | fraction of scored `观察`/`避开` names whose horizon total return stayed **above −40%** | A scanner that keeps you out of −40% craters is doing its job even if it never beats IWM. |
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

2. **Once, to seed the BUY arm:** run `python tools/track_forward.py --backfill-validation-fp`
   to inject the 19 validation BUY false-positives (P12d). Idempotent.

3. **Monthly:** run `python tools/track_forward.py --score` to price-score any verdicts whose
   horizon has elapsed. In the first year this produces 0 price-scored verdicts (all recent) ,
   but the BUY-data-integrity metric is already meaningful from the backfilled cohort.

4. **After ~20 verdicts mature:** run `--scorecard` and examine the calibration table + de-risk
   metrics. Only then is price-Brier-based rubric tuning justified.

---

## Honest Note: Until Verdicts Mature, Calibration is Unknown

The first forward-tracked verdicts from runs in 2026-06 will mature in 2027-06. Until then, for the
**price-Brier** axis:

- The scorecard will show "0 price-scored, N pending"
- **No price-calibration-based rubric tuning is justified**
- The correct response to "why do we always get WATCH?" is "we don't know yet, check back in 12 months"

**But the BUY arm is no longer blind.** The de-risk-native **BUY data-integrity** metric (P12c/P12d)
is meaningful **today**: the 19 backfilled validation BUYs give a hard, present-tense answer ,
0.0% of BUY verdicts survive a balance-sheet cross-check. That is actionable now, without waiting
for price. It is the part of the loop most worth heeding before any clean BUY ever fires.

This is not a failure of the system. It is the correct epistemically honest state. The value of
Phase 6 is that it converts uncertainty from "permanent / unresolvable" to
"time-bounded / resolvable by evidence", and, for data-integrity, "resolvable now."

---

## Cross-References

- **`tools/track_forward.py`**, implementation (record, score, scorecard, status, selftest)
- **`metrics/verdicts.jsonl`**, the append-only verdict log
- **`metrics/scorecard.md`**, generated calibration report
- **`reference/cognitive-priors.md`**, epistemic priors that this calibration loop is designed to test
- **`reference/judgment-rubric.md`**, the rubric whose outputs populate verdicts.jsonl
- **`SKILL.md §Track-forward`**, operational instructions for running the loop
