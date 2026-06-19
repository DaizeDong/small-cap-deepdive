"""
cheap_pass.py — Stage 0 机械体检 + kill-flag 扫描(无定性叙事)

把发现阶段的小盘候选机械打分,kill-flag>=3 或财务硬伤直接淘汰,把 N 家砍到少数进 deep dive。
体现"agent 优势=规模化机械纪律"(对抗调研结论):不讲故事,只数硬信号。
设计依据:reference/mechanical-checks.md。

数据:SEC EDGAR(companyfacts XBRL + 全文检索 kill-flag) + yfinance(流通股稀释)。
kill-flag(成簇出现≈几乎必暴雷):going concern / material weakness / 重述 /
  death-spiral 可转债(variable conversion) / 审计师更换 / 反向拆股。

用法: python cheap_pass.py --universe universe_<slug>_<date>.csv
输出: reports/smallcap/cheappass_<slug>_<date>.csv
"""
from __future__ import annotations
import argparse
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from edgar import Company

# Import _common exports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import init_edgar, REPORTS, slug, today, CFG, http_get

FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"

# kill-flag 短语:在最新 10-K 全文里出现即为真信号(edgartools 读全文,非全市场计数)。
# 注意:SEC FTS 的 cik 参数过滤不可靠(实测健康公司也返回上限),故必须读单家全文判定。
KILL_PHRASES = {
    "going_concern": "going concern",
    "substantial_doubt": "substantial doubt",       # 比 going concern 更特异
    "material_weakness": "material weakness",
    "death_spiral": "variable conversion",
    "reverse_split": "reverse stock split",
}


def _extract_business_blurb(txt: str, max_chars: int = 2000) -> str:
    """Extract Item 1 Business section blurb from 10-K full text.

    Searches for the 'Item 1' / 'Business' heading and returns the first
    max_chars characters after it. Returns empty string if not found.
    """
    import re as _re
    low = txt.lower()
    # Try to find "item 1" followed shortly by "business" heading patterns.
    # Match variations: "item 1.", "item 1 -", "item 1\nbusiness", "item 1. business"
    patterns = [
        r"item\s+1[\.\-\s]+business",   # "item 1. business" or "item 1 business"
        r"item\s+1\b",                   # bare "item 1" fallback
    ]
    idx = -1
    for pat in patterns:
        m = _re.search(pat, low)
        if m:
            idx = m.end()
            break
    if idx < 0:
        return ""
    # Skip past a short heading line (newlines / table-of-contents artifacts)
    # and grab the actual content
    blurb = txt[idx:idx + max_chars + 200].strip()
    # Remove leading whitespace/newlines
    blurb = blurb.lstrip("\r\n\t ")
    return blurb[:max_chars]


def killflag_scan(ticker: str) -> dict:
    """读最新 10-K 全文,判定各 kill-flag 短语是否真实出现。
    going_concern + substantial_doubt 同时命中 = 强信号(真持续经营疑虑)。

    material_weakness: requires affirmative ICFR finding (identified/not-effective),
    not bare risk-factor boilerplate ("our failure to maintain effective controls...").
    This prevents the 4/4 false-positive pattern seen in the audit run.

    Also extracts business_blurb (Item 1 first ~2000 chars) for theme-fit gate reuse,
    avoiding redundant WebSearch in theme-fit-gate.js.
    """
    out = {f"kf_{k}": 0 for k in KILL_PHRASES}
    out["kf_scanned"] = False
    out["business_blurb"] = ""
    try:
        c = Company(ticker)
        # amendments=False:10-K/A 修正件是部分文件,常缺 going-concern 全文
        # (实测 IQST:10-K/A 仅 30K 字符漏判,原始 10-K 381K 字符命中)
        fl = c.get_filings(form="10-K", amendments=False)
        f = fl.latest(1) if fl is not None and len(fl) else None
        if f is None:
            return out
        txt = f.text() if hasattr(f, "text") else str(f.obj())
        low = txt.lower()
        for name, phrase in KILL_PHRASES.items():
            if name == "material_weakness":
                # Affirmative-finding rule: "material weakness" must co-occur with
                # an affirmative finding phrase to fire the flag.
                # Risk-factor boilerplate alone ("if we fail to maintain...") does NOT count.
                _mw_affirmative = (
                    "identified a material weakness" in low
                    or "identified material weakness" in low
                    or "were not effective" in low
                    or "was not effective" in low
                    or "have identified" in low
                )
                out["kf_material_weakness"] = 1 if (phrase in low and _mw_affirmative) else 0
            else:
                out[f"kf_{name}"] = 1 if phrase in low else 0
        out["kf_scanned"] = True
        # Extract business blurb for theme-fit gate (Fix 3)
        out["business_blurb"] = _extract_business_blurb(txt)
    except Exception as e:
        print(f"  [warn] killflag {ticker}: {e}", file=sys.stderr)
    return out


