"""Discovery provenance must not overwrite terminal loss or its denominator."""
import csv
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import _recall as recall
from make_fixtures import recall_stage_scenarios
from test_private_runs import state


@pytest.fixture
def sample():
    return recall_stage_scenarios()


def result(sample, final=None, **kwargs):
    return recall.recall_at_gold(
        sample['theme'], sample['final'] if final is None else final,
        mapping={sample['theme']: sample['gold']}, **kwargs)


def test_discovery_channels_do_not_replace_terminal_loss(sample):
    observed = result(sample, fts_tickers=sample['fts'], sic_tickers=sample['sic'],
                      mktcap_dropped=sample['dropped'], gated_out=sample['gated'])
    stages = observed['stage_breakdown']
    assert stages['recalled_final'] == ['SYNTHA', 'SYNTHB']
    assert stages['dropped_mktcap'] == ['SYNTHC']
    assert stages['gated_out'] == ['SYNTHD']
    assert stages['discovered_not_final'] == ['SYNTHE']
    assert stages['fts_missed'] == ['SYNTHF']
    assert observed['discovery_channels']['sic_only'] == ['SYNTHB', 'SYNTHC', 'SYNTHE']
    assert observed['discovery_channels']['both'] == ['SYNTHD']
    assert observed['recalled_gold'] == stages['recalled_final']
    assert observed['recall_at_gold'] == round(2 / 6, 4)
    assert observed['discovery_recall_at_gold'] == round(5 / 6, 4)
    assert observed['discovered_gold'] == sorted(set(sample['fts']) | set(sample['sic']))
    for partitions in (stages, observed['discovery_channels']):
        members = [ticker for tickers in partitions.values() for ticker in tickers]
        assert len(members) == len(set(members)) == len(observed['gold']) == 6
        assert set(members) == set(observed['gold'])


@pytest.mark.parametrize('input_kind', ['candidate', 'universe'])
def test_reader_to_report_keeps_sic_discovery_and_downstream_loss(sample, tmp_path, input_kind):
    if input_kind == 'candidate':
        path = tmp_path / 'synthetic-candidates.json'
        path.write_text(json.dumps(sample['candidate_rows']), encoding='utf-8')
        reader = recall._recall_set_from_candidate_files
    else:
        path = tmp_path / 'synthetic-universe.csv'
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(sample['universe_rows'][0]))
            writer.writeheader()
            writer.writerows(sample['universe_rows'])
        reader = recall._recall_set_from_universe_files
    final, _, channels = reader([path])
    observed = result(sample, final=final, fts_tickers=channels['fts'], sic_tickers=channels['sic'],
                      mktcap_dropped=channels['mktcap_dropped'], gated_out=channels['gated_out'])
    assert 'SYNTHC' in observed['missing_gold']
    assert 'SYNTHC' in observed['stage_breakdown']['dropped_mktcap']
    assert 'SYNTHC' in observed['discovery_channels']['sic_only']
    assert observed['recalled_gold'] == observed['stage_breakdown']['recalled_final']


def test_without_channel_evidence_final_and_loss_still_reconcile(sample):
    observed = result(sample, mktcap_dropped=sample['dropped'])
    assert observed['discovery_channels']['unattributed'] == ['SYNTHA', 'SYNTHB', 'SYNTHC']
    assert observed['discovery_recall_at_gold'] == 0.5
    assert observed['recall_at_gold'] == round(2 / 6, 4)


def test_final_evidence_wins_over_conflicting_prior_loss_tags(sample):
    observed = result(sample, mktcap_dropped=sample['final'], gated_out=sample['final'])
    assert observed['stage_breakdown']['recalled_final'] == observed['recalled_gold']
    assert observed['stage_breakdown']['dropped_mktcap'] == []
    assert observed['stage_breakdown']['gated_out'] == []


def test_unmeasurable_cohort_does_not_emit_zero_recall(sample):
    assert recall.recall_at_gold(sample['theme'], sample['final'], mapping={}) is None


@pytest.mark.parametrize('conflicting_final', [False, True])
def test_cli_combines_universe_discovery_with_later_gate_outcome(sample, tmp_path, state, monkeypatch, capsys, conflicting_final):
    monkeypatch.delitem(sys.modules, 'track_forward', raising=False)
    module = importlib.import_module('track_forward')
    monkeypatch.setattr(recall, 'THEME_GOLD', {sample['theme']: sample['gold']})
    universe = tmp_path / 'synthetic-universe.csv'
    with universe.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(sample['universe_rows'][0]))
        writer.writeheader()
        writer.writerows(sample['universe_rows'])
    candidates = tmp_path / 'synthetic-gate.json'
    rows = sample['conflicting_gate_rows'] if conflicting_final else sample['later_gate_rows']
    candidates.write_text(json.dumps(rows), encoding='utf-8')
    captured = []
    def measure(*args, **kwargs):
        observed = recall.recall_at_gold(*args, **kwargs)
        captured.append(observed)
        return observed
    monkeypatch.setattr(module, 'recall_at_gold', measure)
    module.cmd_recall_gold(SimpleNamespace(theme=sample['theme'], universe=[str(universe)], recall_gold=[str(candidates)]))
    observed = captured[0]
    assert observed['recalled_gold'] == (['SYNTHA', 'SYNTHB'] if conflicting_final else ['SYNTHA'])
    assert observed['stage_breakdown']['gated_out'] == ([] if conflicting_final else ['SYNTHB'])
    assert observed['discovery_channels']['sic_only'] == ['SYNTHB', 'SYNTHC']
    assert observed['discovery_recall_at_gold'] == 0.5
    final_count = 2 if conflicting_final else 1
    assert observed['recall_at_gold'] == round(final_count / 6, 4)
    output = capsys.readouterr().out
    assert 'discovery@gold: 50.0% (3/6)' in output
    expected_final = 'recall@gold:   33.3% (2/6)' if conflicting_final else 'recall@gold:   16.7% (1/6)'
    assert expected_final in output


def test_existing_tracker_selftest_uses_consistent_recall_contract(state, monkeypatch):
    monkeypatch.delitem(sys.modules, 'track_forward', raising=False)
    importlib.import_module('track_forward')._selftest()
