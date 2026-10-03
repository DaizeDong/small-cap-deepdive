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
    export SMALLCAP_RUN=<run-name>
    python tools/finalize_run.py                       # finalize the active run dir
    python tools/finalize_run.py --input "<private-companion>/reports/smallcap/<run-name>"
    python tools/finalize_run.py --no-rank             # skip the rank.py rebuild
    python tools/finalize_run.py --selftest
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from datetime import date

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import REPORTS, today
from _output_paths import prove_output_path
from filter_by_sic import (stage_completion, stage_work, read_stage_receipt,
                           prepare_stage_output, write_stage_receipt, stage_receipt_path)

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
    Directory links and nested repositories are preserved without traversal. The
    caller must prove the canonical output directory PRIVATE before invoking repair.
    Returns the list of files relocated. No-op (empty list) when no nested tree exists.
    """
    moved: list[Path] = []

    def linked(path):
        try:
            status = path.lstat()
        except FileNotFoundError:
            return False
        return (stat.S_ISLNK(status.st_mode) or
                (os.name == "nt" and bool(status.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)))

    def ordinary_directory(path):
        return (not linked(path) and path.is_dir() and not os.path.lexists(path / ".git")
                and not ((path / "HEAD").is_file() and (path / "objects").is_dir()))

    def prune_empty(directory):
        if not any(directory.iterdir()):
            directory.rmdir()

    def lift(directory):
        for src in sorted(directory.iterdir()):
            if linked(src):
                continue
            if src.is_dir():
                if ordinary_directory(src):
                    lift(src)
            elif src.is_file():
                dest = reports_dir / src.name
                if os.path.lexists(dest):
                    sys.stderr.write(
                        f"WARNING: nested-tree repair skipped {src} (dest {dest} already exists)\n")
                    continue
                src.replace(dest)
                moved.append(dest)
        prune_empty(directory)

    # Check each prefix before descending: resolving only the leaf could hide a junction.
    prefix = reports_dir / "reports"
    if not ordinary_directory(prefix):
        return moved
    nested_root = prefix / "smallcap"
    if not ordinary_directory(nested_root):
        return moved
    for run_sub in sorted(nested_root.iterdir()):
        if ordinary_directory(run_sub):
            lift(run_sub)
    prune_empty(nested_root)
    prune_empty(prefix)
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
        "verdict_date": None,
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
        elif key == "verdict_date":
            out["verdict_date"] = None if low in _UNSET else val
    return out


# ---------------------------------------------------------------------------
# Candidate / report discovery
# ---------------------------------------------------------------------------

def _candidate_rows(path: str | Path) -> list[dict]:
    """Read a present candidate artifact without treating invalid evidence as empty."""
    try:
        data = read_json_utf8(path)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read candidate JSON: {Path(path).name}") from exc
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict) and ("candidates" in data or "results" in data):
        rows = data.get("candidates", data.get("results"))
    else:
        raise ValueError(f"Invalid candidate schema: {Path(path).name}")
    if not isinstance(rows, list):
        raise ValueError(f"Invalid candidate rows: {Path(path).name}")
    seen = set()
    for row in rows:
        ticker = (row.get("ticker") or row.get("symbol")) if isinstance(row, dict) else None
        if not isinstance(ticker, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", ticker):
            raise ValueError(f"Candidate row has invalid ticker: {Path(path).name}")
        if ticker.upper() in seen:
            raise ValueError(f"Candidate identity is duplicated: {Path(path).name}")
        seen.add(ticker.upper())
    return rows


def candidate_artifacts(reports_dir: Path) -> list[Path]:
    return sorted({path for path in reports_dir.glob("candidates_*.json")
                   if path.name not in {"candidates_gate2_survivors.json", "candidates_event_admitted.json"}
                   and not path.name.endswith(".stage.json")}
                  | ({reports_dir / "all_candidates.json"}
                     if (reports_dir / "all_candidates.json").exists() else set()))


def deep_band_tickers(reports_dir: Path) -> set[str]:
    """Tickers that earned a full deep-dive (band='deep') from the run's candidates JSON(s).

    A deep-band candidate MUST end up with a report. We read every candidates_*.json /
    all_candidates.json in the dir and collect tickers whose band == 'deep'. If no candidates
    files carry a band field (legacy runs), fall back to "every ticker with a deepdive JSON"
    so the completeness check still bites.
    """
    if (reports_dir / "candidates_event_admitted.json").exists():
        from _event_admission import read_event_admission
        rows, _ = read_event_admission(reports_dir)
        return {row["ticker"].upper() if row["ticker"] else "CIK" + row["cik"]
                for row in rows if row["band"] in {"deep", "unknown"}}
    deep: set[str] = set()
    saw_band = False
    cand_files = candidate_artifacts(reports_dir)
    for cf in cand_files:
        rows = _candidate_rows(cf)
        for row in rows:
            band = row.get("band")
            if band is not None:
                saw_band = True
            tk = row.get("ticker") or row.get("symbol")
            if tk and band == "deep":
                deep.add(str(tk).upper())
    if not saw_band:
        # Legacy fallback: a deepdive JSON existing means a deep-dive happened.
        for f in glob.glob(str(reports_dir / "deepdive_*.json")):
            match = re.fullmatch(r"deepdive_(.+)_\d{4}-\d{2}-\d{2}", Path(f).stem)
            if match:
                deep.add(match.group(1).upper())
    return deep


def report_tickers(reports_dir: Path) -> set[str]:
    out = set()
    for f in glob.glob(str(reports_dir / "report_*.md")):
        out.add(Path(f).stem.replace("report_", "").upper())
    return out


def _tickers_from_json(path: str) -> set[str]:
    """Collect tickers from a validated, possibly empty candidate artifact."""
    return {(row.get("ticker") or row.get("symbol")).upper() for row in _candidate_rows(path)}


def gate2_misrecall_tickers(reports_dir: Path) -> set[str]:
    """Only a bound, explicit successful Gate2 rejection resolves a candidate."""
    path = reports_dir / "gate2_results.json"
    if not path.exists():
        return set()
    from run_theme import read_gate2_results
    rows, _ = read_gate2_results(reports_dir)
    return {row["ticker"].upper() for row in rows
            if row["judgment_status"] == "complete" and row["theme_fit"] == "misrecall"}


def _eligible_report_files(reports_dir: Path) -> list[Path]:
    """Validate ranking's selected paths before any verdict can be emitted."""
    from rank import ranking_report_files
    paths = ranking_report_files(reports_dir)
    tickers = [path.stem.removeprefix("report_").upper() for path in paths]
    if any(not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,31}", ticker) for ticker in tickers):
        raise ValueError("Selected report identity is invalid")
    if len(set(tickers)) != len(tickers):
        raise ValueError("Selected report identity is duplicated")
    return paths


