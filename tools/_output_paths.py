"""Canonical PRIVATE destinations backed by the pinned shared proof API."""
from functools import lru_cache
import importlib.util
import os
from pathlib import Path
import stat
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class OutputPathError(RuntimeError):
    """A destination could not be proved safe for private runtime data."""


@lru_cache(maxsize=1)
def _guard_module():
    """Load only the pinned kit; missing or incompatible dependencies fail closed."""
    path = SOURCE_ROOT / 'guards/tools/data_boundary.py'
    if not path.is_file():
        raise OutputPathError('Initialize pinned guards with git submodule update --init --recursive -- guards')
    spec = importlib.util.spec_from_file_location('_smallcap_output_boundary', path)
    if spec is None or spec.loader is None:
        raise OutputPathError('Cannot load the pinned PRIVATE companion proof')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        error_type = getattr(module, 'GitError', None)
        if (not callable(getattr(module, 'prove_private_companion', None))
                or not isinstance(error_type, type) or not issubclass(error_type, Exception)):
            raise OutputPathError('Pinned guards lacks the supported PRIVATE companion proof API')
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def _nearest_repository(existing):
    for candidate in (existing, *existing.parents):
        marker = candidate / '.git'
        if os.path.lexists(marker):
            if not marker.is_file() and not marker.is_dir():
                raise OutputPathError('invalid Git worktree marker')
            return candidate
        if (candidate / 'HEAD').is_file() and (candidate / 'objects').is_dir():
            raise OutputPathError('output requires a worktree, not a bare repository')
    raise OutputPathError('output requires a versioned PRIVATE companion')


def _prove_output_path(requested):
    path = Path(requested).expanduser()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    if any(part.lower() == '.git' or ':' in part or part.endswith((' ', '.')) for part in parts):
        raise OutputPathError('ambiguous or reserved output path')
    try:
        path = path.resolve()
        if path.is_relative_to(SOURCE_ROOT) or SOURCE_ROOT.is_relative_to(path):
            raise OutputPathError('runtime output must be outside the tool source in a separate PRIVATE companion')
        existing = path
        while True:
            try:
                info = existing.stat()
                break
            except FileNotFoundError:
                if existing == existing.parent:
                    raise OutputPathError('cannot find an existing output ancestor')
                existing = existing.parent
        if stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                raise OutputPathError('runtime output cannot use a hardlinked file')
            existing = existing.parent
        elif not stat.S_ISDIR(info.st_mode):
            raise OutputPathError('runtime output requires an ordinary file or directory')
        nearest = _nearest_repository(existing)
        boundary = _guard_module()
        try:
            proof = boundary.prove_private_companion(str(existing))
        except boundary.GitError as exc:
            raise OutputPathError('Cannot prove PRIVATE output destination: ' + str(exc)) from exc
        repository = Path(proof.root).resolve()
        if repository != nearest:
            raise OutputPathError('nearest Git marker does not identify its enclosing worktree')
        if not path.is_relative_to(repository) or SOURCE_ROOT.is_relative_to(repository):
            raise OutputPathError('runtime output requires a separate PRIVATE worktree')
        return path, proof
    except (OSError, ValueError) as exc:
        raise OutputPathError('cannot prove PRIVATE output destination: ' + str(exc)) from exc


def prove_output_path(requested):
    """Return the canonical target after proving its actual enclosing repository PRIVATE."""
    return _prove_output_path(requested)[0]


def prepare_output(requested):
    """Recheck path and publication identity after creating the destination's parents."""
    path, before = _prove_output_path(requested)
    path.parent.mkdir(parents=True, exist_ok=True)
    final, after = _prove_output_path(path)
    if final != path or (before.root, before.repositories, before.signature) != (
            after.root, after.repositories, after.signature):
        raise OutputPathError('PRIVATE output destination changed while preparing its parent')
    return final
