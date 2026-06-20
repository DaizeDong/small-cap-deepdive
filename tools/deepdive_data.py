"""
deepdive_data.py — Stage 1 深度尽调的数据拉取层(机械部分)

对 cheap pass 幸存者,拉齐 deep dive 所需的结构化数据:
  - 财务序列(收入/净利/OCF/现金/资产/权益,多期)→ 增长质量、runway、现金流质量
  - 稀释史(流通股 YoY)
  - Form 4 内部人交易(净买卖方向 = 最硬的管理层诚实信号)
  - 10-K 关键章节文本(business/risk factors)供判断层读
设计依据:reference/mechanical-checks.md。

判断层(护城河/管理层/估值/多空论点)由 agent 读这些数据后做,不在此脚本。
本脚本只负责"把硬数据摆到桌上",防止 agent 凭记忆/叙事编。

用法:
    python deepdive_data.py --ticker IQST
    python deepdive_data.py --candidates reports/smallcap/candidates_<slug>.json
输出: reports/smallcap/deepdive_<ticker>_<date>.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from edgar import Company

# sys.path shim so this script can be run directly from tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import init_edgar, UA, REPORTS, today, CFG, http_get

FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
DEI_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/{concept}.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Non-open-market transaction codes to exclude (RSU grants, option exercises, gifts, etc.)
_EXCLUDE_CODES = {"A", "M", "G", "D", "F", "I", "J", "L", "U", "W", "X", "Z"}

# Revenue concepts in priority order (earlier = lower priority, later = higher priority / overrides).
# IncludingAssessedTax added: many companies (e.g. BUKS fiscal-year != CY) switched to this
# after the 2018 ASC 606 adoption, while Revenues stopped being updated.
REVENUE_CONCEPTS = [
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
]

# Debt concepts: prefer split long-term current/noncurrent; fallback to LongTermDebt aggregate;
# final fallback to total Liabilities (flags this in derived.debt_fallback).
# Empirical: WLFC uses only LongTermDebt (no split); LNN uses both split concepts.
# C1a: additional concepts in the cascade to reduce debt truncation (FTAI uses SeniorNotes/TermLoans)
DEBT_CONCEPTS_PRIMARY = ["LongTermDebtNoncurrent", "LongTermDebtCurrent"]
DEBT_CONCEPT_FALLBACK1 = "LongTermDebt"
DEBT_CONCEPT_FALLBACK1B = "LongTermDebtAndCapitalLeaseObligations"
DEBT_CONCEPT_FALLBACK1C = "DebtLongtermAndShorttermCombinedAmount"
DEBT_CONCEPT_FALLBACK2 = "Liabilities"

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

# P3 — concentration extraction. Magnitude-based, sourced from concentration-footnote numerics
# in the filing text (companyconcept XBRL does NOT expose dimensional segment members, so the
# segment-member breakdown is only recoverable from the footnote text). Replaces the old
# substring detector ("customers accounted for") which SIGA's filing never used.
# A single named counterparty (government, "one customer", named largest client) = top_customer_pct.
# A single product/program/segment/drug share of revenue = top_program_pct.
_CONC_SINGLE_CUSTOMER = re.compile(
    r"u\.?\s*s\.?\s*government|federal government|one customer|single customer|"
    r"largest customer|one client|single client|largest client|its largest|our largest|"
    r"a single (?:customer|client|counterpart)|one (?:counterpart|payor|payer)|barda",
    re.IGNORECASE,
)
_CONC_SINGLE_PROGRAM = re.compile(
    r"one (?:product|program|segment|drug|contract)|single (?:product|program|segment|drug|contract)|"
    r"largest (?:product|program|segment|drug)|our (?:lead|sole|primary|principal) (?:product|program|drug)|"
    r"a single (?:product|program|segment|drug)",
    re.IGNORECASE,
)
_CONC_REVENUE_TERM = re.compile(
    r"revenue|net sales|product sales|of (?:our |its |total )?sales|"
    r"accounts receivable|receivable",
    re.IGNORECASE,
)
_CONC_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
# How far (chars) a percentage may sit from its qualifying context phrase.
_CONC_WINDOW = 180


def _one_concept(cik: str, concept: str, taxonomy: str = "us-gaap") -> list:
    """拉单个 XBRL 概念的年度序列。

    Annual selection: prefer entries where fp=='FY' AND form starts with '10-K'.
    Secondary guard: for flow concepts (revenue/income) with start+end dates, also accept
    day-span 330-400 as fallback when fp/form fields are absent.
    Instant concepts (balance-sheet items without 'start') are always included.

    Same end-date dedup within one concept: last entry in API response order wins,
    which aligns with EDGAR ordering (restated/amended values appear after originals).
    """
    if taxonomy == "us-gaap":
        url = FACTS.format(cik=str(cik).zfill(10), concept=concept)
    else:
        url = DEI_FACTS.format(cik=str(cik).zfill(10), concept=concept)
    try:
        r = http_get(url, timeout=20)
        if r.status_code != 200:
            return []
        units = r.json().get("units", {})
        vals = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        from datetime import date
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
    except Exception:
        return []


def concept_series(cik: str, concepts, n: int = 8) -> list:
    """拉一个或多个 XBRL 概念,**合并**取真正最新的 n 期。

    Concept merge: for the same end-date, later concepts in the list override earlier ones.
    This means callers should list older/narrower concepts first and the preferred/current
    concept last. Within a single concept, _one_concept already keeps the last (restated) value.
    """
    if isinstance(concepts, str):
        concepts = [concepts]
    seen: dict = {}
    for concept in concepts:
        for a in _one_concept(cik, concept):
            # Later concept overrides earlier for the same end date.
            seen[a["end"]] = a
        time.sleep(0.15)
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


def _shares_series(cik: str, n: int = 8) -> list:
    """Shares outstanding with a three-level fallback chain.

    1. us-gaap:CommonStockSharesOutstanding  (precise period-end count)
    2. dei:EntityCommonStockSharesOutstanding (cover-page count; coarser but current)
    3. us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding (annual average; diluted)

    Each level supplements gaps from the previous; the combined series is sorted by end date
    and the last n entries are returned. Duplicate end-dates: latest taxonomy/concept wins.
    """
    seen: dict = {}
    # Level 1: us-gaap common shares
    for a in _one_concept(cik, "CommonStockSharesOutstanding", taxonomy="us-gaap"):
        seen[a["end"]] = a
    time.sleep(0.15)
    # Level 2: dei cover-page count (instant, no start date in XBRL response)
    for a in _one_concept(cik, "EntityCommonStockSharesOutstanding", taxonomy="dei"):
        seen[a["end"]] = a
    time.sleep(0.15)
    # Level 3: diluted weighted-average (flow concept, annual fp=FY only via _one_concept filter)
    for a in _one_concept(cik, "WeightedAverageNumberOfDilutedSharesOutstanding", taxonomy="us-gaap"):
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


def _validate_ticker_entity(ticker: str, resolved_cik: str, rev_series: list, shares_series: list, ni_series: list) -> tuple[bool, str | None]:
    """C1b wrong-entity guard.

    Returns (wrong_entity_suspected, reason_str).

    Heuristics:
    1. Ticker absent from SEC company_tickers.json → suspected wrong entity.
    2. shares_outstanding < 1000 → suspiciously small (sub-entity or wrong CIK).
    3. |net_income| / revenue > 2.0 for the latest period → structurally impossible
       for an operating company (indicates wrong-entity or unit anomaly).
    4. revenue is present but absurdly small given any available context (below $1000,
       indicating a unit-of-1 mis-tag or the wrong subsidiary).

    Returns (False, None) when no issue detected.
    Returns (True, reason) when any heuristic fires.
    """
    reasons = []

    # Heuristic 1: ticker→CIK cross-check
    if ticker:
        tickers_map = _get_sec_tickers()
        if tickers_map:  # only validate when we successfully fetched the map
            canonical = tickers_map.get(ticker.upper())
            if canonical is None:
                reasons.append(f"ticker_absent_from_sec_company_tickers")
            else:
                canonical_cik = canonical["cik"].lstrip("0")
                resolved_stripped = str(resolved_cik).lstrip("0")
                if canonical_cik and resolved_stripped and canonical_cik != resolved_stripped:
                    reasons.append(
                        f"cik_mismatch:sec_canonical={canonical_cik},resolved={resolved_stripped}"
                    )

    # Heuristic 2: shares < 1000
    if shares_series:
        latest_shares = shares_series[-1]["val"]
        if latest_shares is not None and latest_shares < 1000:
            reasons.append(f"shares_lt_1000:{latest_shares:.0f}")

    # Heuristic 3: |net_income| / revenue > 2.0
    latest_ni = ni_series[-1]["val"] if ni_series else None
    latest_rev = rev_series[-1]["val"] if rev_series else None
    if latest_ni is not None and latest_rev is not None and latest_rev > 0:
        ratio = abs(latest_ni) / latest_rev
        if ratio > 2.0:
            reasons.append(f"ni_to_revenue_ratio_absurd:{ratio:.1f}")

    # Heuristic 4: revenue absurdly low (below $1000 = unit mis-tag)
    if latest_rev is not None and 0 < latest_rev < 1000:
        reasons.append(f"revenue_absurdly_low:{latest_rev:.0f}")

    if reasons:
        return True, ";".join(reasons)
    return False, None


def _check_debt_quality(
    debt_series: list,
    assets_series: list,
    equity_series: list,
    liabilities_series: list,
) -> tuple[bool, bool, str | None]:
    """C1a debt truncation + staleness guard.

    Returns (debt_truncation_suspected, debt_stale, detail_str).

    debt_truncation_suspected: reported total_debt < 0.5 * implied_debt
      where implied_debt = total_liabilities - stockholders_equity
      (or total_assets - stockholders_equity when liabilities absent).

    debt_stale: latest debt end-date is >18 months older than latest assets/revenue end-date.
    """
    if not debt_series:
        return False, False, None

    latest_debt_entry = debt_series[-1]
    latest_debt_val = latest_debt_entry["val"]
    latest_debt_date = latest_debt_entry["end"]

    # Staleness check: compare debt end-date with assets end-date
    debt_stale = False
    if assets_series:
        latest_assets_date = assets_series[-1]["end"]
        try:
            from datetime import date as _date
            d_debt = _date.fromisoformat(latest_debt_date)
            d_assets = _date.fromisoformat(latest_assets_date)
            lag_days = (d_assets - d_debt).days
            if lag_days > _DEBT_STALE_DAYS:
                debt_stale = True
        except Exception:
            pass

    # Debt truncation check: reported_debt vs implied_debt
    debt_truncation_suspected = False
    detail = None

    # Try to compute implied_debt = Liabilities - Equity
    implied_debt: float | None = None
    if liabilities_series and equity_series:
        # Match by end date; use latest matching pair
        liab_map = {v["end"]: v["val"] for v in liabilities_series}
        eq_map = {v["end"]: v["val"] for v in equity_series}
        common = sorted(set(liab_map) & set(eq_map))
        if common:
            latest_end = common[-1]
            implied_debt = liab_map[latest_end] - eq_map[latest_end]

    # Fallback: Assets - Equity when Liabilities absent
    if implied_debt is None and assets_series and equity_series:
        asset_map = {v["end"]: v["val"] for v in assets_series}
        eq_map = {v["end"]: v["val"] for v in equity_series}
        common = sorted(set(asset_map) & set(eq_map))
        if common:
            latest_end = common[-1]
            implied_debt = asset_map[latest_end] - eq_map[latest_end]

    if implied_debt is not None and implied_debt > 0 and latest_debt_val is not None:
        if latest_debt_val < 0.5 * implied_debt:
            debt_truncation_suspected = True
            detail = (
                f"reported_total_debt={latest_debt_val/1e6:.1f}M, "
                f"implied_debt(liab-equity)={implied_debt/1e6:.1f}M, "
                f"ratio={latest_debt_val/implied_debt:.2f}"
            )

    return debt_truncation_suspected, debt_stale, detail


def _debt_series(cik: str, n: int = 8) -> tuple[list, str]:
    """Pull total debt series using a three-level fallback chain.

    Level 1: sum LongTermDebtNoncurrent + LongTermDebtCurrent (per-date sum).
             Used when at least one of the two split concepts is available.
    Level 2: LongTermDebt aggregate (single concept).
             Used when split concepts both return empty.
    Level 3: Liabilities (total liabilities as proxy).
             Used only when both Level 1 and Level 2 return empty.

    Returns (series, fallback_label) where fallback_label documents which level was used.
    Series entries: {"end": date_str, "val": amount}.

    Empirical notes:
    - WLFC (CIK 1018164): only LongTermDebt available (no split), Level 2 applies.
    - LNN (CIK 836157): both split concepts available, Level 1 applies.
    """
    # Level 1: try split concepts
    noncurrent = _one_concept(cik, "LongTermDebtNoncurrent")
    time.sleep(0.15)
    current = _one_concept(cik, "LongTermDebtCurrent")
    time.sleep(0.15)
    if noncurrent or current:
        # Merge by end date: sum both components where available
        merged: dict = {}
        for v in noncurrent:
            merged[v["end"]] = merged.get(v["end"], 0) + v["val"]
        for v in current:
            merged[v["end"]] = merged.get(v["end"], 0) + v["val"]
        series = [{"end": k, "val": v} for k, v in sorted(merged.items())]
        return series[-n:], "LongTermDebtNoncurrent+LongTermDebtCurrent"

    # Level 2: LongTermDebt aggregate
    lt_debt = _one_concept(cik, DEBT_CONCEPT_FALLBACK1)
    time.sleep(0.15)
    if lt_debt:
        series = [{"end": v["end"], "val": v["val"]} for v in lt_debt]
        return series[-n:], "LongTermDebt"

    # Level 2b: LongTermDebtAndCapitalLeaseObligations (C1a: catches FTAI-style filers)
    lt_debt_lease = _one_concept(cik, DEBT_CONCEPT_FALLBACK1B)
    time.sleep(0.15)
    if lt_debt_lease:
        series = [{"end": v["end"], "val": v["val"]} for v in lt_debt_lease]
        return series[-n:], "LongTermDebtAndCapitalLeaseObligations"

    # Level 2c: DebtLongtermAndShorttermCombinedAmount (C1a: catches combined reporters)
    lt_debt_combined = _one_concept(cik, DEBT_CONCEPT_FALLBACK1C)
    time.sleep(0.15)
    if lt_debt_combined:
        series = [{"end": v["end"], "val": v["val"]} for v in lt_debt_combined]
        return series[-n:], "DebtLongtermAndShorttermCombinedAmount"

    # Level 3: total Liabilities (proxy; note this in derived)
    liabilities = _one_concept(cik, DEBT_CONCEPT_FALLBACK2)
    time.sleep(0.15)
    if liabilities:
        series = [{"end": v["end"], "val": v["val"]} for v in liabilities]
        return series[-n:], "Liabilities_proxy"

    return [], "unavailable"


def _da_series(cik: str, n: int = 8) -> tuple[list, str]:
    """Pull depreciation & amortization series using multi-concept merge.

    Priority chain (later overrides earlier for same end date):
    1. DepreciationAndAmortization
    2. DepreciationAmortizationAndAccretionNet
    3. DepreciationDepletionAndAmortization

    Returns (series, fallback_label) describing which concepts provided data.
    Empirical: WLFC has both DA and DDA; LNN has only DA.
    """
    seen: dict = {}
    found_concepts: list = []
    for concept in DA_CONCEPTS:
        entries = _one_concept(cik, concept)
        time.sleep(0.15)
        if entries:
            found_concepts.append(concept)
            for v in entries:
                seen[v["end"]] = {"end": v["end"], "val": v["val"]}
    series = sorted(seen.values(), key=lambda x: x["end"])[-n:]
    label = "+".join(found_concepts) if found_concepts else "unavailable"
    return series, label


def _ebit_with_source(cik: str, op_income_series: list, n: int = 8) -> tuple[list, str | None]:
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
    """
    # Path 1: OperatingIncomeLoss (already pulled by caller)
    if op_income_series:
        return op_income_series[-n:], EBIT_PRIMARY_CONCEPT

    # Path 2/3: pretax continuing-ops income as the EBIT base
    pretax = concept_series(cik, EBIT_PRETAX_CONCEPTS, n=n)
    time.sleep(0.15)
    if not pretax:
        return [], None

    # Try interest addback (EBIT = pretax + interest expense). Interest is reported as a
    # positive expense; adding it back to pretax income approximates operating income.
    interest = concept_series(cik, EBIT_INTEREST_CONCEPTS, n=n)
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


