"""Generate synthetic financial evidence cases for the public fixture entrypoint."""
from copy import deepcopy


def financial_scenarios():
    """Return independent cases; no company, policy or runtime data is imported."""
    million = 1_000_000
    ends = [f'{year}-12-31' for year in range(2020, 2025)]

    def series(values):
        return [{'end': end, 'val': value * million} for end, value in zip(ends, values)]

    financials = {
        'ebit': series([11, 28, 10, 29, 10]),
        'dep_amort': series([2] * len(ends)),
        'ocf': series([30] * len(ends)),
        'capex': series([10] * len(ends)),
        'revenue': series([100] * len(ends)),
        'assets': series([500] * len(ends)),
        'equity': series([250] * len(ends)),
        'shares_outstanding': series([10] * len(ends)),
    }
    complete = {
        'ticker': 'SYNF',
        'financials': financials,
        'derived': {
            'latest_cash': 10 * million, 'latest_total_debt': 30 * million,
            'latest_revenue': 100 * million, 'latest_net_income': 15 * million,
            'latest_ocf': 30 * million, 'latest_ebit': 10 * million,
            'latest_dep_amort': 2 * million, 'latest_ebitda': 12 * million,
            'latest_capex': 10 * million, 'latest_fcf': 20 * million,
            'fcf_is_ocf_proxy': False, 'sic': '3500',
        },
    }
    historical_missing = deepcopy(complete)
    historical_missing['financials']['capex'] = financials['capex'][-1:]
    null_capex = deepcopy(complete)
    null_capex['financials']['capex'][1]['val'] = None
    outside_window = deepcopy(complete)
    outside_window['financials']['ocf'].insert(0, {'end': '2019-12-31', 'val': 30 * million})
    latest_missing = deepcopy(complete)
    latest_missing['financials']['ebit'] = series([10] * len(ends))
    latest_missing['financials']['capex'] = []
    latest_missing['derived']['latest_capex'] = None
    latest_missing['derived']['latest_fcf'] = latest_missing['derived']['latest_ocf']
    all_missing = deepcopy(complete)
    all_missing['financials']['capex'] = []

    clean = {'rating': '买入', 'adjudication': 'data_verified_clean'}
    failed = {'rating': '买入', 'adjudication': 'data_false_positive'}
    pending = {'rating': '买入', 'adjudication': None}
    unknown = {'rating': '买入', 'adjudication': 'review_failed'}
    config = {'wacc': 0.10, 'equity_discount_rate': 0.11, 'cap_rate_low': 0.09,
              'cap_rate_high': 0.12, 'normalize_years': 5, 'cyclical_cv_threshold': 0.25}
    return {
        'config': config, 'market_cap': 130 * million, 'buy_market_cap': 115 * million,
        'complete': complete, 'historical_missing': historical_missing,
        'null_capex': null_capex, 'outside_window': outside_window,
        'latest_missing': latest_missing, 'all_missing': all_missing,
        'expected_fcf': 20 * million,
        'calibration_cases': [
            {'rows': [], 'expected': {'rate': None, 'total_buys': 0, 'reviewed_buys': 0,
                                     'clean_buys': 0, 'false_positive_buys': 0, 'pending_buys': 0,
                                     'review_coverage': None}},
            {'rows': [pending], 'expected': {'rate': None, 'total_buys': 1, 'reviewed_buys': 0,
                                           'clean_buys': 0, 'false_positive_buys': 0, 'pending_buys': 1,
                                           'review_coverage': 0.0}},
            {'rows': [clean, failed, pending, unknown, {'rating': '观察'}],
             'expected': {'rate': 0.5, 'total_buys': 4, 'reviewed_buys': 2, 'clean_buys': 1,
                          'false_positive_buys': 1, 'pending_buys': 2, 'review_coverage': 0.5}},
            {'rows': [failed], 'expected': {'rate': 0.0, 'total_buys': 1, 'reviewed_buys': 1,
                                          'clean_buys': 0, 'false_positive_buys': 1, 'pending_buys': 0,
                                          'review_coverage': 1.0}},
        ],
        'sensitivity': {'debt': [0, 80 * million], 'cash': [0, 40 * million],
                        'ocf_reduction': 3 * million, 'higher_cap_rate': 0.15},
        'cli': {'input_name': 'synthetic-input.json', 'tool_name': 'synthetic-tool',
                'public_name': 'synthetic-public', 'public_origin': 'https://github.com/example/synthetic-public',
                'public_identity': 'example/synthetic-public', 'other_ticker': 'SYNX',
                'invalid_ticker': '../SYNF', 'date': '2025-02-03',
                'invalid_documents': [[], {'ticker': 123}],
                'prior_output': 'synthetic existing valuation\n', 'market_source': 'synthetic-override'},
    }
