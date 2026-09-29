"""Generated aliases exercise real identity and PRIVATE proof without SSH execution."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from make_fixtures import ssh_alias_scenarios

SAMPLE = ssh_alias_scenarios()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    def denied(*args, **kwargs):
        raise AssertionError('No real process or SSH command is permitted')
    monkeypatch.setattr(subprocess, 'run', denied)
    module = importlib.import_module('_output_paths')
    config = tmp_path/'.ssh/config'
    config.parent.mkdir()
    return module, config


@pytest.mark.parametrize('case,origin,config_text,accepted', SAMPLE['cases'])
def test_configured_alias_identity(isolated, case, origin, config_text, accepted):
    module, config = isolated
    if config_text is not None:
        config.write_text(config_text, encoding='utf-8')
    if accepted:
        assert module._github_identity(origin) == SAMPLE['identity']
    else:
        with pytest.raises(module.OutputPathError):
            module._github_identity(origin)


@pytest.mark.parametrize('visibility', ['PRIVATE', 'PUBLIC', None])
def test_alias_still_requires_actual_private_visibility(isolated, tmp_path, monkeypatch, visibility):
    module, config = isolated
    config.write_text(SAMPLE['ordinary'], encoding='utf-8')
    companion = tmp_path/'companion'
    companion.mkdir()
    (companion/'.git').mkdir()
    destination = companion/'reports/output.json'
    queried = []
    def metadata(argv, **kwargs):
        queried.append(argv)
        if argv[0] == 'git' and '--show-toplevel' in argv:
            output = str(companion)
        elif argv[0] == 'git' and 'remote' in argv:
            output = SAMPLE['origin'] if 'get-url' in argv else 'origin'
        elif argv[:3] == ['gh', 'repo', 'view']:
            assert argv[3].removeprefix('https://github.com/') == SAMPLE['identity']
            output = json.dumps({'visibility': visibility})
        else:
            raise AssertionError('Unexpected process, including SSH: '+repr(argv))
        return subprocess.CompletedProcess(argv, 0, output, '')
    monkeypatch.setattr(subprocess, 'run', metadata)
    if visibility == 'PRIVATE':
        assert module.prove_output_path(destination) == destination.resolve()
    else:
        with pytest.raises(module.OutputPathError):
            module.prove_output_path(destination)
    assert any(argv[0] == 'gh' for argv in queried)
    assert not destination.parent.exists()


def test_https_host_never_reads_ssh_config(isolated, monkeypatch):
    module, config = isolated
    actual = Path.read_text
    def guarded(path, *args, **kwargs):
        if path == config:
            raise AssertionError('HTTPS host resolution must not inspect SSH configuration')
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    assert module._github_identity('https://github.com/'+SAMPLE['identity']+'.git') == SAMPLE['identity']
    with pytest.raises(module.OutputPathError):
        module._github_identity('https://'+SAMPLE['alias']+'/'+SAMPLE['identity']+'.git')
