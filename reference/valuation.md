# Valuation Module — Phase 2

> **Contract:** this module outputs numbers only. It does NOT output a buy/sell rating.
> Phase 3 consumes `margin_of_safety_pct` or `nav_margin_of_safety_pct` to trigger a BUY/AVOID
> flag mechanically, following the three-way `mos_basis` decision tree below.

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
| `rdcf_basis` | `"equity_fcf_vs_market_cap"` | Denominator basis for the reverse-DCF computation |
| `reverse_dcf_implied_growth` | g = discount_rate − norm_fcf / market_cap | Levered (equity) FCF vs market cap; null with reason if FCF ≤ 0, market_cap ≤ 0, or g ≥ discount_rate |
| `fcf_cap_model_unsuitable` | total_debt / total_assets > 0.62 | True for aircraft lessors, finance cos; triggers NAV path |
| `intrinsic_value_band` | norm_fcf / cap_rate − net_debt | Low end: cap_rate_high (12%); high end: cap_rate_low (9%); present for all companies (even unsuitable ones) when FCF > 0 |
| `nav_intrinsic_band` | tangible_equity × [0.80, 1.05] | Only computed when fcf_cap_model_unsuitable = true |
| `mos_basis` | `"fcf_cap"` / `"nav"` / `"abstain"` | Routing signal — see Phase 3 contract below |
| `margin_of_safety_pct` | (intrinsic_low_equity − market_cap) / market_cap | FCF-cap MoS; null when mos_basis ≠ "fcf_cap" |
| `nav_margin_of_safety_pct` | (nav_band_low − market_cap) / market_cap | NAV MoS; populated when mos_basis = "nav" |

---

## Margin-of-Safety Basis & Phase 3 Contract

Phase 3 (ranking / BUY trigger) MUST follow this three-way decision tree on `mos_basis`.
This is a hard contract — no exceptions based on narrative or management explanation.

### `mos_basis = "fcf_cap"`

- **When:** `fcf_cap_model_unsuitable = false` (normal operating company).
- **Phase 3 action:** use `margin_of_safety_pct` for the BUY trigger with full weight (1.0).
- **Interpretation:** positive MoS = market cap is below the conservative FCF-capitalized
  intrinsic value. The larger the positive MoS, the deeper the discount.

### `mos_basis = "nav"`

- **When:** `fcf_cap_model_unsuitable = true` AND `latest_equity` is available (so tangible
  equity can be computed).
- **Phase 3 action:** use `nav_margin_of_safety_pct` for the BUY trigger at reduced weight
  (0.6) — lower confidence because asset book values embed accounting conventions and
  collateral haircuts vary by asset class.
- **Surface as:** "asset-heavy / NAV basis" in reports.
- **EV multiples** (`ev_sales`, `ev_ebitda`) should be reported alongside for relative
  comparison.
- **Do NOT** use `margin_of_safety_pct` (FCF MoS) for these companies; it will be null with
  `mos_null_reason = "fcf_cap_model_unsuitable_use_nav"`.

### `mos_basis = "abstain"`

- **When:** `fcf_cap_model_unsuitable = true` AND `latest_equity` is unavailable (NAV band
  cannot be computed).
- **Phase 3 action:** do NOT apply a BUY or AVOID trigger on MoS. Never penalize the ranking
  for a model-mismatch (a company that is asset-heavy is not automatically bad).
- **Report only:** `ev_ebitda` and `ev_sales` for relative comparison against peers.
- **Do NOT** report either `margin_of_safety_pct` or `nav_margin_of_safety_pct` as meaningful
  signals.

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

**Why market_cap (not EV) for reverse-DCF:**
`norm_fcf` is OCF − CapEx — a levered (equity) cash flow that is computed after interest payments.
The correct denominator in the Gordon growth model for levered FCF is the equity value (market cap),
not EV (which is the claim of all capital providers). Using EV with levered FCF systematically
understates implied growth for leveraged companies. The `rdcf_basis = "equity_fcf_vs_market_cap"`
field documents this choice explicitly.

**Why skip EBITDA partial entries:**
When only EBIT or only D&A is available for a given year-end, including that partial sum distorts
the coefficient-of-variation used to detect cyclicality and distorts the normalized average.
`_build_ebitda_series` skips those year-ends and records the count in `ebitda_series_partial_entries:<n>`.

---

## Inputs: Source and Fallback Chain

All inputs come from SEC/XBRL (T1) except market cap (yfinance or override):