def eligible_report_tickers(reports_dir: Path) -> set[str]:
    """Use ranking's single source of truth for eligible report identities."""
    return {path.stem.removeprefix("report_").upper() for path in _eligible_report_files(reports_dir)}


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

def _issuer_json_files(reports_dir: Path, prefix: str, ticker: str) -> list[Path]:
    """Resolve a case-preserved issuer spelling without merging colliding artifacts."""
    pattern = re.compile(rf"{re.escape(prefix)}_{re.escape(ticker)}_(?:\d{{4}}-\d{{2}}-\d{{2}}|ERROR)\.json",
                         re.IGNORECASE)
    files = sorted((path for path in reports_dir.glob(f"{prefix}_*.json")
                    if pattern.fullmatch(path.name)), key=lambda path: path.name.casefold())
    if len({path.name.casefold() for path in files}) != len(files):
        raise ValueError("Issuer artifact identity is duplicated")
    return files


def _report_file(reports_dir: Path, ticker: str) -> Path:
    name = f"report_{ticker}.md".casefold()
    files = [path for path in reports_dir.glob("report_*.md") if path.name.casefold() == name]
    if len(files) != 1:
        raise ValueError("Report rating is unavailable: identity is missing or duplicated")
    return files[0]


def _find_json(reports_dir: Path, prefix: str, ticker: str, *, binding=None) -> dict:
    files = _issuer_json_files(reports_dir, prefix, ticker)
    if not files:
        return {}
    raw = files[-1].read_bytes()
    obj = json.loads(raw.decode("utf-8-sig"))
    if binding is not None:
        binding.update(artifact=files[-1].name, bytes=len(raw),
                       sha256=hashlib.sha256(raw).hexdigest())
    return obj if isinstance(obj, dict) else {}


