"""_deepdive_flags.py — derived-flag computations extracted from deepdive_data.py.

Pure refactor: the concentration extractor + flag composer, the wrong-entity / low-revenue-loss /
insurance / lessor / foreign-filer guards, the debt cross-source / truncation helpers, and the
trajectory + contamination + normalization-mask derived fields. No behavior change — every symbol
was moved verbatim from deepdive_data.py and is re-exported there so the public module path is
unchanged. Imports from _common and _deepdive_concepts only; NEVER from deepdive_data (no circular
import).

The two helpers that probe XBRL (_insurance_concepts_present, _lessor_asset_heavy) resolve the
fetcher through the _deepdive_concepts module namespace (_dc._one_concept) so deepdive_data's
selftest, which patches _deepdive_concepts._one_concept, still controls them.
"""
from __future__ import annotations
import re
import time
from pathlib import Path
import sys

# sys.path shim so this module can be imported when tools/ is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _deepdive_concepts as _dc
from _deepdive_concepts import (
    INSURANCE_CONCEPTS,
    LESSOR_SIC_CODES,
    LEASE_INCOME_CONCEPTS,
    PPE_FLEET_CONCEPTS,
    _LESSOR_PPE_RATIO,
    _DEBT_STALE_DAYS,
    _get_sec_tickers,
)

# P3, concentration extraction. Magnitude-based, sourced from concentration-footnote numerics
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

# v0.3.1 #7, SEGMENT-disclosure guard. DSGR's "100% of [Canada Branch Division] revenue" is a
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
# for the wrong reason, no customer phrase near the pct, masking the regex break).
_CONC_SEGMENT_CTX = re.compile(
    r"%?\s*of\s*\[?\s*(?:(?:the|our|its|total)\s+)?"
    r"(?:[a-z][\w&./’'-]+\s*){0,4}?"
    r"(?:segment|division|branch|region|geograph|subsidiar|business unit|reportable|reporting unit|"
    r"operating segment|product line|category)"
    r"[\w\s&./’'\]\[-]{0,40}?revenue",
    re.IGNORECASE,
)
# v0.3.1 #7 (cont.), POSSESSIVE proper-noun segment guard. The real DSGR filing also says
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
    # ProperNoun (1-4 Capitalized tokens), then a possessive apostrophe, trailing "s" OPTIONAL so
    # PLURAL possessives ("Gexpro Services’ revenue") match too, then up to ~20 chars of qualifier
    # (a fiscal year, "total", "consolidated") before "revenue" ("Services’ 2025 total revenue").
    r"[A-Z][\w&.'-]+(?:\s+[A-Z][\w&.'-]+){0,3}\s*[’'](?:s)?\s+[\w\s]{0,20}?revenue",
)
# v0.3.1 #7 (cont.), DIVERSIFICATION guard. "the top 20 customers represented approximately 83%"
# / "our 15 largest customers" is a DIVERSIFIED base (plural N customers), the OPPOSITE of single-
# counterparty concentration, it must never produce a kill. Real DSGR states exactly this for the
# Gexpro Services segment. Distinct from the singular _CONC_SINGLE_CUSTOMER ("our largest customer").
_CONC_DIVERSIFIED_CUSTOMERS = re.compile(
    r"top\s+\d+\s+customers|\d+\s+largest\s+customers|our\s+\d+\s+largest\b",
    re.IGNORECASE,
)


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
            if _dc._one_concept(cik, concept):
                present.append(concept)
                # Insurance SIC + any single concept is already conclusive, stop probing early.
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


