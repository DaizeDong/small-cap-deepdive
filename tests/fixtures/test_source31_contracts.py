"""Generated offline-suite controls with synthetic observations."""
from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path

import pytest

from make_fixtures import source31_valuation_config, tracking_quote_scenarios, source28_realize
from test_private_runs import state
from test_tracking_quote_contract import tracker


def test_offline_denials_escape_ordinary_exception_handlers(offline_network_targets):
    labels = {label for label, _ in offline_network_targets}
    assert {"socket.socket.connect", "socket.socket.connect_ex", "socket.socket.sendto",
            "socket.create_connection", "socket.getaddrinfo",
            "urllib.request.OpenerDirector.open"} <= labels
    for label, operation in offline_network_targets:
        with pytest.raises(pytest.fail.Exception, match="offline suite"):
            try:
                operation()
            except Exception:
                pytest.fail("an ordinary handler swallowed the network denial: " + label)


def test_explicit_transport_mock_can_return_synthetic_data(monkeypatch):
    import requests
    response = SimpleNamespace(status_code=200, text="synthetic response")
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *args, **kwargs: response)
    assert requests.get("https://example.com/synthetic") is response


def test_valuation_fixture_returns_independent_config_values():
    first = source31_valuation_config()
    second = source31_valuation_config()
    assert first == {"wacc": 0.10, "cap_rate_low": 0.09, "cap_rate_high": 0.12,
                     "normalize_years": 5, "cyclical_cv_threshold": 0.25}
    first["wacc"] = 1.0
    assert second["wacc"] == 0.10


CASE = json.loads(Path(__file__).with_name("source31_contracts.json").read_text(encoding="utf-8"))
CONCENTRATION = CASE["concentration"]


@pytest.mark.parametrize("case", CONCENTRATION, ids=lambda case: case["name"])
def test_segment_exclusion_stays_with_its_percentage(case):
    from _deepdive_flags import _extract_concentration, _concentration_flag
    customer, program, detail = _extract_concentration(case["text"])
    assert (customer, program) == (case["customer"], case["program"])
    assert _concentration_flag(customer, program) == case["flag"]
    assert (detail is None) is (customer is None and program is None)


@pytest.mark.parametrize("case", CASE["rounding"], ids=lambda case: case["name"])
def test_score_and_scorecard_keep_the_same_precise_outcome(tracker, state, monkeypatch, case):
    row = deepcopy(tracking_quote_scenarios()["base_row"])
    row["implied_prob"] = 0.8
    calls, saved = [], []

    def snapshot(ticker, entry, horizon):
        calls.append(ticker)
        entry_quote = row["entry_quote"] if ticker == row["ticker"] else row["benchmark_entry_quote"]
        return {"available": True,
                "return_fraction": case["excess_pct"] / 100 if ticker == row["ticker"] else 0.0,
                "entry_quote": deepcopy(entry_quote), "horizon_quote": {"resolved_date": horizon}}

    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])
    monkeypatch.setattr(tracker, "_save_verdicts", lambda rows: saved.append(deepcopy(rows)))
    monkeypatch.setattr(tracker, "_fetch_return_snapshot", snapshot)
    tracker.cmd_score(SimpleNamespace())
    assert calls == [row["ticker"], row["benchmark"]]
    assert len(saved) == 1 and saved[0][0]["scored"] is True
    assert row["realized_excess_pct_unrounded"] == pytest.approx(case["excess_pct"])
    assert row["stock_return_pct_unrounded"] == pytest.approx(case["excess_pct"])
    assert row["favorable"] is case["favorable"]
    assert tracker._favorable_outcome(row) is case["favorable"]
    assert row["brier"] == pytest.approx(0.04 if case["favorable"] else 0.64)
    destination = Path(state["companion"]) / "data" / "metrics" / "scorecard.md"
    monkeypatch.setattr(tracker, "SCORECARD_FILE", destination)
    tracker.cmd_scorecard(SimpleNamespace())
    scorecard = destination.read_text(encoding="utf-8")
    assert "**Outcome coverage:** 1/1; missing 0" in scorecard
    assert "all 1 stored scores" in scorecard
    assert ("| YES |" if case["favorable"] else "| NO |") in scorecard
    assert ("**Overall hit rate (stock beat benchmark):** 100.0%" if case["favorable"]
            else "**Overall hit rate (stock beat benchmark):** 0.0%") in scorecard
    rating_line = next(line for line in scorecard.splitlines() if line.startswith("| " + row["rating"] + " |"))
    assert ("| 100.0% |" if case["favorable"] else "| 0.0% |") in rating_line
    calibration_line = next(line for line in scorecard.splitlines() if line.startswith("| 0.70–1.01 |"))
    assert ("| 1.00 | +0.20 |" if case["favorable"] else "| 0.00 | -0.80 |") in calibration_line


