"""Producer outcomes retain all input identities and never promote unobserved source work."""
import copy
import json
import re
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import deepdive_data as producer
import filter_by_sic as stages
import run_theme
from make_fixtures import downstream_producer_completion_scenarios, source31_valuation_config


@pytest.fixture
def sample():
    return downstream_producer_completion_scenarios()


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    calls = {"init": 0, "pull": []}

    def output(path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def initialize():
        calls["init"] += 1

    monkeypatch.setattr(stages, "prepare_output", output)
    monkeypatch.setattr(producer, "REPORTS", tmp_path)
    monkeypatch.setattr(producer, "init_edgar", initialize)
    return tmp_path, calls


def artifact(path, rows, *, complete=True):
    path.write_text(json.dumps(rows), encoding="utf-8")
    completion = stages.stage_completion("synthetic_candidates", len(rows),
        work=[stages.stage_work("synthetic_input", status="complete" if complete else "unavailable")])
    stages.write_stage_receipt(path, completion)
    return path


def survivors(runtime, sample, *, empty=False, complete=True):
    run_dir, _ = runtime
    original = sample["empty"] if empty else sample["original_candidates"]
    source = artifact(run_dir / "candidates_synthetic.json", original, complete=complete)
    request_path = run_theme.prepare_gate2_request(source)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response = run_dir / "gate2_workflow_result.json"
    response.write_text(json.dumps({"schema": "smallcap.gate2.result.v1", "input": request["input"],
                                   "all": sample["empty"] if empty else sample["gate2_outcomes"]}),
                        encoding="utf-8")
    _, path, _ = run_theme.persist_gate2_result(request_path, response)
    return path


def mock_pull(monkeypatch, runtime, sample, *, incomplete=False):
    _, calls = runtime

    def pull(ticker, cik):
        calls["pull"].append((ticker, cik))
        data = copy.deepcopy(sample["pull_data_incomplete" if incomplete else "pull_data"])
        data.update(ticker=ticker, cik=cik)
        return data

    monkeypatch.setattr(producer, "pull", pull)


def configure_valuation(monkeypatch):
    import valuation
    monkeypatch.setattr(valuation, "_val_cfg", source31_valuation_config)
    return valuation


def assert_successful_valuation(output, completion, row):
    block = json.loads(output.read_text(encoding="utf-8"))
    assert block.get("status") != "ERROR", block
    assert block["ticker"] == row["ticker"] and "mos_basis" in block
    assert block["market_cap_source"] == "synthetic_fixture"
    assert "valuation_failed" not in completion["reasons"]


def prepared(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)
    producer.run_batch(path, pull_date=sample["verdict_date"])
    request_path = producer.prepare_fanout_request(path, sample["verdict_date"])
    valuation = configure_valuation(monkeypatch)
    monkeypatch.setattr(valuation, "_get_market_cap", lambda *_: (sample["candidates"][0]["mktcap"], "synthetic_fixture"))
    for row in sample["survivor_rows"]:
        output, completion = producer.prepare_valuation_artifact(request_path, row["input_index"])
        assert_successful_valuation(output, completion, row)
    return path, request_path


def response(runtime, sample, request_path, case):
    run_dir, _ = runtime
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = {"schema": "smallcap.deepdive.result.v1", "input": request["input"],
              "request_id": request["request_id"],
              "all": copy.deepcopy(sample["fanout_outcomes"][case])}
    path = run_dir / "deepdive_workflow_result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def test_bound_survivor_indices_retain_original_candidate_positions(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [row["input_index"] for row in rows] == [row["input_index"] for row in sample["survivor_rows"]]
    assert completion["status"] == "partial"
    for row, expected in zip(rows, sample["survivor_rows"]):
        receipt = stages.read_stage_receipt(output.parent / row["artifact"], 1)
        assert receipt["input_identity"] == producer._identity(expected)
        assert receipt["input"] == producer._binding(path)
        assert "financial_source_completion_unobserved" in receipt["reasons"]
        assert "sic_source_completion_unobserved" in receipt["reasons"]
        assert receipt["row_count"] == 1


@pytest.mark.parametrize("incomplete", [False, True])
def test_returned_payload_cannot_prove_source_completion(runtime, sample, monkeypatch, incomplete):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample, incomplete=incomplete)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    assert completion["status"] == "partial"
    first = json.loads(output.read_text(encoding="utf-8"))["all"][0]
    receipt = stages.read_stage_receipt(output.parent / first["artifact"], 1)
    assert first["data_status"] == "partial"
    observed = [w for w in receipt["work"] if w["source"] == "observed_financial_series"]
    assert len(observed) == 14
    assert all(w["status"] == ("unavailable" if incomplete else "complete") for w in observed)


