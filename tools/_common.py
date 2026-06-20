"""Shared config/IO spine for small-cap-deepdive tools. All hardcoding lives here via config."""
from __future__ import annotations
import json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
import requests

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_REF = _REPO / "reference"

def load_config() -> dict:
    # precedence: config.json (gitignored) > config.example.json defaults; env SMALLCAP_* overrides scalars
    cfg = json.loads((_REF / "config.example.json").read_text(encoding="utf-8"))
    real = _REF / "config.json"
    if real.exists():
        cfg.update(json.loads(real.read_text(encoding="utf-8")))
    for k in list(cfg):
        env = os.environ.get("SMALLCAP_" + k.upper())
        if env is not None:
            cfg[k] = env
    return cfg

CFG = load_config()
UA = {"User-Agent": CFG["sec_user_agent"]}
# Batch runs: SMALLCAP_RUN (e.g. "2026-06-19_aginput") routes all outputs into a
# per-run subdir so each run's candidates/cheappass/deepdive/valuation/reports stay
# together and runs (and skill versions) can be compared. Unset => flat (legacy).
_RUN = os.environ.get("SMALLCAP_RUN", "").strip().strip("/\\")
REPORTS = (Path(CFG["output_dir"]) / _RUN) if _RUN else Path(CFG["output_dir"])
REPORTS.mkdir(parents=True, exist_ok=True)

def init_edgar() -> None:
    from edgar import set_identity
    set_identity(CFG["sec_user_agent"])

def slug(name: str) -> str:
    return re.sub(r"\W+", "_", str(name).lower())[:40].strip("_")

def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def http_get(url: str, params: dict | None = None, timeout: int = 25, retries: int = 4) -> requests.Response:
    last = None
    for attempt in range(retries):
        last = requests.get(url, headers=UA, params=params, timeout=timeout)
        if last.status_code in (429, 500):
            time.sleep(2 ** attempt * 1.5)
            continue
        return last
    return last


# ---------------------------------------------------------------------------
# Market-cap resolution (P5) — decouple mktcap from yfinance.
#
# yfinance market cap is null for a large fraction of small/foreign tickers,
# and the theme path used to DROP those rows (flag_no_mktcap). That silently
# discarded 91-100% of some themes before any gate (synthesis / data_robustness
# F5). The fix: a fallback chain — yfinance -> SEC companyfacts shares x price —
# and, when mktcap is still genuinely unresolvable, tag band="unknown" and let
# the row FLOW THROUGH the gates (mirroring discover_events.py:_band, which
# already keeps null as "unknown" rather than dropping pre-listing spinoffs).
# ---------------------------------------------------------------------------

_DEI_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/{concept}.json"
_GAAP_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"


def sec_shares_outstanding(cik: str | int | None) -> float | None:
    """Latest reported shares-outstanding for a CIK via SEC companyconcept.

    Free, no-key fallback for market-cap reconstruction when yfinance returns
    null. Fallback chain mirrors deepdive_data._shares_series ordering:
      1. dei:EntityCommonStockSharesOutstanding (cover-page count; most current)
      2. us-gaap:CommonStockSharesOutstanding   (period-end balance-sheet count)
    Returns the value at the latest "end" date, or None on any failure.
    """
    if cik is None or str(cik).strip() in ("", "nan"):
        return None
    cik10 = str(cik).split(".")[0].strip().zfill(10)
    for url in (
        _DEI_FACTS.format(cik=cik10, concept="EntityCommonStockSharesOutstanding"),
        _GAAP_FACTS.format(cik=cik10, concept="CommonStockSharesOutstanding"),
    ):
        try:
            r = http_get(url, timeout=20)
            if r.status_code != 200:
                continue
            units = r.json().get("units", {})
            vals = units.get("shares") or []
            dated = [v for v in vals if v.get("end") and v.get("val") is not None]
            if not dated:
                continue
            latest = max(dated, key=lambda v: v["end"])
            val = float(latest["val"])
            if val > 0:
                return val
        except Exception:
            continue
    return None


