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
import time
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


def _build_ebitda_series(ebit_series: list[dict], da_series: list[dict]) -> list[dict]:
    """Construct year-by-year EBITDA series from EBIT and D&A series (matched by end date).

    For dates with only one component, that component is used alone (partial EBITDA).
    The result is sorted by end date.
    """
    ebit_map = {v["end"]: v["val"] for v in ebit_series}
    da_map = {v["end"]: v["val"] for v in da_series}
    all_ends = sorted(set(ebit_map) | set(da_map))
    result = []
    for end in all_ends:
        e = ebit_map.get(end)
        d = da_map.get(end)
        if e is not None and d is not None:
            result.append({"end": end, "val": e + d})
        elif e is not None:
            result.append({"end": end, "val": e})  # no D&A for this year
        elif d is not None:
            result.append({"end": end, "val": d})  # no EBIT for this year (unusual)
    return result


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
      reverse_dcf_implied_growth,
      intrinsic_value_band (low/high equity and per-share),
      margin_of_safety_pct,
      assumptions, data_quality, computed_at.
    """
    fin = dd.get("financials", {})
    der = dd.get("derived", {})
    dq: list[str] = []  # data_quality flags

    wacc = cfg["wacc"]
    cap_low = cfg["cap_rate_low"]    # low cap rate → high value
    cap_high = cfg["cap_rate_high"]  # high cap rate → low value
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

    # Build EBITDA series for normalization
    ebitda_series = _build_ebitda_series(ebit_series, da_series)

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
    else:
        norm_ebitda = latest_ebitda
        norm_fcf = latest_fcf
        fcf_proxy_flag = fcf_is_proxy
        norm_note = "non_cyclical:latest"

    if norm_ebitda is None:
        dq.append("normalized_ebitda_unavailable")
    if norm_fcf is None:
        dq.append("normalized_fcf_unavailable")

    # --- Reverse DCF (Gordon growth approximation) ---
    # g = wacc - normalized_fcf / EV
    # Guard: EV <=0 or normalized_fcf <=0 or EV is None → null with reason
    rdcf_growth: float | None = None
    rdcf_null_reason: str | None = None
    if ev is None or ev <= 0:
        rdcf_null_reason = "ev_nonpositive"
    elif norm_fcf is None:
        rdcf_null_reason = "normalized_fcf_unavailable"
    elif norm_fcf <= 0:
        rdcf_null_reason = "normalized_fcf_nonpositive"
    else:
        g = wacc - (norm_fcf / ev)
        rdcf_growth = round(g, 4)
        if rdcf_growth < -0.20:
            dq.append("rdcf_implied_growth_very_negative:market_pricing_in_decline")
        elif rdcf_growth > 0.20:
            dq.append("rdcf_implied_growth_very_high:market_pricing_in_high_growth")

    # --- Intrinsic value band ---
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
        # Enterprise value from FCF
        ev_implied_low = norm_fcf / cap_high   # high cap rate → low EV
        ev_implied_high = norm_fcf / cap_low   # low cap rate → high EV
        # Convert EV → equity (subtract net debt; if unavailable use 0)
        nd = net_debt if net_debt is not None else 0
        eq_low = ev_implied_low - nd
        eq_high = ev_implied_high - nd
        # Per-share
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

    # --- Margin of safety ---
    # MoS = (intrinsic_low_equity - market_cap) / market_cap
    # Positive = cheap vs CONSERVATIVE intrinsic low end
    mos: float | None = None
    if iv_band is not None and market_cap > 0:
        mos = round((iv_band["equity_low"] - market_cap) / market_cap, 4)

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
        # Reverse DCF
        "reverse_dcf_implied_growth": rdcf_growth,
        "reverse_dcf_null_reason": rdcf_null_reason,
        # Intrinsic value band
        "intrinsic_value_band": iv_band,
        # Margin of safety
        "margin_of_safety_pct": mos,
        # Transparency
        "assumptions": {
            "wacc": wacc,
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
    print(f"  Reverse DCF g:   {rdcf if rdcf is not None else f'null ({rdcf_reason})'}")
    iv = block.get("intrinsic_value_band")
    if iv:
        print(f"  Intrinsic Band:  ${iv['equity_low']/1e6:.0f}M - ${iv['equity_high']/1e6:.0f}M equity")
        if iv.get("per_share_low") is not None:
            print(f"                   ${iv['per_share_low']:.2f} - ${iv['per_share_high']:.2f} per share")
    else:
        print(f"  Intrinsic Band:  null")
    mos = block.get("margin_of_safety_pct")
    print(f"  Margin of Safety: {f'{mos*100:.1f}%' if mos is not None else 'null'}")
    dq = block.get("data_quality", [])
    if dq:
        print(f"  Data Quality:    {dq}")
    print()


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------
def _selftest():
    """Assert the valuation block populates correctly for WLFC and LNN.

    WLFC (CIK 1018164): a run-3 "cheap" suspect; expects high/positive MoS.
    LNN (CIK 836157): agricultural irrigation company.

    Requires fresh deepdive JSONs. If not found, pulls them live.
    """
    init_edgar()
    cfg = _val_cfg()

    def _get_or_pull(ticker: str, cik: str) -> dict:
        """Get latest deepdive JSON for ticker, pulling fresh if needed."""
        # Find latest existing deepdive JSON
        candidates = sorted(REPORTS.glob(f"deepdive_{ticker}_*.json"), reverse=True)
        if candidates:
            dd = json.loads(candidates[0].read_text(encoding="utf-8"))
            # Check it has Phase 2 fields
            if dd.get("financials", {}).get("ebit") is not None:
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

        # Core assertions
        ev = block.get("ev")
        assert ev is not None and ev > 0, f"{ticker}: ev must be >0, got {ev}"

        ev_ebitda = block.get("ev_ebitda")
        assert ev_ebitda is None or ev_ebitda > 0, (
            f"{ticker}: ev_ebitda must be positive or null, got {ev_ebitda}"
        )

        rdcf = block.get("reverse_dcf_implied_growth")
        rdcf_reason = block.get("reverse_dcf_null_reason")
        assert rdcf is not None or rdcf_reason is not None, (
            f"{ticker}: reverse_dcf must be float or have null_reason"
        )
        assert rdcf is None or isinstance(rdcf, float), (
            f"{ticker}: reverse_dcf_implied_growth must be float or None, got {type(rdcf)}"
        )

        iv = block.get("intrinsic_value_band")
        if iv is not None:
            assert iv["equity_low"] < iv["equity_high"], (
                f"{ticker}: intrinsic band low must be < high: {iv['equity_low']} vs {iv['equity_high']}"
            )

        mos = block.get("margin_of_safety_pct")
        if iv is not None:
            assert mos is not None and isinstance(mos, float), (
                f"{ticker}: margin_of_safety_pct must be float when band is available, got {mos}"
            )

        return block

    # --- WLFC ---
    print("  Testing WLFC (CIK 1018164)...")
    dd_wlfc = _get_or_pull("WLFC", "1018164")
    block_wlfc = _assert_valuation("WLFC", "1018164", dd_wlfc)
    print(f"  WLFC assertions PASS")
    print("\n--- WLFC Full Valuation Block ---")
    print(json.dumps(block_wlfc, indent=2))
    print("--- End WLFC Valuation Block ---\n")

    # Write WLFC valuation to disk
    out_wlfc = REPORTS / f"valuation_WLFC_{today()}.json"
    out_wlfc.write_text(json.dumps(block_wlfc, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- LNN ---
    print("  Testing LNN (CIK 836157)...")
    dd_lnn = _get_or_pull("LNN", "836157")
    block_lnn = _assert_valuation("LNN", "836157", dd_lnn)
    print(f"  LNN assertions PASS")

    # Write LNN valuation to disk
    out_lnn = REPORTS / f"valuation_LNN_{today()}.json"
    out_lnn.write_text(json.dumps(block_lnn, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nvaluation selftest PASS")


if __name__ == "__main__":
    main()
