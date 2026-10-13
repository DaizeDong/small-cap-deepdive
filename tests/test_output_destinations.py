"""Companion destination checks are path-only and start no process."""
import importlib
from pathlib import Path
import subprocess

import pytest

from test_private_runs import state
from make_fixtures import initialization_scenarios

FIX = initialization_scenarios()


def test_destination_checks_start_no_process(state, monkeypatch):
    module = importlib.import_module('_output_paths')
    def refuse(*args, **kwargs):
        raise AssertionError('destination check started a process')
    monkeypatch.setattr(subprocess, 'run', refuse)
    monkeypatch.setattr(subprocess, 'Popen', refuse)
    destination = Path(state['companion']) / 'new-profile/config.json'
    assert module.prove_output_path(destination) == destination
    assert not destination.parent.exists()


def test_generic_output_refuses_existing_hardlinked_file(state, monkeypatch):
    module = importlib.import_module('_output_paths')
    target = Path(state['companion']) / 'RANKING.md'
    target.write_text(FIX['existing_config'], encoding='utf-8')
    real_stat = Path.stat
    from types import SimpleNamespace
    def hardlink_metadata(path, *args, **kwargs):
        info = real_stat(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode, st_nlink=2)
        return info
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'stat', hardlink_metadata)
        with pytest.raises(module.OutputPathError):
            module.prove_output_path(target)
    assert target.read_text(encoding='utf-8') == FIX['existing_config']