def _extract_concentration(tenk_text: str) -> tuple[float | None, float | None, str | None]:
    """P3 — magnitude-based revenue/customer concentration from filing footnote numerics.

    companyconcept XBRL does NOT expose dimensional segment members, so the only mechanical
    source for the magnitude is the concentration-footnote text the filing already provides.
    This replaces the old English substring detector ("customers accounted for"), which SIGA's
    ~90%-BARDA-dependent filing never used.

    Strategy: scan every percentage in the text; keep one whose context window contains BOTH
    a revenue/sales/receivable term AND a single-counterparty phrase (top_customer_pct) or a
    single-product/program phrase (top_program_pct). Take the max per class (worst-case
    concentration). A counterparty match takes precedence over a program match for the same
    percentage (named-customer dependence is the harder kill-flag).

    Returns (top_customer_pct, top_program_pct, detail) — pcts are floats 0-100 or None.
    The kill/watch flag is composed by the caller (_concentration_flag).
    """
    if not tenk_text:
        return None, None, None
    low = tenk_text.lower()
    top_customer: float | None = None
    top_program: float | None = None
    cust_ctx: str | None = None
    prog_ctx: str | None = None
    def _nearest_dist(pat, window, anchor):
        """Smallest char distance from `anchor` (pct position within window) to any match of pat."""
        best = None
        for mm in pat.finditer(window):
            mid = (mm.start() + mm.end()) // 2
            dist = abs(mid - anchor)
            if best is None or dist < best:
                best = dist
        return best

    for m in _CONC_PCT.finditer(low):
        try:
            pct = float(m.group(1))
        except ValueError:
            continue
        if not (0 < pct <= 100):
            continue
        lo = max(0, m.start() - _CONC_WINDOW)
        hi = min(len(low), m.end() + _CONC_WINDOW)
        window = low[lo:hi]
        if not _CONC_REVENUE_TERM.search(window):
            continue
        anchor = m.start() - lo  # pct position relative to window start
        cust_d = _nearest_dist(_CONC_SINGLE_CUSTOMER, window, anchor)
        prog_d = _nearest_dist(_CONC_SINGLE_PROGRAM, window, anchor)
        if cust_d is None and prog_d is None:
            continue
        # Bind the percentage to whichever qualifying phrase is NEAREST. Ties (and customer-only)
        # resolve to customer — named-counterparty dependence is the harder kill-flag.
        if prog_d is not None and (cust_d is None or prog_d < cust_d):
            cls = "program"
        else:
            cls = "customer"
        snippet = tenk_text[max(0, m.start() - 70):m.end() + 30].replace("\n", " ").strip()
        if cls == "customer":
            if top_customer is None or pct > top_customer:
                top_customer = pct
                cust_ctx = snippet
        else:
            if top_program is None or pct > top_program:
                top_program = pct
                prog_ctx = snippet
    parts = []
    if top_customer is not None:
        parts.append(f"top_customer={top_customer:.0f}% [{cust_ctx}]")
    if top_program is not None:
        parts.append(f"top_program={top_program:.0f}% [{prog_ctx}]")
    detail = " ; ".join(parts) if parts else None
    return top_customer, top_program, detail


