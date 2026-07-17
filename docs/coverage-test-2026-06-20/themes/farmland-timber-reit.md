# Coverage Test, farmland-timber-reit (RealEstate / niche-REIT NAV)

- **Run batch:** `reports/smallcap/2026-06-21_cov-farmland-timber-reit/`
- **Skill version:** v0.3.0, commit `f12fef5` (run manifest records `skill_dirty: true`)
- **Theme keywords:** `farmland REIT, timber REIT, agricultural land`
- **Code-path focus:** NAV / niche-REIT routing; financial-SIC FCF-unsuitability guard (SIC 6798);
  cyclical NAV fallback; ag-grower vs REIT discrimination.
- **System date during run:** 2026-06-21 (one day after the `2026-06-20` batch label; harmless).

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| discover (small-cap universe, ≤$2.0B) | 47 | FTS recall on the 3 keywords. No SIC reverse-recall floor, theme not in `THEME_SIC` (opt-in; expected no-op). |
| cheap_pass survivors | 34 | kill-flag eliminations applied; 1 transient timeout on CSIQ killflag (recovered, not silent-skipped). |
| SIC gate output (candidates JSON) | 34 | 17 `keep`, 17 `review` → all 34 forwarded. |
| of which **deep band** (≤$2.0B) | 24 | the names that earn a full deep-dive. |
| of which **watch band** ($2 to 5B) | 10 | out of deep-dive scope. |
| **LLM theme-fit (Gate 2) survivors** | **6** | I judged true membership from blurbs; 18 deep-band names dropped as misrecall. |
| deep-dived (deepdive_data + valuation) | 6 | every Gate-2 survivor, no sampling. |
| **mechanical BUYs** | **0** | |
| **clean BUYs (post-adversarial)** | **0** | |

`finalize_run` completeness: **deep-band 24, reports 6, gate2-misrecall resolved 18, missing 0.**
No `deepdive_*_ERROR.json` produced. recall@gold = **n/a** (no gold list for this theme).

### Gate-2 theme-fit decisions (the discriminating step)

The FTS over-recalled hard, the keyword "agricultural land" pulls in every ag-grower, ag-bank,
ag-mortgage, and ag-adjacent name. My membership calls (theme = land/farmland/timber **owner**,
NAV-valued):

**Retained, pure_play (true farmland/ag REIT):**
- **LAND** (Gladstone Land, SIC 6798), externally-managed agricultural REIT owning/leasing farmland.
- **FPI** (Farmland Partners, SIC 6798), internally-managed REIT owning N. American farmland.

**Retained, partial (substantial ag-land ownership, NAV-relevant, not a REIT):**
- **ALCO** (Alico, SIC 0100), agribusiness/land-management; owns ~49,537 acres FL land (citrus + land development).
- **LMNR** (Limoneira, SIC 0100), CA citrus/avocado grower; land-rich (acreage + real estate).
- **LND** (BrasilAgro, SIC 0100, 20-F), "Brazilian Agricultural Real Estate Co"; buys/develops/sells farmland.
- **MLP** (Maui Land & Pineapple, SIC 6500), Hawaii land owner (~22,300 acres), real-estate dev/sales.

**Dropped, misrecall (18):** MED (weight-loss), GWRS/ARTNA (water utilities), SND (frac sand),
AVO/DOLE (fresh-produce distributors, asset-light, no land NAV), MUX (gold mining), ITMSF (mapping
tech), MOB (drone/defense), CSIQ (solar), CZFS/LARK/FRAF/PLBC/CWBC/ALRS/HBT (community banks,
SIC 602x), **AGM** (Farmer Mac, agricultural-mortgage finance, SIC 6111; a financial, not a land owner).

> Note: AGM would also be caught by the financial-SIC guard at valuation, but Gate 2 correctly
> removes it earlier as off-theme (it owns loans, not land).

---

## 2. Ranked shortlist (from RANKING.md)

| Rank | Ticker | Rating | Conf | mos_basis | numeric MoS | buy_eligible | killflags | Membership |
|---|---|---|---|---|---|---|---|---|
| 1 | LAND | 观察 watch | 45 | nav | NAV +47% | **false** | 0 | pure_play |
| 2 | LND | 观察 watch | 35 | fcf_cap | null | true | 0 | partial |
| 3 ⬇ | MLP | 避开 avoid | 60 | nav | NAV −93% | true | 0 | partial |
| 4 ⬇ | FPI | 避开 avoid | 55 | nav | NAV −100% | false | 1 (mat. weakness) | pure_play |
| 5 ⬇ | LMNR | 避开 avoid | 55 | fcf_cap | −125% | false | 0 | partial |
| 6 ⬇ | ALCO | 避开 avoid | 50 | fcf_cap | null | false | 1 (mat. weakness) | partial |

