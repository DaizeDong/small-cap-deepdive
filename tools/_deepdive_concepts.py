"""XBRL concept-series fetching, annual selection, and filing-date provenance.

Concept constants, taxonomy merge helpers, and the SEC ticker cache are re-exported by
deepdive_data. I01 completion comes from filter_by_sic without importing the orchestrator.

The generic financial-series fetcher `_one_concept` is the monkeypatch point used by
deepdive_data's selftest. Historical market caps use `instant_share_evidence`, which
retains raw units, conflicting counts and request diagnostics before selection.
"""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import date
from functools import wraps
import math
import re
import time
from pathlib import Path
import sys

# sys.path shim so this module can be imported when tools/ is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import http_get
from _cash_flow_evidence import paired_annual_sum_evidence
from filter_by_sic import StageRows, rows_completion, stage_completion, stage_work

FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
DEI_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/{concept}.json"
# v0.3.2 #11, ifrs-full taxonomy endpoint. Foreign 20-F/40-F filers tag financials under
# ifrs-full instead of us-gaap; companyconcept exposes them on this taxonomy path. Extending the
# concept cascade to probe these recovers SOME foreign filers (graceful, absent -> empty, no crash).
IFRS_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/ifrs-full/{concept}.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Revenue concepts in priority order (earlier = lower priority, later = higher priority / overrides).
# Probe both contract-revenue concepts because issuers can change which tag supplies
# a period; fiscal-year selection remains independent of calendar-year boundaries.
REVENUE_CONCEPTS = [
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
]

# v0.3.2 #11, IFRS (ifrs-full taxonomy) concept cascade for foreign 20-F/40-F filers. Whole
# 20-F/40-F cohorts (Canadian PM juniors, China VIEs, foreign industrials) returned EMPTY
# financials because their XBRL is tagged under ifrs-full, not us-gaap. Probing the most common
# IFRS tags recovers SOME of these filers (graceful: absent concepts -> empty, never a crash).
# Each list is probed AFTER the us-gaap cascade and merged by end-date (us-gaap wins on a tie,
# IFRS only fills genuine gaps), see concept_series_with_ifrs.
IFRS_REVENUE_CONCEPTS = [
    "Revenue",
    "RevenueFromContractsWithCustomers",
]
IFRS_NET_INCOME_CONCEPTS = [
    "ProfitLoss",
    "ProfitLossAttributableToOwnersOfParent",
]
IFRS_OCF_CONCEPTS = [
    "CashFlowsFromUsedInOperatingActivities",
    "CashFlowsFromUsedInOperatingActivitiesContinuingOperations",
]

# Asset-heavy lessors can require lease-fleet NAV even below the debt/assets threshold.
# The producer emits lessor_asset_heavy; valuation uses it to force NAV routing.
# (a) SIC of leasing/rental businesses: 6726 (investment offices, incl. lease holdcos),
#     7377 (computer rental/leasing), 4741 (rental of railroad cars), 6159 (federal/agency lease
#     credit), 7359 (equipment rental & leasing nec).
LESSOR_SIC_CODES = {"6726", "7377", "4741", "6159", "7359"}
# (b) operating/finance lease-INCOME revenue concepts: the presence of lease income as a revenue
#     line is itself a leasing-business signal (the company earns rent on a fleet it owns).
LEASE_INCOME_CONCEPTS = [
    "OperatingLeasesIncomeStatementLeaseRevenue",
    "OperatingLeaseLeaseIncome",
    "SalesTypeLeaseRevenue",
    "DirectFinancingLeaseRevenue",
    "FinanceLeaseInterestIncome",
    "LeaseIncome",
]
# (c) PP&E / lease-fleet asset concepts: a very high (PP&E or lease-fleet)/total_assets ratio
#     COMBINED with rental/lease revenue is the third route (covers lessors whose SIC is a generic
#     industrial code and who tag rent under a non-lease-income revenue concept).
PPE_FLEET_CONCEPTS = [
    "PropertyPlantAndEquipmentNet",
    "PropertySubjectToOrAvailableForOperatingLeaseNet",
    "EquipmentLeasedToOtherPartyNet",
]
# Ratio above which (PP&E or lease-fleet)/total_assets is "very high" for route (c).
_LESSOR_PPE_RATIO = 0.55

# Debt concepts: prefer split long-term current/noncurrent; fallback to LongTermDebt aggregate;
# final fallback to total Liabilities (flags this in derived.debt_fallback).
# The debt cascade supports both split components and aggregate debt tags.
DEBT_CONCEPTS_PRIMARY = ["LongTermDebtNoncurrent", "LongTermDebtCurrent"]
DEBT_CONCEPT_FALLBACK1 = "LongTermDebt"
DEBT_CONCEPT_FALLBACK1B = "LongTermDebtAndCapitalLeaseObligations"
DEBT_CONCEPT_FALLBACK1C = "DebtLongtermAndShorttermCombinedAmount"
DEBT_CONCEPT_FALLBACK2 = "Liabilities"

# A reported zero is evidence; an absent component remains unknown.
DEBT_SUM_CONCEPTS = [
    "LongTermDebtNoncurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "FinanceLeaseLiabilityNoncurrent",
    "FinanceLeaseLiabilityCurrent",
]

