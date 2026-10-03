"""_calibration.py — Brier / confidence-as-probability / de-risk-native metrics.

This module owns scoring math: the Brier kernel, the confidence-as-probability mapping (P12a),
the data_false_positive predicate + price-scorable filter (P12d), and the three de-risk-native
metrics (P12c: blowup-avoidance / downside-capture / BUY-data-integrity).

Imports ONLY stdlib; it NEVER imports back from track_forward (no circular import). The
orchestrator re-exports its metrics. BUY integrity requires explicit adjudication and reports
review coverage separately from the outcome among reviewed verdicts.
"""
from __future__ import annotations

import math


# Default rating → implied_prob convention (used only when no model confidence is supplied).
# Rationale: 买入 predicts OUTperformance, 避开 predicts UNDERperformance.
# NOTE (P12): the LIVE path now derives implied_prob from the model's own confidence mapped by
# rating DIRECTION (see _implied_prob_from_confidence). RATING_PROB is the fallback when a verdict
# carries no confidence, and the reference anchor the calibration scorecard reports per bucket.
RATING_PROB = {
    "买入": 0.65,
    "观察": 0.50,
    "避开": 0.35,
}

# Rating → directional sign for confidence-as-probability mapping (P12a).
# 买入 predicts OUTperformance (+1), 避开 predicts UNDERperformance (-1), 观察 is neutral (0).
RATING_DIRECTION = {
    "买入": 1,
    "观察": 0,
    "避开": -1,
}

# De-risk-native metric thresholds (P12c).
BLOWUP_DRAWDOWN_THRESHOLD = -0.40  # a horizon total return <= -40% counts as a "blowup"

# Calibration bucket edges for implied_prob
CALIB_BUCKETS = [(0.0, 0.40), (0.40, 0.55), (0.55, 0.70), (0.70, 1.01)]


def _parse_confidence(value) -> float | None:
    """Accept absent confidence or a finite fraction/percentage, preserving its units."""
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "null", "none")):
        return None
    if isinstance(value, bool):
        raise ValueError("Confidence must be a finite number from 0 to 100, not a boolean")
    try:
        confidence = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Confidence must be a finite number from 0 to 100") from exc
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 100.0:
        raise ValueError("Confidence must be a finite number from 0 to 100")
    return confidence