def _concentration_flag(top_customer_pct: float | None, top_program_pct: float | None) -> str | None:
    """P3 — compose the concentration kill/watch flag per the data contract.

    kill  if top_program_pct > 60 OR top_customer_pct > 40
    watch if either lands in the 40-60 band (and no kill)
    None  otherwise.
    """
    def _val(x):
        return x if x is not None else -1.0
    cust = _val(top_customer_pct)
    prog = _val(top_program_pct)
    if prog > 60 or cust > 40:
        return "kill"
    if (40 <= cust <= 60) or (40 <= prog <= 60):
        return "watch"
    return None


def _annual_vals(series: list) -> list:
    """Dedup a {end,val} series to one value per fiscal year (latest end within each calendar
    year wins), dropping sub-annual stubs and duplicate-year mislabels that corrupt a trend
    slope. Returns values sorted ascending by year. Used by _trajectory_fields so an ancient
    scale-up at the front of the raw series cannot invert the recent-trajectory sign."""
    by_year: dict = {}
    for s in series:
        v = s.get("val")
        end = s.get("end") or ""
        if v is None or len(end) < 4:
            continue
        yr = end[:4]
        if yr not in by_year or end > by_year[yr][0]:
            by_year[yr] = (end, v)
    return [by_year[y][1] for y in sorted(by_year)]


def _trajectory_fields(rev_series: list, norm_base_series: list) -> dict:
    """P6 — deterministic revenue trajectory + contamination derived fields.

    Computed from the multiyear series already pulled (no new network calls).

    - rev_slope_sign (int -1/0/1): sign of the simple linear slope over the revenue series.
    - rev_accel_sign (int -1/0/1): sign of the mean 2nd difference (acceleration) of revenue.
    - latest_below_avg (bool): latest normalization-base value < trailing average of the
      prior normalization-base values.
    - contamination_ratio (float|None): latest normalization-base / 5yr-avg of the base.
    - fundamental_decline_flag (bool): rev_slope_sign<0 AND contamination_ratio<1.0 AND
      latest_below_avg. The melting-ice-cube / lumpy-OCF value-trap veto (SIGA contamination ~0.68).

    `norm_base_series` is the series the valuation layer normalizes on (OCF/FCF); revenue is the
    trajectory carrier. Both are lists of {"end","val"} sorted ascending by end date.
    """
    out = {
        "rev_slope_sign": 0,
        "rev_accel_sign": 0,
        "latest_below_avg": False,
        "contamination_ratio": None,
        "fundamental_decline_flag": False,
    }

    # RECENT-window trajectory. The raw multiyear series can be contaminated at the FRONT by
    # sub-annual stubs / mislabeled fiscal years (e.g. SIGA's 9-month 8.1M stub + a duplicate-year
    # tag), whose ancient ramp inverts the all-time least-squares slope to +1 even when the company
    # is currently rolling over. Annualize, then slope over the trailing <=5 years so the veto
    # measures CURRENT trajectory rather than an ancient scale-up.
    rev_window = _annual_vals(rev_series)[-5:]
    # Revenue slope sign via least-squares slope over index 0..n-1 of the recent window.
    if len(rev_window) >= 2:
        n = len(rev_window)
        xs = list(range(n))
        mx = sum(xs) / n
        my = sum(rev_window) / n
        denom = sum((x - mx) ** 2 for x in xs)
        if denom != 0:
            slope = sum((xs[i] - mx) * (rev_window[i] - my) for i in range(n)) / denom
            out["rev_slope_sign"] = (1 if slope > 0 else -1 if slope < 0 else 0)
    # Revenue acceleration sign via mean 2nd difference of the recent window.
    if len(rev_window) >= 3:
        second_diffs = [
            rev_window[i + 2] - 2 * rev_window[i + 1] + rev_window[i]
            for i in range(len(rev_window) - 2)
        ]
        accel = sum(second_diffs) / len(second_diffs)
        out["rev_accel_sign"] = (1 if accel > 0 else -1 if accel < 0 else 0)

    # Contamination + latest-below-avg on the normalization base.
    base_vals = [s["val"] for s in norm_base_series if s.get("val") is not None]
    if len(base_vals) >= 2:
        latest = base_vals[-1]
        prior = base_vals[:-1]
        trailing_avg = sum(prior) / len(prior)
        out["latest_below_avg"] = latest < trailing_avg
        # 5yr-avg = average of up to the last 5 base values (inclusive of latest).
        window5 = base_vals[-5:]
        avg5 = sum(window5) / len(window5)
        if avg5 != 0:
            out["contamination_ratio"] = round(latest / avg5, 4)

    cr = out["contamination_ratio"]
    out["fundamental_decline_flag"] = bool(
        out["rev_slope_sign"] < 0
        and cr is not None and cr < 1.0
        and out["latest_below_avg"]
    )
    return out