# v0.3.1 #3, ASC842 operating-lease liability concepts. cross_source_mismatch over-fires on
# lease-heavy retail because SEC debt excludes operating leases while yfinance's totalDebt includes
# capitalized leases. We ADD these (current + noncurrent) to the SEC debt side ONLY for the
# cross-source comparison, so both sources are lease-comparable. NOT added to latest_total_debt
# itself (EV uses contractual debt; the lease add is a comparison-only adjustment).
OPERATING_LEASE_CONCEPTS = [
    "OperatingLeaseLiabilityNoncurrent",
    "OperatingLeaseLiabilityCurrent",
]

# C1: 18-month threshold for debt staleness (in days)
_DEBT_STALE_DAYS = 548  # 18 months ≈ 548 days

# D&A concepts are merged in this order; later values override the same period end.
DA_CONCEPTS = [
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationDepletionAndAmortization",
]

# CapEx uses the standard property, plant and equipment acquisition concept.
CAPEX_CONCEPT = "PaymentsToAcquirePropertyPlantAndEquipment"

# EBIT uses a concept cascade because filers may omit the primary operating-income tag.
# Cascade order (earlier = higher priority): operating income first; if absent, fall back to
# pretax income (continuing ops), optionally adding back interest expense to approximate EBIT.
# Each path tags `ebit_source` so the consumer knows which concept produced the number.
EBIT_PRIMARY_CONCEPT = "OperatingIncomeLoss"
EBIT_PRETAX_CONCEPTS = [
    # IncomeLossFromContinuingOperationsBeforeIncomeTaxes... has several long variants;
    # list older/narrower first, preferred last (concept_series later-overrides-earlier).
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]
EBIT_INTEREST_CONCEPTS = [
    "InterestExpense",
    "InterestAndDebtExpense",
    "InterestExpenseDebt",
]

# Insurance concepts support routing insurance subsidiaries even with non-financial SICs.
# The detector applies its own corroboration rules before emitting the routing flag.
INSURANCE_CONCEPTS = [
    "PremiumsEarnedNet",
    "PremiumsEarnedNetPropertyAndCasualty",
    "PremiumsWrittenNet",
    "LiabilityForClaimsAndClaimsAdjustmentExpense",
    "LossesAndLossAdjustmentExpense",
    "PolicyholderFunds",
    "LiabilityForFuturePolicyBenefits",
    "DeferredPolicyAcquisitionCosts",
    "UnearnedPremiums",
]


# Only known instant concepts may omit a start date. New concepts with unknown
# period type need duration evidence until their instant semantics are registered.
_INSTANT_CONCEPTS = {
    *DEBT_SUM_CONCEPTS, *OPERATING_LEASE_CONCEPTS, *PPE_FLEET_CONCEPTS,
    DEBT_CONCEPT_FALLBACK1, DEBT_CONCEPT_FALLBACK1B, DEBT_CONCEPT_FALLBACK1C,
    DEBT_CONCEPT_FALLBACK2,
    "Assets", "AssetsCurrent", "LiabilitiesCurrent", "StockholdersEquity",
    "LiabilitiesAndStockholdersEquity", "CashAndCashEquivalentsAtCarryingValue",
    "Goodwill", "IntangibleAssetsNetExcludingGoodwill", "RetainedEarningsAccumulatedDeficit",
    "CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding",
    "LiabilityForClaimsAndClaimsAdjustmentExpense", "PolicyholderFunds",
    "LiabilityForFuturePolicyBenefits", "DeferredPolicyAcquisitionCosts", "UnearnedPremiums",
}


# PIT (backtest, FIX 1), as-of filed-date accumulator. When a point-in-time pull runs (asof set),
# _one_concept records the max "filed" date of the facts it actually KEPT (filed<=asof, the latest-
# filed-per-end-date disclosures an investor at `asof` could have seen) into this module-level
# accumulator. deepdive_data.pull() resets it before its as-of cascade and reads it back after, so
# derived.asof_max_filing_date reflects the newest filing date that fed ANY concept value used in the
# point-in-time reconstruction. This is what makes the look-ahead audit NON-vacuous (the harness
# asserts asof_max_filing_date <= asof). The accumulator is process-global but ALWAYS reset by the
# caller via reset_asof_filed_tracker() at the top of an as-of pull, so concurrent live (asof=None)
# pulls, which NEVER touch it, cannot corrupt it. The asof=None path does not record anything, so
# live pulls do not alter this accumulator.
_asof_max_filed: str | None = None


class ConceptObservations:
    """Completion of source queries attempted inside one observation scope."""

    def __init__(self):
        self._queries = []

    def completion(self, row_count=0):
        return stage_completion(
            "sec_financial_observations", row_count, upstream=deepcopy(self._queries),
            reasons=[] if self._queries else ["no_source_queries_observed"])


_concept_observers = ContextVar("smallcap_concept_observers", default=())


@contextmanager
def concept_observations():
    """Collect queries without changing return values or sharing concurrent state."""
    observation = ConceptObservations()
    token = _concept_observers.set((*_concept_observers.get(), observation))
    try:
        yield observation
    finally:
        _concept_observers.reset(token)


def _record_observation(completion):
    for observation in _concept_observers.get():
        observation._queries.append(deepcopy(completion))


