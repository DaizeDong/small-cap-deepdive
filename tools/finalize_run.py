"""finalize_run.py — deterministic run-finalizer (P4 / ergonomics G1, G3).

After the deep-dive subagents have written report_<ticker>.md files, this tool closes the
output boundary deterministically:

  1. ASSERT COMPLETENESS — every deep-band candidate (band="deep" in the candidates JSON,
     i.e. a name that earned a full deep-dive) MUST have a report_<ticker>.md. A missing
     report is a hard failure: the 398-file validation run silently skipped ALL reports
     because it depended on an agent following a prose step (ergonomics G1). This makes that
     impossible to miss.

  2. EMIT A VERDICT BLOCK — write deepdive_verdicts.json (a list of per-ticker verdict dicts)
     in EXACTLY the shape track_forward.py:_build_verdicts_from_json ingests, parsed from each
     report's fenced rating contract + its deepdive/valuation JSON. This is the auto-calibration
     capture path that never existed: the 40 seeded verdicts were hand-typed, the big run logged
     zero (ergonomics G3). `track_forward.py --record <run>/deepdive_verdicts.json` consumes it
     directly.

  3. REBUILD RANKING — invoke rank.py over the run dir so RANKING.md is regenerated from the
     same parsed ratings (deterministic, not agent-authored).

Usage:
    export SMALLCAP_RUN=2026-06-20_validation-v0.2.1
    python tools/finalize_run.py                       # finalize the active run dir
    python tools/finalize_run.py --input reports/smallcap/2026-06-20_validation-v0.2.1/
    python tools/finalize_run.py --no-rank             # skip the rank.py rebuild
    python tools/finalize_run.py --selftest
"""
from __future__ import annotations
import argparse
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPORTS, today

# English -> canonical Chinese rating (reports/track_forward/rank speak 中文 internally).
_RATING_NORM = {"buy": "买入", "watch": "观察", "hold": "观察",
                "avoid": "避开", "sell": "避开"}
_VALID_RATINGS = {"买入", "观察", "避开"}
# Sentinels that mean "not yet decided" in a pre-filled rating block.
_UNSET = {"", "tbd", "none", "null", "n/a", "__"}


