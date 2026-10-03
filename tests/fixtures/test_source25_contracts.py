"""Generated Source25 contracts. All observations and identities are synthetic."""
import ast
from copy import deepcopy
import importlib
import itertools
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_private_runs import state
from test_source22_contracts import modules
from test_debt_evidence import debt_module
from test_financial_evidence import valuation_module
from make_fixtures import annual_fact_scenarios, annual_fact_response, source25_annual_cashflows

CASE = json.loads(Path(__file__).with_name("source25_contracts.json").read_text(encoding="utf-8"))
ROOT = Path(__file__).resolve().parents[2]


def selected(path, names, namespace=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    context = {} if namespace is None else dict(namespace)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), context)
    return context


@pytest.mark.parametrize("case", CASE["mos"], ids=lambda case: case["name"])
def test_persisted_mos_is_always_in_report_percent_units(modules, case):
    assert modules["finalize_run"]._verdict_mos_pct(case["parsed"], case["valuation"]) == case["expected"]


@pytest.mark.parametrize("basis", ["fcf_cap", "nav"])
def test_finalizer_fallback_matches_explicit_percent_report(modules, state, monkeypatch, basis):
    finalizer = modules["finalize_run"]
    directory = Path(state["root"])
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / ("report_" + CASE["ticker"] + ".md")
    field = "margin_of_safety_pct" if basis == "fcf_cap" else "nav_margin_of_safety_pct"
    monkeypatch.setattr(finalizer, "_find_json", lambda *_args, **_kwargs:
                        {"ticker": CASE["ticker"], "valuation": {field: 0.375}})
    rows = []
    for mos in ("null", "37.5"):
        report.write_text(CASE["report"].format(basis=basis, mos=mos), encoding="utf-8")
        rows.append(finalizer.build_verdict(CASE["ticker"], directory, None))
    assert rows[0]["margin_of_safety_pct"] == rows[1]["margin_of_safety_pct"] == 37.5


@pytest.mark.parametrize("case", CASE["debt"], ids=lambda case: case["name"])
def test_debt_preserves_aggregate_and_component_coverage(debt_module, monkeypatch, case):
    calls = []
    def query(_cik, concept, **_kwargs):
        calls.append(concept)
        return deepcopy(case["concepts"].get(concept, []))
    monkeypatch.setattr(debt_module._dc, "_one_concept", query)
    rows, _ = debt_module._dc._debt_series(CASE["cik"])
    assert rows[-1]["val"] == case["expected"]
    assert rows[-1]["debt_evidence_status"] == case["status"]
    assert "Liabilities" not in calls
    assert "LongTermDebt" in calls
    if case["name"] == "partial_with_aggregate":
        assert rows[-1]["components"]["LongTermDebtNoncurrent"] == 20
        assert rows[-1]["aggregates"]["LongTermDebt"] == 100


@pytest.mark.parametrize("name", ["complete_components", "partial_component",
                                  "partial_with_aggregate", "conflicting_aggregate"])
def test_debt_status_reaches_producer_and_buy_guard(debt_module, monkeypatch, name):
    case = next(case for case in CASE["debt"] if case["name"] == name)
    query = lambda _cik, concept, **_kwargs: deepcopy(case["concepts"].get(concept, []))
    monkeypatch.setattr(debt_module._dc, "_one_concept", query)
    monkeypatch.setattr(debt_module, "_one_concept", query)
    result = debt_module.pull(CASE["ticker"], CASE["cik"], yf_fn=lambda _ticker: None)
    derived = result["derived"]
    assert derived["latest_total_debt"] == case["expected"]
    assert derived["debt_evidence_status"] == case["status"]
    assert derived["debt_evidence_uncertain"] == (case["status"] != "reported")
    from _valuation_eligibility import compose_buy_eligibility
    eligible, reasons = compose_buy_eligibility(
        {}, extreme_mos_review_required=False, large_cap_out_of_scope=False,
        fcf_sustainability_uncertain=False, financial_sic_forced_unsuitable=False,
        insurance_concepts_present=False, concentration_flag=None,
        fundamental_decline_flag=False, peak_contamination_flag=False,
        cross_source_mismatch=False, normalization_masks_current_loss=False,
        mos=0.5, nav_mos=None, mos_basis="fcf_cap",
        debt_evidence_uncertain=derived["debt_evidence_uncertain"])
    assert eligible == (case["status"] == "reported")
    assert ("debt_evidence_uncertain" in reasons) == (case["status"] != "reported")


@pytest.mark.parametrize("case", CASE["ownership"], ids=lambda case: case["name"])
def test_ownership_count_requires_complete_acquisition_parse_and_pagination(modules, case):
    signals = importlib.import_module("signals")
    report = importlib.import_module("make_report")
    tracker = importlib.import_module("track_forward")
    pages = iter(deepcopy(case["pages"]))
    def request(*_args, **_kwargs):
        page = next(pages)
        return SimpleNamespace(status_code=page["http_status"], json=lambda: page["payload"])
    own = signals.compute_ownership(CASE["ticker"], CASE["cik"], http_fn=request)
    assert own["recent_13d_13g_count"] == case["count"]
    assert len(own["recent_13d_13g"]) == case["observed"]
    completion = own["recent_13d_13g_completion"]
    assert completion["status"] == case["status"]
    assert completion["reason"] == case["reason"]
    rendered = report._render_ownership(own)
    if case["status"] != "complete":
        assert "none found" not in rendered
        assert "null (unavailable;" in rendered
    elif case["count"] == 0:
        assert "none found" in rendered
    snapshot = tracker._signals_snapshot({"ownership": own})
    assert snapshot["ownership"]["recent_13d_13g_count"] == case["count"]
    assert snapshot["ownership"]["recent_13d_13g_completion"] == completion


