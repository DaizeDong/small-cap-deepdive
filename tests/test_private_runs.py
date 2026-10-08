"""Exercise shipped interfaces with generated inputs and offline metadata seams."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
SAMPLE = json.loads((ROOT/'tests/fixtures/private_runs.json').read_text(encoding='utf-8'))
REAL_RUN = subprocess.run


def install_metadata(state, patch):
    from make_fixtures import output_visibility_receipt
    outputs = importlib.import_module('_output_paths')
    boundary = outputs._guard_module()
    fixture_root = Path(state['companion']).parent
    receipt = fixture_root / ('synthetic-visibility-' + str(os.getpid()) + '.json')
    ssh_paths = [str(fixture_root / '.ssh/config'), str(fixture_root / 'ssh_config')]
    patch(boundary, '_ssh_config_sources', lambda: {'paths': ssh_paths, 'chains': [ssh_paths]})

    def prove(destination, visibility_map=None):
        receipt.write_text(json.dumps(output_visibility_receipt(state['visibility'])), encoding='utf-8')
        return boundary.prove_private_companion(destination, visibility_map=receipt)

    facade = types.SimpleNamespace(prove_private_companion=prove, GitError=boundary.GitError,
                                   read_private_companion_git=boundary.read_private_companion_git)
    patch(outputs, '_guard_module', lambda: facade)
    patch(outputs._storage_module(), 'load_boundary', lambda: facade)

    def execute(argv, **kwargs):
        argv = [str(value) for value in argv]
        if argv[0] == 'git':
            if '--short' in argv:
                answer = '0123456789ab'
            elif 'status' in argv:
                answer = ''
            else:
                requested = Path(argv[argv.index('-C')+1] if '-C' in argv else kwargs['cwd']).resolve()
                repository = next((node for node in (requested, *requested.parents)
                                   if (node/'.git').exists()), None)
                if repository is None:
                    return subprocess.CompletedProcess(argv, 1, '', 'not a repository')
                remote_map = state.get('remotes', {}).get(str(repository))
                if remote_map is None:
                    origin = state['origins'].get(str(repository), '')
                    remote_map = {'origin': {'fetch': [origin], 'push': [origin]}} if origin else {}
                if '--show-toplevel' in argv:
                    answer = str(repository)
                elif 'rev-parse' in argv and '--verify' in argv:
                    answer = '0123456789abcdef0123456789abcdef01234567'
                elif 'check-ignore' in argv:
                    return subprocess.CompletedProcess(argv, 1, '', '')
                elif '--absolute-git-dir' in argv:
                    answer = str(repository / '.git')
                elif 'config' in argv and '--list' in argv:
                    answer = ''.join('remote.' + name + '.' + role + '\n' + url + '\0'
                                     for name, directions in remote_map.items()
                                     for role, urls in (('url', directions.get('fetch', [])),
                                                        ('pushurl', directions.get('push', [])))
                                     for url in urls)
                elif 'remote' in argv:
                    if 'get-url' not in argv:
                        answer = '\n'.join(remote_map)
                    else:
                        directions = remote_map.get(argv[-1], {})
                        urls = directions.get('push' if '--push' in argv else 'fetch', [])
                        answer = '\n'.join(urls if '--all' in argv else urls[:1])
                else:
                    raise AssertionError('unexpected Git query: '+repr(argv))
        elif argv[0] == 'gh':
            identity = argv[3].removeprefix('https://github.com/') if argv[1:3] == ['repo', 'view'] else ''
            visibility = state['visibility'].get(identity)
            if visibility is None:
                return subprocess.CompletedProcess(argv, 1, '', 'unknown synthetic visibility')
            answer = json.dumps({'visibility': visibility})
        else:
            raise AssertionError('external process refused: '+argv[0])
        return subprocess.CompletedProcess(argv, 0, answer, '')
    patch(subprocess, 'run', execute)


def finance_stubs(patch):
    def concentration_outside_scope(*args, **kwargs):
        pytest.fail("concentration extraction is outside the synthetic state fixture")

    exports = {
        '_pit_universe': {'pit_universe': lambda *a, **k: []},
        'backtest_returns': {'forward_return_with_reason': lambda *a, **k: {},
                             'benchmark_return': lambda *a, **k: 0,
                             'mktcap_asof': lambda *a, **k: {}, 'DEFAULT_HORIZON_MONTHS': 12},
        'deepdive_data': {'pull': lambda *a, **k: {},
                          '_extract_concentration': concentration_outside_scope,
                          '_concentration_flag': concentration_outside_scope},
        'valuation': {'compute_valuation': lambda *a, **k: {}},
        '_valuation_model': {'_val_cfg': lambda *a, **k: {}},
    }
    for name, values in exports.items():
        module = types.ModuleType(name)
        module.__dict__.update(values)
        patch(sys.modules, name, module)


@pytest.fixture
def state(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(('SMALLCAP_', 'SMALL_CAP_DEEPDIVE_')):
            monkeypatch.delenv(key)
    companion = tmp_path/'synthetic companion'
    companion.mkdir()
    (companion/'.git').mkdir()
    config = {**SAMPLE['config'], 'output_dir': str(companion/'reports/smallcap')}
    (companion/'config.json').write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setenv('SMALL_CAP_DEEPDIVE_CONFIG_DIR', str(companion))
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    value = {'companion': str(companion), 'root': str(companion/'reports/smallcap'),
             'origins': {str(companion): SAMPLE['origin']},
             'visibility': {'example/synthetic-smallcap-config': 'PRIVATE'}}
    install_metadata(value, monkeypatch.setattr)
    finance_stubs(monkeypatch.setitem)
    for name in ('_common', 'new_run', 'make_report', 'backtest'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return value


def common():
    return importlib.import_module('_common')


def allocate(monkeypatch, *arguments):
    monkeypatch.setattr(sys, 'argv', ['new_run.py', '--label', SAMPLE['label'], *arguments])
    return importlib.import_module('new_run').main()


def tree(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in Path(path).rglob('*') if p.is_file()}


def test_imports_do_not_read_config_or_create_output(state, monkeypatch):
    actual = Path.read_text
    def guarded(path, *args, **kwargs):
        if path.name == 'config.json':
            raise AssertionError('config read during import')
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    for name in ('_common', 'new_run', 'make_report', 'backtest'):
        importlib.import_module(name)
    assert not Path(state['root']).exists()


def test_output_root_is_absolute_lazy_and_companion_relative(state):
    path = Path(state['companion'])/'config.json'
    path.write_text(json.dumps(SAMPLE['config']), encoding='utf-8')
    assert common().output_root() == Path(state['root'])
    assert not Path(state['root']).exists()


@pytest.mark.parametrize('visibility', ['PUBLIC', None])
def test_unproved_visibility_refuses_before_creation(state, visibility):
    state['visibility']['example/synthetic-smallcap-config'] = visibility
    with pytest.raises(RuntimeError):
        common().output_root()
    assert not Path(state['root']).exists()


def test_linked_private_worktree_is_accepted(state):
    marker = Path(state['companion'])/'.git'
    marker.rmdir()
    marker.write_text(SAMPLE['linked_marker'], encoding='utf-8')
    assert common().output_root() == Path(state['root'])


def test_missing_configuration_fails_without_output(state):
    (Path(state['companion'])/'config.json').unlink()
    with pytest.raises(RuntimeError):
        common().output_root()
    assert not Path(state['root']).exists()


def test_tool_output_is_refused(state, monkeypatch):
    monkeypatch.setenv('SMALLCAP_OUTPUT_DIR', str(ROOT/'reports/synthetic-refused'))
    with pytest.raises(RuntimeError):
        common().output_root()
    assert not (ROOT/'reports/synthetic-refused').exists()


def test_new_runs_are_unique_and_ignore_active_run(state, monkeypatch, capsys):
    monkeypatch.setenv('SMALLCAP_RUN', 'unrelated-run')
    allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    first = capsys.readouterr().out.strip()
    allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    second = capsys.readouterr().out.strip()
    assert first != second
    for name in (first, second):
        directory = Path(state['root'])/name
        manifest = json.loads((directory/'_run.json').read_text(encoding='utf-8'))
        assert manifest['input_hash'] == SAMPLE['hash']
        assert manifest['reports_root'] == state['root']
        assert manifest['run_name'] == name
        assert (directory/'_run_state.txt').read_text(encoding='utf-8').strip() == name
    assert not (Path(state['root'])/'unrelated-run').exists()


@pytest.mark.parametrize('name', SAMPLE['invalid_names'])
def test_invalid_labels_and_run_names_refused(state, monkeypatch, name):
    monkeypatch.setattr(sys, 'argv', ['new_run.py', '--label', name, '--input-hash', SAMPLE['hash']])
    with pytest.raises((RuntimeError, ValueError, SystemExit)):
        importlib.import_module('new_run').main()
    # Empty allocation labels fail, but an empty state selector means unbatched.
    if name != SAMPLE['run_state']['empty']:
        with pytest.raises((RuntimeError, ValueError)):
            common().run_state_path(run=name)
    assert not Path(state['root']).exists()


def test_state_paths_share_root_and_unbatched_processes_are_distinct(state):
    module = common()
    assert module.run_state_path(run='synthetic-run') == Path(state['root'])/'synthetic-run/_run_state.txt'
    first = module.run_state_path(pid=101)
    second = module.run_state_path(pid=202)
    assert first != second
    assert first.is_relative_to(Path(state['root'])) and second.is_relative_to(Path(state['root']))


@pytest.mark.parametrize('mutation', ['hash', 'root', 'identity', 'missing', 'malformed'])
def test_bad_resume_preserves_all_prior_bytes(state, monkeypatch, capsys, mutation):
    allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    name = capsys.readouterr().out.strip()
    manifest_path = Path(state['root'])/name/'_run.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if mutation in ('root', 'identity'):
        manifest['reports_root' if mutation == 'root' else 'run_name'] = 'synthetic-mismatch'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    elif mutation == 'missing':
        manifest_path.unlink()
    elif mutation == 'malformed':
        manifest_path.write_text('{', encoding='utf-8')
    before = tree(state['root'])
    with pytest.raises((RuntimeError, ValueError, SystemExit)):
        allocate(monkeypatch, '--resume', name, '--input-hash',
                 SAMPLE['other_hash'] if mutation == 'hash' else SAMPLE['hash'])
    assert tree(state['root']) == before


def test_resume_preserves_bytes_and_returns_same_name(state, monkeypatch, capsys):
    allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    name = capsys.readouterr().out.strip()
    before = tree(state['root'])
    allocate(monkeypatch, '--resume', name, '--input-hash', SAMPLE['hash'])
    assert capsys.readouterr().out.strip() == name
    assert tree(state['root']) == before


def test_report_default_uses_shared_active_root(state, monkeypatch, tmp_path):
    source = tmp_path/'input.json'
    source.write_text(json.dumps(SAMPLE['report']), encoding='utf-8')
    monkeypatch.setenv('SMALLCAP_RUN', 'synthetic-active')
    monkeypatch.setattr(sys, 'argv', ['make_report.py', '--json', str(source)])
    importlib.import_module('make_report').main()
    assert (Path(state['root'])/'synthetic-active/report_SYNTH.md').is_file()
    assert not (tmp_path/'report_SYNTH.md').exists()


@pytest.mark.parametrize('visibility', ['PRIVATE', 'PUBLIC', None])
def test_explicit_report_proves_actual_other_companion(state, monkeypatch, tmp_path, visibility):
    other = tmp_path/'other companion'
    other.mkdir()
    (other/'.git').mkdir()
    state['origins'][str(other)] = SAMPLE['other_origin']
    state['visibility']['example/synthetic-other-config'] = visibility
    source = tmp_path/'input.json'
    source.write_text(json.dumps(SAMPLE['report']), encoding='utf-8')
    destination = other/'reports/smallcap/nested/report.md'
    monkeypatch.setattr(sys, 'argv', ['make_report.py', '--json', str(source), '--out', str(destination)])
    if visibility == 'PRIVATE':
        importlib.import_module('make_report').main()
        assert destination.is_file()
    else:
        with pytest.raises((RuntimeError, SystemExit)):
            importlib.import_module('make_report').main()
        assert not destination.exists()


def test_backtest_writer_uses_same_unbatched_root(state):
    module = importlib.import_module('backtest')
    result = module.run_cell(SAMPLE['label'], SAMPLE['asof'], universe_fn=lambda *a, **k: [],
        pull_fn=lambda *a, **k: {}, valuation_fn=lambda *a, **k: {},
        mktcap_fn=lambda *a, **k: {}, forward_fn=lambda *a, **k: {},
        benchmark_fn=lambda *a, **k: {'status': 'ok', 'total_return': 0}, write=True)
    path = Path(result['output_path'])
    assert path.is_relative_to(Path(state['root'])/'backtest')
    assert path.is_file()


@pytest.mark.parametrize('visibility', ['PRIVATE', 'PUBLIC'])
def test_doctor_json_uses_same_root_without_output(state, monkeypatch, capsys, visibility):
    state['visibility']['example/synthetic-smallcap-config'] = visibility
    config_path = Path(state['companion']) / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['sec_user_agent'] = 'Synthetic Analyst user1@example-employer.com'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name: object())
    monkeypatch.setattr(importlib.metadata, 'version', lambda name: SAMPLE['dependencies'][name])
    monkeypatch.setattr(sys, 'argv', ['verify_config.py', '--json'])
    spec = importlib.util.spec_from_file_location('synthetic_doctor', ROOT/'scripts/verify_config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    status = module.main()
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == ('ready' if visibility == 'PRIVATE' else 'not_ready')
    assert (status == 0) == (visibility == 'PRIVATE')
    if visibility == 'PRIVATE':
        assert report['reports_root'] == state['root']
    assert report['checks']
    assert not Path(state['root']).exists()


def test_allocations_across_independent_processes_are_unique(state, monkeypatch, tmp_path):
    control = tmp_path/'control.json'
    control.write_text(json.dumps(state), encoding='utf-8')
    command = [sys.executable, '-B', str(Path(__file__)), str(control)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: REAL_RUN(command, capture_output=True, text=True), range(6)))
    assert all(result.returncode == 0 for result in results), [result.stderr for result in results]
    names = [result.stdout.strip() for result in results]
    assert len(set(names)) == 6
    assert all((Path(state['root'])/name/'_run.json').is_file() for name in names)


def test_no_hash_allocation_is_compatible_but_resume_requires_explicit_hash(state, monkeypatch, capsys):
    allocate(monkeypatch)
    name = capsys.readouterr().out.strip()
    manifest = json.loads((Path(state['root'])/name/'_run.json').read_text(encoding='utf-8'))
    assert len(manifest['input_hash']) == 64
    before = tree(state['root'])
    with pytest.raises(ValueError, match='input-hash'):
        allocate(monkeypatch, '--resume', name)
    assert tree(state['root']) == before


def test_fixed_clock_does_not_reuse_a_run(state, monkeypatch, capsys):
    monkeypatch.setattr(common(), 'today', lambda: SAMPLE['asof'])
    allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    first = capsys.readouterr().out.strip()
    allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    second = capsys.readouterr().out.strip()
    assert first.startswith(SAMPLE['asof']) and second.startswith(SAMPLE['asof'])
    assert first != second


def test_output_permission_error_is_not_a_success(state, monkeypatch):
    actual = Path.mkdir
    def refuse(path, *args, **kwargs):
        if path.is_relative_to(Path(state['root'])):
            raise PermissionError('synthetic readonly output')
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', refuse)
    with pytest.raises(PermissionError, match='readonly'):
        allocate(monkeypatch, '--input-hash', SAMPLE['hash'])
    assert not Path(state['root']).exists()


def test_unversioned_destination_is_refused(state):
    (Path(state['companion'])/'.git').rmdir()
    with pytest.raises(RuntimeError, match='versioned|worktree'):
        common().output_root()


def test_missing_pinned_resolver_is_actionable(state, monkeypatch):
    actual = Path.is_file
    def exists(path):
        return False if path == ROOT/'guards/tools/datadir.py' else actual(path)
    monkeypatch.setattr(Path, 'is_file', exists)
    with pytest.raises(RuntimeError, match='submodule'):
        common().output_root()


def junction(link, destination):
    if os.name == 'nt':
        command = "New-Item -ItemType Junction -Path '%s' -Target '%s' | Out-Null" % (
            str(link).replace("'", "''"), str(destination).replace("'", "''"))
        result = REAL_RUN(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                          capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(destination, target_is_directory=True)


def test_linked_output_is_checked_at_its_actual_destination(state, tmp_path):
    outside = tmp_path/'unversioned target'
    outside.mkdir()
    junction(Path(state['companion'])/'reports', outside)
    with pytest.raises(RuntimeError):
        common().output_root()
    assert list(outside.iterdir()) == []


def test_installed_alias_from_unrelated_cwd_uses_source_root(state, tmp_path):
    alias = tmp_path/'synthetic skill alias'
    junction(alias, ROOT)
    assert (alias/'SKILL.md').is_file()
    control = tmp_path/'control.json'
    control.write_text(json.dumps(state), encoding='utf-8')
    unrelated = tmp_path/'unrelated cwd'
    unrelated.mkdir()
    result = REAL_RUN([sys.executable, '-B', str(alias/'tests/test_private_runs.py'), str(control)],
                      cwd=unrelated, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (Path(state['root'])/result.stdout.strip()/'_run.json').is_file()
    assert list(unrelated.iterdir()) == []


if __name__ == '__main__':
    child_state = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    install_metadata(child_state, setattr)
    sys.argv = ['new_run.py', '--label', SAMPLE['unicode_label'], '--input-hash', SAMPLE['hash']]
    runpy.run_path(str(ROOT/'tools/new_run.py'), run_name='__main__')
