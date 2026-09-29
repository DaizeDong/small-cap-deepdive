"""Generate reproducible synthetic inputs for private-output regression tests."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ssh_alias_scenarios():
    """Ordinary SSH aliases and conservative unsupported-config controls."""
    alias = 'synthetic-gh'
    identity = 'example/synthetic-smallcap-config'
    ordinary = 'Host synthetic-gh\n  HostName github.com\n'
    return {'alias': alias, 'identity': identity, 'origin': 'git@'+alias+':'+identity+'.git',
            'ordinary': ordinary, 'cases': [
                ['scp', 'git@'+alias+':'+identity+'.git', ordinary, True],
                ['ssh-url', 'ssh://git@'+alias+'/'+identity+'.git', ordinary, True],
                ['multiple-hosts', 'git@'+alias+':'+identity+'.git', 'Host unused synthetic-gh\n HostName github.com\n', True],
                ['equals', 'git@'+alias+':'+identity+'.git', 'Host synthetic-gh\n HostName = "github.com" # synthetic\n', True],
                ['inactive-commands', 'git@'+alias+':'+identity+'.git', ordinary+' ProxyCommand synthetic-no-execute\n LocalCommand synthetic-no-execute\n', True],
                ['literal-https', 'https://github.com/'+identity+'.git', None, True],
                ['literal-ssh', 'git@github.com:'+identity+'.git', None, True],
                ['literal-host-rewrite', 'git@github.com:'+identity+'.git', 'Host github.com\n HostName example.com\n', False],
                ['literal-global-rewrite', 'git@github.com:'+identity+'.git', 'HostName example.com\n', False],
                ['literal-unmatched-config', 'git@github.com:'+identity+'.git', 'Host unrelated\n HostName example.com\n', True],
                ['unknown', 'git@unknown-synthetic:'+identity+'.git', ordinary, False],
                ['missing', 'git@'+alias+':'+identity+'.git', None, False],
                ['unrelated', 'git@'+alias+':'+identity+'.git', 'Host synthetic-gh\n HostName example.com\n', False],
                ['lookalike', 'git@'+alias+':'+identity+'.git', 'Host synthetic-gh\n HostName github.com.example.com\n', False],
                ['first-value', 'git@'+alias+':'+identity+'.git', 'Host *\n HostName example.com\n'+ordinary, False],
                ['negated', 'git@'+alias+':'+identity+'.git', 'Host * !synthetic-gh\n HostName github.com\n', False],
                ['match-exec', 'git@'+alias+':'+identity+'.git', ordinary+'Match exec "synthetic-no-execute"\n', False],
                ['include', 'git@'+alias+':'+identity+'.git', 'Include synthetic-config\n'+ordinary, False],
                ['malformed', 'git@'+alias+':'+identity+'.git', 'Host "synthetic-gh\n HostName github.com\n', False],
                ['https-alias', 'https://'+alias+'/'+identity+'.git', ordinary, False],
                ['bad-slug', 'git@'+alias+':example/repo/extra.git', ordinary, False],
                ['wildcard', 'git@'+alias+':'+identity+'.git', 'Host synthetic-*\n HostName github.com\n', True],
                ['first-value-preserved', 'git@'+alias+':'+identity+'.git', ordinary+'Host *\n HostName example.com\n', True],
                ['compact-equals', 'git@'+alias+':'+identity+'.git', 'Host=synthetic-gh\n HostName=github.com\n', True],
                ['global-hostname', 'git@'+alias+':'+identity+'.git', 'HostName github.com\n', True],
                ['case-insensitive', 'git@SYNTHETIC-GH:'+identity+'.git', 'hOsT Synthetic-Gh\n HOSTNAME GitHub.com\n', True],
                ['literal-brackets', 'git@'+alias+':'+identity+'.git', 'Host [s]ynthetic-gh\n HostName github.com\n', False],
                ['canonicalization', 'git@'+alias+':'+identity+'.git', ordinary+' CanonicalizeHostname yes\n', False],
                ['empty-host', 'git@'+alias+':'+identity+'.git', 'Host\n HostName github.com\n', False],
            ]}


def private_run_scenario():
    return {
        'origin': 'https://github.com/example/synthetic-smallcap-config.git',
        'other_origin': 'git@github.com:example/synthetic-other-config.git',
        'config': {'schema_version': 1, 'sec_user_agent': 'user1@example.com',
                   'output_dir': 'reports/smallcap'},
        'label': 'Synthetic theme', 'unicode_label': '合成研究 A', 'note': 'Generated control',
        'hash': hashlib.sha256(b'synthetic-input-v1').hexdigest(),
        'other_hash': hashlib.sha256(b'synthetic-input-v2').hexdigest(),
        'invalid_names': ['', '.', '..', '...', '../escape', 'nested/name', 'nested\\name',
                          '/absolute', 'C:drive', 'bad\nname', 'bad\x00name'],
        'report': {'ticker': 'SYNTH', 'company_name': 'AcmeCorp', 'valuation': {}},
        'asof': '2020-01-01', 'linked_marker': 'gitdir: synthetic-git-metadata\n',
        'dependencies': {'requests': '2.31.0', 'edgartools': '5.35.1',
                         'yfinance': '1.4.1', 'pandas': '3.0.1'},
        'run_state': {'empty': '', 'active': 'synthetic-active',
                      'explicit': 'synthetic-explicit', 'unsafe': '../synthetic-escape',
                      'pids': [101, 202],
                      'inherited': [None, 'synthetic-active', '../synthetic-escape']},
    }


def generated():
    payload = (json.dumps(private_run_scenario(), ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    finalizer = (json.dumps(finalizer_scenario(), ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    manifest = {'origin': 'tools/make_fixtures.py:private_run_scenario', 'synthetic_only': True,
                'files': {'private_runs.json': hashlib.sha256(payload).hexdigest(),
                          'finalizer.json': hashlib.sha256(finalizer).hexdigest()}}
    return {'private_runs.json': payload,
            'finalizer.json': finalizer,
            'manifest.json': (json.dumps(manifest, indent=2)+'\n').encode('utf-8')}


def finalizer_scenario():
    """Invented report and relocation inputs, independent of investment data."""
    return {
        'run': 'synthetic-output-run', 'ticker': 'SYNTA', 'other_ticker': 'SYNTB',
        'report': '# AcmeCorp synthetic report\n\n```rating\nverdict_date: 2000-01-01\nrating: watch\nconfidence: 64\n'
                  'hold_period: 12 months\nmos_basis: abstain\nbuy_eligible: false\n'
                  'killflag_count: 0\nfundamental_decline_flag: false\n```\n',
        'canonical': '{"synthetic_location": "canonical"}\n',
        'duplicate': '{"synthetic_location": "nested"}\n',
        'other_origin': 'https://github.com/example/synthetic-other-config.git',
        'rank_error': 'Synthetic ranking child failed before output.',
        'rank_returncodes': [0, 7],
    }


def ranking_scenarios():
    """Independent synthetic report/sidecar disagreements for the complete rank caller."""
    cases = []
    for name, report_flags, sidecar_flags, expected, sink in [
        ('report-only-two', 2, None, 2, True),
        ('report-only-zero', 0, None, 0, False),
        ('report-higher', 3, 1, 3, True),
        ('sidecar-higher', 1, 3, 3, True),
        ('report-two-sidecar-zero', 2, 0, 2, True),
        ('sidecar-two-report-zero', 0, 2, 2, True),
        ('both-one', 1, 1, 1, False),
    ]:
        report = finalizer_scenario()['report'].replace('rating: watch', 'rating: buy')
        report = report.replace('confidence: 64', 'confidence: 99')
        report = report.replace('killflag_count: 0', 'killflag_count: ' + str(report_flags))
        cases.append({'name': name, 'ticker': 'SYNRISK', 'safe_ticker': 'SYNSAFE',
                      'report': report, 'safe_report': finalizer_scenario()['report'],
                      'sidecar': None if sidecar_flags is None else {
                          'killflag_count': sidecar_flags, 'derived': {}, 'tenk': {}, 'insider': {}},
                      'asof': '2000-01-01', 'expected_flags': expected, 'expected_sink': sink})
    return cases


def malformed_ranking_scenarios():
    """Bad fenced numeric values must not promote optimistic legacy prose."""
    base = ranking_scenarios()[0]
    return [{**base, 'name': 'invalid-confidence-' + value,
             'report': base['report'].replace('confidence: 99', 'confidence: ' + value)
                       + '\n评级: 买入\n置信度: 99%\n'} for value in ['nan', 'inf']]


def initialization_scenarios():
    """Synthetic setup destinations and metadata without an EDGAR identity."""
    return {
        'destinations': [('private', 'PRIVATE', True), ('public', 'PUBLIC', False),
                         ('unknown', None, False), ('unversioned', 'PRIVATE', False)],
        'existing_config': '{"synthetic_preserved": true}\n',
        'ambient_host': 'example.com',
        'public_origin': 'https://github.com/example/synthetic-public.git',
        'public_identity': 'example/synthetic-public',
        'remote_cases': [('push-public', 'PUBLIC', False), ('push-unknown', None, False),
                         ('extra-public', 'PUBLIC', False), ('extra-unknown', None, False),
                         ('extra-private', 'PRIVATE', True), ('multi-public', 'PUBLIC', False),
                         ('multi-private', 'PRIVATE', True)],
    }


def decision_scenarios():
    """Synthetic final-decision, provenance, and candidate-integrity controls."""
    ticker = 'SYNDEC'
    date = '2000-01-01'
    base = finalizer_scenario()['report']
    report = '# ' + ticker + ' Deep Dive — ' + date + ' (timestamp-locked)\n' + base.split('\n', 1)[1]
    return {
        'ticker': ticker, 'date': date, 'later_date': '2001-01-01', 'report': report,
        'prior_output': '[{"synthetic_prior_output": true}]\n',
        'candidate': {'ticker': ticker, 'band': 'deep'},
        'unfinished': [report.replace('rating: watch', 'rating: ' + value)
                       + '\n评级: 买入\n置信度: 99%\n'
                       for value in ['TBD', 'unknown', '']],
        'bad_confidence': [report.replace('confidence: 64', 'confidence: ' + value)
                           for value in ['TBD', '-1', '101']],
        'risk_report': report.replace('killflag_count: 0', 'killflag_count: 3')
                             .replace('fundamental_decline_flag: false',
                                      'fundamental_decline_flag: true\nconcentration_flag: kill'),
        'invalid_candidates': ['{', '{}', 'null', '{"candidates": {}}', '[null]'],
        'empty_survivors': [[], {'candidates': []}],
    }


def financial_scenarios():
    """Expose the financial synthetic corpus through the common fixture entrypoint."""
    from financial_fixtures import financial_scenarios as build
    return build()


def tracking_scenarios():
    """Synthetic ledger rows for review coverage and persisted risk provenance."""
    decision = decision_scenarios()
    base = {'ticker': decision['ticker'], 'verdict_date': decision['date'],
            'rating': '买入', 'scored': False, 'horizon_months': 12,
            'implied_prob': 0.8, 'mos_pct': 35, 'fp_cause': 'synthetic mismatch'}
    return {'mixed': [{**base, 'adjudication': label} for label in
                      ('data_verified_clean', 'data_false_positive', None, 'unrecognized')],
            'unreviewed': [{**base, 'adjudication': None}],
            'prior_bytes': json.dumps({**base, 'rating': '观察'}, ensure_ascii=False) + '\n',
            'malformed_ledgers': ['{broken\n', '[]\n', 'null\n']}


def config_override_scenarios():
    """Generate typed settings and invalid numbers for configuration entrypoints."""
    return {
        'valid': [('market_cap_max', '1000000000', 1000000000),
                  ('watch_band_max', '2e9', 2000000000),
                  ('normalize_years', '3', 3), ('wacc', '0.12', 0.12)],
        'invalid': [('market_cap_max', 'NaN'), ('wacc', '1e309'),
                    ('wacc', '-Infinity'), ('normalize_years', '3.5'),
                    ('normalize_years', 'true'), ('market_cap_max', 'null'),
                    ('cap_rate_low', 'invalid')],
        'band': {'market_cap_max': '1000000000', 'watch_band_max': '2000000000',
                 'capitalizations': [(500000000, 'deep'), (1500000000, 'watch'),
                                    (2500000000, 'large')]},
    }


def debt_scenarios():
    """Expose generated contractual-debt evidence controls through the fixture CLI module."""
    from debt_fixtures import debt_scenarios as generate
    return generate()


def annual_fact_scenarios():
    """Synthetic SEC facts distinguish period duration from annual-filing labels."""
    annual = {'start': '2023-01-01', 'end': '2023-12-31', 'val': 1000,
              'fy': 2023, 'fp': 'FY', 'form': '10-K', 'filed': '2024-02-01'}
    return {'annual': annual,
            'quarter': {**annual, 'start': '2023-10-01', 'val': 90},
            'transition': {**annual, 'start': '2023-07-01', 'form': '10-KT', 'val': 400},
            'restated': {**annual, 'val': 1100, 'filed': '2024-05-01'},
            'instant': {'end': '2023-12-31', 'val': 2000, 'filed': '2024-02-01'},
            'asof': '2024-03-01', 'cik': '42', 'concept': 'Revenues',
            'instant_concept': 'Assets',
            'flow_concepts': ['Revenues', 'NetIncomeLoss', 'ProfitLoss',
                              'NetCashProvidedByUsedInOperatingActivities',
                              'PaymentsToAcquirePropertyPlantAndEquipment',
                              'WeightedAverageNumberOfDilutedSharesOutstanding']}


def debt_valuation_scenarios():
    """Generate unknown-debt cases and matched reported-debt valuation controls."""
    from copy import deepcopy
    financial = financial_scenarios()
    variants = {
        'missing': {'latest_total_debt': None},
        'unavailable': {'debt_evidence_status': 'unavailable'},
        'conflicting': {'debt_evidence_status': 'conflicting'},
        'flagged': {'debt_evidence_status': 'reported', 'debt_evidence_uncertain': True},
        'proxy': {'debt_source': 'Liabilities_proxy'},
        'zero': {'latest_total_debt': 0, 'debt_evidence_status': 'reported'},
        'reported': {'debt_evidence_status': 'reported'},
    }
    cases = {}
    for name, changes in variants.items():
        data = deepcopy(financial['complete'])
        data['derived'].update(changes)
        data['derived']['debt_evidence_detail'] = 'synthetic debt evidence case: ' + name
        cases[name] = data
    return {'cases': cases, 'config': financial['config'],
            'market_cap': financial['buy_market_cap']}


def sic_recall_scenarios():
    """Synthetic issuer identities and sidecar destinations for SIC recall controls."""
    return {
        'theme': 'synthetic-machinery',
        'fts': [{'cik': '0000000042', 'ticker': 'SYNTH', 'name': 'AcmeCorp'}],
        'sic': [{'cik': '42', 'name': 'AcmeCorp', 'sic': '1234'},
                {'cik': '0000000043', 'name': 'AcmeCorp', 'sic': '1234'}],
        'invalid_ciks': [None, '', True, 0, -42, 1.2, 'invalid', '12.3', '10000000000'],
        'public_origin': 'https://github.com/example/synthetic-public',
        'public_identity': 'example/synthetic-public',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--out', type=Path, help='write generated fixture files into this directory')
    args = parser.parse_args()
    destination = args.out if args.out is not None else ROOT/'tests/fixtures'
    for name, content in generated().items():
        path = destination/name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise SystemExit('generated fixture mismatch: '+name)
        else:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    print('synthetic fixtures match' if args.check else 'synthetic fixtures generated')


if __name__ == '__main__':
    main()