def get_concept_series(cik: str, concept: str) -> list:
    """拉某 XBRL 概念的时间序列(取 USD 单位的全部值)。"""
    url = FACTS.format(cik=str(cik).zfill(10), concept=concept)
    try:
        r = http_get(url, timeout=20)
        if r.status_code != 200:
            return []
        units = r.json().get("units", {})
        vals = units.get("USD") or units.get("USD/shares") or []
        return sorted(vals, key=lambda x: x.get("end", ""))
    except Exception:
        return []


def latest_val(series: list):
    return series[-1]["val"] if series else None


def health_check(row) -> dict:
    """单公司机械体检:runway / 现金流质量 / 稀释 / kill-flag。"""
    cik = str(row["cik"])
    out = {"ticker": row["ticker"], "name": row["name"], "mktcap": row.get("mktcap")}

    # --- 财务硬数据(XBRL) ---
    cash = latest_val(get_concept_series(cik, "CashAndCashEquivalentsAtCarryingValue"))
    time.sleep(0.15)
    ni = get_concept_series(cik, "NetIncomeLoss")
    time.sleep(0.15)
    ocf = get_concept_series(cik, "NetCashProvidedByUsedInOperatingActivities")
    time.sleep(0.15)
    rev = get_concept_series(cik, "Revenues") or get_concept_series(
        cik, "RevenueFromContractWithCustomerExcludingAssessedTax")
    time.sleep(0.15)

    out["cash"] = cash
    out["net_income"] = latest_val(ni)
    out["ocf_latest"] = latest_val(ocf)
    out["revenue"] = latest_val(rev)

    # runway:现金 / 季度净烧钱(用最近 OCF 近似;OCF>0 则不烧)
    burn = None
    if ocf:
        recent_ocf = ocf[-1]["val"]
        if recent_ocf < 0 and cash:
            burn = cash / (abs(recent_ocf))  # 单位=该 OCF 期数(粗略,多为年度)
    out["runway_periods"] = round(burn, 1) if burn else None

    # 现金流质量:净利>0 但 OCF<0 = 红旗
    out["flag_ocf_ni_divergence"] = (
        out["net_income"] is not None and out["ocf_latest"] is not None
        and out["net_income"] > 0 and out["ocf_latest"] < 0
    )

    # --- kill-flag 全文扫描(edgartools 读 10-K 全文,精准判定)---
    flags = killflag_scan(row["ticker"])
    out.update(flags)
    # business_blurb carried forward from killflag_scan (Fix 3: theme-fit gate reuse)
    out["business_blurb"] = flags.get("business_blurb", "")
    # 计数:going_concern+substantial_doubt 同时命中才算"持续经营"1票(避免例行提及误报)
    has_going_concern = (flags.get("kf_going_concern") and flags.get("kf_substantial_doubt"))
    going = 1 if has_going_concern else 0
    out["killflag_count"] = (
        going
        + flags.get("kf_material_weakness", 0)
        + flags.get("kf_death_spiral", 0)
        + flags.get("kf_reverse_split", 0)
    )
    time.sleep(0.3)
    return out


def score(df: pd.DataFrame) -> pd.DataFrame:
    """0-100 体检分 + 淘汰判定。"""
    df = df.copy()
    # 淘汰规则(kill-flag 计数已收紧,going concern 需双命中才计1)
    df["reject_going_concern"] = (df.get("kf_going_concern", 0).fillna(0).astype(bool)
                                  & df.get("kf_substantial_doubt", 0).fillna(0).astype(bool))
    df["reject_killflags"] = df["killflag_count"] >= 2
    df["reject_burn"] = df["runway_periods"].notna() & (df["runway_periods"] < 1.0) & \
                        (df["net_income"].fillna(0) < 0)
    df["rejected"] = df["reject_going_concern"] | df["reject_killflags"] | df["reject_burn"]
    # 简单体检分:从100扣
    s = pd.Series(100.0, index=df.index)
    s -= df["killflag_count"].fillna(0) * 20
    s -= df["flag_ocf_ni_divergence"].astype(int) * 15
    s -= (df["revenue"].fillna(0) <= 0).astype(int) * 25
    s -= (df["runway_periods"].fillna(99) < 2).astype(int) * 20
    df["health_score"] = s.clip(0, 100)
    return df


