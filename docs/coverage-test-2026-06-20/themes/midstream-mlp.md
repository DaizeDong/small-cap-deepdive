# Coverage Test — Theme: midstream-mlp

- **Theme keywords:** `midstream, pipeline, gathering and processing`
- **Sector:** Energy
- **Code-path focus:** MLP distributions / financial routing
- **Skill version:** small-cap-deepdive v0.3.0 (commit `f12fef5`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-midstream-mlp/`
- **Date:** 2026-06-21
- **Verdict:** **0 BUY** (0 clean). Correct, expected, and a feature — see PHILOSOPHY.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw FTS recall (small-cap band) | 137 | EDGAR full-text on `midstream` / `pipeline` / `gathering and processing` |
| **SIC reverse-recall floor** | **n/a** | `midstream-mlp` is **NOT** in `THEME_SIC` → `theme_sics()` returns `[]`. FTS-only recall (graceful degrade, opt-in by construction). |
| cheap_pass survivors | 87 | 50 eliminated on hard kill-flags (going-concern / death-spiral / ICFR≥2) |
| SIC Gate-1 (keep/review) | 87 | keep=69, review=18 (review forwarded to LLM, not dropped) |
| Candidates written | 87 | band: deep=55, watch=31, unknown=1 |
| **Deep band (full deep-dive pool)** | **55** | the names that earn an LLM theme-fit pass + deep-dive |
| **Gate-2 LLM theme-fit retained** | **8** | 3 pure_play + 5 partial. 47 misrecall dropped (resolved, not missing). |
| Deep-dived + valued | 8 | every theme-fit deep-band survivor — no sampling |
| **Mechanical BUY** | **0** | every survivor fails the BUY rule |
| BUY surviving adversarial check | 0 | n/a (no mechanical BUYs to challenge) |

**mos_basis distribution (8 valued):** `fcf_cap` = 6, `nav` = 1, `abstain` = 1.

---

## 2. The dominant data-quality story: "pipeline" is a polluted keyword

The deep band (55) was overwhelmingly off-theme. The LLM theme-fit gate (Gate 2) is doing the
load-bearing precision work here, exactly as designed:

- **47 / 55 misrecalls (85%).** Two large misrecall clusters:
  1. **Biotech drug "pipeline"** — 14 names (ATNM, ADCT, ABCL, ABUS, VYGR, MGNX, IRD, NVAX, RXRX,
     EPRX, STTK, ASMB, CTNM, IMCR). SIC 2834/2836. This is the canonical "refractory swept oncology"
     failure mode reappearing through the word *pipeline*. Gate-1 SIC tagged these `review` (pharma is
     hard-exclude), and the LLM correctly killed them.
  2. **Upstream E&P** — ~20 names (BATL, EPM, PNRG, WTI, VTS, TXO, REPX, HPK, DEC, MXC, USEG, EPSN,
     AMPY, INR, GRNT, REI, OBE, GFR, VET, KGEI). SIC 1311. These hit the keyword via "gathering &
     processing of our own production" or having an upstream MLP structure (TXO Partners is an
     **upstream** MLP, not midstream — a classic trap the gate caught).
  3. Long tail: shipping (NMM), lodging (CVEO), marine/heavy construction (ORN, NOA), NDT inspection
     (MG), ethanol (REX), renewables generation (XIFR), utility (UTL), asset mgmt (WHG), e-commerce
     (GCT), BDC finance (NMFC), holding co (ACTG), solar (SUUN).

- **8 true theme members survived Gate 2** (3 pure_play + 5 partial):
  SMC, GEL, WBI (pure midstream); OPAL, SLNG, RGCO, MTRX, ESOA (partial / midstream-adjacent
  services & logistics).

**Coverage observation (this is the point of the test):** because there is **no dedicated
midstream SIC in `THEME_SIC`**, recall rested entirely on FTS + the LLM gate. Midstream pipeline
SICs that *would* be natural floor candidates (`4610` pipelines, `4922` natural-gas transmission,
`4924` natural-gas distribution) exist in the universe (GEL=4610, SMC=4922, SLNG=4924) but the floor
was a no-op. The pipeline handled this gracefully — no crash, no silent drop — but a low-FTS-density
midstream micro-cap could be missed. This is the documented opt-in design, surfaced honestly.

---

## 3. Ranked shortlist (all WATCH / AVOID — no BUY)

| Rank | Ticker | Name | Rating | mos_basis | MoS | buy_eligible | kill-flags | Why not BUY |
|---|---|---|---|---|---|---:|---:|---|
| 1 | ESOA | Energy Services of America | 观察 WATCH | fcf_cap | **-96.4%** | True | 0 | MoS deeply negative — priced far above intrinsic FCF band |
| 2 | MTRX | Matrix Service | 观察 WATCH | nav | **-42.5%** | True | 0 | FCF model unsuitable → NAV path; NAV MoS negative |
| 3 | OPAL | OPAL Fuels | 观察 WATCH | fcf_cap | **null** | True | 0 | Normalized FCF non-positive → intrinsic band unavailable |
| 4 | RGCO | RGC Resources | 观察 WATCH | fcf_cap | **null** | True | 0 | Normalized FCF non-positive → intrinsic band unavailable |
| 5 | SMC | Summit Midstream | 观察 WATCH | fcf_cap | -313.8% | **False** | 0 | `extreme_mos_review_required` (heavy net debt vs equity FCF) |
| 6 | WBI | WaterBridge Infrastructure | 观察 WATCH | fcf_cap | -140.5% | **False** | 0 | `extreme_mos_review_required` + `fcf_sustainability_uncertain` (OCF proxy, capital-intensive) |
| 7 ⬇ | GEL | Genesis Energy LP | 避开 AVOID | abstain | n/a | **False** | 0 | **V-shape veto:** `fundamental_decline_flag` + `peak_contamination_flag` |
| 8 ⬇ | SLNG | Stabilis Solutions | 避开 AVOID | fcf_cap | -98.6% | **False** | 1 | `cross_source_mismatch` (debt SEC 5.8M vs yf 29.3M, 5.1×) + 1 kill-flag |

---

## 4. BUY-rule reasoning per survivor

The BUY rule (v0.3.0): `mos_basis ∈ {fcf_cap, nav}` **AND** numeric MoS ≥ 30% **AND**
`buy_eligible == true` **AND** zero kill-flags. Every survivor fails on at least one leg.

- **ESOA** — basis `fcf_cap` ✓, but MoS = -96.4% (FAIL ≥30%). EV/EBITDA null (D&A unavailable),
  lumpy-OCF normalization suspect (peak OCF 21.1M > 2× median 6.2M) corroborated by contamination
  0.39. A pipeline-construction *contractor*, not an asset-owning MLP — fits theme only partially.
- **MTRX** — FCF model unsuitable (`debt_stale` > 18mo behind assets triggered the C1 guard) →
  routed to NAV. NAV MoS = -42.5% (trades **above** tangible book of $282M). Net-income negative,
  EBITDA negative. A services name with a peaky cycle (contamination 4.10).
- **OPAL** — basis `fcf_cap`, but normalized FCF is negative (-$86M) → no intrinsic band, MoS null
  (FAIL: needs numeric ≥30%). Heavy growth-capex RNG build-out; not a distributable-cash MLP yet.
- **RGCO** — basis `fcf_cap`, normalized FCF -$3M (non-positive) → MoS null (FAIL). A regulated gas
  utility with a Midstream subsidiary (MVP JV exposure); cyclical CV 0.50 is utility-rate noise.
- **SMC** — `buy_eligible = False` via `extreme_mos_review_required` (MoS -313.8%). EV $1.62B on
  $398M equity — the FCF-to-equity bridge is swamped by leverage; the extreme-MoS guard correctly
  refuses to print a number that large. **This is the cleanest pure-play midstream name and it still
  cannot pass** — leverage is the binding constraint, not theme fit.
- **WBI** — `buy_eligible = False` (extreme-MoS -140.5% + FCF-sustainability). Capex unavailable →
  FCF = OCF proxy on a 7.1× assets/revenue capital-intensive base; the guard distrusts that proxy.
  Recent IPO (Sept 2025) → only 3yr normalization, insufficient history.
- **GEL** — `buy_eligible = False` via the **V-shape value-trap vetoes**: `fundamental_decline_flag`
  (revenue slope negative, latest below 5yr avg) **and** `peak_contamination_flag` (trough→peak→
  rollover, latest net income -$440M). FCF model unsuitable (debt/assets 0.69 > 0.62) and NAV also
  unavailable → `mos_basis = abstain`. Correctly sunk to AVOID.
- **SLNG** — `buy_eligible = False` via `cross_source_mismatch`: SEC total_debt $5.8M vs yfinance
  $29.3M (5.1×, >2.5× threshold) — a hard data-integrity block on BUY. Plus 1 cheap_pass kill-flag.
  MoS -98.6% regardless.

---

## 5. BUYs and adversarial verification

**None.** There are zero mechanical BUYs, so there is nothing to adversarially confirm or refute.
`n_buy_clean = 0`.

Honest 0-BUY interpretation: the small-cap midstream universe right now is **levered or
cyclically-impaired, not cheap**. The single best pure-play (Summit Midstream, SMC) is a real
midstream G&P operator with a non-cyclical EBITDA profile (CV 0.095, norm EBITDA $206M, EV/EBITDA
7.85×) — but its equity is a thin sliver under $1.62B EV, so the equity-FCF margin-of-safety math
blows out past the extreme-MoS guard. That is the structurally correct read for a high-leverage MLP:
the *enterprise* may be sound while the *equity* carries the risk. The scanner declining to call it a
BUY is the tool working as designed, not a miss.

---

## 6. Code-paths exercised (this run's evidence)

- **SIC reverse-recall floor — graceful no-op.** `theme_sics("midstream-mlp") == []`. Recall fell back
  to FTS-only; pipeline did not crash and did not silently drop. (Negative-coverage path confirmed.)
- **SIC Gate-1 tri-state** (`sic_classify`): keep=69 / review=18. Pharma SIC 2834/2836 routed to
  `review` (not dropped) → handed to LLM, which killed them. The keep+review→LLM safety net held.
- **Gate-2 LLM theme-fit** + **finalize_run misrecall resolution**: 47 misrecalls read from
  `gate2_results.json` and subtracted from the completeness check → 0 missing, no spurious warning.
- **MLP distribution / financial-routing focus (the assigned code path):**
  - `mos_basis` routing across all three branches in one run: `fcf_cap` (6), `nav` (1), `abstain` (1).
  - **FCF-model-unsuitable → NAV fallback** fired on MTRX (debt_stale C1 guard) and GEL (debt/assets
    0.69 > 0.62 ceiling).
  - **NAV path** computed for MTRX (tangible equity $282M, NAV band $226M–$297M).
  - **abstain** reached on GEL when both FCF-cap and NAV were unavailable.
  - **OCF-proxy-for-FCF** path (capex unavailable) on WBI + GEL, with the
    `fcf_sustainability_uncertain` guard firing on WBI's capital-intensive base.
- **buy_eligible guards that fired:** `extreme_mos_review_required` (SMC, WBI),
  `fcf_sustainability_uncertain` (WBI), `fundamental_decline_flag` + `peak_contamination_flag`
  (GEL, V-shape vetoes), `cross_source_mismatch` (SLNG, second-source debt check).
- **cheap_pass kill-flags:** 50 eliminated pre-deep-dive; 1 residual kill-flag carried on SLNG.
- **Signals side-channel (firewalled):** `price_divergence` / `ownership` / `signals_meta` emitted
  into every deepdive JSON; `buy_eligible` computed independently in valuation.py. No signal touched
  any BUY decision. Firewall confirmed.

---

## 7. Data-quality issues observed

- **No SIC recall floor for this theme** — the structural coverage gap (see §2). A low-keyword-density
  micro-cap midstream operator could escape recall. Recommend adding `midstream`/`pipeline` →
  `["4610","4922","4924"]` to `THEME_SIC` if midstream becomes a tracked theme.
- **Empty business blurbs** for several names (VTS, TXO, HPK, SUUN, KGEI, OBE, NMFC, VET, EPRX) —
  Gate-2 classification for these relied on issuer identity / SIC rather than blurb text. All nine
  were E&P/biotech/finance misrecalls; none were plausible midstream members, so the empty-blurb
  fallback did not change the retained set.
- **`debt_stale`** on MTRX and GEL (debt > 18 months behind latest assets) — triggered the C1
  data-quality guard and forced the NAV path; correct conservative behavior.
- **`cross_source_mismatch`** on SLNG — SEC vs yfinance debt disagreement 5.1× — exactly the
  integrity block the second-source check exists for.
- **`concentration_unquantified`** (text flag true, XBRL magnitude null) on RGCO, OPAL, MTRX, WBI —
  flagged but not BUY-blocking absent a quantified magnitude.
- **Lumpy-OCF normalization suspect** on ESOA, OPAL, WBI — peak-year OCF > 2× median of others;
  normalization confidence appropriately discounted.

---

## 8. recall@gold

**n/a.** `midstream-mlp` has no hand-built gold list (the gold cohorts are water-utilities,
railcar-leasing, regional-gaming, deathcare). `track_forward.py --recall-gold --theme midstream-mlp`
returns `no gold list for theme 'midstream-mlp' → not measurable`. Recorded as n/a, not zero.

---

## 9. Market-intel / T2 analyst context (does NOT drive buy_eligible)

TrendsMCP, labeled T2 only:
- **News sentiment** for "midstream pipeline natural gas": 12M +312% (16.8 → 69.3), 3M +24%
  (56.0 → 69.3). A constructive, improving macro narrative for the sector.
- **News volume:** flat 12M and 3M.

Read: the sector backdrop is improving, which *raises*, not lowers, the bar for a mechanical BUY —
a rising-sentiment sector with zero clean cheap small-caps means the obvious value has likely been
priced. This is T2 color for a human PM; it had **no** effect on any buy_eligible computation.

---

## 10. Skeptical-PM usable verdict

**Usable: YES.** The run is internally consistent, the funnel is fully auditable, every deep-band
survivor was deep-dived with no `_ERROR.json`, and the 0-BUY outcome is well-explained by leverage
(SMC), capital-intensity / negative normalized FCF (WBI, OPAL, RGCO), trades-above-book (MTRX,
ESOA), and a clean V-shape veto (GEL) plus a data-integrity block (SLNG).

The output is precisely what the tool promises: a **landmine scanner**, not a buy list. It correctly
flushed an 85%-polluted "pipeline" keyword universe down to 8 true members and then declined to bless
any of them. A PM would take SMC and GEL onto a watchlist for a leverage-normalization / cyclical-
trough revisit, and would note the missing SIC floor as the one coverage caveat for this theme.

**Funnel:** 137 raw → 55 deep → 8 survivors → 0 BUY (0 clean). **Hotness: cold.**
