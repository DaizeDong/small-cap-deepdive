"""Reports must preserve missing assessments and independently observed risk flags."""
from copy import deepcopy
import importlib

import pytest

from test_private_runs import state
from make_fixtures import report_evidence_scenarios

FIX = report_evidence_scenarios()


@pytest.fixture
def report(state):
    return importlib.import_module('make_report')


@pytest.mark.parametrize('name', list(FIX['unknown']))
def test_missing_checks_cannot_render_a_clean_banner(report, name):
    case = FIX['unknown'][name]
    text = report.render_report(case['deep'], case['valuation'], FIX['date'])
    assert 'MoS inputs are clean' not in text
    assert 'unverified:' in text
    if name.startswith('invalid_mos_'):
        assert 'mos_pct: null' in text


@pytest.mark.parametrize('name', ['no_filing', 'unavailable_filing', 'partial_filing', 'invalid_flag'])
def test_unchecked_filing_fields_are_unknown_not_false(report, name):
    case = FIX['unknown'][name]
    text = report.render_report(case['deep'], case['valuation'], FIX['date'])
    assert 'Unknown (not verified)' in text
    assert 'killflag_count: TBD' in text


def test_complete_checked_evidence_retains_clean_output(report):
    text = report.render_report(FIX['deep'], FIX['valuation'], FIX['date'])
    assert 'MoS inputs are clean' in text
    assert 'unverified:' not in text
    assert 'killflag_count: 0' in text
    assert 'has_going_concern: False' in text


@pytest.mark.parametrize('name', [name for name in FIX['unknown'] if name.startswith('invalid_count_')])
def test_invalid_aggregate_count_is_not_a_verified_zero(report, name):
    case = FIX['unknown'][name]
    text = report.render_report(case['deep'], case['valuation'], FIX['date'])
    assert 'killflag_count: TBD' in text
    assert 'unverified: killflag_count' in text


@pytest.mark.parametrize('flag', ['has_going_concern', 'has_material_weakness', 'has_death_spiral'])
def test_explicit_zero_cannot_erase_observed_filing_risk(report, flag):
    deep = deepcopy(FIX['deep'])
    deep['killflag_count'] = 0
    deep['tenk'][flag] = True
    text = report.render_report(deep, FIX['valuation'], FIX['date'])
    assert 'killflag_count: 1' in text
    assert flag in '\n'.join(report.collect_trust_flags(deep, FIX['valuation']))
    assert 'MoS inputs are clean' not in text


@pytest.mark.parametrize('kind', ['concentration', 'distress'])
def test_explicit_zero_cannot_erase_observed_derived_risk(report, kind):
    deep = deepcopy(FIX['deep'])
    deep['killflag_count'] = 0
    deep['derived']['concentration_flag' if kind == 'concentration' else 'distress_kill'] = (
        'kill' if kind == 'concentration' else True)
    text = report.render_report(deep, FIX['valuation'], FIX['date'])
    assert 'killflag_count: 1' in text
    assert 'MoS inputs are clean' not in text


def test_partial_checks_keep_positive_risk_and_disclose_missing_evidence(report):
    deep = deepcopy(FIX['unknown']['partial_filing']['deep'])
    deep['tenk']['has_going_concern'] = True
    text = report.render_report(deep, FIX['valuation'], FIX['date'])
    assert 'killflag_count: 1' in text
    assert 'unverified:' in text
    assert 'has_going_concern: True' in text


def test_rendering_does_not_change_evidence(report):
    deep, val = deepcopy(FIX['deep']), deepcopy(FIX['valuation'])
    report.render_report(deep, val, FIX['date'])
    assert deep == FIX['deep'] and val == FIX['valuation']


def test_existing_report_selftest_uses_complete_evidence(report):
    report._selftest()
