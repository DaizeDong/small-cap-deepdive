"""PRIVATE proof follows every configured fetch and push destination."""
import importlib
from pathlib import Path
import subprocess

import pytest

from test_private_runs import SAMPLE, state
from make_fixtures import initialization_scenarios

FIX = initialization_scenarios()


@pytest.mark.parametrize('case,visibility,accepted', FIX['remote_cases'])
def test_all_fetch_and_push_destinations_must_be_private(state, case, visibility, accepted):
    module = importlib.import_module('_output_paths')
    destination = Path(state['companion']) / 'new-profile/config.json'
    origin = {'fetch': [SAMPLE['origin']], 'push': [SAMPLE['origin']]}
    remotes = {'origin': origin}
    if case.startswith('push-'):
        origin['push'] = [FIX['public_origin']]
    elif case.startswith('extra-'):
        remotes['archive'] = {'fetch': [FIX['public_origin']], 'push': [FIX['public_origin']]}
    else:
        origin['fetch'].append(FIX['public_origin'])
    state['remotes'] = {state['companion']: remotes}
    state['visibility'][FIX['public_identity']] = visibility
    if accepted:
        assert module.prove_output_path(destination) == destination
    else:
        with pytest.raises(module.OutputPathError):
            module.prove_output_path(destination)
    assert not destination.parent.exists()


def test_visibility_proof_uses_receipts_without_ambient_host_queries(state, monkeypatch):
    monkeypatch.setenv('GH_HOST', FIX['ambient_host'])
    metadata = subprocess.run
    checks = []
    def execute(argv, **kwargs):
        if argv[:3] == ['gh', 'repo', 'view']:
            checks.append(argv)
        return metadata(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', execute)
    module = importlib.import_module('_output_paths')
    module.prove_output_path(Path(state['companion']))
    assert not checks


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
