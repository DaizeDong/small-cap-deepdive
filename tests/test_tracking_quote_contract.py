"""Quote validation retains dated evidence and leaves unsupported outcomes unscored."""
from copy import deepcopy
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from make_fixtures import tracking_quote_scenarios
from test_private_runs import state

CASE = tracking_quote_scenarios()


def _unexpected_fetch(*args, **kwargs):
    pytest.fail("A quote fetch was not expected for this synthetic case")


@pytest.fixture
def tracker(state, monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=_unexpected_fetch))
    module = importlib.import_module("track_forward")
    monkeypatch.setattr(module, "DEFAULT_BENCHMARK", CASE["benchmark"])
    monkeypatch.setattr(module, "_today", lambda: CASE["today"])
    return module


class _SyntheticHistory:
    def __init__(self, case):
        self.index = case["dates"]
        self.columns = case["columns"]
        self.values = case["values"]
        self.empty = not self.values
        self.iloc = self

    def __getitem__(self, position):
        row, column = position
        return self.values[row][column]


def _install_quotes(monkeypatch, tracker, quotes):
    calls = []

    def fetch(ticker, on_date, verbose=False, *, evidence=None):
        calls.append((ticker, on_date))
        quote = deepcopy(quotes[ticker])
        if evidence is not None:
            evidence.update(quote)
        return quote["price"]

    monkeypatch.setattr(tracker, "_fetch_close", fetch)
    return calls


def _install_rows(monkeypatch, tracker, rows):
    saved = []
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: rows)
    monkeypatch.setattr(tracker, "_save_verdicts", lambda result: saved.append(deepcopy(result)))
    return saved


@pytest.mark.parametrize("case", CASE["provider_cases"], ids=lambda case: case["name"])
def test_provider_quote_requires_value_date_and_identified_column(tracker, monkeypatch, case):
    calls = []

    def download(ticker, **kwargs):
        calls.append((ticker, kwargs))
        return _SyntheticHistory(case)

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    evidence = {}
    value = tracker._fetch_close(CASE["ticker"], CASE["requested"], evidence=evidence)
    assert len(calls) == 1
    assert calls[0][0] == CASE["ticker"]
    assert calls[0][1]["start"] == CASE["download_start"]
    assert calls[0][1]["end"] == CASE["download_end"]
    assert calls[0][1]["auto_adjust"] is True
    assert value == case["price"]
    assert evidence["available"] is (case["reason"] is None)
    assert evidence["reason"] == case["reason"]
    assert evidence["resolved_date"] == case["resolved"]
    if evidence["available"]:
        assert evidence["price"] == value
        assert evidence["requested_date"] == CASE["requested"]
        assert evidence["ticker"] == CASE["ticker"]
        assert evidence["source"] == "yfinance"
        assert evidence["price_basis"] == "yfinance_auto_adjust"
        assert evidence["price_column"] == case["field"]


@pytest.mark.parametrize("on_date", CASE["invalid_requested_dates"])
def test_invalid_requested_date_stops_before_provider(tracker, on_date):
    evidence = {}
    assert tracker._fetch_close(CASE["ticker"], on_date, evidence=evidence) is None
    assert evidence["available"] is False
    assert evidence["reason"] == "invalid_requested_date"


def test_provider_exception_has_a_bounded_unavailable_reason(tracker, monkeypatch):
    def download(*args, **kwargs):
        raise RuntimeError(CASE["provider_exception"])

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    quote = tracker._quote_on(CASE["ticker"], CASE["requested"])
    assert quote["available"] is False
    assert quote["price"] is None
    assert quote["reason"] == "quote_fetch_error"
    assert quote["error_type"] == "RuntimeError"
    assert CASE["provider_exception"] not in repr(quote)


def test_fetch_close_keeps_the_original_float_api(tracker, monkeypatch):
    case = CASE["provider_cases"][0]
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(
        download=lambda *args, **kwargs: _SyntheticHistory(case)))
    assert tracker._fetch_close(CASE["ticker"], CASE["requested"]) == case["price"]


def test_legacy_float_injection_does_not_become_evidence(tracker, monkeypatch):
    monkeypatch.setattr(tracker, "_fetch_close", lambda *args, **kwargs: CASE["base_row"]["entry_price"])
    quote = tracker._quote_on(CASE["ticker"], CASE["base_row"]["verdict_date"])
    assert quote["available"] is False
    assert quote["price"] is None
    assert quote["reason"] == "quote_evidence_missing"


def test_none_return_does_not_become_available_from_evidence(tracker, monkeypatch):
    def fetch(ticker, on_date, verbose=False, *, evidence=None):
        evidence.update(deepcopy(CASE["entry_quotes"][ticker]))
        return None

    monkeypatch.setattr(tracker, "_fetch_close", fetch)
    quote = tracker._quote_on(CASE["ticker"], CASE["base_row"]["verdict_date"])
    assert quote["available"] is False
    assert quote["price"] is None
    assert quote["reason"] == "invalid_quote_price"


@pytest.mark.parametrize("case", CASE["no_fetch"], ids=lambda case: case["name"])
def test_invalid_entry_evidence_remains_unscored_without_fetch(tracker, monkeypatch, case):
    row = deepcopy(case["row"])
    before = deepcopy(row)
    saved = _install_rows(monkeypatch, tracker, [row])
    monkeypatch.setattr(tracker, "_fetch_close", _unexpected_fetch)
    tracker.cmd_score(SimpleNamespace())
    assert row["scored"] is False
    assert row["score_unavailable_reason"] == case["reason"]
    assert repr(row["entry_price"]) == repr(before["entry_price"])
    assert repr(row["benchmark_entry_price"]) == repr(before["benchmark_entry_price"])
    assert row["stock_return_pct"] is None
    assert row["realized_excess_pct"] is None
    assert row["brier"] is None
    assert "horizon_quote" not in row
    assert len(saved) == 1