def _decision_date(md: str, parsed: dict, explicit: str | None) -> tuple[str, str]:
    """Keep a persisted decision date; an explicit date may initialize an undated legacy report."""
    values = []
    if parsed.get("verdict_date"):
        values.append((parsed["verdict_date"], "rating.verdict_date"))
    heading = re.search(r"^# .+ Deep Dive [—-] (\d{4}-\d{2}-\d{2}) \(timestamp-locked\)\s*$", md, re.M)
    if heading:
        values.append((heading.group(1), "timestamp-locked report heading"))
    if explicit:
        values.append((explicit, "explicit verdict date"))
    if not values:
        raise ValueError("Decision has no persisted verdict_date; date the report or pass --verdict-date")
    for value, _ in values:
        try:
            valid = date.fromisoformat(value).isoformat() == value
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError("Decision verdict_date must be YYYY-MM-DD")
    if len({value for value, _ in values}) != 1:
        raise ValueError("Conflicting decision dates; explicitly revise the dated report before finalizing")
    return values[0]


def _verdict_mos_pct(parsed: dict, valuation: dict) -> float | None:
    """Persist report percentages; valuation fallback fields carry decimal ratios."""
    from math import isfinite

    value = parsed["mos_pct"]
    multiplier = 1
    if value is None:
        field = {"nav": "nav_margin_of_safety_pct",
                 "fcf_cap": "margin_of_safety_pct"}.get(parsed["mos_basis"])
        value = valuation.get(field) if field else None
        multiplier = 100
    if type(value) not in (int, float) or not isfinite(value):
        return None
    result = value * multiplier
    return result if isfinite(result) else None


def build_verdict(ticker: str, reports_dir: Path, run_date: str | None) -> dict:
    """Build one verdict dict from a report's fenced rating block + its deepdive/valuation JSON.

    Field names match track_forward.py:_build_verdicts_from_json EXACTLY (ticker, rating,
    confidence, margin_of_safety_pct, mos_basis, catalyst, kill_flags, verdict_date, cik,
    theme, kill_flags). track_forward fills entry/benchmark prices + scoring at --record time.
    Report confidence keeps its integer value with an explicit percent unit for the tracker.
    """
    rp = _report_file(reports_dir, ticker)
    report_raw = rp.read_bytes()
    md = report_raw.decode("utf-8")
    parsed = parse_rating_block(md)
    if not parsed["found"] or parsed["rating"] is None:
        raise ValueError(f"Unfinished or invalid decision rating for {ticker}")
    confidence = parsed["confidence"]
    if not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValueError(f"Unfinished or invalid decision confidence for {ticker}")
    if parsed["rating"] == "买入" and parsed["buy_eligible"] is not True:
        raise ValueError(f"BUY requires explicit buy eligibility for {ticker}")
    verdict_date, date_source = _decision_date(md, parsed, run_date)
    deep_binding = {}
    deep = _find_json(reports_dir, "deepdive", ticker, binding=deep_binding)
    from _signal_snapshot import snapshot_from_deep
    signals_snapshot = snapshot_from_deep(deep, ticker, verdict_date, deep_binding)
    val = deep.get("valuation") if isinstance(deep.get("valuation"), dict) else {}
    if not val:
        val = _find_json(reports_dir, "valuation", ticker)
    if parsed["rating"] == "买入" and val.get("buy_eligible") is False:
        raise ValueError(f"BUY contradicts valuation eligibility for {ticker}")
    der = deep.get("derived", {}) if isinstance(deep, dict) else {}

    mos = _verdict_mos_pct(parsed, val)

    # Kill-flags as a list of strings for the verdict (track_forward accepts list or str).
    kill_flags: list[str] = []
    tk = deep.get("tenk", {}) if isinstance(deep, dict) else {}
    for name, present in (("going_concern", tk.get("has_going_concern")),
                          ("material_weakness", tk.get("has_material_weakness")),
                          ("death_spiral", tk.get("has_death_spiral"))):
        if present:
            kill_flags.append(name)
    if der.get("concentration_flag") == "kill" or parsed["concentration_flag"] == "kill":
        kill_flags.append("concentration_kill")
    if der.get("fundamental_decline_flag") or parsed["fundamental_decline_flag"]:
        kill_flags.append("fundamental_decline")
    report_count = parsed["killflag_count"]
    structured_count = deep.get("killflag_count", 0)
    if (type(report_count) is not int or report_count < 0
            or type(structured_count) is not int or structured_count < 0):
        raise ValueError(f"Invalid decision risk count for {ticker}")
    risk_count = max(report_count, structured_count, len(kill_flags))

    return {
        "ticker": ticker,
        "cik": str(deep.get("cik")) if deep.get("cik") else None,
        "theme": deep.get("theme") or deep.get("theme_slug"),
        "verdict_date": verdict_date,
        "verdict_date_source": date_source,
        "report_sha256": hashlib.sha256(report_raw).hexdigest(),
        "rating": parsed["rating"],
        "confidence": parsed["confidence"],
        "confidence_unit": "percent",
        "margin_of_safety_pct": mos,
        "mos_basis": parsed["mos_basis"],
        "buy_eligible": parsed["buy_eligible"],
        "kill_flags": kill_flags,
        "killflag_count": risk_count,
        "unresolved_killflag_count": risk_count - len(kill_flags),
        "risk_evidence": {"report_count": report_count, "structured_count": structured_count},
        "signals_snapshot": signals_snapshot,
        "catalyst": None,
    }


