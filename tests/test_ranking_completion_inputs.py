"""Real ranking calls require bound exclusions and preserve every prior output pair."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

from test_private_runs import state
from make_fixtures import downstream_completion_scenarios, ranking_recall_completion_scenarios


@pytest.fixture
def ranking(state, monkeypatch):
    for name in ('rank', 'run_theme', 'filter_by_sic', 'finalize_run'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('rank')
    stages = importlib.import_module('filter_by_sic')
    run = Path(state['root']) / 'ranking-completion'
    run.mkdir(parents=True)
    return module, stages, run, ranking_recall_completion_scenarios(), downstream_completion_scenarios()


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def complete_pair(stages, path, rows):
    completion = stages.stage_completion('synthetic_input', len(rows),
                                         work=[stages.stage_work('synthetic_input')])
    stages.write_stage_receipt(path, completion)
    return stages.read_stage_receipt(path, len(rows))


def candidate_pair(stages, run, sample, gate, rows=None):
    path = run / sample['candidate_artifact']
    rows = deepcopy(gate['candidates'] if rows is None else rows)
    write_json(path, rows)
    return path, rows, complete_pair(stages, path, rows)


def gate2_pair(stages, run, sample, gate, mode='survive'):
    candidate, rows, upstream = candidate_pair(stages, run, sample, gate)
    judgments = deepcopy(gate['judgments'])
    if mode == 'misrecall':
        for row in judgments:
            row['theme_fit'] = 'misrecall'
    elif mode == 'error':
        judgments[0] = deepcopy(gate['errors'][0])
    elif mode == 'identity_mismatch':
        judgments[0]['ticker'] = rows[1]['ticker']
    path = run / 'gate2_results.json'
    write_json(path, judgments)
    completion = importlib.import_module('run_theme').gate2_completion(judgments, upstream)
    completion['input'] = {key: upstream[key] for key in
                           ('artifact', 'artifact_bytes', 'artifact_sha256', 'run_dir')}
    stages.write_stage_receipt(path, completion)
    if mode == 'stale_candidate':
        candidate.write_bytes(candidate.read_bytes() + b'\n')
    return candidate, path


def report_file(run, sample, ticker=None):
    path = run / ('report_' + (ticker or sample['ticker']) + '.md')
    path.write_text(sample['report_text'], encoding='utf-8')
    return path


def hard_data_file(run, sample, offset=0):
    asof = (date.fromisoformat(sample['asof']) + timedelta(days=offset)).isoformat()
    path = run / ('deepdive_' + sample['ticker'] + '_' + asof + '.json')
    write_json(path, sample['hard_data'])
    return path


def call_rank(module, run, monkeypatch, output=None):
    argv = ['rank.py', '--input', str(run)]
    if output is not None:
        argv += ['--output', output]
    monkeypatch.setattr(sys, 'argv', argv)
    return module.main()


def test_bound_misrecall_completes_empty_ranking_even_with_old_report(ranking, monkeypatch):
    module, stages, run, sample, gate = ranking
    gate2_pair(stages, run, sample, gate, 'misrecall')
    report_file(run, sample)
    assert call_rank(module, run, monkeypatch) == 0
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
    assert receipt['status'] == 'complete'
    assert receipt['empty'] is True
    assert '| ' + sample['ticker'] + ' |' not in (run / 'RANKING.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('mode', ['error', 'identity_mismatch', 'stale_candidate'])
def test_failed_or_unbound_gate2_never_proves_exclusion(ranking, monkeypatch, mode):
    module, stages, run, sample, gate = ranking
    gate2_pair(stages, run, sample, gate, mode)
    if mode == 'error':
        assert call_rank(module, run, monkeypatch) == 2
        receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
        assert receipt['status'] != 'complete'
        assert 'unranked_deep_candidates' in receipt['reasons']
    else:
        with pytest.raises(SystemExit) as error:
            call_rank(module, run, monkeypatch)
        assert error.value.code == 2
        assert not (run / 'RANKING.md').exists()
        assert not (run / 'RANKING.md.stage.json').exists()


def test_unrelated_report_cannot_satisfy_deep_candidate_obligation(ranking, monkeypatch):
    module, stages, run, sample, gate = ranking
    candidate_pair(stages, run, sample, gate)
    report_file(run, sample, gate['candidates'][1]['ticker'])
    assert call_rank(module, run, monkeypatch) == 2
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
    assert 'unranked_deep_candidates' in receipt['reasons']
    assert module.ranking_report_files(run) == []
    assert '| ' + gate['candidates'][1]['ticker'] + ' |' not in (run / 'RANKING.md').read_text(encoding='utf-8')


def test_complete_watch_only_scope_produces_empty_ranking(ranking, monkeypatch):
    module, stages, run, sample, gate = ranking
    watch = gate['candidates'][1]
    candidate_pair(stages, run, sample, gate, rows=[watch])
    report_file(run, sample, watch['ticker'])
    assert call_rank(module, run, monkeypatch) == 0
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
    assert receipt['status'] == 'complete' and receipt['empty'] is True
    assert module.ranking_report_files(run) == []


@pytest.mark.parametrize('complete', [False, True])
def test_candidate_completion_controls_stale_watch_and_unbound_report_scope(ranking, monkeypatch, complete):
    module, stages, run, sample, gate = ranking
    if complete:
        candidate_pair(stages, run, sample, gate)
    else:
        write_json(run / sample['candidate_artifact'], gate['candidates'])
    deep_report = report_file(run, sample)
    watch_report = report_file(run, sample, gate['candidates'][1]['ticker'])
    unbound_ticker = sample['recall']['gold'][4].strip().upper()
    unbound_report = report_file(run, sample, unbound_ticker)
    expected_reports = [deep_report] if complete else sorted([deep_report, watch_report, unbound_report])
    assert module.ranking_report_files(run) == expected_reports
    assert call_rank(module, run, monkeypatch) == (0 if complete else 2)
    receipt = stages.read_stage_receipt(run / 'RANKING.md', len(expected_reports))
    assert receipt['status'] == ('complete' if complete else 'partial')
    output = (run / 'RANKING.md').read_text(encoding='utf-8')
    assert '| ' + sample['ticker'] + ' |' in output
    for ticker in (gate['candidates'][1]['ticker'], unbound_ticker):
        assert ('| ' + ticker + ' |' in output) is not complete


def test_unresolved_band_cannot_make_empty_ranking_complete(ranking, monkeypatch):
    module, stages, run, sample, gate = ranking
    unresolved = {**gate['candidates'][0], 'band': gate['unknown_band']}
    candidate_pair(stages, run, sample, gate, rows=[unresolved])
    assert call_rank(module, run, monkeypatch) == 2
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
    assert receipt['status'] == 'partial'
    assert 'unresolved_candidate_band' in receipt['reasons']


@pytest.mark.parametrize('identity', ['missing', 'null', 'number', 'empty', 'path'])
def test_malformed_watch_identity_cannot_prove_complete_empty_scope(ranking, monkeypatch, identity):
    module, stages, run, sample, gate = ranking
    watch = deepcopy(gate['candidates'][1])
    if identity == 'missing':
        watch.pop('ticker')
    elif identity == 'null':
        watch['ticker'] = None
    elif identity == 'number':
        watch['ticker'] = len(gate['candidates'])
    elif identity == 'empty':
        watch['ticker'] = ''
    else:
        watch['ticker'] = '../' + watch['ticker']
    candidate_pair(stages, run, sample, gate, rows=[watch])
    assert call_rank(module, run, monkeypatch) == 2
    assert stages.read_stage_receipt(run / 'RANKING.md', 0)['status'] == 'invalid'


@pytest.mark.parametrize('malformed_band', [[], {}])
def test_malformed_band_is_incomplete_instead_of_raising_typeerror(ranking, monkeypatch, malformed_band):
    module, stages, run, sample, gate = ranking
    row = {**gate['candidates'][1], 'band': malformed_band}
    candidate_pair(stages, run, sample, gate, rows=[row])
    assert call_rank(module, run, monkeypatch) == 2
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
    assert receipt['status'] == 'partial'
    assert 'unresolved_candidate_band' in receipt['reasons']


@pytest.mark.parametrize('fold_case', [False, True])
def test_duplicate_watch_identities_cannot_prove_complete_empty_scope(ranking, monkeypatch, fold_case):
    module, stages, run, sample, gate = ranking
    first = deepcopy(gate['candidates'][1])
    second = deepcopy(first)
    if fold_case:
        second['ticker'] = second['ticker'].lower()
    candidate_pair(stages, run, sample, gate, rows=[first, second])
    assert call_rank(module, run, monkeypatch) == 2
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 0)
    assert receipt['status'] == 'partial'
    assert 'ambiguous_candidate_identity' in receipt['reasons']


def test_receipt_binds_exact_selected_reports_hard_data_candidates_and_gate2(ranking, monkeypatch):
    module, stages, run, sample, gate = ranking
    candidate, gate2 = gate2_pair(stages, run, sample, gate)
    report = report_file(run, sample)
    older = hard_data_file(run, sample)
    latest = hard_data_file(run, sample, offset=1)
    complete_pair(stages, latest, [])
    assert call_rank(module, run, monkeypatch) == 0
    receipt = stages.read_stage_receipt(run / 'RANKING.md', 1)
    expected_paths = [report, latest, candidate, stages.stage_receipt_path(candidate),
                      gate2, stages.stage_receipt_path(gate2)]
    expected = [{'artifact': path.name, 'artifact_bytes': len(path.read_bytes()),
                 'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(expected_paths)]
    assert receipt['input_artifacts'] == expected == module.ranking_input_artifacts(run)
    assert older.name not in {row['artifact'] for row in expected}
    assert stages.stage_receipt_path(latest).name not in {row['artifact'] for row in expected}


@pytest.mark.parametrize('mutation', ['new_report', 'changed_report', 'new_hard_data', 'changed_hard_data'])
def test_input_change_during_ranking_prevents_output(ranking, monkeypatch, mutation):
    module, stages, run, sample, gate = ranking
    candidate_pair(stages, run, sample, gate)
    report = report_file(run, sample)
    hard_data = hard_data_file(run, sample)
    original = module.rank_frame

    def mutate_after_parsing(frame):
        result = original(frame)
        if mutation == 'new_report':
            report_file(run, sample, gate['candidates'][1]['ticker'])
        elif mutation == 'changed_report':
            report.write_bytes(report.read_bytes() + b'\n')
        elif mutation == 'new_hard_data':
            hard_data_file(run, sample, offset=1)
        else:
            hard_data.write_bytes(hard_data.read_bytes() + b'\n')
        return result

    monkeypatch.setattr(module, 'rank_frame', mutate_after_parsing)
    with pytest.raises(SystemExit) as error:
        call_rank(module, run, monkeypatch)
    assert error.value.code == 2
    assert not (run / 'RANKING.md').exists()
    assert not (run / 'RANKING.md.stage.json').exists()


@pytest.mark.parametrize('with_receipt', [False, True])
def test_existing_artifact_and_receipt_are_immutable_and_new_basename_works(ranking, monkeypatch, with_receipt):
    module, stages, run, sample, gate = ranking
    candidate_pair(stages, run, sample, gate)
    report_file(run, sample)
    target = run / 'RANKING.md'
    target.write_text(sample['prior_ranking'], encoding='utf-8')
    if with_receipt:
        complete_pair(stages, target, [])
    prior = {path.name: path.read_bytes() for path in run.glob('RANKING.md*')}
    with pytest.raises(FileExistsError):
        call_rank(module, run, monkeypatch)
    assert {path.name: path.read_bytes() for path in run.glob('RANKING.md*')} == prior
    assert call_rank(module, run, monkeypatch, sample['ranking_output']) == 0
    assert stages.read_stage_receipt(run / sample['ranking_output'], 1)['status'] == 'complete'
    assert {path.name: path.read_bytes() for path in run.glob('RANKING.md*')} == prior


def test_output_requires_same_directory_basename(ranking, monkeypatch):
    module, _, run, sample, _ = ranking
    with pytest.raises(SystemExit) as error:
        call_rank(module, run, monkeypatch, '../' + sample['ranking_output'])
    assert error.value.code == 2
    assert not (run.parent / sample['ranking_output']).exists()
