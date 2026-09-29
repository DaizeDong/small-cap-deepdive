"""Ledger writes and user-visible integrity summaries preserve uncertainty."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_private_runs import state
from make_fixtures import tracking_scenarios

CASE = tracking_scenarios()


@pytest.fixture
def tracker(state, monkeypatch):
    module = importlib.import_module('track_forward')
    metrics = Path(state['companion']) / 'data' / 'metrics'
    monkeypatch.setattr(module, 'METRICS_DIR', metrics)
    monkeypatch.setattr(module, 'VERDICTS_FILE', metrics / 'verdicts.jsonl')
    monkeypatch.setattr(module, 'SCORECARD_FILE', metrics / 'scorecard.md')
    return module


@pytest.mark.parametrize('content', CASE['malformed_ledgers'])
def test_bad_ledger_is_not_silently_dropped_before_rewrite(tracker, content):
    tracker.METRICS_DIR.mkdir(parents=True)
    tracker.VERDICTS_FILE.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError, match='ledger|line|record'):
        tracker._load_verdicts()
    assert tracker.VERDICTS_FILE.read_text(encoding='utf-8') == content


@pytest.mark.parametrize('operation', ['append', 'save', 'scorecard'])
@pytest.mark.parametrize('visibility', ['PUBLIC', None])
def test_unproved_tracker_write_preserves_all_existing_bytes(tracker, state, operation, visibility):
    tracker.METRICS_DIR.mkdir(parents=True)
    tracker.VERDICTS_FILE.write_text(CASE['prior_bytes'], encoding='utf-8')
    state['visibility']['example/synthetic-smallcap-config'] = visibility
    before = {p.name: p.read_bytes() for p in tracker.METRICS_DIR.iterdir()}
    with pytest.raises(RuntimeError, match='PRIVATE|PUBLIC|visibility|verification'):
        if operation == 'append':
            tracker._append_verdict(CASE['unreviewed'][0])
        elif operation == 'save':
            tracker._save_verdicts(CASE['unreviewed'])
        else:
            tracker.cmd_scorecard(SimpleNamespace())
    assert {p.name: p.read_bytes() for p in tracker.METRICS_DIR.iterdir()} == before


def test_private_tracker_roundtrip_preserves_rows(tracker):
    tracker._save_verdicts(CASE['mixed'][:2])
    tracker._append_verdict(CASE['mixed'][2])
    assert tracker._load_verdicts() == CASE['mixed'][:3]


@pytest.mark.parametrize('ending', ['', '\n', '\r\n'])
def test_append_keeps_valid_last_record_without_final_newline(tracker, ending):
    tracker.METRICS_DIR.mkdir(parents=True)
    first = json.dumps(CASE['mixed'][0], ensure_ascii=False)
    tracker.VERDICTS_FILE.write_bytes((first + ending).encode('utf-8'))
    assert tracker._load_verdicts() == CASE['mixed'][:1]
    tracker._append_verdict(CASE['mixed'][1])
    assert tracker._load_verdicts() == CASE['mixed'][:2]


def test_status_reports_pending_data_reviews(tracker, capsys):
    tracker._save_verdicts(CASE['mixed'])
    tracker.cmd_status(SimpleNamespace())
    text = capsys.readouterr().out
    assert '50.0%' in text
    assert 'reviewed 2/4' in text
    assert 'pending 2' in text


def test_unreviewed_buys_do_not_appear_verified_in_scorecard(tracker):
    tracker._save_verdicts(CASE['unreviewed'])
    tracker.cmd_scorecard(SimpleNamespace())
    text = tracker.SCORECARD_FILE.read_text(encoding='utf-8')
    assert 'reviewed 0/1' in text
    assert 'pending 1' in text
    integrity = next(line for line in text.splitlines() if 'BUY data-integrity' in line)
    assert '100.0%' not in integrity
