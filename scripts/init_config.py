#!/usr/bin/env python3
"""Stamp a spec-conformant config.json for small-cap-deepdive (config-spec E3/E4).

Template-driven + deterministic: copies reference/config.example.json (the authoritative
default schema) into the resolved config dir as config.json. Re-running with the same --out
produces byte-identical output (E4). It then points out the one hard requirement —
sec_user_agent (your EDGAR User-Agent: real name + email) — which you must edit before use.

Discovery convention this skill uses (also in CONFIG.md, E2). config.json resolves from, in order:
  1. $SMALL_CAP_DEEPDIVE_CONFIG_DIR   (or alias $SMALL_CAP_DEEPDIVE_CONFIG) -> <dir>/config.json
  2. ~/.small-cap-deepdive-config/config.json          (dotfile default)
  3. ~/.config/small-cap-deepdive-config/config.json   (XDG default)
  4. nothing found -> NOT INITIALIZED. No step lands inside the repo.

Usage:
  python scripts/init_config.py [--out <dir>] [--force]

--out  target config DIR; if omitted, uses $SMALL_CAP_DEEPDIVE_CONFIG_DIR, else
       ~/.small-cap-deepdive-config/. It used to default to the in-repo reference/ dir, which made
       "just run init" the shortest path to an EDGAR identity inside a public repo. Writing into
       the repo is now refused outright: a read may degrade, a write must fail hard.
Stdlib only. Cross-platform. Writes config.json outside the repo; never echoes PII.
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
_DEFAULT_OUT = "~/.small-cap-deepdive-config"


def resolve_out(out_arg):
    """Target config DIR. Always outside the repo: this writes a file that will hold PII."""
    if out_arg:
        return Path(os.path.expanduser(out_arg))
    env = os.environ.get("SMALL_CAP_DEEPDIVE_CONFIG_DIR") or os.environ.get("SMALL_CAP_DEEPDIVE_CONFIG")
    if env:
        return Path(os.path.expanduser(env))
    return Path(os.path.expanduser(_DEFAULT_OUT))


def is_inside_repo(p):
    try:
        return _REPO == p.resolve() or _REPO in p.resolve().parents
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="Stamp a spec-conformant config.json from the example template.")
    ap.add_argument("--out", default=None,
                    help="target config dir (default: $SMALL_CAP_DEEPDIVE_CONFIG_DIR, else %s)"
                         % _DEFAULT_OUT)
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
    # A write must fail hard. config.json holds the sec_user_agent PII, so a target inside this
    # public repo is refused with instructions rather than quietly stamped there.
    if is_inside_repo(out_dir):
        print("ERROR: refusing to write config.json inside the skill repo: %s" % out_dir)
        print("  config.json holds your EDGAR identity (real name + email). It belongs outside")
        print("  a public repo, always. There is no in-repo location for it any more.")
        print("    python scripts/init_config.py --out %s" % _DEFAULT_OUT)
        return 2
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
    # Discovery finds ~/.small-cap-deepdive-config and the XDG dir on its own; anywhere else needs
    # the env var, so only print the hint when it is actually required.
    _auto = [Path(os.path.expanduser("~/.small-cap-deepdive-config")),
             Path(os.path.expanduser("~/.config/small-cap-deepdive-config"))]
    if all(out_dir.resolve() != d.resolve() for d in _auto):
        print("  Then point the skill at this dir:")
        print("    export SMALL_CAP_DEEPDIVE_CONFIG_DIR=%s" % out_dir)
    print("")
    print("Then verify:  python scripts/verify_config.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
