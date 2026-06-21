"""Open a timestamped run batch and print its name for SMALLCAP_RUN.

Each run gets its own subdir under output_dir (e.g. reports/smallcap/2026-06-19_aginput/)
so a run's candidates / cheappass / deepdive / valuation / report files stay together
and runs can be compared across skill versions. A _run.json manifest records the date,
the skill git commit (+dirty flag), the label/note, and a snapshot of the valuation
config — this is the hook for "compare skill ability across versions".

Usage:
    export SMALLCAP_RUN=$(python tools/new_run.py --label aginput)
    # → every subsequent tool writes into reports/smallcap/<date>_aginput/
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

from _common import CFG, run_state_path, today

_REPO = Path(__file__).resolve().parent.parent

_SNAPSHOT_KEYS = [
    "wacc", "cap_rate_low", "cap_rate_high", "normalize_years",
    "cyclical_cv_threshold", "market_cap_max", "watch_band_max",
]


def _git_version(repo: Path) -> tuple[str, bool]:
    """Return (short_commit, dirty) for the skill repo, ('unknown', False) on failure."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unknown"
        dirty = bool(subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip())
        return commit, dirty
    except Exception:
        return "unknown", False


def main() -> None:
    ap = argparse.ArgumentParser(description="Open a timestamped run batch directory.")
    ap.add_argument("--label", required=True,
                    help="short run label, e.g. aginput / validation-v0.2.1 / spinoffs")
    ap.add_argument("--note", default="", help="optional free-text note recorded in the manifest")
    args = ap.parse_args()

    safe_label = args.label.strip().strip("/\\").replace(" ", "-")
    run_name = f"{today()}_{safe_label}"
    run_dir = Path(CFG["output_dir"]) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    commit, dirty = _git_version(_REPO)
    manifest = {
        "run_label": safe_label,
        "run_name": run_name,
        "created": today(),
        "skill_commit": commit,
        "skill_dirty": dirty,
        "note": args.note,
        "config_snapshot": {k: CFG.get(k) for k in _SNAPSHOT_KEYS},
    }
    (run_dir / "_run.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # v0.3.2 #10: park run-state under THIS run's batch dir (per-SMALLCAP_RUN), never a
    # single shared /tmp/smallcap_run.txt — so concurrent agents on different themes do
    # not clobber each other. run_state_path(run=run_name) resolves to <run_dir>/_run_state.txt.
    state_path = run_state_path(run=run_name)
    state_path.write_text(run_name + "\n", encoding="utf-8")

    # stdout = the batch name, consumed by: export SMALLCAP_RUN=$(python tools/new_run.py --label X)
    print(run_name)


if __name__ == "__main__":
    main()
