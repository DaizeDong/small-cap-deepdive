# Coverage Test — Theme: BDC (Business Development Companies / Middle-Market Lending)

- **Slug:** `bdc`
- **Sector:** Financials
- **Keywords:** `business development company, middle market lending`
- **Code-path focus:** BDC no-SIC fallback routing
- **Run batch:** `reports/smallcap/2026-06-21_cov-bdc/` (skill commit `f12fef5`, v0.3.0)
- **Date:** 2026-06-21
- **Verdict headline:** **0 BUY (clean).** Correct, expected scanner answer for this theme.

---

## 1. Funnel

| Stage | Count | Source |
|---|---|---|
| Raw universe (FTS + SIC reverse-recall floor) | 98 | `universe_bdc_2026-06-21.csv` (deep=69, watch=8, unknown=13, large=8) |
| cheap_pass survivors | 49 | `cheappass_bdc_2026-06-21.csv` |
| After kill-flag screen + SIC Gate-1 | 23 | `candidates_bdc.json` (keep=18, review=5) |
| Deep-band survivors (deep-dived, FULL — no sampling) | 18 | `candidates_bdc_deep.json` |
| Gate-2 theme members retained | 15 | LLM theme-fit (14 pure_play BDC + 1 partial REFI) |
| Mechanical BUYs | **0** | BUY rule applied to valuation blocks |
| Clean BUYs (post-adversarial) | **0** | — |

Deep-dive coverage: **18 / 18** deep-band survivors, **0 errors**, **0 ERROR.json** crashes.
Valuation produced for all 18 (CICB required a ticker re-resolution to `CION` after yfinance
returned null on `CICB`; resolved via retry, no silent skip).

> Note on RANKING.md banner: the auto-banner reads "41 → 36 → 19 → 18", which are rank.py's
> aggregate heuristic counts and do not match this run's authoritative per-stage CSV/JSON
> numbers above. Logged as a data-quality / reporting cosmetic, not a pipeline error.

---

## 2. Code-paths exercised (focus: BDC no-SIC fallback routing)

This is the headline path under test, and it fired exactly as designed:

1. **Discover — FTS + SIC reverse-recall floor.** BDCs surfaced via full-text search on the two
   keywords. BDC has no dedicated SIC code in `THEME_SIC`, so there is **no SIC recall floor**
   for this theme — the universe is FTS-driven (this is itself part of the "no-SIC" story).

2. **SIC Gate-1 — no-SIC → keep (the focus path).** `filter_by_sic.sic_classify()` returns
   `"keep"` when `sic == "nan"` (deferring to the LLM rather than auto-excluding). **15 of the 23
   candidates carried `sic=nan`** (WHF, RWAY, NMFC, SLRC, CGBD, BBDC, KBDC, GSBD, MSDL, GBDC, OTF,
   HRZN, PNNT, OCSL, CICB, TSLX) — externally-managed 1940-Act investment companies file with a
   blank SEC SIC. The no-SIC fallback correctly routed all of them to `keep` / deep-dive instead
   of dropping them. **This is the single most load-bearing path for a BDC theme** — without it,
   the entire BDC sector would be invisible to the SIC gate.

3. **Valuation — financial-structure structural fallback (the catch).** Because there is no SIC to
   key on, the v0.3.0 financial-SIC guard falls back to **structural detection**: it flags
   `financial_structure_suspected_no_sic: revenue_absent_ocf_present` and sets
   `financial_sic_fcf_unsuitable=True`, producing `buy_eligible=False` with reason
   `financial_sic_forced_unsuitable`. This fired on **all 17 financial entities** (every BDC +
   REFI mortgage-REIT + CNNE holdco). The no-SIC routing thus does the right thing at *both* ends:
   it lets BDCs IN at the gate, then the valuation layer correctly rules them OUT of the FCF/NAV
   BUY model.

4. **mktcap fallback chain.** Several BDCs priced from SEC shares×price; CICB needed manual
   ticker re-resolution (CICB→CION).

5. **Cross-source guard.** Fired on REFI, CNNE, NBBK (`cross_source_mismatch`).

6. **Signals side-channel (T2 diagnostic).** Emitted automatically and firewalled — produced no
   file in the run dir and influenced no `buy_eligible` value. Confirmed clean.

---

## 3. Gate-2 LLM theme-fit (judged from 10-K blurbs)

| Verdict | Tickers |
|---|---|
| pure_play (14) | WHF, RWAY, NMFC, SLRC, CGBD, BBDC, KBDC, GSBD, MSDL, HRZN, PNNT, OCSL, CICB, TSLX |
| partial (1) | REFI (commercial mortgage REIT / cannabis lender — a lender, not a 1940-Act BDC) |
| misrecall (3) | GRUSF (cannabis cultivator), CNNE (diversified holdco), NBBK (bank holding co.) |

