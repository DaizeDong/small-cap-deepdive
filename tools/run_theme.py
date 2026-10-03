"""
run_theme.py — Single-theme end-to-end driver

Orchestrates: discover → cheap_pass → SIC filter → handoff message.

Stages:
  1. discover.py  — SEC FTS recall + market-cap filter → universe_<slug>_<date>.csv
  2. cheap_pass.py — mechanical health check → cheappass_<slug>_<date>.csv
  3. (inline) SIC filter: join universe for cik/sic, apply filter_by_sic.sic_ok,
     write REPORTS/candidates_<slug>.json
  4. Print "Next steps" handoff — LLM stages are SKILL.md-orchestrated, not auto-run.

Usage:
    python tools/run_theme.py --theme "railcar,railcar leasing" --slug railcar
    python tools/run_theme.py --theme "refractory,refractory materials" --slug refractory --micro
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, slug as _slug, today

import pandas as pd

from filter_by_sic import (sic_classify, stage_completion, stage_work,
                           stage_receipt_path, prepare_stage_output,
                           read_stage_receipt, write_stage_receipt)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str) -> None:
    """Run a sibling stage; code 2 may carry a partial artifact with its receipt."""
    print(f"\n{'='*72}\n[{label}] {' '.join(cmd[2:])}\n{'='*72}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode not in (0, 2):
        print(f"[ERROR] {label} exited with code {result.returncode} — aborting.", flush=True)
        sys.exit(result.returncode)


def _fresh_output(path: Path) -> Path:
    """A stage invocation cannot reuse a prior run's artifact or receipt."""
    if path.exists() or stage_receipt_path(path).exists():
        raise FileExistsError(f"Existing stage output {path.name}; use a new run directory")
    return path


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def stage_discover(theme_kw: str, out_slug: str, max_mcap: float,
                   watch_band_max: float | None = None) -> Path:
    """Run discover.py; return the universe CSV path.

    Phase 4: passes --forms including 20-F/40-F (discover.py default) and
    --watch-band-max for dual-band tagging.
    """
    py = CFG["python_cmd"]
    uni = _fresh_output(REPORTS / f"universe_{out_slug}_{today()}.csv")
    tools_dir = Path(__file__).resolve().parent
    cmd = [
        py, str(tools_dir / "discover.py"),
        "--theme", theme_kw,
        # forms: discover.py default now includes 20-F,40-F; omit explicit --forms
        # here so the discover.py default (10-K,10-Q,20-F,40-F) is used.
        "--max-mcap", str(max_mcap),
        "--out-slug", out_slug,
    ]
    if watch_band_max is not None:
        cmd += ["--watch-band-max", str(watch_band_max)]
    _run(cmd, "DISCOVER")

    if not uni.is_file() or not stage_receipt_path(uni).is_file():
        print(f"[ERROR] universe CSV not found for slug '{out_slug}'.", flush=True)
        sys.exit(1)
    print(f"[DISCOVER] output: {uni}", flush=True)
    return uni


def stage_cheap_pass(universe_csv: Path, out_slug: str, max_mcap: float | None = None) -> Path:
    """Run cheap_pass.py; return the cheappass CSV path."""
    py = CFG["python_cmd"]
    cp = _fresh_output(REPORTS / f"cheappass_{out_slug}_{today()}.csv")
    tools_dir = Path(__file__).resolve().parent
    cmd = [
        py, str(tools_dir / "cheap_pass.py"),
        "--universe", str(universe_csv),
        "--out-slug", out_slug,
        "--max-mcap", str(CFG["market_cap_max"] if max_mcap is None else max_mcap),
    ]
    _run(cmd, "CHEAP_PASS")

    if not cp.is_file() or not stage_receipt_path(cp).is_file():
        print(f"[ERROR] cheappass CSV not found for slug '{out_slug}'.", flush=True)
        sys.exit(1)
    print(f"[CHEAP_PASS] output: {cp}", flush=True)
    return cp


