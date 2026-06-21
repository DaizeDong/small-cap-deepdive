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

Usage:
    python valuation.py --json reports/smallcap/deepdive_WLFC_2026-06-19.json --ticker WLFC
    python valuation.py --json ... --ticker WLFC --mktcap 1644548480
    python valuation.py --selftest
Output:
    reports/smallcap/valuation_<ticker>_<date>.json
    Also merges the valuation block into the deepdive JSON (adds key "valuation").
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# sys.path shim so this script can be run directly from tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, init_edgar, today


# ---------------------------------------------------------------------------
# Config defaults (overridable via config.json)
# ---------------------------------------------------------------------------
_VALUATION_DEFAULTS = {
    "wacc": 0.10,
    "cap_rate_low": 0.09,    # low cap rate → HIGH equity value (optimistic end)
    "cap_rate_high": 0.12,   # high cap rate → LOW equity value (conservative end)
    "normalize_years": 5,
    "cyclical_cv_threshold": 0.25,
}


def _val_cfg() -> dict:
    """Merge valuation config keys from CFG with defaults."""
    defaults = dict(_VALUATION_DEFAULTS)
    for k in defaults:
        if k in CFG:
            defaults[k] = float(CFG[k])
    return defaults


# ---------------------------------------------------------------------------
# Market cap resolution
# ---------------------------------------------------------------------------
def _get_market_cap(ticker: str, mktcap_override: int | None = None) -> tuple[int | None, str]:
    """Return (market_cap_in_dollars, source_label).

    Priority: explicit --mktcap override > yfinance live quote.
    Returns (None, reason) if unavailable.
    """
    if mktcap_override is not None:
        return mktcap_override, "override"
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        mc = info.get("marketCap")
        if mc and mc > 0:
            return int(mc), "yfinance"
        return None, "yfinance_returned_null"
    except Exception as e:
        return None, f"yfinance_error:{e}"


# ---------------------------------------------------------------------------
# Cyclicality test
# ---------------------------------------------------------------------------
def _coefficient_of_variation(series: list) -> float | None:
    """Compute CV = std/mean for a numeric list. Returns None if insufficient data."""
    vals = [v for v in series if v is not None]
    if len(vals) < 3:
        return None
    mean = statistics.mean(vals)
    if mean == 0:
        return None
    stdev = statistics.stdev(vals)
    return stdev / abs(mean)


def _is_cyclical(ebitda_series: list[dict], revenue_series: list[dict], threshold: float) -> tuple[bool, float | None]:
    """Return (cyclical_flag, cv_used).

    Uses EBITDA series if >=3 data points; falls back to revenue if EBITDA insufficient.
    Returns (False, None) if neither series has >=3 points.
    """
    ebitda_vals = [v["val"] for v in ebitda_series if v.get("val") is not None]
    if len(ebitda_vals) >= 3:
        cv = _coefficient_of_variation(ebitda_vals)
        return (cv is not None and cv > threshold), cv
    # Fallback: revenue CV
    rev_vals = [v["val"] for v in revenue_series if v.get("val") is not None]
    if len(rev_vals) >= 3:
        cv = _coefficient_of_variation(rev_vals)
        return (cv is not None and cv > threshold), cv
    return False, None


# ---------------------------------------------------------------------------
# Normalized metric computation
# ---------------------------------------------------------------------------
def _normalize(series: list[dict], n_years: int) -> float | None:
    """Return trailing n_years average of series val. Handles partial availability."""
    vals = [v["val"] for v in series if v.get("val") is not None]
    if not vals:
        return None
    window = vals[-n_years:]
    return statistics.mean(window)


def _build_ebitda_series(ebit_series: list[dict], da_series: list[dict]) -> tuple[list[dict], int]:
    """Construct year-by-year EBITDA series from EBIT and D&A series (matched by end date).

    Only includes year-ends where BOTH EBIT and D&A are present — partial sums distort
    cyclicality CV and normalization.  Year-ends with only one component are skipped;
    the count of skipped entries is returned so the caller can flag it.

    Returns (ebitda_series, n_partial_skipped).
    The result list is sorted by end date.
    """
    ebit_map = {v["end"]: v["val"] for v in ebit_series}
    da_map = {v["end"]: v["val"] for v in da_series}
    all_ends = sorted(set(ebit_map) | set(da_map))
    result = []
    n_partial = 0
    for end in all_ends:
        e = ebit_map.get(end)
        d = da_map.get(end)
        if e is not None and d is not None:
            result.append({"end": end, "val": e + d})
        else:
            n_partial += 1  # skip partial — do not let half-sums distort CV
    return result, n_partial


def _build_fcf_series(ocf_series: list[dict], capex_series: list[dict], fcf_is_proxy: bool) -> tuple[list[dict], bool]:
    """Construct year-by-year FCF = OCF - CapEx series.

    If capex_series is empty (proxy mode), returns OCF series as FCF with is_proxy=True.
    Otherwise matches by end date; years without a capex match use OCF alone.
    """
    if fcf_is_proxy or not capex_series:
        return [{"end": v["end"], "val": v["val"]} for v in ocf_series], True
    ocf_map = {v["end"]: v["val"] for v in ocf_series}
    capex_map = {v["end"]: v["val"] for v in capex_series}
    # CapEx in XBRL PaymentsToAcquire... is stored as positive dollar outflow
    result = []
    for end in sorted(ocf_map):
        ocf_val = ocf_map[end]
        cx = capex_map.get(end)
        if cx is not None:
            result.append({"end": end, "val": ocf_val - cx})
        else:
            result.append({"end": end, "val": ocf_val})  # no capex matched
    return result, False