---

## 3. BUY rule application, honest 0-BUY

**BUY = mos_basis ∈ {fcf_cap, nav} AND numeric MoS ≥ 30 AND buy_eligible==true AND zero kill-flags.**
Every name fails at least one clause:

- **LAND**, NAV MoS **+47%** (≥30 ✔), but `buy_eligible=false`: vetoed by three v0.3.0 guards ,
  `financial_sic_forced_unsuitable` (SIC 6798 → FCF model unsuitable), `fundamental_decline_flag`
  (rev slope −1, contamination 0.23, latest below avg), and `cross_source_mismatch`
  (SEC rev 12.2M vs yfinance 88.0M, 7.2x). The attractive-looking NAV MoS is **exactly the trap the
  guards exist to catch**: book-equity-proxy NAV on a farmland REIT whose own revenue series is
  internally inconsistent across sources. Correctly NOT a BUY.
- **FPI**, NAV MoS **−100%** (fails ≥30) and `buy_eligible=false` (`financial_sic_forced_unsuitable`)
  and 1 kill-flag (material_weakness). Trades far above book NAV. Not a BUY.
- **ALCO**, MoS null (`buy_eligible=false`: `cross_source_mismatch`; SEC rev 44.1M vs yf 16.4M),
  plus `low_revenue_loss_ratio` (latest NI −147.3M vs rev 44.1M = 3.3x), lumpy OCF, 1 kill-flag. Not a BUY.
- **LMNR**, fcf_cap MoS **−125%** (`extreme_mos_review_required`, `buy_eligible=false`), negative
  earnings, lumpy OCF. Not a BUY.
- **LND**, `buy_eligible=true`, **but numeric MoS = null** (`intrinsic_band_unavailable`; the 20-F
  exposes no usable cash/debt/D&A/capex series → no intrinsic band can be formed). Fails the
  "numeric MoS ≥ 30" clause. Not a BUY, and rightly so: you cannot value what you cannot read.
- **MLP**, `buy_eligible=true`, mos_basis nav, **NAV MoS = −93%** (price ≈ 14x tangible book NAV).
  Fails ≥30 by a wide margin. Not a BUY.

**Result: 0 mechanical BUYs, 0 clean BUYs.** No adversarial verification needed (nothing to defend),
but see §4 for the one name (LAND) whose surface NAV MoS could mislead a less-disciplined screen.

---

## 4. Adversarial check on the only "attractive" surface number (LAND)

LAND is the one name where a naive NAV screen would shout BUY (NAV MoS +47%). Is that real or artifact?

- **Artifact.** The NAV is a **book-equity proxy** (`nav_goodwill_or_intangibles_unavailable:
  tangible_equity_uses_book_equity_proxy`). For a farmland REIT, book equity reflects depreciated
  historical cost of land/improvements, not the mark-to-market land value that an actual NAV thesis
  would need, so the "+47% discount to NAV" is a discount to an accounting number, not to appraised
  land value. Could break either direction.
- **Corroborating veto:** `cross_source_mismatch` (7.2x revenue disagreement) means the data layer
  itself does not trust the financials feeding this valuation. The `fundamental_decline_flag`
  (declining rent/revenue trajectory) further argues against treating the book discount as upside.
- **Verdict:** the v0.3.0 financial-SIC + cross-source + decline guards **correctly** prevented a
  false BUY here. A real farmland-REIT NAV thesis requires per-acre appraisal data the skill does
  not ingest, this is a known coverage gap, not a missed opportunity. **No clean BUY.**

---

## 5. Which code-paths fired (the point of the test)

- **financial-SIC FCF-unsuitability guard (SIC 6798):** fired on both REITs (LAND, FPI) →
  `financial_sic_fcf_unsuitable`, routing them to NAV basis and blocking fcf_cap BUYs. ✔ As designed.
- **NAV routing / book-equity-proxy NAV:** exercised on LAND, FPI, MLP (`mos_basis=nav`,
  `nav_intrinsic_band` computed from tangible-equity proxy). ✔ niche-REIT path covered.
- **cross_source_mismatch guard:** fired on LAND (7.2x) and ALCO (2.7x) → both vetoed. ✔
- **fundamental_decline_veto:** fired on LAND (rev slope −1, latest below 5y avg). ✔
- **extreme_mos_review_required:** fired on LMNR (−125% MoS > 100%). ✔
- **low_revenue_loss_ratio:** fired on ALCO (|NI|/rev = 3.3x). ✔
- **lumpy_ocf_normalization_suspect:** fired on ALCO and LMNR. ✔
- **cyclical normalization:** MLP routed cyclical (cv_ebitda 12.5 > 0.25) → trailing-5yr-avg
  normalized FCF, then `fcf_cap_blocked_by_c1_data_quality_guard` → NAV fallback. ✔
