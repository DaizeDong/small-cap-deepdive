"""
_valuation_eligibility.py — the buy_eligible composite for valuation.py.

Extracted (pure mechanical move, ZERO behavior change) from compute_valuation()
in valuation.py. This module owns the single mechanical boolean the BUY trigger
ANDs in (buy_eligible) and its reason list — all the guard reads/reasons that
gate it.

Import direction: this module imports NOTHING from valuation.py (it takes every
input it needs as an argument), so there is no circular import. valuation.py
re-exports compose_buy_eligibility so it stays importable from the valuation path.
"""
from __future__ import annotations


def compose_buy_eligibility(
    der: dict,
    *,
    extreme_mos_review_required: bool,
    large_cap_out_of_scope: bool,
    fcf_sustainability_uncertain: bool,
    financial_sic_forced_unsuitable: bool,
    insurance_concepts_present: bool,
    concentration_flag,
    fundamental_decline_flag: bool,
    peak_contamination_flag: bool,
    cross_source_mismatch: bool,
    normalization_masks_current_loss: bool,
    mos,
    nav_mos,
    mos_basis: str,
) -> tuple[bool, list[str]]:
    """Compose buy_eligible — the single mechanical boolean the BUY trigger ANDs.

    buy_eligible is True ONLY when every blocking guard is clear. The rubric/SKILL BUY
    trigger additionally requires mos_basis=="fcf_cap" AND MoS>=30 AND zero Tier-3-load-
    bearing; buy_eligible is the deterministic guard-composite half of that contract.

    Returns (buy_eligible, buy_ineligible_reasons).
    """
    # --- P1: compose buy_eligible, the single mechanical boolean the BUY trigger ANDs in ---
    _buy_ineligible_reasons: list[str] = []
    if extreme_mos_review_required:
        _buy_ineligible_reasons.append("extreme_mos_review_required")
    if large_cap_out_of_scope:
        _buy_ineligible_reasons.append("large_cap_out_of_scope")
    if fcf_sustainability_uncertain:
        _buy_ineligible_reasons.append("fcf_sustainability_uncertain")
    if financial_sic_forced_unsuitable:
        _buy_ineligible_reasons.append("financial_sic_forced_unsuitable")
    # A3: insurance_concepts_present gates buy_eligible (distinct from financial_sic_forced_
    # unsuitable so the reason-string is accurate even on a non-financial SIC, e.g. BOC SIC-65).
    if insurance_concepts_present:
        _buy_ineligible_reasons.append("insurance_concepts_present")
    # A4: low_revenue_loss_ratio_extreme (|NI|/rev>20x, STSS/MVIS/TIPT tail) gates buy_eligible
    # with the accurate label, replacing the old wrong_entity_suspected co-fire on that tail. The
    # non-extreme low_revenue_loss_ratio (>2x) stays a data_quality label ONLY (does NOT gate).
    if der.get("low_revenue_loss_ratio_extreme"):
        _buy_ineligible_reasons.append("low_revenue_loss_ratio_extreme")
    if der.get("debt_truncation_suspected"):
        _buy_ineligible_reasons.append("debt_truncation_suspected")
    if der.get("wrong_entity_suspected"):
        _buy_ineligible_reasons.append("wrong_entity_suspected")
    if concentration_flag == "kill":
        _buy_ineligible_reasons.append("concentration_kill")
    if fundamental_decline_flag:
        _buy_ineligible_reasons.append("fundamental_decline_flag")
    # P-A: peak_contamination_flag downgrades BUY->WATCH like fundamental_decline_flag.
    if peak_contamination_flag:
        _buy_ineligible_reasons.append("peak_contamination_flag")
    # P7: cross_source_mismatch (a >2.5x SEC-vs-yfinance disagreement on debt/revenue/shares)
    # gates buy_eligible, a corrupted single-source number cannot back a tradeable MoS. This is
    # a DATA-INTEGRITY gate, not a between-filings signal; gating here is intended.
    if cross_source_mismatch:
        _buy_ineligible_reasons.append("cross_source_mismatch")
    # v0.3.1 #1: normalization_masks_current_loss gates buy_eligible (downgrade BUY->WATCH). The
    # trailing-avg normalized FCF is masking current cash burn / a divested-segment stub; the
    # mechanical guards (cyclical vetoes) are silenced by the degenerate base, so this is the only
    # path that catches the TUSK-shape phantom BUY.
    if normalization_masks_current_loss:
        _buy_ineligible_reasons.append("normalization_masks_current_loss")
    # v0.3.1 #9: a null MoS can NEVER be a tradeable BUY. When the active basis carries no numeric
    # MoS (fcf_cap with no intrinsic band, or nav/abstain with no NAV MoS), buy_eligible MUST be
    # False with an explicit reason, not left True-by-absence-of-data (the DAVA/TV/QNC footgun
    # where buy_eligible=True co-existed with MoS=null, caught only by the downstream MoS>=30 clause).
    _active_mos_for_eligibility = mos if mos_basis == "fcf_cap" else nav_mos
    if _active_mos_for_eligibility is None:
        _buy_ineligible_reasons.append("not_assessable_no_intrinsic_band")
    _buy_eligible = len(_buy_ineligible_reasons) == 0
    return _buy_eligible, _buy_ineligible_reasons
