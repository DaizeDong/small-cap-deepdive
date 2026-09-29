"""Configured numerical thresholds reach real consumers as finite numbers."""
import json
from pathlib import Path

import pytest

from test_private_runs import state, common
from make_fixtures import config_override_scenarios

CASE = config_override_scenarios()


@pytest.mark.parametrize('key,raw,expected', CASE['valid'])
def test_numeric_environment_settings_are_typed(state, monkeypatch, key, raw, expected):
    monkeypatch.setenv('SMALLCAP_' + key.upper(), raw)
    value = common().load_config()[key]
    assert type(value) is type(expected)
    assert value == expected


def test_numeric_environment_thresholds_drive_real_band_selection(state, monkeypatch):
    for key in ('market_cap_max', 'watch_band_max'):
        monkeypatch.setenv('SMALLCAP_' + key.upper(), CASE['band'][key])
    module = common()
    for capitalization, expected in CASE['band']['capitalizations']:
        assert module.band_for(capitalization) == expected


@pytest.mark.parametrize('key,raw', CASE['invalid'])
def test_invalid_numeric_environment_fails_at_configuration_boundary(state, monkeypatch, key, raw):
    monkeypatch.setenv('SMALLCAP_' + key.upper(), raw)
    with pytest.raises(RuntimeError, match=key):
        common().load_config()


def test_nonnumeric_private_setting_is_not_exposed_as_numeric_threshold(state):
    path = Path(state['companion']) / 'config.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    config['market_cap_max'] = CASE['invalid'][0][1]
    path.write_text(json.dumps(config), encoding='utf-8')
    with pytest.raises(RuntimeError, match='market_cap_max'):
        common().load_config()
