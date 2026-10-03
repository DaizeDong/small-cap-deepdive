"""
valuation.py — Phase 2 deterministic valuation layer for small-cap-deepdive.

GUARDRAILS (enforced by code behavior, not LLM judgment):
  1. All inputs are T1 SEC/XBRL data from deepdive_data.py or yfinance market cap.
  2. Cyclicals use normalized (trailing multi-year average) EBITDA/FCF, NOT latest peak/trough.
  3. The intrinsic value band is deliberately conservative (cap rates 9-12%).
  4. This module outputs numbers ONLY. It does NOT output a buy/sell rating.
     Phase 3 consumes margin_of_safety_pct to trigger BUY/AVOID mechanically.
  5. Any unavailable input is documented in data_quality flags; computation proceeds
     on available data with explicit null-with-reason where required.

Philosophy:
  Valuation is a data transformation, not a recommendation. The output block feeds
  Phase 3's margin-of-safety BUY trigger. An analyst or Phase 3 agent reads this
  block and acts; this module never tells them what to do.

Private path setup:
    Initialize a versioned PRIVATE companion with SMALL_CAP_DEEPDIVE_CONFIG_DIR.
    Set REPORTS_ROOT to the absolute path returned by _common.reports_dir():
        python -c "import sys; sys.path.insert(0, 'tools'); from _common import reports_dir; print(reports_dir())"
    The resolver includes SMALLCAP_RUN when set and fails if initialization is missing.

Usage (REPORTS_ROOT is the resolved absolute private path):
    python tools/valuation.py --json "${REPORTS_ROOT}/deepdive_SYNTA_2000-01-01.json" --ticker SYNTA
    python tools/valuation.py --json "${REPORTS_ROOT}/deepdive_SYNTA_2000-01-01.json" --ticker SYNTA --mktcap 120000000
    python tools/valuation.py --selftest
Output: _common.reports_dir()/valuation_<ticker>_<date>.json.
The CLI also merges the valuation block into the supplied private deepdive JSON;
both destinations pass the private-output path check. --selftest is synthetic.
--live-diagnostic is a separate explicit entry point that may acquire live data and
write private reports.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# sys.path shim so this script can be run directly from tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, init_edgar, today, reports_dir, prove_output_path, prepare_output

# Valuation model primitives extracted to a sibling module (pure mechanical move).
# Re-exported here so any consumer importing them from `valuation` keeps working.
from _valuation_model import (
    _VALUATION_DEFAULTS,
    _val_cfg,
    _get_market_cap,
    _coefficient_of_variation,
    _is_cyclical,
    _normalize,
    _build_ebitda_series,
)
# buy_eligible composite (the BUY-trigger guard half) extracted to a sibling module.
from _valuation_eligibility import compose_buy_eligibility
from _cash_flow_evidence import paired_cash_flow_evidence, paired_annual_sum_evidence


# ---------------------------------------------------------------------------
# Core valuation computation
# ---------------------------------------------------------------------------
def _build_fcf_series(ocf_series: list[dict], capex_series: list[dict],
                      fcf_is_proxy: bool) -> tuple[list[dict], bool]:
    """Keep the valuation API while applying the same annual-period evidence contract."""
    periods = paired_cash_flow_evidence(ocf_series, capex_series, fcf_is_proxy)
    return periods, any(not period["qualified"] for period in periods)


def _debt_evidence(derived: dict, financials: dict) -> tuple:
    """Reconcile a debt scalar with the latest complete, same-period evidence.

    A number or a summary label alone cannot establish contractual-debt coverage.
    Older complete periods cannot override newer partial, malformed or conflicting rows.
    """
    from datetime import date
    from math import isclose
    from sys import float_info

    components = ("LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings",
                  "FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent")
    scopes = {
        "LongTermDebt": components[:2],
        "LongTermDebtAndCapitalLeaseObligations": components[:2] + components[3:],
        "DebtLongtermAndShorttermCombinedAmount": components[:3],
    }
    known = {"reported", "partial", "conflicting", "invalid", "unavailable", "unverified"}

    def numeric(value):
        return type(value) in (int, float) and 0 <= value <= float_info.max

    scalar = derived.get("latest_total_debt")
    value = scalar if numeric(scalar) else None
    declared = derived.get("debt_evidence_status")
    if declared is not None and (not isinstance(declared, str) or declared not in known):
        declared = "unverified"
    issues = []
    statuses = []
    if declared and declared != "reported":
        statuses.append(declared)
    series = financials.get("total_debt")
    if series is None or series == []:
        statuses.append("unavailable" if value is None else "unverified")
        if value is not None:
            issues.append("latest debt-period evidence missing")
    elif not isinstance(series, list):
        statuses.append("invalid")
        issues.append("debt series is not a list")
    else:
        dated = []
        for row in series:
            if not isinstance(row, dict):
                statuses.append("invalid")
                issues.append("debt period is not an object")
                continue
            try:
                end = row.get("end")
                if not isinstance(end, str) or len(end) != 10:
                    raise ValueError("invalid period date")
                period = date.fromisoformat(end)
            except (TypeError, ValueError):
                statuses.append("invalid")
                issues.append("debt period date invalid")
                continue
            dated.append((period, row))
        if dated:
            latest = max(day for day, _ in dated)
            latest_rows = [row for day, row in dated if day == latest]
            for row in latest_rows:
                status = row.get("debt_evidence_status")
                status = status if isinstance(status, str) and status in known else "unverified"
                statuses.append(status)
                amount = row.get("val")
                if not numeric(amount):
                    statuses.append("invalid" if amount is not None else "unavailable")
                    issues.append("latest debt-period value unavailable or invalid")
                elif value is not None and not isclose(value, amount, rel_tol=1e-6, abs_tol=1):
                    statuses.append("conflicting")
                    issues.append("latest debt scalar differs from latest period")
                parts = row.get("components")
                if not isinstance(parts, dict) or any(key not in parts for key in components):
                    statuses.append("partial")
                    issues.append("latest period lacks contractual-debt components")
                elif (any(not numeric(parts[key]) for key in components)
                      or not numeric(sum(float(parts[key]) for key in components))):
                    statuses.append("invalid")
                    issues.append("latest contractual-debt component or total invalid")
                elif numeric(amount):
                    if not isclose(sum(float(parts[key]) for key in components), amount, rel_tol=1e-6, abs_tol=1):
                        statuses.append("conflicting")
                        issues.append("latest debt total differs from component sum")
                    aggregates = row.get("aggregates", {})
                    if not isinstance(aggregates, dict):
                        statuses.append("invalid")
                        issues.append("latest debt aggregates malformed")
                    else:
                        for key, tags in scopes.items():
                            if key in aggregates and (not numeric(aggregates[key]) or not isclose(
                                    aggregates[key], sum(float(parts[tag]) for tag in tags), rel_tol=1e-6, abs_tol=1)):
                                statuses.append("conflicting")
                                issues.append("latest debt aggregate conflicts with component evidence")
                if row.get("missing_components"):
                    statuses.append("partial")
                if row.get("conflicting_aggregates"):
                    statuses.append("conflicting")
                if "proxy" in str(row.get("source") or "").lower():
                    statuses.append("partial")
        else:
            statuses.append("unavailable")
    if scalar is not None and value is None:
        statuses.append("invalid")
        issues.append("derived debt value invalid")
    elif value is None:
        statuses.append("unavailable")
    priority = ("conflicting", "invalid", "partial", "unavailable", "unverified")
    status = next((item for item in priority if item in statuses), "reported")
    uncertain = bool(status != "reported" or derived.get("debt_evidence_uncertain")
                     or "proxy" in str(derived.get("debt_source") or "").lower())
    detail = derived.get("debt_evidence_detail")
    if issues:
        detail = "; ".join([str(detail)] if detail else []) + ("; " if detail else "") + "; ".join(dict.fromkeys(issues))
    return value, status, uncertain, detail


def compute_valuation(dd: dict, market_cap: int, cfg: dict) -> dict:
    """
    Compute the full valuation block from a deepdive JSON dict and market cap.

    Returns a dict with keys:
      ev, ev_sales, ev_ebitda, pe, fcf_yield,
      cyclical, cv_ebitda, normalized_ebitda, normalized_fcf,
      rdcf_basis, reverse_dcf_implied_growth,
      fcf_cap_model_unsuitable, mos_basis,
      intrinsic_value_band (low/high equity and per-share),
      margin_of_safety_pct / mos_null_reason,
      nav_intrinsic_band, nav_margin_of_safety_pct,
      assumptions, data_quality, computed_at.
    """
    fin = dd.get("financials", {})
    der = dd.get("derived", {})
    dq: list[str] = []  # data_quality flags

    discount_rate_key = "equity_discount_rate" if "equity_discount_rate" in cfg else "wacc"
    discount_rate = cfg[discount_rate_key]
    cap_low = cfg["cap_rate_low"]    # low cap rate → HIGH equity value (optimistic end)
    cap_high = cfg["cap_rate_high"]  # high cap rate → LOW equity value (conservative end)
    n_years = int(cfg["normalize_years"])
    cv_threshold = cfg["cyclical_cv_threshold"]

    # --- Inputs ---
    latest_cash = der.get("latest_cash")
    latest_debt, debt_status, debt_uncertain, debt_detail = _debt_evidence(der, fin)
    if debt_uncertain:
        dq.append(f"debt_evidence_uncertain:{debt_status}:{debt_detail or 'contractual debt not established'}")
    latest_revenue = der.get("latest_revenue")
    latest_ni = der.get("latest_net_income")
    latest_ocf = der.get("latest_ocf")
    latest_ebit = der.get("latest_ebit")
    latest_da = der.get("latest_dep_amort")
    latest_capex = der.get("latest_capex")
    fcf_is_proxy = der.get("fcf_is_ocf_proxy", False)

    # Asset-heavy / NAV inputs (assets from financials series; goodwill/intangibles from derived)
    assets_series = fin.get("assets", [])
    latest_assets = assets_series[-1]["val"] if assets_series else der.get("latest_assets")
    equity_series = fin.get("equity", [])
    latest_equity = equity_series[-1]["val"] if equity_series else None
    latest_goodwill = der.get("latest_goodwill")
    latest_intangibles = der.get("latest_intangibles")

    # --- I3: propagate data_quality_warn and C1 flags from deepdive derived ---
    _dq_warn = der.get("data_quality_warn")
    if _dq_warn:
        dq.append(f"deepdive_data_quality_warn:{_dq_warn}")
    if der.get("debt_truncation_suspected"):
        _dt_detail = der.get("debt_truncation_detail", "")
        dq.append(f"debt_truncation_suspected:{_dt_detail}")
    if der.get("debt_stale"):
        dq.append("debt_stale:>18_months_behind_latest_assets")
    if der.get("wrong_entity_suspected"):
        _we_reason = der.get("wrong_entity_reason", "")
        dq.append(f"wrong_entity_suspected:{_we_reason}")
    # P-B: low_revenue_loss_ratio is a DATA-QUALITY LABEL ONLY (early/pre-revenue resource
    # pattern: present-but-tiny revenue + large genuine loss). It surfaces in data_quality so a
    # PM sees the real cause (right entity, tiny revenue) instead of the old wrong_entity misfire.
    # It does NOT by itself flip buy_eligible, those names stay blocked by their null/negative
    # FCF (MoS null) as before, NOT by this label.
    if der.get("low_revenue_loss_ratio"):
        _lrl_detail = der.get("low_revenue_loss_ratio_detail", "")
        # A4: distinguish the EXTREME (>20x) tier (gates buy_eligible) from the advisory label.
        _lrl_tag = "low_revenue_loss_ratio_extreme" if der.get("low_revenue_loss_ratio_extreme") else "low_revenue_loss_ratio"
        dq.append(f"{_lrl_tag}:{_lrl_detail}")
    # A2: concentration_unquantified, text customer-concentration flag True but no XBRL magnitude
    # Text-only or early-XBRL financial evidence may omit the magnitude. Advisory only:
    # surfaced in data_quality so a PM sees the unquantified concentration; does NOT gate.
    if der.get("concentration_unquantified"):
        dq.append("concentration_unquantified:text_flag_true_but_xbrl_magnitude_null")
    # v0.3.2 #11: foreign_filer_unvaluable, a 20-F/40-F filer whose revenue/net-income/OCF were
    # STILL empty after the producer's us-gaap+ifrs-full concept cascade. Surface it as an EXPLICIT
    # data-quality label so the abstain reads "foreign filer, un-valuable from EDGAR" instead of a
    # bare intrinsic_band_unavailable null. Label-only here; the null MoS already gates buy_eligible
    # via not_assessable_no_intrinsic_band (no separate BUY gate needed, never a false BUY).
    _foreign_filer_unvaluable = bool(der.get("foreign_filer_unvaluable", False))
    if _foreign_filer_unvaluable:
        _ffu_detail = der.get("foreign_filer_unvaluable_detail", "")
        dq.append(f"foreign_filer_unvaluable:{_ffu_detail}")

    # --- C2: financial-SIC guard, exclude financial sector from FCF-cap model ---
    # SIC prefixes: 60=banks, 61=non-depository credit, 63=insurance carriers,
    #               64=insurance agents, 67=holding companies/investment/REITs/BDCs
    _FINANCIAL_SIC_PREFIXES = ("60", "61", "63", "64", "67")
    sic_code = str(der.get("sic") or "").strip()
    _financial_sic = bool(sic_code and any(sic_code.startswith(p) for p in _FINANCIAL_SIC_PREFIXES))
    # A3: insurance_concepts_present, an insurance underwriter / insurance-subsidiary holdco
    # detected from XBRL concepts (PremiumsEarned / policy reserves / losses&LAE / policyholder
    # funds). These route like a financial_sic name (nav/abstain, never an fcf_cap BUY) EVEN when
    # the top-level SIC is non-financial. Distinct buy_eligible gate below.
    _insurance_concepts_present = bool(der.get("insurance_concepts_present", False))
    _financial_sic_forced_unsuitable = False
    if _financial_sic:
        _financial_sic_forced_unsuitable = True
        dq.append(f"financial_sic_fcf_unsuitable:sic={sic_code}")
    elif _insurance_concepts_present:
        # A3: insurance-bearing holdco on a non-financial SIC routes like financial_sic.
        _financial_sic_forced_unsuitable = True
        _ins_concept = der.get("insurance_concept_matched", "")
        dq.append(f"insurance_concepts_present_fcf_unsuitable:concept={_ins_concept}")
    elif not sic_code:
        # Missing SIC leaves financial structure unconfirmed. Revenue absent with
        # operating cash flow present is a conservative fallback signature for which
        # FCF capitalization is unsuitable.
        if latest_revenue is None and latest_ocf is not None:
            _financial_sic_forced_unsuitable = True
            dq.append("financial_structure_suspected_no_sic:revenue_absent_ocf_present")
        else:
            dq.append("sic_unavailable_cannot_confirm_nonfinancial")

    ebit_series = fin.get("ebit", [])
    da_series = fin.get("dep_amort", [])
    ocf_series = fin.get("ocf", [])
    capex_series = fin.get("capex", [])
    rev_series = fin.get("revenue", [])
    shares_series = fin.get("shares_outstanding", [])

    # Shares: use latest from series
    latest_shares = shares_series[-1]["val"] if shares_series else None

    # --- Data quality flags ---
    if latest_cash is None:
        dq.append("cash_unavailable")
    if latest_debt is None:
        dq.append("debt_unavailable")
    else:
        debt_source = der.get("debt_source", "")
        if "proxy" in debt_source:
            dq.append(f"debt_is_total_liabilities_proxy:{debt_source}")
    if latest_da is None:
        dq.append("dep_amort_unavailable")
    if latest_capex is None:
        dq.append("capex_unavailable_fcf_unqualified")
    if fcf_is_proxy:
        dq.append("fcf_equals_ocf_proxy_no_capex")
    if latest_ni is None or latest_ni <= 0:
        dq.append("net_income_nonpositive_pe_null")
    if latest_shares is None:
        dq.append("shares_unavailable_per_share_null")

    # --- EV computation ---
    # EV = market_cap + total_debt - cash
    # Missing or conflicting contractual debt cannot support an EV estimate.
    ev: float | None = None
    ev_note: str | None = None
    if debt_uncertain:
        ev_note = "debt_evidence_uncertain"
    elif latest_cash is not None:
        ev = market_cap + latest_debt - latest_cash
    else:
        ev = market_cap + latest_debt
        ev_note = "cash_excluded"
        dq.append("ev_excludes_cash")

    if ev is not None and ev <= 0:
        dq.append("ev_nonpositive_multiples_null")

    # --- Multiples ---
    ev_sales: float | None = None
    if ev and ev > 0 and latest_revenue and latest_revenue > 0:
        ev_sales = round(ev / latest_revenue, 2)

    # Build EBITDA series for normalization (full pairs only; skips partial entries)
    ebitda_series, n_ebitda_partial = _build_ebitda_series(ebit_series, da_series)
    ebitda_periods = paired_annual_sum_evidence(ebit_series, da_series)
    latest_ebitda_evidence = ebitda_periods[-1] if ebitda_periods else None
    if n_ebitda_partial > 0:
        dq.append(f"ebitda_series_partial_entries:{n_ebitda_partial}")

    # Reconstruct current EBITDA from the same qualified annual operands as the producer.
    # A derived scalar cannot replace a missing or incompatible latest period.
    ebit_source = der.get("ebit_source")
    latest_ebitda = latest_ebitda_evidence["val"] if latest_ebitda_evidence else None
    if der.get("latest_ebitda") is not None and der["latest_ebitda"] != latest_ebitda:
        dq.append("derived_latest_ebitda_not_supported_by_matching_period")
    if der.get("latest_ebitda") is None and latest_ebitda is not None and ebit_source:
        dq.append(f"ebitda_recovered_via_ebit_cascade:ebit_source={ebit_source}")

    ev_ebitda: float | None = None
    if ev and ev > 0 and latest_ebitda and latest_ebitda > 0:
        ev_ebitda = round(ev / latest_ebitda, 2)
    elif ev and ev > 0 and latest_ebitda:
        dq.append("ebitda_nonpositive_ev_ebitda_null")

    pe: float | None = None
    if latest_ni and latest_ni > 0:
        pe = round(market_cap / latest_ni, 2)

    paired_fcf = paired_cash_flow_evidence(ocf_series, capex_series, bool(fcf_is_proxy))
    latest_fcf_evidence = paired_fcf[-1] if paired_fcf else None
    latest_fcf = latest_fcf_evidence["val"] if latest_fcf_evidence else None
    if der.get("latest_fcf") is not None and der["latest_fcf"] != latest_fcf:
        dq.append("derived_latest_fcf_not_supported_by_matching_period")
    fcf_yield: float | None = None
    if latest_fcf is not None and market_cap > 0:
        fcf_yield = round(latest_fcf / market_cap, 4)

    # --- Cyclicality ---
    cyclical, cv_val = _is_cyclical(ebitda_series, rev_series, cv_threshold)
    cv_rounded = round(cv_val, 4) if cv_val is not None else None

    # --- Normalized metrics ---
    fcf_periods = []
    if cyclical:
        norm_ebitda = _normalize(ebitda_series, n_years)
        fcf_periods = paired_fcf[-n_years:]
        fcf_proxy_flag = not fcf_periods or any(not period["capex_complete"] for period in fcf_periods)
        norm_fcf = None if fcf_proxy_flag else _normalize(fcf_periods, n_years)
        norm_note = f"cyclical:trailing_{n_years}yr_avg"
        # Flag if the normalization window is shorter than requested
        n_fcf_used = len([v for v in fcf_periods if v.get("val") is not None])
        if n_fcf_used < n_years and norm_fcf is not None:
            dq.append(f"normalized_uses_{n_fcf_used}yr_insufficient")
    else:
        norm_ebitda = latest_ebitda
        fcf_periods = paired_fcf[-1:]
        fcf_proxy_flag = not fcf_periods or not fcf_periods[0]["qualified"]
        norm_fcf = None if fcf_proxy_flag else fcf_periods[0]["val"]
        norm_note = "non_cyclical:latest"

    incomplete_periods = [period["end"] for period in fcf_periods if not period["capex_complete"]]
    if fcf_proxy_flag:
        dq.append("normalized_fcf_capex_incomplete_or_ocf_proxy")
    fcf_normalization = {
        "mode": "trailing_periods" if cyclical else "latest",
        "requested_periods": n_years if cyclical else 1,
        "periods": fcf_periods,
        "incomplete_periods": incomplete_periods,
        "latest_capex_complete": bool(latest_fcf_evidence and latest_fcf_evidence["qualified"]),
        "policy": "no_capitalization_when_selected_capex_evidence_is_incomplete",
    }

    if norm_ebitda is None:
        dq.append("normalized_ebitda_unavailable")
    if norm_fcf is None:
        dq.append("normalized_fcf_unavailable")

    # --- Asset-heavy / leveraged flag ---
    # FCF-cap model is unsuitable when debt/assets > 0.62.
    # This debt ratio is a model-suitability threshold, not evidence of a specific issuer outcome.
    # C2: financial SIC also forces fcf_cap_model_unsuitable regardless of debt/assets ratio.
    fcf_cap_model_unsuitable: bool = False
    if _financial_sic_forced_unsuitable:
        # C2: financial-sector companies (banks, insurers, BDCs, REITs, holding cos)
        #, FCF capitalization is structurally invalid for these business models.
        fcf_cap_model_unsuitable = True
        # note already appended to dq above
    elif latest_debt is not None and latest_assets and latest_assets > 0:
        debt_to_assets = latest_debt / latest_assets
        if debt_to_assets > 0.62:
            fcf_cap_model_unsuitable = True
            dq.append(f"fcf_cap_model_unsuitable:debt_to_assets={debt_to_assets:.4f}>0.62")

    # --- v0.3.2 #8: lessor / leasing-business NAV routing (debt/assets<0.62 hole) ---
    # Leasing-business evidence can require NAV even below the debt/assets threshold.
    # The producer (deepdive_data.py) emits derived.lessor_asset_heavy=True on a leasing/rental
    # business signal (leasing SIC, lease-income concept, or very-high PP&E/lease-fleet ratio with
    # rental revenue). Consume it here: a lessor forces fcf_cap_model_unsuitable=True (-> lease-fleet
    # NAV basis) EVEN WHEN debt/assets<0.62. This NEVER manufactures a BUY, it only routes a name
    # AWAY from the FCF-cap path toward NAV/abstain. This is the consumer half of the #8 contract.
    _lessor_asset_heavy = bool(der.get("lessor_asset_heavy", False))
    if _lessor_asset_heavy and not fcf_cap_model_unsuitable:
        fcf_cap_model_unsuitable = True  # route to lease-fleet NAV instead of trough-cycle FCF
        _lessor_detail = der.get("lessor_asset_heavy_detail", "")
        dq.append(f"lessor_asset_heavy_fcf_unsuitable_route_nav:{_lessor_detail}")

    # --- C1 data-quality blocks on valuation routing ---
    # Unreliable debt or entity evidence blocks FCF routing and BUY eligibility.
    # A computable NAV band does not clear these guards in the eligibility composite.
    _c1_data_block = (debt_uncertain or der.get("debt_truncation_suspected")
                      or der.get("debt_stale") or der.get("wrong_entity_suspected"))
    if _c1_data_block and not fcf_cap_model_unsuitable:
        fcf_cap_model_unsuitable = True
        dq.append("fcf_cap_blocked_by_c1_data_quality_guard")

    # --- Reverse DCF (Gordon growth approximation) ---
    # OCF - CapEx is post-interest cash flow. Treat it as an equity cash-flow
    # proxy under zero net new borrowing; no excess-cash addback is assumed.
    # Correct denominator: market_cap (equity value), not EV.
    # g = discount_rate - norm_fcf / market_cap
    # Economic validity: if g >= discount_rate, the perpetuity is invalid → null.
    rdcf_growth: float | None = None
    rdcf_null_reason: str | None = None
    rdcf_basis = "equity_fcf_vs_market_cap"
    if market_cap is None or market_cap <= 0:
        rdcf_null_reason = "market_cap_nonpositive"
    elif norm_fcf is None:
        rdcf_null_reason = "normalized_fcf_unavailable"
    elif norm_fcf <= 0:
        rdcf_null_reason = "normalized_fcf_nonpositive"
    else:
        g = discount_rate - (norm_fcf / market_cap)
        if g >= discount_rate:
            # Economically invalid: Gordon denominator (discount_rate - g) <= 0
            rdcf_null_reason = "implied_growth_ge_discount_rate"
        else:
            rdcf_growth = round(g, 4)
            if rdcf_growth < -0.20:
                dq.append("rdcf_implied_growth_very_negative:market_pricing_in_decline")
            elif rdcf_growth > 0.20:
                dq.append("rdcf_implied_growth_very_high:market_pricing_in_high_growth")

    # --- Intrinsic value band (FCF capitalization) ---
    # Capitalize the same post-interest cash flow directly to equity value.
    # A second net-debt subtraction would mix enterprise and equity bases.
    # cap_rate_high (0.12) → low equity estimate (conservative end)
    # cap_rate_low (0.09) → high equity estimate (optimistic end)
    iv_band: dict | None = None
    if norm_fcf is not None and norm_fcf > 0:
        eq_low = norm_fcf / cap_high
        eq_high = norm_fcf / cap_low
        if latest_shares and latest_shares > 0:
            ps_low = round(eq_low / latest_shares, 2)
            ps_high = round(eq_high / latest_shares, 2)
        else:
            ps_low = None
            ps_high = None
        iv_band = {
            "equity_low": round(eq_low),
            "equity_high": round(eq_high),
            "per_share_low": ps_low,
            "per_share_high": ps_high,
            "cap_rate_used_low": cap_low,
            "cap_rate_used_high": cap_high,
            "basis": "post_interest_equity_cash_flow",
            "note": "equity_cash_flow_cap;zero_net_new_borrowing;no_excess_cash_addback",
        }
    else:
        iv_band = None
        if norm_fcf is None:
            dq.append("intrinsic_band_null:normalized_fcf_unavailable")
        else:
            dq.append("intrinsic_band_null:normalized_fcf_nonpositive")

    # --- NAV path (for asset-heavy / fcf_cap_model_unsuitable companies) ---
    # tangible_equity = latest_equity - goodwill - intangibles  (floor 0)
    nav_band: dict | None = None
    nav_mos: float | None = None
    nav_tangible_equity: float | None = None
    nav_equity_proxy_used: bool = False

    if fcf_cap_model_unsuitable and latest_equity is not None:
        goodwill = latest_goodwill if latest_goodwill is not None else 0.0
        intangibles = latest_intangibles if latest_intangibles is not None else 0.0
        tangible_eq = max(0.0, latest_equity - goodwill - intangibles)
        nav_tangible_equity = tangible_eq
        if latest_goodwill is None or latest_intangibles is None:
            nav_equity_proxy_used = True
            dq.append("nav_goodwill_or_intangibles_unavailable:tangible_equity_uses_book_equity_proxy")
        nav_band = {
            "band_low": round(tangible_eq * 0.80),
            "band_high": round(tangible_eq * 1.05),
            "tangible_equity_used": round(tangible_eq),
            "goodwill_deducted": round(goodwill),
            "intangibles_deducted": round(intangibles),
            "proxy_used": nav_equity_proxy_used,
        }
        if market_cap > 0:
            nav_mos = round((nav_band["band_low"] - market_cap) / market_cap, 4)

    # --- Margin of safety routing (three-way mos_basis decision) ---
    # fcf_cap: normal companies → use FCF intrinsic band MoS
    # nav:     asset-heavy (fcf_cap_model_unsuitable) AND equity is available → NAV MoS
    # abstain: asset-heavy AND equity unavailable → no MoS; report EV multiples only
    mos: float | None = None
    mos_null_reason: str | None = None
    mos_basis: str

    if fcf_cap_model_unsuitable:
        if nav_band is not None:
            mos_basis = "nav"
            mos_null_reason = "fcf_cap_model_unsuitable_use_nav"
        else:
            mos_basis = "abstain"
            mos_null_reason = "fcf_cap_model_unsuitable_nav_also_unavailable"
        # FCF MoS is intentionally null for asset-heavy companies
    else:
        mos_basis = "fcf_cap"
        if iv_band is not None and market_cap > 0:
            mos = round((iv_band["equity_low"] - market_cap) / market_cap, 4)
        elif iv_band is None:
            mos_null_reason = "intrinsic_band_unavailable"

    # --- G1: extreme MoS defense-in-depth ---
    # |MoS| > 100% (or nav equivalent) is almost always a data/model pathology, never
    # confirmed real cheapness. Force downgrade BUY→WATCH and add flag.
    # This is a backstop: even if C1/C2 miss a case, a >100% MoS never auto-BUYs.
    _extreme_mos_review_required = False
    _active_mos = mos if mos_basis == "fcf_cap" else nav_mos
    if _active_mos is not None and abs(_active_mos) > 1.0:
        _extreme_mos_review_required = True
        dq.append(f"extreme_mos_review_required:mos={_active_mos*100:.1f}%_exceeds_100pct")

    # --- G2: large-cap ceiling, mktcap > watch_band_max must NOT receive BUY ---
    # For a small-cap tool, anything in the large-cap band is out of scope.
    # watch_band_max from config (default 2B).
    _WATCH_BAND_MAX = int(cfg.get("watch_band_max", 2_000_000_000))
    _large_cap_out_of_scope = market_cap > _WATCH_BAND_MAX
    if _large_cap_out_of_scope:
        dq.append(f"out_of_scope_large_cap:market_cap={market_cap/1e9:.1f}B>watch_band_max={_WATCH_BAND_MAX/1e9:.1f}B")

    # --- I1: FCF sustainability guard ---
    # Downgrade BUY→WATCH when FCF quality is suspect:
    #   (i)  reverse_dcf_implied_growth < -0.15, market prices in steep decline while
    #        our MoS says cheap = contradiction → unsupported terminal value
    #   (ii) selected CapEx evidence is missing or marked as an OCF proxy
    #   (iii) lumpy OCF (CV high but not fully captured by cyclical flag)
    #
    # This guard applies to the FCF basis; NAV has separate evidence requirements.
    _fcf_sustainability_uncertain = bool(fcf_proxy_flag and mos_basis == "fcf_cap")
    if _fcf_sustainability_uncertain:
        dq.append("fcf_sustainability_uncertain:ocf_proxy_capex_unknown_or_incomplete_history")
    if mos_basis == "fcf_cap" and mos is not None:
        # (i) reverse-DCF growth strongly negative while MoS positive → contradiction
        if rdcf_growth is not None and rdcf_growth < -0.15:
            _fcf_sustainability_uncertain = True
            dq.append(f"fcf_sustainability_uncertain:rdcf_growth={rdcf_growth:.3f}<-0.15")

    # --- P10: lumpy-OCF normalization guard (specced in I1, never coded until now) ---
    # A single peak year can inflate trailing normalized FCF. Flag-and-downgrade;
    # never silently delete the observation from the normalization window.
    # A year is "lumpy" when its OCF > 2x the median of the OTHER years in the window.
    # This overlaps P6 contamination; we read the producer's contamination_ratio as the
    # corroborating signal (latest below its own 5yr-avg base => over-normalized peak).
    _lumpy_ocf_normalization_suspect = False
    if cyclical and mos_basis == "fcf_cap":
        _ocf_window_vals = [v["val"] for v in ocf_series if v.get("val") is not None][-n_years:]
        if len(_ocf_window_vals) >= 3:
            for i, _yv in enumerate(_ocf_window_vals):
                _others = _ocf_window_vals[:i] + _ocf_window_vals[i + 1:]
                _others_pos = [o for o in _others if o is not None]
                if not _others_pos:
                    continue
                _med = statistics.median(_others_pos)
                if _med > 0 and _yv > 2.0 * _med:
                    _lumpy_ocf_normalization_suspect = True
                    dq.append(
                        f"lumpy_ocf_normalization_suspect:peak_year_ocf={_yv/1e6:.1f}M"
                        f">2x_median_of_others={_med/1e6:.1f}M"
                    )
                    break
    # Corroborate with the producer's contamination_ratio (latest base / 5yr-avg < 1.0
    # means the normalization base is averaging in a peak the latest year no longer earns).
    _contamination_ratio = der.get("contamination_ratio")
    if (
        _lumpy_ocf_normalization_suspect
        and _contamination_ratio is not None
        and _contamination_ratio < 1.0
    ):
        dq.append(f"lumpy_ocf_corroborated_by_contamination:ratio={_contamination_ratio}")

    # --- P6: fundamental-trajectory veto (downgrade-only) ---
    # Read the producer's deterministic fundamental_decline_flag (rev_slope_sign<0 AND
    # contamination_ratio<1.0 AND latest_below_avg). When set, a static-MoS BUY must be
    # downgraded BUY->WATCH. This is downgrade-only: it NEVER manufactures a BUY and never
    # upgrades. It is the mechanical carve-out to rubric:222 (decline magnitude +
    # latest-below-own-average + contamination<1), NOT a qualitative forward judgment.
    _fundamental_decline_flag = bool(der.get("fundamental_decline_flag", False))
    if _fundamental_decline_flag:
        dq.append(
            f"fundamental_decline_veto:rev_slope_sign={der.get('rev_slope_sign')},"
            f"contamination_ratio={_contamination_ratio},"
            f"latest_below_avg={der.get('latest_below_avg')}"
        )

    # --- P-A: peak_contamination veto (downgrade-only, independent of rev_slope_sign) ---
    # Read the producer's peak_contamination_flag (contamination_ratio<0.8 AND latest_below_avg
    # AND latest_net_income<0). This is the V-shape value-trap catch (trough->peak->rollover)
    # that fundamental_decline_flag MISSES because that flag is gated on rev_slope_sign<0; on a
    # positive whole-window slope can leave fundamental_decline_flag false. When set,
    # a static-MoS BUY must be downgraded BUY->WATCH, exactly like fundamental_decline_flag.
    # Downgrade-only: it NEVER manufactures a BUY and never upgrades.
    _peak_contamination_flag = bool(der.get("peak_contamination_flag", False))
    if _peak_contamination_flag:
        dq.append(
            f"peak_contamination_veto:contamination_ratio={_contamination_ratio},"
            f"latest_below_avg={der.get('latest_below_avg')},"
            f"latest_net_income={der.get('latest_net_income')}"
        )

    # --- P3: concentration kill-flag (read from producer) ---
    # The producer extracts concentration from filing-footnote context.
    # Its kill flag forces buy_eligible=False.
    _concentration_flag = der.get("concentration_flag")
    if _concentration_flag == "kill":
        dq.append(
            f"concentration_kill:top_customer_pct={der.get('top_customer_pct')},"
            f"top_program_pct={der.get('top_program_pct')}"
        )
    elif _concentration_flag == "watch":
        dq.append(
            f"concentration_watch:top_customer_pct={der.get('top_customer_pct')},"
            f"top_program_pct={der.get('top_program_pct')}"
        )

    # --- P7: second-source sanity band (read from producer derived) ---
    # The producer (deepdive_data.py) cross-checks SEC-XBRL latest debt/revenue/shares against an
    # independent source (yfinance). cross_source_mismatch is True ONLY when a field disagreed
    # grossly (>2.5x), meaning the single SEC value cannot be trusted. This is a DATA-INTEGRITY
    # gate (unlike the flag-only signals): it is FINE for it to gate, because a corrupted input
    # number cannot produce a tradeable MoS. An absent second source leaves cross_source_checked
    # False / mismatch False, so this NEVER blocks a name on missing data. When set, a static-MoS
    # BUY is downgraded BUY->WATCH/abstain.
    _cross_source_checked = bool(der.get("cross_source_checked", False))
    _cross_source_mismatch = bool(der.get("cross_source_mismatch", False))
    _cross_source_detail = der.get("cross_source_detail")
    if _cross_source_mismatch:
        dq.append(f"cross_source_mismatch:{_cross_source_detail}")

    # --- v0.3.1 #1: normalization_masks_current_loss (the degenerate-base / divested-stub catch) ---
    # Positive-base cyclical vetoes exclude negative contamination ratios, yet a positive
    # trailing average can still mask current cash losses.
    # The producer (deepdive_data.py) emits normalization_masks_current_loss = normalized_fcf>0 AND
    # (latest_ocf<0 OR latest_fcf<0 OR contamination_ratio<0). We AND (not flag) into buy_eligible
    # here so the BUY is downgraded BUY->WATCH, exactly like fundamental_decline / peak_contamination.
    # Downgrade-only: it NEVER manufactures a BUY. This is the consumer half of the #1 contract.
    _normalization_masks_current_loss = bool(der.get("normalization_masks_current_loss", False))
    if _normalization_masks_current_loss:
        dq.append(
            f"normalization_masks_current_loss:normalized_fcf_proxy={der.get('normalized_fcf_proxy')},"
            f"latest_ocf={der.get('latest_ocf')},latest_fcf={der.get('latest_fcf')},"
            f"contamination_ratio={_contamination_ratio}"
        )

    # --- P1: compose buy_eligible, the single mechanical boolean the BUY trigger ANDs ---
    # All blocking guards must clear. The rubric also requires active MoS >= 30%,
    # complete evidence, no kill-flags, and no Tier-3-load-bearing evidence, with
    # additional model-fit conditions for NAV. The composite records guard reasons.
    _buy_eligible, _buy_ineligible_reasons = compose_buy_eligibility(
        der,
        extreme_mos_review_required=_extreme_mos_review_required,
        large_cap_out_of_scope=_large_cap_out_of_scope,
        fcf_sustainability_uncertain=_fcf_sustainability_uncertain,
        financial_sic_forced_unsuitable=_financial_sic_forced_unsuitable,
        insurance_concepts_present=_insurance_concepts_present,
        concentration_flag=_concentration_flag,
        fundamental_decline_flag=_fundamental_decline_flag,
        peak_contamination_flag=_peak_contamination_flag,
        cross_source_mismatch=_cross_source_mismatch,
        normalization_masks_current_loss=_normalization_masks_current_loss,
        mos=mos,
        nav_mos=nav_mos,
        mos_basis=mos_basis,
        debt_evidence_uncertain=debt_uncertain,
        lumpy_ocf_normalization_suspect=_lumpy_ocf_normalization_suspect,
    )

    if dd.get("as_of") is not None:
        mos_basis, mos, nav_mos = "abstain", None, None
        mos_null_reason = "historical_eligibility_contract_incomplete"
        _buy_eligible = False
        _buy_ineligible_reasons.append(mos_null_reason)
        dq.append(mos_null_reason)

    # --- Assemble output ---
    block = {
        "ticker": dd.get("ticker"),
        "computed_at": today(),
        "market_cap": market_cap,
        "market_cap_source": "see_caller",  # filled in by caller
        # EV
        "ev": round(ev) if ev is not None else None,
        "ev_note": ev_note,
        "debt_evidence_status": debt_status,
        "debt_evidence_uncertain": debt_uncertain,
        "debt_evidence_detail": debt_detail,
        # Multiples
        "ev_sales": ev_sales,
        "ev_ebitda": ev_ebitda,
        "pe": pe,
        "fcf_yield": fcf_yield,
        # Cyclicality
        "cyclical": cyclical,
        "cv_ebitda": cv_rounded,
        "cyclical_cv_threshold_used": cv_threshold,
        # Normalized metrics
        "normalized_ebitda": round(norm_ebitda) if norm_ebitda is not None else None,
        "normalized_fcf": round(norm_fcf) if norm_fcf is not None else None,
        "normalization_note": norm_note,
        "normalized_fcf_is_proxy": fcf_proxy_flag,
        "fcf_normalization": fcf_normalization,
        "latest_fcf": latest_fcf,
        "latest_fcf_evidence": latest_fcf_evidence,
        "latest_ebitda_evidence": latest_ebitda_evidence,
        "ebitda_periods": ebitda_periods,
        # Reverse DCF (equity-FCF basis, denominator is market_cap, not EV)
        "rdcf_basis": rdcf_basis,
        "reverse_dcf_implied_growth": rdcf_growth,
        "reverse_dcf_null_reason": rdcf_null_reason,
        # Asset-heavy / model suitability
        "fcf_cap_model_unsuitable": fcf_cap_model_unsuitable,
        # v0.3.2 #8: lessor_asset_heavy (read from producer derived). When True, this name was
        # routed to NAV/abstain (fcf_cap_model_unsuitable forced True) EVEN at debt/assets<0.62 ,
        # making the lease-fleet NAV basis explicit in reports.
        "lessor_asset_heavy": _lessor_asset_heavy,
        "lessor_asset_heavy_detail": der.get("lessor_asset_heavy_detail") if _lessor_asset_heavy else None,
        "latest_assets": round(latest_assets) if latest_assets is not None else None,
        "latest_total_debt_for_nav": round(latest_debt) if latest_debt is not None else None,
        # FCF intrinsic value band (meaningful only when mos_basis == "fcf_cap")
        "intrinsic_value_band": iv_band,
        # NAV band (meaningful only when mos_basis == "nav")
        "nav_intrinsic_band": nav_band,
        "nav_tangible_equity": round(nav_tangible_equity) if nav_tangible_equity is not None else None,
        # Margin of safety routing
        "mos_basis": mos_basis,
        "margin_of_safety_pct": mos,
        "mos_null_reason": mos_null_reason,
        "nav_margin_of_safety_pct": nav_mos,
        # G1: extreme MoS defense-in-depth
        "extreme_mos_review_required": _extreme_mos_review_required,
        # G2: large-cap ceiling
        "large_cap_out_of_scope": _large_cap_out_of_scope,
        # I1: FCF sustainability guard
        "fcf_sustainability_uncertain": _fcf_sustainability_uncertain,
        # P10: lumpy-OCF normalization guard
        "lumpy_ocf_normalization_suspect": _lumpy_ocf_normalization_suspect,
        # P6: fundamental-trajectory veto (read from producer derived)
        "fundamental_decline_flag": _fundamental_decline_flag,
        "contamination_ratio": _contamination_ratio,
        # P-A: V-shape value-trap veto (read from producer derived; independent of slope)
        "peak_contamination_flag": _peak_contamination_flag,
        # v0.3.1 #1: degenerate-base / divested-stub catch (read from producer derived). When True,
        # the trailing-avg normalized FCF>0 is masking current cash burn -> buy_eligible=False
        # (downgrade BUY->WATCH), covering current losses outside the cyclical vetoes.
        "normalization_masks_current_loss": _normalization_masks_current_loss,
        # P7: second-source sanity band (read from producer derived). cross_source_mismatch is a
        # DATA-INTEGRITY gate on buy_eligible (>2.5x SEC-vs-yfinance disagreement); checked=False
        # means no second source was available (never blocks).
        "cross_source_checked": _cross_source_checked,
        "cross_source_mismatch": _cross_source_mismatch,
        "cross_source_detail": _cross_source_detail,
        # P-B: early/pre-revenue resource label (data-quality only; does NOT flip buy_eligible)
        "low_revenue_loss_ratio": bool(der.get("low_revenue_loss_ratio", False)),
        # A4: the >20x EXTREME tier (gates buy_eligible with the accurate label)
        "low_revenue_loss_ratio_extreme": bool(der.get("low_revenue_loss_ratio_extreme", False)),
        # A3: insurance underwriter / insurance-subsidiary holdco (routes nav/abstain, gates BUY)
        "insurance_concepts_present": _insurance_concepts_present,
        # A2: text concentration flag True but XBRL magnitude null (advisory; does NOT gate)
        "concentration_unquantified": bool(der.get("concentration_unquantified", False)),
        # P-G: filing-form provenance (10-K/20-F/40-F) for the trust banner
        "form_used": der.get("form_used"),
        # v0.3.2 #11: foreign_filer_unvaluable (read from producer derived), a 20-F/40-F filer whose
        # financials stayed empty even after the us-gaap+ifrs-full cascade. Explicit abstain label
        # for the report/banner so it is NOT a silent intrinsic_band_unavailable null.
        "foreign_filer_unvaluable": _foreign_filer_unvaluable,
        "foreign_filer_unvaluable_detail": der.get("foreign_filer_unvaluable_detail") if _foreign_filer_unvaluable else None,
        # P3: concentration kill/watch (read from producer derived)
        "concentration_flag": _concentration_flag,
        "top_customer_pct": der.get("top_customer_pct"),
        "top_program_pct": der.get("top_program_pct"),
        # P9: EBIT cascade source actually used
        "ebit_source": ebit_source,
        # P1: composed mechanical BUY-eligibility (BUY trigger ANDs this in)
        "buy_eligible": _buy_eligible,
        "buy_ineligible_reasons": _buy_ineligible_reasons,
        # C2: financial SIC flag
        "financial_sic_fcf_unsuitable": _financial_sic_forced_unsuitable,
        "sic_used": sic_code if sic_code else None,
        # Transparency
        "assumptions": {
            "discount_rate": discount_rate,
            "discount_rate_basis": "equity_required_return",
            "discount_rate_config_key": discount_rate_key,
            "legacy_wacc_is_equity_rate_alias": discount_rate_key == "wacc",
            "cash_flow_basis": "post_interest_ocf_less_capex",
            "net_new_borrowing_assumed": 0,
            "excess_cash_added": False,
            "cap_rate_low": cap_low,
            "cap_rate_high": cap_high,
            "normalize_years": n_years,
            "cyclical_cv_threshold": cv_threshold,
        },
        "data_quality": dq,
    }
    return block


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="valuation.py — Phase 2 deterministic valuation layer. "
                    "Reads a deepdive JSON and outputs a valuation block."
    )
    ap.add_argument("--json", default="", help="Path to deepdive_<ticker>_<date>.json")
    ap.add_argument("--ticker", default="", help="Ticker symbol (used for market cap lookup)")
    ap.add_argument("--mktcap", type=int, default=0, help="Market cap override in dollars (optional)")
    diagnostic = ap.add_mutually_exclusive_group()
    diagnostic.add_argument("--selftest", action="store_true", help="Run synthetic valuation assertions")
    diagnostic.add_argument("--live-diagnostic", action="store_true",
                            help="Explicit live issuer diagnostic; may fetch data and write private REPORTS")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return
    if args.live_diagnostic:
        _live_diagnostic()
        return

    if not args.json:
        ap.error("--json is required (path to deepdive JSON)")
    if not args.ticker:
        ap.error("--ticker is required")

    ticker = args.ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,19}", ticker):
        ap.error("--ticker must be a plain ticker symbol")
    # --json is also a write destination because the CLI merges the result into it.
    json_path = prove_output_path(Path(args.json))
    if not json_path.is_file():
        print(f"ERROR: file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    dd = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(dd, dict) or not isinstance(dd.get("ticker"), str):
        ap.error("deepdive JSON must be an object with a ticker identity")
    if dd["ticker"].strip().upper() != ticker:
        ap.error("--ticker does not match the deepdive JSON identity")
    out_path = prove_output_path(reports_dir() / f"valuation_{ticker}_{today()}.json")
    init_edgar()
    mktcap_override = args.mktcap if args.mktcap > 0 else None
    market_cap, mktcap_source = _get_market_cap(ticker, mktcap_override)

    if market_cap is None:
        print(f"ERROR: cannot get market cap for {ticker}: {mktcap_source}", file=sys.stderr)
        sys.exit(1)

    cfg = _val_cfg()
    block = compute_valuation(dd, market_cap, cfg)
    block["market_cap_source"] = mktcap_source

    # Write standalone valuation JSON
    json_path = prove_output_path(json_path)
    out_path = prepare_output(out_path)
    out_path.write_text(json.dumps(block, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Valuation written: {out_path}")

    # Also merge into the deepdive JSON
    dd["valuation"] = block
    json_path.write_text(json.dumps(dd, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Deepdive JSON updated with valuation block: {json_path}")

    # Print summary
    _print_valuation_summary(block)


def _print_valuation_summary(block: dict) -> None:
    """Print a human-readable summary of the valuation block."""
    def money(value, reason):
        return f"${value/1e6:.0f}M" if value is not None else f"null ({reason})"

    t = block.get("ticker", "?")
    mc = block.get("market_cap")
    ev = block.get("ev")
    mos_basis = block.get("mos_basis", "?")
    print(f"\n=== {t} Valuation Summary ===")
    print(f"  Market Cap:      {money(mc, 'market_cap_unavailable')}")
    print(f"  EV:              {money(ev, block.get('ev_note') or 'ev_unavailable')}" +
          (f"  [{block['ev_note']}]" if ev is not None and block.get("ev_note") else ""))
    print(f"  EV/Sales:        {block.get('ev_sales')}")
    print(f"  EV/EBITDA:       {block.get('ev_ebitda')}")
    print(f"  P/E:             {block.get('pe')}")
    print(f"  FCF Yield:       {block.get('fcf_yield')}")
    print(f"  Cyclical:        {block.get('cyclical')} (CV={block.get('cv_ebitda')})")
    print(f"  Norm. EBITDA:    {money(block.get('normalized_ebitda'), 'normalized_ebitda_unavailable')}  [{block.get('normalization_note')}]")
    print(f"  Norm. FCF:       {money(block.get('normalized_fcf'), 'normalized_fcf_unavailable')}")
    rdcf = block.get("reverse_dcf_implied_growth")
    rdcf_reason = block.get("reverse_dcf_null_reason")
    rdcf_basis = block.get("rdcf_basis", "equity_fcf_vs_market_cap")
    print(f"  Reverse DCF g:   {rdcf if rdcf is not None else f'null ({rdcf_reason})'} [basis={rdcf_basis}]")
    print(f"  FCF Model Unsuitable: {block.get('fcf_cap_model_unsuitable')}")
    print(f"  MoS Basis:       {mos_basis}")
    iv = block.get("intrinsic_value_band")
    if iv:
        print(f"  FCF Intrinsic:   ${iv['equity_low']/1e6:.0f}M - ${iv['equity_high']/1e6:.0f}M equity")
        if iv.get("per_share_low") is not None:
            print(f"                   ${iv['per_share_low']:.2f} - ${iv['per_share_high']:.2f} per share")
    nav = block.get("nav_intrinsic_band")
    if nav:
        print(f"  NAV Band:        ${nav['band_low']/1e6:.0f}M - ${nav['band_high']/1e6:.0f}M equity")
        print(f"  Tangible Equity: ${(block.get('nav_tangible_equity') or 0)/1e6:.0f}M")
    mos = block.get("margin_of_safety_pct")
    nav_mos = block.get("nav_margin_of_safety_pct")
    mos_reason = block.get("mos_null_reason")
    if mos_basis == "fcf_cap":
        print(f"  MoS (FCF):       {f'{mos*100:.1f}%' if mos is not None else f'null ({mos_reason})'}")
    elif mos_basis == "nav":
        print(f"  MoS (NAV):       {f'{nav_mos*100:.1f}%' if nav_mos is not None else 'null'}")
        print(f"  FCF MoS:         null ({mos_reason})")
    else:  # abstain
        print(f"  MoS:             abstain ({mos_reason})")
    print(f"  buy_eligible:    {block.get('buy_eligible')}"
          + (f"  reasons={block.get('buy_ineligible_reasons')}" if block.get("buy_ineligible_reasons") else ""))
    print(f"  Concentration:   {block.get('concentration_flag')} "
          f"(cust={block.get('top_customer_pct')} prog={block.get('top_program_pct')})")
    print(f"  Decline flag:    {block.get('fundamental_decline_flag')} "
          f"(contamination={block.get('contamination_ratio')})  Lumpy-OCF: {block.get('lumpy_ocf_normalization_suspect')}")
    print(f"  Peak-contam flag:{block.get('peak_contamination_flag')}  "
          f"Low-rev-loss: {block.get('low_revenue_loss_ratio')}  Form: {block.get('form_used')}")
    print(f"  EBIT source:     {block.get('ebit_source')}")
    dq = block.get("data_quality", [])
    if dq:
        print(f"  Data Quality:    {dq}")
    print()


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------
def _live_diagnostic():
    """Explicit live diagnostic: may fetch issuer data and write private REPORTS."""
    init_edgar()
    cfg = _val_cfg()

    def _get_or_pull(ticker: str, cik: str) -> dict:
        """Get latest deepdive JSON for ticker, pulling fresh if needed.

        Requires Phase 2 fields (ebit, equity series) AND goodwill/intangibles in derived
        (added in Phase 2 fix round). If the cached file is missing any of these, pulls fresh.
        """
        candidates = sorted(REPORTS.glob(f"deepdive_{ticker}_*.json"), reverse=True)
        if candidates:
            dd = json.loads(candidates[0].read_text(encoding="utf-8"))
            # Require Phase 2 fields AND goodwill/intangibles keys in derived
            der = dd.get("derived", {})
            has_phase2 = dd.get("financials", {}).get("ebit") is not None
            has_goodwill_key = "latest_goodwill" in der
            if has_phase2 and has_goodwill_key:
                print(f"  Using cached deepdive: {candidates[0].name}")
                return dd
        # Pull fresh
        print(f"  Pulling fresh deepdive for {ticker}...", file=sys.stderr)
        import deepdive_data as dd_mod
        data = dd_mod.pull(ticker, cik)
        out = REPORTS / f"deepdive_{ticker}_{today()}.json"
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return data

    def _assert_valuation(ticker: str, cik: str, dd: dict) -> dict:
        """Compute and assert the valuation block for a ticker."""
        market_cap, mktcap_source = _get_market_cap(ticker)
        if market_cap is None:
            print(f"  WARNING: cannot get market cap for {ticker}: {mktcap_source}", file=sys.stderr)
            market_cap = 1  # allow test to proceed with degenerate value
        block = compute_valuation(dd, market_cap, cfg)
        block["market_cap_source"] = mktcap_source

        # Core assertions: EV must be positive
        ev = block.get("ev")
        assert ev is not None and ev > 0, f"{ticker}: ev must be >0, got {ev}"

        ev_ebitda = block.get("ev_ebitda")
        assert ev_ebitda is None or ev_ebitda > 0, (
            f"{ticker}: ev_ebitda must be positive or null, got {ev_ebitda}"
        )

        # Reverse DCF: must have a value OR a documented null_reason
        rdcf = block.get("reverse_dcf_implied_growth")
        rdcf_reason = block.get("reverse_dcf_null_reason")
        assert rdcf is not None or rdcf_reason is not None, (
            f"{ticker}: reverse_dcf must be float or have null_reason"
        )
        assert rdcf is None or isinstance(rdcf, float), (
            f"{ticker}: reverse_dcf_implied_growth must be float or None, got {type(rdcf)}"
        )

        # mos_basis must be one of the three valid values
        mos_basis = block.get("mos_basis")
        assert mos_basis in ("fcf_cap", "nav", "abstain"), (
            f"{ticker}: mos_basis must be fcf_cap/nav/abstain, got {mos_basis!r}"
        )

        # FCF intrinsic band: low < high if present
        iv = block.get("intrinsic_value_band")
        if iv is not None:
            assert iv["equity_low"] < iv["equity_high"], (
                f"{ticker}: intrinsic band low must be < high: {iv['equity_low']} vs {iv['equity_high']}"
            )

        # FCF MoS: must be float when mos_basis="fcf_cap" AND iv_band is not None
        mos = block.get("margin_of_safety_pct")
        if mos_basis == "fcf_cap" and iv is not None:
            assert mos is not None and isinstance(mos, float), (
                f"{ticker}: margin_of_safety_pct must be float when fcf_cap + iv_band, got {mos}"
            )

        return block

    # --- WLFC ---
    print("  Testing WLFC (CIK 1018164)...")
    dd_wlfc = _get_or_pull("WLFC", "1018164")
    block_wlfc = _assert_valuation("WLFC", "1018164", dd_wlfc)

    # The live lessor case must establish model suitability from its current inputs.
    assert block_wlfc.get("fcf_cap_model_unsuitable") is True, (
        f"WLFC: expected fcf_cap_model_unsuitable=True from current evidence, got "
        f"{block_wlfc.get('fcf_cap_model_unsuitable')}"
    )
    assert block_wlfc.get("mos_basis") in ("nav", "abstain"), (
        f"WLFC: expected mos_basis nav or abstain, got {block_wlfc.get('mos_basis')!r}"
    )
    assert block_wlfc.get("margin_of_safety_pct") is None, (
        f"WLFC: FCF margin_of_safety_pct must be null for asset-heavy company, "
        f"got {block_wlfc.get('margin_of_safety_pct')}"
    )
    print(f"  WLFC assertions PASS")
    print("\n--- WLFC Full Valuation Block ---")
    print(json.dumps(block_wlfc, indent=2))
    print("--- End WLFC Valuation Block ---\n")
    _print_valuation_summary(block_wlfc)

    # Write WLFC valuation to disk
    out_wlfc = REPORTS / f"valuation_WLFC_{today()}.json"
    out_wlfc.write_text(json.dumps(block_wlfc, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- LNN ---
    print("  Testing LNN (CIK 836157)...")
    dd_lnn = _get_or_pull("LNN", "836157")
    block_lnn = _assert_valuation("LNN", "836157", dd_lnn)

    # LNN-specific: should be FCF-cap basis (not an aircraft lessor / finance company)
    assert block_lnn.get("mos_basis") == "fcf_cap", (
        f"LNN: expected mos_basis='fcf_cap', got {block_lnn.get('mos_basis')!r}"
    )
    print(f"  LNN assertions PASS")
    print("\n--- LNN Full Valuation Block ---")
    print(json.dumps(block_lnn, indent=2))
    print("--- End LNN Valuation Block ---\n")
    _print_valuation_summary(block_lnn)

    # Write LNN valuation to disk
    out_lnn = REPORTS / f"valuation_LNN_{today()}.json"
    out_lnn.write_text(json.dumps(block_lnn, indent=2, ensure_ascii=False), encoding="utf-8")


def _selftest():
    """Run synthetic valuation assertions without live acquisition or report writes."""
    from make_fixtures import source26_debt_fixture, source28_annual_inputs, source32_legacy_scenarios
    _legacy = source32_legacy_scenarios()
    cfg = dict(_VALUATION_DEFAULTS)
    # --- C2: financial-SIC exclusion unit test ---
    # Simulate a BDC (SIC 6726) with positive FCF, must route to nav/abstain, NOT fcf_cap
    _dd_financial = _legacy['valuation_financial']
    _block_fin = compute_valuation(source26_debt_fixture(_dd_financial), 300_000_000, cfg)
    assert _block_fin.get("financial_sic_fcf_unsuitable") is True, (
        f"C2: financial_sic_fcf_unsuitable must be True for SIC 6726, got {_block_fin.get('financial_sic_fcf_unsuitable')}"
    )
    assert _block_fin.get("mos_basis") in ("nav", "abstain"), (
        f"C2: financial SIC company must route to nav/abstain, got {_block_fin.get('mos_basis')!r}"
    )
    assert _block_fin.get("fcf_cap_model_unsuitable") is True, (
        f"C2: fcf_cap_model_unsuitable must be True for financial SIC"
    )
    print("  C2 financial-SIC exclusion: BDC SIC 6726 routes to nav/abstain  OK")

    # Synthetic absent-SIC financial data must use the BDC fallback.
    _dd_no_sic_bdc = _legacy['valuation_no_sic_bdc']
    _block_no_sic = compute_valuation(source26_debt_fixture(_dd_no_sic_bdc), 280_000_000, cfg)
    assert any("financial_structure_suspected_no_sic" in f for f in _block_no_sic.get("data_quality", [])), (
        f"C2-fallback: BDC with no SIC must flag financial_structure_suspected_no_sic, "
        f"got dq={_block_no_sic.get('data_quality')}"
    )
    assert _block_no_sic.get("mos_basis") in ("nav", "abstain"), (
        f"C2-fallback: SIC-less BDC must route nav/abstain not fcf_cap, got {_block_no_sic.get('mos_basis')!r}"
    )
    print("  C2-fallback: SIC-less BDC (no revenue + OCF) routes to nav/abstain  OK")

    # Synthetic high cash flow exercises an extreme margin-of-safety result.
    _dd_extreme = _legacy['valuation_extreme']
    # Market cap = $1.2M (micro-cap), FCF = $3.6M → MoS would be (3.6M/0.12 - 1.2M) / 1.2M ~ 2400%
    _block_extreme = compute_valuation(source26_debt_fixture(_dd_extreme), 1_200_000, cfg)
    _mos_val = _block_extreme.get("margin_of_safety_pct")
    assert _mos_val is not None, "G1: generated annual cash flows must produce a numeric MoS"
    assert _mos_val > 1.0, "G1: the synthetic extreme case must exceed 100% MoS"
    assert _block_extreme.get("extreme_mos_review_required") is True, (
        f"G1: extreme_mos_review_required must be True for MoS={_mos_val*100:.0f}%"
    )
    assert any("extreme_mos" in str(x) for x in _block_extreme.get("data_quality", [])), (
        "G1: extreme_mos_review_required must appear in data_quality list"
    )
    print(f"  G1 extreme-MoS defense: fires for MoS={_mos_val*100:.0f}%  OK")

    # --- G2: large-cap ceiling unit test ---
    # Use a market_cap > 2B, should set large_cap_out_of_scope=True
    _block_large = compute_valuation(source26_debt_fixture(_dd_extreme), 5_000_000_000, cfg)  # $5B market cap
    assert _block_large.get("large_cap_out_of_scope") is True, (
        f"G2: large_cap_out_of_scope must be True for $5B market cap"
    )
    assert any("out_of_scope_large_cap" in str(x) for x in _block_large.get("data_quality", [])), (
        f"G2: out_of_scope_large_cap must appear in data_quality list"
    )
    print("  G2 large-cap ceiling: fires for $5B market cap  OK")

    # --- I3: data_quality_warn propagation unit test ---
    _dd_with_warn = dict(_dd_extreme)
    _dd_with_warn["derived"] = dict(_dd_extreme["derived"])
    _dd_with_warn["derived"]["data_quality_warn"] = "test_warning:unit_anomaly"
    _block_warn = compute_valuation(source26_debt_fixture(_dd_with_warn), 300_000_000, cfg)
    assert any("test_warning" in str(x) for x in _block_warn.get("data_quality", [])), (
        f"I3: data_quality_warn must propagate into valuation data_quality list"
    )
    print("  I3 data_quality_warn propagation: fires correctly  OK")

    # --- I1: FCF sustainability guard unit test ---
    # Simulate: rdcf_growth would be < -0.15 (market pricing in steep decline)
    # Use tiny market_cap so FCF/mktcap ratio forces g = wacc - FCF/mktcap < -0.15
    # wacc=0.10; FCF=3.6M; mktcap=14M → g = 0.10 - 3.6/14 = 0.10 - 0.257 = -0.157 < -0.15
    _block_i1 = compute_valuation(source26_debt_fixture(_dd_extreme), 14_000_000, cfg)
    rdcf_g = _block_i1.get("reverse_dcf_implied_growth")
    if rdcf_g is not None and rdcf_g < -0.15:
        assert _block_i1.get("fcf_sustainability_uncertain") is True, (
            f"I1: fcf_sustainability_uncertain must be True when rdcf_growth={rdcf_g:.3f}<-0.15"
        )
        assert any("fcf_sustainability_uncertain" in str(x) for x in _block_i1.get("data_quality", [])), (
            f"I1: fcf_sustainability_uncertain must appear in data_quality list"
        )
        print(f"  I1 FCF sustainability guard: fires for rdcf_growth={rdcf_g:.3f}  OK")
    else:
        print(f"  I1 FCF sustainability guard: rdcf_growth={rdcf_g}, skipping assertion (market_cap too high for -0.15 trigger)")

    # --- P2: EVERY OCF-proxy now flags (the dead `elif` is fixed) ---
    # Build a clean, capital-light OCF-proxy name with assets present and assets/rev <= 5
    # (the exact path the old code silently skipped). It MUST now flag uncertain.
    _dd_proxy_light = _legacy['valuation_proxy_light']
    # Market cap chosen so mos_basis=fcf_cap and a numeric MoS exists.
    _block_proxy = compute_valuation(source26_debt_fixture(_dd_proxy_light), 100_000_000, cfg)
    assert _block_proxy.get("mos_basis") == "fcf_cap", (
        f"P2: light proxy fixture must route fcf_cap, got {_block_proxy.get('mos_basis')!r}"
    )
    assert _block_proxy.get("fcf_sustainability_uncertain") is True, (
        "P2: capital-light OCF-proxy (assets/rev<=5) must NOW flag fcf_sustainability_uncertain "
        "(was silently skipped by the dead elif)"
    )
    assert any("fcf_sustainability_uncertain" in str(x) for x in _block_proxy.get("data_quality", [])), (
        "P2: ocf-proxy uncertainty must appear in data_quality list"
    )
    assert "fcf_sustainability_uncertain" in _block_proxy.get("buy_ineligible_reasons", []), (
        "P2: ocf-proxy must propagate into buy_ineligible_reasons"
    )
    assert _block_proxy.get("buy_eligible") is False, (
        "P2: an OCF-proxy name cannot be buy_eligible"
    )
    print("  P2 OCF-proxy: capital-light proxy now flags uncertain + blocks buy_eligible  OK")

    # --- P1+P6: fundamental_decline_flag forces buy_eligible=False ---
    # Clean non-proxy name (would otherwise be eligible) + producer decline flag set.
    _dd_clean_base = _legacy['valuation_clean_base']
    from make_fixtures import source25_annual_cashflows, source25_equity_basis_scenarios
    _dd_clean_base["financials"].update(source25_annual_cashflows())
    source28_annual_inputs(_dd_clean_base)
    # (iv) Clean name keeps buy_eligible=True (small-cap mktcap, non-proxy, no flags).
    _block_clean = compute_valuation(source26_debt_fixture(_dd_clean_base), 120_000_000, cfg)
    assert _block_clean.get("mos_basis") == "fcf_cap", (
        f"P1: clean fixture must route fcf_cap, got {_block_clean.get('mos_basis')!r}"
    )
    assert _block_clean.get("buy_eligible") is True, (
        f"P1: a clean name with zero flags must keep buy_eligible=True, "
        f"reasons={_block_clean.get('buy_ineligible_reasons')}"
    )
    assert _block_clean.get("buy_ineligible_reasons") == [], (
        f"P1: clean name must have empty buy_ineligible_reasons, got {_block_clean.get('buy_ineligible_reasons')}"
    )
    # P9 corollary: ebit_source propagates and ev_ebitda computes.
    assert _block_clean.get("ebit_source") == "OperatingIncomeLoss", (
        f"P9: ebit_source must propagate, got {_block_clean.get('ebit_source')!r}"
    )
    assert _block_clean.get("ev_ebitda") is not None and _block_clean.get("ev_ebitda") > 0, (
        f"P9: ev_ebitda must compute on a clean name, got {_block_clean.get('ev_ebitda')}"
    )
    # P-A/P-B/P-G corollary on the clean name: the new fields propagate with safe defaults and
    # the clean name is NOT blocked by either new flag.
    assert _block_clean.get("peak_contamination_flag") is False, (
        f"P-A: clean name must have peak_contamination_flag=False, got {_block_clean.get('peak_contamination_flag')}"
    )
    assert "peak_contamination_flag" not in _block_clean.get("buy_ineligible_reasons", []), (
        "P-A: clean name must NOT carry peak_contamination_flag in buy_ineligible_reasons"
    )
    assert _block_clean.get("low_revenue_loss_ratio") is False, (
        f"P-B: clean name must have low_revenue_loss_ratio=False, got {_block_clean.get('low_revenue_loss_ratio')}"
    )
    assert _block_clean.get("form_used") == "10-K", (
        f"P-G: form_used must propagate from producer derived, got {_block_clean.get('form_used')!r}"
    )
    print("  P1 clean name: buy_eligible=True, no reasons; P9 ev_ebitda computes  OK")
    print("  P-A/P-B/P-G clean name: peak_flag=False low_rev_loss=False form=10-K propagated  OK")

    # (ii) fundamental_decline_flag => buy_eligible False (downgrade veto)
    _dd_decline = dict(_dd_clean_base)
    _dd_decline["derived"] = dict(_dd_clean_base["derived"])
    _dd_decline["derived"]["fundamental_decline_flag"] = True
    _dd_decline["derived"]["rev_slope_sign"] = -1
    _dd_decline["derived"]["latest_below_avg"] = True
    _dd_decline["derived"]["contamination_ratio"] = _legacy["valuation_overrides"]["decline_ratio"]
    _block_decline = compute_valuation(source26_debt_fixture(_dd_decline), 120_000_000, cfg)
    assert _block_decline.get("fundamental_decline_flag") is True, (
        "P6: producer fundamental_decline_flag must be read into the valuation block"
    )
    assert _block_decline.get("buy_eligible") is False, (
        "P6: fundamental_decline_flag must force buy_eligible=False"
    )
    assert "fundamental_decline_flag" in _block_decline.get("buy_ineligible_reasons", []), (
        "P6: fundamental_decline_flag must appear in buy_ineligible_reasons"
    )
    assert any("fundamental_decline_veto" in str(x) for x in _block_decline.get("data_quality", [])), (
        "P6: fundamental_decline_veto must appear in data_quality list"
    )
    print("  P6 trajectory veto: fundamental_decline_flag forces buy_eligible=False  OK")

    # (iii) concentration kill => buy_eligible False
    _dd_conc = dict(_dd_clean_base)
    _dd_conc["derived"] = dict(_dd_clean_base["derived"])
    _dd_conc["derived"]["concentration_flag"] = "kill"
    _dd_conc["derived"]["top_customer_pct"] = _legacy["valuation_overrides"]["customer_pct"]
    _block_conc = compute_valuation(source26_debt_fixture(_dd_conc), 120_000_000, cfg)
    assert _block_conc.get("concentration_flag") == "kill", (
        "P3: concentration_flag kill must be read into the valuation block"
    )
    assert _block_conc.get("buy_eligible") is False, (
        "P3: concentration kill must force buy_eligible=False"
    )
    assert "concentration_kill" in _block_conc.get("buy_ineligible_reasons", []), (
        "P3: concentration_kill must appear in buy_ineligible_reasons"
    )
    assert any("concentration_kill" in str(x) for x in _block_conc.get("data_quality", [])), (
        "P3: concentration_kill must appear in data_quality list"
    )
    print("  P3 concentration kill: forces buy_eligible=False  OK")

    # The synthetic peak has a rising whole-window slope, contaminated cash flow and a current loss.
    _dd_peak = dict(_dd_clean_base)
    _dd_peak["derived"] = dict(_dd_clean_base["derived"])
    _dd_peak["ticker"] = "TEST_synthetic peak_VSHAPE"
    _dd_peak["derived"]["peak_contamination_flag"] = True
    _dd_peak["derived"]["fundamental_decline_flag"] = False   # V-shape: slope is +1
    _dd_peak["derived"]["rev_slope_sign"] = 1
    _dd_peak["derived"]["latest_below_avg"] = True
    _dd_peak["derived"]["contamination_ratio"] = _legacy["valuation_overrides"]["peak_ratio"]
    _dd_peak["derived"]["latest_net_income"] = _legacy["valuation_overrides"]["peak_income"]
    _block_peak = compute_valuation(source26_debt_fixture(_dd_peak), 120_000_000, cfg)
    assert _block_peak.get("peak_contamination_flag") is True, (
        "P-A: producer peak_contamination_flag must be read into the valuation block"
    )
    assert _block_peak.get("fundamental_decline_flag") is False, (
        "P-A: fundamental_decline_flag must stay False on the V-shape (independent catch)"
    )
    assert _block_peak.get("buy_eligible") is False, (
        "P-A: peak_contamination_flag must force buy_eligible=False (downgrade BUY->WATCH)"
    )
    assert "peak_contamination_flag" in _block_peak.get("buy_ineligible_reasons", []), (
        "P-A: peak_contamination_flag must appear in buy_ineligible_reasons"
    )
    assert "fundamental_decline_flag" not in _block_peak.get("buy_ineligible_reasons", []), (
        "P-A: the V-shape must be blocked by peak_contamination_flag ALONE, not decline_flag"
    )
    assert any("peak_contamination_veto" in str(x) for x in _block_peak.get("data_quality", [])), (
        "P-A: peak_contamination_veto must appear in data_quality list"
    )
    print("  P-A peak_contamination veto: V-shape buy_eligible=False via peak flag ALONE "
          "(decline_flag stays False)  OK")

    # --- P7: cross_source_mismatch is a DATA-INTEGRITY gate on buy_eligible ---
    # The producer cross-checks SEC-XBRL latest debt/revenue/shares against yfinance; a >2.5x
    # disagreement (cross_source_mismatch=True) means the single SEC number cannot be trusted, so a
    # static-MoS BUY must downgrade BUY->WATCH/abstain. Unlike the iter4 flag-only signals, this
    # one is INTENDED to gate (corrupted input cannot back a tradeable MoS).
    # (i) clean baseline (no cross_source_* keys) propagates safe defaults and does NOT block.
    assert _block_clean.get("cross_source_checked") is False, (
        f"P7: clean fixture (no second source) must default cross_source_checked=False, "
        f"got {_block_clean.get('cross_source_checked')}"
    )
    assert _block_clean.get("cross_source_mismatch") is False, (
        f"P7: clean fixture must default cross_source_mismatch=False, "
        f"got {_block_clean.get('cross_source_mismatch')}"
    )
    assert "cross_source_mismatch" not in _block_clean.get("buy_ineligible_reasons", []), (
        "P7: absent second source must NEVER add cross_source_mismatch to buy_ineligible_reasons"
    )
    # (ii) gross mismatch on an otherwise-clean name => buy_eligible False + reason + dq line.
    _dd_xs = dict(_dd_clean_base)
    _dd_xs["derived"] = dict(_dd_clean_base["derived"])
    _dd_xs["ticker"] = "TEST_XSRC_MISMATCH"
    _dd_xs["derived"]["cross_source_checked"] = True
    _dd_xs["derived"]["cross_source_mismatch"] = True
    _dd_xs["derived"]["cross_source_detail"] = (
        "gross disagreement (>2.5x) — total_debt: SEC=11.0M vs yf=4000.0M (ratio 363.6x)"
    )
    _block_xs = compute_valuation(source26_debt_fixture(_dd_xs), 120_000_000, cfg)
    assert _block_xs.get("cross_source_mismatch") is True, (
        "P7: producer cross_source_mismatch must be read into the valuation block"
    )
    assert _block_xs.get("buy_eligible") is False, (
        f"P7: cross_source_mismatch must force buy_eligible=False (DATA-INTEGRITY gate), "
        f"reasons={_block_xs.get('buy_ineligible_reasons')}"
    )
    assert "cross_source_mismatch" in _block_xs.get("buy_ineligible_reasons", []), (
        "P7: cross_source_mismatch must appear in buy_ineligible_reasons"
    )
    assert any("cross_source_mismatch" in str(x) for x in _block_xs.get("data_quality", [])), (
        "P7: cross_source_mismatch detail must appear in data_quality list"
    )
    # (iii) checked=True but mismatch=False (sources agree within 2.5x) must NOT block.
    _dd_xs_ok = dict(_dd_clean_base)
    _dd_xs_ok["derived"] = dict(_dd_clean_base["derived"])
    _dd_xs_ok["ticker"] = "TEST_XSRC_AGREE"
    _dd_xs_ok["derived"]["cross_source_checked"] = True
    _dd_xs_ok["derived"]["cross_source_mismatch"] = False
    _dd_xs_ok["derived"]["cross_source_detail"] = "second source within 2.5x on all comparable fields"
    _block_xs_ok = compute_valuation(source26_debt_fixture(_dd_xs_ok), 120_000_000, cfg)
    assert _block_xs_ok.get("cross_source_checked") is True, (
        "P7: cross_source_checked=True must propagate when a second source was compared"
    )
    assert _block_xs_ok.get("buy_eligible") == _block_clean.get("buy_eligible"), (
        "P7: agreement within 2.5x must NOT change buy_eligible vs the otherwise-identical clean name"
    )
    assert "cross_source_mismatch" not in _block_xs_ok.get("buy_ineligible_reasons", []), (
        "P7: agreement (mismatch=False) must NOT add cross_source_mismatch to buy_ineligible_reasons"
    )
    print("  P7 cross_source gate: >2.5x mismatch blocks buy_eligible; agreement/absent never block  OK")

    # --- P-B: low_revenue_loss_ratio is DATA-QUALITY ONLY and does NOT flip buy_eligible ---
    # A name carrying ONLY low_revenue_loss_ratio (no other blocking flag) must surface the label
    # in data_quality but NOT add it to buy_ineligible_reasons. CRITICAL: it must not relabel a
    # previously-blocked name into buy_eligible=true, and it must not itself create a block.
    _dd_lrl = dict(_dd_clean_base)
    _dd_lrl["derived"] = dict(_dd_clean_base["derived"])
    _dd_lrl["ticker"] = "TEST_LOW_REV_LOSS"
    _dd_lrl["derived"]["low_revenue_loss_ratio"] = True
    _dd_lrl["derived"]["low_revenue_loss_ratio_detail"] = (
        "latest_net_income=-120.0M vs revenue=45.0M (|NI|/rev=2.7x) — early/pre-revenue resource pattern, right entity"
    )
    _block_lrl = compute_valuation(source26_debt_fixture(_dd_lrl), 120_000_000, cfg)
    assert _block_lrl.get("low_revenue_loss_ratio") is True, (
        "P-B: producer low_revenue_loss_ratio must be read into the valuation block"
    )
    assert any("low_revenue_loss_ratio" in str(x) for x in _block_lrl.get("data_quality", [])), (
        "P-B: low_revenue_loss_ratio must surface in the data_quality list"
    )
    assert "low_revenue_loss_ratio" not in _block_lrl.get("buy_ineligible_reasons", []), (
        "P-B: low_revenue_loss_ratio is a label ONLY — must NOT enter buy_ineligible_reasons"
    )
    # The label alone (clean-name base, fcf_cap route) leaves buy_eligible unchanged from clean.
    assert _block_lrl.get("buy_eligible") == _block_clean.get("buy_eligible"), (
        "P-B: low_revenue_loss_ratio must NOT change buy_eligible vs the otherwise-identical clean name"
    )
    print("  P-B low_revenue_loss_ratio: surfaced in data_quality, does NOT flip buy_eligible  OK")

    # P-B regression: the relabel must not flip a PREVIOUSLY-BLOCKED name to buy_eligible=true.
    # Take the synthetic early-revenue resource pattern (null FCF -> MoS null, the historical
    # block) and assert that even WITH low_revenue_loss_ratio set it stays NOT buy_eligible.
    _dd_blocked = _legacy['valuation_blocked']
    _block_blocked = compute_valuation(source26_debt_fixture(_dd_blocked), 200_000_000, cfg)
    # CRITICAL (per data contract): the relabel removed the OLD wrong_entity_suspected misfire
    # from buy_ineligible_reasons, so it must NOT have introduced low_revenue_loss_ratio as a
    # block, and, most importantly, the name must remain a NON-tradeable BUY because its FCF/MoS
    # is null. A tradeable BUY downstream requires mos_basis=="fcf_cap" AND a NUMERIC MoS>=30; a
    # null MoS can never satisfy that. We assert the real block (MoS null) holds regardless of
    # whatever buy_eligible reports, AND that low_revenue_loss_ratio never became a block reason.
    assert "low_revenue_loss_ratio" not in _block_blocked.get("buy_ineligible_reasons", []), (
        "P-B CRITICAL: low_revenue_loss_ratio must NEVER be a buy_ineligible reason"
    )
    assert "wrong_entity_suspected" not in _block_blocked.get("buy_ineligible_reasons", []), (
        "P-B: wrong_entity_suspected must no longer block the early-revenue resource pattern"
    )
    assert _block_blocked.get("margin_of_safety_pct") is None, (
        f"P-B CRITICAL: the early-revenue resource name must keep null FCF MoS (the real, "
        f"unchanged block — a null MoS can never reach the BUY trigger's MoS>=30 gate), "
        f"got {_block_blocked.get('margin_of_safety_pct')}"
    )
    # Belt-and-suspenders: a null MoS cannot constitute a tradeable BUY no matter what
    # buy_eligible says, encode that the BUY trigger (mos_basis==fcf_cap AND MoS>=30) fails.
    _mos_blocked = _block_blocked.get("margin_of_safety_pct")
    _tradeable_buy = (
        _block_blocked.get("buy_eligible") is True
        and _block_blocked.get("mos_basis") == "fcf_cap"
        and _mos_blocked is not None and _mos_blocked >= 0.30
    )
    assert _tradeable_buy is False, (
        f"P-B CRITICAL: the relabel must NOT flip the previously-blocked early-revenue name into "
        f"a tradeable BUY; got buy_eligible={_block_blocked.get('buy_eligible')} "
        f"mos_basis={_block_blocked.get('mos_basis')} mos={_mos_blocked}"
    )
    print("  P-B relabel safety: previously-blocked early-rev name stays NON-tradeable "
          "(MoS null; low_rev_loss never a block)  OK")

    # --- A4: extreme loss-to-revenue ratio (>20x) gates buy_eligible ---
    # The clean fixture is buy_eligible=True on fcf_cap. Setting ONLY the extreme tier (with the
    # advisory label also True, as the producer always co-sets them) must flip buy_eligible=False
    # with the accurate reason-string, replacing the old wrong_entity_suspected co-fire.
    _dd_lrl_ext = dict(_dd_clean_base)
    _dd_lrl_ext["derived"] = dict(_dd_clean_base["derived"])
    _dd_lrl_ext["ticker"] = "TEST_LOW_REV_LOSS_EXTREME"
    _dd_lrl_ext["derived"]["low_revenue_loss_ratio"] = True
    _dd_lrl_ext["derived"]["low_revenue_loss_ratio_extreme"] = True
    _dd_lrl_ext["derived"]["low_revenue_loss_ratio_detail"] = (
        "latest_net_income=-1384.0M vs revenue=1.0M (|NI|/rev=1384.0x) — early/pre-revenue pattern, "
        "right entity; EXTREME (>20x) — gates buy_eligible"
    )
    _block_lrl_ext = compute_valuation(source26_debt_fixture(_dd_lrl_ext), 120_000_000, cfg)
    assert _block_lrl_ext.get("low_revenue_loss_ratio_extreme") is True, (
        "A4: producer low_revenue_loss_ratio_extreme must be read into the valuation block"
    )
    assert _block_lrl_ext.get("buy_eligible") is False, (
        f"A4: low_revenue_loss_ratio_extreme (>20x) MUST gate buy_eligible=False, "
        f"reasons={_block_lrl_ext.get('buy_ineligible_reasons')}"
    )
    assert "low_revenue_loss_ratio_extreme" in _block_lrl_ext.get("buy_ineligible_reasons", []), (
        "A4: low_revenue_loss_ratio_extreme must appear in buy_ineligible_reasons (accurate label)"
    )
    assert "wrong_entity_suspected" not in _block_lrl_ext.get("buy_ineligible_reasons", []), (
        "A4: the extreme tail must gate on low_revenue_loss_ratio_extreme, NOT wrong_entity_suspected"
    )
    assert any("low_revenue_loss_ratio_extreme" in str(x) for x in _block_lrl_ext.get("data_quality", [])), (
        "A4: low_revenue_loss_ratio_extreme must surface in data_quality"
    )
    print("  A4 low_revenue_loss_ratio_extreme: >20x gates buy_eligible=False (not wrong_entity)  OK")

    # A4-regression: the NON-extreme label (>2x, <=20x) must NOT gate, buy_eligible unchanged.
    _dd_lrl_mild = dict(_dd_clean_base)
    _dd_lrl_mild["derived"] = dict(_dd_clean_base["derived"])
    _dd_lrl_mild["ticker"] = "TEST_LOW_REV_LOSS_MILD"
    _dd_lrl_mild["derived"]["low_revenue_loss_ratio"] = True
    _dd_lrl_mild["derived"]["low_revenue_loss_ratio_extreme"] = False
    _dd_lrl_mild["derived"]["low_revenue_loss_ratio_detail"] = "|NI|/rev=2.7x — right entity"
    _block_lrl_mild = compute_valuation(source26_debt_fixture(_dd_lrl_mild), 120_000_000, cfg)
    assert _block_lrl_mild.get("buy_eligible") == _block_clean.get("buy_eligible"), (
        "A4: non-extreme low_revenue_loss_ratio must NOT change buy_eligible (label-only)"
    )
    assert "low_revenue_loss_ratio_extreme" not in _block_lrl_mild.get("buy_ineligible_reasons", []), (
        "A4: non-extreme must NOT add low_revenue_loss_ratio_extreme to buy_ineligible_reasons"
    )
    print("  A4 non-extreme low_revenue_loss_ratio: >2x stays label-only (no gate)  OK")

    # Synthetic insurance evidence must respect the SIC and concept-count thresholds.
    _dd_ins = dict(_dd_clean_base)
    _dd_ins["derived"] = dict(_dd_clean_base["derived"])
    _dd_ins["ticker"] = "TEST_INSURANCE_HOLDCO"
    _dd_ins["derived"]["sic"] = "6510"
    _dd_ins["derived"]["insurance_concepts_present"] = True
    _dd_ins["derived"]["insurance_concept_matched"] = "PremiumsEarnedNet"
    _block_ins = compute_valuation(source26_debt_fixture(_dd_ins), 120_000_000, cfg)
    assert _block_ins.get("insurance_concepts_present") is True, (
        "A3: producer insurance_concepts_present must be read into the valuation block"
    )
    assert _block_ins.get("mos_basis") in ("nav", "abstain"), (
        f"A3: insurance_concepts_present must route nav/abstain (never fcf_cap), "
        f"got {_block_ins.get('mos_basis')!r}"
    )
    assert _block_ins.get("fcf_cap_model_unsuitable") is True, (
        "A3: insurance_concepts_present must force fcf_cap_model_unsuitable=True"
    )
    assert _block_ins.get("buy_eligible") is False, (
        f"A3: insurance_concepts_present must gate buy_eligible=False, "
        f"reasons={_block_ins.get('buy_ineligible_reasons')}"
    )
    assert "insurance_concepts_present" in _block_ins.get("buy_ineligible_reasons", []), (
        "A3: insurance_concepts_present must appear (distinctly) in buy_ineligible_reasons"
    )
    assert any("insurance_concepts_present" in str(x) for x in _block_ins.get("data_quality", [])), (
        "A3: insurance_concepts_present must surface in data_quality"
    )
    # Synthetic insurance evidence must respect the SIC and concept-count thresholds.
    _ins_tradeable_buy = (
        _block_ins.get("buy_eligible") is True
        and _block_ins.get("mos_basis") == "fcf_cap"
    )
    assert _ins_tradeable_buy is False, (
        "A3 CRITICAL: a SIC-65 insurance-subsidiary holdco must never reach an fcf_cap BUY"
    )
    print("  A3 insurance_concepts_present: SIC-65 holdco routes nav/abstain + gates BUY  OK")

    # --- A2: concentration_unquantified surfaces in data_quality but does NOT gate ---
    _dd_cu = dict(_dd_clean_base)
    _dd_cu["derived"] = dict(_dd_clean_base["derived"])
    _dd_cu["ticker"] = "TEST_CONC_UNQUANT"
    _dd_cu["derived"]["concentration_unquantified"] = True
    _block_cu = compute_valuation(source26_debt_fixture(_dd_cu), 120_000_000, cfg)
    assert _block_cu.get("concentration_unquantified") is True, (
        "A2: producer concentration_unquantified must be read into the valuation block"
    )
    assert any("concentration_unquantified" in str(x) for x in _block_cu.get("data_quality", [])), (
        "A2: concentration_unquantified must surface in data_quality"
    )
    assert "concentration_unquantified" not in _block_cu.get("buy_ineligible_reasons", []), (
        "A2: concentration_unquantified is advisory ONLY — must NOT gate buy_eligible"
    )
    assert _block_cu.get("buy_eligible") == _block_clean.get("buy_eligible"), (
        "A2: concentration_unquantified must NOT change buy_eligible (advisory)"
    )
    print("  A2 concentration_unquantified: surfaced in data_quality, does NOT gate  OK")

    # Synthetic declining revenue and a cash-flow peak exercise contamination.
    _dd_lumpy = _legacy['valuation_lumpy']
    source28_annual_inputs(_dd_lumpy)
    _block_lumpy = compute_valuation(source26_debt_fixture(_dd_lumpy), 300_000_000, cfg)
    assert _block_lumpy.get("cyclical") is True, (
        f"P10: lumpy fixture must be cyclical, got {_block_lumpy.get('cyclical')}"
    )
    assert _block_lumpy.get("lumpy_ocf_normalization_suspect") is True, (
        "P10: a year with OCF > 2x median of others must set lumpy_ocf_normalization_suspect"
    )
    assert any("lumpy_ocf_normalization_suspect" in str(x) for x in _block_lumpy.get("data_quality", [])), (
        "P10: lumpy_ocf_normalization_suspect must appear in data_quality list"
    )
    assert any("lumpy_ocf_corroborated_by_contamination" in str(x) for x in _block_lumpy.get("data_quality", [])), (
        "P10: lumpy guard must corroborate with producer contamination_ratio<1.0"
    )
    print("  P10 lumpy-OCF guard: peak-year>2x-median flags + corroborates contamination  OK")

    # A positive normalized cash-flow base must not conceal a synthetic current loss.
    _dd_masked_case = dict(_dd_clean_base)
    _dd_masked_case["derived"] = dict(_dd_clean_base["derived"])
    _dd_masked_case["ticker"] = "SYNMASKED"
    _dd_masked_case["derived"]["normalization_masks_current_loss"] = True
    _dd_masked_case["derived"]["normalized_fcf_proxy"] = 12_000_000   # trailing-avg POSITIVE
    _dd_masked_case["derived"]["latest_ocf"] = _legacy["valuation_overrides"]["current_ocf"]
    _dd_masked_case["derived"]["latest_fcf"] = _legacy["valuation_overrides"]["current_fcf"]
    _block_masked_case = compute_valuation(source26_debt_fixture(_dd_masked_case), 120_000_000, cfg)
    assert _block_masked_case.get("normalization_masks_current_loss") is True, (
        "#1: producer normalization_masks_current_loss must be read into the valuation block"
    )
    assert "normalization_masks_current_loss" in _block_masked_case.get("buy_ineligible_reasons", []), (
        f"#1: normalization_masks_current_loss must gate buy_eligible (downgrade BUY->WATCH), "
        f"reasons={_block_masked_case.get('buy_ineligible_reasons')}"
    )
    assert _block_masked_case.get("buy_eligible") is False, (
        "#1 CRITICAL: the synthetic current-loss degenerate-base shape must NOT be buy_eligible "
        "(trailing-avg normalized_fcf>0 masking current cash burn)"
    )
    assert any("normalization_masks_current_loss" in str(x) for x in _block_masked_case.get("data_quality", [])), (
        "#1: normalization_masks_current_loss must surface in data_quality"
    )
    # NEGATIVE CONTROL: a clean grower (producer flag False) must stay buy_eligible, the gate must
    # NOT fire on healthy normalization. Reuse the clean fixture (flag absent/False).
    assert _block_clean.get("normalization_masks_current_loss") is False, (
        "#1: clean grower must have normalization_masks_current_loss=False (no false fire)"
    )
    assert "normalization_masks_current_loss" not in _block_clean.get("buy_ineligible_reasons", []), (
        "#1: clean grower must NOT be gated by normalization_masks_current_loss"
    )
    assert _block_clean.get("buy_eligible") is True, (
        "#1: clean grower stays buy_eligible (the #1 gate is downgrade-only, never trigger-happy)"
    )
    print("  #1 normalization_masks_current_loss: synthetic current-loss shape gated BUY->WATCH; clean grower untouched  OK")

    # POSITIVE CONTROL (#1 + #9): a clean grower with a REAL numeric MoS>=30 must stay buy_eligible.
    # The two new v0.3.1 gates (#1 normalization_masks_current_loss, #9 not_assessable_no_intrinsic_band)
    # are downgrade-only / null-guards; neither may suppress a genuinely cheap healthy name. Scale the
    # clean fixture's FCF up so the conservative cap model yields MoS>=30 at the same market cap.
    _dd_cheap = dict(_dd_clean_base)
    _dd_cheap["derived"] = dict(_dd_clean_base["derived"])
    _dd_cheap["ticker"] = "TEST_CHEAP_GROWER"
    # Post-interest FCF=20M -> equity_low=20M/0.12=166.67M, with no net-cash addback.
    # Against 120M market cap this gives MoS=38.89%, within the original positive-control band.
    _dd_cheap["derived"]["latest_ocf"] = 25_000_000
    _dd_cheap["derived"]["latest_fcf"] = 20_000_000
    _dd_cheap["financials"] = dict(_dd_clean_base["financials"])
    _dd_cheap["financials"].update(source25_annual_cashflows(ocf=25_000_000))
    _block_cheap = compute_valuation(source26_debt_fixture(_dd_cheap), 120_000_000, cfg)
    assert _block_cheap.get("mos_basis") == "fcf_cap", (
        f"#1/#9 positive control: cheap grower must route fcf_cap, got {_block_cheap.get('mos_basis')!r}"
    )
    _mos_cheap = _block_cheap.get("margin_of_safety_pct")
    assert _block_cheap["intrinsic_value_band"]["equity_low"] == round(20_000_000 / 0.12)
    assert _mos_cheap == 0.3889
    assert _mos_cheap is not None and _mos_cheap >= 0.30, (
        f"#1/#9 positive control: cheap grower must have a REAL numeric MoS>=30%, got {_mos_cheap}"
    )
    assert _block_cheap.get("normalization_masks_current_loss") is False, (
        "#1 positive control: cheap grower (positive latest FCF) must NOT set normalization_masks_current_loss"
    )
    assert "not_assessable_no_intrinsic_band" not in _block_cheap.get("buy_ineligible_reasons", []), (
        "#9 positive control: a real numeric MoS must NOT add not_assessable_no_intrinsic_band"
    )
    assert _block_cheap.get("buy_eligible") is True, (
        f"#1/#9 positive control: a clean grower with real MoS>=30 must stay buy_eligible=True, "
        f"reasons={_block_cheap.get('buy_ineligible_reasons')}"
    )
    print("  #1/#9 positive control: clean grower with real MoS>=30 stays buy_eligible=True  OK")

    # Preserve the original 18M FCF economics under the current post-interest equity basis.
    # Its 10M net cash is not added back: equity=150M and MoS=25%, below the 30% threshold.
    _case_18m = source25_equity_basis_scenarios()[0]
    _block_18m = compute_valuation(_case_18m["data"], _case_18m["market_cap"], cfg)
    assert _block_18m["intrinsic_value_band"]["equity_low"] == 150_000_000
    assert _block_18m["margin_of_safety_pct"] == 0.25
    assert _block_18m["margin_of_safety_pct"] < 0.30
    assert _block_18m["buy_eligible"] is True  # Eligibility guards do not encode the final MoS threshold.
    print("  Original 18M FCF: equity=150M, MoS=25%, no net-cash addback  OK")

    # Absent intrinsic value must remain explicitly ineligible.
    _dd_no_band = dict(_dd_clean_base)
    _dd_no_band["derived"] = dict(_dd_clean_base["derived"])
    _dd_no_band["ticker"] = "TEST_NO_BAND"
    _dd_no_band["derived"]["latest_fcf"] = None    # non-cyclical norm_fcf = latest_fcf -> null
    _dd_no_band["derived"]["latest_ocf"] = None
    _dd_no_band["financials"] = dict(_dd_clean_base["financials"])
    _dd_no_band["financials"]["ocf"] = []          # no OCF base -> no normalized FCF -> null band
    _dd_no_band["financials"]["capex"] = []
    _block_no_band = compute_valuation(source26_debt_fixture(_dd_no_band), 120_000_000, cfg)
    assert _block_no_band.get("mos_basis") == "fcf_cap", (
        f"#9: no-OCF fixture must route fcf_cap (non-asset-heavy SIC), "
        f"got {_block_no_band.get('mos_basis')!r}"
    )
    assert _block_no_band.get("margin_of_safety_pct") is None, (
        f"#9: no intrinsic band must yield a NULL MoS, got {_block_no_band.get('margin_of_safety_pct')}"
    )
    assert "not_assessable_no_intrinsic_band" in _block_no_band.get("buy_ineligible_reasons", []), (
        f"#9: a null MoS must add not_assessable_no_intrinsic_band, "
        f"reasons={_block_no_band.get('buy_ineligible_reasons')}"
    )
    assert _block_no_band.get("buy_eligible") is False, (
        "#9 CRITICAL: buy_eligible must NEVER be True with a null MoS"
    )
    # Belt-and-suspenders: across ALL three null-MoS basis routes (fcf_cap null band, nav with no NAV
    # MoS, abstain) buy_eligible must be False, assert the invariant directly on the no-band block.
    assert not (_block_no_band.get("buy_eligible") is True
                and _block_no_band.get("margin_of_safety_pct") is None), (
        "#9 INVARIANT: buy_eligible=True with margin_of_safety_pct=None is forbidden"
    )
    print("  #9 null-MoS: no intrinsic band -> not_assessable_no_intrinsic_band, buy_eligible=False  OK")

    # Synthetic lessors below the debt firewall must route on their leasing evidence.
    _dd_lessor = dict(_dd_clean_base)
    _dd_lessor["derived"] = dict(_dd_clean_base["derived"])
    _dd_lessor["ticker"] = "SYNLESSORHIGH"
    _dd_lessor["derived"]["sic"] = "3743"               # railroad equipment, non-financial prefix
    _dd_lessor["derived"]["lessor_asset_heavy"] = True
    _dd_lessor["derived"]["lessor_asset_heavy_detail"] = "lessor_sic:3743;ppe_fleet_ratio=0.70>0.55+rental_rev"
    # debt/assets = 420M/1000M = 0.42 < 0.62 (the firewall would NOT route this without #8).
    _dd_lessor["derived"]["latest_total_debt"] = _legacy["valuation_overrides"]["lessor_high_debt"]
    _dd_lessor["financials"] = dict(_dd_clean_base["financials"])
    _dd_lessor["financials"]["assets"] = [{"end": "2024-12-31", "val": 1_000_000_000}]
    _dd_lessor["financials"]["equity"] = [{"end": "2024-12-31", "val": 400_000_000}]
    _block_lessor = compute_valuation(source26_debt_fixture(_dd_lessor), 300_000_000, cfg)
    # Sanity: debt/assets really is below the 0.62 firewall, so the routing is ATTRIBUTABLE to #8.
    assert (_legacy["valuation_overrides"]["lessor_high_debt"] / _legacy["valuation_overrides"]["lessor_assets"]) < 0.62, "#8 fixture: debt/assets must be <0.62 to prove the hole"
    assert _block_lessor.get("lessor_asset_heavy") is True, (
        f"#8: lessor_asset_heavy must propagate to the block, got {_block_lessor.get('lessor_asset_heavy')}"
    )
    assert _block_lessor.get("fcf_cap_model_unsuitable") is True, (
        f"#8 CRITICAL: a lessor (debt/assets=0.42<0.62) must force fcf_cap_model_unsuitable=True "
        f"(route to lease-fleet NAV), got {_block_lessor.get('fcf_cap_model_unsuitable')}"
    )
    assert _block_lessor.get("mos_basis") in ("nav", "abstain"), (
        f"#8: a lessor must route nav/abstain (NOT trough-cycle fcf_cap), "
        f"got {_block_lessor.get('mos_basis')!r}"
    )
    assert any("lessor_asset_heavy_fcf_unsuitable_route_nav" in str(x)
               for x in _block_lessor.get("data_quality", [])), (
        f"#8: routing reason must be in data_quality, got {_block_lessor.get('data_quality')}"
    )
    # Negative control: the SAME fixture WITHOUT the lessor flag (and below 0.62) routes fcf_cap ,
    # proving the routing is driven by lessor_asset_heavy, not by the debt/assets ratio.
    _dd_not_lessor = dict(_dd_lessor)
    _dd_not_lessor["derived"] = dict(_dd_lessor["derived"])
    _dd_not_lessor["ticker"] = "TEST_NOT_LESSOR"
    _dd_not_lessor["derived"]["lessor_asset_heavy"] = False
    _dd_not_lessor["derived"]["lessor_asset_heavy_detail"] = None
    _block_not_lessor = compute_valuation(source26_debt_fixture(_dd_not_lessor), 300_000_000, cfg)
    assert _block_not_lessor.get("fcf_cap_model_unsuitable") is False, (
        f"#8 control: a NON-lessor at debt/assets=0.42 must STAY fcf_cap (firewall not tripped), "
        f"got {_block_not_lessor.get('fcf_cap_model_unsuitable')}"
    )
    assert _block_not_lessor.get("mos_basis") == "fcf_cap", (
        f"#8 control: non-lessor at 0.42 debt/assets must route fcf_cap, "
        f"got {_block_not_lessor.get('mos_basis')!r}"
    )
    assert _block_not_lessor.get("lessor_asset_heavy") is False, (
        "#8 control: lessor_asset_heavy must be False on the non-lessor block"
    )
    print("  #8 lessor_asset_heavy: synthetic (debt/assets=0.42) forces NAV routing; "
          "non-lessor at 0.42 stays fcf_cap  OK")

    # The lower synthetic debt ratio supplies a separate NAV-routing case.
    _dd_lower_lessor = dict(_dd_clean_base)
    _dd_lower_lessor["derived"] = dict(_dd_clean_base["derived"])
    _dd_lower_lessor["ticker"] = "SYNLESSORLOW"
    _dd_lower_lessor["derived"]["sic"] = "7359"                  # equipment rental/leasing, non-financial prefix
    _dd_lower_lessor["derived"]["lessor_asset_heavy"] = True
    _dd_lower_lessor["derived"]["lessor_asset_heavy_detail"] = "lessor_sic:7359;operating_lease_income_concept+rental_rev"
    # debt/assets = 340M/1000M = 0.34 < 0.62 (firewall would NOT route this without #8).
    _dd_lower_lessor["derived"]["latest_total_debt"] = _legacy["valuation_overrides"]["lessor_low_debt"]
    _dd_lower_lessor["financials"] = dict(_dd_clean_base["financials"])
    _dd_lower_lessor["financials"]["assets"] = [{"end": "2024-12-31", "val": 1_000_000_000}]
    _dd_lower_lessor["financials"]["equity"] = [{"end": "2024-12-31", "val": 450_000_000}]
    _block_lower_lessor = compute_valuation(source26_debt_fixture(_dd_lower_lessor), 300_000_000, cfg)
    assert (_legacy["valuation_overrides"]["lessor_low_debt"] / _legacy["valuation_overrides"]["lessor_assets"]) == 0.34, "#8 synthetic lower-ratio fixture: debt/assets must be exactly 0.34"
    assert _block_lower_lessor.get("lessor_asset_heavy") is True, (
        f"#8 synthetic lower-ratio: lessor_asset_heavy must propagate, got {_block_lower_lessor.get('lessor_asset_heavy')}"
    )
    assert _block_lower_lessor.get("fcf_cap_model_unsuitable") is True, (
        f"#8 synthetic lower-ratio CRITICAL: a lessor at debt/assets=0.34<0.62 must force fcf_cap_model_unsuitable=True, "
        f"got {_block_lower_lessor.get('fcf_cap_model_unsuitable')}"
    )
    assert _block_lower_lessor.get("mos_basis") == "nav", (
        f"#8 synthetic lower-ratio: a lessor with equity present must route mos_basis='nav' (not fcf_cap/abstain), "
        f"got {_block_lower_lessor.get('mos_basis')!r}"
    )
    assert _block_lower_lessor.get("margin_of_safety_pct") is None, (
        f"#8 synthetic lower-ratio: FCF margin_of_safety_pct must be null when routed to NAV, "
        f"got {_block_lower_lessor.get('margin_of_safety_pct')}"
    )
    assert any("lessor_asset_heavy_fcf_unsuitable_route_nav" in str(x)
               for x in _block_lower_lessor.get("data_quality", [])), (
        f"#8 synthetic lower-ratio: routing reason must surface in data_quality, got {_block_lower_lessor.get('data_quality')}"
    )
    # Normal-name control restated at 0.34: the clean (non-lessor) fixture is unchanged, proving
    # the NAV routing is attributable to lessor_asset_heavy, never to the sub-firewall ratio itself.
    assert _block_clean.get("lessor_asset_heavy") is False, (
        f"#8: a normal name must have lessor_asset_heavy=False, got {_block_clean.get('lessor_asset_heavy')}"
    )
    assert _block_clean.get("mos_basis") == "fcf_cap", (
        f"#8: a normal name must stay mos_basis='fcf_cap' (unchanged), got {_block_clean.get('mos_basis')!r}"
    )
    assert not any("lessor_asset_heavy" in str(x) for x in _block_clean.get("data_quality", [])), (
        "#8: a normal name must NOT emit any lessor_asset_heavy data_quality line"
    )
    print("  #8 synthetic lower-ratio (debt/assets=0.34) forces mos_basis=nav; normal name stays fcf_cap unchanged  OK")

    # --- v0.3.2 #11: foreign_filer_unvaluable is surfaced as an explicit abstain label ---
    # A 20-F filer whose financials stayed empty after the producer's IFRS cascade emits
    # derived.foreign_filer_unvaluable=True. valuation MUST surface it in the block + data_quality
    # so the abstain is CLEARLY labeled (not a silent intrinsic_band_unavailable null). It is a
    # LABEL only, the null MoS still gates buy_eligible via not_assessable (no false BUY).
    _dd_ffu = dict(_dd_no_band)                          # no-band fixture => null MoS already
    _dd_ffu["derived"] = dict(_dd_no_band["derived"])
    _dd_ffu["ticker"] = "TEST_FOREIGN_UNVALUABLE"
    _dd_ffu["derived"]["form_used"] = "20-F"
    _dd_ffu["derived"]["foreign_filer_unvaluable"] = True
    _dd_ffu["derived"]["foreign_filer_unvaluable_detail"] = (
        "foreign filer (form=20-F) returned EMPTY revenue/net-income/OCF even after the "
        "us-gaap+ifrs-full concept cascade — un-valuable from EDGAR (graceful abstain)"
    )
    _block_ffu = compute_valuation(source26_debt_fixture(_dd_ffu), 120_000_000, cfg)
    assert _block_ffu.get("foreign_filer_unvaluable") is True, (
        f"#11: foreign_filer_unvaluable must propagate to the block, "
        f"got {_block_ffu.get('foreign_filer_unvaluable')}"
    )
    assert _block_ffu.get("foreign_filer_unvaluable_detail"), (
        "#11: the explicit detail string must be surfaced (not a silent null)"
    )
    assert any("foreign_filer_unvaluable" in str(x) for x in _block_ffu.get("data_quality", [])), (
        f"#11: foreign_filer_unvaluable must be an explicit data_quality label, "
        f"got {_block_ffu.get('data_quality')}"
    )
    # Graceful abstain, never a false BUY: the null MoS still gates buy_eligible.
    assert _block_ffu.get("buy_eligible") is False, (
        "#11 CRITICAL: a foreign un-valuable filer (null MoS) must NEVER be buy_eligible"
    )
    # Negative control: a domestic 10-K name must NOT carry the foreign label.
    assert _block_clean.get("foreign_filer_unvaluable") is False, (
        f"#11 control: a domestic 10-K name must have foreign_filer_unvaluable=False, "
        f"got {_block_clean.get('foreign_filer_unvaluable')}"
    )
    assert not any("foreign_filer_unvaluable" in str(x) for x in _block_clean.get("data_quality", [])), (
        "#11 control: a domestic filer must NOT emit the foreign_filer_unvaluable label"
    )
    print("  #11 foreign_filer_unvaluable: 20-F empty-after-IFRS labeled explicitly + buy_eligible=False; "
          "domestic 10-K clean  OK")

    print("\nvaluation selftest PASS")


if __name__ == "__main__":
    main()