def test_complete_empty_bound_cohort_never_initializes_provider(runtime, sample):
    path = survivors(runtime, sample, empty=True)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    assert json.loads(output.read_text(encoding="utf-8"))["all"] == []
    assert completion["status"] == "complete" and completion["empty"] is True
    assert runtime[1] == {"init": 0, "pull": []}


def test_empty_upstream_without_completion_stays_incomplete(runtime, sample):
    path = survivors(runtime, sample, empty=True, complete=False)
    _, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    assert completion["status"] != "complete"
    assert runtime[1]["init"] == 0


@pytest.mark.parametrize("case", [
    "nonobject", "missing_ticker", "null_ticker", "nonstring_ticker", "empty_ticker",
    "path_ticker", "missing_cik", "null_cik", "invalid_cik", "missing_band",
    "invalid_band", "list_band", "object_band", "malformed_watch", "malformed_large",
])
def test_all_malformed_rows_fail_before_provider_or_output(runtime, sample, case):
    run_dir, calls = runtime
    path = artifact(run_dir / "candidates_gate2_survivors.json", [sample["malformed_rows"][case]])
    with pytest.raises(ValueError):
        producer.run_batch(path, pull_date=sample["verdict_date"])
    assert calls["init"] == 0
    assert not (run_dir / "deepdive_data_results.json").exists()
    assert not list(run_dir.glob("deepdive_*.json"))


def test_generic_case_colliding_identity_is_invalid_before_provider(runtime, sample):
    run_dir, calls = runtime
    rows = copy.deepcopy(sample["candidates"])
    rows[1]["ticker"] = rows[0]["ticker"].lower()
    path = artifact(run_dir / "candidates_synthetic.json", rows)
    with pytest.raises(ValueError, match="duplicated"):
        producer.run_batch(path, pull_date=sample["verdict_date"])
    assert calls["init"] == 0


@pytest.mark.parametrize("shape", ["object", "malformed"])
def test_invalid_candidate_envelope_is_not_an_empty_cohort(runtime, sample, shape):
    run_dir, calls = runtime
    path = run_dir / "candidates_synthetic.json"
    content = json.dumps({"candidates": sample["candidates"]}) if shape == "object" else "{"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        producer.run_batch(path, pull_date=sample["verdict_date"])
    assert calls["init"] == 0
    assert not (run_dir / "deepdive_data_results.json").exists()


def test_watch_and_large_have_explicit_skipped_outcomes(runtime, sample):
    run_dir, calls = runtime
    rows = [{k: v for k, v in row.items() if k != "input_index"} for row in sample["skipped_rows"]]
    path = artifact(run_dir / "candidates_synthetic.json", rows)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    outcomes = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [row["data_status"] for row in outcomes] == ["skipped", "skipped"]
    assert all(row["artifact"] is None for row in outcomes)
    assert calls["init"] == 0
    assert completion["status"] == "partial"  # This legacy list has no bound Gate2 input.


def test_modified_survivor_bytes_do_not_reuse_completed_gate2(runtime, sample):
    path = survivors(runtime, sample)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="receipt"):
        producer.run_batch(path, pull_date=sample["verdict_date"])
    assert runtime[1]["init"] == 0


def test_init_failure_has_an_error_artifact_for_every_input(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)

    def fail():
        raise RuntimeError(sample["pull_errors"][0]["error_code"])

    monkeypatch.setattr(producer, "init_edgar", fail)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert len(rows) == len(sample["survivor_rows"])
    assert all(row["data_status"] == "error" for row in rows)
    for row in rows:
        assert json.loads((output.parent / row["artifact"]).read_text(encoding="utf-8"))["status"] == "ERROR"
        assert stages.read_stage_receipt(output.parent / row["artifact"], 1)["status"] != "complete"
    assert completion["status"] != "complete"


def test_one_pull_failure_does_not_drop_the_other_identity(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)

    def pull(ticker, cik):
        if ticker == sample["candidates"][0]["ticker"]:
            raise RuntimeError(sample["pull_errors"][0]["error_code"])
        return {**copy.deepcopy(sample["pull_data"]), "ticker": ticker, "cik": cik}

    monkeypatch.setattr(producer, "pull", pull)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [row["data_status"] for row in rows] == ["error", "partial"]
    assert completion["status"] == "partial"


