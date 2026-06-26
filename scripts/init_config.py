#!/usr/bin/env python3
"""Stamp a spec-conformant config.json for small-cap-deepdive (config-spec E3/E4).

Template-driven + deterministic: copies reference/config.example.json (the authoritative
default schema) into the resolved config dir as config.json. Re-running with the same --out
produces byte-identical output (E4). It then points out the one hard requirement —
sec_user_agent (your EDGAR User-Agent: real name + email) — which you must edit before use.

Discovery convention this skill uses (also in CONFIG.md, E2). config.json resolves from, in order:
  1. $SMALL_CAP_DEEPDIVE_CONFIG_DIR   (or alias $SMALL_CAP_DEEPDIVE_CONFIG) -> <dir>/config.json
  2. ~/.small-cap-deepdive-config/config.json          (dotfile fallback)
  3. ~/.config/small-cap-deepdive-config/config.json   (XDG fallback)
  4. reference/config.json                             (in-repo legacy/default)

Usage:
  python scripts/init_config.py [--out <dir>] [--force]

--out  target config DIR; if omitted, uses $SMALL_CAP_DEEPDIVE_CONFIG_DIR, else the in-repo
       reference/ dir (zero-config default — identical to the legacy `cp` setup).
Stdlib only. Cross-platform. Writes config.json (gitignored / Mode B); never echoes PII.
"""
import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_EXAMPLE = _REPO / "reference" / "config.example.json"
_PLACEHOLDER_UA = "small-cap-deepdive research your-email@example.com"


def resolve_out(out_arg):
    if out_arg:
        return Path(os.path.expanduser(out_arg))
    env = os.environ.get("SMALL_CAP_DEEPDIVE_CONFIG_DIR") or os.environ.get("SMALL_CAP_DEEPDIVE_CONFIG")
    if env:
        return Path(os.path.expanduser(env))
    return _REPO / "reference"  # zero-config default == legacy in-repo location


def main():
    ap = argparse.ArgumentParser(description="Stamp a spec-conformant config.json from the example template.")
    ap.add_argument("--out", default=None, help="target config dir (default: env var or in-repo reference/)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing config.json")
    a = ap.parse_args()

    if not _EXAMPLE.is_file():
        print("ERROR: template not found: %s" % _EXAMPLE)
        return 2
    try:
        template = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    except Exception as e:
        print("ERROR: config.example.json is not valid JSON: %s" % e)
        return 2

    out_dir = resolve_out(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "config.json"

    print("Init small-cap-deepdive config")
    print("  template : %s" % _EXAMPLE)
    print("  target   : %s" % target)
    if target.exists() and not a.force:
        print("  SKIP (exists): pass --force to overwrite. Existing config left untouched.")
    else:
        # Deterministic stamp: pretty-printed copy of the example schema, sorted-stable, \n newlines.
        target.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
        print("  wrote: %s" % target)

    print("")
    print("REQUIRED before first run: set \"sec_user_agent\" to your real name + email")
    print("  (EDGAR User-Agent; the placeholder %r causes 403s from efts.sec.gov)." % _PLACEHOLDER_UA)
    if out_dir.resolve() != (_REPO / "reference").resolve():
        env_hint = out_dir
        print("  Then point the skill at this dir:")
        print("    export SMALL_CAP_DEEPDIVE_CONFIG_DIR=%s" % env_hint)
    print("")
    print("Then verify:  python scripts/verify_config.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