@pytest.mark.parametrize("case", CASE["outcomes"], ids=lambda case: case["name"])
def test_legacy_rounding_and_invalid_precision_report_missing_outcomes(case):
    from _calibration import _favorable_outcome, _outcome_summary
    row = {key: source28_realize(value) for key, value in case["row"].items()}
    assert _favorable_outcome(row) is case["expected"]
    result = _outcome_summary([row])
    assert result["observed"] == (0 if case["expected"] is None else 1)
    assert result["missing"] == (1 if case["expected"] is None else 0)
    assert result["rate"] == (None if case["expected"] is None else float(case["expected"]))


@pytest.mark.parametrize("case", CASE["risk"], ids=lambda case: case["name"])
def test_risk_metrics_use_precise_sign_and_threshold_coverage(case):
    from _calibration import _risk_metric_summary, _blowup_avoidance_rate, _downside_capture_rate
    row = {"rating": "避开", "scored": True,
           "stock_return_pct": round(case["stock"], 2) if case["exact"] else case["stock"],
           "realized_excess_pct": round(case["excess"], 2) if case["exact"] else case["excess"]}
    if case["exact"]:
        row.update(stock_return_pct_unrounded=case["stock"],
                   realized_excess_pct_unrounded=case["excess"], favorable=case["excess"] > 0)
    for metric in ("avoidance", "capture"):
        summary = _risk_metric_summary([row], metric, -0.4)
        assert summary["rate"] == case[metric]
        assert summary["observed"] == (0 if case[metric] is None else 1)
        assert summary["missing"] == (1 if case[metric] is None else 0)
    assert _blowup_avoidance_rate([row]) == case["avoidance"]
    assert _downside_capture_rate([row]) == case["capture"]


@pytest.mark.parametrize("known", [False, True])
def test_scorecard_separates_legacy_missing_outcomes_from_stored_brier(tracker, state, monkeypatch, known):
    base = tracking_quote_scenarios()["base_row"]
    unknown = dict(base, ticker="SYNUNKNOWN", scored=True, implied_prob=0.8,
                   stock_return_pct=-41.0, realized_excess_pct=0.0, brier=0.04, rating="避开")
    rows = [unknown]
    if known:
        rows.append(dict(unknown, ticker="SYNKNOWN", realized_excess_pct_unrounded=0.001,
                         stock_return_pct_unrounded=-41.0, favorable=True))
    before = deepcopy(rows)
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: rows)
    destination = Path(state["companion"]) / "data" / "metrics" / "scorecard.md"
    monkeypatch.setattr(tracker, "SCORECARD_FILE", destination)
    tracker.cmd_scorecard(SimpleNamespace())
    scorecard = destination.read_text(encoding="utf-8")
    assert rows == before
    assert f"**Outcome coverage:** {int(known)}/{len(rows)}; missing 1" in scorecard
    assert f"all {len(rows)} stored scores" in scorecard
    assert "| SYNUNKNOWN | 避开 | 0.80 | 0.0 | UNKNOWN | 0.04 |" in scorecard
    assert ("**Overall hit rate (stock beat benchmark):** 100.0%" if known
            else "**Overall hit rate (stock beat benchmark):** N/A") in scorecard
    calibration = next(line for line in scorecard.splitlines() if line.startswith("| 0.70–1.01 |"))
    assert (f"| {len(rows)} | 1 | 0.800 | 1.00 | +0.20 |" if known
            else "| 1 | 0 | — | — | — |") in calibration
    downside = next(line for line in scorecard.splitlines() if line.startswith("| Downside-capture"))
    assert f"coverage {int(known)}/{len(rows)}; missing 1" in downside
