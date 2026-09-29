#!/usr/bin/env python3
"""Initialize deterministic configuration in a verified, versioned PRIVATE companion.

Explicit --out takes precedence over the supported config environment selectors.
Otherwise use the same companion discovery as the runtime. An existing PRIVATE
Git worktree is required before writing or asking for an EDGAR identity.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

_REPO = Path(__file__).resolve().parents[1]
_EXAMPLE = _REPO / 'reference/config.example.json'
sys.path.insert(0, str(_REPO / 'tools'))
from _output_paths import OutputPathError, prove_output_path


def resolve_out(out_arg):
    """Use the runtime's companion selectors without requiring config.json yet."""
    selected = out_arg or os.environ.get('SMALL_CAP_DEEPDIVE_CONFIG_DIR') or os.environ.get('SMALL_CAP_DEEPDIVE_CONFIG')
    if selected:
        return Path(selected).expanduser()
    from _common import _companion_root
    return _companion_root()


def check_config_target(target):
    """Refuse file aliases before either skipping or replacing existing config."""
    try:
        info = target.lstat()
    except FileNotFoundError:
        return
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, 'st_file_attributes', 0) & 1024):
        raise OutputPathError('config.json must be an ordinary file with no links')


def write_config(target, text):
    """Replace only after a complete write and a fresh destination proof."""
    descriptor, name = tempfile.mkstemp(prefix='.config-', suffix='.tmp', dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        check_config_target(target)
        if prove_output_path(target) != target:
            raise OutputPathError('config destination changed during initialization')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', help='directory within an existing PRIVATE companion')
    parser.add_argument('--force', action='store_true', help='replace an existing ordinary config.json')
    args = parser.parse_args()
    try:
        out_dir = prove_output_path(resolve_out(args.out))
        target = out_dir / 'config.json'
        check_config_target(target)
        if prove_output_path(target) != target:
            raise OutputPathError('config destination must remain in the verified directory')
        template = json.loads(_EXAMPLE.read_text(encoding='utf-8'))
        if not isinstance(template, dict):
            raise ValueError('config template must be a JSON object')
        out_dir.mkdir(parents=True, exist_ok=True)
        if target.exists() and not args.force:
            print('Existing config preserved; use --force to replace it.')
        else:
            write_config(target, json.dumps(template, indent=2, ensure_ascii=False) + '\n')
            print('Config initialized.')
    except (OSError, RuntimeError, ValueError) as error:
        print('ERROR: ' + str(error))
        print('Create or clone a PRIVATE Git companion with an origin remote, then select it with --out or SMALL_CAP_DEEPDIVE_CONFIG_DIR.')
        return 2

    print('Verified PRIVATE configuration directory: ' + str(out_dir))
    print('Set sec_user_agent privately in config.json before live EDGAR requests.')
    print('Retain configuration and runtime history in the PRIVATE companion with commit and push.')
    print('Use SMALL_CAP_DEEPDIVE_CONFIG_DIR to select this directory for subsequent commands.')
    print('Then verify: python scripts/verify_config.py --json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
