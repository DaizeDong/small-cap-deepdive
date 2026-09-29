"""Unknown or conflicting debt must survive the producer-to-valuation boundary."""
import pytest

from test_private_runs import state
from test_financial_evidence import valuation_module
from make_fixtures import debt_valuation_scenarios

FIX = debt_valuation_scenarios()


@pytest.mark.parametrize('case', ['missing', 'unavailable', 'conflicting', 'flagged', 'proxy'])
def test_uncertain_debt_cannot_create_ev_or_buy_eligibility(valuation_module, case):
    result = valuation_module.compute_valuation(FIX['cases'][case], FIX['market_cap'], FIX['config'])
    assert result['ev'] is None
    assert result['ev_sales'] is None and result['ev_ebitda'] is None
    assert result['ev_note'] == 'debt_evidence_uncertain'
    assert result['debt_evidence_uncertain']
    assert not result['buy_eligible']
    assert 'debt_evidence_uncertain' in result['buy_ineligible_reasons']
    assert any('debt_evidence_uncertain' in flag for flag in result['data_quality'])
    assert result['debt_evidence_detail'] == FIX['cases'][case]['derived']['debt_evidence_detail']


@pytest.mark.parametrize('case', ['zero', 'reported'])
def test_reported_debt_retains_ev_and_eligibility(valuation_module, case):
    data = FIX['cases'][case]
    result = valuation_module.compute_valuation(data, FIX['market_cap'], FIX['config'])
    assert result['ev'] == round(FIX['market_cap'] + data['derived']['latest_total_debt'] - data['derived']['latest_cash'])
    assert result['buy_eligible']
    assert not result.get('debt_evidence_uncertain', False)