def _lessor_asset_heavy(
    cik: str,
    sic_code: str | None,
    assets_series: list,
    lease_income_present: bool | None = None,
    ppe_fleet_val: float | None = None,
    rental_lease_revenue: bool | None = None,
) -> tuple[bool, str | None]:
    """v0.3.2 #8 — detect an asset-heavy leasing/rental business (railcar/equipment/auto lessor).

    Returns (lessor_asset_heavy, detail). valuation forces fcf_cap_model_unsuitable=True (route to
    lease-fleet NAV) when this is True EVEN IF debt/assets < 0.62 — closing the GBX/RAIL hole where
    a textbook NAV candidate was mis-valued on trough-cycle FCF.

    Fires when ANY of three independent leasing signals is present:
      (a) SIC in LESSOR_SIC_CODES (leasing/rental businesses), OR
      (b) an operating/finance lease-INCOME revenue concept is present (lease_income_present), OR
      (c) (PP&E or lease-fleet)/total_assets is very high (>_LESSOR_PPE_RATIO) AND the filer reports
          rental/lease revenue (rental_lease_revenue) — covers lessors on a generic industrial SIC.

    The lease_income_present / ppe_fleet_val / rental_lease_revenue inputs are normally probed by
    the caller (pull) so the network probes are shared; when not supplied they are probed here from
    companyconcept (so the helper is self-contained for direct callers/tests). Network-safe: any
    probe failure degrades to "signal absent", never a crash and never a false fire.
    """
    sic = str(sic_code or "")
    reasons: list[str] = []

    # (a) leasing/rental SIC.
    if sic in LESSOR_SIC_CODES:
        reasons.append(f"lessor_sic:{sic}")

    # (b) lease-income revenue concept present.
    if lease_income_present is None:
        lease_income_present = False
        for concept in LEASE_INCOME_CONCEPTS:
            try:
                if _dc._one_concept(cik, concept):
                    lease_income_present = True
                    break
            except Exception:
                pass
            time.sleep(0.1)
    if lease_income_present:
        reasons.append("lease_income_concept_present")

    # (c) very-high PP&E/lease-fleet ratio AND rental/lease revenue.
    latest_assets = None
    if assets_series:
        latest_assets = assets_series[-1].get("val")
    if ppe_fleet_val is None:
        ppe_fleet_val = None
        best_end = None
        for concept in PPE_FLEET_CONCEPTS:
            try:
                entries = _dc._one_concept(cik, concept)
            except Exception:
                entries = []
            time.sleep(0.1)
            for v in entries:
                if v.get("val") is not None and (best_end is None or v["end"] >= best_end):
                    best_end = v["end"]
                    ppe_fleet_val = v["val"]
    if rental_lease_revenue is None:
        # When not supplied, treat a present lease-income concept as the rental-revenue signal.
        rental_lease_revenue = bool(lease_income_present)
    if (ppe_fleet_val is not None and latest_assets not in (None, 0)
            and (ppe_fleet_val / latest_assets) > _LESSOR_PPE_RATIO
            and rental_lease_revenue):
        reasons.append(
            f"ppe_fleet_ratio={ppe_fleet_val / latest_assets:.2f}>{_LESSOR_PPE_RATIO}+rental_rev"
        )

    if reasons:
        return True, ";".join(reasons)
    return False, None


def _foreign_filer_unvaluable(
    form_used: str | None,
    rev_series: list,
    ni_series: list,
    ocf_series: list,
) -> tuple[bool, str | None]:
    """v0.3.2 #11 — label a foreign 20-F/40-F filer whose financials are STILL empty after the IFRS
    concept cascade, so the abstain is CLEARLY flagged (not a silent null).

    Returns (foreign_filer_unvaluable, detail). True when the filer used a foreign form (20-F/40-F)
    AND all three primary financial series (revenue, net income/profit, OCF) are empty even after
    the us-gaap+ifrs-full merge. valuation/report can then say "foreign filer — un-valuable from
    EDGAR" instead of presenting a bare intrinsic_band_unavailable null.

    Graceful abstain only — never crashes, never a false BUY. A foreign filer that DID recover
    financials via the IFRS cascade returns (False, None) (it is valuable).
    """
    form = str(form_used or "")
    is_foreign = form.startswith("20-F") or form.startswith("40-F")
    if not is_foreign:
        return False, None
    has_rev = bool(rev_series)
    has_ni = bool(ni_series)
    has_ocf = bool(ocf_series)
    if not (has_rev or has_ni or has_ocf):
        return True, (
            f"foreign filer (form={form}) returned EMPTY revenue/net-income/OCF even after the "
            f"us-gaap+ifrs-full concept cascade — un-valuable from EDGAR (graceful abstain)"
        )
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
        # v0.3.1 #7, SEGMENT-disclosure guard. If THIS percentage is "X% of [<segment/division/
        # branch/region/subsidiary> ...] revenue" (a segment/geography breakdown), it is NOT
        # customer/program concentration, skip it entirely so DSGR's "100% of [Canada Branch
        # Division] revenue" never mis-sets top_customer_pct. Anchor the segment match to the text
        # starting AT the percent (the "% of ... revenue" tail) so a nearby unrelated segment word
        # elsewhere in the window does not suppress a genuine customer percentage.
        tail = low[m.start():hi]
        if _CONC_SEGMENT_CTX.search(tail):
            continue
        # v0.3.1 #7 (cont.), POSSESSIVE proper-noun segment guard, on ORIGINAL-CASE tail (capitalization
        # is the discriminator). "X% of Lawson’s revenue" / "X% of [Segment]’s revenue" is a segment
        # breakdown, not customer concentration, skip so an unrelated "largest customer" sentence in
        # the window can't bind this segment percentage to the customer class (the DSGR 92% re-kill).
        orig_tail = tenk_text[m.start():hi]
        if _CONC_SEGMENT_POSSESSIVE.search(orig_tail):
            continue
        # v0.3.1 #7 (cont.), DIVERSIFICATION guard. "the top 20 customers represented ~83%" is a
        # diversified base (the opposite of single-counterparty risk). If a plural "top N customers"
        # phrase sits in the window AND it is NEARER the percent than any single-customer phrase,
        # this percentage is a diversification disclosure, not a kill, skip it. (Nearness so a
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
        # resolve to customer, named-counterparty dependence is the harder kill-flag.
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
    # arises when the 5yr-avg base is negative (negative FCF/OCF normalization base), then
    # cr<1.0 / cr<0.8 pass TRIVIALLY for any negative number and the veto fires on garbage
    # (BWIN fired at cr=-2.4618). Require 0 < cr on BOTH flags so a negative/degenerate base can
    # never trip the veto. (cr==0 is likewise excluded: a zero latest base is not a meaningful
    # contamination signal.)
    out["fundamental_decline_flag"] = bool(
        out["rev_slope_sign"] < 0
        and cr is not None and 0 < cr < 1.0
        and out["latest_below_avg"]
    )

    # P-A: peak_contamination_flag, independent of rev_slope_sign. Catches the V-shape value
    # trap (trough->peak->rollover) where the all-window slope is +1 so fundamental_decline_flag
    # never fires, yet the normalization base is past-peak-contaminated (<0.8) AND the company is
    # currently loss-making. NRP: cr=0.7445, latest_below_avg=True, NI=-84.8M -> True while its
    # rev_slope_sign=+1 keeps fundamental_decline_flag=False.
    # A1: same 0 < cr lower bound as fundamental_decline_flag, a negative cr must not trip it.
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


