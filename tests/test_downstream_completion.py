"""Downstream stage evidence distinguishes empty, rejected, missing and completed work."""
import copy
import csv
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import _recall as recall
import filter_by_sic as stages
import finalize_run as finalizer
import run_theme as run_theme
from make_fixtures import downstream_completion_scenarios


@pytest.fixture
def sample():
    return downstream_completion_scenarios()


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    def synthetic_output(path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    monkeypatch.setattr(stages, "prepare_output", synthetic_output)
    monkeypatch.setattr(finalizer, "prove_output_path", synthetic_output)
    monkeypatch.setattr(finalizer, "REPORTS", tmp_path)
    monkeypatch.setattr(run_theme, "REPORTS", tmp_path)
    return tmp_path


def artifact(path, rows, *, complete=True, identity=None, binding=None):
    path.write_text(json.dumps(rows), encoding="utf-8")
    count = len(rows) if isinstance(rows, list) else 1
    completion = stages.stage_completion("synthetic_input", count,
        work=[stages.stage_work("synthetic_observation", status="complete" if complete else "unavailable")])
    if identity is not None:
        completion["input_identity"] = identity
    if binding is not None:
        completion["input"] = binding
    stages.write_stage_receipt(path, completion)
    return path


def gate(run_dir, sample, outcomes=None, *, candidates=None, complete=True):
    rows = copy.deepcopy(sample["candidates"] if candidates is None else candidates)
    source = artifact(run_dir / "candidates_synthetic.json", rows, complete=complete)
    request_path = run_theme.prepare_gate2_request(source)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response = {"schema": "smallcap.gate2.result.v1", "input": request["input"],
                "all": copy.deepcopy(sample["judgments"] if outcomes is None else outcomes)}
    response_path = run_dir / "workflow_result.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    return source, request_path, response_path


def invoke_finalizer(run_dir, monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["finalize_run.py", "--input", str(run_dir), "--no-rank", *extra])
    return finalizer.main()


def test_gate2_error_and_explicit_rejection_have_different_outcomes(run_dir, sample):
    outcomes = [sample["errors"][0], sample["judgments"][1]]
    _, request, response = gate(run_dir, sample, outcomes)
    out, survivors, completion = run_theme.persist_gate2_result(request, response)
    records, receipt = run_theme.read_gate2_results(run_dir)
    assert receipt["status"] == completion["status"] == "partial"
    assert records[0]["judgment_status"] == "error"
    assert json.loads(survivors.read_text(encoding="utf-8")) == []
    assert finalizer.gate2_misrecall_tickers(run_dir) == {sample["candidates"][1]["ticker"]}
    assert finalizer.assert_reports_complete(run_dir)[1] == {sample["candidates"][0]["ticker"]}
    assert stages.read_stage_receipt(out, len(records))["status"] == "partial"


def test_missing_result_retains_requested_identity(run_dir, sample):
    _, request, response = gate(run_dir, sample, [])
    _, _, completion = run_theme.persist_gate2_result(request, response)
    records, _ = run_theme.read_gate2_results(run_dir)
    assert completion["status"] != "complete"
    assert [r["input_index"] for r in records] == list(range(len(sample["candidates"])))
    assert all(r["error_code"] == "missing_result" for r in records)
    assert finalizer.gate2_misrecall_tickers(run_dir) == set()


@pytest.mark.parametrize("field", ["ticker", "cik", "band", "input_index"])
def test_rebound_result_is_rejected_before_artifact_writes(run_dir, sample, field):
    outcomes = copy.deepcopy(sample["judgments"])
    outcomes[0][field] = outcomes[1][field]
    _, request, response = gate(run_dir, sample, outcomes)
    with pytest.raises(ValueError):
        run_theme.persist_gate2_result(request, response)
    assert not (run_dir / "gate2_results.json").exists()
    assert not (run_dir / "candidates_gate2_survivors.json").exists()


def test_duplicate_result_index_is_not_coverage(run_dir, sample):
    outcomes = [sample["judgments"][0], sample["judgments"][0]]
    _, request, response = gate(run_dir, sample, outcomes)
    with pytest.raises(ValueError, match="duplicated"):
        run_theme.persist_gate2_result(request, response)


def test_modified_candidate_bytes_invalidate_prepared_request(run_dir, sample):
    source, request, response = gate(run_dir, sample)
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bytes"):
        run_theme.persist_gate2_result(request, response)


def test_run_directory_binding_prevents_copied_request_reuse(run_dir, sample):
    source, request, response = gate(run_dir, sample)
    request_data = json.loads(request.read_text(encoding="utf-8"))
    request_data["input"]["run_dir"] = str(run_dir / "another-run")
    request.write_text(json.dumps(request_data), encoding="utf-8")
    with pytest.raises(ValueError, match="directory"):
        run_theme.persist_gate2_result(request, response)
    assert source.exists()


def test_result_cannot_change_financial_candidate_fields(run_dir, sample):
    outcomes = copy.deepcopy(sample["judgments"])
    outcomes[0]["health_score"] = -1
    outcomes[0]["mktcap"] = -1
    _, request, response = gate(run_dir, sample, outcomes)
    run_theme.persist_gate2_result(request, response)
    rows, _ = run_theme.read_gate2_results(run_dir)
    for key in ("health_score", "mktcap"):
        assert rows[0].get(key) == sample["candidates"][0].get(key)
    assert [r["band"] for r in rows] == [r["band"] for r in sample["candidates"]]


@pytest.mark.parametrize("complete", [False, True])
def test_zero_candidate_gate_preserves_upstream_completion(run_dir, sample, complete):
    _, request, response = gate(run_dir, sample, [], candidates=[], complete=complete)
    _, survivors, completion = run_theme.persist_gate2_result(request, response)
    assert (completion["status"] == "complete") is complete
    assert completion["requested_work"] == 0
    assert json.loads(survivors.read_text(encoding="utf-8")) == []


def test_unknown_band_never_becomes_deep_or_complete(run_dir, sample):
    candidates = copy.deepcopy(sample["candidates"])
    outcomes = copy.deepcopy(sample["judgments"])
    candidates[0]["band"] = outcomes[0]["band"] = sample["unknown_band"]
    _, request, response = gate(run_dir, sample, outcomes, candidates=candidates)
    run_theme.persist_gate2_result(request, response)
    rows, completion = run_theme.read_gate2_results(run_dir)
    assert rows[0]["band"] == sample["unknown_band"]
    assert completion["status"] == "partial"


def test_existing_gate2_pair_is_immutable(run_dir, sample):
    _, request, response = gate(run_dir, sample)
    out, _, _ = run_theme.persist_gate2_result(request, response)
    before = (out.read_bytes(), stages.stage_receipt_path(out).read_bytes())
    with pytest.raises(FileExistsError):
        run_theme.persist_gate2_result(request, response)
    assert (out.read_bytes(), stages.stage_receipt_path(out).read_bytes()) == before


def test_candidate_discovery_excludes_stage_receipts_and_survivor_file(run_dir, sample):
    _, request, response = gate(run_dir, sample)
    run_theme.persist_gate2_result(request, response)
    assert [p.name for p in finalizer.candidate_artifacts(run_dir)] == ["candidates_synthetic.json"]
    assert finalizer.deep_band_tickers(run_dir) == {sample["candidates"][0]["ticker"]}


def test_survivor_complement_is_not_a_rejection(run_dir, sample):
    artifact(run_dir / "candidates_synthetic.json", sample["candidates"])
    artifact(run_dir / "candidates_gate2_survivors.json", [])
    assert finalizer.gate2_misrecall_tickers(run_dir) == set()
    deep, missing = finalizer.assert_reports_complete(run_dir)
    assert missing == deep == {sample["candidates"][0]["ticker"]}
    assert finalizer.finalization_inputs(run_dir, deep, missing)["status"] == "partial"


@pytest.mark.parametrize("allow_missing", [False, True])
def test_allow_missing_never_returns_complete(run_dir, sample, monkeypatch, allow_missing):
    _, request, response = gate(run_dir, sample)
    run_theme.persist_gate2_result(request, response)
    args = ["--allow-missing"] if allow_missing else []
    assert invoke_finalizer(run_dir, monkeypatch, *args) == 2
    summary = json.loads((run_dir / "finalization.json").read_text(encoding="utf-8"))
    assert summary["status"] == "partial"
    assert summary["missing_reports"] == [sample["candidates"][0]["ticker"]]


def test_complete_empty_run_can_finalize(run_dir, monkeypatch):
    artifact(run_dir / "candidates_synthetic.json", [])
    assert invoke_finalizer(run_dir, monkeypatch) == 0
    assert json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8")) == []
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "complete"


def test_all_explicit_misrecalls_can_finalize(run_dir, sample, monkeypatch):
    outcomes = copy.deepcopy(sample["judgments"])
    for row in outcomes:
        row["theme_fit"] = "misrecall"
    _, request, response = gate(run_dir, sample, outcomes)
    run_theme.persist_gate2_result(request, response)
    assert invoke_finalizer(run_dir, monkeypatch) == 0


def test_rejected_stale_report_is_preserved_but_not_emitted(run_dir, sample, monkeypatch):
    outcomes = copy.deepcopy(sample["judgments"])
    for row in outcomes:
        row["theme_fit"] = "misrecall"
    _, request, response = gate(run_dir, sample, outcomes)
    run_theme.persist_gate2_result(request, response)
    report = run_dir / f"report_{sample['candidates'][0]['ticker']}.md"
    report.write_text(sample["selftest"]["parse_cases"]["missing"], encoding="utf-8")
    original = report.read_bytes()
    assert invoke_finalizer(run_dir, monkeypatch) == 0
    assert json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8")) == []
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "complete"
    assert report.read_bytes() == original


@pytest.mark.parametrize("with_receipt", [False, True])
def test_report_requires_bound_deepdive_completion(run_dir, sample, monkeypatch, with_receipt):
    _, request, response = gate(run_dir, sample)
    _, survivors, _ = run_theme.persist_gate2_result(request, response)
    candidate = sample["candidates"][0]
    ticker = candidate["ticker"]
    (run_dir / f"report_{ticker}.md").write_text(sample["report_text"], encoding="utf-8")
    data_path = run_dir / f"deepdive_{ticker}_{sample['asof']}.json"
    data = {"cik": candidate["cik"], "killflag_count": 0}
    if with_receipt:
        identity = {"input_index": 0, **{key: candidate[key] for key in ("ticker", "cik", "band")}}
        artifact(data_path, data, identity=identity, binding=run_theme._artifact_binding(survivors))
    else:
        data_path.write_text(json.dumps(data), encoding="utf-8")
    assert invoke_finalizer(run_dir, monkeypatch) == (0 if with_receipt else 2)


@pytest.mark.parametrize("band", ["watch", "unknown"])
def test_non_deep_stale_report_is_excluded_from_finalized_count(run_dir, sample, monkeypatch, band):
    candidates = copy.deepcopy(sample["candidates"])
    outcomes = copy.deepcopy(sample["judgments"])
    candidates[0]["band"] = outcomes[0]["band"] = band
    _, request, response = gate(run_dir, sample, outcomes, candidates=candidates)
    run_theme.persist_gate2_result(request, response)
    report = run_dir / f"report_{candidates[0]['ticker']}.md"
    report.write_text(sample["selftest"]["parse_cases"]["missing"], encoding="utf-8")
    assert finalizer.eligible_report_tickers(run_dir) == set()
    assert invoke_finalizer(run_dir, monkeypatch) == (0 if band == "watch" else 2)
    assert json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8")) == []
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] != "invalid"


