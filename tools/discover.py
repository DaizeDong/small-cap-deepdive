"""
discover.py — 主题驱动的小盘候选公司发现
SEC EDGAR 全文检索(实测端点) → 提取 ticker/CIK/SIC → yfinance 市值+流动性过滤 → 去噪。
设计依据:reference/discovery-engine.md。

用法:
    python discover.py --theme "AI agents" --max-mcap 2e9
    python discover.py --theme "AI agents,agentic,AI agent" --forms 10-K,10-Q
输出:reports/smallcap/universe_<theme>_<date>.csv
"""
from __future__ import annotations
import argparse
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Import from _common
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UA, REPORTS, slug as _slug, http_get, today, CFG

FTS = "https://efts.sec.gov/LATEST/search-index"

# 解析 display_names: "Apple Inc.  (AAPL)  (CIK 0000320193)"
NAME_RE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*\(CIK\s*(\d+)\)")


def fts_search(phrase: str, forms: str, startdt: str, enddt: str,
               max_pages: int = 10) -> list[dict]:
    """SEC 全文检索精确短语。翻页(每页100)。返回去重 hit 列表。"""
    out, seen = [], set()
    for page in range(max_pages):
        q = urllib.parse.quote(f'"{phrase}"')
        url = f"{FTS}?q={q}&forms={forms}&startdt={startdt}&enddt={enddt}&from={page*100}"
        d = None
        try:
            r = http_get(url, timeout=25)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"  [warn] FTS page {page} ({phrase}): {e}", file=sys.stderr)
        if d is None:
            break
        hits = d.get("hits", {}).get("hits", [])
        if not hits:
            break
        total = d["hits"]["total"]["value"]
        for h in hits:
            s = h["_source"]
            for dn in s.get("display_names", []):
                m = NAME_RE.match(dn)
                if not m:
                    continue
                name, tickers, cik = m.group(1), m.group(2), m.group(3)
                tick = tickers.split(",")[0].strip()
                key = cik
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": name.strip(), "ticker": tick, "cik": cik,
                            "sic": (s.get("sics") or [""])[0],
                            "location": (s.get("biz_locations") or [""])[0],
                            "form": s.get("form"), "file_date": s.get("file_date"),
                            "matched_phrase": phrase})
        time.sleep(1.5)  # SEC 限速
        if (page + 1) * 100 >= total:
            break
    return out


def enrich_marketcap(df: pd.DataFrame) -> pd.DataFrame:
    """逐 ticker 用 yfinance 补市值+流动性(候选集已小,可逐个)。"""
    import yfinance as yf
    rows = []
    for i, t in enumerate(df["ticker"]):
        rec = {"mktcap": None, "avg_dollar_vol": None, "price": None, "exch": None}
        try:
            info = yf.Ticker(t).info
            rec["mktcap"] = info.get("marketCap")
            rec["price"] = info.get("currentPrice") or info.get("regularMarketPrice")
            rec["exch"] = info.get("exchange")
            # 近30日日均成交额
            h = yf.Ticker(t).history(period="1mo")
            if not h.empty:
                rec["avg_dollar_vol"] = float((h["Close"] * h["Volume"]).mean())
        except Exception:
            pass
        rows.append(rec)
        time.sleep(0.25)
        if (i + 1) % 20 == 0:
            print(f"  marketcap {i+1}/{len(df)}", file=sys.stderr)
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# SPAC/空壳启发式
SPAC_PAT = re.compile(r"acquisition corp|blank check|capital corp|holdings? (?:corp|ltd)$", re.I)


def apply_filters(df: pd.DataFrame, max_mcap: float, min_dollar_vol: float) -> pd.DataFrame:
    df = df.copy()
    df["flag_no_mktcap"] = df["mktcap"].isna()
    df["flag_too_big"] = df["mktcap"] > max_mcap
    df["flag_spac"] = df["name"].str.contains(SPAC_PAT, na=False) | (df["sic"] == "6770")
    df["flag_illiquid"] = df["avg_dollar_vol"].fillna(0) < min_dollar_vol
    df["flag_no_price"] = df["price"].isna()
    df["smallcap_candidate"] = (
        df["mktcap"].notna() & (df["mktcap"] <= max_mcap) & (df["mktcap"] > 0)
        & ~df["flag_spac"] & ~df["flag_illiquid"] & df["price"].notna()
    )
    return df


