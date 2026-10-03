"""Holding-period quote retrieval, uncertainty and aggregate coverage contracts."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import backtest_returns as returns
import backtest
from make_fixtures import backtest_quote_scenarios


class History:
    def __init__(self, rows):
        self.rows = rows
        self.empty = not rows
        self.columns = ['Close']

    def iterrows(self):
        for day, price in self.rows:
            yield day, {'Close': price}


class BacktestQuoteContracts(unittest.TestCase):
    def setUp(self):
        self.case = backtest_quote_scenarios()

    def default_result(self, exits):
        calls = []

        def history(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return History([[self.case['entry'][1], self.case['entry'][0]]])
            if isinstance(exits, Exception):
                raise exits
            return History(exits)

        provider = SimpleNamespace(Ticker=lambda symbol: SimpleNamespace(history=history))
        with patch.dict('sys.modules', {'yfinance': provider}):
            result = returns.forward_return_with_reason(self.case['ticker'], self.case['asof'])
        return result, calls

    def injected_result(self, exit_quote, entry=None):
        first = self.case['entry'] if entry is None else entry

        def lookup(ticker, on_date):
            quote = first if on_date == self.case['asof'] else exit_quote
            if isinstance(quote, Exception):
                raise quote
            return quote

        return returns.forward_return_with_reason(
            self.case['ticker'], self.case['asof'], price_fn=lookup)

    def test_default_exit_search_covers_entire_holding_period(self):
        result, calls = self.default_result(self.case['stale_rows'])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['total_return'], -0.992)
        self.assertEqual(calls[1]['start'], self.case['entry'][1])
        self.assertEqual(calls[1]['end'], '2021-07-01')
        self.assertIs(calls[1]['raise_errors'], True)

    def test_default_selects_latest_valid_date_and_reports_rejected_rows(self):
        result, _ = self.default_result(self.case['selection_rows'])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['exit_date'], '2021-06-29')
        self.assertEqual(result['total_return'], 0.2)
        diagnostic = result['price_diagnostics']['exit']
        self.assertEqual(diagnostic['invalid_rows'], 2)
        self.assertEqual(diagnostic['out_of_window_rows'], 2)

    def test_default_and_injected_reject_invalid_prices(self):
        for value in self.case['invalid_prices']:
            with self.subTest(value=repr(value)):
                result, _ = self.default_result([[self.case['target'], value]])
                self.assertNotEqual(result['status'], 'ok')
                self.assertIsNone(result['total_return'])
                for entry_bad in (False, True):
                    quote = [value, self.case['asof'] if entry_bad else self.case['target']]
                    result = self.injected_result(
                        [12, self.case['target']] if entry_bad else quote,
                        entry=quote if entry_bad else None)
                    self.assertNotEqual(result['status'], 'ok')
                    self.assertIsNone(result['total_return'])

    def test_injected_rejects_invalid_shapes_and_outside_dates(self):
        quotes = self.case['invalid_quotes'] + [
            [12, day] for day in self.case['outside_exit_dates']]
        for quote in quotes:
            with self.subTest(quote=quote):
                result = self.injected_result(quote)
                self.assertEqual(result['status'], 'invalid_exit_price')
                self.assertIsNone(result['total_return'])

    def test_provider_failure_and_successful_empty_are_distinguishable(self):
        failed, _ = self.default_result(RuntimeError('synthetic provider failure'))
        empty, _ = self.default_result([])
        self.assertEqual(failed['status'], 'provider_error')
        self.assertEqual(failed['error_stage'], 'exit')
        self.assertEqual(empty['status'], 'no_exit_price')
        failed = self.injected_result(RuntimeError('synthetic provider failure'))
        self.assertEqual(failed['status'], 'provider_error')
        self.assertEqual(self.injected_result(None)['status'], 'no_exit_price')
        entry_error = self.injected_result([12, self.case['target']],
                                          entry=RuntimeError('synthetic provider failure'))
        self.assertEqual(entry_error['status'], 'provider_error')
        self.assertEqual(entry_error['error_stage'], 'entry')

    def test_stale_proxy_does_not_claim_a_terminal_event(self):
        result = self.injected_result([0.08, '2020-10-01'])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['total_return'], -0.992)
        self.assertTrue(result['realized_to_last_close'])
        self.assertEqual(result['return_kind'], 'stale_quote_proxy')
        self.assertEqual(result['terminal_status'], 'unknown')
        self.assertEqual(result['exit_quote_age_days'], 272)
        self.assertNotIn('name delisted', result['reason'])

    def test_quote_boundaries_and_fresh_observations(self):
        for day in [self.case['entry'][1], self.case['target']]:
            with self.subTest(day=day):
                result, _ = self.default_result([[day, 12]])
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['exit_date'], day)
        result, _ = self.default_result([[self.case['target'], 12]])
        self.assertEqual(result['return_kind'], 'observed_close')
        self.assertEqual(result['exit_quote_age_days'], 0)

    def test_coverage_conserves_population_and_exposes_proxy_contribution(self):
        rows = self.case['coverage_rows']
        stats = backtest.per_bucket_stats(rows, 0.1)['AVOID']
        coverage = stats['coverage']
        self.assertEqual(coverage, {'total': 6, 'fresh': 1, 'stale_proxy': 1,
                                   'missing': 1, 'provider_error': 1,
                                   'invalid': 2, 'pipeline_error': 0})
        self.assertEqual(stats['n'], 2)
        self.assertEqual(stats['unpriceable_count'], 4)
        self.assertEqual(stats['estimate_basis'], 'observed_and_last_quote_proxies')
        self.assertAlmostEqual(stats['mean_return'], -0.746)
        self.assertEqual(stats['cohorts']['stale_proxy']['mean_return'], -0.992)
        risks = backtest.blowup_avoidance(rows)
        self.assertEqual(risks['coverage'], coverage)
        self.assertEqual(risks['n_blowups'], 2)
        self.assertEqual(risks['cohorts']['stale_proxy']['n_blowups'], 1)
        self.assertEqual(risks['cohorts']['fresh']['n_blowups'], 1)

    def test_entry_dates_and_conflicting_provider_rows_are_invalid(self):
        for day in self.case['outside_entry_dates']:
            with self.subTest(day=day):
                result = self.injected_result([12, self.case['target']], entry=[10, day])
                self.assertEqual(result['status'], 'invalid_entry_price')
        result, _ = self.default_result(self.case['conflicting_rows'])
        self.assertEqual(result['status'], 'invalid_exit_price')
        self.assertIsNone(result['total_return'])

    def test_finite_large_returns_do_not_overflow_summary_math(self):
        self.assertEqual(backtest._mean(self.case['large_returns']), 1e308)
        self.assertEqual(backtest._median(self.case['large_returns']), 1e308)

    def test_cell_output_retains_proxy_dates_and_population(self):
        forward = self.injected_result([0.08, '2020-10-01'])
        with patch.object(backtest, '_val_cfg', return_value={}), \
                patch.object(backtest, 'bucket_name', return_value=self.case['bucket']):
            result = backtest.run_cell(
                'synthetic', self.case['asof'],
                universe_fn=lambda *_: [self.case['entity']],
                pull_fn=lambda *_, **__: self.case['deep'],
                valuation_fn=lambda *_: {}, mktcap_fn=lambda *_, **__: {'mktcap': None},
                forward_fn=lambda *_: forward,
                benchmark_fn=lambda *_: {'status': 'ok', 'benchmark': 'SYNTH_BENCH',
                                          'total_return': 0.1}, write=False)
        self.assertEqual(result['return_coverage']['stale_proxy'], 1)
        self.assertEqual(result['return_coverage']['total'], 1)
        row = result['names'][0]
        self.assertEqual(row['return_kind'], 'stale_quote_proxy')
        self.assertEqual(row['exit_quote_age_days'], 272)
        self.assertEqual(row['forward_return']['exit_date'], '2020-10-01')
        self.assertEqual(result['per_bucket_stats']['abstain']['cohorts']['stale_proxy']['n'], 1)


if __name__ == '__main__':
    unittest.main()