- **debt_stale guard:** fired on MLP (>18 months behind latest assets). ✔
- **20-F / data-poverty abstain:** LND (20-F) produced `intrinsic_band_null` → MoS null → no BUY,
  rather than fabricating a number. ✔ correct abstain discipline.
- **SIC reverse-recall floor:** NOT fired, theme absent from `THEME_SIC` (opt-in). Expected no-op;
  recall fell back to FTS-only. (Farmland/timber REITs do share SIC 6798 with all equity REITs, so a
  floor on 6798 would be far too broad to be useful, the design choice to leave it opt-in is sound here.)
- **Gate-2 misrecall resolution path:** 18 deep-band names resolved via
  `candidates_gate2_survivors.json` → `finalize_run` reported 0 missing (no spurious warning). ✔

---

## 6. Data-quality issues observed

1. **Pervasive cross-source revenue disagreement on ag names**, SEC vs yfinance revenue differs
   2.7x (ALCO) to 7.2x (LAND). Root cause: ag-grower/REIT revenue recognition + yfinance using a
   different consolidation/segment than SEC XBRL. The guard catches it, but it means **fundamentals
   for this whole pocket are low-trust** without manual XBRL reconciliation.
2. **Book-equity-proxy NAV on every REIT/land name**, no goodwill/intangible breakout available, so
   tangible equity = book equity. For farmland the *relevant* NAV (appraised per-acre land value) is
   simply not in the ingested data. Structural coverage gap for this theme.
3. **LND (20-F) data poverty**, cash/debt/D&A/capex all unavailable; EV = market-cap-only. The skill
   correctly abstains rather than guesses, but it means foreign ag-real-estate names are effectively
   un-valuable on the current pipeline.
4. **One transient EDGAR timeout** (CSIQ killflag) during cheap_pass, recovered via the pipeline's
   own handling; no silent skip; CSIQ was a misrecall anyway.
5. **RANKING.md cosmetic count quirk**, header reads "7 家逐一 deep dive → 幸存 6"; actual deep-dive
   count is 6 throughout (candidates, reports, verdicts). No downstream effect.

---

## 7. recall@gold

**n/a**, `farmland-timber-reit` is not in `THEME_GOLD`. `track_forward.py --recall-gold` returns
"no gold list for theme … → not measurable." (Confirmed by running it.) The 4 gold-list themes are
water-utilities, railcar-leasing, regional-gaming, deathcare.

---

## 8. Market-intel / Trends (T2 analyst context, labeled, does NOT drive any BUY)

- **TrendsMCP:** quota exhausted for the day/month at run time (5/5 daily, 100/100 monthly), no
  external search-volume series available for "farmland REIT" / "farmland investment". Not blocking;
  T2 never feeds `buy_eligible`.
- **market-intel cache** (`~/CodesSelf/market-intel`): no cached coverage of
  farmland/timber/ag-REIT names found.
- **Firewalled T2 signals already embedded per name** (diagnostic only, from the deepdive JSONs):
  - LAND: divergence `aligned`, 6m +0.8%, 12m −9.0%.
  - FPI: divergence `unpriced_improvement`, 6m −3.0%, 12m −10.1% (fundamentals up, tape down, note,
    but FPI is still a non-BUY on guards + material weakness).
  - ALCO: `aligned`, 6m +8.1%, 12m +29.3%.
  - LMNR: `aligned`, 6m −12.9%, 12m −10.8%.
  - LND: `unclear`, 6m −0.8%, 12m −10.1%.
  - MLP: `aligned`, 6m +9.2%, 12m +6.9%.
  These are context only and (correctly) changed no rating.

---

## 9. Skeptical-PM verdict: is this run USABLE?

**Yes, usable, and a clean pass for the niche-REIT/NAV code-path.** The pipeline:
- enumerated the universe, correctly separated 2 genuine farmland REITs + 4 ag-land NAV plays from
  18 ag-adjacent misrecalls (banks, distributors, miners, a mortgage GSE);
- routed both REITs to NAV basis via the financial-SIC guard;
- produced **zero false BUYs**, with the one seductive number (LAND's +47% book-NAV discount)
  correctly vetoed by cross-source + decline guards rather than waved through;
- abstained (not fabricated) on the data-poor 20-F name (LND);
- closed completeness with 0 missing.

The honest takeaway for a PM: **there is no clean small-cap BUY in this pocket on the current data**,
and the binding reason is structural, a real farmland/timber NAV thesis needs appraised per-acre land
values that SEC XBRL does not carry. The skill is doing its job as a landmine-scanner: it eliminated
the off-theme names and refused to manufacture a BUY from a book-value artifact. **No name here
warrants capital without manual per-acre NAV work + XBRL revenue reconciliation.**
