"""Derived financial flags and contractual-debt evidence helpers.

The helpers are re-exported by deepdive_data.py. Concept fetches use the
_deepdive_concepts namespace, avoiding a circular import.
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

# Concentration magnitude comes from filing footnotes; companyconcept does not expose
# dimensional segment members. Associate each percentage with its own context.
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
_CONC_SHARE_PREDICATE = re.compile(
    r"\b(?:accounts? for|accounted for|represents?|represented|constitutes?|constituted|"
    r"comprises?|comprised|totals?|totaled|generates?|generated|contributes?|contributed|"
    r"provides?|provided|makes? up|made up|is|are|was|were)\b",
    re.IGNORECASE,
)
_CONC_SHARED_MODIFIERS = re.compile(
    r"(?:(?:it|they)\b\s*)?"
    # Recognize grammatical modifiers explicitly; a word ending in -ly may be a noun.
    # Unrecognized prefixes retain an ambiguity note instead of borrowing a subject.
    r"(?:(?:previously|subsequently|initially|eventually|ultimately|currently|formerly|"
    r"lately|recently|frequently|infrequently|regularly|usually|occasionally|generally|"
    r"consistently|repeatedly|continually|continuously|invariably|primarily|principally|"
    r"mainly|mostly|largely|partially|partly|substantially|significantly|approximately|"
    r"roughly|nearly|only|merely|solely|completely|entirely|directly|indirectly|jointly|"
    r"collectively|separately|individually|effectively|also|still|already|then|now|always|often|sometimes|never|"
    r"almost|even|just|again|nevertheless|nonetheless|however|therefore|thus|hence|"
    r"otherwise|meanwhile|instead|likewise|furthermore|moreover|indeed|has|have|had|will|"
    r"would|could|may|might|did|do|does|is|are|was|were|be|been|being|not)\b\s*|"
    r"(?:in\s+(?:total|aggregate|all|effect|fact|part|practice)|on\s+average|at\s+times)\b\s*|"
    r"(?:in|during|throughout|over|for)\s+"
    r"(?:(?:[a-z][a-z-]*|\d+)\s+){0,5}"
    r"(?:years?|quarters?|periods?|months?|weeks?)\b\s*)*",
    re.IGNORECASE,
)
# These relations attribute the filer's revenue to a customer or its group.
# Other possessive heads do not establish that revenue relationship.
_CONC_CUSTOMER_RELATION = re.compile(r"(?:its|their)\s+(?:orders|purchases|affiliates)\b")
_CONC_ENTITY_NAME = re.compile(
    r"\b[A-Z][\w.'-]*(?:\s+(?:(?:and|of|the)\s+)?[A-Z][\w.'-]*)*"
)
_CONC_REVENUE_TERM = re.compile(
    r"revenue|net sales|product sales|of (?:our |its |total )?sales|"
    r"accounts receivable|receivable",
    re.IGNORECASE,
)
_CONC_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
# How far (chars) a percentage may sit from its qualifying context phrase.
_CONC_WINDOW = 180
_CONC_NAME_DOTS = re.compile(
    r"\b(?:[A-Za-z]\.\s*){2,}|\b[A-Z][a-z0-9]+(?:\.[A-Z][a-z0-9]+)+\b|"
    r"\b(?i:St|Ste|Mt|Dr|Jr|Sr|Inc|Corp|Co|Ltd|Pte|Pty|Intl|Assn|Bros)\.(?=\s|[’',)]|$)|"
    r"\d+\.\d+"
)
_CONC_CLAUSE_END = re.compile(r"[.!?;:,]")
_CONC_AGGREGATE_END = re.compile(
    r"%\s*of\s*(?:(?:the|our|its)\s+)?"
    r"(?P<aggregate>(?:(?:total|consolidated|net|combined|overall|company|group)\s+)?)"
    r"(?:revenues?|sales|receivables?)\b\s*"
    r"(?P<boundary>[.!?;:,]|(?:and|but|while|whereas)\b)",
    re.IGNORECASE,
)

# Segment or geography revenue percentages must not become customer concentration.
# Bind the denominator to this percentage and its clause. Accept collapsed whitespace
# and both apostrophe forms, preserving genuine customer percentages in nearby clauses.
_CONC_SEGMENT_CTX = re.compile(
    r"%?\s*of\s*\[?\s*(?:(?:the|our|its|total)\s+)?"
    r"(?:[a-z][\w&./’'-]+\s*){0,4}?"
    r"(?:segment|division|branch|region|geograph|subsidiar|business unit|reportable|reporting unit|"
    r"operating segment|product line|category)"
    r"[\w\s&./’'\]\[-]{0,40}?revenue",
    re.IGNORECASE,
)
# A capitalized possessive denominator can identify a segment's own revenue.
# Match original case and exclude generic company-wide denominator words.
_CONC_SEGMENT_POSSESSIVE = re.compile(
    r"%\s*of\s*"
    r"(?!(?:the\s+)?(?:total|consolidated|net|company|group|combined|its|our|all)\b)"
    # Match one to four capitalized tokens and singular or plural possessives.
    # Allow a short qualifier before revenue.
    r"[A-Z][\w&.'-]+(?:\s+[A-Z][\w&.'-]+){0,3}\s*[’'](?:s)?\s+[\w\s]{0,20}?revenue",
)
# Plural customer groups describe diversification rather than single-counterparty risk.
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

    Loss relative to revenue is a financial-shape check, not an entity-identity check.
    The low_revenue_loss_ratio and low_revenue_loss_ratio_extreme flags express those
    advisory and blocking tiers separately.

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

    # Loss-to-revenue ratios are handled by the separate financial-shape flags.

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
      Surface the advisory label without changing eligibility.
    - ratio > 20.0 also sets low_revenue_loss_ratio_extreme, which blocks buy_eligible.

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

    Probes INSURANCE_CONCEPTS via companyconcept. A corroborated insurance signal
    routes to NAV/abstention even when the registered SIC is non-financial.

    A single stray accounting tag is insufficient. Require either:
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

    Returns (lessor_asset_heavy, detail). Valuation forces NAV routing when this is
    true even below the debt/assets threshold.

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
    """Check contractual-debt staleness without inferring debt from balance-sheet totals.

    The first return value remains for compatibility. A low debt-to-liabilities ratio
    does not establish truncation: liabilities include obligations other than debt.
    """
    if not debt_series or not assets_series:
        return False, False, None

    from datetime import date

    try:
        debt_date = date.fromisoformat(debt_series[-1]["end"])
        assets_date = date.fromisoformat(assets_series[-1]["end"])
    except (KeyError, TypeError, ValueError):
        return False, False, None
    return False, (assets_date - debt_date).days > _DEBT_STALE_DAYS, None


def _debt_for_ev(
    summed_debt: float | None,
    liabilities_series: list,
    equity_series: list,
    assets_series: list,
) -> tuple[float | None, bool, str | None]:
    """Preserve contractual debt and disclose missing or invalid debt evidence.

    Assets minus equity gives total liabilities, which includes non-debt items.
    Liabilities minus equity has no contractual-debt interpretation. Neither can
    replace debt. The balance-sheet arguments and substitution flag are retained
    for callers using the existing interface.
    """
    from math import isfinite

    if summed_debt is None:
        return None, False, "Contractual debt unavailable; balance-sheet totals do not establish debt."
    if (isinstance(summed_debt, bool) or not isinstance(summed_debt, (int, float))
            or not isfinite(summed_debt) or summed_debt < 0):
        return None, False, "Contractual debt is invalid; no replacement inferred from balance-sheet totals."
    return summed_debt, False, None


def _extract_concentration(tenk_text: str) -> tuple[float | None, float | None, str | None]:
    """P3 — magnitude-based revenue/customer concentration from filing footnote numerics.

    companyconcept XBRL does NOT expose dimensional segment members, so the only mechanical
    source for the magnitude is the concentration-footnote text the filing already provides.
    A single fixed substring cannot cover the supported disclosure forms.

    Bind each percentage to a revenue denominator and single customer/program in the same
    statement. Other percentages delimit its context unless they form a numeric list sharing
    a denominator. Preserve abbreviation/name dots and appositive commas. Take the maximum
    per class; the nearest qualifying phrase assigns the class, with ties going to customer.

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
    ambiguous_clause = False
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
        original_window = tenk_text[lo:hi]
        protected = [span.span() for span in _CONC_NAME_DOTS.finditer(original_window)]
        boundaries = {punct.span() for punct in re.finditer(r"[.!?;]", original_window)
                      if not any(start <= punct.start() < end for start, end in protected)}
        # An aggregate denominator ends its statement even when collapsed spacing
        # resembles a dotted brand name, such as "total Revenue.Next sentence".
        boundaries.update(end.span("boundary") for end in _CONC_AGGREGATE_END.finditer(original_window)
                          if end.group("aggregate") or not any(
                              start <= end.start("boundary") < stop for start, stop in protected))
        anchor = m.start() - lo
        before = max((end for start, end in boundaries if end <= anchor), default=0)
        after = min((start for start, end in boundaries if start >= anchor), default=len(original_window))
        hi, lo = lo + after, lo + before

        # A list such as "55%, 45%, and 35% of revenue" shares its subject and
        # denominator. A different percentage assertion cannot lend either one.
        percentages = list(_CONC_PCT.finditer(low, lo, hi))
        index = next(i for i, pct_match in enumerate(percentages) if pct_match.start() == m.start())
        first = last = index
        while first > 0 and re.fullmatch(r"[\s,]*(?:(?:and|or)\s*)?",
                                        low[percentages[first - 1].end():percentages[first].start()]):
            first -= 1
        while last + 1 < len(percentages) and re.fullmatch(r"[\s,]*(?:(?:and|or)\s*)?",
                                                          low[percentages[last].end():percentages[last + 1].start()]):
            last += 1
        if first > 0:
            lo = percentages[first - 1].end()
        if last + 1 < len(percentages):
            hi = percentages[last + 1].start()
        group_start, group_end = percentages[first].start(), percentages[last].end()
        # Carry a subject across a conjunction only when the next predicate is
        # explicitly shared. A nominal or unresolved prefix starts its own clause.
        prefix = low[lo:group_start]
        original_prefix = tenk_text[lo:group_start]
        # Qualifiers can overlap: "our largest" must not hide the longer
        # "largest customer" ending immediately before a company name.
        subjects = []
        for offset in range(len(prefix)):
            for kind, pattern in (("customer", _CONC_SINGLE_CUSTOMER), ("program", _CONC_SINGLE_PROGRAM)):
                subject = pattern.match(original_prefix, offset)
                if subject:
                    subjects.append((subject.end(), kind))
        subject_ends = [end for end, kind in subjects]
        named_subjects = [name.span() for name in _CONC_ENTITY_NAME.finditer(original_prefix)
                          if any(end <= name.start()
                                 and not original_prefix[end:name.start()].strip(" ,")
                                 for end in subject_ends)]
        joins = []
        ambiguous_prefix = False
        for join in re.finditer(r"\b(?:and|but|while|whereas)\b", prefix):
            if any(start <= join.start() < end for start, end in named_subjects):
                continue
            remainder = prefix[join.end():]
            predicates = list(_CONC_SHARE_PREDICATE.finditer(remainder))
            predicate = predicates[-1] if predicates else None
            modifiers = remainder[:predicate.start()].strip() if predicate else None
            original_modifiers = (original_prefix[join.end():join.end() + predicate.start()].strip()
                                  if predicate else None)
            relation = _CONC_CUSTOMER_RELATION.match(modifiers) if modifiers else None
            antecedent = max((subject for subject in subjects if subject[0] <= join.start()),
                             key=lambda subject: subject[0], default=(0, None))[1]
            if (relation and antecedent == "customer"
                    and _CONC_SHARED_MODIFIERS.fullmatch(modifiers[relation.end():].strip())):
                continue
            if (modifiers is not None and _CONC_SHARED_MODIFIERS.fullmatch(modifiers)
                    and not (original_modifiers and original_modifiers[0].isupper())):
                continue
            if (modifiers and original_modifiers and antecedent is not None
                    and (re.match(r"(?:its|their)\b", modifiers)
                         or (not original_modifiers[0].isupper()
                             and not re.match(r"(?:a|an|the|our|another|these|those)\b", modifiers)))):
                ambiguous_prefix = True
            # This also handles percentage-led clauses. Numeric lists already
            # share a group_start, so their internal joins never land here.
            joins.append(join)
        if joins:
            lo += joins[-1].end()
        window = low[lo:hi]
        # Revenue must be the percentage's denominator or the subject of a share
        # assertion. A revenue mention elsewhere in the statement is insufficient.
        denominator = re.match(
            r"\s*(?:,\s*respectively\s*,)?\s*of\s*"
            r"(?:(?:the|our|its|total|consolidated|net|combined|overall|company|group|"
            r"all|annual|global|worldwide|\d{4})\s+)*",
            low[group_end:hi])
        revenue_after = (denominator is not None and re.match(
            r"(?:revenues?|(?:(?:net|product)\s+)?sales|(?:accounts\s+)?receivables?)\b",
            low[group_end + denominator.end():hi]) is not None)
        revenue_before = any(re.fullmatch(
            r"\s*(?:share\s*)?(?:(?:from|with|to)\s+[^,;.!?]+?\s+)?"
            r"(?:was|were|represented|accounted for|constituted|comprised|totaled)\s*"
            r"(?:(?:approximately|about|nearly|over|under|more than|less than)\s*)?",
            low[term.end():group_start]) for term in _CONC_REVENUE_TERM.finditer(low, lo, group_start))
        if not revenue_after and not revenue_before:
            continue
        # Bind a segment denominator to this percentage and clause, so an unrelated
        # segment word cannot suppress a genuine customer concentration percentage.
        # Keep the denominator inside its clause while retaining abbreviation/name dots.
        # An explicit aggregate denominator takes priority over a dotted-name interpretation.
        tail_start = percentages[last].end() - 1
        original_tail = tenk_text[tail_start:hi]
        protected = [span.span() for span in _CONC_NAME_DOTS.finditer(original_tail)]
        boundary = next((punct.start() for punct in _CONC_CLAUSE_END.finditer(original_tail)
                         if not any(start <= punct.start() < end for start, end in protected)),
                        len(original_tail))
        aggregate_end = _CONC_AGGREGATE_END.match(original_tail)
        if aggregate_end and (aggregate_end.group("aggregate") or not any(
                start <= aggregate_end.start("boundary") < stop for start, stop in protected)):
            boundary = min(boundary, aggregate_end.start("boundary"))
        tail_end = tail_start + boundary
        tail = low[tail_start:tail_end]
        if _CONC_SEGMENT_CTX.match(tail):
            continue
        # Capitalized possessive denominators identify segment revenue; an unrelated
        # customer sentence cannot reclassify the segment's percentage.
        orig_tail = tenk_text[tail_start:tail_end]
        if _CONC_SEGMENT_POSSESSIVE.match(orig_tail):
            continue
        # A plural customer-group phrase nearer than any single-customer phrase
        # identifies diversification. Keep unrelated single-customer evidence intact.
        _div_d = _nearest_dist(_CONC_DIVERSIFIED_CUSTOMERS, window, m.start() - lo)
        if _div_d is not None:
            _sc_d = _nearest_dist(_CONC_SINGLE_CUSTOMER, window, m.start() - lo)
            if _sc_d is None or _div_d <= _sc_d:
                continue
        ambiguous_clause = ambiguous_clause or ambiguous_prefix
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
    if ambiguous_clause:
        parts.append("ambiguous_concentration_clause: prior subject not inherited")
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
      latest_below_avg. This veto requires a positive normalization base.
      A1: the 0< lower bound rejects a degenerate NEGATIVE base so the veto can't fire trivially.
    - peak_contamination_flag (bool): 0<contamination_ratio<0.8 AND latest_below_avg AND
      latest_net_income<0. P-A — the V-shape value-trap catch (trough->peak->rollover) that
      fundamental_decline_flag MISSES because that flag is gated on rev_slope_sign<0. On a V-shape
      the whole-window slope is +1 (so fundamental_decline_flag stays False), but the normalization
      base is past-peak-contaminated and current net income is negative.
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

    # Use at most five annual revenue observations so old stubs and duplicate years
    # cannot dominate the recent trajectory.
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
    # Both trajectory flags require a positive contamination ratio. A negative or
    # zero base does not satisfy these positive-base comparisons.
    out["fundamental_decline_flag"] = bool(
        out["rev_slope_sign"] < 0
        and cr is not None and 0 < cr < 1.0
        and out["latest_below_avg"]
    )

    # Peak contamination is independent of revenue slope. Current losses can coexist
    # with a positive whole-window slope after a peak.
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
    """Detect a positive trailing average that masks current cash burn.

    A negative contamination ratio lies outside the positive-base cyclical vetoes;
    current cash losses still need their own eligibility check.

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

    This four-flag policy score ranges from zero to four. Historical predictive
    figures are not current validation: the shipped analysis ranks within years,
    does not implement logistic refitting, and requires a new occurrence-correct
    bootstrap run on the preserved private dataset.

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
