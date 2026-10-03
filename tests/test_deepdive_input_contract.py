"""The generated W02 corpus exercises parsed evidence and period selection."""
from copy import deepcopy
import importlib
import sys

import pytest

from make_fixtures import deepdive_input_scenarios
from test_private_runs import state
from test_financial_evidence import valuation_module


CASES = deepdive_input_scenarios()


@pytest.fixture
def deepdive_module(state, monkeypatch):
    for name in ("deepdive_data", "_deepdive_concepts", "_deepdive_flags", "_common"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("deepdive_data")


@pytest.mark.parametrize("case", CASES["insider"], ids=lambda case: case["id"])
def test_insider_result_requires_a_recognized_complete_scope(deepdive_module, case):
    result = deepdive_module._parse_insider_page(
        case["html"], case["ticker"], case["response_url"], case["observed_at"])
    for field, expected in case["expected"].items():
        assert result[field] == expected
    if not result["available"]:
        assert result["net_signal"] is None
        assert result["reason"]
    else:
        assert result["provenance"]["complete"]
        assert result["provenance"]["schema"] == "openinsider_trade_table"
        assert result["provenance"]["window_basis"] == "filing_date"
        assert result["provenance"]["html_sha256"]


@pytest.mark.parametrize("case", CASES["fcf"], ids=lambda case: case["id"])
def test_fcf_requires_matching_annual_operands(valuation_module, case):
    periods = valuation_module.paired_cash_flow_evidence(
        case["ocf"], case["capex"], case.get("proxy", False))
    assert len(periods) == len(case["expected"])
    for actual, expected in zip(periods, case["expected"]):
        for field, value in expected.items():
            assert actual[field] == value
        if actual["qualified"]:
            assert actual["capex_complete"]
            assert actual["operands"]["ocf"]["start"] == actual["operands"]["capex"]["start"]
            assert actual["operands"]["ocf"]["end"] == actual["operands"]["capex"]["end"]
            assert actual["val"] == actual["ocf"] - actual["capex"]
        else:
            assert actual["val"] is None
            assert actual["reason"]


@pytest.mark.parametrize("case", CASES["valuation"], ids=lambda case: case["id"])
def test_both_valuation_routes_use_the_same_period_evidence(valuation_module, case):
    result = valuation_module.compute_valuation(
        deepcopy(case["data"]), case["market_cap"], deepcopy(case["config"]))
    for field, expected in case["expected"].items():
        assert result[field] == expected
    latest = result["latest_fcf_evidence"]
    assert latest is not None
    assert latest["end"] == case["expected_latest_end"]
    selected = result["fcf_normalization"]["periods"]
    assert [row["end"] for row in selected] == case["expected_selected_ends"]
    if any(not row["qualified"] for row in selected):
        assert result["normalized_fcf"] is None
        assert result["normalized_fcf_is_proxy"]
    if not result["cyclical"]:
        assert selected == [latest]
        assert result["normalized_fcf"] == latest["val"]
