# Track-Forward Calibration — Phase 6

> The epistemic spine of the skill's feedback loop.
> Without this, the rubric is "confident garbage" risk: outputs are internally consistent but
> never checked against realized outcomes.

---

## Why This Exists

Three real runs of this skill produced 40 deep-dives and **0 BUY verdicts**. We cannot know
whether that conservatism is:

**(A) Correct** — the market is efficient for small-caps; real mis-pricings are genuinely rare
and the rubric correctly identifies them; or

**(B) Miscalibrated** — the rubric is too strict (or too loose in the AVOID direction), producing
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
| `rating` | `string` | `买入` / `观察` / `避开` — must match rubric enumeration |
| `mos_pct` | `number\|null` | Margin of safety pct from valuation.py; null if `mos_basis=nav` or `abstain` |
| `mos_basis` | `string` | `fcf_cap` / `nav` / `abstain` |
| `kill_flags` | `array[string]` | Active kill flags at verdict time (empty list = none) |
| `catalyst` | `string\|null` | T1-evidenced catalyst string or null |
| `implied_prob` | `number` (0–1) | Model probability the thesis resolves favorably (stock beats benchmark over horizon) |
| `horizon_months` | `integer` | Default 12. Forward tracking period in months. |
| `entry_price` | `number\|null` | Stock closing price on/near verdict_date (yfinance) |
| `entry_date` | `string` (YYYY-MM-DD) | Date entry_price was fetched |
| `benchmark` | `string` | Default `IWM` (Russell 2000). The correct small-cap universe benchmark. |
| `benchmark_entry_price` | `number\|null` | Benchmark closing price on/near verdict_date |
| `scored` | `boolean` | False until horizon has elapsed and prices are fetched |
| `realized_excess_pct` | `number\|null` | Stock total return minus benchmark total return over horizon; null until scored |
| `brier` | `number\|null` | `(implied_prob - favorable)^2`; null until scored |
| `notes` | `string\|null` | Free-text annotation |

**Append-only discipline:** lines are never deleted. Scores are rewritten in place when
`python tools/track_forward.py --score` runs. The file is the source of truth; do not edit manually.

---

## Rating → Implied Probability Convention

Default mapping (encoded in `tools/track_forward.py::RATING_PROB`):

| Rating | `implied_prob` | Interpretation |
|---|---|---|
| `买入` | **0.65** | Model predicts 65% probability stock outperforms benchmark over horizon |
| `观察` | **0.50** | Model is neutral — no directional edge predicted |
| `避开` | **0.35** | Model predicts 35% probability of outperformance (i.e., 65% UNDERperformance) |

**Why these numbers:**
- 0.65 / 0.35 are modest, non-overconfident departures from 0.5. A well-calibrated analyst
  should rarely exceed ±20pp of base rate.
- `避开` at 0.35 means AVOID actively predicts underperformance, not just neutrality. This is
  the correct interpretation: if AVOID is uninformative it should converge to 0.50 over time;
  if calibrated it should show realized favorable freq < 0.35.

**Overriding:** Per-record `implied_prob` can be set explicitly in CLI flags or JSON ingestion.
The defaults are a convention, not a constraint.

---

## Brier Score Methodology

**Favorable outcome definition:** stock total return **> benchmark total return** over the horizon.
(Total return = price appreciation only in this implementation — dividends excluded for simplicity.
Document this limitation in notes if material for high-dividend stocks.)

**Per-verdict Brier score:**

```
o = 1 if (stock_return > benchmark_return) else 0
brier = (implied_prob - o)^2
```

Properties:
- Brier = 0: perfect prediction
- Brier = 0.25: uninformative (equivalent to always predicting p = 0.5)
- Brier = 1.0: perfectly wrong predictions

**Average Brier** across N verdicts: simple arithmetic mean.

**Skill score** (optional future extension): `1 - (Brier / 0.25)` — positive = better than
uninformative, negative = worse than uninformative.

---

## Calibration Table

Groups verdicts by `implied_prob` bucket and compares predicted probability to realized favorable
frequency. A well-calibrated model has `realized_freq ≈ predicted_p_midpoint` in each bucket.

Buckets used (encoded in `CALIB_BUCKETS`):

| p bucket | Expected rating |
|---|---|
| 0.00–0.40 | Primarily 避开 |
| 0.40–0.55 | Primarily 观察 |
| 0.55–0.70 | Primarily 买入 |
| 0.70–1.01 | High-conviction 买入 (rare) |

**Interpretation:** If the 避开 bucket shows realized favorable freq = 0.60, the model's AVOID
verdicts are not actually predicting underperformance — the AVOID threshold is too aggressive.
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
  performance differential (which can be 5–15% annually in either direction).
- The question being answered is: "does this specific small-cap outperform the small-cap
  universe?" — not "does it outperform the market?"

**Consistent comparison:** both entry_price and benchmark_entry_price are fetched on the same
date; both horizon prices are fetched at the same horizon end date. The excess is:

```
realized_excess_pct = stock_total_return - IWM_total_return
```

---

## Scorecard Cadence

1. **After each deep-dive run:** run `python tools/track_forward.py --record <verdicts_json>` to
   log all verdicts. This takes ~1 minute.

2. **Monthly:** run `python tools/track_forward.py --score` to score any verdicts whose horizon
   has elapsed. In the first year, this will produce 0 scored verdicts (all verdicts are recent).

3. **After ~20 verdicts mature:** run `--scorecard` and examine the calibration table. Only then
   is rubric tuning justified.

---

## Honest Note: Until Verdicts Mature, Calibration is Unknown

The first verdicts from runs in 2026-06 will mature in 2027-06. Until then:

- The scorecard will show "0 scored, N pending"
- **No calibration-based rubric tuning is justified**
- The correct response to "why do we always get WATCH?" is "we don't know yet — check back in 12 months"

This is not a failure of the system. It is the correct epistemically honest state. The value of
Phase 6 is that it converts this uncertainty from "permanent / unresolvable" to
"time-bounded / resolvable by evidence."

---

## Cross-References

- **`tools/track_forward.py`** — implementation (record, score, scorecard, status, selftest)
- **`metrics/verdicts.jsonl`** — the append-only verdict log
- **`metrics/scorecard.md`** — generated calibration report
- **`reference/cognitive-priors.md`** — epistemic priors that this calibration loop is designed to test
- **`reference/judgment-rubric.md`** — the rubric whose outputs populate verdicts.jsonl
- **`SKILL.md §Track-forward`** — operational instructions for running the loop