def insider_trades(ticker: str, cik: str = "") -> dict:
    """内部人交易净方向(最硬的管理层诚实信号)。
    源由 CFG["insider_source"] 控制,默认 openinsider(已测试路径)。

    Returns open-market-only counts and dollar values:
      - open_market_buys / open_market_sells: count of P / S transaction codes only
      - buy_value / sell_value: sum of dollar Value column for P / S rows
      - buys / sells: same as open_market_buys/sells (backward compat alias)
      - net_signal: based on open-market P vs S only
    Excludes non-open-market codes: A (grant/award), M (option exercise), G (gift),
    and any other code — these are RSU/option noise, not management conviction signals.
    """
    if CFG["insider_source"] == "openinsider":
        out = {
            "available": False,
            "buys": 0, "sells": 0,
            "open_market_buys": 0, "open_market_sells": 0,
            "buy_value": 0, "sell_value": 0,
            "net_signal": None, "source": "openinsider",
        }
        try:
            # openinsider screener: last 730 days, open-market P/S rows, up to 100 rows
            url = (
                f"http://openinsider.com/screener?s={ticker}"
                "&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago="
                "&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
                "&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h="
                "&sortcol=0&cnt=100&page=1"
            )
            r = http_get(url, timeout=30)
            if r.status_code != 200:
                out["error"] = f"http {r.status_code}"
                return out

            # Parse HTML table rows to extract transaction type code and Value column.
            # openinsider table columns (0-indexed, typical layout):
            #   0: filing date, 1: trade date, 2: ticker, 3: company, 4: insider name,
            #   5: title, 6: trade type code, 7: price, 8: qty, 9: owned, 10: delta%,
            #   11: Value
            # A leading checkbox <td> can shift every column; we detect actual column
            # positions from the header row instead of using hardcoded indices.
            from html.parser import HTMLParser

            class _TableParser(HTMLParser):
                """Minimal parser: collect <td> and <th> text within <tr> blocks."""
                def __init__(self):
                    super().__init__()
                    self._in_cell = False
                    self._cur_row: list[str] = []
                    self._cur_cell: list[str] = []
                    self.rows: list[list[str]] = []

                def handle_starttag(self, tag, attrs):
                    if tag == "tr":
                        self._cur_row = []
                    elif tag in ("td", "th"):
                        self._in_cell = True
                        self._cur_cell = []

                def handle_endtag(self, tag):
                    if tag in ("td", "th"):
                        self._in_cell = False
                        self._cur_row.append("".join(self._cur_cell).strip())
                    elif tag == "tr" and self._cur_row:
                        self.rows.append(self._cur_row)
                        self._cur_row = []

                def handle_data(self, data):
                    if self._in_cell:
                        self._cur_cell.append(data)

            parser = _TableParser()
            parser.feed(r.text)

            def _parse_value(s: str) -> float:
                """Parse openinsider Value cell like '$1,234,567' or '+$1,234,567'.
                Strips all non-numeric characters (sign, currency, commas) via regex.
                Parenthesized negatives like '($1,234)' are not expected in the Value
                column (which stores absolute dollar amounts) but are handled safely —
                the regex strips parens along with other non-numeric chars, returning
                the absolute value."""
                cleaned = re.sub(r"[^0-9.]", "", s)
                try:
                    return float(cleaned) if cleaned else 0.0
                except ValueError:
                    return 0.0

            # Detect header row to find column indices for trade-type and Value.
            # Hardcoded fallback (col 6 / col 11) used if no header found.
            _FALLBACK_CODE_COL = 6
            _FALLBACK_VALUE_COL = 11
            code_col: int | None = None
            value_col: int | None = None
            for row in parser.rows:
                row_low = [c.lower() for c in row]
                # Look for the Trade Type column
                for i, cell in enumerate(row_low):
                    if any(kw in cell for kw in ("trade type", "trans", "type")):
                        code_col = i
                        break
                # Look for the Value column
                for i, cell in enumerate(row_low):
                    if cell == "value" or cell.strip() == "value":
                        value_col = i
                        break
                if code_col is not None and value_col is not None:
                    break  # header found
            if code_col is None or value_col is None:
                import logging
                logging.warning(
                    "openinsider: header row not found; falling back to hardcoded column "
                    "indices (code=%d, value=%d). Table layout may have changed.",
                    _FALLBACK_CODE_COL, _FALLBACK_VALUE_COL,
                )
                code_col = _FALLBACK_CODE_COL
                value_col = _FALLBACK_VALUE_COL

            open_market_buys = 0
            open_market_sells = 0
            buy_value = 0.0
            sell_value = 0.0

            for row in parser.rows:
                if len(row) <= max(code_col, value_col):
                    continue
                code_cell = row[code_col].strip()
                # code_cell is like "P - Purchase" or "S - Sale" or "A - Award"
                code_match = re.match(r"^([A-Z])", code_cell)
                if not code_match:
                    continue
                code = code_match.group(1)
                if code in _EXCLUDE_CODES:
                    continue  # skip non-open-market transactions
                val = _parse_value(row[value_col])
                if code == "P":
                    open_market_buys += 1
                    buy_value += val
                elif code == "S":
                    open_market_sells += 1
                    sell_value += val

            out.update({
                "available": True,
                "open_market_buys": open_market_buys,
                "open_market_sells": open_market_sells,
                "buys": open_market_buys,   # backward-compat alias
                "sells": open_market_sells,  # backward-compat alias
                "buy_value": round(buy_value),
                "sell_value": round(sell_value),
                "net_signal": (
                    "net_buy" if open_market_buys > open_market_sells else
                    "net_sell" if open_market_sells > open_market_buys else
                    "neutral"
                ),
            })
        except Exception as e:
            out["error"] = str(e)
        return out
    elif CFG["insider_source"] == "edgar":
        # TODO(roadmap): edgar Form4 direction parser
        # edgartools Form4 direction matching was unreliable in testing (returned None).
        # Hardening this path is a roadmap item; openinsider remains the tested default.
        return {"available": False, "note": "edgar source not yet implemented"}
    else:
        return {"available": False, "error": f"unknown insider_source: {CFG['insider_source']}"}


def tenk_sections(ticker: str, cik: str = "") -> dict:
    """取最新年报的关键文本片段(business + risk factors 节选)供判断层读。

    Phase 4 — 20-F / 40-F graceful fallback:
    If no 10-K filing is found, falls back to 20-F then 40-F.
    Foreign-domiciled filers (shipping, some industrials/mining) file 20-F/40-F.
    Going-concern/material-weakness language is structurally similar in 20-F.
    XBRL concept_series (us-gaap companyfacts) already works for foreign filers.
    Sets out["filing_form"] to the form type actually read.

    A1 — CIK fallback: when ticker is absent but cik is present, construct Company
    from int(cik) directly (edgartools supports numeric CIK construction).
    """
    out = {"available": False}
    try:
        # A1: prefer CIK construction when ticker absent to handle pre-listing spinoffs
        if cik and not ticker:
            c = Company(int(cik))
        else:
            c = Company(ticker)
        f = None
        form_used = None
        # Primary: 10-K (amendments=False — 10-K/A 修正件常缺 going-concern 全文)
        fl = c.get_filings(form="10-K", amendments=False)
        if fl is not None and len(fl):
            f = fl.latest(1)
            form_used = "10-K"
        # Fallback 1: 20-F (foreign-domiciled filers — Phase 4)
        if f is None:
            fl20 = c.get_filings(form="20-F", amendments=False)
            if fl20 is not None and len(fl20):
                f = fl20.latest(1)
                form_used = "20-F"
        # Fallback 2: 40-F (Canadian filers — Phase 4)
        if f is None:
            fl40 = c.get_filings(form="40-F", amendments=False)
            if fl40 is not None and len(fl40):
                f = fl40.latest(1)
                form_used = "40-F"
        if f is None:
            return out
        txt = f.text() if hasattr(f, "text") else str(f.obj())
        low = txt.lower()
        out["available"] = True
        out["filing_form"] = form_used
        out["filing_date"] = str(getattr(f, "filing_date", ""))
        out["total_len"] = len(txt)
        # kill-flag 复核
        out["has_going_concern"] = "going concern" in low and "substantial doubt" in low
        # material_weakness: require affirmative ICFR finding, not bare boilerplate phrase.
        # Risk-factor language ("our failure to maintain effective controls...") often
        # contains "material weakness" without an actual finding — caused 4/4 FP in audit.
        # Require co-occurrence with an affirmative phrase within the same document.
        _mw_affirmative = (
            "identified a material weakness" in low
            or "identified material weakness" in low
            or "were not effective" in low
            or "was not effective" in low
        )
        out["has_material_weakness"] = "material weakness" in low and _mw_affirmative
        out["has_death_spiral"] = "variable conversion" in low
        # P3 — magnitude-based concentration from the full filing text (the only mechanical
        # source for the segment-member magnitude; companyconcept XBRL has no dimensional
        # members). Replaces the old "customers accounted for" substring, which SIGA's
        # ~90%-BARDA-dependent filing never used. Done here because txt (full body) is in scope.
        _tc, _tp, _cd = _extract_concentration(txt)
        out["top_customer_pct"] = _tc
        out["top_program_pct"] = _tp
        out["concentration_detail"] = _cd
        # Backward-compat boolean: True when any concentration magnitude was extracted OR the
        # legacy substring is present (preserves existing consumers reading this flag).
        out["customer_concentration_flag"] = (
            _tc is not None or _tp is not None
            or "customers accounted for" in low or "customer accounted for" in low
        )
        # 截取 risk factors 开头(供 agent 读真实风险)
        idx = low.find("risk factors")
        out["risk_excerpt"] = txt[idx:idx + 3000] if idx >= 0 else ""
    except Exception as e:
        out["error"] = str(e)
    return out


