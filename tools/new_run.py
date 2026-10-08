"""Allocate an exclusive PRIVATE run or resume matching metadata.

Without --input-hash, allocation hashes canonical UTF-8 JSON containing label,
note and the nonsecret config snapshot: sorted keys, compact separators and
ensure_ascii=False. Resume always requires an explicit SHA256.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote
import uuid

from _common import load_config, output_root, prove_output_path, today, validate_run_name
from _output_paths import authorize_output

_REPO = Path(__file__).resolve().parent.parent
_SNAPSHOT_KEYS = ['wacc', 'cap_rate_low', 'cap_rate_high', 'normalize_years',
                  'cyclical_cv_threshold', 'market_cap_max', 'watch_band_max']


def _git_version(repo):
    """Failed source-version queries remain explicitly unknown."""
    try:
        commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--short', 'HEAD'],
                                capture_output=True, text=True, timeout=10)
        status = subprocess.run(['git', '-C', str(repo), 'status', '--porcelain'],
                                capture_output=True, text=True, timeout=10)
        if commit.returncode or status.returncode:
            return 'unknown', None
        return commit.stdout.strip() or 'unknown', bool(status.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return 'unknown', None


def _label(value):
    if not value or not value.strip().strip('.') or any(
            char in '/\\:' or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('label must be nonempty and contain no path syntax or control characters')
    return quote(value, safe='-_')


def _input_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', value):
        raise ValueError('input hash must be a 64-hex SHA256')
    return value.lower()


def _run_directory(root, name):
    directory = prove_output_path(root/validate_run_name(name))
    if directory.parent != root or directory.name != name:
        raise ValueError('run identity escapes its configured reports root')
    return directory


def resume(root, name, expected_hash):
    directory = _run_directory(root, name)
    manifest_path = prove_output_path(directory/'_run.json')
    state_path = prove_output_path(directory/'_run_state.txt')
    if manifest_path.parent != directory or state_path.parent != directory:
        raise ValueError('run metadata escapes its directory')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        state = state_path.read_text(encoding='utf-8').strip()
    except (OSError, ValueError) as exc:
        raise ValueError('cannot resume: run manifest or state is missing, unreadable or invalid') from exc
    if not isinstance(manifest, dict) or any(key not in manifest for key in (
            'run_label', 'run_name', 'created', 'skill_commit', 'skill_dirty',
            'note', 'config_snapshot', 'input_hash', 'reports_root')):
        raise ValueError('resume manifest is incomplete or invalid')
    if (not all(isinstance(manifest[key], str) for key in (
            'run_label', 'run_name', 'created', 'skill_commit', 'note', 'input_hash', 'reports_root'))
            or type(manifest['skill_dirty']) not in (bool, type(None))):
        raise ValueError('resume manifest field types are invalid')
    if (manifest['run_name'] != name or manifest['reports_root'] != str(root)
            or _input_hash(manifest['input_hash']) != expected_hash
            or not isinstance(manifest['config_snapshot'], dict)
            or state != name):
        raise ValueError('resume manifest hash, root or run identity does not match')
    return name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--note', default='')
    parser.add_argument('--input-hash')
    parser.add_argument('--resume', metavar='RUN_ID')
    args = parser.parse_args(argv)
    label = _label(args.label)
    if args.resume is not None:
        validate_run_name(args.resume)
        if args.input_hash is None:
            raise ValueError('resume requires --input-hash SHA256')
    supplied_hash = _input_hash(args.input_hash) if args.input_hash is not None else None
    root = output_root()
    if args.resume is not None:
        name = resume(root, args.resume, supplied_hash)
    else:
        config = load_config()
        snapshot = {key: config.get(key) for key in _SNAPSHOT_KEYS}
        canonical = json.dumps({'label': args.label, 'note': args.note, 'config_snapshot': snapshot},
                               sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        input_hash = supplied_hash or hashlib.sha256(canonical).hexdigest()
        created = today()
        commit, dirty = _git_version(_REPO)
        authorize_output(root, directory=True, artifact_id='current-reports')
        root.mkdir(parents=True, exist_ok=True)
        root = prove_output_path(root)
        for attempt in range(8):
            name = f'{created}_{label}_{uuid.uuid4().hex}'
            directory = _run_directory(root, name)
            authorize_output(directory, directory=True, artifact_id='current-reports')
            try:
                directory.mkdir(exist_ok=False)
                break
            except FileExistsError:
                continue
        else:
            raise RuntimeError('could not allocate an exclusive run directory')
        manifest = {'run_label': args.label, 'run_name': name, 'created': created,
                    'skill_commit': commit, 'skill_dirty': dirty, 'note': args.note,
                    'config_snapshot': snapshot, 'input_hash': input_hash, 'reports_root': str(root)}
        for filename, text in (
                ('_run.json', json.dumps(manifest, indent=2, ensure_ascii=False)+'\n'),
                ('_run_state.txt', name+'\n')):
            target = authorize_output(directory/filename, artifact_id='current-reports')
            if target.parent != directory:
                raise ValueError('allocated run metadata escaped its directory')
            with target.open('x', encoding='utf-8') as stream:
                stream.write(text)
    print(name)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print('new_run: '+str(exc), file=sys.stderr)
        raise SystemExit(1)