def _observed_series(stage, *, source_argument=None):
    """Attach query completion while preserving the existing series calculations."""
    def decorate(function):
        @wraps(function)
        def observed(*args, **kwargs):
            upstream = []
            if source_argument is not None:
                series = args[1] if len(args) > 1 else kwargs[source_argument]
                upstream.append(rows_completion(series, "supplied_financial_series"))
            with concept_observations() as observation:
                value = function(*args, **kwargs)
            rows = value[0] if isinstance(value, tuple) else value
            upstream.extend(observation._queries)
            result = StageRows(rows, stage=stage, upstream=upstream,
                               reasons=[] if upstream else ["no_source_queries_observed"])
            return (result, *value[1:]) if isinstance(value, tuple) else result
        return observed
    return decorate


def _concept_result(rows, request, status, reason="", **diagnostics):
    result = StageRows(rows, stage="sec_concept", work=[stage_work(
        "sec_companyconcept", request["taxonomy"] + ":" + request["concept"],
        status=status, reason=reason)])
    result.completion.update(request=request, observation=diagnostics)
    _record_observation(result.completion)
    return result


def _fact_shape_valid(fact, *, asof, allow_instant):
    """Recognize malformed evidence before applying the unchanged annual filter."""
    if not isinstance(fact, dict) or type(fact.get("val")) not in (int, float):
        return False
    try:
        if not math.isfinite(fact["val"]):
            return False
        end = date.fromisoformat(fact["end"])
        if "start" not in fact and not allow_instant:
            return False
        if "start" in fact:
            if date.fromisoformat(fact["start"]) > end:
                return False
        if asof is not None:
            date.fromisoformat(fact.get("filed"))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return True


def reset_asof_filed_tracker() -> None:
    """Reset the as-of filed-date accumulator to None (call before an as-of pull cascade)."""
    global _asof_max_filed
    _asof_max_filed = None


def get_asof_max_filed() -> str | None:
    """Return the max 'filed' date (YYYY-MM-DD) recorded across as-of concept pulls since the last
    reset_asof_filed_tracker(), or None if no as-of fact was kept."""
    return _asof_max_filed


def _record_asof_filed(filed: str | None) -> None:
    """Record a kept fact's 'filed' date into the as-of accumulator, keeping the max. No-op on None."""
    global _asof_max_filed
    if not filed:
        return
    if _asof_max_filed is None or filed > _asof_max_filed:
        _asof_max_filed = filed


def _concept_unit(concept: str) -> str:
    """Return the unit required by the financial concept, without cross-unit fallback."""
    if concept in {"CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding",
                   "WeightedAverageNumberOfDilutedSharesOutstanding",
                   "WeightedAverageNumberOfSharesOutstandingBasic"}:
        return "shares"
    if concept in {"EarningsPerShareBasic", "EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"}:
        return "USD/shares"
    return "USD"


def _annual_entry(fact: dict, *, allow_instant: bool, unit: str | None = None,
                  cik: str | None = None, taxonomy: str | None = None,
                  concept: str | None = None) -> dict | None:
    """Keep annual flows and instant balances with their original date evidence."""
    try:
        end = fact["end"]
        date.fromisoformat(end)
        entry = {"end": end, "val": fact["val"], "fy": fact.get("fy"),
                 "filed": fact.get("filed")}
        for key in ("unit", "currency", "cik", "entity", "taxonomy", "concept", "accn", "source", "form", "fp"):
            if key in fact:
                entry[key] = fact[key]
        for key, value in (("unit", unit), ("cik", cik), ("taxonomy", taxonomy), ("concept", concept)):
            if value is not None:
                entry[key] = value
        if unit in {"USD", "USD/shares"}:
            entry["currency"] = "USD"
        if "start" not in fact and not allow_instant:
            return None
        if "start" in fact:
            start = fact["start"]
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if not 330 <= days <= 400:
                return None
            entry.update(start=start, duration_days=days,
                         fp=fact.get("fp", ""), form=fact.get("form", ""))
        return entry
    except (KeyError, TypeError, ValueError):
        return None