def test_retired_history_route_cannot_write_or_change_calibration(modules, monkeypatch):
    tracker = importlib.import_module("track_forward")
    calls = []
    monkeypatch.setattr(tracker, "_append_verdict", lambda row: calls.append(row))
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: calls.append("read"))
    with pytest.raises(RuntimeError, match="retired"):
        tracker.cmd_backfill_validation_fp(SimpleNamespace())
    assert calls == []
    assert not hasattr(tracker, "VALIDATION_FP")
    assert not hasattr(tracker, "VALIDATION_FP_DATE")


@pytest.mark.parametrize("edit", CASE["invalid_identities"])
@pytest.mark.parametrize("asof", [None, "2024-03-01"])
def test_annual_response_identity_must_match_request(state, monkeypatch, edit, asof):
    import _deepdive_concepts as concepts
    case = annual_fact_scenarios()
    payload = annual_fact_response([case["annual"]])
    payload.update(edit)
    monkeypatch.setattr(concepts, "http_get", lambda *_args, **_kwargs:
                        SimpleNamespace(status_code=200, json=lambda: payload))
    rows = concepts._one_concept(case["cik"], case["concept"], asof=asof)
    assert rows == []
    assert rows.completion["status"] == "invalid"


@pytest.mark.parametrize("reverse", [False, True])
def test_research_selector_applies_shared_annual_duration_rule(state, reverse):
    import _deepdive_concepts as concepts
    from datetime import date
    functions = selected(ROOT / "docs/backtest-2026-06/distress_features_fast.py",
                         {"_select_concept"}, {"DC": concepts, "date": date})
    case = annual_fact_scenarios()
    values = [case["annual"], case["quarter"]]
    actual = functions["_select_concept"]({"USD": values[::-1] if reverse else values},
                                         case["asof"], case["concept"])
    expected = {key: case["annual"][key]
                for key in ("start", "end", "val", "fy", "filed", "fp", "form")}
    expected.update(duration_days=364, unit="USD", currency="USD",
                    taxonomy="us-gaap", concept=case["concept"])
    assert actual == [expected]
    assert functions["_select_concept"]({"USD": [case["instant"]]},
                                        case["asof"], case["concept"]) == []
    assert functions["_select_concept"]({"USD": [case["instant"]]},
                                        case["asof"], case["instant_concept"])[0]["val"] == 2000


def inference_functions():
    return selected(ROOT / "docs/backtest-2026-06/significance_test.py",
                    {"bucket_statistics", "permutation_inference"})


@pytest.mark.parametrize("kind", ["missing", "empty", "nonfinite"])
def test_significance_unavailable_groups_do_not_create_minimum_p_values(kind):
    data = deepcopy(CASE["inference"]["missing" if kind == "missing" else "complete"])
    if kind == "empty":
        data = {"excess": [], "labels": [], "cells": []}
    elif kind == "nonfinite":
        data["excess"][0] = float("nan")
    calls = []
    result = inference_functions()["permutation_inference"](
        **data, permutations=24, shuffle=lambda rows: calls.append(rows))
    assert result["status"] == "unavailable"
    assert result["p_values"] is None
    assert result["permutations"] == 0
    assert calls == []


def test_valid_group_permutations_retain_finite_calculation():
    data = CASE["inference"]["complete"]
    permutations = iter(itertools.permutations(data["labels"]))
    result = inference_functions()["permutation_inference"](
        **data, permutations=24, shuffle=lambda _rows: next(permutations))
    assert result["status"] == "complete"
    assert result["permutations"] == 24
    assert result["observed"]["medians"] == data["excess"]
    # With singleton buckets every permutation has the same omnibus variance.
    assert result["exceedances"][2] == 24
    assert result["p_values"][2] == 1.0
    assert all(0 < value <= 1 for value in result["p_values"])


@pytest.mark.parametrize("missing_start", [False, True])
def test_positive_valuation_fixture_requires_annual_cashflow_dates(valuation_module, missing_start):
    from make_fixtures import financial_scenarios
    fixture = financial_scenarios()
    data = deepcopy(fixture["complete"])
    data["financials"].update(source25_annual_cashflows())
    if missing_start:
        for field in ("ocf", "capex"):
            data["financials"][field][0].pop("start")
    value = valuation_module.compute_valuation(data, fixture["buy_market_cap"], fixture["config"])
    assert value["buy_eligible"] is (not missing_start)
    assert ("fcf_sustainability_uncertain" in value["buy_ineligible_reasons"]) is missing_start
    if missing_start:
        assert value["intrinsic_value_band"] is None


@pytest.mark.parametrize("case", CASE["equity_basis"], ids=lambda case: case["name"])
@pytest.mark.parametrize("extra_cash", [0, 30_000_000])
def test_post_interest_fcf_has_no_net_cash_addback(valuation_module, case, extra_cash):
    from _valuation_model import _VALUATION_DEFAULTS
    data = deepcopy(case["data"])
    data["derived"]["latest_cash"] += extra_cash
    value = valuation_module.compute_valuation(data, case["market_cap"], dict(_VALUATION_DEFAULTS))
    assert value["mos_basis"] == "fcf_cap"
    assert value["intrinsic_value_band"]["equity_low"] == case["equity_low"]
    assert value["margin_of_safety_pct"] == case["mos"]
    assert value["buy_eligible"] is True
    assert (value["margin_of_safety_pct"] >= 0.30) is case["meets_threshold"]