def test_deep_gate_error_with_old_report_matches_partial_ranking_scope(run_dir, sample, monkeypatch):
    _, request, response = gate(run_dir, sample, [sample["errors"][0], sample["judgments"][1]])
    run_theme.persist_gate2_result(request, response)
    ticker = sample["candidates"][0]["ticker"]
    (run_dir / f"report_{ticker}.md").write_text(sample["report_text"], encoding="utf-8")
    assert finalizer.eligible_report_tickers(run_dir) == {ticker}
    assert invoke_finalizer(run_dir, monkeypatch) == 2
    assert stages.read_stage_receipt(run_dir / "deepdive_verdicts.json", 1)["status"] == "partial"


def test_unbound_stale_report_does_not_fill_missing_bound_report(run_dir, sample, monkeypatch):
    _, request, response = gate(run_dir, sample, sample["judgments"][:1], candidates=sample["candidates"][:1])
    run_theme.persist_gate2_result(request, response)
    unbound = sample["candidates"][1]["ticker"]
    (run_dir / f"report_{unbound}.md").write_text(sample["selftest"]["parse_cases"]["missing"], encoding="utf-8")
    assert finalizer.eligible_report_tickers(run_dir) == set()
    assert invoke_finalizer(run_dir, monkeypatch, "--allow-missing") == 2
    assert json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8")) == []
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "partial"


