"""
deepdive_data.py — Stage 1 深度尽调的数据拉取层(机械部分)

对 cheap pass 幸存者,拉齐 deep dive 所需的结构化数据:
  - 财务序列(收入/净利/OCF/现金/资产/权益,多期)→ 增长质量、runway、现金流质量
  - 稀释史(流通股 YoY)
  - Form 4 内部人交易(净买卖方向 = 最硬的管理层诚实信号)
  - 10-K 关键章节文本(business/risk factors)供判断层读
设计依据:reference/mechanical-checks.md。

判断层(护城河/管理层/估值/多空论点)由 agent 读这些数据后做,不在此脚本。
本脚本只负责"把硬数据摆到桌上",防止 agent 凭记忆/叙事编。

用法:
    python deepdive_data.py --ticker IQST
    python deepdive_data.py --candidates reports/smallcap/candidates_<slug>.json
输出: reports/smallcap/deepdive_<ticker>_<date>.json
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from edgar import Company

# sys.path shim so this script can be run directly from tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import init_edgar, UA, REPORTS, today, CFG, http_get

FACTS = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"


def _one_concept(cik: str, concept: str) -> list:
    """拉单个 XBRL 概念的年度序列(跨度 350-380 天 或 instant)。"""
    url = FACTS.format(cik=str(cik).zfill(10), concept=concept)
    try:
        r = http_get(url, timeout=20)
        if r.status_code != 200:
            return []
        units = r.json().get("units", {})
        vals = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        from datetime import date
        annual = []
        for v in vals:
            if "start" in v and "end" in v:
                try:
                    s = date.fromisoformat(v["start"]); e = date.fromisoformat(v["end"])
                    if 350 <= (e - s).days <= 380:
                        annual.append({"end": v["end"], "val": v["val"], "fy": v.get("fy")})
                except Exception:
                    pass
            elif "end" in v:  # instant(资产负债表项)
                annual.append({"end": v["end"], "val": v["val"], "fy": v.get("fy")})
        return annual
    except Exception:
        return []


def concept_series(cik: str, concepts, n: int = 8) -> list:
    """拉一个或多个 XBRL 概念,**合并**取真正最新的 n 期。
    关键修复(2026-06-18):公司常在 2018 新收入准则后换概念
    (Revenues → RevenueFromContractWithCustomerExcludingAssessedTax)。
    旧版用 `or` 短路只取到旧概念的 2018 截止值 → latest_revenue 是 2017 旧数。
    现合并所有传入概念,同 end 日去重(后出现的概念优先=更新口径)。"""
    if isinstance(concepts, str):
        concepts = [concepts]
    seen = {}
    for concept in concepts:
        for a in _one_concept(cik, concept):
            # 同 end 日:已有则保留(先传入的概念优先级低,后传入覆盖)
            seen[a["end"]] = a
        time.sleep(0.15)
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


def pct_growth(series: list) -> float | None:
    vals = [s["val"] for s in series if s.get("val") is not None]
    if len(vals) < 2 or vals[-2] == 0:
        return None
    return round((vals[-1] / vals[-2] - 1) * 100, 1)


def insider_trades(ticker: str) -> dict:
    """内部人交易净方向(最硬的管理层诚实信号)。
    源由 CFG["insider_source"] 控制,默认 openinsider(已测试路径)。
    """
    if CFG["insider_source"] == "openinsider":
        out = {"available": False, "buys": 0, "sells": 0, "net_signal": None,
               "buy_value": 0, "sell_value": 0, "source": "openinsider"}
        try:
            # openinsider 最近交易表(精确解析 P/S transaction code)
            url = f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=100&page=1"
            r = http_get(url, timeout=20)
            if r.status_code != 200:
                out["error"] = f"http {r.status_code}"
                return out
            import re as _re
            # 表格行含 transaction type 列:P - Purchase / S - Sale
            buys = len(_re.findall(r"P\s*-\s*Purchase", r.text))
            sells = len(_re.findall(r"S\s*-\s*Sale", r.text))
            out.update({"available": True, "buys": buys, "sells": sells,
                        "net_signal": ("net_buy" if buys > sells else
                                       "net_sell" if sells > buys else "neutral")})
        except Exception as e:
            out["error"] = str(e)
        return out
    elif CFG["insider_source"] == "edgar":
        # TODO(roadmap): edgar Form4 direction parser
        # edgartools Form4 direction matching was unreliable in testing (returned None).
        # Hardening this path is a roadmap item; openinsider remains the tested default.
        return {"available": False, "note": "edgar source not yet implemented"}
    else:
        return {"available": False, "error": f"unknown insider_source: {CFG['insider_source']}"}


def tenk_sections(ticker: str) -> dict:
    """取最新 10-K 的关键文本片段(business + risk factors 节选)供判断层读。"""
    out = {"available": False}
    try:
        c = Company(ticker)
        # amendments=False:10-K/A 修正件常缺 going-concern 全文(实测 IQST 漏判)
        fl = c.get_filings(form="10-K", amendments=False)
        f = fl.latest(1) if fl is not None and len(fl) else None
        if f is None:
            return out
        txt = f.text() if hasattr(f, "text") else str(f.obj())
        low = txt.lower()
        out["available"] = True
        out["filing_date"] = str(getattr(f, "filing_date", ""))
        out["total_len"] = len(txt)
        # kill-flag 复核
        out["has_going_concern"] = "going concern" in low and "substantial doubt" in low
        out["has_material_weakness"] = "material weakness" in low
        out["has_death_spiral"] = "variable conversion" in low
        # 客户集中度信号
        out["customer_concentration_flag"] = "customers accounted for" in low or \
            "customer accounted for" in low
        # 截取 risk factors 开头(供 agent 读真实风险)
        idx = low.find("risk factors")
        out["risk_excerpt"] = txt[idx:idx + 3000] if idx >= 0 else ""
    except Exception as e:
        out["error"] = str(e)
    return out


def pull(ticker: str, cik: str) -> dict:
    d = {"ticker": ticker, "cik": cik,
         "pulled_at": today()}
    print(f"  拉财务序列...", file=sys.stderr)
    rev = concept_series(cik, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
    time.sleep(0.2)
    ni = concept_series(cik, "NetIncomeLoss"); time.sleep(0.2)
    ocf = concept_series(cik, "NetCashProvidedByUsedInOperatingActivities"); time.sleep(0.2)
    cash = concept_series(cik, "CashAndCashEquivalentsAtCarryingValue"); time.sleep(0.2)
    shares = concept_series(cik, "CommonStockSharesOutstanding"); time.sleep(0.2)
    assets = concept_series(cik, "Assets"); time.sleep(0.2)
    equity = concept_series(cik, "StockholdersEquity"); time.sleep(0.2)

    d["financials"] = {
        "revenue": rev, "net_income": ni, "ocf": ocf, "cash": cash,
        "shares_outstanding": shares, "assets": assets, "equity": equity,
    }
    d["derived"] = {
        "revenue_growth_pct": pct_growth(rev),
        "shares_growth_pct": pct_growth(shares),  # 正=稀释
        "latest_revenue": rev[-1]["val"] if rev else None,
        "latest_net_income": ni[-1]["val"] if ni else None,
        "latest_ocf": ocf[-1]["val"] if ocf else None,
        "latest_cash": cash[-1]["val"] if cash else None,
        "ocf_ni_divergence": (ni and ocf and ni[-1]["val"] > 0 and ocf[-1]["val"] < 0),
        "runway_periods": (round(cash[-1]["val"] / abs(ocf[-1]["val"]), 1)
                           if (cash and ocf and ocf[-1]["val"] < 0) else None),
    }
    print(f"  拉内部人交易...", file=sys.stderr)
    d["insider"] = insider_trades(ticker); time.sleep(0.3)
    print(f"  拉 10-K 章节...", file=sys.stderr)
    d["tenk"] = tenk_sections(ticker)
    return d


def _selftest():
    init_edgar()
    rev = concept_series("1066194", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
    years = [v["end"][:4] for v in rev]
    assert any(y >= "2024" for y in years), f"EGAN revenue must reach >=2024 after concept merge, got {years}"
    print("deepdive_data selftest PASS")


def _pull_and_save(ticker: str, cik: str) -> None:
    """Pull data for one ticker and write JSON to REPORTS dir."""
    print(f"深度尽调数据拉取: {ticker} (CIK {cik})", file=sys.stderr)
    d = pull(ticker, cik)
    out = REPORTS / f"deepdive_{ticker}_{today()}.json"
    out.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    der = d["derived"]
    print(f"\n=== {ticker} 数据摘要 ===")
    print(f"  营收: ${(der['latest_revenue'] or 0)/1e6:.1f}M (增速 {der['revenue_growth_pct']}%)")
    print(f"  净利: ${(der['latest_net_income'] or 0)/1e6:.1f}M | OCF: ${(der['latest_ocf'] or 0)/1e6:.1f}M")
    print(f"  现金: ${(der['latest_cash'] or 0)/1e6:.1f}M | runway: {der['runway_periods']} 期")
    print(f"  股本增速(稀释): {der['shares_growth_pct']}% | OCF/NI背离: {der['ocf_ni_divergence']}")
    print(f"  内部人: {d['insider'].get('net_signal')} (买{d['insider'].get('buys')}/卖{d['insider'].get('sells')})")
    print(f"  going concern: {d['tenk'].get('has_going_concern')} | 客户集中: {d['tenk'].get('customer_concentration_flag')}")
    print(f"\n数据: {out}")


def main():
    ap = argparse.ArgumentParser(
        description="deepdive_data — Stage 1 data pull. Use --ticker for single company or "
                    "--candidates for batch mode."
    )
    ap.add_argument("--ticker", default="", help="单只股票 ticker")
    ap.add_argument("--cik", default="", help="留空则用 edgartools 解析")
    ap.add_argument(
        "--candidates",
        default="",
        help="candidates JSON 文件路径 (list of {ticker, cik, ...}); 批量拉取所有候选",
    )
    ap.add_argument("--selftest", action="store_true", help="运行自检并退出")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    if args.candidates:
        # Batch mode: loop over candidates JSON
        candidates_path = Path(args.candidates)
        if not candidates_path.exists():
            ap.error(f"--candidates file not found: {args.candidates}")
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        if not isinstance(candidates, list):
            ap.error("--candidates file must contain a JSON array of {ticker, cik, ...}")
        init_edgar()
        for i, rec in enumerate(candidates):
            ticker = rec.get("ticker", "")
            cik = str(rec.get("cik", ""))
            if not ticker:
                print(f"  [warn] skipping record {i}: missing ticker", file=sys.stderr)
                continue
            if not cik:
                try:
                    cik = str(Company(ticker).cik)
                except Exception as e:
                    print(f"  [warn] cannot resolve CIK for {ticker}: {e}", file=sys.stderr)
                    continue
            try:
                _pull_and_save(ticker, cik)
            except Exception as e:
                print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return

    if not args.ticker:
        ap.error("--ticker or --candidates is required unless --selftest")

    init_edgar()
    cik = args.cik
    if not cik:
        try:
            cik = str(Company(args.ticker).cik)
        except Exception as e:
            print(f"无法解析 CIK: {e}", file=sys.stderr); sys.exit(1)
    _pull_and_save(args.ticker, cik)


if __name__ == "__main__":
    main()