def stage_sic_filter(cheappass_csv: Path, universe_csv: Path, out_slug: str, theme_kw: str = "") -> Path:
    """Inline: join cheappass with universe for cik/sic, apply SIC filter, write candidates JSON.

    Phase 4 changes:
    - Uses sic_classify() (tri-state) instead of sic_ok() (bool).
      sic_tier="keep" | "review": both pass to LLM gate.
      sic_tier="drop": excluded (currently never returned by sic_classify).
    - Carries sic_tier into each candidate record so theme-fit-gate can surface it.
    - Carries recall_channel from the universe; missing provenance stays unknown.
    - Carries band ("deep" | "watch") from universe CSV into each candidate record.
      Downstream deepdive_data / rank must skip expensive deep-dive for band="watch".

    theme_kw: human-readable theme keyword string (e.g. "railcar,railcar leasing").
    Written into each candidate record as "theme" so that theme-fit-gate.js can
    interpolate it into prompts without getting 'undefined'.
    """
    hard_exclude: list[str] = CFG["sic_hard_exclude"]

    cdf = pd.read_csv(cheappass_csv, dtype={"ticker": str})
    # Include "band" from universe if present
    uni_cols = ["ticker", "cik", "sic", "mktcap"]
    udf_raw = pd.read_csv(universe_csv, dtype={"ticker": str, "cik": str, "sic": str})
    if not {"ticker", "rejected"}.issubset(cdf.columns) or not set(uni_cols).issubset(udf_raw.columns):
        raise ValueError("SIC filter input schema is incomplete")
    flags = cdf["rejected"].map(lambda value: str(value).strip().lower())
    if not flags.isin(["true", "false"]).all():
        raise ValueError("rejected must contain explicit boolean values")
    cdf["rejected"] = flags.eq("true").astype(bool)
    for frame in (cdf, udf_raw):
        if frame["ticker"].isna().any() or frame["ticker"].str.strip().eq("").any() or frame["ticker"].duplicated().any():
            raise ValueError("SIC filter requires unique nonempty ticker identities")
    if not set(cdf["ticker"]).issubset(set(udf_raw["ticker"])):
        raise ValueError("Cheap-pass identity is absent from its universe")
    upstream = [read_stage_receipt(universe_csv, len(udf_raw)),
                read_stage_receipt(cheappass_csv, len(cdf))]
    if any(item["status"] == "invalid" for item in upstream):
        raise ValueError("SIC filter input receipt is invalid")
    cheap_receipt = upstream[1]
    decisions = cheap_receipt.get("decisions", [])
    reasons = []
    if cheap_receipt.get("input_artifact") != str(universe_csv.resolve()):
        reasons.append("unbound_cheap_pass_input")
    by_ticker = {}
    if decisions:
        if len(decisions) != len(udf_raw):
            raise ValueError("Cheap-pass decisions do not cover the input universe")
        for index, row in udf_raw.iterrows():
            decision = decisions[index]
            if (not isinstance(decision, dict) or decision.get("input_index") != index
                    or decision.get("ticker") != row["ticker"]
                    or decision.get("cik") != row["cik"]):
                raise ValueError("Cheap-pass decision identity does not match the universe")
            by_ticker[row["ticker"]] = decision
        for _, row in cdf.iterrows():
            expected = "rejected_existing_policy" if row["rejected"] else "retained"
            if by_ticker[row["ticker"]].get("screening_decision") != expected:
                raise ValueError("Cheap-pass row disagrees with its decision receipt")
    elif len(udf_raw):
        reasons.append("missing_cheap_pass_decisions")
    if "band" in udf_raw.columns:
        uni_cols.append("band")
    if "recall_channel" in udf_raw.columns:
        uni_cols.append("recall_channel")
    udf = udf_raw[uni_cols]

    # Join to obtain cik/sic/band for cheappass rows
    merged = cdf.merge(udf, on="ticker", how="left", suffixes=("", "_u"))

    # Keep only survivors (not rejected by cheap_pass)
    survivors = merged[~merged["rejected"]].copy()

    # Apply SIC tri-state classification (Phase 4: "review" now passes, not dropped)
    survivors["sic_tier"] = survivors["sic"].apply(lambda x: sic_classify(str(x), hard_exclude))
    candidates = survivors[survivors["sic_tier"] != "drop"].copy()

    n_keep = (candidates["sic_tier"] == "keep").sum()
    n_review = (candidates["sic_tier"] == "review").sum()
    print(
        f"\n[SIC_FILTER] cheappass survivors: {len(survivors)} → "
        f"after SIC filter: {len(candidates)} "
        f"(keep={n_keep}, review={n_review} — review goes to LLM gate)",
        flush=True,
    )

    # Build candidate records
    records = []
    for _, r in candidates.iterrows():
        cik_raw = r.get("cik")
        # business_blurb: extracted by cheap_pass.py from Item 1 of the 10-K.
        # Used by theme-fit-gate.js as PRIMARY basis for classification, eliminating
        # redundant WebSearch for each candidate (Fix 3).
        blurb_raw = r.get("business_blurb", "")
        # The universe owns discovery provenance, including a conflicting cheap-pass column.
        recall_raw = (r.get("recall_channel_u", r.get("recall_channel"))
                      if "recall_channel" in udf_raw.columns else None)
        recall_channel = (recall_raw if isinstance(recall_raw, str)
                          and recall_raw in ("fts", "sic_reverse", "sic", "both") else "unknown")
        # band: "deep" | "watch" | None (from universe CSV; None if universe predates Phase 4)
        band_raw = by_ticker.get(r["ticker"], {}).get("band", r.get("band", None))
        if band_raw not in ("deep", "watch"):
            band_raw = "unknown"
            reasons.append("unresolved_candidate_band")
        records.append({
            "ticker": r["ticker"],
            "cik": str(int(cik_raw)) if pd.notna(cik_raw) else None,
            "name": r.get("name", ""),
            "theme_slug": out_slug,
            "theme": theme_kw,           # D4: human-readable theme for theme-fit-gate.js prompt
            "sic": str(r.get("sic", "")).split(".")[0],
            "sic_tier": str(r.get("sic_tier", "keep")),   # Phase 4: "keep" | "review"
            "band": band_raw,
            "recall_channel": recall_channel,
            "mktcap": float(r["mktcap"]) if pd.notna(r.get("mktcap")) else None,
            "health_score": float(r["health_score"]) if pd.notna(r.get("health_score")) else None,
            "killflag_count": int(r["killflag_count"]) if pd.notna(r.get("killflag_count")) else None,
            "avg_dollar_vol": float(r["avg_dollar_vol"]) if pd.notna(r.get("avg_dollar_vol")) else None,
            "business_blurb": str(blurb_raw) if pd.notna(blurb_raw) else "",
        })

    out = prepare_stage_output(REPORTS / f"candidates_{out_slug}.json")
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    completion = stage_completion("sic_filter", len(records),
                                  work=[stage_work("sic_filter", str(row["ticker"])) for _, row in cdf.iterrows()],
                                  upstream=upstream, reasons=sorted(set(reasons)))
    completion["input_artifacts"] = [_artifact_binding(universe_csv), _artifact_binding(cheappass_csv)]
    completion["decisions"] = decisions
    write_stage_receipt(out, completion)
    print(f"[SIC_FILTER] candidates written → {out} ({len(records)} tickers)", flush=True)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _artifact_binding(path: Path) -> dict:
    payload = path.read_bytes()
    return {"artifact": path.name, "artifact_bytes": len(payload),
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "run_dir": str(path.resolve().parent)}