def test_existing_ranking_and_receipt_are_preserved(run_dir):
    ranking = run_dir / "RANKING.md"
    artifact(ranking, [])
    before = (ranking.read_bytes(), stages.stage_receipt_path(ranking).read_bytes())
    selected = finalizer._ranking_output(run_dir)
    assert selected.name == "RANKING.finalized-1.md"
    assert (ranking.read_bytes(), stages.stage_receipt_path(ranking).read_bytes()) == before


def test_complete_watch_candidates_without_gate2_exclude_old_reports(run_dir, sample, monkeypatch):
    candidate = sample["candidates"][1]
    artifact(run_dir / "candidates_synthetic.json", [candidate])
    (run_dir / f"report_{candidate['ticker']}.md").write_text(sample["selftest"]["parse_cases"]["missing"], encoding="utf-8")
    assert finalizer.eligible_report_tickers(run_dir) == set()
    assert invoke_finalizer(run_dir, monkeypatch) == 2
    assert json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8")) == []
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "partial"


def test_complete_empty_candidates_exclude_unbound_old_report(run_dir, sample, monkeypatch):
    artifact(run_dir / "candidates_synthetic.json", [])
    report = run_dir / f"report_{sample['candidates'][0]['ticker']}.md"
    report.write_text(sample["selftest"]["parse_cases"]["missing"], encoding="utf-8")
    before = report.read_bytes()
    assert finalizer.eligible_report_tickers(run_dir) == set()
    assert invoke_finalizer(run_dir, monkeypatch) == 0
    assert json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8")) == []
    assert report.read_bytes() == before


