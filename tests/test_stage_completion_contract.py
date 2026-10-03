"""Completion evidence survives empty output and failed retrieval work."""
import importlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

from make_fixtures import stage_completion_scenarios
from test_private_runs import state


@pytest.fixture
def sample():
    return stage_completion_scenarios()


@pytest.fixture
def modules(state, monkeypatch):
    names = ('filter_by_sic', 'discover', 'discover_events', 'cheap_pass', 'rank', '_pit_universe')
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return {name: importlib.import_module(name) for name in names}


class Response:
    def __init__(self, payload=None, text='', status=200):
        self.payload, self.text, self.status_code = payload, text, status

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError('synthetic HTTP failure')

    def json(self):
        return self.payload


def no_provider(*args, **kwargs):
    raise AssertionError('provider must not run for this input')


@pytest.mark.parametrize('field,expected', [
    ('fts_empty', 'complete'), ('fts_malformed', 'unavailable')])
def test_fts_empty_requires_a_valid_source_envelope(modules, sample, monkeypatch, field, expected):
    module = modules['discover']
    monkeypatch.setattr(module, 'http_get', lambda *a, **k: Response(sample[field]))
    monkeypatch.setattr(module.time, 'sleep', lambda *a: None)
    rows = module.fts_search('synthetic query', '10-K', sample['asof'], sample['asof'])
    assert rows == sample['empty_rows']
    assert rows.completion['status'] == expected


@pytest.mark.parametrize('interrupted', [False, True])
def test_fts_cap_and_interruption_preserve_partial_work(modules, sample, monkeypatch, interrupted):
    module = modules['discover']
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        if len(calls) > 1:
            raise RuntimeError('synthetic second page failure')
        return Response(sample['fts_capped'])

    monkeypatch.setattr(module, 'http_get', fetch)
    monkeypatch.setattr(module.time, 'sleep', lambda *a: None)
    rows = module.fts_search('synthetic query', '10-K', sample['asof'], sample['asof'],
                             max_pages=2 if interrupted else 1)
    assert rows and rows.completion['status'] == 'partial'
    reason = 'request_or_schema_failed' if interrupted else 'page_cap'
    assert any(item['reason'] == reason for item in rows.completion['work'])
    assert rows.completion['requested_work'] > rows.completion['completed_work']


@pytest.mark.parametrize('field,expected', [
    ('sic_empty_html', 'complete'), ('sic_unknown_html', 'unavailable')])
def test_sic_empty_requires_recognized_zero_result_evidence(modules, sample, field, expected):
    rows = modules['filter_by_sic'].enumerate_sic(
        '0000', fetch=lambda *a, **k: Response(text=sample[field]), sleep=0)
    assert rows == sample['empty_rows']
    assert rows.completion['status'] == expected


def test_receipt_missing_and_changed_artifact_are_not_complete(modules, sample, state):
    module = modules['filter_by_sic']
    directory = Path(state['root'])
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / 'candidates_synthetic.json'
    artifact.write_text(json.dumps(sample['empty_rows']), encoding='utf-8')
    assert module.read_stage_receipt(artifact, 0)['status'] == 'unavailable'
    completion = module.stage_completion('synthetic_discovery', 0, work=[
        module.stage_work('synthetic_source', reason='explicit_zero_results')])
    module.write_stage_receipt(artifact, completion)
    assert module.read_stage_receipt(artifact, 0)['status'] == 'complete'
    with pytest.raises(FileExistsError):
        module.prepare_stage_output(artifact)
    artifact.write_text(json.dumps(sample['empty_rows']) + '\n', encoding='utf-8')
    assert module.read_stage_receipt(artifact, 0)['status'] == 'invalid'


def test_recall_union_retains_unavailable_source(modules, sample):
    module = modules['filter_by_sic']
    complete = module.StageRows(sample['empty_rows'], stage='fts', work=[module.stage_work('fts')])
    unavailable = module.StageRows(sample['empty_rows'], stage='sic', reasons=['request_failed'])
    rows = module.union_recall(complete, unavailable)
    assert rows == sample['empty_rows']
    assert rows.completion['status'] == 'partial'
    assert [item['status'] for item in rows.completion['upstream']] == ['complete', 'unavailable']


def test_empty_frames_keep_downstream_columns_and_boolean_types(modules, sample):
    empty = pd.DataFrame(sample['empty_rows'])
    cheap = modules['cheap_pass'].score(empty)
    ranking = modules['rank'].rank_frame(empty)
    assert {'ticker', 'revenue', 'killflag_count', 'rejected', 'health_score_complete'} <= set(cheap)
    assert {'ticker', 'rating', 'confidence', 'killflags', 'sink', 'combined'} <= set(ranking)
    assert cheap['rejected'].dtype == bool
    assert ranking['sink'].dtype == bool
    assert cheap.empty and ranking.empty


