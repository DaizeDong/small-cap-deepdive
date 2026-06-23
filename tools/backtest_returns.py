"""PIT backtest returns layer (PIECE 3 of docs/backtest-2026-06/spec.md).

Free + survivorship-safe forward-return + entry-market-cap + benchmark machinery for the
point-in-time backtest harness. Three public helpers:

  * forward_return(ticker, asof, horizon_months=12)  — dividend-adjusted total return
        asof -> asof+horizon. A name that DELISTED before asof+horizon realizes to its LAST
        available close (a blown-up name lands near -100%, which is the POINT a de-risk scanner
        must be graded on avoiding). Returns None + a labeled reason when price data is genuinely
        unavailable (never fabricated).
  * mktcap_asof(ticker, asof, cik=None)              — entry market cap = price-as-of-T x PIT
        shares-outstanding (us-gaap/dei concept series filed<=asof, latest period-end). yfinance
        marketCap is a CURRENT field (look-ahead) so it is NOT used here.
  * benchmark_return(asof, horizon_months=12)        — forward_return on IWM (Russell 2000 ETF;
        the correct small-cap universe comparison, matching track_forward.DEFAULT_BENCHMARK).

ADDITIVE — nothing here touches the live latest-filing path. yfinance is called with
auto_adjust=True, so the resolved closes are split- AND dividend-adjusted (total-return basis);
matches tools/track_forward._fetch_close. A `price_fn` is injectable through every helper so the
selftest is network-free and deterministic.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

# Add tools dir to path for sibling imports (mirrors track_forward.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import resolve_mktcap  # noqa: E402  (resolve-then-band fallback chain)

DEFAULT_BENCHMARK = "IWM"   # Russell 2000 small-cap ETF — matches track_forward.DEFAULT_BENCHMARK
DEFAULT_HORIZON_MONTHS = 12
# Sub-$0.10 entry => a penny/sub-penny forward return is a data artifact, not a tradeable outcome
# (e.g. GNOLF 2024 oilsvc: entry $0.00001 -> exit $0.01 = a fake +999x that swung the raw panel mean
# by +26). Flagged status="penny_unreliable" and excluded from stats (forward_return returns None).
_MIN_ENTRY_PRICE = 0.10

# ---------------------------------------------------------------------------
# Price resolution
#
# A price_fn has the signature: price_fn(ticker, on_date) -> (price, resolved_date) | None
#   * price        : float dividend-adjusted close (total-return basis)
#   * resolved_date: "YYYY-MM-DD" of the trading day actually used (on or BEFORE on_date)
#   * None         : no price on/near on_date (delisting / data gap / un-fetchable)
# Returning the resolved_date is what lets forward_return detect a DELISTED name: when the
# exit-date request resolves to a date materially earlier than asof+horizon, the series ended
# mid-horizon (the name stopped trading) and we realize to that last close instead.
# ---------------------------------------------------------------------------


def _yf_price_fn(ticker: str, on_date: str) -> tuple[float, str] | None:
    """Default (network) price function — DIVIDEND-ADJUSTED close on/near on_date via yfinance.

    Returns (price, resolved_date) using the most recent trading day on or BEFORE on_date within
    a backward search window, or None on any failure (yfinance unavailable, ticker not found,
    delisted with no data in window, etc.). NEVER raises.

    Total-return basis: auto_adjust=True back-adjusts Close for BOTH splits AND cash dividends, so
    the returned close is the dividend-adjusted (total-return) price — identical convention to
    tools/track_forward._fetch_close. The backward window is wide (14 days) so a thinly-traded or
    near-delisting name still resolves to its last real print.
    """
    try:
        import yfinance as yf
        dt = datetime.strptime(on_date, "%Y-%m-%d")
        start = (dt - timedelta(days=14)).strftime("%Y-%m-%d")
        end = (dt + timedelta(days=2)).strftime("%Y-%m-%d")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if hist is None or hist.empty:
            return None
        # Filter to on/before on_date FIRST, then resolve Close from the filtered slice (avoids the
        # off-by-one-trading-day bug fixed in track_forward._fetch_close).
        hist_filt = hist[hist.index <= dt.strftime("%Y-%m-%d")]
        if hist_filt.empty:
            return None
        if "Close" in hist_filt.columns:
            close_col = hist_filt["Close"]
        elif "Adj Close" in hist_filt.columns:
            close_col = hist_filt["Adj Close"]
        else:
            close_col = hist_filt.iloc[:, 0]
        raw = close_col.iloc[-1]
        price = float(raw.item() if hasattr(raw, "item") else raw)
        resolved = hist_filt.index[-1]
        resolved_date = resolved.strftime("%Y-%m-%d") if hasattr(resolved, "strftime") else str(resolved)[:10]
        if price <= 0 or price != price:  # non-positive / NaN is no better than absent
            return None
        return price, resolved_date
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def _add_months(date_str: str, months: int) -> str:
    """Add `months` calendar months to a YYYY-MM-DD date (clamped to month length).

    Pure-stdlib (no dateutil; dateutil is NOT in tools/requirements.txt). 2024-02-29 + 12 ->
    2025-02-28 (clamped), 2023-08-31 + 1 -> 2023-09-30, etc.
    """
    d = datetime.strptime(date_str, "%Y-%m-%d")
    m0 = d.month - 1 + months
    year = d.year + m0 // 12
    month = m0 % 12 + 1
    # clamp day to the last valid day of the target month
    if month == 12:
        next_month_first = datetime(year + 1, 1, 1)
    else:
        next_month_first = datetime(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    day = min(d.day, last_day)
    return datetime(year, month, day).strftime("%Y-%m-%d")


def _days_between(date1: str, date2: str) -> int:
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    return (d2 - d1).days


# How many days BEFORE the requested exit date a resolved close may land before we treat the name
# as having DELISTED mid-horizon (rather than just a normal weekend/holiday gap). ~45 days covers
# the widest exchange holiday + thin-trading gaps without false-flagging a live name.
_DELIST_GAP_DAYS = 45


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def forward_return(
    ticker: str,
    asof: str,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    price_fn=_yf_price_fn,
) -> dict | None:
    """Dividend-adjusted total return for `ticker` over [asof, asof + horizon_months].

    Returns a dict:
      {
        "ticker", "asof", "target_exit_date", "horizon_months",
        "entry_date",  "entry_price",
        "exit_date",   "exit_price",
        "total_return",          # (exit/entry - 1), dividend-adjusted (total-return basis)
        "realized_to_last_close",# True iff the name delisted/stopped trading before the target
                                 #   exit date and the return was realized to its LAST close
        "status": "ok",
      }
    or None when price data is GENUINELY unavailable. The None branch is paired with a labeled
    reason via the sibling forward_return_with_reason(); this thin wrapper returns the dict-or-None
    so callers that only want the number stay simple.

    DELISTED / blown-up names: yfinance keeps a name's prints up to its last trading day, then the
    series stops. If the resolved exit-date close lands materially BEFORE the target exit date
    (> _DELIST_GAP_DAYS), the name stopped trading mid-horizon — we realize the return to that LAST
    available close and set realized_to_last_close=True. A name that fell ~99% before delisting
    therefore lands near -100%, which is exactly the outcome a de-risk scanner is graded on
    avoiding (spec: "a blown-up name lands near -100%, which is the POINT").
    """
    res = forward_return_with_reason(ticker, asof, horizon_months, price_fn=price_fn)
    if res.get("status") == "ok":
        return res
    return None


def forward_return_with_reason(
    ticker: str,
    asof: str,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    price_fn=_yf_price_fn,
) -> dict:
    """forward_return that ALWAYS returns a dict — on failure, status != "ok" + a labeled reason.

    The harness (PIECE 4) joins on this so an un-fetchable name is recorded with WHY (never
    fabricated, never silently dropped). status ∈ {"ok", "no_entry_price", "no_exit_price"}.
      * no_entry_price : no price on/near asof (e.g. name not yet listed at asof). NOT a blowup —
                         the name simply cannot be entered, so it carries no realized return.
      * no_exit_price  : entry resolved but NO close at/before the target exit date at all
                         (data fully un-fetchable for the window). Distinct from a delisted name
                         that DID have a last close mid-horizon (that one resolves status="ok"
                         with realized_to_last_close=True).
    """
    target_exit = _add_months(asof, horizon_months)
    base = {
        "ticker": ticker,
        "asof": asof,
        "target_exit_date": target_exit,
        "horizon_months": horizon_months,
        "entry_date": None, "entry_price": None,
        "exit_date": None, "exit_price": None,
        "total_return": None,
        "realized_to_last_close": False,
    }

    entry = price_fn(ticker, asof)
    if not entry:
        return {**base, "status": "no_entry_price",
                "reason": f"no dividend-adjusted close on/near asof {asof} for {ticker} "
                          f"(not listed at asof, or price data un-fetchable)"}
    entry_price, entry_date = float(entry[0]), entry[1]
    if entry_price <= 0:
        return {**base, "status": "no_entry_price",
                "reason": f"non-positive entry price ({entry_price}) for {ticker} at {asof}"}
    if entry_price < _MIN_ENTRY_PRICE:
        return {**base, "entry_price": entry_price, "entry_date": entry_date,
                "status": "penny_unreliable",
                "reason": f"sub-${_MIN_ENTRY_PRICE:.2f} entry price ({entry_price}) for {ticker} at "
                          f"{asof} - penny/sub-penny forward return is a data artifact; excluded from stats"}

    exit_ = price_fn(ticker, target_exit)
    if not exit_:
        return {**base, "entry_date": entry_date, "entry_price": entry_price,
                "status": "no_exit_price",
                "reason": f"entry resolved but NO close at/before target exit {target_exit} for "
                          f"{ticker} (price window fully un-fetchable)"}
    exit_price, exit_date = float(exit_[0]), exit_[1]

    # DELISTED-mid-horizon detection: the exit-date request resolved to a date materially earlier
    # than the target exit date => the series ended (name stopped trading). Realize to last close.
    realized_to_last = _days_between(exit_date, target_exit) > _DELIST_GAP_DAYS

    total_return = (exit_price / entry_price) - 1.0
    return {
        **base,
        "entry_date": entry_date, "entry_price": entry_price,
        "exit_date": exit_date, "exit_price": exit_price,
        "total_return": round(total_return, 6),
        "realized_to_last_close": realized_to_last,
        "status": "ok",
        "reason": ("realized to last available close (name delisted/stopped trading before "
                   f"target exit {target_exit})" if realized_to_last else "full-horizon return"),
    }


def mktcap_asof(
    ticker: str,
    asof: str,
    cik: str | int | None = None,
    price_fn=_yf_price_fn,
    shares_fn=None,
) -> dict:
    """Entry market cap AS-OF T = (price-as-of-T) x (PIT shares-outstanding filed<=T).

    yfinance `marketCap` is a CURRENT field (look-ahead contamination), so it is NOT used. Instead
    we reconstruct: dividend-adjusted close near asof x SEC shares-outstanding from the
    point-in-time concept series (us-gaap CommonStockSharesOutstanding / dei
    EntityCommonStockSharesOutstanding, filed<=asof, latest period-end). This is survivorship-safe
    and look-ahead-clean.

    Returns a dict {ticker, asof, price, price_date, shares, mktcap, source, reason}. mktcap is
    None (with a labeled reason, source="unresolved") when price OR shares are genuinely
    unavailable — never fabricated. `shares_fn` is injectable for the network-free selftest; the
    default resolves PIT shares via _deepdive_concepts._shares_series(cik, asof=asof).
    """
    out = {"ticker": ticker, "asof": asof, "price": None, "price_date": None,
           "shares": None, "mktcap": None, "source": "unresolved", "reason": None}

    px = price_fn(ticker, asof)
    if not px:
        out["reason"] = f"no price on/near asof {asof} for {ticker}"
        return out
    price, price_date = float(px[0]), px[1]
    out["price"], out["price_date"] = price, price_date

    if shares_fn is None:
        shares_fn = _default_pit_shares_fn(asof)
    try:
        shares = shares_fn(cik)
    except Exception:
        shares = None
    out["shares"] = shares

    # resolve_mktcap with yf_mktcap=None forces the SEC shares x price branch — the look-ahead-safe
    # path. (We pass cik through; the injected shares_fn already carries the asof.)
    mc, src = resolve_mktcap(None, price, cik, shares_fn=lambda _c: shares)
    out["mktcap"], out["source"] = mc, src
    if mc is None:
        out["reason"] = (f"price resolved ({price}) but PIT shares-outstanding unavailable for "
                         f"cik={cik} at {asof}")
    return out


def _default_pit_shares_fn(asof: str):
    """Build a shares_fn(cik) -> float|None that returns PIT shares-outstanding as-of `asof`.

    Wraps _deepdive_concepts._shares_series(cik, asof=asof) (filed<=asof, latest period-end). Kept
    out of mktcap_asof's import path so the selftest (which injects its own shares_fn) needs no
    network and no _deepdive_concepts import.
    """
    def _fn(cik):
        if cik is None or str(cik).strip() in ("", "nan"):
            return None
        try:
            from _deepdive_concepts import _shares_series
            series = _shares_series(str(cik), asof=asof)
            vals = [s["val"] for s in series if s.get("val") is not None and s["val"] > 0]
            return float(vals[-1]) if vals else None
        except Exception:
            return None
    return _fn


def benchmark_return(
    asof: str,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    price_fn=_yf_price_fn,
    benchmark: str = DEFAULT_BENCHMARK,
) -> dict:
    """Forward total return of the benchmark (IWM) over the SAME [asof, asof+horizon] window.

    Returns forward_return_with_reason's dict for the benchmark ticker (status="ok" on success;
    a labeled reason otherwise). IWM is the Russell 2000 small-cap ETF — the correct universe
    comparison for a small-cap scanner (matches track_forward.DEFAULT_BENCHMARK). The harness
    subtracts this from each name's total_return to get excess-vs-IWM.
    """
    res = forward_return_with_reason(benchmark, asof, horizon_months, price_fn=price_fn)
    res["benchmark"] = benchmark
    return res


# ---------------------------------------------------------------------------
# Selftest — network-free (injectable price_fn), deterministic.
# ---------------------------------------------------------------------------


def _selftest() -> None:
    """PIECE 3 unit assertions. All price/shares are injected — NO network."""

    # ---- _add_months: month arithmetic + clamping ----
    assert _add_months("2020-06-30", 12) == "2021-06-30", "12mo of 2020-06-30"
    assert _add_months("2024-02-29", 12) == "2025-02-28", "leap-day +12mo clamps to 2025-02-28"
    assert _add_months("2023-08-31", 1) == "2023-09-30", "+1mo clamps to month length"
    assert _add_months("2022-06-30", 6) == "2022-12-30", "+6mo"

    # A scripted price book: (ticker, on_date) -> (price, resolved_date). Mirrors yfinance's
    # "most recent trading day on/before on_date" contract; a missing key => None (unavailable).
    BOOK = {
        # NORMAL name — full horizon, +25% total return, exit resolves AT the target date.
        ("AAA", "2020-06-30"): (100.0, "2020-06-30"),
        ("AAA", "2021-06-30"): (125.0, "2021-06-30"),
        # DELISTED/blown-up name — entered at 50, last print 0.40 in 2020-09, then the series
        # STOPS. Any exit-date request resolves to that last close (2020-09-15) — ~9.5 months
        # before the 2021-06-30 target => realized_to_last_close, return ~= -99.2%.
        ("ZZZ", "2020-06-30"): (50.0, "2020-06-30"),
        ("ZZZ", "2021-06-30"): (0.40, "2020-09-15"),
        # IWM benchmark — +18% over the window.
        ("IWM", "2020-06-30"): (140.0, "2020-06-30"),
        ("IWM", "2021-06-30"): (165.2, "2021-06-30"),
        # NEVER-LISTED-at-asof name — no entry print at all.
        # ("NOPE", ...) intentionally absent.
        # ENTRY-only name — entry exists, exit window fully un-fetchable.
        ("HALF", "2020-06-30"): (10.0, "2020-06-30"),
        # ("HALF", "2021-06-30") intentionally absent => no_exit_price.
    }

    def fake_price(ticker, on_date):
        return BOOK.get((ticker, on_date))

    # ---- 1) a NORMAL forward return computes (dividend-adjusted total return) ----
    r = forward_return("AAA", "2020-06-30", 12, price_fn=fake_price)
    assert r is not None, "normal name must return a dict, not None"
    assert r["status"] == "ok", f"normal status: {r['status']}"
    assert abs(r["total_return"] - 0.25) < 1e-9, f"normal total_return must be 0.25, got {r['total_return']}"
    assert r["realized_to_last_close"] is False, "normal name is NOT realized-to-last-close"
    assert r["entry_date"] == "2020-06-30" and r["exit_date"] == "2021-06-30", "normal entry/exit dates"
    assert r["target_exit_date"] == "2021-06-30", "target exit date"

    # ---- 1b) penny guard: sub-$0.10 entry -> penny_unreliable, excluded (forward_return None) ----
    _penny = forward_return_with_reason("PNY", "2020-06-30", 12,
                                        price_fn=lambda t, d: (0.00001, "2020-06-30"))
    assert _penny["status"] == "penny_unreliable", f"sub-$0.10 entry must be penny_unreliable, got {_penny['status']}"
    assert forward_return("PNY", "2020-06-30", 12,
                          price_fn=lambda t, d: (0.00001, "2020-06-30")) is None, "penny entry -> forward_return None (excluded from stats)"

    # ---- 2) a DELISTED name (price series ends mid-horizon) realizes to LAST close ----
    d = forward_return("ZZZ", "2020-06-30", 12, price_fn=fake_price)
    assert d is not None, "delisted name still returns a realized number, not None"
    assert d["status"] == "ok", f"delisted status: {d['status']}"
    assert d["realized_to_last_close"] is True, "delisted name MUST flag realized_to_last_close"
    assert d["exit_date"] == "2020-09-15", f"delisted exit resolves to last close, got {d['exit_date']}"
    # (0.40/50) - 1 = -0.992 — a blown-up name lands near -100% (the POINT).
    assert abs(d["total_return"] - (0.40 / 50.0 - 1.0)) < 1e-9, f"delisted return, got {d['total_return']}"
    assert d["total_return"] < -0.95, "a blown-up name must land near -100%"

    # ---- 3) missing data -> None with a labeled reason (never fabricated) ----
    n = forward_return("NOPE", "2020-06-30", 12, price_fn=fake_price)
    assert n is None, "un-enterable name must return None from forward_return"
    nr = forward_return_with_reason("NOPE", "2020-06-30", 12, price_fn=fake_price)
    assert nr["status"] == "no_entry_price", f"no-entry status: {nr['status']}"
    assert nr["total_return"] is None, "no-entry name has no return"
    assert "no dividend-adjusted close" in nr["reason"], f"no-entry must carry a reason: {nr['reason']}"
    # entry resolves but exit window is gone -> no_exit_price (distinct from delisted-with-last-close)
    h = forward_return("HALF", "2020-06-30", 12, price_fn=fake_price)
    assert h is None, "entry-only name (no exit) returns None"
    hr = forward_return_with_reason("HALF", "2020-06-30", 12, price_fn=fake_price)
    assert hr["status"] == "no_exit_price", f"no-exit status: {hr['status']}"
    assert hr["entry_price"] == 10.0, "no-exit name still records the entry it DID resolve"
    assert "NO close at/before target exit" in hr["reason"], f"no-exit reason: {hr['reason']}"

    # ---- 4) benchmark_return on IWM over the same window ----
    b = benchmark_return("2020-06-30", 12, price_fn=fake_price)
    assert b["status"] == "ok" and b["benchmark"] == "IWM", f"benchmark: {b}"
    assert abs(b["total_return"] - (165.2 / 140.0 - 1.0)) < 1e-9, f"IWM return, got {b['total_return']}"
    # excess-vs-IWM sanity: normal name (+25%) beat IWM (+18%); blowup (-99%) trailed it badly.
    assert r["total_return"] - b["total_return"] > 0, "normal name beat IWM (positive excess)"
    assert d["total_return"] - b["total_return"] < -1.0, "blowup badly trailed IWM (negative excess)"

    # ---- 5) mktcap_asof = price-as-of-T x PIT shares (yfinance marketCap NOT used) ----
    m = mktcap_asof("AAA", "2020-06-30", cik="320193",
                    price_fn=fake_price, shares_fn=lambda _c: 2_000_000.0)
    assert m["mktcap"] == 100.0 * 2_000_000.0, f"mktcap = price x shares, got {m['mktcap']}"
    assert m["source"] == "sec_shares_x_price", f"mktcap source must be SEC shares x price: {m['source']}"
    assert m["price_date"] == "2020-06-30", "mktcap price_date"
    # shares unavailable -> None + reason (never fabricated)
    mu = mktcap_asof("AAA", "2020-06-30", cik="320193", price_fn=fake_price, shares_fn=lambda _c: None)
    assert mu["mktcap"] is None and mu["source"] == "unresolved", f"no-shares mktcap unresolved: {mu}"
    assert "PIT shares-outstanding unavailable" in mu["reason"], f"no-shares reason: {mu['reason']}"
    # price unavailable -> None + reason
    mp = mktcap_asof("NOPE", "2020-06-30", cik="320193", price_fn=fake_price, shares_fn=lambda _c: 1e6)
    assert mp["mktcap"] is None and "no price" in mp["reason"], f"no-price mktcap: {mp}"

    print("backtest_returns selftest PASS (normal forward return; delisted->realized-to-last-close "
          "~-99%; missing data->None+reason; IWM benchmark + excess; mktcap_asof = price x PIT shares)")


def _cli() -> None:
    ap = argparse.ArgumentParser(
        description="PIT backtest returns (PIECE 3) — forward_return / mktcap_asof / benchmark_return.")
    ap.add_argument("--selftest", action="store_true", help="Run network-free selftest and exit")
    ap.add_argument("--ticker", help="Ticker for a live forward_return (network).")
    ap.add_argument("--asof", help="As-of date YYYY-MM-DD.")
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_MONTHS, help="Horizon in months (default 12).")
    ap.add_argument("--cik", help="CIK for a live mktcap_asof (network).")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return
    if args.ticker and args.asof:
        import json
        fr = forward_return_with_reason(args.ticker, args.asof, args.horizon)
        print(json.dumps(fr, indent=2))
        bm = benchmark_return(args.asof, args.horizon)
        print(json.dumps({"benchmark_return": bm}, indent=2))
        if args.cik:
            print(json.dumps({"mktcap_asof": mktcap_asof(args.ticker, args.asof, cik=args.cik)}, indent=2))
        return
    ap.error("use --selftest, or --ticker T --asof YYYY-MM-DD [--cik C] for a live lookup.")


if __name__ == "__main__":
    _cli()