@pytest.mark.parametrize("with_receipt", [False, True])
def test_empty_candidate_recall_requires_completion_evidence(run_dir, with_receipt):
    path = run_dir / "candidates_synthetic.json"
    if with_receipt:
        artifact(path, [])
    else:
        path.write_text("[]", encoding="utf-8")
    result = recall._recall_set_from_candidate_files([path])
    recalled, count, sets = result
    assert recalled == set() and count == 0 and not any(sets.values())
    assert (result.completion["status"] == "complete") is with_receipt


def test_invalid_receipt_does_not_contribute_recalled_members(run_dir, sample):
    path = artifact(run_dir / "candidates_synthetic.json", sample["candidates"])
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = recall._recall_set_from_candidate_files([path])
    assert result.completion["status"] == "invalid"
    assert result[0] == set()


@pytest.mark.parametrize("kind", ["candidate", "universe"])
def test_unreadable_recall_source_remains_unavailable(run_dir, kind):
    reader = (recall._recall_set_from_candidate_files if kind == "candidate"
              else recall._recall_set_from_universe_files)
    result = reader([run_dir / "missing-input"])
    assert result.completion["status"] == "invalid"
    assert result[0] == set()


def test_unknown_universe_flag_is_not_a_recorded_rejection(run_dir, sample):
    path = run_dir / "universe_synthetic.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["ticker", "smallcap_candidate"])
        writer.writeheader()
        writer.writerow({"ticker": sample["candidates"][0]["ticker"], "smallcap_candidate": sample["invalid_boolean"]})
    result = recall._recall_set_from_universe_files([path])
    assert result.completion["status"] == "invalid"
    assert result[2]["mktcap_dropped"] == set()


def test_partial_recall_preserves_ratio_and_marks_missingness_unknown(sample):
    tickers = [row["ticker"] for row in sample["candidates"]]
    complete = stages.stage_completion("synthetic", 1, work=[stages.stage_work("synthetic")])
    partial = stages.stage_completion("synthetic", 1, reasons=["missing_receipt"])
    kwargs = {"mapping": {"synthetic": tickers}, "fts_tickers": tickers}
    known = recall.recall_at_gold("synthetic", tickers[:1], completion=complete, **kwargs)
    unknown = recall.recall_at_gold("synthetic", tickers[:1], completion=partial, **kwargs)
    for key in ("gold", "recall_at_gold", "discovery_recall_at_gold", "stage_breakdown", "discovery_channels"):
        assert known[key] == unknown[key]
    assert known["unknown_missing_gold"] == []
    assert unknown["unknown_missing_gold"] == tickers[1:]
    assert unknown["coverage_complete"] is False


