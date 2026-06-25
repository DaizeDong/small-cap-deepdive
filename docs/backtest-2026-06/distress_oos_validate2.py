"""distress_oos_validate2.py — corrected, cluster-robust OOS validation of the PIT distress
score as a blowup predictor. Supersedes distress_oos_validate.py after adversarial review.

Corrections honored (codex adversarial review, 2026-06-24):
  * NO outcome-based |return|<=5 cap (it was a forward-return filter that asymmetrically
    drops big winners). Priceability = status ok AND entry_price>=0.10 only (non-outcome).
  * Cluster-robust inference: ticker-cluster bootstrap CI on the lift (411 name-years come
    from ~93 unique tickers / 20 cells / 5 years; Fisher's row-independence is anti-conservative).
  * Report a CORE-4 distress rank (neg_ocf, neg_margin, accum_deficit, low_altman) alongside the
    8-flag composite — high_lev is directionally wrong; "8-flag robust composite" is overstated.
  * Honest framing: NOT "pre-registered"; an a-priori mechanism-grounded spec (Altman/distress
    theory) validated OOS, reported WITH its forking-path exposure.

Network-free; seed=42; reproducible. Reuses feature engineering from distress_oos_validate.py.
"""
from __future__ import annotations
import json, os, sys, math, random
from collections import defaultdict

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import distress_oos_validate as H  # features(), FLAGS, fisher()

CORE4 = ["neg_ocf", "neg_margin", "accum_deficit", "low_altman"]


def load(cap_returns=False):
    data = json.load(open(os.path.join(HERE, "distress_features.json")))
    rows, excluded_no_entry, extreme = [], 0, 0
    for r in data:
        tr, st, ep = r.get("total_return"), r.get("status"), r.get("entry")
        if r.get("theme") == "regbank":
            continue
        if st != "ok" or tr is None:
            continue
        if not ep or ep < 0.10:
            excluded_no_entry += 1
            continue
        if abs(tr) > 5:
            extreme += 1
            if cap_returns:
                continue
        f = H.features(r)
        if not f["_has_core"]:
            continue
        rr = dict(r); rr.update(f)
        rr["composite"] = sum(f[k] for k in H.FLAGS)
        rr["core4"] = sum(f[k] for k in CORE4)
        rows.append(rr)
    return rows, excluded_no_entry, extreme


def loyo_lift(rows, scorekey, q=0.2):
    """per-year top-q by score, pooled; returns (a,b,c,d, lift, recall)."""
    flags = []
    byyr = defaultdict(list)
    for r in rows:
        byyr[r["year"]].append(r)
    for y, g in byyr.items():
        g = sorted(g, key=lambda r: r[scorekey], reverse=True)
        k = max(1, int(round(len(g) * q)))
        top = set(id(r) for r in g[:k])
        for r in g:
            flags.append((1 if id(r) in top else 0, r["blow"]))
    a = sum(1 for t, b in flags if t and b); b = sum(1 for t, bl in flags if t and not bl)
    c = sum(1 for t, bl in flags if not t and bl); d = sum(1 for t, bl in flags if not t and not bl)
    base = (a + c) / (a + b + c + d); prec = a / (a + b) if (a + b) else 0
    lift = prec / base if base else 0; rec = a / (a + c) if (a + c) else 0
    return a, b, c, d, lift, rec, prec, base


def ticker_bootstrap(rows, scorekey, B=5000, q=0.2):
    by_tkr = defaultdict(list)
    for r in rows:
        by_tkr[r["ticker"]].append(r)
    tickers = list(by_tkr)
    lifts = []
    for _ in range(B):
        samp = []
        for _ in range(len(tickers)):
            samp.extend(by_tkr[random.choice(tickers)])
        a, b, c, d, lift, *_ = loyo_lift(samp, scorekey, q)
        if (a + c) > 0 and (a + b) > 0 and (a + c) / (a + b + c + d) > 0:
            lifts.append(lift)
    lifts.sort()
    n = len(lifts)
    pct = lambda p: lifts[min(n - 1, int(p * n))]
    p_le1 = sum(1 for x in lifts if x <= 1.0) / n
    return pct(0.025), pct(0.5), pct(0.975), p_le1, n


def main():
    rows, exc_noentry, extreme = load(cap_returns=False)
    nb = sum(r["blow"] for r in rows)
    utk = len(set(r["ticker"] for r in rows))
    ubt = len(set(r["ticker"] for r in rows if r["blow"]))
    print(f"NO outcome-cap. non-financial+core: n={len(rows)} blowups={nb}")
    print(f"  unique tickers={utk}  unique blowup tickers={ubt}  (clustering: {len(rows)} rows from {utk} tickers)")
    print(f"  excluded no/penny entry={exc_noentry}  extreme |ret|>5 KEPT={extreme}")
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r["year"]][0] += 1; by[r["year"]][1] += r["blow"]
    print("  by year (n,blow):", {y: tuple(v) for y, v in sorted(by.items())})
    print()
    for sk, lbl in [("composite", "8-flag composite"), ("core4", "CORE-4 distress rank")]:
        a, b, c, d, lift, rec, prec, base = loyo_lift(rows, sk)
        orr, p = H.fisher(a, b, c, d)
        lo, med, hi, p_le1, nbs = ticker_bootstrap(rows, sk)
        print(f"=== {lbl} (per-year top-quintile, pooled) ===")
        print(f"   point: topQ_blow={a} prec={prec:.3f} base={base:.3f} lift={lift:.2f}x recall={rec:.2f}")
        print(f"   row-Fisher (ANTI-CONSERVATIVE, ignores clustering): OR={orr:.2f} p={p:.2e}")
        print(f"   TICKER-CLUSTER bootstrap lift: median={med:.2f}x  95%CI=[{lo:.2f}, {hi:.2f}]  P(lift<=1)={p_le1:.4f}")
        print()
    # sensitivity: WITH the old cap, to show direction of the contamination codex flagged
    rows_cap, _, _ = load(cap_returns=True)
    a, b, c, d, lift, rec, prec, base = loyo_lift(rows_cap, "composite")
    print(f"[sensitivity] WITH old |ret|<=5 cap: n={len(rows_cap)} base={base:.3f} composite lift={lift:.2f}x "
          f"(vs no-cap base above) -> shows cap's effect on base/lift")


if __name__ == "__main__":
    main()