def _one_concept(cik: str, concept: str, taxonomy: str = "us-gaap", asof: str | None = None) -> list:
    """拉单个 XBRL 概念的年度序列。

    Flow facts require a 330-400 day span, regardless of annual filing labels. Quarterly
    comparatives and short transition periods in annual filings are excluded, not annualized.
    Registered instant concepts (balances and period-end shares) do not need a duration.
    A missing start date alone cannot establish that a concept is an instant balance.
    Returned facts retain filing dates, validated units and the response identity;
    flows also retain start dates and duration.

    Same end-date dedup within one concept: last entry in API response order wins,
    which aligns with EDGAR ordering (restated/amended values appear after originals).

    PIT (backtest) — `asof` (a YYYY-MM-DD string) makes this a point-in-time pull:
      * each companyconcept fact carries its own "filed" date in the JSON; keep ONLY facts
        with filed <= asof (drops facts disclosed after the as-of date — no look-ahead);
      * per end-date, pick the LATEST-FILED fact <= asof (the most recent disclosure that an
        investor standing at `asof` could have seen — restatements filed after asof are ignored).
    `asof=None` keeps the last eligible fact in API order. A fact missing a valid "filed"
    date is conservatively dropped in the asof path (cannot be dated <= T safely).
    """
    request = {"cik": str(cik)[:10], "taxonomy": str(taxonomy)[:40],
               "concept": str(concept)[:200],
               "asof": asof[:10] if isinstance(asof, str) else None}
    try:
        request["cik"] = _share_cik(cik)
        if (taxonomy not in {"us-gaap", "ifrs-full", "dei"}
                or not isinstance(concept, str) or not concept or len(concept) > 200):
            raise ValueError("invalid concept identity")
        if asof is not None:
            _share_day(asof)
    except (TypeError, ValueError):
        return _concept_result([], request, "invalid", "invalid_query_identity")
    if taxonomy == "us-gaap":
        url = FACTS.format(cik=request["cik"], concept=concept)
    elif taxonomy == "ifrs-full":  # v0.3.2 #11, foreign-filer IFRS concept recovery
        url = IFRS_FACTS.format(cik=request["cik"], concept=concept)
    else:
        url = DEI_FACTS.format(cik=request["cik"], concept=concept)
    try:
        r = http_get(url, timeout=20)
    except Exception:
        return _concept_result([], request, "unavailable", "request_failed")
    http_status = getattr(r, "status_code", None)
    if type(http_status) is not int:
        return _concept_result([], request, "invalid", "invalid_http_response")
    if http_status == 404:
        return _concept_result([], request, "complete", "concept_not_reported", http_status=404)
    if http_status != 200:
        return _concept_result([], request, "unavailable", "http_status",
                               http_status=http_status)
    try:
        payload = r.json()
    except Exception:
        return _concept_result([], request, "invalid", "invalid_json", http_status=200)
    try:
        if (not isinstance(payload, dict)
                or _share_cik(payload.get("cik")) != request["cik"]
                or payload.get("taxonomy") != taxonomy or payload.get("tag") != concept):
            raise ValueError("concept identity mismatch")
    except (TypeError, ValueError):
        return _concept_result([], request, "invalid", "invalid_response_identity", http_status=200)
    units = payload.get("units")
    if not isinstance(units, dict) or any(not isinstance(v, list) for v in units.values()):
        return _concept_result([], request, "invalid", "invalid_units", http_status=200)
    expected_unit = _concept_unit(concept)
    selected = expected_unit if units.get(expected_unit) else None
    if selected is None and any(units.values()):
        return _concept_result([], request, "invalid", "incompatible_concept_units",
                               http_status=200, expected_unit=expected_unit)
    vals = units[selected] if selected is not None else []
    malformed, excluded, future = 0, 0, 0
    try:
        seen: dict = {}
        for fact in vals:
            if not _fact_shape_valid(fact, asof=asof, allow_instant=concept in _INSTANT_CONCEPTS):
                malformed += 1
                continue
            entry = _annual_entry(fact, allow_instant=concept in _INSTANT_CONCEPTS,
                                  unit=selected, cik=request["cik"], taxonomy=taxonomy, concept=concept)
            if entry is None:
                excluded += 1
                continue
            if asof is not None:
                filed = entry["filed"]
                try:
                    date.fromisoformat(filed)
                except (TypeError, ValueError):
                    malformed += 1
                    continue
                if filed > asof:
                    future += 1
                    continue
                previous = seen.get(entry["end"])
                if previous is not None and filed < previous["filed"]:
                    continue
            seen[entry["end"]] = entry
        if asof is not None:
            for entry in seen.values():
                _record_asof_filed(entry["filed"])
        return _concept_result(list(seen.values()), request,
            "invalid" if malformed else "complete", "malformed_facts" if malformed else "",
            http_status=200, selected_unit=selected, received_facts=len(vals),
            eligible_facts=len(seen), excluded_duration=excluded, excluded_future=future,
            malformed_facts=malformed)
    except Exception:
        return _concept_result([], request, "invalid", "fact_parse_failed", http_status=200)


def _share_cik(value) -> str:
    text = str(value).strip()
    if (isinstance(value, bool) or not text.isascii() or not text.isdigit()
            or not 1 <= len(text) <= 10 or int(text) == 0):
        raise ValueError("invalid SEC issuer identifier")
    return text.zfill(10)


def _share_day(value) -> str:
    if not isinstance(value, str) or len(value) != 10 or date.fromisoformat(value).isoformat() != value:
        raise ValueError("share observation and filing dates must use YYYY-MM-DD")
    return value


