"""_deepdive_concepts.py — XBRL concept-series pull layer extracted from deepdive_data.py.

Pure refactor: the XBRL companyconcept fetchers, the concept-cascade constants, the us-gaap +
ifrs-full merge helpers, and the SEC company_tickers cache. No behavior change — every symbol here
was moved verbatim from deepdive_data.py and is re-exported there so the public module path is
unchanged. Imports only from _common (and stdlib); NEVER from deepdive_data (no circular import).

The single low-level fetcher `_one_concept` is the monkeypatch point used by deepdive_data's
selftest (it patches _deepdive_concepts._one_concept). Every concept/flag helper that pulls XBRL
resolves the fetcher through this module's namespace so a single patch covers them all.
"""
from __future__ import annotations
import time
from pathlib import Path
import sys

# sys.path shim so this module can be imported when tools/ is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import http_get

FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
DEI_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/{concept}.json"
# v0.3.2 #11 — ifrs-full taxonomy endpoint. Foreign 20-F/40-F filers tag financials under
# ifrs-full instead of us-gaap; companyconcept exposes them on this taxonomy path. Extending the
# concept cascade to probe these recovers SOME foreign filers (graceful — absent -> empty, no crash).
IFRS_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/ifrs-full/{concept}.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Revenue concepts in priority order (earlier = lower priority, later = higher priority / overrides).
# IncludingAssessedTax added: many companies (e.g. BUKS fiscal-year != CY) switched to this
# after the 2018 ASC 606 adoption, while Revenues stopped being updated.
REVENUE_CONCEPTS = [
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
]

# v0.3.2 #11 — IFRS (ifrs-full taxonomy) concept cascade for foreign 20-F/40-F filers. Whole
# 20-F/40-F cohorts (Canadian PM juniors, China VIEs, foreign industrials) returned EMPTY
# financials because their XBRL is tagged under ifrs-full, not us-gaap. Probing the most common
# IFRS tags recovers SOME of these filers (graceful: absent concepts -> empty, never a crash).
# Each list is probed AFTER the us-gaap cascade and merged by end-date (us-gaap wins on a tie,
# IFRS only fills genuine gaps) — see concept_series_with_ifrs.
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

# v0.3.2 #8 — lessor / leasing-business detection. Asset-heavy lessors (railcar/equipment/auto
# leasing) carry a huge lease fleet on the balance sheet but modest, deeply cyclical FCF, so they
# belong on a lease-fleet NAV basis. They fell BELOW valuation's debt/assets>0.62
# fcf_cap_model_unsuitable threshold (GBX 0.41, RAIL 0.35) and were mis-valued on trough FCF.
# deepdive emits lessor_asset_heavy; valuation forces fcf_cap_model_unsuitable=True (-> NAV) on it
# even when debt/assets<0.62.
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
# Empirical: WLFC uses only LongTermDebt (no split); LNN uses both split concepts.
# C1a: additional concepts in the cascade to reduce debt truncation (FTAI uses SeniorNotes/TermLoans)
DEBT_CONCEPTS_PRIMARY = ["LongTermDebtNoncurrent", "LongTermDebtCurrent"]
DEBT_CONCEPT_FALLBACK1 = "LongTermDebt"
DEBT_CONCEPT_FALLBACK1B = "LongTermDebtAndCapitalLeaseObligations"
DEBT_CONCEPT_FALLBACK1C = "DebtLongtermAndShorttermCombinedAmount"
DEBT_CONCEPT_FALLBACK2 = "Liabilities"

# v0.3.1 #2 — SUM the standard debt concepts at Level 1 instead of picking a single/partial tag.
# Picking one liability concept under-read debt and was the #1 driver of cross_source_mismatch.
# Level 1 now SUMs (per end-date) the noncurrent + current long-term debt + short-term borrowings
# + finance-lease components. Each summand is optional (absent concepts contribute 0); the level
# fires when ANY summand is present.
DEBT_SUM_CONCEPTS = [
    "LongTermDebtNoncurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "FinanceLeaseLiabilityNoncurrent",
    "FinanceLeaseLiabilityCurrent",
]

# v0.3.1 #3 — ASC842 operating-lease liability concepts. cross_source_mismatch over-fires on
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

# D&A concepts in priority order: DepreciationDepletionAndAmortization is most common;
# DepreciationAndAmortization is a widely-used alternative (LNN uses this, WLFC uses both).
# DepreciationAmortizationAndAccretionNet: rare, used by financial services firms.
DA_CONCEPTS = [
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationDepletionAndAmortization",
]

# CapEx: standard XBRL concept; present for WLFC and LNN.
CAPEX_CONCEPT = "PaymentsToAcquirePropertyPlantAndEquipment"

