"""Shared config/IO spine for small-cap-deepdive tools. All hardcoding lives here via config."""
from __future__ import annotations
import json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
import requests

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_REF = _REPO / "reference"

def load_config() -> dict:
    # precedence: config.json (gitignored) > config.example.json defaults; env SMALLCAP_* overrides scalars
    cfg = json.loads((_REF / "config.example.json").read_text(encoding="utf-8"))
    real = _REF / "config.json"
    if real.exists():
        cfg.update(json.loads(real.read_text(encoding="utf-8")))
    for k in list(cfg):
        env = os.environ.get("SMALLCAP_" + k.upper())
        if env is not None:
            cfg[k] = env
    return cfg

CFG = load_config()
UA = {"User-Agent": CFG["sec_user_agent"]}
# Batch runs: SMALLCAP_RUN (e.g. "2026-06-19_aginput") routes all outputs into a
# per-run subdir so each run's candidates/cheappass/deepdive/valuation/reports stay
# together and runs (and skill versions) can be compared. Unset => flat (legacy).
_RUN = os.environ.get("SMALLCAP_RUN", "").strip().strip("/\\")
REPORTS = (Path(CFG["output_dir"]) / _RUN) if _RUN else Path(CFG["output_dir"])
REPORTS.mkdir(parents=True, exist_ok=True)

def init_edgar() -> None:
    from edgar import set_identity
    set_identity(CFG["sec_user_agent"])

def slug(name: str) -> str:
    return re.sub(r"\W+", "_", str(name).lower())[:40].strip("_")

def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def http_get(url: str, params: dict | None = None, timeout: int = 25, retries: int = 4) -> requests.Response:
    last = None
    for attempt in range(retries):
        last = requests.get(url, headers=UA, params=params, timeout=timeout)
        if last.status_code in (429, 500):
            time.sleep(2 ** attempt * 1.5)
            continue
        return last
    return last