def emit_verdicts(reports_dir: Path, tickers: set[str], run_date: str | None,
                  completion: dict | None = None) -> Path:
    verdicts = [build_verdict(t, reports_dir, run_date) for t in sorted(tickers)]
    out = prepare_stage_output(reports_dir / "deepdive_verdicts.json")
    out.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    upstream = completion or stage_completion("finalization_inputs", len(verdicts),
                                               reasons=["missing_finalization_evidence"])
    write_stage_receipt(out, stage_completion("verdicts", len(verdicts), upstream=[upstream]))
    return out


# ---------------------------------------------------------------------------
# RANKING rebuild
# ---------------------------------------------------------------------------

def _event_finalization_inputs(reports_dir, deep, missing):
    """Keep event source, screening and report completeness bound to one cohort."""
    from _event_admission import read_event_admission, artifact_binding
    rows, admission = read_event_admission(reports_dir)
    gate2 = reports_dir / "gate2_results.json"
    if gate2.exists() or stage_receipt_path(gate2).exists():
        raise ValueError("A run cannot mix event admission and Gate2 results")
    work, reasons = [], []
    source_name = admission["input"]["artifact"]
    for path in candidate_artifacts(reports_dir):
        if path.name != source_name and _candidate_rows(path):
            reasons.append("candidates_without_bound_event")
    expected = {row["ticker"].upper() if row["ticker"] else "CIK" + row["cik"]:
                {key: row[key] for key in ("input_index", "ticker", "cik", "band")}
                for row in rows if row["band"] in {"deep", "unknown"}}
    binding = {key: admission[key] for key in
               ("artifact", "artifact_bytes", "artifact_sha256", "run_dir")}
    upstream = [admission]
    for ticker in sorted(deep):
        paths = _issuer_json_files(reports_dir, "deepdive", ticker)
        if not paths:
            work.append(stage_work("deepdive_data", ticker, status="unavailable",
                                   reason="missing_deepdive_artifact"))
        else:
            receipt = read_stage_receipt(paths[-1], 1)
            upstream.append(receipt)
            if receipt.get("input_identity") != expected.get(ticker):
                reasons.append("missing_deepdive_input_identity")
            if receipt.get("input") != binding:
                reasons.append("unbound_deepdive_input")
        work.append(stage_work("report", ticker,
                               status="unavailable" if ticker in missing else "complete",
                               reason="missing_report" if ticker in missing else ""))
    if artifact_binding(reports_dir / "candidates_event_admitted.json") != binding:
        raise ValueError("Event admission changed during finalization")
    return stage_completion("finalization_inputs", len(eligible_report_tickers(reports_dir)),
                            work=work, upstream=upstream, reasons=sorted(set(reasons)))


