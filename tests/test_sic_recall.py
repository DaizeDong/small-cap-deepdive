"""Recall union and its sidecar preserve identity and private destination evidence."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

import pytest

from test_private_runs import state
from make_fixtures import sic_recall_scenarios

FIX = sic_recall_scenarios()


@pytest.fixture
def module(state, monkeypatch):
    monkeypatch.delitem(sys.modules, 'filter_by_sic', raising=False)
    return importlib.import_module('filter_by_sic')


@pytest.mark.parametrize('kind', ['unversioned', 'public', 'unknown'])
def test_explicit_sidecar_refuses_unproved_destination_before_creation(module, state, tmp_path, kind):
    parent = tmp_path / kind
    parent.mkdir()
    if kind != 'unversioned':
        (parent / '.git').mkdir()
        state['origins'][str(parent)] = FIX['public_origin']
        state['visibility'][FIX['public_identity']] = 'PUBLIC' if kind == 'public' else None
    destination = parent / 'not-created'
    with pytest.raises(RuntimeError):
        module.write_sic_floor_sidecar(FIX['theme'], FIX['sic'], destination)
    assert not destination.exists()


def test_default_sidecar_rechecks_companion_visibility(module, state):
    identity = next(iter(state['visibility']))
    state['visibility'][identity] = 'PUBLIC'
    with pytest.raises(RuntimeError):
        module.write_sic_floor_sidecar(FIX['theme'], FIX['sic'])
    assert not Path(state['root']).exists()


@pytest.mark.parametrize('explicit', [False, True])
def test_sidecar_writes_generated_rows_in_verified_private_companion(module, state, explicit):
    directory = Path(state['companion']) / 'nested' if explicit else None
    path = module.write_sic_floor_sidecar(FIX['theme'], FIX['sic'], directory)
    assert json.loads(path.read_text(encoding='utf-8')) == FIX['sic']
    assert path.is_relative_to(Path(state['companion']))
    receipt = module.read_stage_receipt(path, len(FIX['sic']))
    assert receipt['status'] == 'partial'
    assert receipt['reasons'] == ['missing_completion_evidence']


def test_recall_union_normalizes_cik_and_retains_both_channels(module):
    fts, sic = deepcopy(FIX['fts']), deepcopy(FIX['sic'])
    result = module.union_recall(fts, sic)
    assert len(result) == 2
    assert result[0]['cik'] == '42'
    assert result[0]['recall_channel'] == 'both'
    assert result[0]['ticker'] == 'SYNTH'
    assert result[1]['cik'] == '43' and result[1]['recall_channel'] == 'sic_reverse'
    assert fts == FIX['fts'] and sic == FIX['sic']


def test_recall_union_deduplicates_repeated_hits_within_one_channel(module):
    result = module.union_recall(FIX['fts'] * 2, [])
    assert len(result) == 1 and result[0]['recall_channel'] == 'fts'


@pytest.mark.parametrize('cik', FIX['invalid_ciks'])
def test_invalid_issuer_identity_does_not_enter_union(module, cik):
    with pytest.raises(ValueError):
        module.union_recall([{'cik': cik}], [])


def test_offline_selftest_respects_private_write_boundary(module):
    module._selftest()