The 3 misrecalls were sunk to AVOID in RANKING.md and recorded in `gate2_results.json`.

---

## 4. Ranked shortlist (15 retained theme members — all WATCH, none BUY)

All 15 are genuine BDCs/lenders that survived kill-flags and have real theme exposure, but **every
one is BUY-ineligible** because the FCF-cap / NAV intrinsic models are invalid for an
externally-managed investment company. Ranking from RANKING.md (by deepdive scorecard):

BBDC, CGBD, CICB, GSBD, HRZN, KBDC, MSDL, NMFC, OCSL, PNNT, REFI, RWAY, SLRC, TSLX, WHF.

Several show large *NAV* MoS that would have been false BUYs without the guard:
PNNT +56.9%, CICB +61.8%, RWAY +48.2%, WHF +44.6%. These are precisely the traps the
financial-SIC guard exists to neutralize — NAV-discount on a BDC is not a model-validated margin
of safety in this skill's framework.

---

## 5. BUY rule application — 0 BUYs

BUY requires: `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30` AND `buy_eligible == true` AND
zero kill-flags. Result across all 18 deep-dived:

- **17 financial entities:** `buy_eligible=False` (`financial_sic_forced_unsuitable`). Fails the
  `buy_eligible` clause outright.
- **GRUSF (the only `buy_eligible=True`):** `mos_basis=fcf_cap`, but `margin_of_safety_pct=None`
  (`mos_null_reason=intrinsic_band_unavailable` — normalized FCF is **negative** at -$1.09M, so no
  intrinsic band exists). Fails the **numeric MoS ≥ 30** clause. Not a BUY.

**Mechanical BUYs: 0.**

### Adversarial verification (the one `buy_eligible=True`: GRUSF)
> Is GRUSF a real opportunity or a data/model artifact? **Artifact + theme misrecall — not a BUY.**
> (1) Theme: GRUSF is a cannabis cultivator (SIC 100, agriculture), not a BDC — the keyword hit is
> incidental. (2) On its own merits: negative normalized FCF means there is no valuation floor; the
> `buy_eligible=True` only arises because GRUSF has a *real* operating SIC, so the financial-SIC
> guard correctly did NOT fire on it — but the FCF model then could not produce an intrinsic band,
> leaving MoS null. The BUY rule's numeric-MoS requirement is the backstop that blocks it.
> **Adversarial verdict: rejected — no actionable margin of safety, wrong theme.**

n_buy_clean = **0**.

---

## 6. Data-quality issues

- **CICB → CION ticker resolution.** yfinance returned null for `CICB`; market cap only resolved
  after re-running valuation with `--ticker CION`. A coverage gap in the ticker-resolution layer.
- **RANKING.md banner counts** (41/36/19/18) are rank.py aggregate heuristics, not this run's
  per-stage funnel — cosmetic mismatch.
- **GRUSF buy_eligible=True with null MoS** is a latent footgun: `buy_eligible` can be True while
  MoS is None. The BUY rule's separate numeric-MoS clause catches it, but a consumer reading
  `buy_eligible` alone would be misled. Worth a guard that forces `buy_eligible=False` when MoS is
  null.
- **Empty blurbs** for NMFC, BBDC, GBDC, OTF (FTS returned no business-description snippet) —
  theme-fit judged from name + known sector; low risk for well-known BDCs.

---

## 7. recall@gold

**n/a.** BDC is not in `THEME_GOLD` (only deathcare, water-utilities, railcar-leasing,
regional-gaming have gold cohorts). `track_forward.py --recall-gold` not run.

---

## 8. Market-intel / T2 context

TrendsMCP quota exhausted for the day (5/5 daily, 100/100 monthly) — no trend enrichment this run.
market-intel not invoked. T2 color is optional and never drives `buy_eligible`; its absence does
not affect the mechanical verdict. Qualitatively: BDCs are a well-covered, dividend-yield-driven
sub-sector trading on NAV discounts and net-investment-income — exactly the kind of "neglected ≠
undervalued" / NAV-trap profile the skill is designed to refuse to call a BUY.

---

## 9. Skeptical-PM usable verdict

**Usable: YES.** The run is a clean, correct demonstration of the BDC no-SIC fallback routing
under test. The fallback let all 16 SIC-less BDCs into the funnel (recall preserved), then the
v0.3.0 financial-SIC structural guard correctly disqualified every one from the FCF/NAV BUY model —
including the four with tempting NAV discounts (PNNT/CICB/RWAY/WHF). The single `buy_eligible=True`
(GRUSF) is a theme misrecall with negative FCF and is correctly blocked by the numeric-MoS clause.
**0 clean BUYs is the right answer.** Minor caveats: the CICB ticker-resolution gap and the
`buy_eligible=True`-with-null-MoS footgun should be tracked, but neither produced a false BUY.
