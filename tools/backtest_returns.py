"""Adjusted-close returns and explicit quote coverage for the PIT backtest.

Exit lookup covers the complete holding interval. An old last quote remains a
labelled proxy with an unknown terminal outcome; it does not prove a delisting,
liquidation value or executable sale. Provider failures and absent or invalid
quotes remain separate outcomes. Injected price functions support offline tests.

Returns use dividend-adjusted prices. Market-cap estimates use a separate quote
and dated share evidence, reconciled to one split basis. Missing or ambiguous
basis evidence cannot qualify a company for valuation.
"""
from __future__ import annotations

import argparse
import math
import sys
import warnings
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from numbers import Number
from pathlib import Path

# Add tools dir to path for sibling imports (mirrors track_forward.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_BENCHMARK = "IWM"   # Russell 2000 small-cap ETF, matches track_forward.DEFAULT_BENCHMARK
DEFAULT_HORIZON_MONTHS = 12
# Entries below the configured penny-price floor are not admitted as tradeable
# forward-return evidence. Preserve penny_unreliable and exclude the observation
# from return statistics rather than magnifying a near-zero denominator.
_MIN_ENTRY_PRICE = 0.10

# ---------------------------------------------------------------------------
# Price resolution
#
# A price_fn has the signature: price_fn(ticker, on_date) -> (price, resolved_date) | None
#   * price        : float dividend-adjusted close (total-return basis)
#   * resolved_date: "YYYY-MM-DD" of the trading day actually used (on or BEFORE on_date)
#   * None         : no price on/near on_date (delisting / data gap / un-fetchable)
# Dates establish quote age. They do not establish why a price series ended.
# ---------------------------------------------------------------------------


def _quote_date(value) -> str:
    if isinstance(value, datetime):
        value = value.date().isoformat()
    elif isinstance(value, date):
        value = value.isoformat()
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("quote date must be YYYY-MM-DD")
    parsed = datetime.strptime(value, "%Y-%m-%d")
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError("quote date must be YYYY-MM-DD")
    return value


def _validated_quote(value, start_date: str, end_date: str) -> tuple[float, str]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("quote must contain exactly price and date")
    price, day = value
    if isinstance(price, bool) or not isinstance(price, Number):
        raise ValueError("quote price must be numeric and not boolean")
    price = float(price)
    if not math.isfinite(price) or price <= 0:
        raise ValueError("quote price must be finite and positive")
    day = _quote_date(day)
    if not start_date <= day <= end_date:
        raise ValueError("quote date is outside the requested interval")
    return price, day


