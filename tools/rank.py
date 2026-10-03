"""
rank.py — 聚合 deep dive 报告,产出主题级排序

读 reports/smallcap/report_*.md,提取评级/置信度,结合 cheap pass 体检分 +
deepdive JSON 的硬数据,产出排序表。AVOID/kill-flag>=2 一律沉底(不靠高分捞回)。

NOTE — watch-band companies (band="watch", $2-5B market cap) are NOT ranked here.
They are surfaced separately via the candidates JSON (band=watch) for human review.
deepdive_data.py --candidates skips them (no report_*.md generated → no rank entry).
This file naturally ranks only deep-band companies that completed a full deep-dive.

用法:
    python tools/rank.py
    python tools/rank.py --slug railcar
    python tools/rank.py --input /path/to/reports/
输出: reports/smallcap/RANKING.md
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from _common import REPORTS, today
from _output_paths import prove_output_path
from filter_by_sic import (stage_completion, stage_work, read_stage_receipt,
                           write_stage_receipt, prepare_stage_output, stage_receipt_path)

RATING_MAP = {"买入": 3, "buy": 3, "观察": 2, "watch": 2, "hold": 2,
              "避开": 1, "avoid": 1, "sell": 1}

# v0.3.1 #13, a PER-TICKER deep-dive file is deepdive_<TICKER>_<YYYY-MM-DD>.json. The run dir
# also holds non-ticker sidecars (deepdive_verdicts.json / deepdive_queue.json /
# deepdive_targets.json) that a naive glob("deepdive_*.json") counts as deep-dives, inflating the
# funnel banner by one (semiconductors 20 vs 19, cybersecurity 26 vs 25, biotech 43 vs 42 all =
# real N + deepdive_verdicts.json). Count only files matching this shape, the SAME per-ticker
# pattern load_hard_data consumes, so the banner equals the names actually deep-dived.
_DEEPDIVE_TICKER_RE = re.compile(r"^deepdive_[A-Za-z0-9.\-]+_\d{4}-\d{2}-\d{2}\.json$")


def read_text_utf8(path, *, payload=None) -> str:
    """Read a report as UTF-8. Windows' default codepage is GBK, so a naive open() of the
    utf-8-written report_*.md raises UnicodeDecodeError for any ad-hoc consumer (ergonomics
    G5). All report reads here go through this helper."""
    if payload is not None:
        return payload.decode("utf-8")
    from pathlib import Path as _P
    return _P(path).read_text(encoding="utf-8")


def extract_rating(md: str) -> dict:
    """从报告文本提取评级/置信度。

    优先解析新的围栏式 front-matter 评级契约(```rating ... ```)——确定性、机器可读;
    finalize_run.parse_rating_block 是单一权威解析器。仅当报告没有围栏块(旧版自由文本报告)
    时回退到旧的散文正则(旧正则在 11 份报告里有 5 份置信度解析失败 — ergonomics G2)。
    """
    out = {"rating": None, "rating_score": 0, "confidence": None, "killflags": 0}

    # 1) Fenced front-matter contract (preferred, deterministic).
    from finalize_run import parse_rating_block
    fm = parse_rating_block(md)
    if fm.get("found"):
        if not fm.get("rating"):
            raise ValueError("Unfinished or invalid authoritative rating; finalize the decision first")
        out["killflags"] = fm.get("killflag_count", 0)
    if fm.get("found") and fm.get("rating"):
        r = fm["rating"]
        out["rating"] = r
        out["rating_score"] = RATING_MAP.get(r.lower() if isinstance(r, str) else r,
                                             RATING_MAP.get(r, 0))
        out["confidence"] = fm.get("confidence")
        return out

    # 2) Fallback: legacy prose regex (容错多种写法).
    # 评级:【买入/观察/避开】 或 评级: 买入 (允许 markdown 粗体/空格)
    m = re.search(r"评级[:：]?\s*[*【\[]*\s*(买入|观察|避开|buy|watch|hold|avoid|sell)",
                  md, re.I)
    if m:
        r = m.group(1).lower()
        out["rating"] = m.group(1)
        out["rating_score"] = RATING_MAP.get(r, 0)
    # 置信度 (允许粗体 + 空格变体: 置信度 **62 %**)
    mc = re.search(r"置信度[:：]?\s*[*]*\s*(\d+)\s*[*]*\s*%", md)
    if mc:
        out["confidence"] = int(mc.group(1))
    return out


def _report_files(base, slug=""):
    scoped = list(base.glob(f"report_{slug}_*.md")) if slug else []
    return sorted(scoped or base.glob("report_*.md"))


def _report_ticker(path):
    return Path(path).stem.removeprefix("report_")


def _hard_data_file(ticker, base):
    files = sorted(path for path in base.glob("deepdive_*.json")
                   if path.name.startswith(f"deepdive_{ticker}_")
                   and _DEEPDIVE_TICKER_RE.fullmatch(path.name))
    return files[-1] if files else None


def _candidate_files(base):
    return sorted(path for path in base.glob("candidates_*.json")
                  if "gate2_survivors" not in path.name
                  and not path.name.endswith(".stage.json")) or sorted(base.glob("all_candidates.json"))


def _run_artifact(base, name):
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or "/" in name or "\\" in name or ":" in name):
        raise ValueError("run artifact must be a same-directory basename")
    return base / name


def _collect_ranking_inputs(reports_dir, report_files=None):
    """Capture the selected payloads and the exact bytes used by upstream validators."""
    base = Path(reports_dir).absolute()
    reports = _report_files(base) if report_files is None else sorted(Path(p).absolute()
                                                                   for p in report_files)
    payloads = {}

    def capture(path):
        path = Path(path).absolute()
        if path.parent != base:
            raise ValueError("ranking inputs must belong to the run directory")
        payload = path.read_bytes()
        if path.name in payloads and payloads[path.name] != payload:
            raise ValueError(f"ranking input changed while reading: {path.name}")
        payloads[path.name] = payload

    def capture_pair(path):
        capture(path)
        receipt = stage_receipt_path(path)
        if receipt.exists():
            capture(receipt)

    gate2_path = base / "gate2_results.json"
    gate2_rows, gate2_completion = None, None
    event_rows, event_completion = None, None
    event_path = base / "candidates_event_admitted.json"
    if event_path.exists() or stage_receipt_path(event_path).exists():
        if gate2_path.exists() or stage_receipt_path(gate2_path).exists():
            raise ValueError("A run cannot mix event admission and Gate2 results")
        from _event_admission import read_event_admission, event_input_artifacts
        _, event_completion = read_event_admission(base)
        event_rows = event_completion["decisions"]
        for member in event_input_artifacts(base, event_completion):
            capture(member)
        for binding in (event_completion, event_completion["input"], event_completion["cheap_input"]):
            payload = payloads[binding["artifact"]]
            if (len(payload) != binding["artifact_bytes"]
                    or hashlib.sha256(payload).hexdigest() != binding["artifact_sha256"]):
                raise ValueError("Captured event input differs from its parsed snapshot")
        if json.loads(payloads[stage_receipt_path(event_path).name]) != event_completion:
            raise ValueError("Captured event receipt differs from its parsed snapshot")
        for key, binding in (("source_receipt_sha256", event_completion["input"]),
                             ("cheap_receipt_sha256", event_completion["cheap_input"])):
            payload = payloads[stage_receipt_path(base / binding["artifact"]).name]
            if hashlib.sha256(payload).hexdigest() != event_completion[key]:
                raise ValueError("Captured upstream receipt differs from its parsed snapshot")
        candidates = [event_path]
        source_name = event_completion["input"]["artifact"]
        for path in _candidate_files(base):
            if path.name not in {source_name, event_path.name}:
                capture_pair(path)
                if json.loads(payloads[path.name]):
                    raise ValueError("Candidate artifact is outside the bound event cohort")
    elif gate2_path.exists() or stage_receipt_path(gate2_path).exists():
        capture_pair(gate2_path)
        receipt_name = stage_receipt_path(gate2_path).name
        if receipt_name not in payloads:
            raise ValueError("Gate2 results require a bound stage receipt")
        receipt = json.loads(payloads[receipt_name])
        binding = receipt.get("input") if isinstance(receipt, dict) else None
        if not isinstance(binding, dict):
            raise ValueError("Gate2 receipt requires its candidate input binding")
        candidates = [_run_artifact(base, binding.get("artifact"))]
        capture_pair(candidates[0])
        # The producer owns validation of every requested index, identity and decision.
        from run_theme import read_gate2_results
        gate2_rows, gate2_completion = read_gate2_results(base)
        if gate2_completion.get("input") != binding:
            raise ValueError("Gate2 input binding changed while reading")
    else:
        candidates = _candidate_files(base)
        for path in candidates:
            capture_pair(path)

    hard_data = {}
    for path in reports:
        capture(path)
        ticker = _report_ticker(path)
        hard_data[ticker] = _hard_data_file(ticker, base)
        if hard_data[ticker] is not None:
            capture(hard_data[ticker])
    # Upstream readers read their own files. Reject mutation around those reads.
    for name in list(payloads):
        capture(base / name)
    bindings = [{"artifact": name, "artifact_bytes": len(payload),
                 "artifact_sha256": hashlib.sha256(payload).hexdigest()}
                for name, payload in sorted(payloads.items())]
    return {"reports": reports, "hard_data": hard_data, "candidates": candidates,
            "payloads": payloads, "input_artifacts": bindings,
            "gate2_rows": gate2_rows, "gate2_completion": gate2_completion,
            "event_rows": event_rows, "event_completion": event_completion}


def ranking_input_artifacts(reports_dir, report_files=None):
    """Return sorted byte bindings using the same input selectors as the ranking CLI."""
    return _collect_ranking_inputs(reports_dir, report_files)["input_artifacts"]


def load_hard_data(ticker: str, reports_dir=None, *, _inputs=None) -> dict:
    # reports_dir defaults to REPORTS, but MUST honor --input so finalize_run's
    # `rank.py --input <run>` finds the run's deepdive JSONs (previously it always
    # globbed REPORTS, so an --input run had no hard data -> missing 'killflags' column).
    base = Path(reports_dir if reports_dir is not None else REPORTS)
    path = (_inputs["hard_data"].get(ticker) if _inputs is not None
            else _hard_data_file(ticker, base))
    if path is None:
        return {}
    payload = _inputs["payloads"][path.name] if _inputs is not None else path.read_bytes()
    d = json.loads(payload)
    if isinstance(d, list):
        return {}
    der = d.get("derived", {})
    tk = d.get("tenk", {})
    ins = d.get("insider", {})
    # M4: read killflag_count if present (resilient to new kill-flag types added in future);
    # fall back to summing the three boolean flags if the field is absent.
    _kfc = d.get("killflag_count")
    if _kfc is not None:
        try:
            kf = int(_kfc)
        except (TypeError, ValueError):
            kf = 0
    else:
        kf = sum([1 if (tk.get("has_going_concern")) else 0,
                  1 if tk.get("has_material_weakness") else 0,
                  1 if tk.get("has_death_spiral") else 0])
    revenue = der.get("latest_revenue")
    net_income = der.get("latest_net_income")
    ocf = der.get("latest_ocf")
    return {"revenue_M": round(revenue / 1e6, 1) if revenue is not None else None,
            "net_income_M": round(net_income / 1e6, 1) if net_income is not None else None,
            "ocf_M": round(ocf / 1e6, 1) if ocf is not None else None,
            "rev_growth": der.get("revenue_growth_pct"),
            "dilution": der.get("shares_growth_pct"),
            "insider": ins.get("net_signal"),
            "killflags": kf,
            "going_concern": tk.get("has_going_concern"),
            "material_weakness": tk.get("has_material_weakness")}


def compute_funnel_stats(reports_dir=None, *, _inputs=None) -> dict:
    """Compute the run's honest funnel from the files present in reports_dir.

    P-H: the old narration read "{report_count} 召回 → {deepdive_count} 小盘候选", which on the
    uranium run rendered "9 召回 → 10 小盘候选" — recall < candidates is nonsensical and both
    labels were wrong (both numbers were just the deep-dived count). The real funnel narrows
    candidates -> deep-band -> deep-dived, so we read the candidates JSON for the true upstream
    counts instead of mislabeling the report/deepdive file counts.

    Returns a dict:
        candidates   — rows in candidates_*.json (theme universe after gates), or None if absent
        deep_band    — rows with band == "deep" in candidates_*.json, or None if absent
        deepdived    — number of per-ticker deepdive_<TICKER>_<DATE>.json files (names that got a
                       full deep-dive); non-ticker sidecars (verdicts/queue/targets) are excluded
                       so the count is not inflated (v0.3.1 #13 off-by-one fix)
        reports      — number of report_*.md files (names with a decision-ready report)
    Counts that can't be derived are None so the template can omit that stage rather than print a
    contradictory number.
    """
    base = Path(reports_dir if reports_dir is not None else REPORTS)
    reports = glob.glob(str(base / "report_*.md"))
    # v0.3.1 #13: count ONLY per-ticker deepdive_<TICKER>_<DATE>.json files; the run dir also
    # contains deepdive_verdicts/queue/targets.json sidecars that a bare glob would over-count by
    # one (the off-by-one banner bug). Filter to the per-ticker shape.
    deepdives = [f for f in glob.glob(str(base / "deepdive_*.json"))
                 if _DEEPDIVE_TICKER_RE.match(Path(f).name)]

    if _inputs is None and (base / "candidates_event_admitted.json").exists():
        _inputs = _collect_ranking_inputs(base, report_files=[])
    candidates = None
    deep_band = None
    # Prefer the theme candidates file (candidates_<slug>.json); fall back to all_candidates.json.
    cand_files = _inputs["candidates"] if _inputs is not None else _candidate_files(base)
    event_completion = _inputs.get("event_completion") if _inputs is not None else None
    rows: list = list(_inputs["event_rows"]) if event_completion is not None else []
    upstream, work = ([event_completion] if event_completion is not None else []), []
    for cf in ([] if event_completion is not None else sorted(cand_files)):
        try:
            payload = (_inputs["payloads"][Path(cf).name] if _inputs is not None
                       else Path(cf).read_bytes())
            d = json.loads(payload)
            r = d if isinstance(d, list) else d.get("candidates") if isinstance(d, dict) else None
            if not isinstance(r, list) or any(not isinstance(x, dict) for x in r):
                raise ValueError("invalid candidate rows")
            if any(not isinstance(row.get("ticker"), str)
                   or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", row["ticker"])
                   for row in r):
                raise ValueError("invalid candidate identity")
        except (OSError, ValueError):
            work.append(stage_work("candidate_artifact", Path(cf).name,
                                   status="invalid", reason="invalid_candidate_payload"))
            continue
        rows.extend(r)
        upstream.append(read_stage_receipt(cf, len(r)))
    if upstream:
        candidates = len(rows)
        deep_band = sum(1 for x in rows if x.get("band") == "deep")

    return {
        "candidates": candidates,
        "deep_band": deep_band,
        "deepdived": len(deepdives),
        "reports": len(reports),
        "candidate_rows": rows,
        "completion": stage_completion("ranking_candidates", len(rows), work=work,
                                        upstream=upstream,
                                        reasons=[] if cand_files else ["missing_candidate_artifact"]),
    }


def _ranking_scope(stats, inputs):
    """Keep each deep identity required unless its bound Gate2 judgment excludes it."""
    if inputs.get("event_rows") is not None:
        required = [row for row in inputs["event_rows"]
                    if row["admission_decision"] in {"retained", "unresolved"}
                    and row["band"] in {"deep", "unknown"}]
        tickers = {row["ticker"].upper() if row["ticker"] else "CIK" + row["cik"]
                   for row in required}
        reasons = ["unresolved_candidate_band"] if any(
            row["band"] == "unknown" for row in required) else []
        return tickers, reasons
    excluded = {row["input_index"] for row in (inputs["gate2_rows"] or [])
                if row["judgment_status"] == "complete" and row["theme_fit"] == "misrecall"}
    required = [row for index, row in enumerate(stats["candidate_rows"])
                if row.get("band") == "deep" and index not in excluded]
    tickers = [str(row.get("ticker") or "").upper() for row in required]
    reasons = []
    if any(row.get("band") not in ("deep", "watch") for row in stats["candidate_rows"]):
        reasons.append("unresolved_candidate_band")
    if any(not ticker for ticker in tickers):
        reasons.append("missing_deep_candidate_identity")
    all_tickers = [str(row.get("ticker") or "").upper() for row in stats["candidate_rows"]]
    if len(set(all_tickers)) != len(all_tickers):
        reasons.append("ambiguous_candidate_identity")
    if any(all_tickers.count(ticker) > 1 for ticker in tickers):
        reasons.append("ambiguous_deep_candidate_identity")
    return set(tickers), reasons


def _ranking_report_selection(stats, inputs):
    required_tickers, reasons = _ranking_scope(stats, inputs)
    scope_known = (inputs.get("event_rows") is not None or inputs["gate2_rows"] is not None
                   or stats["completion"]["status"] == "complete")
    reports = [path for path in inputs["reports"]
               if not scope_known or _report_ticker(path).upper() in required_tickers]
    return reports, required_tickers, reasons, scope_known


def ranking_report_files(reports_dir, report_files=None):
    """Select report observations exactly as rank does, for downstream receipt counts."""
    inputs = _collect_ranking_inputs(reports_dir, report_files)
    stats = compute_funnel_stats(reports_dir, _inputs=inputs)
    reports, _, _, _ = _ranking_report_selection(stats, inputs)
    return reports


def funnel_line(stats: dict, survivors: int) -> str:
    """Render the funnel narration as a single monotonically-narrowing chain (P-H).

    Only stages with a real count are shown, in narrowing order, so the line can never read a
    larger number downstream of a smaller one. `survivors` is the cheap-pass survivor count
    (rows in the ranked frame).
    """
    stages: list[str] = []
    if stats.get("candidates") is not None:
        stages.append(f"{stats['candidates']} 候选")
    if stats.get("deep_band") is not None:
        stages.append(f"{stats['deep_band']} 小盘(deep band)")
    stages.append(f"{stats['deepdived']} 家逐一 deep dive")
    if survivors != stats["deepdived"]:
        stages.append(f"cheap pass 幸存 {survivors}")
    return "> 漏斗:" + " → ".join(stages) + "。AVOID/kill-flag≥2 一律沉底。**研究输出,非投资建议。**"


def rank_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the ranking rule: AVOID (rating_score<=1) OR kill-flag>=2 sinks to the bottom;
    survivors order by rating_score * confidence. Pure function — used by main() and selftest."""
    df = df.copy()
    if len(df) == 0:
        for col in ("ticker", "rating", "insider"):
            df[col] = pd.Series(dtype="object")
        for col in ("rating_score", "confidence", "killflags", "combined", "revenue_M",
                    "net_income_M", "ocf_M", "rev_growth", "dilution"):
            df[col] = pd.Series(dtype="float64")
        df["sink"] = pd.Series(dtype="bool")
        return df
    # Direct callers may have neither report nor sidecar risk counts.
    # The complete caller reconciles both sources before creating this frame.
    if "killflags" not in df.columns:
        df["killflags"] = 0
    df["sink"] = (df["rating_score"] <= 1) | (df["killflags"].fillna(0) >= 2)
    df["combined"] = df["rating_score"] * (df["confidence"].fillna(50) / 100)
    return df.sort_values(["sink", "combined"], ascending=[True, False])


def _selftest() -> None:
    """Verify rating parsing + the sink/ordering rule with synthetic data (no files/network)."""
    # extract_rating: tolerant parsing of multiple writings (legacy prose fallback)
    assert extract_rating("评级:买入\n置信度: 70%")["rating_score"] == 3, "买入 -> 3"
    assert extract_rating("评级:买入\n置信度: 70%")["confidence"] == 70, "confidence parse"
    assert extract_rating("评级:【避开】")["rating_score"] == 1, "避开 bracketed -> 1"
    assert extract_rating("评级： 观察")["rating_score"] == 2, "观察 fullwidth colon -> 2"
    assert extract_rating("no rating here")["rating_score"] == 0, "no rating -> 0"
    # G2 fix: the legacy regex failures (bold-first rating, spaced/bolded confidence) now parse.
    assert extract_rating("评级 **观察**")["rating_score"] == 2, "bold-first 观察 (old regex failed)"
    assert extract_rating("置信度 **62 %**")["confidence"] == 62, "bold+spaced confidence (old failed)"

    # NEW front-matter contract: fenced ```rating``` block is preferred and deterministic.
    fm = ("# X Deep Dive\n\n```rating\nrating: 买入\nconfidence: 80\nmos_basis: fcf_cap\n"
          "buy_eligible: true\n```\nbody...\n")
    assert extract_rating(fm)["rating_score"] == 3, "fenced 买入 -> 3"
    assert extract_rating(fm)["confidence"] == 80, "fenced confidence"
    # English in the fenced block normalizes to 中文 score.
    assert extract_rating("```rating\nrating: WATCH\nconfidence: 50\n```")["rating_score"] == 2, \
        "fenced english WATCH -> 2"
    # Fenced block wins even if prose disagrees (front-matter is authoritative).
    mixed = "```rating\nrating: 避开\nconfidence: 40\n```\n评级: 买入 置信度: 90%"
    assert extract_rating(mixed)["rating_score"] == 1, "fenced block overrides prose"
    assert extract_rating(mixed)["confidence"] == 40, "fenced confidence overrides prose"
    # An unfinished fenced decision is invalid, including in the supported CLI.
    try:
        extract_rating("```rating\nrating: TBD\n```")
    except ValueError:
        pass
    else:
        raise AssertionError("unfinished fenced decisions must be rejected")
    # rank_frame: sink (AVOID + kill-flag>=2) + ordering
    df = pd.DataFrame([
        {"ticker": "BUY0KF", "rating_score": 3, "confidence": 80, "killflags": 0},
        {"ticker": "WATCH",  "rating_score": 2, "confidence": 60, "killflags": 0},
        {"ticker": "AVOID",  "rating_score": 1, "confidence": 90, "killflags": 0},
        {"ticker": "BUY2KF", "rating_score": 3, "confidence": 99, "killflags": 2},
    ])
    order = rank_frame(df)["ticker"].tolist()
    assert order[0] == "BUY0KF", f"clean BUY must rank first, got {order}"
    assert order[1] == "WATCH", f"WATCH second, got {order}"
    assert set(order[2:]) == {"AVOID", "BUY2KF"}, f"AVOID + kill-flag>=2 must sink, got {order}"
    ranked = rank_frame(df).set_index("ticker")
    assert bool(ranked.loc["BUY2KF", "sink"]) is True, "kill-flag>=2 sinks even a 买入"
    # Defensive: report-only rows (no deepdive JSON -> no 'killflags' column) must not crash
    # the rebuild (finalize_run invokes rank.py --input and a scaffolded report may have no
    # hard data yet).
    df_nohard = pd.DataFrame([{"ticker": "RPT", "rating_score": 2, "confidence": 60}])
    out = rank_frame(df_nohard)
    assert bool(out.iloc[0]["sink"]) is False, "report-only row (no killflags col) survives, no crash"

    # P-H: funnel narration is a monotonically-narrowing chain with TRUE labels, never the old
    # garbled "9 召回 → 10 小盘候选" (recall < candidates). Reconstruct the uranium funnel.
    uranium = {"candidates": 68, "deep_band": 42, "deepdived": 9, "reports": 9}
    fl = funnel_line(uranium, survivors=9)
    assert "68 候选" in fl and "42 小盘" in fl and "9 家逐一 deep dive" in fl, f"funnel stages: {fl}"
    assert "召回" not in fl, "old mislabel '召回' must be gone (P-H)"
    # the chain must be strictly non-increasing in the numbers it prints (no 9->10 inversion)
    nums = [int(x) for x in re.findall(r"(\d+)", fl)]
    assert nums == sorted(nums, reverse=True), f"funnel numbers must narrow monotonically: {nums}"
    # compute_funnel_stats reads candidates JSON for true counts (not the report/deepdive counts).
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        rd = Path(td)
        json.dump([{"ticker": "A", "band": "deep"}, {"ticker": "B", "band": "deep"},
                   {"ticker": "C", "band": "watch"}],
                  open(rd / "candidates_theme.json", "w", encoding="utf-8"))
        # a gate2_survivors file must NOT be counted as the candidate universe
        json.dump([{"ticker": "A", "band": "deep"}],
                  open(rd / "candidates_gate2_survivors.json", "w", encoding="utf-8"))
        (rd / "deepdive_A_2026-06-20.json").write_text("{}", encoding="utf-8")
        (rd / "report_A.md").write_text("x", encoding="utf-8")
        # v0.3.1 #13: drop the run-state sidecars that previously inflated the deep-dive banner by
        # one (deepdive_verdicts/queue/targets.json). compute_funnel_stats must count ONLY the
        # per-ticker deepdive_<TICKER>_<DATE>.json file, so deepdived stays 1, not 4.
        for sidecar in ("deepdive_verdicts.json", "deepdive_queue.json", "deepdive_targets.json"):
            (rd / sidecar).write_text("{}", encoding="utf-8")
        st = compute_funnel_stats(rd)
        assert st["candidates"] == 3, f"candidates from theme file (gate2_survivors excluded): {st}"
        assert st["deep_band"] == 2, f"deep-band count: {st}"
        assert st["deepdived"] == 1 and st["reports"] == 1, (
            f"deepdive/report counts: deepdived must EXCLUDE verdicts/queue/targets sidecars "
            f"(#13 off-by-one), got {st}")
        # The banner narration then reports the true deep-dived count (1), never N+1 (4).
        assert "1 家逐一 deep dive" in funnel_line(st, 1), \
            f"#13: banner must show actual deep-dived count, not inflated by sidecars: {st}"
        # Direct assertion on the filename matcher: ticker files match, sidecars do not.
        assert _DEEPDIVE_TICKER_RE.match("deepdive_AOSL_2026-06-21.json"), "#13: ticker file matches"
        assert _DEEPDIVE_TICKER_RE.match("deepdive_BRK.A_2026-06-21.json"), "#13: dotted ticker matches"
        assert not _DEEPDIVE_TICKER_RE.match("deepdive_verdicts.json"), "#13: verdicts sidecar excluded"
        assert not _DEEPDIVE_TICKER_RE.match("deepdive_queue.json"), "#13: queue sidecar excluded"
        assert not _DEEPDIVE_TICKER_RE.match("deepdive_targets.json"), "#13: targets sidecar excluded"
    # no candidates file -> candidates/deep_band None, line omits those stages (no crash/contradiction)
    fl2 = funnel_line({"candidates": None, "deep_band": None, "deepdived": 5, "reports": 5}, 5)
    assert "候选" not in fl2 and "5 家逐一 deep dive" in fl2, f"funnel omits absent stages: {fl2}"

    print("rank selftest PASS (extract_rating parsing + sink/ordering: AVOID & kill-flag>=2 sink "
          "+ P-H funnel narration narrows monotonically with true labels + #13 deep-dive banner "
          "counts only per-ticker deepdive files (verdicts/queue/targets sidecars excluded, "
          "off-by-one fixed))")


def main():
    ap = argparse.ArgumentParser(
        description="rank.py — aggregate deep-dive reports and produce a ranked shortlist."
    )
    ap.add_argument(
        "--slug", default="",
        help="Optional theme slug: if set, only report_<slug>_*.md files are included "
             "(gracefully ignored if no slug-scoped files exist, falling back to all report_*.md).",
    )
    ap.add_argument(
        "--input", default="",
        help="Optional path to the reports directory (default: REPORTS from config).",
    )
    ap.add_argument("--output", default="RANKING.md",
                    help="New ranking basename in the run directory; existing outputs are preserved.")
    ap.add_argument("--selftest", action="store_true",
                    help="Run self-test (rating parsing + sink/ranking logic) and exit")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    reports_dir = prove_output_path(Path(args.input) if args.input else REPORTS)
    try:
        output_path = prove_output_path(_run_artifact(reports_dir, args.output))
        inputs = _collect_ranking_inputs(reports_dir, _report_files(reports_dir, args.slug))
        stats = compute_funnel_stats(reports_dir, _inputs=inputs)
        report_files, required_tickers, reasons, scope_known = _ranking_report_selection(stats, inputs)
    except (OSError, ValueError) as exc:
        ap.error(f"invalid ranking inputs: {exc}")

    rows, work = [], []
    for rp in report_files:
        ticker = _report_ticker(rp)
        try:
            md = read_text_utf8(rp, payload=inputs["payloads"][rp.name])
            rec = {"ticker": ticker}
            rec.update(extract_rating(md))
            report_killflags = rec["killflags"]
            rec.update(load_hard_data(ticker, reports_dir, _inputs=inputs))
        except (OSError, ValueError, OverflowError) as exc:
            ap.error(f"invalid report {Path(rp).name}: {exc}")
        # Disagreement must not erase risk already identified by either source.
        rec["killflags"] = max(report_killflags, rec["killflags"])
        rows.append(rec)
        work.append(stage_work("report_parse", Path(rp).name))
    df = pd.DataFrame(rows)

    # 排序:AVOID(rating_score=1)或 kill-flag>=2 沉底;其余按 评级分*置信度
    df = rank_frame(df)

    ranked_tickers = {row["ticker"].upper() for row in rows}
    if not rows and stats["candidates"] != 0 and (not scope_known or required_tickers):
        reasons.append("empty_ranking_without_complete_empty_candidates")
    if required_tickers - ranked_tickers:
        reasons.append("unranked_deep_candidates")
    if len(ranked_tickers) != len(rows):
        reasons.append("duplicate_report_identity")
    upstream = [stats["completion"]]
    if inputs["gate2_completion"] is not None:
        upstream.append(inputs["gate2_completion"])
    if inputs.get("event_completion") is not None:
        upstream.append(inputs["event_completion"])
    completion = stage_completion("ranking", len(df), work=work,
                                  upstream=upstream, reasons=reasons)
    completion["input_artifacts"] = inputs["input_artifacts"]

    date = today()
    slug_label = f" [{args.slug}]" if args.slug else ""
    lines = [f"# 小盘深度调研排序{slug_label} — {date}", "",
             funnel_line(stats, len(df)), "",
             f"> Stage status: {completion['status']} (observed ranking scope).", "",
             "## 排序", "",
             "| 排名 | 代码 | 评级 | 置信 | 营收 | 净利 | OCF | 增速 | 稀释 | 内部人 | kill-flag |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    rank = 0
    for _, r in df.iterrows():
        rank += 1
        def m(v): return f"${v:.0f}M" if pd.notna(v) else "—"
        def p(v): return f"{v:+.0f}%" if pd.notna(v) else "—"
        flag = " ⬇沉底" if r["sink"] else ""
        lines.append(
            f"| {rank}{flag} | {r['ticker']} | {r.get('rating','?')} | "
            f"{r.get('confidence','?')}% | {m(r.get('revenue_M'))} | {m(r.get('net_income_M'))} | "
            f"{m(r.get('ocf_M'))} | {p(r.get('rev_growth'))} | {p(r.get('dilution'))} | "
            f"{r.get('insider','—')} | {int(r['killflags']) if pd.notna(r.get('killflags')) else '—'} |")

    # 分层小结
    top = df[~df["sink"]]
    lines += ["", "## 分层", "",
              f"- **非沉底(观察/买入候选):** {len(top)} 家 — " +
              ", ".join(top["ticker"].tolist()),
              f"- **沉底(避开/kill-flag≥2):** {df['sink'].sum()} 家", "",
              "各家完整尽调见 `report_<ticker>.md`(含可证伪多空论点+pre-mortem+反方)。"]

    try:
        current_inputs = ranking_input_artifacts(reports_dir, _report_files(reports_dir, args.slug))
        if current_inputs != inputs["input_artifacts"]:
            raise ValueError("ranking inputs changed; use a stable run input set")
    except (OSError, ValueError) as exc:
        ap.error(f"cannot publish ranking from changed inputs: {exc}")
    out = prepare_stage_output(output_path)
    with out.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    write_stage_receipt(out, completion)
    print(df[["ticker", "rating", "confidence", "killflags", "sink", "combined"]].to_string())
    print(f"\n排序: {out}")
    return 0 if completion["status"] == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())
