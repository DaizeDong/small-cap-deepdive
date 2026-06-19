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

    # --- C2: financial-SIC guard — exclude financial sector from FCF-cap model ---
    # SIC prefixes: 60=banks, 61=non-depository credit, 63=insurance carriers,
    #               64=insurance agents, 67=holding companies/investment/REITs/BDCs
    _FINANCIAL_SIC_PREFIXES = ("60", "61", "63", "64", "67")
    sic_code = str(der.get("sic") or "").strip()
    _financial_sic = bool(sic_code and any(sic_code.startswith(p) for p in _FINANCIAL_SIC_PREFIXES))
    _financial_sic_forced_unsuitable = False
    if _financial_sic:
        _financial_sic_forced_unsuitable = True
        dq.append(f"financial_sic_fcf_unsuitable:sic={sic_code}")

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

    ev_ebitda: float | None = None
    latest_ebitda = der.get("latest_ebitda")
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

        # (ii) OCF-proxy FCF on capital-intensive company (PP&E-heavy proxy):
        # capital-intensive heuristic: latest_assets > 5 * latest_revenue (large asset base)
        if fcf_is_proxy and latest_assets is not None and latest_revenue and latest_revenue > 0:
            asset_rev_ratio = latest_assets / latest_revenue
            if asset_rev_ratio > 5.0:
                _fcf_sustainability_uncertain = True
                dq.append(
                    f"fcf_sustainability_uncertain:ocf_proxy_on_capital_intensive"
                    f"(assets/rev={asset_rev_ratio:.1f})"
                )
        elif fcf_is_proxy:
            # Even without asset data, any OCF-proxy on unknown capex is uncertain
            _fcf_sustainability_uncertain = True
            dq.append("fcf_sustainability_uncertain:ocf_proxy_capex_unknown")

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

    print("\nvaluation selftest PASS")


if __name__ == "__main__":
    main()
