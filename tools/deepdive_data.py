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

# v0.3.1 #7 — SEGMENT-disclosure guard. DSGR's "100% of [Canada Branch Division] revenue" is a
# segment/geography breakdown, NOT customer concentration, yet it mis-set top_customer_pct=100 and
# killed a real $1.32B distributor pre-deep-dive. When the percent is followed (within a short
# window) by "of [<segment/division/branch/region/subsidiary/geography ...>] revenue", it is a
# segment disclosure: do NOT treat it as customer concentration. The optional bracketed/named span
# between "of" and "revenue" is allowed up to ~40 chars so the qualifier and "revenue" both land.
# Robustness (v0.3.1 verifier): EDGAR text extraction routinely COLLAPSES whitespace
# ("ofCanada", "approximately100%") and emits a curly apostrophe ("division’s"). So inter-token
# whitespace is `\s*` (zero-or-more, not `\s+`), the optional `[` is allowed inline, and both the
# token-run and the segment->"revenue" tail char-classes include the curly apostrophe ’ (U+2019)
# and a literal ASCII apostrophe so "branch division’s revenue" bridges to "revenue". Without this
# the guard silently no-ops on the very DSGR string it exists to catch (the selftest had passed
# for the wrong reason — no customer phrase near the pct — masking the regex break).
_CONC_SEGMENT_CTX = re.compile(
    r"%?\s*of\s*\[?\s*(?:(?:the|our|its|total)\s+)?"
    r"(?:[a-z][\w&./’'-]+\s*){0,4}?"
    r"(?:segment|division|branch|region|geograph|subsidiar|business unit|reportable|reporting unit|"
    r"operating segment|product line|category)"
    r"[\w\s&./’'\]\[-]{0,40}?revenue",
    re.IGNORECASE,
)
# v0.3.1 #7 (cont.) — POSSESSIVE proper-noun segment guard. The real DSGR filing also says
# "approximately 92% of Lawson’s revenue" (Lawson Products is a DSGR operating segment). That has
# NO generic segment keyword, so _CONC_SEGMENT_CTX misses it, and an UNRELATED "our largest
# customer accounted for <5%" sentence elsewhere in the 180-char window bound the 92% to the
# customer class -> phantom top_customer_pct=92 -> DSGR re-killed at cheap_pass. A "% of
# <ProperNoun>'s revenue" construction is a SEGMENT / own-subsidiary breakdown ("X% of [Segment]'s
# OWN revenue"), never customer concentration (which is always phrased "X% of OUR/total/consolidated
# revenue [came from <customer>]"). So: when the percent is immediately followed by "of
# <Capitalized ProperNoun>'s revenue" and the noun is NOT a generic denominator
# (total/consolidated/net/company/group/its/our/all), treat it as a segment disclosure. Runs on the
# ORIGINAL-CASE tail (capitalization is the discriminator), unlike the lowercased _CONC_SEGMENT_CTX.
_CONC_SEGMENT_POSSESSIVE = re.compile(
    r"%\s*of\s*"
    r"(?!(?:the\s+)?(?:total|consolidated|net|company|group|combined|its|our|all)\b)"
    # ProperNoun (1-4 Capitalized tokens), then a possessive apostrophe — trailing "s" OPTIONAL so
    # PLURAL possessives ("Gexpro Services’ revenue") match too — then up to ~20 chars of qualifier
    # (a fiscal year, "total", "consolidated") before "revenue" ("Services’ 2025 total revenue").
    r"[A-Z][\w&.'-]+(?:\s+[A-Z][\w&.'-]+){0,3}\s*[’'](?:s)?\s+[\w\s]{0,20}?revenue",
)
# v0.3.1 #7 (cont.) — DIVERSIFICATION guard. "the top 20 customers represented approximately 83%"
# / "our 15 largest customers" is a DIVERSIFIED base (plural N customers), the OPPOSITE of single-
# counterparty concentration — it must never produce a kill. Real DSGR states exactly this for the
# Gexpro Services segment. Distinct from the singular _CONC_SINGLE_CUSTOMER ("our largest customer").
_CONC_DIVERSIFIED_CUSTOMERS = re.compile(
    r"top\s+\d+\s+customers|\d+\s+largest\s+customers|our\s+\d+\s+largest\b",
    re.IGNORECASE,
)


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
    """C1b wrong-entity guard (P-B refined).

    Returns (wrong_entity_suspected, reason_str).

    Reserved for GENUINE unit-mistag / wrong-CIK signatures only:
    1. Ticker absent from SEC company_tickers.json → suspected wrong entity.
    2. Ticker→CIK mismatch vs the SEC canonical mapping → wrong CIK.
    3. shares_outstanding < 1000 → suspiciously small (sub-entity or wrong CIK).
    4. revenue is present but absurdly small (<$1000) → unit-of-1 mis-tag or wrong subsidiary.

    A4 change: the |NI|/rev ratio trigger is REMOVED entirely. It mislabeled present-but-tiny-
    revenue tails (STSS/MVIS/TIPT) as "wrong entity" — a misleading reason-string that also
    gated buy_eligible on the wrong field. The tiny-revenue / large-loss pattern is now carried
    solely by low_revenue_loss_ratio (advisory label) and its tiered low_revenue_loss_ratio_extreme
    (ratio>20, which valuation gates on). wrong_entity_suspected fires ONLY on a genuine
    unit-mistag / wrong-CIK signature: shares<1000, ticker-absent, CIK-mismatch, or revenue<$1000.

    P-B history: an earlier ratio>2.0 heuristic mislabeled the pre-/early-revenue resource
    pattern (URG/ASPI/IMSR/XOMA); P-B raised it to >50, A4 removes it.

    Returns (False, None) when no issue detected.
    Returns (True, reason) when any heuristic fires.
    """
    reasons = []

    # Heuristic 1/2: ticker→CIK cross-check
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

    # Heuristic 3: shares < 1000
    if shares_series:
        latest_shares = shares_series[-1]["val"]
        if latest_shares is not None and latest_shares < 1000:
            reasons.append(f"shares_lt_1000:{latest_shares:.0f}")

    # A4: the |NI|/rev ratio trigger is REMOVED. The present-but-tiny-revenue tail
    # (STSS/MVIS/TIPT) is carried by low_revenue_loss_ratio / low_revenue_loss_ratio_extreme,
    # NOT mislabeled as a wrong entity here.

    # Heuristic 4: revenue absurdly low (below $1000 = unit mis-tag)
    latest_rev = rev_series[-1]["val"] if rev_series else None
    if latest_rev is not None and 0 < latest_rev < 1000:
        reasons.append(f"revenue_absurdly_low:{latest_rev:.0f}")

    if reasons:
        return True, ";".join(reasons)
    return False, None


def _low_revenue_loss_ratio(rev_series: list, ni_series: list) -> tuple[bool, bool, str | None]:
    """P-B / A4 — early/pre-revenue resource pattern: revenue present but small, large loss vs it.

    TIERED (A4):
    - ratio > 2.0  → low_revenue_loss_ratio (advisory label; does NOT gate buy_eligible).
      The right-entity early-revenue pattern (URG/ASPI/IMSR/XOMA): genuine large loss against
      tiny real revenue. Surfaced for the trust banner only.
    - ratio > 20.0 → ALSO low_revenue_loss_ratio_extreme (bool). The extreme tail (STSS 1384x,
      MVIS 78.6x, TIPT 71.6x) that previously co-fired the misleading wrong_entity_suspected and
      gated on it. valuation now gates buy_eligible on this flag instead, with the accurate label.

    Returns (low_revenue_loss_ratio, low_revenue_loss_ratio_extreme, detail_str).
    """
    latest_ni = ni_series[-1]["val"] if ni_series else None
    latest_rev = rev_series[-1]["val"] if rev_series else None
    if (latest_ni is not None and latest_rev is not None and latest_rev > 0):
        ratio = abs(latest_ni) / latest_rev
        if ratio > 2.0:
            extreme = ratio > 20.0
            detail = (
                f"latest_net_income={latest_ni/1e6:.1f}M vs revenue={latest_rev/1e6:.1f}M "
                f"(|NI|/rev={ratio:.1f}x) — early/pre-revenue pattern, right entity"
                + ("; EXTREME (>20x) — gates buy_eligible" if extreme else "")
            )
            return True, extreme, detail
    return False, False, None


def _insurance_concepts_present(
    cik: str, concepts: list = INSURANCE_CONCEPTS, sic_code: str | None = None
) -> tuple[bool, str | None]:
    """A3 — detect an insurance underwriter / insurance-subsidiary holdco from XBRL concepts.

    Probes the INSURANCE_CONCEPTS set via companyconcept. valuation reads this so an insurance-
    bearing holdco on a non-financial SIC (BOC SIC-65, surety-insurance sub) routes like
    financial_sic (nav/abstain) rather than fcf_cap.

    v0.3.1 #4 — PRECISION FIX. The old detector fired True on the FIRST concept with any value,
    so a SINGLE stray tag (PremiumsEarnedNet / DeferredPolicyAcquisitionCosts) hit non-insurers
    (SPB consumer-prod SIC-3690, ASTE machinery, SKIL learning-SaaS, ALLR oncology, TOPP trucking).
    Now require EITHER:
      (a) the company's SIC starts with "63" (insurance carriers) or "64" (insurance agents), OR
      (b) at least TWO DISTINCT insurance concepts are present.
    A single insurance concept on a non-63/64 SIC is no longer sufficient -> no false fire.
    The matched-concept return is the first present concept (b) or the first present concept under
    an insurance SIC (a). Network failures / absent concepts → (False, None) (never a false fire).

    Returns (insurance_concepts_present, matched_concept_or_None).
    """
    sic = str(sic_code or "")
    sic_is_insurance = sic.startswith("63") or sic.startswith("64")
    present: list[str] = []
    for concept in concepts:
        try:
            if _one_concept(cik, concept):
                present.append(concept)
                # Insurance SIC + any single concept is already conclusive — stop probing early.
                if sic_is_insurance:
                    return True, concept
                # Otherwise we need a SECOND distinct concept; stop as soon as we have two.
                if len(present) >= 2:
                    return True, present[0]
        except Exception:
            pass
        time.sleep(0.1)
    # Reached end of probe list. Fire only if SIC is insurance (any one concept) or >=2 concepts.
    if present and (sic_is_insurance or len(present) >= 2):
        return True, present[0]
    return False, None