def _strict_share_query(cik: str, asof: str, taxonomy: str, concept: str) -> tuple[dict, list]:
    """Decode one raw SEC response without generic unit selection or deduplication."""
    source = f"sec:{taxonomy}:{concept}"
    detail = {"source": source, "status": "provider_error", "http_status": None}
    template = DEI_FACTS if taxonomy == "dei" else FACTS
    try:
        response = http_get(template.format(cik=cik, concept=concept), timeout=20)
    except Exception as exc:
        detail.update(error_type=type(exc).__name__, reason="SEC request failed")
        return detail, []
    status = getattr(response, "status_code", None)
    if not isinstance(status, int) or isinstance(status, bool):
        detail.update(status="invalid", reason="SEC response has no integer HTTP status")
        return detail, []
    detail["http_status"] = status
    if status == 404:
        detail.update(status="absent", reason="SEC concept not found")
        return detail, []
    if status != 200:
        detail["reason"] = f"SEC request returned HTTP {status}"
        return detail, []
    try:
        body = response.json()
    except Exception as exc:
        detail.update(status="invalid", error_type=type(exc).__name__, reason="SEC response is not valid JSON")
        return detail, []
    try:
        if (not isinstance(body, dict) or _share_cik(body.get("cik")) != cik
                or body.get("taxonomy") != taxonomy or body.get("tag") != concept):
            raise ValueError("SEC response identity does not match the requested issuer and concept")
        units = body.get("units")
        if not isinstance(units, dict) or not all(isinstance(rows, list) for rows in units.values()):
            raise ValueError("SEC units must map unit names to fact lists")
        detail["units"] = sorted(units)
        if any(unit != "shares" and rows for unit, rows in units.items()):
            raise ValueError("instantaneous share concepts require shares units only")
        facts = units.get("shares", [])
        detail.update(observations_received=len(facts), excluded_after_asof=0)
        candidates = []
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError("SEC share fact is not an object")
            end, filed = _share_day(fact.get("end")), _share_day(fact.get("filed"))
            if end > asof or filed > asof:
                detail["excluded_after_asof"] += 1
                continue
            if filed < end or fact.get("start") is not None:
                raise ValueError("share fact is not a dated instantaneous count")
            count = fact.get("val")
            if (isinstance(count, bool) or not isinstance(count, (int, float))
                    or count <= 0 or not math.isfinite(count)):
                raise ValueError("SEC shares must be a finite positive number")
            candidates.append({"shares": count, "date": end, "filed": filed,
                               "basis": "as_reported", "basis_date": end, "unit": "shares",
                               "source": source,
                               "accession": fact.get("accn") if isinstance(fact.get("accn"), str) else None})
    except (ValueError, TypeError, OverflowError) as exc:
        detail.update(status="invalid", reason=str(exc))
        return detail, []
    detail.update(status="ok" if candidates else "absent", eligible_observations=len(candidates),
                  reason="eligible instantaneous share facts" if candidates else "no eligible share facts at asof")
    return detail, candidates


def instant_share_evidence(cik, asof: str) -> dict:
    """Return strict common-share evidence and every query's outcome.

    All queried concepts must resolve to valid data or confirmed absence. An error
    in one query blocks continuation using another query's count. This policy is
    explicit in the returned envelope; financial-series callers retain their own
    established behavior in `_one_concept`.
    """
    out = {"status": "unavailable", "evidence": None, "queries": [],
           "selection_policy": "latest_observation_then_latest_filing",
           "continuation_policy": "require_all_concept_queries_resolved",
           "reason": "no eligible instantaneous share evidence"}
    if cik is None or isinstance(cik, str) and not cik.strip():
        out["reason"] = "SEC issuer identifier unavailable"
        return out
    try:
        cik, asof = _share_cik(cik), _share_day(asof)
    except (ValueError, TypeError, OverflowError) as exc:
        out.update(status="invalid", reason=str(exc))
        return out
    candidates = []
    for taxonomy, concept in (("dei", "EntityCommonStockSharesOutstanding"),
                              ("us-gaap", "CommonStockSharesOutstanding")):
        query, facts = _strict_share_query(cik, asof, taxonomy, concept)
        out["queries"].append(query)
        candidates.extend(facts)
    for status in ("provider_error", "invalid"):
        failed = [query for query in out["queries"] if query["status"] == status]
        if failed:
            out.update(status=status, reason="; ".join(query["source"] + ": " + query["reason"] for query in failed))
            return out
    if not candidates:
        return out
    newest = max((row["date"], row["filed"]) for row in candidates)
    selected = [row for row in candidates if (row["date"], row["filed"]) == newest]
    counts = {row["shares"] for row in selected}
    if len(counts) != 1:
        out.update(status="invalid", conflicting_values=sorted(counts),
                   reason="conflicting instantaneous share counts for the latest observation and filing date")
        return out
    chosen = min(selected, key=lambda row: (row["source"], row["accession"] or ""))
    evidence = {**chosen, "sources": sorted({row["source"] for row in selected}),
                "matching_facts": len(selected)}
    _record_asof_filed(evidence["filed"])
    out.update(status="ok", evidence=evidence, reason="latest eligible disclosed share count selected")
    return out


@_observed_series("sec_concept_series")
def concept_series(cik: str, concepts, n: int = 8, asof: str | None = None) -> list:
    """拉一个或多个 XBRL 概念,**合并**取真正最新的 n 期。

    Concept merge: for the same end-date, later concepts in the list override earlier ones.
    This means callers should list older/narrower concepts first and the preferred/current
    concept last. Within a single concept, _one_concept already keeps the last (restated) value.

    PIT — `asof` (YYYY-MM-DD) threads through to _one_concept so every concept in the cascade is
    pulled point-in-time (filed<=asof, latest-filed per end-date). asof=None == live default.
    """
    if isinstance(concepts, str):
        concepts = [concepts]
    seen: dict = {}
    for concept in concepts:
        for a in _one_concept(cik, concept, asof=asof):
            # Later concept overrides earlier for the same end date.
            seen[a["end"]] = a
        time.sleep(0.15)
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