def csv_artifact(path, fields, rows, *, input_path=None, decisions=None):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    completion = stages.stage_completion("synthetic_csv", len(rows),
                                        work=[stages.stage_work("synthetic_observation")])
    if input_path is not None:
        completion["input_artifact"] = str(input_path.resolve())
        completion["decisions"] = decisions or []
    stages.write_stage_receipt(path, completion)
    return path


@pytest.mark.parametrize("all_rejected", [False, True])
def test_sic_filter_distinguishes_complete_empty_and_complete_rejected(run_dir, sample, monkeypatch, all_rejected):
    monkeypatch.setattr(run_theme, "CFG", {"sic_hard_exclude": []})
    candidates = sample["candidates"] if all_rejected else []
    universe_rows = [{key: row.get(key) for key in ("ticker", "cik", "sic", "mktcap", "band")}
                     for row in candidates]
    universe = csv_artifact(run_dir / "universe_synthetic.csv",
                            ["ticker", "cik", "sic", "mktcap", "band"], universe_rows)
    decisions = [{"input_index": index, **{key: row[key] for key in ("ticker", "cik", "band")},
                  "screening_decision": "rejected_existing_policy"}
                 for index, row in enumerate(candidates)]
    cheap = csv_artifact(run_dir / "cheappass_synthetic.csv", ["ticker", "rejected"],
                         [{"ticker": row["ticker"], "rejected": True} for row in candidates],
                         input_path=universe, decisions=decisions)
    output = run_theme.stage_sic_filter(cheap, universe, "synthetic")
    assert json.loads(output.read_text(encoding="utf-8")) == []
    assert stages.read_stage_receipt(output, 0)["status"] == "complete"


def test_sic_filter_rejects_unknown_boolean_before_output(run_dir, sample, monkeypatch):
    monkeypatch.setattr(run_theme, "CFG", {"sic_hard_exclude": []})
    row = sample["candidates"][0]
    universe = csv_artifact(run_dir / "universe_synthetic.csv",
                            ["ticker", "cik", "sic", "mktcap", "band"],
                            [{key: row.get(key) for key in ("ticker", "cik", "sic", "mktcap", "band")}])
    cheap = csv_artifact(run_dir / "cheappass_synthetic.csv", ["ticker", "rejected"],
                         [{"ticker": row["ticker"], "rejected": sample["invalid_boolean"]}], input_path=universe)
    with pytest.raises(ValueError, match="boolean"):
        run_theme.stage_sic_filter(cheap, universe, "synthetic")
    assert not (run_dir / "candidates_synthetic.json").exists()


