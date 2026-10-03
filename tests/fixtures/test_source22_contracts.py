"""Generated source22 contract cases; every payload is synthetic."""
from copy import deepcopy
import csv
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_private_runs import state

CASE = json.loads(Path(__file__).with_name("source22_contracts.json").read_text(encoding="utf-8"))


@pytest.fixture
def modules(state, monkeypatch):
    names = ("filter_by_sic", "_event_admission", "_event_insider", "_pit_universe",
             "deepdive_data", "rank", "finalize_run")
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return {name: importlib.import_module(name) for name in names}


def completions(stages, case, source_binding):
    source = stages.stage_completion("event_spinoffs", len(case["source"]),
        work=[stages.stage_work("synthetic_event_source", status=case["source_status"])])
    cheap = stages.stage_completion("cheap_pass", len(case["screened"]),
        work=[stages.stage_work("synthetic_screening")], upstream=[source])
    cheap.update(input=source_binding, input_count=len(case["source"]),
                 decisions=deepcopy(case["decisions"]))
    return source, cheap


@pytest.mark.parametrize("case", CASE["event"], ids=lambda case: case["name"])
def test_event_source_and_screening_contract(modules, case):
    module, stages = modules["_event_admission"], modules["filter_by_sic"]
    source_binding = {"artifact": "candidates_event_synthetic.json", "run_dir": "/synthetic"}
    cheap_binding = {"artifact": "cheappass_synthetic.csv", "run_dir": "/synthetic"}
    source, cheap = completions(stages, case, source_binding)
    args = (case["source"], source, cheap, source_binding, cheap_binding, case["screened"])
    if case["error"]:
        with pytest.raises(ValueError):
            module.event_admission(*args)
    else:
        rows, receipt = module.event_admission(*args)
        assert [row["input_index"] for row in rows] == case["expected_indices"]
        assert receipt["status"] == case["expected_status"]
        assert receipt["theme_fit_required"] is False
        assert len(receipt["decisions"]) == len(case["source"])
        assert receipt["input"] == source_binding and receipt["cheap_input"] == cheap_binding


@pytest.mark.parametrize("case", CASE["html"], ids=lambda case: case["name"])
def test_event_insider_page_evidence(modules, case):
    result = modules["_event_insider"].parse_cluster_page(case["html"],
        observed_date=CASE["asof"], response_url=CASE["response_url"])
    assert result["status"] == case["status"]
    assert len(result["records"]) == case["records"]
    assert result["proof"]["scope"] == "returned_latest_cluster_buys_page"


def test_event_insider_wrong_response_route_cannot_prove_page(modules):
    result = modules["_event_insider"].parse_cluster_page(CASE["html"][0]["html"],
        observed_date=CASE["asof"], response_url="https://example.com/login")
    assert result["status"] == "unavailable" and not result["records"]


@pytest.mark.parametrize("case", CASE["pit"], ids=lambda case: case["name"])
def test_pit_symbol_requires_matching_response_identity(modules, case):
    evidence = {}
    result = modules["_pit_universe"].cik_trading_symbol_asof(
        CASE["request_cik"], CASE["asof"], evidence=evidence,
        submissions_tickers=["SYNTHFALLBACK"],
        fetch=lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: case["payload"]))
    assert result == case["expected"]
    assert evidence["pit_proven"] is case["proven"]
    if case["proven"]:
        assert evidence["filed"] == "2000-12-15"
    else:
        assert evidence["filed"] is None
        assert evidence["source"] == "current_submissions"
        assert any(row["status"] == "unavailable" for row in evidence["work"])


@pytest.mark.parametrize("case", CASE["policy"], ids=lambda case: case["name"])
def test_frozen_buy_policy_at_accepted_report_boundary(modules, case):
    report = deepcopy(case["report"])
    row = {"ticker": report["ticker"]}
    if case["accepted"]:
        assert modules["deepdive_data"]._validated_report(report, row, CASE["asof"]) == report
    else:
        with pytest.raises(ValueError):
            modules["deepdive_data"]._validated_report(report, row, CASE["asof"])


def event_files(modules, directory, case):
    directory.mkdir(parents=True, exist_ok=True)
    module, stages = modules["_event_admission"], modules["filter_by_sic"]
    source_path = directory / "candidates_event_synthetic.json"
    source_path.write_text(json.dumps(case["source"]), encoding="utf-8")
    source_binding = module.artifact_binding(source_path)
    source, cheap = completions(stages, case, source_binding)
    stages.write_stage_receipt(source_path, source)
    cheap_path = directory / "cheappass_synthetic.csv"
    with cheap_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "input_index", "ticker", "cik", "rejected", "kf_scanned", "disclosure_review_required"])
        writer.writeheader()
        writer.writerows(case["screened"])
    stages.write_stage_receipt(cheap_path, cheap)
    admitted, receipt = module.write_event_admission(source_path, cheap_path)
    return {"source": source_path, "cheap": cheap_path, "admitted": admitted}, receipt


@pytest.mark.parametrize("case_name", ["complete", "source_partial", "missing_scan", "complete_empty"])
def test_event_handoff_reaches_rank_and_finalization_without_gate2(modules, state, case_name):
    case = next(case for case in CASE["event"] if case["name"] == case_name)
    directory = Path(state["root"])
    paths, receipt = event_files(modules, directory, case)
    rows, binding, input_completion = modules["deepdive_data"]._data_input(paths["admitted"])
    assert input_completion["status"] == case["expected_status"]
    deep = [row for row in rows if row["band"] == "deep"]
    stages = modules["filter_by_sic"]
    for row in deep:
        report = deepcopy(CASE["policy"][-1]["report"])
        report["ticker"] = row["ticker"]
        (directory / ("report_" + row["ticker"] + ".md")).write_text(report["report_md"], encoding="utf-8")
        data = directory / ("deepdive_" + row["ticker"] + "_" + CASE["asof"] + ".json")
        data.write_text(json.dumps({"ticker": row["ticker"], "synthetic_handoff_only": True}), encoding="utf-8")
        completion = stages.stage_completion("deepdive_data", 1, upstream=[input_completion])
        completion.update(input=binding,
            input_identity={key: row[key] for key in ("input_index", "ticker", "cik", "band")})
        stages.write_stage_receipt(data, completion)
    rank = modules["rank"]
    inputs = rank._collect_ranking_inputs(directory)
    stats = rank.compute_funnel_stats(directory, _inputs=inputs)
    selected, required, _, _ = rank._ranking_report_selection(stats, inputs)
    assert required == {row["ticker"] for row in deep}
    assert {path.stem.removeprefix("report_") for path in selected} == required
    finalize = modules["finalize_run"]
    deep_tickers, missing = finalize.assert_reports_complete(directory)
    assert not missing
    completion = finalize.finalization_inputs(directory, deep_tickers, missing)
    assert completion["status"] == case["expected_status"]
    assert not (directory / "gate2_results.json").exists()


@pytest.mark.parametrize("target", CASE["tamper_targets"])
def test_event_handoff_rejects_changed_bound_bytes(modules, state, target):
    paths, _ = event_files(modules, Path(state["root"]), CASE["event"][0])
    path = paths[target]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        modules["_event_admission"].read_event_admission(path.parent)
