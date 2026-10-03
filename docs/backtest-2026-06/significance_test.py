#!/usr/bin/env python3
"""Significance test for the v0.3.x PIT backtest panel: are the bucket labels
distinguishable from random?

Primary test = STRATIFIED within-cell label permutation. The names within one cell share an
IWM and a regime (cross-sectionally correlated); treating all 959 as independent would be
pseudo-replication and anti-conservative. So the null shuffles bucket labels *within each cell*
(preserving each cell's IWM, size, and bucket-size composition) and asks whether the observed
bucket structure could arise from random labeling. Cluster bootstrap (resample whole cells)
gives honest CIs. Kruskal-Wallis / Mann-Whitney are reported as clustering-naive references.

Run: python docs/backtest-2026-06/significance_test.py   (from repo root)
Deterministic (seed=42), network-free, reads only the on-disk cell JSONs.
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from distress_features_extract import backtest_files

rng = np.random.default_rng(42)
FILES = [f for f in backtest_files()
         if "_covid" not in f.name and "_run" not in f.name]
BCODE = {"buy_eligible": 0, "WATCH": 1, "AVOID": 2, "abstain": 3}
BNAME = ["buy_eligible", "WATCH", "AVOID", "abstain"]


def bucket_statistics(excess, labels):
    """Return finite four-bucket statistics or an explicit unavailable result."""
    from math import isfinite
    from statistics import median, pvariance

    if len(excess) != len(labels):
        return {"status": "unavailable", "reason": "length_mismatch"}
    groups = [[] for _ in range(4)]
    for value, label in zip(excess, labels):
        if (type(value) not in (int, float) or not isfinite(value)
                or type(label) is not int or label not in range(4)):
            return {"status": "unavailable", "reason": "invalid_observation"}
        groups[label].append(value)
    counts = [len(group) for group in groups]
    if any(count == 0 for count in counts):
        return {"status": "unavailable", "reason": "missing_bucket", "counts": counts}
    medians = [median(group) for group in groups]
    try:
        values = [medians[2] - medians[1], medians[0] - medians[1], pvariance(medians)]
    except (OverflowError, ValueError):
        return {"status": "unavailable", "reason": "nonfinite_statistic", "counts": counts}
    if any(not isfinite(value) for value in values):
        return {"status": "unavailable", "reason": "nonfinite_statistic", "counts": counts}
    return {"status": "complete", "counts": counts, "medians": medians,
            "avoid_watch": values[0], "buy_watch": values[1], "omnibus": values[2]}


def permutation_inference(excess, labels, cells, *, permutations, shuffle):
    """Preserve within-cell label permutations and reject unavailable statistics."""
    observed = bucket_statistics(excess, labels)
    unavailable = {"status": "unavailable", "reason": observed.get("reason"),
                   "observed": observed, "p_values": None, "permutations": 0}
    if observed["status"] != "complete":
        return unavailable
    if len(cells) != len(labels) or type(permutations) is not int or permutations <= 0:
        return {**unavailable, "reason": "invalid_permutation_design"}
    indices = {}
    for index, cell in enumerate(cells):
        indices.setdefault(cell, []).append(index)
    exceedances = [0, 0, 0]
    for iteration in range(permutations):
        permuted = list(labels)
        for group in indices.values():
            original = [labels[index] for index in group]
            replacement = list(shuffle(original))
            if sorted(replacement) != sorted(original):
                return {**unavailable, "reason": "invalid_label_permutation",
                        "permutations": iteration}
            for index, label in zip(group, replacement):
                permuted[index] = int(label)
        sample = bucket_statistics(excess, permuted)
        if sample["status"] != "complete":
            return {**unavailable, "reason": "unavailable_permutation_statistic",
                    "permutations": iteration}
        exceedances[0] += sample["avoid_watch"] >= observed["avoid_watch"]
        exceedances[1] += sample["buy_watch"] <= observed["buy_watch"]
        exceedances[2] += sample["omnibus"] >= observed["omnibus"]
    return {"status": "complete", "observed": observed, "permutations": permutations,
            "exceedances": exceedances,
            "p_values": [(count + 1) / (permutations + 1) for count in exceedances]}


def num(x):
    try:
        value = float(x)
        return value if np.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


rows_ex, rows_lab, rows_cell = [], [], []
for ci, f in enumerate(sorted(FILES)):
    d = json.load(open(f, encoding="utf-8"))
    iwm = num((d.get("benchmark") or {}).get("total_return"))
    if iwm is None:
        continue
    for nm in (d.get("names") or []):
        ret = num(nm.get("total_return"))
        if ret is None:
            ret = num(nm.get("forward_return"))
        if ret is None or abs(ret) > 5:        # no return, or penny artifact -> excluded
            continue
        bk = "buy_eligible" if nm.get("buy_eligible") else nm.get("bucket")
        if bk not in BCODE:
            continue
        rows_ex.append(ret - iwm)
        rows_lab.append(BCODE[bk])
        rows_cell.append(ci)

ex = np.array(rows_ex); lab = np.array(rows_lab); cellid = np.array(rows_cell)
N = len(ex)


def bmed(e, l):
    return [np.median(e[l == c]) if (l == c).any() else np.nan for c in range(4)]


B = 20000
inference = permutation_inference(ex.tolist(), lab.tolist(), cellid.tolist(),
                                  permutations=B, shuffle=rng.permutation)
ncount = {BNAME[c]: int((lab == c).sum()) for c in range(4)}
print(f"N={N}  cells={len(set(cellid.tolist()))}  bucket n={ncount}")
if inference["status"] != "complete":
    print("[PRIMARY] unavailable: " + str(inference["reason"]) + "; no p-values computed")
    raise SystemExit(0)
obs = inference["observed"]["medians"]
g_av_wa = inference["observed"]["avoid_watch"]
g_bu_wa = inference["observed"]["buy_watch"]
obs_omni = inference["observed"]["omnibus"]
print("observed median excess vs IWM: " + str({BNAME[c]: round(obs[c], 4) for c in range(4)}))
print(f"gaps: AVOID-WATCH={g_av_wa:+.4f}  BUY-WATCH={g_bu_wa:+.4f}  omnibus var-of-medians={obs_omni:.5f}")

# index list per cell
cidx = {}
for i, c in enumerate(cellid.tolist()):
    cidx.setdefault(c, []).append(i)
cidx = {k: np.array(v) for k, v in cidx.items()}

# ---- stratified within-cell permutation ----
p_av, p_bu, p_omni = inference["p_values"]
print(f"\n[PRIMARY] stratified within-cell permutation (B={B}), one-sided:")
print(f"  omnibus  'any bucket structure beyond random?'  p = {p_omni:.4f}")
print(f"  AVOID outperforms WATCH (inversion real?)        p = {p_av:.4f}")
print(f"  buy_eligible underperforms WATCH (BUY worse?)    p = {p_bu:.4f}")

# ---- cluster bootstrap CIs (resample whole cells) ----
ucells = list(cidx.keys())
Bc = 10000
bs = np.full((Bc, 4), np.nan)
for b in range(Bc):
    pick = rng.choice(ucells, size=len(ucells), replace=True)
    e = np.concatenate([ex[cidx[c]] for c in pick])
    l = np.concatenate([lab[cidx[c]] for c in pick])
    bs[b] = bmed(e, l)
print(f"\ncluster-bootstrap 95% CI of bucket median excess (B={Bc}, resample cells):")
for c in range(4):
    col = bs[:, c][~np.isnan(bs[:, c])]
    if len(col) == 0 or not np.isfinite(col).all():
        print(f"  {BNAME[c]:14} unavailable: no finite bootstrap observations")
        continue
    lo, hi = np.percentile(col, [2.5, 97.5])
    inc0 = "includes 0" if lo <= 0 <= hi else "EXCLUDES 0"
    print(f"  {BNAME[c]:14} median={obs[c]:+.3f}  95%CI[{lo:+.3f}, {hi:+.3f}]  ({inc0})")

# ---- references (clustering-naive) ----
try:
    from scipy import stats
    H, pkw = stats.kruskal(*[ex[lab == c] for c in range(4)])
    U, pmw = stats.mannwhitneyu(ex[lab == 2], ex[lab == 1], alternative="greater")
    print(f"\n[reference, ignores clustering -> anti-conservative]")
    print(f"  Kruskal-Wallis (any group differs)  H={H:.2f} p={pkw:.4g}")
    print(f"  Mann-Whitney AVOID > WATCH          p={pmw:.4g}")
except Exception as e:
    print(f"\n[reference] scipy unavailable: {e}")