def _two_years_ago() -> str:
    """Return ISO date string for today minus 2 years (dynamic FTS recall window)."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", required=True, help="逗号分隔的主题短语")
    ap.add_argument("--forms", default="10-K,10-Q")
    ap.add_argument("--startdt", default=_two_years_ago(),
                    help="FTS 起始日期 (default: today minus 2 years)")
    ap.add_argument("--enddt", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--max-mcap", type=float, default=CFG["market_cap_max"], help="小盘上限,默认 $2B")
    ap.add_argument("--min-dollar-vol", type=float, default=CFG["min_dollar_vol"], help="日均成交额下限")
    ap.add_argument("--max-pages", type=int, default=10,
                    help="每短语最大翻页数 (default: 10, 每页100条)")
    ap.add_argument("--out-slug", default="", help="输出文件名 slug(多主题区分用)")
    args = ap.parse_args()

    phrases = [p.strip() for p in args.theme.split(",") if p.strip()]
    print(f"[1/3] SEC FTS 召回 (主题: {phrases}, forms: {args.forms})...", file=sys.stderr)
    all_hits = []
    for j, ph in enumerate(phrases):
        if j > 0:
            time.sleep(3)  # 短语间隔,避免 SEC 限流
        hits = fts_search(ph, args.forms, args.startdt, args.enddt, args.max_pages)
        print(f"  '{ph}': {len(hits)} 家", file=sys.stderr)
        all_hits += hits
    if not all_hits:
        print(f"  [warn] 主题 '{phrases}' SEC FTS 零命中 — 关键词可能过严(需更自然短语)", file=sys.stderr)
        date = today()
        slug = args.out_slug or _slug(phrases[0])
        # 写空 universe 占位,避免后续崩
        pd.DataFrame(columns=["ticker", "cik", "name", "mktcap", "smallcap_candidate"]
                     ).to_csv(REPORTS / f"universe_{slug}_{date}.csv", index=False)
        print(f"\n=== 发现结果 ===\n总召回 0 家 — 零命中,已写空占位", file=sys.stderr)
        return
    df = pd.DataFrame(all_hits).drop_duplicates(subset="cik").reset_index(drop=True)
    print(f"  去重后 {len(df)} 家", file=sys.stderr)

    print(f"[2/3] yfinance 补市值+流动性...", file=sys.stderr)
    df = enrich_marketcap(df)

    print(f"[3/3] 过滤去噪...", file=sys.stderr)
    df = apply_filters(df, args.max_mcap, args.min_dollar_vol)

    date = today()
    slug = args.out_slug or _slug(phrases[0])
    out = REPORTS / f"universe_{slug}_{date}.csv"
    df.sort_values("mktcap", na_position="last").to_csv(out, index=False)

    cand = df[df["smallcap_candidate"]]
    print(f"\n=== 发现结果 ===")
    print(f"总召回 {len(df)} 家 | 小盘候选 {len(cand)} 家 (市值<${args.max_mcap/1e9:.1f}B, 已剔SPAC/低流动性)")
    print(f"\n小盘候选 (按市值):")
    show = cand.sort_values("mktcap")[["ticker", "name", "mktcap", "avg_dollar_vol", "sic"]]
    for _, r in show.iterrows():
        mc = f"${r['mktcap']/1e6:.0f}M" if pd.notna(r['mktcap']) else "—"
        dv = f"${r['avg_dollar_vol']/1e6:.1f}M/d" if pd.notna(r['avg_dollar_vol']) else "—"
        print(f"  {r['ticker']:8} {mc:>8} {dv:>10}  {r['name'][:40]}")
    print(f"\n清单: {out}")


if __name__ == "__main__":
    main()
