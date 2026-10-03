"""Generated numeric-domain regressions with synthetic debt evidence."""
from copy import deepcopy
import json

import pytest

from make_fixtures import source27_scenarios
from test_financial_evidence import valuation_module
from test_private_runs import state
from _valuation_model import _VALUATION_DEFAULTS

CASE = source27_scenarios()


@pytest.mark.parametrize("name", list(CASE["debt"]))
def test_debt_numeric_domain_reaches_valuation_without_exception(valuation_module, name):
    case = CASE["debt"][name]
    data = json.loads(json.dumps(case["data"], allow_nan=False))
    before = deepcopy(data)
    result = valuation_module.compute_valuation(data, CASE["market_cap"], dict(_VALUATION_DEFAULTS))
    assert result["debt_evidence_status"] == case["status"]
    assert result["debt_evidence_uncertain"] is case["uncertain"]
    assert result["buy_eligible"] is (not case["uncertain"])
    assert data == before
    if case["uncertain"]:
        assert result["ev"] is None
        assert result["ev_sales"] is None
        assert result["ev_ebitda"] is None
        assert "debt_evidence_uncertain" in result["buy_ineligible_reasons"]
    else:
        derived = data["derived"]
        assert result["ev"] == CASE["market_cap"] + derived["latest_total_debt"] - derived["latest_cash"]
        assert result["margin_of_safety_pct"] == 0.3889
