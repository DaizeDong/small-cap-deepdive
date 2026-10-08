"""Configuration, reports and tracking select the same declared PRIVATE root."""
import importlib
import json
import os
from pathlib import Path

import pytest

from test_output_proof_selectors import native_case
from test_initialization import load_init, invoke


@pytest.fixture
def selected_roots(native_case, monkeypatch):
    case = native_case
    first = case['repositories']['private']
    second = case['root'] / 'second-private'
    second.mkdir()
    case['git'](second, 'init', '-q')
    case['git'](second, 'remote', 'add', 'origin', case['origins']['private'])
    for name in tuple(os.environ):
        if name.startswith(('SMALL_CAP_DEEPDIVE_', 'SMALLCAP_')):
            monkeypatch.delenv(name)
    monkeypatch.setenv('SMALL_CAP_DEEPDIVE_CONFIG', str(first))
    monkeypatch.setenv('SMALL_CAP_DEEPDIVE_CONFIG_DIR', str(second))
    return case, first, second


def test_alias_order_is_shared_by_initializer_reports_and_tracking(selected_roots):
    _, first, _ = selected_roots
    common = importlib.import_module('_common')
    tracking = importlib.import_module('track_forward')
    assert common._companion_root() == first
    assert load_init().resolve_out(None) == first
    assert tracking._metrics_dir() == first / 'data' / 'metrics'


def test_data_override_selects_same_root_before_both_config_aliases(selected_roots, monkeypatch):
    _, _, second = selected_roots
    (second / 'data').mkdir()
    monkeypatch.setenv('SMALL_CAP_DEEPDIVE_DATA_DIR', str(second / 'data'))
    assert importlib.import_module('_common')._companion_root() == second
    assert load_init().resolve_out(None) == second
    assert importlib.import_module('track_forward')._metrics_dir() == second / 'data' / 'metrics'


def test_nested_profile_is_refused_before_initializer_creates_it(selected_roots, monkeypatch):
    _, first, _ = selected_roots
    nested = first / 'conservative'
    assert invoke(load_init(), monkeypatch, '--out', str(nested)) == 2
    assert not nested.exists()


@pytest.mark.parametrize('relative', ['undeclared/result.json', 'reports/smallcap/ignored.json'])
def test_report_writer_refuses_undeclared_or_ignored_artifacts(selected_roots, relative):
    _, first, _ = selected_roots
    (first / '.gitignore').write_text('reports/smallcap/ignored.json\n', encoding='utf-8')
    from _output_paths import prepare_output, OutputPathError
    with pytest.raises(OutputPathError):
        prepare_output(first / relative)
    assert not (first / relative).exists()


def test_report_output_cannot_replace_configuration(selected_roots):
    _, first, _ = selected_roots
    from _output_paths import prepare_output, OutputPathError
    target = first / 'config.json'
    before = target.read_bytes() if target.exists() else None
    with pytest.raises(OutputPathError, match='different producer'):
        prepare_output(target)
    assert (target.read_bytes() if target.exists() else None) == before


def test_report_alias_is_rejected_before_path_resolution(selected_roots):
    case, first, _ = selected_roots
    real = first / 'reports/smallcap/real'
    real.mkdir(parents=True)
    alias = real.with_name('alias')
    if os.name == 'nt':
        case['native_run'](['cmd', '/d', '/c', 'mklink', '/J', str(alias), str(real)],
                           capture_output=True, check=True)
    else:
        alias.symlink_to(real, target_is_directory=True)
    try:
        from _output_paths import prepare_output, OutputPathError
        with pytest.raises(OutputPathError, match='filesystem aliases'):
            prepare_output(alias / 'synthetic.json')
        assert not (real / 'synthetic.json').exists()
    finally:
        if os.name == 'nt':
            alias.rmdir()
        else:
            alias.unlink()


@pytest.mark.parametrize('identity', ['', 'Research user1@example.com'])
def test_missing_or_example_sec_identity_is_not_ready(selected_roots, monkeypatch, capsys, identity):
    _, first, _ = selected_roots
    common = importlib.import_module('_common')
    config = json.loads((Path(common._REF) / 'config.example.json').read_text(encoding='utf-8'))
    config['sec_user_agent'] = identity
    monkeypatch.setattr(common, 'load_config', lambda: config)
    monkeypatch.setattr(common, 'output_root', lambda: first / 'reports/smallcap')
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location('smallcap_doctor_under_test', Path(common._REPO) / 'scripts/verify_config.py')
    doctor = module_from_spec(spec)
    spec.loader.exec_module(doctor)
    monkeypatch.setattr(doctor.importlib.metadata, 'version', lambda name: '999.0.0')
    monkeypatch.setattr(doctor.importlib.util, 'find_spec', lambda name: object())
    assert doctor.main(['--json']) == 1
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'not_ready'
    assert next(row for row in report['checks'] if row['name'] == 'SEC identity configured')['status'] == 'fail'
