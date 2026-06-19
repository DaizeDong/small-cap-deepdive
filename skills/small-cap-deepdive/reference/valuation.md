# Valuation Module — Phase 2

> **Contract:** this module outputs numbers only. It does NOT output a buy/sell rating.
> Phase 3 consumes `margin_of_safety_pct` to trigger a BUY/AVOID flag mechanically.

---

## What `tools/valuation.py` Computes

Given a `deepdive_<ticker>_<date>.json` (produced by `deepdive_data.py`) and a current market cap
(from yfinance or `--mktcap` override), the module produces a `valuation` block containing:

| Field | Formula | Notes |
|---|---|---|
| `ev` | market_cap + total_debt − cash | Partial if debt/cash unavailable; annotated in `ev_note` |
| `ev_sales` | ev / latest_revenue | null if revenue ≤ 0 or ev ≤ 0 |
| `ev_ebitda` | ev / latest_ebitda | Uses latest EBITDA; normalized EBITDA in `normalized_ebitda` |
| `pe` | market_cap / net_income | null if net income ≤ 0 |
| `fcf_yield` | fcf / market_cap | FCF = OCF − CapEx; if capex unavailable, OCF is used with flag |
| `cyclical` | CV(EBITDA) > threshold | CV computed over available annual EBITDA series; see below |
| `normalized_ebitda` | Trailing N-year average | Only for cyclicals; non-cyclicals use latest |
| `normalized_fcf` | Trailing N-year average FCF | Same normalization logic |
| `reverse_dcf_implied_growth` | g = wacc − normalized_fcf / EV | Gordon approximation; null with reason if FCF ≤ 0 or EV ≤ 0 |
| `intrinsic_value_band` | normalized_fcf / cap_rate − net_debt | Low end: cap_rate_high (12%); high end: cap_rate_low (9%) |
| `margin_of_safety_pct` | (intrinsic_low_equity − market_cap) / market_cap | Positive = cheap vs conservative intrinsic |

---

## Conservative / Normalized Philosophy

**Why normalization matters for cyclicals:**
Using peak EBITDA in an up-cycle overstates intrinsic value; using trough EBITDA in a down-cycle
understates it. For cyclical businesses (EBITDA coefficient-of-variation > 0.25), the module uses
the trailing N-year average (default 5 years) as the base rate for both EBITDA and FCF.

The CV is measured on the annual EBITDA series from SEC/XBRL data. If EBITDA series is too short
(< 3 data points), the CV falls back to revenue CV. If neither series has ≥ 3 points, `cyclical`
defaults to False with a data-quality flag.

**Why two cap rates:**
A single intrinsic value estimate is false precision. The band forces the consumer (Phase 3 or
human analyst) to see both the conservative and less-conservative estimate. The CONSERVATIVE end
(cap_rate_high = 12%) is the one used for `margin_of_safety_pct`. Buying when the conservative
intrinsic is below market price means you need the market to be wrong AND to be wrong in a
worst-case way before you lose money on the thesis.

---

## Inputs: Source and Fallback Chain

All inputs come from SEC/XBRL (T1) except market cap (yfinance or override):

| Input | Primary XBRL concept | Fallback |
|---|---|---|
| `total_debt` | `LongTermDebtNoncurrent` + `LongTermDebtCurrent` | `LongTermDebt`; then `Liabilities` (proxy, flagged) |
| `ebit` | `OperatingIncomeLoss` | — |
| `dep_amort` | `DepreciationAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `DepreciationDepletionAndAmortization` (merged) | — |
| `capex` | `PaymentsToAcquirePropertyPlantAndEquipment` | If unavailable, FCF = OCF (proxy, flagged) |

The `debt_source` and `da_source` fields in `derived` document which fallback level was used.

**Empirical notes from probing WLFC and LNN:**
- WLFC (CIK 1018164): `LongTermDebt` available (no split concepts); `DepreciationDepletionAndAmortization` and `DepreciationAndAmortization` both present (merged).
- LNN (CIK 836157): both `LongTermDebtNoncurrent` + `LongTermDebtCurrent` available; only `DepreciationAndAmortization` present.

---

## Config Keys

Set in `config.json` (see `config.example.json` for defaults):

| Key | Default | Meaning |
|---|---|---|
| `wacc` | 0.10 | Discount rate used in reverse DCF Gordon approximation |
| `cap_rate_low` | 0.09 | Low cap rate → high equity estimate (optimistic band end) |
| `cap_rate_high` | 0.12 | High cap rate → low equity estimate (conservative band end) |
| `normalize_years` | 5 | Trailing years averaged for cyclical normalization |
| `cyclical_cv_threshold` | 0.25 | EBITDA coefficient-of-variation above which a company is treated as cyclical |

---

## Output Files

- `reports/smallcap/valuation_<ticker>_<date>.json` — standalone valuation block
- The deepdive JSON is also updated in-place with a top-level `"valuation"` key

---

## Data Quality Flags

The `data_quality` field is a list of strings. Each string documents a gap or assumption:

| Flag | Meaning |
|---|---|
| `cash_unavailable` | Cash field absent from XBRL; EV excludes cash |
| `debt_unavailable` | Debt concept absent; EV excludes debt |
| `debt_is_total_liabilities_proxy:...` | Debt fell back to total Liabilities |
| `capex_unavailable_fcf_uses_ocf_proxy` | No CapEx concept; FCF = OCF |
| `fcf_equals_ocf_proxy_no_capex` | Redundant confirm of proxy mode |
| `net_income_nonpositive_pe_null` | P/E is null because NI ≤ 0 |
| `ev_nonpositive_multiples_null` | EV ≤ 0; multiples suppressed |
| `ebitda_nonpositive_ev_ebitda_null` | EBITDA ≤ 0; EV/EBITDA null |
| `normalized_ebitda_unavailable` | Insufficient data for normalization |
| `intrinsic_band_null:...` | Reason why intrinsic band could not be computed |
| `rdcf_implied_growth_very_negative` | g < −20%; market is pricing in decline |
| `rdcf_implied_growth_very_high` | g > 20%; market is pricing in very high growth |

---

## Guardrails (Code Behavior, Not LLM Judgment)

1. **T1 data only.** All financial inputs are from SEC/XBRL. Market cap is from yfinance
   (clearly labeled; override with `--mktcap` for audit reproducibility).
2. **Cyclicals use normalized, not peak/trough.** Hardcoded in `compute_valuation()`.
3. **Band is deliberately conservative.** The MoS uses the high-cap-rate (low-value) end.
4. **No recommendation emitted.** The module's JSON contains no buy/sell/avoid text.
   Phase 3 reads `margin_of_safety_pct` and applies the BUY trigger mechanically.
5. **Divide-by-zero and non-positive guards.** Every division is guarded; results are
   null with a documented reason rather than NaN or exceptions.

---

## Cross-References

- `mechanical-checks.md` — data-layer guards; valuation module respects all five.
- `judgment-rubric.md` — human/agent judgment layer reads valuation block alongside scores.
- Phase 3 (planned) — reads `margin_of_safety_pct` and triggers BUY at configured threshold.
- `config.example.json` — all valuation config keys with defaults.
