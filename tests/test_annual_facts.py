"""Quarterly facts cannot become annual inputs merely by appearing in a 10-K."""
from types import SimpleNamespace

import pytest

from test_private_runs import state
from make_fixtures import annual_fact_scenarios, annual_fact_response

CASE = annual_fact_scenarios()


def fetch(monkeypatch, facts, asof, concept=None):
    import _deepdive_concepts as concepts
    monkeypatch.setattr(concepts, 'http_get', lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: annual_fact_response(facts, concept=concept)))
    return concepts._one_concept(CASE['cik'], concept or CASE['concept'], asof=asof)


@pytest.mark.parametrize('asof', [None, CASE['asof']])
@pytest.mark.parametrize('reverse', [False, True])
def test_annual_selection_does_not_depend_on_quarter_order(state, monkeypatch, asof, reverse):
    facts = [CASE['annual'], CASE['quarter']]
    rows = fetch(monkeypatch, facts[::-1] if reverse else facts, asof)
    assert len(rows) == 1 and rows[0]['val'] == 1000
    assert rows[0]['start'] == '2023-01-01'
    assert rows[0]['duration_days'] == 364


@pytest.mark.parametrize('asof', [None, CASE['asof']])
@pytest.mark.parametrize('kind', ['quarter', 'transition'])
def test_short_annual_filing_period_is_not_a_full_year(state, monkeypatch, asof, kind):
    assert fetch(monkeypatch, [CASE[kind]], asof) == []


def test_pit_annual_series_retains_latest_eligible_filing(state, monkeypatch):
    rows = fetch(monkeypatch, [CASE['annual'], CASE['restated']], CASE['asof'])
    assert len(rows) == 1 and rows[0]['val'] == 1000
    assert rows[0]['filed'] == '2024-02-01'


@pytest.mark.parametrize('asof', [None, CASE['asof']])
def test_instant_facts_remain_usable_without_flow_duration(state, monkeypatch, asof):
    rows = fetch(monkeypatch, [CASE['instant']], asof, CASE['instant_concept'])
    assert len(rows) == 1 and rows[0]['val'] == 2000
    assert 'start' not in rows[0]


@pytest.mark.parametrize('asof', [None, CASE['asof']])
@pytest.mark.parametrize('concept', CASE['flow_concepts'])
def test_flow_facts_without_start_are_not_instant_balances(state, monkeypatch, asof, concept):
    assert fetch(monkeypatch, [CASE['instant']], asof, concept) == []
