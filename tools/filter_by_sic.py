"""
filter_by_sic.py — 用 SIC 行业码过滤主题误召回(关键修复)

问题:单关键词 SEC 全文检索过度召回 —— "refractory"=难治性癌症扫进全部biotech,
"railcar"扫进任何铁路运货的公司(Build-A-Bear/ethanol/potash)。
修复:每主题只保留行业 SIC 码相关的公司。从已有 universe csv 重新筛幸存者,
不重跑 discovery(数据已有)。

排除的医药/医疗 SIC:2833/2834/2835/2836(药)、3826/3841/3845(医械)、8000s(医疗服务)。
"""
from __future__ import annotations
import argparse
import glob
import json
import re
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CFG, REPORTS, slug

MICRO_CAP = 5e8

# 策略改为粗排除:不做窄白名单(易误剔真标的如 NL/VHI=2810),
# 而是排除明显与工业主题无关的大类(医药/医疗/软件/金融/零售/餐饮),
# 其余全部保留交给 LLM 精判主题契合。
THEME_SIC = {}  # 不再用窄白名单

# 硬排除的 SIC 前缀:医药/医疗器械/医疗服务/软件/金融/保险/房产/零售/餐饮/玩具
HARD_EXCLUDE = CFG["sic_hard_exclude"]


def sic_ok(sic: str, hard_exclude: list[str]) -> bool:
    """粗排除:只剔明显无关大类(医药/软件/金融/零售),其余保留交 LLM 精判。
    SIC 缺失时保留(让 LLM 判),不一刀切剔除。"""
    sic = str(sic).split(".")[0].strip()
    if not sic or sic == "nan":
        return True  # 缺 SIC 不剔,交 LLM 判
    # 按长到短匹配硬排除前缀
    for ex in sorted(hard_exclude, key=len, reverse=True):
        if sic.startswith(ex):
            return False
    return True


def _selftest():
    he = CFG["sic_hard_exclude"]
    assert sic_ok("2810", he) is True, "NL/VHI 2810 must NOT be excluded"
    assert sic_ok("2834", he) is False, "pharma 2834 must be excluded"
    assert sic_ok("8071", he) is False, "medical lab 8071 must be excluded"
    assert sic_ok("3743", he) is True, "railcar 3743 must be kept"
    assert sic_ok("", he) is True, "missing sic must be kept (defer to LLM)"
    print("filter_by_sic selftest PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true", help="Run selftest and exit")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return

    THEMES = json.load(open(REPORTS / "themes.json", encoding="utf-8"))["selected"]
    survivors = []
    summary = []
    for t in THEMES:
        s = slug(t["name"])
        allowed = THEME_SIC.get(s, [])
        cp = sorted(glob.glob(str(REPORTS / f"cheappass_{s}_*.csv")))
        uni = sorted(glob.glob(str(REPORTS / f"universe_{s}_*.csv")))
        if not cp or not uni:
            continue
        cdf = pd.read_csv(cp[-1])
        udf = pd.read_csv(uni[-1])[["ticker", "cik", "sic", "mktcap"]]
        cdf = cdf.merge(udf, on="ticker", how="left", suffixes=("", "_u"))
        surv = cdf[~cdf["rejected"]]
        micro = surv[surv["mktcap"].fillna(0) < MICRO_CAP].copy()
        before = len(micro)
        micro["sic_ok"] = micro["sic"].apply(lambda x: sic_ok(x, HARD_EXCLUDE))
        clean = micro[micro["sic_ok"]]
        summary.append((t["name"][:36], t["horizon"], before, len(clean),
                        list(clean["ticker"])))
        for _, r in clean.iterrows():
            cik = r.get("cik")
            if pd.isna(cik):
                continue
            survivors.append({
                "ticker": r["ticker"], "cik": str(int(cik)),
                "name": r.get("name", ""), "theme": t["name"], "horizon": t["horizon"],
                "theme_slug": s, "sic": str(r.get("sic")).split(".")[0],
                "mktcap": float(r["mktcap"]) if pd.notna(r.get("mktcap")) else None,
                "health_score": float(r["health_score"]) if pd.notna(r.get("health_score")) else None,
                "killflag_count": int(r["killflag_count"]) if pd.notna(r.get("killflag_count")) else None,
            })
    out = REPORTS / "survivors_sic_clean.json"
    json.dump(survivors, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("SIC 过滤结果(主题 | 横向 | SIC前→后):")
    for name, hz, b, a, tks in summary:
        print(f"  {name:38}[{hz[:9]:9}] {b:2}→{a:2}  {' '.join(tks)}")
    print(f"\n清洗后总幸存者: {len(survivors)} (原 49)")
    print(f"清单: {out}")


if __name__ == "__main__":
    main()
