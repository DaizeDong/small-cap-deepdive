"""Canonical companion destinations, checked by path only.

Every check is a filesystem check and starts no process: no aliases, hard links or
Git metadata; outside this tool source; inside a separate Git worktree (the PRIVATE
companion). Repository visibility is not checked at runtime; commit-time hooks and
CI enforce PRIVATE publication. An unresolved destination raises; there is no
in-repo fallback.
"""
import os
from pathlib import Path
import stat

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class OutputPathError(RuntimeError):
    """A destination is not a safe companion path for private runtime data."""


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
        for node in (path.absolute(), *path.absolute().parents):
            try:
                info = node.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise OutputPathError('PRIVATE output cannot use filesystem aliases')
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
        repository = _nearest_repository(existing).resolve()
        if not path.is_relative_to(repository) or SOURCE_ROOT.is_relative_to(repository):
            raise OutputPathError('runtime output requires a separate PRIVATE worktree')
        return path, repository
    except (OSError, ValueError) as exc:
        raise OutputPathError('cannot check output destination: ' + str(exc)) from exc


def prove_output_path(requested):
    """Return the canonical target once it passes the companion path checks."""
    return _prove_output_path(requested)[0]


def prove_companion_root(requested):
    """Configuration profiles are separate PRIVATE worktree roots, never subdirectories."""
    path, repository = _prove_output_path(requested)
    if path != repository:
        raise OutputPathError('Select a PRIVATE worktree root; nested configuration profiles are unsupported')
    return path


def authorize_output(requested, *, directory=False, artifact_id=None):
    """Path-only admission; ``directory`` and ``artifact_id`` are kept for callers."""
    path = _prove_output_path(requested)[0]
    if directory and path.exists() and not path.is_dir():
        raise OutputPathError('directory output exists as a file')
    return path


def prepare_output(requested, *, artifact_id='current-reports'):
    """Recheck the path and its worktree after creating the destination's parents."""
    path, before = _prove_output_path(requested)
    path.parent.mkdir(parents=True, exist_ok=True)
    final, after = _prove_output_path(path)
    if final != path or before != after:
        raise OutputPathError('PRIVATE output destination changed while preparing its parent')
    return final
