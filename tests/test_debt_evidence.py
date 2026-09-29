"""Debt remains contractual evidence when balance-sheet tags change."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from make_fixtures import debt_scenarios

FIX = debt_scenarios()


@pytest.fixture
def debt_module(monkeypatch):
    common = ModuleType("_common")
    common.init_edgar = lambda: None
    common.UA = "user1@example.com"
    common.REPORTS = None
    common.CFG = {}
    common.today = lambda: FIX["date"]

    def blocked(*args, **kwargs):
        raise AssertionError("External data is outside this generated debt test")

    common.http_get = blocked
    monkeypatch.setitem(sys.modules, "_common", common)
    monkeypatch.setitem(sys.modules, "edgar", SimpleNamespace(Company=blocked))
    for name in ("deepdive_data", "_deepdive_flags", "_deepdive_concepts"):
        monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.delitem(sys.modules, name)
    module = importlib.import_module("deepdive_data")
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "http_get", lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: {"sic": "3571"}))
    monkeypatch.setattr(module, "_validate_ticker_entity", lambda *a: (False, None))
    monkeypatch.setattr(module, "_insurance_concepts_present", lambda *a, **k: (False, None))
    monkeypatch.setattr(module, "_lessor_asset_heavy", lambda *a, **k: (False, None))
    monkeypatch.setattr(module, "tenk_sections", lambda *a, **k: {})
    monkeypatch.setattr(module, "insider_trades", lambda *a, **k: {"available": False})
    monkeypatch.setattr(module, "_operating_lease_liability", lambda *a, **k: None)
    return module


@pytest.mark.parametrize("liabilities_present", [True, False])
@pytest.mark.parametrize("case", FIX["amount_cases"], ids=lambda case: case["name"])
def test_balance_sheet_totals_do_not_replace_contractual_debt(
        debt_module, liabilities_present, case):
    debt, substituted, detail = debt_module._debt_for_ev(
        case["amount"], FIX["liabilities"] if liabilities_present else [],
        FIX["equity"], FIX["assets"])
    assert debt == case["expected"]
    assert not substituted
    if case["expected"] is None:
        assert detail


@pytest.mark.parametrize("liabilities_present", [True, False])
def test_low_debt_ratio_is_not_evidence_of_truncation(debt_module, liabilities_present):
    series = [{"end": FIX["date"], "val": 0}]
    suspected, stale, detail = debt_module._check_debt_quality(
        series, FIX["assets"], FIX["equity"],
        FIX["liabilities"] if liabilities_present else [])
    assert (suspected, stale, detail) == (False, False, None)


def test_stale_contractual_debt_still_has_a_quality_flag(debt_module):
    series = [{"end": FIX["old_date"], "val": FIX["reported"]}]
    suspected, stale, _ = debt_module._check_debt_quality(
        series, FIX["assets"], FIX["equity"], FIX["liabilities"])
    assert stale
    assert not suspected


def pull_case(module, monkeypatch, *, missing=False, without_liabilities=False,
              conflicting=False, lease=None):
    concepts = deepcopy(FIX["unknown"] if missing else FIX["components"])
    if without_liabilities:
        concepts.pop("Liabilities", None)
    monkeypatch.setattr(module._dc, "_one_concept",
                        lambda cik, concept, **kw: deepcopy(concepts.get(concept, [])))
    monkeypatch.setattr(module, "_one_concept", module._dc._one_concept)
    monkeypatch.setattr(module, "_operating_lease_liability", lambda *a, **k: lease)
    second = {"total_debt": FIX["second_debt"]} if conflicting else None
    return module.pull(FIX["ticker"], FIX["cik"], yf_fn=lambda ticker: second)


@pytest.mark.parametrize("without_liabilities", [True, False])
def test_pull_preserves_reconciled_contractual_components(
        debt_module, monkeypatch, without_liabilities):
    result = pull_case(debt_module, monkeypatch, without_liabilities=without_liabilities)
    derived = result["derived"]
    assert result["financials"]["total_debt"][-1]["val"] == FIX["reported"]
    assert derived["latest_total_debt"] == FIX["reported"]
    assert not derived["debt_truncation_suspected"]
    assert derived["debt_evidence_status"] == "reported"
    assert all(name in derived["debt_source"] for name in FIX["component_names"])


@pytest.mark.parametrize("without_liabilities", [True, False])
def test_missing_debt_and_liabilities_proxy_remain_unknown(
        debt_module, monkeypatch, without_liabilities):
    result = pull_case(debt_module, monkeypatch, missing=True,
                       without_liabilities=without_liabilities)
    assert result["financials"]["total_debt"] == []
    assert result["derived"]["latest_total_debt"] is None
    assert result["derived"]["debt_evidence_status"] == "unavailable"
    assert result["derived"]["debt_evidence_detail"]


def test_cross_source_conflict_preserves_reported_debt_and_discloses_uncertainty(
        debt_module, monkeypatch):
    result = pull_case(debt_module, monkeypatch, conflicting=True)
    derived = result["derived"]
    assert derived["latest_total_debt"] == FIX["reported"]
    assert derived["cross_source_mismatch"]
    assert derived["debt_evidence_status"] == "conflicting"
    assert derived["debt_evidence_detail"]
    assert not derived["debt_truncation_suspected"]


def test_operating_leases_cannot_fill_missing_contractual_debt(debt_module, monkeypatch):
    result = pull_case(debt_module, monkeypatch, missing=True, conflicting=True,
                       lease=FIX["lease"])
    assert result["derived"]["latest_total_debt"] is None
    assert result["derived"]["debt_evidence_status"] == "unavailable"
    assert not result["derived"]["cross_source_checked"]