def concept_series_asof(cik: str, concept, asof: str, n: int = 8) -> list:
    """PIT (backtest) sibling of concept_series — point-in-time concept pull.

    Returns the same output shape as concept_series, but using ONLY companyconcept facts with
    JSON "filed" <= asof, picking the latest-FILED fact per period end (the most recent disclosure
    visible to an investor standing at `asof`). Restatements/amendments filed after `asof` are
    ignored — this is the look-ahead-safe reconstruction the backtest harness joins forward returns
    against. `concept` may be a single concept string or a cascade list (later overrides earlier,
    same merge semantics as concept_series). Thin wrapper over concept_series(..., asof=asof).
    """
    return concept_series(cik, concept, n=n, asof=asof)


@_observed_series("sec_taxonomy_series")
def concept_series_with_ifrs(cik: str, gaap_concepts, ifrs_concepts, n: int = 8,
                             asof: str | None = None) -> list:
    """v0.3.2 #11 — pull a concept across BOTH us-gaap and ifrs-full, merging by end-date.

    The us-gaap cascade is probed first (domestic filers, the common case). The ifrs-full
    cascade is then probed and used ONLY to FILL end-dates the us-gaap pass left empty — a
    us-gaap value is never overwritten by an IFRS one. This recovers SOME foreign 20-F/40-F
    filers (whose financials are tagged under ifrs-full) without disturbing domestic results.

    Graceful: a foreign filer with no IFRS tags either still returns the us-gaap series or an
    empty list (which downstream labels foreign_filer_unvaluable). Never raises.

    PIT — `asof` (YYYY-MM-DD) threads through to _one_concept for both taxonomies so the merged
    series is point-in-time (filed<=asof, latest-filed per end-date). asof=None == live default.
    """
    if isinstance(gaap_concepts, str):
        gaap_concepts = [gaap_concepts]
    if isinstance(ifrs_concepts, str):
        ifrs_concepts = [ifrs_concepts]
    seen: dict = {}
    # us-gaap first (preferred, domestic taxonomy).
    for concept in gaap_concepts:
        for a in _one_concept(cik, concept, taxonomy="us-gaap", asof=asof):
            seen[a["end"]] = a
        time.sleep(0.15)
    # ifrs-full second, fill gaps only; do NOT overwrite a us-gaap value at the same end-date.
    for concept in ifrs_concepts:
        for a in _one_concept(cik, concept, taxonomy="ifrs-full", asof=asof):
            if a["end"] not in seen:
                seen[a["end"]] = a
        time.sleep(0.15)
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


@_observed_series("sec_legacy_shares_series")
def _shares_series(cik: str, n: int = 8, asof: str | None = None) -> list:
    """Shares outstanding with a three-level fallback chain.

    1. us-gaap:CommonStockSharesOutstanding  (precise period-end count)
    2. dei:EntityCommonStockSharesOutstanding (cover-page count; coarser but current)
    3. us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding (annual average; diluted)

    Each level supplements gaps from the previous; the combined series is sorted by end date
    and the last n entries are returned. Duplicate end-dates: latest taxonomy/concept wins.

    PIT — `asof` (YYYY-MM-DD) threads through to _one_concept at every level so the shares
    series is point-in-time (filed<=asof, latest-filed per end-date). asof=None == live default.
    """
    seen: dict = {}
    # Level 1: us-gaap common shares
    for a in _one_concept(cik, "CommonStockSharesOutstanding", taxonomy="us-gaap", asof=asof):
        seen[a["end"]] = a
    time.sleep(0.15)
    # Level 2: dei cover-page count (instant, no start date in XBRL response)
    for a in _one_concept(cik, "EntityCommonStockSharesOutstanding", taxonomy="dei", asof=asof):
        seen[a["end"]] = a
    time.sleep(0.15)
    # Level 3: diluted weighted-average (flow concept, annual fp=FY only via _one_concept filter)
    for a in _one_concept(cik, "WeightedAverageNumberOfDilutedSharesOutstanding",
                          taxonomy="us-gaap", asof=asof):
        if a["end"] not in seen:  # only fill gaps; don't overwrite more precise counts
            seen[a["end"]] = a
    time.sleep(0.15)
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


def pct_growth(series: list) -> float | None:
    vals = [s["val"] for s in series if s.get("val") is not None]
    if len(vals) < 2 or vals[-2] == 0:
        return None
    return round((vals[-1] / vals[-2] - 1) * 100, 1)


# C1, company_tickers.json cache (fetched once per process; keyed by ticker uppercase)
_sec_tickers_cache: dict | None = None


class _TickerObservations(dict):
    """Dictionary-compatible cache value with its source completion evidence."""

    def __init__(self, rows=(), *, status, reason=""):
        super().__init__(rows)
        self.completion = stage_completion("sec_tickers", len(self), work=[stage_work(
            "sec_company_tickers", status=status, reason=reason)])


