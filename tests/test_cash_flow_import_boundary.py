"""Cash-flow pairing preserves the existing offline debt injection boundary."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from make_fixtures import deepdive_input_scenarios
from test_debt_evidence import debt_module, pull_case


def test_pairing_helper_needs_no_application_modules(monkeypatch):
    for name in ('_common', 'valuation', 'edgar'):
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.delitem(sys.modules, '_cash_flow_evidence', raising=False)
    helper = importlib.import_module('_cash_flow_evidence')
    case = deepdive_input_scenarios()['fcf'][0]
    original = deepcopy(case)

    actual = helper.paired_cash_flow_evidence(
        case['ocf'], case['capex'], case.get('proxy', False))

    assert len(actual) == len(case['expected'])
    for period, expected in zip(actual, case['expected']):
        assert {key: period[key] for key in expected} == expected
    assert case == original


def test_real_pull_preserves_debt_when_valuation_is_unavailable(debt_module, monkeypatch):
    monkeypatch.setitem(sys.modules, 'valuation', None)

    result = pull_case(debt_module, monkeypatch)

    assert result['derived']['debt_evidence_status'] == 'reported'
