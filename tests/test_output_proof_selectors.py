"""Native Git discovery cannot borrow a different repository's PRIVATE identity."""
import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import _output_paths as outputs
from make_fixtures import output_path_security_case, output_visibility_receipt


@pytest.fixture
def native_case(tmp_path, monkeypatch):
    case = output_path_security_case(tmp_path)
    case["home"].mkdir()
    for key in tuple(os.environ):
        if key.upper().startswith("GIT_") or key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}:
            monkeypatch.delenv(key)
    for key in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(key, str(case["home"]))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    native_run = subprocess.run

    def git(path, *args):
        result = native_run(["git", "-C", str(path), *args], capture_output=True,
                            text=True, encoding="utf-8", check=True)
        return result.stdout.strip()

    case["git"] = git
    for name, path in case["repositories"].items():
        path.mkdir()
        git(path, "init", "-q")
        git(path, "remote", "add", "origin", case["origins"][name])
    receipt = case["home"] / ".pii-guard/visibility.json"
    receipt.parent.mkdir()
    receipt.write_text(json.dumps(output_visibility_receipt(case["visibility"])), encoding="utf-8")

    def execute(argv, **kwargs):
        if argv[0] == "git":
            return native_run(argv, **kwargs)
        if argv[:3] == ["gh", "repo", "view"]:
            identity = argv[3].removeprefix("https://github.com/")
            return subprocess.CompletedProcess(argv, 0, json.dumps({
                "visibility": case["visibility"].get(identity),
            }), "")
        raise AssertionError("Unexpected process in offline destination proof: " + argv[0])

    monkeypatch.setattr(subprocess, "run", execute)
    return case


def test_public_destination_is_refused_without_selectors(native_case):
    target = native_case["repositories"]["public"] / native_case["output"]
    with pytest.raises(outputs.OutputPathError):
        outputs.prove_output_path(target)
    assert not target.parent.exists()


def test_public_destination_cannot_borrow_private_gitdir(native_case, monkeypatch):
    public, private = (native_case["repositories"][key] for key in ("public", "private"))
    monkeypatch.setenv("GIT_DIR", str(private / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(public))
    target = public / native_case["output"]
    with pytest.raises(outputs.OutputPathError):
        outputs.prepare_output(target)
    assert not target.parent.exists()


def test_private_destination_ignores_callers_public_gitdir(native_case, monkeypatch):
    public, private = (native_case["repositories"][key] for key in ("public", "private"))
    monkeypatch.setenv("GIT_DIR", str(public / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(private))
    target = private / native_case["output"]
    assert outputs.prove_output_path(target) == target
    assert not target.parent.exists()


def test_nested_public_repository_is_checked_instead_of_private_parent(native_case, monkeypatch):
    parent = native_case["repositories"]["private"]
    nested = parent / "nested"
    nested.mkdir()
    native_case["git"](nested, "init", "-q")
    native_case["git"](nested, "remote", "add", "origin", native_case["origins"]["public"])
    monkeypatch.setenv("GIT_DIR", str(parent / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(nested))
    target = nested / native_case["output"]
    with pytest.raises(outputs.OutputPathError):
        outputs.prove_output_path(target)
    assert not target.parent.exists()


def test_private_companion_without_origin_uses_shared_remote_policy(native_case):
    private = native_case["repositories"]["private"]
    native_case["git"](private, "remote", "rename", "origin", "Vault")
    target = private / native_case["output"]
    assert outputs.prepare_output(target) == target
    assert target.parent.is_dir() and not target.exists()


def test_unknown_visibility_is_refused_before_creation(native_case):
    target = native_case["repositories"]["unknown"] / native_case["output"]
    with pytest.raises(outputs.OutputPathError):
        outputs.prepare_output(target)
    assert not target.parent.exists()


def test_effective_rewrite_cannot_hide_a_public_physical_remote(native_case, monkeypatch):
    public = native_case["repositories"]["public"]
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url." + native_case["origins"]["private"] + ".insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", native_case["origins"]["public"])
    target = public / native_case["output"]
    with pytest.raises(outputs.OutputPathError):
        outputs.prepare_output(target)
    assert not target.parent.exists()


@pytest.mark.parametrize('dependency', ['missing', 'incompatible'])
def test_unavailable_shared_api_fails_before_creation(native_case, monkeypatch, dependency):
    tool = native_case['home'] / 'synthetic-tool'
    if dependency == 'incompatible':
        module = tool / 'guards/tools/data_boundary.py'
        module.parent.mkdir(parents=True)
        module.write_text(native_case['incompatible_api'], encoding='utf-8')
    target = native_case['repositories']['private'] / native_case['output']
    monkeypatch.setattr(outputs, 'SOURCE_ROOT', tool)
    outputs._guard_module.cache_clear()
    try:
        with pytest.raises(outputs.OutputPathError, match='guards'):
            outputs.prepare_output(target)
    finally:
        outputs._guard_module.cache_clear()
    assert not target.parent.exists()


@pytest.mark.parametrize('field', ['root', 'repositories', 'signature'])
def test_changed_proof_is_refused_before_product_write(native_case, monkeypatch, field):
    boundary = outputs._guard_module()
    prove = boundary.prove_private_companion
    calls = []
    changes = {'root': str(native_case['repositories']['public']),
               'repositories': (native_case['identities']['unknown'],),
               'signature': native_case['changed_signature']}

    def changing_proof(destination):
        proof = prove(destination)
        calls.append(destination)
        return replace(proof, **{field: changes[field]}) if len(calls) == 2 else proof

    monkeypatch.setattr(boundary, 'prove_private_companion', changing_proof)
    target = native_case['repositories']['private'] / native_case['output']
    with pytest.raises(outputs.OutputPathError):
        outputs.prepare_output(target)
    assert len(calls) == 2 and not target.exists()