# v0.3.1 #1, normalization window (years) for the producer-side normalized-FCF proxy. Mirrors
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


def distress_core4(
    latest_ocf: float | None,
    latest_ebit: float | None,
    latest_retained_earnings: float | None,
    latest_equity: float | None,
    latest_assets: float | None,
    latest_current_assets: float | None,
    latest_current_liabilities: float | None,
    latest_liabilities: float | None,
) -> dict:
    """CORE-4 point-in-time fundamental DISTRESS rank — the de-risk layer's blowup predictor.

    Out-of-sample-validated (docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md): over a 25-cell
    survivorship-safe PIT panel (non-financial operating companies, n=412, 55 forward-12mo blowups
    <-40%), the count of these four mechanism-grounded distress flags concentrates blowups far above
    base rate — at the kill cutoff (score>=3): precision 35.4% vs 13.3% base (lift 2.65x), recall 62%;
    ticker-cluster bootstrap 95% CI on the top-quintile lift = [1.73, 3.00], P(lift<=1)=0 over 5000
    resamples. The cliff is sharp: score 0-2 ~5-9% blowup, score 3 = 25%, score 4 = 41.7%.

    Each flag is from PIT fundamentals ONLY (no forward / price info), grounded in distress theory:
      * neg_ocf       — operating cash flow < 0
      * neg_margin    — operating income (EBIT) < 0
      * accum_deficit — retained earnings < 0
      * low_altman    — Altman Z'' (emerging-market / non-manufacturer variant) < 1.1:
                          Z'' = 6.56*WC/TA + 3.26*RE/TA + 6.72*EBIT/TA + 1.05*Equity/Liab
                        (computed only when all components are present and TA, Liab > 0).

    Scope: operating companies. Banks/insurers are NOT in scope (their distress is NIM/NPL/
    deposit-flight, a different model) and already route to financial_sic / abstain upstream.

    Returns {distress_score (0-4), distress_flags (list[str]), distress_kill (score>=3),
             distress_altman_z (float|None)}. distress_kill is ANDed into the kill-flag count, so a
    high-distress name buckets to AVOID (the bucket a de-risk scanner is graded on) regardless of
    cheapness — a distressed name blows up whether or not it screens cheap.
    """
    flags: list[str] = []
    if latest_ocf is not None and latest_ocf < 0:
        flags.append("neg_ocf")
    if latest_ebit is not None and latest_ebit < 0:
        flags.append("neg_margin")
    if latest_retained_earnings is not None and latest_retained_earnings < 0:
        flags.append("accum_deficit")
    z = None
    if (None not in (latest_current_assets, latest_current_liabilities, latest_assets,
                     latest_retained_earnings, latest_ebit, latest_equity, latest_liabilities)
            and latest_assets > 0 and latest_liabilities > 0):
        x1 = (latest_current_assets - latest_current_liabilities) / latest_assets
        x2 = latest_retained_earnings / latest_assets
        x3 = latest_ebit / latest_assets
        x4 = latest_equity / latest_liabilities
        z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    if z is not None and z < 1.1:
        flags.append("low_altman")
    score = len(flags)
    return {
        "distress_score": score,
        "distress_flags": flags,
        "distress_kill": score >= 3,
        "distress_altman_z": z,
    }
