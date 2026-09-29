"""Generated controls for omitted and explicitly unbatched run-state paths."""
from pathlib import Path

import pytest

from test_private_runs import SAMPLE, common, state

CASE = SAMPLE['run_state']


@pytest.mark.parametrize('inherited', CASE['inherited'])
def test_explicit_empty_is_unbatched_despite_inherited_run(state, monkeypatch, inherited):
    if inherited is not None:
        monkeypatch.setenv('SMALLCAP_RUN', inherited)
    paths = [common().run_state_path(run=CASE['empty'], pid=pid) for pid in CASE['pids']]
    assert paths == [Path(state['root'])/f'_run_state_{pid}.txt' for pid in CASE['pids']]
    assert len(set(paths)) == len(CASE['pids'])
    assert not Path(state['root']).exists()


def test_omitted_run_uses_active_environment(state, monkeypatch):
    monkeypatch.setenv('SMALLCAP_RUN', CASE['active'])
    assert common().run_state_path(pid=CASE['pids'][0]) == (
        Path(state['root'])/CASE['active']/'_run_state.txt')
    assert not Path(state['root']).exists()


def test_omitted_run_without_environment_is_process_scoped(state):
    assert common().run_state_path(pid=CASE['pids'][0]) == (
        Path(state['root'])/f"_run_state_{CASE['pids'][0]}.txt")
    assert not Path(state['root']).exists()


@pytest.mark.parametrize('inherited', CASE['inherited'][1:])
def test_valid_explicit_run_overrides_inherited_run(state, monkeypatch, inherited):
    monkeypatch.setenv('SMALLCAP_RUN', inherited)
    assert common().run_state_path(run=CASE['explicit']) == (
        Path(state['root'])/CASE['explicit']/'_run_state.txt')
    assert not Path(state['root']).exists()


def test_unsafe_inherited_run_still_fails_when_argument_is_omitted(state, monkeypatch):
    monkeypatch.setenv('SMALLCAP_RUN', CASE['unsafe'])
    with pytest.raises(ValueError):
        common().run_state_path()
    assert not Path(state['root']).exists()