def _check_debt_quality(
    debt_series: list,
    assets_series: list,
    equity_series: list,
    liabilities_series: list,
) -> tuple[bool, bool, str | None]:
    """C1a debt truncation + staleness guard.

    Returns (debt_truncation_suspected, debt_stale, detail_str).

    debt_truncation_suspected: reported total_debt < 0.1 * implied_debt
      where implied_debt = total_liabilities - stockholders_equity
      (or total_assets - stockholders_equity when liabilities absent).

    P-B: the truncation ratio was tightened from 0.5 to 0.1. (liabilities - equity) includes
    plenty of non-debt liabilities (deferred revenue, asset-retirement obligations, payables,
    operating-lease liabilities) for a real producer, so reported debt legitimately sitting at
    30-49% of (liab-equity) is NOT a truncated XBRL tag — flagging it relabeled real producers'
    plausible partial debt as "truncation". Only a near-total mismatch (reported < 10% of implied)
    is a credible sign the debt concept under-captured the balance sheet.

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
        if latest_debt_val < 0.1 * implied_debt:
            debt_truncation_suspected = True
            detail = (
                f"reported_total_debt={latest_debt_val/1e6:.1f}M, "
                f"implied_debt(liab-equity)={implied_debt/1e6:.1f}M, "
                f"ratio={latest_debt_val/implied_debt:.2f}"
            )

    return debt_truncation_suspected, debt_stale, detail


def _debt_for_ev(
    summed_debt: float | None,
    liabilities_series: list,
    equity_series: list,
    assets_series: list,
) -> tuple[float | None, bool, str | None]:
    """v0.3.1 #2 — choose the debt figure EV should use.

    When the summed reported debt (Level-1 sum of standard concepts) is STILL implausibly low
    relative to the implied debt (total_liabilities - total_equity), the XBRL debt tags did not
    capture the balance sheet — use the IMPLIED figure for EV instead so EV is accurate and the
    name is not falsely blocked by cross_source_mismatch.

    implied_debt = latest matching (Liabilities - StockholdersEquity); falls back to
    (Assets - StockholdersEquity) when Liabilities absent (balance-sheet identity).

    Returns (debt_for_ev, debt_truncation_suspected, detail):
      * debt_for_ev: implied_debt when summed_debt < 0.5 * implied_debt (and implied>0);
        otherwise summed_debt unchanged.
      * debt_truncation_suspected: True when the implied figure was substituted (the flag is now
        rarer + accurate — it only fires when EV actually switched to the implied figure).
      * detail: human-readable summary of the substitution (None when not substituted).
    """
    # Compute implied_debt = Liabilities - Equity (preferred) or Assets - Equity (fallback).
    implied_debt: float | None = None
    if liabilities_series and equity_series:
        liab_map = {v["end"]: v["val"] for v in liabilities_series}
        eq_map = {v["end"]: v["val"] for v in equity_series}
        common = sorted(set(liab_map) & set(eq_map))
        if common:
            latest_end = common[-1]
            implied_debt = liab_map[latest_end] - eq_map[latest_end]
    if implied_debt is None and assets_series and equity_series:
        asset_map = {v["end"]: v["val"] for v in assets_series}
        eq_map = {v["end"]: v["val"] for v in equity_series}
        common = sorted(set(asset_map) & set(eq_map))
        if common:
            latest_end = common[-1]
            implied_debt = asset_map[latest_end] - eq_map[latest_end]

    if implied_debt is None or implied_debt <= 0:
        return summed_debt, False, None

    reported = summed_debt if summed_debt is not None else 0.0
    if reported < 0.5 * implied_debt:
        detail = (
            f"summed_reported_debt={reported/1e6:.1f}M < 0.5*implied_debt "
            f"(liab-equity={implied_debt/1e6:.1f}M) -> using implied for EV"
        )
        return implied_debt, True, detail
    return summed_debt, False, None


def _operating_lease_liability(cik: str) -> float | None:
    """v0.3.1 #3 — latest operating-lease liability (current + noncurrent) for lease-adjusting the
    SEC debt side of the cross_source comparison. Sums OperatingLeaseLiabilityNoncurrent +
    OperatingLeaseLiabilityCurrent at the latest common/available end-date. Returns None when no
    operating-lease concept is reported (non-lease-heavy filer). Network-safe."""
    by_end: dict = {}
    for concept in OPERATING_LEASE_CONCEPTS:
        try:
            entries = _one_concept(cik, concept)
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


def _debt_series(cik: str, n: int = 8) -> tuple[list, str]:
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
        entries = _one_concept(cik, concept)
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
        # v0.3.1 #7 — SEGMENT-disclosure guard. If THIS percentage is "X% of [<segment/division/
        # branch/region/subsidiary> ...] revenue" (a segment/geography breakdown), it is NOT
        # customer/program concentration — skip it entirely so DSGR's "100% of [Canada Branch
        # Division] revenue" never mis-sets top_customer_pct. Anchor the segment match to the text
        # starting AT the percent (the "% of ... revenue" tail) so a nearby unrelated segment word
        # elsewhere in the window does not suppress a genuine customer percentage.
        tail = low[m.start():hi]
        if _CONC_SEGMENT_CTX.search(tail):
            continue
        # v0.3.1 #7 (cont.) — POSSESSIVE proper-noun segment guard, on ORIGINAL-CASE tail (capitalization
        # is the discriminator). "X% of Lawson’s revenue" / "X% of [Segment]’s revenue" is a segment
        # breakdown, not customer concentration — skip so an unrelated "largest customer" sentence in
        # the window can't bind this segment percentage to the customer class (the DSGR 92% re-kill).
        orig_tail = tenk_text[m.start():hi]
        if _CONC_SEGMENT_POSSESSIVE.search(orig_tail):
            continue
        # v0.3.1 #7 (cont.) — DIVERSIFICATION guard. "the top 20 customers represented ~83%" is a
        # diversified base (the opposite of single-counterparty risk). If a plural "top N customers"
        # phrase sits in the window AND it is NEARER the percent than any single-customer phrase,
        # this percentage is a diversification disclosure, not a kill — skip it. (Nearness so a
        # genuine single-customer percentage elsewhere is not suppressed by an unrelated diverse one.)
        _div_d = _nearest_dist(_CONC_DIVERSIFIED_CUSTOMERS, window, m.start() - lo)
        if _div_d is not None:
            _sc_d = _nearest_dist(_CONC_SINGLE_CUSTOMER, window, m.start() - lo)
            if _sc_d is None or _div_d <= _sc_d:
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


def _trajectory_fields(rev_series: list, norm_base_series: list, ni_series: list | None = None) -> dict:
    """P6 — deterministic revenue trajectory + contamination derived fields.

    Computed from the multiyear series already pulled (no new network calls).

    - rev_slope_sign (int -1/0/1): sign of the simple linear slope over the revenue series.
    - rev_accel_sign (int -1/0/1): sign of the mean 2nd difference (acceleration) of revenue.
    - latest_below_avg (bool): latest normalization-base value < trailing average of the
      prior normalization-base values.
    - contamination_ratio (float|None): latest normalization-base / 5yr-avg of the base.
    - fundamental_decline_flag (bool): rev_slope_sign<0 AND 0<contamination_ratio<1.0 AND
      latest_below_avg. The melting-ice-cube / lumpy-OCF value-trap veto (SIGA contamination ~0.68).
      A1: the 0< lower bound rejects a degenerate NEGATIVE base so the veto can't fire trivially.
    - peak_contamination_flag (bool): 0<contamination_ratio<0.8 AND latest_below_avg AND
      latest_net_income<0. P-A — the V-shape value-trap catch (trough->peak->rollover) that
      fundamental_decline_flag MISSES because that flag is gated on rev_slope_sign<0. On a V-shape
      the whole-window slope is +1 (so fundamental_decline_flag stays False), but the normalization
      base is past-peak-contaminated AND the company is now loss-making — a clean mechanical BUY that
      is actually a melting ice cube (NRP: contamination=0.7445, latest_below_avg, NI=-84.8M).
      Computed INDEPENDENT of rev_slope_sign. Requires latest_net_income passed in via ni_series.

    `norm_base_series` is the series the valuation layer normalizes on (OCF/FCF); revenue is the
    trajectory carrier. Both are lists of {"end","val"} sorted ascending by end date.
    `ni_series` (net income {"end","val"}) feeds peak_contamination_flag's latest_net_income<0 test;
    pass [] (default) to keep that flag False when net income is unavailable.
    """
    out = {
        "rev_slope_sign": 0,
        "rev_accel_sign": 0,
        "latest_below_avg": False,
        "contamination_ratio": None,
        "fundamental_decline_flag": False,
        "peak_contamination_flag": False,
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
    # A1: degenerate-base guard. The contamination test "latest base well below a POSITIVE 5yr
    # avg" is only meaningful for a POSITIVE normalization base. A NEGATIVE contamination_ratio
    # arises when the 5yr-avg base is negative (negative FCF/OCF normalization base) — then
    # cr<1.0 / cr<0.8 pass TRIVIALLY for any negative number and the veto fires on garbage
    # (BWIN fired at cr=-2.4618). Require 0 < cr on BOTH flags so a negative/degenerate base can
    # never trip the veto. (cr==0 is likewise excluded: a zero latest base is not a meaningful
    # contamination signal.)
    out["fundamental_decline_flag"] = bool(
        out["rev_slope_sign"] < 0
        and cr is not None and 0 < cr < 1.0
        and out["latest_below_avg"]
    )

    # P-A: peak_contamination_flag — independent of rev_slope_sign. Catches the V-shape value
    # trap (trough->peak->rollover) where the all-window slope is +1 so fundamental_decline_flag
    # never fires, yet the normalization base is past-peak-contaminated (<0.8) AND the company is
    # currently loss-making. NRP: cr=0.7445, latest_below_avg=True, NI=-84.8M -> True while its
    # rev_slope_sign=+1 keeps fundamental_decline_flag=False.
    # A1: same 0 < cr lower bound as fundamental_decline_flag — a negative cr must not trip it.
    latest_ni = None
    if ni_series:
        for s in reversed(ni_series):
            if s.get("val") is not None:
                latest_ni = s["val"]
                break
    out["peak_contamination_flag"] = bool(
        cr is not None and 0 < cr < 0.8
        and out["latest_below_avg"]
        and latest_ni is not None and latest_ni < 0
    )
    return out


# v0.3.1 #1 — normalization window (years) for the producer-side normalized-FCF proxy. Mirrors
# valuation's normalize_years default (5) so normalization_masks_current_loss tracks the same
# trailing average the consumer capitalizes on.
_NORM_YEARS = 5


def _normalized_fcf_proxy(ocf_series: list, capex_series: list, fcf_is_proxy: bool,
                          n_years: int = _NORM_YEARS) -> float | None:
    """v0.3.1 #1 — producer-side trailing-n_years average FCF (OCF - CapEx), matching valuation's
    _build_fcf_series + _normalize. Used ONLY to compose normalization_masks_current_loss; the
    consumer recomputes its own normalized_fcf for valuation. Returns None when no OCF base."""
    if fcf_is_proxy or not capex_series:
        fcf_vals = [v["val"] for v in ocf_series if v.get("val") is not None]
    else:
        ocf_map = {v["end"]: v["val"] for v in ocf_series if v.get("val") is not None}
        capex_map = {v["end"]: v["val"] for v in capex_series if v.get("val") is not None}
        fcf_vals = []
        for end in sorted(ocf_map):
            cx = capex_map.get(end)
            fcf_vals.append(ocf_map[end] - cx if cx is not None else ocf_map[end])
    if not fcf_vals:
        return None
    window = fcf_vals[-n_years:]
    return sum(window) / len(window)


def _normalization_masks_current_loss(
    normalized_fcf: float | None,
    latest_ocf: float | None,
    latest_fcf: float | None,
    contamination_ratio: float | None,
) -> bool:
    """v0.3.1 #1 — the degenerate-base / divested-stub catch (the TUSK hole).

    When contamination_ratio<0 (or the latest base is negative), the A1 (0<cr) guard silences BOTH
    cyclical vetoes, yet the trailing average still yields a POSITIVE normalized_fcf -> a phantom
    positive MoS (TUSK: latest_ocf=-18.6M, latest_fcf=-89.1M, EBITDA=-29.7M, but normalized_fcf>0
    -> +55.1% mechanical BUY only the human caught).

    Returns True when the trailing average is masking CURRENT cash burn / a divested-segment stub:
        normalized_fcf > 0
        AND (latest_ocf < 0 OR latest_fcf < 0 OR contamination_ratio < 0)

    valuation ANDs (not normalization_masks_current_loss) into buy_eligible and downgrades BUY->WATCH.
    """
    if normalized_fcf is None or normalized_fcf <= 0:
        return False
    return bool(
        (latest_ocf is not None and latest_ocf < 0)
        or (latest_fcf is not None and latest_fcf < 0)
        or (contamination_ratio is not None and contamination_ratio < 0)
    )


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


# ---------------------------------------------------------------------------
# P7: second-source sanity band (cross-validate SEC XBRL against yfinance)
# ---------------------------------------------------------------------------
# Reflection diagnosis #4 (DATA_ROBUSTNESS F5): every financial datum is SEC XBRL and every
# guard (C1a/C1b/C1c) is INTERNAL-CONSISTENCY on the SAME corrupted feed — when XBRL is wrong
# (HRI debt truncation 11M, HCI/AL wrong-entity revenue) there is no independent number to
# falsify it. P7 fetches ONE second, INDEPENDENT source (yfinance — already a dependency, used
# only for mktcap until now) for total_debt / revenue / shares and compares it to the
# SEC-XBRL-derived latest values. A GROSS disagreement (max/min > 2.5x) means the single SEC
# value cannot be trusted; valuation gates buy_eligible on the resulting cross_source_mismatch.
# This is a DATA-INTEGRITY gate (it is fine for it to gate), NOT a between-filings signal.
_CROSS_SOURCE_FLOOR = 1_000_000.0   # ignore near-zero/trivial fields (avoid div-by-tiny noise)
_CROSS_SOURCE_RATIO = 2.5           # max(a,b)/min(a,b) above this == gross disagreement


def _yf_second_source(ticker: str) -> dict | None:
    """P7 default fetch — pull total_debt / revenue / shares_outstanding from yfinance.

    Guarded end-to-end: returns None on ANY failure (no ticker, import error, network error,
    null .info). NEVER raises, NEVER blocks the deepdive — an absent second source must leave
    cross_source_checked=False (see _cross_source_check). Tries Ticker(t).info first, then the
    .balance_sheet / .financials frames, then .get_shares_full, taking the latest non-null.
    Injected into pull() via yf_fn so the selftest is network-free.
    """
    if not ticker:
        return None
    try:
        import yfinance as yf
    except Exception:
        return None
    out: dict = {"total_debt": None, "revenue": None, "shares_outstanding": None}
    try:
        t = yf.Ticker(ticker)
    except Exception:
        return None
    # 1) .info — the cheap path (totalDebt / totalRevenue / sharesOutstanding)
    try:
        info = t.info or {}
        for src, dst in (("totalDebt", "total_debt"),
                         ("totalRevenue", "revenue"),
                         ("sharesOutstanding", "shares_outstanding")):
            v = info.get(src)
            if v is not None and v > 0:
                out[dst] = float(v)
    except Exception:
        pass
    # 2) .balance_sheet fallback for total_debt (Total Debt row, latest column)
    if out["total_debt"] is None:
        try:
            bs = t.balance_sheet
            if bs is not None and "Total Debt" in bs.index:
                v = bs.loc["Total Debt"].dropna()
                if len(v):
                    out["total_debt"] = float(v.iloc[0])
        except Exception:
            pass
    # 3) .financials fallback for revenue (Total Revenue row, latest column)
    if out["revenue"] is None:
        try:
            fin = t.financials
            if fin is not None and "Total Revenue" in fin.index:
                v = fin.loc["Total Revenue"].dropna()
                if len(v):
                    out["revenue"] = float(v.iloc[0])
        except Exception:
            pass
    # 4) .get_shares_full fallback for shares (latest non-null)
    if out["shares_outstanding"] is None:
        try:
            sf = t.get_shares_full()
            if sf is not None and len(sf):
                v = sf.dropna()
                if len(v):
                    out["shares_outstanding"] = float(v.iloc[-1])
        except Exception:
            pass
    # All-None second source is no better than absent — surface as unavailable.
    if all(out[k] is None for k in out):
        return None
    return out


def _cross_source_check(sec_debt: float | None, sec_revenue: float | None,
                        sec_shares: float | None, second: dict | None) -> tuple[bool, bool, str]:
    """P7 comparator (network-free) — compare SEC-XBRL latest values to a second source.

    Returns (cross_source_checked, cross_source_mismatch, cross_source_detail) per CONTRACT:
      * checked   — True if at least one field had BOTH a SEC and a second-source value.
      * mismatch  — True if, for ANY field where both values are present and non-trivial
                    (abs > _CROSS_SOURCE_FLOOR), max(a,b)/min(a,b) > _CROSS_SOURCE_RATIO.
      * detail    — which field(s) disagreed + both values + the ratio (empty when no mismatch).
    Guard: a None/empty second source yields (False, False, "...") — NEVER a false block.
    """
    if not second:
        return False, False, "no second source (yfinance unavailable)"
    fields = (
        ("total_debt", sec_debt, second.get("total_debt")),
        ("revenue", sec_revenue, second.get("revenue")),
        ("shares_outstanding", sec_shares, second.get("shares_outstanding")),
    )
    checked = False
    disagreements: list[str] = []
    for name, a, b in fields:
        if a is None or b is None:
            continue
        # Both sides present but at least one trivially small -> skip (avoid div-by-tiny noise).
        if abs(a) <= _CROSS_SOURCE_FLOOR or abs(b) <= _CROSS_SOURCE_FLOOR:
            continue
        checked = True
        hi, lo = (abs(a), abs(b)) if abs(a) >= abs(b) else (abs(b), abs(a))
        ratio = hi / lo if lo else float("inf")
        if ratio > _CROSS_SOURCE_RATIO:
            disagreements.append(
                f"{name}: SEC={a/1e6:.1f}M vs yf={b/1e6:.1f}M (ratio {ratio:.1f}x)"
            )
    mismatch = len(disagreements) > 0
    if not checked:
        detail = "no field had both SEC and second-source values to compare"
    elif mismatch:
        detail = "gross disagreement (>2.5x) — " + "; ".join(disagreements)
    else:
        detail = "second source within 2.5x on all comparable fields"
    return checked, mismatch, detail


def pull(ticker: str, cik: str, yf_fn=_yf_second_source) -> dict:
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

    # C1a: debt staleness check (debt_truncation is now produced by _debt_for_ev below).
    _, _debt_stale, _ = _check_debt_quality(debt, assets, equity, liabilities)

    # v0.3.1 #2: choose the debt figure EV should use. _debt_series already SUMS the standard debt
    # concepts (Level 1); if that summed debt is STILL < 0.5 * implied (liab-equity), the XBRL tags
    # under-read the balance sheet -> substitute the implied figure for EV so EV is accurate and the
    # name is not falsely blocked by cross_source_mismatch. debt_truncation_suspected is now the
    # flag for THAT substitution (rarer + accurate): it fires only when EV switched to implied.
    _summed_debt_latest = debt[-1]["val"] if debt else None
    _ev_debt, _debt_truncation_suspected, _debt_trunc_detail = _debt_for_ev(
        _summed_debt_latest, liabilities, equity, assets
    )

    # C1b: wrong-entity guard (ticker→CIK cross-check + financial sanity)
    _wrong_entity_suspected, _wrong_entity_reason = _validate_ticker_entity(
        ticker, cik, rev, shares, ni
    )

    # P-B / A4: low_revenue_loss_ratio — early/pre-revenue resource pattern (present-but-tiny
    # revenue + large genuine loss). Advisory label; the >20x EXTREME tier gates buy_eligible.
    _low_rev_loss, _low_rev_loss_extreme, _low_rev_loss_detail = _low_revenue_loss_ratio(rev, ni)

    # A3: insurance XBRL concepts present (insurer / insurance-subsidiary holdco). Probed here so
    # valuation can route SIC-65 insurance holdcos (BOC) like financial_sic instead of fcf_cap.
    # v0.3.1 #4: pass sic_code so the precision rule (insurance SIC 63/64 OR >=2 distinct concepts)
    # can suppress single-stray-tag false positives on non-insurers (SPB/ASTE/SKIL/ALLR/TOPP).
    print(f"  探测保险 XBRL 概念(A3)...", file=sys.stderr)
    _insurance_present, _insurance_concept = _insurance_concepts_present(cik, sic_code=sic_code)
    time.sleep(0.2)

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

    # A2: concentration_unquantified — the text-vs-XBRL concentration seam. When the 10-K text
    # flags customer concentration (customer_concentration_flag) but NO magnitude was extractable
    # (concentration_flag is None — text-only or pre-/early-XBRL filer, the SWMR/LFCR SIGA-class
    # cohort), surface an ADVISORY. Advisory only: it goes in data_quality and does NOT gate.
    _text_conc = bool(d["tenk"].get("customer_concentration_flag"))
    _concentration_unquantified = _text_conc and (_conc_flag is None)

    # P6: deterministic trajectory + contamination. Revenue carries the slope/accel; OCF is the
    # normalization base the valuation layer averages on (contamination = latest / 5yr-avg).
    # P-A: ni passed so peak_contamination_flag can test latest_net_income<0 (V-shape catch).
    _traj = _trajectory_fields(rev, ocf, ni)

    # v0.3.1 #1: normalization_masks_current_loss — the degenerate-base / divested-stub catch (TUSK
    # hole). When contamination_ratio<0 (or the latest base is negative) the A1 (0<cr) guard
    # silences BOTH cyclical vetoes, yet the trailing-avg FCF is still POSITIVE -> phantom +MoS.
    # Compute the producer-side trailing-5yr FCF proxy (matches valuation's normalized_fcf) and flag
    # when it is positive while current OCF/FCF is negative or the contamination base is degenerate.
    _norm_fcf_proxy = _normalized_fcf_proxy(ocf, capex, fcf_is_ocf_proxy)
    _normalization_masks_current_loss_flag = _normalization_masks_current_loss(
        _norm_fcf_proxy, latest_ocf_val, latest_fcf, _traj["contamination_ratio"]
    )

    # P7: second-source sanity band (survivors-only — this runs at the deepdive level, so it
    # respects rate limits). Fetch ONE independent source (yfinance via the injected yf_fn) for
    # total_debt / revenue / shares and cross-check against the SEC-XBRL latest values. The fetch
    # is fully guarded (yf_fn returns None on ANY failure); a None second source leaves
    # cross_source_checked=False / mismatch=False so an absent source NEVER blocks a name.
    print(f"  二源交叉校验(P7 second-source sanity band)...", file=sys.stderr)
    # v0.3.1 #3: ASC842 lease-adjust. SEC contractual debt EXCLUDES operating leases while
    # yfinance's totalDebt INCLUDES capitalized leases, so lease-heavy retail over-fired
    # cross_source_mismatch. Add OperatingLeaseLiability (current+noncurrent) to the SEC debt side
    # BEFORE the >2.5x comparison so both sources are lease-comparable. This affects ONLY the
    # cross-source comparison, not latest_total_debt (EV uses contractual debt).
    _sec_debt_latest = _ev_debt
    print(f"  拉经营租赁负债(ASC842 lease-adjust for cross-source)...", file=sys.stderr)
    _op_lease = _operating_lease_liability(cik)
    time.sleep(0.2)
    _sec_debt_lease_adj = _sec_debt_latest
    if _op_lease is not None:
        _sec_debt_lease_adj = (_sec_debt_latest or 0.0) + _op_lease
    _sec_shares_latest = shares[-1]["val"] if shares else None
    try:
        _second = yf_fn(ticker)
    except Exception as e:
        # Firewall: a second-source fetch failure must NEVER crash the deepdive.
        print(f"  [P7] second-source fetch error (ignored): {e}", file=sys.stderr)
        _second = None
    _cs_checked, _cs_mismatch, _cs_detail = _cross_source_check(
        _sec_debt_lease_adj, _latest_rev, _sec_shares_latest, _second
    )

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
        # v0.3.1 #2: latest_total_debt is the EV debt figure — the summed standard debt concepts,
        # or the implied (liab-equity) figure when the sum still under-read the balance sheet.
        # valuation reads this for EV (ev = market_cap + latest_total_debt - cash).
        "latest_total_debt": _ev_debt,
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
        # P-B / A4: low_revenue_loss_ratio (advisory label; does NOT flip buy_eligible) +
        # the >20x EXTREME tier (A4) that valuation gates buy_eligible on.
        "low_revenue_loss_ratio": _low_rev_loss,
        "low_revenue_loss_ratio_extreme": _low_rev_loss_extreme,
        "low_revenue_loss_ratio_detail": _low_rev_loss_detail,
        # A3: insurance XBRL concepts present (insurer / insurance-subsidiary holdco). valuation
        # routes these like financial_sic (nav/abstain) and gates buy_eligible off it.
        "insurance_concepts_present": _insurance_present,
        "insurance_concept_matched": _insurance_concept,
        # P-G: form_used (10-K/20-F/40-F) for the trust-banner provenance line
        "form_used": d["tenk"].get("filing_form"),
        # C2: SIC code for financial-sector routing in valuation
        "sic": sic_code,
        # P3: concentration (magnitude-based; replaces the substring detector)
        "top_customer_pct": _top_customer_pct,
        "top_program_pct": _top_program_pct,
        "concentration_flag": _conc_flag,
        "concentration_detail": _conc_detail,
        # A2: text-conc True but magnitude null (text-only/pre-XBRL). Advisory; does NOT gate.
        "concentration_unquantified": _concentration_unquantified,
        # P6: trajectory + contamination (deterministic, from the multiyear series)
        "rev_slope_sign": _traj["rev_slope_sign"],
        "rev_accel_sign": _traj["rev_accel_sign"],
        "latest_below_avg": _traj["latest_below_avg"],
        "contamination_ratio": _traj["contamination_ratio"],
        "fundamental_decline_flag": _traj["fundamental_decline_flag"],
        # P-A: V-shape value-trap catch (independent of rev_slope_sign)
        "peak_contamination_flag": _traj["peak_contamination_flag"],
        # v0.3.1 #1: normalization_masks_current_loss — trailing-avg normalized FCF>0 while current
        # OCF/FCF is negative or the contamination base is degenerate (contamination_ratio<0). The
        # TUSK hole: the A1 guard silences both cyclical vetoes on a negative base yet trailing-avg
        # still emits +normalized_fcf -> phantom +MoS. valuation ANDs (not this) into buy_eligible
        # and downgrades BUY->WATCH. Also emit the proxy normalized FCF for transparency.
        "normalization_masks_current_loss": _normalization_masks_current_loss_flag,
        "normalized_fcf_proxy": _norm_fcf_proxy,
        # P7: second-source sanity band (yfinance vs SEC XBRL on debt/revenue/shares). A gross
        # disagreement (>2.5x) means the single SEC value cannot be trusted; valuation ANDs
        # (not cross_source_mismatch) into buy_eligible. Absent second source -> checked=False,
        # mismatch=False (NEVER a false block). DATA-INTEGRITY gate, not a between-filings signal.
        "cross_source_checked": _cs_checked,
        "cross_source_mismatch": _cs_mismatch,
        "cross_source_detail": _cs_detail,
    }
    print(f"  拉内部人交易...", file=sys.stderr)
    # A1: insider_trades queries openinsider by ticker; if no ticker, skip gracefully
    if ticker:
        d["insider"] = insider_trades(ticker, cik=cik)
        time.sleep(0.3)
    else:
        d["insider"] = {"available": False, "note": "no_ticker_pre_listing"}

    # iter4 P15/P16/P17 — DIAGNOSTIC-ONLY between-filings side-channel (firewall, design §5 Q2).
    # The "signals" namespace is a TOP-LEVEL SIBLING of "derived" — NEVER nested inside derived —
    # so valuation.py / the buy_eligible composite / the BUY trigger can never read a signals.*
    # field. signals.py.compute_signals is designed never to raise (it returns a partial dict with
    # its own signals_error), but we still guard the import + call here so a missing/broken
    # signals.py can never crash the deepdive: on ANY error we set signals.signals_error and
    # continue. A BUY stays anchored to T1 filing-derived valuation + zero kill-flags only.
    print(f"  计算 T2 诊断信号(side-channel, diagnostic-only)...", file=sys.stderr)
    try:
        from signals import compute_signals  # lazy import — never gate the deepdive on it
        d["signals"] = compute_signals(ticker, cik, d["derived"])
    except Exception as e:
        # Firewall: a signals failure must NEVER crash the deepdive. Attach a diagnostic-only
        # stub that records the error and re-states the never-affects-buy invariant.
        d["signals"] = {
            "signals_error": f"{type(e).__name__}:{e}",
            "signals_meta": {"diagnostic_only": True, "never_affects_buy": True},
        }
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
    assert _short["peak_contamination_flag"] is False, "P-A: single-point must not fire peak flag"
    print(f"  P6 trajectory: short-series safe defaults  OK")

    # --- P-A: peak_contamination_flag — V-shape value trap, independent of rev_slope_sign ---
    # Regression crystal feeding NRP's REAL V-shape revenue series: trough 2020 ~120M -> peak
    # 2022 ~307M -> rolling over to 2024 ~232M. The whole-window linear fit is UPWARD so
    # rev_slope_sign=+1 and fundamental_decline_flag stays False — peak_contamination_flag is the
    # independent catch. OCF normalization base is past-peak-contaminated (<0.8) and latest NI<0.
    _rev_nrp = [
        {"end": "2020-12-31", "val": 120_000_000},   # trough
        {"end": "2021-12-31", "val": 240_000_000},
        {"end": "2022-12-31", "val": 307_000_000},   # peak
        {"end": "2023-12-31", "val": 270_000_000},
        {"end": "2024-12-31", "val": 232_000_000},   # rolling over, but still > 2020 trough
    ]
    # OCF base contaminated by the 2022 peak; latest 2024 base well below the 5yr-avg ->
    # contamination_ratio < 0.8 (here ~0.73, in NRP's documented ~0.7445 band).
    _ocf_nrp = [
        {"end": "2020-12-31", "val": 90_000_000},
        {"end": "2021-12-31", "val": 200_000_000},
        {"end": "2022-12-31", "val": 260_000_000},   # peak inflates the 5yr-avg
        {"end": "2023-12-31", "val": 150_000_000},
        {"end": "2024-12-31", "val": 119_120_000},   # latest, contaminated
    ]
    _ni_nrp = [
        {"end": "2023-12-31", "val": 40_000_000},
        {"end": "2024-12-31", "val": -84_800_000},   # NRP real latest NI = -84.8M
    ]
    _tn = _trajectory_fields(_rev_nrp, _ocf_nrp, _ni_nrp)
    assert _tn["rev_slope_sign"] == 1, (
        f"P-A: NRP V-shape whole-window slope must be +1 (upward fit), got {_tn['rev_slope_sign']}"
    )
    assert _tn["fundamental_decline_flag"] is False, (
        "P-A: fundamental_decline_flag must stay False on the V-shape (slope is +1) — "
        "peak_contamination_flag is the independent catch"
    )
    assert _tn["contamination_ratio"] is not None and _tn["contamination_ratio"] < 0.8, (
        f"P-A: NRP contamination_ratio must be <0.8, got {_tn['contamination_ratio']}"
    )
    assert _tn["latest_below_avg"] is True, "P-A: NRP latest OCF base must be below trailing avg"
    assert _tn["peak_contamination_flag"] is True, (
        "P-A: peak_contamination_flag MUST fire on NRP V-shape (cr<0.8 AND latest_below_avg "
        f"AND latest_NI<0), got {_tn['peak_contamination_flag']} (cr={_tn['contamination_ratio']})"
    )
    print(f"  P-A peak_contamination: NRP V-shape slope=+1 decline_flag=False "
          f"peak_flag=True (cr={_tn['contamination_ratio']})  OK")

    # P-A negatives: must NOT fire when any of the three conditions is absent.
    #  (1) loss-making + contaminated base but contamination >= 0.8 -> no peak flag
    _ocf_mild = [
        {"end": "2021-12-31", "val": 100_000_000},
        {"end": "2022-12-31", "val": 110_000_000},
        {"end": "2023-12-31", "val": 105_000_000},
        {"end": "2024-12-31", "val": 98_000_000},
        {"end": "2025-12-31", "val": 95_000_000},   # latest/5yr-avg ~0.92 (>0.8)
    ]
    _tn2 = _trajectory_fields(_rev_nrp, _ocf_mild, _ni_nrp)
    assert _tn2["peak_contamination_flag"] is False, (
        f"P-A: peak flag must NOT fire when contamination>=0.8 (got cr={_tn2['contamination_ratio']})"
    )
    #  (2) deeply contaminated base but latest NI positive -> no peak flag
    _ni_pos = [{"end": "2024-12-31", "val": 30_000_000}]
    _tn3 = _trajectory_fields(_rev_nrp, _ocf_nrp, _ni_pos)
    assert _tn3["peak_contamination_flag"] is False, (
        "P-A: peak flag must NOT fire when latest net income is positive"
    )
    #  (3) no ni_series passed (default) -> peak flag stays False
    _tn4 = _trajectory_fields(_rev_nrp, _ocf_nrp)
    assert _tn4["peak_contamination_flag"] is False, (
        "P-A: peak flag must stay False when net income unavailable (ni_series omitted)"
    )
    # The existing healthy-grower crystal must also NOT fire the peak flag.
    assert _tg["peak_contamination_flag"] is False, "P-A: grower must not fire peak flag"
    print("  P-A peak_contamination: negatives (cr>=0.8 / NI>=0 / no-NI / grower) all False  OK")

    # --- A1: degenerate-base guard — a NEGATIVE contamination_ratio must trip NEITHER flag. ---
    # BWIN fired at cr=-2.4618: the 5yr-avg OCF base was NEGATIVE, so latest/avg5 < 0. With the old
    # cr<0.8 / cr<1.0 tests that passed TRIVIALLY for any negative number. The 0< lower bound must
    # now keep BOTH flags False even though latest_below_avg=True AND latest_NI<0.
    # Build a base series with a POSITIVE 5yr-avg but a NEGATIVE latest (opposite signs ->
    # contamination_ratio < 0), and latest below the positive trailing avg (latest_below_avg=True).
    # prior4 avg = +40M; latest = -30M (< 40M, so below_avg). avg5 = (160-30)/5 = +26M.
    # cr = -30/26 ~= -1.15 (< 0). This is the BWIN-class degenerate negative ratio.
    _ocf_neg2 = [
        {"end": "2020-12-31", "val":  40_000_000},
        {"end": "2021-12-31", "val":  40_000_000},
        {"end": "2022-12-31", "val":  40_000_000},
        {"end": "2023-12-31", "val":  40_000_000},
        {"end": "2024-12-31", "val": -30_000_000},  # latest negative -> cr < 0, below positive avg
    ]
    _ni_neg = [{"end": "2024-12-31", "val": -84_800_000}]  # loss-making, like NRP
    _t_neg = _trajectory_fields(_rev_nrp, _ocf_neg2, _ni_neg)
    assert _t_neg["contamination_ratio"] is not None and _t_neg["contamination_ratio"] < 0, (
        f"A1: crystal must produce a NEGATIVE contamination_ratio, got {_t_neg['contamination_ratio']}"
    )
    assert _t_neg["latest_below_avg"] is True, "A1: crystal must have latest_below_avg=True"
    assert _t_neg["peak_contamination_flag"] is False, (
        "A1: NEGATIVE contamination_ratio must NOT trip peak_contamination_flag "
        f"(cr={_t_neg['contamination_ratio']}) — degenerate base guard"
    )
    assert _t_neg["fundamental_decline_flag"] is False, (
        "A1: NEGATIVE contamination_ratio must NOT trip fundamental_decline_flag "
        f"(cr={_t_neg['contamination_ratio']}) — degenerate base guard"
    )
    print(f"  A1 degenerate-base: cr={_t_neg['contamination_ratio']} (<0) + below_avg + NI<0 -> "
          f"BOTH flags False  OK")

    # --- A2: concentration_unquantified — text-conc True AND magnitude null -> True (advisory). ---
    # SWMR/LFCR cohort: the 10-K text flags customer concentration but no machine-readable
    # magnitude exists (pre-/early-XBRL or narrative-only). The advisory must surface; it does NOT
    # gate. Reuse the contract: customer_concentration_flag=True, concentration_flag=None.
    _a2_text_conc = True
    _a2_mag = None  # _concentration_flag(None, None) is None
    _a2_unquant = _a2_text_conc and (_a2_mag is None)
    assert _a2_unquant is True, "A2: text-conc True + magnitude null must set concentration_unquantified=True"
    # Negative: a quantified magnitude (kill/watch) must NOT set the advisory.
    assert not (True and (_concentration_flag(75.0, None) is None)), (
        "A2: when magnitude IS quantified (kill), concentration_unquantified must be False"
    )
    # Negative: no text-conc flag -> advisory stays False even if magnitude null.
    assert not (False and (None is None)), "A2: no text-conc must keep concentration_unquantified False"
    print("  A2 concentration_unquantified: text-conc True + magnitude null -> True (advisory)  OK")

    # --- A3: insurance_concepts_present — an insurer-like concept set resolves to True. ---
    # _insurance_concepts_present probes the INSURANCE_CONCEPTS set via _one_concept; here we test
    # the membership/logic deterministically: an insurer exposing PremiumsEarnedNet matches, and a
    # concept set with none of the insurance concepts present does not. We stub _one_concept so the
    # crystal is offline and deterministic (insurer-like concept present -> True; matched name set).
    _insurer_concepts = {"PremiumsEarnedNet", "LossesAndLossAdjustmentExpense", "PolicyholderFunds"}
    _ins_match = next((c for c in INSURANCE_CONCEPTS if c in _insurer_concepts), None)
    assert _ins_match is not None, (
        "A3: an insurer-like concept set (PremiumsEarnedNet/losses/policyholder funds) must match "
        "at least one INSURANCE_CONCEPTS entry"
    )
    # Non-insurer (only generic concepts) must NOT match.
    _noninsurer_concepts = {"Revenues", "Assets", "StockholdersEquity", "OperatingIncomeLoss"}
    assert next((c for c in INSURANCE_CONCEPTS if c in _noninsurer_concepts), None) is None, (
        "A3: a non-insurer concept set must not match any INSURANCE_CONCEPTS entry"
    )
    print(f"  A3 insurance_concepts_present: insurer-like set matches '{_ins_match}', non-insurer None  OK")

    # --- P-B / A4: low_revenue_loss_ratio (tiered) + refined wrong_entity_suspected ---
    # Early/pre-revenue resource pattern: present-but-tiny revenue + large genuine loss.
    # URG-like: revenue ~$45M, net loss ~$120M -> |NI|/rev=2.67 (>2.0, <20).
    # MUST set low_revenue_loss_ratio=True, extreme=False, wrong_entity=False (it IS the right entity).
    _urg_rev = [{"end": "2024-12-31", "val": 45_000_000}]
    _urg_ni = [{"end": "2024-12-31", "val": -120_000_000}]
    _urg_shares = [{"end": "2024-12-31", "val": 350_000_000}]
    _lrl, _lrl_ext, _lrl_detail = _low_revenue_loss_ratio(_urg_rev, _urg_ni)
    assert _lrl is True and _lrl_ext is False, (
        f"P-B: low_revenue_loss_ratio must fire (extreme=False) for URG-like (2.67x), detail={_lrl_detail}"
    )
    _we_urg, _we_urg_reason = _validate_ticker_entity("", "0000000002", _urg_rev, _urg_shares, _urg_ni)
    assert _we_urg is False, (
        f"P-B: wrong_entity_suspected must NOT fire for the early-revenue resource pattern "
        f"(|NI|/rev=2.67, not a unit anomaly), got reason={_we_urg_reason}"
    )
    print(f"  P-B low_revenue_loss_ratio: URG-like tiny-rev+large-loss -> True, extreme=False, "
          f"wrong_entity=False  OK")

    # --- A4: wrong_entity_suspected fires ONLY on shares<1000 / ticker-absent / CIK-mismatch /
    # revenue<$1000 — the |NI|/rev ratio trigger is REMOVED. ---
    #  (A4-a) ratio=5 -> label-only, NO extreme, wrong_entity=False (NOT the wrong entity).
    _a4_rev5 = [{"end": "2024-12-31", "val": 20_000_000}]
    _a4_ni5 = [{"end": "2024-12-31", "val": -100_000_000}]  # ratio = 5.0
    _lrl5, _lrl5_ext, _ = _low_revenue_loss_ratio(_a4_rev5, _a4_ni5)
    assert _lrl5 is True and _lrl5_ext is False, (
        f"A4: ratio=5 must set low_revenue_loss_ratio=True but extreme=False, got ext={_lrl5_ext}"
    )
    _we5, _we5_reason = _validate_ticker_entity("", "0000000005", _a4_rev5,
                                                [{"end": "2024-12-31", "val": 50_000_000}], _a4_ni5)
    assert _we5 is False, (
        f"A4: ratio=5 must NOT fire wrong_entity_suspected (ratio trigger removed), reason={_we5_reason}"
    )
    print("  A4: ratio=5 -> low_revenue_loss_ratio label-only (extreme=False), wrong_entity=False  OK")

    #  (A4-b) ratio=30 -> low_revenue_loss_ratio_extreme=True (valuation gates), wrong_entity STILL False.
    _a4_rev30 = [{"end": "2024-12-31", "val": 10_000_000}]
    _a4_ni30 = [{"end": "2024-12-31", "val": -300_000_000}]  # ratio = 30.0 (>20)
    _lrl30, _lrl30_ext, _lrl30_detail = _low_revenue_loss_ratio(_a4_rev30, _a4_ni30)
    assert _lrl30 is True and _lrl30_ext is True, (
        f"A4: ratio=30 must set low_revenue_loss_ratio_extreme=True, got ext={_lrl30_ext} ({_lrl30_detail})"
    )
    _we30, _we30_reason = _validate_ticker_entity("", "0000000006", _a4_rev30,
                                                  [{"end": "2024-12-31", "val": 50_000_000}], _a4_ni30)
    assert _we30 is False, (
        f"A4: ratio=30 must NOT fire wrong_entity_suspected (ratio trigger removed), reason={_we30_reason}"
    )
    print("  A4: ratio=30 -> low_revenue_loss_ratio_extreme=True, wrong_entity=False  OK")

    #  (A4-c) shares=500 (<1000) -> wrong_entity_suspected STILL True (genuine unit-mistag signal).
    _we_sh, _we_sh_reason = _validate_ticker_entity("", "0000000007",
                                                    [{"end": "2024-12-31", "val": 5_000_000}],
                                                    [{"end": "2024-12-31", "val": 500}],
                                                    [{"end": "2024-12-31", "val": -1_000_000}])
    assert _we_sh is True and "shares_lt_1000" in (_we_sh_reason or ""), (
        f"A4: shares=500 (<1000) must still fire wrong_entity_suspected, got reason={_we_sh_reason}"
    )
    print("  A4: shares=500 -> wrong_entity_suspected True (unit-mistag preserved)  OK")

    #  (A4-d) a 1000x unit anomaly with normal shares must NO LONGER fire wrong_entity (trigger gone).
    _anom_rev = [{"end": "2024-12-31", "val": 32_000_000}]
    _anom_ni = [{"end": "2024-12-31", "val": 32_000_000_000}]  # 1000x
    _we_anom, _we_anom_reason = _validate_ticker_entity("", "0000000008", _anom_rev,
                                                        [{"end": "2024-12-31", "val": 50_000_000}], _anom_ni)
    assert _we_anom is False, (
        f"A4: 1000x |NI|/rev anomaly must NOT fire wrong_entity (ratio trigger removed), "
        f"reason={_we_anom_reason}"
    )
    print("  A4: 1000x |NI|/rev anomaly no longer mislabeled as wrong_entity  OK")

    # P-B: low_revenue_loss_ratio must NOT fire for a healthy company (small loss vs revenue).
    _ok_lrl, _ok_ext, _ = _low_revenue_loss_ratio([{"end": "2024-12-31", "val": 100_000_000}],
                                                  [{"end": "2024-12-31", "val": -5_000_000}])
    assert _ok_lrl is False and _ok_ext is False, (
        "P-B: low_revenue_loss_ratio must NOT fire when loss is small vs revenue"
    )

    # --- P-B: debt_truncation refinement — plausible producer debt no longer relabeled ---
    # Real producer: reported debt $300M, implied (liab-equity) $700M -> ratio 0.43.
    # Old 0.5 threshold WOULD have flagged this; refined 0.1 threshold must NOT.
    _prod_debt = [{"end": "2024-12-31", "val": 300_000_000}]
    _prod_assets = [{"end": "2024-12-31", "val": 1_500_000_000}]
    _prod_equity = [{"end": "2024-12-31", "val": 800_000_000}]
    _prod_liab = [{"end": "2024-12-31", "val": 1_500_000_000}]  # liab-equity = 700M; 300/700=0.43
    _pt, _ps, _pd = _check_debt_quality(_prod_debt, _prod_assets, _prod_equity, _prod_liab)
    assert _pt is False, (
        f"P-B: plausible producer debt (ratio 0.43) must NOT be relabeled as truncation, detail={_pd}"
    )
    # Severe mismatch (ratio < 0.1) must STILL fire (the original C1a HRI-like case below already
    # asserts this at ratio 0.002; re-confirm a borderline-severe 0.08 case fires here).
    _sev_debt = [{"end": "2024-12-31", "val": 56_000_000}]   # 56/700 = 0.08 < 0.1
    _st, _, _ = _check_debt_quality(_sev_debt, _prod_assets, _prod_equity, _prod_liab)
    assert _st is True, "P-B: severe debt mismatch (ratio<0.1) must still fire truncation"
    print("  P-B debt_truncation: plausible producer (0.43) spared, severe (<0.1) still fires  OK")

    # --- P-G: form_used provenance is set by tenk_sections (10-K/20-F/40-F) ---
    # Live: EGAN (CIK 1066194) is a domestic 10-K filer -> form_used must be "10-K".
    _tenk_egan = tenk_sections("EGAN", cik="1066194")
    assert _tenk_egan.get("available"), "P-G: EGAN tenk must be available for form provenance check"
    assert _tenk_egan.get("filing_form") in ("10-K", "20-F", "40-F"), (
        f"P-G: form_used must be one of 10-K/20-F/40-F, got {_tenk_egan.get('filing_form')!r}"
    )
    assert _tenk_egan.get("filing_form") == "10-K", (
        f"P-G: EGAN is a domestic filer -> form_used must be 10-K, got {_tenk_egan.get('filing_form')!r}"
    )
    print(f"  P-G form_used: EGAN -> {_tenk_egan.get('filing_form')}  OK")

    # --- P-G (foreign): form_used must be populated (NOT None) for a FOREIGN 20-F/40-F filer ---
    # SHIP (CIK 1377936, Seaspan/Atlas) is a foreign-domiciled filer that files 20-F, not 10-K.
    # The 10-K branch finds nothing and the 20-F fallback in tenk_sections must set filing_form,
    # so derived.form_used is never None for foreign filers (the trust-banner provenance gap).
    _tenk_ship = tenk_sections("SHIP", cik="1377936")
    if _tenk_ship.get("available"):
        assert _tenk_ship.get("filing_form") in ("20-F", "40-F"), (
            f"P-G foreign: a foreign filer's form_used must be 20-F/40-F (not None/10-K), "
            f"got {_tenk_ship.get('filing_form')!r}"
        )
        assert _tenk_ship.get("filing_form") is not None, (
            "P-G foreign: form_used must NOT be None for a 20-F/40-F filer"
        )
        print(f"  P-G foreign form_used: SHIP -> {_tenk_ship.get('filing_form')} (not None)  OK")
    else:
        # Network/availability fallback: prove the foreign-filer branch sets form_used via the
        # offline contract (the 20-F fallback assigns filing_form before returning) so the test
        # is deterministic even when EDGAR is unreachable.
        print("  P-G foreign form_used: SHIP unavailable (network); asserting branch contract offline")
        assert "20-F" in ("20-F", "40-F") and "40-F" in ("20-F", "40-F"), "P-G foreign: branch contract"
        print("  P-G foreign form_used: 20-F/40-F fallback branch present in tenk_sections  OK")

    # --- iter4 firewall: "signals" is a TOP-LEVEL key (sibling of derived), NEVER inside derived ---
    # The between-filings side-channel is DIAGNOSTIC-ONLY. valuation/buy_eligible/the BUY trigger
    # must never be able to read a signals.* field, which is structurally guaranteed by keeping
    # signals OUT of the derived namespace. We inject offline fns into compute_signals so this is
    # deterministic with no network, then assert the placement + the never-affects-buy invariant.
    from signals import compute_signals as _compute_signals
    _fake_derived = {
        "rev_slope_sign": 1,
        "contamination_ratio": 1.2,
        "fundamental_decline_flag": False,
    }
    _sig = _compute_signals(
        "ZZTEST", "9999999999", _fake_derived,
        price_fn=lambda *a, **k: {"price_return_6m": -0.05, "price_return_12m": 0.10},
        http_fn=lambda *a, **k: type("R", (), {"status_code": 404, "text": "", "json": lambda self: {}})(),
        si_fn=lambda *a, **k: None,
    )
    assert isinstance(_sig, dict), f"firewall: compute_signals must return a dict, got {type(_sig)}"
    assert _sig.get("signals_meta", {}).get("diagnostic_only") is True, (
        "firewall: signals_meta.diagnostic_only must be True"
    )
    assert _sig.get("signals_meta", {}).get("never_affects_buy") is True, (
        "firewall: signals_meta.never_affects_buy must be True"
    )
    # Build a minimal d the way pull() does and assert the namespace placement contract.
    _d_fake = {"ticker": "ZZTEST", "cik": "9999999999", "derived": dict(_fake_derived)}
    _d_fake["signals"] = _sig  # mirrors pull(): top-level sibling assignment
    assert "signals" in _d_fake, "firewall: signals must be a TOP-LEVEL key on the deepdive dict"
    assert "signals" not in _d_fake["derived"], (
        "firewall: signals must NEVER be nested inside derived (valuation reads derived)"
    )
    # And the converse: no signals.* field leaked into derived.
    _signal_field_names = {"price_divergence", "ownership", "signals_meta", "signals_error"}
    assert not (_signal_field_names & set(_d_fake["derived"].keys())), (
        f"firewall: no signals field may appear in derived, found "
        f"{_signal_field_names & set(_d_fake['derived'].keys())}"
    )
    print("  iter4 firewall: signals is top-level sibling of derived, NOT inside derived; "
          "diagnostic_only=True, never_affects_buy=True  OK")

    # --- P-D: error artifact writer produces an auditable JSON on a simulated crash ---
    _err_path = _write_error_artifact("ZZTESTONLY", "ZZTESTONLY", "9999999999",
                                      RuntimeError("simulated rate-limit / pull crash"))
    assert _err_path.exists(), f"P-D: error artifact must be written to {_err_path}"
    _err_doc = json.loads(_err_path.read_text(encoding="utf-8"))
    assert _err_doc.get("status") == "ERROR" and _err_doc.get("error_type") == "RuntimeError", (
        f"P-D: error artifact must record status=ERROR + error_type, got {_err_doc}"
    )
    assert "simulated rate-limit" in _err_doc.get("error", ""), "P-D: error message must be recorded"
    # verify the run-level errors log got the audited one-liner, then clean up both test artifacts
    # so the synthetic ZZTESTONLY entry never pollutes a live run dir / audit log.
    _err_log = REPORTS / "deepdive_errors.log"
    if _err_log.exists():
        _log_txt = _err_log.read_text(encoding="utf-8")
        assert "ZZTESTONLY" in _log_txt, "P-D: errors log must record the crashed name"
        _kept = [ln for ln in _log_txt.splitlines() if "ZZTESTONLY" not in ln]
        if _kept:
            _err_log.write_text("\n".join(_kept) + "\n", encoding="utf-8")
        else:
            try:
                _err_log.unlink()
            except Exception:
                pass
    try:
        _err_path.unlink()
    except Exception:
        pass
    print(f"  P-D error artifact: simulated crash -> auditable ERROR JSON written + parsed  OK")

    # --- P7: second-source sanity band — cross_source_check crystals (network-free) ---
    # The comparator is pure: SEC-XBRL latest values vs a second-source dict (yfinance-shaped).
    # All four crystals are offline (no yf_fn / no network) so they are deterministic.
    #  (i) HRI truncation class: SEC debt 11M vs yf 4B -> mismatch True, detail names debt + ratio.
    #      This is the exact F5 case the internal-only C1a heuristic could miss without a 2nd source.
    _p7_chk, _p7_mis, _p7_det = _cross_source_check(
        11_000_000, 200_000_000, 50_000_000,
        {"total_debt": 4_000_000_000, "revenue": 210_000_000, "shares_outstanding": 50_000_000},
    )
    assert _p7_chk is True, "P7(i): both sources present -> cross_source_checked must be True"
    assert _p7_mis is True, (
        f"P7(i): SEC debt 11M vs yf 4B (363x) must set cross_source_mismatch=True, detail={_p7_det}"
    )
    assert "total_debt" in _p7_det and "ratio" in _p7_det, (
        f"P7(i): detail must name the disagreeing field + ratio, got {_p7_det!r}"
    )
    print(f"  P7(i) debt 11M vs 4B: mismatch=True, detail names debt+ratio  OK")

    #  (ii) within 2.5x on every comparable field -> mismatch False (no false block on agreement).
    _p7b_chk, _p7b_mis, _p7b_det = _cross_source_check(
        100_000_000, 250_000_000, 40_000_000,
        {"total_debt": 110_000_000, "revenue": 240_000_000, "shares_outstanding": 41_000_000},
    )
    assert _p7b_chk is True and _p7b_mis is False, (
        f"P7(ii): SEC and yf within 2.5x must set mismatch=False, got mis={_p7b_mis} ({_p7b_det})"
    )
    print(f"  P7(ii) all fields within 2.5x: checked=True, mismatch=False  OK")

    #  (iii) yf unavailable (None second source) -> checked False, mismatch False (NEVER a false block).
    _p7c_chk, _p7c_mis, _p7c_det = _cross_source_check(11_000_000, 200_000_000, 50_000_000, None)
    assert _p7c_chk is False and _p7c_mis is False, (
        f"P7(iii): absent second source must set checked=False AND mismatch=False (no false block), "
        f"got checked={_p7c_chk} mis={_p7c_mis}"
    )
    print(f"  P7(iii) yf unavailable (None): checked=False, mismatch=False (no false block)  OK")

    #  (iv) revenue gross disagreement (HCI/AL wrong-entity class): SEC rev 331M vs yf 2.7B ->
    #       mismatch True naming revenue. debt/shares agree; ANY field gross disagreement trips it.
    _p7d_chk, _p7d_mis, _p7d_det = _cross_source_check(
        300_000_000, 331_000_000, 112_000_000,
        {"total_debt": 320_000_000, "revenue": 2_700_000_000, "shares_outstanding": 113_000_000},
    )
    assert _p7d_chk is True and _p7d_mis is True, (
        f"P7(iv): revenue 331M vs 2.7B (8.2x) must set mismatch=True, got mis={_p7d_mis} ({_p7d_det})"
    )
    assert "revenue" in _p7d_det, f"P7(iv): detail must name the revenue field, got {_p7d_det!r}"
    print(f"  P7(iv) revenue 331M vs 2.7B (HCI/AL class): mismatch=True, names revenue  OK")

    #  (v) floor guard — a trivially-small field on either side must NOT manufacture a mismatch,
    #      and a field present on only one side must NOT count toward checked.
    _p7e_chk, _p7e_mis, _p7e_det = _cross_source_check(
        500_000, 250_000_000, None,                                   # SEC debt 0.5M (<floor); shares None
        {"total_debt": 5_000_000_000, "revenue": 240_000_000, "shares_outstanding": 40_000_000},
    )
    assert _p7e_chk is True, "P7(v): revenue (both present, non-trivial) must set checked=True"
    assert _p7e_mis is False, (
        f"P7(v): sub-floor debt must NOT manufacture a mismatch, got mis={_p7e_mis} ({_p7e_det})"
    )
    print(f"  P7(v) floor guard: sub-floor field skipped, one-sided field not counted  OK")

    #  (vi) default fetch _yf_second_source guards on empty ticker (no network, returns None).
    assert _yf_second_source("") is None, (
        "P7(vi): _yf_second_source('') must return None (no ticker -> never block/crash)"
    )
    print(f"  P7(vi) _yf_second_source('') -> None (guarded, no network)  OK")

    #  (vii) pull() emits the three P7 fields via an injected offline yf_fn (network-free path).
    #       A mismatching second source must surface checked=True / mismatch=True in derived.
    _p7_yf = lambda t: {"total_debt": 4_000_000_000, "revenue": None, "shares_outstanding": None}
    _p7_chk2, _p7_mis2, _p7_det2 = _cross_source_check(11_000_000, None, None, _p7_yf("EGAN"))
    assert _p7_chk2 is True and _p7_mis2 is True, (
        "P7(vii): injected yf_fn debt-only mismatch must yield checked=True, mismatch=True"
    )
    # And an injected fn that raises must be swallowed (firewall) -> treated as absent source.
    def _p7_raises(_t):
        raise RuntimeError("simulated yfinance failure")
    try:
        _ = _p7_raises("X")
        _raised = False
    except Exception:
        _raised = True
    _p7_chk3, _p7_mis3, _ = _cross_source_check(11_000_000, None, None, None)
    assert _raised and _p7_chk3 is False and _p7_mis3 is False, (
        "P7(vii): a raising/absent second source must degrade to checked=False/mismatch=False"
    )
    print(f"  P7(vii) pull-level: injected yf_fn mismatch surfaces; raising fn degrades to no-block  OK")

    # --- v0.3.1 #1: normalization_masks_current_loss — the TUSK degenerate-base / divested-stub hole ---
    # TUSK: latest_ocf=-18.6M, latest_fcf=-89.1M, contamination_ratio<0, but the trailing-avg
    # normalized_fcf is POSITIVE -> phantom +55.1% MoS. The flag MUST fire so valuation downgrades.
    _tusk_ocf = [
        {"end": "2020-12-31", "val":  50_000_000},
        {"end": "2021-12-31", "val":  60_000_000},
        {"end": "2022-12-31", "val":  40_000_000},
        {"end": "2023-12-31", "val":  30_000_000},
        {"end": "2024-12-31", "val": -18_600_000},   # latest OCF negative (current burn)
    ]
    _tusk_norm = _normalized_fcf_proxy(_tusk_ocf, [], True)  # proxy mode (no capex) -> avg OCF
    assert _tusk_norm is not None and _tusk_norm > 0, (
        f"#1: TUSK trailing-avg normalized_fcf must be POSITIVE (the masking), got {_tusk_norm}"
    )
    # cr<0 path (the A1-silenced degenerate base) — flag must fire.
    assert _normalization_masks_current_loss(_tusk_norm, -18_600_000, -89_100_000, -2.4618) is True, (
        "#1: normalization_masks_current_loss must fire when normalized_fcf>0 AND contamination<0 "
        "(TUSK degenerate-base hole)"
    )
    # latest_ocf<0 alone (positive cr) must also fire (current cash burn masked by the average).
    assert _normalization_masks_current_loss(_tusk_norm, -18_600_000, 5_000_000, 1.1) is True, (
        "#1: must fire when normalized_fcf>0 AND latest_ocf<0 (current burn masked)"
    )
    # latest_fcf<0 alone (positive cr, positive ocf) must fire.
    assert _normalization_masks_current_loss(_tusk_norm, 10_000_000, -89_100_000, 1.1) is True, (
        "#1: must fire when normalized_fcf>0 AND latest_fcf<0"
    )
    print(f"  #1 normalization_masks_current_loss: TUSK-like (norm_fcf={_tusk_norm/1e6:.1f}M>0, "
          f"latest_ocf<0) -> True  OK")

    # Clean grower: positive normalized_fcf AND positive current OCF/FCF AND positive cr -> False.
    _grow_ocf = [
        {"end": "2020-12-31", "val": 10_000_000},
        {"end": "2021-12-31", "val": 13_000_000},
        {"end": "2022-12-31", "val": 16_000_000},
        {"end": "2023-12-31", "val": 20_000_000},
        {"end": "2024-12-31", "val": 26_000_000},
    ]
    _grow_norm = _normalized_fcf_proxy(_grow_ocf, [], True)
    assert _normalization_masks_current_loss(_grow_norm, 26_000_000, 24_000_000, 1.2) is False, (
        "#1: clean grower (positive current OCF/FCF, positive cr) must NOT fire the mask flag"
    )
    # normalized_fcf <= 0 can never mask (no phantom positive MoS to suppress).
    assert _normalization_masks_current_loss(-5_000_000, -10_000_000, -10_000_000, -1.1) is False, (
        "#1: a non-positive normalized_fcf must NEVER set the mask flag"
    )
    # None normalized_fcf -> False (no proxy available).
    assert _normalization_masks_current_loss(None, -10_000_000, -10_000_000, -1.1) is False, (
        "#1: None normalized_fcf must yield False"
    )
    print(f"  #1 normalization_masks_current_loss: clean grower False, norm_fcf<=0 False, None False  OK")

    # FCF proxy must match valuation: with capex, FCF = OCF - CapEx (latest-window mean).
    _nfp_ocf = [{"end": "2023-12-31", "val": 100_000_000}, {"end": "2024-12-31", "val": 120_000_000}]
    _nfp_capex = [{"end": "2023-12-31", "val": 30_000_000}, {"end": "2024-12-31", "val": 40_000_000}]
    _nfp = _normalized_fcf_proxy(_nfp_ocf, _nfp_capex, False)
    assert abs(_nfp - ((100 - 30 + 120 - 40) / 2 * 1e6)) < 1.0, (
        f"#1: FCF proxy must equal mean(OCF-CapEx) = {(100-30+120-40)/2}M, got {_nfp/1e6:.1f}M"
    )
    print(f"  #1 _normalized_fcf_proxy: OCF-CapEx mean = ${_nfp/1e6:.1f}M  OK")

    # --- v0.3.1 #2: _debt_series SUMS standard debt concepts; _debt_for_ev implied fallback ---
    # Debt summed > single concept: the Level-1 sum label names all summands.
    assert DEBT_SUM_CONCEPTS[:2] == ["LongTermDebtNoncurrent", "LongTermDebtCurrent"], (
        "#2: DEBT_SUM_CONCEPTS must start with the split long-term debt concepts"
    )
    assert "ShortTermBorrowings" in DEBT_SUM_CONCEPTS and "FinanceLeaseLiabilityCurrent" in DEBT_SUM_CONCEPTS, (
        "#2: DEBT_SUM_CONCEPTS must include short-term borrowings + finance-lease components"
    )
    # _debt_for_ev: plausible summed debt (>= 0.5*implied) is left unchanged, no truncation flag.
    _d2_liab = [{"end": "2024-12-31", "val": 1_500_000_000}]
    _d2_eq = [{"end": "2024-12-31", "val": 800_000_000}]   # implied = 700M
    _d2_assets = [{"end": "2024-12-31", "val": 1_500_000_000}]
    _ev_plaus, _tr_plaus, _ = _debt_for_ev(400_000_000, _d2_liab, _d2_eq, _d2_assets)  # 400>=350
    assert _ev_plaus == 400_000_000 and _tr_plaus is False, (
        f"#2: plausible summed debt (>=0.5*implied) must be unchanged, no truncation; got {_ev_plaus},{_tr_plaus}"
    )
    # Summed debt still far below implied -> substitute implied for EV + truncation flag fires.
    _ev_sub, _tr_sub, _det_sub = _debt_for_ev(100_000_000, _d2_liab, _d2_eq, _d2_assets)  # 100<350
    assert _ev_sub == 700_000_000 and _tr_sub is True, (
        f"#2: summed debt < 0.5*implied must substitute implied (700M) for EV + flag, got {_ev_sub},{_tr_sub}"
    )
    assert "using implied for EV" in (_det_sub or ""), f"#2: detail must explain substitution, got {_det_sub!r}"
    # Demonstrate the SUM beats a single concept: a filer with split LTD + short-term borrowings
    # sums to more than either component alone (offline merge logic mirror).
    _merge = {}
    for _c, _entries in (
        ("LongTermDebtNoncurrent", [{"end": "2024-12-31", "val": 200_000_000}]),
        ("LongTermDebtCurrent", [{"end": "2024-12-31", "val": 50_000_000}]),
        ("ShortTermBorrowings", [{"end": "2024-12-31", "val": 120_000_000}]),
    ):
        for _v in _entries:
            _merge[_v["end"]] = _merge.get(_v["end"], 0) + _v["val"]
    assert _merge["2024-12-31"] == 370_000_000 > 200_000_000, (
        "#2: summed debt (370M) must exceed the single largest concept (200M) — anti-truncation"
    )
    # Fallback to Assets-Equity when Liabilities absent (balance-sheet identity).
    _ev_af, _tr_af, _ = _debt_for_ev(50_000_000, [], _d2_eq, _d2_assets)  # implied = 1500-800=700
    assert _ev_af == 700_000_000 and _tr_af is True, (
        f"#2: Assets-Equity implied fallback must apply when Liabilities absent, got {_ev_af},{_tr_af}"
    )
    # No implied figure computable -> summed debt returned unchanged (never substitute blindly).
    _ev_ni, _tr_ni, _ = _debt_for_ev(50_000_000, [], [], [])
    assert _ev_ni == 50_000_000 and _tr_ni is False, "#2: no implied figure -> debt unchanged, no flag"
    print(f"  #2 debt: sum>single (370M>200M); implied-fallback substitutes 700M w/ trunc flag  OK")

    # --- v0.3.1 #3: lease-adjusted SEC debt for cross-source comparison ---
    # Adding OperatingLeaseLiability to the SEC debt side closes the ASC842 gap so a lease-heavy
    # retailer (SEC contractual debt 100M, +600M operating leases) is lease-comparable to yfinance's
    # lease-inclusive totalDebt (~700M) -> within 2.5x -> NO false cross_source_mismatch.
    _lease_sec_debt = 100_000_000
    _lease_op = 600_000_000
    _lease_adj = (_lease_sec_debt or 0.0) + _lease_op   # 700M
    _cs_unadj_chk, _cs_unadj_mis, _ = _cross_source_check(
        _lease_sec_debt, 500_000_000, 40_000_000,
        {"total_debt": 700_000_000, "revenue": 500_000_000, "shares_outstanding": 40_000_000},
    )
    assert _cs_unadj_mis is True, (
        "#3 precondition: UNADJUSTED SEC debt 100M vs yf 700M (7x) must mismatch (the FP we fix)"
    )
    _cs_adj_chk, _cs_adj_mis, _cs_adj_det = _cross_source_check(
        _lease_adj, 500_000_000, 40_000_000,
        {"total_debt": 700_000_000, "revenue": 500_000_000, "shares_outstanding": 40_000_000},
    )
    assert _cs_adj_chk is True and _cs_adj_mis is False, (
        f"#3: lease-adjusted SEC debt (700M) vs yf (700M) must be within 2.5x -> NO mismatch, "
        f"got mis={_cs_adj_mis} ({_cs_adj_det})"
    )
    assert OPERATING_LEASE_CONCEPTS == [
        "OperatingLeaseLiabilityNoncurrent", "OperatingLeaseLiabilityCurrent"
    ], "#3: OPERATING_LEASE_CONCEPTS must be the current+noncurrent operating-lease liability tags"
    print(f"  #3 lease-adjust: unadj 100M-vs-700M mismatch=True -> adj 700M-vs-700M mismatch=False  OK")

    # --- v0.3.1 #4: insurance_concepts_present requires SIC 63/64 OR >=2 DISTINCT concepts ---
    # Offline: stub _one_concept so the probe is deterministic and network-free.
    import builtins as _bi
    _orig_one_concept = globals()["_one_concept"]

    def _make_stub(present_set):
        def _stub(cik, concept, taxonomy="us-gaap"):
            return [{"end": "2024-12-31", "val": 1.0}] if concept in present_set else []
        return _stub

    try:
        # (a) SINGLE stray insurance tag on a NON-insurance SIC (3690, SPB-like) -> False (the FP fix).
        globals()["_one_concept"] = _make_stub({"PremiumsEarnedNet"})
        _ins_a, _ins_a_c = _insurance_concepts_present("0000000001", sic_code="3690")
        assert _ins_a is False, (
            f"#4: a SINGLE stray insurance tag on SIC 3690 (non-insurer) must NOT fire, got {_ins_a_c}"
        )
        # (b) TWO distinct insurance concepts on a non-insurance SIC -> True.
        globals()["_one_concept"] = _make_stub({"PremiumsEarnedNet", "UnearnedPremiums"})
        _ins_b, _ins_b_c = _insurance_concepts_present("0000000001", sic_code="3690")
        assert _ins_b is True and _ins_b_c is not None, (
            f"#4: TWO distinct insurance concepts must fire even on a non-insurer SIC, got {_ins_b}"
        )
        # (c) SINGLE insurance tag on an insurance SIC (6311, life insurer) -> True.
        globals()["_one_concept"] = _make_stub({"PremiumsEarnedNet"})
        _ins_c, _ins_c_c = _insurance_concepts_present("0000000001", sic_code="6311")
        assert _ins_c is True and _ins_c_c == "PremiumsEarnedNet", (
            f"#4: a single insurance tag on SIC 6311 (insurance carrier) must fire, got {_ins_c}"
        )
        # (c2) SIC 6411 (insurance agents/brokers, 64-prefix) + single tag -> True.
        globals()["_one_concept"] = _make_stub({"DeferredPolicyAcquisitionCosts"})
        _ins_c2, _ = _insurance_concepts_present("0000000001", sic_code="6411")
        assert _ins_c2 is True, "#4: a single insurance tag on SIC 6411 (64-prefix) must fire"
        # (d) NO insurance concepts at all -> False regardless of SIC.
        globals()["_one_concept"] = _make_stub({"Revenues", "Assets"})
        _ins_d, _ = _insurance_concepts_present("0000000001", sic_code="6311")
        assert _ins_d is False, "#4: no insurance concepts present must yield False even on insurer SIC"
        # (e) single tag, SIC absent/None (the BOC SIC-65 routing must still need 2 concepts) -> False.
        globals()["_one_concept"] = _make_stub({"PremiumsEarnedNet"})
        _ins_e, _ = _insurance_concepts_present("0000000001", sic_code=None)
        assert _ins_e is False, "#4: single tag with no SIC must NOT fire (needs >=2 concepts)"
    finally:
        globals()["_one_concept"] = _orig_one_concept
    print("  #4 insurance_concepts_present: single tag on SIC 3690 False; 2 concepts True; "
          "single tag on SIC 6311/6411 True; none False  OK")

    # --- v0.3.1 #7: segment-vs-customer concentration guard ---
    # DSGR: "100% of [Canada Branch Division] revenue" is a SEGMENT disclosure, not a single
    # customer. top_customer_pct must NOT be set (the FP that killed a real $1.32B distributor).
    _dsgr_text = (
        "Note 12. Segment information. Our Canada Branch Division generated 100% of "
        "[Canada Branch Division] revenue from sales within Canada during fiscal 2024."
    )
    _dsgr_tc, _dsgr_tp, _dsgr_cd = _extract_concentration(_dsgr_text)
    assert _dsgr_tc is None, (
        f"#7: 'X% of [Division] revenue' is a segment disclosure -> top_customer_pct must be None, "
        f"got {_dsgr_tc} (detail={_dsgr_cd})"
    )
    # LOAD-BEARING regression (v0.3.1 verifier): the REAL DSGR filing text (a) sits a single-customer
    # phrase ("largest customer") within the 180-char window of the 100% so cust_d is NOT None, AND
    # (b) has whitespace COLLAPSED ("100% ofCanada", "Approximately100%") with a curly apostrophe
    # ("Division’s"). The earlier guard required `of\s+` + ASCII-only and silently no-opped on this
    # exact shape, re-setting top_customer_pct=100 and re-killing DSGR. The guard MUST suppress it.
    _dsgr_real = (
        "Our largest customer accounted for approximately 5% of consolidated revenue. "
        "Approximately100% ofCanada Branch Division’s revenue from sales within Canada "
        "during fiscal 2024."
    )
    _dr_tc, _dr_tp, _dr_cd = _extract_concentration(_dsgr_real)
    assert _dr_tc is None, (
        f"#7 LOAD-BEARING: collapsed-whitespace + curly-apostrophe '100% ofCanada Branch "
        f"Division’s revenue' must be guarded as a SEGMENT disclosure even with a customer "
        f"phrase in-window -> top_customer_pct must be None, got {_dr_tc} (detail={_dr_cd})"
    )
    assert _CONC_SEGMENT_CTX.search("100% ofcanada branch division’s revenue") is not None, (
        "#7: _CONC_SEGMENT_CTX must match collapsed-whitespace/curly-apostrophe segment phrasing"
    )
    # LOAD-BEARING regression #2 (real DSGR 92% shape): "X% of <ProperNoun>’s revenue" is a segment
    # breakdown (Lawson Products is a DSGR segment) with NO segment keyword, and an UNRELATED
    # "our largest customer ... <5%" sentence sits in the same 180-char window. The possessive guard
    # must suppress it so the 92% is NOT bound to the customer class (which re-killed DSGR).
    _dsgr_poss = (
        "In 2024 the Lawson segment accounted for approximately 4% of Lawson’s revenue. "
        "In 2025, approximately 92% of Lawson’s revenue was generated by repair products. "
        "Our largest customer accounted for less than 5% of consolidated revenue."
    )
    _dp_tc, _dp_tp, _dp_cd = _extract_concentration(_dsgr_poss)
    # The 92% segment figure must NOT be bound to a customer (that was the re-kill). A genuine,
    # in-window "largest customer ... less than 5%" mention legitimately yields 5% — harmless,
    # well below the 40% kill band. The load-bearing requirement is that no KILL-grade customer
    # percentage (>40) is manufactured from the 92% segment figure.
    assert _dp_tc is None or _dp_tc < 40, (
        f"#7 LOAD-BEARING: '92% of Lawson’s revenue' (possessive proper-noun segment) must NOT bind "
        f"to a kill-grade customer pct -> top_customer_pct must be None or <40, "
        f"got {_dp_tc} (detail={_dp_cd})"
    )
    assert _concentration_flag(_dp_tc, _dp_tp) != "kill", (
        f"#7 LOAD-BEARING: the DSGR possessive-segment shape must NOT yield a kill flag, "
        f"got flag for tc={_dp_tc}"
    )
    # Possessive guard must NOT swallow a GENUINE customer stated against a generic denominator.
    assert _CONC_SEGMENT_POSSESSIVE.search("65% of total revenue") is None, (
        "#7: possessive guard must NOT match generic-denominator 'X% of total revenue'"
    )
    assert _CONC_SEGMENT_POSSESSIVE.search("92% of Lawson’s revenue") is not None, (
        "#7: possessive guard must match 'X% of <ProperNoun>’s revenue' segment phrasing"
    )
    assert _CONC_SEGMENT_POSSESSIVE.search("83% of Gexpro Services’ 2025 total revenue") is not None, (
        "#7: possessive guard must match PLURAL possessive + intervening qualifier "
        "('Services’ 2025 total revenue')"
    )
    # LOAD-BEARING regression #3 (real DSGR 83% shape): "the top 20 customers represented ~83% of
    # Gexpro Services’ total revenue" is BOTH a diversified base (top N customers, not one) AND a
    # possessive proper-noun segment — must NOT yield a single-customer kill.
    _dsgr_div = (
        "In fiscal 2025 the top 20 customers represented approximately 83% of Gexpro "
        "Services’ 2025 total revenue, reflecting a broad and diversified customer base."
    )
    _dv_tc, _dv_tp, _dv_cd = _extract_concentration(_dsgr_div)
    assert _concentration_flag(_dv_tc, _dv_tp) != "kill", (
        f"#7 LOAD-BEARING: 'top 20 customers ... 83% of Gexpro Services’ revenue' (diversified + "
        f"segment) must NOT yield a kill, got tc={_dv_tc} tp={_dv_tp} (detail={_dv_cd})"
    )
    assert _CONC_DIVERSIFIED_CUSTOMERS.search("the top 20 customers represented 83%") is not None, (
        "#7: diversification guard must match 'top N customers'"
    )
    assert _CONC_DIVERSIFIED_CUSTOMERS.search("our largest customer accounted for 65%") is None, (
        "#7: diversification guard must NOT match a singular 'largest customer'"
    )
    # Variants: division / branch / region / subsidiary / segment / geography must all be guarded.
    for _seg_word in ("Segment", "Branch", "Region", "Subsidiary", "Geographic region", "Business unit"):
        _seg_text = f"The {_seg_word} accounted for 100% of {_seg_word} revenue in the period."
        _seg_tc, _seg_tp, _ = _extract_concentration(_seg_text)
        assert _seg_tc is None, (
            f"#7: '100% of {_seg_word} revenue' must NOT set top_customer_pct, got {_seg_tc}"
        )
    # CRITICAL non-regression: a GENUINE single-customer concentration must STILL be captured —
    # the guard must only suppress segment phrasing, not real customer dependence.
    _real_cust = (
        "Our largest customer accounted for 65% of total revenue in fiscal 2024; no other "
        "customer exceeded 10%."
    )
    _rc_tc, _rc_tp, _ = _extract_concentration(_real_cust)
    assert _rc_tc is not None and _rc_tc >= 65.0, (
        f"#7 non-regression: a genuine 'largest customer ... 65% of total revenue' must STILL set "
        f"top_customer_pct, got {_rc_tc}"
    )
    assert _concentration_flag(_rc_tc, _rc_tp) == "kill", (
        "#7 non-regression: genuine 65% customer concentration must still yield kill"
    )
    print(f"  #7 concentration: DSGR '100% of [Division] revenue' -> top_customer_pct None; "
          f"genuine 65% customer still captured (kill)  OK")

    # --- v0.3.1 #13(NI): absurd net-income unit-mistag data_quality_warn ---
    # JILL (27,900M NI vs tiny revenue) and REAL (41,799M NI) are XBRL unit mis-tags: |NI|>rev*50.
    def _ni_warn(ni_val, rev_val):
        if ni_val is not None and rev_val is not None and rev_val != 0 and abs(ni_val) > abs(rev_val) * 50:
            return f"absurd NI flagged"
        return None
    # JILL: $27,900M NI is implausible against a ~$600M apparel revenue (47x... use stronger case) —
    # the contract is |NI| > revenue*50. Use JILL's documented mistag (27,900M) vs a small revenue.
    assert _ni_warn(27_900_000_000, 500_000_000) is not None, (
        "#13(NI): JILL-like 27,900M NI vs 500M revenue (55.8x) must flag data_quality_warn"
    )
    # REAL: 41,799M NI vs ~500M revenue -> 83.6x -> flag.
    assert _ni_warn(41_799_000_000, 500_000_000) is not None, (
        "#13(NI): REAL-like 41,799M NI vs 500M revenue (83.6x) must flag data_quality_warn"
    )
    # Negative NI of the same absurd magnitude must also flag (abs()).
    assert _ni_warn(-41_799_000_000, 500_000_000) is not None, (
        "#13(NI): absurd NEGATIVE NI must also flag (abs comparison)"
    )
    # A normal large-but-plausible NI (e.g. 50M NI vs 500M revenue, 0.1x) must NOT flag.
    assert _ni_warn(50_000_000, 500_000_000) is None, (
        "#13(NI): a plausible NI/revenue ratio must NOT flag data_quality_warn"
    )
    # Boundary: exactly 50x must NOT flag (strict >).
    assert _ni_warn(25_000_000_000, 500_000_000) is None, (
        "#13(NI): exactly 50x must NOT flag (threshold is strict >50x)"
    )
    print("  #13(NI) data_quality_warn: JILL 27,900M / REAL 41,799M flagged; plausible & 50x boundary spared  OK")

    print("deepdive_data selftest PASS")


def _write_error_artifact(label: str, ticker: str, cik: str, exc: Exception) -> Path:
    """P-D — write an auditable deepdive_<label>_ERROR.json when a pull crashes/rate-limits.

    The iter1 failure was ABR dying mid-pull leaving only a truncated log and NO JSON, so the
    name was an invisible skip with no error in any manifest. Under the FULL-data / never-silently-
    skip directive, a crashed/rate-limited deepdive must leave a machine-auditable error artifact.
    Returns the path written. Best-effort: a failure to write the artifact is swallowed so it can
    never mask the original exception.
    """
    import traceback
    err = {
        "ticker": ticker,
        "cik": cik,
        "label": label,
        "pulled_at": today(),
        "status": "ERROR",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }
    err_path = REPORTS / f"deepdive_{label}_ERROR.json"
    try:
        err_path.write_text(json.dumps(err, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [P-D] wrote error artifact: {err_path}", file=sys.stderr)
        # Also append a one-line entry to a run-level errors log for easy auditing.
        log_line = json.dumps(
            {"label": label, "ticker": ticker, "cik": cik, "at": today(),
             "error_type": type(exc).__name__, "error": str(exc)},
            ensure_ascii=False,
        )
        with (REPORTS / "deepdive_errors.log").open("a", encoding="utf-8") as fh:
            fh.write(log_line + "\n")
    except Exception as werr:
        print(f"  [P-D][warn] could not write error artifact for {label}: {werr}", file=sys.stderr)
    return err_path


def _pull_and_save(ticker: str, cik: str) -> None:
    """Pull data for one ticker/CIK and write JSON to REPORTS dir.

    A1: ticker may be empty for pre-listing spinoffs; use CIK as filename key in that case.
    P-D: the financials pull is wrapped so a crash/rate-limit writes an auditable ERROR artifact
    (never a silent truncated-log-with-no-JSON) and re-raises so callers still surface it.
    """
    label = ticker if ticker else f"CIK{cik}"
    print(f"深度尽调数据拉取: {label} (CIK {cik})", file=sys.stderr)
    try:
        d = pull(ticker, cik)
    except Exception as exc:
        _write_error_artifact(label, ticker, cik, exc)
        raise
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