def _get_sec_tickers() -> dict:
    """Fetch and cache SEC company_tickers.json (ticker→{cik, title}).

    Returns dict keyed by UPPER-CASE ticker symbol.
    Failed requests return an incomplete mapping and are not stored as an empty cache.
    """
    global _sec_tickers_cache
    if _sec_tickers_cache is not None:
        completion = getattr(_sec_tickers_cache, "completion", stage_completion(
            "sec_tickers", len(_sec_tickers_cache), reasons=["unobserved_ticker_cache"]))
        _record_observation(completion)
        return _sec_tickers_cache
    try:
        r = http_get(SEC_COMPANY_TICKERS_URL, timeout=20)
    except Exception:
        result = _TickerObservations(status="unavailable", reason="request_failed")
    else:
        status = getattr(r, "status_code", None)
        if type(status) is not int:
            result = _TickerObservations(status="invalid", reason="invalid_http_response")
        elif status != 200:
            result = _TickerObservations(status="unavailable", reason="http_status")
            result.completion["http_status"] = status
        else:
            result = _parse_sec_tickers(r)
    _record_observation(result.completion)
    if result.completion["status"] == "complete":
        _sec_tickers_cache = result
    return result


def _parse_sec_tickers(response):
    try:
        raw = response.json()
        if not isinstance(raw, dict):
            raise ValueError("invalid ticker envelope")
        # raw is { "0": {cik_str, ticker, title}, "1": ... }
        result: dict = {}
        invalid = False
        for entry in raw.values():
            if not isinstance(entry, dict):
                invalid = True
                continue
            ticker = entry.get("ticker")
            try:
                cik = _share_cik(entry.get("cik_str"))
            except (TypeError, ValueError):
                invalid = True
                continue
            if (not isinstance(ticker, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", ticker)
                    or not isinstance(entry.get("title"), str)):
                invalid = True
                continue
            t = str(entry.get("ticker", "")).upper()
            if t:
                if t in result:
                    invalid = True
                result[t] = {
                    "cik": cik,
                    "title": entry.get("title", ""),
                }
        return _TickerObservations(result, status="invalid" if invalid else "complete",
                                   reason="malformed_ticker_rows" if invalid else "")
    except Exception:
        return _TickerObservations(status="invalid", reason="invalid_ticker_payload")


def _reconcile_debt_periods(concepts: dict, n: int = 8) -> tuple[list, str]:
    """Retain reported components and aggregates without treating absence as zero."""
    from math import isclose, isfinite

    aggregate_scopes = {
        DEBT_CONCEPT_FALLBACK1: DEBT_SUM_CONCEPTS[:2],
        DEBT_CONCEPT_FALLBACK1B: DEBT_SUM_CONCEPTS[:2] + DEBT_SUM_CONCEPTS[3:],
        DEBT_CONCEPT_FALLBACK1C: DEBT_SUM_CONCEPTS[:3],
    }
    periods = {}
    for concept, entries in concepts.items():
        for entry in entries:
            end = entry.get("end")
            if isinstance(end, str):
                periods.setdefault(end, {})[concept] = entry.get("val")
    result = []
    for end, values in sorted(periods.items()):
        valid = {name: value for name, value in values.items()
                 if type(value) in (int, float) and isfinite(value) and value >= 0}
        components = {name: valid[name] for name in DEBT_SUM_CONCEPTS if name in valid}
        aggregates = {name: valid[name] for name in aggregate_scopes if name in valid}
        missing = [name for name in DEBT_SUM_CONCEPTS if name not in components]
        conflicts = []
        for name, aggregate in aggregates.items():
            present = [components[tag] for tag in aggregate_scopes[name] if tag in components]
            subtotal = sum(present)
            if (subtotal > aggregate and not isclose(subtotal, aggregate, rel_tol=1e-6, abs_tol=1)
                    or len(present) == len(aggregate_scopes[name])
                    and not isclose(subtotal, aggregate, rel_tol=1e-6, abs_tol=1)):
                conflicts.append(name)
        if not missing:
            value = sum(components.values())
            source = "+".join(DEBT_SUM_CONCEPTS)
            status = "reported"
            detail = None
        elif aggregates:
            source = next(name for name in reversed(aggregate_scopes) if name in aggregates)
            value = aggregates[source]
            status = "partial"
            detail = "Reported aggregate retained; complete contractual-debt coverage is unproved."
        elif components:
            value = sum(components.values())
            source = "+".join(components)
            status = "partial"
            detail = "Only some contractual-debt components were reported; absent tags are not zero."
        else:
            value, source, status = None, "unavailable", "unavailable"
            detail = "No valid contractual-debt observation is available."
        if len(valid) != len(values):
            status = "invalid"
            detail = "A contractual-debt observation is invalid; complete debt is unproved."
        if conflicts:
            status = "conflicting"
            detail = "Reported debt aggregates conflict with same-period component evidence."
        result.append({"end": end, "val": value, "source": source,
                       "debt_evidence_status": status, "debt_evidence_detail": detail,
                       "components": components, "aggregates": aggregates,
                       "missing_components": missing, "conflicting_aggregates": conflicts})
    result = result[-n:]
    return result, result[-1]["source"] if result else "unavailable"


@_observed_series("sec_debt_series")
def _debt_series(cik: str, n: int = 8, asof: str | None = None) -> tuple[list, str]:
    """Query debt components and aggregates, then reconcile each reporting period.

    Partial observations remain diagnostic evidence. Total liabilities never substitute
    for debt, and an aggregate is queried even when a component is already present.
    """
    concepts = {}
    for concept in [*DEBT_SUM_CONCEPTS, DEBT_CONCEPT_FALLBACK1,
                    DEBT_CONCEPT_FALLBACK1B, DEBT_CONCEPT_FALLBACK1C]:
        concepts[concept] = _one_concept(cik, concept, asof=asof)
        time.sleep(0.15)
    return _reconcile_debt_periods(concepts, n)


@_observed_series("sec_da_series")
def _da_series(cik: str, n: int = 8, asof: str | None = None) -> tuple[list, str]:
    """Pull depreciation & amortization series using multi-concept merge.

    Priority chain (later overrides earlier for same end date):
    1. DepreciationAndAmortization
    2. DepreciationAmortizationAndAccretionNet
    3. DepreciationDepletionAndAmortization

    Returns (series, fallback_label) describing which concepts provided data.
    Different filers can supply one or several concepts in the priority chain.

    PIT — `asof` (YYYY-MM-DD) threads through to _one_concept so the D&A series is point-in-time
    (filed<=asof, latest-filed per end-date). asof=None == live default.
    """
    seen: dict = {}
    found_concepts: list = []
    for concept in DA_CONCEPTS:
        entries = _one_concept(cik, concept, asof=asof)
        time.sleep(0.15)
        if entries:
            found_concepts.append(concept)
            for v in entries:
                seen[v["end"]] = dict(v)
    series = sorted(seen.values(), key=lambda x: x["end"])[-n:]
    label = "+".join(found_concepts) if found_concepts else "unavailable"
    return series, label


@_observed_series("sec_ebit_series", source_argument="op_income_series")
def _ebit_with_source(cik: str, op_income_series: list, n: int = 8,
                      asof: str | None = None) -> tuple[list, str | None]:
    """P9 — EBIT concept cascade with `ebit_source` tagging.

    Recovers an EBIT series for the ~47% of names that don't tag OperatingIncomeLoss
    (banks/insurers, IFRS filers, some industrials), so EV/EBITDA can compute.

    Cascade (each path tagged):
      1. OperatingIncomeLoss                              -> ebit_source="OperatingIncomeLoss"
      2. PretaxContinuingOps + interest expense addback   -> ebit_source="pretax+interest_addback"
      3. PretaxContinuingOps (no interest available)      -> ebit_source="pretax_proxy"

    Returns (series, ebit_source), retaining annual periods and operand provenance.
    ebit_source is None when nothing recovers (caller leaves ebit empty).
    The pretax addback requires compatible annual start/end periods; interest is added back (interest reduces
    pretax income, so EBIT ~= pretax + interest expense).

    PIT — `asof` (YYYY-MM-DD) threads through to the pretax/interest concept_series probes so the
    EBIT fallback is point-in-time. The op_income_series is pulled point-in-time by the caller.
    asof=None == live default.
    """
    # Path 1: OperatingIncomeLoss (already pulled by caller)
    if op_income_series:
        return op_income_series[-n:], EBIT_PRIMARY_CONCEPT

    # Path 2/3: pretax continuing-ops income as the EBIT base
    pretax = concept_series(cik, EBIT_PRETAX_CONCEPTS, n=n, asof=asof)
    time.sleep(0.15)
    if not pretax:
        return [], None

    # Try interest addback (EBIT = pretax + interest expense). Interest is reported as a
    # positive expense; adding it back to pretax income approximates operating income.
    interest = concept_series(cik, EBIT_INTEREST_CONCEPTS, n=n, asof=asof)
    time.sleep(0.15)
    if interest:
        paired = {row["end"]: row for row in paired_annual_sum_evidence(
            pretax, interest, left_name="pretax", right_name="interest") if row["qualified"]}
        series = []
        any_addback = False
        for v in pretax:
            evidence = paired.get(v["end"])
            if evidence is not None:
                series.append({**v, "val": evidence["val"], "concept": "pretax_plus_interest",
                               "source": "derived:pretax_plus_interest", "operands": evidence["operands"]})
                any_addback = True
            else:
                series.append(dict(v))
        if any_addback:
            return series[-n:], "pretax+interest_addback"

    # Path 3: pretax proxy (no interest series to add back)
    series = [dict(v) for v in pretax]
    return series[-n:], "pretax_proxy"


def _operating_lease_liability(cik: str, asof: str | None = None) -> float | None:
    """v0.3.1 #3 — latest operating-lease liability (current + noncurrent) for lease-adjusting the
    SEC debt side of the cross_source comparison. Sums OperatingLeaseLiabilityNoncurrent +
    OperatingLeaseLiabilityCurrent at the latest common/available end-date. Returns None when no
    operating-lease concept is reported (non-lease-heavy filer). Network-safe.

    PIT — `asof` (YYYY-MM-DD) threads through to _one_concept so the lease liability is
    point-in-time (filed<=asof, latest-filed per end-date). asof=None == live default."""
    by_end: dict = {}
    for concept in OPERATING_LEASE_CONCEPTS:
        try:
            entries = _one_concept(cik, concept, asof=asof)
        except Exception:
            _concept_result([], {"cik": str(cik)[:10], "taxonomy": "us-gaap",
                                 "concept": concept, "asof": asof},
                            "unavailable", "query_failed")
            entries = []
        time.sleep(0.15)
        for v in entries:
            if v.get("val") is not None:
                by_end.setdefault(v["end"], 0.0)
                by_end[v["end"]] += v["val"]
    if not by_end:
        return None
    latest_end = sorted(by_end)[-1]
    return by_end[latest_end]
