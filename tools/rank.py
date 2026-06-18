"""
rank.py — 聚合 deep dive 报告,产出主题级排序

读 reports/smallcap/report_*.md,提取评级/置信度,结合 cheap pass 体检分 +
deepdive JSON 的硬数据,产出排序表。AVOID/kill-flag>=2 一律沉底(不靠高分捞回)。

用法: python tools/rank.py
输出: reports/smallcap/RANKING.md
"""
from __future__ import annotations
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


def extract_rating(md: str) -> dict:
    """从报告文本提取评级/置信度(容错多种写法)。"""
    out = {"rating": None, "rating_score": 0, "confidence": None}
    # 评级:【买入/观察/避开】 或 评级: 买入
    m = re.search(r"评级[:：]\s*[【\[]?\s*(买入|观察|避开|buy|watch|hold|avoid|sell)",
                  md, re.I)
    if m:
        r = m.group(1).lower()
        out["rating"] = m.group(1)
        out["rating_score"] = RATING_MAP.get(r, 0)
    # 置信度
    mc = re.search(r"置信度[:：]\s*(\d+)\s*%", md)
    if mc:
        out["confidence"] = int(mc.group(1))
    return out


def load_hard_data(ticker: str) -> dict:
    files = glob.glob(str(REPORTS / f"deepdive_{ticker}_*.json"))
    if not files:
        return {}
    d = json.load(open(sorted(files)[-1], encoding="utf-8"))
    if isinstance(d, list):
        return {}
    der = d.get("derived", {})
    tk = d.get("tenk", {})
    ins = d.get("insider", {})
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


def main():
    reports = glob.glob(str(REPORTS / "report_*.md"))
    rows = []
    for rp in sorted(reports):
        ticker = Path(rp).stem.replace("report_", "")
        md = Path(rp).read_text(encoding="utf-8")
        rec = {"ticker": ticker}
        rec.update(extract_rating(md))
        rec.update(load_hard_data(ticker))
        rows.append(rec)
    df = pd.DataFrame(rows)

    # 排序:AVOID(rating_score=1)或 kill-flag>=2 沉底;其余按 评级分*置信度
    df["sink"] = (df["rating_score"] <= 1) | (df["killflags"].fillna(0) >= 2)
    df["combined"] = df["rating_score"] * (df["confidence"].fillna(50) / 100)
    df = df.sort_values(["sink", "combined"], ascending=[True, False])

    # Compute actual funnel numbers
    universe_count, deepdive_count = compute_funnel_stats()

    date = today()
    lines = [f"# AI agent 主题 — 小盘深度调研排序 — {date}", "",
             f"> 主题=AI agent/agentic。漏斗:{universe_count} 召回 → {deepdive_count} 小盘候选 → cheap pass 幸存 {len(df)} →",
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

    out = REPORTS / "RANKING.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(df[["ticker", "rating", "confidence", "killflags", "sink", "combined"]].to_string())
    print(f"\n排序: {out}")


if __name__ == "__main__":
    main()
