"""Market-cap evidence must share a split basis and remain visible downstream."""
from copy import deepcopy
from datetime import datetime
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import backtest
import backtest_returns as returns
import _deepdive_concepts as sec
from make_fixtures import market_cap_basis_scenarios, market_cap_sec_scenarios
from test_market_cap_sec_source import synthetic_http


class History:
    def __init__(self, rows):
        self.rows = rows
        self.empty = not rows
        self.columns = ['Close', 'Adj Close', 'Stock Splits', 'Dividends']

    def iterrows(self):
        return iter(self.rows)


class MarketCapBasisContracts(unittest.TestCase):
    def setUp(self):
        self.case = market_cap_basis_scenarios()

    def result(self, quote=None, shares=None):
        return returns.mktcap_asof(
            self.case['ticker'], self.case['asof'], self.case['cik'],
            price_fn=lambda *_: deepcopy(self.case['quote'] if quote is None else quote),
            shares_fn=lambda *_: deepcopy(self.case['shares'] if shares is None else shares))

    def assert_unusable(self, result):
        self.assertIs(result.get('usable'), False)
        self.assertNotEqual(result.get('basis_status'), 'compatible')
        self.assertIsNone(result['mktcap'])
        self.assertTrue(result.get('reason'))

    def test_split_normalization_preserves_cap_across_directions_and_chains(self):
        for case in self.case['chains']:
            with self.subTest(case=case['id']):
                result = self.result(case['quote'], case['shares'])
                self.assertIs(result.get('usable'), True)
                self.assertEqual(result.get('basis_status'), 'compatible')
                self.assertAlmostEqual(result['mktcap'], case['expected'], places=5)
                self.assertEqual(result.get('shares_date'), case['shares']['date'])
                self.assertEqual(result.get('shares_filed'), case['shares']['filed'])
                self.assertEqual(result.get('normalization_basis_date'), case['quote']['basis_date'])

    def test_dividend_adjusted_and_undeclared_quotes_cannot_supply_market_cap(self):
        for basis in ('total_return_adjusted', 'dividend_adjusted', 'unknown', None):
            with self.subTest(basis=basis):
                quote = deepcopy(self.case['quote'])
                quote['basis'] = basis
                self.assert_unusable(self.result(quote))
        quote = deepcopy(self.case['quote'])
        quote['actions']['dividends'] = [{'date': '2021-06-30', 'amount': 99}]
        self.assertAlmostEqual(self.result(quote)['mktcap'], 100000000.0)

    def test_missing_incomplete_conflicting_or_invalid_actions_fail_closed(self):
        mutations = [
            lambda a: a.update(complete=False),
            lambda a: a.update(start='2020-04-01'),
            lambda a: a.update(end='2021-06-30'),
            lambda a: a['splits'].append({'date': '2021-06-30', 'ratio': 2}),
            lambda a: a['splits'].append({'date': '2023-01-01', 'ratio': 2}),
            lambda a: a['splits'].append({'date': 'invalid', 'ratio': 2}),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                quote = deepcopy(self.case['quote'])
                change(quote['actions'])
                self.assert_unusable(self.result(quote))
        quote = deepcopy(self.case['quote'])
        quote.pop('actions')
        self.assert_unusable(self.result(quote))
        for number in self.case['invalid_numbers']:
            quote = deepcopy(self.case['quote'])
            quote['actions']['splits'][0]['ratio'] = number
            with self.subTest(ratio=repr(number)):
                self.assert_unusable(self.result(quote))

    def test_numeric_and_date_validation_precedes_qualification(self):
        for value in self.case['invalid_numbers']:
            for field in ('price', 'shares'):
                with self.subTest(field=field, value=repr(value)):
                    quote, shares = deepcopy(self.case['quote']), deepcopy(self.case['shares'])
                    (quote if field == 'price' else shares)[field] = value
                    self.assert_unusable(self.result(quote, shares))
        for field, value in (('date', '2021-01-01'), ('filed', '2021-01-01'),
                             ('date', '2020-02-30'), ('filed', '2019-01-01')):
            shares = deepcopy(self.case['shares'])
            shares[field] = value
            with self.subTest(field=field, value=value):
                self.assert_unusable(self.result(shares=shares))

    def test_ambiguous_filing_and_same_day_split_basis_is_unresolved(self):
        quote, shares = deepcopy(self.case['quote']), deepcopy(self.case['shares'])
        shares.update(basis='as_reported', basis_timing=None)
        quote['actions']['splits'].append({'date': '2020-04-15', 'ratio': 2})
        self.assert_unusable(self.result(quote, shares))
        shares = deepcopy(self.case['shares'])
        shares.pop('basis_timing')
        quote = deepcopy(self.case['quote'])
        quote['actions']['splits'].append({'date': shares['date'], 'ratio': 2})
        self.assert_unusable(self.result(quote, shares))

    def test_same_explicit_basis_needs_no_inferred_split_factor(self):
        quote, shares = deepcopy(self.case['quote']), deepcopy(self.case['shares'])
        quote.update(price=100, basis='as_traded', basis_date=self.case['asof'])
        quote.pop('actions')
        shares.update(date=self.case['asof'], filed=self.case['asof'], basis_date=self.case['asof'])
        result = self.result(quote, shares)
        self.assertIs(result.get('usable'), True)
        self.assertEqual(result['mktcap'], 100000000)

    def test_legacy_arithmetic_is_preserved_and_marked_unverified(self):
        result = returns.mktcap_asof(
            self.case['ticker'], self.case['asof'], self.case['cik'],
            price_fn=lambda *_: (100, self.case['asof']), shares_fn=lambda *_: 1000000)
        self.assertEqual(result['mktcap'], 100000000)
        self.assertEqual(result['source'], 'sec_shares_x_price')
        self.assertIs(result.get('usable'), False)
        self.assertEqual(result.get('basis_status'), 'legacy_unverified')

    def test_default_provider_uses_split_only_prices_and_dated_instant_shares(self):
        calls, requests = [], []

        def history(**kwargs):
            calls.append(kwargs)
            return History(self.case['history'])

        provider = SimpleNamespace(Ticker=lambda _: SimpleNamespace(history=history))
        inputs = market_cap_sec_scenarios()
        transport = synthetic_http(inputs, inputs['basis_responses'], requests)
        with patch.dict('sys.modules', {'yfinance': provider}), \
                patch.object(sec, 'http_get', transport), \
                patch.object(sec, 'instant_share_evidence', wraps=sec.instant_share_evidence) as lookup:
            result = returns.mktcap_asof(self.case['ticker'], self.case['asof'], self.case['cik'])
        lookup.assert_called_once_with(self.case['cik'], self.case['asof'])
        self.assertIs(result.get('usable'), True)
        self.assertEqual(result['mktcap'], 100000000)
        self.assertEqual(result.get('reported_shares'), 1000000)
        self.assertIs(calls[0]['auto_adjust'], False)
        self.assertIs(calls[0]['back_adjust'], False)
        self.assertIs(calls[0]['actions'], True)
        self.assertIs(calls[0]['raise_errors'], True)
        self.assertLessEqual(calls[0]['start'], self.case['shares']['date'])
        self.assertGreater(calls[0]['end'], '2022-06-30')
        self.assertTrue(requests)
        self.assertFalse(any('WeightedAverage' in url for url, _ in requests))

    def test_default_missing_action_column_is_not_an_empty_split_history(self):
        frame = History(self.case['history'])
        frame.columns.remove('Stock Splits')
        provider = SimpleNamespace(Ticker=lambda _: SimpleNamespace(history=lambda **_: frame))
        inputs = market_cap_sec_scenarios()
        transport = synthetic_http(inputs, inputs['basis_responses'], [])
        with patch.dict('sys.modules', {'yfinance': provider}), patch.object(sec, 'http_get', transport):
            result = returns.mktcap_asof(self.case['ticker'], self.case['asof'], self.case['cik'])
        self.assert_unusable(result)

    def test_default_does_not_guess_that_an_observation_day_split_has_finished(self):
        observation = self.case['quote']['basis_date']

        class ObservationDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromisoformat(observation).replace(tzinfo=tz)

        history = deepcopy(self.case['history'])
        history[1][1]['Stock Splits'] = 0.0
        history[2][1]['Stock Splits'] = 4.0
        provider = SimpleNamespace(Ticker=lambda _: SimpleNamespace(history=lambda **_: History(history)))
        inputs = market_cap_sec_scenarios()
        transport = synthetic_http(inputs, inputs['basis_responses'], [])
        with patch.dict('sys.modules', {'yfinance': provider}), patch.object(sec, 'http_get', transport), \
                patch.object(returns, 'datetime', ObservationDateTime):
            result = returns.mktcap_asof(self.case['ticker'], self.case['asof'], self.case['cik'])
        self.assert_unusable(result)
        self.assertIn('same-day', result['reason'])

    def test_unverified_basis_and_reason_survive_the_full_name_pipeline(self):
        evidence = self.result({**self.case['quote'], 'basis': 'total_return_adjusted'})
        valuation_caps = []

        def value(deep, cap, cfg):
            valuation_caps.append(cap)
            return {}

        proposed = {'bucket': backtest.BUCKETS[0], 'mos_basis': 'owner_earnings', 'mos_pct': 60,
                    'buy_eligible': True, 'killflag_count': 0, 'buy_ineligible_reasons': []}
        with patch.object(backtest, '_val_cfg', return_value={}), \
                patch.object(backtest, 'bucket_name', return_value=proposed):
            row = backtest._process_name(
                self.case['entity'], self.case['asof'], 12,
                lambda *_, **__: {}, value, lambda *_, **__: evidence,
                lambda *_: {'status': 'no_exit_price', 'total_return': None})
        self.assertEqual(valuation_caps, [0])
        self.assertIs(row.get('mktcap_usable'), False)
        self.assertEqual(row.get('market_cap_evidence'), evidence)
        self.assertEqual(row.get('mktcap_reason'), evidence['reason'])
        self.assertFalse(row['buy_eligible'])
        self.assertEqual(row['bucket'], backtest.BUCKET_ABSTAIN)


if __name__ == '__main__':
    unittest.main()
