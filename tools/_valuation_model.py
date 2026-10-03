"""
_valuation_model.py — valuation model primitives for valuation.py.

This module holds deterministic model inputs and transforms. Missing CapEx
remains explicit in the period evidence used by the valuation orchestrator:

  * config defaults + _val_cfg() merge
  * market-cap resolution (_get_market_cap)
  * cyclicality test (_coefficient_of_variation, _is_cyclical)
  * normalized-metric construction (_normalize, _build_ebitda_series, _build_fcf_series)

Import direction: this module imports _common, the pure annual-evidence helper and
stdlib. It never imports back from valuation.py. valuation.py re-exports the
public symbols below so consumers importing them from valuation keep working.
"""
from __future__ import annotations

import statistics

# sys.path shim is established by the importing orchestrator (valuation.py) which
# inserts tools/ onto sys.path before importing this module.
from _common import CFG
from _cash_flow_evidence import paired_annual_sum_evidence


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
    if "equity_discount_rate" in CFG:
        defaults["equity_discount_rate"] = float(CFG["equity_discount_rate"])
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
    """Return qualified annual EBITDA pairs and the count of rejected periods."""
    periods = paired_annual_sum_evidence(ebit_series, da_series)
    result = [{"end": row["end"], "val": row["val"]} for row in periods if row["qualified"]]
    return result, len(periods) - len(result)


def _build_fcf_series(ocf_series: list[dict], capex_series: list[dict], fcf_is_proxy: bool) -> tuple[list[dict], bool]:
    """Pair OCF and CapEx by period, retaining unknown FCF as a null value.

    The boolean marks incomplete/proxy evidence anywhere in the returned series.
    Callers selecting a shorter window must inspect the selected period records.
    Reported zero CapEx is complete; an absent observation is not zero spending.
    """
    ocf_map = {v["end"]: v["val"] for v in ocf_series}
    capex_map = {v["end"]: v["val"] for v in capex_series}
    # CapEx in XBRL PaymentsToAcquire... is stored as positive dollar outflow
    result = []
    for end in sorted(ocf_map):
        ocf_val = ocf_map[end]
        cx = capex_map.get(end)
        complete = ocf_val is not None and cx is not None and not fcf_is_proxy
        result.append({"end": end, "val": ocf_val - cx if complete else None,
                       "ocf": ocf_val, "capex": cx, "capex_complete": complete})
    return result, any(not row["capex_complete"] for row in result)