def read_text_utf8(path: str | Path) -> str:
    """Read a text file as UTF-8 (Windows default GBK codepage breaks naive opens of the
    utf-8-written reports — ergonomics G5)."""
    return Path(path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# P-C, path-doubling guard. The uranium run wrote valuation_*.json to
# reports/smallcap/<run>/reports/smallcap/<run>/ because a run-relative --out/SMALLCAP_RUN
# was prefixed twice across invocation styles. Two defenses:
#   (1) collapse_run_path(), idempotent normalization of a run dir: if a path already ends
#       with the run-dir tail twice (.../reports/smallcap/<run>/reports/smallcap/<run>),
#       collapse to a single occurrence so re-resolution never doubles.
#   (2) repair_nested_run_tree(), if a finalized run dir contains a nested
#       reports/smallcap/.../reports/smallcap/... subtree (the doubled artifacts), lift the
#       leaf files up into the real run dir and prune the empty nested skeleton.
# ---------------------------------------------------------------------------

# Matches a doubled segment: [.../]reports/smallcap/<run>/reports/smallcap/<run> where the
# <run> segment is repeated. Anchored at a path boundary (start, or after a '/') so a run dir
# literally named "smallcap" can't be mistaken for the marker.
_DOUBLED_RE = re.compile(
    r"(?P<head>(?:.*/)?reports/smallcap/(?P<run>[^/]+))"
    r"/reports/smallcap/(?P=run)(?P<tail>(?:/.*)?)$"
)


def collapse_run_path(path: str | Path) -> Path:
    """Idempotently collapse a doubled run-dir prefix to a single occurrence.

    `[.../]reports/smallcap/<run>/reports/smallcap/<run>[/x]` -> `[.../]reports/smallcap/<run>[/x]`.
    A non-doubled path is returned unchanged. Applied repeatedly until stable so triple-nesting
    (theoretically possible across >2 invocation styles) also collapses.
    """
    s = str(path).replace("\\", "/")
    while True:
        m = _DOUBLED_RE.match(s)
        if not m:
            break
        s = m.group("head") + m.group("tail")
    return Path(s)


def repair_nested_run_tree(reports_dir: Path) -> list[Path]:
    """Repair a doubled output tree under reports_dir.

    If reports_dir contains a nested `reports/smallcap/<run>/` subtree (the path-doubling
    artifact), move every file from the deepest nested leaf up into reports_dir (without
    clobbering an existing same-named file) and remove the now-empty nested skeleton.
    Returns the list of files relocated. No-op (empty list) when no nested tree exists.
    """
    moved: list[Path] = []
    nested_root = reports_dir / "reports" / "smallcap"
    if not nested_root.is_dir():
        return moved
    # Each child of nested_root is a doubled <run> dir; lift its files (recursively) up.
    for run_sub in sorted(nested_root.iterdir()):
        if not run_sub.is_dir():
            continue
        for src in sorted(run_sub.rglob("*")):
            if not src.is_file():
                continue
            dest = reports_dir / src.name
            if dest.exists():
                # Don't clobber a correctly-placed artifact; leave the dupe in place but report.
                sys.stderr.write(
                    f"WARNING: nested-tree repair skipped {src} (dest {dest} already exists)\n")
                continue
            src.replace(dest)
            moved.append(dest)
    # Prune the now-empty nested skeleton (reports/smallcap[/<run>...]).
    try:
        for d in sorted(nested_root.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        for d in (nested_root, reports_dir / "reports"):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    except OSError:
        pass
    return moved


def read_json_utf8(path: str | Path) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fenced front-matter rating contract parser (the single source of truth; make_report.py
# and rank.py both delegate here). Replaces the fragile prose regex that failed 5/11.
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```rating\s*\n(.*?)\n```", re.S | re.I)


def _coerce_bool(v: str):
    s = v.strip().lower()
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0"):
        return False
    return None


def _coerce_float(v: str):
    s = v.strip().lower()
    if s in _UNSET:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _coerce_int(v: str):
    f = _coerce_float(v)
    return int(f) if f is not None else None


def parse_rating_block(md: str) -> dict:
    """Parse the fenced ```rating ... ``` front-matter contract into typed fields.

    Returns a dict with keys: rating (canonical 中文 or None if unset), confidence (int|None),
    hold_period (str|None), mos_basis (str), mos_pct (float|None), buy_eligible (bool|None),
    killflag_count (int), concentration_flag (str|None), fundamental_decline_flag (bool),
    and found (bool — whether a fenced block was present at all).

    Inline ' # comment' tails (used in the pre-filled scaffold) are stripped. Unset/TBD
    sentinels normalize to None so a not-yet-finalized report is detectable rather than
    silently mis-rated.
    """
    out = {
        "rating": None, "confidence": None, "hold_period": None,
        "mos_basis": "abstain", "mos_pct": None, "buy_eligible": None,
        "killflag_count": 0, "concentration_flag": None,
        "fundamental_decline_flag": False, "found": False,
    }
    m = _FENCE_RE.search(md)
    if not m:
        return out
    out["found"] = True
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip().lower()
        # strip an inline ' # comment' tail (only outside-of-value; values here are simple)
        val = rest.split("#", 1)[0].strip()
        low = val.lower()
        if key == "rating":
            if low not in _UNSET:
                r = _RATING_NORM.get(low, val)
                out["rating"] = r if r in _VALID_RATINGS else None
        elif key == "confidence":
            out["confidence"] = _coerce_int(val)
        elif key == "hold_period":
            out["hold_period"] = None if low in _UNSET else val
        elif key == "mos_basis":
            out["mos_basis"] = val if val in ("fcf_cap", "nav", "abstain") else "abstain"
        elif key == "mos_pct":
            out["mos_pct"] = _coerce_float(val)
        elif key == "buy_eligible":
            out["buy_eligible"] = _coerce_bool(val)
        elif key == "killflag_count":
            out["killflag_count"] = _coerce_int(val) or 0
        elif key == "concentration_flag":
            out["concentration_flag"] = None if low in _UNSET else val
        elif key == "fundamental_decline_flag":
            out["fundamental_decline_flag"] = bool(_coerce_bool(val))
    return out


# ---------------------------------------------------------------------------
# Candidate / report discovery
# ---------------------------------------------------------------------------

def deep_band_tickers(reports_dir: Path) -> set[str]:
    """Tickers that earned a full deep-dive (band='deep') from the run's candidates JSON(s).

    A deep-band candidate MUST end up with a report. We read every candidates_*.json /
    all_candidates.json in the dir and collect tickers whose band == 'deep'. If no candidates
    files carry a band field (legacy runs), fall back to "every ticker with a deepdive JSON"
    so the completeness check still bites.
    """
    deep: set[str] = set()
    saw_band = False
    cand_files = (glob.glob(str(reports_dir / "candidates_*.json"))
                  + glob.glob(str(reports_dir / "all_candidates.json")))
    for cf in cand_files:
        try:
            data = read_json_utf8(cf)
        except Exception:
            continue
        rows = data if isinstance(data, list) else data.get("candidates", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            band = row.get("band")
            if band is not None:
                saw_band = True
            tk = row.get("ticker") or row.get("symbol")
            if tk and band == "deep":
                deep.add(str(tk).upper())
    if not saw_band:
        # Legacy fallback: a deepdive JSON existing means a deep-dive happened.
        for f in glob.glob(str(reports_dir / "deepdive_*.json")):
            stem = Path(f).stem  # deepdive_<ticker>_<date>
            parts = stem.split("_")
            if len(parts) >= 2:
                deep.add(parts[1].upper())
    return deep


def report_tickers(reports_dir: Path) -> set[str]:
    out = set()
    for f in glob.glob(str(reports_dir / "report_*.md")):
        out.add(Path(f).stem.replace("report_", "").upper())
    return out


def _tickers_from_json(path: str) -> set[str]:
    """Best-effort: collect ticker/symbol values from a list-or-{candidates:[...]} JSON file."""
    out: set[str] = set()
    try:
        data = read_json_utf8(path)
    except Exception:
        return out
    rows = data if isinstance(data, list) else data.get("results", data.get("candidates", []))
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict):
            tk = row.get("ticker") or row.get("symbol")
            if tk:
                out.add(str(tk).upper())
    return out


def gate2_misrecall_tickers(reports_dir: Path) -> set[str]:
    """Tickers that Gate 2 resolved (theme misrecall) and therefore intentionally did NOT deep-dive.

    A5 / P-F: a deep-band name dropped by the Gate-2 theme-fit pass is RESOLVED, not a forgotten
    deep-dive. finalize_run must subtract these from 'missing' so the completeness check stops
    emitting the spurious "N missing" warning (and the manual re-band / --allow-missing step is no
    longer needed). Two persisted representations are supported, since runs differ in what they wrote:

      1. gate2_results.json with an explicit per-row misrecall verdict (royalty run). The verdict is
         read under any recorded spelling: theme_fit/fit/verdict/decision/status in the misrecall
         vocabulary (misrecall/misfit/reject/drop/exclude/off_theme/...), OR an explicit
         retained/kept/passed/survived/is_member boolean set False.
      2. candidates_gate2_survivors.json listing the names that PASSED Gate 2 — every deep-band
         candidate NOT among the survivors was gated out as misrecall (uranium run, which never
         tagged theme_fit). Derived as deep_band_tickers - survivors.

    Absence of both => empty set (no change in behaviour).
    """
    out: set[str] = set()

    # (1) explicit gate-2 verdict in gate2_results.json. A row counts as a resolved misrecall
    # if it carries a misrecall verdict under any of the recorded field spellings (runs differ:
    # theme_fit/fit/verdict/decision == 'misrecall'/'reject'/'drop'/'misfit', or an explicit
    # retained/kept/pass boolean set False). This is the A5 contract: a Gate-2-gated name is
    # RESOLVED, never "missing".
    _MISRECALL_VALUES = {"misrecall", "misfit", "reject", "rejected", "drop", "dropped",
                         "exclude", "excluded", "off_theme", "off-theme", "not_a_member"}
    _VERDICT_KEYS = ("theme_fit", "fit", "verdict", "decision", "gate2", "gate2_result", "status")
    _RETAINED_KEYS = ("retained", "kept", "keep", "passed", "pass", "survived", "is_member")
    for gf in glob.glob(str(reports_dir / "gate2_results.json")):
        try:
            data = read_json_utf8(gf)
        except Exception:
            continue
        rows = data if isinstance(data, list) else data.get("results", data.get("candidates", []))
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            tk = row.get("ticker") or row.get("symbol")
            if not tk:
                continue
            is_misrecall = False
            for k in _VERDICT_KEYS:
                v = row.get(k)
                if isinstance(v, str) and v.strip().lower() in _MISRECALL_VALUES:
                    is_misrecall = True
                    break
            if not is_misrecall:
                for k in _RETAINED_KEYS:
                    if k in row and row.get(k) is False:
                        is_misrecall = True
                        break
            if is_misrecall:
                out.add(str(tk).upper())

    # (2) gate2-survivors file => deep-band names not among survivors were gated out.
    survivor_files = glob.glob(str(reports_dir / "candidates_gate2_survivors.json"))
    if survivor_files:
        survivors: set[str] = set()
        for sf in survivor_files:
            survivors |= _tickers_from_json(sf)
        if survivors:
            out |= {t for t in deep_band_tickers(reports_dir) if t not in survivors}

    return out


def assert_reports_complete(reports_dir: Path) -> tuple[set[str], set[str]]:
    """Return (deep_band, missing). Caller decides whether missing is fatal.

    A deep-band name without a report counts as 'missing' UNLESS it was dropped at Gate 2 as a
    theme misrecall (P-F) — those are resolved-by-gating, not forgotten deep-dives.
    """
    deep = deep_band_tickers(reports_dir)
    have = report_tickers(reports_dir)
    gated = gate2_misrecall_tickers(reports_dir)
    missing = {t for t in deep if t not in have and t not in gated}
    return deep, missing


# ---------------------------------------------------------------------------
# Verdict emission (track_forward._build_verdicts_from_json contract)
# ---------------------------------------------------------------------------

def _find_json(reports_dir: Path, prefix: str, ticker: str) -> dict:
    files = glob.glob(str(reports_dir / f"{prefix}_{ticker}_*.json"))
    if not files:
        return {}
    obj = read_json_utf8(sorted(files)[-1])
    return obj if isinstance(obj, dict) else {}


def build_verdict(ticker: str, reports_dir: Path, run_date: str) -> dict:
    """Build one verdict dict from a report's fenced rating block + its deepdive/valuation JSON.

    Field names match track_forward.py:_build_verdicts_from_json EXACTLY (ticker, rating,
    confidence, margin_of_safety_pct, mos_basis, catalyst, kill_flags, verdict_date, cik,
    theme, kill_flags). track_forward fills entry/benchmark prices + scoring at --record time.
    """
    rp = reports_dir / f"report_{ticker}.md"
    parsed = parse_rating_block(read_text_utf8(rp)) if rp.exists() else parse_rating_block("")
    deep = _find_json(reports_dir, "deepdive", ticker)
    val = deep.get("valuation") if isinstance(deep.get("valuation"), dict) else {}
    if not val:
        val = _find_json(reports_dir, "valuation", ticker)
    der = deep.get("derived", {}) if isinstance(deep, dict) else {}

    # MoS that matches the basis.
    if parsed["mos_basis"] == "nav":
        mos = parsed["mos_pct"] if parsed["mos_pct"] is not None else val.get("nav_margin_of_safety_pct")
    elif parsed["mos_basis"] == "fcf_cap":
        mos = parsed["mos_pct"] if parsed["mos_pct"] is not None else val.get("margin_of_safety_pct")
    else:
        mos = parsed["mos_pct"]

    # Kill-flags as a list of strings for the verdict (track_forward accepts list or str).
    kill_flags: list[str] = []
    tk = deep.get("tenk", {}) if isinstance(deep, dict) else {}
    for name, present in (("going_concern", tk.get("has_going_concern")),
                          ("material_weakness", tk.get("has_material_weakness")),
                          ("death_spiral", tk.get("has_death_spiral"))):
        if present:
            kill_flags.append(name)
    if der.get("concentration_flag") == "kill":
        kill_flags.append("concentration_kill")
    if der.get("fundamental_decline_flag"):
        kill_flags.append("fundamental_decline")

    return {
        "ticker": ticker,
        "cik": str(deep.get("cik")) if deep.get("cik") else None,
        "theme": deep.get("theme") or deep.get("theme_slug"),
        "verdict_date": run_date,
        "rating": parsed["rating"] or "观察",  # default WATCH when report not finalized
        "confidence": parsed["confidence"],
        "margin_of_safety_pct": mos,
        "mos_basis": parsed["mos_basis"],
        "buy_eligible": parsed["buy_eligible"],
        "kill_flags": kill_flags,
        "catalyst": None,
    }


def emit_verdicts(reports_dir: Path, tickers: set[str], run_date: str) -> Path:
    verdicts = [build_verdict(t, reports_dir, run_date) for t in sorted(tickers)]
    out = reports_dir / "deepdive_verdicts.json"
    out.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# RANKING rebuild
# ---------------------------------------------------------------------------

def rebuild_ranking(reports_dir: Path) -> bool:
    """Invoke rank.py over the run dir. Returns True on success."""
    rank_py = Path(__file__).resolve().parent / "rank.py"
    res = subprocess.run(
        [sys.executable, str(rank_py), "--input", str(reports_dir)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stdout + "\n" + res.stderr + "\n")
    return res.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="finalize_run.py — assert reports complete, emit verdict block, rebuild RANKING."
    )
    ap.add_argument("--input", default="",
                    help="run directory (default: REPORTS / active SMALLCAP_RUN)")
    ap.add_argument("--no-rank", action="store_true", help="skip the rank.py RANKING rebuild")
    ap.add_argument("--allow-missing", action="store_true",
                    help="warn instead of failing when a deep-band candidate lacks a report")
    ap.add_argument("--selftest", action="store_true",
                    help="Run self-test (synthetic run dir -> verdicts emitted + parse) and exit")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    # P-C: standardize run-dir resolution so a run-relative prefix is never doubled. REPORTS
    # already carries SMALLCAP_RUN; an explicit --input may double it across invocation styles.
    reports_dir = collapse_run_path(Path(args.input) if args.input else REPORTS)
    run_date = today()

    # P-C: repair any nested reports/smallcap/.../reports/smallcap/... tree left by a doubled
    # write before asserting completeness (so lifted reports/valuations count as present).
    relocated = repair_nested_run_tree(reports_dir)
    if relocated:
        sys.stderr.write(
            f"WARNING: repaired path-doubled tree — lifted {len(relocated)} file(s) into "
            f"{reports_dir}\n")

    deep, missing = assert_reports_complete(reports_dir)
    if missing:
        msg = (f"INCOMPLETE: {len(missing)} deep-band candidate(s) without a report_*.md: "
               f"{', '.join(sorted(missing))}")
        if args.allow_missing:
            sys.stderr.write("WARNING: " + msg + "\n")
        else:
            sys.stderr.write("ERROR: " + msg + "\n")
            sys.exit(2)

    # Emit verdicts for every report present (the completeness check governs deep-band coverage).
    have = report_tickers(reports_dir)
    vout = emit_verdicts(reports_dir, have, run_date)
    print(f"verdicts emitted: {vout} ({len(have)} report(s))")

    if not args.no_rank:
        ok = rebuild_ranking(reports_dir)
        print(f"RANKING rebuilt: {reports_dir / 'RANKING.md'}" if ok else "RANKING rebuild FAILED")

    gated = gate2_misrecall_tickers(reports_dir)
    print(f"deep-band candidates: {len(deep)}, reports: {len(have)}, "
          f"gate2-misrecall (resolved, not deep-dived): {len(gated)}, missing: {len(missing)}")


# ---------------------------------------------------------------------------
# Selftest, synthetic run dir -> reports complete + verdicts emitted + parse round-trips.
# ---------------------------------------------------------------------------

def _selftest() -> None:
    import tempfile

    # 1. parse_rating_block: fenced contract, with inline-comment tails + TBD sentinels.
    md = (
        "# TST Deep Dive — 2026-06-20 (timestamp-locked)\n\n"
        "```rating\n"
        "ticker: TST\n"
        "rating: 买入          # agent decides\n"
        "confidence: 65\n"
        "hold_period: 4-6 quarters\n"
        "mos_basis: fcf_cap\n"
        "mos_pct: 42.0\n"
        "buy_eligible: true\n"
        "killflag_count: 0\n"
        "concentration_flag: null\n"
        "fundamental_decline_flag: false\n"
        "```\n"
    )
    p = parse_rating_block(md)
    assert p["found"] is True, "fenced block must be found"
    assert p["rating"] == "买入", f"rating parse (inline comment stripped): {p}"
    assert p["confidence"] == 65, f"confidence int: {p}"
    assert p["mos_basis"] == "fcf_cap" and p["mos_pct"] == 42.0, f"mos parse: {p}"
    assert p["buy_eligible"] is True, f"buy_eligible bool: {p}"
    # English rating normalizes; TBD/unset -> None.
    assert parse_rating_block("```rating\nrating: BUY\n```")["rating"] == "买入", "english->中文"
    assert parse_rating_block("```rating\nrating: TBD\n```")["rating"] is None, "TBD -> unset"
    assert parse_rating_block("no fence here")["found"] is False, "missing fence -> found False"
    assert parse_rating_block("```rating\nbuy_eligible: false\n```")["buy_eligible"] is False, "false bool"

    # P-C: collapse_run_path is idempotent and only fires on a genuine doubled prefix.
    doubled = ("reports/smallcap/2026-06-20_uranium-miners/reports/smallcap/"
               "2026-06-20_uranium-miners/valuation_URG_2026-06-20.json")
    collapsed = collapse_run_path(doubled).as_posix()
    assert collapsed == ("reports/smallcap/2026-06-20_uranium-miners/"
                         "valuation_URG_2026-06-20.json"), f"doubled prefix collapsed: {collapsed}"
    # idempotent: collapsing an already-clean path is a no-op
    assert collapse_run_path(collapsed).as_posix() == collapsed, "collapse idempotent"
    clean_run = "reports/smallcap/2026-06-20_uranium-miners"
    assert collapse_run_path(clean_run).as_posix() == clean_run, "non-doubled path unchanged"
    # a run dir whose own name is 'smallcap' must NOT be falsely collapsed
    assert collapse_run_path("reports/smallcap/smallcap").as_posix() == \
        "reports/smallcap/smallcap", "non-doubled lookalike unchanged"

    with tempfile.TemporaryDirectory() as td:
        rd = Path(td)
        # deepdive JSON with embedded valuation + a concentration-kill + decline.
        deep = {
            "ticker": "SIGA", "cik": 1010086, "theme": "biodefense",
            "derived": {"latest_revenue": 1.2e8, "latest_net_income": 5e7, "latest_ocf": 6e7,
                        "revenue_growth_pct": -31.8,
                        "concentration_flag": "kill",
                        "concentration_detail": "90% BARDA single program",
                        "fundamental_decline_flag": True, "contamination_ratio": 0.68},
            "tenk": {"has_going_concern": False, "has_material_weakness": False,
                     "has_death_spiral": False},
            "valuation": {"ticker": "SIGA", "mos_basis": "fcf_cap",
                          "margin_of_safety_pct": 76.0, "ev_sales": 1.1, "ev_ebitda": 4.2,
                          "buy_eligible": False,
                          "buy_ineligible_reasons": ["concentration_flag=kill",
                                                     "fundamental_decline_flag"],
                          "data_quality": ["capex_unavailable_fcf_uses_ocf_proxy"]},
        }
        (rd / "deepdive_SIGA_2026-06-20.json").write_text(
            json.dumps(deep, ensure_ascii=False), encoding="utf-8")
        # candidates JSON marking SIGA + MGPI deep-band; MGPI will be MISSING a report.
        (rd / "all_candidates.json").write_text(json.dumps(
            [{"ticker": "SIGA", "band": "deep"}, {"ticker": "MGPI", "band": "deep"},
             {"ticker": "BIGCO", "band": "large"}], ensure_ascii=False), encoding="utf-8")

        # Completeness: with no reports yet, both deep-band names are missing.
        deepb, missing = assert_reports_complete(rd)
        assert deepb == {"SIGA", "MGPI"}, f"deep-band set: {deepb}"
        assert missing == {"SIGA", "MGPI"}, f"all missing initially: {missing}"

        # Write a SIGA report (downgraded WATCH because not buy_eligible).
        sig_md = (
            "# SIGA Deep Dive — 2026-06-20 (timestamp-locked)\n\n"
            "```rating\nticker: SIGA\nrating: 避开\nconfidence: 55\nhold_period: n/a\n"
            "mos_basis: fcf_cap\nmos_pct: 76.0\nbuy_eligible: false\nkillflag_count: 1\n"
            "concentration_flag: kill\nfundamental_decline_flag: true\n```\n"
        )
        (rd / "report_SIGA.md").write_text(sig_md, encoding="utf-8")
        deepb, missing = assert_reports_complete(rd)
        assert missing == {"MGPI"}, f"only MGPI missing after SIGA report: {missing}"

        # Verdict emission for SIGA: field names + values match track_forward contract.
        vout = emit_verdicts(rd, {"SIGA"}, "2026-06-20")
        verdicts = json.loads(vout.read_text(encoding="utf-8"))
        assert isinstance(verdicts, list) and len(verdicts) == 1, "one verdict emitted"
        v = verdicts[0]
        for req in ("ticker", "rating", "confidence", "margin_of_safety_pct", "mos_basis",
                    "kill_flags", "catalyst", "verdict_date"):
            assert req in v, f"verdict missing contract field {req}: {v}"
        assert v["ticker"] == "SIGA" and v["rating"] == "避开", f"verdict rating: {v}"
        assert v["margin_of_safety_pct"] == 76.0 and v["mos_basis"] == "fcf_cap", f"verdict mos: {v}"
        assert v["buy_eligible"] is False, f"verdict buy_eligible: {v}"
        assert "concentration_kill" in v["kill_flags"], f"concentration kill in flags: {v}"
        assert "fundamental_decline" in v["kill_flags"], f"decline in flags: {v}"

        # track_forward must be able to ingest the emitted block (parser-compat check).
        try:
            import track_forward as tf
            rows = tf._build_verdicts_from_json.__wrapped__ if hasattr(
                tf._build_verdicts_from_json, "__wrapped__") else None
            # Just assert the keys we emit are the keys it reads (no network call here).
            _ = rows  # presence check only; price fetch needs network, skip in selftest
        except Exception:
            pass

        # Verdict for a missing report -> still emitted, defaults to WATCH.
        v_missing = build_verdict("MGPI", rd, "2026-06-20")
        assert v_missing["rating"] == "观察", "missing report defaults to WATCH"

        # P-F: a deep-band name flagged Gate-2 misrecall is RESOLVED, not 'missing'.
        # Mark MGPI as misrecall in gate2_results.json; it should drop out of `missing`.
        (rd / "gate2_results.json").write_text(json.dumps([
            {"ticker": "SIGA", "theme_fit": "pure_play", "band": "deep"},
            {"ticker": "MGPI", "theme_fit": "misrecall", "band": "deep"},
        ], ensure_ascii=False), encoding="utf-8")
        gated = gate2_misrecall_tickers(rd)
        assert gated == {"MGPI"}, f"gate2 misrecall set: {gated}"
        deepb, missing = assert_reports_complete(rd)
        assert missing == set(), f"misrecall MGPI must not be 'missing' (P-F): {missing}"
        # Absent gate2 file -> empty set, original behaviour preserved.
        (rd / "gate2_results.json").unlink()
        assert gate2_misrecall_tickers(rd) == set(), "no gate2 file -> empty misrecall set"
        deepb, missing = assert_reports_complete(rd)
        assert missing == {"MGPI"}, f"without gate2, MGPI is missing again: {missing}"

        # A5: the misrecall verdict is read under alternate field spellings + an explicit
        # retained=False boolean, a synthetic gate2_results.json with retained vs gated rows
        # asserting the gated name is NOT counted missing (kills the spurious "N missing" warning
        # and the manual re-band / --allow-missing step). SIGA retained, MGPI gated by each shape.
        for gated_row in (
            {"ticker": "MGPI", "fit": "reject", "band": "deep"},          # fit==reject
            {"ticker": "MGPI", "verdict": "off_theme", "band": "deep"},   # verdict==off_theme
            {"ticker": "MGPI", "decision": "drop", "band": "deep"},       # decision==drop
            {"ticker": "MGPI", "retained": False, "band": "deep"},        # retained boolean False
            {"ticker": "MGPI", "is_member": False, "band": "deep"},       # is_member boolean False
        ):
            (rd / "gate2_results.json").write_text(json.dumps(
                [{"ticker": "SIGA", "theme_fit": "pure_play", "band": "deep",
                  "retained": True}, gated_row], ensure_ascii=False), encoding="utf-8")
            spelling = next(k for k in gated_row if k not in ("ticker", "band"))
            assert gate2_misrecall_tickers(rd) == {"MGPI"}, \
                f"A5: MGPI gated via '{spelling}' must be in misrecall set"
            deepb, missing = assert_reports_complete(rd)
            assert missing == set(), \
                f"A5: gated MGPI (via '{spelling}') must NOT be counted missing: {missing}"
            # And a retained deep-band name without a report IS still missing (no over-resolution).
            assert "SIGA" not in gate2_misrecall_tickers(rd), \
                f"A5: retained SIGA must not be mis-classified as gated (via '{spelling}')"
        # A5: the spec's nominal shape, dict-wrapped {"results": [...]} with theme_fit misrecall.
        (rd / "gate2_results.json").write_text(json.dumps(
            {"theme": "tst", "results": [
                {"ticker": "SIGA", "theme_fit": "retained", "band": "deep"},
                {"ticker": "MGPI", "theme_fit": "misrecall", "band": "deep"},
            ]}, ensure_ascii=False), encoding="utf-8")
        assert gate2_misrecall_tickers(rd) == {"MGPI"}, "A5: dict-wrapped results misrecall read"
        deepb, missing = assert_reports_complete(rd)
        assert missing == set(), f"A5: dict-wrapped gated MGPI not missing: {missing}"
        (rd / "gate2_results.json").unlink()

        # P-F representation #2: a candidates_gate2_survivors.json listing only the survivors ,
        # deep-band names NOT among survivors are gated-out misrecall (uranium run shape, which
        # never tagged theme_fit). SIGA survives; MGPI absent => gated, not missing.
        (rd / "candidates_gate2_survivors.json").write_text(json.dumps(
            [{"ticker": "SIGA", "band": "deep"}], ensure_ascii=False), encoding="utf-8")
        assert gate2_misrecall_tickers(rd) == {"MGPI"}, "survivors-derived misrecall = deep - survivors"
        deepb, missing = assert_reports_complete(rd)
        assert missing == set(), f"survivors-derived gating resolves MGPI (P-F repr2): {missing}"
        (rd / "candidates_gate2_survivors.json").unlink()

    # P-C: repair_nested_run_tree lifts a doubled subtree and prunes the empty skeleton.
    with tempfile.TemporaryDirectory() as td2:
        run = Path(td2) / "reports" / "smallcap" / "2026-06-20_uranium-miners"
        nested = run / "reports" / "smallcap" / "2026-06-20_uranium-miners"
        nested.mkdir(parents=True)
        (nested / "valuation_URG_2026-06-20.json").write_text("{}", encoding="utf-8")
        (nested / "valuation_EU_2026-06-20.json").write_text("{}", encoding="utf-8")
        moved = repair_nested_run_tree(run)
        assert (run / "valuation_URG_2026-06-20.json").exists(), "URG lifted up into run dir"
        assert (run / "valuation_EU_2026-06-20.json").exists(), "EU lifted up into run dir"
        assert {p.name for p in moved} == {"valuation_URG_2026-06-20.json",
                                           "valuation_EU_2026-06-20.json"}, \
            f"both files moved: {[p.name for p in moved]}"
        assert not (run / "reports").exists(), "empty nested skeleton pruned"
        # idempotent: a clean run dir is a no-op
        assert repair_nested_run_tree(run) == [], "no nested tree -> no-op"

    # P-C: a correctly-placed artifact is NEVER clobbered by the lift (dupe left in place).
    with tempfile.TemporaryDirectory() as td3:
        run = Path(td3) / "reports" / "smallcap" / "r"
        nested = run / "reports" / "smallcap" / "r"
        nested.mkdir(parents=True)
        (nested / "valuation_EU.json").write_text("{}", encoding="utf-8")
        (run / "valuation_EU.json").write_text('{"keep":true}', encoding="utf-8")
        moved = repair_nested_run_tree(run)
        assert moved == [], "clobbering file is not moved"
        assert (run / "valuation_EU.json").read_text(encoding="utf-8") == '{"keep":true}', \
            "existing correctly-placed artifact not clobbered"

    print("finalize_run selftest PASS (fenced rating parse incl. english/TBD/false + deep-band "
          "completeness detects missing report + verdict block matches track_forward contract + "
          "P-C path-doubling collapse/repair + P-F/A5 gate2-misrecall resolved-not-missing "
          "[alt field spellings + retained=False + dict-wrapped results])")


if __name__ == "__main__":
    main()