# P9 — EBIT concept cascade. ~47% of names had null EV/EBITDA because EBIT was a single
# OperatingIncomeLoss pull (banks/insurers, IFRS filers, some industrials don't tag it).
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

# A3 — insurance XBRL concepts. Presence of ANY of these signals an insurance underwriter /
# insurance-subsidiary holdco even when the SIC is non-financial (e.g. Boston Omaha SIC-65 owns a
# surety-insurance sub). valuation reads insurance_concepts_present and routes such names like a
# financial_sic (nav/abstain) instead of fcf_cap, closing the BOC latent hole.
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


# PIT (backtest, FIX 1) — as-of filed-date accumulator. When a point-in-time pull runs (asof set),
# _one_concept records the max "filed" date of the facts it actually KEPT (filed<=asof, the latest-
# filed-per-end-date disclosures an investor at `asof` could have seen) into this module-level
# accumulator. deepdive_data.pull() resets it before its as-of cascade and reads it back after, so
# derived.asof_max_filing_date reflects the newest filing date that fed ANY concept value used in the
# point-in-time reconstruction. This is what makes the look-ahead audit NON-vacuous (the harness
# asserts asof_max_filing_date <= asof). The accumulator is process-global but ALWAYS reset by the
# caller via reset_asof_filed_tracker() at the top of an as-of pull, so concurrent live (asof=None)
# pulls — which NEVER touch it — cannot corrupt it. The asof=None path does not record anything, so
# the live default stays byte-identical.
_asof_max_filed: str | None = None


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


def _one_concept(cik: str, concept: str, taxonomy: str = "us-gaap", asof: str | None = None) -> list:
    """拉单个 XBRL 概念的年度序列。

    Annual selection: prefer entries where fp=='FY' AND form starts with '10-K'.
    Secondary guard: for flow concepts (revenue/income) with start+end dates, also accept
    day-span 330-400 as fallback when fp/form fields are absent.
    Instant concepts (balance-sheet items without 'start') are always included.

    Same end-date dedup within one concept: last entry in API response order wins,
    which aligns with EDGAR ordering (restated/amended values appear after originals).

    PIT (backtest) — `asof` (a YYYY-MM-DD string) makes this a point-in-time pull:
      * each companyconcept fact carries its own "filed" date in the JSON; keep ONLY facts
        with filed <= asof (drops facts disclosed after the as-of date — no look-ahead);
      * per end-date, pick the LATEST-FILED fact <= asof (the most recent disclosure that an
        investor standing at `asof` could have seen — restatements filed after asof are ignored).
    `asof=None` is the live default: behavior is BYTE-IDENTICAL to the pre-PIT code path (the
    asof block is never entered, dedup stays "last in API order wins"). A fact missing a "filed"
    field is conservatively DROPPED in the asof path (cannot be dated <= T safely).
    """
    if taxonomy == "us-gaap":
        url = FACTS.format(cik=str(cik).zfill(10), concept=concept)
    elif taxonomy == "ifrs-full":  # v0.3.2 #11 — foreign-filer IFRS concept recovery
        url = IFRS_FACTS.format(cik=str(cik).zfill(10), concept=concept)
    else:
        url = DEI_FACTS.format(cik=str(cik).zfill(10), concept=concept)
    try:
        r = http_get(url, timeout=20)
        if r.status_code != 200:
            return []
        units = r.json().get("units", {})
        vals = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        from datetime import date
        if asof is None:
            # --- LIVE DEFAULT PATH (byte-identical to pre-PIT behavior) ---
            seen_end: dict = {}  # dedup by end date; last wins (restated overrides original)
            for v in vals:
                if "start" in v and "end" in v:
                    try:
                        s = date.fromisoformat(v["start"])
                        e = date.fromisoformat(v["end"])
                        days = (e - s).days
                        fp = v.get("fp", "")
                        form = v.get("form", "")
                        # Accept: fp==FY AND form is annual (10-K or 10-K/A)
                        is_annual_tagged = (fp == "FY" and form.startswith("10-K"))
                        # Fallback: day span ~annual when tags absent
                        is_annual_span = (330 <= days <= 400)
                        if is_annual_tagged or is_annual_span:
                            seen_end[v["end"]] = {
                                "end": v["end"], "val": v["val"],
                                "fy": v.get("fy"), "fp": fp, "form": form,
                            }
                    except Exception:
                        pass
                elif "end" in v:  # instant (balance-sheet item — no start date)
                    seen_end[v["end"]] = {"end": v["end"], "val": v["val"], "fy": v.get("fy")}
            return list(seen_end.values())
        # --- PIT (as-of) PATH — filed<=asof, latest-filed-per-end-date wins ---
        seen_pit: dict = {}  # end-date -> {entry, _filed} ; keep the latest-filed <= asof
        for v in vals:
            filed = v.get("filed")
            if not filed or filed > asof:  # drop undated or future-filed facts (no look-ahead)
                continue
            if "start" in v and "end" in v:
                try:
                    s = date.fromisoformat(v["start"])
                    e = date.fromisoformat(v["end"])
                    days = (e - s).days
                    fp = v.get("fp", "")
                    form = v.get("form", "")
                    is_annual_tagged = (fp == "FY" and form.startswith("10-K"))
                    is_annual_span = (330 <= days <= 400)
                    if not (is_annual_tagged or is_annual_span):
                        continue
                    entry = {
                        "end": v["end"], "val": v["val"],
                        "fy": v.get("fy"), "fp": fp, "form": form,
                    }
                except Exception:
                    continue
            elif "end" in v:  # instant (balance-sheet item — no start date)
                entry = {"end": v["end"], "val": v["val"], "fy": v.get("fy")}
            else:
                continue
            prev = seen_pit.get(v["end"])
            # Latest-filed wins; tie on filed -> later API-order wins (mirrors live dedup).
            if prev is None or filed >= prev["_filed"]:
                seen_pit[v["end"]] = {"_filed": filed, "entry": entry}
        # FIX 1 — record the max "filed" date of the facts actually KEPT (the latest-filed-per-end
        # disclosures that feed the returned values). This is the look-ahead-audit evidence: every
        # recorded date is, by construction, <= asof. Live (asof=None) path never reaches here.
        for x in seen_pit.values():
            _record_asof_filed(x["_filed"])
        return [x["entry"] for x in seen_pit.values()]
    except Exception:
        return []


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
    # us-gaap first (preferred — domestic taxonomy).
    for concept in gaap_concepts:
        for a in _one_concept(cik, concept, taxonomy="us-gaap", asof=asof):
            seen[a["end"]] = a
        time.sleep(0.15)
    # ifrs-full second — fill gaps only; do NOT overwrite a us-gaap value at the same end-date.
    for concept in ifrs_concepts:
        for a in _one_concept(cik, concept, taxonomy="ifrs-full", asof=asof):
            if a["end"] not in seen:
                seen[a["end"]] = a
        time.sleep(0.15)
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


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


