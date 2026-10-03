"""Exercise both shipped filing callers with generated annual-report statements."""
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from make_fixtures import filing_disclosure_scenarios, filing_negation_scenarios

FIX = filing_disclosure_scenarios()
FIX['cases'].extend(filing_negation_scenarios())


@pytest.fixture
def callers(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('External data is outside generated filing controls')

    common = ModuleType('_common')
    common.init_edgar = lambda: None
    common.UA = 'user1@example.com'
    common.REPORTS = None
    common.CFG = {}
    common.today = lambda: FIX['filing_date']
    common.http_get = blocked
    common.slug = lambda value: value
    common.resolve_mktcap = blocked
    common.band_for = blocked
    monkeypatch.setitem(sys.modules, '_common', common)
    monkeypatch.setitem(sys.modules, 'edgar', SimpleNamespace(Company=blocked))
    for name in ('cheap_pass', 'deepdive_data', '_deepdive_flags', '_deepdive_concepts'):
        monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.delitem(sys.modules, name)
    deep = importlib.import_module('deepdive_data')
    cheap = importlib.import_module('cheap_pass')

    class Filings(list):
        def latest(self, count):
            assert count == 1
            return self[0]

    def run(text):
        filing = SimpleNamespace(text=lambda: text, filing_date=FIX['filing_date'])
        company = SimpleNamespace(get_filings=lambda **kwargs: Filings([filing]))
        monkeypatch.setattr(deep, 'Company', lambda ticker: company)
        monkeypatch.setattr(cheap, 'Company', lambda ticker: company)
        return cheap.killflag_scan(FIX['ticker']), deep.tenk_sections(FIX['ticker'])

    return run


@pytest.mark.parametrize('case', FIX['cases'], ids=lambda row: row['id'])
def test_disclosure_polarity_reaches_both_shipped_callers(callers, case):
    cheap, deep = callers(case['text'])
    assert 'error' not in cheap and 'error' not in deep
    assert deep.get('has_' + case['topic']) is case['flag']
    actual = cheap.get('kf_' + case['topic'])
    assert actual is None if case['flag'] is None else actual == int(case['flag'])
    if case['topic'] == 'going_concern':
        other = cheap.get('kf_substantial_doubt')
        assert other is None if case['flag'] is None else other == int(case['flag'])


@pytest.mark.parametrize('case', FIX['cases'], ids=lambda row: row['id'])
def test_both_callers_keep_exact_evidence_and_unknown_state(callers, case):
    cheap, deep = callers(case['text'])
    for result in (cheap, deep):
        evidence = result.get('disclosure_evidence', {}).get(case['topic'])
        assert evidence is not None
        assert evidence['status'] == case['status']
        assert evidence['flag'] is case['flag']
        assert evidence['spans']
        for span in evidence['spans']:
            assert case['text'][span['start']:span['end']] == span['text']
    assert cheap['disclosure_review_required'] is (case['flag'] is None)
