"""Generated final-review regressions; all inputs are synthetic."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_fixtures import (source36_scenarios, source22_scenarios,
    source25_equity_basis_scenarios, source32_legacy_scenarios,
    source26_debt_fixture, source28_annual_inputs, tracking_quote_scenarios,
    downstream_producer_completion_scenarios)
from test_private_runs import state
from test_financial_evidence import valuation_module
from test_stage_completion_contract import modules, Response
from test_tracking_integrity import tracker
from test_debt_evidence import debt_module
from test_downstream_completion import run_dir, sample as downstream_sample
from test_filing_disclosures import callers

CASE = source36_scenarios()


@pytest.mark.parametrize("case", CASE["concentration"], ids=lambda case: case["name"])
def test_percentage_belongs_to_its_concentration_assertion(modules, case):
    from _deepdive_flags import _extract_concentration, _concentration_flag
    customer, program, detail = _extract_concentration(case["text"])
    assert customer == case["customer"]
    assert program == case["program"]
    assert _concentration_flag(customer, program) == _concentration_flag(
        case["customer"], case["program"])
    if case.get("ambiguous"):
        assert "ambiguous" in detail


@pytest.mark.parametrize("case", CASE["concentration"], ids=lambda case: case["name"])
def test_concentration_assertion_scope_reaches_actual_screening(modules, monkeypatch, case):
    cheap = modules["cheap_pass"]
    from _deepdive_flags import _extract_concentration, _concentration_flag
    monkeypatch.setattr(cheap, "_extract_concentration", _extract_concentration)
    monkeypatch.setattr(cheap, "_concentration_flag", _concentration_flag)
    class Filings:
        def __len__(self):
            return 1
        def latest(self, count):
            return SimpleNamespace(text=lambda: CASE["resolved_disclosures"] + " " + case["text"])
    monkeypatch.setattr(cheap, "Company", lambda ticker: SimpleNamespace(get_filings=lambda **kw: Filings()))
    monkeypatch.setattr(cheap, "get_concept_series", lambda *args: [{"val": 1000000}])
    monkeypatch.setattr(cheap.time, "sleep", lambda seconds: None)
    result = cheap.health_check({"ticker": "SYNTH", "name": "AcmeCorp", "cik": CASE["cik"]})
    assert result["kf_scanned"] is True
    assert result["top_customer_pct"] == case["customer"]
    assert result["top_program_pct"] == case["program"]
    if case.get("ambiguous"):
        assert "ambiguous" in result["concentration_detail"]
    scored = cheap.score(cheap.pd.DataFrame([result])).iloc[0]
    expected_reject = _concentration_flag(case["customer"], case["program"]) == "kill"
    assert bool(scored["reject_concentration"]) == expected_reject
    assert bool(scored["rejected"]) == expected_reject
    assert result["disclosure_review_required"] is bool(case.get("ambiguous"))
    assert bool(scored["health_score_complete"]) is not bool(case.get("ambiguous"))


@pytest.mark.parametrize("case", [case for case in CASE["concentration"]
    if case["name"].startswith(("unknown_possessive_", "customer_relation_"))], ids=lambda case: case["name"])
def test_possessive_uncertainty_reaches_deepdive_completion(callers, case):
    cheap, tenk = callers(CASE["resolved_disclosures"] + " " + case["text"])
    ambiguous = bool(case.get("ambiguous"))
    assert all(item["flag"] is not None for item in tenk["disclosure_evidence"].values())
    assert cheap["disclosure_review_required"] is ambiguous
    assert tenk["disclosure_review_required"] is ambiguous
    data = downstream_producer_completion_scenarios()["pull_data"]
    data["tenk"] = tenk
    deep = importlib.import_module("deepdive_data")
    stages = importlib.import_module("filter_by_sic")
    upstream = stages.stage_completion("synthetic_source", 1, work=[stages.stage_work("synthetic_observation")])
    data["source_observations"] = {
        "financials": stages.stage_completion("sec_financial_observations", 1, upstream=[upstream]),
        "sic": stages.stage_completion("sec_submissions_sic", 1, upstream=[upstream]),
    }
    completion = deep._data_completion(data, {}, {}, upstream)
    assert ("concentration_ambiguous" in completion["reasons"]) is ambiguous
    assert (completion["status"] == "complete") is not ambiguous


@pytest.mark.parametrize("identity,expected", [
    ("Synthetic Analyst user1@example.com", "fail"),
    ("Synthetic Analyst USER1@EXAMPLE.COM", "fail"),
    ("Synthetic Analyst your-email@example.com", "fail"),
    ("", "fail"), ("Synthetic Analyst", "fail"),
    ("Synthetic Analyst user1@example-employer.com", "pass")])
def test_configuration_doctor_does_not_accept_example_identity(state, monkeypatch, capsys, identity, expected):
    config_path = Path(state["companion"]) / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sec_user_agent"] = identity
    config_path.write_text(json.dumps(config), encoding="utf-8")
    before = config_path.read_bytes()
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "100.0.0")
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("synthetic_identity_doctor", root / "scripts/verify_config.py")
    doctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doctor)
    assert doctor.main(["--json"]) == (0 if expected == "pass" else 1)
    output = capsys.readouterr().out
    report = json.loads(output)
    item = next(row for row in report["checks"] if row["name"] == "SEC identity configured")
    assert item["status"] == expected
    assert report["live_services_checked"] is False
    if identity:
        assert identity not in output
    assert config_path.read_bytes() == before and not Path(state["root"]).exists()


def _bound_decision_run(run_dir, sample, *, rating="BUY", confidence=80, eligible=True, valuation_eligible=True):
    from test_downstream_completion import gate, artifact, run_theme
    _, request, response = gate(run_dir, sample)
    _, survivors, _ = run_theme.persist_gate2_result(request, response)
    candidate = sample["candidates"][0]
    ticker = candidate["ticker"]
    report = ("```rating\nrating: " + rating + "\nconfidence: " + str(confidence)
              + "\nverdict_date: 2026-01-15\nmos_basis: fcf_cap\nmos_pct: 20\nbuy_eligible: "
              + json.dumps(eligible) + "\nkillflag_count: 0\n```\n")
    (run_dir / ("report_" + ticker + ".md")).write_text(report, encoding="utf-8")
    identity = {"input_index": 0, **{key: candidate[key] for key in ("ticker", "cik", "band")}}
    artifact(run_dir / ("deepdive_" + ticker + "_" + sample["asof"] + ".json"),
             {"cik": candidate["cik"], "killflag_count": 0,
              "valuation": {"buy_eligible": valuation_eligible}},
             identity=identity, binding=run_theme._artifact_binding(survivors))
    return ticker


@pytest.mark.parametrize("eligible,valuation_eligible", [(False, True), (None, True), (True, False), (True, True)])
def test_finalization_cannot_complete_a_buy_that_fails_eligibility(run_dir, downstream_sample, monkeypatch,
                                                                eligible, valuation_eligible):
    from test_downstream_completion import invoke_finalizer, stages
    _bound_decision_run(run_dir, downstream_sample, eligible=eligible, valuation_eligible=valuation_eligible)
    if eligible is True and valuation_eligible is True:
        assert invoke_finalizer(run_dir, monkeypatch) == 0
        assert stages.read_stage_receipt(run_dir / "finalization.json", 1)["status"] == "complete"
    else:
        with pytest.raises(ValueError, match="BUY|eligib"):
            invoke_finalizer(run_dir, monkeypatch)
        assert not (run_dir / "deepdive_verdicts.json").exists()
        assert not (run_dir / "finalization.json").exists()


@pytest.mark.parametrize("rating", ["BUY", "AVOID"])
@pytest.mark.parametrize("percent", [0, 1, 2, 80, 100])
def test_report_percent_confidence_survives_finalizer_and_tracker(run_dir, downstream_sample, tracker,
                                                                monkeypatch, rating, percent):
    from test_downstream_completion import finalizer
    ticker = _bound_decision_run(run_dir, downstream_sample, rating=rating, confidence=percent)
    verdict = finalizer.build_verdict(ticker, run_dir, None)
    assert verdict["confidence"] == percent and verdict["confidence_unit"] == "percent"
    path = run_dir / "synthetic-verdicts.json"
    path.write_text(json.dumps([verdict]), encoding="utf-8")
    monkeypatch.setattr(tracker, "_fetch_close", lambda *args, **kwargs: 10.0)
    row, = tracker._build_verdicts_from_json(path)
    expected = percent / 100 if rating == "BUY" else 1 - percent / 100
    assert row["implied_prob"] == pytest.approx(min(0.999, max(0.001, expected)))
    assert row["confidence"] == percent / 100


@pytest.mark.parametrize("unit,value", [("unknown", 80), ("fraction", 2), ("percent", True)])
def test_invalid_confidence_units_fail_before_quote_lookup(tracker, tmp_path, monkeypatch, unit, value):
    path = tmp_path / "synthetic-unit-verdicts.json"
    path.write_text(json.dumps([{"ticker": "SYNTA", "rating": "BUY", "confidence": value,
                                "confidence_unit": unit}]), encoding="utf-8")
    def no_quote(*args, **kwargs):
        pytest.fail("invalid units must fail before quotes")
    monkeypatch.setattr(tracker, "_fetch_close", no_quote)
    with pytest.raises(ValueError):
        tracker._build_verdicts_from_json(path)


@pytest.mark.parametrize("status,expected", [(404, "complete"), (200, "complete"), (429, "partial"), (503, "partial")])
def test_absent_optional_concept_preserves_observation_completion(debt_module, monkeypatch, status, expected):
    import filter_by_sic as stages
    concepts = debt_module._dc
    annual = {"start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-01",
              "val": 100000000, "form": "10-K", "fp": "FY", "fy": 2024}
    payloads = iter([(200, {"cik": 9900001, "taxonomy": "us-gaap", "tag": "Revenues", "units": {"USD": [annual]}}),
                     (status, {"cik": 9900001, "taxonomy": "ifrs-full", "tag": "Revenue", "units": {"USD": []}})])
    def fetch(*args, **kwargs):
        code, payload = next(payloads)
        return SimpleNamespace(status_code=code, json=lambda: deepcopy(payload))
    monkeypatch.setattr(concepts, "http_get", fetch)
    with concepts.concept_observations() as observation:
        rows = concepts.concept_series_with_ifrs("9900001", ["Revenues"], ["Revenue"])
    assert rows[-1]["val"] == 100000000 and rows.completion["status"] == expected
    financials = observation.completion(1)
    assert financials["status"] == expected
    complete = stages.stage_completion("synthetic", 1, work=[stages.stage_work("synthetic")])
    data = {"financials": {name: [{"end": "2024-12-31", "val": 1}] for name in
            ("revenue", "net_income", "ocf", "cash", "shares_outstanding", "assets", "equity", "total_debt",
             "ebit", "dep_amort", "capex", "goodwill", "intangibles", "liabilities")},
            "derived": {}, "tenk": {"available": True}, "insider": {"available": True},
            "source_observations": {"financials": financials, "sic":
                stages.stage_completion("sec_submissions_sic", 1, work=[stages.stage_work("synthetic")])}}
    assert debt_module._data_completion(data, {}, {}, complete)["status"] == expected


@pytest.mark.parametrize("response_cik,expected", [("9900001", True), (9900001, True), ("0009900001", True),
                                                  ("9900002", False), (None, False), (True, False)])
def test_pit_submissions_must_prove_requested_issuer_before_attribution(modules, response_cik, expected):
    pit = modules["_pit_universe"]
    calls = []
    submissions = {"name": "AcmeCorp Synthetic", "tickers": ["SYNTA"],
                   "filings": {"recent": {"form": ["10-K"], "filingDate": ["2020-02-01"]}, "files": []}}
    if response_cik is not None:
        submissions["cik"] = response_cik
    def fetch(url, **kwargs):
        calls.append(url)
        payload = ({"cik": 9900001, "taxonomy": "dei", "tag": "TradingSymbol",
                    "units": {"pure": [{"filed": "2020-02-01", "val": "SYNTA"}]}}
                   if "/companyconcept/" in url else submissions)
        return SimpleNamespace(status_code=200, json=lambda: deepcopy(payload))
    evidence = {}
    row = pit.cik_periodic_asof("9900001", "2021-01-01", fetch=fetch, evidence=evidence)
    if expected:
        assert row["cik"] == "9900001" and row["ticker"] == "SYNTA"
        assert evidence["outcome"] == "periodic_observed"
    else:
        assert row is None and len(calls) == 1
        assert evidence["outcome"] == "unavailable"
        assert evidence["work"][0]["status"] == "invalid"


@pytest.mark.parametrize("cik", [True, 9900001.5, "0", "invalid"])
def test_pit_invalid_query_identity_fails_before_fetch(modules, cik):
    def no_fetch(*args, **kwargs):
        pytest.fail("invalid identity must fail before fetch")
    evidence = {}
    assert modules["_pit_universe"].cik_periodic_asof(cik, "2021-01-01", fetch=no_fetch, evidence=evidence) is None
    assert evidence["work"][0]["status"] == "invalid"


def test_existing_pit_selftest_retains_positive_identity_controls(modules):
    modules["_pit_universe"]._selftest()


def _discover(modules, monkeypatch, status, resolved):
    events = modules["discover_events"]
    concepts = importlib.import_module("_deepdive_concepts")
    source = source22_scenarios()
    page = next(item for item in source["html"] if item["records"] and item["status"] == "complete")
    monkeypatch.setattr(events, "today", lambda: source["asof"])
    response = Response(text=page["html"])
    response.url = source["response_url"]
    monkeypatch.setattr(events, "http_get", lambda *args, **kwargs: response)
    parsed = events.parse_cluster_page(page["html"], observed_date=source["asof"],
                                      response_url=source["response_url"])
    mapping = concepts._TickerObservations(
        {item["ticker"]: {"cik": CASE["cik"], "title": "AcmeCorp"}
         for item in parsed["records"]} if resolved else {},
        status=status, reason="" if status == "complete" else "request_failed")
    calls = []
    def tickers():
        calls.append("sec_tickers")
        return mapping
    monkeypatch.setattr(events, "_get_sec_tickers", tickers, raising=False)
    monkeypatch.setattr(events, "_yf_mktcap", lambda ticker: 10_000_000)
    monkeypatch.setattr(events.time, "sleep", lambda seconds: None)
    rows = events.discover_insider_clusters(enrich_mktcap=True)
    return rows, calls


@pytest.mark.parametrize("status,resolved,expected", [
    ("complete", True, "complete"), ("complete", False, "partial"),
    ("unavailable", False, "partial"), ("invalid", True, "invalid")])
def test_insider_identity_is_bound_before_admission(modules, monkeypatch, status, resolved, expected):
    rows, calls = _discover(modules, monkeypatch, status, resolved)
    assert rows and calls == ["sec_tickers"]
    assert rows.completion["status"] == expected
    assert rows.completion["upstream"][0]["status"] == status
    assert all(row["cik"] == (CASE["cik"] if resolved else "") for row in rows)
    if not resolved:
        assert any(work["reason"] == "unresolved_event_identity" for work in rows.completion["work"])
    stages = modules["filter_by_sic"]
    source_binding = {"artifact": "candidates_event_synthetic.json", "run_dir": "/synthetic"}
    cheap_binding = {"artifact": "cheappass_synthetic.csv", "run_dir": "/synthetic"}
    decisions = [dict(input_index=i, ticker=row["ticker"], cik=row["cik"], band=row["band"],
                      screening_decision="retained", evidence_complete=True)
                 for i, row in enumerate(rows)]
    cheap = stages.stage_completion("cheap_pass", len(rows),
        work=[stages.stage_work("synthetic_screening")], upstream=[rows.completion])
    cheap.update(input=source_binding, input_count=len(rows), decisions=decisions)
    screened = [dict(input_index=str(i), ticker=row["ticker"], cik=row["cik"], rejected="False",
                     kf_scanned="True", disclosure_review_required="False")
                for i, row in enumerate(rows)]
    admission = importlib.import_module("_event_admission")
    survivors, completion = admission.event_admission(rows, rows.completion, cheap,
        source_binding, cheap_binding, screened)
    assert completion["status"] == expected
    assert [row["cik"] for row in survivors] == [row["cik"] for row in rows]


@pytest.mark.parametrize("cik", CASE["invalid_ciks"])
def test_invalid_identity_cannot_issue_financial_queries(modules, monkeypatch, cik):
    cheap = modules["cheap_pass"]
    queries = []
    monkeypatch.setattr(cheap, "get_concept_series", lambda *args: queries.append(args) or [])
    monkeypatch.setattr(cheap.time, "sleep", lambda *args: None)
    monkeypatch.setattr(cheap, "killflag_scan", lambda *args: {})
    with pytest.raises(ValueError, match="issuer identity"):
        cheap.health_check({"ticker": "SYNTH", "name": "AcmeCorp", "cik": cik})
    assert queries == []


def test_resolved_identity_reaches_financial_queries(modules, monkeypatch):
    cheap = modules["cheap_pass"]
    queries = []
    monkeypatch.setattr(cheap, "get_concept_series", lambda *args: queries.append(args) or [])
    monkeypatch.setattr(cheap.time, "sleep", lambda *args: None)
    monkeypatch.setattr(cheap, "killflag_scan", lambda *args: {})
    cheap.health_check({"ticker": "SYNTH", "name": "AcmeCorp", "cik": CASE["cik"]})
    assert len(queries) == 5
    assert all(cik == CASE["cik"] for cik, concept in queries)


def test_current_and_stale_debt_have_distinct_eligibility(valuation_module):
    from _deepdive_flags import _check_debt_quality
    base = deepcopy(source25_equity_basis_scenarios()[0]["data"])
    base["derived"].update(latest_goodwill=0, latest_intangibles=0, lessor_asset_heavy=True)
    results = []
    for stale in (False, True):
        data = deepcopy(base)
        if stale:
            data["financials"]["total_debt"][0]["end"] = "2020-12-31"
        data["derived"]["debt_stale"] = _check_debt_quality(
            data["financials"]["total_debt"], data["financials"]["assets"],
            data["financials"]["equity"], [])[1]
        assert data["derived"]["debt_stale"] is stale
        results.append(valuation_module.compute_valuation(data, 80_000_000,
            dict(valuation_module._VALUATION_DEFAULTS)))
    current, stale = results
    assert current["mos_basis"] == stale["mos_basis"] == "nav"
    assert current["buy_eligible"] is True
    assert stale["buy_eligible"] is False
    assert "debt_stale" in stale["buy_ineligible_reasons"]
    assert "debt_stale" not in current["buy_ineligible_reasons"]


def test_lumpy_ocf_blocks_buy_without_changing_normalization(valuation_module):
    from _deepdive_flags import _trajectory_fields
    data = source32_legacy_scenarios()["valuation_lumpy"]
    source28_annual_inputs(data)
    data = source26_debt_fixture(data)
    data["derived"].update(_trajectory_fields(data["financials"]["revenue"],
        data["financials"]["ocf"], [{"end": "2024-12-31", "val": 15_000_000}]))
    before = deepcopy(data)
    value = valuation_module.compute_valuation(data, 250_000_000,
        dict(valuation_module._VALUATION_DEFAULTS))
    assert data == before
    assert value["mos_basis"] == "fcf_cap" and value["margin_of_safety_pct"] > 0.30
    assert value["lumpy_ocf_normalization_suspect"] is True
    assert value["buy_eligible"] is False
    assert "lumpy_ocf_normalization_suspect" in value["buy_ineligible_reasons"]
    assert "debt_stale" not in value["buy_ineligible_reasons"]


@pytest.mark.parametrize("stock_return,expected_rate", [(-50.0, 0.0), (50.0, 1.0)])
def test_scorecard_names_the_above_threshold_population(tracker, monkeypatch, stock_return, expected_rate):
    row = dict(tracking_quote_scenarios()["base_row"], rating="避开", scored=True,
               stock_return_pct_unrounded=stock_return, stock_return_pct=stock_return,
               realized_excess_pct_unrounded=stock_return, realized_excess_pct=stock_return,
               favorable=stock_return > 0, brier=0.04, implied_prob=0.8)
    before = deepcopy(row)
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])
    tracker.cmd_scorecard(SimpleNamespace())
    assert row == before
    assert tracker._risk_metric_summary([row], "avoidance", -0.4)["rate"] == expected_rate
    text = tracker.SCORECARD_FILE.read_text(encoding="utf-8")
    metric = next(line for line in text.splitlines() if line.startswith("| Above-threshold outcome rate"))
    assert "total return > -40%" in metric
    assert f"| {expected_rate * 100:.1f}% | 1 |" in metric
    assert "does not establish successful loss avoidance" in text
    assert "Blowup-avoidance" not in text