def resolve_mktcap(
    yf_mktcap: float | None,
    price: float | None,
    cik: str | int | None,
    shares_fn=sec_shares_outstanding,
) -> tuple[float | None, str]:
    """Resolve market cap via a fallback chain. Returns (mktcap, source).

    source ∈ {"yfinance", "sec_shares_x_price", "unresolved"}.
      1. yfinance marketCap (already-available free source) if positive.
      2. SEC companyfacts shares-outstanding x last price (both must be positive).
      3. unresolved -> (None, "unresolved"); caller tags band="unknown" and flows
         the row through instead of dropping it.
    shares_fn is injectable for selftest (avoids a network call).
    """
    if yf_mktcap is not None and yf_mktcap > 0:
        return float(yf_mktcap), "yfinance"
    if price is not None and price > 0:
        shares = shares_fn(cik)
        if shares is not None and shares > 0:
            return float(shares) * float(price), "sec_shares_x_price"
    return None, "unresolved"


def band_for(mktcap: float | None, max_mcap: float | None = None,
             watch_max: float | None = None) -> str:
    """Single source of truth for market-cap band tagging.

    Mirrors discover_events.py:_band so the theme path and event path agree:
      "deep"    = mktcap < max_mcap           → full deep-dive
      "watch"   = max_mcap..watch_max         → surface separately, no deep-dive
      "large"   = > watch_max                 → out of scope, no deep-dive (flag, flow through)
      "unknown" = mktcap missing/unresolvable → process (do NOT drop; flow through gates)

    Previously discover.apply_filters returned band=None for BOTH null mktcap AND
    >watch_max, and null-mktcap rows were dropped (flag_no_mktcap). null now maps
    to "unknown" and flows through; oversize maps to "large" and is flagged, not
    silently conflated with no-data.
    """
    if max_mcap is None:
        max_mcap = CFG.get("market_cap_max", 2_000_000_000)
    if watch_max is None:
        watch_max = CFG.get("watch_band_max", 5_000_000_000)
    # None / NaN (mktcap != mktcap) / non-positive => unknown (flow through, not drop).
    if mktcap is None or mktcap != mktcap or mktcap <= 0:
        return "unknown"
    if mktcap < max_mcap:
        return "deep"
    if mktcap < watch_max:
        return "watch"
    return "large"


def _selftest() -> None:
    """P5 market-cap fallback + band-tagging unit assertions."""
    # resolve_mktcap: yfinance wins when present
    mc, src = resolve_mktcap(1.5e9, 10.0, "320193", shares_fn=lambda c: 5e6)
    assert mc == 1.5e9 and src == "yfinance", f"yfinance branch: {mc},{src}"
    # resolve_mktcap: SEC shares x price fallback when yfinance null
    mc, src = resolve_mktcap(None, 10.0, "320193", shares_fn=lambda c: 5e6)
    assert mc == 5e7 and src == "sec_shares_x_price", f"sec fallback: {mc},{src}"
    # resolve_mktcap: genuinely unresolvable -> (None, "unresolved"), NOT a crash/drop
    mc, src = resolve_mktcap(None, None, "320193", shares_fn=lambda c: 5e6)
    assert mc is None and src == "unresolved", f"no-price unresolved: {mc},{src}"
    mc, src = resolve_mktcap(None, 10.0, "320193", shares_fn=lambda c: None)
    assert mc is None and src == "unresolved", f"no-shares unresolved: {mc},{src}"
    mc, src = resolve_mktcap(0, 10.0, None, shares_fn=lambda c: None)
    assert mc is None and src == "unresolved", f"zero-yf no-cik unresolved: {mc},{src}"

    # band_for: null/zero mktcap => "unknown" (flow through), NOT None (dropped)
    assert band_for(None) == "unknown", "null mktcap must band='unknown' (flow through, not drop)"
    assert band_for(0) == "unknown", "zero mktcap must band='unknown'"
    assert band_for(float("nan")) == "unknown", "NaN mktcap must band='unknown'"
    # band_for: thresholds (default $2B deep / $5B watch)
    assert band_for(1.0e9) == "deep", "1B must be 'deep'"
    assert band_for(3.0e9) == "watch", "3B must be 'watch'"
    assert band_for(8.0e9) == "large", "8B must be 'large' (out of scope, flag not drop)"
    # band_for: explicit thresholds honored
    assert band_for(1.0e9, max_mcap=5e8, watch_max=2e9) == "watch", "custom thresholds"

    print("_common selftest PASS (P5 resolve_mktcap fallback chain + band_for unknown flow-through)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="_common — shared spine. CLI supports --selftest only.")
    ap.add_argument("--selftest", action="store_true", help="Run selftest and exit")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    else:
        ap.error("_common.py is a library module; use --selftest to verify its helpers.")