def _candidate_input(path: Path) -> tuple[list[dict], dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Gate2 candidates must be a JSON list")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("ticker"), str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", row["ticker"])
                or not isinstance(row.get("cik"), str) or not re.fullmatch(r"[0-9]{1,10}", row["cik"])
                or row.get("band") not in ("deep", "watch", "unknown")):
            raise ValueError("Gate2 candidate identity or band is invalid")
        identity = row["ticker"]
        if identity in seen:
            raise ValueError("Gate2 candidate identity is duplicated")
        seen.add(identity)
    completion = read_stage_receipt(path, len(rows))
    if completion["status"] == "invalid":
        raise ValueError("Gate2 candidate receipt is invalid")
    return rows, completion


def _bound_candidates(run_dir: Path, binding: dict) -> tuple[list[dict], dict]:
    if not isinstance(binding, dict):
        raise ValueError("Gate2 input binding is missing")
    name = binding.get("artifact")
    if not isinstance(name, str) or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Gate2 input must name one artifact in the same run")
    path = run_dir / name
    if _artifact_binding(path) != binding:
        raise ValueError("Gate2 candidate bytes or run directory changed")
    return _candidate_input(path)


def _gate2_rows(candidates: list[dict], rows, *, allow_missing=False) -> list[dict]:
    """Bind every outcome to its requested identity; absence stays an explicit error."""
    if not isinstance(rows, list):
        raise ValueError("Gate2 results must contain an all list")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Gate2 result must be an object")
        index = row.get("input_index")
        if type(index) is not int or not 0 <= index < len(candidates) or index in indexed:
            raise ValueError("Gate2 result index is invalid or duplicated")
        candidate = candidates[index]
        if any(row.get(key) != candidate[key] for key in ("ticker", "cik", "band")):
            raise ValueError("Gate2 result identity or band was rebound")
        if "recall_channel" in row and row["recall_channel"] != candidate.get("recall_channel"):
            raise ValueError("Gate2 result recall channel was rebound")
        status = row.get("judgment_status")
        if status == "complete":
            if (row.get("theme_fit") not in ("pure_play", "partial", "misrecall")
                    or any(not isinstance(row.get(key), str) or not row[key].strip()
                           for key in ("reason", "real_business"))):
                raise ValueError("Gate2 judgment schema is invalid")
        elif status == "error":
            if (row.get("theme_fit") is not None or not isinstance(row.get("error_code"), str)
                    or not row["error_code"]):
                raise ValueError("Gate2 error cannot carry a classification")
        else:
            raise ValueError("Gate2 judgment status is invalid")
        base = {key: value for key, value in candidate.items()
                if key not in {"input_index", "judgment_status", "theme_fit", "reason", "real_business", "error_code", "had_blurb"}}
        outcome = {key: row[key] for key in ("theme_fit", "reason", "real_business", "error_code", "had_blurb")
                   if key in row}
        indexed[index] = {**base, **outcome, "input_index": index, "judgment_status": status}
    for index, candidate in enumerate(candidates):
        if index not in indexed:
            if not allow_missing:
                raise ValueError("Gate2 persisted results omit a requested identity")
            indexed[index] = {**candidate, "input_index": index,
                              "judgment_status": "error", "theme_fit": None,
                              "error_code": "missing_result"}
    return [indexed[index] for index in range(len(candidates))]


