"""distress_oos_validate.py — does a PIT fundamental distress score predict blowups OOS?

Reads distress_features.json (raw PIT series), engineers mechanism-grounded distress
features LOCALLY, and asks the only question that matters for a de-risk tool:

  Does the distress score concentrate forward 12mo blowups (<-40%) significantly more
  than the base rate, OUT OF SAMPLE?

Anti-overfit discipline (self-evolve truth-isolation):
  * Scope = NON-FINANCIAL operating companies (theme != regbank). Bank distress (NIM,
    NPLs, deposit flight) is a different model; banks already route to financial_sic abstain.
  * (A) PRE-REGISTERED unweighted composite (count of distress flags) — ZERO fitting.
  * (B) Logistic fit on TRAIN years only, frozen, scored on TEST years (2023-24).
  * Primary OOS metric: top-quintile blowup capture (recall) + lift + Fisher exact p.
  * Reports TRAIN, TEST, and pooled — accept "edge" ONLY if it holds on TEST.

Network-free; seed=42; reproducible.
"""
from __future__ import annotations
import json, os, random, math
from datetime import date
from collections import defaultdict

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))
FEAT = os.path.join(HERE, "distress_features.json")


def latest(series):
    return series[-1]["val"] if series else None


def yago(series, target_days=365, tol=130):
    if not series or len(series) < 2:
        return None
    try:
        le = date.fromisoformat(series[-1]["end"])
    except Exception:
        return None
    best, bestd = None, 1e9
    for x in series[:-1]:
        try:
            e = date.fromisoformat(x["end"])
        except Exception:
            continue
        dd = abs((le - e).days - target_days)
        if dd < bestd:
            bestd, best = dd, x["val"]
    return best if bestd < tol else None


def features(rec):
    s = rec.get("series") or {}
    g = lambda k: latest(s.get(k))
    cash, ocf, assets, liab, equity = g("cash"), g("ocf"), g("assets"), g("liab"), g("equity")
    ca, cl, re_, ebit = g("curassets"), g("curliab"), g("retearn"), g("ebit")
    sh, sh1 = g("shares"), yago(s.get("shares"))
    f = {}
    f["neg_equity"] = 1 if (equity is not None and equity < 0) else 0
    f["neg_ocf"] = 1 if (ocf is not None and ocf < 0) else 0
    f["neg_margin"] = 1 if (ebit is not None and ebit < 0) else 0
    f["accum_deficit"] = 1 if (re_ is not None and re_ < 0) else 0
    f["low_runway"] = 1 if (ocf is not None and ocf < 0 and cash is not None and cash < -ocf) else 0
    f["high_dilution"] = 1 if (sh and sh1 and sh1 > 0 and (sh / sh1 - 1) > 0.20) else 0
    f["high_lev"] = 1 if (assets and liab is not None and assets > 0 and liab / assets > 0.85) else 0
    z = None
    if None not in (ca, cl, assets, re_, ebit, equity, liab) and assets > 0 and liab > 0:
        X1 = (ca - cl) / assets; X2 = re_ / assets; X3 = ebit / assets; X4 = equity / liab
        z = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4
    f["low_altman"] = 1 if (z is not None and z < 1.1) else 0
    f["_z"] = z
    f["_has_core"] = 1 if (assets is not None and equity is not None) else 0
    return f


def fisher(a, b, c, d):
    n = a + b + c + d; r1 = a + b; c1 = a + c
    if r1 == 0 or c1 == 0 or n - r1 == 0:
        return float("nan"), float("nan")
    def hg(x):
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    hi = min(r1, c1)
    p = sum(hg(x) for x in range(a, hi + 1))
    orr = (a * d) / (b * c) if b * c else float("inf")
    return orr, p


FLAGS = ["neg_equity", "neg_ocf", "neg_margin", "accum_deficit", "low_runway",
         "high_dilution", "high_lev", "low_altman"]


