"""Exercise the actual default SEC adapter through generated HTTP responses."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import _deepdive_concepts as concepts
import backtest
import backtest_returns as returns
from make_fixtures import market_cap_sec_scenarios


def synthetic_http(case, responses, calls):
    """Replace transport only; raw decoding and all SEC selection stay real."""
    def get(url, **kwargs):
        calls.append((url, kwargs))
        index = next(i for i, (taxonomy, tag) in enumerate(case['concepts'])
                     if url.endswith('/' + taxonomy + '/' + tag + '.json'))
        response = deepcopy(responses[index])
        exceptions = {'TimeoutError': TimeoutError, 'ConnectionError': ConnectionError,
                      'ValueError': ValueError}
        if 'exception' in response:
            raise exceptions[response['exception']]()

        def decode():
            if 'json_exception' in response:
                raise exceptions[response['json_exception']]()
            return deepcopy(response['body'])

        return SimpleNamespace(status_code=response['status'], json=decode)
    return get


class DefaultSecSharesContracts(unittest.TestCase):
    def setUp(self):
        self.case = market_cap_sec_scenarios()

    def evaluate(self, case_name=None, *, responses=None, price_fn=None):
        calls = []
        if responses is None:
            responses = self.case['cases'][case_name]
        transport = synthetic_http(self.case, responses, calls)
        with patch.object(concepts, 'http_get', transport):
            result = returns.mktcap_asof(
                self.case['ticker'], self.case['asof'], self.case['cik'],
                price_fn=price_fn or (lambda *_: deepcopy(self.case['quote'])))
        return result, calls

    def assert_unusable(self, result):
        self.assertIs(result.get('usable'), False)
        self.assertIsNone(result['mktcap'])
        self.assertTrue(result.get('reason'))

    def test_real_default_boundary_requires_share_units_and_retains_provenance(self):
        result, calls = self.evaluate('valid')
        self.assertIs(result.get('usable'), True)
        self.assertEqual(result['mktcap'], self.case['expected_cap'])
        self.assertEqual(result.get('shares_status'), 'ok')
        lookup = result.get('shares_lookup', {})
        self.assertEqual(lookup.get('evidence', {}).get('unit'), 'shares')
        self.assertEqual(lookup.get('evidence', {}).get('shares'), self.case['expected_shares'])
        self.assertEqual(len(lookup.get('queries', [])), 2)
        self.assertEqual(len(calls), 2)

    def test_equal_date_conflicts_never_depend_on_response_order(self):
        for name in ('conflict_forward', 'conflict_reverse', 'cross_concept_conflict'):
            with self.subTest(case=name):
                result, _ = self.evaluate(name)
                self.assert_unusable(result)
                self.assertEqual(result.get('shares_status'), 'invalid')
                self.assertIn('conflict', result.get('reason', '').lower())

    def test_identical_duplicates_and_later_revisions_remain_usable(self):
        for name, cap in (('identical', self.case['expected_cap']),
                          ('revised_forward', self.case['revised_cap']),
                          ('revised_reverse', self.case['revised_cap'])):
            with self.subTest(case=name):
                result, _ = self.evaluate(name)
                self.assertIs(result.get('usable'), True)
                self.assertEqual(result['mktcap'], cap)

    def test_usd_mixed_and_unsupported_units_cannot_become_shares(self):
        for name in ('usd_only', 'mixed_units', 'unsupported_unit'):
            with self.subTest(case=name):
                result, _ = self.evaluate(name)
                self.assert_unusable(result)
                self.assertEqual(result.get('shares_status'), 'invalid')

    def test_http_and_transport_failures_remain_provider_errors(self):
        for name in ('http_429', 'http_503', 'TimeoutError', 'ConnectionError'):
            with self.subTest(case=name):
                result, _ = self.evaluate(name)
                self.assert_unusable(result)
                self.assertEqual(result.get('shares_status'), 'provider_error')
                queries = result.get('shares_lookup', {}).get('queries', [])
                self.assertTrue(any(query.get('status') == 'provider_error' for query in queries))

    def test_successful_absence_is_distinct_from_malformed_responses(self):
        for name in ('empty', 'missing_concepts', 'future_only'):
            with self.subTest(case=name):
                result, _ = self.evaluate(name)
                self.assert_unusable(result)
                self.assertEqual(result.get('shares_status'), 'unavailable')
                self.assertTrue(result.get('shares_lookup', {}).get('queries'))
        for name in ('invalid_json', 'invalid_response', 'wrong_issuer'):
            with self.subTest(case=name):
                result, _ = self.evaluate(name)
                self.assert_unusable(result)
                self.assertEqual(result.get('shares_status'), 'invalid')

    def test_partial_query_failure_uses_an_explicit_conservative_policy(self):
        result, _ = self.evaluate('partial_http')
        self.assert_unusable(result)
        self.assertEqual(result.get('shares_status'), 'provider_error')
        lookup = result.get('shares_lookup', {})
        self.assertEqual(lookup.get('continuation_policy'), self.case['continuation_policy'])
        self.assertEqual({query.get('status') for query in lookup.get('queries', [])},
                         {'provider_error', 'ok'})

    def test_invalid_instantaneous_facts_are_explicitly_rejected(self):
        for index, responses in enumerate(self.case['invalid_facts']):
            with self.subTest(case=index):
                result, _ = self.evaluate(responses=responses)
                self.assert_unusable(result)
                self.assertEqual(result.get('shares_status'), 'invalid')

    def test_future_observations_and_disclosures_cannot_replace_available_facts(self):
        result, _ = self.evaluate('future_filtered')
        self.assertIs(result.get('usable'), True)
        self.assertEqual(result['mktcap'], self.case['expected_cap'])
        self.assertLessEqual(result['shares_filed'], self.case['asof'])

    def test_invalid_or_incomplete_sec_evidence_cannot_reach_buy(self):
        for name in ('conflict_forward', 'usd_only', 'partial_http'):
            with self.subTest(case=name):
                valuations = []
                proposed = {'bucket': backtest.BUCKETS[0], 'mos_basis': 'owner_earnings',
                            'mos_pct': 60, 'buy_eligible': True, 'killflag_count': 0,
                            'buy_ineligible_reasons': []}
                calls = []
                transport = synthetic_http(self.case, self.case['cases'][name], calls)

                def value(deep, cap, cfg):
                    valuations.append(cap)
                    return {}

                def cap(*args, **kwargs):
                    return returns.mktcap_asof(*args, **kwargs,
                                              price_fn=lambda *_: deepcopy(self.case['quote']))

                with patch.object(concepts, 'http_get', transport), \
                        patch.object(backtest, '_val_cfg', return_value={}), \
                        patch.object(backtest, 'bucket_name', return_value=deepcopy(proposed)):
                    row = backtest._process_name(
                        self.case['entity'], self.case['asof'], 12,
                        lambda *_, **__: {}, value, cap,
                        lambda *_: {'status': 'no_exit_price', 'total_return': None})
                saved = json.loads(json.dumps(row, allow_nan=False))
                self.assertEqual(valuations, [0])
                self.assertFalse(saved['buy_eligible'])
                self.assertEqual(saved['bucket'], backtest.BUCKET_ABSTAIN)
                self.assertTrue(saved.get('market_cap_evidence', {}).get('shares_lookup', {}).get('queries'))

    def test_sec_diagnostics_survive_a_separate_price_failure(self):
        def failed_price(*_):
            raise ConnectionError()

        result, _ = self.evaluate('valid', price_fn=failed_price)
        self.assert_unusable(result)
        self.assertEqual(result.get('price_status'), 'provider_error')
        self.assertEqual(result.get('shares_status'), 'ok')
        self.assertTrue(result.get('shares_lookup', {}).get('queries'))


if __name__ == '__main__':
    unittest.main()
