"""Lazy shared configuration and PRIVATE output paths for small-cap tools."""
from __future__ import annotations
from collections.abc import MutableMapping
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone

from _output_paths import prove_output_path, prepare_output

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_REF = _REPO / "reference"
_CONFIG_DIR_ENV_VARS = ("SMALL_CAP_DEEPDIVE_CONFIG_DIR", "SMALL_CAP_DEEPDIVE_CONFIG")


class ConfigNotInitialized(RuntimeError):
    pass


CONFIG_SETUP_HINT = (
    "small-cap-deepdive is UNINITIALIZED. Set SMALL_CAP_DEEPDIVE_CONFIG_DIR to your "
    "versioned PRIVATE companion containing config.json, copied from "
    "reference/config.example.json. Initialize the pinned resolver with "
    "git submodule update --init --recursive -- guards. "
    "Runtime output never falls back to the tool source, cwd or system Temp."
)


def _companion_root():
    """Use the pinned resolver, bound to this consumer including linked worktrees."""
    path = _REPO/'guards/tools/datadir.py'
    if not path.is_file():
        raise ConfigNotInitialized(CONFIG_SETUP_HINT)
    spec = importlib.util.spec_from_file_location('_smallcap_pinned_datadir', path)
    if spec is None or spec.loader is None:
        raise ConfigNotInitialized('cannot load pinned guards resolver; '+CONFIG_SETUP_HINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._own_repo_root = lambda: str(_REPO)
    module._config_env_vars = lambda skill: _CONFIG_DIR_ENV_VARS
    for selector in (*_CONFIG_DIR_ENV_VARS, 'SMALL_CAP_DEEPDIVE_DATA_DIR'):
        if os.environ.get(selector) and not Path(os.environ[selector]).expanduser().is_dir():
            raise ConfigNotInitialized(selector+' names a missing companion directory')
    companion = module.resolve_companion_root('small-cap-deepdive')
    if companion is None:
        raise ConfigNotInitialized(CONFIG_SETUP_HINT)
    return prove_output_path(companion)


def resolve_config_json() -> Path | None:
    """Resolve config through the same proved companion used for output."""
    path = _companion_root()/'config.json'
    return prove_output_path(path) if path.is_file() else None


def config_json_path() -> Path:
    path = resolve_config_json()
    if path is None:
        raise ConfigNotInitialized(CONFIG_SETUP_HINT)
    return path


def _numeric_setting(key, value, expected_type):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        raise ConfigNotInitialized(f'{key} must be a finite number')
    if expected_type is int and type(value) is float and not value.is_integer():
        raise ConfigNotInitialized(f'{key} must be an integer')
    try:
        result = expected_type(value)
    except (OverflowError, ValueError) as exc:
        raise ConfigNotInitialized(f'{key} is outside the supported numeric range') from exc
    if type(result) is float and not math.isfinite(result):
        raise ConfigNotInitialized(f'{key} must be a finite number')
    return result


def load_config() -> dict:
    real = config_json_path()
    defaults = json.loads((_REF/'config.example.json').read_text(encoding='utf-8'))
    overlay = json.loads(real.read_text(encoding='utf-8'))
    if not isinstance(overlay, dict):
        raise ConfigNotInitialized('config.json must contain an object')
    numeric_types = {key: type(value) for key, value in defaults.items()
                     if type(value) in (int, float)}
    defaults.update(overlay)
    for key in list(defaults):
        value = os.environ.get('SMALLCAP_'+key.upper())
        if value is not None:
            if key in numeric_types:
                try:
                    value = json.loads(value)
                except (ValueError, TypeError) as exc:
                    raise ConfigNotInitialized(f'{key} requires a numeric environment value') from exc
            defaults[key] = value
        if key in numeric_types:
            defaults[key] = _numeric_setting(key, defaults[key], numeric_types[key])
    return defaults


class _LazyMapping(MutableMapping):
    def __init__(self, loader):
        self.loader = loader
        self._data = None

    def _values(self):
        if self._data is None:
            self._data = self.loader()
        return self._data

    def __getitem__(self, key):
        return self._values()[key]

    def __setitem__(self, key, value):
        self._values()[key] = value

    def __delitem__(self, key):
        del self._values()[key]

    def __iter__(self):
        return iter(self._values())

    def __len__(self):
        return len(self._values())


CFG = _LazyMapping(load_config)
UA = _LazyMapping(lambda: {'User-Agent': CFG['sec_user_agent']})


def _resolve_output_dir(raw):
    if not isinstance(raw, (str, os.PathLike)) or not str(raw).strip():
        raise ConfigNotInitialized('output_dir must be a nonempty path')
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = _companion_root()/path
    return prove_output_path(path)


def output_root() -> Path:
    """Return the absolute PRIVATE unbatched root without creating directories."""
    return _resolve_output_dir(load_config()['output_dir'])


def validate_run_name(name: str) -> str:
    if not isinstance(name, str) or not name or not name.strip('.'):
        raise ValueError('run name must be a nonempty directory component')
    if name != name.strip() or name.endswith('.') or any(
            char in '/\\:<>"|?*' or ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError('run name contains unsafe path syntax or control characters')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                     *(f'COM{i}' for i in range(1, 10)),
                                     *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('reserved run name')
    return name


def reports_dir() -> Path:
    root = output_root()
    run = os.environ.get('SMALLCAP_RUN', '')
    if not run:
        return root
    destination = prove_output_path(root/validate_run_name(run))
    if destination.parent != root or destination.name != run:
        raise ValueError('active run escapes its configured root')
    return destination


class _LazyReports(os.PathLike):
    """Compatibility path for existing writers; every final child is proved."""
    def __fspath__(self):
        return str(reports_dir())

    def __str__(self):
        return str(reports_dir())

    def __truediv__(self, name):
        base = reports_dir()
        path = prove_output_path(base/name)
        if not path.is_relative_to(base):
            raise ValueError('default report path escapes the active reports directory')
        return prepare_output(path)

    def __getattr__(self, name):
        return getattr(reports_dir(), name)


REPORTS = _LazyReports()


def init_edgar() -> None:
    from edgar import set_identity
    set_identity(CFG['sec_user_agent'])


def run_state_path(run: str | None = None, pid: int | None = None) -> Path:
    """Use the environment when omitted; an empty run selects process-scoped state."""
    selected = os.environ.get('SMALLCAP_RUN', '') if run is None else run
    if selected != '':
        selected = validate_run_name(selected)
    root = output_root()
    if selected:
        directory = prove_output_path(root/selected)
        if directory.parent != root or directory.name != selected:
            raise ValueError('run state escapes its configured root')
        return prove_output_path(directory/'_run_state.txt')
    process = os.getpid() if pid is None else int(pid)
    if process <= 0:
        raise ValueError('pid must be positive')
    return prove_output_path(root/f'_run_state_{process}.txt')

def slug(name: str) -> str:
    return re.sub(r"\W+", "_", str(name).lower())[:40].strip("_")

def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def http_get(url: str, params: dict | None = None, timeout: int = 25, retries: int = 4) -> requests.Response:
    import requests
    last = None
    for attempt in range(retries):
        last = requests.get(url, headers=UA, params=params, timeout=timeout)
        if last.status_code in (429, 500):
            time.sleep(2 ** attempt * 1.5)
            continue
        return last
    return last


# ---------------------------------------------------------------------------
# Market-cap resolution (P5), decouple mktcap from yfinance.
#
# yfinance market cap is null for a large fraction of small/foreign tickers,
# and the theme path used to DROP those rows (flag_no_mktcap). That silently
# discarded 91-100% of some themes before any gate (synthesis / data_robustness
# F5). The fix: a fallback chain, yfinance -> SEC companyfacts shares x price ,
# and, when mktcap is still genuinely unresolvable, tag band="unknown" and let
# the row FLOW THROUGH the gates (mirroring discover_events.py:_band, which
# already keeps null as "unknown" rather than dropping pre-listing spinoffs).
# ---------------------------------------------------------------------------

_DEI_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/{concept}.json"
_GAAP_FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"


def sec_shares_outstanding(cik: str | int | None) -> float | None:
    """Latest reported shares-outstanding for a CIK via SEC companyconcept.

    Free, no-key fallback for market-cap reconstruction when yfinance returns
    null. Fallback chain mirrors deepdive_data._shares_series ordering:
      1. dei:EntityCommonStockSharesOutstanding (cover-page count; most current)
      2. us-gaap:CommonStockSharesOutstanding   (period-end balance-sheet count)
    Returns the value at the latest "end" date, or None on any failure.
    """
    if cik is None or str(cik).strip() in ("", "nan"):
        return None
    cik10 = str(cik).split(".")[0].strip().zfill(10)
    for url in (
        _DEI_FACTS.format(cik=cik10, concept="EntityCommonStockSharesOutstanding"),
        _GAAP_FACTS.format(cik=cik10, concept="CommonStockSharesOutstanding"),
    ):
        try:
            r = http_get(url, timeout=20)
            if r.status_code != 200:
                continue
            units = r.json().get("units", {})
            vals = units.get("shares") or []
            dated = [v for v in vals if v.get("end") and v.get("val") is not None]
            if not dated:
                continue
            latest = max(dated, key=lambda v: v["end"])
            val = float(latest["val"])
            if val > 0:
                return val
        except Exception:
            continue
    return None


def resolve_mktcap(
    yf_mktcap: float | None,
    price: float | None,
    cik: str | int | None,
    shares_fn=sec_shares_outstanding,
) -> tuple[float | None, str]:
    """Resolve market cap via a fallback chain. Returns (mktcap, source).

    source ∈ {"yfinance", "sec_shares_x_price", "unresolved"}.
      1. yfinance marketCap (already-available free source) if positive.
      2. SEC companyfacts shares-outstanding x last price (both must be positive).
      3. unresolved -> (None, "unresolved"); caller tags band="unknown" and flows
         the row through instead of dropping it.
    shares_fn is injectable for selftest (avoids a network call).
    """
    if yf_mktcap is not None and yf_mktcap > 0:
        return float(yf_mktcap), "yfinance"
    if price is not None and price > 0:
        shares = shares_fn(cik)
        if shares is not None and shares > 0:
            return float(shares) * float(price), "sec_shares_x_price"
    return None, "unresolved"


def band_for(mktcap: float | None, max_mcap: float | None = None,
             watch_max: float | None = None) -> str:
    """Single source of truth for market-cap band tagging.

    Mirrors discover_events.py:_band so the theme path and event path agree:
      "deep"    = mktcap < max_mcap           → full deep-dive
      "watch"   = max_mcap..watch_max         → surface separately, no deep-dive
      "large"   = > watch_max                 → out of scope, no deep-dive (flag, flow through)
      "unknown" = mktcap missing/unresolvable → process (do NOT drop; flow through gates)

    Previously discover.apply_filters returned band=None for BOTH null mktcap AND
    >watch_max, and null-mktcap rows were dropped (flag_no_mktcap). null now maps
    to "unknown" and flows through; oversize maps to "large" and is flagged, not
    silently conflated with no-data.
    """
    if max_mcap is None:
        max_mcap = CFG.get("market_cap_max", 2_000_000_000)
    if watch_max is None:
        watch_max = CFG.get("watch_band_max", 5_000_000_000)
    # None / NaN (mktcap != mktcap) / non-positive => unknown (flow through, not drop).
    if mktcap is None or mktcap != mktcap or mktcap <= 0:
        return "unknown"
    if mktcap < max_mcap:
        return "deep"
    if mktcap < watch_max:
        return "watch"
    return "large"


def _selftest() -> None:
    """P5 market-cap fallback + band-tagging unit assertions."""
    from make_fixtures import source34_scenarios
    _cap = source34_scenarios()["market_cap"]
    # resolve_mktcap: yfinance wins when present
    mc, src = resolve_mktcap(1.5e9, 10.0, _cap["cik"], shares_fn=lambda c: 5e6)
    assert mc == 1.5e9 and src == "yfinance", f"yfinance branch: {mc},{src}"
    # resolve_mktcap: SEC shares x price fallback when yfinance null
    mc, src = resolve_mktcap(None, 10.0, _cap["cik"], shares_fn=lambda c: 5e6)
    assert mc == 5e7 and src == "sec_shares_x_price", f"sec fallback: {mc},{src}"
    # resolve_mktcap: genuinely unresolvable -> (None, "unresolved"), NOT a crash/drop
    mc, src = resolve_mktcap(None, None, _cap["cik"], shares_fn=lambda c: 5e6)
    assert mc is None and src == "unresolved", f"no-price unresolved: {mc},{src}"
    mc, src = resolve_mktcap(None, 10.0, _cap["cik"], shares_fn=lambda c: None)
    assert mc is None and src == "unresolved", f"no-shares unresolved: {mc},{src}"
    mc, src = resolve_mktcap(0, 10.0, None, shares_fn=lambda c: None)
    assert mc is None and src == "unresolved", f"zero-yf no-cik unresolved: {mc},{src}"

    # band_for: null/zero mktcap => "unknown" (flow through), NOT None (dropped)
    assert band_for(None) == "unknown", "null mktcap must band='unknown' (flow through, not drop)"
    assert band_for(0) == "unknown", "zero mktcap must band='unknown'"
    assert band_for(float("nan")) == "unknown", "NaN mktcap must band='unknown'"
    # band_for: thresholds (default $2B deep / $5B watch)
    assert band_for(1.0e9) == "deep", "1B must be 'deep'"
    assert band_for(3.0e9) == "watch", "3B must be 'watch'"
    assert band_for(8.0e9) == "large", "8B must be 'large' (out of scope, flag not drop)"
    # band_for: explicit thresholds honored
    assert band_for(1.0e9, max_mcap=5e8, watch_max=2e9) == "watch", "custom thresholds"

    # Resolve a generated in-band company before applying size exclusion.
    _mc, _src = resolve_mktcap(None, _cap["price"], _cap["cik"],
                              shares_fn=lambda c: _cap["shares"])
    assert _mc == _cap["value"] and _src == "sec_shares_x_price", (
        f"P12: generated missing-cap case must reconstruct, got {_mc},{_src}")
    assert band_for(_mc, 2e9, 5e9) == "deep", (
        "P12: in-band reconstruction must remain in scope")
    _mcb, _ = resolve_mktcap(None, _cap["large_price"], _cap["large_cik"],
                           shares_fn=lambda c: _cap["large_shares"])
    assert band_for(_mcb, 2e9, 5e9) == "large", (
        "P12: an oversize reconstruction is excluded after resolution")

    # Path-isolation math remains offline; generated regressions exercise PRIVATE proof.
    import tempfile
    from unittest.mock import patch
    with tempfile.TemporaryDirectory(prefix='smallcap-state-control-') as temporary:
        root = Path(temporary)
        with patch.dict(os.environ, {'SMALLCAP_RUN': ''}), \
             patch.dict(globals(), {'output_root': lambda: root,
                                    'prove_output_path': lambda value: Path(value).resolve()}):
            first = run_state_path(run="2026-06-20_themeA")
            second = run_state_path(run="2026-06-20_themeB")
            assert first != second and first.parent.parent == root
            assert first.name == second.name == '_run_state.txt'
            p_pid1 = run_state_path(pid=11111)
            p_pid2 = run_state_path(pid=22222)
            assert p_pid1 != p_pid2 and p_pid1.parent == p_pid2.parent == root
            assert p_pid1.name == '_run_state_11111.txt'

    print("_common selftest PASS (P5 resolve_mktcap fallback chain + band_for unknown flow-through "
          "+ P12 resolve-then-band ordering + #10 run-state isolation)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="_common — shared spine. CLI supports --selftest only.")
    ap.add_argument("--selftest", action="store_true", help="Run selftest and exit")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    else:
        ap.error("_common.py is a library module; use --selftest to verify its helpers.")
