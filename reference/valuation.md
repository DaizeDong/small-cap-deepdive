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
| `ev_ebitda` | ev / latest_ebitda | Uses latest EBITDA; normalized EBITDA in `normalized_ebitda`. EBIT recovered via the cascade below (`ebit_source` tags the concept used) so EV/EBITDA computes even when `OperatingIncomeLoss` is untagged |
| `pe` | market_cap / net_income | null if net income ≤ 0 |
| `fcf_yield` | fcf / market_cap | FCF = OCF − CapEx; if capex unavailable, OCF is used with flag |
| `cyclical` | CV(EBITDA) > threshold | CV computed over available annual EBITDA series; see below |
| `normalized_ebitda` | Trailing N-year average | Only for cyclicals; non-cyclicals use latest |
| `normalized_fcf` | Trailing N-year average FCF | Same normalization logic |
| `rdcf_basis` | `"equity_fcf_vs_market_cap"` | Denominator basis for the reverse-DCF computation |
| `reverse_dcf_implied_growth` | g = discount_rate − norm_fcf / market_cap | Levered (equity) FCF vs market cap; null with reason if FCF ≤ 0, market_cap ≤ 0, or g ≥ discount_rate |
| `fcf_cap_model_unsuitable` | total_debt / total_assets > 0.62 **OR** `lessor_asset_heavy == true` | True for aircraft lessors, finance cos; triggers NAV path. **v0.3.2 #8:** `lessor_asset_heavy` (read from deepdive `derived`) forces this true EVEN BELOW the 0.62 threshold — asset-heavy lessors are valued on lease-fleet NAV, not trough-cycle FCF (see "Lessor NAV routing" below) |
| `lessor_asset_heavy` | bool (deepdive `derived`) | A leasing/rental-business signal emitted by `deepdive_data.py`: leasing/rental SIC OR a lease-income revenue concept OR a very high PP&E / lease-fleet ratio with rental/lease revenue. Read by `valuation.py` (v0.3.2 #8); when true forces `fcf_cap_model_unsuitable = true` (NAV route) regardless of debt/assets |
| `intrinsic_value_band` | norm_fcf / cap_rate − net_debt | Low end: cap_rate_high (12%); high end: cap_rate_low (9%); present for all companies (even unsuitable ones) when FCF > 0 |
| `nav_intrinsic_band` | tangible_equity × [0.80, 1.05] | Only computed when fcf_cap_model_unsuitable = true |
| `mos_basis` | `"fcf_cap"` / `"nav"` / `"abstain"` | Routing signal — see Phase 3 contract below |
| `margin_of_safety_pct` | (intrinsic_low_equity − market_cap) / market_cap | FCF-cap MoS; null when mos_basis ≠ "fcf_cap" |
| `nav_margin_of_safety_pct` | (nav_band_low − market_cap) / market_cap | NAV MoS; populated when mos_basis = "nav" |
| `ebit_source` | str | The EBIT concept the cascade actually used (see "EBIT Concept Cascade" below); tags provenance so EV/EBITDA is auditable |
| `rev_slope_sign` | sign(linear slope of multiyear revenue series) | −1 / 0 / 1; from `derived` trajectory block (P6) |
| `rev_accel_sign` | sign(2nd difference of revenue series) | int; revenue acceleration/deceleration |
| `latest_below_avg` | latest normalization base < trailing avg of base | bool; "is the most recent year below its own normalized average" |
| `contamination_ratio` | latest normalization-base / 5yr-avg | float; < 1.0 means the normalized average is propped up by older/peak years (peak-contamination) |
| `fundamental_decline_flag` | rev_slope_sign < 0 AND contamination_ratio < 1.0 AND latest_below_avg | bool; the deterministic melting-ice-cube veto (P6) — see below |
| `buy_eligible` | composed boolean (see "buy_eligible Composition") | bool; the single mechanical gate Phase 3 ANDs into the BUY trigger |
| `buy_ineligible_reasons` | list[str] | Each guard that fired, for the report TRUST BANNER and audit |

---

## Margin-of-Safety Basis & Phase 3 Contract

Phase 3 (ranking / BUY trigger) MUST follow this three-way decision tree on `mos_basis`.
This is a hard contract — no exceptions based on narrative or management explanation.

### `mos_basis = "fcf_cap"`

- **When:** `fcf_cap_model_unsuitable = false` (normal operating company).
- **Phase 3 action:** use `margin_of_safety_pct` for the BUY trigger with full weight (1.0),
  **gated by `buy_eligible == true`**. A BUY requires `mos_basis == "fcf_cap"` AND MoS ≥ 30% AND
  `buy_eligible == true`; `fundamental_decline_flag` or a `"kill"` `concentration_flag` (both folded
  into `buy_eligible`) downgrade BUY → WATCH (→ AVOID if a kill-flag also fires). See the
  "`buy_eligible` Composition" section and `judgment-rubric.md`.
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

## Lessor NAV Routing — `lessor_asset_heavy` (v0.3.2 #8)

**The hole it closes.** The NAV path was gated on a single threshold: `total_debt / total_assets >
0.62`. That works for aircraft lessors and finance cos that fund their fleets with heavy debt, but
it mis-routes asset-heavy *lessors that fund their fleet with equity / moderate leverage*. The
canonical misses are the railcar lessors: **GBX (Greenbrier, debt/assets = 0.41)** and **RAIL
(FreightCar America, 0.35)** both fall *below* 0.62, so v0.3.1 valued them on trough-cycle
normalized FCF instead of their lease-fleet NAV — GBX's 17,000-car fleet is a textbook NAV
candidate that was left mis-valued (backlog #8). The 0.62 debt ratio is the wrong discriminator for
a lessor: the right one is *whether the business is a leasing/rental fleet at all*.

**The signal.** `deepdive_data.py` emits `lessor_asset_heavy` (bool) into `derived` — a
leasing/rental-business signal that fires on ANY of:
- a leasing/rental **SIC** in `{6726, 7377, 4741, 6159, 7359}` (investment/lease holdcos, computer
  rental/leasing, railroad-car rental, agency lease credit, equipment rental & leasing nec); OR
- an **operating-/finance-lease-income revenue concept** present in the filing's XBRL; OR
- a very high **PP&E (or lease-fleet) / total-assets ratio** combined with rental/lease revenue.

The reason string is recorded in `lessor_asset_heavy_detail`.

**The routing.** `valuation.py` reads `derived.lessor_asset_heavy`; when it is true it forces
`fcf_cap_model_unsuitable = true` — routing the name to the **NAV path (`mos_basis = "nav"`, or
`"abstain"` when tangible equity is unavailable)** EVEN IF `total_debt / total_assets < 0.62`. It
appends `lessor_asset_heavy_fcf_unsuitable_route_nav:<detail>` to `data_quality` so the NAV routing
is auditable and attributable to the lessor signal (not to the debt ratio). GBX and RAIL therefore
value on **lease-fleet NAV**, not phantom trough-cycle FCF. This is a routing change only — it
moves a name from FCF-cap to NAV; it never manufactures a BUY (the NAV path still requires
`nav_margin_of_safety_pct ≥ 30%`, zero kill-flags, `buy_eligible == true`, and the 0.6 confidence
down-weight). A normal industrial with no leasing signals keeps `lessor_asset_heavy = false` and is
unaffected.

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

## Fundamental-Trajectory & Contamination Veto (P6)

**The problem this solves.** The FCF-cap intrinsic value is a no-growth perpetuity on a trailing
normalized FCF. With no trajectory term, the model up-weights exactly the names whose high current
FCF yield is high *because* the market expects the cash flow to fall — the textbook value trap. A
declining, peak-contaminated name (SIGA: revenue −31.8% YoY, BARDA-peak-averaged `norm_fcf`) scored
a +76% MoS BUY while clean growers scored below threshold. The static MoS model has no structural
defense against a melting ice cube.

**The fix (deterministic, downgrade-only).** `compute_valuation()` emits a small trajectory block in
`derived` from the multiyear revenue/normalization-base series and composes a single veto flag. It is
purely mechanical — no forward judgment, no narrative — and it only ever *removes* a BUY, never
creates one.

| Field | Definition |
|---|---|
| `rev_slope_sign` | sign of the linear slope over the multiyear revenue series (−1 down / 0 flat / 1 up) |
| `rev_accel_sign` | sign of the 2nd difference (revenue acceleration vs deceleration) |
| `latest_below_avg` | True when the latest normalization base is below the trailing average of that base |
| `contamination_ratio` | latest normalization-base ÷ 5yr-avg. < 1.0 means the average that anchors `norm_fcf`/`normalized_ebitda` is inflated by older/peak years |
| `fundamental_decline_flag` | **`rev_slope_sign < 0` AND `contamination_ratio < 1.0` AND `latest_below_avg`** |

When all three conditions hold, the most recent year is below its own normalized average AND the
average is propped up by higher prior years AND the revenue trend is down — i.e. the deep "discount"
is an artifact of normalizing on a contaminated peak. `fundamental_decline_flag = true` forces
`buy_eligible = false` (and downstream, BUY → WATCH, or AVOID if a kill-flag also fires; see
`judgment-rubric.md`).

**Relationship to the rubric:222 carve-out.** `judgment-rubric.md` bans vetoing a 30%+ MoS on
qualitative "cyclical-turn-not-realized" / forward-judgment grounds. This veto is the *narrow
mechanical exception* explicitly carved out there: decline magnitude (`rev_slope_sign<0`) +
latest-below-own-average + contamination < 1. It is NOT the qualitative forward call the rubric
forbids; it is a deterministic arithmetic fact about the trailing series the normalization itself
rests on.

---

## EBIT Concept Cascade (P9)

Previously EBIT was a single XBRL pull (`OperatingIncomeLoss`), leaving EV/EBITDA null on ~47% of
names — banks, insurers, IFRS filers, and some industrials that do not tag that concept. EV/EBITDA is
the value PM's workhorse comp; missing it on half the universe forced over-reliance on the FCF-cap
MoS. The module now recovers EBIT through a tagged cascade and records which concept supplied it in
`ebit_source`:

1. `OperatingIncomeLoss` (preferred) → `ebit_source = "OperatingIncomeLoss"`
2. `IncomeLossFromContinuingOperationsBeforeIncomeTaxes` (+ interest expense addback when an interest
   concept is available) → `ebit_source = "continuing_ops_pretax+interest"` (or the no-addback variant
   when interest is unavailable)
3. Pretax-income proxy → `ebit_source = "pretax_proxy"`

When EBIT is recovered via any cascade level, `latest_ebitda` and therefore `ev_ebitda` compute
(subject to the existing EBITDA > 0 and EV > 0 guards). `ebit_source` makes the provenance auditable
so a PM can discount a pretax-proxy EBITDA appropriately. The cascade is provenance-tagged the same
way `debt_source` and `da_source` already are.

---

## `buy_eligible` Composition (P1 — the gate Phase 3 ANDs in)

The v0.2.1 guards (extreme-MoS, large-cap, FCF-sustainability) were advisory strings the BUY trigger
never blocked on — a $5.4B name cleared BUY in a small-cap tool. They are now promoted into one
mechanical boolean that the BUY trigger must AND in. `compute_valuation()` composes and EMITS:

```
buy_eligible =
      (not extreme_mos_review_required)
  AND (not large_cap_out_of_scope)
  AND (not fcf_sustainability_uncertain)
  AND (not financial_sic_forced_unsuitable)
  AND (not debt_truncation_suspected)
  AND (not wrong_entity_suspected)
  AND (concentration_flag != "kill")
  AND (not fundamental_decline_flag)
```

`buy_ineligible_reasons` is the list of guards that fired (e.g. `["large_cap_out_of_scope",
"fundamental_decline_flag"]`), used for the report TRUST BANNER and audit. `buy_eligible = true`
means *no guard objected* — it is necessary but not sufficient for a BUY (Phase 3 still requires
`mos_basis == "fcf_cap"`, MoS ≥ 30%, zero kill-flags, and no Tier-3-load-bearing evidence; see
`judgment-rubric.md`). The concentration kill-flag (`concentration_flag`) is produced in the deepdive
`derived` block from XBRL `RevenueFromContractWithCustomer` segment members / concentration footnote
numerics (P3) — see `data-sources.md` and `mechanical-checks.md` — not from the old English substring.

---

## Inputs: Source and Fallback Chain

All inputs come from SEC/XBRL (T1) except market cap (yfinance or override):

| Input | Primary XBRL concept | Fallback |
|---|---|---|
| `total_debt` | `LongTermDebtNoncurrent` + `LongTermDebtCurrent` | `LongTermDebt`; then `Liabilities` (proxy, flagged) |
| `ebit` | `OperatingIncomeLoss` | Cascade: `IncomeLossFromContinuingOperationsBeforeIncomeTaxes` (+interest addback if available) → pretax proxy; concept used recorded in `ebit_source` (see "EBIT Concept Cascade") |
| `dep_amort` | `DepreciationAndAmortization`, `DepreciationAmortizationAndAccretionNet`, `DepreciationDepletionAndAmortization` (merged) | — |
| `capex` | `PaymentsToAcquirePropertyPlantAndEquipment` | If unavailable, FCF = OCF (proxy, flagged) |
| `assets` | `Assets` | — |
| `equity` | `StockholdersEquity` | — |
| `goodwill` | `Goodwill` | Absent → 0 used for NAV with proxy flag |
| `intangibles` | `IntangibleAssetsNetExcludingGoodwill` | Absent → 0 used for NAV with proxy flag |

The `debt_source` and `da_source` fields in `derived` document which fallback level was used.

**Foreign-filer IFRS recovery (v0.3.2 #11).** Whole 20-F / 40-F cohorts previously returned empty
financials because their XBRL is tagged under the `ifrs-full` taxonomy, not `us-gaap` — yielding
`intrinsic_band_unavailable` for the entire cohort. `deepdive_data.py` now extends the XBRL concept
cascade for the most common IFRS tags (`ifrs-full` `Revenue`, `ProfitLoss`,
`CashFlowsFromUsedInOperatingActivities`, and equivalents) so SOME foreign filers recover (the
`us-gaap` path is tried first; IFRS only fills genuine gaps). When financials are STILL empty for a
foreign filer after the cascade, the producer emits `foreign_filer_unvaluable` (bool) so the abstain
is CLEARLY labeled rather than a silent null — see the data-quality flag below and the
`foreign_filer_unvaluable` paragraph in `judgment-rubric.md`. This is a tractable XBRL-tag
extension only; it does NOT attempt full financial-statement document parsing. The abstain stays
graceful — never a crash, never a false BUY.

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
| `lessor_asset_heavy_fcf_unsuitable_route_nav:<detail>` | v0.3.2 #8 — `derived.lessor_asset_heavy == true` forced `fcf_cap_model_unsuitable = true` (NAV route) EVEN BELOW the 0.62 debt/assets threshold; an asset-heavy lessor (GBX 0.41 / RAIL 0.35) valued on lease-fleet NAV, not trough-cycle FCF. `<detail>` names the firing signal (leasing/rental SIC, lease-income concept, or PP&E/fleet ratio + rental revenue) |
| `foreign_filer_unvaluable:<detail>` | v0.3.2 #11 — a 20-F / 40-F foreign filer whose revenue / net-income / OCF were STILL empty after the us-gaap + ifrs-full concept cascade; the abstain is explicitly labeled "foreign filer — un-valuable from EDGAR" instead of a bare `intrinsic_band_null`. Label-only; the null MoS already forces `buy_eligible = false` via `not_assessable_no_intrinsic_band` (no separate BUY gate; never a false BUY) |
| `net_debt_excludes_cash` | Net debt = total_debt only (cash unavailable) |
| `net_debt_excludes_debt_liabilities` | Net debt computed as −cash (debt unavailable) |
| `nav_goodwill_or_intangibles_unavailable:...` | Goodwill or intangibles absent; tangible equity uses book equity as proxy |
| `ebit_recovered_via_cascade:<ebit_source>` | EBIT was not from `OperatingIncomeLoss`; recovered via the P9 cascade (concept named) |
| `fundamental_decline_veto` | `fundamental_decline_flag = true`; trajectory + contamination veto fired (P6); forces `buy_eligible = false` |
| `buy_ineligible:<reason>` | One row per guard in `buy_ineligible_reasons` that set `buy_eligible = false` |

---

## Guardrails (Code Behavior, Not LLM Judgment)

1. **T1 data only.** All financial inputs are from SEC/XBRL. Market cap is from yfinance
   (clearly labeled; override with `--mktcap` for audit reproducibility).
2. **Cyclicals use normalized, not peak/trough.** Hardcoded in `compute_valuation()`.
3. **Band is deliberately conservative.** The MoS uses the high-cap-rate (low-value) end.
4. **No recommendation emitted.** The module's JSON contains no buy/sell/avoid text.
   Phase 3 reads `mos_basis` + `margin_of_safety_pct` / `nav_margin_of_safety_pct` + the
   `buy_eligible` gate and applies the BUY trigger mechanically per the Phase 3 contract above.
   `buy_eligible` is a mechanical eligibility boolean (a conjunction of guards), NOT a
   recommendation — it can only block a BUY, never assert one.
8. **Trajectory veto is downgrade-only and deterministic.** `fundamental_decline_flag` is a pure
   function of the trailing series (slope sign + contamination ratio + latest-below-average). It
   removes a BUY; it can never manufacture one. This is the narrow mechanical carve-out to
   `judgment-rubric.md:222`, not the qualitative forward judgment that rule bans.
9. **EBIT cascade is provenance-tagged.** EBIT recovered below `OperatingIncomeLoss` is labeled in
   `ebit_source`; EV/EBITDA computed off a proxy is auditable, never silently presented as primary.
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
- Phase 3 (implemented) — reads `mos_basis`, the corresponding MoS field, and the `buy_eligible`
  gate; applies BUY trigger per the three-way contract documented in "Margin-of-Safety Basis &
  Phase 3 Contract" above.
- `data-sources.md` — origin of the P3 `concentration_flag` (XBRL `RevenueFromContractWithCustomer`
  segment members) that `buy_eligible` consumes.
- `config.example.json` — all valuation config keys with defaults.