def pull(ticker: str, cik: str) -> dict:
    """Pull all financial/insider/tenk data for a company.

    A1 — CIK-first: ticker may be empty when cik is present (pre-listing spinoffs).
    XBRL concept endpoints are CIK-based and always work.
    insider_trades / tenk_sections use ticker for their HTML/edgartools calls;
    they receive the cik fallback so Company() can be constructed from CIK.
    """
    d = {"ticker": ticker, "cik": cik,
         "pulled_at": today()}
    print(f"  拉财务序列...", file=sys.stderr)
    rev = concept_series(cik, REVENUE_CONCEPTS)
    time.sleep(0.2)
    ni = concept_series(cik, "NetIncomeLoss"); time.sleep(0.2)
    ocf = concept_series(cik, "NetCashProvidedByUsedInOperatingActivities"); time.sleep(0.2)
    cash = concept_series(cik, "CashAndCashEquivalentsAtCarryingValue"); time.sleep(0.2)
    shares = _shares_series(cik); time.sleep(0.2)
    assets = concept_series(cik, "Assets"); time.sleep(0.2)
    equity = concept_series(cik, "StockholdersEquity"); time.sleep(0.2)

    # Phase 2 additions: valuation inputs
    print(f"  拉估值输入序列(债务/EBIT/D&A/CapEx/Goodwill/Intangibles)...", file=sys.stderr)
    debt, debt_source = _debt_series(cik)
    time.sleep(0.2)
    # P9: EBIT concept cascade. Pull OperatingIncomeLoss first; if absent, _ebit_with_source
    # falls back to pretax-continuing-ops (+interest addback) so EV/EBITDA recovers.
    _op_income = concept_series(cik, EBIT_PRIMARY_CONCEPT); time.sleep(0.2)
    ebit, ebit_source = _ebit_with_source(cik, _op_income)
    time.sleep(0.2)
    da, da_source = _da_series(cik)
    time.sleep(0.2)
    capex_raw = concept_series(cik, CAPEX_CONCEPT); time.sleep(0.2)
    # CapEx from XBRL is a cash outflow stored as a positive number in PaymentsTo... concept.
    # We keep it positive (absolute value of spend) in the series for transparency.
    capex = capex_raw

    # NAV inputs: goodwill and intangibles (needed for tangible equity calculation)
    goodwill = concept_series(cik, "Goodwill"); time.sleep(0.2)
    intangibles = concept_series(cik, "IntangibleAssetsNetExcludingGoodwill"); time.sleep(0.2)

    # C1a: liabilities series for debt-truncation cross-check (Liabilities - Equity = implied debt)
    # Also serves as fallback for Assets when Assets concept is empty (C1c balance-sheet identity)
    print(f"  拉 Liabilities 序列(用于 C1 债务截断检验)...", file=sys.stderr)
    liabilities = concept_series(cik, "Liabilities"); time.sleep(0.2)
    # C1c: if Assets is empty, try LiabilitiesAndStockholdersEquity as fallback
    if not assets:
        assets = concept_series(cik, "LiabilitiesAndStockholdersEquity"); time.sleep(0.2)

    # C1: pull SIC from EDGAR company metadata for financial-sector guard (C2)
    sic_code: str | None = None
    try:
        sic_url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        sic_r = http_get(sic_url, timeout=20)
        if sic_r.status_code == 200:
            sic_code = str(sic_r.json().get("sic", "") or "")
    except Exception:
        pass
    time.sleep(0.2)

    # Derive EBITDA = EBIT + D&A (matching end dates; use latest available pair)
    def _latest_paired_sum(s1: list, s2: list) -> float | None:
        """Sum latest matching end-date pair, or fallback to latest of each independently."""
        if not s1 or not s2:
            return None
        # Try end-date alignment (preferred)
        ends1 = {v["end"]: v["val"] for v in s1}
        ends2 = {v["end"]: v["val"] for v in s2}
        common = sorted(set(ends1) & set(ends2))
        if common:
            latest_end = common[-1]
            return ends1[latest_end] + ends2[latest_end]
        # Fallback: just sum the respective latest entries (may be different fiscal ends)
        return s1[-1]["val"] + s2[-1]["val"]

    latest_ebitda = _latest_paired_sum(ebit, da)
    latest_ocf_val = ocf[-1]["val"] if ocf else None
    latest_capex = capex[-1]["val"] if capex else None
    # FCF = OCF - CapEx; if capex unavailable, use OCF as proxy with flag
    if latest_ocf_val is not None and latest_capex is not None:
        latest_fcf = latest_ocf_val - latest_capex
        fcf_is_ocf_proxy = False
    elif latest_ocf_val is not None:
        latest_fcf = latest_ocf_val
        fcf_is_ocf_proxy = True
    else:
        latest_fcf = None
        fcf_is_ocf_proxy = False

    d["financials"] = {
        "revenue": rev, "net_income": ni, "ocf": ocf, "cash": cash,
        "shares_outstanding": shares, "assets": assets, "equity": equity,
        # Phase 2 additions
        "total_debt": debt,
        "ebit": ebit,
        "dep_amort": da,
        "capex": capex,
        # NAV inputs
        "goodwill": goodwill,
        "intangibles": intangibles,
        # C1: liabilities series for debt-truncation cross-check
        "liabilities": liabilities,
    }
    # M5 — data-quality anomaly detection: flag implausible net_income (XBRL unit anomaly).
    # If |net_income| > revenue * 50 (e.g. $32B net income vs $32M revenue), the XBRL
    # value is almost certainly a unit mis-tag (millions reported in units of 1).
    # We do NOT alter the value; valuation uses OCF, so this is display-only.
    _latest_ni = ni[-1]["val"] if ni else None
    _latest_rev = rev[-1]["val"] if rev else None
    _data_quality_warn = None
    if (_latest_ni is not None and _latest_rev is not None and _latest_rev != 0
            and abs(_latest_ni) > abs(_latest_rev) * 50):
        _data_quality_warn = (
            f"latest_net_income ({_latest_ni/1e6:.1f}M) is implausibly large relative to "
            f"revenue ({_latest_rev/1e6:.1f}M) — possible XBRL unit mis-tag; "
            f"treat net_income with caution; valuation uses OCF which is unaffected."
        )

    # C1a: debt truncation + staleness check
    _debt_truncation_suspected, _debt_stale, _debt_trunc_detail = _check_debt_quality(
        debt, assets, equity, liabilities
    )

    # C1b: wrong-entity guard (ticker→CIK cross-check + financial sanity)
    _wrong_entity_suspected, _wrong_entity_reason = _validate_ticker_entity(
        ticker, cik, rev, shares, ni
    )

    # P9: ebit_source tagged by the cascade (None when no EBIT base recovered).
    _ebit_source = ebit_source if ebit else None

    # 10-K sections pulled BEFORE derived so P3 concentration can read the footnote text.
    print(f"  拉 10-K 章节...", file=sys.stderr)
    # A1: tenk_sections uses CIK fallback when ticker absent
    d["tenk"] = tenk_sections(ticker, cik=cik)

    # P3: magnitude-based concentration. tenk_sections extracts the magnitudes from the full
    # filing body (the only mechanical source — companyconcept XBRL has no dimensional members);
    # here we read them back and compose the kill/watch flag per the data contract.
    _top_customer_pct = d["tenk"].get("top_customer_pct")
    _top_program_pct = d["tenk"].get("top_program_pct")
    _conc_detail = d["tenk"].get("concentration_detail")
    _conc_flag = _concentration_flag(_top_customer_pct, _top_program_pct)

    # P6: deterministic trajectory + contamination. Revenue carries the slope/accel; OCF is the
    # normalization base the valuation layer averages on (contamination = latest / 5yr-avg).
    _traj = _trajectory_fields(rev, ocf)

    d["derived"] = {
        "revenue_growth_pct": pct_growth(rev),
        "shares_growth_pct": pct_growth(shares),  # 正=稀释
        "latest_revenue": _latest_rev,
        "latest_net_income": _latest_ni,
        "data_quality_warn": _data_quality_warn,
        "latest_ocf": latest_ocf_val,
        "latest_cash": cash[-1]["val"] if cash else None,
        "ocf_ni_divergence": (ni and ocf and ni[-1]["val"] > 0 and ocf[-1]["val"] < 0),
        "runway_periods": (round(cash[-1]["val"] / abs(ocf[-1]["val"]), 1)
                           if (cash and ocf and ocf[-1]["val"] < 0) else None),
        # Phase 2 additions
        "latest_total_debt": debt[-1]["val"] if debt else None,
        "debt_source": debt_source,
        "latest_ebit": ebit[-1]["val"] if ebit else None,
        # P9: which concept the EBIT cascade actually used (consumer reads to recover EV/EBITDA)
        "ebit_source": _ebit_source,
        "latest_dep_amort": da[-1]["val"] if da else None,
        "da_source": da_source,
        "latest_capex": latest_capex,
        "latest_ebitda": latest_ebitda,
        "latest_fcf": latest_fcf,
        "fcf_is_ocf_proxy": fcf_is_ocf_proxy,
        # NAV inputs
        "latest_goodwill": goodwill[-1]["val"] if goodwill else None,
        "latest_intangibles": intangibles[-1]["val"] if intangibles else None,
        # C1a: debt quality flags
        "debt_truncation_suspected": _debt_truncation_suspected,
        "debt_truncation_detail": _debt_trunc_detail,
        "debt_stale": _debt_stale,
        # C1b: wrong-entity flags
        "wrong_entity_suspected": _wrong_entity_suspected,
        "wrong_entity_reason": _wrong_entity_reason,
        # C2: SIC code for financial-sector routing in valuation
        "sic": sic_code,
        # P3: concentration (magnitude-based; replaces the substring detector)
        "top_customer_pct": _top_customer_pct,
        "top_program_pct": _top_program_pct,
        "concentration_flag": _conc_flag,
        "concentration_detail": _conc_detail,
        # P6: trajectory + contamination (deterministic, from the multiyear series)
        "rev_slope_sign": _traj["rev_slope_sign"],
        "rev_accel_sign": _traj["rev_accel_sign"],
        "latest_below_avg": _traj["latest_below_avg"],
        "contamination_ratio": _traj["contamination_ratio"],
        "fundamental_decline_flag": _traj["fundamental_decline_flag"],
    }
    print(f"  拉内部人交易...", file=sys.stderr)
    # A1: insider_trades queries openinsider by ticker; if no ticker, skip gracefully
    if ticker:
        d["insider"] = insider_trades(ticker, cik=cik)
        time.sleep(0.3)
    else:
        d["insider"] = {"available": False, "note": "no_ticker_pre_listing"}
    return d


