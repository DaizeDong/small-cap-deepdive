"""Generated aliases exercise shared PRIVATE proof without SSH execution."""
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from make_fixtures import ssh_alias_scenarios
from test_private_runs import install_metadata

SAMPLE = ssh_alias_scenarios()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    companion = tmp_path / 'companion'
    companion.mkdir()
    (companion / '.git').mkdir()
    state = {'companion': str(companion),
             'origins': {str(companion): SAMPLE['origin']},
             'visibility': {SAMPLE['identity']: 'PRIVATE'}}
    install_metadata(state, monkeypatch.setattr)
    metadata = subprocess.run
    queried = []

    def execute(argv, **kwargs):
        assert argv[0] == 'git', 'Only local Git metadata is permitted'
        queried.append(argv)
        return metadata(argv, **kwargs)

    monkeypatch.setattr(subprocess, 'run', execute)
    config = tmp_path / '.ssh/config'
    config.parent.mkdir()
    return importlib.import_module('_output_paths'), state, config, queried


@pytest.mark.parametrize('case,origin,config_text,accepted', SAMPLE['cases'])
def test_configured_alias_destination(isolated, case, origin, config_text, accepted):
    module, state, config, queried = isolated
    state['origins'][state['companion']] = origin
    if config_text is not None:
        config.write_text(config_text, encoding='utf-8')
    destination = Path(state['companion']) / 'reports/output.json'
    if accepted:
        assert module.prove_output_path(destination) == destination.resolve()
    else:
        with pytest.raises(module.OutputPathError):
            module.prove_output_path(destination)
    assert queried and not destination.parent.exists()


@pytest.mark.parametrize('visibility', ['PRIVATE', 'PUBLIC', None])
def test_alias_still_requires_actual_private_visibility(isolated, visibility):
    module, state, config, queried = isolated
    state['visibility'][SAMPLE['identity']] = visibility
    config.write_text(SAMPLE['ordinary'], encoding='utf-8')
    destination = Path(state['companion']) / 'reports/output.json'
    if visibility == 'PRIVATE':
        assert module.prove_output_path(destination) == destination.resolve()
    else:
        with pytest.raises(module.OutputPathError):
            module.prove_output_path(destination)
    assert queried and not destination.parent.exists()


def test_https_host_never_reads_ssh_config(isolated, monkeypatch):
    module, state, config, _ = isolated
    config.write_text(SAMPLE['ordinary'], encoding='utf-8')
    actual = Path.read_bytes

    def guarded(path, *args, **kwargs):
        if path == config:
            raise AssertionError('HTTPS proof must not inspect SSH configuration')
        return actual(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_bytes', guarded)
    destination = Path(state['companion']) / 'reports/output.json'
    state['origins'][state['companion']] = 'https://github.com/' + SAMPLE['identity'] + '.git'
    assert module.prove_output_path(destination) == destination.resolve()
    state['origins'][state['companion']] = 'https://' + SAMPLE['alias'] + '/' + SAMPLE['identity'] + '.git'
    with pytest.raises(module.OutputPathError):
        module.prove_output_path(destination)
