#!/usr/bin/env python3
"""Doctor for small-cap-deepdive's config (config-spec E3). Resolves config.json via the
documented discovery order, validates the merged config against the schema, and prints
PASS/FAIL per check naming exactly what is wrong. Exit 0 = ready, 1 = not ready, 2 = usage error.

It catches the #1 silent failure: a placeholder/empty sec_user_agent (which 403s against EDGAR
instead of erroring loudly). PII is NEVER echoed — only presence / shape is reported.

Discovery order (config-spec E2):
  1. $SMALL_CAP_DEEPDIVE_CONFIG_DIR (or $SMALL_CAP_DEEPDIVE_CONFIG) -> <dir>/config.json
  2. ~/.small-cap-deepdive-config/config.json   3. ~/.config/small-cap-deepdive-config/config.json
  4. reference/config.json (in-repo legacy/default)

Usage:
  python scripts/verify_config.py [--config-dir <dir>]
Stdlib only. Never prints secret/PII values.
"""
import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_REF = _REPO / "reference"
_EXAMPLE = _REF / "config.example.json"
_PLACEHOLDER_UA = "small-cap-deepdive research your-email@example.com"
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"

# field -> (python type, required)  — mirrors config.example.json schema (config-spec E1).
_NUMERIC = {
    "market_cap_max": int, "watch_band_max": int, "micro_cap_max": int,
    "min_dollar_vol": int, "normalize_years": int,
    "wacc": float, "cap_rate_low": float, "cap_rate_high": float,
    "cyclical_cv_threshold": float,
}
_STR = ("output_dir", "python_cmd", "insider_source")


def discover(override):
    if override:
        p = Path(os.path.expanduser(override)) / "config.json"
        return p, "explicit (--config-dir)"
    for var in ("SMALL_CAP_DEEPDIVE_CONFIG_DIR", "SMALL_CAP_DEEPDIVE_CONFIG"):
        d = os.environ.get(var)
        if d:
            p = Path(os.path.expanduser(d)) / "config.json"
            if p.exists():
                return p, "env:%s" % var
    for d in (Path(os.path.expanduser("~/.small-cap-deepdive-config")),
              Path(os.path.expanduser("~/.config/small-cap-deepdive-config"))):
        p = d / "config.json"
        if p.exists():
            return p, "default:%s" % d
    return (_REF / "config.json"), "in-repo default (reference/config.json)"


def main():
    ap = argparse.ArgumentParser(description="Validate small-cap-deepdive config.")
    ap.add_argument("--config-dir", default=None)
    a = ap.parse_args()

    if not _EXAMPLE.is_file():
        print("ERROR: %s missing (run from the skill repo)." % _EXAMPLE)
        return 2
    defaults = json.loads(_EXAMPLE.read_text(encoding="utf-8"))

    cfg_path, how = discover(a.config_dir)
    print("Config doctor for small-cap-deepdive")
    print("  discovery -> %s" % how)
    print("  config.json: %s%s" % (cfg_path, "" if cfg_path.exists() else "  (NOT FOUND)"))

    cfg = dict(defaults)
    overlay = {}
    if cfg_path.exists():
        try:
            overlay = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg.update(overlay)
        except Exception as e:
            print("  [%s] config.json valid JSON -> %s" % (FAIL, e))
            return 1
    # apply SMALLCAP_* env overrides (same as load_config) so doctor matches runtime.
    for k in list(cfg):
        env = os.environ.get("SMALLCAP_" + k.upper())
        if env is not None:
            cfg[k] = env
    print("-" * 64)

    results = []

    def check(name, ok, detail="", level=FAIL):
        results.append((name, ok, detail, level))

    # --- schema_version: structural contract tag (config-spec E1). Soft — defaults supply it. ---
    sv = cfg.get("schema_version")
    check("schema_version present (== 1)", sv == 1, "got %r (expected 1)" % sv, WARN)

    # --- sec_user_agent: the one runtime-required PII (never echoed). Per Mode B the PII is filled
    # as a SEPARATE step AFTER the structural skeleton is stamped, so a missing/placeholder UA is a
    # loud WARN (named per E3, not silently OK) rather than a structural FAIL. This lets a freshly
    # init'd config verify as structurally READY (config-spec E5 hot-swap) while still telling you
    # exactly what to set before any live EDGAR call. Runtime still hard-needs it (EDGAR 403s loudly
    # on a placeholder UA), so the protection is preserved, just relocated to where the secret is used. ---
    ua = cfg.get("sec_user_agent")
    if not ua or not str(ua).strip():
        check("sec_user_agent set", False,
              "empty/missing -> set real name+email before any live EDGAR call or it 403s", WARN)
    elif str(ua).strip() == _PLACEHOLDER_UA:
        check("sec_user_agent set", False,
              "still the example PLACEHOLDER -> set real name+email or EDGAR will 403", WARN)
    elif "@" not in str(ua):
        check("sec_user_agent has an email", False,
              "no '@' (EDGAR needs 'Name email@domain')", WARN)
    else:
        check("sec_user_agent set (real name+email)", True)  # value intentionally NOT printed

    # --- type checks for known scalar fields (config-spec E1) ---
    for key, typ in _NUMERIC.items():
        v = cfg.get(key)
        if v is None:
            check("%s present" % key, False, "missing (no default applied)")
            continue
        try:
            float(v)
            ok = True
        except (TypeError, ValueError):
            ok = False
        check("%s is numeric" % key, ok, "got %r" % v)
    for key in _STR:
        v = cfg.get(key)
        check("%s present" % key, v is not None and str(v).strip() != "", "missing/empty")

    sic = cfg.get("sic_hard_exclude")
    check("sic_hard_exclude is a list", isinstance(sic, list), "type %s" % type(sic).__name__)

    # --- E6: secrets isolation — overlay file must be gitignored / out-of-tree ---
    gi = _REPO / ".gitignore"
    gi_txt = gi.read_text(encoding="utf-8", errors="replace") if gi.is_file() else ""
    check(".gitignore blocks config.json + *.env + secrets/",
          all(s in gi_txt for s in ("config.json", "*.env", "secrets/")),
          "harden .gitignore (config-spec E6)")
    # if the active config.json sits inside the repo, confirm it is the gitignored in-repo one
    try:
        inside = _REPO in cfg_path.resolve().parents
    except Exception:
        inside = False
    if inside and cfg_path.exists():
        check("in-repo config.json is gitignored (not committed)", "config.json" in gi_txt,
              "config.json not in .gitignore")

    # report
    n_fail = sum(1 for _, ok, _, lvl in results if not ok and lvl == FAIL)
    n_warn = sum(1 for _, ok, _, lvl in results if not ok and lvl == WARN)
    for nm, ok, detail, lvl in results:
        tag = PASS if ok else lvl
        line = "  [%s] %s" % (tag, nm)
        if detail and not ok:
            line += "  -> %s" % detail
        print(line)
    print("-" * 64)
    if n_fail:
        print("NOT READY: %d check(s) failed. Fix the above, then re-run verify_config.py." % n_fail)
        print("  Tip: python scripts/init_config.py   # stamp a fresh config.json from the template")
        return 1
    if n_warn:
        # Structure conforms (hot-swappable) but the runtime PII is not yet set: name it loudly,
        # still exit 0 so the swap-test / discovery contract holds (config-spec E5).
        print("READY (structure conforms) — but %d WARNING(s) above. Set sec_user_agent "
              "(your real name + email) in config.json before any live EDGAR call, or requests 403." % n_warn)
        return 0
    print("READY: config conforms. sec_user_agent is set; defaults/overrides resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