@pytest.mark.parametrize("case", CASE["score_cases"], ids=lambda case: case["name"])
def test_scoring_uses_validated_horizon_quotes(tracker, monkeypatch, case):
    row = deepcopy(case["row"])
    _install_rows(monkeypatch, tracker, [row])
    calls = []
    def download(ticker, **kwargs):
        calls.append((ticker, kwargs))
        entry = row["entry_quote"] if ticker == CASE["ticker"] else row["benchmark_entry_quote"]
        end = case["quotes"][ticker]
        return _SyntheticHistory({"dates": [entry["resolved_date"], end["resolved_date"]],
                                  "columns": ["Close"], "values": [[entry["price"]], [end["price"]]]})
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    tracker.cmd_score(SimpleNamespace())
    assert len(calls) == 2
    assert "horizon_quote" in row and "benchmark_horizon_quote" in row
    if case["reason"] is None:
        assert row["scored"] is True
        for field in ("stock_return_pct", "realized_excess_pct", "brier"):
            assert row[field] == case[field]
        assert "score_unavailable_reason" not in row
    else:
        assert row["scored"] is False
        assert row["score_unavailable_reason"] == case["reason"]
        assert row["stock_return_pct"] is None
        assert row["realized_excess_pct"] is None
        assert row["brier"] is None


def test_already_scored_legacy_row_is_untouched(tracker, monkeypatch):
    row = deepcopy(CASE["scored_row"])
    before = deepcopy(row)
    saved = _install_rows(monkeypatch, tracker, [row])
    monkeypatch.setattr(tracker, "_fetch_close", _unexpected_fetch)
    tracker.cmd_score(SimpleNamespace())
    assert row == before
    assert saved == [[before]]


@pytest.mark.parametrize("builder", ["flags", "json"])
def test_new_records_persist_entry_quote_evidence(tracker, monkeypatch, tmp_path, builder):
    _install_quotes(monkeypatch, tracker, CASE["entry_quotes"])
    if builder == "flags":
        row = tracker._build_verdict_from_flags(SimpleNamespace(**CASE["flags"]))
    else:
        payload = tmp_path / "synthetic-verdict.json"
        payload.write_text(json.dumps(CASE["record_payload"]), encoding="utf-8")
        row = tracker._build_verdicts_from_json(payload)[0]
    assert row["entry_quote"] == CASE["entry_quotes"][CASE["ticker"]]
    assert row["benchmark_entry_quote"] == CASE["entry_quotes"][CASE["benchmark"]]
    assert row["entry_price"] == row["entry_quote"]["price"]
    assert row["benchmark_entry_price"] == row["benchmark_entry_quote"]["price"]
    assert row["scored"] is False


def test_backfill_preserves_non_null_legacy_values(tracker, monkeypatch):
    row = deepcopy(CASE["legacy_row"])
    before = deepcopy(row)
    saved = _install_rows(monkeypatch, tracker, [row])
    monkeypatch.setattr(tracker, "_fetch_close", _unexpected_fetch)
    tracker.cmd_backfill(SimpleNamespace())
    assert row == before
    assert saved == [[before]]


def test_backfill_does_not_rewrite_already_scored_incomplete_row(tracker, monkeypatch):
    row = deepcopy(CASE["scored_incomplete_row"])
    before = deepcopy(row)
    saved = _install_rows(monkeypatch, tracker, [row])
    monkeypatch.setattr(tracker, "_fetch_close", _unexpected_fetch)
    tracker.cmd_backfill(SimpleNamespace())
    assert row == before
    assert saved == [[before]]


def test_backfill_records_evidence_for_missing_values(tracker, monkeypatch):
    row = deepcopy(CASE["missing_row"])
    _install_rows(monkeypatch, tracker, [row])
    calls = _install_quotes(monkeypatch, tracker, CASE["entry_quotes"])
    tracker.cmd_backfill(SimpleNamespace())
    assert len(calls) == 2
    assert row["entry_quote"] == CASE["entry_quotes"][CASE["ticker"]]
    assert row["benchmark_entry_quote"] == CASE["entry_quotes"][CASE["benchmark"]]
    assert row["entry_price"] == row["entry_quote"]["price"]
    assert row["benchmark_entry_price"] == row["benchmark_entry_quote"]["price"]


def test_partial_backfill_preserves_invalid_legacy_value_without_formatting_failure(tracker, monkeypatch):
    row = deepcopy(CASE["partial_invalid_row"])
    _install_rows(monkeypatch, tracker, [row])
    calls = _install_quotes(monkeypatch, tracker, CASE["entry_quotes"])
    tracker.cmd_backfill(SimpleNamespace())
    assert calls == [(CASE["benchmark"], row["verdict_date"])]
    assert row["entry_price"] == CASE["partial_invalid_row"]["entry_price"]
    assert row["benchmark_entry_price"] == CASE["entry_quotes"][CASE["benchmark"]]["price"]


def test_backfill_keeps_unavailable_values_missing(tracker, monkeypatch):
    row = deepcopy(CASE["missing_row"])
    _install_rows(monkeypatch, tracker, [row])
    quotes = {symbol: CASE["unavailable_quote"] for symbol in (CASE["ticker"], CASE["benchmark"])}
    _install_quotes(monkeypatch, tracker, quotes)
    tracker.cmd_backfill(SimpleNamespace())
    assert row["entry_price"] is None and row["benchmark_entry_price"] is None
    assert row["entry_quote"]["reason"] == "no_quotes"
    assert row["benchmark_entry_quote"]["reason"] == "no_quotes"