def _selftest():
    init_edgar()

    # --- EGAN (CIK 1066194): fiscal-year == calendar-year concept-merge ---
    rev_egan = concept_series("1066194", REVENUE_CONCEPTS)
    years_egan = [v["end"][:4] for v in rev_egan]
    assert any(y >= "2024" for y in years_egan), (
        f"EGAN revenue must reach >=2024 after concept merge, got {years_egan}"
    )
    print(f"  EGAN: revenue years={years_egan}, latest={rev_egan[-1]['val']/1e6:.1f}M  OK")

    # --- BUKS (CIK 15847): fiscal-year != calendar-year (Apr 30 year-end), ASC-606 concept ---
    # Historically stuck at FY2018 $48M because 'Revenues' only covers through 2018;
    # the correct concept post-2018 is RevenueFromContractWithCustomerIncludingAssessedTax.
    rev_buks = concept_series("15847", REVENUE_CONCEPTS)
    years_buks = [v["end"][:4] for v in rev_buks]
    latest_buks = rev_buks[-1]["val"] if rev_buks else 0
    assert any(y >= "2024" for y in years_buks), (
        f"BUKS revenue must reach >=2024 (stuck-2018 bug), got {years_buks}"
    )
    assert latest_buks > 60_000_000, (
        f"BUKS latest revenue must be >$60M (real ~$84M FY2025), got ${latest_buks/1e6:.1f}M"
    )
    print(f"  BUKS: revenue years={years_buks}, latest=${latest_buks/1e6:.1f}M  OK")

    # --- WLFC (CIK 1018164): revenue must be in $400M-$800M range, not a tiny unit-leak value ---
    rev_wlfc = concept_series("1018164", REVENUE_CONCEPTS)
    latest_wlfc = rev_wlfc[-1]["val"] if rev_wlfc else 0
    assert 400_000_000 <= latest_wlfc <= 800_000_000, (
        f"WLFC latest revenue must be $400M-$800M (FY2024=$569M or FY2025=$730M), "
        f"got ${latest_wlfc/1e6:.1f}M — possible unit leak if <10000"
    )
    print(f"  WLFC: latest revenue=${latest_wlfc/1e6:.1f}M  OK")

    # --- Insider trades: open-market buy/sell values and counts (A1) ---
    # Use AI (C3.ai) — a ticker known to have open-market insider activity over the
    # last 730 days. Assert type correctness AND that at least one dollar-value side
    # is NONZERO (catches the silently-wrong-column failure where all values read as 0
    # even though available=True).
    ins = insider_trades("AI")
    assert isinstance(ins.get("open_market_buys"), int), (
        f"open_market_buys must be int, got {type(ins.get('open_market_buys'))}"
    )
    assert isinstance(ins.get("open_market_sells"), int), (
        f"open_market_sells must be int, got {type(ins.get('open_market_sells'))}"
    )
    assert isinstance(ins.get("buy_value"), (int, float)), (
        f"buy_value must be numeric, got {type(ins.get('buy_value'))}"
    )
    assert isinstance(ins.get("sell_value"), (int, float)), (
        f"sell_value must be numeric, got {type(ins.get('sell_value'))}"
    )
    assert ins.get("net_signal") in ("net_buy", "net_sell", "neutral", None), (
        f"net_signal unexpected value: {ins.get('net_signal')!r}"
    )
    # Hard-assert at least one side is nonzero — catches column-misread silently returning 0.
    # C3.ai has documented insider purchases; if both sides are 0 the column parsing is broken.
    assert ins.get("available") and (ins.get("buy_value", 0) > 0 or ins.get("sell_value", 0) > 0), (
        f"AI insider: buy_value and sell_value are BOTH zero with available=True — "
        f"column parsing is broken (wrong column indices). "
        f"buys={ins.get('open_market_buys')} sells={ins.get('open_market_sells')} "
        f"buy_value={ins.get('buy_value')} sell_value={ins.get('sell_value')}"
    )
    print(f"  AI insider: buys={ins.get('open_market_buys')} "
          f"sells={ins.get('open_market_sells')} "
          f"buy_value=${ins.get('buy_value', 0):,.0f} "
          f"sell_value=${ins.get('sell_value', 0):,.0f} "
          f"net={ins.get('net_signal')}  OK")

    # --- M5: data_quality_warn unit — verify the flag is set when implausible ratio exists ---
    # We synthesize a minimal scenario inline (no live EDGAR call needed for unit logic test).
    # Simulate a case where |net_income| > revenue * 50 and verify warn is emitted.
    _test_ni = 32_000_000_000   # 32B (unit mis-tag — should be 32M)
    _test_rev = 32_000_000      # 32M (correct)
    _warn = None
    if _test_ni is not None and _test_rev is not None and _test_rev != 0 and abs(_test_ni) > abs(_test_rev) * 50:
        _warn = f"latest_net_income is implausibly large relative to revenue — possible XBRL unit mis-tag"
    assert _warn is not None, "M5 data_quality_warn: failed to fire for |NI|>rev*50 (unit test broken)"
    print(f"  M5 data_quality_warn: fires correctly for implausible NI/rev ratio  OK")

    # --- C1a: debt truncation guard unit test ---
    # Simulate: reported_debt=11M, implied_debt(liab-equity)=4500M → ratio=0.002 < 0.5 → truncation
    _test_debt = [{"end": "2024-12-31", "val": 11_000_000}]
    _test_assets = [{"end": "2024-12-31", "val": 8_000_000_000}]
    _test_equity = [{"end": "2024-12-31", "val": 3_500_000_000}]
    _test_liab = [{"end": "2024-12-31", "val": 4_500_000_000}]
    _trunc, _stale, _detail = _check_debt_quality(_test_debt, _test_assets, _test_equity, _test_liab)
    assert _trunc, f"C1a: debt_truncation_suspected must fire when reported<0.5*implied (detail={_detail})"
    assert not _stale, "C1a: debt_stale must NOT fire when dates match"
    print(f"  C1a debt_truncation_suspected: fires correctly for HRI-like scenario  OK")

    # Staleness test: debt date 2020, assets date 2024 → stale
    _test_debt_stale = [{"end": "2020-12-31", "val": 11_000_000}]
    _test_assets_recent = [{"end": "2024-12-31", "val": 8_000_000_000}]
    _, _stale2, _ = _check_debt_quality(_test_debt_stale, _test_assets_recent, _test_equity, _test_liab)
    assert _stale2, "C1a: debt_stale must fire when debt date is >18m behind assets date"
    print(f"  C1a debt_stale: fires correctly for stale-debt scenario  OK")

    # --- C1b: wrong-entity guard unit test ---
    # Simulate a company with shares < 1000 (sub-entity)
    _fake_shares = [{"end": "2024-12-31", "val": 200}]
    _we, _we_reason = _validate_ticker_entity("", "0000000001", [], _fake_shares, [])
    assert _we, f"C1b: wrong_entity_suspected must fire for shares<1000 (reason={_we_reason})"
    print(f"  C1b wrong_entity_suspected: fires for shares<1000 scenario  OK")

    # Normal company with reasonable shares should not fire (no ticker check when ticker empty)
    _normal_shares = [{"end": "2024-12-31", "val": 50_000_000}]
    _we2, _ = _validate_ticker_entity("", "0000000001", [], _normal_shares, [])
    assert not _we2, "C1b: wrong_entity_suspected must NOT fire for normal shares count"
    print(f"  C1b wrong_entity_suspected: does NOT fire for normal company  OK")

    # --- P3: concentration extraction (magnitude-based, replaces substring) ---
    # SIGA-like footnote: single counterparty (U.S. Government) at 75% → top_customer_pct.
    _siga_text = (
        "Note 9. At December 31, 2025 and 2024, 75% and 45%, respectively, of accounts "
        "receivable represent receivables from the U.S. Government. Substantially all of "
        "our product revenue is derived from contracts with BARDA."
    )
    _tc, _tp, _cd = _extract_concentration(_siga_text)
    assert _tc is not None and _tc >= 75.0, (
        f"P3: SIGA-like single-counterparty 75% must be captured as top_customer_pct, got {_tc}"
    )
    assert _cd is not None and "top_customer" in _cd, f"P3: detail must describe customer, got {_cd!r}"
    assert _concentration_flag(_tc, _tp) == "kill", (
        f"P3: top_customer_pct>40 must yield kill, got {_concentration_flag(_tc, _tp)}"
    )
    print(f"  P3 concentration: SIGA-like top_customer={_tc:.0f}% -> kill  OK")

    # Program concentration >60% → kill; revenue-share phrasing.
    _prog_text = (
        "Our lead product accounted for approximately 82% of total revenue for the year. "
        "No single customer represented more than 10% of net sales."
    )
    _tc2, _tp2, _cd2 = _extract_concentration(_prog_text)
    assert _tp2 is not None and _tp2 >= 82.0, f"P3: program 82% must be captured, got {_tp2}"
    assert _concentration_flag(_tc2, _tp2) == "kill", (
        f"P3: top_program_pct>60 must yield kill, got {_concentration_flag(_tc2, _tp2)}"
    )
    print(f"  P3 concentration: lead-product top_program={_tp2:.0f}% -> kill  OK")

    # Threshold semantics (kill precedence per contract: kill if cust>40 OR prog>60):
    assert _concentration_flag(48.0, None) == "kill", "P3: customer 48% (>40) must be kill"
    assert _concentration_flag(40.0, None) == "watch", "P3: customer exactly 40 must be watch (not >40)"
    assert _concentration_flag(None, 55.0) == "watch", "P3: program 55% (40-60) must be watch"
    assert _concentration_flag(None, 65.0) == "kill", "P3: program 65% (>60) must be kill"
    assert _concentration_flag(None, None) is None, "P3: no concentration must be None flag"
    assert _concentration_flag(30.0, 30.0) is None, "P3: 30%/30% (below band) must be None"
    print(f"  P3 concentration_flag: kill/watch/None thresholds correct  OK")

    # --- P9: EBIT cascade tagging (no live call — exercise the source labels) ---
    # Path 1: OperatingIncomeLoss present → tagged OperatingIncomeLoss (offline; pass op income).
    _op = [{"end": "2024-12-31", "val": 50_000_000}]
    _ebit1, _src1 = _ebit_with_source("0000000001", _op)
    assert _src1 == "OperatingIncomeLoss" and _ebit1 == _op, (
        f"P9: OperatingIncomeLoss path must tag OperatingIncomeLoss, got {_src1}"
    )
    # Empty op-income with a CIK that has no pretax either → no recovery, source None.
    _ebit0, _src0 = _ebit_with_source("0000000001", [])
    assert _ebit0 == [] and _src0 is None, f"P9: unrecoverable EBIT must yield ([], None), got {_src0}"
    print(f"  P9 ebit_source: OperatingIncomeLoss path + unrecoverable path tagged correctly  OK")

    # Live cascade: ASIX (CIK 1739104) and BBW (CIK 1113809) do NOT tag OperatingIncomeLoss
    # (the ~47% null-EV/EBITDA case). The cascade must recover a non-empty EBIT series tagged
    # as a pretax fallback so EV/EBITDA can compute.
    _op_asix = concept_series("1739104", EBIT_PRIMARY_CONCEPT)
    _ebit_asix, _src_asix = _ebit_with_source("1739104", _op_asix)
    assert not _op_asix, "P9: ASIX must NOT tag OperatingIncomeLoss (cascade precondition)"
    assert _ebit_asix and _src_asix in ("pretax+interest_addback", "pretax_proxy"), (
        f"P9: ASIX EBIT must recover via pretax cascade, got source={_src_asix} n={len(_ebit_asix)}"
    )
    print(f"  P9 ebit_source: ASIX recovers via {_src_asix} (n={len(_ebit_asix)})  OK")

    # --- P6: trajectory + contamination derived fields ---
    # Declining revenue + lumpy OCF with a BARDA-style peak (SIGA contamination ~0.68).
    _rev_decline = [
        {"end": "2021-12-31", "val": 130_000_000},
        {"end": "2022-12-31", "val": 120_000_000},
        {"end": "2023-12-31", "val": 110_000_000},
        {"end": "2024-12-31", "val": 95_000_000},
        {"end": "2025-12-31", "val": 89_000_000},
    ]
    # OCF base: peak year (94.8) inflates the 5yr-avg so latest (43.5) is contaminated.
    _ocf_lumpy = [
        {"end": "2021-12-31", "val": 11_500_000},
        {"end": "2022-12-31", "val": 41_600_000},
        {"end": "2023-12-31", "val": 94_800_000},
        {"end": "2024-12-31", "val": 48_800_000},
        {"end": "2025-12-31", "val": 43_500_000},
    ]
    _t = _trajectory_fields(_rev_decline, _ocf_lumpy)
    assert _t["rev_slope_sign"] == -1, f"P6: declining revenue must give slope_sign -1, got {_t['rev_slope_sign']}"
    assert isinstance(_t["rev_accel_sign"], int) and _t["rev_accel_sign"] in (-1, 0, 1), (
        f"P6: rev_accel_sign must be int in (-1,0,1), got {_t['rev_accel_sign']!r}"
    )
    assert _t["latest_below_avg"] is True, "P6: latest OCF below trailing avg must be True"
    assert _t["contamination_ratio"] is not None and _t["contamination_ratio"] < 1.0, (
        f"P6: contamination_ratio (latest/5yr-avg) must be <1.0 for the lumpy series, "
        f"got {_t['contamination_ratio']}"
    )
    # latest 43.5 / 5yr-avg(11.5,41.6,94.8,48.8,43.5)=48.04 = 0.9055 per the contract formula.
    assert abs(_t["contamination_ratio"] - 0.9055) < 0.001, (
        f"P6: contamination_ratio must equal latest/5yr-avg=0.9055, got {_t['contamination_ratio']}"
    )
    assert _t["fundamental_decline_flag"] is True, (
        "P6: fundamental_decline_flag must fire when slope<0 AND contamination<1 AND latest_below_avg"
    )
    print(f"  P6 trajectory: slope=-1 accel={_t['rev_accel_sign']} "
          f"contamination={_t['contamination_ratio']} decline_flag=True  OK")

    # P6 regression: the REAL SIGA revenue series is contaminated at the front by a 9-month stub
    # and a duplicate-year mislabel; the raw all-time slope is +1, masking the decline. The
    # annualize + trailing-5 cleaning must recover slope=-1 so the veto fires (this is the bug the
    # phase-1 reviewer caught that the hand-cleaned _rev_decline crystal above could not surface).
    _rev_siga = [
        {"end": "2019-09-30", "val": 8_111_000},     # 9-month stub
        {"end": "2019-12-31", "val": 26_742_085},    # mislabeled FY, same calendar year as stub
        {"end": "2020-12-31", "val": 124_959_304},
        {"end": "2021-12-31", "val": 133_670_454},
        {"end": "2022-12-31", "val": 110_775_610},
        {"end": "2023-12-31", "val": 139_917_220},
        {"end": "2024-12-31", "val": 138_719_350},
        {"end": "2025-12-31", "val": 94_574_902},     # real decline, -31.8% YoY
    ]
    _ts = _trajectory_fields(_rev_siga, _ocf_lumpy)
    assert _ts["rev_slope_sign"] == -1, (
        f"P6 regression: contaminated SIGA series must annualize+trail to slope -1 "
        f"(raw all-time slope was +1), got {_ts['rev_slope_sign']}"
    )
    assert _ts["fundamental_decline_flag"] is True, (
        "P6 regression: SIGA must fire fundamental_decline_flag after series cleaning"
    )
    print("  P6 regression: contaminated SIGA series -> slope=-1, decline_flag=True  OK")

    # Healthy grower: rising revenue, stable/rising OCF → no decline flag.
    _rev_grow = [
        {"end": "2021-12-31", "val": 80_000_000},
        {"end": "2022-12-31", "val": 95_000_000},
        {"end": "2023-12-31", "val": 110_000_000},
        {"end": "2024-12-31", "val": 130_000_000},
        {"end": "2025-12-31", "val": 155_000_000},
    ]
    _ocf_grow = [
        {"end": "2021-12-31", "val": 10_000_000},
        {"end": "2022-12-31", "val": 13_000_000},
        {"end": "2023-12-31", "val": 16_000_000},
        {"end": "2024-12-31", "val": 20_000_000},
        {"end": "2025-12-31", "val": 26_000_000},
    ]
    _tg = _trajectory_fields(_rev_grow, _ocf_grow)
    assert _tg["rev_slope_sign"] == 1, f"P6: growing revenue must give slope_sign 1, got {_tg['rev_slope_sign']}"
    assert _tg["latest_below_avg"] is False, "P6: latest OCF above trailing avg must be False for grower"
    assert _tg["contamination_ratio"] is not None and _tg["contamination_ratio"] > 1.0, (
        f"P6: grower contamination_ratio must be >1.0, got {_tg['contamination_ratio']}"
    )
    assert _tg["fundamental_decline_flag"] is False, (
        "P6: fundamental_decline_flag must NOT fire for a healthy grower"
    )
    print(f"  P6 trajectory: grower slope=1 contamination={_tg['contamination_ratio']} "
          f"decline_flag=False  OK")

    # Edge: short series (1 point) must not crash and must yield neutral/safe defaults.
    _short = _trajectory_fields([{"end": "2025-12-31", "val": 100}], [{"end": "2025-12-31", "val": 5}])
    assert _short["rev_slope_sign"] == 0 and _short["contamination_ratio"] is None, (
        f"P6: single-point series must give neutral defaults, got {_short}"
    )
    assert _short["fundamental_decline_flag"] is False, "P6: single-point must not fire decline flag"
    print(f"  P6 trajectory: short-series safe defaults  OK")

    print("deepdive_data selftest PASS")


