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
from _common import UA, REPORTS, slug as _slug, http_get, today, CFG, resolve_mktcap, band_for
# P8 SIC reverse-recall (the recall FLOOR): enumerate a theme's dedicated SIC and UNION
# with FTS so a true small-cap FTS missed (low keyword density / top-1000 cap) is recalled.
from filter_by_sic import theme_sics, sic_reverse_recall, union_recall

FTS = "https://efts.sec.gov/LATEST/search-index"

# CIK -> ticker resolution for SIC-only rows (browse-edgar gives no ticker). Lazy-loaded.
_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_CIK_TICKER_CACHE: dict[str, str] | None = None


def _cik_to_ticker(cik: str) -> str:
    """Resolve a CIK to its primary ticker via SEC company_tickers.json (cached).

    SIC-reverse rows come from browse-edgar, which has no ticker column; enrich_marketcap
    needs one. Returns "" if the CIK has no listed ticker (delisted / non-listed filer) —
    those flow through as band='unknown' like any other ticker-less row.
    """
    global _CIK_TICKER_CACHE
    if _CIK_TICKER_CACHE is None:
        _CIK_TICKER_CACHE = {}
        try:
            r = http_get(_COMPANY_TICKERS, timeout=25)
            for v in r.json().values():
                _CIK_TICKER_CACHE[str(v["cik_str"])] = v["ticker"]
        except Exception as e:  # pragma: no cover - network guard
            print(f"  [warn] company_tickers load failed: {e}", file=sys.stderr)
    return _CIK_TICKER_CACHE.get(str(cik).strip().lstrip("0"), "")

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


def merge_sic_reverse(fts_hits: list[dict], theme: str, forms: str,
                      resolve_ticker=_cik_to_ticker, fetch=None) -> list[dict]:
    """P8: UNION the FTS recall with the theme's dedicated-SIC enumeration (recall floor).

    No-op (returns fts_hits unchanged, all tagged recall_channel='fts') when the theme has
    no dedicated SIC — opt-in by construction. Otherwise enumerates the dedicated SIC(s),
    unions on CIK (filter_by_sic.union_recall tags fts/sic_reverse/both), and back-fills a
    ticker for the SIC-only rows so enrich_marketcap can resolve their market cap. SIC-only
    rows are stamped form/file_date='' and matched_phrase='[sic_reverse]' for provenance.
    fetch is injectable for offline tests.
    """
    sics = theme_sics(theme)
    if not sics:
        # Tag the channel even on the no-floor path so the column is always present.
        return [dict(h, recall_channel="fts") for h in fts_hits]
    sic_rows = sic_reverse_recall(theme, forms=forms, fetch=fetch)
    print(f"  [P8] SIC reverse-recall (dedicated SIC {sics}): {len(sic_rows)} registrants",
          file=sys.stderr)
    merged = union_recall(fts_hits, sic_rows)
    for r in merged:
        if r.get("recall_channel") == "sic_reverse":
            if not r.get("ticker"):
                r["ticker"] = resolve_ticker(r["cik"])
            r.setdefault("location", "")
            r.setdefault("form", "")
            r.setdefault("file_date", "")
            r.setdefault("matched_phrase", "[sic_reverse]")
    n_sic_only = sum(1 for r in merged if r.get("recall_channel") == "sic_reverse")
    n_both = sum(1 for r in merged if r.get("recall_channel") == "both")
    print(f"  [P8] union: {len(merged)} total ({n_sic_only} sic_reverse-only recovered, "
          f"{n_both} in both channels)", file=sys.stderr)
    return merged


