"""Actual caller boundaries preserve synthetic files and surface ranking failures."""
import importlib
import json
import os
from pathlib import Path
import runpy
import stat
import subprocess
import sys

import pytest

from test_private_runs import ROOT, SAMPLE, REAL_RUN, install_metadata, junction, state

FIX = json.loads((ROOT/'tests/fixtures/finalizer.json').read_text(encoding='utf-8'))


def inventory(root):
    rows = {}
    def visit(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            status = path.lstat()
            if stat.S_ISLNK(status.st_mode) or (os.name == 'nt' and status.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                rows[relative] = ('link', str(path.resolve()))
            elif path.is_dir():
                rows[relative] = ('directory',)
                visit(path)
            else:
                rows[relative] = ('file', path.read_bytes())
    visit(root)
    return rows


def report(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/('report_'+FIX['ticker']+'.md')).write_text(FIX['report'], encoding='utf-8')


def invoke(module, arguments, monkeypatch):
    monkeypatch.setattr(sys, 'argv', [module+'.py', *arguments])
    try:
        runpy.run_path(str(ROOT/'tools'/(module+'.py')), run_name='__main__')
    except SystemExit as error:
        return error.code or 0
    return 0


@pytest.mark.parametrize('module', ['finalize_run', 'rank'])
@pytest.mark.parametrize('destination', ['public', 'unknown', 'broken'])
def test_explicit_destination_is_proved_before_any_repairs_or_writes(state, monkeypatch, tmp_path, module, destination):
    outside = tmp_path/'other companion'
    run = outside/'reports/smallcap'/FIX['run']
    nested = run/'reports/smallcap'/FIX['run']
    report(run)
    nested.mkdir(parents=True)
    (nested/'valuation_SYNTB.json').write_text(FIX['duplicate'], encoding='utf-8')
    (outside/'.git').mkdir()
    state['origins'][str(outside)] = FIX['other_origin']
    state['visibility']['example/synthetic-other-config'] = 'PUBLIC' if destination == 'public' else None
    if destination == 'broken':
        metadata = subprocess.run
        def reject_broken(argv, **kwargs):
            if argv[:3] == ['git', '-C', str(outside)] and '--show-toplevel' in argv:
                return subprocess.CompletedProcess(argv, 128, '', 'synthetic unusable worktree')
            return metadata(argv, **kwargs)
        monkeypatch.setattr(subprocess, 'run', reject_broken)
    before = inventory(outside)
    arguments = ['--input', str(run), *(['--no-rank'] if module == 'finalize_run' else [])]
    with pytest.raises(RuntimeError, match='PRIVATE|PUBLIC|worktree|verification'):
        invoke(module, arguments, monkeypatch)
    assert inventory(outside) == before


@pytest.mark.parametrize('module', ['finalize_run', 'rank'])
def test_configured_private_default_produces_usable_output(state, monkeypatch, module):
    run = Path(state['root'])/FIX['run']
    report(run)
    monkeypatch.setenv('SMALLCAP_RUN', FIX['run'])
    assert invoke(module, ['--no-rank'] if module == 'finalize_run' else [], monkeypatch) == 0
    if module == 'finalize_run':
        assert json.loads((run/'deepdive_verdicts.json').read_text(encoding='utf-8'))[0]['ticker'] == FIX['ticker']
    else:
        assert FIX['ticker'] in (run/'RANKING.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('module', ['finalize_run', 'rank'])
@pytest.mark.parametrize('visibility', ['PUBLIC', None])
def test_configured_unproved_default_preserves_existing_tree(state, monkeypatch, module, visibility):
    run = Path(state['root'])/FIX['run']
    report(run/'reports/smallcap'/FIX['run'])
    monkeypatch.setenv('SMALLCAP_RUN', FIX['run'])
    state['visibility']['example/synthetic-smallcap-config'] = visibility
    before = inventory(Path(state['companion']))
    with pytest.raises(RuntimeError, match='PRIVATE|PUBLIC|visibility'):
        invoke(module, ['--no-rank'] if module == 'finalize_run' else [], monkeypatch)
    assert inventory(Path(state['companion'])) == before


@pytest.mark.parametrize('linked', [False, True])
def test_repair_without_python312_junction_api(state, monkeypatch, tmp_path, linked):
    run = Path(state['root'])/FIX['run']
    report(run)
    nested = run/'reports/smallcap'/FIX['run']
    if linked:
        target = tmp_path/'linked target'
        report(target)
        nested.parent.mkdir(parents=True)
        junction(nested, target)
    else:
        report(nested)
        target = nested
    for base in type(run).__mro__:
        if 'is_junction' in base.__dict__:
            monkeypatch.delattr(base, 'is_junction')
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 0
    # A duplicate stays at its original location in either an ordinary tree or a link target.
    assert (target/('report_'+FIX['ticker']+'.md')).read_text(encoding='utf-8') == FIX['report']
    assert (run/'deepdive_verdicts.json').is_file()


def test_ordinary_nested_repair_moves_files_and_retains_duplicates(state, monkeypatch):
    run = Path(state['root'])/FIX['run']
    nested = run/'reports/smallcap'/FIX['run']
    report(nested)
    (run/'valuation_SYNTB.json').write_text(FIX['canonical'], encoding='utf-8')
    (nested/'valuation_SYNTB.json').write_text(FIX['duplicate'], encoding='utf-8')
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 0
    assert (run/('report_'+FIX['ticker']+'.md')).read_text(encoding='utf-8') == FIX['report']
    assert not (nested/('report_'+FIX['ticker']+'.md')).exists()
    assert (run/'valuation_SYNTB.json').read_text(encoding='utf-8') == FIX['canonical']
    assert (nested/'valuation_SYNTB.json').read_text(encoding='utf-8') == FIX['duplicate']


def test_ordinary_nested_repair_prunes_only_empty_skeleton(state, monkeypatch):
    run = Path(state['root'])/FIX['run']
    nested = run/'reports/smallcap'/FIX['run']
    report(nested)
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 0
    assert not (run/'reports').exists()
    assert (run/('report_'+FIX['ticker']+'.md')).is_file()


@pytest.mark.parametrize('boundary', ['nested_repo', 'nested_link', 'prefix_link'])
def test_repair_does_not_cross_repositories_or_directory_links(state, monkeypatch, tmp_path, boundary):
    run = Path(state['root'])/FIX['run']
    report(run)
    outside = tmp_path/'outside subtree'
    outside.mkdir()
    (outside/'valuation_SYNTB.json').write_text(FIX['duplicate'], encoding='utf-8')
    nested = run/'reports/smallcap'/FIX['run']
    if boundary == 'nested_repo':
        nested.mkdir(parents=True)
        (nested/'.git').mkdir()
        (nested/'valuation_SYNTB.json').write_text(FIX['duplicate'], encoding='utf-8')
        protected = nested
    elif boundary == 'nested_link':
        nested.parent.mkdir(parents=True)
        junction(nested, outside)
        protected = outside
    else:
        (outside/'smallcap'/FIX['run']).mkdir(parents=True)
        (outside/'smallcap'/FIX['run']/'valuation_SYNTB.json').write_text(FIX['duplicate'], encoding='utf-8')
        junction(run/'reports', outside)
        protected = outside
    before = inventory(protected)
    assert invoke('finalize_run', ['--input', str(run), '--no-rank'], monkeypatch) == 0
    assert inventory(protected) == before
    assert not (run/'valuation_SYNTB.json').exists()
    assert (run/'deepdive_verdicts.json').is_file()


@pytest.mark.parametrize('module', ['finalize_run', 'rank'])
def test_explicit_directory_link_uses_the_destination_repository(state, monkeypatch, tmp_path, module):
    outside = tmp_path/'public companion'
    report(outside)
    (outside/'.git').mkdir()
    state['origins'][str(outside)] = FIX['other_origin']
    state['visibility']['example/synthetic-other-config'] = 'PUBLIC'
    alias = Path(state['companion'])/'linked-output'
    junction(alias, outside)
    before = inventory(outside)
    with pytest.raises(RuntimeError, match='PRIVATE|PUBLIC'):
        invoke(module, ['--input', str(alias), *(['--no-rank'] if module == 'finalize_run' else [])], monkeypatch)
    assert inventory(outside) == before


@pytest.mark.parametrize('rank_code,no_rank', [(0, False), (7, False), (7, True)])
def test_finalizer_process_exit_retains_verdict_when_rank_child_fails(state, tmp_path, rank_code, no_rank):
    run = Path(state['root'])/FIX['run']
    report(run)
    control = tmp_path/'child-control.json'
    control.write_text(json.dumps({'state':state,'run':str(run),'rank_code':rank_code,'no_rank':no_rank}), encoding='utf-8')
    result = REAL_RUN([sys.executable, '-X', 'utf8', '-B', str(Path(__file__)), str(control)],
                      capture_output=True, text=True, encoding='utf-8')
    assert (result.returncode == 0) is (no_rank or rank_code == 0), result.stderr
    verdicts = json.loads((run/'deepdive_verdicts.json').read_text(encoding='utf-8'))
    assert verdicts[0]['ticker'] == FIX['ticker']
    if not no_rank and rank_code:
        assert FIX['rank_error'] in result.stderr


if __name__ == '__main__':
    control = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    install_metadata(control['state'], setattr)
    metadata = subprocess.run
    def child_call(argv, **kwargs):
        if any(str(arg).endswith('rank.py') for arg in argv):
            return subprocess.CompletedProcess(argv, control['rank_code'], '', FIX['rank_error'])
        return metadata(argv, **kwargs)
    subprocess.run = child_call
    sys.argv = ['finalize_run.py', '--input', control['run'], *(['--no-rank'] if control['no_rank'] else [])]
    runpy.run_path(str(ROOT/'tools/finalize_run.py'), run_name='__main__')