def test_empty_discovery_keeps_the_normal_universe_schema(modules, sample, state, monkeypatch):
    module = modules['discover']
    directory = Path(state['root'])
    directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, 'REPORTS', directory)
    monkeypatch.setattr(module, 'http_get', lambda *a, **k: Response(sample['fts_empty']))
    monkeypatch.setattr(module, '_enrich_one', no_provider)
    monkeypatch.setattr(sys, 'argv', ['discover.py', '--theme', 'synthetic',
        '--startdt', sample['asof'], '--enddt', sample['asof']])
    assert module.main() == 0
    artifact, = directory.glob('universe_*.csv')
    frame = pd.read_csv(artifact)
    assert frame.empty
    assert {'ticker', 'cik', 'name', 'sic', 'price', 'avg_dollar_vol', 'mktcap_source',
            'recall_channel', 'band', 'smallcap_candidate'} <= set(frame)
    assert modules['filter_by_sic'].read_stage_receipt(artifact, 0)['status'] == 'complete'


def test_spinoff_truncation_cannot_be_complete(modules, sample, monkeypatch):
    module = modules['discover_events']
    monkeypatch.setattr(module, 'http_get', lambda *a, **k: Response(sample['fts_capped']))
    rows = module.discover_spinoffs(startdt=sample['asof'], enddt=sample['asof'], enrich_mktcap=False)
    assert rows and rows.completion['status'] == 'partial'
    assert any(item['reason'] == 'unfetched_pages' for item in rows.completion['work'])


def test_insider_unknown_layout_is_unavailable(modules, sample, monkeypatch):
    module = modules['discover_events']
    monkeypatch.setattr(module, 'http_get', lambda *a, **k: Response(text=sample['sic_unknown_html']))
    rows = module.discover_insider_clusters(enrich_mktcap=False)
    assert rows == sample['empty_rows']
    assert rows.completion['status'] == 'unavailable'


def test_invalid_universe_fails_before_provider_initialization(modules, sample, tmp_path, monkeypatch):
    module = modules['cheap_pass']
    artifact = tmp_path / 'invalid-universe.json'
    artifact.write_text(json.dumps(sample['invalid_universe']), encoding='utf-8')
    monkeypatch.setattr(module, 'init_edgar', no_provider)
    monkeypatch.setattr(module, 'resolve_ceiling', no_provider)
    monkeypatch.setattr(sys, 'argv', ['cheap_pass.py', '--universe', str(artifact)])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2


def test_complete_empty_candidates_finish_cheap_and_rank_without_providers(modules, sample, state, monkeypatch):
    shared, cheap, rank = (modules[name] for name in ('filter_by_sic', 'cheap_pass', 'rank'))
    directory = Path(state['root'])
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / 'candidates_synthetic.json'
    artifact.write_text(json.dumps(sample['empty_rows']), encoding='utf-8')
    shared.write_stage_receipt(artifact, shared.stage_completion('synthetic_discovery', 0,
        work=[shared.stage_work('synthetic_source', reason='explicit_zero_results')]))
    monkeypatch.setattr(cheap, 'REPORTS', directory)
    monkeypatch.setattr(cheap, 'init_edgar', no_provider)
    monkeypatch.setattr(cheap, 'health_check', no_provider)
    monkeypatch.setattr(sys, 'argv', ['cheap_pass.py', '--universe', str(artifact)])
    assert cheap.main() == 0
    cheap_file, = directory.glob('cheappass_*.csv')
    assert pd.read_csv(cheap_file).empty
    assert shared.read_stage_receipt(cheap_file, 0)['status'] == 'complete'
    monkeypatch.setattr(sys, 'argv', ['rank.py', '--input', str(directory)])
    assert rank.main() == 0
    assert shared.read_stage_receipt(directory / 'RANKING.md', 0)['status'] == 'complete'
    assert rank.compute_funnel_stats(directory)['candidates'] == 0


def test_current_symbol_fallback_is_unproved_history(modules, sample):
    module = modules['_pit_universe']
    evidence = {}
    result = module.cik_trading_symbol_asof(sample['cik'], sample['asof'],
        fetch=lambda *a, **k: Response(status=503),
        submissions_tickers=sample['current_tickers'], evidence=evidence)
    assert result == sample['current_tickers'][0].upper()
    assert evidence['source'] == 'current_submissions'
    assert evidence['pit_proven'] is False and evidence['filed'] is None
    assert any(item['reason'] == 'current_symbol_unproved_asof' for item in evidence['work'])


def test_failed_historical_shard_remains_in_evidence(modules, sample):
    module = modules['_pit_universe']
    evidence = {}

    def fetch(url, **kwargs):
        if url.endswith(sample['failed_shard_name']):
            raise RuntimeError('synthetic shard failure')
        if '/companyconcept/' in url:
            return Response(sample['symbol_fact'])
        return Response(sample['submissions'])

    result = module.cik_periodic_asof(sample['cik'], sample['asof'], fetch=fetch, evidence=evidence)
    assert result is not None
    assert evidence['identity']['pit_proven'] is True
    assert evidence['identity']['filed'] <= sample['asof']
    failures = [item for item in evidence['work'] if item['status'] != 'complete']
    assert any(item['query'] == sample['failed_shard_name'] for item in failures)