def test_persistence_failure_propagates_without_aggregate_success(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)

    def fail(*_):
        raise OSError("synthetic_write_failure")

    monkeypatch.setattr(producer, "write_stage_receipt", fail)
    with pytest.raises(OSError, match="synthetic_write_failure"):
        producer.run_batch(path, pull_date=sample["verdict_date"])
    assert not (path.parent / "deepdive_data_results.json").exists()


def test_existing_data_artifact_is_never_overwritten(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)
    output, _ = producer.run_batch(path, pull_date=sample["verdict_date"])
    before = {p.name: p.read_bytes() for p in output.parent.glob("deepdive_*.json")}
    with pytest.raises(FileExistsError):
        producer.run_batch(path, pull_date=sample["verdict_date"])
    assert {p.name: p.read_bytes() for p in output.parent.glob("deepdive_*.json")} == before
    assert runtime[1]["init"] == 1


def test_legacy_cik_only_retains_original_identity(runtime, sample, monkeypatch):
    run_dir, _ = runtime
    row = {**sample["candidates"][0], "ticker": ""}
    path = artifact(run_dir / "candidates_synthetic.json", [row])

    class Company:
        tickers = []

        def __init__(self, _):
            pass

    monkeypatch.setattr(producer, "Company", Company)
    mock_pull(monkeypatch, runtime, sample)
    output, completion = producer.run_batch(path, pull_date=sample["verdict_date"])
    outcome = json.loads(output.read_text(encoding="utf-8"))["all"][0]
    receipt = stages.read_stage_receipt(run_dir / outcome["artifact"], 1)
    assert receipt["input_identity"]["ticker"] == ""
    assert receipt["input_identity"]["cik"] == row["cik"]
    assert completion["status"] == "partial"


def test_successful_host_reports_keep_partial_data_upstream(runtime, sample, monkeypatch):
    path, request = prepared(runtime, sample, monkeypatch)
    result = response(runtime, sample, request, "success")
    output, reports, completion = producer.persist_fanout_result(request, result)
    assert len(reports) == len(sample["survivor_rows"])
    assert completion["status"] == "partial"
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [r["report_status"] for r in rows] == ["complete", "complete"]
    for report, row in zip(reports, rows):
        receipt = stages.read_stage_receipt(report, 1)
        assert receipt["input_identity"] == producer._identity(row)
        assert receipt["input"] == producer._binding(path)
        assert receipt["status"] == "partial"


@pytest.mark.parametrize("case", ["killflag_unsafe_integer", "killflag_overflow"])
def test_unsafe_report_count_preserves_valid_peer(runtime, sample, monkeypatch, case):
    _, request = prepared(runtime, sample, monkeypatch)
    output, reports, completion = producer.persist_fanout_result(
        request, response(runtime, sample, request, case))
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [row["input_index"] for row in rows] == [row["input_index"] for row in sample["survivor_rows"]]
    assert rows[0] == {**producer._identity(sample["survivor_rows"][0]),
                       "report_status": "error", "error_code": "invalid_agent_result"}
    assert rows[1]["report_status"] == "complete"
    assert rows[1]["report"] == sample["fanout_outcomes"]["success"][1]["report"]
    assert len(reports) == 1
    assert reports[0].read_text(encoding="utf-8") == rows[1]["report"]["report_md"]
    assert not (request.parent / f"report_{rows[0]['ticker']}.md").exists()
    assert completion["status"] == "partial"


def test_safe_integer_report_count_boundary_is_retained(runtime, sample, monkeypatch):
    _, request = prepared(runtime, sample, monkeypatch)
    output, reports, completion = producer.persist_fanout_result(
        request, response(runtime, sample, request, "killflag_safe_max"))
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [row["report_status"] for row in rows] == ["complete", "complete"]
    assert rows[0]["report"] == sample["fanout_outcomes"]["killflag_safe_max"][0]["report"]
    assert len(reports) == 2
    assert completion["status"] == "partial"


def test_failed_pull_cannot_be_promoted_by_a_host_report(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)

    def fail(*_):
        raise RuntimeError(sample["pull_errors"][0]["error_code"])

    monkeypatch.setattr(producer, "pull", fail)
    producer.run_batch(path, pull_date=sample["verdict_date"])
    request = producer.prepare_fanout_request(path, sample["verdict_date"])
    with pytest.raises(ValueError, match="Failed data pull"):
        producer.persist_fanout_result(request, response(runtime, sample, request, "success"))
    assert not list(request.parent.glob("report_*.md"))


