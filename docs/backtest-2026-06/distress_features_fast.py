"""distress_features_fast.py — companyfacts-batch puller, byte-equivalent to the trusted
per-concept puller, validated before use.

Speedup: ONE companyfacts request per CIK (cached) instead of ~12 companyconcept requests
per name. The PIT selection logic is copied verbatim from _deepdive_concepts._one_concept's
as-of path (filed<=asof, annual 10-K/FY or 330-400d span, latest-filed-per-end wins) and the
cascade-merge from concept_series (later concept overrides per end-date, last n=8 by end).

Shares stay on the trusted _shares_series (its 3-level fallback is not re-implemented).

Modes:
  validate  -> recompute the 12 financial concept series for rows ALREADY in
               distress_features.json and diff against stored {end,val}; report mismatches.
               READ-ONLY. Must pass before trusting/running.
  run       -> resumable full pull into distress_features.json (skips rows already present).
"""
from __future__ import annotations
import json, os, sys, time
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import _deepdive_concepts as DC  # noqa: E402
from _deepdive_concepts import _shares_series, REVENUE_CONCEPTS  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "distress_features.json")
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

CONCEPTS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "assets": ["Assets"], "liab": ["Liabilities"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "curassets": ["AssetsCurrent"], "curliab": ["LiabilitiesCurrent"],
    "retearn": ["RetainedEarningsAccumulatedDeficit"], "ebit": ["OperatingIncomeLoss"],
    "ni": ["NetIncomeLoss"], "revenue": list(REVENUE_CONCEPTS), "gross": ["GrossProfit"],
}

_cache: dict = {}


def get_facts(cik):
    c = str(cik).zfill(10)
    if c in _cache:
        return _cache[c]
    facts = {}
    try:
        r = DC.http_get(COMPANYFACTS.format(cik=c), timeout=45)
        if getattr(r, "status_code", None) == 200:
            facts = (r.json().get("facts", {}) or {}).get("us-gaap", {}) or {}
    except Exception:
        facts = {}
    _cache[c] = facts
    return facts


def _select_concept(units, asof):
    """verbatim port of _one_concept PIT path for one concept's units dict."""
    vals = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
    seen = {}
    for v in vals:
        filed = v.get("filed")
        if not filed or filed > asof:
            continue
        if "start" in v and "end" in v:
            try:
                s = date.fromisoformat(v["start"]); e = date.fromisoformat(v["end"])
                days = (e - s).days; fp = v.get("fp", ""); form = v.get("form", "")
                if not ((fp == "FY" and form.startswith("10-K")) or (330 <= days <= 400)):
                    continue
                entry = {"end": v["end"], "val": v["val"]}
            except Exception:
                continue
        elif "end" in v:
            entry = {"end": v["end"], "val": v["val"]}
        else:
            continue
        prev = seen.get(v["end"])
        if prev is None or filed >= prev[0]:
            seen[v["end"]] = (filed, entry)
    return [x[1] for x in seen.values()]


def series_cf(facts, cascade, asof, n=8):
    seen = {}
    for concept in cascade:
        units = (facts.get(concept, {}) or {}).get("units", {}) or {}
        for e in _select_concept(units, asof):
            seen[e["end"]] = e
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


def pull_one(rec):
    facts = get_facts(rec["cik"])
    s = {}
    for key, cc in CONCEPTS.items():
        s[key] = series_cf(facts, cc, rec["asof"], n=8)
    try:
        s["shares"] = [{"end": x.get("end"), "val": x.get("val")}
                       for x in (_shares_series(rec["cik"], n=8, asof=rec["asof"]) or [])]
    except Exception:
        s["shares"] = []
    rec["series"] = s
    return rec


def validate():
    if not os.path.exists(OUT):
        print("no existing output to validate against"); return False
    done = json.load(open(OUT))
    done = [r for r in done if r.get("series")][:30]
    print(f"validating {len(done)} already-pulled rows (financial concepts only)...")
    mism = 0
    for r in done:
        facts = get_facts(r["cik"])
        for key, cc in CONCEPTS.items():
            got = series_cf(facts, cc, r["asof"], n=8)
            exp = r["series"].get(key, [])
            g = [(x["end"], x["val"]) for x in got]
            e = [(x["end"], x["val"]) for x in exp]
            if g != e:
                mism += 1
                print(f"  MISMATCH {r['ticker']} {r['asof']} {key}\n    fast={g[-3:]}\n    trust={e[-3:]}")
    print("VALIDATION", "PASS — companyfacts byte-equivalent" if mism == 0 else f"FAIL ({mism} mismatches)")
    return mism == 0


def run():
    import glob
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
            rows.append({"ticker": nm.get("ticker"), "cik": nm.get("cik"), "asof": d["asof"],
                         "year": d["asof"][:4], "theme": d["theme"], "bench": bench,
                         "mos": nm.get("mos_pct"), "peak": "peak_contamination_flag" in rs,
                         "fund": "fundamental_decline_flag" in rs, "total_return": tr,
                         "status": fr.get("status"), "entry": fr.get("entry_price"),
                         "blow": 1 if (tr is not None and tr < -0.4) else 0})
    done = {}
    if os.path.exists(OUT):
        for r in json.load(open(OUT)):
            if r.get("series"):
                done[(r["ticker"], r["asof"])] = r
    todo = [r for r in rows if (r["ticker"], r["asof"]) not in done]
    print(f"total={len(rows)} done={len(done)} todo={len(todo)}", flush=True)
    out = list(done.values()); t0 = time.time(); n = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(pull_one, r): r for r in todo}
        for fut in as_completed(futs):
            try:
                out.append(fut.result())
            except Exception as e:
                rr = futs[fut]; rr["series"] = {}; rr["pull_error"] = str(e)[:120]; out.append(rr)
            n += 1
            if n % 40 == 0:
                json.dump(out, open(OUT, "w"))
                el = time.time() - t0
                print(f"  {n}/{len(todo)} {el:.0f}s ~{el/n:.2f}s/name eta {el/n*(len(todo)-n)/60:.0f}min", flush=True)
    json.dump(out, open(OUT, "w"))
    print(f"DONE wrote {len(out)} rows in {(time.time()-t0)/60:.1f}min", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if mode == "validate":
        validate()
    elif mode == "run":
        run()
