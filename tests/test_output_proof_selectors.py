"""Native Git worktrees: destination checks are path-only and ignore Git selectors."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import _output_paths as outputs
from make_fixtures import output_path_security_case


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
    case['native_run'] = native_run
    for name, path in case["repositories"].items():
        path.mkdir()
        git(path, "init", "-q")
        git(path, "remote", "add", "origin", case["origins"][name])
        tree = git(path, 'write-tree')
        commit = git(path, '-c', 'user.name=Example User', '-c', 'user.email=user1@example.com',
                     'commit-tree', tree, '-m', 'Synthetic empty fixture')
        git(path, 'update-ref', 'HEAD', commit)

    def execute(argv, **kwargs):
        raise AssertionError("Destination checks must start no process: " + str(argv[0]))

    monkeypatch.setattr(subprocess, "run", execute)
    return case


def test_private_destination_ignores_callers_gitdir_selection(native_case, monkeypatch):
    public, private = (native_case["repositories"][key] for key in ("public", "private"))
    monkeypatch.setenv("GIT_DIR", str(public / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(private))
    target = private / native_case["output"]
    assert outputs.prove_output_path(target) == target
    assert not target.parent.exists()


def test_companion_without_origin_is_accepted(native_case):
    private = native_case["repositories"]["private"]
    native_case["git"](private, "remote", "rename", "origin", "Vault")
    target = private / native_case["output"]
    assert outputs.prepare_output(target) == target
    assert target.parent.is_dir() and not target.exists()


def test_nested_repository_is_its_own_companion_root(native_case):
    parent = native_case["repositories"]["private"]
    nested = parent / "nested"
    nested.mkdir()
    native_case["git"](nested, "init", "-q")
    assert outputs.prove_companion_root(nested) == nested.resolve()
    with pytest.raises(outputs.OutputPathError, match="worktree root"):
        outputs.prove_companion_root(parent / "plain-subdirectory")


def test_destination_outside_any_worktree_is_refused_before_creation(native_case):
    loose = native_case["root"] / "loose"
    loose.mkdir()
    target = loose / native_case["output"]
    with pytest.raises(outputs.OutputPathError, match="versioned PRIVATE companion"):
        outputs.prepare_output(target)
    assert not target.parent.exists()


def test_destination_inside_tool_source_is_refused(native_case, monkeypatch):
    private = native_case["repositories"]["private"]
    monkeypatch.setattr(outputs, "SOURCE_ROOT", private)
    target = private / native_case["output"]
    with pytest.raises(outputs.OutputPathError, match="outside the tool source"):
        outputs.prepare_output(target)
    assert not target.parent.exists()