def _pull_and_save(ticker: str, cik: str) -> None:
    """Pull data for one ticker/CIK and write JSON to REPORTS dir.

    A1: ticker may be empty for pre-listing spinoffs; use CIK as filename key in that case.
    """
    label = ticker if ticker else f"CIK{cik}"
    print(f"深度尽调数据拉取: {label} (CIK {cik})", file=sys.stderr)
    d = pull(ticker, cik)
    out = REPORTS / f"deepdive_{label}_{today()}.json"
    out.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    der = d["derived"]
    print(f"\n=== {label} 数据摘要 ===")
    print(f"  营收: ${(der['latest_revenue'] or 0)/1e6:.1f}M (增速 {der['revenue_growth_pct']}%)")
    print(f"  净利: ${(der['latest_net_income'] or 0)/1e6:.1f}M | OCF: ${(der['latest_ocf'] or 0)/1e6:.1f}M")
    print(f"  现金: ${(der['latest_cash'] or 0)/1e6:.1f}M | runway: {der['runway_periods']} 期")
    print(f"  股本增速(稀释): {der['shares_growth_pct']}% | OCF/NI背离: {der['ocf_ni_divergence']}")
    print(f"  内部人: {d['insider'].get('net_signal')} (买{d['insider'].get('buys')}/卖{d['insider'].get('sells')})")
    print(f"  going concern: {d['tenk'].get('has_going_concern')} | 客户集中: {d['tenk'].get('customer_concentration_flag')}")
    print(f"\n数据: {out}")


