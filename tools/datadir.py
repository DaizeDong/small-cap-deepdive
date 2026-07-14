#!/usr/bin/env python3
"""datadir -- where a skill's REAL-RUN OUTPUT goes. Never the repo.

These skills already had a private-companion-config boundary, and it worked. But it only ever
covered INPUTS: the credentials, the mailboxes, the account slugs. Nothing covered OUTPUTS -- what
the skill LEARNED from a real run. So `track_forward.py` appended the operator's actual stock
verdicts (ticker, entry date, entry price; hundreds of them) to `metrics/verdicts.jsonl`, and
`metrics/live-runs.jsonl` recorded what was bought and where it shipped -- straight into public
repos, on every run, by design.

No content scanner catches that. There is no email in it, no phone, no ZIP. It is just the
operator's life, correctly formatted. The fix is not a better sieve, it is a pipe that does not
point at the public repo in the first place.

  resolve_data_dir("small-cap-deepdive")  ->  the private directory, or None

Discovery order (first existing wins):
  1. $<SKILL>_DATA_DIR                       explicit override / hot-swap
  2. ~/.<skill>-config/data/                 reuse the private companion config repo it already has
  3. ~/.<skill>-data/                        standalone fallback
  4. None                                    -> the tool is UNINITIALIZED, which is exactly what a
                                                freshly cloned public skill SHOULD be

`data_path()` raises a DataDirNotInitialized with instructions rather than silently falling back to a
path inside the repo. A silent in-repo fallback is how this happened: `reference/config.json` was the
documented "legacy fallback", and the operator's real SEC contact email ended up committed in it.
A fallback into the repo is not a convenience, it is the leak.

Vendored into each skill as `tools/datadir.py`. Stdlib only.
"""
import os
from pathlib import Path


class DataDirNotInitialized(RuntimeError):
    pass


def _env_var(skill):
    return skill.upper().replace("-", "_") + "_DATA_DIR"


def resolve_data_dir(skill, create=False):
    """Return the private data dir for `skill`, or None if the tool is uninitialized."""
    d = os.environ.get(_env_var(skill))
    candidates = []
    if d:
        candidates.append(Path(os.path.expanduser(d)))
    candidates.append(Path(os.path.expanduser("~/.%s-config" % skill)) / "data")
    candidates.append(Path(os.path.expanduser("~/.%s-data" % skill)))
    for p in candidates:
        if p.is_dir():
            return p
    if create:
        p = candidates[0] if d else candidates[1]
        p.mkdir(parents=True, exist_ok=True)
        return p
    return None


def data_path(skill, relpath, create=False):
    """Resolve <private data dir>/<relpath>. Never returns a path inside the repo."""
    base = resolve_data_dir(skill, create=create)
    if base is None:
        raise DataDirNotInitialized(
            "%s has no private data directory, so it has nowhere to put real-run output.\n"
            "This is the correct state for a freshly cloned public skill: it ships as an\n"
            "uninitialized tool. Point it at your own store:\n"
            "    mkdir -p ~/.%s-config/data\n"
            "    (or set %s)\n"
            "Real-run output NEVER goes back into the repo -- the repo carries only the schema\n"
            "(<file>.example) and a synthetic fixture set."
            % (skill, skill, _env_var(skill)))
    p = base / relpath
    if create:
        p.parent.mkdir(parents=True, exist_ok=True)
    return p
