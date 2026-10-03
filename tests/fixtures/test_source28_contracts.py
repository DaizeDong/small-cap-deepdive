
"""Generated Source28 regressions. Inputs are synthetic; tests call shipped modules."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from make_fixtures import (source28_scenarios, source28_realize, source28_bound_sample,
                           source25_equity_basis_scenarios, tracking_quote_scenarios)
from test_private_runs import state
from test_financial_evidence import valuation_module
from test_source22_contracts import modules
from test_tracking_quote_contract import tracker
from test_deepdive_producer_completion import runtime
import test_deepdive_producer_completion as producer_tests

CASE = source28_scenarios()
QUOTE = tracking_quote_scenarios()


def forbidden(*args, **kwargs):
    pytest.fail("An external acquisition or ledger write was not expected")


@pytest.mark.parametrize("case", CASE["bound"], ids=lambda case: case["name"])
def test_bound_report_cannot_override_valuation_before_persistence(runtime, valuation_module, monkeypatch, case):
    sample = source28_bound_sample(case)
    _, request_path = producer_tests.prepared(runtime, sample, monkeypatch)
    producer = producer_tests.producer
    request = json.loads(request_path.read_text(encoding="utf-8"))
    snapshots = {Path(row[key]): Path(row[key]).read_bytes()
                 for row in request["candidates"] for key in ("json_path", "valuation_path")}
    block = json.loads(Path(request["candidates"][0]["valuation_path"]).read_text(encoding="utf-8"))
    assert block["mos_basis"] == "fcf_cap"
    assert block["buy_eligible"] is (not case.get("valuation_ineligible", False))
    assert block["margin_of_safety_pct"] == 0.3889
    result_path = producer_tests.response(runtime, sample, request_path, "success")
    output, reports, completion = producer.persist_fanout_result(request_path, result_path)
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    first, peer = rows
    assert peer["report_status"] == "complete"
    assert peer["report"]["rating"] == "\u89c2\u5bdf"
    assert completion["status"] == "partial"
    first_path = request_path.parent / ("report_" + first["ticker"] + ".md")
    if case["error"]:
        assert first["report_status"] == "error"
        assert first["error_code"] == case["error"]
        assert "report" not in first
        assert not first_path.exists()
        assert len(reports) == 1
    else:
        assert first["report_status"] == "complete"
        assert first["report"]["rating"] == case["report"]["rating"]
        assert first_path.read_text(encoding="utf-8") == first["report"]["report_md"]
        assert len(reports) == 2
        receipt = producer_tests.stages.read_stage_receipt(first_path, 1)
        assert receipt["valuation_artifact"] == producer._binding(
            Path(request["candidates"][0]["valuation_path"]))
    assert {path: path.read_bytes() for path in snapshots} == snapshots


@pytest.mark.parametrize("case", CASE["annual"], ids=lambda case: case["name"])
def test_annual_ebitda_requires_compatible_periods_units_and_values(valuation_module, case):
    evidence = importlib.import_module("_cash_flow_evidence")
    data = source28_realize(deepcopy(case))
    periods = evidence.paired_annual_sum_evidence(data["left"], data["right"])
    assert [row["val"] for row in periods] == data["values"]
    assert [row["qualified"] for row in periods] == [value is not None for value in data["values"]]
    if data["reason"] is not None:
        assert all(row["reason"] == data["reason"] for row in periods)
    rows, incomplete = valuation_module._build_ebitda_series(data["left"], data["right"])
    assert rows == [{"end": row["end"], "val": row["val"]} for row in periods if row["qualified"]]
    assert incomplete == sum(value is None for value in data["values"])
    assert all(set(row["operands"]) == {"ebit", "dep_amort"} for row in periods)


@pytest.mark.parametrize("case", CASE["annual"], ids=lambda case: case["name"])
def test_pretax_addback_uses_the_same_qualified_annual_pairing(modules, monkeypatch, case):
    concepts = importlib.import_module("_deepdive_concepts")
    data = source28_realize(deepcopy(case))
    monkeypatch.setattr(concepts.time, "sleep", lambda *_: None)
    monkeypatch.setattr(concepts, "concept_series",
                        lambda cik, tags, **kwargs: deepcopy(
                            data["left"] if tags == concepts.EBIT_PRETAX_CONCEPTS else data["right"]))
    rows, source = concepts._ebit_with_source("0000000001", [])
    ends = sorted({row["end"] for row in data["left"] + data["right"]})
    expected = dict(zip(ends, data["values"]))
    qualified = {end: value for end, value in expected.items() if value is not None}
    assert source == ("pretax+interest_addback" if qualified else "pretax_proxy")
    assert len(rows) == len(data["left"])
    for row, original in zip(rows, data["left"]):
        assert row["val"] == qualified.get(original["end"], original["val"])
        assert row.get("start") == original.get("start")
        if original["end"] in qualified:
            assert set(row["operands"]) == {"pretax", "interest"}
            assert row["operands"]["pretax"]["start"] == row["operands"]["interest"]["start"]


@pytest.mark.parametrize("case", CASE["concepts"], ids=lambda case: case["name"])
def test_concept_unit_selection_preserves_annual_identity(modules, monkeypatch, case):
    concepts = importlib.import_module("_deepdive_concepts")
    fact = deepcopy(CASE["concept_fact"])
    fact["accn"] = "synthetic-accession"
    payload = {"cik": 123, "taxonomy": "us-gaap", "tag": case["concept"],
               "units": {case["unit"]: [fact]}}
    monkeypatch.setattr(concepts, "http_get",
                        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: payload))
    rows = concepts._one_concept("0000000123", case["concept"], asof="2001-03-01")
    assert rows.completion["status"] == case["status"]
    if case["status"] == "complete":
        assert len(rows) == 1 and rows[0]["val"] == fact["val"]
        assert rows[0]["unit"] == case["unit"]
        assert rows[0]["cik"] == "0000000123"
        assert rows[0]["concept"] == case["concept"]
        assert rows[0]["accn"] == fact["accn"]
        if case["concept"] != "CommonStockSharesOutstanding":
            assert rows[0]["start"] == fact["start"]
            assert rows[0]["duration_days"] == fact["duration_days"]
    else:
        assert rows == []


def test_depreciation_cascade_keeps_period_and_accession(modules, monkeypatch):
    concepts = importlib.import_module("_deepdive_concepts")
    fact = deepcopy(CASE["concept_fact"])
    fact["accn"] = "synthetic-accession"
    monkeypatch.setattr(concepts.time, "sleep", lambda *_: None)
    monkeypatch.setattr(concepts, "_one_concept",
                        lambda cik, tag, **kwargs: [deepcopy(fact)] if tag == concepts.DA_CONCEPTS[0] else [])
    rows, source = concepts._da_series("0000000001")
    assert source == concepts.DA_CONCEPTS[0]
    assert rows[0]["start"] == fact["start"]
    assert rows[0]["end"] == fact["end"]
    assert rows[0]["accn"] == fact["accn"]


@pytest.mark.parametrize("case", CASE["confidence_invalid"], ids=lambda case: case["name"])
def test_json_confidence_preflight_rejects_later_invalid_row_before_quotes_or_writes(
        tracker, monkeypatch, tmp_path, case):
    value = source28_realize(case["value"])
    rows = [dict(QUOTE["record_payload"], confidence=0.7),
            dict(QUOTE["record_payload"], ticker="SYNQ2", confidence=value)]
    path = tmp_path / "synthetic-verdicts.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(tracker, "_quote_on", forbidden)
    monkeypatch.setattr(tracker, "_append_verdict", forbidden)
    monkeypatch.setattr(tracker, "_load_verdicts", forbidden)
    with pytest.raises(ValueError, match="Confidence"):
        tracker.cmd_record(SimpleNamespace(record_path=str(path)))


@pytest.mark.parametrize("case", CASE["confidence_invalid"], ids=lambda case: case["name"])
def test_flag_confidence_rejects_invalid_domain_before_quote(tracker, monkeypatch, case):
    flags = dict(QUOTE["flags"], confidence=source28_realize(case["value"]))
    monkeypatch.setattr(tracker, "_quote_on", forbidden)
    with pytest.raises(ValueError, match="Confidence"):
        tracker._build_verdict_from_flags(SimpleNamespace(**flags))


@pytest.mark.parametrize("rating,direction", [("\u4e70\u5165", 1), ("\u89c2\u5bdf", 0), ("\u907f\u5f00", -1)])
@pytest.mark.parametrize("case", CASE["confidence_valid"], ids=lambda case: case["name"])
def test_valid_confidence_units_direction_and_storage_are_preserved(tracker, monkeypatch, case, rating, direction):
    flags = dict(QUOTE["flags"], rating=rating, confidence=case["value"])
    calls = []
    def quote(ticker, date, verbose=False):
        calls.append((ticker, date))
        return deepcopy(QUOTE["entry_quotes"][ticker])
    monkeypatch.setattr(tracker, "_quote_on", quote)
    row = tracker._build_verdict_from_flags(SimpleNamespace(**flags))
    expected = min(0.999, max(0.001, 0.5 + direction * (case["fraction"] - 0.5)))
    assert row["confidence"] == float(case["value"])
    assert row["implied_prob"] == pytest.approx(expected)
    assert len(calls) == 2


@pytest.mark.parametrize("value", CASE["omitted_confidence"])
@pytest.mark.parametrize("rating", ["\u4e70\u5165", "\u89c2\u5bdf", "\u907f\u5f00"])
def test_omitted_confidence_keeps_rating_fallback(tracker, value, rating):
    assert tracker._implied_prob_from_confidence(rating, value) == tracker.RATING_PROB[rating]


@pytest.mark.parametrize("case", CASE["probability_invalid"], ids=lambda case: case["name"])
def test_invalid_stored_probability_stays_unscored_without_return_snapshots(tracker, monkeypatch, case):
    row = deepcopy(QUOTE["base_row"])
    if case.get("missing"):
        row.pop("implied_prob")
    else:
        row["implied_prob"] = source28_realize(case["value"])
    saved = []
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])
    monkeypatch.setattr(tracker, "_save_verdicts", lambda rows: saved.append(deepcopy(rows)))
    monkeypatch.setattr(tracker, "_fetch_return_snapshot", forbidden)
    tracker.cmd_score(SimpleNamespace())
    expected = "missing_implied_prob" if case.get("missing") or case.get("value") is None else "invalid_implied_prob"
    assert saved and saved[0][0]["scored"] is False
    assert saved[0][0]["brier"] is None
    assert saved[0][0]["score_unavailable_reason"] == expected


@pytest.mark.parametrize("probability", [0, 0.7, 1])
def test_valid_probability_boundaries_score_with_finite_brier(tracker, monkeypatch, probability):
    row = deepcopy(QUOTE["base_row"])
    row["implied_prob"] = probability
    calls, saved = [], []
    def snapshot(ticker, entry, horizon):
        calls.append(ticker)
        entry_quote = row["entry_quote"] if ticker == row["ticker"] else row["benchmark_entry_quote"]
        return {"available": True, "return_fraction": 0.2 if ticker == row["ticker"] else 0.1,
                "entry_quote": deepcopy(entry_quote), "horizon_quote": {"resolved_date": horizon}}
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])
    monkeypatch.setattr(tracker, "_save_verdicts", lambda rows: saved.append(deepcopy(rows)))
    monkeypatch.setattr(tracker, "_fetch_return_snapshot", snapshot)
    tracker.cmd_score(SimpleNamespace())
    assert calls == [row["ticker"], row["benchmark"]]
    assert saved[0][0]["scored"] is True
    assert saved[0][0]["brier"] == pytest.approx(round((probability - 1) ** 2, 6))


def test_zero_primary_mos_is_not_replaced_by_alternate_value(tracker, monkeypatch, tmp_path):
    path = tmp_path / "synthetic-verdict.json"
    path.write_text(json.dumps(dict(QUOTE["record_payload"], margin_of_safety_pct=0, mos_pct=40)),
                    encoding="utf-8")
    monkeypatch.setattr(tracker, "_quote_on",
                        lambda ticker, *args, **kwargs: deepcopy(QUOTE["entry_quotes"][ticker]))
    assert tracker._build_verdicts_from_json(path)[0]["mos_pct"] == 0


@pytest.mark.parametrize("case", CASE["display"], ids=lambda case: case["name"])
def test_ranking_and_report_distinguish_zero_from_unavailable(modules, state, case):
    report = importlib.import_module("make_report")
    directory = Path(state["root"])
    directory.mkdir(parents=True, exist_ok=True)
    data = {"ticker": "SYNTH", "derived": {name: case["value"]
            for name in ("latest_revenue", "latest_net_income", "latest_ocf")}}
    (directory / "deepdive_SYNTH_2000-01-01.json").write_text(json.dumps(data), encoding="utf-8")
    hard = modules["rank"].load_hard_data("SYNTH", directory)
    number = None if case["value"] is None else round(case["value"] / 1e6, 1)
    assert [hard[name] for name in ("revenue_M", "net_income_M", "ocf_M")] == [number] * 3
    rendered = report.render_report(data, {}, "2000-01-01")
    text = "N/A" if number is None else f"{number:.1f}M"
    assert f"latest rev {text}, NI {text}, OCF {text}" in rendered
    assert "Base rate: unknown until supported" in rendered


@pytest.mark.parametrize("case", CASE["display"][:2], ids=lambda case: case["name"])
def test_valuation_summary_distinguishes_zero_from_unavailable(valuation_module, capsys, case):
    block = dict(ticker="SYNTH", **{name: case["value"]
                 for name in ("market_cap", "ev", "normalized_ebitda", "normalized_fcf")})
    valuation_module._print_valuation_summary(block)
    output = capsys.readouterr().out
    if case["value"] is None:
        for reason in ("market_cap_unavailable", "ev_unavailable",
                       "normalized_ebitda_unavailable", "normalized_fcf_unavailable"):
            assert "null (" + reason + ")" in output
        assert "$0M" not in output
    else:
        assert output.count("$0M") == 4


@pytest.mark.parametrize("case", source25_equity_basis_scenarios(), ids=lambda case: case["name"])
def test_original_18m_and_separate_20m_equity_controls_stay_distinct(valuation_module, case):
    result = valuation_module.compute_valuation(deepcopy(case["data"]), case["market_cap"],
                                               dict(valuation_module._VALUATION_DEFAULTS))
    expected_fcf = 18_000_000 if case["name"] == "original_18m" else 20_000_000
    assert result["normalized_fcf"] == expected_fcf
    assert result["intrinsic_value_band"]["equity_low"] == case["equity_low"]
    assert result["margin_of_safety_pct"] == case["mos"]
    assert (result["buy_eligible"] and result["margin_of_safety_pct"] >= 0.30) is case["meets_threshold"]


@pytest.mark.parametrize("case", CASE["confidence_valid"], ids=lambda case: case["name"])
def test_json_preserves_valid_confidence_units(tracker, monkeypatch, tmp_path, case):
    path = tmp_path / "synthetic-confidence.json"
    path.write_text(json.dumps(dict(QUOTE["record_payload"], confidence=case["value"])), encoding="utf-8")
    monkeypatch.setattr(tracker, "_quote_on",
                        lambda ticker, *args, **kwargs: deepcopy(QUOTE["entry_quotes"][ticker]))
    row = tracker._build_verdicts_from_json(path)[0]
    assert row["confidence"] == float(case["value"])
    assert row["implied_prob"] == pytest.approx(min(0.999, max(0.001, case["fraction"])))


@pytest.mark.parametrize("case", CASE["probability_invalid"], ids=lambda case: case["name"])
def test_brier_defends_its_probability_domain(tracker, case):
    value = source28_realize(case.get("value"))
    with pytest.raises(ValueError, match="probability"):
        tracker._brier(value, True)


@pytest.mark.parametrize("case", CASE["annual"], ids=lambda case: case["name"])
def test_valuation_uses_annual_ebitda_evidence_over_stale_derived_scalar(valuation_module, case):
    data = deepcopy(source25_equity_basis_scenarios()[1]["data"])
    operands = source28_realize(deepcopy(case))
    data["financials"]["ebit"] = operands["left"]
    data["financials"]["dep_amort"] = operands["right"]
    result = valuation_module.compute_valuation(data, 120_000_000,
                                               dict(valuation_module._VALUATION_DEFAULTS))
    expected = operands["values"][-1]
    assert result["latest_ebitda_evidence"]["val"] == expected
    if expected is None or expected == 0:
        assert result["ev_ebitda"] is None