| Input | Primary XBRL concept | Fallback |
|---|---|---|
| `total_debt` | `LongTermDebtNoncurrent` + `LongTermDebtCurrent` | `LongTermDebt`; then `Liabilities` (proxy, flagged) |
| `ebit` | `OperatingIncomeLoss` | — |
| `dep_amort` | `DepreciationAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `DepreciationDepletionAndAmortization` (merged) | — |
| `capex` | `PaymentsToAcquirePropertyPlantAndEquipment` | If unavailable, FCF = OCF (proxy, flagged) |
| `assets` | `Assets` | — |
| `equity` | `StockholdersEquity` | — |
| `goodwill` | `Goodwill` | Absent → 0 used for NAV with proxy flag |
| `intangibles` | `IntangibleAssetsNetExcludingGoodwill` | Absent → 0 used for NAV with proxy flag |

The `debt_source` and `da_source` fields in `derived` document which fallback level was used.

**Empirical notes from probing WLFC and LNN:**
- WLFC (CIK 1018164): `LongTermDebt` available (no split concepts); `DepreciationDepletionAndAmortization` and `DepreciationAndAmortization` both present (merged). Debt/assets ~67% → `fcf_cap_model_unsuitable = true`.
- LNN (CIK 836157): both `LongTermDebtNoncurrent` + `LongTermDebtCurrent` available; only `DepreciationAndAmortization` present. Normal industrial → `fcf_cap_model_unsuitable = false`, `mos_basis = "fcf_cap"`.

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

The `data_quality` field is a list of strings. Each string documents a gap or assumption.
This table is the canonical list of ALL flags emitted by `compute_valuation()`:

| Flag | Meaning |
|---|---|
| `cash_unavailable` | Cash field absent from XBRL; EV excludes cash |
| `debt_unavailable` | Debt concept absent; EV excludes debt |
| `debt_is_total_liabilities_proxy:<src>` | Debt fell back to total Liabilities (flagged with source label) |
| `dep_amort_unavailable` | D&A series absent; EBITDA series will be incomplete |
| `capex_unavailable_fcf_uses_ocf_proxy` | No CapEx concept found; FCF will equal OCF |
| `fcf_equals_ocf_proxy_no_capex` | Confirms proxy mode (redundant confirmation of above) |
| `net_income_nonpositive_pe_null` | NI ≤ 0; P/E ratio is null |
| `shares_unavailable_per_share_null` | Shares series absent; per-share intrinsic values are null |
| `ev_excludes_cash` | EV computed without cash (cash unavailable) |
| `ev_excludes_debt` | EV computed without debt (debt unavailable) |
| `ev_is_market_cap_only` | Both debt and cash unavailable; EV = market cap |
| `ev_nonpositive_multiples_null` | EV ≤ 0; EV/Sales and EV/EBITDA are suppressed |
| `ebitda_nonpositive_ev_ebitda_null` | EBITDA ≤ 0; EV/EBITDA is null |
| `ebitda_series_partial_entries:<n>` | n year-ends skipped from EBITDA series (only one of EBIT/D&A available) |
| `normalized_ebitda_unavailable` | Insufficient data to compute normalized EBITDA |
| `normalized_fcf_unavailable` | Insufficient data to compute normalized FCF |
| `normalized_uses_<n>yr_insufficient` | Normalization window used only n years (< normalize_years config) |
| `intrinsic_band_null:normalized_fcf_unavailable` | FCF intrinsic band null because FCF data is absent |
| `intrinsic_band_null:normalized_fcf_nonpositive` | FCF intrinsic band null because normalized FCF ≤ 0 |
| `rdcf_implied_growth_very_negative:...` | Reverse-DCF g < −20%; market pricing in steep decline |
| `rdcf_implied_growth_very_high:...` | Reverse-DCF g > 20%; market pricing in very high growth |
| `fcf_cap_model_unsuitable:debt_to_assets=<x>>0.62` | Debt/assets > 62%; FCF-cap model not appropriate; NAV path used |
| `net_debt_excludes_cash` | Net debt = total_debt only (cash unavailable) |
| `net_debt_excludes_debt_liabilities` | Net debt computed as −cash (debt unavailable) |
| `nav_goodwill_or_intangibles_unavailable:...` | Goodwill or intangibles absent; tangible equity uses book equity as proxy |

---

## Guardrails (Code Behavior, Not LLM Judgment)

1. **T1 data only.** All financial inputs are from SEC/XBRL. Market cap is from yfinance
   (clearly labeled; override with `--mktcap` for audit reproducibility).
2. **Cyclicals use normalized, not peak/trough.** Hardcoded in `compute_valuation()`.
3. **Band is deliberately conservative.** The MoS uses the high-cap-rate (low-value) end.
4. **No recommendation emitted.** The module's JSON contains no buy/sell/avoid text.
   Phase 3 reads `mos_basis` + `margin_of_safety_pct` / `nav_margin_of_safety_pct` and
   applies the BUY trigger mechanically per the Phase 3 contract above.
5. **Divide-by-zero and non-positive guards.** Every division is guarded; results are
   null with a documented reason rather than NaN or exceptions.
6. **EBITDA partial entries skipped.** Year-ends with only one of EBIT / D&A are excluded
   from the EBITDA series to avoid distorting the cyclicality CV and normalization.
7. **Reverse-DCF validity guard.** If implied g ≥ discount_rate (economically invalid
   perpetuity), the result is set to null with `reverse_dcf_null_reason =
   "implied_growth_ge_discount_rate"` instead of emitting a nonsensical number.

---

## Cross-References

- `mechanical-checks.md` — data-layer guards; valuation module respects all five.
- `judgment-rubric.md` — human/agent judgment layer reads valuation block alongside scores.
- Phase 3 (implemented) — reads `mos_basis` and the corresponding MoS field; applies BUY trigger
  per the three-way contract documented in "Margin-of-Safety Basis & Phase 3 Contract" above.
- `config.example.json` — all valuation config keys with defaults.