def gate2_completion(rows, upstream):
    """Build I01 evidence for validated outcomes and the bound candidate receipt."""
    return stage_completion("gate2", len(rows), work=[
        {**stage_work("theme_fit", f"{row['cik']}:{row['ticker']}",
                      status="complete" if row["judgment_status"] == "complete" else "unavailable",
                      reason="" if row["judgment_status"] == "complete" else row["error_code"]),
         "input_index": row["input_index"], "band": row["band"]} for row in rows],
        upstream=[upstream], reasons=["unresolved_candidate_band"]
        if any(row["band"] == "unknown" for row in rows) else [])


def prepare_gate2_request(candidates_path: Path) -> Path:
    """Persist a deterministic request for the configured workflow host."""
    candidates_path = Path(candidates_path)
    candidates, upstream = _candidate_input(candidates_path)
    request = {"schema": "smallcap.gate2.request.v1", "input": _artifact_binding(candidates_path),
               "candidates": [{**row, "input_index": index} for index, row in enumerate(candidates)],
               "completion": upstream}
    out = prepare_stage_output(candidates_path.parent / "gate2_request.json")
    out.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")
    completion = stage_completion("gate2_request", len(candidates), upstream=[upstream])
    completion["input"] = request["input"]
    write_stage_receipt(out, completion)
    return out


def persist_gate2_result(request_path: Path, result_path: Path) -> tuple[Path, Path, dict]:
    """Validate workflow output and persist results and survivors without running a model."""
    request_path, result_path = Path(request_path), Path(result_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict) or request.get("schema") != "smallcap.gate2.request.v1":
        raise ValueError("Gate2 request schema is invalid")
    candidates, upstream = _bound_candidates(request_path.parent, request.get("input"))
    expected = [{**row, "input_index": index} for index, row in enumerate(candidates)]
    if request.get("candidates") != expected or request.get("completion") != upstream:
        raise ValueError("Gate2 request no longer matches its candidates")
    request_receipt = read_stage_receipt(request_path, len(candidates))
    if (request_receipt["status"] == "invalid" or request_receipt.get("input") != request["input"]):
        raise ValueError("Gate2 request receipt is missing or invalid")
    if (not isinstance(result, dict) or result.get("schema") != "smallcap.gate2.result.v1"
            or result.get("input") != request["input"]):
        raise ValueError("Gate2 result is not bound to the requested input")
    rows = _gate2_rows(candidates, result.get("all"), allow_missing=True)
    completion = gate2_completion(rows, upstream)
    completion["input"] = request["input"]
    completion["request_artifact"] = _artifact_binding(request_path)
    survivors = [row for row in rows if row["judgment_status"] == "complete"
                 and row["theme_fit"] in {"pure_play", "partial"}]
    out = prepare_stage_output(request_path.parent / "gate2_results.json")
    sout = prepare_stage_output(request_path.parent / "candidates_gate2_survivors.json")
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    write_stage_receipt(out, completion)
    survivor_completion = stage_completion("gate2_survivors", len(survivors),
                                          upstream=[read_stage_receipt(out, len(rows))])
    survivor_completion["input"] = request["input"]
    sout.write_text(json.dumps(survivors, indent=2, ensure_ascii=False), encoding="utf-8")
    write_stage_receipt(sout, survivor_completion)
    return out, sout, completion