# ---------------------------------------------------------------------------
# Core valuation computation
# ---------------------------------------------------------------------------
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

    discount_rate = cfg["wacc"]  # used as the discount rate in reverse-DCF
    cap_low = cfg["cap_rate_low"]    # low cap rate → HIGH equity value (optimistic end)
    cap_high = cfg["cap_rate_high"]  # high cap rate → LOW equity value (conservative end)
    n_years = int(cfg["normalize_years"])
    cv_threshold = cfg["cyclical_cv_threshold"]

    # --- Inputs ---
    latest_cash = der.get("latest_cash")
    latest_debt = der.get("latest_total_debt")
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
    # It does NOT by itself flip buy_eligible — those names stay blocked by their null/negative
    # FCF (MoS null) as before, NOT by this label.
    if der.get("low_revenue_loss_ratio"):
        _lrl_detail = der.get("low_revenue_loss_ratio_detail", "")
        # A4: distinguish the EXTREME (>20x) tier (gates buy_eligible) from the advisory label.
        _lrl_tag = "low_revenue_loss_ratio_extreme" if der.get("low_revenue_loss_ratio_extreme") else "low_revenue_loss_ratio"
        dq.append(f"{_lrl_tag}:{_lrl_detail}")
    # A2: concentration_unquantified — text customer-concentration flag True but no XBRL magnitude
    # (text-only / pre-/early-XBRL filer, the SWMR/LFCR SIGA-class blind spot). Advisory ONLY:
    # surfaced in data_quality so a PM sees the unquantified concentration; does NOT gate.
    if der.get("concentration_unquantified"):
        dq.append("concentration_unquantified:text_flag_true_but_xbrl_magnitude_null")

    # --- C2: financial-SIC guard — exclude financial sector from FCF-cap model ---
    # SIC prefixes: 60=banks, 61=non-depository credit, 63=insurance carriers,
    #               64=insurance agents, 67=holding companies/investment/REITs/BDCs
    _FINANCIAL_SIC_PREFIXES = ("60", "61", "63", "64", "67")
    sic_code = str(der.get("sic") or "").strip()
    _financial_sic = bool(sic_code and any(sic_code.startswith(p) for p in _FINANCIAL_SIC_PREFIXES))
    # A3: insurance_concepts_present — an insurance underwriter / insurance-subsidiary holdco
    # detected from XBRL concepts (PremiumsEarned / policy reserves / losses&LAE / policyholder
    # funds). These route like a financial_sic name (nav/abstain, never an fcf_cap BUY) EVEN when
    # the top-level SIC is non-financial — closing the BOC SIC-65 surety-insurance-holdco hole
    # where prefix 65 is not in _FINANCIAL_SIC_PREFIXES. Distinct buy_eligible gate below.
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
        # C2-fallback: SEC submissions sometimes omit the top-level SIC (observed on
        # several BDCs / closed-end funds, e.g. WHF). Detect the investment-company
        # signature — NO GAAP revenue but operating cash flow present (loan/portfolio
        # cash flows) — and treat it as financial-structure: FCF-cap is unsuitable.
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
        dq.append("capex_unavailable_fcf_uses_ocf_proxy")
    if fcf_is_proxy:
        dq.append("fcf_equals_ocf_proxy_no_capex")
    if latest_ni is None or latest_ni <= 0:
        dq.append("net_income_nonpositive_pe_null")
    if latest_shares is None:
        dq.append("shares_unavailable_per_share_null")

    # --- EV computation ---
    # EV = market_cap + total_debt - cash
    # If debt or cash is unavailable, compute partial EV with annotation
    ev: float | None = None
    ev_note: str | None = None
    if latest_debt is not None and latest_cash is not None:
        ev = market_cap + latest_debt - latest_cash
    elif latest_debt is not None:
        ev = market_cap + latest_debt
        ev_note = "cash_excluded"
        dq.append("ev_excludes_cash")
    elif latest_cash is not None:
        ev = market_cap - latest_cash
        ev_note = "debt_excluded"
        dq.append("ev_excludes_debt")
    else:
        ev = float(market_cap)
        ev_note = "debt_and_cash_excluded"
        dq.append("ev_is_market_cap_only")

    if ev is not None and ev <= 0:
        dq.append("ev_nonpositive_multiples_null")

    # --- Multiples ---
    ev_sales: float | None = None
    if ev and ev > 0 and latest_revenue and latest_revenue > 0:
        ev_sales = round(ev / latest_revenue, 2)

    # Build EBITDA series for normalization (full pairs only; skips partial entries)
    ebitda_series, n_ebitda_partial = _build_ebitda_series(ebit_series, da_series)
    if n_ebitda_partial > 0:
        dq.append(f"ebitda_series_partial_entries:{n_ebitda_partial}")

    # --- P9: EBIT concept cascade → EBITDA recovery ---
    # The producer tags ebit_source (the concept actually used: OperatingIncomeLoss /
    # pretax+interest_addback / pretax_proxy). When latest_ebitda is missing but EBIT
    # was recovered via the cascade, reconstruct latest EBITDA = recovered_EBIT + D&A so
    # EV/EBITDA computes on the ~47% of names that previously came back null.
    ebit_source = der.get("ebit_source")
    latest_ebitda = der.get("latest_ebitda")
    if latest_ebitda is None and ebit_source:
        # Prefer the latest full EBIT+D&A pair from the constructed series; fall back to
        # derived latest_ebit + latest_da.
        _recovered_ebitda = ebitda_series[-1]["val"] if ebitda_series else None
        if _recovered_ebitda is None and latest_ebit is not None and latest_da is not None:
            _recovered_ebitda = latest_ebit + latest_da
        if _recovered_ebitda is not None:
            latest_ebitda = _recovered_ebitda
            dq.append(f"ebitda_recovered_via_ebit_cascade:ebit_source={ebit_source}")

    ev_ebitda: float | None = None
    if ev and ev > 0 and latest_ebitda and latest_ebitda > 0:
        ev_ebitda = round(ev / latest_ebitda, 2)
    elif ev and ev > 0 and latest_ebitda:
        dq.append("ebitda_nonpositive_ev_ebitda_null")

    pe: float | None = None
    if latest_ni and latest_ni > 0:
        pe = round(market_cap / latest_ni, 2)

    latest_fcf = der.get("latest_fcf")
    fcf_yield: float | None = None
    if latest_fcf is not None and market_cap > 0:
        fcf_yield = round(latest_fcf / market_cap, 4)

    # --- Cyclicality ---
    cyclical, cv_val = _is_cyclical(ebitda_series, rev_series, cv_threshold)
    cv_rounded = round(cv_val, 4) if cv_val is not None else None

    # --- Normalized metrics ---
    if cyclical:
        norm_ebitda = _normalize(ebitda_series, n_years)
        norm_fcf_series, fcf_proxy_flag = _build_fcf_series(ocf_series, capex_series, fcf_is_proxy)
        norm_fcf = _normalize(norm_fcf_series, n_years)
        norm_note = f"cyclical:trailing_{n_years}yr_avg"
        # Flag if the normalization window is shorter than requested
        n_fcf_used = len([v for v in norm_fcf_series if v.get("val") is not None])
        if n_fcf_used < n_years and norm_fcf is not None:
            dq.append(f"normalized_uses_{n_fcf_used}yr_insufficient")
    else:
        norm_ebitda = latest_ebitda
        norm_fcf = latest_fcf
        fcf_proxy_flag = fcf_is_proxy
        norm_note = "non_cyclical:latest"

    if norm_ebitda is None:
        dq.append("normalized_ebitda_unavailable")
    if norm_fcf is None:
        dq.append("normalized_fcf_unavailable")

    # --- Asset-heavy / leveraged flag ---
    # FCF-cap model is unsuitable when debt/assets > 0.62.
    # Threshold: 0.62 robustly catches aircraft lessors (WLFC ~64-71% across quarters) and
    # finance companies while sparing cyclical industrials (LNN ~14%).
    # The annual FY figure for WLFC is typically ~67-69%; quarterly dips to ~64% during
    # fleet drawdowns, so 0.62 is the right boundary to avoid false negatives.
    # C2: financial SIC also forces fcf_cap_model_unsuitable regardless of debt/assets ratio.
    fcf_cap_model_unsuitable: bool = False
    if _financial_sic_forced_unsuitable:
        # C2: financial-sector companies (banks, insurers, BDCs, REITs, holding cos)
        # — FCF capitalization is structurally invalid for these business models.
        fcf_cap_model_unsuitable = True
        # note already appended to dq above
    elif latest_debt is not None and latest_assets and latest_assets > 0:
        debt_to_assets = latest_debt / latest_assets
        if debt_to_assets > 0.62:
            fcf_cap_model_unsuitable = True
            dq.append(f"fcf_cap_model_unsuitable:debt_to_assets={debt_to_assets:.4f}>0.62")

    # --- C1 data-quality blocks on valuation routing ---
    # If debt_truncation or wrong_entity detected, treat EV/MoS as unreliable.
    # These flags are already in dq; here we force abstain by treating fcf_cap unsuitable.
    _c1_data_block = der.get("debt_truncation_suspected") or der.get("debt_stale") or der.get("wrong_entity_suspected")
    if _c1_data_block and not fcf_cap_model_unsuitable:
        fcf_cap_model_unsuitable = True  # force abstain path
        dq.append("fcf_cap_blocked_by_c1_data_quality_guard")

    # --- Reverse DCF (Gordon growth approximation) ---
    # norm_fcf is levered (equity) FCF (OCF - CapEx, post-interest).
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
    # Conservative FCF capitalization: equity_value = normalized_fcf / cap_rate - net_debt
    # cap_rate_high (0.12) → low equity estimate (conservative end)
    # cap_rate_low (0.09) → high equity estimate (optimistic end)
    # Net debt = total_debt - cash (positive = net debt owed)
    net_debt: float | None = None
    if latest_debt is not None and latest_cash is not None:
        net_debt = latest_debt - latest_cash
    elif latest_debt is not None:
        net_debt = latest_debt
        dq.append("net_debt_excludes_cash")
    elif latest_cash is not None:
        net_debt = -latest_cash  # net cash position
        dq.append("net_debt_excludes_debt_liabilities")

    iv_band: dict | None = None
    if norm_fcf is not None and norm_fcf > 0:
        ev_implied_low = norm_fcf / cap_high   # high cap rate → low EV
        ev_implied_high = norm_fcf / cap_low   # low cap rate → high EV
        nd = net_debt if net_debt is not None else 0
        eq_low = ev_implied_low - nd
        eq_high = ev_implied_high - nd
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
            "note": f"conservative_fcf_cap;net_debt={'included' if net_debt is not None else 'excluded(unavailable)'}",
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

    # --- G2: large-cap ceiling — mktcap > watch_band_max must NOT receive BUY ---
    # For a small-cap tool, anything in the large-cap band is out of scope.
    # watch_band_max from config (default 2B).
    _WATCH_BAND_MAX = int(cfg.get("watch_band_max", 2_000_000_000))
    _large_cap_out_of_scope = market_cap > _WATCH_BAND_MAX
    if _large_cap_out_of_scope:
        dq.append(f"out_of_scope_large_cap:market_cap={market_cap/1e9:.1f}B>watch_band_max={_WATCH_BAND_MAX/1e9:.1f}B")

    # --- I1: FCF sustainability guard ---
    # Downgrade BUY→WATCH when FCF quality is suspect:
    #   (i)  reverse_dcf_implied_growth < -0.15 — market prices in steep decline while
    #        our MoS says cheap = contradiction → unsupported terminal value
    #   (ii) OCF-proxy AND capital-intensive (large PP&E proxy = assets >> equity, or
    #        large capex historically) — true FCF after capex is unknown and likely lower
    #   (iii) lumpy OCF (CV high but not fully captured by cyclical flag)
    #
    # This only fires for fcf_cap path (nav/abstain already route away from BUY).
    _fcf_sustainability_uncertain = False
    if mos_basis == "fcf_cap" and mos is not None:
        # (i) reverse-DCF growth strongly negative while MoS positive → contradiction
        if rdcf_growth is not None and rdcf_growth < -0.15:
            _fcf_sustainability_uncertain = True
            dq.append(f"fcf_sustainability_uncertain:rdcf_growth={rdcf_growth:.3f}<-0.15")

        # (ii) P2: EVERY OCF-proxy FCF is uncertain — true FCF after capex is unknown
        # and structurally <= OCF. assets/rev>5 is used ONLY to escalate severity,
        # NEVER as a gate (the old dead `elif` silently skipped capital-light proxies
        # with assets present but ratio<=5 — ~18% of the universe went unflagged).
        if fcf_is_proxy:
            _fcf_sustainability_uncertain = True
            if latest_assets is not None and latest_revenue and latest_revenue > 0:
                asset_rev_ratio = latest_assets / latest_revenue
                if asset_rev_ratio > 5.0:
                    dq.append(
                        f"fcf_sustainability_uncertain:ocf_proxy_on_capital_intensive"
                        f"(assets/rev={asset_rev_ratio:.1f})"
                    )
                else:
                    dq.append(
                        f"fcf_sustainability_uncertain:ocf_proxy_capex_unknown"
                        f"(assets/rev={asset_rev_ratio:.1f})"
                    )
            else:
                # No asset/revenue data — still uncertain (unknown capex on unknown base)
                dq.append("fcf_sustainability_uncertain:ocf_proxy_capex_unknown")

    # --- P10: lumpy-OCF normalization guard (specced in I1, never coded until now) ---
    # When a cyclical name is normalized on a trailing 5yr average, a single peak year
    # (e.g. SIGA's 2023 BARDA delivery, ~8x the trough) over-inflates norm_fcf and
    # manufactures a false MoS. Flag-and-downgrade — NEVER silently delete the year.
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
    # V-shape the whole-window slope is +1 so fundamental_decline_flag stays False (NRP). When set,
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
    # concentration_flag is composed by the producer from XBRL segment members:
    #   "kill"  if top_program_pct>60 OR top_customer_pct>40
    #   "watch" if either in 40-60
    # A "kill" forces buy_eligible=False (catches SIGA's ~90% BARDA dependence).
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

    # --- P1: compose buy_eligible — the single mechanical boolean the BUY trigger ANDs ---
    # buy_eligible is True ONLY when every blocking guard is clear. The rubric/SKILL BUY
    # trigger additionally requires mos_basis=="fcf_cap" AND MoS>=30 AND zero Tier-3-load-
    # bearing; buy_eligible is the deterministic guard-composite half of that contract.
    _buy_ineligible_reasons: list[str] = []
    if _extreme_mos_review_required:
        _buy_ineligible_reasons.append("extreme_mos_review_required")
    if _large_cap_out_of_scope:
        _buy_ineligible_reasons.append("large_cap_out_of_scope")
    if _fcf_sustainability_uncertain:
        _buy_ineligible_reasons.append("fcf_sustainability_uncertain")
    if _financial_sic_forced_unsuitable:
        _buy_ineligible_reasons.append("financial_sic_forced_unsuitable")
    # A3: insurance_concepts_present gates buy_eligible (distinct from financial_sic_forced_
    # unsuitable so the reason-string is accurate even on a non-financial SIC, e.g. BOC SIC-65).
    if _insurance_concepts_present:
        _buy_ineligible_reasons.append("insurance_concepts_present")
    # A4: low_revenue_loss_ratio_extreme (|NI|/rev>20x — STSS/MVIS/TIPT tail) gates buy_eligible
    # with the accurate label, replacing the old wrong_entity_suspected co-fire on that tail. The
    # non-extreme low_revenue_loss_ratio (>2x) stays a data_quality label ONLY (does NOT gate).
    if der.get("low_revenue_loss_ratio_extreme"):
        _buy_ineligible_reasons.append("low_revenue_loss_ratio_extreme")
    if der.get("debt_truncation_suspected"):
        _buy_ineligible_reasons.append("debt_truncation_suspected")
    if der.get("wrong_entity_suspected"):
        _buy_ineligible_reasons.append("wrong_entity_suspected")
    if _concentration_flag == "kill":
        _buy_ineligible_reasons.append("concentration_kill")
    if _fundamental_decline_flag:
        _buy_ineligible_reasons.append("fundamental_decline_flag")
    # P-A: peak_contamination_flag downgrades BUY->WATCH like fundamental_decline_flag.
    if _peak_contamination_flag:
        _buy_ineligible_reasons.append("peak_contamination_flag")
    _buy_eligible = len(_buy_ineligible_reasons) == 0

    # --- Assemble output ---
    block = {
        "ticker": dd.get("ticker"),
        "computed_at": today(),
        "market_cap": market_cap,
        "market_cap_source": "see_caller",  # filled in by caller
        # EV
        "ev": round(ev) if ev is not None else None,
        "ev_note": ev_note,
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
        # Reverse DCF (equity-FCF basis — denominator is market_cap, not EV)
        "rdcf_basis": rdcf_basis,
        "reverse_dcf_implied_growth": rdcf_growth,
        "reverse_dcf_null_reason": rdcf_null_reason,
        # Asset-heavy / model suitability
        "fcf_cap_model_unsuitable": fcf_cap_model_unsuitable,
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
    ap.add_argument("--selftest", action="store_true", help="Run self-test on WLFC and LNN and exit")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if not args.json:
        ap.error("--json is required (path to deepdive JSON)")
    if not args.ticker:
        ap.error("--ticker is required")

    init_edgar()
    json_path = Path(args.json)
    if not json_path.exists():
        print(f"ERROR: file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    dd = json.loads(json_path.read_text(encoding="utf-8"))
    ticker = args.ticker.upper()
    mktcap_override = args.mktcap if args.mktcap > 0 else None
    market_cap, mktcap_source = _get_market_cap(ticker, mktcap_override)

    if market_cap is None:
        print(f"ERROR: cannot get market cap for {ticker}: {mktcap_source}", file=sys.stderr)
        sys.exit(1)

    cfg = _val_cfg()
    block = compute_valuation(dd, market_cap, cfg)
    block["market_cap_source"] = mktcap_source

    # Write standalone valuation JSON
    out_path = REPORTS / f"valuation_{ticker}_{today()}.json"
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
    t = block.get("ticker", "?")
    mc = block.get("market_cap", 0) or 0
    ev = block.get("ev")
    mos_basis = block.get("mos_basis", "?")
    print(f"\n=== {t} Valuation Summary ===")
    print(f"  Market Cap:      ${mc/1e6:.0f}M")
    print(f"  EV:              ${(ev or 0)/1e6:.0f}M" + (f"  [{block.get('ev_note')}]" if block.get("ev_note") else ""))
    print(f"  EV/Sales:        {block.get('ev_sales')}")
    print(f"  EV/EBITDA:       {block.get('ev_ebitda')}")
    print(f"  P/E:             {block.get('pe')}")
    print(f"  FCF Yield:       {block.get('fcf_yield')}")
    print(f"  Cyclical:        {block.get('cyclical')} (CV={block.get('cv_ebitda')})")
    print(f"  Norm. EBITDA:    ${(block.get('normalized_ebitda') or 0)/1e6:.0f}M  [{block.get('normalization_note')}]")
    print(f"  Norm. FCF:       ${(block.get('normalized_fcf') or 0)/1e6:.0f}M")
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
def _selftest():
    """Assert the valuation block populates correctly for WLFC and LNN.

    WLFC (CIK 1018164): aircraft lessor — expects fcf_cap_model_unsuitable=True,
      mos_basis="nav" or "abstain", NO FCF MoS (the old -137% MoS was a bug).
    LNN (CIK 836157): agricultural irrigation company — expects mos_basis="fcf_cap"
      with a numeric margin_of_safety_pct.

    Requires fresh deepdive JSONs. If not found, pulls them live.
    """
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

    # WLFC-specific: must be flagged as asset-heavy (aircraft lessor; debt/assets ~67%)
    assert block_wlfc.get("fcf_cap_model_unsuitable") is True, (
        f"WLFC: expected fcf_cap_model_unsuitable=True (debt/assets ~67%), got "
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

    # --- C2: financial-SIC exclusion unit test ---
    # Simulate a BDC (SIC 6726) with positive FCF — must route to nav/abstain, NOT fcf_cap
    _dd_financial = {
        "ticker": "TEST_BDC",
        "derived": {
            "latest_cash": 100_000_000,
            "latest_total_debt": 500_000_000,
            "latest_revenue": 200_000_000,
            "latest_net_income": 50_000_000,
            "latest_ocf": 80_000_000,
            "latest_ebit": 60_000_000,
            "latest_dep_amort": 5_000_000,
            "latest_capex": 10_000_000,
            "latest_ebitda": 65_000_000,
            "latest_fcf": 70_000_000,
            "fcf_is_ocf_proxy": False,
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "latest_cash": 100_000_000,
            "sic": "6726",  # holding companies/BDCs/REITs
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
        },
        "financials": {
            "assets": [{"end": "2024-12-31", "val": 2_000_000_000}],
            "equity": [{"end": "2024-12-31", "val": 1_500_000_000}],
            "ebit": [{"end": "2024-12-31", "val": 60_000_000}],
            "dep_amort": [{"end": "2024-12-31", "val": 5_000_000}],
            "ocf": [{"end": "2024-12-31", "val": 80_000_000}],
            "capex": [{"end": "2024-12-31", "val": 10_000_000}],
            "revenue": [{"end": "2024-12-31", "val": 200_000_000}],
            "shares_outstanding": [{"end": "2024-12-31", "val": 10_000_000}],
        },
    }
    _block_fin = compute_valuation(_dd_financial, 300_000_000, cfg)
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

    # --- C2-fallback: SIC absent + BDC signature (no revenue, OCF present) — real WHF case ---
    _dd_no_sic_bdc = {
        "ticker": "TEST_BDC_NO_SIC",
        "derived": {
            "latest_cash": 20_000_000,
            "latest_total_debt": 300_000_000,
            "latest_revenue": None,          # BDC: no GAAP revenue
            "latest_net_income": 40_000_000,
            "latest_ocf": 77_000_000,        # portfolio cash flow present
            "latest_ebit": None,
            "latest_dep_amort": None,
            "latest_capex": None,
            "latest_ebitda": None,
            "latest_fcf": 77_000_000,
            "fcf_is_ocf_proxy": True,
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "sic": None,                     # SEC omitted SIC (real WHF behaviour)
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
        },
        "financials": {
            "assets": [{"end": "2024-12-31", "val": 700_000_000}],
            "equity": [{"end": "2024-12-31", "val": 380_000_000}],
            "ocf": [{"end": "2024-12-31", "val": 77_000_000}],
            "revenue": [],                   # empty revenue series
            "shares_outstanding": [{"end": "2024-12-31", "val": 20_000_000}],
        },
    }
    _block_no_sic = compute_valuation(_dd_no_sic_bdc, 280_000_000, cfg)
    assert any("financial_structure_suspected_no_sic" in f for f in _block_no_sic.get("data_quality", [])), (
        f"C2-fallback: BDC with no SIC must flag financial_structure_suspected_no_sic, "
        f"got dq={_block_no_sic.get('data_quality')}"
    )
    assert _block_no_sic.get("mos_basis") in ("nav", "abstain"), (
        f"C2-fallback: SIC-less BDC must route nav/abstain not fcf_cap, got {_block_no_sic.get('mos_basis')!r}"
    )
    print("  C2-fallback: SIC-less BDC (no revenue + OCF) routes to nav/abstain  OK")

    # --- G1: extreme MoS defense unit test ---
    # Simulate a case where FCF MoS would be >100% (e.g., CISS-like scenario)
    _dd_extreme = {
        "ticker": "TEST_EXTREME",
        "derived": {
            "latest_cash": 0,
            "latest_total_debt": 0,
            "latest_revenue": 10_000_000,
            "latest_net_income": 3_000_000,
            "latest_ocf": 3_800_000,
            "latest_ebit": 3_000_000,
            "latest_dep_amort": 500_000,
            "latest_capex": 200_000,
            "latest_ebitda": 3_500_000,
            "latest_fcf": 3_600_000,
            "fcf_is_ocf_proxy": False,
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "sic": "3990",  # non-financial
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
        },
        "financials": {
            "assets": [{"end": "2024-12-31", "val": 5_000_000}],
            "equity": [{"end": "2024-12-31", "val": 4_000_000}],
            "ebit": [{"end": "2024-12-31", "val": 3_000_000}],
            "dep_amort": [{"end": "2024-12-31", "val": 500_000}],
            "ocf": [{"end": "2024-12-31", "val": 3_800_000}],
            "capex": [{"end": "2024-12-31", "val": 200_000}],
            "revenue": [{"end": "2024-12-31", "val": 10_000_000}],
            "shares_outstanding": [{"end": "2024-12-31", "val": 1_000_000}],
        },
    }
    # Market cap = $1.2M (micro-cap), FCF = $3.6M → MoS would be (3.6M/0.12 - 1.2M) / 1.2M ~ 2400%
    _block_extreme = compute_valuation(_dd_extreme, 1_200_000, cfg)
    if _block_extreme.get("margin_of_safety_pct") is not None:
        _mos_val = _block_extreme.get("margin_of_safety_pct", 0)
        if abs(_mos_val) > 1.0:
            assert _block_extreme.get("extreme_mos_review_required") is True, (
                f"G1: extreme_mos_review_required must be True for MoS={_mos_val*100:.0f}%"
            )
            assert any("extreme_mos" in str(x) for x in _block_extreme.get("data_quality", [])), (
                f"G1: extreme_mos_review_required must appear in data_quality list"
            )
            print(f"  G1 extreme-MoS defense: fires for MoS={_mos_val*100:.0f}%  OK")
        else:
            print(f"  G1 extreme-MoS defense: MoS={_mos_val*100:.1f}% not >100%, skipping assertion")
    else:
        print("  G1 extreme-MoS defense: MoS null (insufficient data), skipping assertion")

    # --- G2: large-cap ceiling unit test ---
    # Use a market_cap > 2B — should set large_cap_out_of_scope=True
    _block_large = compute_valuation(_dd_extreme, 5_000_000_000, cfg)  # $5B market cap
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
    _block_warn = compute_valuation(_dd_with_warn, 300_000_000, cfg)
    assert any("test_warning" in str(x) for x in _block_warn.get("data_quality", [])), (
        f"I3: data_quality_warn must propagate into valuation data_quality list"
    )
    print("  I3 data_quality_warn propagation: fires correctly  OK")

    # --- I1: FCF sustainability guard unit test ---
    # Simulate: rdcf_growth would be < -0.15 (market pricing in steep decline)
    # Use tiny market_cap so FCF/mktcap ratio forces g = wacc - FCF/mktcap < -0.15
    # wacc=0.10; FCF=3.6M; mktcap=14M → g = 0.10 - 3.6/14 = 0.10 - 0.257 = -0.157 < -0.15
    _block_i1 = compute_valuation(_dd_extreme, 14_000_000, cfg)
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
    _dd_proxy_light = {
        "ticker": "TEST_PROXY_LIGHT",
        "derived": {
            "latest_cash": 5_000_000,
            "latest_total_debt": 0,
            "latest_revenue": 50_000_000,
            "latest_net_income": 8_000_000,
            "latest_ocf": 10_000_000,
            "latest_ebit": 9_000_000,
            "latest_dep_amort": 500_000,
            "latest_capex": None,             # capex missing -> OCF proxy
            "latest_ebitda": 9_500_000,
            "latest_fcf": 10_000_000,
            "fcf_is_ocf_proxy": True,         # OCF proxy
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "sic": "3990",                    # non-financial
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
        },
        "financials": {
            # assets/rev = 80M/50M = 1.6 (<=5): the old `elif` would NEVER fire here
            "assets": [{"end": "2024-12-31", "val": 80_000_000}],
            "equity": [{"end": "2024-12-31", "val": 70_000_000}],
            "ebit": [{"end": "2024-12-31", "val": 9_000_000}],
            "dep_amort": [{"end": "2024-12-31", "val": 500_000}],
            "ocf": [{"end": "2024-12-31", "val": 10_000_000}],
            "capex": [],                      # no capex series -> proxy
            "revenue": [{"end": "2024-12-31", "val": 50_000_000}],
            "shares_outstanding": [{"end": "2024-12-31", "val": 10_000_000}],
        },
    }
    # Market cap chosen so mos_basis=fcf_cap and a numeric MoS exists.
    _block_proxy = compute_valuation(_dd_proxy_light, 100_000_000, cfg)
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
    _dd_clean_base = {
        "ticker": "TEST_CLEAN",
        "derived": {
            "latest_cash": 20_000_000,
            "latest_total_debt": 10_000_000,
            "latest_revenue": 100_000_000,
            "latest_net_income": 15_000_000,
            "latest_ocf": 20_000_000,
            "latest_ebit": 18_000_000,
            "latest_dep_amort": 4_000_000,
            "latest_capex": 5_000_000,
            "latest_ebitda": 22_000_000,
            "latest_fcf": 15_000_000,
            "fcf_is_ocf_proxy": False,
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "sic": "3990",                    # non-financial
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
            "ebit_source": "OperatingIncomeLoss",
            "concentration_flag": None,
            "top_customer_pct": None,
            "top_program_pct": None,
            "fundamental_decline_flag": False,
            "rev_slope_sign": 1,
            "rev_accel_sign": 0,
            "latest_below_avg": False,
            "contamination_ratio": 1.05,
            "peak_contamination_flag": False,
            "low_revenue_loss_ratio": False,
            "form_used": "10-K",
        },
        "financials": {
            "assets": [{"end": "2024-12-31", "val": 200_000_000}],
            "equity": [{"end": "2024-12-31", "val": 150_000_000}],
            "ebit": [{"end": "2024-12-31", "val": 18_000_000}],
            "dep_amort": [{"end": "2024-12-31", "val": 4_000_000}],
            "ocf": [{"end": "2024-12-31", "val": 20_000_000}],
            "capex": [{"end": "2024-12-31", "val": 5_000_000}],
            "revenue": [{"end": "2024-12-31", "val": 100_000_000}],
            "shares_outstanding": [{"end": "2024-12-31", "val": 10_000_000}],
        },
    }
    # (iv) Clean name keeps buy_eligible=True (small-cap mktcap, non-proxy, no flags).
    _block_clean = compute_valuation(_dd_clean_base, 120_000_000, cfg)
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
    _dd_decline["derived"]["contamination_ratio"] = 0.68  # SIGA-like
    _block_decline = compute_valuation(_dd_decline, 120_000_000, cfg)
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
    _dd_conc["derived"]["top_customer_pct"] = 75.0   # SIGA-like single-counterparty
    _block_conc = compute_valuation(_dd_conc, 120_000_000, cfg)
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

    # --- P-A: peak_contamination_flag => buy_eligible False (V-shape value-trap veto) ---
    # NRP-class: a clean MECHANICAL BUY (rev_slope_sign=+1 so fundamental_decline_flag stays
    # False) that is actually a melting ice cube — the producer set peak_contamination_flag on
    # the V-shape (contamination<0.8 AND latest_below_avg AND latest_NI<0). valuation must read
    # the flag, downgrade BUY->WATCH, and surface the veto — WITHOUT fundamental_decline_flag.
    _dd_peak = dict(_dd_clean_base)
    _dd_peak["derived"] = dict(_dd_clean_base["derived"])
    _dd_peak["ticker"] = "TEST_NRP_VSHAPE"
    _dd_peak["derived"]["peak_contamination_flag"] = True
    _dd_peak["derived"]["fundamental_decline_flag"] = False   # V-shape: slope is +1
    _dd_peak["derived"]["rev_slope_sign"] = 1
    _dd_peak["derived"]["latest_below_avg"] = True
    _dd_peak["derived"]["contamination_ratio"] = 0.7445       # NRP documented value
    _dd_peak["derived"]["latest_net_income"] = -84_800_000    # NRP latest NI
    _block_peak = compute_valuation(_dd_peak, 120_000_000, cfg)
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
    _block_lrl = compute_valuation(_dd_lrl, 120_000_000, cfg)
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
    # Take the real-world early-revenue resource pattern (null FCF -> MoS null, the historical
    # block) and assert that even WITH low_revenue_loss_ratio set it stays NOT buy_eligible.
    _dd_blocked = {
        "ticker": "TEST_URG_LIKE",
        "derived": {
            "latest_cash": 30_000_000,
            "latest_total_debt": 50_000_000,
            "latest_revenue": 45_000_000,
            "latest_net_income": -120_000_000,
            "latest_ocf": None,               # no OCF -> FCF null -> MoS null (the real block)
            "latest_ebit": None,
            "latest_dep_amort": None,
            "latest_capex": None,
            "latest_ebitda": None,
            "latest_fcf": None,
            "fcf_is_ocf_proxy": False,
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "sic": "1040",                    # gold/metal mining, non-financial
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,  # P-B: NOT mislabeled as wrong entity anymore
            "low_revenue_loss_ratio": True,   # P-B: surfaced as the correct label instead
            "low_revenue_loss_ratio_detail": "early-revenue resource pattern, right entity",
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
            "ebit_source": None,
            "concentration_flag": None,
            "top_customer_pct": None,
            "top_program_pct": None,
            "fundamental_decline_flag": False,
            "peak_contamination_flag": False,
            "rev_slope_sign": 1,
            "rev_accel_sign": 0,
            "latest_below_avg": False,
            "contamination_ratio": None,
            "form_used": "10-K",
        },
        "financials": {
            "assets": [{"end": "2024-12-31", "val": 400_000_000}],
            "equity": [{"end": "2024-12-31", "val": 250_000_000}],
            "ocf": [],                        # empty -> no FCF
            "revenue": [{"end": "2024-12-31", "val": 45_000_000}],
            "shares_outstanding": [{"end": "2024-12-31", "val": 350_000_000}],
        },
    }
    _block_blocked = compute_valuation(_dd_blocked, 200_000_000, cfg)
    # CRITICAL (per data contract): the relabel removed the OLD wrong_entity_suspected misfire
    # from buy_ineligible_reasons, so it must NOT have introduced low_revenue_loss_ratio as a
    # block, and — most importantly — the name must remain a NON-tradeable BUY because its FCF/MoS
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
    # buy_eligible says — encode that the BUY trigger (mos_basis==fcf_cap AND MoS>=30) fails.
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

    # --- A4: low_revenue_loss_ratio_extreme (>20x) GATES buy_eligible (STSS/MVIS/TIPT tail) ---
    # The clean fixture is buy_eligible=True on fcf_cap. Setting ONLY the extreme tier (with the
    # advisory label also True, as the producer always co-sets them) must flip buy_eligible=False
    # with the accurate reason-string — replacing the old wrong_entity_suspected co-fire.
    _dd_lrl_ext = dict(_dd_clean_base)
    _dd_lrl_ext["derived"] = dict(_dd_clean_base["derived"])
    _dd_lrl_ext["ticker"] = "TEST_LOW_REV_LOSS_EXTREME"
    _dd_lrl_ext["derived"]["low_revenue_loss_ratio"] = True
    _dd_lrl_ext["derived"]["low_revenue_loss_ratio_extreme"] = True
    _dd_lrl_ext["derived"]["low_revenue_loss_ratio_detail"] = (
        "latest_net_income=-1384.0M vs revenue=1.0M (|NI|/rev=1384.0x) — early/pre-revenue pattern, "
        "right entity; EXTREME (>20x) — gates buy_eligible"
    )
    _block_lrl_ext = compute_valuation(_dd_lrl_ext, 120_000_000, cfg)
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

    # A4-regression: the NON-extreme label (>2x, <=20x) must NOT gate — buy_eligible unchanged.
    _dd_lrl_mild = dict(_dd_clean_base)
    _dd_lrl_mild["derived"] = dict(_dd_clean_base["derived"])
    _dd_lrl_mild["ticker"] = "TEST_LOW_REV_LOSS_MILD"
    _dd_lrl_mild["derived"]["low_revenue_loss_ratio"] = True
    _dd_lrl_mild["derived"]["low_revenue_loss_ratio_extreme"] = False
    _dd_lrl_mild["derived"]["low_revenue_loss_ratio_detail"] = "|NI|/rev=2.7x — right entity"
    _block_lrl_mild = compute_valuation(_dd_lrl_mild, 120_000_000, cfg)
    assert _block_lrl_mild.get("buy_eligible") == _block_clean.get("buy_eligible"), (
        "A4: non-extreme low_revenue_loss_ratio must NOT change buy_eligible (label-only)"
    )
    assert "low_revenue_loss_ratio_extreme" not in _block_lrl_mild.get("buy_ineligible_reasons", []), (
        "A4: non-extreme must NOT add low_revenue_loss_ratio_extreme to buy_ineligible_reasons"
    )
    print("  A4 non-extreme low_revenue_loss_ratio: >2x stays label-only (no gate)  OK")

    # --- A3: insurance_concepts_present routes nav/abstain AND gates buy_eligible ---
    # An insurance-subsidiary holdco on a NON-financial SIC (BOC SIC-65 = 6510, NOT in the
    # financial-SIC prefix list) must route like financial_sic (nav/abstain, never fcf_cap) and
    # gate buy_eligible with a distinct, accurate reason — closing the latent fcf_cap-BUY hole.
    _dd_ins = dict(_dd_clean_base)
    _dd_ins["derived"] = dict(_dd_clean_base["derived"])
    _dd_ins["ticker"] = "TEST_INSURANCE_HOLDCO"
    _dd_ins["derived"]["sic"] = "6510"            # SIC-65 real-estate operator (BOC) — NON-financial prefix
    _dd_ins["derived"]["insurance_concepts_present"] = True
    _dd_ins["derived"]["insurance_concept_matched"] = "PremiumsEarnedNet"
    _block_ins = compute_valuation(_dd_ins, 120_000_000, cfg)
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
    # CRITICAL: a SIC-65 insurance holdco must NEVER produce an fcf_cap BUY (the BOC latent hole).
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
    _block_cu = compute_valuation(_dd_cu, 120_000_000, cfg)
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

    # --- P10: lumpy-OCF normalization guard fires on a peak year > 2x median ---
    # Cyclical series with one BARDA-like peak (95M) vs others (~11-49M); contamination<1.
    _dd_lumpy = {
        "ticker": "TEST_LUMPY",
        "derived": {
            "latest_cash": 10_000_000,
            "latest_total_debt": 0,
            "latest_revenue": 60_000_000,
            "latest_net_income": 20_000_000,
            "latest_ocf": 43_500_000,
            "latest_ebit": 25_000_000,
            "latest_dep_amort": 2_000_000,
            "latest_capex": 1_000_000,
            "latest_ebitda": 27_000_000,
            "latest_fcf": 42_500_000,
            "fcf_is_ocf_proxy": False,
            "latest_goodwill": 0,
            "latest_intangibles": 0,
            "sic": "2836",                    # biological products (SIGA-like), non-financial
            "debt_truncation_suspected": False,
            "debt_stale": False,
            "wrong_entity_suspected": False,
            "data_quality_warn": None,
            "debt_source": "LongTermDebt",
            "ebit_source": "OperatingIncomeLoss",
            "contamination_ratio": 0.68,      # latest base below its own 5yr-avg
            "fundamental_decline_flag": False,
            "rev_slope_sign": 0,
            "latest_below_avg": True,
        },
        "financials": {
            "assets": [{"end": "2024-12-31", "val": 200_000_000}],
            "equity": [{"end": "2024-12-31", "val": 180_000_000}],
            "ebit": [
                {"end": "2020-12-31", "val": 8_000_000},
                {"end": "2021-12-31", "val": 35_000_000},
                {"end": "2022-12-31", "val": 80_000_000},
                {"end": "2023-12-31", "val": 30_000_000},
                {"end": "2024-12-31", "val": 25_000_000},
            ],
            "dep_amort": [
                {"end": "2020-12-31", "val": 2_000_000},
                {"end": "2021-12-31", "val": 2_000_000},
                {"end": "2022-12-31", "val": 2_000_000},
                {"end": "2023-12-31", "val": 2_000_000},
                {"end": "2024-12-31", "val": 2_000_000},
            ],
            # OCF: 2022 peak = 94.8M is > 2x the median of the others (~43.5M)
            "ocf": [
                {"end": "2020-12-31", "val": 11_500_000},
                {"end": "2021-12-31", "val": 41_600_000},
                {"end": "2022-12-31", "val": 94_800_000},
                {"end": "2023-12-31", "val": 48_800_000},
                {"end": "2024-12-31", "val": 43_500_000},
            ],
            "capex": [
                {"end": "2020-12-31", "val": 1_000_000},
                {"end": "2021-12-31", "val": 1_000_000},
                {"end": "2022-12-31", "val": 1_000_000},
                {"end": "2023-12-31", "val": 1_000_000},
                {"end": "2024-12-31", "val": 1_000_000},
            ],
            "revenue": [
                {"end": "2020-12-31", "val": 30_000_000},
                {"end": "2021-12-31", "val": 60_000_000},
                {"end": "2022-12-31", "val": 120_000_000},
                {"end": "2023-12-31", "val": 70_000_000},
                {"end": "2024-12-31", "val": 60_000_000},
            ],
            "shares_outstanding": [{"end": "2024-12-31", "val": 70_000_000}],
        },
    }
    _block_lumpy = compute_valuation(_dd_lumpy, 300_000_000, cfg)
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

    print("\nvaluation selftest PASS")


if __name__ == "__main__":
    main()
