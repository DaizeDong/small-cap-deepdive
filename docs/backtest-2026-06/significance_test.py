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
import json, glob
import numpy as np

rng = np.random.default_rng(42)
FILES = [f for f in glob.glob("reports/smallcap/backtest/*_*.json")
         if "_covid" not in f and "_run" not in f]
BCODE = {"buy_eligible": 0, "WATCH": 1, "AVOID": 2, "abstain": 3}
BNAME = ["buy_eligible", "WATCH", "AVOID", "abstain"]


def num(x):
    try:
        return float(x)
    except Exception:
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


obs = bmed(ex, lab)
ncount = {BNAME[c]: int((lab == c).sum()) for c in range(4)}
print(f"N={N}  cells={len(set(cellid.tolist()))}  bucket n={ncount}")
print("observed median excess vs IWM: " + str({BNAME[c]: round(obs[c], 4) for c in range(4)}))
g_av_wa = obs[2] - obs[1]
g_bu_wa = obs[0] - obs[1]
obs_omni = float(np.var([obs[c] for c in range(4)]))
print(f"gaps: AVOID-WATCH={g_av_wa:+.4f}  BUY-WATCH={g_bu_wa:+.4f}  omnibus var-of-medians={obs_omni:.5f}")

# index list per cell
cidx = {}
for i, c in enumerate(cellid.tolist()):
    cidx.setdefault(c, []).append(i)
cidx = {k: np.array(v) for k, v in cidx.items()}

# ---- stratified within-cell permutation ----
B = 20000
ge_av = le_bu = ge_omni = 0
for _ in range(B):
    plab = lab.copy()
    for idx in cidx.values():
        plab[idx] = rng.permutation(lab[idx])
    pm = bmed(ex, plab)
    if (pm[2] - pm[1]) >= g_av_wa:
        ge_av += 1
    if (pm[0] - pm[1]) <= g_bu_wa:
        le_bu += 1
    if float(np.var([pm[c] for c in range(4)])) >= obs_omni:
        ge_omni += 1
p_av = (ge_av + 1) / (B + 1)
p_bu = (le_bu + 1) / (B + 1)
p_omni = (ge_omni + 1) / (B + 1)
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
