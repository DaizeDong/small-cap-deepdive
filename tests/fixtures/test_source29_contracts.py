
"""Generated Source29 regressions. All company and financial inputs are synthetic."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

from make_fixtures import source29_scenarios
from test_private_runs import state

CASE = source29_scenarios()


@pytest.fixture
def runtime(state, monkeypatch, tmp_path):
    for name in ("filter_by_sic", "run_theme", "cheap_pass", "_recall"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    stages = importlib.import_module("filter_by_sic")
    theme = importlib.import_module("run_theme")
    cheap = importlib.import_module("cheap_pass")
    recall = importlib.import_module("_recall")

    def output(path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(stages, "prepare_output", output)
    monkeypatch.setattr(theme, "REPORTS", tmp_path)
    monkeypatch.setattr(theme, "CFG", {"sic_hard_exclude": []})
    monkeypatch.setattr(cheap.time, "sleep", lambda *_: None)
    return {"theme": theme, "cheap": cheap, "recall": recall, "stages": stages,
            "directory": tmp_path}


@pytest.mark.parametrize("case", CASE["cash"], ids=lambda case: case["name"])
def test_observed_zero_cash_reaches_the_existing_burn_rejection(runtime, monkeypatch, case):
    cheap = runtime["cheap"]
    values = {"CashAndCashEquivalentsAtCarryingValue": case["cash"],
              "NetCashProvidedByUsedInOperatingActivities": case["ocf"],
              "NetIncomeLoss": CASE["net_income"], "Revenues": CASE["revenue"]}
    monkeypatch.setattr(cheap, "get_concept_series",
                        lambda _cik, concept: [] if values[concept] is None else [{"val": values[concept]}])
    monkeypatch.setattr(cheap, "killflag_scan", lambda _ticker: deepcopy(CASE["flags"]))
    observed = cheap.health_check(deepcopy(CASE["candidate"]))
    assert observed["cash"] == case["cash"]
    assert observed["runway_periods"] == case["runway"]
    scored = cheap.score(pd.DataFrame([observed])).iloc[0]
    assert bool(scored["reject_burn"]) is case["reject"]
    assert bool(scored["rejected"]) is case["reject"]


def candidate_artifact(runtime, case, cheap_shadow):
    theme, stages = runtime["theme"], runtime["stages"]
    source = deepcopy(CASE["candidate"])
    universe = {key: source[key] for key in ("ticker", "cik", "sic", "mktcap", "band")}
    if not case.get("missing"):
        universe["recall_channel"] = case["input"]
    screened = {key: source[key] for key in
                ("ticker", "name", "mktcap", "health_score", "killflag_count", "avg_dollar_vol", "business_blurb")}
    screened["rejected"] = False
    if cheap_shadow:
        screened["recall_channel"] = "fts" if case["input"] != "fts" else "sic_reverse"
    universe_path = runtime["directory"] / "synthetic-universe.csv"
    cheap_path = runtime["directory"] / "synthetic-cheap.csv"
    pd.DataFrame([universe]).to_csv(universe_path, index=False)
    pd.DataFrame([screened]).to_csv(cheap_path, index=False)
    discovery = stages.stage_completion("discover", 1, work=[stages.stage_work("synthetic_discovery")])
    stages.write_stage_receipt(universe_path, discovery)
    screening = stages.stage_completion("cheap_pass", 1, work=[stages.stage_work("synthetic_screening")],
                                         upstream=[discovery])
    screening["input_artifact"] = str(universe_path.resolve())
    screening["decisions"] = [{"input_index": 0, "ticker": source["ticker"], "cik": source["cik"],
                               "band": source["band"], "screening_decision": "retained"}]
    stages.write_stage_receipt(cheap_path, screening)
    return theme.stage_sic_filter(cheap_path, universe_path, source["theme_slug"], source["theme"])


@pytest.mark.parametrize("case", CASE["channels"], ids=lambda case: case["name"])
@pytest.mark.parametrize("cheap_shadow", [False, True], ids=["no-shadow", "conflicting-cheap-channel"])
def test_universe_channel_reaches_gate2_and_recall_accounting(runtime, case, cheap_shadow):
    theme, stages, recall = runtime["theme"], runtime["stages"], runtime["recall"]
    path = candidate_artifact(runtime, case, cheap_shadow)
    candidate, = json.loads(path.read_text(encoding="utf-8"))
    assert candidate["recall_channel"] == case["expected"]
    assert candidate["ticker"] == CASE["candidate"]["ticker"]
    request_path = theme.prepare_gate2_request(path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["candidates"][0]["recall_channel"] == case["expected"]
    judgment = {**request["candidates"][0], **CASE["judgment"]}
    response_path = runtime["directory"] / "synthetic-gate-response.json"
    response_path.write_text(json.dumps({"schema": "smallcap.gate2.result.v1",
        "input": request["input"], "all": [judgment]}), encoding="utf-8")
    output, survivors, completion = theme.persist_gate2_result(request_path, response_path)
    records, receipt = theme.read_gate2_results(runtime["directory"])
    assert receipt["status"] == completion["status"] == "complete"
    assert records[0]["recall_channel"] == case["expected"]
    assert json.loads(output.read_text(encoding="utf-8"))[0]["recall_channel"] == case["expected"]
    survivor, = json.loads(survivors.read_text(encoding="utf-8"))
    assert survivor["recall_channel"] == case["expected"]
    final, fts_count, channels = recall._recall_set_from_candidate_files([survivors])
    ticker = CASE["candidate"]["ticker"]
    assert final == {ticker}
    assert fts_count == int(case["fts"])
    assert channels["fts"] == ({ticker} if case["fts"] else set())
    assert channels["sic"] == ({ticker} if case["sic"] else set())
    assert stages.read_stage_receipt(survivors, 1)["status"] == "complete"


@pytest.mark.parametrize("case", CASE["channels"], ids=lambda case: case["name"])
def test_gate2_omission_and_missing_result_preserve_bound_provenance(runtime, case):
    theme = runtime["theme"]
    candidate = {**deepcopy(CASE["candidate"]), "recall_channel": case["expected"]}
    row = {key: candidate[key] for key in ("ticker", "cik", "band")}
    row.update(input_index=0, **CASE["judgment"])
    assert "recall_channel" not in row
    completed, = theme._gate2_rows([candidate], [row])
    missing, = theme._gate2_rows([candidate], [], allow_missing=True)
    assert completed["recall_channel"] == missing["recall_channel"] == case["expected"]
    assert missing["judgment_status"] == "error"
    assert missing["error_code"] == "missing_result"


@pytest.mark.parametrize("case", CASE["channels"], ids=lambda case: case["name"])
def test_gate2_cannot_rebind_a_discovery_channel(runtime, case):
    candidate = {**deepcopy(CASE["candidate"]), "recall_channel": case["expected"]}
    replacement = "sic_reverse" if case["expected"] == "fts" else "fts"
    row = {**candidate, "input_index": 0, **CASE["judgment"], "recall_channel": replacement}
    with pytest.raises(ValueError, match="recall channel"):
        runtime["theme"]._gate2_rows([candidate], [row])

@pytest.fixture
def historical_extractor(state, monkeypatch, tmp_path):
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "docs/backtest-2026-06/distress_features_extract.py"
    spec = importlib.util.spec_from_file_location("synthetic_distress_extractor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifact = tmp_path / "synthetic-feature-ledger.json"
    monkeypatch.setattr(module, "features_path", lambda: artifact)
    monkeypatch.setattr(module, "backtest_files", lambda: [])
    monkeypatch.setattr(module, "prepare_output", lambda path: path)
    return module, artifact


@pytest.mark.parametrize("case", CASE["resume_invalid"], ids=lambda case: case["name"])
def test_invalid_existing_feature_ledger_fails_before_write(historical_extractor, monkeypatch, case):
    module, artifact = historical_extractor
    previous = case["content"].encode("utf-8")
    artifact.write_bytes(previous)

    def unexpected(*_args, **_kwargs):
        pytest.fail("Invalid resume evidence reached a worker or output write")

    monkeypatch.setattr(module, "ThreadPoolExecutor", unexpected)
    monkeypatch.setattr(module, "write_features", unexpected)
    with pytest.raises(ValueError):
        module.main()
    assert artifact.read_bytes() == previous


def test_unreadable_existing_feature_ledger_fails_before_write(historical_extractor, monkeypatch):
    module, artifact = historical_extractor
    previous = json.dumps([CASE["resume_row"]]).encode("utf-8")
    artifact.write_bytes(previous)

    def unreadable():
        raise PermissionError("Synthetic unreadable feature artifact")

    def unexpected(*_args, **_kwargs):
        pytest.fail("Unreadable resume evidence reached a worker or output write")

    monkeypatch.setattr(module, "load_features", unreadable)
    monkeypatch.setattr(module, "ThreadPoolExecutor", unexpected)
    monkeypatch.setattr(module, "write_features", unexpected)
    with pytest.raises(PermissionError):
        module.main()
    assert artifact.read_bytes() == previous


@pytest.mark.parametrize("case", CASE["resume_valid"], ids=lambda case: case["name"])
def test_valid_or_absent_feature_ledger_retains_resume_behavior(historical_extractor, monkeypatch, case):
    module, artifact = historical_extractor
    if case["exists"]:
        artifact.write_text(json.dumps(case["rows"]), encoding="utf-8")

    class EmptyPool:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, *_args, **_kwargs):
            pytest.fail("No new rows should be fetched in this synthetic resume case")

    monkeypatch.setattr(module, "ThreadPoolExecutor", EmptyPool)
    module.main()
    assert json.loads(artifact.read_text(encoding="utf-8")) == case["rows"]
