"""Final decisions retain uncertainty, risk evidence, and their original date."""
import json
from pathlib import Path

import pytest

from test_private_runs import state
from test_finalize_boundaries import invoke
from make_fixtures import decision_scenarios

CASE = decision_scenarios()


def make_run(state, report=None):
    run = Path(state['root']) / 'decision-controls'
    run.mkdir(parents=True)
    if report is not None:
        (run / ('report_' + CASE['ticker'] + '.md')).write_text(report, encoding='utf-8')
        (run / 'all_candidates.json').write_text(json.dumps([CASE['candidate']]), encoding='utf-8')
    return run


@pytest.mark.parametrize('report', CASE['unfinished'], ids=['tbd', 'unknown', 'empty'])
def test_authoritative_unfinished_rating_cannot_replace_ranking(state, monkeypatch, report):
    run = make_run(state, report)
    output = run / 'RANKING.md'
    output.write_text(CASE['prior_output'], encoding='utf-8')
    before = output.read_bytes()
    assert invoke('rank', ['--input', str(run)], monkeypatch) == 2
    assert output.read_bytes() == before
    assert output.read_text(encoding='utf-8') == CASE['prior_output']


@pytest.mark.parametrize('report', CASE['unfinished'] + CASE['bad_confidence'],
                         ids=['tbd', 'unknown', 'empty', 'unset-confidence', 'negative', 'over-100'])
def test_unfinished_decision_does_not_replace_verdict_output(state, monkeypatch, report):
    run = make_run(state, report)
    output = run / 'deepdive_verdicts.json'
    output.write_text(CASE['prior_output'], encoding='utf-8')
    with pytest.raises(ValueError, match='rating|confidence|unfinished|decision'):
        invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch)
    assert output.read_text(encoding='utf-8') == CASE['prior_output']


def test_report_risks_survive_verdict_emission(state):
    from finalize_run import build_verdict
    run = make_run(state, CASE['risk_report'])
    result = build_verdict(CASE['ticker'], run, CASE['date'])
    assert set(result['kill_flags']) >= {'concentration_kill', 'fundamental_decline'}
    assert result['killflag_count'] == 3
    assert result['unresolved_killflag_count'] == 1
    assert result['risk_evidence']['report_count'] == 3


def test_refinalizing_preserves_timestamp_locked_date(state, monkeypatch):
    import _common
    from filter_by_sic import read_stage_receipt
    run = make_run(state, CASE['report'])
    monkeypatch.setattr(_common, 'today', lambda: CASE['later_date'])
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 2
    output = run / 'deepdive_verdicts.json'
    first = json.loads(output.read_text(encoding='utf-8'))
    assert first[0]['verdict_date'] == CASE['date']
    assert len(first[0]['report_sha256']) == 64
    assert read_stage_receipt(output, 1)['status'] != 'complete'
    sealed = [output, Path(str(output) + '.stage.json'),
              run / 'finalization.json', run / 'finalization.json.stage.json']
    snapshots = {path: path.read_bytes() for path in sealed}
    monkeypatch.setattr(_common, 'today', lambda: CASE['date'])
    with pytest.raises(FileExistsError, match='already|sealed'):
        invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch)
    assert {path: path.read_bytes() for path in sealed} == snapshots
    assert json.loads(output.read_text(encoding='utf-8')) == first


def test_prior_verdict_output_is_not_a_deepdive_candidate(state):
    from finalize_run import deep_band_tickers
    run = make_run(state)
    (run / 'deepdive_verdicts.json').write_text(CASE['prior_output'], encoding='utf-8')
    assert deep_band_tickers(run) == set()


@pytest.mark.parametrize('survivors', CASE['empty_survivors'])
def test_unreceipted_empty_survivors_leave_candidates_incomplete(state, monkeypatch, survivors):
    run = make_run(state)
    (run / 'all_candidates.json').write_text(json.dumps([CASE['candidate']]), encoding='utf-8')
    (run / 'candidates_gate2_survivors.json').write_text(json.dumps(survivors), encoding='utf-8')
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 2
    completion = json.loads((run / 'finalization.json').read_text(encoding='utf-8'))
    assert completion['status'] != 'complete'
    assert completion['deep_tickers'] == completion['missing_reports'] == [CASE['ticker']]
    assert not (run / 'deepdive_verdicts.json').exists()
    assert not (run / 'deepdive_verdicts.json.stage.json').exists()


@pytest.mark.parametrize('content', CASE['invalid_candidates'])
def test_invalid_candidate_evidence_cannot_disable_completeness(state, monkeypatch, content):
    from filter_by_sic import read_stage_receipt
    run = make_run(state, CASE['report'])
    (run / 'all_candidates.json').write_text(content, encoding='utf-8')
    output = run / 'deepdive_verdicts.json'
    output.write_text(CASE['prior_output'], encoding='utf-8')
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 2
    assert output.read_text(encoding='utf-8') == CASE['prior_output']
    finalization = run / 'finalization.json'
    completion = json.loads(finalization.read_text(encoding='utf-8'))
    assert completion['status'] == read_stage_receipt(finalization, 0)['status'] == 'invalid'
    assert completion['work'][0]['reason'] == 'invalid_or_unreadable_input'
    assert not (run / 'deepdive_verdicts.json.stage.json').exists()


@pytest.mark.parametrize('content', CASE['invalid_candidates'])
def test_invalid_survivor_evidence_is_not_an_empty_completed_gate(state, monkeypatch, content):
    run = make_run(state)
    (run / 'all_candidates.json').write_text(json.dumps([CASE['candidate']]), encoding='utf-8')
    survivors = run / 'candidates_gate2_survivors.json'
    survivors.write_text(content, encoding='utf-8')
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 2
    completion = json.loads((run / 'finalization.json').read_text(encoding='utf-8'))
    assert completion['status'] != 'complete'
    assert completion['deep_tickers'] == completion['missing_reports'] == [CASE['ticker']]
    assert survivors.read_text(encoding='utf-8') == content
    assert not (run / 'deepdive_verdicts.json').exists()


def test_tracker_retains_finalizer_risks_and_date_evidence(state, monkeypatch):
    import track_forward as tracker
    from finalize_run import build_verdict
    run = make_run(state, CASE['risk_report'])
    verdict = build_verdict(CASE['ticker'], run, CASE['date'])
    path = run / 'deepdive_verdicts.json'
    path.write_text(json.dumps([verdict]), encoding='utf-8')
    monkeypatch.setattr(tracker, '_fetch_close', lambda *a, **k: 10.0)
    row, = tracker._build_verdicts_from_json(path)
    assert row['killflag_count'] == 3
    assert row['unresolved_killflag_count'] == 1
    assert set(row['kill_flags']) >= {'concentration_kill', 'fundamental_decline'}
    assert row['risk_evidence']['report_count'] == 3
    assert row['verdict_date'] == CASE['date']
    assert row['report_sha256'] == verdict['report_sha256']
    assert row['verdict_date_source'] == verdict['verdict_date_source']