# C1 — company_tickers.json cache (fetched once per process; keyed by ticker uppercase)
_sec_tickers_cache: dict | None = None


def _get_sec_tickers() -> dict:
    """Fetch and cache SEC company_tickers.json (ticker→{cik, title}).

    Returns dict keyed by UPPER-CASE ticker symbol.
    On network failure returns empty dict (caller treats as inconclusive).
    """
    global _sec_tickers_cache
    if _sec_tickers_cache is not None:
        return _sec_tickers_cache
    try:
        r = http_get(SEC_COMPANY_TICKERS_URL, timeout=20)
        if r.status_code != 200:
            _sec_tickers_cache = {}
            return {}
        raw = r.json()
        # raw is { "0": {cik_str, ticker, title}, "1": ... }
        result: dict = {}
        for entry in raw.values():
            t = str(entry.get("ticker", "")).upper()
            if t:
                result[t] = {
                    "cik": str(entry.get("cik_str", "")).zfill(10),
                    "title": entry.get("title", ""),
                }
        _sec_tickers_cache = result
        return result
    except Exception:
        _sec_tickers_cache = {}
        return {}


def _debt_series(cik: str, n: int = 8, asof: str | None = None) -> tuple[list, str]:
    """Pull total debt series using a multi-level fallback chain.

    Level 1 (v0.3.1 #2): SUM the standard debt concepts per end-date instead of picking a single
             partial-liability tag. Summands (each optional, absent -> 0):
               LongTermDebtNoncurrent + LongTermDebtCurrent + ShortTermBorrowings
               + FinanceLeaseLiabilityNoncurrent + FinanceLeaseLiabilityCurrent
             Fires when ANY summand is present. This was the #1 driver of cross_source_mismatch:
             a single concept under-read total debt for levered issuers / lease-heavy filers.
    Level 2: LongTermDebt aggregate (single concept).
             Used when ALL Level-1 summand concepts return empty.
    Level 3: Liabilities (total liabilities as proxy).
             Used only when Level 1 and Level 2 return empty.

    Returns (series, fallback_label) where fallback_label documents which level was used.
    Series entries: {"end": date_str, "val": amount}.

    The implied-debt fallback for EV (when the summed debt is still < 0.5 * implied) is applied
    downstream in _debt_for_ev(), not here — _debt_series stays the raw reported-debt series.

    Empirical notes:
    - WLFC (CIK 1018164): only LongTermDebt available (no split), Level 2 applies.
    - LNN (CIK 836157): both split concepts available, Level 1 applies.
    """
    # Level 1 (v0.3.1 #2): SUM all standard debt concepts per end-date.
    merged: dict = {}
    any_summand = False
    for concept in DEBT_SUM_CONCEPTS:
        entries = _one_concept(cik, concept, asof=asof)
        time.sleep(0.15)
        if entries:
            any_summand = True
            for v in entries:
                if v.get("val") is not None:
                    merged[v["end"]] = merged.get(v["end"], 0) + v["val"]
    if any_summand:
        series = [{"end": k, "val": v} for k, v in sorted(merged.items())]
        return series[-n:], "+".join(DEBT_SUM_CONCEPTS)

    # Level 2: LongTermDebt aggregate
    lt_debt = _one_concept(cik, DEBT_CONCEPT_FALLBACK1, asof=asof)
    time.sleep(0.15)
    if lt_debt:
        series = [{"end": v["end"], "val": v["val"]} for v in lt_debt]
        return series[-n:], "LongTermDebt"

    # Level 2b: LongTermDebtAndCapitalLeaseObligations (C1a: catches FTAI-style filers)
    lt_debt_lease = _one_concept(cik, DEBT_CONCEPT_FALLBACK1B, asof=asof)
    time.sleep(0.15)
    if lt_debt_lease:
        series = [{"end": v["end"], "val": v["val"]} for v in lt_debt_lease]
        return series[-n:], "LongTermDebtAndCapitalLeaseObligations"

    # Level 2c: DebtLongtermAndShorttermCombinedAmount (C1a: catches combined reporters)
    lt_debt_combined = _one_concept(cik, DEBT_CONCEPT_FALLBACK1C, asof=asof)
    time.sleep(0.15)
    if lt_debt_combined:
        series = [{"end": v["end"], "val": v["val"]} for v in lt_debt_combined]
        return series[-n:], "DebtLongtermAndShorttermCombinedAmount"

    # Level 3: total Liabilities (proxy; note this in derived)
    liabilities = _one_concept(cik, DEBT_CONCEPT_FALLBACK2, asof=asof)
    time.sleep(0.15)
    if liabilities:
        series = [{"end": v["end"], "val": v["val"]} for v in liabilities]
        return series[-n:], "Liabilities_proxy"

    return [], "unavailable"


