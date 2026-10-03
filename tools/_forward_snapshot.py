"""Return endpoints selected from one provider adjustment snapshot."""
from __future__ import annotations
from datetime import date, timedelta
import hashlib
import json
import math


def _day(value):
    if not isinstance(value, str):
        return None
    try:
        result = date.fromisoformat(value)
    except ValueError:
        return None
    return result if result.isoformat() == value else None


def snapshot_return(ticker, entry_date, horizon_date, rows, *, price_column="Close", observed_at=None):
    """Use two dated closes from one auto-adjusted response; retain their exact values.

    rows contains date/price pairs from ONE yfinance download for ONE ticker.
    The content digest binds selected endpoints, not provider authenticity.
    """
    result = {"schema_version": 1, "available": False, "reason": None,
              "ticker": ticker, "source": "yfinance", "price_basis": "yfinance_auto_adjust",
              "entry_quote": None, "horizon_quote": None, "return_fraction": None}
    def fail(reason):
        result["reason"] = reason
        return result
    first, last = _day(entry_date), _day(horizon_date)
    if first is None or last is None or first >= last:
        return fail("invalid_snapshot_dates")
    if not isinstance(ticker, str) or not ticker.strip():
        return fail("invalid_ticker")
    ticker = ticker.strip().upper()
    result["ticker"] = ticker
    if price_column not in ("Close", "Adj Close"):
        return fail("missing_price_column")
    if not isinstance(rows, list) or not rows:
        return fail("no_quotes")
    parsed = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2 or _day(row[0]) is None:
            return fail("invalid_quote_date")
        parsed.append((_day(row[0]), row[1]))
    endpoints = []
    for label, requested in (("entry", first), ("horizon", last)):
        try:
            start = requested - timedelta(days=7)
        except OverflowError:
            return fail("invalid_snapshot_dates")
        candidates = [(day, value) for day, value in parsed if start <= day <= requested]
        if not candidates:
            return fail(label + ":no_admissible_quote_date")
        resolved = max(day for day, _ in candidates)
        values = [value for day, value in candidates if day == resolved]
        if len(values) != 1:
            return fail(label + ":ambiguous_quote_date")
        value = values[0]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return fail(label + ":invalid_price")
        try:
            price = float(value)
        except (ValueError, OverflowError):
            return fail(label + ":invalid_price")
        if not math.isfinite(price) or price <= 0:
            return fail(label + ":invalid_price")
        quote = {"schema_version": 1, "available": True, "reason": None, "price": price,
                 "ticker": ticker, "requested_date": requested.isoformat(),
                 "resolved_date": resolved.isoformat(), "source": "yfinance",
                 "price_basis": "yfinance_auto_adjust", "price_column": price_column}
        result[label + "_quote"] = quote
        endpoints.append(quote)
    if endpoints[0]["resolved_date"] >= endpoints[1]["resolved_date"]:
        return fail("nonforward_quote_dates")
    change = endpoints[1]["price"] / endpoints[0]["price"] - 1
    if not math.isfinite(change):
        return fail("nonfinite_return")
    binding = hashlib.sha256(json.dumps(endpoints, sort_keys=True, allow_nan=False,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()
    result.update(available=True, return_fraction=change,
                  adjustment_snapshot={"selected_endpoints_sha256": binding,
                                       "observed_at": observed_at,
                                       "scope": "one_auto_adjusted_download"})
    return result
