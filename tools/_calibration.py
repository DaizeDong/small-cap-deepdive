"""_calibration.py — Brier / confidence-as-probability / de-risk-native metrics.

v0.3.3 refactor: extracted verbatim from track_forward.py to shrink that orchestrator. This
module owns the scoring MATH — the Brier kernel, the confidence-as-probability mapping (P12a),
the data_false_positive predicate + price-scorable filter (P12d), and the three de-risk-native
metrics (P12c: blowup-avoidance / downside-capture / BUY-data-integrity).

Imports ONLY stdlib; it NEVER imports back from track_forward (no circular import). The
orchestrator re-exports every public symbol below so the PUBLIC API (track_forward.<symbol>) is
UNCHANGED. NO behavior change — this is a pure mechanical move.
"""
from __future__ import annotations


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


def _implied_prob_from_confidence(rating: str, confidence: float | None) -> float:
    """Map a model confidence (0..1) to an implied probability of FAVORABLE outcome, by
    rating direction (P12a).

        favorable = stock total return > benchmark total return over horizon.

    Direction sign d = RATING_DIRECTION[rating] in {+1, 0, -1}:
        implied_prob = 0.5 + d * (confidence - 0.5)

    Examples:
        买入 (d=+1), confidence 0.70 -> 0.70   (high confidence the thesis resolves favorably)
        避开 (d=-1), confidence 0.70 -> 0.30   (high confidence in UNDERperformance)
        观察 (d= 0), any confidence  -> 0.50   (neutral by construction)
        买入 (d=+1), confidence 0.50 -> 0.50   (no edge)

    When confidence is None/invalid, fall back to the fixed RATING_PROB convention. Result is
    clamped to (0, 1) so Brier math is always well-defined.
    """
    d = RATING_DIRECTION.get(rating, 0)
    if confidence is None:
        return RATING_PROB.get(rating, 0.50)
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return RATING_PROB.get(rating, 0.50)
    # Tolerate confidence given as a percentage (e.g. 70 -> 0.70).
    if c > 1.0:
        c = c / 100.0
    p = 0.5 + d * (c - 0.5)
    # Clamp into the open interval so a perfectly-wrong/right Brier stays in [0,1] and never NaN.
    return min(0.999, max(0.001, p))


def _brier(implied_prob: float, favorable: bool) -> float:
    """Brier score for a single verdict: (p - o)^2 where o in {0, 1}."""
    o = 1.0 if favorable else 0.0
    return (implied_prob - o) ** 2


def _is_data_false_positive(row: dict) -> bool:
    """True if a verdict is an adversarially-resolved BUY data false-positive (P12d).

    These rows carry adjudication=="data_false_positive": a BUY-eligible (MoS>=30%) name that the
    validation campaign proved is a data/model pathology (debt truncation, wrong-entity,
    financial-SIC misroute, OCF-proxy, concentration, lumpy OCF). They are KEPT OUT of the
    price-Brier (they have no forward price horizon) but DO feed the BUY-data-integrity metric.
    """
    return row.get("adjudication") == "data_false_positive"


def _price_scorable(rows: list[dict]) -> list[dict]:
    """Scored verdicts eligible for the price-Brier: scored AND not a data_false_positive.

    The 19 backfilled BUY false-positives are adjudicated by balance-sheet cross-check, not by a
    forward price, so they must never contaminate the price-return Brier / calibration table.
    """
    return [r for r in rows if r.get("scored") and not _is_data_false_positive(r)]


# ---------------------------------------------------------------------------
# De-risk-native metrics (P12c)
#
# Brier-vs-IWM measures stock-picking. This scanner's job is blowup AVOIDANCE. These three
# metrics measure that directly and are reported alongside Brier in the scorecard.
# ---------------------------------------------------------------------------

def _blowup_avoidance_rate(rows: list[dict],
                           threshold: float = BLOWUP_DRAWDOWN_THRESHOLD) -> float | None:
    """Fraction of scored 观察/避开 (de-risk) verdicts whose stock horizon TOTAL RETURN avoided a
    blowup (return > threshold, default -40%). Higher is better.

    Only price-scorable, non-BUY verdicts with a non-null stock_return_pct are counted. Returns
    None when there are no such verdicts yet.
    """
    pool = [r for r in _price_scorable(rows)
            if r.get("rating") in ("观察", "避开") and r.get("stock_return_pct") is not None]
    if not pool:
        return None
    avoided = sum(1 for r in pool if (r["stock_return_pct"] / 100.0) > threshold)
    return avoided / len(pool)


def _downside_capture_rate(rows: list[dict],
                           threshold: float = BLOWUP_DRAWDOWN_THRESHOLD) -> float | None:
    """Fraction of scored 避开 (AVOID) verdicts that did their job: UNDERperformed the benchmark
    (realized_excess_pct < 0) AND drew down past the blowup threshold. This is the de-risk
    "we correctly told you to run" rate. Higher means AVOID is genuinely flagging losers.

    Returns None when there are no scored AVOID verdicts with the needed fields.
    """
    pool = [r for r in _price_scorable(rows)
            if r.get("rating") == "避开"
            and r.get("stock_return_pct") is not None
            and r.get("realized_excess_pct") is not None]
    if not pool:
        return None
    captured = sum(
        1 for r in pool
        if r["realized_excess_pct"] < 0 and (r["stock_return_pct"] / 100.0) <= threshold
    )
    return captured / len(pool)


def _buy_data_integrity_rate(rows: list[dict]) -> float | None:
    """Fraction of all BUY verdicts that survive a balance-sheet cross-check, i.e. are NOT
    adjudicated data_false_positive. Measurable TODAY from the backfilled 19 — no 12-month wait.

    integrity = clean_BUYs / all_BUYs. With only the 19 validation false-positives logged and no
    clean BUY yet, this is 0.0 — the honest, decision-relevant headline number. Returns None when
    no BUY verdicts exist at all.
    """
    buys = [r for r in rows if r.get("rating") == "买入"]
    if not buys:
        return None
    clean = sum(1 for r in buys if not _is_data_false_positive(r))
    return clean / len(buys)