def _da_series(cik: str, n: int = 8, asof: str | None = None) -> tuple[list, str]:
    """Pull depreciation & amortization series using multi-concept merge.

    Priority chain (later overrides earlier for same end date):
    1. DepreciationAndAmortization
    2. DepreciationAmortizationAndAccretionNet
    3. DepreciationDepletionAndAmortization

    Returns (series, fallback_label) describing which concepts provided data.
    Empirical: WLFC has both DA and DDA; LNN has only DA.

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
                seen[v["end"]] = {"end": v["end"], "val": v["val"]}
    series = sorted(seen.values(), key=lambda x: x["end"])[-n:]
    label = "+".join(found_concepts) if found_concepts else "unavailable"
    return series, label


def _ebit_with_source(cik: str, op_income_series: list, n: int = 8,
                      asof: str | None = None) -> tuple[list, str | None]:
    """P9 — EBIT concept cascade with `ebit_source` tagging.

    Recovers an EBIT series for the ~47% of names that don't tag OperatingIncomeLoss
    (banks/insurers, IFRS filers, some industrials), so EV/EBITDA can compute.

    Cascade (each path tagged):
      1. OperatingIncomeLoss                              -> ebit_source="OperatingIncomeLoss"
      2. PretaxContinuingOps + interest expense addback   -> ebit_source="pretax+interest_addback"
      3. PretaxContinuingOps (no interest available)      -> ebit_source="pretax_proxy"

    Returns (series, ebit_source). series entries: {"end", "val"}.
    ebit_source is None when nothing recovers (caller leaves ebit empty).
    The pretax addback is matched by end date; interest is added back (interest reduces
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
        int_map = {v["end"]: v["val"] for v in interest}
        series = []
        any_addback = False
        for v in pretax:
            iv = int_map.get(v["end"])
            if iv is not None:
                series.append({"end": v["end"], "val": v["val"] + iv})
                any_addback = True
            else:
                series.append({"end": v["end"], "val": v["val"]})
        if any_addback:
            return series[-n:], "pretax+interest_addback"

    # Path 3: pretax proxy (no interest series to add back)
    series = [{"end": v["end"], "val": v["val"]} for v in pretax]
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