def test_current_stage_never_reuses_old_output(run_dir, sample):
    path = artifact(run_dir / "universe_synthetic.json", sample["candidates"])
    before = path.read_bytes()
    with pytest.raises(FileExistsError, match="new run"):
        run_theme._fresh_output(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("no_rank", [False, True])
def test_duplicate_selected_report_identity_is_invalid_before_verdicts(run_dir, sample, monkeypatch, no_rank):
    import rank
    candidate = sample["candidates"][0]
    artifact(run_dir / "candidates_synthetic.json", [candidate])
    report = run_dir / f"report_{candidate['ticker']}.md"
    report.write_text(sample["report_text"], encoding="utf-8")
    case_variant = run_dir / f"report_{candidate['ticker'].lower()}.md"
    # Model the shared selector's two paths without requiring a case-sensitive tmp volume.
    monkeypatch.setattr(rank, "ranking_report_files", lambda _: [report, case_variant])
    monkeypatch.setattr(finalizer, "rebuild_ranking", lambda *_: pytest.fail("ranking must not run"))
    argv = ["finalize_run.py", "--input", str(run_dir)] + (["--no-rank"] if no_rank else [])
    monkeypatch.setattr(sys, "argv", argv)
    assert finalizer.main() == 2
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "invalid"
    assert not (run_dir / "deepdive_verdicts.json").exists()
    assert report.read_text(encoding="utf-8") == sample["report_text"]


@pytest.mark.parametrize("gated", [False, True])
def test_case_colliding_watch_candidates_cannot_complete_empty(run_dir, sample, monkeypatch, gated):
    rows = [copy.deepcopy(sample["candidates"][1]) for _ in range(2)]
    rows[1]["ticker"] = rows[0]["ticker"].lower()
    if gated:
        outcomes = [{**copy.deepcopy(sample["judgments"][1]), "input_index": i,
                     "ticker": row["ticker"], "cik": row["cik"], "band": row["band"],
                     "theme_fit": sample["judgments"][0]["theme_fit"]}
                    for i, row in enumerate(rows)]
        _, request, response = gate(run_dir, sample, outcomes, candidates=rows)
        run_theme.persist_gate2_result(request, response)
    else:
        artifact(run_dir / "candidates_synthetic.json", rows)
    assert invoke_finalizer(run_dir, monkeypatch) == 2
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "invalid"
    assert not (run_dir / "deepdive_verdicts.json").exists()


def test_duplicate_candidate_identity_across_artifacts_is_invalid(run_dir, sample, monkeypatch):
    row = sample["candidates"][1]
    artifact(run_dir / "candidates_synthetic_a.json", [row])
    artifact(run_dir / "candidates_synthetic_b.json", [row])
    assert invoke_finalizer(run_dir, monkeypatch) == 2
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "invalid"
    assert not (run_dir / "deepdive_verdicts.json").exists()


@pytest.mark.parametrize("ticker", ["../SYNTHA", " "])
def test_malformed_watch_identity_cannot_be_excluded_into_completion(run_dir, sample, monkeypatch, ticker):
    row = {**sample["candidates"][1], "ticker": ticker}
    artifact(run_dir / "candidates_synthetic.json", [row])
    assert invoke_finalizer(run_dir, monkeypatch) == 2
    assert stages.read_stage_receipt(run_dir / "finalization.json", 0)["status"] == "invalid"
    assert not (run_dir / "deepdive_verdicts.json").exists()


def test_lowercase_bound_report_and_data_preserve_input_spelling(run_dir, sample, monkeypatch):
    candidates = copy.deepcopy(sample["candidates"][:1])
    outcomes = copy.deepcopy(sample["judgments"][:1])
    candidates[0]["ticker"] = candidates[0]["ticker"].lower()
    outcomes[0]["ticker"] = candidates[0]["ticker"]
    _, request, response = gate(run_dir, sample, outcomes, candidates=candidates)
    _, survivors, _ = run_theme.persist_gate2_result(request, response)
    row = candidates[0]
    report = run_dir / f"report_{row['ticker']}.md"
    report.write_text(sample["report_text"], encoding="utf-8")
    data = run_dir / f"deepdive_{row['ticker']}_{sample['asof']}.json"
    identity = {"input_index": 0, **{key: row[key] for key in ("ticker", "cik", "band")}}
    artifact(data, {"cik": row["cik"], "killflag_count": 0},
             identity=identity, binding=run_theme._artifact_binding(survivors))
    assert finalizer._report_file(run_dir, row["ticker"].upper()) == report
    assert finalizer._issuer_json_files(run_dir, "deepdive", row["ticker"].upper()) == [data]
    assert invoke_finalizer(run_dir, monkeypatch) == 0
    verdicts = json.loads((run_dir / "deepdive_verdicts.json").read_text(encoding="utf-8"))
    assert verdicts[0]["ticker"] == row["ticker"].upper()
    assert verdicts[0]["cik"] == row["cik"]


def test_case_colliding_data_artifacts_are_not_arbitrarily_selected(run_dir, sample, monkeypatch):
    ticker = sample["candidates"][0]["ticker"]
    first = run_dir / f"deepdive_{ticker}_{sample['asof']}.json"
    second = run_dir / f"deepdive_{ticker.lower()}_{sample['asof']}.json"
    monkeypatch.setattr(Path, "glob", lambda *_: iter([first, second]))
    with pytest.raises(ValueError, match="duplicated"):
        finalizer._issuer_json_files(run_dir, "deepdive", ticker)


def test_missing_report_retains_rating_error_contract(run_dir, sample):
    with pytest.raises(ValueError, match="rating"):
        finalizer.build_verdict(sample["candidates"][0]["ticker"], run_dir, sample["asof"])