def _yf_lookup(ticker: str, start_date: str, on_date: str) -> dict:
    """Retrieve one explicit interval and select its latest valid dated close."""
    diagnostic = {"rows_seen": 0, "invalid_rows": 0, "out_of_window_rows": 0}
    end = (datetime.strptime(on_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        import yfinance as yf
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # history exposes failures through raise_errors; download can turn them into an empty frame.
            hist = yf.Ticker(ticker).history(
                start=start_date, end=end, auto_adjust=True, raise_errors=True)
    except Exception as exc:
        return {"status": "provider_error", "quote": None, "diagnostics": diagnostic,
                "error_type": type(exc).__name__}

    quotes = {}
    try:
        if hist is None:
            return {"status": "invalid", "quote": None, "diagnostics": diagnostic,
                    "detail": "history response is None"}
        if hist.empty:
            return {"status": "missing", "quote": None, "diagnostics": diagnostic}
        column = next((name for name in ("Close", "Adj Close") if name in hist.columns), None)
        if column is None:
            return {"status": "invalid", "quote": None, "diagnostics": diagnostic,
                    "detail": "history has no adjusted close column"}
        for index, row in hist.iterrows():
            diagnostic["rows_seen"] += 1
            try:
                day = _quote_date(index)
                if not start_date <= day <= on_date:
                    diagnostic["out_of_window_rows"] += 1
                    continue
                quote = _validated_quote((row[column], day), start_date, on_date)
            except (ValueError, TypeError, OverflowError, KeyError):
                diagnostic["invalid_rows"] += 1
                continue
            previous = quotes.get(day)
            if previous is not None and previous != quote:
                return {"status": "invalid", "quote": None, "diagnostics": diagnostic,
                        "detail": "conflicting closes for one date"}
            quotes[day] = quote
    except Exception as exc:
        return {"status": "invalid", "quote": None, "diagnostics": diagnostic,
                "detail": "unreadable price history", "error_type": type(exc).__name__}
    latest = quotes[max(quotes)] if quotes else None
    status = "ok" if latest is not None else ("invalid" if diagnostic["invalid_rows"] else "missing")
    return {"status": status, "quote": latest, "diagnostics": diagnostic}


def _yf_price_fn(ticker: str, on_date: str, *, start_date: str | None = None) -> tuple[float, str] | None:
    """Compatibility quote helper; missing returns None, retrieval/validation failures raise.

    A standalone entry query looks back 14 days. Forward returns use _yf_lookup
    with the resolved entry date as the exit query's lower bound.
    """
    on_date = _quote_date(on_date)
    start_date = _quote_date(start_date) if start_date is not None else (
        datetime.strptime(on_date, "%Y-%m-%d") - timedelta(days=14)).strftime("%Y-%m-%d")
    if start_date > on_date:
        raise ValueError("price interval starts after its end")
    result = _yf_lookup(ticker, start_date, on_date)
    if result["status"] in {"provider_error", "invalid"}:
        raise RuntimeError(f"price lookup {result['status']}: {result.get('error_type', result.get('detail', 'invalid rows'))}")
    return result["quote"]


def _query_quote(ticker: str, on_date: str, start_date: str, price_fn) -> dict:
    if price_fn is None or price_fn is _yf_price_fn:
        result = _yf_lookup(ticker, start_date, on_date)
    else:
        try:
            value = price_fn(ticker, on_date)
        except Exception as exc:
            return {"status": "provider_error", "quote": None, "diagnostics": {},
                    "error_type": type(exc).__name__}
        result = {"status": "missing" if value is None else "ok", "quote": value, "diagnostics": {}}
    if result["status"] == "ok":
        try:
            result["quote"] = _validated_quote(result["quote"], start_date, on_date)
        except (ValueError, TypeError, OverflowError) as exc:
            result.update(status="invalid", quote=None, detail=str(exc))
    return result


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


# Quote-age policy only. The historical name is retained for compatibility;
# exceeding this threshold does not establish a terminal corporate event.
_DELIST_GAP_DAYS = 45


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def forward_return(
    ticker: str,
    asof: str,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    price_fn=None,
) -> dict | None:
    """Return a measured adjusted-close result, including labelled stale proxies, or None.

    Use forward_return_with_reason for missing/error outcomes. Successful results
    retain quote dates, age and return_kind. The legacy realized_to_last_close
    flag means stale_quote_proxy; it does not confirm a realized sale or delisting.
    """
    res = forward_return_with_reason(ticker, asof, horizon_months, price_fn=price_fn)
    if res.get("status") == "ok":
        return res
    return None


def forward_return_with_reason(
    ticker: str,
    asof: str,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    price_fn=None,
) -> dict:
    """Return quote evidence or an explicit missing, invalid or provider-error outcome."""
    base = {
        "ticker": ticker,
        "asof": asof,
        "target_exit_date": None,
        "horizon_months": horizon_months,
        "entry_date": None, "entry_price": None,
        "exit_date": None, "exit_price": None,
        "total_return": None,
        "realized_to_last_close": False,
        "return_kind": None, "terminal_status": "unknown",
        "exit_quote_age_days": None, "price_diagnostics": {},
    }
    try:
        asof = _quote_date(asof)
        if isinstance(horizon_months, bool) or not isinstance(horizon_months, int) or horizon_months < 0:
            raise ValueError("horizon_months must be a nonnegative integer")
        target_exit = _add_months(asof, horizon_months)
        entry_start = (datetime.strptime(asof, "%Y-%m-%d") - timedelta(days=14)).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError) as exc:
        return {**base, "status": "invalid_request", "reason": str(exc)}
    base.update(asof=asof, target_exit_date=target_exit)

    def lookup_failure(result, stage):
        status = result["status"]
        if status == "missing":
            reason = (f"no dividend-adjusted close on/near asof {asof} for {ticker}" if stage == "entry" else
                      f"NO close at/before target exit {target_exit} within the holding interval for {ticker}")
        else:
            reason = f"{stage} quote {status}: {result.get('detail', result.get('error_type', 'no eligible close'))}"
        return {**base, "status": ("provider_error" if status == "provider_error" else
                                  f"invalid_{stage}_price" if status == "invalid" else f"no_{stage}_price"),
                "error_stage": stage, "error_type": result.get("error_type"),
                "reason": reason}

    entry = _query_quote(ticker, asof, entry_start, price_fn)
    base["price_diagnostics"]["entry"] = entry["diagnostics"]
    if entry["status"] != "ok":
        return lookup_failure(entry, "entry")
    entry_price, entry_date = entry["quote"]
    base.update(entry_price=entry_price, entry_date=entry_date)
    if entry_price < _MIN_ENTRY_PRICE:
        return {**base, "entry_price": entry_price, "entry_date": entry_date,
                "status": "penny_unreliable",
                "reason": f"sub-${_MIN_ENTRY_PRICE:.2f} entry price ({entry_price}) for {ticker} at "
                          f"{asof} - penny/sub-penny forward return is a data artifact; excluded from stats"}

    exit_ = _query_quote(ticker, target_exit, entry_date, price_fn)
    base["price_diagnostics"]["exit"] = exit_["diagnostics"]
    if exit_["status"] != "ok":
        return lookup_failure(exit_, "exit")
    exit_price, exit_date = exit_["quote"]
    quote_age = _days_between(exit_date, target_exit)
    realized_to_last = quote_age > _DELIST_GAP_DAYS

    total_return = (exit_price / entry_price) - 1.0
    if not math.isfinite(total_return):
        return {**base, "status": "invalid_return", "reason": "price ratio is not finite"}
    return {
        **base,
        "entry_date": entry_date, "entry_price": entry_price,
        "exit_date": exit_date, "exit_price": exit_price,
        "total_return": round(total_return, 6),
        "realized_to_last_close": realized_to_last,
        "return_kind": "stale_quote_proxy" if realized_to_last else "observed_close",
        "exit_quote_age_days": quote_age,
        "status": "ok",
        "reason": (f"last observed adjusted-close proxy, {quote_age} days before target; terminal outcome unknown"
                   if realized_to_last else "observed adjusted-close return near target date"),
    }


def _cap_positive(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValueError(f"{field} must be a numeric, nonboolean value")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return value


def _split_events(envelope, start: str, end: str) -> dict[str, float]:
    """Validate a declared complete action interval, including duplicate dates."""
    if not isinstance(envelope, dict) or envelope.get("complete") is not True:
        raise ValueError("complete split-action evidence is unavailable")
    lower, upper = _quote_date(envelope.get("start")), _quote_date(envelope.get("end"))
    if lower > start or upper < end or lower > upper:
        raise ValueError("split-action coverage does not span both evidence bases")
    rows = envelope.get("splits")
    if not isinstance(rows, list):
        raise ValueError("split-action rows are unavailable")
    events = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid split-action row")
        day = _quote_date(row.get("date"))
        ratio = _cap_positive(row.get("ratio"), "split ratio")
        if not lower <= day <= upper:
            raise ValueError("split action falls outside its declared coverage")
        if day in events and events[day] != ratio:
            raise ValueError("conflicting split ratios on one effective date")
        events[day] = ratio
    return events


def _market_cap_evidence(quote: dict, shares: dict, asof: str) -> dict:
    """Express dated shares in the quote's split basis before multiplying."""
    start = (date.fromisoformat(asof) - timedelta(days=14)).isoformat()
    price, price_date = _validated_quote((quote.get("price"), quote.get("date")), start, asof)
    count = _cap_positive(shares.get("shares"), "shares")
    share_date, filed = _quote_date(shares.get("date")), _quote_date(shares.get("filed"))
    if not share_date <= price_date <= asof or not share_date <= filed <= asof:
        raise ValueError("share observation/filing is outside the point-in-time window")
    price_basis, share_basis = quote.get("basis"), shares.get("basis")
    if price_basis not in {"as_traded", "split_adjusted"}:
        raise ValueError("price basis is unknown or includes dividend adjustments")
    if share_basis not in {"as_traded", "as_reported", "split_adjusted"}:
        raise ValueError("share basis is unknown or is not an instantaneous count")
    price_anchor = _quote_date(quote.get("basis_date", price_date))
    share_anchor = _quote_date(shares.get("basis_date", share_date))
    if price_anchor < price_date or (price_basis == "as_traded" and price_anchor != price_date):
        raise ValueError("price basis date contradicts its stated basis")
    if share_anchor < share_date or (share_basis != "split_adjusted" and share_anchor != share_date):
        raise ValueError("share basis date contradicts its stated basis")
    if price_basis == "split_adjusted" and "basis_date" not in quote:
        raise ValueError("split-adjusted price lacks a basis date")
    if share_basis == "split_adjusted" and "basis_date" not in shares:
        raise ValueError("split-adjusted shares lack a basis date")
    for field in ("currency", "share_class"):
        if quote.get(field) is not None and shares.get(field) is not None and quote[field] != shares[field]:
            raise ValueError(f"price and shares disagree on {field}")

    lower, upper = min(price_anchor, share_anchor), max(price_anchor, share_anchor)
    needs_events = lower != upper or share_basis == "as_reported"
    envelope = quote.get("actions")
    if needs_events or envelope is not None:
        events = _split_events(envelope, min(lower, share_date), max(upper, filed))
    else:
        events = {}
    if share_basis == "as_reported" and any(share_date <= day <= filed and ratio != 1
                                            for day, ratio in events.items()):
        raise ValueError("a split between the share observation and filing leaves restatement basis ambiguous")
    for anchor, evidence in ((price_anchor, quote), (share_anchor, shares)):
        if events.get(anchor, 1) != 1 and evidence.get("basis_timing") != "after_actions":
            raise ValueError("same-day split basis needs an explicit after-actions convention")

    # Decimal prevents intermediate split products from overflowing before a later
    # reverse split cancels them. Final public values must still be finite floats.
    with localcontext() as context:
        context.prec = 64
        factor = Decimal(1)
        for day, ratio in sorted(events.items()):
            if lower < day <= upper:
                factor *= Decimal(str(ratio))
        if share_anchor > price_anchor:
            factor = Decimal(1) / factor
        aligned = Decimal(str(count)) * factor
        market_cap = aligned * Decimal(str(price))
        aligned_float = _cap_positive(float(aligned), "aligned shares")
        cap_float = _cap_positive(float(market_cap), "market cap")
        factor_float = _cap_positive(float(factor), "split factor")
    return {"price": price, "price_date": price_date, "price_basis": price_basis,
            "price_basis_date": price_anchor, "reported_shares": count,
            "shares": aligned_float, "shares_date": share_date, "shares_filed": filed,
            "shares_basis": share_basis, "shares_basis_date": share_anchor,
            "shares_source": shares.get("source"), "split_factor": factor_float,
            "normalization_basis_date": price_anchor, "mktcap": cap_float,
            "source": "sec_shares_x_price", "basis_status": "compatible", "usable": True,
            "estimate_kind": "latest_disclosed_count_snapshot", "status": "ok",
            "price_age_days": _days_between(price_date, asof),
            "shares_age_days": _days_between(share_date, asof),
            "action_coverage": ({key: envelope.get(key) for key in ("start", "end", "complete")}
                                if envelope is not None else None),
            "reason": "split bases reconciled; share changes after the disclosed count are not estimated"}


def _yf_market_cap_quote(ticker: str, asof: str, shares) -> dict | None:
    """Fetch split-only Close and the actions needed to undo its current basis."""
    observed = datetime.now(timezone.utc).date()
    if asof > observed.isoformat():
        raise ValueError("asof is after the price observation date")
    entry_start = (date.fromisoformat(asof) - timedelta(days=14)).isoformat()
    start = min(entry_start, _quote_date(shares["date"])) if isinstance(shares, dict) else entry_start
    import yfinance as yf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        history = yf.Ticker(ticker).history(
            start=start, end=(observed + timedelta(days=1)).isoformat(),
            auto_adjust=False, back_adjust=False, actions=True, raise_errors=True)
    if history is None:
        raise ValueError("market-cap history response is None")
    if history.empty:
        return None
    if not {"Close", "Stock Splits"}.issubset(history.columns):
        raise ValueError("market-cap history needs Close and explicit Stock Splits columns")
    quotes, splits = {}, []
    invalid_prices = 0
    for index, row in history.iterrows():
        day = _quote_date(index)
        if not start <= day <= observed.isoformat():
            raise ValueError("history row is outside the requested action interval")
        ratio = row["Stock Splits"]
        if isinstance(ratio, bool) or not isinstance(ratio, Number) or not math.isfinite(float(ratio)):
            raise ValueError("missing or invalid split-action value")
        if ratio != 0:
            splits.append({"date": day, "ratio": _cap_positive(ratio, "split ratio")})
        if entry_start <= day <= asof:
            try:
                price, _ = _validated_quote((row["Close"], day), entry_start, asof)
            except (ValueError, TypeError, OverflowError, KeyError):
                invalid_prices += 1
                continue
            if day in quotes and quotes[day] != price:
                raise ValueError("conflicting market-cap closes on one date")
            quotes[day] = price
    if not quotes:
        if invalid_prices:
            raise ValueError("no valid market-cap close in the requested entry interval")
        return None
    day = max(quotes)
    return {"price": quotes[day], "date": day, "basis": "split_adjusted",
            "basis_date": observed.isoformat(),
            "provider": "yfinance", "invalid_price_rows": invalid_prices,
            "actions": {"start": start, "end": observed.isoformat(), "complete": True,
                        "splits": splits,
                        "coverage_basis": "successful history request with explicit action column"}}


def mktcap_asof(ticker: str, asof: str, cik: str | int | None = None,
               price_fn=None, shares_fn=None) -> dict:
    """Return a dated snapshot estimate only when price/share split bases agree.

    Structured callbacks return the evidence described in docs/backtest-market-cap-basis.md.
    Legacy tuple/scalar injections retain their arithmetic result with usable=False;
    they supply no basis evidence and must not feed valuation. Current marketCap,
    dividend-adjusted prices and weighted-average shares are never default fallbacks.
    """
    out = {"ticker": ticker, "asof": asof, "price": None, "price_date": None,
           "shares": None, "mktcap": None, "source": "unresolved", "reason": None,
           "status": "unresolved", "basis_status": "unresolved", "usable": False}
    try:
        asof = _quote_date(asof)
        start = (date.fromisoformat(asof) - timedelta(days=14)).isoformat()
    except (ValueError, TypeError, OverflowError):
        out["reason"] = "invalid asof date"
        return out
    try:
        if shares_fn is None:
            lookup = _default_pit_shares_fn(asof)(cik)
            out.update(shares_lookup=lookup, shares_status=lookup["status"])
            if lookup["status"] != "ok":
                out["reason"] = lookup["reason"]
                return out
            shares = lookup["evidence"]
        else:
            shares = shares_fn(cik)
    except Exception as exc:
        out.update(shares_status="invalid" if isinstance(exc, ValueError) else "provider_error",
                   reason=f"PIT shares lookup failed: {type(exc).__name__}")
        return out
    try:
        quote = (_yf_market_cap_quote(ticker, asof, shares) if price_fn is None or price_fn is _yf_price_fn
                 else price_fn(ticker, asof))
    except Exception as exc:
        out.update(price_status="invalid" if isinstance(exc, ValueError) else "provider_error",
                   reason=f"market-cap quote lookup failed: {type(exc).__name__}: {exc}")
        return out
    if quote is None:
        out.update(price_status="missing", reason=f"no price on/near asof {asof} for {ticker}")
        return out
    if shares is None:
        out.update(shares_status="unavailable",
                   reason=f"PIT shares-outstanding unavailable for cik={cik} at {asof}")
        return out
    try:
        if isinstance(quote, (tuple, list)) and not isinstance(shares, dict):
            price, day = _validated_quote(quote, start, asof)
            count = _cap_positive(shares, "shares")
            cap = _cap_positive(price * count, "legacy market cap")
            out.update(price=price, price_date=day, shares=count, mktcap=cap,
                       source="sec_shares_x_price", status="legacy_unverified",
                       basis_status="legacy_unverified",
                       reason="legacy callbacks do not declare a price/share basis; arithmetic is not usable for valuation")
        elif isinstance(quote, dict) and isinstance(shares, dict):
            out.update(_market_cap_evidence(quote, shares, asof))
        else:
            raise ValueError("both price and share callbacks must supply dated basis evidence")
    except (ValueError, TypeError, OverflowError, ArithmeticError) as exc:
        out.update(reason=str(exc), status="invalid_evidence", basis_status="unresolved")
    return out


def _default_pit_shares_fn(asof: str):
    """Fetch the strict SEC envelope without the lossy financial-series adapter."""
    def _fn(cik):
        from _deepdive_concepts import instant_share_evidence
        return instant_share_evidence(cik, asof)
    return _fn


def benchmark_return(
    asof: str,
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    price_fn=None,
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
# Selftest, network-free (injectable price_fn), deterministic.
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
        # NORMAL name, full horizon, +25% total return, exit resolves AT the target date.
        ("AAA", "2020-06-30"): (100.0, "2020-06-30"),
        ("AAA", "2021-06-30"): (125.0, "2021-06-30"),
        # DELISTED/blown-up name, entered at 50, last print 0.40 in 2020-09, then the series
        # STOPS. Any exit-date request resolves to that last close (2020-09-15), ~9.5 months
        # before the 2021-06-30 target => realized_to_last_close, return ~= -99.2%.
        ("ZZZ", "2020-06-30"): (50.0, "2020-06-30"),
        ("ZZZ", "2021-06-30"): (0.40, "2020-09-15"),
        # IWM benchmark, +18% over the window.
        ("IWM", "2020-06-30"): (140.0, "2020-06-30"),
        ("IWM", "2021-06-30"): (165.2, "2021-06-30"),
        # NEVER-LISTED-at-asof name, no entry print at all.
        # ("NOPE", ...) intentionally absent.
        # ENTRY-only name, entry exists, exit window fully un-fetchable.
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
    # (0.40/50) - 1 = -0.992, a blown-up name lands near -100% (the POINT).
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