@pytest.mark.parametrize("case", ["error", "missing", "empty"])
def test_failed_or_missing_host_results_remain_per_input_outcomes(runtime, sample, monkeypatch, case):
    _, request = prepared(runtime, sample, monkeypatch)
    output, reports, completion = producer.persist_fanout_result(
        request, response(runtime, sample, request, case))
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert [r["input_index"] for r in rows] == [r["input_index"] for r in sample["survivor_rows"]]
    assert any(r["report_status"] == "error" for r in rows)
    assert len(reports) < len(rows)
    assert completion["status"] == "partial"


@pytest.mark.parametrize("case", [
    "duplicate", "mismatched_identity", "mismatched_original_index", "mismatched_report_ticker",
])
def test_invalid_host_result_rejects_entire_batch_before_reports(runtime, sample, monkeypatch, case):
    _, request = prepared(runtime, sample, monkeypatch)
    with pytest.raises(ValueError):
        producer.persist_fanout_result(request, response(runtime, sample, request, case))
    assert not list(request.parent.glob("report_*.md"))
    assert not (request.parent / "deepdive_fanout_results.json").exists()


def test_empty_host_cohort_can_complete_without_provider(runtime, sample):
    path = survivors(runtime, sample, empty=True)
    producer.run_batch(path, pull_date=sample["verdict_date"])
    request = producer.prepare_fanout_request(path, sample["verdict_date"])
    output, reports, completion = producer.persist_fanout_result(
        request, response(runtime, sample, request, "empty"))
    assert json.loads(output.read_text(encoding="utf-8"))["all"] == []
    assert reports == [] and completion["status"] == "complete"
    assert runtime[1]["init"] == 0


@pytest.mark.parametrize("field", ["request_id", "input"])
def test_foreign_result_binding_fails_before_reports(runtime, sample, monkeypatch, field):
    _, request = prepared(runtime, sample, monkeypatch)
    result = response(runtime, sample, request, "success")
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload[field] = None
    result.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="bound"):
        producer.persist_fanout_result(request, result)
    assert not list(request.parent.glob("report_*.md"))


def test_changed_data_bytes_invalidate_prepared_request(runtime, sample, monkeypatch):
    _, request = prepared(runtime, sample, monkeypatch)
    result = response(runtime, sample, request, "success")
    payload = json.loads(request.read_text(encoding="utf-8"))
    data = Path(payload["candidates"][0]["json_path"])
    data.write_text(data.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        producer.persist_fanout_result(request, result)
    assert not list(request.parent.glob("report_*.md"))


@pytest.mark.parametrize("change", ["missing_block", "duplicate_block", "date", "rating", "eligibility", "mos"])
def test_unfinished_or_conflicting_report_contract_is_rejected(runtime, sample, monkeypatch, change):
    _, request = prepared(runtime, sample, monkeypatch)
    result = response(runtime, sample, request, "success")
    payload = json.loads(result.read_text(encoding="utf-8"))
    report = payload["all"][1]["report"]
    text = report["report_md"]
    if change == "missing_block":
        report["report_md"] = report["one_liner"]
    elif change == "duplicate_block":
        report["report_md"] = text + text
    elif change == "date":
        report["report_md"] = text.replace(sample["verdict_date"], "2001-01-02")
    elif change == "rating":
        report["rating"] = "买入"
    elif change == "eligibility":
        report["report_md"] = text.replace("buy_eligible: false", "buy_eligible: TBD")
    else:
        report["report_md"] = re.sub(r"(?m)^mos_pct: .*", "mos_pct: TBD", text)
    result.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        producer.persist_fanout_result(request, result)
    assert not list(request.parent.glob("report_*.md"))


def test_existing_report_is_preserved_before_any_new_report(runtime, sample, monkeypatch):
    _, request = prepared(runtime, sample, monkeypatch)
    result = response(runtime, sample, request, "success")
    old = request.parent / f"report_{sample['survivor_rows'][1]['ticker']}.md"
    original = sample["fanout_outcomes"]["success"][1]["report"]["report_md"]
    old.write_text(original, encoding="utf-8")
    with pytest.raises(FileExistsError):
        producer.persist_fanout_result(request, result)
    assert old.read_text(encoding="utf-8") == original
    assert len(list(request.parent.glob("report_*.md"))) == 1


def test_batch_cli_returns_nonzero_for_partial_data(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)
    monkeypatch.setattr(sys, "argv", ["deepdive_data.py", "--candidates", str(path)])
    assert producer.main() == 2


def test_batch_cli_returns_zero_only_for_complete_empty(runtime, sample, monkeypatch):
    path = survivors(runtime, sample, empty=True)
    monkeypatch.setattr(sys, "argv", ["deepdive_data.py", "--candidates", str(path)])
    assert producer.main() == 0
    assert runtime[1]["init"] == 0


def test_generated_error_writer_selftest_is_isolated(runtime):
    producer._selftest_error_artifact()
    assert not list(runtime[0].iterdir())
    assert runtime[1]["init"] == 0


def test_workflow_valuation_adapter_preserves_bound_source_bytes(runtime, sample, monkeypatch):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)
    producer.run_batch(path, pull_date=sample["verdict_date"])
    request = producer.prepare_fanout_request(path, sample["verdict_date"])
    envelope = json.loads(request.read_text(encoding="utf-8"))
    row = envelope["candidates"][0]
    source = Path(row["json_path"])
    before = (source.read_bytes(), stages.stage_receipt_path(source).read_bytes(), request.read_bytes())
    valuation = configure_valuation(monkeypatch)
    monkeypatch.setattr(valuation, "_get_market_cap",
                        lambda *_: (sample["candidates"][0]["mktcap"], "synthetic_fixture"))
    output, completion = producer.prepare_valuation_artifact(request, row["input_index"])
    assert_successful_valuation(output, completion, row)
    assert output != source
    assert (source.read_bytes(), stages.stage_receipt_path(source).read_bytes(), request.read_bytes()) == before
    block = json.loads(output.read_text(encoding="utf-8"))
    assert "valuation" not in json.loads(source.read_text(encoding="utf-8"))
    assert block["ticker"] == row["ticker"] and "mos_basis" in block
    receipt = stages.read_stage_receipt(output, 1)
    assert receipt["input"] == producer._binding(source)
    assert receipt["input_identity"] == producer._identity(row)
    assert receipt["request_id"] == envelope["request_id"]
    assert completion["status"] == "partial"