def finalization_inputs(reports_dir: Path, deep: set[str], missing: set[str]) -> dict:
    """Collect observed upstream coverage; unknown work cannot become a complete run."""
    event_path = reports_dir / "candidates_event_admitted.json"
    if event_path.exists() or stage_receipt_path(event_path).exists():
        return _event_finalization_inputs(reports_dir, deep, missing)
    work, upstream, reasons = [], [], []
    files = candidate_artifacts(reports_dir)
    have = eligible_report_tickers(reports_dir)
    if not files:
        reasons.append("missing_candidate_artifact")
    candidate_count = 0
    candidate_identities = set()
    for path in files:
        rows = _candidate_rows(path)
        for row in rows:
            ticker = (row.get("ticker") or row.get("symbol")).upper()
            if ticker in candidate_identities:
                raise ValueError("Candidate identity is duplicated across artifacts")
            candidate_identities.add(ticker)
        candidate_count += len(rows)
        upstream.append(read_stage_receipt(path, len(rows)))
        if any(row.get("band") not in {"deep", "watch"} for row in rows):
            reasons.append("unresolved_candidate_band")
    gated, expected_deep = set(), {}
    survivor_binding = None
    if (reports_dir / "gate2_results.json").exists():
        from run_theme import read_gate2_results, _artifact_binding
        rows, receipt = read_gate2_results(reports_dir)
        upstream.append(receipt)
        gated = {row["ticker"].upper() for row in rows
                 if row["judgment_status"] == "complete" and row["theme_fit"] == "misrecall"}
        survivors = [row for row in rows if row["judgment_status"] == "complete"
                     and row["theme_fit"] in {"pure_play", "partial"}]
        expected_deep = {row["ticker"].upper(): {key: row[key] for key in ("input_index", "ticker", "cik", "band")}
                         for row in survivors if row["band"] == "deep"}
        survivor_path = reports_dir / "candidates_gate2_survivors.json"
        if survivor_path.exists():
            if _candidate_rows(survivor_path) != survivors:
                raise ValueError("Gate2 survivors disagree with explicit bound outcomes")
            survivor_receipt = read_stage_receipt(survivor_path, len(survivors))
            upstream.append(survivor_receipt)
            if survivor_receipt.get("input") != receipt["input"]:
                raise ValueError("Gate2 survivors are not bound to the same candidates")
            survivor_binding = _artifact_binding(survivor_path)
        elif survivors:
            reasons.append("missing_gate2_survivors")
        bound_name = receipt["input"]["artifact"]
        if candidate_count and any(path.name != bound_name and _candidate_rows(path) for path in files):
            reasons.append("candidates_without_bound_gate2")
    elif candidate_count:
        reasons.append("missing_gate2_results")
    if files and not (reports_dir / "gate2_results.json").exists() and have - deep:
        reasons.append("reports_outside_deep_candidates")
    for ticker in sorted(deep - gated):
        data_paths = _issuer_json_files(reports_dir, "deepdive", ticker)
        if not data_paths:
            work.append(stage_work("deepdive_data", ticker, status="unavailable",
                                   reason="missing_deepdive_artifact"))
        else:
            receipt = read_stage_receipt(data_paths[-1], 1)
            upstream.append(receipt)
            identity = receipt.get("input_identity")
            if identity != expected_deep.get(ticker) or identity is None:
                reasons.append("missing_deepdive_input_identity")
            if survivor_binding is None or receipt.get("input") != survivor_binding:
                reasons.append("unbound_deepdive_input")
        work.append(stage_work("report", ticker,
                               status="unavailable" if ticker in missing else "complete",
                               reason="missing_report" if ticker in missing else ""))
    return stage_completion("finalization_inputs", len(have),
                            work=work, upstream=upstream, reasons=sorted(set(reasons)))


def _write_finalization(reports_dir: Path, completion: dict, *, deep, missing, ranking=None) -> Path:
    out = prepare_stage_output(reports_dir / "finalization.json")
    record = {**completion, "deep_tickers": sorted(deep), "missing_reports": sorted(missing),
              "ranking_artifact": ranking.name if ranking else None}
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    write_stage_receipt(out, completion)
    return out


def _ranking_output(reports_dir: Path) -> Path:
    """Use a fresh ranking path; all earlier artifact/receipt pairs remain immutable."""
    for index in range(10000):
        name = "RANKING.md" if index == 0 else f"RANKING.finalized-{index}.md"
        path = reports_dir / name
        if not path.exists() and not stage_receipt_path(path).exists():
            return prove_output_path(path)
    raise FileExistsError("No fresh ranking output name remains")