def enrich_marketcap(df: pd.DataFrame) -> pd.DataFrame:
    """逐 ticker 补市值+流动性(候选集已小,可逐个)。

    P5: market cap is no longer yfinance-only. Per row we try the fallback chain
    (resolve_mktcap): yfinance marketCap -> SEC companyfacts shares-outstanding x
    last price. mktcap_source records which leg resolved it ("yfinance" /
    "sec_shares_x_price" / "unresolved"). A row that stays unresolved is NOT
    dropped here — apply_filters tags it band="unknown" and flows it through.
    """
    import yfinance as yf
    ciks = df["cik"].tolist() if "cik" in df.columns else [None] * len(df)
    rows = []
    for i, t in enumerate(df["ticker"]):
        rec = {"mktcap": None, "avg_dollar_vol": None, "price": None,
               "exch": None, "mktcap_source": "unresolved"}
        yf_mktcap = None
        # P12: split .info and .history into INDEPENDENT try blocks. yfinance's
        # .info call is the fragile leg (SJW/HI/MRC: it raises or returns {} for
        # real names), and the old single try aborted BOTH legs together — losing
        # price/volume too, which then (a) starved resolve_mktcap of a price for the
        # SEC shares x price reconstruction and (b) tripped flag_illiquid. Isolating
        # them means an .info failure no longer silently drops a real small-cap.
        try:
            info = yf.Ticker(t).info
            yf_mktcap = info.get("marketCap")
            rec["price"] = info.get("currentPrice") or info.get("regularMarketPrice")
            rec["exch"] = info.get("exchange")
        except Exception:
            pass
        try:
            # 近30日日均成交额
            h = yf.Ticker(t).history(period="1mo")
            if not h.empty:
                rec["avg_dollar_vol"] = float((h["Close"] * h["Volume"]).mean())
                # P12: derive a price from the history close when .info gave none —
                # this is the price that lets resolve_mktcap reconstruct mktcap from
                # SEC shares for a yfinance-NaN name BEFORE any size-exclusion.
                if rec["price"] is None or not (rec["price"] > 0):
                    last_close = float(h["Close"].dropna().iloc[-1])
                    if last_close > 0:
                        rec["price"] = last_close
        except Exception:
            pass
        # Fallback chain: yfinance -> SEC shares x price. Keeps mktcap when yfinance
        # is null but a price + SEC shares-outstanding exist (common for small/foreign).
        mc, src = resolve_mktcap(yf_mktcap, rec["price"], ciks[i] if i < len(ciks) else None)
        rec["mktcap"] = mc
        rec["mktcap_source"] = src
        rows.append(rec)
        time.sleep(0.25)
        if (i + 1) % 20 == 0:
            print(f"  marketcap {i+1}/{len(df)}", file=sys.stderr)
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# SPAC/空壳启发式
SPAC_PAT = re.compile(r"acquisition corp|blank check|capital corp|holdings? (?:corp|ltd)$", re.I)


def apply_filters(df: pd.DataFrame, max_mcap: float, min_dollar_vol: float,
                  watch_band_max: float | None = None) -> pd.DataFrame:
    """Apply market-cap + liquidity filters.

    Band tagging (Phase 4 dual-band + P5 unknown flow-through; band_for is the SSOT
    shared with discover_events.py):
      band="deep"    — mktcap < max_mcap (standard small-cap; full rubric downstream)
      band="watch"   — max_mcap <= mktcap < watch_band_max (surfaced separately;
                       theme-fit + one-line note, NOT expensive deep-dive)
      band="large"   — mktcap >= watch_band_max (out of scope; flagged flag_too_big,
                       flowed through so downstream guards/gates can see it, not dropped)
      band="unknown" — mktcap missing/unresolvable after the fallback chain. P5:
                       previously this was band=None and the row was DROPPED
                       (flag_no_mktcap). yfinance-null was silently discarding
                       91-100% of some themes before any gate. Unknown-band rows now
                       FLOW THROUGH (smallcap_candidate=True), mirroring the event
                       path (discover_events.py:99-120) which keeps null as "unknown".

    watch_band_max: from config key watch_band_max (default $5B).
    smallcap_candidate is True for deep/watch/unknown bands (anything not "large"),
    subject to the non-mktcap gates (not SPAC, not illiquid). downstream
    run_theme/deepdive must check band before running the full rubric.
    """
    if watch_band_max is None:
        watch_band_max = CFG.get("watch_band_max", 5_000_000_000)
    df = df.copy()
    df["flag_no_mktcap"] = df["mktcap"].isna()
    df["flag_too_big"] = df["mktcap"] > watch_band_max
    df["flag_spac"] = df["name"].str.contains(SPAC_PAT, na=False) | (df["sic"] == "6770")
    df["flag_illiquid"] = df["avg_dollar_vol"].fillna(0) < min_dollar_vol
    df["flag_no_price"] = df["price"].isna()
    # Band via shared SSOT (null/zero -> "unknown"; >=watch_band_max -> "large").
    df["band"] = df["mktcap"].apply(lambda mc: band_for(mc, max_mcap, watch_band_max))
    # smallcap_candidate: NOT too big (deep/watch/unknown), not SPAC, not illiquid.
    # P5: unknown-band (null mktcap) rows are kept — flow through instead of drop.
    # The illiquidity gate still applies; a no-price row with no volume is illiquid
    # and falls out there, not via a blanket mktcap drop.
    df["smallcap_candidate"] = (
        (df["band"] != "large") & ~df["flag_spac"] & ~df["flag_illiquid"]
    )
    return df


