"""distress_features_extract.py — PIT raw-fact puller for the blowup-prediction study.

Pulls, point-in-time (filed<=asof), the raw XBRL concept series needed to engineer
small-cap distress features, for every (ticker, cik, asof) row in the 25-cell backtest
panel. Stores the RAW series per concept so feature engineering can be re-run locally
without re-hitting EDGAR.

Design: pull-once / iterate-features-locally. Resumable (skips rows already in the
output JSON). Network-bound; modest thread pool respects EDGAR's 10 req/s.

Output: docs/backtest-2026-06/distress_features.json
  [{ticker,cik,asof,year, label fields (blow,mos,peak,fund,total_return,bench,entry,status),
     series:{key:[{end,val},...]}}]
"""
from __future__ import annotations
import json, glob, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from _deepdive_concepts import concept_series_asof, _shares_series, REVENUE_CONCEPTS  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "distress_features.json")

CONCEPTS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "assets": ["Assets"],
    "liab": ["Liabilities"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "curassets": ["AssetsCurrent"],
    "curliab": ["LiabilitiesCurrent"],
    "retearn": ["RetainedEarningsAccumulatedDeficit"],
    "ebit": ["OperatingIncomeLoss"],
    "ni": ["NetIncomeLoss"],
    "revenue": list(REVENUE_CONCEPTS),
    "gross": ["GrossProfit"],
}


def _slim(series):
    return [{"end": x.get("end"), "val": x.get("val")} for x in (series or [])]


def pull_one(rec):
    cik, asof = rec["cik"], rec["asof"]
    series = {}
    for key, cc in CONCEPTS.items():
        try:
            series[key] = _slim(concept_series_asof(cik, cc, asof, n=8))
        except Exception:
            series[key] = []
    try:
        series["shares"] = _slim(_shares_series(cik, n=8, asof=asof))
    except Exception:
        series["shares"] = []
    rec["series"] = series
    return rec


def main():
    files = [f for f in sorted(glob.glob(os.path.join(ROOT, "reports/smallcap/backtest/*_*.json")))
             if not f.endswith(".run.log")]
    rows = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if "names" not in d:
            continue
        bench = (d.get("benchmark") or {}).get("total_return")
        for nm in d.get("names", []):
            fr = nm.get("forward_return") or {}
            rs = nm.get("buy_ineligible_reasons") or []
            tr = nm.get("total_return", fr.get("total_return"))
            rows.append({
                "ticker": nm.get("ticker"), "cik": nm.get("cik"),
                "asof": d["asof"], "year": d["asof"][:4], "theme": d["theme"],
                "bench": bench, "mos": nm.get("mos_pct"),
                "peak": "peak_contamination_flag" in rs, "fund": "fundamental_decline_flag" in rs,
                "total_return": tr, "status": fr.get("status"), "entry": fr.get("entry_price"),
                "blow": 1 if (tr is not None and tr < -0.4) else 0,
            })
    # resume
    done = {}
    if os.path.exists(OUT):
        try:
            for r in json.load(open(OUT)):
                done[(r["ticker"], r["asof"])] = r
        except Exception:
            done = {}
    todo = [r for r in rows if (r["ticker"], r["asof"]) not in done]
    print(f"total rows={len(rows)} already_done={len(done)} todo={len(todo)}", flush=True)
    out = list(done.values())
    t0 = time.time()
    n = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(pull_one, r): r for r in todo}
        for fut in as_completed(futs):
            try:
                out.append(fut.result())
            except Exception as e:
                r = futs[fut]
                r["series"] = {}
                r["pull_error"] = str(e)[:120]
                out.append(r)
            n += 1
            if n % 25 == 0:
                json.dump(out, open(OUT, "w"))
                el = time.time() - t0
                print(f"  {n}/{len(todo)} done  {el:.0f}s  ~{el/n:.1f}s/name  eta {el/n*(len(todo)-n)/60:.0f}min", flush=True)
    json.dump(out, open(OUT, "w"))
    print(f"DONE wrote {len(out)} rows to {OUT} in {(time.time()-t0)/60:.1f}min", flush=True)


if __name__ == "__main__":
    main()