def rebuild_ranking(reports_dir: Path, output: Path | None = None) -> bool:
    """Invoke rank.py over the run dir. Returns True on success."""
    rank_py = Path(__file__).resolve().parent / "rank.py"
    output = output or _ranking_output(reports_dir)
    if output.parent.resolve() != reports_dir.resolve() or output.exists() or stage_receipt_path(output).exists():
        raise FileExistsError("Ranking output must be a fresh artifact in the current run")
    res = subprocess.run(
        [sys.executable, str(rank_py), "--input", str(reports_dir), "--output", output.name],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stdout + "\n" + res.stderr + "\n")
    return res.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="finalize_run.py — assert reports complete, emit verdict block, rebuild RANKING."
    )
    ap.add_argument("--input", default="",
                    help="run directory (default: REPORTS / active SMALLCAP_RUN)")
    ap.add_argument("--no-rank", action="store_true", help="skip the rank.py RANKING rebuild")
    ap.add_argument("--verdict-date", help="YYYY-MM-DD for a legacy report without a persisted decision date")
    ap.add_argument("--allow-missing", action="store_true",
                    help="emit partial artifacts for missing reports; incomplete runs still exit 2")
    ap.add_argument("--selftest", action="store_true",
                    help="Run self-test (synthetic run dir -> verdicts emitted + parse) and exit")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return 0

    # P-C: standardize run-dir resolution so a run-relative prefix is never doubled. REPORTS
    # already carries SMALLCAP_RUN; an explicit --input may double it across invocation styles.
    reports_dir = prove_output_path(collapse_run_path(Path(args.input) if args.input else REPORTS))
    # Verify the final file too, before repair can mutate any existing artifacts.
    prove_output_path(reports_dir / "deepdive_verdicts.json")
    prepare_stage_output(reports_dir / "finalization.json")
    if stage_receipt_path(reports_dir / "deepdive_verdicts.json").exists():
        raise FileExistsError("Verdicts are already sealed; use a new run output")
    run_date = args.verdict_date

    # P-C: repair any nested reports/smallcap/.../reports/smallcap/... tree left by a doubled
    # write before asserting completeness (so lifted reports/valuations count as present).
    relocated = repair_nested_run_tree(reports_dir)
    if relocated:
        sys.stderr.write(
            f"WARNING: repaired path-doubled tree — lifted {len(relocated)} file(s) into "
            f"{reports_dir}\n")

    try:
        deep, missing = assert_reports_complete(reports_dir)
        report_files = _eligible_report_files(reports_dir)
        have = {path.stem.removeprefix("report_").upper() for path in report_files}
        input_completion = finalization_inputs(reports_dir, deep, missing)
    except (OSError, ValueError, TypeError):
        invalid = stage_completion("finalization", 0, work=[stage_work(
            "finalization_inputs", status="invalid", reason="invalid_or_unreadable_input")])
        _write_finalization(reports_dir, invalid, deep=set(), missing=set())
        sys.stderr.write("ERROR: finalization input evidence is invalid or unreadable\n")
        return 2
    if missing:
        msg = (f"INCOMPLETE: {len(missing)} deep-band candidate(s) without a report_*.md: "
               f"{', '.join(sorted(missing))}")
        if args.allow_missing:
            sys.stderr.write("WARNING: " + msg + "\n")
        else:
            sys.stderr.write("ERROR: " + msg + "\n")
            completion = stage_completion("finalization", input_completion["row_count"],
                                          upstream=[input_completion])
            _write_finalization(reports_dir, completion, deep=deep, missing=missing)
            return 2

    # Preserve old reports on disk and use the same bound deep-input scope as ranking.
    prove_output_path(reports_dir / "deepdive_verdicts.json")
    vout = emit_verdicts(reports_dir, have, run_date, input_completion)
    print(f"verdicts emitted: {vout} ({len(have)} report(s))")

    ranking_ok = True
    ranking_path = None
    upstream = [read_stage_receipt(vout, len(have))]
    if not args.no_rank:
        ranking_path = _ranking_output(reports_dir)
        ranking_ok = rebuild_ranking(reports_dir, ranking_path)
        upstream.append(read_stage_receipt(ranking_path, len(report_files)))
        print(f"RANKING output: {ranking_path}; complete: {ranking_ok}")

    gated = gate2_misrecall_tickers(reports_dir)
    print(f"deep-band candidates: {len(deep)}, reports: {len(have)}, "
          f"gate2-misrecall (resolved, not deep-dived): {len(gated)}, missing: {len(missing)}")
    completion = stage_completion("finalization", len(have), upstream=upstream,
                                  reasons=[] if ranking_ok else ["ranking_incomplete"])
    _write_finalization(reports_dir, completion, deep=deep, missing=missing, ranking=ranking_path)
    print(f"Finalization status: {completion['status']}")
    return 0 if completion["status"] == "complete" else 2