def read_gate2_results(reports_dir: Path) -> tuple[list[dict], dict]:
    """Return validated outcomes and completion for finalization and ranking."""
    path = Path(reports_dir) / "gate2_results.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Gate2 persisted results must be a list")
    receipt = read_stage_receipt(path, len(raw))
    if receipt["status"] == "invalid" or "input" not in receipt:
        raise ValueError("Gate2 results require a valid bound receipt")
    candidates, upstream = _bound_candidates(path.parent, receipt["input"])
    rows = _gate2_rows(candidates, raw)
    expected = gate2_completion(rows, upstream)
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Gate2 completion disagrees with its bound outcomes")
    return rows, receipt


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Single-theme end-to-end driver: discover → cheap_pass → SIC filter.",
    )
    ap.add_argument(
        "--theme",
        help='Comma-separated FTS keywords, e.g. "railcar,railcar leasing"',
    )
    ap.add_argument(
        "--slug",
        help="Short identifier used in output filenames, e.g. railcar",
    )
    ap.add_argument(
        "--micro", action="store_true",
        help=f"Use micro-cap limit ({CFG['micro_cap_max']/1e6:.0f}M) instead of "
             f"standard small-cap limit ({CFG['market_cap_max']/1e9:.1f}B)",
    )
    ap.add_argument("--prepare-gate2", type=Path, help="Prepare a bound request from an existing candidates artifact")
    ap.add_argument("--gate2-request", type=Path, help="Previously prepared gate2_request.json")
    ap.add_argument("--gate2-result", type=Path, help="Workflow result JSON to validate and persist")
    args = ap.parse_args()
    if args.gate2_result or args.gate2_request:
        if not args.gate2_result or not args.gate2_request or args.prepare_gate2:
            ap.error("--gate2-request and --gate2-result must be supplied together")
        out, survivors, completion = persist_gate2_result(args.gate2_request, args.gate2_result)
        print(f"Gate2 status: {completion['status']}; results: {out}; survivors: {survivors}")
        return 0 if completion["status"] == "complete" else 2
    if args.prepare_gate2:
        out = prepare_gate2_request(args.prepare_gate2)
        request = json.loads(out.read_text(encoding="utf-8"))
        print(f"Gate2 request: {out}; status: {request['completion']['status']}")
        return 0 if request["completion"]["status"] == "complete" else 2
    if not args.theme or not args.slug:
        ap.error("--theme and --slug are required for the mechanical pipeline")

    out_slug = _slug(args.slug)
    max_mcap = CFG["micro_cap_max"] if args.micro else CFG["market_cap_max"]
    watch_band_max = CFG.get("watch_band_max", 5_000_000_000)
    cap_label = f"${max_mcap/1e6:.0f}M (micro)" if args.micro else f"${max_mcap/1e9:.1f}B"

    print(
        f"\n{'#'*72}\n"
        f"  run_theme  slug={out_slug}  cap={cap_label}  watch_band=${watch_band_max/1e9:.1f}B\n"
        f"  theme keywords: {args.theme}\n"
        f"{'#'*72}",
        flush=True,
    )

    # Stage 1, discover (Phase 4: passes watch_band_max for dual-band tagging)
    universe_csv = stage_discover(args.theme, out_slug, max_mcap, watch_band_max=watch_band_max)

    # Stage 2, cheap pass
    cheappass_csv = stage_cheap_pass(universe_csv, out_slug, max_mcap)

    # Stage 3, inline SIC filter → candidates JSON
    candidates_json = stage_sic_filter(cheappass_csv, universe_csv, out_slug, theme_kw=args.theme)
    request_path = prepare_gate2_request(candidates_json)
    candidates = json.loads(candidates_json.read_text(encoding="utf-8"))
    completion = read_stage_receipt(candidates_json, len(candidates))

    # Stage 4, handoff message
    print(
        f"\n{'='*72}\n"
        f"  Mechanical pipeline status: {completion['status']}.\n"
        f"\n"
        f"  Next steps (SKILL.md-orchestrated, not auto-run by this script):\n"
        f"    1. Run LLM theme-fit gate:\n"
        f"         Pass {request_path} JSON inline to workflows/theme-fit-gate.js in the configured workflow host.\n"
        f"         Keep the host's installed llmcall routing defaults.\n"
        f"         Persist its JSON result with --gate2-request {request_path} --gate2-result <workflow-result.json>.\n"
        f"    2. Batch deep-dive data collection:\n"
        f"         python tools/deepdive_data.py --candidates {candidates_json.parent / 'candidates_gate2_survivors.json'}\n"
        f"    3. Rank survivors:\n"
        f"         python tools/rank.py --slug {out_slug}\n"
        f"{'='*72}",
        flush=True,
    )
    return 0 if completion["status"] == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