def _validate_probability(value) -> float:
    """Require a stored probability to be a finite JSON number in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Implied probability must be a finite number from 0 to 1")
    try:
        probability = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("Implied probability must be a finite number from 0 to 1") from exc
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("Implied probability must be a finite number from 0 to 1")
    return probability


def _implied_prob_from_confidence(rating: str, confidence: float | None) -> float:
    """Map a finite confidence fraction/percentage to a probability of FAVORABLE outcome, by
    rating direction (P12a).

        favorable = stock total return > benchmark total return over horizon.

    Direction sign d = RATING_DIRECTION[rating] in {+1, 0, -1}:
        implied_prob = 0.5 + d * (confidence - 0.5)

    Examples:
        买入 (d=+1), confidence 0.70 -> 0.70   (high confidence the thesis resolves favorably)
        避开 (d=-1), confidence 0.70 -> 0.30   (high confidence in UNDERperformance)
        观察 (d= 0), valid confidence -> 0.50   (neutral by construction)
        买入 (d=+1), confidence 0.50 -> 0.50   (no edge)

    Absent confidence uses the fixed RATING_PROB convention. Explicit values must be finite
    and in [0, 100]: [0, 1] is a fraction, and (1, 100] is a percentage. A value of 1 means
    100% confidence. Invalid inputs raise ValueError, including for a neutral rating.
    """
    c = _parse_confidence(confidence)
    if c is None:
        return RATING_PROB.get(rating, 0.50)
    if c > 1.0:
        c = c / 100.0
    d = RATING_DIRECTION.get(rating, 0)
    p = 0.5 + d * (c - 0.5)
    # Preserve the open-interval convention after validating the input domain.
    return min(0.999, max(0.001, p))


def _brier(implied_prob: float, favorable: bool) -> float:
    """Brier score for a single verdict: (p - o)^2 where o in {0, 1}."""
    o = 1.0 if favorable else 0.0
    return (_validate_probability(implied_prob) - o) ** 2


_ADJUDICATION_PROTOCOL = "smallcap-data-review-v1"
_ADJUDICATION_DISPOSITIONS = {"data_verified_clean", "data_false_positive"}
_ADJUDICATION_CLEAN_FIELDS = {"issuer_identity", "total_debt", "operating_cash_flow",
                              "capital_expenditures", "verdict_inputs"}
_ADJUDICATION_BINDING_FIELDS = ("ticker", "cik", "verdict_date", "rating", "report_sha256")


def _adjudication_review(row: dict) -> dict:
    """Validate a documented review receipt and its verdict binding, not reviewer truth."""
    from datetime import date
    import re

    def pending(reason):
        return {"status": "pending", "disposition": None, "reason": reason}

    label = row.get("adjudication")
    if not isinstance(label, str) or label not in _ADJUDICATION_DISPOSITIONS:
        return pending("no_completed_disposition" if label is None else "unsupported_disposition")
    receipt = row.get("adjudication_evidence")
    if not isinstance(receipt, dict):
        return pending("missing_review_receipt")
    if (type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1
            or receipt.get("protocol") != _ADJUDICATION_PROTOCOL):
        return pending("unsupported_review_protocol")
    if receipt.get("disposition") != label:
        return pending("disposition_mismatch")
    binding = {field: row.get(field) for field in _ADJUDICATION_BINDING_FIELDS}
    if (not isinstance(binding["ticker"], str) or not binding["ticker"].strip()
            or not isinstance(binding["report_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", binding["report_sha256"]) is None
            or receipt.get("verdict") != binding):
        return pending("verdict_binding_unproved")
    try:
        if any(not isinstance(day, str) or len(day) != 10 for day in
               (binding["verdict_date"], receipt.get("review_date"))):
            raise ValueError("review dates require YYYY-MM-DD")
        verdict_day = date.fromisoformat(binding["verdict_date"])
        review_day = date.fromisoformat(receipt.get("review_date"))
    except (TypeError, ValueError):
        return pending("review_date_invalid")
    if review_day < verdict_day:
        return pending("review_predates_verdict")
    sources = receipt.get("sources")
    checks = receipt.get("checks")
    if not isinstance(sources, list) or not sources or not isinstance(checks, list) or not checks:
        return pending("review_evidence_missing")
    source_hashes = set()
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get("reference"), str)
                or not source["reference"].strip() or not isinstance(source.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) is None
                or source["sha256"] == binding["report_sha256"]):
            return pending("source_reference_invalid")
        source_hashes.add(source["sha256"])
    outcomes = []
    for check in checks:
        if (not isinstance(check, dict) or not isinstance(check.get("field"), str)
                or not check["field"].strip() or not isinstance(check.get("source_sha256"), str)
                or check["source_sha256"] not in source_hashes or not isinstance(check.get("result"), str)
                or check["result"] not in {"matches", "mismatch"}):
            return pending("review_check_invalid")
        outcomes.append(check["result"])
    if label == "data_verified_clean" and not _ADJUDICATION_CLEAN_FIELDS.issubset(
            {check["field"] for check in checks}):
        return pending("clean_review_scope_incomplete")
    if ((label == "data_verified_clean" and any(result != "matches" for result in outcomes))
            or (label == "data_false_positive" and "mismatch" not in outcomes)):
        return pending("review_checks_disagree_with_disposition")
    return {"status": "reviewed", "disposition": label, "reason": None}


def _require_adjudication_receipt(row: dict) -> None:
    """New completed dispositions require the receipt contract used by metrics."""
    label = row.get("adjudication")
    # An unknown workflow label is an unfinished review, not a completed disposition.
    if row.get("adjudication_evidence") is None and (
            not isinstance(label, str) or label not in _ADJUDICATION_DISPOSITIONS):
        return
    review = _adjudication_review(row)
    if review["status"] != "reviewed":
        raise ValueError("Adjudication receipt required for a new labeled verdict: " + review["reason"])


def _adjudication_blocks_price(row: dict) -> bool:
    """Quarantine unsupported review claims; a data-false-positive label never admits prices."""
    if _is_data_false_positive(row):
        return True
    if row.get("adjudication") is None and row.get("adjudication_evidence") is None:
        return False
    return _adjudication_review(row)["status"] != "reviewed"


def _is_data_false_positive(row: dict) -> bool:
    """Identify an FP label for price quarantine; this does not establish completed review.

    Historical labels remain intact, but only _adjudication_review can make them count as
    reviewed integrity outcomes. Unsupported labels stay pending and outside price scoring.
    """
    return row.get("adjudication") == "data_false_positive"


def _price_scorable(rows: list[dict]) -> list[dict]:
    """Scored verdicts with no FP label or unsupported adjudication claim.

    Review-pending labels are quarantined independently of the reviewed integrity metric;
    requiring a receipt must never admit a formerly excluded FP row to price scoring.
    """
    return [r for r in rows if r.get("scored") and not _adjudication_blocks_price(r)]


# ---------------------------------------------------------------------------
# De-risk-native metrics (P12c)
#
# Brier-vs-IWM measures stock-picking. This scanner's job is blowup AVOIDANCE. These three
# metrics measure that directly and are reported alongside Brier in the scorecard.
# ---------------------------------------------------------------------------

def _return_comparison(row: dict, field: str, threshold_pct: float) -> int | None:
    """Compare precise returns, or a legacy rounding interval, with a percentage threshold."""
    exact_field = field + "_unrounded"
    exact = exact_field in row
    value = row.get(exact_field if exact else field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        if not math.isfinite(value) or not math.isfinite(threshold_pct):
            return None
    except (OverflowError, TypeError):
        return None
    # A legacy two-decimal value at the boundary has lost the decisive precision.
    # This includes rounded zero: neither its sign nor exact equality can be recovered.
    if not exact and value - 0.005 <= threshold_pct <= value + 0.005:
        return None
    return (value > threshold_pct) - (value < threshold_pct)


def _favorable_outcome(row: dict) -> bool | None:
    """Resolve the same strict excess > 0 outcome used when the Brier score was stored."""
    comparison = _return_comparison(row, "realized_excess_pct", 0.0)
    if comparison is None:
        return None
    favorable = comparison > 0
    if "favorable" in row and (type(row["favorable"]) is not bool or row["favorable"] != favorable):
        return None
    return favorable


def _outcome_summary(rows: list[dict]) -> dict:
    known = [(row, _favorable_outcome(row)) for row in rows]
    known = [(row, outcome) for row, outcome in known if outcome is not None]
    return {"rows": [row for row, _ in known],
            "rate": sum(outcome for _, outcome in known) / len(known) if known else None,
            "observed": len(known), "total": len(rows), "missing": len(rows) - len(known)}


def _risk_metric_summary(rows: list[dict], metric: str, threshold: float) -> dict:
    ratings = ("观察", "避开") if metric == "avoidance" else ("避开",)
    pool = [row for row in _price_scorable(rows) if row.get("rating") in ratings]
    outcomes = []
    for row in pool:
        stock = _return_comparison(row, "stock_return_pct", threshold * 100.0)
        if metric == "avoidance":
            outcome = None if stock is None else stock > 0
        else:
            excess = (_return_comparison(row, "realized_excess_pct", 0.0)
                      if _favorable_outcome(row) is not None else None)
            outcome = None if stock is None or excess is None else stock <= 0 and excess < 0
        if outcome is not None:
            outcomes.append(outcome)
    return {"rate": sum(outcomes) / len(outcomes) if outcomes else None,
            "observed": len(outcomes), "total": len(pool), "missing": len(pool) - len(outcomes)}


def _blowup_avoidance_rate(rows: list[dict],
                           threshold: float = BLOWUP_DRAWDOWN_THRESHOLD) -> float | None:
    """Rate among de-risk verdicts with a resolvable stock-return threshold comparison."""
    return _risk_metric_summary(rows, "avoidance", threshold)["rate"]


def _downside_capture_rate(rows: list[dict],
                           threshold: float = BLOWUP_DRAWDOWN_THRESHOLD) -> float | None:
    """Rate of underperformance plus blowup among AVOID verdicts with precise outcomes."""
    return _risk_metric_summary(rows, "capture", threshold)["rate"]


def _buy_data_integrity_summary(rows: list[dict]) -> dict:
    """Separate review coverage from integrity among explicitly reviewed BUYs.

    Only verdict-bound receipts for the declared review protocol supply completed outcomes.
    Bare, unsupported or malformed labels remain pending, including failed review attempts.
    Receipt validation does not independently authenticate the referenced source bytes.
    """
    buys = [r for r in rows if r.get("rating") == "买入"]
    reviews = [_adjudication_review(row) for row in buys]
    clean = sum(review["disposition"] == "data_verified_clean" for review in reviews)
    false_positive = sum(review["disposition"] == "data_false_positive" for review in reviews)
    reviewed = clean + false_positive
    return {"rate": clean / reviewed if reviewed else None,
            "total_buys": len(buys), "reviewed_buys": reviewed,
            "clean_buys": clean, "false_positive_buys": false_positive,
            "pending_buys": len(buys) - reviewed,
            "review_coverage": reviewed / len(buys) if buys else None}


def _buy_data_integrity_rate(rows: list[dict]) -> float | None:
    """Compatibility scalar; an unreviewed BUY contributes no clean outcome."""
    return _buy_data_integrity_summary(rows)["rate"]
