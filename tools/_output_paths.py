"""Canonical PRIVATE GitHub destination proof, with no import-time discovery."""
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
from urllib.parse import urlsplit

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class OutputPathError(RuntimeError):
    """A destination could not be proved safe for private runtime data."""


def _query(arguments):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, encoding='utf-8', timeout=20,
                                env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OutputPathError('PRIVATE destination verification requires working Git and gh commands') from exc
    if result.returncode:
        raise OutputPathError('PRIVATE destination verification failed: '+arguments[0])
    return result.stdout.strip()


def _repository(existing):
    for candidate in (existing, *existing.parents):
        marker = candidate/'.git'
        if os.path.lexists(marker):
            if not marker.is_file() and not marker.is_dir():
                raise OutputPathError('invalid Git worktree marker')
            resolved = Path(_query(['git', '-C', str(candidate), 'rev-parse', '--show-toplevel'])).resolve()
            if resolved != candidate:
                raise OutputPathError('nearest Git marker does not identify its enclosing worktree')
            return resolved
        if (candidate/'HEAD').is_file() and (candidate/'objects').is_dir():
            raise OutputPathError('output requires a worktree, not a bare repository')
    raise OutputPathError('output requires a versioned PRIVATE companion with an origin remote')


def _ssh_hostname(alias):
    """Read ordinary user Host/HostName rules without invoking SSH or commands."""
    try:
        lines = (Path.home()/'.ssh/config').read_text(encoding='utf-8').splitlines()
        active, hostname = True, None
        for line in lines:
            tokens = shlex.split(re.sub(r'^(\s*\w+)\s*=\s*', r'\1 ', line), comments=True)
            if not tokens:
                continue
            keyword, values = tokens[0].lower(), tokens[1:]
            if keyword in {'include', 'match'} or keyword.startswith('canonicalize') or keyword == 'canonicaldomains':
                raise OutputPathError('SSH alias verification supports only ordinary Host/HostName rules')
            if keyword == 'host':
                if not values:
                    raise OutputPathError('SSH Host rule has no patterns')
                positive, negated = False, False
                for pattern in values:
                    expression = re.escape(pattern.removeprefix('!').lower()).replace(r'\*', '.*').replace(r'\?', '.')
                    if re.fullmatch(expression, alias.lower()):
                        if pattern.startswith('!'):
                            negated = True
                        else:
                            positive = True
                active = positive and not negated
            elif keyword == 'hostname':
                if len(values) != 1:
                    raise OutputPathError('SSH HostName rule must contain one hostname')
                if active and hostname is None:
                    hostname = values[0].lower()
        return hostname or ('github.com' if alias.lower() == 'github.com' else None)
    except FileNotFoundError as exc:
        if alias.lower() == 'github.com':
            return 'github.com'
        raise OutputPathError('cannot resolve SSH alias without SSH configuration') from exc
    except (OSError, ValueError) as exc:
        raise OutputPathError('cannot resolve SSH alias from ordinary user SSH configuration') from exc


def _github_identity(remote):
    is_ssh = True
    if '://' in remote:
        parsed = urlsplit(remote)
        if parsed.scheme not in {'https', 'ssh'} or parsed.password or parsed.query or parsed.fragment:
            raise OutputPathError('unsupported companion origin')
        host, name = parsed.hostname, parsed.path.lstrip('/')
        is_ssh = parsed.scheme == 'ssh'
    else:
        parsed = re.fullmatch(r'(?:[^@/:\s]+@)?([^/:\s]+):([^\s]+)', remote)
        if parsed is None:
            raise OutputPathError('companion origin must identify a GitHub repository')
        host, name = parsed.groups()
    host = host.lower() if host else None
    if is_ssh and host:
        host = _ssh_hostname(host)
    if host != 'github.com':
        raise OutputPathError('companion origin must use github.com for visibility verification')
    name = name.removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name):
        raise OutputPathError('invalid GitHub companion identity')
    return name


def _prove_private_remotes(repository):
    """Check all effective fetch and push URLs against their explicit GitHub host."""
    prefix = ['git', '-C', str(repository), 'remote']
    remotes = _query(prefix).splitlines()
    if 'origin' not in remotes:
        raise OutputPathError('PRIVATE companion requires an origin remote')
    identities = set()
    for remote in remotes:
        if not remote or remote.startswith('-'):
            raise OutputPathError('invalid companion remote name')
        for direction in ([], ['--push']):
            urls = _query([*prefix, 'get-url', *direction, '--all', remote]).splitlines()
            if not urls:
                raise OutputPathError('companion remote has no verifiable destination')
            identities.update(_github_identity(url) for url in urls)
    for identity in sorted(identities):
        answer = json.loads(_query(['gh', 'repo', 'view', 'https://github.com/' + identity,
                                    '--json', 'visibility']))
        if not isinstance(answer, dict) or answer.get('visibility') != 'PRIVATE':
            raise OutputPathError('output companion is PUBLIC or its visibility is unknown')


def prove_output_path(requested):
    """Return the canonical target after proving its actual enclosing repository PRIVATE."""
    path = Path(requested).expanduser()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    if any(part.lower() == '.git' or ':' in part or part.endswith((' ', '.')) for part in parts):
        raise OutputPathError('ambiguous or reserved output path')
    try:
        path = path.resolve()
        if path.is_relative_to(SOURCE_ROOT) or SOURCE_ROOT.is_relative_to(path):
            raise OutputPathError('runtime output must be outside the tool source in a separate PRIVATE companion')
        existing = path
        while True:
            try:
                info = existing.stat()
                break
            except FileNotFoundError:
                if existing == existing.parent:
                    raise OutputPathError('cannot find an existing output ancestor')
                existing = existing.parent
        if stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                raise OutputPathError('runtime output cannot use a hardlinked file')
            existing = existing.parent
        elif not stat.S_ISDIR(info.st_mode):
            raise OutputPathError('runtime output requires an ordinary file or directory')
        repository = _repository(existing)
        if not path.is_relative_to(repository) or SOURCE_ROOT.is_relative_to(repository):
            raise OutputPathError('runtime output requires a separate PRIVATE worktree')
        _prove_private_remotes(repository)
        return path
    except (OSError, ValueError) as exc:
        raise OutputPathError('cannot prove PRIVATE output destination: '+str(exc)) from exc


def prepare_output(requested):
    """Prove before creating parents, then prove the actual final file destination again."""
    path = prove_output_path(requested)
    path.parent.mkdir(parents=True, exist_ok=True)
    return prove_output_path(path)
