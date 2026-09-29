"""Generated financial controls cover unknown evidence and valuation write proof."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from test_private_runs import state
from make_fixtures import financial_scenarios

FIX = financial_scenarios()


@pytest.fixture
def valuation_module(state, monkeypatch):
    for name in ('valuation', '_valuation_model', '_common'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('valuation')
    # Resolver discovery is outside this financial test scope; destination proof is real.
    monkeypatch.setattr(sys.modules['_common'], '_companion_root', lambda: Path(state['companion']))
    return module


def value(module, data, market_cap=None, config=None):
    return module.compute_valuation(deepcopy(data), market_cap or FIX['market_cap'],
                                    deepcopy(config or FIX['config']))


@pytest.mark.parametrize('case', ['historical_missing', 'null_capex', 'all_missing'])
def test_missing_capex_cannot_create_a_tradeable_normalized_value(valuation_module, case):
    result = value(valuation_module, FIX[case])
    assert result['cyclical']
    assert result['normalized_fcf'] is None
    assert result['intrinsic_value_band'] is None
    assert not result['buy_eligible']
    assert result['fcf_sustainability_uncertain']
    assert result['normalized_fcf_is_proxy']
    assert result['fcf_normalization']['incomplete_periods']
    assert any('capex' in flag for flag in result['data_quality'])


def test_matched_capex_control_retains_fcf_and_buy_eligibility(valuation_module):
    result = value(valuation_module, FIX['complete'], FIX['buy_market_cap'])
    assert result['normalized_fcf'] == FIX['expected_fcf']
    assert result['buy_eligible']
    assert result['margin_of_safety_pct'] >= 0.30
    assert not result['normalized_fcf_is_proxy']
    assert not result['fcf_normalization']['incomplete_periods']


def test_only_the_selected_window_controls_capex_completeness(valuation_module):
    result = value(valuation_module, FIX['outside_window'])
    assert result['normalized_fcf'] == FIX['expected_fcf']
    assert not result['normalized_fcf_is_proxy']
    assert len(result['fcf_normalization']['periods']) == FIX['config']['normalize_years']


def test_missing_latest_capex_is_unknown_even_without_upstream_proxy_flag(valuation_module):
    result = value(valuation_module, FIX['latest_missing'])
    assert not result['cyclical']
    assert not result['buy_eligible']
    assert result['fcf_sustainability_uncertain']


@pytest.mark.parametrize('case', FIX['calibration_cases'])
def test_integrity_counts_only_explicitly_adjudicated_buys(case):
    calibration = importlib.import_module('_calibration')
    assert calibration._buy_data_integrity_rate(case['rows']) == case['expected']['rate']
    assert calibration._buy_data_integrity_summary(case['rows']) == case['expected']


def test_capitalization_and_reverse_dcf_share_equity_basis(valuation_module):
    result = value(valuation_module, FIX['complete'])
    expected_low = round(FIX['expected_fcf'] / FIX['config']['cap_rate_high'])
    expected_high = round(FIX['expected_fcf'] / FIX['config']['cap_rate_low'])
    assert result['intrinsic_value_band']['equity_low'] == expected_low
    assert result['intrinsic_value_band']['equity_high'] == expected_high
    assert result['intrinsic_value_band']['basis'] == 'post_interest_equity_cash_flow'
    assert result['assumptions']['discount_rate_basis'] == 'equity_required_return'
    assert result['reverse_dcf_implied_growth'] == round(
        FIX['config']['equity_discount_rate'] - FIX['expected_fcf'] / FIX['market_cap'], 4)


@pytest.mark.parametrize('field', ['debt', 'cash'])
def test_balance_sheet_does_not_double_adjust_post_interest_cash_flow(valuation_module, field):
    result = []
    for amount in FIX['sensitivity'][field]:
        data = deepcopy(FIX['complete'])
        data['derived']['latest_total_debt' if field == 'debt' else 'latest_cash'] = amount
        result.append(value(valuation_module, data))
    assert result[0]['ev'] != result[1]['ev']
    assert result[0]['intrinsic_value_band'] == result[1]['intrinsic_value_band']


def test_interest_and_required_return_reduce_equity_value(valuation_module):
    baseline = value(valuation_module, FIX['complete'])
    data = deepcopy(FIX['complete'])
    for period in data['financials']['ocf']:
        period['val'] -= FIX['sensitivity']['ocf_reduction']
    data['derived']['latest_ocf'] -= FIX['sensitivity']['ocf_reduction']
    data['derived']['latest_fcf'] -= FIX['sensitivity']['ocf_reduction']
    less_cash = value(valuation_module, data)
    config = deepcopy(FIX['config'])
    config['cap_rate_high'] = FIX['sensitivity']['higher_cap_rate']
    higher_return = value(valuation_module, FIX['complete'], config=config)
    assert less_cash['intrinsic_value_band']['equity_low'] < baseline['intrinsic_value_band']['equity_low']
    assert higher_return['intrinsic_value_band']['equity_low'] < baseline['intrinsic_value_band']['equity_low']


@pytest.fixture
def cli(valuation_module, state, monkeypatch):
    calls = []
    monkeypatch.setattr(valuation_module, 'init_edgar', lambda: calls.append('init'))
    monkeypatch.setattr(valuation_module, '_get_market_cap',
                        lambda *args: (calls.append('market') or FIX['market_cap'], FIX['cli']['market_source']))
    monkeypatch.setattr(valuation_module, '_val_cfg', lambda: deepcopy(FIX['config']))
    monkeypatch.setattr(valuation_module, 'today', lambda: FIX['cli']['date'])

    def invoke(path, ticker=None):
        monkeypatch.setattr(sys, 'argv', ['valuation.py', '--json', str(path), '--ticker',
                                        ticker or FIX['complete']['ticker']])
        return valuation_module.main()

    return invoke, calls


def input_file(directory, data=None):
    path = directory / FIX['cli']['input_name']
    path.write_text(json.dumps(FIX['complete'] if data is None else data), encoding='utf-8')
    return path


@pytest.mark.parametrize('kind', ['unversioned', 'source', 'public', 'hardlinked'])
def test_unproved_mutating_input_is_refused_before_live_work(cli, state, tmp_path, monkeypatch, kind):
    outputs = importlib.import_module('_output_paths')
    directory = tmp_path
    if kind == 'source':
        directory = tmp_path / FIX['cli']['tool_name']
        directory.mkdir()
        monkeypatch.setattr(outputs, 'SOURCE_ROOT', directory)
    elif kind == 'public':
        directory = tmp_path / FIX['cli']['public_name']
        directory.mkdir()
        (directory / '.git').mkdir()
        state['origins'][str(directory)] = FIX['cli']['public_origin']
        state['visibility'][FIX['cli']['public_identity']] = 'PUBLIC'
    elif kind == 'hardlinked':
        directory = Path(state['companion'])
    source = input_file(directory)
    before = source.read_bytes()
    if kind == 'hardlinked':
        original_stat = Path.stat

        def linked_metadata(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            return SimpleNamespace(st_mode=result.st_mode, st_nlink=2) if path == source else result

        monkeypatch.setattr(Path, 'stat', linked_metadata)
    invoke, calls = cli
    with pytest.raises((RuntimeError, ValueError, SystemExit)):
        invoke(source)
    assert not calls
    if kind == 'hardlinked':
        monkeypatch.setattr(Path, 'stat', original_stat)
    assert source.read_bytes() == before
    assert not Path(state['root']).exists()


@pytest.mark.parametrize('identity', ['different', 'missing', 'invalid_cli'])
def test_identity_failure_preserves_input_and_existing_output(cli, state, identity):
    data = deepcopy(FIX['complete'])
    ticker = None
    if identity == 'different':
        data['ticker'] = FIX['cli']['other_ticker']
    elif identity == 'missing':
        del data['ticker']
    else:
        ticker = FIX['cli']['invalid_ticker']
    source = input_file(Path(state['companion']), data)
    before = source.read_bytes()
    output = Path(state['root']) / f"valuation_{FIX['complete']['ticker']}_{FIX['cli']['date']}.json"
    output.parent.mkdir(parents=True)
    output.write_text(FIX['cli']['prior_output'], encoding='utf-8')
    invoke, calls = cli
    with pytest.raises((RuntimeError, ValueError, SystemExit)):
        invoke(source, ticker)
    assert not calls
    assert source.read_bytes() == before
    assert output.read_text(encoding='utf-8') == FIX['cli']['prior_output']


def test_valid_private_input_keeps_the_merge_contract(cli, state):
    source = input_file(Path(state['companion']))
    invoke, calls = cli
    invoke(source, FIX['complete']['ticker'].lower())
    merged = json.loads(source.read_text(encoding='utf-8'))
    output = Path(state['root']) / f"valuation_{FIX['complete']['ticker']}_{FIX['cli']['date']}.json"
    assert merged['valuation'] == json.loads(output.read_text(encoding='utf-8'))
    assert merged['financials'] == FIX['complete']['financials']
    assert merged['valuation']['ticker'] == FIX['complete']['ticker']
    assert calls == ['init', 'market']


@pytest.mark.parametrize('data', FIX['cli']['invalid_documents'])
def test_invalid_document_fails_before_live_work(cli, state, data):
    source = input_file(Path(state['companion']), data)
    before = source.read_bytes()
    invoke, calls = cli
    with pytest.raises((RuntimeError, ValueError, SystemExit)):
        invoke(source)
    assert not calls
    assert source.read_bytes() == before
    assert not Path(state['root']).exists()


def test_unproved_report_destination_fails_before_live_work(cli, state, tmp_path, monkeypatch):
    source = input_file(Path(state['companion']))
    before = source.read_bytes()
    directory = tmp_path / FIX['cli']['public_name']
    directory.mkdir()
    (directory / '.git').mkdir()
    state['origins'][str(directory)] = FIX['cli']['public_origin']
    state['visibility'][FIX['cli']['public_identity']] = 'PUBLIC'
    monkeypatch.setenv('SMALLCAP_OUTPUT_DIR', str(directory))
    invoke, calls = cli
    with pytest.raises((RuntimeError, ValueError, SystemExit)):
        invoke(source)
    assert not calls
    assert source.read_bytes() == before
    assert list(directory.iterdir()) == [directory / '.git']
