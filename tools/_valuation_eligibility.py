"""
_valuation_eligibility.py — the buy_eligible composite for valuation.py.

This module owns the single mechanical boolean the BUY trigger
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
    debt_evidence_uncertain: bool = False,
    lumpy_ocf_normalization_suspect: bool = False,
) -> tuple[bool, list[str]]:
    """Compose buy_eligible — the single mechanical boolean the BUY trigger ANDs.

    buy_eligible requires all blocking guards to clear and an assessable active basis.
    The judgment rubric also requires active MoS >= 30%, complete evidence, and no
    kill-flags or Tier-3-load-bearing evidence. NAV has additional model-fit conditions.

    Returns (buy_eligible, buy_ineligible_reasons).
    """
    # --- P1: compose buy_eligible, the single mechanical boolean the BUY trigger ANDs in ---
    _buy_ineligible_reasons: list[str] = []
    if debt_evidence_uncertain:
        _buy_ineligible_reasons.append("debt_evidence_uncertain")
    if extreme_mos_review_required:
        _buy_ineligible_reasons.append("extreme_mos_review_required")
    if large_cap_out_of_scope:
        _buy_ineligible_reasons.append("large_cap_out_of_scope")
    if fcf_sustainability_uncertain:
        _buy_ineligible_reasons.append("fcf_sustainability_uncertain")
    if financial_sic_forced_unsuitable:
        _buy_ineligible_reasons.append("financial_sic_forced_unsuitable")
    # Insurance evidence has its own reason even when the SIC is non-financial.
    if insurance_concepts_present:
        _buy_ineligible_reasons.append("insurance_concepts_present")
    # The extreme loss-to-revenue condition gates eligibility with its own reason.
    # The non-extreme condition remains a data-quality label.
    if der.get("low_revenue_loss_ratio_extreme"):
        _buy_ineligible_reasons.append("low_revenue_loss_ratio_extreme")
    if der.get("debt_truncation_suspected"):
        _buy_ineligible_reasons.append("debt_truncation_suspected")
    if der.get("debt_stale"):
        _buy_ineligible_reasons.append("debt_stale")
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
    # A trailing normalization that masks current cash burn requires review before BUY.
    if normalization_masks_current_loss:
        _buy_ineligible_reasons.append("normalization_masks_current_loss")
    if lumpy_ocf_normalization_suspect:
        _buy_ineligible_reasons.append("lumpy_ocf_normalization_suspect")
    # The active valuation basis must carry a numeric margin of safety. An absent
    # intrinsic band cannot be made eligible by an otherwise empty reason list.
    _active_mos_for_eligibility = mos if mos_basis == "fcf_cap" else nav_mos
    if _active_mos_for_eligibility is None:
        _buy_ineligible_reasons.append("not_assessable_no_intrinsic_band")
    _buy_eligible = len(_buy_ineligible_reasons) == 0
    return _buy_eligible, _buy_ineligible_reasons