def topq_test(pool, scorekey, label, q=0.2):
    """top-q by score vs rest; blowup 2x2 + Fisher."""
    pool = [r for r in pool if r.get(scorekey) is not None]
    if len(pool) < 20:
        print(f"   {label}: n<20 ({len(pool)}) skip"); return
    pool = sorted(pool, key=lambda r: r[scorekey], reverse=True)
    k = max(1, int(round(len(pool) * q)))
    top, rest = pool[:k], pool[k:]
    a = sum(r["blow"] for r in top); b = len(top) - a
    c = sum(r["blow"] for r in rest); d = len(rest) - c
    base = (a + c) / len(pool); prec = a / len(top); rec = a / (a + c) if (a + c) else 0
    orr, p = fisher(a, b, c, d)
    print(f"   {label:14s} n={len(pool):3d} topQ={k:3d} blow_top={a:2d} prec={prec:.3f} "
          f"base={base:.3f} lift={prec/base if base else 0:.2f}x recall={rec:.2f} OR={orr:.2f} p={p:.4f}")


def main():
    if not os.path.exists(FEAT):
        print("features file not ready:", FEAT); return
    data = json.load(open(FEAT))
    rows = []
    for r in data:
        tr, st, ep = r.get("total_return"), r.get("status"), r.get("entry")
        if not (st == "ok" and ep and ep >= 0.10 and tr is not None and abs(tr) <= 5):
            continue
        if r.get("theme") == "regbank":
            continue  # bank distress is a different model
        f = features(r)
        if not f["_has_core"]:
            continue
        rr = dict(r); rr.update(f)
        rr["composite"] = sum(f[k] for k in FLAGS)
        rr["neg_z"] = (-f["_z"]) if f["_z"] is not None else None
        rows.append(rr)
    print(f"non-financial priceable w/ core fundamentals: n={len(rows)}  blowups={sum(r['blow'] for r in rows)}")
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r["year"]][0] += 1; by[r["year"]][1] += r["blow"]
    print("  by year (n, blowups):", {y: tuple(v) for y, v in sorted(by.items())})
    print()
    TRAIN = [r for r in rows if r["year"] in ("2020", "2021", "2022")]
    TEST = [r for r in rows if r["year"] in ("2023", "2024")]

    print("=== (A) PRE-REGISTERED composite distress count -> blowup capture (top quintile) ===")
    for lbl, pool in [("TRAIN", TRAIN), ("TEST", TEST), ("ALL", rows)]:
        topq_test(pool, "composite", lbl)
    print()
    print("    composite count vs blowup-rate gradient (ALL):")
    g = defaultdict(lambda: [0, 0])
    for r in rows:
        g[r["composite"]][0] += 1; g[r["composite"]][1] += r["blow"]
    for c in sorted(g):
        n, bl = g[c]
        print(f"     score={c} n={n:3d} blow={bl:2d} rate={bl/n:.3f}")
    print()

    # (B) logistic fit on TRAIN, frozen, OOS on TEST
    try:
        import numpy as np
        Xtr = np.array([[r[k] for k in FLAGS] for r in TRAIN], float)
        ytr = np.array([r["blow"] for r in TRAIN], float)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        Xs = (Xtr - mu) / sd
        w = np.zeros(Xs.shape[1]); b0 = math.log((ytr.mean() + 1e-6) / (1 - ytr.mean() + 1e-6))
        lr = 0.1
        for _ in range(4000):
            z = Xs @ w + b0; p = 1 / (1 + np.exp(-z)); err = p - ytr
            w -= lr * (Xs.T @ err / len(ytr) + 1e-3 * w); b0 -= lr * err.mean()
        for r in rows:
            xs = (np.array([r[k] for k in FLAGS], float) - mu) / sd
            r["logit"] = float(1 / (1 + math.exp(-(xs @ w + b0))))
        print("=== (B) logistic (fit TRAIN, frozen) -> OOS top-quintile blowup capture ===")
        print("    weights:", {k: round(float(wi), 2) for k, wi in zip(FLAGS, w)})
        for lbl, pool in [("TRAIN", TRAIN), ("TEST", TEST), ("ALL", rows)]:
            topq_test(pool, "logit", lbl)
        # OOS AUC on TEST
        def auc(pool):
            pos = [r["logit"] for r in pool if r["blow"]]; neg = [r["logit"] for r in pool if not r["blow"]]
            if not pos or not neg: return float("nan")
            return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
        print(f"    OOS AUC TEST={auc(TEST):.3f}  TRAIN={auc(TRAIN):.3f}  ALL={auc(rows):.3f}")
    except Exception as e:
        print("logistic step skipped:", e)


if __name__ == "__main__":
    main()