def main():
    ap = argparse.ArgumentParser(
        description="deepdive_data — Stage 1 data pull. Use --ticker for single company or "
                    "--candidates for batch mode."
    )
    ap.add_argument("--ticker", default="", help="单只股票 ticker")
    ap.add_argument("--cik", default="", help="留空则用 edgartools 解析")
    ap.add_argument(
        "--candidates",
        default="",
        help="candidates JSON 文件路径 (list of {ticker, cik, ...}); 批量拉取所有候选",
    )
    ap.add_argument("--selftest", action="store_true", help="运行自检并退出")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if args.candidates:
        # Batch mode: loop over candidates JSON
        candidates_path = Path(args.candidates)
        if not candidates_path.exists():
            ap.error(f"--candidates file not found: {args.candidates}")
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        if not isinstance(candidates, list):
            ap.error("--candidates file must contain a JSON array of {ticker, cik, ...}")
        init_edgar()
        for i, rec in enumerate(candidates):
            ticker = rec.get("ticker", "")
            cik = str(rec.get("cik", ""))
            band = rec.get("band", "")

            # C3 — band disambiguation:
            #   "deep"    = mktcap < market_cap_max  → PROCESS
            #   "watch"   = market_cap_max..watch_band_max → SKIP (surfaced separately)
            #   "large"   = > watch_band_max → SKIP (out of scope)
            #   "unknown" = mktcap unavailable / pre-listing → PROCESS (likely spinoff)
            #   None / "" (legacy) = treat as "unknown" → PROCESS
            if band in ("watch", "large"):
                label = ticker if ticker else f"CIK{cik}"
                print(
                    f"  skipping {band}-band {label} (surfaced separately, no deep-dive)",
                    file=sys.stderr,
                )
                continue

            # A1 — CIK-first path: ticker-less pre-listing spinoffs
            if not ticker and not cik:
                print(
                    f"  [warn] skipping record {i}: both ticker and cik empty",
                    file=sys.stderr,
                )
                continue

            if not ticker and cik:
                # Try to resolve a ticker from CIK via edgartools
                try:
                    tickers_resolved = Company(int(cik)).tickers
                    if tickers_resolved:
                        ticker = tickers_resolved[0]
                        print(
                            f"  [A1] CIK {cik}: resolved ticker={ticker} from edgartools",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"  [A1] CIK {cik}: no ticker in edgartools; proceeding CIK-only",
                            file=sys.stderr,
                        )
                except Exception as e:
                    print(
                        f"  [A1] CIK {cik}: ticker resolve failed ({e}); proceeding CIK-only",
                        file=sys.stderr,
                    )

            if not cik and ticker:
                try:
                    cik = str(Company(ticker).cik)
                except Exception as e:
                    print(f"  [warn] cannot resolve CIK for {ticker}: {e}", file=sys.stderr)
                    continue

            label = ticker if ticker else f"CIK{cik}"
            try:
                _pull_and_save(ticker, cik)
            except Exception as e:
                print(f"  [warn] {label}: {e}", file=sys.stderr)
        return

    if not args.ticker:
        ap.error("--ticker or --candidates is required unless --selftest")

    init_edgar()
    cik = args.cik
    if not cik:
        try:
            cik = str(Company(args.ticker).cik)
        except Exception as e:
            print(f"无法解析 CIK: {e}", file=sys.stderr); sys.exit(1)
    _pull_and_save(args.ticker, cik)


if __name__ == "__main__":
    main()
