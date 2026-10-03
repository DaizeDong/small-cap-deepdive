"""Pure annual monetary evidence shared by data retrieval and valuation."""
from __future__ import annotations

import math
from datetime import date


def _annual_duration(row):
    try:
        start, end = row["start"], row["end"]
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
        if start_date.isoformat() != start or end_date.isoformat() != end:
            return None
        days = (end_date - start_date).days
        declared = row.get("duration_days", days)
        if type(declared) is not int or declared != days or not 330 <= days <= 400:
            return None
        return start, end, days
    except (KeyError, TypeError, ValueError):
        return None


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _fact_provenance(row):
    keys = ("start", "end", "duration_days", "filed", "fy", "fp", "form",
            "unit", "currency", "cik", "entity", "taxonomy", "concept", "accn", "source", "operands")
    return {key: row[key] for key in keys if key in row}


def _identity_conflict(left, right):
    for key in ("unit", "currency", "cik", "entity", "taxonomy", "accn"):
        a, b = left.get(key), right.get(key)
        if a is not None and b is not None:
            if key == "cik":
                a, b = str(a).lstrip("0"), str(b).lstrip("0")
            if a != b:
                return key
    return None


def _monetary_unit_invalid(row):
    return any(row.get(key) is not None and row[key] != "USD" for key in ("unit", "currency"))


def _identity_summary(left, right):
    keys = ("unit", "currency", "cik", "entity", "taxonomy", "accn")
    checked = [key for key in keys if left.get(key) is not None and right.get(key) is not None]
    return {"identity_fields_checked": checked,
            "identity_fields_unrecorded": [key for key in keys if key not in checked],
            "provenance_complete": False}


def paired_cash_flow_evidence(ocf_series: list[dict], capex_series: list[dict],
                              fcf_is_proxy: bool = False) -> list[dict]:
    """Pair annual cash flows by exact duration and retain rejected-period evidence."""
    periods = []
    ends = sorted({str(row.get("end") or "") for row in ocf_series})
    for end in ends:
        observations = [row for row in ocf_series if str(row.get("end") or "") == end]
        ocf = observations[0]
        span = _annual_duration(ocf)
        period = {
            "start": ocf.get("start"), "end": end,
            "duration_days": span[2] if span else None,
            "val": None, "ocf": ocf.get("val"), "capex": None,
            "qualified": False, "capex_complete": False,
            "reason": None, "operands": {"ocf": _fact_provenance(ocf), "capex": None},
        }
        periods.append(period)
        if len(observations) != 1:
            period["reason"] = "ambiguous_ocf_period"
            continue
        if span is None:
            period["reason"] = "ocf_annual_period_unproven"
            continue
        candidates = [row for row in capex_series if _annual_duration(row) == span]
        if len(candidates) != 1:
            period["reason"] = "matching_capex_period_missing" if not candidates else "ambiguous_capex_period"
            continue
        capex = candidates[0]
        period["capex"] = capex.get("val")
        period["operands"]["capex"] = _fact_provenance(capex)
        conflict = _identity_conflict(ocf, capex)
        if conflict:
            period["reason"] = f"fact_identity_conflict:{conflict}"
            continue
        if _monetary_unit_invalid(ocf) or _monetary_unit_invalid(capex):
            period["reason"] = "cash_flow_unit_not_usd"
            continue
        if fcf_is_proxy:
            period["reason"] = "upstream_ocf_proxy"
            continue
        if not _finite_number(ocf.get("val")) or not _finite_number(capex.get("val")):
            period["reason"] = "cash_flow_value_unavailable"
            continue
        value = ocf["val"] - capex["val"]
        if not _finite_number(value):
            period["reason"] = "cash_flow_value_nonfinite"
            continue
        period.update(
            val=value, qualified=True, capex_complete=True,
            reason="matching_annual_period", **_identity_summary(ocf, capex),
        )
    return periods


def paired_annual_sum_evidence(left_series: list[dict], right_series: list[dict],
                               *, left_name="ebit", right_name="dep_amort") -> list[dict]:
    """Add compatible annual monetary observations, preserving every unmatched end."""
    periods = []
    ends = sorted({str(row.get("end") or "") for row in [*left_series, *right_series]})
    for end in ends:
        left_rows = [row for row in left_series if str(row.get("end") or "") == end]
        right_rows = [row for row in right_series if str(row.get("end") or "") == end]
        left = left_rows[0] if left_rows else {}
        right = right_rows[0] if right_rows else {}
        span = _annual_duration(left)
        period = {"start": left.get("start", right.get("start")), "end": end,
                  "duration_days": span[2] if span else None, "val": None,
                  left_name: left.get("val"), right_name: right.get("val"),
                  "qualified": False, "reason": None,
                  "operands": {left_name: _fact_provenance(left), right_name: _fact_provenance(right)}}
        periods.append(period)
        if len(left_rows) != 1 or len(right_rows) != 1:
            period["reason"] = "missing_or_ambiguous_annual_operand"
            continue
        if span is None or _annual_duration(right) != span:
            period["reason"] = "matching_annual_period_unproven"
            continue
        conflict = _identity_conflict(left, right)
        if conflict:
            period["reason"] = f"fact_identity_conflict:{conflict}"
            continue
        if _monetary_unit_invalid(left) or _monetary_unit_invalid(right):
            period["reason"] = "annual_sum_unit_not_usd"
            continue
        if not _finite_number(left.get("val")) or not _finite_number(right.get("val")):
            period["reason"] = "annual_sum_value_unavailable"
            continue
        value = left["val"] + right["val"]
        if not _finite_number(value):
            period["reason"] = "annual_sum_value_nonfinite"
            continue
        period.update(val=value, qualified=True, reason="matching_annual_period",
                      **_identity_summary(left, right))
    return periods
