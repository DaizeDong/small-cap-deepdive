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
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add tools dir to path for _common import
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from _common import REPORTS, today

RATING_MAP = {"买入": 3, "buy": 3, "观察": 2, "watch": 2, "hold": 2,
              "避开": 1, "avoid": 1, "sell": 1}


def read_text_utf8(path) -> str:
    """Read a report as UTF-8. Windows' default codepage is GBK, so a naive open() of the
    utf-8-written report_*.md raises UnicodeDecodeError for any ad-hoc consumer (ergonomics
    G5). All report reads here go through this helper."""
    from pathlib import Path as _P
    return _P(path).read_text(encoding="utf-8")


def extract_rating(md: str) -> dict:
    """从报告文本提取评级/置信度。

    优先解析新的围栏式 front-matter 评级契约(```rating ... ```)——确定性、机器可读;
    finalize_run.parse_rating_block 是单一权威解析器。仅当报告没有围栏块(旧版自由文本报告)
    时回退到旧的散文正则(旧正则在 11 份报告里有 5 份置信度解析失败 — ergonomics G2)。
    """
    out = {"rating": None, "rating_score": 0, "confidence": None}

    # 1) Fenced front-matter contract (preferred, deterministic).
    try:
        from finalize_run import parse_rating_block
        fm = parse_rating_block(md)
    except Exception:
        fm = {"found": False}
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


def load_hard_data(ticker: str, reports_dir=None) -> dict:
    # reports_dir defaults to REPORTS, but MUST honor --input so finalize_run's
    # `rank.py --input <run>` finds the run's deepdive JSONs (previously it always
    # globbed REPORTS, so an --input run had no hard data -> missing 'killflags' column).
    base = reports_dir if reports_dir is not None else REPORTS
    files = glob.glob(str(base / f"deepdive_{ticker}_*.json"))
    if not files:
        return {}
    d = json.load(open(sorted(files)[-1], encoding="utf-8"))
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
    return {"revenue_M": round((der.get("latest_revenue") or 0) / 1e6, 1),
            "net_income_M": round((der.get("latest_net_income") or 0) / 1e6, 1),
            "ocf_M": round((der.get("latest_ocf") or 0) / 1e6, 1),
            "rev_growth": der.get("revenue_growth_pct"),
            "dilution": der.get("shares_growth_pct"),
            "insider": ins.get("net_signal"),
            "killflags": kf,
            "going_concern": tk.get("has_going_concern"),
            "material_weakness": tk.get("has_material_weakness")}


def compute_funnel_stats() -> tuple[int, int]:
    """Compute actual funnel numbers from files present.

    Returns:
        (universe_count, deepdive_count) — count of report_*.md and deepdive_*.json files
    """
    reports = glob.glob(str(REPORTS / "report_*.md"))
    deepdives = glob.glob(str(REPORTS / "deepdive_*.json"))

    universe = len(reports)
    deepdive = len(deepdives)

    return universe, deepdive


def rank_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the ranking rule: AVOID (rating_score<=1) OR kill-flag>=2 sinks to the bottom;
    survivors order by rating_score * confidence. Pure function — used by main() and selftest."""
    df = df.copy()
    # Defensive: a report with no matching deepdive JSON yields no 'killflags' column.
    # Treat absent hard-data as 0 kill-flags rather than KeyError-ing the whole rebuild.
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
    # TBD/unset rating in a fenced block -> fall through (no rating), not a crash.
    assert extract_rating("```rating\nrating: TBD\n```")["rating_score"] == 0, "fenced TBD -> unset"
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
    print("rank selftest PASS (extract_rating parsing + sink/ordering: AVOID & kill-flag>=2 sink)")


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
    ap.add_argument("--selftest", action="store_true",
                    help="Run self-test (rating parsing + sink/ranking logic) and exit")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    reports_dir = Path(args.input) if args.input else REPORTS

    # Slug-scoped pattern: prefer report_<slug>_*.md; fall back to all report_*.md
    if args.slug:
        scoped = glob.glob(str(reports_dir / f"report_{args.slug}_*.md"))
        report_files = scoped if scoped else glob.glob(str(reports_dir / "report_*.md"))
    else:
        report_files = glob.glob(str(reports_dir / "report_*.md"))

    rows = []
    for rp in sorted(report_files):
        ticker = Path(rp).stem.replace("report_", "")
        md = read_text_utf8(rp)
        rec = {"ticker": ticker}
        rec.update(extract_rating(md))
        rec.update(load_hard_data(ticker, reports_dir))
        rows.append(rec)
    df = pd.DataFrame(rows)

    # 排序:AVOID(rating_score=1)或 kill-flag>=2 沉底;其余按 评级分*置信度
    df = rank_frame(df)

    # Compute actual funnel numbers from the selected reports_dir
    report_all = glob.glob(str(reports_dir / "report_*.md"))
    deepdive_all = glob.glob(str(reports_dir / "deepdive_*.json"))
    universe_count, deepdive_count = len(report_all), len(deepdive_all)

    date = today()
    slug_label = f" [{args.slug}]" if args.slug else ""
    lines = [f"# 小盘深度调研排序{slug_label} — {date}", "",
             f"> 漏斗:{universe_count} 召回 → {deepdive_count} 小盘候选 → cheap pass 幸存 {len(df)} →",
             f"> {len(df)} 家微盘逐一 deep dive。AVOID/kill-flag≥2 一律沉底。**研究输出,非投资建议。**", "",
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

    out = reports_dir / "RANKING.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(df[["ticker", "rating", "confidence", "killflags", "sink", "combined"]].to_string())
    print(f"\n排序: {out}")


if __name__ == "__main__":
    main()
