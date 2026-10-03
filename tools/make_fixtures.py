"""Generate reproducible synthetic inputs for private-output regression tests."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def output_path_security_case(root):
    from output_path_fixtures import output_path_security_case as generate
    return generate(root)


def output_visibility_receipt(states):
    from output_path_fixtures import visibility_receipt
    return visibility_receipt(states)


def filing_disclosure_scenarios():
    """Invented filing statements exercise polarity, timing and unresolved evidence."""
    rows = [
        ('going-current', 'going_concern', 'These conditions raise substantial doubt about AcmeCorp ability to continue as a going concern.', True, 'affirmative'),
        ('going-negative', 'going_concern', 'There is no substantial doubt about AcmeCorp ability to continue as a going concern.', False, 'negated'),
        ('going-not-raise', 'going_concern', 'These conditions do not raise substantial doubt about our ability to continue as a going concern.', False, 'negated'),
        ('going-alleviated', 'going_concern', 'Our completed financing has alleviated substantial doubt about our ability to continue as a going concern.', False, 'resolved'),
        ('going-not-alleviated', 'going_concern', 'Substantial doubt about our ability to continue as a going concern has not been alleviated.', True, 'affirmative'),
        ('going-conditional', 'going_concern', 'If financing becomes unavailable, conditions may raise substantial doubt about our ability to continue as a going concern.', None, 'ambiguous'),
        ('going-basis-only', 'going_concern', 'The financial statements were prepared on a going concern basis.', False, 'not_asserted'),
        ('going-unlinked', 'going_concern', 'AcmeCorp uses the going concern basis. A proposed transaction remains subject to substantial doubt.', None, 'ambiguous'),
        ('weakness-current', 'material_weakness', 'We identified a material weakness in internal control over financial reporting.', True, 'affirmative'),
        ('weakness-negative', 'material_weakness', 'We have not identified any material weaknesses in internal control over financial reporting.', False, 'negated'),
        ('weakness-no-exists', 'material_weakness', 'No material weakness exists in our internal control over financial reporting.', False, 'negated'),
        ('weakness-remediated', 'material_weakness', 'The material weakness identified in the prior year has been fully remediated.', False, 'resolved'),
        ('weakness-not-remediated', 'material_weakness', 'The previously identified material weakness has not been remediated.', True, 'affirmative'),
        ('weakness-historical', 'material_weakness', 'In a prior year, we identified a material weakness in internal control over financial reporting.', None, 'historical'),
        ('weakness-conditional', 'material_weakness', 'If we identify a material weakness, our controls may not be effective.', None, 'ambiguous'),
        ('weakness-unlinked', 'material_weakness', 'A material weakness is a defined accounting concept. Our marketing campaign was not effective.', None, 'ambiguous'),
        ('weakness-mixed', 'material_weakness', 'No material weakness exists in inventory controls, but we identified a material weakness in payroll controls.', True, 'affirmative'),
        ('weakness-two-periods', 'material_weakness', 'The prior material weakness has been fully remediated. We identified a material weakness in a different current process.', True, 'affirmative'),
        ('weakness-hypothetical-remedy', 'material_weakness', 'We identified a material weakness and plan to remediate it in the next year.', True, 'affirmative'),
        ('weakness-no-assurance', 'material_weakness', 'We cannot provide assurance that no material weakness will arise in the future.', None, 'ambiguous'),
    ]
    rows.extend([
        ('weakness-none-unremediated', 'material_weakness', 'There are no unremediated material weaknesses at AcmeCorp.', False, 'negated'),
        ('weakness-unremediated-not-found', 'material_weakness', 'We have not detected any unremediated material weakness in the current controls.', False, 'negated'),
        ('weakness-unremediated-current', 'material_weakness', 'An unremediated material weakness remains in the inventory process.', True, 'affirmative'),
        ('weakness-unresolved-negative', 'material_weakness', 'No unresolved material weakness exists in the inventory process.', False, 'negated'),
        ('going-negative-unrelated-unresolved', 'going_concern', 'There is no substantial doubt about our ability to continue as a going concern and the inventory material weakness remains unremediated.', False, 'negated'),
        ('going-negative-unrelated-future-remedy', 'going_concern', 'There is no substantial doubt about our ability to continue as a going concern and we plan to remediate the inventory issue.', False, 'negated'),
        ('weakness-remedy-then-current', 'material_weakness', 'The material weakness in payroll has been corrected and another material weakness remains in inventory.', True, 'affirmative'),
        ('weakness-clean-then-current', 'material_weakness', 'No material weakness was found in payroll and a material weakness exists in inventory.', True, 'affirmative'),
        ('weakness-unrelated-remedy', 'material_weakness', 'A shipping dispute was resolved and we identified a material weakness in financial reporting.', True, 'affirmative'),
        ('weakness-shared-subject-current', 'material_weakness', 'We resolved a billing dispute and identified a material weakness in the inventory controls.', True, 'affirmative'),
        ('going-unrelated-remedy', 'going_concern', 'The shipping dispute was resolved and substantial doubt about our ability to continue as a going concern exists.', True, 'affirmative'),
        ('going-new-current-assertion', 'going_concern', 'There was no substantial doubt about our ability to continue as a going concern and current conditions raise substantial doubt about our ability to continue as a going concern.', True, 'affirmative'),
        ('going-remedy-then-current', 'going_concern', 'Earlier substantial doubt about our ability to continue as a going concern was alleviated and new conditions raise substantial doubt about our ability to continue as a going concern.', True, 'affirmative'),
        ('weakness-comma-current', 'material_weakness', 'No material weakness was identified in payroll, a material weakness exists in inventory.', True, 'affirmative'),
        ('weakness-unattached-remedy', 'material_weakness', 'The vendor contract was resolved following a discussion of material weaknesses.', None, 'ambiguous'),
        ('going-unattached-remedy', 'going_concern', 'The vendor contract was resolved following a discussion of substantial doubt about our ability to continue as a going concern.', None, 'ambiguous'),
        ('going-topics-unseparated', 'going_concern', 'An unremediated material weakness has no relation to substantial doubt about our ability to continue as a going concern.', None, 'ambiguous'),
        ('weakness-conditional-coordination', 'material_weakness', 'If a material weakness were found and another material weakness remained, an inspection could be required.', None, 'ambiguous'),
        ('weakness-unresolved-current', 'material_weakness', 'No unremediated material weakness was found, but the old material weakness remains unresolved.', True, 'affirmative'),
        ('weakness-unbound-double-mention', 'material_weakness', 'No material weakness related to an account was reported with the material weakness affecting another account.', None, 'ambiguous'),
    ])
    return {'ticker': 'SYNTH', 'filing_date': '2000-03-01', 'cases': [
        {'id': name, 'topic': topic, 'text': text, 'flag': flag, 'status': status}
        for name, topic, text, flag, status in rows]}


def filing_negation_scenarios():
    """Generate varied scope and remedy statements without using filing data."""
    rows = []
    subjects = {
        'material_weakness': ('material weakness in inventory controls', 'remediated'),
        'going_concern': ('substantial doubt about our ability to continue as a going concern', 'alleviated'),
    }
    for topic in subjects:
        disclosure = ('material weaknesses' if topic == 'material_weakness'
                      else subjects[topic][0])
        for modifier in ('remaining', 'separately documented', 'previously unreported', 'significant'):
            for quantifier in ('no', 'without any'):
                if quantifier == 'no':
                    text = ('There are ' if topic == 'material_weakness' else 'There is ')
                else:
                    text = 'We completed the assessment '
                text += f'{quantifier} {modifier} unresolved {disclosure}.'
                name = f'{topic}-{quantifier}-{modifier}'.replace(' ', '-')
                rows.append((name, topic, text, None, 'ambiguous'))
    for topic, (subject, verb) in subjects.items():
        for negator in ('not', 'never'):
            for modifier in ('', 'fully ', 'successfully '):
                rows.extend([
                    (f'{topic}-object-{negator}-{modifier.strip() or "plain"}', topic,
                     f'We have {negator} {modifier}{verb} the {subject}.', True, 'affirmative'),
                    (f'{topic}-subject-{negator}-{modifier.strip() or "plain"}', topic,
                     f'The {subject} has {negator} been {modifier}{verb}.', True, 'affirmative'),
                ])
        rows.extend([
            (f'{topic}-qualified-action', topic,
             f'We have not always {verb} the {subject}.', None, 'ambiguous'),
            (f'{topic}-interrupted-action', topic,
             f'We have never, despite repeated attempts, {verb} the {subject}.', None, 'ambiguous'),
            (f'{topic}-double-action-negation', topic,
             f'The {subject} has not never been {verb}.', None, 'ambiguous'),
            (f'{topic}-completed-object-control', topic,
             f'We have successfully {verb} the {subject}.', False, 'resolved'),
            (f'{topic}-completed-subject-control', topic,
             f'The {subject} has already been fully {verb}.', False, 'resolved'),
        ])
    rows.extend([
        ('weakness-negated-report-of-absence', 'material_weakness',
         'We did not say there was no material weakness.', None, 'ambiguous'),
        ('going-negated-report-of-absence', 'going_concern',
         'We did not say there was no substantial doubt about our ability to continue as a going concern.', None, 'ambiguous'),
        ('weakness-negation-in-separated-assertion', 'material_weakness',
         'We never resolved the shipping dispute and identified a material weakness in inventory controls.', True, 'affirmative'),
        ('going-negation-in-separated-sentence', 'going_concern',
         'Substantial doubt about our ability to continue as a going concern has been alleviated. We never resolved the shipping dispute.', False, 'resolved'),
    ])
    return [{'id': name, 'topic': topic, 'text': text, 'flag': flag, 'status': status}
            for name, topic, text, flag, status in rows]


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
                ['inline-comment', 'git@'+alias+':'+identity+'.git', 'Host synthetic-gh\n HostName = "github.com" # synthetic\n', False],
                ['active-commands', 'git@'+alias+':'+identity+'.git', ordinary+' ProxyCommand synthetic-no-execute\n LocalCommand synthetic-no-execute\n', False],
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
                ['later-hostname-conflict', 'git@'+alias+':'+identity+'.git', ordinary+'Host *\n HostName example.com\n', False],
                ['compact-equals', 'git@'+alias+':'+identity+'.git', 'Host=synthetic-gh\n HostName=github.com\n', True],
                ['global-hostname', 'git@'+alias+':'+identity+'.git', 'HostName github.com\n', True],
                ['mixed-case-host-pattern', 'git@SYNTHETIC-GH:'+identity+'.git', 'hOsT Synthetic-Gh\n HOSTNAME GitHub.com\n', False],
                ['case-insensitive-directives', 'git@SYNTHETIC-GH:'+identity+'.git', 'hOsT synthetic-gh\n HOSTNAME GitHub.com\n', True],
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
    payloads = {
        "private_runs.json": (json.dumps(private_run_scenario(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "finalizer.json": (json.dumps(finalizer_scenario(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_full_review_regressions.py": full_review_regression_source().encode("utf-8"),
        "source22_contracts.json": (json.dumps(source22_scenarios(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_source22_contracts.py": source22_regression_source().encode("utf-8"),
        "source23_contracts.json": (json.dumps(source23_scenarios(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_source23_contracts.py": source23_regression_source().encode("utf-8"),
        "source24_contracts.json": (json.dumps(source24_scenarios(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_source24_contracts.py": source24_regression_source().encode("utf-8"),
        "source25_contracts.json": (json.dumps(source25_scenarios(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_source25_contracts.py": source25_regression_source().encode("utf-8"),
        "source26_contracts.json": (json.dumps(source26_scenarios(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_source26_contracts.py": source26_regression_source().encode("utf-8"),
        "source27_contracts.json": (json.dumps(source27_scenarios(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "test_source27_contracts.py": source27_regression_source().encode("utf-8"),
        "source28_contracts.json": (json.dumps(source28_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source28_contracts.py": source28_regression_source().encode("utf-8"),
        "source29_contracts.json": (json.dumps(source29_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source29_contracts.py": source29_regression_source().encode("utf-8"),
        "source30_contracts.json": (json.dumps(source30_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source30_contracts.py": source30_regression_source().encode("utf-8"),
        "source31_contracts.json": (json.dumps(source31_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source31_contracts.py": source31_regression_source().encode("utf-8"),
        "source32_contracts.json": (json.dumps(source32_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source32_contracts.py": source32_regression_source().encode("utf-8"),
        "source33_contracts.json": (json.dumps(source33_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source33_contracts.py": source33_regression_source().encode("utf-8"),
        "source34_contracts.json": (json.dumps(source34_scenarios(), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"),
        "test_source34_contracts.py": source34_regression_source().encode("utf-8"),
        "test_source35_contracts.py": source35_regression_source().encode("utf-8"),
        "test_source36_contracts.py": source36_regression_source().encode("utf-8"),
    }
    manifest = {"origin": "tools/make_fixtures.py:generated", "synthetic_only": True,
                "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()},
                "repository_examples": {name: hashlib.sha256(raw).hexdigest()
                                        for name, raw in source32_repository_examples().items()}}
    return {**payloads, "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8")}


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


def source26_debt_fixture(data):
    """Declare complete synthetic debt coverage; use only when constructing test inputs."""
    value = data["derived"].get("latest_total_debt")
    if value is None:
        data["financials"]["total_debt"] = []
        return data
    components = {name: 0 for name in (
        "LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings",
        "FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent")}
    components["LongTermDebtNoncurrent"] = value
    data["derived"].setdefault("debt_evidence_status", "reported")
    data["financials"]["total_debt"] = [{
        "end": "2024-12-31", "val": value, "source": "synthetic_complete_components",
        "debt_evidence_status": "reported", "debt_evidence_detail": None,
        "components": components, "aggregates": {}, "missing_components": [],
        "conflicting_aggregates": [],
    }]
    return data


def source26_review_receipt(row):
    """Generate review evidence for invented verdicts, never for loaded runtime history."""
    source_hash = hashlib.sha256(b"synthetic independent filing evidence").hexdigest()
    return {
        "schema_version": 1, "protocol": "smallcap-data-review-v1",
        "disposition": row["adjudication"],
        "verdict": {key: row.get(key) for key in
                    ("ticker", "cik", "verdict_date", "rating", "report_sha256")},
        "review_date": row["verdict_date"],
        "sources": [{"reference": "synthetic-filing-evidence", "sha256": source_hash}],
        "checks": [{"field": field, "source_sha256": source_hash,
                    "result": "mismatch" if row["adjudication"] == "data_false_positive" else "matches"}
                   for field in ("issuer_identity", "total_debt", "operating_cash_flow",
                                 "capital_expenditures", "verdict_inputs")],
    }


def source26_reviewed_fixture(row, ticker="SYNREVIEW"):
    """Supply the missing evidence contract of a synthetic positive review."""
    row.update(ticker=ticker, cik=None, verdict_date="2000-01-01",
               report_sha256=hashlib.sha256(("synthetic report " + ticker).encode()).hexdigest())
    row["adjudication_evidence"] = source26_review_receipt(row)
    return row


def financial_scenarios():
    """Expose the financial synthetic corpus through the common fixture entrypoint."""
    from datetime import date
    from financial_fixtures import financial_scenarios as build
    corpus = build()
    # These fixtures define calendar-year flows, including the unmatched older OCF.
    for case in corpus.values():
        if not isinstance(case, dict) or not isinstance(case.get('financials'), dict):
            continue
        source26_debt_fixture(case)
        for metric in ('ocf', 'capex', 'ebit', 'dep_amort'):
            for period in case['financials'].get(metric, []):
                end = date.fromisoformat(period['end'])
                start = date(end.year, 1, 1)
                period['start'] = start.isoformat()
                period['duration_days'] = (end - start).days
    for case in corpus["calibration_cases"]:
        for row in case["rows"]:
            if row.get("adjudication") in ("data_verified_clean", "data_false_positive"):
                source26_reviewed_fixture(row)
    return corpus


def deepdive_input_scenarios():
    """Generate synthetic page, annual-flow and valuation inputs with stated outcomes."""
    from copy import deepcopy
    from datetime import date
    from html import escape
    from urllib.parse import urlencode

    ticker = 'SYNF'
    observed_at = '2025-01-15'
    query = {'s': ticker, 'fd': '730', 'td': '0', 'xp': '1',
             'xs': '1', 'cnt': '100', 'page': '1'}
    response_url = 'https://openinsider.com/screener?' + urlencode(query)
    columns = ['Filing Date', 'Trade Date', 'Ticker', 'Trade Type', 'Value']
    purchase = {'Filing Date': '2024-06-02', 'Trade Date': '2024-06-01',
                'Ticker': ticker, 'Trade Type': 'P - Purchase', 'Value': '$1,200'}
    sale = {**purchase, 'Trade Type': 'S - Sale', 'Value': '$200'}

    def table(rows, headings=None, zero_message=None):
        headings = columns if headings is None else headings
        header = '<tr>' + ''.join('<th>' + escape(label) + '</th>' for label in headings) + '</tr>'
        if zero_message is not None:
            body = '<tr><td colspan="' + str(len(headings)) + '">' + escape(zero_message) + '</td></tr>'
        else:
            body = ''.join('<tr>' + ''.join('<td>' + escape(row[label]) + '</td>'
                                          for label in headings) + '</tr>' for row in rows)
        return '<table>' + header + body + '</table>'

    insider = []

    def page_case(case_id, html, *, expected=None, reason=None, incomplete=False, url=None):
        if reason is not None:
            expected = {'available': False, 'net_signal': None, 'reason': reason,
                        'status': 'incomplete' if incomplete else 'unavailable'}
        insider.append({'id': case_id, 'html': html, 'ticker': ticker,
                        'response_url': response_url if url is None else url,
                        'observed_at': observed_at, 'expected': expected})

    balanced = {'available': True, 'status': 'available', 'buys': 1, 'sells': 1,
                'open_market_buys': 1, 'open_market_sells': 1,
                'buy_value': 1200, 'sell_value': 200, 'net_signal': 'neutral'}
    zero = {'available': True, 'status': 'available', 'buys': 0, 'sells': 0,
            'buy_value': 0, 'sell_value': 0, 'net_signal': 'neutral'}
    page_case('matching-purchases-sales', table([purchase, sale]), expected=balanced)
    page_case('shifted-columns', table([purchase, sale],
              ['Ticker', 'Value', 'Trade Date', 'Trade Type', 'Filing Date']), expected=deepcopy(balanced))
    page_case('excluded-code-only', table([{**purchase, 'Trade Type': 'A - Grant'}]), expected=deepcopy(zero))
    for case_id, message in [('explicit-no-results', 'No results found.'),
                             ('explicit-no-matching', 'No matching transactions found.')]:
        page_case(case_id, table([], zero_message=message), expected=deepcopy(zero))
    page_case('reported-zero-dollar-purchase', table([{**purchase, 'Value': '$0'}]),
              expected={**zero, 'buys': 1, 'net_signal': 'net_buy'})
    page_case('unrelated-success-page', '<html><p>Synthetic unrelated page</p></html>',
              reason='recognized_table_missing')
    headerless = '<table><tr>' + ''.join('<td>' + escape(purchase[key]) + '</td>'
                                       for key in columns) + '</tr></table>'
    page_case('headerless-transactions', headerless, reason='recognized_table_missing')
    page_case('empty-without-zero-proof', table([]), reason='empty_table_without_zero_evidence', incomplete=True)
    page_case('wrong-row-ticker', table([{**purchase, 'Ticker': 'SYNX'}]),
              reason='row_ticker_mismatch', incomplete=True)
    for case_id, url in [
            ('wrong-response-host', response_url.replace('openinsider.com', 'example.com')),
            ('wrong-response-path', response_url.replace('/screener?', '/other?')),
            ('wrong-response-query', response_url.replace('fd=730', 'fd=30'))]:
        page_case(case_id, table([purchase]), reason='response_scope_mismatch', url=url)
    for case_id, changes in [
            ('missing-filing-date', {'Filing Date': ''}),
            ('invalid-trade-date', {'Trade Date': '2024-02-30'}),
            ('invalid-filing-date', {'Filing Date': 'not-a-date'})]:
        page_case(case_id, table([{**purchase, **changes}]), reason='row_date_invalid', incomplete=True)
    for case_id, changes in [
            ('old-filing', {'Filing Date': '2020-06-02', 'Trade Date': '2020-06-01'}),
            ('future-filing', {'Filing Date': '2026-06-02', 'Trade Date': '2026-06-01'}),
            ('trade-after-filing', {'Trade Date': '2024-06-03'})]:
        page_case(case_id, table([{**purchase, **changes}]),
                  reason='row_outside_filing_window', incomplete=True)
    closed = table([purchase])
    page_case('unclosed-table', closed.removesuffix('</table>'), reason='table_not_closed')
    page_case('unclosed-row', closed.replace('</tr></table>', '</table>'), reason='table_not_closed')
    page_case('unclosed-cell', closed.replace('</td></tr></table>', '</tr></table>'), reason='table_not_closed')
    page_case('ambiguous-tables', closed + closed, reason='ambiguous_tables')
    page_case('row-limit', table([purchase for _ in range(100)]), reason='row_limit_reached', incomplete=True)
    for case_id, suffix in [('next-page-with-ticker', '?s=' + ticker + '&page=2'),
                            ('next-page-without-ticker', '?page=2')]:
        page_case(case_id, closed + '<a href="' + escape(suffix, quote=True) + '">Next</a>',
                  reason='additional_results_page', incomplete=True)
    page_case('unknown-transaction-code', table([{**purchase, 'Trade Type': 'Q - Unknown'}]),
              reason='transaction_code_unsupported', incomplete=True)
    page_case('malformed-transaction-code', table([{**purchase, 'Trade Type': 'purchase'}]),
              reason='transaction_code_invalid', incomplete=True)
    page_case('malformed-money', table([{**purchase, 'Value': '$1,2x0'}]),
              reason='transaction_value_invalid', incomplete=True)

    identity_fields = ['unit', 'currency', 'cik', 'entity', 'taxonomy', 'accn']

    def fact(year, value, concept):
        start, end = date(year, 1, 1), date(year, 12, 31)
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'duration_days': (end - start).days, 'val': value,
                'unit': 'USD', 'currency': 'USD', 'cik': '0000000001',
                'entity': 'SyntheticIssuer', 'taxonomy': 'us-gaap',
                'accn': f'0000000001-{year + 1}-000001', 'concept': concept,
                'filed': f'{year + 1}-02-15', 'fy': year, 'fp': 'FY',
                'form': '10-K', 'source': 'synthetic_sec_fact'}

    def expected_period(year, value=None, reason='matching_annual_period'):
        qualified = reason == 'matching_annual_period'
        result = {'end': f'{year}-12-31', 'val': value,
                  'qualified': qualified, 'capex_complete': qualified, 'reason': reason}
        if qualified:
            result.update(identity_fields_checked=list(identity_fields), identity_fields_unrecorded=[],
                          provenance_complete=False)
        return result

    ocf = fact(2023, 30, 'NetCashProvidedByUsedInOperatingActivities')
    capex = fact(2023, 10, 'PaymentsToAcquirePropertyPlantAndEquipment')
    fcf = []

    def flow_case(case_id, operating, investing, expected, proxy=False):
        fcf.append({'id': case_id, 'ocf': deepcopy(operating), 'capex': deepcopy(investing),
                    'proxy': proxy, 'expected': deepcopy(expected)})

    matched = expected_period(2023, 20)
    matched['operands'] = {'ocf': {key: value for key, value in ocf.items() if key != 'val'},
                           'capex': {key: value for key, value in capex.items() if key != 'val'}}
    flow_case('matched-annual-pair', [ocf], [capex], [matched])
    flow_case('zero-capex', [ocf], [{**capex, 'val': 0}], [expected_period(2023, 30)])
    flow_case('end-mismatch', [ocf], [fact(2022, 10, capex['concept'])],
              [expected_period(2023, reason='matching_capex_period_missing')])
    shorter = {**capex, 'start': '2023-01-02', 'duration_days': 363}
    flow_case('same-end-different-duration', [ocf], [shorter],
              [expected_period(2023, reason='matching_capex_period_missing')])
    no_start = {key: value for key, value in ocf.items() if key != 'start'}
    flow_case('missing-ocf-start', [no_start], [capex],
              [expected_period(2023, reason='ocf_annual_period_unproven')])
    flow_case('invalid-declared-ocf-duration', [{**ocf, 'duration_days': 365}], [capex],
              [expected_period(2023, reason='ocf_annual_period_unproven')])
    flow_case('invalid-declared-capex-duration', [ocf], [{**capex, 'duration_days': None}],
              [expected_period(2023, reason='matching_capex_period_missing')])
    for side in ('ocf', 'capex'):
        for label, value in [('null', None), ('nan', float('nan')), ('infinite', float('inf')), ('boolean', True)]:
            operating = {**ocf, 'val': value} if side == 'ocf' else ocf
            investing = {**capex, 'val': value} if side == 'capex' else capex
            flow_case(side + '-' + label, [operating], [investing],
                      [expected_period(2023, reason='cash_flow_value_unavailable')])
    conflicts = {'unit': 'EUR', 'currency': 'EUR', 'cik': '0000000002',
                 'entity': 'OtherSyntheticIssuer', 'taxonomy': 'other-gaap',
                 'accn': '0000000001-2024-999999'}
    for field, value in conflicts.items():
        flow_case('identity-conflict-' + field, [ocf], [{**capex, field: value}],
                  [expected_period(2023, reason='fact_identity_conflict:' + field)])
    flow_case('duplicate-ocf', [ocf, deepcopy(ocf)], [capex],
              [expected_period(2023, reason='ambiguous_ocf_period')])
    flow_case('duplicate-capex', [ocf], [capex, deepcopy(capex)],
              [expected_period(2023, reason='ambiguous_capex_period')])
    flow_case('upstream-proxy', [ocf], [capex],
              [expected_period(2023, reason='upstream_ocf_proxy')], proxy=True)
    older_ocf, older_capex = fact(2022, 30, ocf['concept']), fact(2022, 10, capex['concept'])
    flow_case('newest-unmatched', [older_ocf, ocf], [older_capex],
              [expected_period(2022, 20), expected_period(2023, reason='matching_capex_period_missing')])
    flow_case('reversed-input-order', [ocf, older_ocf], [capex, older_capex],
              [expected_period(2022, 20), expected_period(2023, 20)])
    minimal_keys = ('start', 'end', 'duration_days', 'val')
    unrecorded = expected_period(2023, 20)
    unrecorded.update(identity_fields_checked=[], identity_fields_unrecorded=list(identity_fields))
    flow_case('unrecorded-identity-remains-explicit',
              [{key: ocf[key] for key in minimal_keys}], [{key: capex[key] for key in minimal_keys}], [unrecorded])
    flow_case('nonfinite-difference', [{**ocf, 'val': 1e308}], [{**capex, 'val': -1e308}],
              [expected_period(2023, reason='cash_flow_value_nonfinite')])

    corpus = financial_scenarios()
    million = 1_000_000
    complete = deepcopy(corpus['complete'])
    noncyclical = deepcopy(complete)
    for period in noncyclical['financials']['ebit']:
        period['val'] = 10 * million
    mismatch = deepcopy(noncyclical)
    mismatch['financials']['capex'][-1].update(start='2024-01-02', duration_days=364)
    newest_missing = deepcopy(noncyclical)
    newest_missing['financials']['capex'].pop()
    valuation = []
    window = [f'{year}-12-31' for year in range(2020, 2025)]
    for case_id, data, cyclical, normalized, latest, selected in [
            ('noncyclical-matched', noncyclical, False, 20 * million, 20 * million, window[-1:]),
            ('noncyclical-mismatched-positive-derived', mismatch, False, None, None, window[-1:]),
            ('noncyclical-newest-unmatched', newest_missing, False, None, None, window[-1:]),
            ('cyclical-complete-window', complete, True, 20 * million, 20 * million, window),
            ('cyclical-incomplete-window', corpus['historical_missing'], True, None, 20 * million, window),
            ('incomplete-outside-window', corpus['outside_window'], True, 20 * million, 20 * million, window)]:
        valuation.append({'id': case_id, 'data': deepcopy(data), 'market_cap': corpus['market_cap'],
                          'config': deepcopy(corpus['config']),
                          'expected': {'cyclical': cyclical, 'normalized_fcf': normalized,
                                       'latest_fcf': latest, 'normalized_fcf_is_proxy': normalized is None},
                          'expected_latest_end': '2024-12-31', 'expected_selected_ends': list(selected)})
    return {'insider': insider, 'fcf': fcf, 'valuation': valuation}


def tracking_scenarios():
    """Synthetic ledger rows for review coverage and persisted risk provenance."""
    decision = decision_scenarios()
    base = {'ticker': decision['ticker'], 'verdict_date': decision['date'],
            'rating': '买入', 'scored': False, 'horizon_months': 12,
            'implied_prob': 0.8, 'mos_pct': 35, 'fp_cause': 'synthetic mismatch'}
    mixed = []
    for index, label in enumerate(('data_verified_clean', 'data_false_positive', None, 'unrecognized')):
        row = {**base, 'ticker': 'SYNREVIEW' + str(index), 'adjudication': label}
        if label in ('data_verified_clean', 'data_false_positive'):
            source26_reviewed_fixture(row, row['ticker'])
        mixed.append(row)
    return {'mixed': mixed, 'unreviewed': [{**base, 'adjudication': None}],
            'prior_bytes': json.dumps({**base, 'rating': '观察'}, ensure_ascii=False) + '\n',
            'malformed_ledgers': ['{broken\n', '[]\n', 'null\n']}


def tracking_quote_scenarios():
    """Generate synthetic quote shapes and tracking rows for the W01 contract."""
    from copy import deepcopy

    ticker, benchmark = "SYNQ", "SYNB"
    requested = "2025-01-05"

    def history(name, dates, columns, values, *, price=None, resolved=None,
                reason=None, field="Close"):
        return {"name": name, "dates": dates, "columns": columns, "values": values,
                "price": price, "resolved": resolved, "reason": reason, "field": field}

    provider_cases = [
        history("weekend", ["2025-01-03"], ["Close"], [[12.0]],
                price=12.0, resolved="2025-01-03"),
        history("unsorted-with-future", ["2025-01-03", "2025-01-06", "2025-01-02"],
                ["Close"], [[12.0], [999.0], [11.0]], price=12.0, resolved="2025-01-03"),
        history("future-only", ["2025-01-06"], ["Close"], [[12.0]],
                reason="no_admissible_quote_date"),
        history("stale-only", ["2024-12-28"], ["Close"], [[12.0]],
                reason="no_admissible_quote_date"),
        history("window-boundary", ["2024-12-29"], ["Close"], [[12.0]],
                price=12.0, resolved="2024-12-29"),
        history("duplicate-date", ["2025-01-03", "2025-01-03"], ["Close"],
                [[12.0], [13.0]], reason="ambiguous_quote_date"),
        history("invalid-date", ["not-a-date"], ["Close"], [[12.0]],
                reason="invalid_quote_date"),
        history("missing-column", ["2025-01-03"], ["Volume"], [[12.0]],
                reason="missing_price_column"),
        history("duplicate-column", ["2025-01-03"], ["Close", "Close"], [[12.0, 13.0]],
                reason="ambiguous_price_column"),
        history("adjusted-close", ["2025-01-03"], ["Adj Close"], [[12.0]],
                price=12.0, resolved="2025-01-03", field="Adj Close"),
        history("field-symbol-columns", ["2025-01-03"],
                [("Close", "OTHER"), ("Close", ticker)], [[999.0, 12.0]],
                price=12.0, resolved="2025-01-03"),
        history("symbol-field-columns", ["2025-01-03"], [(ticker, "Close")], [[12.0]],
                price=12.0, resolved="2025-01-03"),
        history("wrong-symbol", ["2025-01-03"], [("Close", "OTHER")], [[12.0]],
                reason="missing_price_column"),
        history("empty", [], ["Close"], [], reason="no_quotes"),
    ]
    invalid_prices = [0.0, -1.0, True, False, None, "", float("nan"),
                      float("inf"), float("-inf"), [1.0, 2.0]]
    provider_cases.extend(
        history(f"invalid-price-{index}", ["2025-01-03"], ["Close"], [[value]],
                reason="invalid_price")
        for index, value in enumerate(invalid_prices)
    )

    def quote(symbol, price, requested_date="2024-01-01"):
        return {"schema_version": 1, "available": True, "price": price,
                "ticker": symbol, "requested_date": requested_date,
                "resolved_date": requested_date, "source": "yfinance",
                "price_basis": "yfinance_auto_adjust", "price_column": "Close", "reason": None}

    base_row = {"verdict_date": "2024-01-01", "ticker": ticker, "benchmark": benchmark,
                "rating": "买入", "horizon_months": 1, "entry_date": "2024-01-01",
                "entry_price": 10.0, "benchmark_entry_price": 20.0,
                "entry_quote": quote(ticker, 10.0), "benchmark_entry_quote": quote(benchmark, 20.0),
                "implied_prob": 0.5, "scored": False, "adjudication": None,
                "stock_return_pct": None, "realized_excess_pct": None, "brier": None}
    no_fetch = []

    def blocked(name, reason, *, updates=None, quote_updates=None, remove=None):
        row = deepcopy(base_row)
        row.update(updates or {})
        if quote_updates:
            row["entry_quote"].update(quote_updates)
        if remove:
            row.pop(remove)
        no_fetch.append({"name": name, "row": row, "reason": reason})

    blocked("legacy-stock", "stock_entry:legacy_quote_evidence_missing", remove="entry_quote")
    blocked("legacy-benchmark", "benchmark_entry:legacy_quote_evidence_missing",
            remove="benchmark_entry_quote")
    blocked("zero-entry", "stock_entry:entry_price_unavailable_or_invalid", updates={"entry_price": 0})
    blocked("boolean-benchmark", "benchmark_entry:entry_price_unavailable_or_invalid",
            updates={"benchmark_entry_price": True})
    blocked("entry-mismatch", "stock_entry:quote_price_mismatch", quote_updates={"price": 11.0})
    blocked("entry-date-mismatch", "stock_entry:entry_date_mismatch", updates={"entry_date": "2024-01-02"})
    blocked("missing-basis", "stock_entry:legacy_quote_evidence_missing", quote_updates={"price_basis": None})
    blocked("future-evidence", "stock_entry:invalid_quote_date_evidence",
            quote_updates={"resolved_date": "2024-01-02"})
    blocked("stale-evidence", "stock_entry:invalid_quote_date_evidence",
            quote_updates={"resolved_date": "2023-12-24"})
    blocked("wrong-ticker", "stock_entry:quote_ticker_mismatch", quote_updates={"ticker": benchmark})
    blocked("boolean-schema", "stock_entry:unsupported_quote_evidence_schema",
            quote_updates={"schema_version": True})
    blocked("unsupported-column", "stock_entry:quote_price_column_missing", quote_updates={"price_column": []})
    blocked("invalid-decision-date", "invalid_verdict_date", updates={"verdict_date": "2024-02-30"})
    blocked("invalid-horizon", "invalid_horizon_months", updates={"horizon_months": float("inf")})

    horizon = {ticker: quote(ticker, 11.0, "2024-01-31"),
               benchmark: quote(benchmark, 20.0, "2024-01-31")}
    score_cases = [{"name": "valid", "row": deepcopy(base_row), "quotes": deepcopy(horizon),
                    "reason": None, "stock_return_pct": 10.0, "realized_excess_pct": 10.0, "brier": 0.25}]
    for symbol, label in ((ticker, "stock"), (benchmark, "benchmark")):
        quotes = deepcopy(horizon)
        quotes[symbol]["price"] = float("nan")
        score_cases.append({"name": f"invalid-{label}-exit", "row": deepcopy(base_row),
                            "quotes": quotes, "reason": f"{label}_snapshot:horizon:invalid_price"})
    overflow_row, overflow_quotes = deepcopy(base_row), deepcopy(horizon)
    overflow_row["entry_price"] = overflow_row["entry_quote"]["price"] = 1e-308
    overflow_quotes[ticker]["price"] = 1e308
    score_cases.append({"name": "nonfinite-return", "row": overflow_row, "quotes": overflow_quotes,
                        "reason": "stock_snapshot:nonfinite_return"})

    flags = {"ticker": ticker, "verdict_date": "2024-01-01", "rating": "买入",
             "confidence": None, "mos_pct": None, "kill_flags": None, "catalyst": None,
             "cik": None, "theme": None, "mos_basis": None}
    legacy_row = deepcopy(base_row)
    legacy_row.pop("entry_quote")
    legacy_row.pop("benchmark_entry_quote")
    missing_row = deepcopy(legacy_row)
    missing_row.update(entry_price=None, benchmark_entry_price=None)
    partial_invalid_row = deepcopy(missing_row)
    partial_invalid_row["entry_price"] = "invalid-synthetic-price"
    scored_row = deepcopy(legacy_row)
    scored_row.update(scored=True, stock_return_pct=10.0, realized_excess_pct=10.0, brier=0.25)
    scored_incomplete_row = deepcopy(scored_row)
    scored_incomplete_row["entry_price"] = None
    return {"ticker": ticker, "benchmark": benchmark, "requested": requested,
            "download_start": "2024-12-29", "download_end": "2025-01-06",
            "provider_cases": provider_cases, "invalid_requested_dates": [None, "2025-02-30", "20250105"],
            "base_row": base_row, "legacy_row": legacy_row, "missing_row": missing_row,
            "partial_invalid_row": partial_invalid_row,
            "scored_row": scored_row, "scored_incomplete_row": scored_incomplete_row,
            "provider_exception": "synthetic-provider-error-message",
            "today": "2024-03-01", "no_fetch": no_fetch,
            "score_cases": score_cases, "flags": flags,
            "record_payload": {"ticker": ticker, "rating": "buy", "verdict_date": "2024-01-01"},
            "entry_quotes": {ticker: quote(ticker, 10.0), benchmark: quote(benchmark, 20.0)},
            "unavailable_quote": {"schema_version": 1, "available": False, "price": None,
                                  "reason": "no_quotes"}}


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
    result = generate()
    result["signals"] = {
        "signals_error": "synthetic_diagnostic_outside_debt_scope",
        "signals_meta": {"diagnostic_only": True, "never_affects_buy": True},
    }
    return result


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
        source26_debt_fixture(data)
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


def report_evidence_scenarios():
    """Generate report inputs with explicit checked, unknown and adverse evidence."""
    from copy import deepcopy

    deep = {
        'ticker': 'SYNTH',
        'tenk': {'available': True, 'has_going_concern': False,
                 'has_material_weakness': False, 'has_death_spiral': False},
        'derived': {'concentration_flag': None, 'fundamental_decline_flag': False,
                    'distress_kill': False},
    }
    valuation = {'ticker': 'SYNTH', 'mos_basis': 'fcf_cap', 'margin_of_safety_pct': 0.30,
                 'data_quality': [], 'buy_eligible': True, 'buy_ineligible_reasons': []}
    cases = {}
    for name in ('no_filing', 'unavailable_filing', 'partial_filing', 'invalid_flag',
                 'no_valuation', 'unchecked_valuation', 'unknown_decline', 'unknown_concentration'):
        item, val = deepcopy(deep), deepcopy(valuation)
        if name == 'no_filing':
            item.pop('tenk')
        elif name == 'unavailable_filing':
            item['tenk']['available'] = False
        elif name == 'partial_filing':
            item['tenk'].pop('has_material_weakness')
        elif name == 'invalid_flag':
            item['tenk']['has_going_concern'] = 'false'
        elif name == 'no_valuation':
            val = {}
        elif name == 'unchecked_valuation':
            val.pop('data_quality')
        elif name == 'unknown_decline':
            item['derived'].pop('fundamental_decline_flag')
        else:
            item['derived'].pop('concentration_flag')
        cases[name] = {'deep': item, 'valuation': val}
    for label, count in [('string', '2'), ('float', 2.0), ('negative', -1), ('boolean', True)]:
        item = deepcopy(deep)
        item['killflag_count'] = count
        cases['invalid_count_' + label] = {'deep': item, 'valuation': deepcopy(valuation)}
    for basis, field in [('fcf_cap', 'margin_of_safety_pct'), ('nav', 'nav_margin_of_safety_pct')]:
        for label, value in [('missing', None), ('nonfinite', float('nan')), ('boolean', True),
                             ('overflow', 1e308)]:
            val = deepcopy(valuation)
            val.update(mos_basis=basis)
            val[field] = value
            cases['invalid_mos_' + basis + '_' + label] = {'deep': deepcopy(deep), 'valuation': val}
    for label, basis in [('list', []), ('mapping', {'synthetic': True})]:
        val = deepcopy(valuation)
        val['mos_basis'] = basis
        cases['invalid_basis_' + label] = {'deep': deepcopy(deep), 'valuation': val}
    for field in ('data_quality', 'buy_ineligible_reasons'):
        for label, value in [('number', 2), ('boolean', True), ('string', 'synthetic'),
                             ('mapping', {'synthetic': True}), ('members', [2]), ('blank', [''])]:
            val = deepcopy(valuation)
            val[field] = value
            cases['invalid_' + field + '_' + label] = {'deep': deepcopy(deep), 'valuation': val}
    return {'deep': deep, 'valuation': valuation, 'unknown': cases, 'date': '2026-01-01'}


def recall_stage_scenarios():
    """Generate discovery channels and downstream outcomes for a synthetic cohort."""
    return {
        'theme': 'synthetic-recall',
        'gold': [' SYNTHA ', 'synthb', 'SYNTHC', 'SYNTHD', 'SYNTHE', 'SYNTHF', 'syntha'],
        'final': [' syntha ', 'SYNTHB'],
        'fts': ['SYNTHA', 'SYNTHD'],
        'sic': ['SYNTHB', 'SYNTHC', 'SYNTHD', 'SYNTHE'],
        'dropped': ['SYNTHC'],
        'gated': ['SYNTHD'],
        'candidate_rows': [
            {'ticker': 'SYNTHA', 'recall_channel': 'fts'},
            {'ticker': 'SYNTHB', 'recall_channel': 'sic_reverse'},
            {'ticker': 'SYNTHC', 'recall_channel': 'sic_reverse', 'dropped_stage': 'mktcap'},
            {'ticker': 'SYNTHD', 'recall_channel': 'both', 'gated_out': True},
        ],
        'universe_rows': [
            {'ticker': 'SYNTHA', 'recall_channel': 'fts', 'smallcap_candidate': 'True'},
            {'ticker': 'SYNTHB', 'recall_channel': 'sic_reverse', 'smallcap_candidate': 'True'},
            {'ticker': 'SYNTHC', 'recall_channel': 'sic_reverse', 'smallcap_candidate': 'False'},
        ],
        'later_gate_rows': [{'ticker': 'SYNTHB', 'recall_channel': 'sic_reverse', 'gated_out': True}],
        'conflicting_gate_rows': [
            {'ticker': 'SYNTHB', 'recall_channel': 'sic_reverse'},
            {'ticker': 'SYNTHB', 'recall_channel': 'sic_reverse', 'gated_out': True},
        ],
    }


def backtest_quote_scenarios():
    """Synthetic prices and dates for holding-period quote and coverage controls."""
    return {
        'ticker': 'SYNTH', 'asof': '2020-06-30', 'target': '2021-06-30',
        'entry': [10.0, '2020-06-30'],
        'stale_rows': [['2020-10-01', 0.08]],
        'selection_rows': [
            ['2021-06-29', 12.0], ['2020-09-01', 2.0],
            ['2021-07-01', 900.0], ['2020-06-29', 900.0],
            ['2021-06-30', 'invalid'], ['not-a-date', 50.0],
        ],
        'invalid_prices': [True, False, 0, -1, float('nan'), float('inf'),
                           -float('inf'), '12.0', None],
        'invalid_quotes': [[], [10], [10, '2021-06-30', 'extra'],
                           {'price': 10}, [10, '2021-02-30'],
                           [10, '2021-6-30'], [10, 'bad']],
        'outside_exit_dates': ['2020-06-29', '2021-07-01'],
        'outside_entry_dates': ['2020-06-01', '2020-07-01'],
        'conflicting_rows': [['2021-06-30', 12.0], ['2021-06-30', 13.0]],
        'large_returns': [1e308, 1e308],
        'entity': {'ticker': 'SYNTH', 'cik': '111', 'name': 'Synthetic Example'},
        'deep': {'tenk': {'filing_date': '2020-03-01'}, 'derived': {}},
        'bucket': {'bucket': 'AVOID', 'mos_basis': 'fcf_cap', 'mos_pct': 40,
                   'buy_eligible': False, 'killflag_count': 1,
                   'buy_ineligible_reasons': ['synthetic_example']},
        'coverage_rows': [
            {'ticker': 'SYNTH_A', 'bucket': 'AVOID', 'total_return': -0.5,
             'return_status': 'ok', 'return_kind': 'observed_close'},
            {'ticker': 'SYNTH_B', 'bucket': 'AVOID', 'total_return': -0.992,
             'return_status': 'ok', 'return_kind': 'stale_quote_proxy'},
            {'ticker': 'SYNTH_C', 'bucket': 'AVOID', 'total_return': None,
             'return_status': 'no_exit_price'},
            {'ticker': 'SYNTH_D', 'bucket': 'AVOID', 'total_return': None,
             'return_status': 'provider_error'},
            {'ticker': 'SYNTH_E', 'bucket': 'AVOID', 'total_return': float('inf'),
             'return_status': 'ok'},
            {'ticker': 'SYNTH_F', 'bucket': 'AVOID', 'total_return': True,
             'return_status': 'ok'},
        ],
    }


def market_cap_basis_scenarios():
    """Synthetic price/share basis evidence; no market observations are used."""
    from copy import deepcopy

    quote = {'price': 25.0, 'date': '2020-06-30', 'basis': 'split_adjusted',
             'basis_date': '2022-06-30', 'basis_timing': 'after_actions',
             'actions': {'start': '2019-01-01', 'end': '2022-06-30', 'complete': True,
                         'splits': [{'date': '2021-06-30', 'ratio': 4.0}]}}
    shares = {'shares': 1000000.0, 'date': '2020-03-31', 'filed': '2020-05-01',
              'basis': 'as_traded', 'basis_date': '2020-03-31',
              'basis_timing': 'after_actions', 'source': 'synthetic_instant_count'}
    chains = []
    for name, actions, price in (
        ('forward', [('2021-06-30', 4)], 25),
        ('reverse', [('2021-06-30', 0.25)], 400),
        ('fractional', [('2021-06-30', 1.5)], 100 / 1.5),
        ('chain', [('2021-01-01', 4), ('2021-06-30', 0.5)], 50),
        ('none', [], 100),
    ):
        q = deepcopy(quote)
        q['price'] = price
        q['actions']['splits'] = [{'date': day, 'ratio': ratio} for day, ratio in actions]
        chains.append({'id': name, 'quote': q, 'shares': deepcopy(shares), 'expected': 100000000.0})
    return {
        'ticker': 'SYNTHA', 'cik': '0000000001', 'asof': '2020-06-30',
        'quote': quote, 'shares': shares, 'chains': chains,
        'invalid_numbers': [True, False, 0, -1, float('nan'), float('inf'), -float('inf'), '5', None],
        'history': [
            ('2020-06-30', {'Close': 25.0, 'Adj Close': 20.0, 'Stock Splits': 0.0, 'Dividends': 0.0}),
            ('2021-06-30', {'Close': 25.0, 'Adj Close': 25.0, 'Stock Splits': 4.0, 'Dividends': 0.0}),
            ('2022-06-30', {'Close': 30.0, 'Adj Close': 30.0, 'Stock Splits': 0.0, 'Dividends': 5.0}),
        ],
        'sec_facts': [
            {'val': 1000000.0, 'end': '2020-03-31', 'filed': '2020-05-01'},
            {'val': 7000000.0, 'end': '2021-03-31', 'filed': '2021-05-01'},
            {'val': 8000000.0, 'end': '2020-03-31', 'filed': '2021-05-01'},
        ],
        'entity': {'ticker': 'SYNTHA', 'cik': '0000000001', 'name': 'AcmeCorp'},
    }


def market_cap_sec_scenarios():
    """Generate raw SEC responses for the strict default market-cap path."""
    from copy import deepcopy

    basis = market_cap_basis_scenarios()
    fact = {'end': '2020-03-31', 'filed': '2020-05-01', 'val': 1250000,
            'form': '10-Q', 'accn': '0000000001-20-000001'}
    names = [('dei', 'EntityCommonStockSharesOutstanding'),
             ('us-gaap', 'CommonStockSharesOutstanding')]

    def response(index, facts=(), *, status=200, unit='shares'):
        taxonomy, concept = names[index]
        return {'status': status, 'body': {
            'cik': 1, 'taxonomy': taxonomy, 'tag': concept,
            'units': {unit: deepcopy(list(facts))}}}

    absent = response(1, status=404)
    conflicting = {**fact, 'val': 1750000}
    revised = {**fact, 'filed': '2020-06-01', 'val': 1500000}
    cases = {
        'valid': [response(0, [fact]), absent],
        'identical': [response(0, [fact, fact]), absent],
        'conflict_forward': [response(0, [fact, conflicting]), absent],
        'conflict_reverse': [response(0, [conflicting, fact]), absent],
        'revised_forward': [response(0, [fact, revised]), absent],
        'revised_reverse': [response(0, [revised, fact]), absent],
        'usd_only': [response(0, [{**fact, 'val': 2}], unit='USD'), absent],
        'unsupported_unit': [response(0, [fact], unit='million_shares'), absent],
        'empty': [response(0), response(1)],
        'missing_concepts': [response(0, status=404), absent],
        'future_only': [response(0, [{**fact, 'filed': '2021-05-01'}]), absent],
        'future_filtered': [response(0, [fact, {**fact, 'val': 9000000, 'filed': '2021-05-01'},
                                        {**fact, 'val': 8000000, 'end': '2021-03-31', 'filed': '2021-05-01'}]), absent],
        'cross_concept_conflict': [response(0, [fact]), response(1, [conflicting])],
    }
    mixed = response(0, [fact])
    mixed['body']['units']['USD'] = [{**fact, 'val': 2}]
    cases['mixed_units'] = [mixed, absent]
    for status in (429, 503):
        cases['http_' + str(status)] = [response(0, status=status), absent]
    cases['partial_http'] = [response(0, status=503), response(1, [fact])]
    for name in ('TimeoutError', 'ConnectionError'):
        cases[name] = [{'exception': name}, absent]
    cases['invalid_json'] = [{'status': 200, 'json_exception': 'ValueError'}, absent]
    cases['invalid_response'] = [{'status': 200, 'body': []}, absent]
    invalid = []
    for value in (True, False, 0, -1, float('nan'), float('inf'), '1250000', None):
        invalid.append([response(0, [{**fact, 'val': value}]), absent])
    for change in ({'filed': 'bad'}, {'end': '2020-02-30'}, {'filed': '2019-01-01'},
                   {'start': '2020-01-01'}):
        invalid.append([response(0, [{**fact, **change}]), absent])
    wrong_identity = response(0, [fact])
    wrong_identity['body']['cik'] = 2
    cases['wrong_issuer'] = [wrong_identity, absent]
    quote = {'price': 80.0, 'date': basis['asof'], 'basis': 'as_traded',
             'basis_date': basis['asof'], 'basis_timing': 'after_actions',
             'actions': {'start': '2019-01-01', 'end': '2020-06-30', 'complete': True, 'splits': []}}
    return {'ticker': basis['ticker'], 'cik': basis['cik'], 'asof': basis['asof'],
            'entity': basis['entity'], 'quote': quote, 'concepts': names, 'cases': cases,
            'invalid_facts': invalid, 'expected_cap': 100000000,
            'revised_cap': 120000000, 'expected_shares': fact['val'],
            'continuation_policy': 'require_all_concept_queries_resolved',
            'basis_responses': [response(0, basis['sec_facts']), response(1, basis['sec_facts'])]}


def stage_completion_scenarios():
    """Generate synthetic completion, coverage-gap and historical-shard inputs."""
    asof = '2001-01-01'
    filed = '2000-12-15'
    ticker = 'SYNTHA'
    cik = '0000000001'
    failed_shard_name = 'CIK0000000001-submissions-001.json'
    hits = [
        {
            '_id': 'synthetic-filing-%03d' % index,
            '_source': {
                'display_names': [
                    'AcmeCorp Synthetic %03d (SYN%03d) (CIK %010d)'
                    % (index, index, index + 1)
                ],
                'file_date': filed,
                'form': '10-12B',
                'root_forms': ['10-12B'],
                'sics': ['3571'],
                'ciks': ['%010d' % (index + 1)],
            },
        }
        for index in range(100)
    ]
    return {
        'empty_rows': [],
        'invalid_universe': {'synthetic_input': 'not-a-list'},
        'fts_empty': {'hits': {'hits': [], 'total': {'value': 0, 'relation': 'eq'}}},
        'fts_malformed': {'synthetic_error': 'missing hits envelope'},
        'fts_capped': {'hits': {'hits': hits, 'total': {'value': 101, 'relation': 'eq'}}},
        'sic_empty_html': '<html><body>No matching companies found</body></html>',
        'sic_unknown_html': '<html><body>Synthetic verification required.</body></html>',
        'asof': asof,
        'cik': cik,
        'current_tickers': [ticker],
        'symbol_fact': {'cik': 1, 'taxonomy': 'dei', 'tag': 'TradingSymbol',
                        'units': {'pure': [{'val': ticker, 'filed': filed}]}},
        'submissions': {
            'cik': cik,
            'name': 'AcmeCorp Synthetic',
            'tickers': [ticker],
            'filings': {
                'recent': {'form': ['10-K'], 'filingDate': [filed]},
                'files': [{'name': failed_shard_name}],
            },
        },
        'failed_shard_name': failed_shard_name,
    }


def downstream_completion_scenarios():
    """Invented downstream completion inputs and finalizer selftest cases."""
    return {'asof': '2001-01-01',
            'candidates': [{'ticker': 'SYNTHA',
                            'cik': '9000000001',
                            'band': 'deep',
                            'name': 'Synthetic Alpha',
                            'theme': 'synthetic machinery',
                            'theme_slug': 'synthetic',
                            'sic': '3500'},
                           {'ticker': 'SYNTHB',
                            'cik': '9000000002',
                            'band': 'watch',
                            'name': 'Synthetic Beta',
                            'theme': 'synthetic machinery',
                            'theme_slug': 'synthetic',
                            'sic': '3500'}],
            'judgments': [{'input_index': 0,
                           'ticker': 'SYNTHA',
                           'cik': '9000000001',
                           'band': 'deep',
                           'judgment_status': 'complete',
                           'theme_fit': 'pure_play',
                           'reason': 'Synthetic fixture',
                           'real_business': 'Synthetic machinery'},
                          {'input_index': 1,
                           'ticker': 'SYNTHB',
                           'cik': '9000000002',
                           'band': 'watch',
                           'judgment_status': 'complete',
                           'theme_fit': 'misrecall',
                           'reason': 'Synthetic fixture',
                           'real_business': 'Synthetic unrelated goods'}],
            'errors': [{'input_index': 0,
                        'ticker': 'SYNTHA',
                        'cik': '9000000001',
                        'band': 'deep',
                        'judgment_status': 'error',
                        'error_code': 'agent_failed'}],
            'unknown_band': 'unknown',
            'invalid_boolean': 'maybe',
            'report_text': '# SYNTHA 2001-01-01\n'
                           '\n'
                           '```rating\n'
                           'verdict_date: 2001-01-01\n'
                           'rating: 观察\n'
                           'confidence: 50\n'
                           'mos_basis: abstain\n'
                           'mos_pct: null\n'
                           'buy_eligible: false\n'
                           'killflag_count: 0\n'
                           'concentration_flag: null\n'
                           'fundamental_decline_flag: false\n'
                           '```\n',
            'selftest': {'parse_report': '# SYNTHA 2001-01-01\n'
                                         '\n'
                                         '```rating\n'
                                         'verdict_date: 2001-01-01\n'
                                         'rating: BUY  # synthetic fixture\n'
                                         'confidence: 65\n'
                                         'mos_basis: fcf_cap\n'
                                         'mos_pct: 42.0\n'
                                         'buy_eligible: true\n'
                                         'killflag_count: 0\n'
                                         'concentration_flag: null\n'
                                         'fundamental_decline_flag: false\n'
                                         '```\n',
                         'risk_report': '# SYNTHA 2001-01-01\n'
                                        '\n'
                                        '```rating\n'
                                        'verdict_date: 2001-01-01\n'
                                        'rating: AVOID\n'
                                        'confidence: 55\n'
                                        'mos_basis: fcf_cap\n'
                                        'mos_pct: 76.0\n'
                                        'buy_eligible: false\n'
                                        'killflag_count: 1\n'
                                        'concentration_flag: kill\n'
                                        'fundamental_decline_flag: true\n'
                                        '```\n',
                         'risk_deep': {'ticker': 'SYNTHA',
                                       'cik': '9000000001',
                                       'theme': 'synthetic',
                                       'derived': {'concentration_flag': 'kill',
                                                   'fundamental_decline_flag': True},
                                       'tenk': {'has_going_concern': False,
                                                'has_material_weakness': False,
                                                'has_death_spiral': False},
                                       'valuation': {'margin_of_safety_pct': 76.0,
                                                     'mos_basis': 'fcf_cap'}},
                         'private_origin': 'https://github.com/example/synthetic-smallcap-config.git',
                         'private_identity': 'example/synthetic-smallcap-config',
                         'run_name': 'synthetic-run',
                         'keep_payload': {'keep': True},
                         'parse_cases': {'english': '```rating\nrating: BUY\n```',
                                         'unset': '```rating\nrating: TBD\n```',
                                         'missing': 'no fence here',
                                         'false': '```rating\nbuy_eligible: false\n```'}}}


def ranking_recall_completion_scenarios():
    """Invented ranking inputs paired with the existing synthetic recall cohort."""
    return {'ticker': 'SYNTHA',
            'cik': '0000000001',
            'name': 'AcmeCorp Synthetic',
            'asof': '2001-01-01',
            'report_text': '# SYNTHA 2001-01-01\n'
                           '\n'
                           '```rating\n'
                           'verdict_date: 2001-01-01\n'
                           'rating: 观察\n'
                           'confidence: 60\n'
                           'mos_basis: abstain\n'
                           'mos_pct: null\n'
                           'buy_eligible: false\n'
                           'killflag_count: 0\n'
                           'concentration_flag: null\n'
                           'fundamental_decline_flag: false\n'
                           '```\n',
            'hard_data': {'derived': {'latest_revenue': 1000000.0,
                                      'latest_net_income': 100000.0,
                                      'latest_ocf': 150000.0},
                          'tenk': {},
                          'insider': {}},
            'candidate_artifact': 'candidates_synthetic.json',
            'ranking_output': 'RANKING.next.md',
            'prior_ranking': 'synthetic prior ranking\n',
            'recall': recall_stage_scenarios()}


def downstream_producer_completion_scenarios():
    """Invented producer inputs with original indices and independent mutable cases."""
    candidates = [
        {"ticker": "SYNTHA", "cik": "9000000001", "band": "deep",
         "name": "AcmeCorp Synthetic Alpha", "theme": "synthetic machinery",
         "theme_slug": "synthetic", "horizon": "synthetic horizon",
         "mktcap": 100000000, "health_score": 60, "killflag_count": 0},
        {"ticker": "SYNTHB", "cik": "9000000002", "band": "deep",
         "name": "AcmeCorp Synthetic Beta", "theme": "synthetic machinery",
         "theme_slug": "synthetic", "horizon": "synthetic horizon",
         "mktcap": 120000000, "health_score": 65, "killflag_count": 0},
    ]
    survivor_rows = [
        {**candidates[0], "input_index": 1, "judgment_status": "complete",
         "theme_fit": "pure_play", "reason": "Synthetic fixture",
         "real_business": "Synthetic machinery"},
        {**candidates[1], "input_index": 3, "judgment_status": "complete",
         "theme_fit": "partial", "reason": "Synthetic fixture",
         "real_business": "Synthetic components"},
    ]
    original_candidates = [
        {**candidates[0], "ticker": "SYNTHR1", "cik": "9000000003",
         "name": "AcmeCorp Synthetic Reject One"},
        candidates[0],
        {**candidates[1], "ticker": "SYNTHR2", "cik": "9000000004",
         "name": "AcmeCorp Synthetic Reject Two"},
        candidates[1],
    ]
    gate2_outcomes = [
        {**original_candidates[0], "input_index": 0, "judgment_status": "complete",
         "theme_fit": "misrecall", "reason": "Synthetic fixture",
         "real_business": "Synthetic unrelated goods"},
        survivor_rows[0],
        {**original_candidates[2], "input_index": 2, "judgment_status": "complete",
         "theme_fit": "misrecall", "reason": "Synthetic fixture",
         "real_business": "Synthetic unrelated services"},
        survivor_rows[1],
    ]
    identity_keys = ("input_index", "ticker", "cik", "band")
    identities = [{key: row[key] for key in identity_keys} for row in survivor_rows]
    reports = []
    # The deliberately incomplete annual inputs use 80% of book equity as the NAV proxy.
    nav_mos_pct = round(round(0.8 * 1_540_000 / 100_000_000 - 1, 4) * 100, 2)
    for row in survivor_rows:
        report_md = (
            f"# {row['ticker']} 2001-01-01\n\n"
            "```rating\n"
            "rating: \u89c2\u5bdf\n"
            "confidence: 55\n"
            "verdict_date: 2001-01-01\n"
            "mos_basis: nav\n"
            f"mos_pct: {nav_mos_pct}\n"
            "buy_eligible: false\n"
            "killflag_count: 0\n"
            "```\n"
        )
        reports.append({
            "ticker": row["ticker"], "rating": "\u89c2\u5bdf", "confidence": 55,
            "one_liner": "Synthetic evidence supports continued observation.",
            "is_misrecall": False, "theme_fit": row["theme_fit"],
            "top_long": "Synthetic recurring sales can improve after a measured cost change.",
            "top_short": "Synthetic customer concentration can offset that improvement.",
            "killflag_notes": "Synthetic fixture has no asserted kill flags.",
            "margin_of_safety_pct": None, "mos_basis": "nav",
            "catalyst": None, "report_md": report_md,
            "eligibility": {"buy_eligible": False, "active_mos_pct": nav_mos_pct,
                            "tier3_load_bearing": False},
        })
    success = [
        {**identity, "report_status": "complete", "report": report}
        for identity, report in zip(identities, reports)
    ]
    pull_data = {
        "ticker": candidates[0]["ticker"], "cik": candidates[0]["cik"],
        "pulled_at": "2001-01-01T00:00:00+00:00",
        "financials": {
            name: [
                {"end": "1999-09-30", "filed": "1999-12-31", "val": values[0]},
                {"end": "2000-09-30", "filed": "2000-12-31", "val": values[1]},
            ]
            for name, values in {
                "revenue": (1000000.0, 1100000.0),
                "net_income": (100000.0, 110000.0),
                "ocf": (150000.0, 165000.0),
                "cash": (250000.0, 275000.0),
                "shares_outstanding": (1000000.0, 1000000.0),
                "assets": (2000000.0, 2200000.0),
                "equity": (1400000.0, 1540000.0),
                "total_debt": (300000.0, 330000.0),
                "ebit": (125000.0, 137500.0),
                "dep_amort": (25000.0, 27500.0),
                "capex": (50000.0, 55000.0),
                "goodwill": (100000.0, 110000.0),
                "intangibles": (50000.0, 55000.0),
                "liabilities": (600000.0, 660000.0),
            }.items()
        },
        "derived": {
            "latest_revenue": 1100000.0, "latest_net_income": 110000.0,
            "latest_ocf": 165000.0, "latest_cash": 275000.0,
            "revenue_growth_pct": 10.0, "shares_growth_pct": 0.0,
            "runway_periods": None, "ocf_ni_divergence": False,
        },
        "tenk": {
            "available": True, "filing_form": "10-K", "filing_date": "2000-12-31",
            "has_going_concern": False, "has_material_weakness": False,
            "has_death_spiral": False, "customer_concentration_flag": None,
        },
        "insider": {"available": True, "net_signal": "neutral", "buys": 0, "sells": 0},
        "signals": {
            "signals_error": None,
            "signals_meta": {"diagnostic_only": True, "never_affects_buy": True},
        },
    }
    malformed_rows = {
        "nonobject": None,
        "missing_ticker": {key: value for key, value in survivor_rows[0].items()
                           if key != "ticker"},
        "null_ticker": {**survivor_rows[0], "ticker": None},
        "nonstring_ticker": {**survivor_rows[0], "ticker": 7},
        "empty_ticker": {**survivor_rows[0], "ticker": ""},
        "path_ticker": {**survivor_rows[0], "ticker": "../SYNTHA"},
        "missing_cik": {key: value for key, value in survivor_rows[0].items()
                        if key != "cik"},
        "null_cik": {**survivor_rows[0], "cik": None},
        "invalid_cik": {**survivor_rows[0], "cik": "synthetic-not-a-cik"},
        "missing_band": {key: value for key, value in survivor_rows[0].items()
                         if key != "band"},
        "invalid_band": {**survivor_rows[0], "band": "unrecognized"},
        "list_band": {**survivor_rows[0], "band": []},
        "object_band": {**survivor_rows[0], "band": {}},
        "malformed_watch": {**survivor_rows[0], "band": "watch", "ticker": None},
        "malformed_large": {**survivor_rows[0], "band": "large", "cik": None},
    }
    cases = {
        "candidates": candidates,
        "original_candidates": original_candidates,
        "gate2_outcomes": gate2_outcomes,
        "survivor_rows": survivor_rows,
        "empty": [],
        "verdict_date": "2001-01-01",
        "malformed_rows": malformed_rows,
        "skipped_rows": [
            {**survivor_rows[0], "band": "watch"},
            {**survivor_rows[1], "band": "large"},
        ],
        "pull_data": pull_data,
        "pull_data_incomplete": {
            **pull_data, "financials": {}, "derived": {},
            "tenk": {"available": False, "error": "synthetic_filing_unavailable"},
            "insider": {"available": False, "note": "synthetic_insider_unavailable"},
            "signals": {
                "signals_error": "synthetic_diagnostic_unavailable",
                "signals_meta": {"diagnostic_only": True, "never_affects_buy": True},
            },
        },
        "pull_errors": [{"ticker": candidates[0]["ticker"], "cik": candidates[0]["cik"],
                         "error_code": "synthetic_pull_failed"}],
        "nonempty_pull_completion": {
            "status": "partial", "reason": "financial_source_completion_unobserved",
        },
        "fanout_outcomes": {
            "success": success,
            **{
                name: [
                    {**success[0], "report": {
                        **reports[0],
                        "report_md": reports[0]["report_md"].replace(
                            "killflag_count: 0\n", f"killflag_count: {count}\n"),
                    }},
                    success[1],
                ]
                for name, count in (
                    ("killflag_safe_max", str(2 ** 53 - 1)),
                    ("killflag_unsafe_integer", str(2 ** 53)),
                    ("killflag_overflow", "9" * 400),
                )
            },
            "error": [
                {**identities[0], "report_status": "error", "error_code": "agent_failed"},
                success[1],
            ],
            "missing": [success[0]],
            "duplicate": [success[0], success[0], success[1]],
            "mismatched_identity": [
                {**success[0], "ticker": candidates[1]["ticker"]}, success[1],
            ],
            "mismatched_original_index": [
                {**success[0], "input_index": 0}, success[1],
            ],
            "mismatched_report_ticker": [
                {**success[0], "report": {**reports[0], "ticker": candidates[1]["ticker"]}},
                success[1],
            ],
            "empty": [],
        },
    }
    # Expand shared templates into independent JSON-shaped cases before callers mutate them.
    cases["source22_policy"] = source22_scenarios()["policy"]
    return json.loads(json.dumps(cases))


def upstream_completion_scenarios():
    """Invented SEC envelopes, transport descriptors and SIC HTML; no I/O."""
    query = {"cik": "1", "concept": "Revenues", "taxonomy": "us-gaap",
             "asof": "2001-04-01"}
    annual = {
        "start": "2000-01-01", "end": "2000-12-31", "filed": "2001-03-01",
        "val": 1000000.0, "fy": 2000, "fp": "FY", "form": "10-K",
    }
    quarterly = {**annual, "start": "2000-10-01", "filed": "2001-02-01",
                 "val": 250000.0, "fp": "Q4"}
    future = {**annual, "filed": "2001-05-01", "val": 1250000.0}
    restated = {**annual, "filed": "2001-03-15", "val": 1100000.0}

    def envelope(facts, tag="Revenues"):
        return {
            "cik": 1, "taxonomy": "us-gaap", "tag": tag,
            "entityName": "AcmeCorp Synthetic",
            "label": "Synthetic " + tag,
            "description": "Invented SEC companyconcept fixture.",
            "units": {"USD": facts},
        }

    baseline = envelope([annual])
    concept_envelopes = {
        "annual": baseline,
        "instant_assets": envelope([
            {"end": "2000-12-31", "filed": "2001-03-01", "val": 2000000.0,
             "fy": 2000, "fp": "FY", "form": "10-K"},
        ], tag="Assets"),
        "complete_empty": envelope([]),
        "quarterly_only": envelope([quarterly]),
        "future_only": envelope([future]),
        "mixed": envelope([quarterly, annual, future]),
        "restatement": envelope([annual, restated]),
        "reversed_restatement": envelope([restated, annual]),
        "nonobject": None,
        "mismatched_cik": {**baseline, "cik": 2},
        "mismatched_taxonomy": {**baseline, "taxonomy": "ifrs-full"},
        "mismatched_tag": {**baseline, "tag": "Assets"},
        "mismatched_cik_empty": {**envelope([]), "cik": 2},
        "mismatched_taxonomy_empty": {**envelope([]), "taxonomy": "ifrs-full"},
        "mismatched_tag_empty": {**envelope([]), "tag": "Assets"},
        "missing_cik": {key: value for key, value in baseline.items() if key != "cik"},
        "missing_taxonomy": {key: value for key, value in baseline.items()
                             if key != "taxonomy"},
        "missing_tag": {key: value for key, value in baseline.items() if key != "tag"},
        "missing_units": {key: value for key, value in baseline.items() if key != "units"},
        "empty_units": {**baseline, "units": {}},
        "units_not_object": {**baseline, "units": []},
        "unsupported_nonempty_units": {**baseline, "units": {"EUR": [annual]}},
        "facts_not_list": {**baseline, "units": {"USD": {"synthetic": "not a list"}}},
        "nonobject_fact": envelope(["synthetic malformed fact"]),
        "bool_val": envelope([{**annual, "val": True}]),
        "string_val": envelope([{**annual, "val": "1000000.0"}]),
        "missing_val": envelope([
            {key: value for key, value in annual.items() if key != "val"},
        ]),
        "missing_start": envelope([
            {key: value for key, value in annual.items() if key != "start"},
        ]),
        "invalid_start": envelope([{**annual, "start": "2000-13-01"}]),
        "missing_end": envelope([
            {key: value for key, value in annual.items() if key != "end"},
        ]),
        "invalid_end": envelope([{**annual, "end": "not-a-date"}]),
        "missing_filed": envelope([
            {key: value for key, value in annual.items() if key != "filed"},
        ]),
        "invalid_filed": envelope([{**annual, "filed": "2001-02-30"}]),
        "mixed_malformed": envelope([annual, {**annual, "val": "invalid"}]),
    }
    http_cases = {
        "ok": {"status_code": 200, "json": baseline},
        "observed_empty": {"status_code": 200, "json": envelope([])},
        "rate_limited": {"status_code": 429, "text": "Synthetic rate limit"},
        "server_error": {"status_code": 500, "text": "Synthetic server error"},
        "timeout": {"exception_type": "TimeoutError", "message": "Synthetic timeout"},
    }
    company_rows = [
        {"cik": "1", "name": "AcmeCorp Synthetic Alpha"},
        {"cik": "2", "name": "AcmeCorp Synthetic Beta"},
        {"cik": "3", "name": "AcmeCorp Synthetic Gamma"},
    ]
    row_html = []
    for row in company_rows:
        cik = row["cik"].zfill(10)
        row_html.append(
            '<tr class="company"><td><a href="/cgi-bin/browse-edgar?'
            f'action=getcompany&amp;CIK={cik}&amp;owner=include">'
            f'{cik}</a></td><td>{row["name"]}</td><td>DE</td></tr>'
        )

    def table(rows, extra=""):
        return (
            "<html><body><h1>Company Search Results</h1>"
            '<table class="tableFile2" summary="Company Search Results">'
            "<caption>Companies matching SIC 3500</caption>"
            '<tr><th scope="col">CIK</th><th scope="col">Company</th>'
            '<th scope="col">State/Country</th></tr>'
            + "".join(rows) + "</table>" + extra + "</body></html>"
        )

    malformed_cik_row = (
        '<tr class="company"><td><a href="/cgi-bin/browse-edgar?'
        'action=getcompany&amp;CIK=invalid&amp;owner=include">invalid</a></td>'
        "<td>AcmeCorp Synthetic Broken Identity</td><td>DE</td></tr>"
    )
    missing_name_row = (
        '<tr class="company"><td><a href="/cgi-bin/browse-edgar?'
        'action=getcompany&amp;CIK=0000000004&amp;owner=include">0000000004</a></td>'
        "<td></td><td>DE</td></tr>"
    )
    challenge = "<h1>Request Rate Threshold Exceeded</h1><p>Synthetic access challenge</p>"
    html_cases = {
        "normal_short": table(row_html[:2]),
        "terminal_short": table(row_html[2:]),
        "full_duplicates": table([row_html[0], row_html[0], row_html[1]]),
        "partially_malformed": table([row_html[0], malformed_cik_row, row_html[1]]),
        "all_malformed": table([malformed_cik_row, missing_name_row]),
        "explicit_zero": table([], "<p>No matching companies found</p>"),
        "challenge": "<html><body>" + challenge + "</body></html>",
        "zero_with_challenge": table([], "<p>No matching companies found</p>" + challenge),
        "unrecognized_empty": "<html><body><p>Synthetic unrelated page</p></body></html>",
    }
    cases = {
        "query": query,
        "query_variants": {
            "whitespace_cik": {**query, "cik": " " + query["cik"] + " "},
        },
        "concept_envelopes": concept_envelopes,
        "http_cases": http_cases,
        "submissions": {
            "valid": {"cik": int(query["cik"]), "sic": "3500"},
            "explicit_empty": {"cik": int(query["cik"]), "sic": ""},
            "missing_sic": {"cik": int(query["cik"])},
            "mismatched_cik": {"cik": int(query["cik"]) + 1, "sic": "3500"},
            "malformed_sic": {"cik": int(query["cik"]), "sic": "synthetic-not-a-sic"},
            "nonobject": None,
        },
        "sic": {
            "code": "3500", "forms": "10-K", "page_size": 3, "max_pages": 3,
            "rows": company_rows, "html_cases": html_cases,
            "raw_row_counts": {
                "normal_short": 2, "terminal_short": 1, "full_duplicates": 3,
                "partially_malformed": 3, "all_malformed": 2, "explicit_zero": 0,
                "challenge": 0, "zero_with_challenge": 0, "unrecognized_empty": 0,
            },
            "pagination": {
                "full_duplicates_then_short": [
                    html_cases["full_duplicates"], html_cases["terminal_short"],
                ],
                "repeated_full_page": [
                    html_cases["full_duplicates"], html_cases["full_duplicates"],
                ],
                "malformed_then_short": [
                    html_cases["partially_malformed"], html_cases["terminal_short"],
                ],
            },
        },
    }
    # Keep each returned case independent when a test mutates its JSON data.
    return json.loads(json.dumps(cases))


def deepdive_selftest_concept_scenarios():
    """Identity-bearing envelopes for the retained synthetic point-in-time selftests."""
    payloads = {
        'pit': {'units': {'USD': [{'start': '2022-01-01', 'end': '2022-12-31', 'val': 100, 'fy': 2022, 'fp': 'FY', 'form': '10-K', 'filed': '2023-03-01'}, {'start': '2022-01-01', 'end': '2022-12-31', 'val': 110, 'fy': 2022, 'fp': 'FY', 'form': '10-K/A', 'filed': '2024-03-01'}, {'start': '2023-01-01', 'end': '2023-12-31', 'val': 200, 'fy': 2023, 'fp': 'FY', 'form': '10-K', 'filed': '2024-03-01'}, {'start': '2024-01-01', 'end': '2024-12-31', 'val': 300, 'fy': 2024, 'fp': 'FY', 'form': '10-K', 'filed': '2025-03-01'}]}},
        'undated': {'units': {'USD': [{'start': '2023-01-01', 'end': '2023-12-31', 'val': 500, 'fy': 2023, 'fp': 'FY', 'form': '10-K'}]}},
        'restatement': {'units': {'USD': [{'end': '2014-12-31', 'val': 1000, 'fy': 2014, 'filed': '2015-03-06'}, {'end': '2014-12-31', 'val': 900, 'fy': 2014, 'filed': '2016-03-04'}]}},
        'revenues': {'units': {'USD': [{'start': '2022-01-01', 'end': '2022-12-31', 'val': 100, 'fy': 2022, 'fp': 'FY', 'form': '10-K', 'filed': '2023-03-01'}, {'start': '2022-01-01', 'end': '2022-12-31', 'val': 110, 'fy': 2022, 'fp': 'FY', 'form': '10-K/A', 'filed': '2024-03-01'}, {'start': '2023-01-01', 'end': '2023-12-31', 'val': 200, 'fy': 2023, 'fp': 'FY', 'form': '10-K', 'filed': '2024-03-15'}, {'start': '2024-01-01', 'end': '2024-12-31', 'val': 300, 'fy': 2024, 'fp': 'FY', 'form': '10-K', 'filed': '2025-03-01'}]}},
        'assets': {'units': {'USD': [{'end': '2022-12-31', 'val': 5000, 'fy': 2022, 'filed': '2023-04-10'}, {'end': '2023-12-31', 'val': 5200, 'fy': 2023, 'filed': '2024-04-10'}]}},
        'empty': {'units': {'USD': []}},
    }
    return {
        name: {
            "cik": 1, "taxonomy": "us-gaap",
            "tag": "Assets" if name in {"restatement", "assets"} else "Revenues",
            **payload,
        }
        for name, payload in payloads.items()
    }


def full_review_scenarios():
    """Synthetic observations for the five integrated-a03 review regressions."""
    point = {"end": "2023-12-31", "val": 100}
    feature = {"ticker": "SYNTHA", "cik": "1", "asof": "2024-06-30",
               "series": {"cash": [point]}}
    facts = {"CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
        {**point, "filed": "2024-03-01"}]}}}
    name = {"ticker": "SYNTHA", "cik": "1", "name": "AcmeCorp",
            "sic": "3500", "mktcap": 800_000_000, "price": 10,
            "smallcap_candidate": True, "band": "watch"}
    oos_features = [
        {**feature, "ticker": f"SYNTHOOS{index}", "year": year, "theme": "synthetic",
         "status": "ok", "entry": 10, "total_return": -0.5 if blow else 0.1, "blow": blow,
         "series": {key: [{**point, "val": value}] for key, value in {
             "cash": 10, "ocf": -20 if blow else 20, "assets": 100, "liab": 90,
             "equity": -10 if blow else 50, "curassets": 30, "curliab": 20,
             "retearn": -5 if blow else 15, "ebit": -5 if blow else 10, "shares": 10,
         }.items()}}
        for index, (year, blow) in enumerate([
            ("2020", False), ("2021", True), ("2023", False), ("2024", True)
        ])
    ]
    return {
        "asof": feature["asof"], "theme": "synthetic", "slug": "synthetic",
        "feature": feature, "facts": facts, "oos_features": oos_features,
        "empty_features": [[], [{"series": {}}], [{**feature, "series": {}}],
                           [{**feature, "series": {"cash": []}}]],
        "invalid_features": [{**feature, "series": {"cash": [{"end": point["end"], "val": None}]}}],
        "panel": {"theme": "synthetic", "asof": feature["asof"],
                  "benchmark": {"total_return": 0.05}, "names": [
                      {"ticker": name["ticker"], "cik": name["cik"],
                       "total_return": -0.5, "mos_pct": 20,
                       "forward_return": {"status": "ok", "entry_price": 10}}]},
        "universe": [name, {**name, "ticker": "SYNTHB", "cik": "2", "name": "AcmeCorp Two"}],
        "config": {"python_cmd": "python", "micro_cap_max": 300_000_000,
                   "market_cap_max": 2_000_000_000, "watch_band_max": 5_000_000_000,
                   "sic_hard_exclude": []},
        "health": {"kf_scanned": True, "disclosure_review_required": False,
                   "cash": 100, "net_income": 10, "ocf_latest": 10, "revenue": 100,
                   "health_score": 100, "killflag_count": 0, "avg_dollar_vol": 1_000_000,
                   "business_blurb": "AcmeCorp makes synthetic machinery.", "rejected": False},
        "processed": {"bucket": "WATCH", "total_return": None,
                      "filing_dates": ["2024-03-01"],
                      "forward_return": {"status": "no_exit_price"}},
        "benchmark": {"benchmark": "SYNTHBM", "status": "no_exit_price", "total_return": None},
        "quote": tracking_quote_scenarios(),
        "sentinel": "synthetic public sentinel",
    }


def full_review_regression_source():
    """Reproducible author regression source; runtime is separately admitted."""
    return r'''"""Generated by tools/make_fixtures.py; all observations and identities are synthetic."""
from copy import deepcopy
import importlib
import json
import runpy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_private_runs import state
from test_tracking_integrity import tracker
from make_fixtures import full_review_scenarios

CASE = full_review_scenarios()


@pytest.fixture
def research(state, monkeypatch):
    directory = Path(__file__).resolve().parents[2] / "docs" / "backtest-2026-06"
    monkeypatch.syspath_prepend(str(directory))
    names = ("distress_features_extract", "distress_features_fast",
             "distress_oos_validate", "distress_oos_validate2")
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return tuple(importlib.import_module(name) for name in names)


def _synthetic_pull(row):
    return {**row, "series": deepcopy(CASE["feature"]["series"])}


@pytest.mark.parametrize("extractor", [0, 1])
def test_extractors_use_current_private_backtest_writer(research, state, monkeypatch, extractor):
    trusted, fast, older, newer = research
    backtest = importlib.import_module("backtest")
    cell = backtest._write_cell(deepcopy(CASE["panel"]))
    module = research[extractor]
    monkeypatch.setattr(module, "pull_one", _synthetic_pull)
    (module.main if extractor == 0 else module.run)()
    destination = Path(state["root"]) / "backtest-research" / "distress_features.json"
    assert trusted.features_path() == destination
    assert trusted.backtest_files() == [cell]
    rows = trusted.load_features()
    assert len(rows) == 1
    assert rows[0]["ticker"] == CASE["panel"]["names"][0]["ticker"]
    assert rows[0]["series"] == CASE["feature"]["series"]
    assert older.load_features() == rows
    calls = []
    monkeypatch.setattr(older, "load_features", lambda: calls.append(destination) or [])
    assert newer.load() == ([], 0, 0)
    assert calls == [destination]


@pytest.mark.parametrize("populated", [False, True])
def test_older_oos_cli_reads_current_private_artifact(research, state, monkeypatch, capsys, populated):
    trusted, _, older, _ = research
    destination = Path(state["root"]) / "backtest-research" / "distress_features.json"
    if populated:
        trusted.write_features(deepcopy(CASE["oos_features"]))
    else:
        assert not destination.exists()
    script = str(Path(older.__file__))
    monkeypatch.setattr(sys, "argv", [script])
    runpy.run_path(script, run_name="__main__")
    output = capsys.readouterr().out
    assert trusted.features_path() == destination
    if populated:
        assert "non-financial priceable w/ core fundamentals: n=4  blowups=2" in output
        assert "OOS AUC TEST=" in output
        assert "logistic step skipped:" not in output
        assert trusted.load_features() == CASE["oos_features"]
    else:
        assert "features file not ready: " + str(destination) in output
        assert not destination.exists()


@pytest.mark.parametrize("extractor", [0, 1])
@pytest.mark.parametrize("visibility", ["PUBLIC", None])
def test_unproved_research_destination_preserves_public_sentinel(
        research, state, monkeypatch, tmp_path, extractor, visibility):
    public = tmp_path / "synthetic public source"
    (public / ".git").mkdir(parents=True)
    sentinel = public / "docs" / "backtest-2026-06" / "distress_features.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text(CASE["sentinel"], encoding="utf-8")
    state["origins"][str(public)] = "https://github.com/example/synthetic-public.git"
    state["visibility"]["example/synthetic-public"] = visibility
    monkeypatch.setattr(research[0], "output_root", lambda: public / "reports" / "smallcap")
    monkeypatch.setattr(research[extractor], "ROOT", str(public))
    with pytest.raises(RuntimeError, match="PRIVATE|PUBLIC|visibility|verification"):
        (research[extractor].main if extractor == 0 else research[extractor].run)()
    assert sentinel.read_text(encoding="utf-8") == CASE["sentinel"]
    assert not (public / "reports").exists()


@pytest.mark.parametrize("extractor", [0, 1])
def test_uninitialized_research_writer_fails_before_pull(research, state, monkeypatch, extractor):
    from _common import ConfigNotInitialized

    (Path(state["companion"]) / "config.json").unlink()
    monkeypatch.setattr(research[extractor], "pull_one",
                        lambda *_: pytest.fail("uninitialized writer reached external work"))
    with pytest.raises(ConfigNotInitialized, match="UNINITIALIZED"):
        (research[extractor].main if extractor == 0 else research[extractor].run)()
    assert not Path(state["root"]).exists()


def test_each_research_checkpoint_reproves_destination(research, state):
    trusted = research[0]
    trusted.write_features([CASE["feature"]])
    destination = trusted.features_path()
    before = destination.read_bytes()
    state["visibility"]["example/synthetic-smallcap-config"] = "PUBLIC"
    with pytest.raises(RuntimeError, match="PRIVATE|PUBLIC"):
        trusted.write_features([])
    assert destination.read_bytes() == before


@pytest.mark.parametrize("rows", CASE["empty_features"])
def test_validation_empty_or_unusable_evidence_exits_nonzero(research, monkeypatch, rows, capsys):
    fast = research[1]
    monkeypatch.setattr(fast, "load_features", lambda: deepcopy(rows))
    monkeypatch.setattr(fast, "get_facts", lambda _: {})
    assert fast._cli(["validate"]) == 1
    output = capsys.readouterr().out
    assert "VALIDATION FAIL" in output and "0 nonempty comparisons" in output


def test_validation_missing_artifact_exits_nonzero(research, monkeypatch):
    def missing():
        raise FileNotFoundError("synthetic missing artifact")

    monkeypatch.setattr(research[1], "load_features", missing)
    assert research[1]._cli(["validate"]) == 1


@pytest.mark.parametrize("kind", ["match", "mismatch", "fetch_failure", "invalid"])
def test_validation_requires_observed_matching_values(research, monkeypatch, kind, capsys):
    fast = research[1]
    rows = CASE["invalid_features"] if kind == "invalid" else [CASE["feature"]]
    facts = deepcopy(CASE["facts"])
    if kind == "mismatch":
        facts["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"][0]["val"] += 1
    if kind == "fetch_failure":
        facts = {}
    monkeypatch.setattr(fast, "load_features", lambda: deepcopy(rows))
    monkeypatch.setattr(fast, "get_facts", lambda _: facts)
    assert fast._cli(["validate"]) == (0 if kind == "match" else 1)
    output = capsys.readouterr().out
    assert ("VALIDATION PASS" in output) is (kind == "match")
    if kind == "match":
        assert "1 nonempty comparisons" in output


def test_snapshot_commit_preserves_concurrent_append(tracker):
    first = deepcopy(CASE["quote"]["base_row"])
    second = {**first, "ticker": "SYNTHB"}
    tracker._save_verdicts([first])
    snapshot = tracker._load_verdicts()
    assert tracker._append_verdict(second) is True
    before = tracker.VERDICTS_FILE.read_bytes()
    snapshot[0]["scored"] = True
    with pytest.raises(RuntimeError, match="changed.*retry"):
        tracker._save_verdicts(snapshot)
    assert tracker.VERDICTS_FILE.read_bytes() == before
    assert tracker._load_verdicts() == [first, second]


def test_two_snapshot_updates_cannot_overwrite_each_other(tracker):
    tracker._save_verdicts([deepcopy(CASE["quote"]["base_row"])])
    first, second = tracker._load_verdicts(), tracker._load_verdicts()
    first[0]["score_unavailable_reason"] = "synthetic_first_update"
    second[0]["score_unavailable_reason"] = "synthetic_second_update"
    tracker._save_verdicts(first)
    before = tracker.VERDICTS_FILE.read_bytes()
    with pytest.raises(RuntimeError, match="changed.*retry"):
        tracker._save_verdicts(second)
    assert tracker.VERDICTS_FILE.read_bytes() == before
    assert tracker._load_verdicts() == first


def test_plain_list_cannot_overwrite_an_existing_ledger(tracker):
    tracker._save_verdicts([deepcopy(CASE["quote"]["base_row"])])
    before = tracker.VERDICTS_FILE.read_bytes()
    with pytest.raises(RuntimeError, match="snapshot"):
        tracker._save_verdicts([])
    assert tracker.VERDICTS_FILE.read_bytes() == before


def test_all_ledger_writers_share_exclusive_lock_and_retry(tracker):
    row = deepcopy(CASE["quote"]["base_row"])
    tracker._save_verdicts([row])
    snapshot = tracker._load_verdicts()
    target = tracker.VERDICTS_FILE
    before = target.read_bytes()
    with tracker._ledger_lock(target):
        for operation in (lambda: tracker._save_verdicts(snapshot),
                          lambda: tracker._append_verdict({**row, "ticker": "SYNTHB"})):
            with pytest.raises(RuntimeError, match="already in progress"):
                operation()
        assert target.read_bytes() == before
    assert tracker._append_verdict({**row, "ticker": "SYNTHB"}) is True
    assert tracker._append_verdict({**row, "ticker": "SYNTHB"}) is False
    assert len(tracker._load_verdicts()) == 2


@pytest.mark.parametrize("command", ["score", "backfill"])
def test_quote_work_allows_append_and_stale_commit_is_rejected(tracker, monkeypatch, command):
    quote = CASE["quote"]
    row = deepcopy(quote["base_row" if command == "score" else "missing_row"])
    second = {**row, "ticker": "SYNTHB"}
    tracker._save_verdicts([row])
    monkeypatch.setattr(tracker, "_today", lambda: quote["today"])
    calls = []

    def fetch(ticker, on_date, verbose=False):
        if not calls:
            assert tracker._append_verdict(second) is True
        calls.append((ticker, on_date))
        evidence = deepcopy(quote["entry_quotes"][ticker])
        evidence.update(requested_date=on_date, resolved_date=on_date)
        return evidence

    if command == "score":
        def fetch_snapshot(ticker, entry_date, horizon_date):
            from _forward_snapshot import snapshot_return
            entry = fetch(ticker, entry_date)
            snapshot = snapshot_return(ticker, entry_date, horizon_date, [
                [entry_date, entry["price"]],
                [horizon_date, entry["price"] * 1.1],
            ])
            assert snapshot["available"] is True
            return snapshot
        monkeypatch.setattr(tracker, "_fetch_return_snapshot", fetch_snapshot)
    else:
        monkeypatch.setattr(tracker, "_quote_on", fetch)
    with pytest.raises(RuntimeError, match="changed.*retry"):
        getattr(tracker, "cmd_" + command)(SimpleNamespace())
    assert calls
    assert tracker._load_verdicts() == [row, second]


@pytest.mark.parametrize("command", ["record", "backfill_validation_fp"])
def test_record_deduplicates_after_builder_interleaving(tracker, monkeypatch, command):
    row = deepcopy(CASE["quote"]["base_row"])

    def build(*_):
        assert tracker._append_verdict(row) is True
        return [deepcopy(row)]

    if command == "record":
        monkeypatch.setattr(tracker, "_build_verdict_from_flags", lambda args: build()[0])
        args = SimpleNamespace(record_path=None, ticker=row["ticker"])
    else:
        monkeypatch.setattr(tracker, "_build_validation_fp_rows", build)
        args = SimpleNamespace()
    getattr(tracker, "cmd_" + command)(args)
    assert tracker._load_verdicts() == [row]


@pytest.mark.parametrize("micro, expected", [(True, "watch"), (False, "deep")])
def test_selected_ceiling_survives_cheap_receipt_and_sic(state, monkeypatch, micro, expected):
    def unused_provider(*_args, **_kwargs):
        pytest.fail("mechanical ceiling case reached an unused provider")

    edgar = ModuleType("edgar")
    edgar.Company = unused_provider
    monkeypatch.setitem(sys.modules, "edgar", edgar)
    for name in ("_extract_concentration", "_concentration_flag"):
        monkeypatch.setattr(sys.modules["deepdive_data"], name, unused_provider, raising=False)
    # Record the prior missing/present state before forcing a fresh import.
    monkeypatch.setitem(sys.modules, "cheap_pass", None)
    monkeypatch.delitem(sys.modules, "cheap_pass", raising=False)
    import pandas as pd
    import filter_by_sic as stages
    import cheap_pass
    import run_theme

    root = Path(state["root"])
    for module in (run_theme, cheap_pass):
        monkeypatch.setattr(module, "REPORTS", root)
        monkeypatch.setattr(module, "CFG", deepcopy(CASE["config"]))
        monkeypatch.setattr(module, "today", lambda: CASE["asof"])
    monkeypatch.setattr(cheap_pass, "init_edgar", lambda: None)
    monkeypatch.setattr(cheap_pass, "health_check",
                        lambda row: {**row.to_dict(), **CASE["health"]})
    monkeypatch.setattr(cheap_pass, "score", lambda frame: frame)
    commands = []
    selected = CASE["config"]["micro_cap_max" if micro else "market_cap_max"]

    def run(command, label):
        commands.append(command)
        assert float(command[command.index("--max-mcap") + 1]) == selected
        if label == "DISCOVER":
            path = root / ("universe_" + CASE["slug"] + "_" + CASE["asof"] + ".csv")
            row = {**CASE["universe"][0], "band": expected}
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([row]).to_csv(path, index=False)
            receipt = stages.stage_completion("synthetic_discover", 1,
                work=[stages.stage_work("synthetic_source")])
            stages.write_stage_receipt(path, receipt)
        else:
            assert label == "CHEAP_PASS"
            with monkeypatch.context() as nested:
                nested.setattr(sys, "argv", command[1:])
                assert cheap_pass.main() == 0

    monkeypatch.setattr(run_theme, "_run", run)
    argv = ["run_theme.py", "--theme", CASE["theme"], "--slug", CASE["slug"]]
    monkeypatch.setattr(sys, "argv", argv + (["--micro"] if micro else []))
    assert run_theme.main() == 0
    assert len(commands) == 2
    cheap = root / ("cheappass_" + CASE["slug"] + "_" + CASE["asof"] + ".csv")
    receipt = stages.read_stage_receipt(cheap, 1)
    assert receipt["decisions"][0]["band"] == expected
    candidates = root / ("candidates_" + CASE["slug"] + ".json")
    assert json.loads(candidates.read_text(encoding="utf-8"))[0]["band"] == expected


@pytest.mark.parametrize("status, count, limit, expected", [
    ("unavailable", 0, None, "unavailable"),
    ("complete", 0, None, "complete"),
    ("partial", 2, None, "partial"),
    ("complete", 2, 1, "partial"),
    ("complete", 2, None, "partial"),
])
def test_backtest_keeps_universe_completion_and_truncation(
        state, monkeypatch, status, count, limit, expected):
    import filter_by_sic as stages
    backtest = importlib.import_module("backtest")
    rows = stages.StageRows(deepcopy(CASE["universe"][:count]), stage="pit_universe",
        work=[stages.stage_work("synthetic_seed", status=status)],
        reasons=["historical_seed_coverage_unproved"] if status == "partial" else [])
    rows.completion.update(asof=CASE["asof"],
        coverage_scope="current_sic_seed_and_observed_submissions",
        identities=[{"cik": row["cik"], "ticker": row["ticker"]} for row in rows])
    monkeypatch.setattr(backtest, "_process_name",
        lambda row, *_: {**row, **deepcopy(CASE["processed"])})
    cell = backtest.run_cell(CASE["theme"], CASE["asof"], universe_fn=lambda *_: rows,
        benchmark_fn=lambda *_: deepcopy(CASE["benchmark"]), limit=limit)
    persisted = json.loads(Path(cell["output_path"]).read_text(encoding="utf-8"))
    assert persisted == {key: value for key, value in cell.items() if key != "output_path"}
    assert cell["universe_completion"] == rows.completion
    assert cell["completion"]["upstream"] == [rows.completion]
    assert cell["completion"]["status"] == expected
    assert ("historical_eligibility_unavailable" in cell["completion"]["reasons"]) is (count > 0)
    assert cell["universe_size_full"] == count
    assert cell["universe_size"] == cell["n_processed"] == (count if limit is None else min(count, limit))
    assert cell["truncated"] is (limit is not None and count > limit)
    assert ("universe_truncated" in cell["completion"]["reasons"]) is cell["truncated"]
    monkeypatch.setattr(backtest, "run_cell", lambda *_a, **_kw: cell)
    monkeypatch.setattr(sys, "argv", ["backtest.py", "--theme", CASE["theme"],
                                    "--asof", CASE["asof"], "--no-write"])
    assert backtest._cli() == (0 if expected == "complete" else 2)


def test_plain_universe_list_keeps_missing_completion_evidence(state):
    backtest = importlib.import_module("backtest")
    cell = backtest.run_cell(CASE["theme"], CASE["asof"], universe_fn=lambda *_: [],
        benchmark_fn=lambda *_: deepcopy(CASE["benchmark"]), write=False)
    assert cell["completion"]["status"] == "unavailable"
    assert "missing_completion_evidence" in cell["universe_completion"]["reasons"]
'''


def source22_scenarios():
    """Generate event, PIT identity and frozen-policy observations from synthetic constants."""
    from copy import deepcopy
    from html import escape
    source = [
        {"ticker": "SYNTH" + letter, "cik": "%010d" % (index + 1),
         "name": "AcmeCorp Synthetic " + letter, "event_type": "spinoff",
         "catalyst": "Synthetic Form 10-12B event", "file_date": "2000-12-10",
         "form": "10-12B", "band": band, "mktcap": 1000000}
        for index, (letter, band) in enumerate(zip("ABCD", ["deep", "watch", "deep", "large"]))
    ]
    decisions = [
        {"input_index": index, "ticker": row["ticker"], "cik": row["cik"], "band": row["band"],
         "screening_decision": decision, "evidence_complete": index != 3}
        for index, (row, decision) in enumerate(zip(source, [
            "retained", "retained", "rejected_existing_policy", "excluded_existing_large_band"]))
    ]
    screened = [
        {"input_index": str(index), "ticker": row["ticker"], "cik": row["cik"],
         "rejected": "True" if index == 2 else "False", "kf_scanned": "True",
         "disclosure_review_required": "False"}
        for index, row in enumerate(source[:3])
    ]
    event_cases = []
    for name in ["complete", "source_partial", "missing_scan", "unknown_rejected_identity",
                 "unknown_band", "missing_decision", "wrong_csv_identity", "wrong_csv_rejection",
                 "duplicate_csv_index", "zero_cik", "unproved_large_exclusion", "complete_empty"]:
        item = {"name": name, "source": deepcopy(source), "decisions": deepcopy(decisions),
                "screened": deepcopy(screened), "source_status": "complete",
                "expected_status": "complete", "expected_indices": [0, 1], "error": False}
        if name == "source_partial":
            item["source_status"] = item["expected_status"] = "partial"
        elif name == "missing_scan":
            item["decisions"][0]["evidence_complete"] = False
            item["screened"][0]["kf_scanned"] = "False"
            item["expected_status"] = "partial"
        elif name == "unknown_rejected_identity":
            item["source"][2]["cik"] = item["decisions"][2]["cik"] = item["screened"][2]["cik"] = ""
            item["expected_status"] = "partial"
        elif name == "unknown_band":
            item["source"][0]["band"] = item["decisions"][0]["band"] = "unknown"
            item["expected_status"] = "partial"
        elif name == "missing_decision":
            item["decisions"].pop()
            item["error"] = True
        elif name == "wrong_csv_identity":
            item["screened"][0]["ticker"] = "UNRELATED"
            item["error"] = True
        elif name == "wrong_csv_rejection":
            item["screened"][0]["rejected"] = "True"
            item["error"] = True
        elif name == "duplicate_csv_index":
            item["screened"][1]["input_index"] = "0"
            item["error"] = True
        elif name == "zero_cik":
            item["source"][0]["cik"] = item["decisions"][0]["cik"] = item["screened"][0]["cik"] = "0000000000"
            item["error"] = True
        elif name == "unproved_large_exclusion":
            item["source"][3]["band"] = "unknown"
            item["error"] = True
        elif name == "complete_empty":
            item.update(source=[], decisions=[], screened=[], expected_indices=[])
        event_cases.append(item)

    headers = ["X", "Filing Date", "Trade Date", "Ticker", "Company Name", "Industry",
               "Ins", "Trade Type", "Price", "Qty", "Owned", "%Own", "Value",
               "1d", "1w", "1m", "6m"]
    valid = ["", "2000-12-15 12:30:00", "2000-12-14", "SYNTHA", "AcmeCorp Synthetic A",
             "Synthetic", "2", "P - Purchase", "$1", "+100", "100", "+1%", "+$100", "", "", "", ""]
    def table(rows, labels=headers, closed=True):
        header = "<tr>" + "".join("<th>" + escape(value) + "</th>" for value in labels) + "</tr>"
        body = "".join("<tr>" + "".join("<td>" + escape(value) + "</td>" for value in row) + "</tr>" for row in rows)
        return "<table>" + header + body + ("</table>" if closed else "")
    html_cases = [
        {"name": "valid", "html": table([valid]), "status": "complete", "records": 1},
        {"name": "unrelated_table", "html": table([valid]) + "<table><tr><td>Other content</td></tr></table>", "status": "complete", "records": 1},
        {"name": "ambiguous_tables", "html": table([valid]) * 2, "status": "unavailable", "records": 0},
        {"name": "duplicate_header", "html": table([valid], headers + ["Value"]), "status": "unavailable", "records": 0},
        {"name": "header_only", "html": table([]), "status": "unavailable", "records": 0},
        {"name": "explicit_zero", "html": table([["No results found"]]), "status": "complete", "records": 0},
        {"name": "unclosed", "html": table([valid], closed=False), "status": "unavailable", "records": 0},
        {"name": "next_page", "html": table([valid]) + '<a href="/latest-cluster-buys?page=2" rel="next">Next</a>', "status": "partial", "records": 1},
        {"name": "zero_with_next", "html": table([["No results found"]]) + '<a href="?page=2" rel="next">Next</a>', "status": "partial", "records": 0},
        {"name": "zero_with_data", "html": table([["No results found"], valid]), "status": "partial", "records": 0},
    ]
    mutations = [
        ("money_garbage", 12, "garbage$100"), ("money_negative", 12, "-$100"),
        ("money_bad_comma", 12, "$1,00"), ("money_empty", 12, ""),
        ("filing_suffix", 1, "2000-12-15 nonsense"), ("date_invalid", 2, "2000-02-30"),
        ("future_filing", 1, "2001-01-02"), ("trade_after_filing", 2, "2000-12-16"),
        ("ticker_unicode", 3, "\u212a"), ("ticker_path", 3, "../SYNTH"),
        ("insider_negative", 6, "-2"), ("trade_unknown", 7, "Q - Unknown"),
    ]
    for name, column, value in mutations:
        invalid = valid.copy()
        invalid[3] = "SYNTHB"
        invalid[column] = value
        html_cases.append({"name": name, "html": table([valid, invalid]), "status": "partial", "records": 1})
    fewer = valid.copy()
    fewer[6] = "1"
    html_cases.append({"name": "valid_exclusion", "html": table([fewer]), "status": "complete", "records": 0})
    bad_fewer = fewer.copy()
    bad_fewer[12] = "N/A"
    html_cases.append({"name": "invalid_below_threshold", "html": table([bad_fewer]), "status": "partial", "records": 0})
    html_cases.append({"name": "truncated_sibling", "html": table([valid, valid[:-1]]), "status": "partial", "records": 1})
    zero_money = valid.copy()
    zero_money[12] = "+$0"
    html_cases.append({"name": "reported_zero", "html": table([zero_money]), "status": "complete", "records": 1})

    symbol = {"cik": 1, "taxonomy": "dei", "tag": "TradingSymbol",
              "units": {"pure": [{"val": "SYNTHPAST", "filed": "2000-01-01"},
                                 {"val": "SYNTHLATEST", "filed": "2000-12-15"},
                                 {"val": "SYNTHFUTURE", "filed": "2001-01-02"}]}}
    pit_cases = []
    def pit_case(name, payload, proven):
        pit_cases.append({"name": name, "payload": payload, "proven": proven,
                          "expected": "SYNTHLATEST" if proven else "SYNTHFALLBACK"})
    pit_case("valid_integer_cik", deepcopy(symbol), True)
    for value in ["1", "0000000001", " 0000000001 "]:
        payload = deepcopy(symbol)
        payload["cik"] = value
        pit_case("valid_string_" + repr(value), payload, True)
    for key in ["cik", "taxonomy", "tag"]:
        payload = deepcopy(symbol)
        del payload[key]
        pit_case("missing_" + key, payload, False)
    for index, value in enumerate([None, True, 1.0, 0, -1, "1.0", "+1", "10000000000", "\uff11", [], {}, 2]):
        payload = deepcopy(symbol)
        payload["cik"] = value
        pit_case("invalid_cik_" + str(index), payload, False)
    for key, values in [("taxonomy", ["us-gaap", "DEI", " dei ", None]),
                        ("tag", ["EntityRegistrantName", "tradingsymbol", " TradingSymbol ", None])]:
        for index, value in enumerate(values):
            payload = deepcopy(symbol)
            payload[key] = value
            pit_case("invalid_" + key + "_" + str(index), payload, False)

    policy_cases = []
    fence = chr(96) * 3
    for name, basis, mos, eligible, tier3, count, buy, accepted in [
        ("fcf_threshold", "fcf_cap", 30, True, False, 0, True, True),
        ("nav_threshold", "nav", 30, True, False, 0, True, True),
        ("catalyst_below_threshold", "fcf_cap", 29.99, True, False, 0, True, False),
        ("nav_below_threshold", "nav", 29.99, True, False, 0, True, False),
        ("blocked_eligibility", "fcf_cap", 40, False, False, 0, True, False),
        ("missing_mos", "fcf_cap", None, True, False, 0, True, False),
        ("abstain_buy", "abstain", 40, True, False, 0, True, False),
        ("tier3_buy", "fcf_cap", 40, True, True, 0, True, False),
        ("killflag_buy", "fcf_cap", 40, True, False, 1, True, False),
        ("watch_catalyst", "fcf_cap", 20, True, False, 0, False, True),
    ]:
        rating = "\u4e70\u5165" if buy else "\u89c2\u5bdf"
        parsed = {"buy_eligible": eligible, "mos_pct": mos, "killflag_count": count}
        report = {"ticker": "SYNTHA", "rating": rating, "confidence": 55,
                  "one_liner": "Synthetic policy boundary.", "is_misrecall": False,
                  "top_long": "Synthetic measured upside.", "top_short": "Synthetic downside.",
                  "killflag_notes": "Synthetic screening outcome.",
                  "margin_of_safety_pct": mos if basis == "fcf_cap" else None,
                  "mos_basis": basis, "catalyst": "Synthetic verified catalyst",
                  "eligibility": {"buy_eligible": eligible, "active_mos_pct": mos,
                                  "tier3_load_bearing": tier3},
                  "report_md": fence + "rating\nrating: %s\nconfidence: 55\nverdict_date: 2001-01-01\nmos_basis: %s\nmos_pct: %s\nbuy_eligible: %s\nkillflag_count: %s\n"
                      % (rating, basis, "null" if mos is None else mos, str(eligible).lower(), count) + fence + "\n"}
        policy_cases.append({"name": name, "report": report, "parsed": parsed, "accepted": accepted})
    return {"event": event_cases, "html": html_cases, "pit": pit_cases, "policy": policy_cases,
            "asof": "2001-01-01", "request_cik": "0000000001",
            "response_url": "https://openinsider.com/latest-cluster-buys",
            "tamper_targets": ["source", "cheap", "admitted"]}


def source22_regression_source():
    return '"""Generated source22 contract cases; every payload is synthetic."""\nfrom copy import deepcopy\nimport csv\nimport importlib\nimport json\nfrom pathlib import Path\nimport sys\nfrom types import SimpleNamespace\n\nimport pytest\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))\nfrom test_private_runs import state\n\nCASE = json.loads(Path(__file__).with_name("source22_contracts.json").read_text(encoding="utf-8"))\n\n\n@pytest.fixture\ndef modules(state, monkeypatch):\n    names = ("filter_by_sic", "_event_admission", "_event_insider", "_pit_universe",\n             "deepdive_data", "rank", "finalize_run")\n    for name in names:\n        monkeypatch.delitem(sys.modules, name, raising=False)\n    return {name: importlib.import_module(name) for name in names}\n\n\ndef completions(stages, case, source_binding):\n    source = stages.stage_completion("event_spinoffs", len(case["source"]),\n        work=[stages.stage_work("synthetic_event_source", status=case["source_status"])])\n    cheap = stages.stage_completion("cheap_pass", len(case["screened"]),\n        work=[stages.stage_work("synthetic_screening")], upstream=[source])\n    cheap.update(input=source_binding, input_count=len(case["source"]),\n                 decisions=deepcopy(case["decisions"]))\n    return source, cheap\n\n\n@pytest.mark.parametrize("case", CASE["event"], ids=lambda case: case["name"])\ndef test_event_source_and_screening_contract(modules, case):\n    module, stages = modules["_event_admission"], modules["filter_by_sic"]\n    source_binding = {"artifact": "candidates_event_synthetic.json", "run_dir": "/synthetic"}\n    cheap_binding = {"artifact": "cheappass_synthetic.csv", "run_dir": "/synthetic"}\n    source, cheap = completions(stages, case, source_binding)\n    args = (case["source"], source, cheap, source_binding, cheap_binding, case["screened"])\n    if case["error"]:\n        with pytest.raises(ValueError):\n            module.event_admission(*args)\n    else:\n        rows, receipt = module.event_admission(*args)\n        assert [row["input_index"] for row in rows] == case["expected_indices"]\n        assert receipt["status"] == case["expected_status"]\n        assert receipt["theme_fit_required"] is False\n        assert len(receipt["decisions"]) == len(case["source"])\n        assert receipt["input"] == source_binding and receipt["cheap_input"] == cheap_binding\n\n\n@pytest.mark.parametrize("case", CASE["html"], ids=lambda case: case["name"])\ndef test_event_insider_page_evidence(modules, case):\n    result = modules["_event_insider"].parse_cluster_page(case["html"],\n        observed_date=CASE["asof"], response_url=CASE["response_url"])\n    assert result["status"] == case["status"]\n    assert len(result["records"]) == case["records"]\n    assert result["proof"]["scope"] == "returned_latest_cluster_buys_page"\n\n\ndef test_event_insider_wrong_response_route_cannot_prove_page(modules):\n    result = modules["_event_insider"].parse_cluster_page(CASE["html"][0]["html"],\n        observed_date=CASE["asof"], response_url="https://example.com/login")\n    assert result["status"] == "unavailable" and not result["records"]\n\n\n@pytest.mark.parametrize("case", CASE["pit"], ids=lambda case: case["name"])\ndef test_pit_symbol_requires_matching_response_identity(modules, case):\n    evidence = {}\n    result = modules["_pit_universe"].cik_trading_symbol_asof(\n        CASE["request_cik"], CASE["asof"], evidence=evidence,\n        submissions_tickers=["SYNTHFALLBACK"],\n        fetch=lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: case["payload"]))\n    assert result == case["expected"]\n    assert evidence["pit_proven"] is case["proven"]\n    if case["proven"]:\n        assert evidence["filed"] == "2000-12-15"\n    else:\n        assert evidence["filed"] is None\n        assert evidence["source"] == "current_submissions"\n        assert any(row["status"] == "unavailable" for row in evidence["work"])\n\n\n@pytest.mark.parametrize("case", CASE["policy"], ids=lambda case: case["name"])\ndef test_frozen_buy_policy_at_accepted_report_boundary(modules, case):\n    report = deepcopy(case["report"])\n    row = {"ticker": report["ticker"]}\n    if case["accepted"]:\n        assert modules["deepdive_data"]._validated_report(report, row, CASE["asof"]) == report\n    else:\n        with pytest.raises(ValueError):\n            modules["deepdive_data"]._validated_report(report, row, CASE["asof"])\n\n\ndef event_files(modules, directory, case):\n    directory.mkdir(parents=True, exist_ok=True)\n    module, stages = modules["_event_admission"], modules["filter_by_sic"]\n    source_path = directory / "candidates_event_synthetic.json"\n    source_path.write_text(json.dumps(case["source"]), encoding="utf-8")\n    source_binding = module.artifact_binding(source_path)\n    source, cheap = completions(stages, case, source_binding)\n    stages.write_stage_receipt(source_path, source)\n    cheap_path = directory / "cheappass_synthetic.csv"\n    with cheap_path.open("w", encoding="utf-8", newline="") as stream:\n        writer = csv.DictWriter(stream, fieldnames=[\n            "input_index", "ticker", "cik", "rejected", "kf_scanned", "disclosure_review_required"])\n        writer.writeheader()\n        writer.writerows(case["screened"])\n    stages.write_stage_receipt(cheap_path, cheap)\n    admitted, receipt = module.write_event_admission(source_path, cheap_path)\n    return {"source": source_path, "cheap": cheap_path, "admitted": admitted}, receipt\n\n\n@pytest.mark.parametrize("case_name", ["complete", "source_partial", "missing_scan", "complete_empty"])\ndef test_event_handoff_reaches_rank_and_finalization_without_gate2(modules, state, case_name):\n    case = next(case for case in CASE["event"] if case["name"] == case_name)\n    directory = Path(state["root"])\n    paths, receipt = event_files(modules, directory, case)\n    rows, binding, input_completion = modules["deepdive_data"]._data_input(paths["admitted"])\n    assert input_completion["status"] == case["expected_status"]\n    deep = [row for row in rows if row["band"] == "deep"]\n    stages = modules["filter_by_sic"]\n    for row in deep:\n        report = deepcopy(CASE["policy"][-1]["report"])\n        report["ticker"] = row["ticker"]\n        (directory / ("report_" + row["ticker"] + ".md")).write_text(report["report_md"], encoding="utf-8")\n        data = directory / ("deepdive_" + row["ticker"] + "_" + CASE["asof"] + ".json")\n        data.write_text(json.dumps({"ticker": row["ticker"], "synthetic_handoff_only": True}), encoding="utf-8")\n        completion = stages.stage_completion("deepdive_data", 1, upstream=[input_completion])\n        completion.update(input=binding,\n            input_identity={key: row[key] for key in ("input_index", "ticker", "cik", "band")})\n        stages.write_stage_receipt(data, completion)\n    rank = modules["rank"]\n    inputs = rank._collect_ranking_inputs(directory)\n    stats = rank.compute_funnel_stats(directory, _inputs=inputs)\n    selected, required, _, _ = rank._ranking_report_selection(stats, inputs)\n    assert required == {row["ticker"] for row in deep}\n    assert {path.stem.removeprefix("report_") for path in selected} == required\n    finalize = modules["finalize_run"]\n    deep_tickers, missing = finalize.assert_reports_complete(directory)\n    assert not missing\n    completion = finalize.finalization_inputs(directory, deep_tickers, missing)\n    assert completion["status"] == case["expected_status"]\n    assert not (directory / "gate2_results.json").exists()\n\n\n@pytest.mark.parametrize("target", CASE["tamper_targets"])\ndef test_event_handoff_rejects_changed_bound_bytes(modules, state, target):\n    paths, _ = event_files(modules, Path(state["root"]), CASE["event"][0])\n    path = paths[target]\n    path.write_bytes(path.read_bytes() + b"\\n")\n    with pytest.raises(ValueError):\n        modules["_event_admission"].read_event_admission(path.parent)\n'


def source23_scenarios():
    """Synthetic financial, snapshot and event regressions for source23."""
    from copy import deepcopy
    first, last = "2000-01-03", "2000-02-02"
    snapshots = []
    for name, entry, horizon, frozen in [
            ("split", 50, 55, 100), ("reverse_split", 1000, 1100, 100),
            ("dividend_adjusted", 90, 100, 100), ("unchanged", 100, 110, 100)]:
        snapshots.append({"name": name, "rows": [[first, entry], [last, horizon]],
                          "frozen": frozen, "expected": horizon / entry - 1})
    bad = [
        ("empty", []), ("missing_entry", [[last, 110]]),
        ("duplicate_entry", [[first, 100], [first, 100], [last, 110]]),
        ("duplicate_exit", [[first, 100], [last, 110], [last, 111]]),
        ("future_only_exit", [[first, 100], ["2000-02-03", 110]]),
        ("stale_entry", [["1999-12-26", 100], [last, 110]]),
        ("invalid_date", [[first, 100], ["2000-02-30", 110]]),
    ]
    for value in [0, -1, True, None, "100", "NaN"]:
        bad.append(("bad_" + str(len(bad)), [[first, value], [last, 110]]))
    clean = {"ticker": "SYNTA", "cik": "0000000123",
             "tenk": {"available": True, "has_going_concern": False,
                      "has_material_weakness": False, "has_death_spiral": False},
             "derived": {"concentration_flag": None, "fundamental_decline_flag": False,
                         "distress_kill": False}}
    val = {"mos_basis": "fcf_cap", "margin_of_safety_pct": 0.4, "buy_eligible": True}
    risks = [{"name": "known_clear", "deep": deepcopy(clean), "bucket": "buy_eligible", "count": 0}]
    for name, deep in [
            ("missing", {}), ("missing_tenk", {"derived": clean["derived"]}),
            ("invalid_count", {**clean, "killflag_count": True}),
            ("historical", {**clean, "as_of": first})]:
        risks.append({"name": name, "deep": deepcopy(deep), "bucket": "abstain",
                      "count": 0 if name == "historical" else None})
    observed = deepcopy(clean)
    observed["tenk"]["has_going_concern"] = True
    risks.append({"name": "known_risk", "deep": observed, "bucket": "AVOID", "count": 1})
    signals = {"price_divergence": {"divergence_label": "aligned"},
               "ownership": {"recent_13d_13g_count": 0, "recent_13d_13g": [],
                             "short_interest_pct": None, "short_trend": None,
                             "staleness_note": "Synthetic unavailable observation."},
               "signals_meta": {"diagnostic_only": True, "never_affects_buy": True,
                                "generated_utc": "2000-01-03T12:00:00Z"}}
    event = source22_scenarios()
    empty = next(case["html"] for case in event["html"] if case["name"] == "explicit_zero")
    valid = event["html"][0]["html"]
    totals = [
        {"name": "empty", "html": empty, "status": "complete"},
        {"name": "empty_total", "html": empty + "<p>Showing 1 to 10 of 100</p>", "status": "partial"},
        {"name": "empty_zero_total", "html": empty + "<p>Showing 0 to 0 of 0</p>", "status": "complete"},
        {"name": "empty_next", "html": empty + '<a rel="next" href="?page=2">Next</a>', "status": "partial"},
        {"name": "valid_larger_total", "html": valid + "<p>Showing 1 to 1 of 100</p>", "status": "partial"},
        {"name": "valid_zero_total", "html": valid + "<p>Showing 0 to 0 of 0</p>", "status": "partial"},
        {"name": "conflicting_totals", "html": empty + "<p>Showing 0 to 0 of 0</p><p>Showing 1 to 1 of 1</p>", "status": "partial"},
        {"name": "malformed_total", "html": empty + "<p>Showing 0 to 0 of 1,,0</p>", "status": "partial"},
    ]
    return {"ticker": "SYNTA", "cik": "0000000123", "entry_date": first, "horizon_date": last,
            "snapshots": snapshots, "bad_snapshots": [{"name": n, "rows": r} for n, r in bad],
            "risks": risks, "valuation": val, "clean": clean, "signals": signals,
            "totals": totals, "event_asof": event["asof"], "response_url": event["response_url"],
            "bootstrap": [{"ticker": "SYNTA", "year": 2000, "core4": 4, "blow": True},
                          {"ticker": "SYNTB", "year": 2000, "core4": 0, "blow": False}],
            "bootstrap_spill": [{"ticker": "SYNTA", "year": 2000, "core4": 4, "blow": False},
                                {"ticker": "SYNTB", "year": 2000, "core4": 3, "blow": True},
                                {"ticker": "SYNTC", "year": 2000, "core4": 0, "blow": False}],
            "report": finalizer_scenario()["report"]}


def source23_regression_source():
    return '"""Generated source23 contracts. All observations and identities are synthetic."""\nfrom copy import deepcopy\nimport importlib\nimport json\nfrom pathlib import Path\nimport sys\nfrom types import SimpleNamespace\n\nimport pytest\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))\nfrom test_private_runs import state\nfrom test_financial_evidence import valuation_module\nfrom test_source22_contracts import modules, event_files, CASE as EVENT\n\nCASE = json.loads(Path(__file__).with_name("source23_contracts.json").read_text(encoding="utf-8"))\n\n\n@pytest.mark.parametrize("case", CASE["snapshots"], ids=lambda case: case["name"])\ndef test_return_uses_one_adjustment_snapshot(case):\n    from _forward_snapshot import snapshot_return\n    result = snapshot_return(CASE["ticker"], CASE["entry_date"], CASE["horizon_date"], case["rows"])\n    assert result["available"] is True\n    assert result["return_fraction"] == pytest.approx(case["expected"])\n    assert result["entry_quote"]["price"] == case["rows"][0][1]\n    assert len(result["adjustment_snapshot"]["selected_endpoints_sha256"]) == 64\n\n\n@pytest.mark.parametrize("case", CASE["bad_snapshots"], ids=lambda case: case["name"])\ndef test_unsupported_snapshot_cannot_produce_a_return(case):\n    from _forward_snapshot import snapshot_return\n    result = snapshot_return(CASE["ticker"], CASE["entry_date"], CASE["horizon_date"], case["rows"])\n    assert result["available"] is False and result["return_fraction"] is None\n\n\n@pytest.mark.parametrize("case", CASE["risks"], ids=lambda case: case["name"])\ndef test_unknown_risk_abstains_without_comparing_none(state, case):\n    import backtest\n    result = backtest.bucket_name(case["deep"], CASE["valuation"])\n    assert result["bucket"] == case["bucket"]\n    assert result["killflag_count"] == case["count"]\n\n\ndef test_reverse_dcf_display_uses_fraction_and_perpetuity_model(state):\n    import make_report\n    result = make_report.render_report(\n        CASE["clean"], {"reverse_dcf_implied_growth": 0.1, "mos_basis": "abstain"})\n    assert "Reverse DCF implied growth (Gordon perpetuity): 10.0%" in result\n    assert "Reverse DCF implied growth (5-yr)" not in result\n\n\n@pytest.mark.parametrize("case", CASE["totals"], ids=lambda case: case["name"])\ndef test_insider_empty_and_result_totals_agree(modules, case):\n    result = modules["_event_insider"].parse_cluster_page(case["html"],\n        observed_date=CASE["event_asof"], response_url=CASE["response_url"])\n    assert result["status"] == case["status"]\n\n\ndef test_resampled_references_remain_distinct_occurrences(state, monkeypatch):\n    directory = Path(__file__).resolve().parents[2] / "docs" / "backtest-2026-06"\n    monkeypatch.syspath_prepend(str(directory))\n    module = importlib.import_module("distress_oos_validate2")\n    a, b = deepcopy(CASE["bootstrap"])\n    result = module.loyo_lift([a, a, b, b, b], "core4")\n    assert result[:4] == (1, 0, 1, 3)\n    assert result[4] == pytest.approx(2.5)\n    assert result[5] == pytest.approx(0.5)\n    calls = iter(["SYNTA", "SYNTA", "SYNTA", "SYNTB"])\n    monkeypatch.setattr(module.random, "choice", lambda _: next(calls))\n    result = module.ticker_bootstrap([a, b], "core4", B=2)\n    assert result[-1] == 2\n\n\ndef test_historical_name_abstains_and_preserves_outcomes(state, monkeypatch):\n    import backtest\n    monkeypatch.setattr(backtest, "_val_cfg", lambda: {})\n    deep = deepcopy(CASE["clean"])\n    deep["derived"]["asof_max_filing_date"] = CASE["entry_date"]\n    row = backtest._process_name(\n        {"ticker": CASE["ticker"], "cik": CASE["cik"]}, CASE["entry_date"], 12,\n        lambda *_, **__: deep, lambda *_: CASE["valuation"],\n        lambda *_, **__: {"mktcap": 1000000, "usable": True},\n        lambda *_: {"status": "ok", "total_return": 0.1})\n    assert row["bucket"] == "abstain" and row["buy_eligible"] is False\n    assert row["total_return"] == 0.1\n    assert row["historical_eligibility"]["status"] == "unavailable"\n    audit = backtest.look_ahead_audit([row], CASE["entry_date"], {}, expect_dates=True)\n    assert audit["scope"] == "filing_dates_only"\n    assert audit["all_eligibility_inputs_proven"] is False\n\n\ndef test_historical_pull_never_calls_undated_sources(modules, monkeypatch):\n    module = modules["deepdive_data"]\n    def forbidden(*args, **kwargs):\n        pytest.fail("An undated provider input was consumed under as_of")\n    for name in ("_sic_observation", "_validate_ticker_entity", "_insurance_concepts_present"):\n        monkeypatch.setattr(module, name, forbidden)\n    for name in ("concept_series_with_ifrs", "concept_series", "_shares_series", "_one_concept"):\n        monkeypatch.setattr(module, name, lambda *_, **__: [])\n    for name in ("_debt_series", "_ebit_with_source", "_da_series"):\n        monkeypatch.setattr(module, name, lambda *_, **__: ([], None))\n    monkeypatch.setattr(module, "_operating_lease_liability", lambda *_, **__: None)\n    monkeypatch.setattr(module, "_lessor_asset_heavy", lambda *_, **__: (False, "synthetic"))\n    monkeypatch.setattr(module, "tenk_sections", lambda *_, **__: {"available": False})\n    monkeypatch.setattr(module.time, "sleep", lambda _: None)\n    result = module.pull(CASE["ticker"], CASE["cik"], yf_fn=forbidden, as_of=CASE["entry_date"])\n    assert result["historical_eligibility"]["status"] == "unavailable"\n    assert result["derived"]["cross_source_checked"] is False\n\n\ndef test_historical_valuation_abstains_even_when_current_inputs_form_a_band(valuation_module):\n    from make_fixtures import debt_valuation_scenarios\n    compute_valuation = valuation_module.compute_valuation\n    case = debt_valuation_scenarios()\n    deep = case["cases"]["reported"]\n    current = compute_valuation(deep, case["market_cap"], case["config"])\n    historical = compute_valuation({**deep, "as_of": CASE["entry_date"]},\n                                   case["market_cap"], case["config"])\n    assert current["mos_basis"] != "abstain"\n    assert historical["mos_basis"] == "abstain"\n    assert historical["margin_of_safety_pct"] is None\n    assert historical["nav_margin_of_safety_pct"] is None\n    assert historical["buy_eligible"] is False\n\n\ndef test_finalizer_signal_snapshot_survives_recording(modules, state, monkeypatch):\n    finalizer = modules["finalize_run"]\n    directory = Path(state["root"])\n    directory.mkdir(parents=True, exist_ok=True)\n    (directory / ("report_" + CASE["ticker"] + ".md")).write_text(CASE["report"], encoding="utf-8")\n    deep = {**deepcopy(CASE["clean"]), "signals": deepcopy(CASE["signals"])}\n    source = directory / ("deepdive_" + CASE["ticker"] + "_2000-01-01.json")\n    source.write_text(json.dumps(deep), encoding="utf-8")\n    verdict = finalizer.build_verdict(CASE["ticker"], directory, "2000-01-01")\n    snapshot = verdict["signals_snapshot"]\n    assert snapshot["source"]["bytes"] == len(source.read_bytes())\n    assert snapshot["signals"] == CASE["signals"]\n    tracker = importlib.import_module("track_forward")\n    monkeypatch.setattr(tracker, "_quote_on", lambda *_args, **_kwargs: {"price": None})\n    path = directory / "synthetic_verdicts.json"\n    path.write_text(json.dumps([verdict]), encoding="utf-8")\n    recorded = tracker._build_verdicts_from_json(path)[0]\n    assert recorded["signals_snapshot"] == snapshot\n    verdict["signals_snapshot"] = None\n    path.write_text(json.dumps([verdict]), encoding="utf-8")\n    without = tracker._build_verdicts_from_json(path)[0]\n    assert (recorded["rating"], recorded["implied_prob"]) == (without["rating"], without["implied_prob"])\n\n\n@pytest.mark.parametrize("field", ["ticker", "cik", "verdict_date", "signals_sha256", "schema_version"])\ndef test_tampered_signal_handoff_is_rejected(field):\n    from _signal_snapshot import snapshot_from_deep, validate_signal_snapshot\n    deep = {**CASE["clean"], "signals": CASE["signals"]}\n    source = {"artifact": "deepdive_SYNTA_2000-01-01.json", "bytes": 1, "sha256": "a" * 64}\n    snapshot = snapshot_from_deep(deep, CASE["ticker"], CASE["entry_date"], source)\n    snapshot[field] = "invalid"\n    with pytest.raises(ValueError):\n        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["entry_date"])\n\n\n@pytest.mark.parametrize("target", ["source", "admitted"])\ndef test_event_never_parses_a_different_text_snapshot(modules, state, monkeypatch, target):\n    paths, _ = event_files(modules, Path(state["root"]), EVENT["event"][0])\n    module = modules["_event_admission"]\n    original = Path.read_text\n    payload = paths[target].read_bytes()\n    changed = json.loads(payload)\n    changed[0]["name"] = "Different synthetic name"\n    alternate = json.dumps(changed)\n    reads = []\n    def alternating_text(path, *args, **kwargs):\n        if path == paths[target]:\n            reads.append(path)\n            return alternate\n        return original(path, *args, **kwargs)\n    monkeypatch.setattr(Path, "read_text", alternating_text)\n    if target == "source":\n        rows, _ = module._event_inputs(paths["source"], paths["cheap"])\n    else:\n        rows, _ = module.read_event_admission(Path(state["root"]))\n    assert rows[0]["name"] != changed[0]["name"]\n    assert reads == []\n\n\ndef test_event_rejects_alternating_bound_bytes(modules, state, monkeypatch):\n    paths, _ = event_files(modules, Path(state["root"]), EVENT["event"][0])\n    module = modules["_event_admission"]\n    original = Path.read_bytes\n    good = original(paths["source"])\n    bad = json.loads(good)\n    bad[0]["catalyst"] = "Different synthetic catalyst"\n    bad = json.dumps(bad).encode("utf-8")\n    reads = []\n    def alternating(path):\n        if path == paths["source"]:\n            reads.append(path)\n            return good if len(reads) % 2 else bad\n        return original(path)\n    monkeypatch.setattr(Path, "read_bytes", alternating)\n    with pytest.raises(ValueError):\n        module.read_event_admission(Path(state["root"]))\n    assert len(reads) >= 2\n\n\ndef test_event_finalizer_rejects_gate2_receipt_without_payload(modules, state):\n    directory = Path(state["root"])\n    event_files(modules, directory, EVENT["event"][0])\n    gate2 = directory / "gate2_results.json"\n    modules["filter_by_sic"].stage_receipt_path(gate2).write_text("{}", encoding="utf-8")\n    assert not gate2.exists()\n    with pytest.raises(ValueError, match="mix event"):\n        modules["finalize_run"]._event_finalization_inputs(directory, set(), set())\n\ndef test_scoring_rebases_frozen_entry_from_one_download(state, monkeypatch):\n    from make_fixtures import tracking_quote_scenarios\n    from test_tracking_quote_contract import _SyntheticHistory\n    import track_forward as tracker\n    fixture = tracking_quote_scenarios()\n    row = deepcopy(fixture["base_row"])\n    calls = []\n    def download(ticker, **kwargs):\n        calls.append((ticker, kwargs))\n        prices = [5.0, 5.5] if ticker == row["ticker"] else [20.0, 20.0]\n        return _SyntheticHistory({"dates": ["2024-01-01", "2024-01-31"],\n                                  "columns": ["Close"], "values": [[value] for value in prices]})\n    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))\n    monkeypatch.setattr(tracker, "_today", lambda: fixture["today"])\n    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])\n    monkeypatch.setattr(tracker, "_save_verdicts", lambda _: None)\n    tracker.cmd_score(SimpleNamespace())\n    assert row["scored"] is True\n    assert row["entry_price"] == 10.0\n    assert row["return_snapshot"]["entry_quote"]["price"] == 5.0\n    assert row["stock_return_pct"] == 10.0 and row["realized_excess_pct"] == 10.0\n    assert len(calls) == 2\n    assert all(kwargs["start"] == "2023-12-25" and kwargs["end"] == "2024-02-01"\n               and kwargs["auto_adjust"] is True for _, kwargs in calls)\n\n\ndef test_bootstrap_cutoff_spill_changes_precision(state, monkeypatch):\n    directory = Path(__file__).resolve().parents[2] / "docs" / "backtest-2026-06"\n    monkeypatch.syspath_prepend(str(directory))\n    module = importlib.import_module("distress_oos_validate2")\n    a, b, c = deepcopy(CASE["bootstrap_spill"])\n    result = module.loyo_lift([a, b, b, c, c, c, c, c, c, c], "core4")\n    assert result[:4] == (1, 1, 1, 7)\n    assert result[4] == pytest.approx(2.5)\n'



def source24_scenarios():
    """Generate invented report-read and standalone-provenance cases."""
    ticker, cik, when = "SYNTA", "0000000123", "2000-01-01"
    report = ("# AcmeCorp synthetic report\n\n" + chr(96) * 3 + "rating\n"
              "verdict_date: 2000-01-01\nrating: {rating}\nconfidence: 64\n"
              "mos_basis: {basis}\nbuy_eligible: {eligible}\nkillflag_count: 0\n"
              "fundamental_decline_flag: false\n" + chr(96) * 3 + "\n")
    reports = []
    for rating, expected in [("buy", "\u4e70\u5165"), ("watch", "\u89c2\u5bdf"), ("avoid", "\u907f\u5f00")]:
        alternate = "watch" if rating != "watch" else "avoid"
        for encoding in ("lf", "crlf", "bom"):
            first = report.format(rating=rating, basis="fcf_cap" if rating == "buy" else "abstain",
                                  eligible=str(rating == "buy").lower())
            second = report.format(rating=alternate, basis="abstain", eligible="false")
            if encoding == "crlf":
                first, second = first.replace("\n", "\r\n"), second.replace("\n", "\r\n")
            elif encoding == "bom":
                first, second = "\ufeff" + first, "\ufeff" + second
            reports.append({"name": rating + "_" + encoding, "first": first,
                            "alternate": second, "expected_rating": expected})
    return {
        "ticker": ticker, "cik": cik, "date": when, "confidence": 64, "reports": reports,
        "deep": {"ticker": ticker, "cik": cik, "signals": {
            "ownership": {"recent_13d_13g_count": 0, "recent_13d_13g": []},
            "signals_meta": {"diagnostic_only": True, "never_affects_buy": True}}},
        "source": {"artifact": "deepdive_SYNTA_2000-01-01.json", "bytes": 7, "sha256": "a" * 64},
        "verdict": {"ticker": ticker, "cik": cik, "verdict_date": when, "rating": "watch",
                    "confidence": 64, "mos_basis": "abstain", "killflag_count": 0},
        "source_edits": [{"field": "artifact", "value": "deepdive_SYNTB_2000-01-01.json"},
                         {"field": "bytes", "value": 99}, {"field": "sha256", "value": "b" * 64}],
        "invalid_verification": ["verified", "artifact_bytes_verified", True, None],
        "bad_source": [{"name": "traversal", "field": "artifact", "value": "../synthetic.json"},
                       {"name": "zero_length", "field": "bytes", "value": 0},
                       {"name": "bool_length", "field": "bytes", "value": True},
                       {"name": "bad_digest", "field": "sha256", "value": "invalid"}],
    }


def source24_regression_source():
    return '"""Generated source24 regressions. Every report and descriptor is synthetic."""\nfrom copy import deepcopy\nimport hashlib\nimport importlib\nimport json\nfrom pathlib import Path\nimport sys\n\nimport pytest\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))\nfrom test_private_runs import state\nfrom test_source22_contracts import modules\n\nCASE = json.loads(Path(__file__).with_name("source24_contracts.json").read_text(encoding="utf-8"))\n\n\n@pytest.mark.parametrize("case", CASE["reports"], ids=lambda case: case["name"])\ndef test_finalizer_parses_and_hashes_one_report_snapshot(modules, state, monkeypatch, case):\n    directory = Path(state["root"])\n    directory.mkdir(parents=True, exist_ok=True)\n    report = directory / ("report_" + CASE["ticker"] + ".md")\n    first = case["first"].encode("utf-8")\n    alternate = case["alternate"].encode("utf-8")\n    report.write_bytes(first)\n    original_bytes, original_text = Path.read_bytes, Path.read_text\n    reads = []\n    def snapshot(path):\n        reads.append(str(path))\n        return first if len(reads) % 2 else alternate\n    def read_bytes(path):\n        return snapshot(path) if path == report else original_bytes(path)\n    def read_text(path, *args, **kwargs):\n        return snapshot(path).decode("utf-8") if path == report else original_text(path, *args, **kwargs)\n    monkeypatch.setattr(Path, "read_bytes", read_bytes)\n    monkeypatch.setattr(Path, "read_text", read_text)\n    verdict = modules["finalize_run"].build_verdict(CASE["ticker"], directory, None)\n    assert verdict["rating"] == case["expected_rating"]\n    assert verdict["confidence"] == CASE["confidence"]\n    assert verdict["verdict_date"] == CASE["date"]\n    assert verdict["killflag_count"] == 0\n    assert verdict["report_sha256"] == hashlib.sha256(first).hexdigest()\n    assert verdict["report_sha256"] != hashlib.sha256(alternate).hexdigest()\n    assert len(reads) == 1\n\n\ndef make_snapshot():\n    from _signal_snapshot import snapshot_from_deep\n    return snapshot_from_deep(CASE["deep"], CASE["ticker"], CASE["date"], CASE["source"])\n\n\n@pytest.mark.parametrize("change", CASE["source_edits"], ids=lambda case: case["field"])\ndef test_recording_retains_source_edits_only_as_unverified_metadata(modules, state, monkeypatch, change):\n    tracker = importlib.import_module("track_forward")\n    monkeypatch.setattr(tracker, "_quote_on", lambda *_args, **_kwargs: {"price": None})\n    snapshot = make_snapshot()\n    snapshot["source"][change["field"]] = change["value"]\n    verdict = {**CASE["verdict"], "signals_snapshot": snapshot}\n    path = Path(state["root"]) / "synthetic_verdicts.json"\n    path.parent.mkdir(parents=True, exist_ok=True)\n    path.write_text(json.dumps([verdict]), encoding="utf-8")\n    recorded = tracker._build_verdicts_from_json(path)[0]\n    assert recorded["signals_snapshot"]["source"] == snapshot["source"]\n    assert recorded["signals_snapshot"]["source_verification"] == "retained_unverified"\n    assert recorded["signals_snapshot"]["signals"] == CASE["deep"]["signals"]\n    assert not (path.parent / snapshot["source"]["artifact"]).exists()\n    verdict["signals_snapshot"] = None\n    path.write_text(json.dumps([verdict]), encoding="utf-8")\n    without = tracker._build_verdicts_from_json(path)[0]\n    assert (recorded["rating"], recorded["implied_prob"]) == (without["rating"], without["implied_prob"])\n\n\ndef test_legacy_snapshot_is_explicitly_marked_unverified_without_mutating_input():\n    from _signal_snapshot import validate_signal_snapshot\n    snapshot = make_snapshot()\n    snapshot.pop("source_verification")\n    before = deepcopy(snapshot)\n    recorded = validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])\n    assert "source_verification" not in snapshot\n    assert snapshot == before\n    assert recorded["source_verification"] == "retained_unverified"\n\n\n@pytest.mark.parametrize("label", CASE["invalid_verification"])\ndef test_unproved_source_verification_claim_is_rejected(label):\n    from _signal_snapshot import validate_signal_snapshot\n    snapshot = make_snapshot()\n    snapshot["source_verification"] = label\n    with pytest.raises(ValueError, match="source verification"):\n        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])\n\n\n@pytest.mark.parametrize("change", CASE["bad_source"], ids=lambda case: case["name"])\ndef test_source_descriptor_shape_is_still_checked(change):\n    from _signal_snapshot import validate_signal_snapshot\n    snapshot = make_snapshot()\n    snapshot["source"][change["field"]] = change["value"]\n    with pytest.raises(ValueError, match="source metadata"):\n        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])\n\n\ndef test_signal_payload_edit_without_digest_update_is_rejected():\n    from _signal_snapshot import validate_signal_snapshot\n    snapshot = make_snapshot()\n    snapshot["signals"]["ownership"]["recent_13d_13g_count"] += 1\n    with pytest.raises(ValueError, match="digest"):\n        validate_signal_snapshot(snapshot, CASE["ticker"], CASE["cik"], CASE["date"])\n'


def annual_fact_response(facts, *, concept=None):
    """Generate a SEC response with the identity required by the requested concept."""
    case = annual_fact_scenarios()
    return {"cik": int(case["cik"]), "taxonomy": "us-gaap",
            "tag": concept or case["concept"], "units": {"USD": facts}}


def ownership_completion_fixture(count):
    """Synthetic complete-feed metadata for explicit in-memory selftests."""
    return {"status": "complete", "reason": "", "acquisition": "complete",
            "parsing": "complete", "pagination": "complete", "total": count,
            "returned": count, "pages": 1, "lookback_days": 540}


def source25_ownership_success_response():
    """A generated successful feed for the existing ownership selftest assertions."""
    return {"hits": {"total": {"value": 2, "relation": "eq"}, "hits": [
        {"_id": "synthetic-g", "_source": {"form": "SC 13G", "file_date": "2026-02-10",
         "display_names": ["AcmeCorp", "AcmeCorp Synthetic Fund"]}},
        {"_id": "synthetic-d", "_source": {"form": "SC 13D", "file_date": "2026-05-01",
         "display_names": ["AcmeCorp", "ACTIVIST AcmeCorp"]}},
    ]}}


def source25_scenarios():
    """Generate invented unit, debt, ownership, identity and inference cases."""
    end, old_end = "2000-12-31", "1999-12-31"
    component_names = ["LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings",
                       "FinanceLeaseLiabilityNoncurrent", "FinanceLeaseLiabilityCurrent"]
    complete = dict(zip(component_names, [20, 3, 2, 4, 1]))

    def debt_case(name, values, value, status, extra=None):
        concepts = {key: [{"end": end, "val": amount}] for key, amount in values.items()}
        if extra:
            concepts.update(extra)
        return {"name": name, "concepts": concepts, "expected": value, "status": status}

    debt = [
        debt_case("complete_components", complete, 30, "reported"),
        debt_case("reported_zero", dict.fromkeys(component_names, 0), 0, "reported"),
        debt_case("partial_component", {component_names[0]: 20}, 20, "partial"),
        debt_case("partial_with_aggregate", {component_names[0]: 20, "LongTermDebt": 100},
                  100, "partial"),
        debt_case("matching_aggregate", {**complete, "LongTermDebt": 23,
                  "DebtLongtermAndShorttermCombinedAmount": 25}, 30, "reported"),
        debt_case("conflicting_aggregate", {**complete, "LongTermDebt": 100}, 30, "conflicting"),
        debt_case("aggregate_different_period", {component_names[0]: 20}, 20, "partial",
                  {"LongTermDebt": [{"end": old_end, "val": 100}]}),
        debt_case("invalid_component", {**complete, component_names[0]: -1}, 10, "invalid"),
    ]

    def hit(index):
        return {"_id": "synthetic-" + str(index), "_source": {
            "form": "SC 13D", "file_date": "2000-01-0" + str(index),
            "display_names": ["AcmeCorp", "AcmeCorp Synthetic Fund"]}}

    def page(hits, total=None, *, exact=True, include_total=True, status=200):
        envelope = {"hits": hits}
        if include_total:
            envelope["total"] = {"value": total, "relation": "eq" if exact else "gte"}
        return {"http_status": status, "payload": {"hits": envelope}}

    def ownership_case(name, pages, status, count, observed, reason=""):
        return {"name": name, "pages": pages, "status": status, "count": count,
                "observed": observed, "reason": reason}

    ownership = [
        ownership_case("complete_empty", [page([], 0)], "complete", 0, 0),
        ownership_case("complete_one", [page([hit(1)], 1)], "complete", 1, 1),
        ownership_case("complete_two_pages", [page([hit(1)], 2), page([hit(2)], 2)],
                       "complete", 2, 2),
        ownership_case("http_failure", [page([], status=503)], "unavailable", None, 0, "http_status"),
        ownership_case("missing_total_empty", [page([], include_total=False)],
                       "partial", None, 0, "exact_total_unavailable"),
        ownership_case("missing_total_nonempty", [page([hit(1)], include_total=False)],
                       "partial", None, 1, "exact_total_unavailable"),
        ownership_case("lower_bound_total", [page([hit(1)], 1, exact=False)],
                       "partial", None, 1, "exact_total_unavailable"),
        ownership_case("failed_second_page", [page([hit(1)], 2), page([], status=503)],
                       "partial", None, 1, "http_status"),
        ownership_case("premature_empty_page", [page([hit(1)], 2), page([], 2)],
                       "partial", None, 1, "premature_empty_page"),
        ownership_case("duplicate_page", [page([hit(1)], 2), page([hit(1)], 2)],
                       "partial", None, 1, "duplicate_page_or_filing"),
        ownership_case("total_mismatch", [page([hit(1)], 0)], "invalid", None, 1, "total_mismatch"),
        ownership_case("bad_payload", [{"http_status": 200, "payload": {}}],
                       "invalid", None, 0, "invalid_payload"),
        ownership_case("bad_row", [page([{"_source": {}}], 1)],
                       "invalid", None, 0, "invalid_payload"),
    ]
    mos = []
    for basis, field in [("fcf_cap", "margin_of_safety_pct"), ("nav", "nav_margin_of_safety_pct")]:
        for name, reported, ratio, expected in [
            ("fallback", None, 0.375, 37.5), ("explicit", 37.5, 0.375, 37.5),
            ("zero", None, 0, 0), ("negative", None, -0.2, -20),
            ("unavailable", None, None, None), ("invalid", None, True, None)]:
            mos.append({"name": basis + "_" + name, "parsed": {"mos_basis": basis, "mos_pct": reported},
                        "valuation": {field: ratio}, "expected": expected})
    mos.append({"name": "abstain", "parsed": {"mos_basis": "abstain", "mos_pct": None},
                "valuation": {"margin_of_safety_pct": 0.5}, "expected": None})
    report = ("# AcmeCorp synthetic report\n" + chr(96) * 3 + "rating\n"
              "verdict_date: 2000-01-01\nrating: watch\nconfidence: 64\n"
              "mos_basis: {basis}\nmos_pct: {mos}\nbuy_eligible: false\n"
              "killflag_count: 0\nfundamental_decline_flag: false\n" + chr(96) * 3 + "\n")
    return {"ticker": "SYNTA", "cik": "0000000123", "report": report, "mos": mos, "debt": debt,
            "ownership": ownership,
            "equity_basis": source25_equity_basis_scenarios(),
            "invalid_identities": [{"cik": 999}, {"taxonomy": "ifrs-full"}, {"tag": "Assets"}],
            "inference": {"complete": {"excess": [-0.2, 0.1, 0.4, 0.2],
                                      "labels": [0, 1, 2, 3], "cells": [0, 0, 0, 0]},
                          "missing": {"excess": [0.1, 0.4, 0.2],
                                      "labels": [1, 2, 3], "cells": [0, 0, 0]}}}


def source25_annual_cashflows(ocf=20_000_000, capex=5_000_000):
    """Generate complete annual pairs for synthetic valuation controls."""
    period = {"start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-01",
              "fp": "FY", "form": "10-K"}
    return {"ocf": [{**period, "val": ocf}],
            "capex": [{**period, "val": capex}]}


def source25_equity_basis_scenarios():
    """Retain the 18M counterexample and a 20M positive case on post-interest equity."""
    cases = []
    for name, ocf, fcf, equity_low, mos, meets_threshold in [
        ("original_18m", 23_000_000, 18_000_000, 150_000_000, 0.25, False),
        ("positive_20m", 25_000_000, 20_000_000, 166_666_667, 0.3889, True),
    ]:
        data = {
            "ticker": "SYNTA",
            "derived": {
                "latest_cash": 20_000_000, "latest_total_debt": 10_000_000,
                "latest_revenue": 100_000_000, "latest_net_income": 15_000_000,
                "latest_ocf": ocf, "latest_ebit": 18_000_000,
                "latest_dep_amort": 4_000_000, "latest_capex": 5_000_000,
                "latest_ebitda": 22_000_000, "latest_fcf": fcf,
                "fcf_is_ocf_proxy": False, "sic": "3990",
            },
            "financials": {
                "assets": [{"end": "2024-12-31", "val": 200_000_000}],
                "equity": [{"end": "2024-12-31", "val": 150_000_000}],
                "ebit": [{"end": "2024-12-31", "val": 18_000_000}],
                "dep_amort": [{"end": "2024-12-31", "val": 4_000_000}],
                "revenue": [{"end": "2024-12-31", "val": 100_000_000}],
                "shares_outstanding": [{"end": "2024-12-31", "val": 10_000_000}],
                **source25_annual_cashflows(ocf=ocf),
            },
        }
        source26_debt_fixture(data)
        source28_annual_inputs(data)
        cases.append({"name": name, "data": data, "market_cap": 120_000_000,
                      "equity_low": equity_low, "mos": mos, "meets_threshold": meets_threshold})
    return cases


def source25_regression_source():
    return '"""Generated Source25 contracts. All observations and identities are synthetic."""\nimport ast\nfrom copy import deepcopy\nimport importlib\nimport itertools\nimport json\nfrom pathlib import Path\nimport sys\nfrom types import SimpleNamespace\n\nimport pytest\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nsys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))\nfrom test_private_runs import state\nfrom test_source22_contracts import modules\nfrom test_debt_evidence import debt_module\nfrom test_financial_evidence import valuation_module\nfrom make_fixtures import annual_fact_scenarios, annual_fact_response, source25_annual_cashflows\n\nCASE = json.loads(Path(__file__).with_name("source25_contracts.json").read_text(encoding="utf-8"))\nROOT = Path(__file__).resolve().parents[2]\n\n\ndef selected(path, names, namespace=None):\n    tree = ast.parse(path.read_text(encoding="utf-8"))\n    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]\n    assert {node.name for node in nodes} == set(names)\n    context = {} if namespace is None else dict(namespace)\n    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), context)\n    return context\n\n\n@pytest.mark.parametrize("case", CASE["mos"], ids=lambda case: case["name"])\ndef test_persisted_mos_is_always_in_report_percent_units(modules, case):\n    assert modules["finalize_run"]._verdict_mos_pct(case["parsed"], case["valuation"]) == case["expected"]\n\n\n@pytest.mark.parametrize("basis", ["fcf_cap", "nav"])\ndef test_finalizer_fallback_matches_explicit_percent_report(modules, state, monkeypatch, basis):\n    finalizer = modules["finalize_run"]\n    directory = Path(state["root"])\n    directory.mkdir(parents=True, exist_ok=True)\n    report = directory / ("report_" + CASE["ticker"] + ".md")\n    field = "margin_of_safety_pct" if basis == "fcf_cap" else "nav_margin_of_safety_pct"\n    monkeypatch.setattr(finalizer, "_find_json", lambda *_args, **_kwargs:\n                        {"ticker": CASE["ticker"], "valuation": {field: 0.375}})\n    rows = []\n    for mos in ("null", "37.5"):\n        report.write_text(CASE["report"].format(basis=basis, mos=mos), encoding="utf-8")\n        rows.append(finalizer.build_verdict(CASE["ticker"], directory, None))\n    assert rows[0]["margin_of_safety_pct"] == rows[1]["margin_of_safety_pct"] == 37.5\n\n\n@pytest.mark.parametrize("case", CASE["debt"], ids=lambda case: case["name"])\ndef test_debt_preserves_aggregate_and_component_coverage(debt_module, monkeypatch, case):\n    calls = []\n    def query(_cik, concept, **_kwargs):\n        calls.append(concept)\n        return deepcopy(case["concepts"].get(concept, []))\n    monkeypatch.setattr(debt_module._dc, "_one_concept", query)\n    rows, _ = debt_module._dc._debt_series(CASE["cik"])\n    assert rows[-1]["val"] == case["expected"]\n    assert rows[-1]["debt_evidence_status"] == case["status"]\n    assert "Liabilities" not in calls\n    assert "LongTermDebt" in calls\n    if case["name"] == "partial_with_aggregate":\n        assert rows[-1]["components"]["LongTermDebtNoncurrent"] == 20\n        assert rows[-1]["aggregates"]["LongTermDebt"] == 100\n\n\n@pytest.mark.parametrize("name", ["complete_components", "partial_component",\n                                  "partial_with_aggregate", "conflicting_aggregate"])\ndef test_debt_status_reaches_producer_and_buy_guard(debt_module, monkeypatch, name):\n    case = next(case for case in CASE["debt"] if case["name"] == name)\n    query = lambda _cik, concept, **_kwargs: deepcopy(case["concepts"].get(concept, []))\n    monkeypatch.setattr(debt_module._dc, "_one_concept", query)\n    monkeypatch.setattr(debt_module, "_one_concept", query)\n    result = debt_module.pull(CASE["ticker"], CASE["cik"], yf_fn=lambda _ticker: None)\n    derived = result["derived"]\n    assert derived["latest_total_debt"] == case["expected"]\n    assert derived["debt_evidence_status"] == case["status"]\n    assert derived["debt_evidence_uncertain"] == (case["status"] != "reported")\n    from _valuation_eligibility import compose_buy_eligibility\n    eligible, reasons = compose_buy_eligibility(\n        {}, extreme_mos_review_required=False, large_cap_out_of_scope=False,\n        fcf_sustainability_uncertain=False, financial_sic_forced_unsuitable=False,\n        insurance_concepts_present=False, concentration_flag=None,\n        fundamental_decline_flag=False, peak_contamination_flag=False,\n        cross_source_mismatch=False, normalization_masks_current_loss=False,\n        mos=0.5, nav_mos=None, mos_basis="fcf_cap",\n        debt_evidence_uncertain=derived["debt_evidence_uncertain"])\n    assert eligible == (case["status"] == "reported")\n    assert ("debt_evidence_uncertain" in reasons) == (case["status"] != "reported")\n\n\n@pytest.mark.parametrize("case", CASE["ownership"], ids=lambda case: case["name"])\ndef test_ownership_count_requires_complete_acquisition_parse_and_pagination(modules, case):\n    signals = importlib.import_module("signals")\n    report = importlib.import_module("make_report")\n    tracker = importlib.import_module("track_forward")\n    pages = iter(deepcopy(case["pages"]))\n    def request(*_args, **_kwargs):\n        page = next(pages)\n        return SimpleNamespace(status_code=page["http_status"], json=lambda: page["payload"])\n    own = signals.compute_ownership(CASE["ticker"], CASE["cik"], http_fn=request)\n    assert own["recent_13d_13g_count"] == case["count"]\n    assert len(own["recent_13d_13g"]) == case["observed"]\n    completion = own["recent_13d_13g_completion"]\n    assert completion["status"] == case["status"]\n    assert completion["reason"] == case["reason"]\n    rendered = report._render_ownership(own)\n    if case["status"] != "complete":\n        assert "none found" not in rendered\n        assert "null (unavailable;" in rendered\n    elif case["count"] == 0:\n        assert "none found" in rendered\n    snapshot = tracker._signals_snapshot({"ownership": own})\n    assert snapshot["ownership"]["recent_13d_13g_count"] == case["count"]\n    assert snapshot["ownership"]["recent_13d_13g_completion"] == completion\n\n\ndef test_retired_history_route_cannot_write_or_change_calibration(modules, monkeypatch):\n    tracker = importlib.import_module("track_forward")\n    calls = []\n    monkeypatch.setattr(tracker, "_append_verdict", lambda row: calls.append(row))\n    monkeypatch.setattr(tracker, "_load_verdicts", lambda: calls.append("read"))\n    with pytest.raises(RuntimeError, match="retired"):\n        tracker.cmd_backfill_validation_fp(SimpleNamespace())\n    assert calls == []\n    assert not hasattr(tracker, "VALIDATION_FP")\n    assert not hasattr(tracker, "VALIDATION_FP_DATE")\n\n\n@pytest.mark.parametrize("edit", CASE["invalid_identities"])\n@pytest.mark.parametrize("asof", [None, "2024-03-01"])\ndef test_annual_response_identity_must_match_request(state, monkeypatch, edit, asof):\n    import _deepdive_concepts as concepts\n    case = annual_fact_scenarios()\n    payload = annual_fact_response([case["annual"]])\n    payload.update(edit)\n    monkeypatch.setattr(concepts, "http_get", lambda *_args, **_kwargs:\n                        SimpleNamespace(status_code=200, json=lambda: payload))\n    rows = concepts._one_concept(case["cik"], case["concept"], asof=asof)\n    assert rows == []\n    assert rows.completion["status"] == "invalid"\n\n\n@pytest.mark.parametrize("reverse", [False, True])\ndef test_research_selector_applies_shared_annual_duration_rule(state, reverse):\n    import _deepdive_concepts as concepts\n    from datetime import date\n    functions = selected(ROOT / "docs/backtest-2026-06/distress_features_fast.py",\n                         {"_select_concept"}, {"DC": concepts, "date": date})\n    case = annual_fact_scenarios()\n    values = [case["annual"], case["quarter"]]\n    actual = functions["_select_concept"]({"USD": values[::-1] if reverse else values},\n                                         case["asof"], case["concept"])\n    expected = {key: case["annual"][key]\n                for key in ("start", "end", "val", "fy", "filed", "fp", "form")}\n    expected.update(duration_days=364, unit="USD", currency="USD",\n                    taxonomy="us-gaap", concept=case["concept"])\n    assert actual == [expected]\n    assert functions["_select_concept"]({"USD": [case["instant"]]},\n                                        case["asof"], case["concept"]) == []\n    assert functions["_select_concept"]({"USD": [case["instant"]]},\n                                        case["asof"], case["instant_concept"])[0]["val"] == 2000\n\n\ndef inference_functions():\n    return selected(ROOT / "docs/backtest-2026-06/significance_test.py",\n                    {"bucket_statistics", "permutation_inference"})\n\n\n@pytest.mark.parametrize("kind", ["missing", "empty", "nonfinite"])\ndef test_significance_unavailable_groups_do_not_create_minimum_p_values(kind):\n    data = deepcopy(CASE["inference"]["missing" if kind == "missing" else "complete"])\n    if kind == "empty":\n        data = {"excess": [], "labels": [], "cells": []}\n    elif kind == "nonfinite":\n        data["excess"][0] = float("nan")\n    calls = []\n    result = inference_functions()["permutation_inference"](\n        **data, permutations=24, shuffle=lambda rows: calls.append(rows))\n    assert result["status"] == "unavailable"\n    assert result["p_values"] is None\n    assert result["permutations"] == 0\n    assert calls == []\n\n\ndef test_valid_group_permutations_retain_finite_calculation():\n    data = CASE["inference"]["complete"]\n    permutations = iter(itertools.permutations(data["labels"]))\n    result = inference_functions()["permutation_inference"](\n        **data, permutations=24, shuffle=lambda _rows: next(permutations))\n    assert result["status"] == "complete"\n    assert result["permutations"] == 24\n    assert result["observed"]["medians"] == data["excess"]\n    # With singleton buckets every permutation has the same omnibus variance.\n    assert result["exceedances"][2] == 24\n    assert result["p_values"][2] == 1.0\n    assert all(0 < value <= 1 for value in result["p_values"])\n\n\n@pytest.mark.parametrize("missing_start", [False, True])\ndef test_positive_valuation_fixture_requires_annual_cashflow_dates(valuation_module, missing_start):\n    from make_fixtures import financial_scenarios\n    fixture = financial_scenarios()\n    data = deepcopy(fixture["complete"])\n    data["financials"].update(source25_annual_cashflows())\n    if missing_start:\n        for field in ("ocf", "capex"):\n            data["financials"][field][0].pop("start")\n    value = valuation_module.compute_valuation(data, fixture["buy_market_cap"], fixture["config"])\n    assert value["buy_eligible"] is (not missing_start)\n    assert ("fcf_sustainability_uncertain" in value["buy_ineligible_reasons"]) is missing_start\n    if missing_start:\n        assert value["intrinsic_value_band"] is None\n\n\n@pytest.mark.parametrize("case", CASE["equity_basis"], ids=lambda case: case["name"])\n@pytest.mark.parametrize("extra_cash", [0, 30_000_000])\ndef test_post_interest_fcf_has_no_net_cash_addback(valuation_module, case, extra_cash):\n    from _valuation_model import _VALUATION_DEFAULTS\n    data = deepcopy(case["data"])\n    data["derived"]["latest_cash"] += extra_cash\n    value = valuation_module.compute_valuation(data, case["market_cap"], dict(_VALUATION_DEFAULTS))\n    assert value["mos_basis"] == "fcf_cap"\n    assert value["intrinsic_value_band"]["equity_low"] == case["equity_low"]\n    assert value["margin_of_safety_pct"] == case["mos"]\n    assert value["buy_eligible"] is True\n    assert (value["margin_of_safety_pct"] >= 0.30) is case["meets_threshold"]\n'


def source26_scenarios():
    """Generate legacy-label and missing-debt-summary regressions with positive controls."""
    from copy import deepcopy
    clean = source26_reviewed_fixture({"rating": "买入", "adjudication": "data_verified_clean"}, "SYNRC")
    fp = source26_reviewed_fixture({"rating": "买入", "adjudication": "data_false_positive"}, "SYNRF")
    review = {"clean": clean, "fp": fp}
    for name, original in (("bare_clean", clean), ("bare_fp", fp)):
        row = deepcopy(original)
        row.pop("adjudication_evidence")
        review[name] = row
    mutations = {
        "wrong_report": ("verdict", "report_sha256", "f" * 64),
        "wrong_protocol": (None, "protocol", "unsupported"),
        "bool_schema": (None, "schema_version", True),
        "early_date": (None, "review_date", "1999-12-31"),
        "compact_date": (None, "review_date", "20000101"),
        "no_sources": (None, "sources", []),
        "no_checks": (None, "checks", []),
        "wrong_disposition": (None, "disposition", "data_false_positive"),
    }
    for name, (parent, key, value) in mutations.items():
        row = deepcopy(clean)
        target = row["adjudication_evidence"]
        if parent:
            target = target[parent]
        target[key] = value
        review[name] = row
    for name, original, field, value in (
        ("clean_mismatch", clean, "result", "mismatch"),
        ("fp_matches", fp, "result", "matches"),
        ("check_unhashable", clean, "result", []),
        ("source_unhashable", clean, "source_sha256", []),
    ):
        row = deepcopy(original)
        row["adjudication_evidence"]["checks"][0][field] = value
        if name == "fp_matches":
            for check in row["adjudication_evidence"]["checks"]:
                check["result"] = "matches"
        review[name] = row
    row = deepcopy(clean)
    row["adjudication_evidence"]["checks"] = row["adjudication_evidence"]["checks"][:1]
    review["incomplete_scope"] = row

    positive = source25_equity_basis_scenarios()[1]
    base = deepcopy(positive["data"])
    base["derived"]["latest_total_debt"] = 12_000_000
    source26_debt_fixture(base)
    debt = {}
    for name in ("complete", "no_summary_complete", "numeric_only", "no_summary_partial",
                 "reported_summary_partial", "no_period_status", "scalar_mismatch",
                 "missing_component", "aggregate_conflict", "newest_partial",
                 "newest_partial_reversed", "invalid_date", "invalid_scalar",
                 "duplicate_conflict", "unavailable_summary", "unknown_summary", "missing_scalar", "zero"):
        data = deepcopy(base)
        der, fin = data["derived"], data["financials"]
        period = fin["total_debt"][0]
        expected = "reported"
        if name in ("no_summary_complete", "numeric_only", "no_summary_partial"):
            der.pop("debt_evidence_status", None)
        if name == "numeric_only":
            fin.pop("total_debt")
            expected = "unverified"
        if name in ("no_summary_partial", "reported_summary_partial", "newest_partial", "newest_partial_reversed"):
            old = deepcopy(period)
            old["end"] = "2023-12-31"
            period.update(debt_evidence_status="partial", components={},
                          aggregates={"LongTermDebt": 12_000_000},
                          missing_components=["ShortTermBorrowings"])
            expected = "partial"
            if name.startswith("newest_partial"):
                fin["total_debt"] = [old, period] if name == "newest_partial" else [period, old]
        if name == "no_period_status":
            period.pop("debt_evidence_status")
            expected = "unverified"
        if name == "scalar_mismatch":
            der["latest_total_debt"] += 1_000_000
            expected = "conflicting"
        if name == "missing_component":
            period["components"].pop("ShortTermBorrowings")
            expected = "partial"
        if name == "aggregate_conflict":
            period["aggregates"]["LongTermDebt"] = 1
            expected = "conflicting"
        if name == "invalid_date":
            period["end"] = "not-a-date"
            expected = "invalid"
        if name == "invalid_scalar":
            der["latest_total_debt"] = True
            expected = "invalid"
        if name == "duplicate_conflict":
            other = deepcopy(period)
            other["val"] += 1_000_000
            fin["total_debt"].append(other)
            expected = "conflicting"
        if name == "unavailable_summary":
            der["debt_evidence_status"] = "unavailable"
            expected = "unavailable"
        if name == "unknown_summary":
            der["debt_evidence_status"] = "unknown_protocol"
            expected = "unverified"
        if name == "missing_scalar":
            der["latest_total_debt"] = None
            source26_debt_fixture(data)
            expected = "unavailable"
        if name == "zero":
            der["latest_total_debt"] = 0
            source26_debt_fixture(data)
        debt[name] = {"data": data, "status": expected, "uncertain": expected != "reported"}
    return {"review": review, "debt": debt, "market_cap": positive["market_cap"]}


def source26_regression_source():
    return "\"\"\"Generated Source26 receipt and debt-boundary regressions.\"\"\"\nfrom copy import deepcopy\nimport json\nfrom types import SimpleNamespace\n\nimport pytest\n\nfrom make_fixtures import source26_scenarios\nfrom test_private_runs import state\nfrom test_tracking_integrity import tracker\nfrom test_financial_evidence import valuation_module\nfrom _calibration import (_adjudication_review, _buy_data_integrity_summary,\n                          _price_scorable, _adjudication_blocks_price)\nfrom _valuation_model import _VALUATION_DEFAULTS\n\nCASE = source26_scenarios()\nINVALID = [name for name in CASE[\"review\"] if name not in (\"clean\", \"fp\")]\n\n\n@pytest.mark.parametrize(\"name\", INVALID)\ndef test_unsupported_review_stays_pending_and_outside_prices(name):\n    row = deepcopy(CASE[\"review\"][name])\n    row[\"scored\"] = True\n    before = deepcopy(row)\n    assert _adjudication_review(row)[\"status\"] == \"pending\"\n    summary = _buy_data_integrity_summary([row])\n    assert summary[\"rate\"] is None\n    assert summary[\"reviewed_buys\"] == 0 and summary[\"pending_buys\"] == 1\n    assert _adjudication_blocks_price(row)\n    assert _price_scorable([row]) == []\n    assert row == before\n\n\ndef test_valid_receipts_measure_coverage_without_admitting_false_positive_prices():\n    clean, fp = (deepcopy(CASE[\"review\"][key]) for key in (\"clean\", \"fp\"))\n    bare = deepcopy(CASE[\"review\"][\"bare_fp\"])\n    clean[\"scored\"] = fp[\"scored\"] = bare[\"scored\"] = True\n    summary = _buy_data_integrity_summary([clean, fp, bare])\n    assert summary == {\"rate\": 0.5, \"total_buys\": 3, \"reviewed_buys\": 2,\n                       \"clean_buys\": 1, \"false_positive_buys\": 1,\n                       \"pending_buys\": 1, \"review_coverage\": 2 / 3}\n    assert _price_scorable([clean, fp, bare]) == [clean]\n    plain = {key: value for key, value in bare.items()\n             if key not in (\"adjudication\", \"adjudication_evidence\")}\n    assert _price_scorable([plain]) == [plain]\n\n\n@pytest.mark.parametrize(\"name\", INVALID)\ndef test_append_rejects_invalid_completed_claim_before_any_write(tracker, monkeypatch, name):\n    calls = []\n    monkeypatch.setattr(tracker, \"prepare_output\", lambda *_: calls.append(\"write\"))\n    with pytest.raises(ValueError):\n        tracker._append_verdict(deepcopy(CASE[\"review\"][name]))\n    assert calls == []\n\n\n@pytest.mark.parametrize(\"name\", (\"bare_clean\", \"bare_fp\"))\ndef test_legacy_snapshot_preserves_claim_but_cannot_add_another_bare_claim(tracker, name):\n    row = deepcopy(CASE[\"review\"][name])\n    tracker.METRICS_DIR.mkdir(parents=True)\n    raw = (json.dumps(row, sort_keys=True) + \"\\n\").encode()\n    tracker.VERDICTS_FILE.write_bytes(raw)\n    rows = tracker._load_verdicts()\n    assert rows[0] == row\n    rows[0][\"notes\"] = \"synthetic score-only annotation\"\n    tracker._save_verdicts(rows)\n    assert tracker._load_verdicts()[0][\"adjudication\"] == row[\"adjudication\"]\n    before = tracker.VERDICTS_FILE.read_bytes()\n    rows = tracker._load_verdicts()\n    added = deepcopy(row)\n    added[\"ticker\"] = \"SYNRNEW\"\n    rows.append(added)\n    with pytest.raises(ValueError):\n        tracker._save_verdicts(rows)\n    assert tracker.VERDICTS_FILE.read_bytes() == before\n\n\n@pytest.mark.parametrize(\"name\", (\"clean\", \"fp\"))\ndef test_explicit_receipt_attachment_is_bound_and_preserves_original_claim(tracker, name):\n    completed = deepcopy(CASE[\"review\"][name])\n    receipt = completed.pop(\"adjudication_evidence\")\n    updated = tracker._with_adjudication_receipt(completed, receipt)\n    assert updated[\"adjudication\"] == completed[\"adjudication\"]\n    assert _adjudication_review(updated)[\"status\"] == \"reviewed\"\n    assert \"adjudication_evidence\" not in completed\n    changed = deepcopy(receipt)\n    changed[\"verdict\"][\"report_sha256\"] = \"0\" * 64\n    with pytest.raises(ValueError):\n        tracker._with_adjudication_receipt(completed, changed)\n\n\ndef test_receipt_command_uses_existing_private_snapshot_transaction(tracker):\n    completed = deepcopy(CASE[\"review\"][\"clean\"])\n    receipt = completed.pop(\"adjudication_evidence\")\n    tracker.METRICS_DIR.mkdir(parents=True)\n    tracker.VERDICTS_FILE.write_text(json.dumps(completed) + \"\\n\", encoding=\"utf-8\")\n    path = tracker.METRICS_DIR / \"synthetic-review.json\"\n    path.write_text(json.dumps(receipt), encoding=\"utf-8\")\n    tracker.cmd_adjudicate(SimpleNamespace(adjudicate=str(path)))\n    rows = tracker._load_verdicts()\n    assert rows[0][\"adjudication_evidence\"] == receipt\n    assert _buy_data_integrity_summary(rows)[\"reviewed_buys\"] == 1\n\n\ndef test_status_and_scorecard_report_bare_labels_as_pending(tracker, capsys):\n    rows = [CASE[\"review\"][\"bare_clean\"], CASE[\"review\"][\"bare_fp\"]]\n    tracker.METRICS_DIR.mkdir(parents=True)\n    tracker.VERDICTS_FILE.write_text(\"\\n\".join(json.dumps(row) for row in rows) + \"\\n\", encoding=\"utf-8\")\n    tracker.cmd_status(SimpleNamespace())\n    status = capsys.readouterr().out\n    assert \"reviewed 0/2\" in status and \"pending 2\" in status and \"N/A\" in status\n    tracker.cmd_scorecard(SimpleNamespace())\n    scorecard = tracker.SCORECARD_FILE.read_text(encoding=\"utf-8\")\n    assert \"reviewed 0/2\" in scorecard and \"pending 2\" in scorecard\n    assert \"Price quarantine: 2\" in scorecard\n\n\n@pytest.mark.parametrize(\"name\", list(CASE[\"debt\"]))\ndef test_latest_debt_evidence_controls_ev_and_buy(valuation_module, name):\n    case = CASE[\"debt\"][name]\n    result = valuation_module.compute_valuation(deepcopy(case[\"data\"]), CASE[\"market_cap\"],\n                                                dict(_VALUATION_DEFAULTS))\n    assert result[\"debt_evidence_status\"] == case[\"status\"]\n    assert result[\"debt_evidence_uncertain\"] is case[\"uncertain\"]\n    assert result[\"buy_eligible\"] is (not case[\"uncertain\"])\n    if case[\"uncertain\"]:\n        assert result[\"ev\"] is None and result[\"ev_sales\"] is None and result[\"ev_ebitda\"] is None\n        assert \"debt_evidence_uncertain\" in result[\"buy_ineligible_reasons\"]\n    else:\n        der = case[\"data\"][\"derived\"]\n        assert result[\"ev\"] == CASE[\"market_cap\"] + der[\"latest_total_debt\"] - der[\"latest_cash\"]\n        assert result[\"margin_of_safety_pct\"] == 0.3889\n"


def source27_scenarios():
    """Generate JSON-valid oversized debt inputs and ordinary-domain controls."""
    from copy import deepcopy
    previous = source26_scenarios()
    debt = {name: deepcopy(previous["debt"][name])
            for name in ("complete", "zero", "invalid_scalar")}
    for name in ("oversized_scalar", "oversized_period", "oversized_component",
                 "oversized_component_sum", "oversized_mixed_component_sum"):
        case = deepcopy(previous["debt"]["complete"])
        data = case["data"]
        derived, period = data["derived"], data["financials"]["total_debt"][0]
        if name == "oversized_scalar":
            derived["latest_total_debt"] = 10 ** 400
        elif name == "oversized_period":
            period["val"] = 10 ** 400
        elif name == "oversized_component":
            period["components"]["LongTermDebtNoncurrent"] = 10 ** 400
        else:
            derived["latest_total_debt"] = period["val"] = 10 ** 308
            period["components"] = {key: 10 ** 308 for key in period["components"]}
            if name == "oversized_mixed_component_sum":
                period["components"]["FinanceLeaseLiabilityCurrent"] = 1.0
            period["aggregates"] = {}
        case.update(status="invalid", uncertain=True)
        debt[name] = case
    return {"debt": debt, "market_cap": previous["market_cap"]}


def source27_regression_source():
    return '"""Generated numeric-domain regressions with synthetic debt evidence."""\nfrom copy import deepcopy\nimport json\n\nimport pytest\n\nfrom make_fixtures import source27_scenarios\nfrom test_financial_evidence import valuation_module\nfrom test_private_runs import state\nfrom _valuation_model import _VALUATION_DEFAULTS\n\nCASE = source27_scenarios()\n\n\n@pytest.mark.parametrize("name", list(CASE["debt"]))\ndef test_debt_numeric_domain_reaches_valuation_without_exception(valuation_module, name):\n    case = CASE["debt"][name]\n    data = json.loads(json.dumps(case["data"], allow_nan=False))\n    before = deepcopy(data)\n    result = valuation_module.compute_valuation(data, CASE["market_cap"], dict(_VALUATION_DEFAULTS))\n    assert result["debt_evidence_status"] == case["status"]\n    assert result["debt_evidence_uncertain"] is case["uncertain"]\n    assert result["buy_eligible"] is (not case["uncertain"])\n    assert data == before\n    if case["uncertain"]:\n        assert result["ev"] is None\n        assert result["ev_sales"] is None\n        assert result["ev_ebitda"] is None\n        assert "debt_evidence_uncertain" in result["buy_ineligible_reasons"]\n    else:\n        derived = data["derived"]\n        assert result["ev"] == CASE["market_cap"] + derived["latest_total_debt"] - derived["latest_cash"]\n        assert result["margin_of_safety_pct"] == 0.3889\n'



def source28_annual_period(end, value, *, start=None, unit="USD"):
    """Construct an explicitly synthetic calendar-year monetary operand."""
    from datetime import date
    finish = date.fromisoformat(end)
    begin = date.fromisoformat(start or f"{finish.year}-01-01")
    return {"start": begin.isoformat(), "end": end, "val": value,
            "duration_days": (finish - begin).days, "unit": unit,
            "filed": f"{finish.year + 1}-02-01", "fp": "FY", "form": "10-K"}


def source28_annual_inputs(data):
    """Add declared calendar-year spans to retained synthetic EBITDA test inputs."""
    for metric in ("ebit", "dep_amort"):
        data["financials"][metric] = [
            {**row, **source28_annual_period(row["end"], row["val"])}
            for row in data["financials"].get(metric, [])
        ]
    return data


def source28_realize(value):
    """Decode deliberately invalid numeric cases after strict JSON fixture loading."""
    if isinstance(value, dict) and set(value) == {"special_number"}:
        return float(value["special_number"])
    if isinstance(value, dict):
        return {key: source28_realize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [source28_realize(item) for item in value]
    return value


def source28_report(report, *, rating, basis="fcf_cap", eligible=True, mos=38.89,
                    verdict_date="2025-03-01"):
    """Build a self-consistent synthetic report to test its separate valuation binding."""
    from copy import deepcopy
    report = deepcopy(report)
    report.update(rating=rating, mos_basis=basis, margin_of_safety_pct=mos,
                  eligibility={"buy_eligible": eligible, "active_mos_pct": mos,
                               "tier3_load_bearing": False})
    report["report_md"] = (
        f"# {report['ticker']} {verdict_date}\n\n"
        "\x60\x60\x60rating\n"
        f"rating: {rating}\nconfidence: 55\nverdict_date: {verdict_date}\n"
        f"mos_basis: {basis}\nmos_pct: {'null' if mos is None else mos}\n"
        f"buy_eligible: {str(eligible).lower()}\nkillflag_count: 0\n"
        "\x60\x60\x60\n"
    )
    return report


def source28_bound_sample(case):
    """Keep real request/persistence calls supplied only with generated observations."""
    from copy import deepcopy
    sample = downstream_producer_completion_scenarios()
    sample["verdict_date"] = "2025-03-01"
    sample["candidates"][0]["mktcap"] = 120_000_000
    sample["pull_data"] = deepcopy(source25_equity_basis_scenarios()[1]["data"])
    sample["pull_data"].update(tenk={"available": False}, insider={"available": False})
    if case.get("valuation_ineligible"):
        sample["pull_data"]["derived"]["cross_source_mismatch"] = True
    for index, outcome in enumerate(sample["fanout_outcomes"]["success"]):
        edits = case["report"] if index == 0 else {
            "rating": "\u89c2\u5bdf", "eligible": not case.get("valuation_ineligible", False)}
        outcome["report"] = source28_report(outcome["report"], **edits)
    return sample


def source28_scenarios():
    """Generate finite JSON plus explicit invalid-number descriptors for Source28."""
    from copy import deepcopy
    left = source28_annual_period("2000-12-31", 10_000_000)
    right = source28_annual_period("2000-12-31", 5_000_000)
    annual = []
    def pair(name, a, b, values, reason=None):
        annual.append({"name": name, "left": a, "right": b,
                       "values": values, "reason": reason})
    pair("matched", [left], [right], [15_000_000])
    pair("zero", [left], [{**right, "val": 0}], [10_000_000])
    pair("both_zero", [{**left, "val": 0}], [{**right, "val": 0}], [0])
    pair("cross_year", [left], [source28_annual_period("1999-12-31", 5_000_000)],
         [None, None], "missing_or_ambiguous_annual_operand")
    pair("different_start", [left],
         [source28_annual_period("2000-12-31", 5_000_000, start="1999-12-01")],
         [None], "matching_annual_period_unproven")
    pair("short_period", [left],
         [source28_annual_period("2000-12-31", 5_000_000, start="2000-10-01")],
         [None], "matching_annual_period_unproven")
    pair("end_only", [left], [{"end": right["end"], "val": right["val"]}],
         [None], "matching_annual_period_unproven")
    pair("missing", [left], [], [None], "missing_or_ambiguous_annual_operand")
    pair("duplicate", [left], [right, deepcopy(right)], [None],
         "missing_or_ambiguous_annual_operand")
    pair("unit_conflict", [left], [{**right, "unit": "shares"}], [None],
         "fact_identity_conflict:unit")
    pair("nonmonetary_unit", [{**left, "unit": "shares"}],
         [{**right, "unit": "shares"}], [None], "annual_sum_unit_not_usd")
    invalid = [
        {"name": "nan", "value": {"special_number": "nan"}},
        {"name": "positive_infinity", "value": {"special_number": "inf"}},
        {"name": "negative_infinity", "value": {"special_number": "-inf"}},
        {"name": "boolean_true", "value": True},
        {"name": "boolean_false", "value": False},
        {"name": "oversized_integer", "value": 10 ** 400},
    ]
    for case in invalid:
        pair(case["name"], [left], [{**right, "val": case["value"]}], [None],
             "annual_sum_value_unavailable")
    pair("overflow", [{**left, "val": 1e308}], [{**right, "val": 1e308}],
         [None], "annual_sum_value_nonfinite")
    pair("newest_unmatched", [source28_annual_period("1999-12-31", 10_000_000), left],
         [source28_annual_period("1999-12-31", 5_000_000)], [15_000_000, None])
    pair("reversed_input", [left, source28_annual_period("1999-12-31", 10_000_000)],
         [right, source28_annual_period("1999-12-31", 5_000_000)], [15_000_000, 15_000_000])
    confidence_invalid = invalid + [
        {"name": "negative", "value": -0.01},
        {"name": "above_hundred", "value": 100.01},
        {"name": "invalid_text", "value": "invalid"},
        {"name": "object", "value": {}},
        {"name": "list", "value": []},
        {"name": "nan_text", "value": "NaN"},
        {"name": "infinity_text", "value": "Infinity"},
    ]
    probability_invalid = invalid + [
        {"name": "negative", "value": -0.01},
        {"name": "above_one", "value": 1.01},
        {"name": "numeric_text", "value": "0.7"},
        {"name": "object", "value": {}},
        {"name": "null", "value": None},
        {"name": "missing", "missing": True},
    ]
    valid = [{"name": name, "value": value, "fraction": fraction}
             for name, value, fraction in [
                 ("zero", 0, 0), ("fraction", 0.7, 0.7), ("one", 1, 1),
                 ("percent", 70, 0.7), ("hundred", 100, 1),
                 ("fraction_text", "0.7", 0.7), ("percent_text", "70", 0.7)]]
    bound = [
        {"name": "consistent_buy", "report": {"rating": "\u4e70\u5165"}, "error": None},
        {"name": "independent_watch", "report": {"rating": "\u89c2\u5bdf"}, "error": None},
        {"name": "ineligible_forged_buy", "valuation_ineligible": True,
         "report": {"rating": "\u4e70\u5165"}, "error": "report_valuation_eligibility_mismatch"},
        {"name": "eligible_claim_mismatch", "report": {"rating": "\u89c2\u5bdf", "eligible": False},
         "error": "report_valuation_eligibility_mismatch"},
        {"name": "basis_mismatch", "report": {"rating": "\u89c2\u5bdf", "basis": "nav"},
         "error": "report_valuation_eligibility_mismatch"},
        {"name": "mos_mismatch", "report": {"rating": "\u4e70\u5165", "mos": 40},
         "error": "report_valuation_mos_mismatch"},
    ]
    concepts = [
        {"name": "monetary_usd", "concept": "NetIncomeLoss", "unit": "USD", "status": "complete"},
        {"name": "monetary_shares", "concept": "NetIncomeLoss", "unit": "shares", "status": "invalid"},
        {"name": "monetary_per_share", "concept": "NetIncomeLoss", "unit": "USD/shares", "status": "invalid"},
        {"name": "monetary_eur", "concept": "NetIncomeLoss", "unit": "EUR", "status": "invalid"},
        {"name": "shares", "concept": "CommonStockSharesOutstanding", "unit": "shares", "status": "complete"},
        {"name": "shares_usd", "concept": "CommonStockSharesOutstanding", "unit": "USD", "status": "invalid"},
        {"name": "eps", "concept": "EarningsPerShareBasic", "unit": "USD/shares", "status": "complete"},
        {"name": "eps_usd", "concept": "EarningsPerShareBasic", "unit": "USD", "status": "invalid"},
    ]
    return {"annual": annual, "confidence_invalid": confidence_invalid,
            "confidence_valid": valid, "probability_invalid": probability_invalid,
            "omitted_confidence": [None, "", "null", "none"],
            "bound": bound, "concepts": concepts, "concept_fact": left,
            "display": [{"name": "null", "value": None}, {"name": "zero", "value": 0},
                        {"name": "positive", "value": 2_000_000}, {"name": "negative", "value": -2_000_000}]}


def source28_regression_source():
    return '\n"""Generated Source28 regressions. Inputs are synthetic; tests call shipped modules."""\nfrom copy import deepcopy\nimport importlib\nimport json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n\nimport pytest\n\nfrom make_fixtures import (source28_scenarios, source28_realize, source28_bound_sample,\n                           source25_equity_basis_scenarios, tracking_quote_scenarios)\nfrom test_private_runs import state\nfrom test_financial_evidence import valuation_module\nfrom test_source22_contracts import modules\nfrom test_tracking_quote_contract import tracker\nfrom test_deepdive_producer_completion import runtime\nimport test_deepdive_producer_completion as producer_tests\n\nCASE = source28_scenarios()\nQUOTE = tracking_quote_scenarios()\n\n\ndef forbidden(*args, **kwargs):\n    pytest.fail("An external acquisition or ledger write was not expected")\n\n\n@pytest.mark.parametrize("case", CASE["bound"], ids=lambda case: case["name"])\ndef test_bound_report_cannot_override_valuation_before_persistence(runtime, valuation_module, monkeypatch, case):\n    sample = source28_bound_sample(case)\n    _, request_path = producer_tests.prepared(runtime, sample, monkeypatch)\n    producer = producer_tests.producer\n    request = json.loads(request_path.read_text(encoding="utf-8"))\n    snapshots = {Path(row[key]): Path(row[key]).read_bytes()\n                 for row in request["candidates"] for key in ("json_path", "valuation_path")}\n    block = json.loads(Path(request["candidates"][0]["valuation_path"]).read_text(encoding="utf-8"))\n    assert block["mos_basis"] == "fcf_cap"\n    assert block["buy_eligible"] is (not case.get("valuation_ineligible", False))\n    assert block["margin_of_safety_pct"] == 0.3889\n    result_path = producer_tests.response(runtime, sample, request_path, "success")\n    output, reports, completion = producer.persist_fanout_result(request_path, result_path)\n    rows = json.loads(output.read_text(encoding="utf-8"))["all"]\n    first, peer = rows\n    assert peer["report_status"] == "complete"\n    assert peer["report"]["rating"] == "\\u89c2\\u5bdf"\n    assert completion["status"] == "partial"\n    first_path = request_path.parent / ("report_" + first["ticker"] + ".md")\n    if case["error"]:\n        assert first["report_status"] == "error"\n        assert first["error_code"] == case["error"]\n        assert "report" not in first\n        assert not first_path.exists()\n        assert len(reports) == 1\n    else:\n        assert first["report_status"] == "complete"\n        assert first["report"]["rating"] == case["report"]["rating"]\n        assert first_path.read_text(encoding="utf-8") == first["report"]["report_md"]\n        assert len(reports) == 2\n        receipt = producer_tests.stages.read_stage_receipt(first_path, 1)\n        assert receipt["valuation_artifact"] == producer._binding(\n            Path(request["candidates"][0]["valuation_path"]))\n    assert {path: path.read_bytes() for path in snapshots} == snapshots\n\n\n@pytest.mark.parametrize("case", CASE["annual"], ids=lambda case: case["name"])\ndef test_annual_ebitda_requires_compatible_periods_units_and_values(valuation_module, case):\n    evidence = importlib.import_module("_cash_flow_evidence")\n    data = source28_realize(deepcopy(case))\n    periods = evidence.paired_annual_sum_evidence(data["left"], data["right"])\n    assert [row["val"] for row in periods] == data["values"]\n    assert [row["qualified"] for row in periods] == [value is not None for value in data["values"]]\n    if data["reason"] is not None:\n        assert all(row["reason"] == data["reason"] for row in periods)\n    rows, incomplete = valuation_module._build_ebitda_series(data["left"], data["right"])\n    assert rows == [{"end": row["end"], "val": row["val"]} for row in periods if row["qualified"]]\n    assert incomplete == sum(value is None for value in data["values"])\n    assert all(set(row["operands"]) == {"ebit", "dep_amort"} for row in periods)\n\n\n@pytest.mark.parametrize("case", CASE["annual"], ids=lambda case: case["name"])\ndef test_pretax_addback_uses_the_same_qualified_annual_pairing(modules, monkeypatch, case):\n    concepts = importlib.import_module("_deepdive_concepts")\n    data = source28_realize(deepcopy(case))\n    monkeypatch.setattr(concepts.time, "sleep", lambda *_: None)\n    monkeypatch.setattr(concepts, "concept_series",\n                        lambda cik, tags, **kwargs: deepcopy(\n                            data["left"] if tags == concepts.EBIT_PRETAX_CONCEPTS else data["right"]))\n    rows, source = concepts._ebit_with_source("0000000001", [])\n    ends = sorted({row["end"] for row in data["left"] + data["right"]})\n    expected = dict(zip(ends, data["values"]))\n    qualified = {end: value for end, value in expected.items() if value is not None}\n    assert source == ("pretax+interest_addback" if qualified else "pretax_proxy")\n    assert len(rows) == len(data["left"])\n    for row, original in zip(rows, data["left"]):\n        assert row["val"] == qualified.get(original["end"], original["val"])\n        assert row.get("start") == original.get("start")\n        if original["end"] in qualified:\n            assert set(row["operands"]) == {"pretax", "interest"}\n            assert row["operands"]["pretax"]["start"] == row["operands"]["interest"]["start"]\n\n\n@pytest.mark.parametrize("case", CASE["concepts"], ids=lambda case: case["name"])\ndef test_concept_unit_selection_preserves_annual_identity(modules, monkeypatch, case):\n    concepts = importlib.import_module("_deepdive_concepts")\n    fact = deepcopy(CASE["concept_fact"])\n    fact["accn"] = "synthetic-accession"\n    payload = {"cik": 123, "taxonomy": "us-gaap", "tag": case["concept"],\n               "units": {case["unit"]: [fact]}}\n    monkeypatch.setattr(concepts, "http_get",\n                        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: payload))\n    rows = concepts._one_concept("0000000123", case["concept"], asof="2001-03-01")\n    assert rows.completion["status"] == case["status"]\n    if case["status"] == "complete":\n        assert len(rows) == 1 and rows[0]["val"] == fact["val"]\n        assert rows[0]["unit"] == case["unit"]\n        assert rows[0]["cik"] == "0000000123"\n        assert rows[0]["concept"] == case["concept"]\n        assert rows[0]["accn"] == fact["accn"]\n        if case["concept"] != "CommonStockSharesOutstanding":\n            assert rows[0]["start"] == fact["start"]\n            assert rows[0]["duration_days"] == fact["duration_days"]\n    else:\n        assert rows == []\n\n\ndef test_depreciation_cascade_keeps_period_and_accession(modules, monkeypatch):\n    concepts = importlib.import_module("_deepdive_concepts")\n    fact = deepcopy(CASE["concept_fact"])\n    fact["accn"] = "synthetic-accession"\n    monkeypatch.setattr(concepts.time, "sleep", lambda *_: None)\n    monkeypatch.setattr(concepts, "_one_concept",\n                        lambda cik, tag, **kwargs: [deepcopy(fact)] if tag == concepts.DA_CONCEPTS[0] else [])\n    rows, source = concepts._da_series("0000000001")\n    assert source == concepts.DA_CONCEPTS[0]\n    assert rows[0]["start"] == fact["start"]\n    assert rows[0]["end"] == fact["end"]\n    assert rows[0]["accn"] == fact["accn"]\n\n\n@pytest.mark.parametrize("case", CASE["confidence_invalid"], ids=lambda case: case["name"])\ndef test_json_confidence_preflight_rejects_later_invalid_row_before_quotes_or_writes(\n        tracker, monkeypatch, tmp_path, case):\n    value = source28_realize(case["value"])\n    rows = [dict(QUOTE["record_payload"], confidence=0.7),\n            dict(QUOTE["record_payload"], ticker="SYNQ2", confidence=value)]\n    path = tmp_path / "synthetic-verdicts.json"\n    path.write_text(json.dumps(rows), encoding="utf-8")\n    monkeypatch.setattr(tracker, "_quote_on", forbidden)\n    monkeypatch.setattr(tracker, "_append_verdict", forbidden)\n    monkeypatch.setattr(tracker, "_load_verdicts", forbidden)\n    with pytest.raises(ValueError, match="Confidence"):\n        tracker.cmd_record(SimpleNamespace(record_path=str(path)))\n\n\n@pytest.mark.parametrize("case", CASE["confidence_invalid"], ids=lambda case: case["name"])\ndef test_flag_confidence_rejects_invalid_domain_before_quote(tracker, monkeypatch, case):\n    flags = dict(QUOTE["flags"], confidence=source28_realize(case["value"]))\n    monkeypatch.setattr(tracker, "_quote_on", forbidden)\n    with pytest.raises(ValueError, match="Confidence"):\n        tracker._build_verdict_from_flags(SimpleNamespace(**flags))\n\n\n@pytest.mark.parametrize("rating,direction", [("\\u4e70\\u5165", 1), ("\\u89c2\\u5bdf", 0), ("\\u907f\\u5f00", -1)])\n@pytest.mark.parametrize("case", CASE["confidence_valid"], ids=lambda case: case["name"])\ndef test_valid_confidence_units_direction_and_storage_are_preserved(tracker, monkeypatch, case, rating, direction):\n    flags = dict(QUOTE["flags"], rating=rating, confidence=case["value"])\n    calls = []\n    def quote(ticker, date, verbose=False):\n        calls.append((ticker, date))\n        return deepcopy(QUOTE["entry_quotes"][ticker])\n    monkeypatch.setattr(tracker, "_quote_on", quote)\n    row = tracker._build_verdict_from_flags(SimpleNamespace(**flags))\n    expected = min(0.999, max(0.001, 0.5 + direction * (case["fraction"] - 0.5)))\n    assert row["confidence"] == float(case["value"])\n    assert row["implied_prob"] == pytest.approx(expected)\n    assert len(calls) == 2\n\n\n@pytest.mark.parametrize("value", CASE["omitted_confidence"])\n@pytest.mark.parametrize("rating", ["\\u4e70\\u5165", "\\u89c2\\u5bdf", "\\u907f\\u5f00"])\ndef test_omitted_confidence_keeps_rating_fallback(tracker, value, rating):\n    assert tracker._implied_prob_from_confidence(rating, value) == tracker.RATING_PROB[rating]\n\n\n@pytest.mark.parametrize("case", CASE["probability_invalid"], ids=lambda case: case["name"])\ndef test_invalid_stored_probability_stays_unscored_without_return_snapshots(tracker, monkeypatch, case):\n    row = deepcopy(QUOTE["base_row"])\n    if case.get("missing"):\n        row.pop("implied_prob")\n    else:\n        row["implied_prob"] = source28_realize(case["value"])\n    saved = []\n    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])\n    monkeypatch.setattr(tracker, "_save_verdicts", lambda rows: saved.append(deepcopy(rows)))\n    monkeypatch.setattr(tracker, "_fetch_return_snapshot", forbidden)\n    tracker.cmd_score(SimpleNamespace())\n    expected = "missing_implied_prob" if case.get("missing") or case.get("value") is None else "invalid_implied_prob"\n    assert saved and saved[0][0]["scored"] is False\n    assert saved[0][0]["brier"] is None\n    assert saved[0][0]["score_unavailable_reason"] == expected\n\n\n@pytest.mark.parametrize("probability", [0, 0.7, 1])\ndef test_valid_probability_boundaries_score_with_finite_brier(tracker, monkeypatch, probability):\n    row = deepcopy(QUOTE["base_row"])\n    row["implied_prob"] = probability\n    calls, saved = [], []\n    def snapshot(ticker, entry, horizon):\n        calls.append(ticker)\n        entry_quote = row["entry_quote"] if ticker == row["ticker"] else row["benchmark_entry_quote"]\n        return {"available": True, "return_fraction": 0.2 if ticker == row["ticker"] else 0.1,\n                "entry_quote": deepcopy(entry_quote), "horizon_quote": {"resolved_date": horizon}}\n    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])\n    monkeypatch.setattr(tracker, "_save_verdicts", lambda rows: saved.append(deepcopy(rows)))\n    monkeypatch.setattr(tracker, "_fetch_return_snapshot", snapshot)\n    tracker.cmd_score(SimpleNamespace())\n    assert calls == [row["ticker"], row["benchmark"]]\n    assert saved[0][0]["scored"] is True\n    assert saved[0][0]["brier"] == pytest.approx(round((probability - 1) ** 2, 6))\n\n\ndef test_zero_primary_mos_is_not_replaced_by_alternate_value(tracker, monkeypatch, tmp_path):\n    path = tmp_path / "synthetic-verdict.json"\n    path.write_text(json.dumps(dict(QUOTE["record_payload"], margin_of_safety_pct=0, mos_pct=40)),\n                    encoding="utf-8")\n    monkeypatch.setattr(tracker, "_quote_on",\n                        lambda ticker, *args, **kwargs: deepcopy(QUOTE["entry_quotes"][ticker]))\n    assert tracker._build_verdicts_from_json(path)[0]["mos_pct"] == 0\n\n\n@pytest.mark.parametrize("case", CASE["display"], ids=lambda case: case["name"])\ndef test_ranking_and_report_distinguish_zero_from_unavailable(modules, state, case):\n    report = importlib.import_module("make_report")\n    directory = Path(state["root"])\n    directory.mkdir(parents=True, exist_ok=True)\n    data = {"ticker": "SYNTH", "derived": {name: case["value"]\n            for name in ("latest_revenue", "latest_net_income", "latest_ocf")}}\n    (directory / "deepdive_SYNTH_2000-01-01.json").write_text(json.dumps(data), encoding="utf-8")\n    hard = modules["rank"].load_hard_data("SYNTH", directory)\n    number = None if case["value"] is None else round(case["value"] / 1e6, 1)\n    assert [hard[name] for name in ("revenue_M", "net_income_M", "ocf_M")] == [number] * 3\n    rendered = report.render_report(data, {}, "2000-01-01")\n    text = "N/A" if number is None else f"{number:.1f}M"\n    assert f"latest rev {text}, NI {text}, OCF {text}" in rendered\n    assert "Base rate: unknown until supported" in rendered\n\n\n@pytest.mark.parametrize("case", CASE["display"][:2], ids=lambda case: case["name"])\ndef test_valuation_summary_distinguishes_zero_from_unavailable(valuation_module, capsys, case):\n    block = dict(ticker="SYNTH", **{name: case["value"]\n                 for name in ("market_cap", "ev", "normalized_ebitda", "normalized_fcf")})\n    valuation_module._print_valuation_summary(block)\n    output = capsys.readouterr().out\n    if case["value"] is None:\n        for reason in ("market_cap_unavailable", "ev_unavailable",\n                       "normalized_ebitda_unavailable", "normalized_fcf_unavailable"):\n            assert "null (" + reason + ")" in output\n        assert "$0M" not in output\n    else:\n        assert output.count("$0M") == 4\n\n\n@pytest.mark.parametrize("case", source25_equity_basis_scenarios(), ids=lambda case: case["name"])\ndef test_original_18m_and_separate_20m_equity_controls_stay_distinct(valuation_module, case):\n    result = valuation_module.compute_valuation(deepcopy(case["data"]), case["market_cap"],\n                                               dict(valuation_module._VALUATION_DEFAULTS))\n    expected_fcf = 18_000_000 if case["name"] == "original_18m" else 20_000_000\n    assert result["normalized_fcf"] == expected_fcf\n    assert result["intrinsic_value_band"]["equity_low"] == case["equity_low"]\n    assert result["margin_of_safety_pct"] == case["mos"]\n    assert (result["buy_eligible"] and result["margin_of_safety_pct"] >= 0.30) is case["meets_threshold"]\n\n\n@pytest.mark.parametrize("case", CASE["confidence_valid"], ids=lambda case: case["name"])\ndef test_json_preserves_valid_confidence_units(tracker, monkeypatch, tmp_path, case):\n    path = tmp_path / "synthetic-confidence.json"\n    path.write_text(json.dumps(dict(QUOTE["record_payload"], confidence=case["value"])), encoding="utf-8")\n    monkeypatch.setattr(tracker, "_quote_on",\n                        lambda ticker, *args, **kwargs: deepcopy(QUOTE["entry_quotes"][ticker]))\n    row = tracker._build_verdicts_from_json(path)[0]\n    assert row["confidence"] == float(case["value"])\n    assert row["implied_prob"] == pytest.approx(min(0.999, max(0.001, case["fraction"])))\n\n\n@pytest.mark.parametrize("case", CASE["probability_invalid"], ids=lambda case: case["name"])\ndef test_brier_defends_its_probability_domain(tracker, case):\n    value = source28_realize(case.get("value"))\n    with pytest.raises(ValueError, match="probability"):\n        tracker._brier(value, True)\n\n\n@pytest.mark.parametrize("case", CASE["annual"], ids=lambda case: case["name"])\ndef test_valuation_uses_annual_ebitda_evidence_over_stale_derived_scalar(valuation_module, case):\n    data = deepcopy(source25_equity_basis_scenarios()[1]["data"])\n    operands = source28_realize(deepcopy(case))\n    data["financials"]["ebit"] = operands["left"]\n    data["financials"]["dep_amort"] = operands["right"]\n    result = valuation_module.compute_valuation(data, 120_000_000,\n                                               dict(valuation_module._VALUATION_DEFAULTS))\n    expected = operands["values"][-1]\n    assert result["latest_ebitda_evidence"]["val"] == expected\n    if expected is None or expected == 0:\n        assert result["ev_ebitda"] is None\n'



def source29_scenarios():
    """Synthetic zero-cash and discovery-provenance regression inputs."""
    candidate = {"ticker": "SYNTHA", "cik": "9000000001", "name": "AcmeCorp Synthetic",
                 "sic": "3714", "band": "deep", "mktcap": 100000000,
                 "health_score": 60, "killflag_count": 0, "avg_dollar_vol": 3000000,
                 "business_blurb": "Synthetic machinery and components.",
                 "theme": "synthetic machinery", "theme_slug": "synthetic"}
    flags = {"kf_scanned": True, "disclosure_review_required": False,
             "kf_going_concern": False, "kf_substantial_doubt": False,
             "kf_material_weakness": False, "kf_death_spiral": False,
             "kf_reverse_split": False, "concentration_flag": ""}
    cash = [
        {"name": "missing-cash", "cash": None, "ocf": -2000000, "runway": None, "reject": False},
        {"name": "zero-cash-burning", "cash": 0, "ocf": -2000000, "runway": 0.0, "reject": True},
        {"name": "one-dollar-burning", "cash": 1, "ocf": -2000000, "runway": 0.0, "reject": True},
        {"name": "partial-period", "cash": 500000, "ocf": -2000000, "runway": 0.2, "reject": True},
        {"name": "one-period", "cash": 2000000, "ocf": -2000000, "runway": 1.0, "reject": False},
        {"name": "two-periods", "cash": 4000000, "ocf": -2000000, "runway": 2.0, "reject": False},
        {"name": "negative-cash", "cash": -2000000, "ocf": -2000000, "runway": -1.0, "reject": True},
        {"name": "zero-ocf", "cash": 0, "ocf": 0, "runway": None, "reject": False},
        {"name": "positive-ocf", "cash": 0, "ocf": 2000000, "runway": None, "reject": False},
        {"name": "missing-ocf", "cash": 0, "ocf": None, "runway": None, "reject": False},
    ]
    channels = [
        {"name": "fts", "input": "fts", "expected": "fts", "fts": True, "sic": False},
        {"name": "sic-only", "input": "sic_reverse", "expected": "sic_reverse", "fts": False, "sic": True},
        {"name": "both", "input": "both", "expected": "both", "fts": True, "sic": True},
        {"name": "legacy-sic", "input": "sic", "expected": "sic", "fts": False, "sic": True},
        {"name": "missing-column", "missing": True, "input": None, "expected": "unknown", "fts": False, "sic": False},
        {"name": "null-cell", "input": None, "expected": "unknown", "fts": False, "sic": False},
        {"name": "empty-cell", "input": "", "expected": "unknown", "fts": False, "sic": False},
        {"name": "unrecognized", "input": "unrecorded", "expected": "unknown", "fts": False, "sic": False},
    ]

    resume_row = {"ticker": "SYNTHA", "cik": "9000000001", "asof": "2025-01-01",
                  "year": "2025", "theme": "synthetic machinery", "series": {"cash": []}}
    resume_invalid = [
        {"name": "malformed-json", "content": "{"},
        {"name": "object-envelope", "content": "{}"},
        {"name": "null-envelope", "content": "null"},
        {"name": "scalar-envelope", "content": json.dumps("synthetic")},
        {"name": "scalar-row", "content": json.dumps([1])},
        {"name": "missing-ticker", "content": json.dumps([{"asof": "2025-01-01"}])},
        {"name": "missing-asof", "content": json.dumps([{"ticker": "SYNTHA"}])},
        {"name": "empty-ticker", "content": json.dumps([{"ticker": " ", "asof": "2025-01-01"}])},
        {"name": "non-string-asof", "content": json.dumps([{"ticker": "SYNTHA", "asof": 2025}])},
        {"name": "valid-prefix-invalid-tail", "content": json.dumps([resume_row, {}])},
    ]
    resume_valid = [
        {"name": "absent", "exists": False, "rows": []},
        {"name": "valid-empty", "exists": True, "rows": []},
        {"name": "valid-observations", "exists": True, "rows": [resume_row]},
    ]
    return {"resume_row": resume_row, "resume_invalid": resume_invalid, "resume_valid": resume_valid, "candidate": candidate, "flags": flags, "cash": cash, "channels": channels,
            "net_income": -1000000, "revenue": 3000000,
            "judgment": {"judgment_status": "complete", "theme_fit": "pure_play",
                         "reason": "Synthetic company makes the theme product.",
                         "real_business": "Synthetic machinery"}}


def source29_regression_source():
    return '\n"""Generated Source29 regressions. All company and financial inputs are synthetic."""\nfrom copy import deepcopy\nimport importlib\nimport json\nfrom pathlib import Path\nimport sys\n\nimport pandas as pd\nimport pytest\n\nfrom make_fixtures import source29_scenarios\nfrom test_private_runs import state\n\nCASE = source29_scenarios()\n\n\n@pytest.fixture\ndef runtime(state, monkeypatch, tmp_path):\n    for name in ("filter_by_sic", "run_theme", "cheap_pass", "_recall"):\n        monkeypatch.delitem(sys.modules, name, raising=False)\n    stages = importlib.import_module("filter_by_sic")\n    theme = importlib.import_module("run_theme")\n    cheap = importlib.import_module("cheap_pass")\n    recall = importlib.import_module("_recall")\n\n    def output(path):\n        path = Path(path)\n        path.parent.mkdir(parents=True, exist_ok=True)\n        return path\n\n    monkeypatch.setattr(stages, "prepare_output", output)\n    monkeypatch.setattr(theme, "REPORTS", tmp_path)\n    monkeypatch.setattr(theme, "CFG", {"sic_hard_exclude": []})\n    monkeypatch.setattr(cheap.time, "sleep", lambda *_: None)\n    return {"theme": theme, "cheap": cheap, "recall": recall, "stages": stages,\n            "directory": tmp_path}\n\n\n@pytest.mark.parametrize("case", CASE["cash"], ids=lambda case: case["name"])\ndef test_observed_zero_cash_reaches_the_existing_burn_rejection(runtime, monkeypatch, case):\n    cheap = runtime["cheap"]\n    values = {"CashAndCashEquivalentsAtCarryingValue": case["cash"],\n              "NetCashProvidedByUsedInOperatingActivities": case["ocf"],\n              "NetIncomeLoss": CASE["net_income"], "Revenues": CASE["revenue"]}\n    monkeypatch.setattr(cheap, "get_concept_series",\n                        lambda _cik, concept: [] if values[concept] is None else [{"val": values[concept]}])\n    monkeypatch.setattr(cheap, "killflag_scan", lambda _ticker: deepcopy(CASE["flags"]))\n    observed = cheap.health_check(deepcopy(CASE["candidate"]))\n    assert observed["cash"] == case["cash"]\n    assert observed["runway_periods"] == case["runway"]\n    scored = cheap.score(pd.DataFrame([observed])).iloc[0]\n    assert bool(scored["reject_burn"]) is case["reject"]\n    assert bool(scored["rejected"]) is case["reject"]\n\n\ndef candidate_artifact(runtime, case, cheap_shadow):\n    theme, stages = runtime["theme"], runtime["stages"]\n    source = deepcopy(CASE["candidate"])\n    universe = {key: source[key] for key in ("ticker", "cik", "sic", "mktcap", "band")}\n    if not case.get("missing"):\n        universe["recall_channel"] = case["input"]\n    screened = {key: source[key] for key in\n                ("ticker", "name", "mktcap", "health_score", "killflag_count", "avg_dollar_vol", "business_blurb")}\n    screened["rejected"] = False\n    if cheap_shadow:\n        screened["recall_channel"] = "fts" if case["input"] != "fts" else "sic_reverse"\n    universe_path = runtime["directory"] / "synthetic-universe.csv"\n    cheap_path = runtime["directory"] / "synthetic-cheap.csv"\n    pd.DataFrame([universe]).to_csv(universe_path, index=False)\n    pd.DataFrame([screened]).to_csv(cheap_path, index=False)\n    discovery = stages.stage_completion("discover", 1, work=[stages.stage_work("synthetic_discovery")])\n    stages.write_stage_receipt(universe_path, discovery)\n    screening = stages.stage_completion("cheap_pass", 1, work=[stages.stage_work("synthetic_screening")],\n                                         upstream=[discovery])\n    screening["input_artifact"] = str(universe_path.resolve())\n    screening["decisions"] = [{"input_index": 0, "ticker": source["ticker"], "cik": source["cik"],\n                               "band": source["band"], "screening_decision": "retained"}]\n    stages.write_stage_receipt(cheap_path, screening)\n    return theme.stage_sic_filter(cheap_path, universe_path, source["theme_slug"], source["theme"])\n\n\n@pytest.mark.parametrize("case", CASE["channels"], ids=lambda case: case["name"])\n@pytest.mark.parametrize("cheap_shadow", [False, True], ids=["no-shadow", "conflicting-cheap-channel"])\ndef test_universe_channel_reaches_gate2_and_recall_accounting(runtime, case, cheap_shadow):\n    theme, stages, recall = runtime["theme"], runtime["stages"], runtime["recall"]\n    path = candidate_artifact(runtime, case, cheap_shadow)\n    candidate, = json.loads(path.read_text(encoding="utf-8"))\n    assert candidate["recall_channel"] == case["expected"]\n    assert candidate["ticker"] == CASE["candidate"]["ticker"]\n    request_path = theme.prepare_gate2_request(path)\n    request = json.loads(request_path.read_text(encoding="utf-8"))\n    assert request["candidates"][0]["recall_channel"] == case["expected"]\n    judgment = {**request["candidates"][0], **CASE["judgment"]}\n    response_path = runtime["directory"] / "synthetic-gate-response.json"\n    response_path.write_text(json.dumps({"schema": "smallcap.gate2.result.v1",\n        "input": request["input"], "all": [judgment]}), encoding="utf-8")\n    output, survivors, completion = theme.persist_gate2_result(request_path, response_path)\n    records, receipt = theme.read_gate2_results(runtime["directory"])\n    assert receipt["status"] == completion["status"] == "complete"\n    assert records[0]["recall_channel"] == case["expected"]\n    assert json.loads(output.read_text(encoding="utf-8"))[0]["recall_channel"] == case["expected"]\n    survivor, = json.loads(survivors.read_text(encoding="utf-8"))\n    assert survivor["recall_channel"] == case["expected"]\n    final, fts_count, channels = recall._recall_set_from_candidate_files([survivors])\n    ticker = CASE["candidate"]["ticker"]\n    assert final == {ticker}\n    assert fts_count == int(case["fts"])\n    assert channels["fts"] == ({ticker} if case["fts"] else set())\n    assert channels["sic"] == ({ticker} if case["sic"] else set())\n    assert stages.read_stage_receipt(survivors, 1)["status"] == "complete"\n\n\n@pytest.mark.parametrize("case", CASE["channels"], ids=lambda case: case["name"])\ndef test_gate2_omission_and_missing_result_preserve_bound_provenance(runtime, case):\n    theme = runtime["theme"]\n    candidate = {**deepcopy(CASE["candidate"]), "recall_channel": case["expected"]}\n    row = {key: candidate[key] for key in ("ticker", "cik", "band")}\n    row.update(input_index=0, **CASE["judgment"])\n    assert "recall_channel" not in row\n    completed, = theme._gate2_rows([candidate], [row])\n    missing, = theme._gate2_rows([candidate], [], allow_missing=True)\n    assert completed["recall_channel"] == missing["recall_channel"] == case["expected"]\n    assert missing["judgment_status"] == "error"\n    assert missing["error_code"] == "missing_result"\n\n\n@pytest.mark.parametrize("case", CASE["channels"], ids=lambda case: case["name"])\ndef test_gate2_cannot_rebind_a_discovery_channel(runtime, case):\n    candidate = {**deepcopy(CASE["candidate"]), "recall_channel": case["expected"]}\n    replacement = "sic_reverse" if case["expected"] == "fts" else "fts"\n    row = {**candidate, "input_index": 0, **CASE["judgment"], "recall_channel": replacement}\n    with pytest.raises(ValueError, match="recall channel"):\n        runtime["theme"]._gate2_rows([candidate], [row])\n\n@pytest.fixture\ndef historical_extractor(state, monkeypatch, tmp_path):\n    import importlib.util\n\n    path = Path(__file__).resolve().parents[2] / "docs/backtest-2026-06/distress_features_extract.py"\n    spec = importlib.util.spec_from_file_location("synthetic_distress_extractor", path)\n    module = importlib.util.module_from_spec(spec)\n    spec.loader.exec_module(module)\n    artifact = tmp_path / "synthetic-feature-ledger.json"\n    monkeypatch.setattr(module, "features_path", lambda: artifact)\n    monkeypatch.setattr(module, "backtest_files", lambda: [])\n    monkeypatch.setattr(module, "prepare_output", lambda path: path)\n    return module, artifact\n\n\n@pytest.mark.parametrize("case", CASE["resume_invalid"], ids=lambda case: case["name"])\ndef test_invalid_existing_feature_ledger_fails_before_write(historical_extractor, monkeypatch, case):\n    module, artifact = historical_extractor\n    previous = case["content"].encode("utf-8")\n    artifact.write_bytes(previous)\n\n    def unexpected(*_args, **_kwargs):\n        pytest.fail("Invalid resume evidence reached a worker or output write")\n\n    monkeypatch.setattr(module, "ThreadPoolExecutor", unexpected)\n    monkeypatch.setattr(module, "write_features", unexpected)\n    with pytest.raises(ValueError):\n        module.main()\n    assert artifact.read_bytes() == previous\n\n\ndef test_unreadable_existing_feature_ledger_fails_before_write(historical_extractor, monkeypatch):\n    module, artifact = historical_extractor\n    previous = json.dumps([CASE["resume_row"]]).encode("utf-8")\n    artifact.write_bytes(previous)\n\n    def unreadable():\n        raise PermissionError("Synthetic unreadable feature artifact")\n\n    def unexpected(*_args, **_kwargs):\n        pytest.fail("Unreadable resume evidence reached a worker or output write")\n\n    monkeypatch.setattr(module, "load_features", unreadable)\n    monkeypatch.setattr(module, "ThreadPoolExecutor", unexpected)\n    monkeypatch.setattr(module, "write_features", unexpected)\n    with pytest.raises(PermissionError):\n        module.main()\n    assert artifact.read_bytes() == previous\n\n\n@pytest.mark.parametrize("case", CASE["resume_valid"], ids=lambda case: case["name"])\ndef test_valid_or_absent_feature_ledger_retains_resume_behavior(historical_extractor, monkeypatch, case):\n    module, artifact = historical_extractor\n    if case["exists"]:\n        artifact.write_text(json.dumps(case["rows"]), encoding="utf-8")\n\n    class EmptyPool:\n        def __init__(self, **_kwargs):\n            pass\n\n        def __enter__(self):\n            return self\n\n        def __exit__(self, *_args):\n            return False\n\n        def submit(self, *_args, **_kwargs):\n            pytest.fail("No new rows should be fetched in this synthetic resume case")\n\n    monkeypatch.setattr(module, "ThreadPoolExecutor", EmptyPool)\n    module.main()\n    assert json.loads(artifact.read_text(encoding="utf-8")) == case["rows"]\n'



def source30_scenarios():
    """Synthetic source-label contracts; no claimed filing identity."""
    return {'schema': 'smallcap.source30.synthetic-prompt-contracts.v1', 'channels': ['fts', 'sic_reverse', 'sic', 'both', 'unknown'], 'forms': ['10-K', '10-Q', '20-F', '40-F'], 'workflows': [{'path': 'workflows/theme-fit-gate.js', 'generic_source': 'SEC filing'}, {'path': 'workflows/deepdive-fanout.js', 'generic_source': 'SEC 披露文件'}], 'theme_gate': 'workflows/theme-fit-gate.js'}


def source30_regression_source():
    return '"""Generated Source30 prompt provenance contracts; no provider calls."""\nimport json\nfrom pathlib import Path\nimport re\nimport pytest\nfrom make_fixtures import source30_scenarios\n\nCASE = source30_scenarios()\nROOT = Path(__file__).resolve().parents[2]\n\ndef _recall_messages(source):\n    block = source.split("const recallSource = c => {", 1)[1].split("\\n}", 1)[0]\n    pairs = re.findall(r\'case "([^"]+)": return ("(?:\\\\.|[^"\\\\])*")\', block)\n    messages = {channel: json.loads(raw) for channel, raw in pairs}\n    assert len(pairs) == len(messages) == 4\n    raw_default, = re.findall(r\'default: return ("(?:\\\\.|[^"\\\\])*")\', block)\n    messages["unknown"] = json.loads(raw_default)\n    assert set(messages) == set(CASE["channels"])\n    return messages\n\ndef _assert_source_neutral(message):\n    assert not any(form in message for form in CASE["forms"])\n    assert not re.search(r"\\bItem\\s+[14]\\b", message, re.IGNORECASE)\n\ndef _blurb_parts(source):\n    block = source.split("  const blurbSection = hasBlurb\\n", 1)[1].split("\\n\\n", 1)[0]\n    provided, missing = block.split("\\n", 1)\n    return {"provided": provided, "missing": missing}\n\n@pytest.mark.parametrize("workflow", CASE["workflows"], ids=lambda case: case["path"])\n@pytest.mark.parametrize("channel", CASE["channels"])\ndef test_discovery_channel_does_not_invent_a_filing_form(workflow, channel):\n    source = (ROOT / workflow["path"]).read_text(encoding="utf-8")\n    message = _recall_messages(source)[channel]\n    _assert_source_neutral(message)\n    assert workflow["generic_source"] in message\n    if channel in ("sic", "sic_reverse", "both"):\n        assert "SIC" in message\n\n@pytest.mark.parametrize("part", ["provided", "missing"])\ndef test_business_excerpt_prompt_does_not_invent_a_form_or_item(part):\n    source = (ROOT / CASE["theme_gate"]).read_text(encoding="utf-8")\n    message = _blurb_parts(source)[part]\n    _assert_source_neutral(message)\n    assert "SEC filing" in message\n    if part == "provided":\n        assert "c.business_blurb.slice(0, 2000)" in message\n        assert "PRIMARY" in message\n    else:\n        assert "No SEC filing" in message\n\ndef test_business_excerpt_description_keeps_the_same_source_contract():\n    source = (ROOT / CASE["theme_gate"]).read_text(encoding="utf-8")\n    metadata = source.split("const invalidInput", 1)[0]\n    comment = source.split("  // business_blurb:", 1)[1].split("  const hasBlurb", 1)[0]\n    _assert_source_neutral(metadata)\n    _assert_source_neutral(comment)\n    assert "SEC filing" in metadata\n    assert "SEC filing" in comment\n'



def source31_valuation_config():
    return {'wacc': 0.1, 'cap_rate_low': 0.09, 'cap_rate_high': 0.12, 'normalize_years': 5, 'cyclical_cv_threshold': 0.25}


def source31_scenarios():
    return json.loads('{"concentration": [{"name": "total_customer", "text": "Our largest customer represented 80% of total revenue.", "customer": 80, "program": null, "flag": "kill"}, {"name": "later_segment", "text": "Our largest customer represented 80% of total revenue. Sales represented 10% of our Retail segment revenue.", "customer": 80, "program": null, "flag": "kill"}, {"name": "earlier_segment", "text": "Sales represented 10% of our Retail segment revenue. Our largest customer represented 80% of total revenue.", "customer": 80, "program": null, "flag": "kill"}, {"name": "later_segment_no_percentage", "text": "Our largest customer represented 80% of total revenue. Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "later_segment_after_sales", "text": "Our largest customer represented 80% of total sales. Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "true_segment", "text": "Our largest customer represented 80% of our Retail segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "collapsed_segment", "text": "Our largest customer represented 80% ofRetail Branch Division\\u2019s revenue.", "customer": null, "program": null, "flag": null}, {"name": "decimal_prior_customer", "text": "Our largest customer represented 5.5% of consolidated revenue. Approximately100% ofRetail Branch Division\\u2019s revenue came from domestic sales.", "customer": 5.5, "program": null, "flag": null}, {"name": "true_possessive", "text": "Our largest customer represented 80% of AcmeCorp Retail\\u2019s revenue.", "customer": null, "program": null, "flag": null}, {"name": "later_possessive", "text": "Our largest customer represented 80% of total revenue. Sales represented 10% of AcmeCorp Retail\\u2019s revenue.", "customer": 80, "program": null, "flag": "kill"}, {"name": "program_later_segment", "text": "Our sole program represented 70% of total revenue. Sales represented 10% of our Retail segment revenue.", "customer": null, "program": 70, "flag": "kill"}, {"name": "program_earlier_segment", "text": "Sales represented 10% of our Retail segment revenue. Our sole program represented 70% of total revenue.", "customer": null, "program": 70, "flag": "kill"}, {"name": "diversified", "text": "Our top 20 customers represented 83% of total revenue.", "customer": null, "program": null, "flag": null}, {"name": "named_revenue_segment", "text": "Our largest customer represented 80% of our Revenue Systems segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "named_sales_segment", "text": "Our largest customer represented 80% of our Sales Systems segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "named_revenue_possessive", "text": "Our largest customer represented 80% of Revenue Systems\\u2019 revenue.", "customer": null, "program": null, "flag": null}, {"name": "acronym_segment", "text": "Our largest customer represented 80% of our U.S. Retail segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "space_before_percent", "text": "Our largest customer represented 80 % of total revenue. Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "plural_possessive", "text": "Our largest customer represented 80% of AcmeCorp Services\\u2019 revenue.", "customer": null, "program": null, "flag": null}, {"name": "customer_watch_boundary", "text": "Our largest customer represented 40% of total revenue. Retail segment revenue was stable.", "customer": 40, "program": null, "flag": "watch"}, {"name": "customer_kill_decimal", "text": "Our largest customer represented 40.1% of total revenue. Retail segment revenue was stable.", "customer": 40.1, "program": null, "flag": "kill"}, {"name": "program_watch_boundary", "text": "Our sole program represented 60% of total revenue. Retail segment revenue was stable.", "customer": null, "program": 60, "flag": "watch"}, {"name": "program_kill_decimal", "text": "Our sole program represented 60.1% of total revenue. Retail segment revenue was stable.", "customer": null, "program": 60.1, "flag": "kill"}, {"name": "both_classes", "text": "Our largest customer represented 80% of total revenue. Our sole program represented 70% of total revenue. Sales represented 10% of our Retail segment revenue.", "customer": 80, "program": 70, "flag": "kill"}, {"name": "comma_clause", "text": "Our largest customer represented 80% of total revenue, while Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "multiline", "text": "Our largest customer represented 80% of total revenue.\\nRetail segment revenue was stable.\\nSales represented 10% of our Retail segment revenue.", "customer": 80, "program": null, "flag": "kill"}, {"name": "collapsed_sentence_spacing", "text": "Our largest customer represented 80% of total revenue.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "branded_name_dot", "text": "Our largest customer represented 80% of our Revenue.Systems segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "own_collapsed", "text": "Our largest customer represented 80% of our revenue.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "bare_collapsed", "text": "Our largest customer represented 80% of revenue.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "company_collapsed", "text": "Our largest customer represented 80% of company revenue.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "worldwide_suffix", "text": "Our largest customer represented 80% of total revenue worldwide. Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "last_year_suffix", "text": "Our largest customer represented 80% of total revenue last year. Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "program_worldwide_suffix", "text": "Our sole program represented 70% of total revenue worldwide. Retail segment revenue was stable.", "customer": null, "program": 70, "flag": "kill"}, {"name": "worldwide_collapsed", "text": "Our largest customer represented 80% of total revenue worldwide.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "last_year_comma", "text": "Our largest customer represented 80% of total revenue last year, while Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "abbreviation_possessive", "text": "Our largest customer represented 80% of U.S. Retail\\u2019s revenue.", "customer": null, "program": null, "flag": null}, {"name": "decimal_segment_name", "text": "Our largest customer represented 80% of our Retail2.0 segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "geographic_abbreviation", "text": "Our largest customer represented 80% of our St. Louis region revenue.", "customer": null, "program": null, "flag": null}, {"name": "spaced_acronym", "text": "Our largest customer represented 80% of our U. S. Retail segment revenue.", "customer": null, "program": null, "flag": null}, {"name": "corporate_possessive_abbreviation", "text": "Our largest customer represented 80% of AcmeCorp Inc.\\u2019s revenue.", "customer": null, "program": null, "flag": null}, {"name": "corporate_subsidiary_abbreviation", "text": "Our largest customer represented 80% of our AcmeCorp Inc. subsidiary revenue.", "customer": null, "program": null, "flag": null}, {"name": "capitalized_aggregate_collapsed", "text": "Our largest customer represented 80% of total Revenue.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "uppercase_aggregate_collapsed", "text": "Our largest customer represented 80% of total REVENUE.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "consolidated_capitalized_collapsed", "text": "Our largest customer represented 80% of consolidated Revenue.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "capitalized_sales_collapsed", "text": "Our largest customer represented 80% of total Sales.Retail segment revenue was stable.", "customer": 80, "program": null, "flag": "kill"}, {"name": "company_abbreviation", "text": "Our largest customer represented 80% of AcmeCorp Co.\\u2019s revenue.", "customer": null, "program": null, "flag": null}, {"name": "limited_abbreviation", "text": "Our largest customer represented 80% of our AcmeCorp Ltd. subsidiary revenue.", "customer": null, "program": null, "flag": null}, {"name": "corporate_pte", "text": "Our largest customer represented 80% of AcmeCorp Pte. Ltd.\\u2019s revenue.", "customer": null, "program": null, "flag": null}, {"name": "corporate_pty", "text": "Our largest customer represented 80% of our AcmeCorp Pty. Ltd. subsidiary revenue.", "customer": null, "program": null, "flag": null}, {"name": "corporate_inc_uppercase", "text": "Our largest customer represented 80% of our AcmeCorp INC. subsidiary revenue.", "customer": null, "program": null, "flag": null}, {"name": "mixed_case_acronym", "text": "Our largest customer represented 80% of our AcmeCorp S.p.A. subsidiary revenue.", "customer": null, "program": null, "flag": null}], "rounding": [{"name": "positive_epsilon", "excess_pct": 0.001, "favorable": true}, {"name": "negative_epsilon", "excess_pct": -0.001, "favorable": false}, {"name": "exact_zero", "excess_pct": 0, "favorable": false}, {"name": "positive", "excess_pct": 12, "favorable": true}, {"name": "negative", "excess_pct": -8, "favorable": false}, {"name": "positive_half_cent", "excess_pct": 0.005, "favorable": true}, {"name": "negative_half_cent", "excess_pct": -0.005, "favorable": false}], "outcomes": [{"name": "legacy_zero", "row": {"realized_excess_pct": 0}, "expected": null}, {"name": "legacy_positive", "row": {"realized_excess_pct": 0.01}, "expected": true}, {"name": "legacy_negative", "row": {"realized_excess_pct": -0.01}, "expected": false}, {"name": "legacy_upper_interval_boundary", "row": {"realized_excess_pct": -0.005}, "expected": null}, {"name": "legacy_lower_interval_boundary", "row": {"realized_excess_pct": 0.005}, "expected": null}, {"name": "precision_overrides_rounding", "row": {"realized_excess_pct": 0, "realized_excess_pct_unrounded": 0.001, "favorable": true}, "expected": true}, {"name": "explicit_false_conflict", "row": {"realized_excess_pct": 0, "realized_excess_pct_unrounded": 0.001, "favorable": false}, "expected": null}, {"name": "explicit_true_conflict", "row": {"realized_excess_pct": 0, "realized_excess_pct_unrounded": 0, "favorable": true}, "expected": null}, {"name": "boolean_precision", "row": {"realized_excess_pct": 1, "realized_excess_pct_unrounded": true}, "expected": null}, {"name": "null_precision", "row": {"realized_excess_pct": 1, "realized_excess_pct_unrounded": null}, "expected": null}, {"name": "text_precision", "row": {"realized_excess_pct": 1, "realized_excess_pct_unrounded": "0.1"}, "expected": null}, {"name": "nan_precision", "row": {"realized_excess_pct": 1, "realized_excess_pct_unrounded": {"special_number": "nan"}}, "expected": null}, {"name": "infinite_precision", "row": {"realized_excess_pct": 1, "realized_excess_pct_unrounded": {"special_number": "inf"}}, "expected": null}, {"name": "negative_infinite_precision", "row": {"realized_excess_pct": 1, "realized_excess_pct_unrounded": {"special_number": "-inf"}}, "expected": null}, {"name": "boolean_outcome", "row": {"realized_excess_pct_unrounded": 1, "favorable": 1}, "expected": null}], "risk": [{"name": "above_threshold", "stock": -39.999, "excess": -0.001, "exact": true, "avoidance": 1, "capture": 0}, {"name": "at_threshold", "stock": -40, "excess": -0.001, "exact": true, "avoidance": 0, "capture": 1}, {"name": "below_threshold", "stock": -40.001, "excess": -0.001, "exact": true, "avoidance": 0, "capture": 1}, {"name": "exact_zero_excess", "stock": -40, "excess": 0, "exact": true, "avoidance": 0, "capture": 0}, {"name": "positive_epsilon_excess", "stock": -40, "excess": 0.001, "exact": true, "avoidance": 0, "capture": 0}, {"name": "legacy_threshold", "stock": -40, "excess": -1, "exact": false, "avoidance": null, "capture": null}, {"name": "legacy_zero_excess", "stock": -41, "excess": 0, "exact": false, "avoidance": 0, "capture": null}, {"name": "legacy_negative", "stock": -41, "excess": -1, "exact": false, "avoidance": 0, "capture": 1}, {"name": "legacy_positive", "stock": -39, "excess": 1, "exact": false, "avoidance": 1, "capture": 0}, {"name": "legacy_threshold_upper_edge", "stock": -40.005, "excess": -1, "exact": false, "avoidance": null, "capture": null}, {"name": "legacy_threshold_lower_edge", "stock": -39.995, "excess": -1, "exact": false, "avoidance": null, "capture": null}]}')


def source31_regression_source():
    return '"""Generated offline-suite controls with synthetic observations."""\nfrom copy import deepcopy\nfrom types import SimpleNamespace\nimport json\nfrom pathlib import Path\n\nimport pytest\n\nfrom make_fixtures import source31_valuation_config, tracking_quote_scenarios, source28_realize\nfrom test_private_runs import state\nfrom test_tracking_quote_contract import tracker\n\n\ndef test_offline_denials_escape_ordinary_exception_handlers(offline_network_targets):\n    labels = {label for label, _ in offline_network_targets}\n    assert {"socket.socket.connect", "socket.socket.connect_ex", "socket.socket.sendto",\n            "socket.create_connection", "socket.getaddrinfo",\n            "urllib.request.OpenerDirector.open"} <= labels\n    for label, operation in offline_network_targets:\n        with pytest.raises(pytest.fail.Exception, match="offline suite"):\n            try:\n                operation()\n            except Exception:\n                pytest.fail("an ordinary handler swallowed the network denial: " + label)\n\n\ndef test_explicit_transport_mock_can_return_synthetic_data(monkeypatch):\n    import requests\n    response = SimpleNamespace(status_code=200, text="synthetic response")\n    monkeypatch.setattr(requests.sessions.Session, "request", lambda *args, **kwargs: response)\n    assert requests.get("https://example.com/synthetic") is response\n\n\ndef test_valuation_fixture_returns_independent_config_values():\n    first = source31_valuation_config()\n    second = source31_valuation_config()\n    assert first == {"wacc": 0.10, "cap_rate_low": 0.09, "cap_rate_high": 0.12,\n                     "normalize_years": 5, "cyclical_cv_threshold": 0.25}\n    first["wacc"] = 1.0\n    assert second["wacc"] == 0.10\n\n\nCASE = json.loads(Path(__file__).with_name("source31_contracts.json").read_text(encoding="utf-8"))\nCONCENTRATION = CASE["concentration"]\n\n\n@pytest.mark.parametrize("case", CONCENTRATION, ids=lambda case: case["name"])\ndef test_segment_exclusion_stays_with_its_percentage(case):\n    from _deepdive_flags import _extract_concentration, _concentration_flag\n    customer, program, detail = _extract_concentration(case["text"])\n    assert (customer, program) == (case["customer"], case["program"])\n    assert _concentration_flag(customer, program) == case["flag"]\n    assert (detail is None) is (customer is None and program is None)\n\n\n@pytest.mark.parametrize("case", CASE["rounding"], ids=lambda case: case["name"])\ndef test_score_and_scorecard_keep_the_same_precise_outcome(tracker, state, monkeypatch, case):\n    row = deepcopy(tracking_quote_scenarios()["base_row"])\n    row["implied_prob"] = 0.8\n    calls, saved = [], []\n\n    def snapshot(ticker, entry, horizon):\n        calls.append(ticker)\n        entry_quote = row["entry_quote"] if ticker == row["ticker"] else row["benchmark_entry_quote"]\n        return {"available": True,\n                "return_fraction": case["excess_pct"] / 100 if ticker == row["ticker"] else 0.0,\n                "entry_quote": deepcopy(entry_quote), "horizon_quote": {"resolved_date": horizon}}\n\n    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])\n    monkeypatch.setattr(tracker, "_save_verdicts", lambda rows: saved.append(deepcopy(rows)))\n    monkeypatch.setattr(tracker, "_fetch_return_snapshot", snapshot)\n    tracker.cmd_score(SimpleNamespace())\n    assert calls == [row["ticker"], row["benchmark"]]\n    assert len(saved) == 1 and saved[0][0]["scored"] is True\n    assert row["realized_excess_pct_unrounded"] == pytest.approx(case["excess_pct"])\n    assert row["stock_return_pct_unrounded"] == pytest.approx(case["excess_pct"])\n    assert row["favorable"] is case["favorable"]\n    assert tracker._favorable_outcome(row) is case["favorable"]\n    assert row["brier"] == pytest.approx(0.04 if case["favorable"] else 0.64)\n    destination = Path(state["companion"]) / "data" / "metrics" / "scorecard.md"\n    monkeypatch.setattr(tracker, "SCORECARD_FILE", destination)\n    tracker.cmd_scorecard(SimpleNamespace())\n    scorecard = destination.read_text(encoding="utf-8")\n    assert "**Outcome coverage:** 1/1; missing 0" in scorecard\n    assert "all 1 stored scores" in scorecard\n    assert ("| YES |" if case["favorable"] else "| NO |") in scorecard\n    assert ("**Overall hit rate (stock beat benchmark):** 100.0%" if case["favorable"]\n            else "**Overall hit rate (stock beat benchmark):** 0.0%") in scorecard\n    rating_line = next(line for line in scorecard.splitlines() if line.startswith("| " + row["rating"] + " |"))\n    assert ("| 100.0% |" if case["favorable"] else "| 0.0% |") in rating_line\n    calibration_line = next(line for line in scorecard.splitlines() if line.startswith("| 0.70–1.01 |"))\n    assert ("| 1.00 | +0.20 |" if case["favorable"] else "| 0.00 | -0.80 |") in calibration_line\n\n\n@pytest.mark.parametrize("case", CASE["outcomes"], ids=lambda case: case["name"])\ndef test_legacy_rounding_and_invalid_precision_report_missing_outcomes(case):\n    from _calibration import _favorable_outcome, _outcome_summary\n    row = {key: source28_realize(value) for key, value in case["row"].items()}\n    assert _favorable_outcome(row) is case["expected"]\n    result = _outcome_summary([row])\n    assert result["observed"] == (0 if case["expected"] is None else 1)\n    assert result["missing"] == (1 if case["expected"] is None else 0)\n    assert result["rate"] == (None if case["expected"] is None else float(case["expected"]))\n\n\n@pytest.mark.parametrize("case", CASE["risk"], ids=lambda case: case["name"])\ndef test_risk_metrics_use_precise_sign_and_threshold_coverage(case):\n    from _calibration import _risk_metric_summary, _blowup_avoidance_rate, _downside_capture_rate\n    row = {"rating": "避开", "scored": True,\n           "stock_return_pct": round(case["stock"], 2) if case["exact"] else case["stock"],\n           "realized_excess_pct": round(case["excess"], 2) if case["exact"] else case["excess"]}\n    if case["exact"]:\n        row.update(stock_return_pct_unrounded=case["stock"],\n                   realized_excess_pct_unrounded=case["excess"], favorable=case["excess"] > 0)\n    for metric in ("avoidance", "capture"):\n        summary = _risk_metric_summary([row], metric, -0.4)\n        assert summary["rate"] == case[metric]\n        assert summary["observed"] == (0 if case[metric] is None else 1)\n        assert summary["missing"] == (1 if case[metric] is None else 0)\n    assert _blowup_avoidance_rate([row]) == case["avoidance"]\n    assert _downside_capture_rate([row]) == case["capture"]\n\n\n@pytest.mark.parametrize("known", [False, True])\ndef test_scorecard_separates_legacy_missing_outcomes_from_stored_brier(tracker, state, monkeypatch, known):\n    base = tracking_quote_scenarios()["base_row"]\n    unknown = dict(base, ticker="SYNUNKNOWN", scored=True, implied_prob=0.8,\n                   stock_return_pct=-41.0, realized_excess_pct=0.0, brier=0.04, rating="避开")\n    rows = [unknown]\n    if known:\n        rows.append(dict(unknown, ticker="SYNKNOWN", realized_excess_pct_unrounded=0.001,\n                         stock_return_pct_unrounded=-41.0, favorable=True))\n    before = deepcopy(rows)\n    monkeypatch.setattr(tracker, "_load_verdicts", lambda: rows)\n    destination = Path(state["companion"]) / "data" / "metrics" / "scorecard.md"\n    monkeypatch.setattr(tracker, "SCORECARD_FILE", destination)\n    tracker.cmd_scorecard(SimpleNamespace())\n    scorecard = destination.read_text(encoding="utf-8")\n    assert rows == before\n    assert f"**Outcome coverage:** {int(known)}/{len(rows)}; missing 1" in scorecard\n    assert f"all {len(rows)} stored scores" in scorecard\n    assert "| SYNUNKNOWN | 避开 | 0.80 | 0.0 | UNKNOWN | 0.04 |" in scorecard\n    assert ("**Overall hit rate (stock beat benchmark):** 100.0%" if known\n            else "**Overall hit rate (stock beat benchmark):** N/A") in scorecard\n    calibration = next(line for line in scorecard.splitlines() if line.startswith("| 0.70–1.01 |"))\n    assert (f"| {len(rows)} | 1 | 0.800 | 1.00 | +0.20 |" if known\n            else "| 1 | 0 | — | — | — |") in calibration\n    downside = next(line for line in scorecard.splitlines() if line.startswith("| Downside-capture"))\n    assert f"coverage {int(known)}/{len(rows)}; missing 1" in downside\n'



def source32_scenarios():
    """Synthetic resume cohorts cover retention, retry replacement and checkpoints."""
    def row(ticker, *, success=False, missing=False):
        value = {"ticker": ticker, "cik": "42", "asof": "2000-01-01",
                 "synthetic_marker": "retained-prior-observation"}
        if not missing:
            value["series"] = {"cash": [{"end": "1999-12-31", "val": 10}]} if success else {}
        if not success:
            value["pull_error"] = "synthetic prior failure"
        return value

    def case(name, prior, tickers=(), failures=(), checkpoint=False):
        return {"name": name, "prior": prior, "tickers": list(tickers),
                "failures": list(failures), "checkpoint": checkpoint}

    failed, success = row("SYNFAILED"), row("SYNSUCCESS", success=True)
    return {"legacy": source32_legacy_scenarios(),
            "acquisition": source32_legacy_acquisition(), "resume": [
        case("absent_failed", [failed]),
        case("absent_missing_series", [row("SYNMISSING", missing=True)]),
        case("absent_success", [success]),
        case("retry_succeeds", [failed], ["SYNFAILED"]),
        case("retry_fails", [failed], ["SYNFAILED"], ["SYNFAILED"]),
        case("success_skipped_new_added", [success], ["SYNSUCCESS", "SYNNEW"]),
        case("mixed_retention_and_retry", [failed, success, row("SYNRETRY")],
             ["SYNSUCCESS", "SYNRETRY", "SYNNEW"], ["SYNRETRY"]),
        case("checkpoint_retains_pending_failure", [failed],
             [f"SYNNEW{i:02}" for i in range(40)] + ["SYNFAILED"], checkpoint=True),
    ]}


def source32_regression_source():
    return '"""Generated Source32 resume regressions with synthetic in-memory dependencies."""\nimport ast\nfrom copy import deepcopy\nimport io\nimport json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n\nimport pytest\n\nfrom make_fixtures import source32_scenarios\n\nCASE = source32_scenarios()\nROOT = Path(__file__).resolve().parents[2]\n\n\ndef _resume_runner(case):\n    source = (ROOT / "docs/backtest-2026-06/distress_features_fast.py").read_text(encoding="utf-8")\n    tree = ast.parse(source)\n    run, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"]\n    assert not run.decorator_list\n    prior = deepcopy(case["prior"])\n    before = deepcopy(prior)\n    snapshots, attempted = [], []\n    panel = {"asof": "2000-01-01", "theme": "synthetic-theme",\n             "benchmark": {"total_return": 0.0},\n             "names": [{"ticker": ticker, "cik": "42", "total_return": 0.1,\n                        "forward_return": {"status": "ok", "entry_price": 10.0}}\n                       for ticker in case["tickers"]]}\n\n    def fake_open(name):\n        assert name == "synthetic-panel"\n        return io.StringIO(json.dumps(panel))\n\n    def pull(row):\n        attempted.append(row["ticker"])\n        if row["ticker"] in case["failures"]:\n            raise RuntimeError("synthetic retry failure")\n        result = deepcopy(row)\n        result["series"] = {"cash": [{"end": "1999-12-31", "val": 20}]}\n        return result\n\n    class Future:\n        def __init__(self, callback, row):\n            self.callback, self.row = callback, row\n\n        def result(self):\n            return self.callback(self.row)\n\n    class Pool:\n        def __init__(self, **kwargs):\n            assert kwargs == {"max_workers": 6}\n\n        def __enter__(self):\n            return self\n\n        def __exit__(self, *args):\n            return False\n\n        def submit(self, callback, row):\n            assert callback is pull\n            return Future(callback, row)\n\n    namespace = {\n        "features_path": lambda: SimpleNamespace(exists=lambda: bool(prior)),\n        "backtest_files": lambda: ["synthetic-panel"] if case["tickers"] else [],\n        "load_features": lambda: deepcopy(prior),\n        "write_features": lambda rows: snapshots.append(deepcopy(rows)),\n        "time": SimpleNamespace(time=lambda: 0.0),\n        "ThreadPoolExecutor": Pool,\n        "as_completed": lambda futures: iter(futures),\n        "pull_one": pull,\n        "open": fake_open,\n        "json": json,\n        "print": lambda *args, **kwargs: None,\n    }\n    exec(compile(ast.Module(body=[run], type_ignores=[]), "<shipped-fast-run>", "exec"), namespace)\n    namespace["run"]()\n    assert prior == before\n    return snapshots, attempted\n\n\n@pytest.mark.parametrize("case", CASE["resume"], ids=lambda case: case["name"])\ndef test_fast_resume_preserves_observations_and_replaces_retries(case):\n    snapshots, attempted = _resume_runner(case)\n    prior = {row["ticker"]: row for row in case["prior"]}\n    successful = {ticker for ticker, row in prior.items() if row.get("series")}\n    expected_attempts = [ticker for ticker in case["tickers"] if ticker not in successful]\n    assert attempted == expected_attempts\n    assert len(snapshots) == (2 if case["checkpoint"] else 1)\n    final = snapshots[-1]\n    keys = [(row["ticker"], row["asof"]) for row in final]\n    assert len(keys) == len(set(keys)) == len(set(prior) | set(case["tickers"]))\n    final_by_ticker = {row["ticker"]: row for row in final}\n    for ticker, old in prior.items():\n        if ticker not in expected_attempts:\n            assert final_by_ticker[ticker] == old\n    for ticker in expected_attempts:\n        row = final_by_ticker[ticker]\n        assert "synthetic_marker" not in row\n        if ticker in case["failures"]:\n            assert row["series"] == {}\n            assert row["pull_error"] == "synthetic retry failure"\n        else:\n            assert row["series"] == {"cash": [{"end": "1999-12-31", "val": 20}]}\n            assert "pull_error" not in row\n    if case["checkpoint"]:\n        checkpoint = {row["ticker"]: row for row in snapshots[0]}\n        assert len(checkpoint) == 41\n        assert checkpoint["SYNFAILED"] == prior["SYNFAILED"]\n        assert final_by_ticker["SYNFAILED"]["series"] != prior["SYNFAILED"]["series"]\n'

def source32_repository_examples():
    """Generate synthetic config and unscored tracking examples for a fresh tool."""
    from copy import deepcopy
    config = {
        "schema_version": 1,
        "sec_user_agent": "small-cap-deepdive example user1@example.com",
        "output_dir": "./reports/smallcap",
        "market_cap_max": 2_000_000_000,
        "watch_band_max": 5_000_000_000,
        "micro_cap_max": 500_000_000,
        "min_dollar_vol": 100_000,
        "sic_hard_exclude": ["2833", "2834", "2835", "2836", "38", "80", "737", "6", "5", "3944"],
        "python_cmd": "python",
        "insider_source": "openinsider",
        "wacc": 0.10,
        "cap_rate_low": 0.09,
        "cap_rate_high": 0.12,
        "normalize_years": 5,
        "cyclical_cv_threshold": 0.25,
    }
    rows = []
    for ticker, rating, probability in (
            ("SYNEXAMPLEA", "\u4e70\u5165", 0.8),
            ("SYNEXAMPLEB", "\u89c2\u5bdf", 0.5),
            ("SYNEXAMPLEC", "\u907f\u5f00", 0.2)):
        row = deepcopy(tracking_quote_scenarios()["base_row"])
        row.update(ticker=ticker, benchmark="SYNBENCH", rating=rating, confidence=0.8,
                   implied_prob=probability, verdict_date="2000-01-01", entry_date="2000-01-01",
                   theme="synthetic-theme", synthetic_fixture=True,
                   thesis="Generated fictional observation; not a position or provider result.")
        for key, symbol in (("entry_quote", ticker), ("benchmark_entry_quote", "SYNBENCH")):
            row[key].update(ticker=symbol, requested_date="2000-01-01", resolved_date="2000-01-01")
        row.update(stock_return_pct_unrounded=None, realized_excess_pct_unrounded=None)
        rows.append(row)
    scorecard = [
        "# Track-Forward Calibration Scorecard",
        "",
        "> Generated synthetic shape example. No row is a real observation.",
        "> Real scorecards are written only in the configured PRIVATE companion.",
        "",
        "## Status: 0 Scored / 3 Pending",
        "",
        "**Calibration unknown until verdicts mature.**",
        "",
        "The generated rows contain no adjudication receipts or realized returns.",
        "BUY review coverage is 0/1; price quarantine is 0. No Brier score, hit rate,",
        "or predictive-edge claim is available.",
        "",
        "## Pending Verdicts",
        "",
        "| Ticker | Theme | Rating | p_implied | Verdict Date | Maturity Date |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        scorecard.append(
            f"| {row['ticker']} | {row['theme']} | {row['rating']} | "
            f"{row['implied_prob']:.2f} | 2000-01-01 | 2000-01-31 |")
    return {
        "reference/config.example.json": (json.dumps(config, indent=2) + "\n").encode("utf-8"),
        "metrics/verdicts.jsonl.example": "".join(
            json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows).encode("utf-8"),
        "metrics/scorecard.md.example": ("\n".join(scorecard) + "\n").encode("utf-8"),
    }


def source32_legacy_scenarios():
    """Generate fictional financial inputs with explicit synthetic annual evidence."""
    from datetime import date

    values = json.loads('{"valuation_financial": {"ticker": "SYNFINANCIAL", "derived": {"latest_cash": 100000000, "latest_total_debt": 500000000, "latest_revenue": 200000000, "latest_net_income": 50000000, "latest_ocf": 80000000, "latest_ebit": 60000000, "latest_dep_amort": 5000000, "latest_capex": 10000000, "latest_ebitda": 65000000, "latest_fcf": 70000000, "fcf_is_ocf_proxy": false, "latest_goodwill": 0, "latest_intangibles": 0, "sic": "6726", "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "data_quality_warn": null, "debt_source": "LongTermDebt"}, "financials": {"assets": [{"end": "2024-12-31", "val": 2000000000}], "equity": [{"end": "2024-12-31", "val": 1500000000}], "ebit": [{"end": "2024-12-31", "val": 60000000}], "dep_amort": [{"end": "2024-12-31", "val": 5000000}], "ocf": [{"end": "2024-12-31", "val": 80000000}], "capex": [{"end": "2024-12-31", "val": 10000000}], "revenue": [{"end": "2024-12-31", "val": 200000000}], "shares_outstanding": [{"end": "2024-12-31", "val": 10000000}]}, "synthetic_fixture": true}, "valuation_no_sic_bdc": {"ticker": "SYNNOSICBDC", "derived": {"latest_cash": 25000000, "latest_total_debt": 260000000, "latest_revenue": null, "latest_net_income": 35000000, "latest_ocf": 90000000, "latest_ebit": null, "latest_dep_amort": null, "latest_capex": null, "latest_ebitda": null, "latest_fcf": 90000000, "fcf_is_ocf_proxy": true, "latest_goodwill": 0, "latest_intangibles": 0, "sic": null, "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "data_quality_warn": null, "debt_source": "LongTermDebt"}, "financials": {"assets": [{"end": "2024-12-31", "val": 820000000}], "equity": [{"end": "2024-12-31", "val": 560000000}], "ocf": [{"end": "2024-12-31", "val": 90000000}], "revenue": [], "shares_outstanding": [{"end": "2024-12-31", "val": 24000000}]}, "synthetic_fixture": true}, "valuation_extreme": {"ticker": "SYNEXTREME", "derived": {"latest_cash": 0, "latest_total_debt": 0, "latest_revenue": 10000000, "latest_net_income": 3000000, "latest_ocf": 3800000, "latest_ebit": 3000000, "latest_dep_amort": 500000, "latest_capex": 200000, "latest_ebitda": 3500000, "latest_fcf": 3600000, "fcf_is_ocf_proxy": false, "latest_goodwill": 0, "latest_intangibles": 0, "sic": "3990", "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "data_quality_warn": null, "debt_source": "LongTermDebt"}, "financials": {"assets": [{"end": "2024-12-31", "val": 5000000}], "equity": [{"end": "2024-12-31", "val": 4000000}], "ebit": [{"end": "2024-12-31", "val": 3000000}], "dep_amort": [{"end": "2024-12-31", "val": 500000}], "ocf": [{"end": "2024-12-31", "val": 3800000}], "capex": [{"end": "2024-12-31", "val": 200000}], "revenue": [{"end": "2024-12-31", "val": 10000000}], "shares_outstanding": [{"end": "2024-12-31", "val": 1000000}]}, "synthetic_fixture": true}, "valuation_proxy_light": {"ticker": "SYNPROXYLIGHT", "derived": {"latest_cash": 5000000, "latest_total_debt": 0, "latest_revenue": 50000000, "latest_net_income": 8000000, "latest_ocf": 10000000, "latest_ebit": 9000000, "latest_dep_amort": 500000, "latest_capex": null, "latest_ebitda": 9500000, "latest_fcf": 10000000, "fcf_is_ocf_proxy": true, "latest_goodwill": 0, "latest_intangibles": 0, "sic": "3990", "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "data_quality_warn": null, "debt_source": "LongTermDebt"}, "financials": {"assets": [{"end": "2024-12-31", "val": 80000000}], "equity": [{"end": "2024-12-31", "val": 70000000}], "ebit": [{"end": "2024-12-31", "val": 9000000}], "dep_amort": [{"end": "2024-12-31", "val": 500000}], "ocf": [{"end": "2024-12-31", "val": 10000000}], "capex": [], "revenue": [{"end": "2024-12-31", "val": 50000000}], "shares_outstanding": [{"end": "2024-12-31", "val": 10000000}]}, "synthetic_fixture": true}, "valuation_clean_base": {"ticker": "SYNCLEANBASE", "derived": {"latest_cash": 20000000, "latest_total_debt": 10000000, "latest_revenue": 100000000, "latest_net_income": 15000000, "latest_ocf": 20000000, "latest_ebit": 18000000, "latest_dep_amort": 4000000, "latest_capex": 5000000, "latest_ebitda": 22000000, "latest_fcf": 15000000, "fcf_is_ocf_proxy": false, "latest_goodwill": 0, "latest_intangibles": 0, "sic": "3990", "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "data_quality_warn": null, "debt_source": "LongTermDebt", "ebit_source": "OperatingIncomeLoss", "concentration_flag": null, "top_customer_pct": null, "top_program_pct": null, "fundamental_decline_flag": false, "rev_slope_sign": 1, "rev_accel_sign": 0, "latest_below_avg": false, "contamination_ratio": 1.05, "peak_contamination_flag": false, "low_revenue_loss_ratio": false, "form_used": "10-K"}, "financials": {"assets": [{"end": "2024-12-31", "val": 200000000}], "equity": [{"end": "2024-12-31", "val": 150000000}], "ebit": [{"end": "2024-12-31", "val": 18000000}], "dep_amort": [{"end": "2024-12-31", "val": 4000000}], "ocf": [{"end": "2024-12-31", "val": 20000000}], "capex": [{"end": "2024-12-31", "val": 5000000}], "revenue": [{"end": "2024-12-31", "val": 100000000}], "shares_outstanding": [{"end": "2024-12-31", "val": 10000000}]}, "synthetic_fixture": true}, "valuation_blocked": {"ticker": "SYNBLOCKED", "derived": {"latest_cash": 40000000, "latest_total_debt": 70000000, "latest_revenue": 60000000, "latest_net_income": -180000000, "latest_ocf": null, "latest_ebit": null, "latest_dep_amort": null, "latest_capex": null, "latest_ebitda": null, "latest_fcf": null, "fcf_is_ocf_proxy": false, "latest_goodwill": 0, "latest_intangibles": 0, "sic": "1040", "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "low_revenue_loss_ratio": true, "low_revenue_loss_ratio_detail": "early-revenue resource pattern, right entity", "data_quality_warn": null, "debt_source": "LongTermDebt", "ebit_source": null, "concentration_flag": null, "top_customer_pct": null, "top_program_pct": null, "fundamental_decline_flag": false, "peak_contamination_flag": false, "rev_slope_sign": 1, "rev_accel_sign": 0, "latest_below_avg": false, "contamination_ratio": null, "form_used": "10-K"}, "financials": {"assets": [{"end": "2024-12-31", "val": 500000000}], "equity": [{"end": "2024-12-31", "val": 300000000}], "ocf": [], "revenue": [{"end": "2024-12-31", "val": 60000000}], "shares_outstanding": [{"end": "2024-12-31", "val": 400000000}]}, "synthetic_fixture": true}, "valuation_lumpy": {"ticker": "SYNLUMPY", "derived": {"latest_cash": 8000000, "latest_total_debt": 0, "latest_revenue": 70000000, "latest_net_income": 15000000, "latest_ocf": 30000000, "latest_ebit": 22000000, "latest_dep_amort": 3000000, "latest_capex": 2000000, "latest_ebitda": 25000000, "latest_fcf": 28000000, "fcf_is_ocf_proxy": false, "latest_goodwill": 0, "latest_intangibles": 0, "sic": "2836", "debt_truncation_suspected": false, "debt_stale": false, "wrong_entity_suspected": false, "data_quality_warn": null, "debt_source": "LongTermDebt", "ebit_source": "OperatingIncomeLoss", "contamination_ratio": 0.7, "fundamental_decline_flag": false, "rev_slope_sign": 0, "latest_below_avg": true}, "financials": {"assets": [{"end": "2024-12-31", "val": 240000000}], "equity": [{"end": "2024-12-31", "val": 210000000}], "ebit": [{"end": "2020-12-31", "val": 8000000}, {"end": "2021-12-31", "val": 24000000}, {"end": "2022-12-31", "val": 100000000}, {"end": "2023-12-31", "val": 30000000}, {"end": "2024-12-31", "val": 22000000}], "dep_amort": [{"end": "2020-12-31", "val": 3000000}, {"end": "2021-12-31", "val": 3000000}, {"end": "2022-12-31", "val": 3000000}, {"end": "2023-12-31", "val": 3000000}, {"end": "2024-12-31", "val": 3000000}], "ocf": [{"end": "2020-12-31", "val": 10000000}, {"end": "2021-12-31", "val": 25000000}, {"end": "2022-12-31", "val": 110000000}, {"end": "2023-12-31", "val": 38000000}, {"end": "2024-12-31", "val": 30000000}], "capex": [{"end": "2020-12-31", "val": 2000000}, {"end": "2021-12-31", "val": 2000000}, {"end": "2022-12-31", "val": 2000000}, {"end": "2023-12-31", "val": 2000000}, {"end": "2024-12-31", "val": 2000000}], "revenue": [{"end": "2020-12-31", "val": 35000000}, {"end": "2021-12-31", "val": 75000000}, {"end": "2022-12-31", "val": 150000000}, {"end": "2023-12-31", "val": 85000000}, {"end": "2024-12-31", "val": 70000000}], "shares_outstanding": [{"end": "2024-12-31", "val": 60000000}]}, "synthetic_fixture": true}, "deepdive_decline_revenue": [{"end": "2019-09-30", "val": 2000000}, {"end": "2019-12-31", "val": 7000000}, {"end": "2020-12-31", "val": 160000000}, {"end": "2021-12-31", "val": 180000000}, {"end": "2022-12-31", "val": 155000000}, {"end": "2023-12-31", "val": 130000000}, {"end": "2024-12-31", "val": 105000000}, {"end": "2025-12-31", "val": 80000000}], "deepdive_peak_revenue": [{"end": "2020-12-31", "val": 100000000}, {"end": "2021-12-31", "val": 220000000}, {"end": "2022-12-31", "val": 360000000}, {"end": "2023-12-31", "val": 280000000}, {"end": "2024-12-31", "val": 240000000}], "deepdive_peak_ocf": [{"end": "2020-12-31", "val": 60000000}, {"end": "2021-12-31", "val": 180000000}, {"end": "2022-12-31", "val": 240000000}, {"end": "2023-12-31", "val": 140000000}, {"end": "2024-12-31", "val": 100000000}], "deepdive_peak_income": [{"end": "2023-12-31", "val": 40000000}, {"end": "2024-12-31", "val": -60000000}], "deepdive_negative_income": [{"end": "2024-12-31", "val": -60000000}], "deepdive_early_revenue": [{"end": "2024-12-31", "val": 60000000}], "deepdive_early_income": [{"end": "2024-12-31", "val": -180000000}], "deepdive_early_shares": [{"end": "2024-12-31", "val": 400000000}], "deepdive_masked_ocf": [{"end": "2020-12-31", "val": 40000000}, {"end": "2021-12-31", "val": 50000000}, {"end": "2022-12-31", "val": 35000000}, {"end": "2023-12-31", "val": 25000000}, {"end": "2024-12-31", "val": -20000000}], "deepdive_lessor_balance": [2400000000, 5000000000], "ni_anomaly_cases": [[30000000000, 400000000], [40000000000, 400000000], [-40000000000, 400000000], [40000000, 400000000], [20000000000, 400000000]], "masked_loss_inputs": [-20000000, -75000000, -1.5], "concentration_receivables": "Our largest customer represented 83% and 47%, respectively, of accounts receivable at the end of 2001 and 2000. This customer is AcmeCorp.", "concentration_program": "Our sole program accounted for approximately 84% of total revenue for the year. No single customer represented more than 10% of net sales.", "concentration_bracket_segment": "Note 12. Segment information. Our Retail Branch Division generated 100% of [Retail Branch Division] revenue from sales within the region during fiscal 2000.", "concentration_collapsed_segment": "Our largest customer accounted for approximately 5% of consolidated revenue. Approximately100% ofRetail Branch Division\\u2019s revenue came from regional sales during fiscal 2000.", "concentration_possessive_segment": "In 2000 the AcmeCorp Retail segment accounted for approximately 3% of AcmeCorp Retail\\u2019s revenue. In 2001, approximately 87% of AcmeCorp Retail\\u2019s revenue was generated by repair products. Our largest customer accounted for less than 5% of consolidated revenue.", "concentration_diversified": "In fiscal 2001 the top 18 customers represented approximately 81% of AcmeCorp Services\\u2019 2001 total revenue, reflecting a broad and diversified customer base.", "concentration_customer": "Our largest customer accounted for 68% of total revenue in fiscal 2000; no other customer exceeded 10%.", "concentration_patterns": {"collapsed": "100% ofretail branch division\\u2019s revenue", "possessive": "87% of AcmeCorp Retail\\u2019s revenue", "plural": "81% of AcmeCorp Services\\u2019 2001 total revenue", "diversified": "the top 18 customers represented 81%"}, "valuation_overrides": {"decline_ratio": 0.7, "customer_pct": 83, "peak_ratio": 0.72, "peak_income": -60000000, "current_ocf": -20000000, "lessor_high_debt": 420000000, "lessor_low_debt": 340000000, "lessor_assets": 1000000000, "current_fcf": -75000000}, "deepdive_lumpy_ocf": [{"end": "2021-12-31", "val": 12000000}, {"end": "2022-12-31", "val": 36000000}, {"end": "2023-12-31", "val": 108000000}, {"end": "2024-12-31", "val": 48000000}, {"end": "2025-12-31", "val": 36000000}], "deepdive_clean_decline_revenue": [{"end": "2021-12-31", "val": 140000000}, {"end": "2022-12-31", "val": 130000000}, {"end": "2023-12-31", "val": 115000000}, {"end": "2024-12-31", "val": 100000000}, {"end": "2025-12-31", "val": 90000000}], "deepdive_lumpy_ratio": 0.75}')
    for key, value in values.items():
        if not key.startswith("valuation_") or not isinstance(value, dict):
            continue
        for field in ("revenue", "ocf", "capex", "ebit", "dep_amort"):
            for row in value.get("financials", {}).get(field, []):
                end = date.fromisoformat(row["end"])
                start = date(end.year, 1, 1)
                row.update(start=start.isoformat(), duration_days=(end - start).days,
                           unit="USD", filed=f"{end.year + 1}-02-01",
                           fp="FY", form="10-K", cik="0000000042", taxonomy="us-gaap")
    return values


def source32_legacy_acquisition():
    """Generate fictional HTTP envelopes for the retained acquisition assertions."""
    from copy import deepcopy
    from html import escape

    revenue_tags = ["Revenues", "SalesRevenueNet",
                    "RevenueFromContractWithCustomerIncludingAssessedTax",
                    "RevenueFromContractWithCustomerExcludingAssessedTax"]
    pretax_tags = [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ]
    tags = revenue_tags + ["OperatingIncomeLoss"] + pretax_tags + [
        "InterestExpense", "InterestAndDebtExpense", "InterestExpenseDebt",
        "PropertyPlantAndEquipmentNet", "PropertySubjectToOrAvailableForOperatingLeaseNet",
        "EquipmentLeasedToOtherPartyNet"]
    envelopes = {
        f"{cik}:{tag}": {"cik": int(cik), "taxonomy": "us-gaap", "tag": tag,
                         "units": {"USD": []}}
        for cik in ("1", "901", "902", "903", "904") for tag in tags
    }

    def fact(year, value, *, april=False):
        return {"start": f"{year-1}-05-01" if april else f"{year}-01-01",
                "end": f"{year}-04-30" if april else f"{year}-12-31",
                "val": value, "fy": year, "fp": "FY", "form": "10-K",
                "filed": f"{year}-07-01" if april else f"{year+1}-03-01"}

    def put(cik, tag, rows):
        envelopes[f"{cik}:{tag}"]["units"]["USD"] = rows

    put("901", "Revenues", [fact(2018, 20_000_000)])
    put("901", revenue_tags[2], [fact(2024, 70_000_000), fact(2025, 80_000_000)])
    put("902", "Revenues", [fact(2018, 30_000_000, april=True)])
    put("902", revenue_tags[2], [fact(2024, 90_000_000, april=True),
                                fact(2025, 100_000_000, april=True)])
    put("903", revenue_tags[3], [fact(2024, 500_000_000), fact(2025, 600_000_000)])
    envelopes["903:" + revenue_tags[3]]["units"]["shares"] = [fact(2025, 600)]
    put("904", pretax_tags[-1], [fact(2024, 40_000_000)])
    put("904", "InterestExpenseDebt", [fact(2024, 5_000_000)])
    columns = ["Filing Date", "Trade Date", "Ticker", "Trade Type", "Value"]
    rows = [
        ["2001-06-15", "2001-06-14", "SYNINSIDER", "P - Purchase", "$12,500"],
        ["2001-06-16", "2001-06-15", "SYNINSIDER", "S - Sale", "$4,000"],
    ]
    table = "<table><tr>" + "".join("<th>" + escape(v) + "</th>" for v in columns) + "</tr>"
    for row in rows:
        table += "<tr>" + "".join("<td>" + escape(v) + "</td>" for v in row) + "</tr>"
    table += "</table>"
    filings = {
        "SYNANNUAL": {"form": "10-K", "filing_date": "2001-03-01",
                      "text": "AcmeCorp synthetic annual filing. Item 1A. Risk factors. General business risks."},
        "SYNFOREIGN": {"form": "20-F", "filing_date": "2001-04-01",
                       "text": "AcmeCorp synthetic foreign annual filing. Item 3. Risk factors. General business risks."},
    }
    return {"concepts": deepcopy(envelopes), "filings": filings,
            "insider": {"ticker": "SYNINSIDER", "observed_at": "2001-07-01",
                        "html": table, "buys": 1, "sells": 1,
                        "buy_value": 12500, "sell_value": 4000}}



def source33_scenarios():
    """Deliberately constructed provider envelopes and resume states."""
    names = ["cash", "ocf", "assets", "liab", "equity", "curassets", "curliab",
             "retearn", "ebit", "ni", "revenue", "gross", "shares"]
    fact = {"end": "1999-12-31", "filed": "2000-01-01", "val": 30, "form": "20-F", "fp": "FY"}
    return {
        "row": {"ticker": "SYNACQUIRE", "cik": "42", "asof": "2000-01-01"},
        "series_names": names,
        "companyfacts": {"facts": {"us-gaap": {"CashAndCashEquivalentsAtCarryingValue":
                                              {"units": {"USD": [fact]}}}}},
        "shares": [{"end": "1999-12-31", "val": 100}],
        "failed_companyfacts": ["http_503", "timeout", "invalid_json", "invalid_shape", "empty"],
        "resume_statuses": [
            {"name": "legacy_all_empty", "empty": True, "status": None, "error": False, "retry": True},
            {"name": "empty_marked_complete", "empty": True, "status": "complete", "error": False, "retry": True},
            {"name": "partial_usable", "empty": False, "status": "partial", "error": False, "retry": True},
            {"name": "unavailable_usable", "empty": False, "status": "unavailable", "error": False, "retry": True},
            {"name": "legacy_with_error", "empty": False, "status": None, "error": True, "retry": True},
            {"name": "legacy_success", "empty": False, "status": None, "error": False, "retry": False},
            {"name": "complete_usable", "empty": False, "status": "complete", "error": False, "retry": False},
        ],
    }


def source33_regression_source():
    return '"""Generated acquisition/retry controls; all provider callbacks are synthetic."""\nimport ast\nfrom copy import deepcopy\nfrom datetime import date\nimport math\nfrom pathlib import Path\nimport re\nfrom types import SimpleNamespace\n\nimport pytest\n\nfrom make_fixtures import source33_scenarios\nfrom test_source32_contracts import _resume_runner\n\nROOT = Path(__file__).resolve().parents[2]\nCASE = source33_scenarios()\n\n\ndef _selected(path, names, supplied):\n    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))\n    available = {}\n    for node in tree.body:\n        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):\n            available[node.name] = node\n        elif isinstance(node, (ast.Assign, ast.AnnAssign)):\n            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:\n                if isinstance(target, ast.Name):\n                    available[target.id] = node\n    wanted, queue = set(names), list(names)\n    while queue:\n        for node in ast.walk(available[queue.pop()]):\n            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)\n                    and node.id in available and node.id not in wanted and node.id not in supplied):\n                wanted.add(node.id)\n                queue.append(node.id)\n    picked = [node for node in tree.body if any(node is available[name] for name in wanted)]\n    assert all(not getattr(node, "decorator_list", []) for node in picked)\n    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)\n    namespace = dict(supplied)\n    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *picked], type_ignores=[])),\n                 "<selected-production-functions>", "exec"), namespace)\n    return namespace\n\n\ndef _producer(events, shares):\n    requests, share_requests = [], []\n    events, shares = deepcopy(events), list(shares)\n\n    def http_get(url, **kwargs):\n        requests.append((url, kwargs))\n        event = events.pop(0)\n        if event == "timeout":\n            raise TimeoutError("synthetic transport timeout")\n\n        def payload():\n            if event == "invalid_json":\n                raise ValueError("synthetic JSON failure")\n            if event == "invalid_shape":\n                return {"facts": {"us-gaap": ["invalid"]}}\n            if event == "empty":\n                return {"facts": {"us-gaap": {}}}\n            return deepcopy(CASE["companyfacts"])\n\n        return SimpleNamespace(status_code=503 if event == "http_503" else 200, json=payload)\n\n    def share_pull(*args, **kwargs):\n        share_requests.append((args, kwargs))\n        event = shares.pop(0)\n        if event == "timeout":\n            raise TimeoutError("synthetic shares timeout")\n        return [] if event == "empty" else deepcopy(CASE["shares"])\n\n    selectors = _selected("tools/_deepdive_concepts.py",\n                          {"_concept_unit", "_fact_shape_valid", "_annual_entry",\n                           "_INSTANT_CONCEPTS", "REVENUE_CONCEPTS"},\n                          {"date": date, "math": math, "re": re})\n    dc = SimpleNamespace(**{key: value for key, value in selectors.items() if key != "__builtins__"})\n    dc.http_get = http_get\n    fast = _selected("docs/backtest-2026-06/distress_features_fast.py", {"get_facts", "pull_one"},\n                     {"DC": dc, "date": date, "REVENUE_CONCEPTS": selectors["REVENUE_CONCEPTS"],\n                      "_shares_series": share_pull})\n    return fast, requests, share_requests\n\n\n@pytest.mark.parametrize("event", CASE["failed_companyfacts"])\ndef test_actual_producer_failure_remains_retryable_and_is_not_negatively_cached(event):\n    fast, requests, share_requests = _producer([event, "ok"], ["timeout", "ok"])\n    row = deepcopy(CASE["row"])\n    first = fast["pull_one"](row)\n    assert row == CASE["row"]\n    assert len(first["series"]) == 13 and all(points == [] for points in first["series"].values())\n    assert first["acquisition_status"] == "unavailable"\n    assert fast["_cache"] == {}\n    snapshots, attempted = _resume_runner({"prior": [first], "tickers": ["SYNACQUIRE"],\n                                          "failures": [], "checkpoint": False})\n    assert attempted == ["SYNACQUIRE"] and len(snapshots[-1]) == 1\n    recovered = fast["pull_one"](first)\n    assert recovered["acquisition_status"] == "complete" and "pull_error" not in recovered\n    assert recovered["series"]["cash"][0]["val"] == 30\n    assert recovered["series"]["shares"] == CASE["shares"]\n    assert first["acquisition_status"] == "unavailable"\n    assert len(requests) == 2 and len(share_requests) == 2\n    assert len(fast["_cache"]) == 1\n\n\n@pytest.mark.parametrize("channel", ["companyfacts", "shares"])\ndef test_partial_acquisition_is_retained_and_retry_recovers(channel):\n    fast, requests, share_requests = _producer(["http_503", "ok"] if channel == "companyfacts" else ["ok"],\n                                              ["ok", "ok"] if channel == "companyfacts" else ["timeout", "ok"])\n    first = fast["pull_one"](CASE["row"])\n    assert first["acquisition_status"] == "partial" and any(first["series"].values())\n    snapshots, attempted = _resume_runner({"prior": [first], "tickers": [],\n                                          "failures": [], "checkpoint": False})\n    assert attempted == [] and snapshots[-1] == [first]\n    snapshots, attempted = _resume_runner({"prior": [first], "tickers": ["SYNACQUIRE"],\n                                          "failures": ["SYNACQUIRE"], "checkpoint": False})\n    assert attempted == ["SYNACQUIRE"]\n    assert snapshots[-1][0]["acquisition_status"] == "unavailable"\n    recovered = fast["pull_one"](first)\n    assert recovered["acquisition_status"] == "complete" and "pull_error" not in recovered\n    assert len(requests) == (2 if channel == "companyfacts" else 1)\n    assert len(share_requests) == 2\n\n\n@pytest.mark.parametrize("case", CASE["resume_statuses"], ids=lambda case: case["name"])\ndef test_resume_uses_evidence_and_explicit_status(case):\n    row = deepcopy(CASE["row"])\n    row["series"] = ({name: [] for name in CASE["series_names"]} if case["empty"]\n                     else {"cash": [{"end": "1999-12-31", "val": 30}]})\n    if case["status"] is not None:\n        row["acquisition_status"] = case["status"]\n    if case["error"]:\n        row["pull_error"] = "synthetic acquisition failure"\n    snapshots, attempted = _resume_runner({"prior": [row], "tickers": ["SYNACQUIRE"],\n                                          "failures": [], "checkpoint": False})\n    assert attempted == (["SYNACQUIRE"] if case["retry"] else [])\n    assert len(snapshots[-1]) == 1\n    if not case["retry"]:\n        assert snapshots[-1] == [row]\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--out', type=Path, help='write generated fixture files into this directory')
    args = parser.parse_args()
    destination = args.out if args.out is not None else ROOT/'tests/fixtures'
    outputs = [(destination/name, content) for name, content in generated().items()]
    outputs.extend((ROOT/name if args.out is None else destination/Path(name).name, content)
                   for name, content in source32_repository_examples().items())
    for path, content in outputs:
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise SystemExit('generated fixture mismatch: '+str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    print('synthetic fixtures match' if args.check else 'synthetic fixtures generated')




def source34_scenarios():
    """Invented acquisition, recall and reporting inputs; no recorded issuer outcomes."""
    cap = {"ticker": "SYNCAP", "cik": "901", "name": "AcmeCorp Synthetic Capital",
           "price": 32.0, "shares": 27_000_000, "value": 864_000_000.0,
           "large_cik": "902", "large_price": 32.0, "large_shares": 260_000_000,
           "large_value": 8_320_000_000.0}
    clean = {"ticker": "SYNOCF", "name": "AcmeCorp Synthetic Components",
             "mktcap": 720_000_000, "cash": 37_000_000, "net_income": -65_000_000,
             "ocf_latest": 54_000_000, "revenue": 960_000_000, "runway_periods": None,
             "flag_ocf_ni_divergence": True, "killflag_count": 0, "kf_going_concern": 0,
             "kf_substantial_doubt": 0, "kf_material_weakness": 0, "kf_death_spiral": 0,
             "kf_reverse_split": 0, "kf_scanned": True,
             "business_blurb": "AcmeCorp manufactures synthetic example components."}
    concentration = dict(clean, ticker="SYNCONC", name="AcmeCorp Synthetic Concentration",
                         net_income=14_000_000, ocf_latest=35_000_000,
                         flag_ocf_ni_divergence=False)
    recall_rows = [
        {"cik": "901", "ticker": "SYNRA", "name": "AcmeCorp Synthetic Alpha"},
        {"cik": "902", "ticker": "SYNRB", "name": "AcmeCorp Synthetic Beta & Co, Inc."},
        {"cik": "903", "ticker": "SYNRC", "name": "AcmeCorp Synthetic Gamma"},
    ]
    def browse(rows):
        return "".join(
            '<tr><td scope="row"><a href="x&amp;CIK=' + row["cik"].zfill(10)
            + '&amp;owner=include&amp;count=100&amp;type=10-K">'
            + row["cik"].zfill(10) + '</a></td><td scope="row">'
            + row["name"].replace("&", "&amp;") + "</td></tr>" for row in rows)
    union = {"rows": recall_rows, "html": browse(recall_rows[:2]),
             "page1": browse(recall_rows[:2]), "page2": browse(recall_rows[2:] + recall_rows[1:2]),
             "all_rows": browse(recall_rows), "other_cik": "904", "other_ticker": "SYNRD",
             "other_name": "AcmeCorp Synthetic Delta"}
    gold = ["SYNRD", "SYNRA", "SYNRC", "SYNRB", "SYNRF", "SYNRE"]
    universe = []
    for index, channel, large, illiquid in [
        (1, "both", False, False), (5, "fts", False, False),
        (2, "sic_reverse", False, False), (0, "both", True, False),
        (3, "fts", False, True),
    ]:
        universe.append({"name": "AcmeCorp Synthetic Recall " + str(index + 1),
                         "ticker": gold[index], "cik": str(920 + index), "sic": "7200",
                         "matched_phrase": "[sic_reverse]" if channel == "sic_reverse" else "synthetic-service",
                         "flag_too_big": large, "flag_illiquid": illiquid,
                         "band": "large" if large else "unknown" if illiquid else "deep",
                         "smallcap_candidate": not (large or illiquid), "recall_channel": channel})
    report_deep = {
        "ticker": "SYNREPORT",
        "derived": {"latest_revenue": 144_000_000, "latest_net_income": 12_000_000,
                    "latest_ocf": 28_000_000, "revenue_growth_pct": -27.0,
                    "concentration_flag": "kill",
                    "concentration_detail": "AcmeCorp synthetic program supplies 74% of revenue",
                    "fundamental_decline_flag": True, "contamination_ratio": 0.61,
                    "rev_slope_sign": -1, "latest_below_avg": True},
        "tenk": {"has_going_concern": False, "has_material_weakness": False, "has_death_spiral": False},
        "signals": {
            "price_divergence": {
                "price_return_6m": 0.12, "price_return_12m": 0.28, "price_source": "synthetic",
                "fundamental_trajectory": {"rev_slope_sign": -1, "contamination_ratio": 0.61,
                    "fundamental_decline_flag": True, "read_from": "deepdive_derived (NOT recomputed)"},
                "divergence_label": "melting_ice_cube_priced", "note": "fundamentals down, price elevated"},
            "ownership": {
                "recent_13d_13g": [
                    {"form": "SC 13D", "file_date": "2001-05-01", "filer": "AcmeCorp Synthetic Holder A"},
                    {"form": "SC 13G", "file_date": "2001-02-14", "filer": "AcmeCorp Synthetic Holder B"}],
                "recent_13d_13g_count": 2, "short_interest_pct": None, "short_trend": None,
                "staleness_note": "Synthetic unavailable short-interest evidence."},
            "signals_meta": {"diagnostic_only": True, "never_affects_buy": True,
                             "sources": ["synthetic price", "synthetic filing"],
                             "notes": "Diagnostic context is excluded from rating inputs."}}
    }
    report_value = {
        "ticker": "SYNREPORT", "mos_basis": "fcf_cap", "margin_of_safety_pct": 0.76,
        "nav_margin_of_safety_pct": None, "ev_sales": 1.1, "ev_ebitda": 4.2,
        "ebit_source": "OperatingIncomeLoss", "reverse_dcf_implied_growth": -12.0,
        "data_quality": ["capex_unavailable_fcf_uses_ocf_proxy",
                         "rdcf_implied_growth_very_negative:market_pricing_in_decline"],
        "buy_eligible": False,
        "buy_ineligible_reasons": ["concentration_flag=kill", "fundamental_decline_flag"]}
    acquisition = source33_scenarios()
    good = acquisition["companyfacts"]
    malformed = []
    for name, value in [
        ("concept_list", ["synthetic-invalid-concept"]),
        ("units_list", {"units": ["synthetic-invalid-units"]}),
        ("units_empty_list", {"units": []}),
        ("values_mapping", {"units": {"USD": {"synthetic": "invalid"}}}),
        ("value_scalar", {"units": {"USD": ["synthetic-invalid-fact"]}}),
        ("unusable_fact", {"units": {"USD": [{"end": "1999-12-31"}]}}),
    ]:
        malformed.append({"name": name, "payload": {"facts": {"us-gaap": {
            "CashAndCashEquivalentsAtCarryingValue": value}}}})
    return {
        "market_cap": cap, "positive_ocf": clean, "concentration_base": concentration,
        "recall_union": union,
        "recall": {"theme": "synthetic-recall", "gold": gold, "universe": universe},
        "shell": {"name": "AcmeCorp Synthetic Finance Subsidiary"},
        "cross_source": {
            "debt_mismatch": [18_000_000, 360_000_000, 72_000_000,
                              {"total_debt": 810_000_000, "revenue": 375_000_000, "shares_outstanding": 70_000_000}],
            "agreement": [180_000_000, 360_000_000, 72_000_000,
                          {"total_debt": 195_000_000, "revenue": 375_000_000, "shares_outstanding": 70_000_000}],
            "unavailable": [18_000_000, 360_000_000, 72_000_000, None],
            "revenue_mismatch": [180_000_000, 36_000_000, 72_000_000,
                                 {"total_debt": 195_000_000, "revenue": 375_000_000, "shares_outstanding": 70_000_000}],
            "floor": [250_000, 360_000_000, None,
                      {"total_debt": 810_000_000, "revenue": 375_000_000, "shares_outstanding": 70_000_000}]},
        "report": {"date": "2001-06-20", "deep": report_deep, "valuation": report_value},
        "signals": {"ticker": "SYNSIGNAL", "cik": "905", "base_date": [2000, 1, 1],
                    "declining": {"rev_slope_sign": -1, "contamination_ratio": 0.73,
                                  "fundamental_decline_flag": True},
                    "price_points": [[0, 20.0], [183, 22.0], [366, 25.0], [400, 28.0]]},
        "acquisition": {"row": acquisition["row"], "good": good, "shares": acquisition["shares"],
                        "malformed": malformed},
    }


def source34_regression_source():
    return '"""Generated Source34 controls use actual producers with synthetic I/O."""\nfrom copy import deepcopy\nfrom datetime import date\nimport io\nimport json\nimport math\nfrom pathlib import Path\nimport re\nfrom types import SimpleNamespace\n\nimport pytest\n\nfrom make_fixtures import source34_scenarios\nfrom test_source33_contracts import _selected\n\nCASE = source34_scenarios()\n\n\ndef _actual_run_sequence(payloads):\n    acquisition = CASE["acquisition"]\n    queued = deepcopy(payloads)\n    requests, share_requests, snapshots, cache_sizes = [], [], [], []\n    state = {"rows": []}\n\n    def http_get(url, **kwargs):\n        requests.append((url, kwargs))\n        payload = queued.pop(0)\n        return SimpleNamespace(status_code=200, json=lambda: deepcopy(payload))\n\n    def share_pull(*args, **kwargs):\n        share_requests.append((args, kwargs))\n        return deepcopy(acquisition["shares"])\n\n    selectors = _selected("tools/_deepdive_concepts.py",\n        {"_concept_unit", "_fact_shape_valid", "_annual_entry", "_INSTANT_CONCEPTS", "REVENUE_CONCEPTS"},\n        {"date": date, "math": math, "re": re})\n    dc = SimpleNamespace(**{k: v for k, v in selectors.items() if k != "__builtins__"})\n    dc.http_get = http_get\n    row = acquisition["row"]\n    panel = {"asof": row["asof"], "theme": "synthetic-acquisition",\n             "benchmark": {"total_return": 0.0},\n             "names": [{"ticker": row["ticker"], "cik": row["cik"], "total_return": 0.1,\n                        "forward_return": {"status": "ok", "entry_price": 12.0}}]}\n\n    def write_features(rows):\n        state["rows"] = deepcopy(rows)\n        snapshots.append(deepcopy(rows))\n\n    def fake_open(name):\n        assert name == "synthetic-panel"\n        return io.StringIO(json.dumps(panel))\n\n    class Future:\n        def __init__(self, callback, row):\n            self.callback, self.row = callback, row\n\n        def result(self):\n            return self.callback(self.row)\n\n    class Pool:\n        def __init__(self, **kwargs):\n            assert kwargs == {"max_workers": 6}\n\n        def __enter__(self):\n            return self\n\n        def __exit__(self, *args):\n            return False\n\n        def submit(self, callback, row):\n            return Future(callback, row)\n\n    fast = _selected("docs/backtest-2026-06/distress_features_fast.py",\n        {"get_facts", "pull_one", "run"},\n        {"DC": dc, "date": date, "REVENUE_CONCEPTS": selectors["REVENUE_CONCEPTS"],\n         "_shares_series": share_pull,\n         "features_path": lambda: SimpleNamespace(exists=lambda: bool(state["rows"])),\n         "backtest_files": lambda: ["synthetic-panel"],\n         "load_features": lambda: deepcopy(state["rows"]),\n         "write_features": write_features, "open": fake_open, "json": json,\n         "time": SimpleNamespace(time=lambda: 0.0), "ThreadPoolExecutor": Pool,\n         "as_completed": lambda futures: iter(futures),\n         "print": lambda *args, **kwargs: None})\n    request_counts, share_counts = [], []\n    for _ in range(3):\n        fast["run"]()\n        request_counts.append(len(requests))\n        share_counts.append(len(share_requests))\n        cache_sizes.append(len(fast["_cache"]))\n    assert fast["get_facts"](row["cik"]) == acquisition["good"]["facts"]["us-gaap"]\n    assert len(requests) == request_counts[-1]\n    return snapshots, request_counts, share_counts, cache_sizes, queued\n\n\n@pytest.mark.parametrize("case", CASE["acquisition"]["malformed"], ids=lambda case: case["name"])\ndef test_same_module_actual_run_recovers_after_nested_or_unusable_facts(case):\n    before = deepcopy(case)\n    rows, calls, shares, cache, queued = _actual_run_sequence(\n        [case["payload"], CASE["acquisition"]["good"]])\n    assert case == before\n    first, second, third = (batch[0] for batch in rows)\n    assert first["acquisition_status"] == "partial"\n    assert first["series"]["shares"] == CASE["acquisition"]["shares"]\n    assert not any(points for key, points in first["series"].items() if key != "shares")\n    assert second["acquisition_status"] == "complete" and "pull_error" not in second\n    assert second["series"]["cash"][0]["val"] == 30\n    assert second["series"]["shares"] == CASE["acquisition"]["shares"]\n    assert third == second\n    assert calls == [1, 2, 2] and shares == [1, 2, 2]\n    assert cache == [0, 1, 1] and queued == []\n\n\ndef test_successful_cache_and_complete_resume_remain_effective():\n    rows, calls, shares, cache, queued = _actual_run_sequence([CASE["acquisition"]["good"]])\n    assert all(batch[0]["acquisition_status"] == "complete" for batch in rows)\n    assert rows[0] == rows[1] == rows[2]\n    assert calls == [1, 1, 1] and shares == [1, 1, 1]\n    assert cache == [1, 1, 1] and queued == []\n\n\n@pytest.mark.parametrize("name,checked,mismatch,field", [\n    ("debt_mismatch", True, True, "total_debt"),\n    ("agreement", True, False, None),\n    ("unavailable", False, False, None),\n    ("revenue_mismatch", True, True, "revenue"),\n    ("floor", True, False, None),\n])\ndef test_generated_independent_source_inputs_preserve_comparator_branches(name, checked, mismatch, field):\n    core = _selected("tools/deepdive_data.py", {"_cross_source_check"}, {"math": math})\n    actual = core["_cross_source_check"](*deepcopy(CASE["cross_source"][name]))\n    assert actual[0] is checked and actual[1] is mismatch\n    if field is not None:\n        assert field in actual[2] and "ratio" in actual[2]\n'

def source35_regression_source():
    return '''"""Generated controls for internal async sockets and fixture isolation."""
import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def test_internal_socketpair_supports_asyncio_wakeup():
    left, right = socket.socketpair()
    try:
        left.send(b"synthetic")
        assert right.recv(9) == b"synthetic"
        with pytest.raises(pytest.fail.Exception, match="offline suite"):
            left.connect(("127.0.0.1", 1))
    finally:
        left.close()
        right.close()
    loop = asyncio.new_event_loop()
    try:
        result = loop.create_future()
        loop.call_soon_threadsafe(result.set_result, 17)
        assert loop.run_until_complete(result) == 17
    finally:
        loop.close()


@pytest.mark.parametrize("address", [("127.0.0.1", 1), ("192.0.2.1", 443)])
def test_ordinary_connections_remain_blocked(address):
    with socket.socket() as client:
        for method in ("connect", "connect_ex"):
            with pytest.raises(pytest.fail.Exception, match="offline suite"):
                getattr(client, method)(address)


@pytest.mark.parametrize("method", ["send", "sendall", "sendto"])
def test_unregistered_socket_sends_remain_blocked(method):
    with socket.socket() as client:
        with pytest.raises(pytest.fail.Exception, match="offline suite"):
            getattr(client, method)(b"synthetic")


def test_consumer_fixture_import_survives_tracker_import():
    tools = Path(__file__).resolve().parents[2] / "tools"
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
        "import track_forward; import make_fixtures; "
        "assert Path(make_fixtures.__file__).resolve().parent == Path(sys.argv[1]); "
        "assert callable(make_fixtures.tracking_scenarios)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", script, str(tools)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_fixture_cli_exports_every_declared_basename(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-I", str(root / "tools/make_fixtures.py"),
                             "--out", str(tmp_path)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    declared = json.loads((root / ".dataclass.json").read_text(encoding="utf-8"))["fixture"]
    assert declared
    for relative in declared:
        assert (tmp_path / Path(relative).name).read_bytes() == (root / relative).read_bytes()
'''


def source36_scenarios():
    """Synthetic final-review controls for assertion scope and existing guards."""
    concentration = []
    for name, extra in [("margin", "Gross margin was 80%."),
                        ("tax", "The effective tax rate was 45%."),
                        ("growth", "Total revenue grew 75%.")]:
        for order in ("before", "after"):
            customer = "One customer accounted for 10% of consolidated revenue."
            text = f"{extra} {customer}" if order == "before" else f"{customer} {extra}"
            concentration.append({"name": f"{name}_{order}", "text": text,
                                  "customer": 10, "program": None})
    concentration.extend([
        {"name": "comma_metrics", "text": "One customer accounted for 10% of consolidated revenue, while gross margin was 80%.", "customer": 10, "program": None},
        {"name": "conjoined_metrics", "text": "One customer accounted for 10% of consolidated revenue and gross margin was 80%.", "customer": 10, "program": None},
        {"name": "conjoined_before", "text": "Gross margin was 80% and one customer accounted for 10% of consolidated revenue.", "customer": 10, "program": None},
        {"name": "program_metrics", "text": "Our sole program represented 20% of total revenue. Gross margin was 80%.", "customer": None, "program": 20},
        {"name": "independent_classes", "text": "One customer accounted for 10% of total revenue, and our sole program represented 70% of total revenue. Gross margin was 85%.", "customer": 10, "program": 70},
        {"name": "abbreviation", "text": "The U.S. government accounted for 65% of total revenue. The effective tax rate was 85%.", "customer": 65, "program": None},
        {"name": "appositive", "text": "Our largest customer, AcmeCorp Inc., accounted for 65% of total revenue. Gross margin was 85%.", "customer": 65, "program": None},
        {"name": "annual_percentage_list", "text": "One customer accounted for 55%, 45%, and 35% of consolidated revenue in the last three years.", "customer": 55, "program": None},
        {"name": "mention_without_share", "text": "One customer was discussed in the revenue footnote and gross margin was 80%.", "customer": None, "program": None},
        {"name": "customer_revenue_growth", "text": "Revenue from one customer grew 80% during the year.", "customer": None, "program": None},
        {"name": "revenue_before_share", "text": "Revenue from one customer was 65%.", "customer": 65, "program": None},
        {"name": "revenue_before_percentage", "text": "Our largest customer accounted for total revenue of 65%.", "customer": None, "program": None},
        {"name": "receivables_percentage_list", "text": "Our largest customer represented 83% and 47%, respectively, of accounts receivable.", "customer": 83, "program": None},
        {"name": "coordinated_exports", "text": "One customer stopped purchasing, and exports accounted for 65% of consolidated revenue.", "customer": None, "program": None},
        {"name": "coordinated_exports_while", "text": "One customer stopped purchasing while exports accounted for 65% of consolidated revenue.", "customer": None, "program": None},
        {"name": "coordinated_exports_with_share", "text": "One customer accounted for 10% of consolidated revenue, and exports accounted for 65% of consolidated revenue.", "customer": 10, "program": None},
        {"name": "customer_with_affiliates", "text": "Our largest customer and its affiliates accounted for 65% of consolidated revenue.", "customer": 65, "program": None},
        {"name": "shared_subject_accounted", "text": "One customer bought our products and accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
        {"name": "shared_subject_represented", "text": "One customer purchased our products and represented 80% of net sales.", "customer": 80, "program": None},
        {"name": "shared_subject_but", "text": "One customer reduced orders but still accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
        {"name": "shared_subject_pronoun", "text": "One customer purchased our products and it accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
        {"name": "shared_subject_program", "text": "Our sole program expanded and generated 80% of consolidated revenue.", "customer": None, "program": 80},
        {"name": "named_customer_conjunction", "text": "Our largest customer, Acme and Sons Inc., accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
        {"name": "named_customer_plain_conjunction", "text": "Our largest customer, Acme and Sons, accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
        {"name": "coordinated_operations", "text": "One customer stopped purchasing, whereas foreign operations generated 65% of consolidated revenue.", "customer": None, "program": None},
        {"name": "percentage_led_exports", "text": "One customer stopped purchasing, and 65% of consolidated revenue came from exports.", "customer": None, "program": None},
        {"name": "percentage_led_exports_generated", "text": "One customer stopped purchasing, but 65% of consolidated revenue was generated by exports.", "customer": None, "program": None},
        {"name": "percentage_led_exports_approximate", "text": "One customer stopped purchasing, and approximately 65% of consolidated revenue came from exports.", "customer": None, "program": None},
        {"name": "percentage_led_customer", "text": "Gross profit increased, and 80% of consolidated revenue came from one customer.", "customer": 80, "program": None},
    ])
    for modifier in ("consistently", "ultimately", "directly", "almost always", "in every quarter"):
        concentration.append({"name": "shared_subject_modifier_" + modifier.replace(" ", "_"),
                              "text": "One customer bought our products and " + modifier
                                      + " accounted for 80% of consolidated revenue.",
                              "customer": 80, "program": None})
    for subject in ("Europe", "North America", "AcmeCorp", "Example Division LLC", "leasing activities"):
        concentration.append({"name": "distinct_subject_" + subject.replace(" ", "_"),
                              "text": "One customer stopped purchasing, while " + subject
                                      + " represented 65% of consolidated revenue.",
                              "customer": None, "program": None})
    concentration.extend([
        {"name": "shared_subject_auxiliary", "text": "One customer bought our products and has consistently accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
        {"name": "shared_subject_frequency", "text": "One customer bought our products and always represented 80% of net sales.", "customer": 80, "program": None},
        {"name": "named_customer_without_appositive", "text": "Our largest customer Acme and Sons Inc. accounted for 80% of consolidated revenue.", "customer": 80, "program": None},
    ])
    for modifier in ("in total", "in aggregate", "for several years"):
        concentration.append({"name": "shared_subject_adjunct_" + modifier.replace(" ", "_"),
                              "text": "One customer bought our products and " + modifier
                                      + " accounted for 80% of consolidated revenue.",
                              "customer": 80, "program": None})
    b_matrix = [
        ("One customer stopped purchasing, and exports accounted for 65% of consolidated revenue.", None, None),
        ("One customer stopped purchasing, and 65% of consolidated revenue came from exports.", None, None),
        ("One customer stopped purchasing, but 65% of consolidated revenue was generated by exports.", None, None),
        ("One customer stopped purchasing, while Europe represented 65% of consolidated revenue.", None, None),
        ("One customer accounted for 65% of consolidated revenue.", 65, None),
        ("Our largest customer expanded purchases and accounted for 65% of consolidated revenue.", 65, None),
        ("Our largest customer expanded purchases and it accounted for 65% of consolidated revenue.", 65, None),
        ("Our largest customer expanded purchases and still accounted for 65% of consolidated revenue.", 65, None),
        ("Our largest customer, AcmeCorp and Sons, accounted for 65% of consolidated revenue.", 65, None),
        ("One customer accounted for 30% of revenue and exports accounted for 65% of consolidated revenue.", 30, None),
        ("One customer accounted for 30%, 45%, and 65% of revenue in the last three years.", 65, None),
        ("One customer stopped purchasing. Exports accounted for 65% of consolidated revenue.", None, None),
        ("A single program accounted for 65% of consolidated revenue.", None, 65),
        ("Our largest customer expanded purchases and its orders accounted for 65% of consolidated revenue.", 65, None),
        ("One customer stopped purchasing, and our export business accounted for 65% of consolidated revenue.", None, None),
    ]
    b_matrix.extend(("Our largest customer expanded purchases and " + modifier
                     + " accounted for 65% of consolidated revenue.", 65, None)
                    for modifier in ("previously", "subsequently", "consistently", "nevertheless"))
    concentration.extend({"name": f"accumulated_b_{index:02d}", "text": text,
                          "customer": customer, "program": program}
                         for index, (text, customer, program) in enumerate(b_matrix, 1))
    concentration.append({"name": "unresolved_clause_is_explicit",
                          "text": "One customer bought our products and under revised arrangements accounted for 80% of consolidated revenue.",
                          "customer": None, "program": None, "ambiguous": True})
    for subject in ("assembly", "supply"):
        concentration.append({"name": "noun_with_adverb_suffix_" + subject,
                              "text": "One customer stopped purchasing, and " + subject
                                      + " accounted for 65% of consolidated revenue.",
                              "customer": None, "program": None, "ambiguous": True})
    for possessive in ("its", "their"):
        for subject in ("home market", "sector", "industry", "sales", "supplier",
                        "distribution network", "territory", "orders business"):
            concentration.append({"name": "unknown_possessive_" + possessive + "_" + subject.replace(" ", "_"),
                                  "text": "One customer stopped purchasing, and " + possessive + " " + subject
                                          + " accounted for 65% of consolidated revenue.",
                                  "customer": None, "program": None, "ambiguous": True})
        for relation in ("orders", "purchases", "affiliates"):
            for modifier in ("", "in total "):
                concentration.append({"name": "customer_relation_" + possessive + "_" + relation + "_" + modifier.strip().replace(" ", "_"),
                                      "text": "Our largest customer expanded purchases and " + possessive + " " + relation
                                              + " " + modifier + "accounted for 65% of consolidated revenue.",
                                      "customer": 65, "program": None})
    concentration.append({"name": "customer_relation_does_not_borrow_program",
                          "text": "Our sole program expanded and its purchases accounted for 65% of consolidated revenue.",
                          "customer": None, "program": None, "ambiguous": True})
    for case in concentration:
        if case["name"] in {"coordinated_exports", "coordinated_exports_while", "coordinated_operations",
                            "distinct_subject_leasing_activities", "accumulated_b_01"}:
            case["ambiguous"] = True
    for denominator in ("consolidated revenue", "revenue"):
        for connector in (", and ", " and ", ", while ", " while ", ", "):
            for customer_pct in (10, 80):
                margin = "Gross profit was 80% of " + denominator
                customer = f"one customer accounted for {customer_pct}% of {denominator}"
                concentration.append({
                    "name": f"gross_profit_share_{denominator}_{connector.strip()}_{customer_pct}",
                    "text": margin + connector + customer + ".",
                    "customer": customer_pct, "program": None})
    return {"concentration": concentration, "cik": "0009900001",
            "resolved_disclosures": "There is no substantial doubt about AcmeCorp ability to continue as a going concern. "
                                    "We have not identified any material weaknesses in internal control over financial reporting.",
            "invalid_ciks": [None, "", " ", "0", "0000000000", "unknown", True, "12345678901"]}


def source36_pit_submissions():
    """Generate issuer-bound submissions for the original offline PIT selftest."""
    return json.loads('{"sub_only_before": {"name": "ONLY BEFORE CO", "tickers": ["OBC"], "filings": {"recent": {"form": ["10-K"], "filingDate": ["2018-04-01"]}, "files": []}, "cik": "111111"}, "sub_only_after": {"name": "FUTURE CO", "tickers": ["FUT"], "filings": {"recent": {"form": ["10-K", "10-Q"], "filingDate": ["2021-03-15", "2021-08-10"]}, "files": []}, "cik": "222222"}, "sub_delisted": {"name": "BLEW UP INC", "tickers": ["BUI"], "filings": {"recent": {"form": ["10-K", "10-Q", "10-K"], "filingDate": ["2017-03-01", "2018-08-01", "2019-03-01"]}, "files": []}, "cik": "333333"}, "sub_active": {"name": "STILL HERE CORP", "tickers": ["SHC"], "filings": {"recent": {"form": ["10-K", "10-K", "10-K"], "filingDate": ["2019-03-01", "2021-03-01", "2023-03-01"]}, "files": []}, "cik": "444444"}, "sub_shard_main": {"name": "OLD TIMER CO", "tickers": ["OTC"], "filings": {"recent": {"form": ["8-K", "10-K"], "filingDate": ["2020-01-05", "2022-03-01"]}, "files": [{"name": "CIK0000555555-submissions-001.json"}]}, "cik": "555555"}}')


def source36_regression_source():
    return '''"""Generated final-review regressions; all inputs are synthetic."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_fixtures import (source36_scenarios, source22_scenarios,
    source25_equity_basis_scenarios, source32_legacy_scenarios,
    source26_debt_fixture, source28_annual_inputs, tracking_quote_scenarios,
    downstream_producer_completion_scenarios)
from test_private_runs import state
from test_financial_evidence import valuation_module
from test_stage_completion_contract import modules, Response
from test_tracking_integrity import tracker
from test_debt_evidence import debt_module
from test_downstream_completion import run_dir, sample as downstream_sample
from test_filing_disclosures import callers

CASE = source36_scenarios()


@pytest.mark.parametrize("case", CASE["concentration"], ids=lambda case: case["name"])
def test_percentage_belongs_to_its_concentration_assertion(modules, case):
    from _deepdive_flags import _extract_concentration, _concentration_flag
    customer, program, detail = _extract_concentration(case["text"])
    assert customer == case["customer"]
    assert program == case["program"]
    assert _concentration_flag(customer, program) == _concentration_flag(
        case["customer"], case["program"])
    if case.get("ambiguous"):
        assert "ambiguous" in detail


@pytest.mark.parametrize("case", CASE["concentration"], ids=lambda case: case["name"])
def test_concentration_assertion_scope_reaches_actual_screening(modules, monkeypatch, case):
    cheap = modules["cheap_pass"]
    from _deepdive_flags import _extract_concentration, _concentration_flag
    monkeypatch.setattr(cheap, "_extract_concentration", _extract_concentration)
    monkeypatch.setattr(cheap, "_concentration_flag", _concentration_flag)
    class Filings:
        def __len__(self):
            return 1
        def latest(self, count):
            return SimpleNamespace(text=lambda: CASE["resolved_disclosures"] + " " + case["text"])
    monkeypatch.setattr(cheap, "Company", lambda ticker: SimpleNamespace(get_filings=lambda **kw: Filings()))
    monkeypatch.setattr(cheap, "get_concept_series", lambda *args: [{"val": 1000000}])
    monkeypatch.setattr(cheap.time, "sleep", lambda seconds: None)
    result = cheap.health_check({"ticker": "SYNTH", "name": "AcmeCorp", "cik": CASE["cik"]})
    assert result["kf_scanned"] is True
    assert result["top_customer_pct"] == case["customer"]
    assert result["top_program_pct"] == case["program"]
    if case.get("ambiguous"):
        assert "ambiguous" in result["concentration_detail"]
    scored = cheap.score(cheap.pd.DataFrame([result])).iloc[0]
    expected_reject = _concentration_flag(case["customer"], case["program"]) == "kill"
    assert bool(scored["reject_concentration"]) == expected_reject
    assert bool(scored["rejected"]) == expected_reject
    assert result["disclosure_review_required"] is bool(case.get("ambiguous"))
    assert bool(scored["health_score_complete"]) is not bool(case.get("ambiguous"))


@pytest.mark.parametrize("case", [case for case in CASE["concentration"]
    if case["name"].startswith(("unknown_possessive_", "customer_relation_"))], ids=lambda case: case["name"])
def test_possessive_uncertainty_reaches_deepdive_completion(callers, case):
    cheap, tenk = callers(CASE["resolved_disclosures"] + " " + case["text"])
    ambiguous = bool(case.get("ambiguous"))
    assert all(item["flag"] is not None for item in tenk["disclosure_evidence"].values())
    assert cheap["disclosure_review_required"] is ambiguous
    assert tenk["disclosure_review_required"] is ambiguous
    data = downstream_producer_completion_scenarios()["pull_data"]
    data["tenk"] = tenk
    deep = importlib.import_module("deepdive_data")
    stages = importlib.import_module("filter_by_sic")
    upstream = stages.stage_completion("synthetic_source", 1, work=[stages.stage_work("synthetic_observation")])
    data["source_observations"] = {
        "financials": stages.stage_completion("sec_financial_observations", 1, upstream=[upstream]),
        "sic": stages.stage_completion("sec_submissions_sic", 1, upstream=[upstream]),
    }
    completion = deep._data_completion(data, {}, {}, upstream)
    assert ("concentration_ambiguous" in completion["reasons"]) is ambiguous
    assert (completion["status"] == "complete") is not ambiguous


@pytest.mark.parametrize("identity,expected", [
    ("Synthetic Analyst user1@example.com", "warn"),
    ("Synthetic Analyst USER1@EXAMPLE.COM", "warn"),
    ("Synthetic Analyst your-email@example.com", "warn"),
    ("", "warn"), ("Synthetic Analyst", "warn"),
    ("Synthetic Analyst user1@example-employer.com", "pass")])
def test_configuration_doctor_does_not_accept_example_identity(state, monkeypatch, capsys, identity, expected):
    config_path = Path(state["companion"]) / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sec_user_agent"] = identity
    config_path.write_text(json.dumps(config), encoding="utf-8")
    before = config_path.read_bytes()
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "100.0.0")
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("synthetic_identity_doctor", root / "scripts/verify_config.py")
    doctor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doctor)
    assert doctor.main(["--json"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    item = next(row for row in report["checks"] if row["name"] == "SEC identity configured")
    assert item["status"] == expected
    assert report["live_services_checked"] is False
    if identity:
        assert identity not in output
    assert config_path.read_bytes() == before and not Path(state["root"]).exists()


def _bound_decision_run(run_dir, sample, *, rating="BUY", confidence=80, eligible=True, valuation_eligible=True):
    from test_downstream_completion import gate, artifact, run_theme
    _, request, response = gate(run_dir, sample)
    _, survivors, _ = run_theme.persist_gate2_result(request, response)
    candidate = sample["candidates"][0]
    ticker = candidate["ticker"]
    report = ("```rating\\nrating: " + rating + "\\nconfidence: " + str(confidence)
              + "\\nverdict_date: 2026-01-15\\nmos_basis: fcf_cap\\nmos_pct: 20\\nbuy_eligible: "
              + json.dumps(eligible) + "\\nkillflag_count: 0\\n```\\n")
    (run_dir / ("report_" + ticker + ".md")).write_text(report, encoding="utf-8")
    identity = {"input_index": 0, **{key: candidate[key] for key in ("ticker", "cik", "band")}}
    artifact(run_dir / ("deepdive_" + ticker + "_" + sample["asof"] + ".json"),
             {"cik": candidate["cik"], "killflag_count": 0,
              "valuation": {"buy_eligible": valuation_eligible}},
             identity=identity, binding=run_theme._artifact_binding(survivors))
    return ticker


@pytest.mark.parametrize("eligible,valuation_eligible", [(False, True), (None, True), (True, False), (True, True)])
def test_finalization_cannot_complete_a_buy_that_fails_eligibility(run_dir, downstream_sample, monkeypatch,
                                                                eligible, valuation_eligible):
    from test_downstream_completion import invoke_finalizer, stages
    _bound_decision_run(run_dir, downstream_sample, eligible=eligible, valuation_eligible=valuation_eligible)
    if eligible is True and valuation_eligible is True:
        assert invoke_finalizer(run_dir, monkeypatch) == 0
        assert stages.read_stage_receipt(run_dir / "finalization.json", 1)["status"] == "complete"
    else:
        with pytest.raises(ValueError, match="BUY|eligib"):
            invoke_finalizer(run_dir, monkeypatch)
        assert not (run_dir / "deepdive_verdicts.json").exists()
        assert not (run_dir / "finalization.json").exists()


@pytest.mark.parametrize("rating", ["BUY", "AVOID"])
@pytest.mark.parametrize("percent", [0, 1, 2, 80, 100])
def test_report_percent_confidence_survives_finalizer_and_tracker(run_dir, downstream_sample, tracker,
                                                                monkeypatch, rating, percent):
    from test_downstream_completion import finalizer
    ticker = _bound_decision_run(run_dir, downstream_sample, rating=rating, confidence=percent)
    verdict = finalizer.build_verdict(ticker, run_dir, None)
    assert verdict["confidence"] == percent and verdict["confidence_unit"] == "percent"
    path = run_dir / "synthetic-verdicts.json"
    path.write_text(json.dumps([verdict]), encoding="utf-8")
    monkeypatch.setattr(tracker, "_fetch_close", lambda *args, **kwargs: 10.0)
    row, = tracker._build_verdicts_from_json(path)
    expected = percent / 100 if rating == "BUY" else 1 - percent / 100
    assert row["implied_prob"] == pytest.approx(min(0.999, max(0.001, expected)))
    assert row["confidence"] == percent / 100


@pytest.mark.parametrize("unit,value", [("unknown", 80), ("fraction", 2), ("percent", True)])
def test_invalid_confidence_units_fail_before_quote_lookup(tracker, tmp_path, monkeypatch, unit, value):
    path = tmp_path / "synthetic-unit-verdicts.json"
    path.write_text(json.dumps([{"ticker": "SYNTA", "rating": "BUY", "confidence": value,
                                "confidence_unit": unit}]), encoding="utf-8")
    def no_quote(*args, **kwargs):
        pytest.fail("invalid units must fail before quotes")
    monkeypatch.setattr(tracker, "_fetch_close", no_quote)
    with pytest.raises(ValueError):
        tracker._build_verdicts_from_json(path)


@pytest.mark.parametrize("status,expected", [(404, "complete"), (200, "complete"), (429, "partial"), (503, "partial")])
def test_absent_optional_concept_preserves_observation_completion(debt_module, monkeypatch, status, expected):
    import filter_by_sic as stages
    concepts = debt_module._dc
    annual = {"start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-01",
              "val": 100000000, "form": "10-K", "fp": "FY", "fy": 2024}
    payloads = iter([(200, {"cik": 9900001, "taxonomy": "us-gaap", "tag": "Revenues", "units": {"USD": [annual]}}),
                     (status, {"cik": 9900001, "taxonomy": "ifrs-full", "tag": "Revenue", "units": {"USD": []}})])
    def fetch(*args, **kwargs):
        code, payload = next(payloads)
        return SimpleNamespace(status_code=code, json=lambda: deepcopy(payload))
    monkeypatch.setattr(concepts, "http_get", fetch)
    with concepts.concept_observations() as observation:
        rows = concepts.concept_series_with_ifrs("9900001", ["Revenues"], ["Revenue"])
    assert rows[-1]["val"] == 100000000 and rows.completion["status"] == expected
    financials = observation.completion(1)
    assert financials["status"] == expected
    complete = stages.stage_completion("synthetic", 1, work=[stages.stage_work("synthetic")])
    data = {"financials": {name: [{"end": "2024-12-31", "val": 1}] for name in
            ("revenue", "net_income", "ocf", "cash", "shares_outstanding", "assets", "equity", "total_debt",
             "ebit", "dep_amort", "capex", "goodwill", "intangibles", "liabilities")},
            "derived": {}, "tenk": {"available": True}, "insider": {"available": True},
            "source_observations": {"financials": financials, "sic":
                stages.stage_completion("sec_submissions_sic", 1, work=[stages.stage_work("synthetic")])}}
    assert debt_module._data_completion(data, {}, {}, complete)["status"] == expected


@pytest.mark.parametrize("response_cik,expected", [("9900001", True), (9900001, True), ("0009900001", True),
                                                  ("9900002", False), (None, False), (True, False)])
def test_pit_submissions_must_prove_requested_issuer_before_attribution(modules, response_cik, expected):
    pit = modules["_pit_universe"]
    calls = []
    submissions = {"name": "AcmeCorp Synthetic", "tickers": ["SYNTA"],
                   "filings": {"recent": {"form": ["10-K"], "filingDate": ["2020-02-01"]}, "files": []}}
    if response_cik is not None:
        submissions["cik"] = response_cik
    def fetch(url, **kwargs):
        calls.append(url)
        payload = ({"cik": 9900001, "taxonomy": "dei", "tag": "TradingSymbol",
                    "units": {"pure": [{"filed": "2020-02-01", "val": "SYNTA"}]}}
                   if "/companyconcept/" in url else submissions)
        return SimpleNamespace(status_code=200, json=lambda: deepcopy(payload))
    evidence = {}
    row = pit.cik_periodic_asof("9900001", "2021-01-01", fetch=fetch, evidence=evidence)
    if expected:
        assert row["cik"] == "9900001" and row["ticker"] == "SYNTA"
        assert evidence["outcome"] == "periodic_observed"
    else:
        assert row is None and len(calls) == 1
        assert evidence["outcome"] == "unavailable"
        assert evidence["work"][0]["status"] == "invalid"


@pytest.mark.parametrize("cik", [True, 9900001.5, "0", "invalid"])
def test_pit_invalid_query_identity_fails_before_fetch(modules, cik):
    def no_fetch(*args, **kwargs):
        pytest.fail("invalid identity must fail before fetch")
    evidence = {}
    assert modules["_pit_universe"].cik_periodic_asof(cik, "2021-01-01", fetch=no_fetch, evidence=evidence) is None
    assert evidence["work"][0]["status"] == "invalid"


def test_existing_pit_selftest_retains_positive_identity_controls(modules):
    modules["_pit_universe"]._selftest()


def _discover(modules, monkeypatch, status, resolved):
    events = modules["discover_events"]
    concepts = importlib.import_module("_deepdive_concepts")
    source = source22_scenarios()
    page = next(item for item in source["html"] if item["records"] and item["status"] == "complete")
    monkeypatch.setattr(events, "today", lambda: source["asof"])
    response = Response(text=page["html"])
    response.url = source["response_url"]
    monkeypatch.setattr(events, "http_get", lambda *args, **kwargs: response)
    parsed = events.parse_cluster_page(page["html"], observed_date=source["asof"],
                                      response_url=source["response_url"])
    mapping = concepts._TickerObservations(
        {item["ticker"]: {"cik": CASE["cik"], "title": "AcmeCorp"}
         for item in parsed["records"]} if resolved else {},
        status=status, reason="" if status == "complete" else "request_failed")
    calls = []
    def tickers():
        calls.append("sec_tickers")
        return mapping
    monkeypatch.setattr(events, "_get_sec_tickers", tickers, raising=False)
    monkeypatch.setattr(events, "_yf_mktcap", lambda ticker: 10_000_000)
    monkeypatch.setattr(events.time, "sleep", lambda seconds: None)
    rows = events.discover_insider_clusters(enrich_mktcap=True)
    return rows, calls


@pytest.mark.parametrize("status,resolved,expected", [
    ("complete", True, "complete"), ("complete", False, "partial"),
    ("unavailable", False, "partial"), ("invalid", True, "invalid")])
def test_insider_identity_is_bound_before_admission(modules, monkeypatch, status, resolved, expected):
    rows, calls = _discover(modules, monkeypatch, status, resolved)
    assert rows and calls == ["sec_tickers"]
    assert rows.completion["status"] == expected
    assert rows.completion["upstream"][0]["status"] == status
    assert all(row["cik"] == (CASE["cik"] if resolved else "") for row in rows)
    if not resolved:
        assert any(work["reason"] == "unresolved_event_identity" for work in rows.completion["work"])
    stages = modules["filter_by_sic"]
    source_binding = {"artifact": "candidates_event_synthetic.json", "run_dir": "/synthetic"}
    cheap_binding = {"artifact": "cheappass_synthetic.csv", "run_dir": "/synthetic"}
    decisions = [dict(input_index=i, ticker=row["ticker"], cik=row["cik"], band=row["band"],
                      screening_decision="retained", evidence_complete=True)
                 for i, row in enumerate(rows)]
    cheap = stages.stage_completion("cheap_pass", len(rows),
        work=[stages.stage_work("synthetic_screening")], upstream=[rows.completion])
    cheap.update(input=source_binding, input_count=len(rows), decisions=decisions)
    screened = [dict(input_index=str(i), ticker=row["ticker"], cik=row["cik"], rejected="False",
                     kf_scanned="True", disclosure_review_required="False")
                for i, row in enumerate(rows)]
    admission = importlib.import_module("_event_admission")
    survivors, completion = admission.event_admission(rows, rows.completion, cheap,
        source_binding, cheap_binding, screened)
    assert completion["status"] == expected
    assert [row["cik"] for row in survivors] == [row["cik"] for row in rows]


@pytest.mark.parametrize("cik", CASE["invalid_ciks"])
def test_invalid_identity_cannot_issue_financial_queries(modules, monkeypatch, cik):
    cheap = modules["cheap_pass"]
    queries = []
    monkeypatch.setattr(cheap, "get_concept_series", lambda *args: queries.append(args) or [])
    monkeypatch.setattr(cheap.time, "sleep", lambda *args: None)
    monkeypatch.setattr(cheap, "killflag_scan", lambda *args: {})
    with pytest.raises(ValueError, match="issuer identity"):
        cheap.health_check({"ticker": "SYNTH", "name": "AcmeCorp", "cik": cik})
    assert queries == []


def test_resolved_identity_reaches_financial_queries(modules, monkeypatch):
    cheap = modules["cheap_pass"]
    queries = []
    monkeypatch.setattr(cheap, "get_concept_series", lambda *args: queries.append(args) or [])
    monkeypatch.setattr(cheap.time, "sleep", lambda *args: None)
    monkeypatch.setattr(cheap, "killflag_scan", lambda *args: {})
    cheap.health_check({"ticker": "SYNTH", "name": "AcmeCorp", "cik": CASE["cik"]})
    assert len(queries) == 5
    assert all(cik == CASE["cik"] for cik, concept in queries)


def test_current_and_stale_debt_have_distinct_eligibility(valuation_module):
    from _deepdive_flags import _check_debt_quality
    base = deepcopy(source25_equity_basis_scenarios()[0]["data"])
    base["derived"].update(latest_goodwill=0, latest_intangibles=0, lessor_asset_heavy=True)
    results = []
    for stale in (False, True):
        data = deepcopy(base)
        if stale:
            data["financials"]["total_debt"][0]["end"] = "2020-12-31"
        data["derived"]["debt_stale"] = _check_debt_quality(
            data["financials"]["total_debt"], data["financials"]["assets"],
            data["financials"]["equity"], [])[1]
        assert data["derived"]["debt_stale"] is stale
        results.append(valuation_module.compute_valuation(data, 80_000_000,
            dict(valuation_module._VALUATION_DEFAULTS)))
    current, stale = results
    assert current["mos_basis"] == stale["mos_basis"] == "nav"
    assert current["buy_eligible"] is True
    assert stale["buy_eligible"] is False
    assert "debt_stale" in stale["buy_ineligible_reasons"]
    assert "debt_stale" not in current["buy_ineligible_reasons"]


def test_lumpy_ocf_blocks_buy_without_changing_normalization(valuation_module):
    from _deepdive_flags import _trajectory_fields
    data = source32_legacy_scenarios()["valuation_lumpy"]
    source28_annual_inputs(data)
    data = source26_debt_fixture(data)
    data["derived"].update(_trajectory_fields(data["financials"]["revenue"],
        data["financials"]["ocf"], [{"end": "2024-12-31", "val": 15_000_000}]))
    before = deepcopy(data)
    value = valuation_module.compute_valuation(data, 250_000_000,
        dict(valuation_module._VALUATION_DEFAULTS))
    assert data == before
    assert value["mos_basis"] == "fcf_cap" and value["margin_of_safety_pct"] > 0.30
    assert value["lumpy_ocf_normalization_suspect"] is True
    assert value["buy_eligible"] is False
    assert "lumpy_ocf_normalization_suspect" in value["buy_ineligible_reasons"]
    assert "debt_stale" not in value["buy_ineligible_reasons"]


@pytest.mark.parametrize("stock_return,expected_rate", [(-50.0, 0.0), (50.0, 1.0)])
def test_scorecard_names_the_above_threshold_population(tracker, monkeypatch, stock_return, expected_rate):
    row = dict(tracking_quote_scenarios()["base_row"], rating="避开", scored=True,
               stock_return_pct_unrounded=stock_return, stock_return_pct=stock_return,
               realized_excess_pct_unrounded=stock_return, realized_excess_pct=stock_return,
               favorable=stock_return > 0, brier=0.04, implied_prob=0.8)
    before = deepcopy(row)
    monkeypatch.setattr(tracker, "_load_verdicts", lambda: [row])
    tracker.cmd_scorecard(SimpleNamespace())
    assert row == before
    assert tracker._risk_metric_summary([row], "avoidance", -0.4)["rate"] == expected_rate
    text = tracker.SCORECARD_FILE.read_text(encoding="utf-8")
    metric = next(line for line in text.splitlines() if line.startswith("| Above-threshold outcome rate"))
    assert "total return > -40%" in metric
    assert f"| {expected_rate * 100:.1f}% | 1 |" in metric
    assert "does not establish successful loss avoidance" in text
    assert "Blowup-avoidance" not in text
'''


if __name__ == '__main__':
    main()