# ---------------------------------------------------------------------------
# Selftest, synthetic run dir -> reports complete + verdicts emitted + parse round-trips.
# ---------------------------------------------------------------------------

def _selftest() -> None:
    """Exercise generated synthetic artifacts with isolated private-repository metadata."""
    import copy
    import tempfile
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import patch
    import _output_paths
    from make_fixtures import downstream_completion_scenarios
    from run_theme import prepare_gate2_request, persist_gate2_result

    sample = downstream_completion_scenarios()
    fixture = sample["selftest"]
    first, second = [row["ticker"] for row in sample["candidates"]]
    asof = sample["asof"]
    candidates = copy.deepcopy(sample["candidates"])
    for row in candidates:
        row["band"] = "deep"

    @contextmanager
    def synthetic_run():
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / ".git").mkdir()
            run = root / "reports" / "smallcap" / fixture["run_name"]
            run.mkdir(parents=True)

            proof = SimpleNamespace(root=str(root), repositories=(fixture["private_identity"],),
                                    signature=fixture["private_origin"])
            boundary = SimpleNamespace(prove_private_companion=lambda destination: proof,
                                       GitError=RuntimeError)
            # Native Git tests cover the shared proof; this seam isolates downstream contracts.
            # Destination, ancestor, file and repeated-proof checks still run.
            with patch.object(_output_paths, "_guard_module", lambda: boundary):
                prove_output_path(run)
                yield run

    def json_artifact(path, value):
        out = prepare_stage_output(path)
        out.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        count = len(value) if isinstance(value, list) else 1
        completion = stage_completion("synthetic_fixture", count,
                                      work=[stage_work("generated_fixture")])
        write_stage_receipt(out, completion)
        return out

    p = parse_rating_block(fixture["parse_report"])
    assert p["found"] is True, "fenced block must be found"
    assert p["rating"] == "买入", f"rating normalization: {p}"
    assert p["confidence"] == 65, f"confidence int: {p}"
    assert p["mos_basis"] == "fcf_cap" and p["mos_pct"] == 42.0, f"mos parse: {p}"
    assert p["buy_eligible"] is True, f"buy_eligible bool: {p}"
    cases = fixture["parse_cases"]
    assert parse_rating_block(cases["english"])["rating"] == "买入", "english->中文"
    assert parse_rating_block(cases["unset"])["rating"] is None, "TBD -> unset"
    assert parse_rating_block(cases["missing"])["found"] is False, "missing fence -> found False"
    assert parse_rating_block(cases["false"])["buy_eligible"] is False, "false bool"

    clean = f"reports/smallcap/{fixture['run_name']}"
    valuation_name = f"valuation_{first}_{asof}.json"
    collapsed = collapse_run_path(f"{clean}/{clean}/{valuation_name}").as_posix()
    assert collapsed == f"{clean}/{valuation_name}", "doubled prefix collapsed"
    assert collapse_run_path(collapsed).as_posix() == collapsed, "collapse idempotent"
    assert collapse_run_path(clean).as_posix() == clean, "non-doubled path unchanged"
    assert collapse_run_path("reports/smallcap/smallcap").as_posix() == "reports/smallcap/smallcap", \
        "non-doubled lookalike unchanged"

    with synthetic_run() as run:
        source = json_artifact(run / "all_candidates.json", candidates)
        json_artifact(run / f"deepdive_{first}_{asof}.json", fixture["risk_deep"])
        deep, missing = assert_reports_complete(run)
        assert deep == {first, second}, f"deep-band set: {deep}"
        assert missing == {first, second}, f"all missing initially: {missing}"
        report = prove_output_path(run / f"report_{first}.md")
        report.write_text(fixture["risk_report"], encoding="utf-8")
        deep, missing = assert_reports_complete(run)
        assert missing == {second}, "only the unreported candidate remains missing"

        vout = emit_verdicts(run, {first}, asof, finalization_inputs(run, deep, missing))
        verdicts = json.loads(vout.read_text(encoding="utf-8"))
        assert isinstance(verdicts, list) and len(verdicts) == 1, "one verdict emitted"
        verdict = verdicts[0]
        for key in ("ticker", "rating", "confidence", "margin_of_safety_pct", "mos_basis",
                    "kill_flags", "catalyst", "verdict_date"):
            assert key in verdict, f"verdict missing contract field {key}"
        assert verdict["ticker"] == first and verdict["rating"] == "避开", "verdict rating"
        assert verdict["margin_of_safety_pct"] == 76.0 and verdict["mos_basis"] == "fcf_cap", "verdict mos"
        assert verdict["buy_eligible"] is False, "verdict buy_eligible"
        assert "concentration_kill" in verdict["kill_flags"], "concentration kill in flags"
        assert "fundamental_decline" in verdict["kill_flags"], "decline in flags"
        assert read_stage_receipt(vout, 1)["status"] == "partial", "usable verdicts do not prove complete coverage"
        try:
            build_verdict(second, run, asof)
        except ValueError as exc:
            assert "rating" in str(exc), str(exc)
        else:
            raise AssertionError("Missing report was finalized")

        request_path = prepare_gate2_request(source)
        request = read_json_utf8(request_path)
        judgments = copy.deepcopy(sample["judgments"])
        for row in judgments:
            row["band"] = "deep"
        response = json_artifact(run / "workflow_result.json",
            {"schema": "smallcap.gate2.result.v1", "input": request["input"], "all": judgments})
        persist_gate2_result(request_path, response)
        assert gate2_misrecall_tickers(run) == {second}, "explicit bound misrecall"
        assert assert_reports_complete(run)[1] == set(), "explicit misrecall resolves report absence"
        assert first not in gate2_misrecall_tickers(run), "retained identity cannot become rejected"

    # Legacy unbound aliases and wrappers cannot establish a resolved identity.
    for alias, value in (("fit", "reject"), ("verdict", "off_theme"), ("decision", "drop"),
                         ("retained", False), ("is_member", False), ("theme_fit", "misrecall")):
        with synthetic_run() as run:
            json_artifact(run / "all_candidates.json", candidates)
            legacy = [{**candidates[1], alias: value}]
            if alias == "theme_fit":
                legacy = {"results": legacy}
            json_artifact(run / "gate2_results.json", legacy)
            try:
                gate2_misrecall_tickers(run)
            except ValueError:
                pass
            else:
                raise AssertionError("Unbound legacy Gate2 shape was accepted")

    with synthetic_run() as run:
        json_artifact(run / "all_candidates.json", candidates)
        assert gate2_misrecall_tickers(run) == set(), "no Gate2 file gives no resolved rejections"
        json_artifact(run / "candidates_gate2_survivors.json", candidates[:1])
        assert gate2_misrecall_tickers(run) == set(), "survivor absence does not prove rejection"
        assert assert_reports_complete(run)[1] == {first, second}, "both unreported identities remain missing"

    with synthetic_run() as run:
        nested = run / "reports" / "smallcap" / fixture["run_name"]
        nested.mkdir(parents=True)
        names = {f"valuation_{ticker}_{asof}.json" for ticker in (first, second)}
        for name in names:
            prove_output_path(nested / name).write_text(json.dumps({}), encoding="utf-8")
        moved = repair_nested_run_tree(run)
        assert all((run / name).exists() for name in names), "both files lifted into run"
        assert {path.name for path in moved} == names, "exact files moved"
        assert not (run / "reports").exists(), "empty nested skeleton pruned"
        assert repair_nested_run_tree(run) == [], "clean run is a no-op"

    with synthetic_run() as run:
        nested = run / "reports" / "smallcap" / fixture["run_name"]
        nested.mkdir(parents=True)
        prove_output_path(nested / valuation_name).write_text(json.dumps({}), encoding="utf-8")
        preserved = json.dumps(fixture["keep_payload"])
        prove_output_path(run / valuation_name).write_text(preserved, encoding="utf-8")
        assert repair_nested_run_tree(run) == [], "clobbering file is not moved"
        assert (run / valuation_name).read_text(encoding="utf-8") == preserved, "existing artifact preserved"

    print("finalize_run selftest PASS (generated synthetic rating/verdict predicates, "
          "bound explicit Gate2 decisions, partial coverage, immutable receipts and path repair)")


if __name__ == "__main__":
    raise SystemExit(main())
