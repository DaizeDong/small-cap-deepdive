"""Generated source24 regressions. Every report and descriptor is synthetic."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_private_runs import state
from test_source22_contracts import modules

CASE = json.loads(Path(__file__).with_name("source24_contracts.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASE["reports"], ids=lambda case: case["name"])
def test_finalizer_parses_and_hashes_one_report_snapshot(modules, state, monkeypatch, case):
    directory = Path(state["root"])
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / ("report_" + CASE["ticker"] + ".md")
    first = case["first"].encode("utf-8")
    alternate = case["alternate"].encode("utf-8")
    report.write_bytes(first)
    original_bytes, original_text = Path.read_bytes, Path.read_text
    reads = []
    def snapshot(path):
        reads.append(str(path))
        return first if len(reads) % 2 else alternate
    def read_bytes(path):
        return snapshot(path) if path == report else original_bytes(path)
    def read_text(path, *args, **kwargs):
        return snapshot(path).decode("utf-8") if path == report else original_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "read_text", read_text)
    verdict = modules["finalize_run"].build_verdict(CASE["ticker"], directory, None)
    assert verdict["rating"] == case["expected_rating"]
    assert verdict["confidence"] == CASE["confidence"]
    assert verdict["verdict_date"] == CASE["date"]
    assert verdict["killflag_count"] == 0
    assert verdict["report_sha256"] == hashlib.sha256(first).hexdigest()
    assert verdict["report_sha256"] != hashlib.sha256(alternate).hexdigest()
    assert len(reads) == 1


def make_snapshot():
    from _signal_snapshot import snapshot_from_deep
    return snapshot_from_deep(CASE["deep"], CASE["ticker"], CASE["date"], CASE["source"])


@pytest.mark.parametrize("change", CASE["source_edits"], ids=lambda case: case["field"])
def test_recording_retains_source_edits_only_as_unverified_metadata(modules, state, monkeypatch, change):
    tracker = importlib.import_module("track_forward")
    monkeypatch.setattr(tracker, "_quote_on", lambda *_args, **_kwargs: {"price": None})
    snapshot = make_snapshot()
    snapshot["source"][change["field"]] = change["value"]
    verdict = {**CASE["verdict"], "signals_snapshot": snapshot}
    path = Path(state["root"]) / "synthetic_verdicts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([verdict]), encoding="utf-8")
    recorded = tracker._build_verdicts_from_json(path)[0]
    assert recorded["signals_snapshot"]["source"] == snapshot["source"]
    assert recorded["signals_snapshot"]["source_verification"] == "retained_unverified"
    assert recorded["signals_snapshot"]["signals"] == CASE["deep"]["signals"]
    assert not (path.parent / snapshot["source"]["artifact"]).exists()
    verdict["signals_snapshot"] = None
    path.write_text(json.dumps([verdict]), encoding="utf-8")
    without = tracker._build_verdicts_from_json(path)[0]
    assert (recorded["rating"], recorded["implied_prob"]) == (without["rating"], without["implied_prob"])


def test_legacy_snapshot_is_explicitly_marked_unverified_without_mutating_input():
    from _signal_snapshot import validate_signal_snapshot
    snapshot = make_snapshot()
    snapshot.pop("source_verification")
    before = deepcopy(snapshot)
    recorded = validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])
    assert "source_verification" not in snapshot
    assert snapshot == before
    assert recorded["source_verification"] == "retained_unverified"


@pytest.mark.parametrize("label", CASE["invalid_verification"])
def test_unproved_source_verification_claim_is_rejected(label):
    from _signal_snapshot import validate_signal_snapshot
    snapshot = make_snapshot()
    snapshot["source_verification"] = label
    with pytest.raises(ValueError, match="source verification"):
        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])


@pytest.mark.parametrize("change", CASE["bad_source"], ids=lambda case: case["name"])
def test_source_descriptor_shape_is_still_checked(change):
    from _signal_snapshot import validate_signal_snapshot
    snapshot = make_snapshot()
    snapshot["source"][change["field"]] = change["value"]
    with pytest.raises(ValueError, match="source metadata"):
        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])


def test_signal_payload_edit_without_digest_update_is_rejected():
    from _signal_snapshot import validate_signal_snapshot
    snapshot = make_snapshot()
    snapshot["signals"]["ownership"]["recent_13d_13g_count"] += 1
    with pytest.raises(ValueError, match="digest"):
        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])
