"""Coverage status reaches the recall CLI without changing cohort math or partitions."""
import csv
import importlib
import json
from pathlib import Path
import sys

import pytest

from test_private_runs import state
from test_finalize_boundaries import invoke
from make_fixtures import ranking_recall_completion_scenarios


@pytest.fixture
def recall_cli(state, monkeypatch):
    for name in ('track_forward', '_recall', 'filter_by_sic'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('track_forward')
    recall = importlib.import_module('_recall')
    stages = importlib.import_module('filter_by_sic')
    sample = ranking_recall_completion_scenarios()['recall']
    monkeypatch.setattr(recall, 'THEME_GOLD', {sample['theme']: sample['gold']})
    run = Path(state['root']) / 'recall-completion'
    run.mkdir(parents=True)
    return module, recall, stages, run, sample


def write_inputs(stages, run, sample, complete):
    universe = run / 'universe_synthetic.csv'
    with universe.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(sample['universe_rows'][0]))
        writer.writeheader()
        writer.writerows(sample['universe_rows'])
    candidates = run / 'candidates_synthetic.json'
    candidates.write_text(json.dumps(sample['later_gate_rows']), encoding='utf-8')
    if complete:
        for path, rows in ((universe, sample['universe_rows']), (candidates, sample['later_gate_rows'])):
            completion = stages.stage_completion('synthetic_recall', len(rows),
                                                 work=[stages.stage_work('synthetic_recall')])
            stages.write_stage_receipt(path, completion)
    return universe, candidates


@pytest.mark.parametrize('complete', [False, True])
def test_cli_preserves_metrics_and_partitions_but_propagates_coverage(recall_cli, monkeypatch, capsys, complete):
    module, recall, stages, run, sample = recall_cli
    universe, candidates = write_inputs(stages, run, sample, complete)
    captured = []

    def measure(*args, **kwargs):
        result = recall.recall_at_gold(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(module, 'recall_at_gold', measure)
    paths = [str(candidates)]
    if complete:
        paths.append(str(stages.stage_receipt_path(candidates)))
    monkeypatch.setattr(sys, 'argv', ['track_forward.py', '--theme', sample['theme'],
                                    '--universe', str(universe), '--recall-gold', *paths])
    assert module.main() == (0 if complete else 2)
    observed = captured[0]
    assert observed['coverage_complete'] is complete
    assert observed['recall_at_gold'] == round(1 / 6, 4)
    assert observed['discovery_recall_at_gold'] == 0.5
    assert observed['recalled_gold'] == [sample['universe_rows'][0]['ticker']]
    assert observed['stage_breakdown']['gated_out'] == [sample['later_gate_rows'][0]['ticker']]
    assert len(observed['gold']) == 6
    partitions = [ticker for members in observed['stage_breakdown'].values() for ticker in members]
    assert len(partitions) == len(set(partitions)) == 6
    output = capsys.readouterr().out
    assert 'discovery@gold: 50.0% (3/6)' in output
    assert 'recall@gold:   16.7% (1/6)' in output
    assert ('incomplete observation' in output) is not complete
    assert ('unknown_missing_gold:' in output) is not complete


def test_supported_script_exit_reports_incomplete_observation(recall_cli, monkeypatch):
    _, _, stages, run, sample = recall_cli
    universe, candidates = write_inputs(stages, run, sample, complete=False)
    assert invoke('track_forward', ['--theme', sample['theme'], '--universe', str(universe),
                                    '--recall-gold', str(candidates)], monkeypatch) == 2


def test_stale_receipt_cannot_establish_complete_recall(recall_cli, monkeypatch, capsys):
    module, _, stages, run, sample = recall_cli
    universe, candidates = write_inputs(stages, run, sample, complete=True)
    candidates.write_bytes(candidates.read_bytes() + b'\n')
    monkeypatch.setattr(sys, 'argv', ['track_forward.py', '--theme', sample['theme'],
                                    '--universe', str(universe), '--recall-gold', str(candidates)])
    assert module.main() == 2
    assert 'incomplete observation' in capsys.readouterr().out


def test_missing_gold_stays_unmeasurable_with_successful_noop(recall_cli, monkeypatch, capsys):
    module, recall, stages, run, sample = recall_cli
    universe, candidates = write_inputs(stages, run, sample, complete=False)
    monkeypatch.setattr(recall, 'THEME_GOLD', {})
    monkeypatch.setattr(sys, 'argv', ['track_forward.py', '--theme', sample['theme'],
                                    '--universe', str(universe), '--recall-gold', str(candidates)])
    assert module.main() == 0
    assert 'not measurable' in capsys.readouterr().out
