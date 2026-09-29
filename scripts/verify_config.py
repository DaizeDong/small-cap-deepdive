#!/usr/bin/env python3
"""Check local config, PRIVATE output proof and dependencies without writing DATA.

--json prints one object. Offline checks do not establish live SEC, market or
model readiness. Config values containing identity are never echoed.
"""
import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

_REPO = Path(__file__).resolve().parents[1]
_NUMERIC = ('market_cap_max', 'watch_band_max', 'micro_cap_max', 'min_dollar_vol',
            'normalize_years', 'wacc', 'cap_rate_low', 'cap_rate_high', 'cyclical_cv_threshold')


def _version(value):
    match = re.match(r'(\d+)\.(\d+)(?:\.(\d+))?', value)
    if match is None:
        raise ValueError('unrecognized installed version')
    return tuple(int(part or 0) for part in match.groups())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-dir')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.config_dir:
        os.environ['SMALL_CAP_DEEPDIVE_CONFIG_DIR'] = args.config_dir
    checks = []
    reports_root = None

    def check(name, ok, detail='', warning=False):
        checks.append({'name': name, 'status': 'pass' if ok else ('warn' if warning else 'fail'),
                       'diagnostic': detail if not ok else ''})

    sys.path.insert(0, str(_REPO/'tools'))
    try:
        from _common import load_config, output_root
        config = load_config()
        reports_root = str(output_root())
        check('PRIVATE companion, config and output root', True)
        check('schema_version', config.get('schema_version') == 1, 'schema_version must equal 1')
        for name in _NUMERIC:
            try:
                float(config[name])
                check(name+' numeric', True)
            except (KeyError, TypeError, ValueError):
                check(name+' numeric', False, 'set a numeric '+name)
        for name in ('output_dir', 'python_cmd', 'insider_source'):
            check(name+' present', bool(str(config.get(name, '')).strip()), 'missing '+name)
        check('sic_hard_exclude list', isinstance(config.get('sic_hard_exclude'), list),
              'sic_hard_exclude must be a list')
        identity = str(config.get('sec_user_agent', ''))
        check('SEC identity configured', '@' in identity and 'your-email@example.com' not in identity,
              'set sec_user_agent privately before live SEC use; no live check was performed', warning=True)
    except (OSError, RuntimeError, ValueError, KeyError, ImportError) as exc:
        check('PRIVATE companion, config and output root', False, str(exc))

    try:
        requirements = (_REPO/'tools/requirements.txt').read_text(encoding='utf-8').splitlines()
        for requirement in requirements:
            if not requirement.strip() or requirement.lstrip().startswith('#'):
                continue
            distribution, minimum = requirement.strip().split('>=', 1)
            module = 'edgar' if distribution == 'edgartools' else distribution
            try:
                found = importlib.util.find_spec(module) is not None
                installed = importlib.metadata.version(distribution)
                ok = found and _version(installed) >= _version(minimum)
                check('dependency '+distribution, ok, 'requires '+requirement.strip())
            except (ImportError, ValueError, importlib.metadata.PackageNotFoundError):
                check('dependency '+distribution, False, 'install declared requirement '+requirement.strip())
    except (OSError, ValueError) as exc:
        check('dependency declarations', False, str(exc))

    ready = not any(item['status'] == 'fail' for item in checks)
    report = {'status': 'ready' if ready else 'not_ready', 'reports_root': reports_root,
              'scope': 'local_configuration_only', 'live_services_checked': False, 'checks': checks}
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print('Small-cap local configuration doctor')
        for item in checks:
            print('[%s] %s%s' % (item['status'].upper(), item['name'],
                                 ': '+item['diagnostic'] if item['diagnostic'] else ''))
        print(report['status'].upper()+': local checks only; live SEC/market/model services were not checked')
    return 0 if ready else 1


if __name__ == '__main__':
    raise SystemExit(main())
