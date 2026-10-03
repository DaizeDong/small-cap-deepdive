"""Generated source23 contracts. All observations and identities are synthetic."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_private_runs import state
from test_financial_evidence import valuation_module
from test_source22_contracts import modules, event_files, CASE as EVENT

CASE = json.loads(Path(__file__).with_name("source23_contracts.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASE["snapshots"], ids=lambda case: case["name"])
def test_return_uses_one_adjustment_snapshot(case):
    from _forward_snapshot import snapshot_return
    result = snapshot_return(CASE["ticker"], CASE["entry_date"], CASE["horizon_date"], case["rows"])
    assert result["available"] is True
    assert result["return_fraction"] == pytest.approx(case["expected"])
    assert result["entry_quote"]["price"] == case["rows"][0][1]
    assert len(result["adjustment_snapshot"]["selected_endpoints_sha256"]) == 64


@pytest.mark.parametrize("case", CASE["bad_snapshots"], ids=lambda case: case["name"])
def test_unsupported_snapshot_cannot_produce_a_return(case):
    from _forward_snapshot import snapshot_return
    result = snapshot_return(CASE["ticker"], CASE["entry_date"], CASE["horizon_date"], case["rows"])
    assert result["available"] is False and result["return_fraction"] is None


@pytest.mark.parametrize("case", CASE["risks"], ids=lambda case: case["name"])
def test_unknown_risk_abstains_without_comparing_none(state, case):
    import backtest
    result = backtest.bucket_name(case["deep"], CASE["valuation"])
    assert result["bucket"] == case["bucket"]
    assert result["killflag_count"] == case["count"]


def test_reverse_dcf_display_uses_fraction_and_perpetuity_model(state):
    import make_report
    result = make_report.render_report(
        CASE["clean"], {"reverse_dcf_implied_growth": 0.1, "mos_basis": "abstain"})
    assert "Reverse DCF implied growth (Gordon perpetuity): 10.0%" in result
    assert "Reverse DCF implied growth (5-yr)" not in result


@pytest.mark.parametrize("case", CASE["totals"], ids=lambda case: case["name"])
def test_insider_empty_and_result_totals_agree(modules, case):
    result = modules["_event_insider"].parse_cluster_page(case["html"],
        observed_date=CASE["event_asof"], response_url=CASE["response_url"])
    assert result["status"] == case["status"]


def test_resampled_references_remain_distinct_occurrences(state, monkeypatch):
    directory = Path(__file__).resolve().parents[2] / "docs" / "backtest-2026-06"
    monkeypatch.syspath_prepend(str(directory))
    module = importlib.import_module("distress_oos_validate2")
    a, b = deepcopy(CASE["bootstrap"])
    result = module.loyo_lift([a, a, b, b, b], "core4")
    assert result[:4] == (1, 0, 1, 3)
    assert result[4] == pytest.approx(2.5)
    assert result[5] == pytest.approx(0.5)
    calls = iter(["SYNTA", "SYNTA", "SYNTA", "SYNTB"])
    monkeypatch.setattr(module.random, "choice", lambda _: next(calls))
    result = module.ticker_bootstrap([a, b], "core4", B=2)
    assert result[-1] == 2


def test_historical_name_abstains_and_preserves_outcomes(state, monkeypatch):
    import backtest
    monkeypatch.setattr(backtest, "_val_cfg", lambda: {})
    deep = deepcopy(CASE["clean"])
    deep["derived"]["asof_max_filing_date"] = CASE["entry_date"]
    row = backtest._process_name(
        {"ticker": CASE["ticker"], "cik": CASE["cik"]}, CASE["entry_date"], 12,
        lambda *_, **__: deep, lambda *_: CASE["valuation"],
        lambda *_, **__: {"mktcap": 1000000, "usable": True},
        lambda *_: {"status": "ok", "total_return": 0.1})
    assert row["bucket"] == "abstain" and row["buy_eligible"] is False
    assert row["total_return"] == 0.1
    assert row["historical_eligibility"]["status"] == "unavailable"
    audit = backtest.look_ahead_audit([row], CASE["entry_date"], {}, expect_dates=True)
    assert audit["scope"] == "filing_dates_only"
    assert audit["all_eligibility_inputs_proven"] is False


def test_historical_pull_never_calls_undated_sources(modules, monkeypatch):
    module = modules["deepdive_data"]
    def forbidden(*args, **kwargs):
        pytest.fail("An undated provider input was consumed under as_of")
    for name in ("_sic_observation", "_validate_ticker_entity", "_insurance_concepts_present"):
        monkeypatch.setattr(module, name, forbidden)
    for name in ("concept_series_with_ifrs", "concept_series", "_shares_series", "_one_concept"):
        monkeypatch.setattr(module, name, lambda *_, **__: [])
    for name in ("_debt_series", "_ebit_with_source", "_da_series"):
        monkeypatch.setattr(module, name, lambda *_, **__: ([], None))
    monkeypatch.setattr(module, "_operating_lease_liability", lambda *_, **__: None)
    monkeypatch.setattr(module, "_lessor_asset_heavy", lambda *_, **__: (False, "synthetic"))
    monkeypatch.setattr(module, "tenk_sections", lambda *_, **__: {"available": False})
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = module.pull(CASE["ticker"], CASE["cik"], yf_fn=forbidden, as_of=CASE["entry_date"])
    assert result["historical_eligibility"]["status"] == "unavailable"
    assert result["derived"]["cross_source_checked"] is False


def test_historical_valuation_abstains_even_when_current_inputs_form_a_band(valuation_module):
    from make_fixtures import debt_valuation_scenarios
    compute_valuation = valuation_module.compute_valuation
    case = debt_valuation_scenarios()
    deep = case["cases"]["reported"]
    current = compute_valuation(deep, case["market_cap"], case["config"])
    historical = compute_valuation({**deep, "as_of": CASE["entry_date"]},
                                   case["market_cap"], case["config"])
    assert current["mos_basis"] != "abstain"
    assert historical["mos_basis"] == "abstain"
    assert historical["margin_of_safety_pct"] is None
    assert historical["nav_margin_of_safety_pct"] is None
    assert historical["buy_eligible"] is False


def test_finalizer_signal_snapshot_survives_recording(modules, state, monkeypatch):
    finalizer = modules["finalize_run"]
    directory = Path(state["root"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ("report_" + CASE["ticker"] + ".md")).write_text(CASE["report"], encoding="utf-8")
    deep = {**deepcopy(CASE["clean"]), "signals": deepcopy(CASE["signals"])}
    source = directory / ("deepdive_" + CASE["ticker"] + "_2000-01-01.json")
    source.write_text(json.dumps(deep), encoding="utf-8")
    verdict = finalizer.build_verdict(CASE["ticker"], directory, "2000-01-01")
    snapshot = verdict["signals_snapshot"]
    assert snapshot["source"]["bytes"] == len(source.read_bytes())
    assert snapshot["signals"] == CASE["signals"]
    tracker = importlib.import_module("track_forward")
    monkeypatch.setattr(tracker, "_quote_on", lambda *_args, **_kwargs: {"price": None})
    path = directory / "synthetic_verdicts.json"
    path.write_text(json.dumps([verdict]), encoding="utf-8")
    recorded = tracker._build_verdicts_from_json(path)[0]
    assert recorded["signals_snapshot"] == snapshot
    verdict["signals_snapshot"] = None
    path.write_text(json.dumps([verdict]), encoding="utf-8")
    without = tracker._build_verdicts_from_json(path)[0]
    assert (recorded["rating"], recorded["implied_prob"]) == (without["rating"], without["implied_prob"])


@pytest.mark.parametrize("field", ["ticker", "cik", "verdict_date", "signals_sha256", "schema_version"])
def test_tampered_signal_handoff_is_rejected(field):
    from _signal_snapshot import snapshot_from_deep, validate_signal_snapshot
    deep = {**CASE["clean"], "signals": CASE["signals"]}
    source = {"artifact": "deepdive_SYNTA_2000-01-01.json", "bytes": 1, "sha256": "a" * 64}
    snapshot = snapshot_from_deep(deep, CASE["ticker"], CASE["entry_date"], source)
    snapshot[field] = "invalid"
    with pytest.raises(ValueError):
        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["entry_date"])


@pytest.mark.parametrize("target", ["source", "admitted"])
def test_event_never_parses_a_different_text_snapshot(modules, state, monkeypatch, target):
    paths, _ = event_files(modules, Path(state["root"]), EVENT["event"][0])
    module = modules["_event_admission"]
    original = Path.read_text
    payload = paths[target].read_bytes()
    changed = json.loads(payload)
    changed[0]["name"] = "Different synthetic name"
    alternate = json.dumps(changed)
    reads = []
    def alternating_text(path, *args, **kwargs):
        if path == paths[target]:
            reads.append(path)
            return alternate
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", alternating_text)
    if target == "source":
        rows, _ = module._event_inputs(paths["source"], paths["cheap"])
    else:
        rows, _ = module.read_event_admission(Path(state["root"]))
    assert rows[0]["name"] != changed[0]["name"]
    assert reads == []


def test_event_rejects_alternating_bound_bytes(modules, state, monkeypatch):
    paths, _ = event_files(modules, Path(state["root"]), EVENT["event"][0])
    module = modules["_event_admission"]
    original = Path.read_bytes
    good = original(paths["source"])
    bad = json.loads(good)
    bad[0]["catalyst"] = "Different synthetic catalyst"
    bad = json.dumps(bad).encode("utf-8")
    reads = []
    def alternating(path):
        if path == paths["source"]:
            reads.append(path)
            return good if len(reads) % 2 else bad
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", alternating)
    with pytest.raises(ValueError):
        module.read_event_admission(Path(state["root"]))
    assert len(reads) >= 2


def test_event_finalizer_rejects_gate2_receipt_without_payload(modules, state):
    directory = Path(state["root"])
    event_files(modules, directory, EVENT["event"][0])
    gate2 = directory / "gate2_results.json"
    modules["filter_by_sic"].stage_receipt_path(gate2).write_text("{}", encoding="utf-8")
    assert not gate2.exists()
    with pytest.raises(ValueError, match="mix event"):
        modules["finalize_run"]._event_finalization_inputs(directory, set(), set())

def test_scoring_rebases_frozen_entry_from_one_download(state, monkeypatch):
    from make_fixtures import tracking_quote_scenarios
    from test_tracking_quote_contract import _SyntheticHistory
    import track_forward as tracker
    fixture = tracking_quote_scenarios()
    row = deepcopy(fixture["base_row"])
    calls = []
    def download(ticker, **kwargs):
        calls.append((ticker, kwargs))
        prices = [5.0, 5.5] if ticker == row["ticker"] else [20.0, 20.0]
        return _SyntheticHistory({"dates": ["2024-01-01", "2024-01-31"],
                                  "columns": ["Close"], "values": [[value] for value in prices]})
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    monkeypatch.setattr(tracker, "_today", lambda: fixture["today"])
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])
    monkeypatch.setattr(tracker, "_save_verdicts", lambda _: None)
    tracker.cmd_score(SimpleNamespace())
    assert row["scored"] is True
    assert row["entry_price"] == 10.0
    assert row["return_snapshot"]["entry_quote"]["price"] == 5.0
    assert row["stock_return_pct"] == 10.0 and row["realized_excess_pct"] == 10.0
    assert len(calls) == 2
    assert all(kwargs["start"] == "2023-12-25" and kwargs["end"] == "2024-02-01"
               and kwargs["auto_adjust"] is True for _, kwargs in calls)


def test_bootstrap_cutoff_spill_changes_precision(state, monkeypatch):
    directory = Path(__file__).resolve().parents[2] / "docs" / "backtest-2026-06"
    monkeypatch.syspath_prepend(str(directory))
    module = importlib.import_module("distress_oos_validate2")
    a, b, c = deepcopy(CASE["bootstrap_spill"])
    result = module.loyo_lift([a, b, b, c, c, c, c, c, c, c], "core4")
    assert result[:4] == (1, 1, 1, 7)
    assert result[4] == pytest.approx(2.5)
