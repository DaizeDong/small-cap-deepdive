"""Setup uses a verified PRIVATE destination before requesting personal configuration."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from test_private_runs import ROOT, state
from make_fixtures import initialization_scenarios

FIX = initialization_scenarios()


def load_init():
    spec = importlib.util.spec_from_file_location('synthetic_init', ROOT / 'scripts/init_config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(module, monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['init_config.py', *args])
    return module.main()


@pytest.mark.parametrize('label,visibility,accepted', FIX['destinations'])
def test_init_proves_destination_before_identity_instructions(state, monkeypatch, capsys, label, visibility, accepted):
    companion = Path(state['companion'])
    (companion / 'config.json').unlink()
    state['visibility']['example/synthetic-smallcap-config'] = visibility
    if label == 'unversioned':
        (companion / '.git').rmdir()
    destination = companion
    result = invoke(load_init(), monkeypatch, '--out', str(destination))
    output = capsys.readouterr().out
    assert (result == 0) is accepted
    assert (destination / 'config.json').exists() is accepted
    if accepted:
        assert json.loads((destination / 'config.json').read_text(encoding='utf-8'))['schema_version'] == 1
    else:
        assert 'sec_user_agent' not in output


def test_init_keeps_existing_config_and_force_is_deterministic(state, monkeypatch):
    target = Path(state['companion']) / 'config.json'
    target.write_text(FIX['existing_config'], encoding='utf-8')
    module = load_init()
    assert invoke(module, monkeypatch, '--out', state['companion']) == 0
    assert target.read_text(encoding='utf-8') == FIX['existing_config']
    assert invoke(module, monkeypatch, '--out', state['companion'], '--force') == 0
    first = target.read_bytes()
    assert invoke(module, monkeypatch, '--out', state['companion'], '--force') == 0
    assert target.read_bytes() == first


def test_failed_atomic_replace_preserves_prior_config_and_cleans_temporary(state, monkeypatch):
    import os
    target = Path(state['companion']) / 'config.json'
    target.write_text(FIX['existing_config'], encoding='utf-8')
    def refuse_replace(*args, **kwargs):
        raise PermissionError('synthetic replacement denied')
    monkeypatch.setattr(os, 'replace', refuse_replace)
    assert invoke(load_init(), monkeypatch, '--out', state['companion'], '--force') == 2
    assert target.read_text(encoding='utf-8') == FIX['existing_config']
    assert list(target.parent.glob('.config-*.tmp')) == []


def test_default_init_uses_runtime_companion_discovery(state, monkeypatch):
    import _common
    companion = Path(state['companion'])
    (companion / 'config.json').unlink()
    monkeypatch.delenv('SMALL_CAP_DEEPDIVE_CONFIG_DIR')
    monkeypatch.setattr(_common, '_companion_root', lambda: companion)
    assert invoke(load_init(), monkeypatch) == 0
    assert (companion / 'config.json').is_file()


@pytest.mark.parametrize('alias_kind', ['hardlink', 'reparse'])
def test_force_refuses_existing_config_alias_before_write(state, monkeypatch, alias_kind):
    target = Path(state['companion']) / 'config.json'
    target.write_text(FIX['existing_config'], encoding='utf-8')
    real_lstat = Path.lstat
    from types import SimpleNamespace
    def alias_metadata(path, *args, **kwargs):
        info = real_lstat(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode,
                                   st_nlink=2 if alias_kind == 'hardlink' else 1,
                                   st_file_attributes=1024 if alias_kind == 'reparse' else 0)
        return info
    module = load_init()
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', alias_metadata)
        assert invoke(module, patch, '--out', state['companion'], '--force') == 2
    assert target.read_text(encoding='utf-8') == FIX['existing_config']
