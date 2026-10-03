"""Generated Source26 receipt and debt-boundary regressions."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from make_fixtures import source26_scenarios
from test_private_runs import state
from test_tracking_integrity import tracker
from test_financial_evidence import valuation_module
from _calibration import (_adjudication_review, _buy_data_integrity_summary,
                          _price_scorable, _adjudication_blocks_price)
from _valuation_model import _VALUATION_DEFAULTS

CASE = source26_scenarios()
INVALID = [name for name in CASE["review"] if name not in ("clean", "fp")]


@pytest.mark.parametrize("name", INVALID)
def test_unsupported_review_stays_pending_and_outside_prices(name):
    row = deepcopy(CASE["review"][name])
    row["scored"] = True
    before = deepcopy(row)
    assert _adjudication_review(row)["status"] == "pending"
    summary = _buy_data_integrity_summary([row])
    assert summary["rate"] is None
    assert summary["reviewed_buys"] == 0 and summary["pending_buys"] == 1
    assert _adjudication_blocks_price(row)
    assert _price_scorable([row]) == []
    assert row == before


def test_valid_receipts_measure_coverage_without_admitting_false_positive_prices():
    clean, fp = (deepcopy(CASE["review"][key]) for key in ("clean", "fp"))
    bare = deepcopy(CASE["review"]["bare_fp"])
    clean["scored"] = fp["scored"] = bare["scored"] = True
    summary = _buy_data_integrity_summary([clean, fp, bare])
    assert summary == {"rate": 0.5, "total_buys": 3, "reviewed_buys": 2,
                       "clean_buys": 1, "false_positive_buys": 1,
                       "pending_buys": 1, "review_coverage": 2 / 3}
    assert _price_scorable([clean, fp, bare]) == [clean]
    plain = {key: value for key, value in bare.items()
             if key not in ("adjudication", "adjudication_evidence")}
    assert _price_scorable([plain]) == [plain]


@pytest.mark.parametrize("name", INVALID)
def test_append_rejects_invalid_completed_claim_before_any_write(tracker, monkeypatch, name):
    calls = []
    monkeypatch.setattr(tracker, "prepare_output", lambda *_: calls.append("write"))
    with pytest.raises(ValueError):
        tracker._append_verdict(deepcopy(CASE["review"][name]))
    assert calls == []


@pytest.mark.parametrize("name", ("bare_clean", "bare_fp"))
def test_legacy_snapshot_preserves_claim_but_cannot_add_another_bare_claim(tracker, name):
    row = deepcopy(CASE["review"][name])
    tracker.METRICS_DIR.mkdir(parents=True)
    raw = (json.dumps(row, sort_keys=True) + "\n").encode()
    tracker.VERDICTS_FILE.write_bytes(raw)
    rows = tracker._load_verdicts()
    assert rows[0] == row
    rows[0]["notes"] = "synthetic score-only annotation"
    tracker._save_verdicts(rows)
    assert tracker._load_verdicts()[0]["adjudication"] == row["adjudication"]
    before = tracker.VERDICTS_FILE.read_bytes()
    rows = tracker._load_verdicts()
    added = deepcopy(row)
    added["ticker"] = "SYNRNEW"
    rows.append(added)
    with pytest.raises(ValueError):
        tracker._save_verdicts(rows)
    assert tracker.VERDICTS_FILE.read_bytes() == before


@pytest.mark.parametrize("name", ("clean", "fp"))
def test_explicit_receipt_attachment_is_bound_and_preserves_original_claim(tracker, name):
    completed = deepcopy(CASE["review"][name])
    receipt = completed.pop("adjudication_evidence")
    updated = tracker._with_adjudication_receipt(completed, receipt)
    assert updated["adjudication"] == completed["adjudication"]
    assert _adjudication_review(updated)["status"] == "reviewed"
    assert "adjudication_evidence" not in completed
    changed = deepcopy(receipt)
    changed["verdict"]["report_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        tracker._with_adjudication_receipt(completed, changed)


def test_receipt_command_uses_existing_private_snapshot_transaction(tracker):
    completed = deepcopy(CASE["review"]["clean"])
    receipt = completed.pop("adjudication_evidence")
    tracker.METRICS_DIR.mkdir(parents=True)
    tracker.VERDICTS_FILE.write_text(json.dumps(completed) + "\n", encoding="utf-8")
    path = tracker.METRICS_DIR / "synthetic-review.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    tracker.cmd_adjudicate(SimpleNamespace(adjudicate=str(path)))
    rows = tracker._load_verdicts()
    assert rows[0]["adjudication_evidence"] == receipt
    assert _buy_data_integrity_summary(rows)["reviewed_buys"] == 1


def test_status_and_scorecard_report_bare_labels_as_pending(tracker, capsys):
    rows = [CASE["review"]["bare_clean"], CASE["review"]["bare_fp"]]
    tracker.METRICS_DIR.mkdir(parents=True)
    tracker.VERDICTS_FILE.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    tracker.cmd_status(SimpleNamespace())
    status = capsys.readouterr().out
    assert "reviewed 0/2" in status and "pending 2" in status and "N/A" in status
    tracker.cmd_scorecard(SimpleNamespace())
    scorecard = tracker.SCORECARD_FILE.read_text(encoding="utf-8")
    assert "reviewed 0/2" in scorecard and "pending 2" in scorecard
    assert "Price quarantine: 2" in scorecard


@pytest.mark.parametrize("name", list(CASE["debt"]))
def test_latest_debt_evidence_controls_ev_and_buy(valuation_module, name):
    case = CASE["debt"][name]
    result = valuation_module.compute_valuation(deepcopy(case["data"]), CASE["market_cap"],
                                                dict(_VALUATION_DEFAULTS))
    assert result["debt_evidence_status"] == case["status"]
    assert result["debt_evidence_uncertain"] is case["uncertain"]
    assert result["buy_eligible"] is (not case["uncertain"])
    if case["uncertain"]:
        assert result["ev"] is None and result["ev_sales"] is None and result["ev_ebitda"] is None
        assert "debt_evidence_uncertain" in result["buy_ineligible_reasons"]
    else:
        der = case["data"]["derived"]
        assert result["ev"] == CASE["market_cap"] + der["latest_total_debt"] - der["latest_cash"]
        assert result["margin_of_safety_pct"] == 0.3889
