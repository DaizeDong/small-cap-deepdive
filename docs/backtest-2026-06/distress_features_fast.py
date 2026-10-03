"""Batch companyfacts puller for historical research.

Annual flow duration, instant-concept classification and fact shape are checked by the
current _deepdive_concepts helpers. Historical outputs remain unvalidated until private
inputs are recomputed and compared; changing this selector provides no historical credit.

Shares continue to use _shares_series. The validate mode compares stored financial
series without modifying them; run writes through the private feature-data resolver.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import _deepdive_concepts as DC  # noqa: E402
from _deepdive_concepts import _shares_series, REVENUE_CONCEPTS  # noqa: E402
from distress_features_extract import backtest_files, features_path, load_features, write_features

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
    """Cache structurally valid company facts; failed requests remain retryable."""
    c = str(cik).zfill(10)
    if c in _cache:
        return _cache[c]
    response = DC.http_get(COMPANYFACTS.format(cik=c), timeout=45)
    if getattr(response, "status_code", None) != 200:
        raise ValueError("companyfacts_http_unavailable")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("companyfacts_invalid_shape")
    taxonomies = payload.get("facts")
    taxonomies = {} if taxonomies is None else taxonomies
    if not isinstance(taxonomies, dict):
        raise ValueError("companyfacts_invalid_shape")
    facts = taxonomies.get("us-gaap")
    facts = {} if facts is None else facts
    if not isinstance(facts, dict):
        raise ValueError("companyfacts_invalid_shape")
    for concept in {name for cascade in CONCEPTS.values() for name in cascade}:
        block = facts.get(concept)
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ValueError("companyfacts_invalid_concept")
        units = block.get("units")
        if units is None:
            continue
        if not isinstance(units, dict):
            raise ValueError("companyfacts_invalid_units")
        values = units.get(DC._concept_unit(concept))
        if values is not None and (not isinstance(values, list)
                                   or any(not isinstance(value, dict) for value in values)):
            raise ValueError("companyfacts_invalid_values")
    if facts:
        _cache[c] = facts
    return facts


def _select_concept(units, asof, concept):
    """Apply current annual-flow and instant-balance rules to one named concept."""
    date.fromisoformat(asof)
    unit = DC._concept_unit(concept)
    vals = units.get(unit) or []
    seen = {}
    allow_instant = concept in DC._INSTANT_CONCEPTS
    for fact in vals:
        if not DC._fact_shape_valid(fact, asof=asof, allow_instant=allow_instant):
            continue
        entry = DC._annual_entry(fact, allow_instant=allow_instant, unit=unit,
                                 taxonomy="us-gaap", concept=concept)
        if entry is None or entry["filed"] > asof:
            continue
        previous = seen.get(entry["end"])
        if previous is None or entry["filed"] >= previous["filed"]:
            seen[entry["end"]] = entry
    return list(seen.values())


def series_cf(facts, cascade, asof, n=8):
    seen = {}
    for concept in cascade:
        units = (facts.get(concept, {}) or {}).get("units", {}) or {}
        for e in _select_concept(units, asof, concept):
            seen[e["end"]] = e
    return sorted(seen.values(), key=lambda x: x["end"])[-n:]


def pull_one(rec):
    """Retain partial observations and mark whether both acquisition channels are usable."""
    rec = dict(rec)
    rec.pop("pull_error", None)
    errors = []
    try:
        facts = get_facts(rec["cik"])
    except Exception as exc:
        facts = {}
        errors.append("companyfacts:" + type(exc).__name__)
    series = {key: series_cf(facts, cascade, rec["asof"], n=8)
              for key, cascade in CONCEPTS.items()}
    financial_usable = any(series.values())
    if not financial_usable:
        _cache.pop(str(rec["cik"]).zfill(10), None)
    try:
        series["shares"] = [{"end": point.get("end"), "val": point.get("val")}
                            for point in (_shares_series(rec["cik"], n=8, asof=rec["asof"]) or [])]
    except Exception as exc:
        series["shares"] = []
        errors.append("shares:" + type(exc).__name__)
    shares_usable = bool(series["shares"])
    rec["series"] = series
    rec["acquisition_status"] = ("complete" if financial_usable and shares_usable and not errors
                                 else "partial" if financial_usable or shares_usable
                                 else "unavailable")
    if errors:
        rec["pull_error"] = ";".join(errors)
    return rec


def validate():
    try:
        done = load_features()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"VALIDATION FAIL: missing or invalid private feature artifact ({type(exc).__name__})")
        return False
    if not isinstance(done, list):
        print("VALIDATION FAIL: expected a list of feature rows")
        return False
    done = [r for r in done if isinstance(r, dict) and r.get("cik") is not None
            and isinstance(r.get("asof"), str) and isinstance(r.get("series"), dict)][:30]
    print(f"validating {len(done)} already-pulled rows (financial concepts only)...")
    mism = compared = invalid = 0

    def pairs(series):
        if not isinstance(series, list):
            raise ValueError("series must be a list")
        result = []
        for point in series:
            if not isinstance(point, dict):
                raise ValueError("series point must be an object")
            end, value = point.get("end"), point.get("val")
            if (not isinstance(end, str) or not end or isinstance(value, bool)
                    or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError("series point must have an end date and finite value")
            date.fromisoformat(end)
            result.append((end, value))
        return result

    for r in done:
        try:
            facts = get_facts(r["cik"])
        except Exception as exc:
            invalid += 1
            print(f"  ACQUISITION FAIL {r.get('ticker', '')}: {type(exc).__name__}")
            continue
        for key, cc in CONCEPTS.items():
            try:
                got = series_cf(facts, cc, r["asof"], n=8)
                exp = r["series"].get(key, [])
                g, e = pairs(got), pairs(exp)
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                invalid += 1
                continue
            if not g and not e:
                continue
            compared += 1
            if g != e:
                mism += 1
                print(f"  MISMATCH {r.get('ticker', '')} {r['asof']} {key}\n    fast={g[-3:]}\n    trust={e[-3:]}")
    passed = compared > 0 and mism == 0 and invalid == 0
    print(f"VALIDATION {'PASS' if passed else 'FAIL'}: {compared} nonempty comparisons; "
          f"{mism} mismatches; {invalid} invalid comparisons")
    return passed


def run():
    destination = features_path()
    files = backtest_files()
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
    prior = load_features() if destination.exists() else []
    out = {(r["ticker"], r["asof"]): r for r in prior}
    # Legacy nonempty observations remain resumable; explicit partial status and all-empty
    # production-shaped dictionaries are retryable even though the dictionary is truthy.
    done = {key for key, row in out.items()
            if isinstance(row.get("series"), dict) and any(row["series"].values())
            and not row.get("pull_error")
            and row.get("acquisition_status", "complete") == "complete"}
    todo = [r for r in rows if (r["ticker"], r["asof"]) not in done]
    print(f"total={len(rows)} done={len(done)} todo={len(todo)}", flush=True)
    # Failed observations remain present until a retry replaces their keyed row.
    t0 = time.time(); n = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(pull_one, r): r for r in todo}
        for fut in as_completed(futs):
            try:
                result = fut.result()
            except Exception as e:
                result = futs[fut]
                result["series"] = {}
                result["pull_error"] = str(e)[:120]
                result["acquisition_status"] = "unavailable"
            out[(result["ticker"], result["asof"])] = result
            n += 1
            if n % 40 == 0:
                write_features(list(out.values()))
                el = time.time() - t0
                print(f"  {n}/{len(todo)} {el:.0f}s ~{el/n:.2f}s/name eta {el/n*(len(todo)-n)/60:.0f}min", flush=True)
    write_features(list(out.values()))
    print(f"DONE wrote {len(out)} rows in {(time.time()-t0)/60:.1f}min", flush=True)


def _cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("validate", "run"), default="validate")
    args = parser.parse_args(argv)
    if args.mode == "validate":
        return 0 if validate() else 1
    run()
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