@pytest.mark.parametrize("mode", ["missing", "invalid_receipt", "failed"])
def test_valuation_failure_keeps_valid_peer_report(runtime, sample, monkeypatch, mode):
    path = survivors(runtime, sample)
    mock_pull(monkeypatch, runtime, sample)
    producer.run_batch(path, pull_date=sample["verdict_date"])
    request = producer.prepare_fanout_request(path, sample["verdict_date"])
    envelope = json.loads(request.read_text(encoding="utf-8"))
    valuation = configure_valuation(monkeypatch)

    def cap(ticker, _):
        if mode == "failed" and ticker == sample["survivor_rows"][0]["ticker"]:
            return None, "synthetic_unavailable"
        return sample["candidates"][0]["mktcap"], "synthetic_fixture"

    monkeypatch.setattr(valuation, "_get_market_cap", cap)
    for position, row in enumerate(envelope["candidates"]):
        if position == 0 and mode == "missing":
            continue
        output, valuation_completion = producer.prepare_valuation_artifact(request, row["input_index"])
        if position == 0 and mode == "failed":
            assert json.loads(output.read_text(encoding="utf-8"))["status"] == "ERROR"
            assert "valuation_failed" in valuation_completion["reasons"]
        else:
            assert_successful_valuation(output, valuation_completion, row)
        if position == 0 and mode == "invalid_receipt":
            receipt_path = stages.stage_receipt_path(output)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["request_id"] = None
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    output, reports, completion = producer.persist_fanout_result(
        request, response(runtime, sample, request, "success"))
    rows = json.loads(output.read_text(encoding="utf-8"))["all"]
    assert rows[0]["report_status"] == "error"
    assert rows[1]["report_status"] == "complete"
    assert len(reports) == 1 and completion["status"] == "partial"
    receipt = stages.read_stage_receipt(reports[0], 1)
    assert receipt["valuation_artifact"] == producer._binding(Path(envelope["candidates"][1]["valuation_path"]))


def test_valuation_cannot_rewrite_prior_output(runtime, sample, monkeypatch):
    _, request = prepared(runtime, sample, monkeypatch)
    envelope = json.loads(request.read_text(encoding="utf-8"))
    row = envelope["candidates"][0]
    output = Path(row["valuation_path"])
    before = (output.read_bytes(), stages.stage_receipt_path(output).read_bytes())
    with pytest.raises(FileExistsError):
        producer.prepare_valuation_artifact(request, row["input_index"])
    assert (output.read_bytes(), stages.stage_receipt_path(output).read_bytes()) == before