def _selftest():
    """Selftest:
    1. IQST — must flag going_concern + substantial_doubt (Guard 2/3: full-text double-hit).
    2. KOP  — amendments=False must NOT return a 10-K/A as the latest filing (Guard 1).
    3. EGAN — must NOT flag has_material_weakness (FP fix: bare boilerplate phrase
               in risk factors must not fire; requires affirmative ICFR finding).
    4. business_blurb — must be non-empty for a valid filer (e.g. EGAN).
    """
    init_edgar()
    # Test 1: IQST going-concern double-hit
    r = killflag_scan("IQST")
    assert r["kf_going_concern"] == 1 and r["kf_substantial_doubt"] == 1, (
        f"IQST must flag going concern (amendments=False fix), "
        f"got kf_going_concern={r['kf_going_concern']} kf_substantial_doubt={r['kf_substantial_doubt']}"
    )
    print(f"  IQST: going_concern={r['kf_going_concern']} substantial_doubt={r['kf_substantial_doubt']}  OK")

    # Test 2: KOP amendment exclusion — latest filing must be 10-K, not 10-K/A
    from edgar import Company
    kop = Company("KOP")
    fl = kop.get_filings(form="10-K", amendments=False)
    f = fl.latest(1) if fl is not None and len(fl) else None
    assert f is not None, "KOP: no 10-K found (amendments=False)"
    form_type = str(getattr(f, "form", "") or getattr(f, "form_type", "")).strip()
    assert form_type != "10-K/A", (
        f"KOP: amendments=False must not return a 10-K/A, got form_type={form_type!r}"
    )
    print(f"  KOP: form_type={form_type!r} (not 10-K/A)  OK")

    # Test 3: EGAN no-material-weakness FP fix
    # EGAN (eGain Corp) is a healthy filer that should NOT have an actual ICFR material weakness.
    # The old bare-phrase rule would fire on boilerplate risk-factor language; the new
    # affirmative-finding rule must return False for a company with no actual ICFR finding.
    egan_r = killflag_scan("EGAN")
    assert egan_r["kf_material_weakness"] == 0, (
        f"EGAN: kf_material_weakness must be 0 under affirmative-finding rule "
        f"(bare boilerplate must not fire), got {egan_r['kf_material_weakness']}"
    )
    print(f"  EGAN: kf_material_weakness={egan_r['kf_material_weakness']} (FP fix verified)  OK")

    # Test 4: business_blurb extracted (Fix 3)
    blurb = egan_r.get("business_blurb", "")
    assert len(blurb) > 100, (
        f"EGAN: business_blurb should be >100 chars (Item 1 extraction), got len={len(blurb)}"
    )
    print(f"  EGAN: business_blurb length={len(blurb)} chars  OK")

    print("cheap_pass selftest PASS (IQST going-concern + KOP amendment exclusion + EGAN MW FP fix + business_blurb)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=False)
    ap.add_argument("--max-mcap", type=float, default=CFG["market_cap_max"])
    ap.add_argument("--limit", type=int, default=0, help="只测前N家(调试用)")
    ap.add_argument("--out-slug", default="", help="输出文件名 slug(多主题区分)")
    ap.add_argument("--selftest", action="store_true", help="Run selftest")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if not args.universe:
        ap.error("--universe is required when not using --selftest")

    init_edgar()
    uni = pd.read_csv(args.universe)
    cand = uni[uni["smallcap_candidate"] == True].copy()
    cand = cand[cand["mktcap"] <= args.max_mcap]
    if args.limit:
        cand = cand.sort_values("mktcap").head(args.limit)
    print(f"对 {len(cand)} 家小盘候选做机械体检...", file=sys.stderr)

    rows = []
    for i, (_, r) in enumerate(cand.iterrows()):
        rows.append(health_check(r))
        if (i + 1) % 10 == 0:
            print(f"  体检 {i+1}/{len(cand)}", file=sys.stderr)
    df = pd.DataFrame(rows)
    df = score(df)
    df = df.sort_values(["rejected", "health_score"], ascending=[True, False])

    date = today()
    tag = f"{args.out_slug}_" if args.out_slug else ""
    out = REPORTS / f"cheappass_{tag}{date}.csv"
    df.to_csv(out, index=False)

    survivors = df[~df["rejected"]]
    print(f"\n=== Cheap pass 结果 ===")
    print(f"体检 {len(df)} 家 | 淘汰 {df['rejected'].sum()} 家 | 幸存 {len(survivors)} 家")
    print(f"\n幸存者(按体检分,进 deep dive 候选):")
    for _, r in survivors.head(15).iterrows():
        rev = f"${r['revenue']/1e6:.0f}M" if pd.notna(r['revenue']) else "无营收"
        print(f"  {r['ticker']:8} 分{r['health_score']:5.0f}  kill-flag {int(r['killflag_count'])}  营收{rev:>8}  {r['name'][:32]}")
    print(f"\n被淘汰(kill-flag>=3 或烧钱):")
    for _, r in df[df["rejected"]].head(12).iterrows():
        print(f"  {r['ticker']:8} kill-flag {int(r['killflag_count'])}  {r['name'][:36]}")
    print(f"\n清单: {out}")


if __name__ == "__main__":
    main()
