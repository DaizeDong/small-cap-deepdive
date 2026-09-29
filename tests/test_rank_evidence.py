"""Ranking preserves report risk evidence through the real output-producing caller."""
import json
from pathlib import Path

import pytest

from test_private_runs import state
from test_finalize_boundaries import invoke
from make_fixtures import ranking_scenarios, malformed_ranking_scenarios


@pytest.mark.parametrize('case', ranking_scenarios(), ids=lambda case: case['name'])
def test_report_and_sidecar_flags_survive_complete_rank_call(state, monkeypatch, case):
    run = Path(state['root']) / case['name']
    run.mkdir(parents=True)
    (run / ('report_' + case['ticker'] + '.md')).write_text(case['report'], encoding='utf-8')
    (run / ('report_' + case['safe_ticker'] + '.md')).write_text(case['safe_report'], encoding='utf-8')
    if case['sidecar'] is not None:
        path = run / ('deepdive_' + case['ticker'] + '_' + case['asof'] + '.json')
        path.write_text(json.dumps(case['sidecar']), encoding='utf-8')
    assert invoke('rank', ['--input', str(run)], monkeypatch) == 0
    lines = (run / 'RANKING.md').read_text(encoding='utf-8').splitlines()
    risk = next(line for line in lines if '| ' + case['ticker'] + ' |' in line)
    safe = next(line for line in lines if '| ' + case['safe_ticker'] + ' |' in line)
    cells = [value.strip() for value in risk.split('|')[1:-1]]
    assert cells[-1] == str(case['expected_flags'])
    assert ('⬇沉底' in cells[0]) is case['expected_sink']
    assert (lines.index(risk) > lines.index(safe)) is case['expected_sink']


@pytest.mark.parametrize('case', malformed_ranking_scenarios(), ids=lambda case: case['name'])
def test_malformed_rating_fence_cannot_replace_prior_ranking(state, monkeypatch, case):
    run = Path(state['root']) / case['name']
    run.mkdir(parents=True)
    (run / ('report_' + case['ticker'] + '.md')).write_text(case['report'], encoding='utf-8')
    target = run / 'RANKING.md'
    target.write_text(case['safe_report'], encoding='utf-8')
    with pytest.raises((ValueError, OverflowError)):
        invoke('rank', ['--input', str(run)], monkeypatch)
    assert target.read_text(encoding='utf-8') == case['safe_report']