def _two_years_ago() -> str:
    """Return ISO date string for today minus 2 years (dynamic FTS recall window)."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%d")


def _selftest() -> None:
    """P5: null-mktcap rows must become band='unknown' and FLOW THROUGH (not drop)."""
    max_mcap = 2_000_000_000
    watch_max = 5_000_000_000
    df = pd.DataFrame([
        # deep small-cap with full data
        {"name": "Deep Co", "ticker": "DEEP", "cik": "1", "sic": "2810",
         "mktcap": 8e8, "price": 10.0, "avg_dollar_vol": 5e6},
        # watch band
        {"name": "Watch Co", "ticker": "WTCH", "cik": "2", "sic": "2810",
         "mktcap": 3e9, "price": 20.0, "avg_dollar_vol": 5e6},
        # large / out of scope
        {"name": "Big Co", "ticker": "BIG", "cik": "3", "sic": "2810",
         "mktcap": 9e9, "price": 50.0, "avg_dollar_vol": 5e6},
        # null mktcap but liquid + has price — the P5 case that used to be DROPPED
        {"name": "Unknown Co", "ticker": "UNK", "cik": "4", "sic": "2810",
         "mktcap": None, "price": 12.0, "avg_dollar_vol": 5e6},
        # null mktcap AND no price/volume — still flows as 'unknown' band, but is illiquid
        {"name": "Dark Co", "ticker": "DARK", "cik": "5", "sic": "2810",
         "mktcap": None, "price": None, "avg_dollar_vol": 0.0},
        # P12: yfinance returned NaN, but enrich_marketcap reconstructed mktcap via SEC
        # shares x price (mktcap_source='sec_shares_x_price'). The resolved in-band cap must
        # land 'deep' and stay a candidate — NOT be size-excluded for being yfinance-NaN.
        # This is the SJW/HI/MRC case: real name, fragile yfinance, recoverable via SEC.
        {"name": "SJW-like", "ticker": "SJWX", "cik": "6", "sic": "4941",
         "mktcap": 1.5e9, "price": 50.0, "avg_dollar_vol": 5e6,
         "mktcap_source": "sec_shares_x_price"},
    ])
    out = apply_filters(df, max_mcap, min_dollar_vol=1e6, watch_band_max=watch_max)

    # band assignments
    bands = dict(zip(out["ticker"], out["band"]))
    assert bands["DEEP"] == "deep", f"DEEP band={bands['DEEP']}"
    assert bands["WTCH"] == "watch", f"WTCH band={bands['WTCH']}"
    assert bands["BIG"] == "large", f"BIG band={bands['BIG']}"
    # CORE P5 ASSERTION: null mktcap -> band='unknown', NOT None (which meant dropped)
    assert bands["UNK"] == "unknown", f"null-mktcap UNK must band='unknown', got {bands['UNK']}"
    assert bands["DARK"] == "unknown", f"null-mktcap DARK must band='unknown', got {bands['DARK']}"
    assert out["band"].notna().all(), "no band may be None/NaN (None==dropped, the old bug)"

    # flow-through: the unknown-band row with price+volume is a live candidate, NOT dropped
    cand = dict(zip(out["ticker"], out["smallcap_candidate"]))
    assert cand["UNK"] is True or cand["UNK"] == True, (
        "null-mktcap but liquid row must remain smallcap_candidate=True (flow through, not drop)"
    )
    assert cand["DEEP"] == True and cand["WTCH"] == True, "deep/watch must stay candidates"
    # large is out of scope (not a candidate) but still present in the frame (flagged, not dropped)
    assert cand["BIG"] == False, "large-band must not be a smallcap_candidate"
    assert "BIG" in bands, "large-band row must remain in the frame, not be dropped"
    # genuinely illiquid unknown row falls out via the illiquidity gate, not a mktcap drop
    assert cand["DARK"] == False, "DARK is illiquid -> not a candidate (via liquidity gate, not mktcap)"

    # P12: a SEC-shares x price reconstructed in-band mktcap must band 'deep' and stay a
    # candidate — the yfinance-NaN name (SJW/HI/MRC) is recovered, NOT size-excluded.
    assert bands["SJWX"] == "deep", (
        f"P12: SEC-reconstructed $1.5B mktcap must band 'deep', got {bands['SJWX']}")
    assert cand["SJWX"] == True, (
        "P12: a real name with yfinance NaN but resolvable SEC shares x price must remain "
        "smallcap_candidate=True (not size-excluded) — the SJW fix")

    # -----------------------------------------------------------------------
    # P8 SIC reverse-recall wiring (merge_sic_reverse). Offline: mock fetch + mock
    # ticker resolver. Asserts the union enumerates the dedicated SIC and merges with
    # the FTS recall WITHOUT dupes, tagging recall_channel and back-filling tickers.
    # -----------------------------------------------------------------------
    class _Resp:
        def __init__(self, text): self.text = text
    # browse-edgar fixture for SIC 7200: SCI (also an FTS hit) + CSV (FTS blind spot).
    sic_html = (
        '<a href="x&amp;CIK=0000089089&amp;owner=include&amp;count=100&amp;type=10-K">0000089089</a></td>'
        '<td scope="row">SERVICE CORP INTERNATIONAL</td>'
        '<a href="x&amp;CIK=0001016281&amp;owner=include&amp;count=100&amp;type=10-K">0001016281</a></td>'
        '<td scope="row">CARRIAGE SERVICES INC</td>'
    )
    def _mock_fetch(url, params=None, timeout=25):
        return _Resp(sic_html if (params or {}).get("start", 0) == 0 else "")
    def _mock_ticker(cik):
        return {"1016281": "CSV", "89089": "SCI"}.get(str(cik).strip().lstrip("0"), "")

    fts_hits = [
        {"name": "SERVICE CORP INTERNATIONAL", "ticker": "SCI", "cik": "89089",
         "sic": "7200", "matched_phrase": "deathcare"},
        {"name": "FTS Only Co", "ticker": "ZZZZ", "cik": "999999",
         "sic": "7200", "matched_phrase": "cremation"},
    ]
    # Mapped theme -> floor kicks in, union enumerates the SIC and merges.
    merged = merge_sic_reverse(fts_hits, "deathcare", "10-K",
                               resolve_ticker=_mock_ticker, fetch=_mock_fetch)
    by_cik = {r["cik"]: r for r in merged}
    assert len(merged) == 3, f"P8 union must dedupe to 3 rows (SCI once), got {len(merged)}"
    assert set(by_cik) == {"89089", "999999", "1016281"}, f"P8 union CIK set: {set(by_cik)}"
    assert by_cik["89089"]["recall_channel"] == "both", "SCI in FTS+SIC must tag 'both'"
    assert by_cik["999999"]["recall_channel"] == "fts", "FTS-only must tag 'fts'"
    assert by_cik["1016281"]["recall_channel"] == "sic_reverse", (
        "CSV is the FTS blind spot recovered by the SIC floor -> 'sic_reverse'"
    )
    assert by_cik["1016281"]["ticker"] == "CSV", "SIC-only row must back-fill ticker for enrichment"
    assert by_cik["1016281"]["matched_phrase"] == "[sic_reverse]", "SIC-only provenance stamp"
    # Every row tagged so the DataFrame always has the recall_channel column.
    assert all("recall_channel" in r for r in merged), "every merged row must carry recall_channel"
    # No-op path: unmapped theme returns FTS rows tagged 'fts', no enumeration.
    plain = merge_sic_reverse(fts_hits, "ai agents", "10-K",
                              resolve_ticker=_mock_ticker, fetch=_mock_fetch)
    assert len(plain) == 2 and all(r["recall_channel"] == "fts" for r in plain), (
        "unmapped theme -> FTS-only, all tagged 'fts' (opt-in no-op)"
    )
    assert all("recall_channel" not in r for r in fts_hits), "merge must NOT mutate fts_hits input"

    print("discover selftest PASS (P5 null-mktcap flow-through + P8 SIC reverse-recall union "
          "+ P12 SEC-reconstructed mktcap not size-excluded)")


def main():
    # --selftest short-circuit: library-style unit check, no --theme required.
    if "--selftest" in sys.argv:
        _selftest()
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="Run unit assertions and exit")
    ap.add_argument("--theme", required=True, help="逗号分隔的主题短语")
    ap.add_argument("--forms", default="10-K,10-Q,20-F,40-F",
                    help="SEC form types to search (default includes 20-F/40-F for foreign filers)")
    ap.add_argument("--startdt", default=_two_years_ago(),
                    help="FTS 起始日期 (default: today minus 2 years)")
    ap.add_argument("--enddt", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--max-mcap", type=float, default=CFG["market_cap_max"],
                    help="小盘上限 band='deep' threshold, 默认 $2B")
    ap.add_argument("--watch-band-max", type=float, default=CFG.get("watch_band_max", 5_000_000_000),
                    help="Watch-band upper cap: companies between max-mcap and this value "
                         "are tagged band='watch' (theme-fit only, no deep-dive). Default $5B.")
    ap.add_argument("--min-dollar-vol", type=float, default=CFG["min_dollar_vol"], help="日均成交额下限")
    ap.add_argument("--max-pages", type=int, default=10,
                    help="每短语最大翻页数 (default: 10, 每页100条)")
    ap.add_argument("--out-slug", default="", help="输出文件名 slug(多主题区分用)")
    ap.add_argument("--sic-reverse", action="store_true",
                    help="P8 recall FLOOR: also enumerate the theme's dedicated SIC(s) "
                         "(filter_by_sic.THEME_SIC) via EDGAR browse-by-SIC and UNION with "
                         "the FTS recall, so a true small-cap FTS missed is still recalled. "
                         "Opt-in; no-op for a theme with no dedicated SIC. Tags recall_channel "
                         "(fts/sic_reverse/both) on every row.")
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
    # P8 recall FLOOR: union FTS with the theme's dedicated-SIC enumeration (opt-in).
    # Use the out-slug (or first phrase) as the theme key for THEME_SIC lookup. Done before
    # the zero-hit guard so a SIC floor can recover candidates even on a 0-FTS-hit theme.
    if args.sic_reverse:
        theme_key = args.out_slug or phrases[0]
        if theme_sics(theme_key):
            print(f"[1b/3] P8 SIC reverse-recall (theme key '{theme_key}')...", file=sys.stderr)
            all_hits = merge_sic_reverse(all_hits, theme_key, args.forms)
        else:
            print(f"  [P8] --sic-reverse set but theme '{theme_key}' has no dedicated SIC; "
                  f"FTS-only (no floor).", file=sys.stderr)
    if not all_hits:
        print(f"  [warn] 主题 '{phrases}' SEC FTS 零命中 — 关键词可能过严(需更自然短语)", file=sys.stderr)
        date = today()
        slug = args.out_slug or _slug(phrases[0])
        # 写空 universe 占位,避免后续崩
        pd.DataFrame(columns=["ticker", "cik", "name", "mktcap", "band", "smallcap_candidate"]
                     ).to_csv(REPORTS / f"universe_{slug}_{date}.csv", index=False)
        print(f"\n=== 发现结果 ===\n总召回 0 家 — 零命中,已写空占位", file=sys.stderr)
        return
    df = pd.DataFrame(all_hits).drop_duplicates(subset="cik").reset_index(drop=True)
    print(f"  去重后 {len(df)} 家", file=sys.stderr)

    print(f"[2/3] yfinance 补市值+流动性...", file=sys.stderr)
    df = enrich_marketcap(df)

    print(f"[3/3] 过滤去噪...", file=sys.stderr)
    df = apply_filters(df, args.max_mcap, args.min_dollar_vol, args.watch_band_max)

    date = today()
    slug = args.out_slug or _slug(phrases[0])
    out = REPORTS / f"universe_{slug}_{date}.csv"
    df.sort_values("mktcap", na_position="last").to_csv(out, index=False)

    deep = df[df["band"] == "deep"]
    watch = df[df["band"] == "watch"]
    print(f"\n=== 发现结果 ===")
    print(f"总召回 {len(df)} 家 | deep候选 {len(deep)} 家 (市值<${args.max_mcap/1e9:.1f}B) | "
          f"watch候选 {len(watch)} 家 (${args.max_mcap/1e9:.1f}B–${args.watch_band_max/1e9:.1f}B)")
    print(f"\nDeep-dive候选 (band=deep, 按市值):")
    show = deep.sort_values("mktcap")[["ticker", "name", "mktcap", "avg_dollar_vol", "sic", "band"]]
    for _, r in show.iterrows():
        mc = f"${r['mktcap']/1e6:.0f}M" if pd.notna(r['mktcap']) else "—"
        dv = f"${r['avg_dollar_vol']/1e6:.1f}M/d" if pd.notna(r['avg_dollar_vol']) else "—"
        print(f"  {r['ticker']:8} {mc:>8} {dv:>10}  {r['name'][:40]}")
    if not watch.empty:
        print(f"\nWatch-band候选 (band=watch — theme-fit only, no deep-dive):")
        for _, r in watch.sort_values("mktcap").iterrows():
            mc = f"${r['mktcap']/1e6:.0f}M" if pd.notna(r['mktcap']) else "—"
            print(f"  {r['ticker']:8} {mc:>8}  {r['name'][:40]}")
    print(f"\n清单: {out}")


if __name__ == "__main__":
    main()
