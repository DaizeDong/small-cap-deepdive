# Coverage Test — Restaurants (ConsDisc)

- **Slug:** `restaurants`
- **Sector:** Consumer Discretionary
- **Keywords:** `restaurant chains, quick service, casual dining`
- **Code-path focus:** unit-economics / lease-heavy operators
- **Skill version:** v0.3.0 (commit `f12fef5`, run manifest reports `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-restaurants/`
  (`new_run.py` stamped the dir `2026-06-21` from the system clock; the task slug was cov-restaurants)
- **Outcome:** **0 BUY.** Correct, expected scanner result — the small-cap restaurant universe is fully valued; no clean industrial beneficiary cleared the BUY contract.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| FTS raw recall | 169 | EDGAR full-text on the 3 keyword phrases (forms 10-K/10-Q/20-F/40-F) |
| — deep band (<$2.0B) | 67 | market-cap resolved |
| — watch band ($2.0–5.0B) | 10 | theme-fit only, no deep-dive (out of small-cap scope) |
| cheap_pass survivors | 43 | mechanical health screen (going-concern / death-spiral / ICFR / concentration) |
| SIC gate (Gate 1) | 43 | keep=12, review=31 — **no drops** (review forwarded to LLM gate) |
| **Deep band into theme-fit** | **36** | the candidates that are small-cap AND survived cheap_pass |
| **LLM theme-fit KEEP** | **19** | true restaurant operators (pure-play + partial) |
| LLM theme-fit MISRECALL | 17 | off-theme keyword sweeps (REITs, banks, CPG, packaging, tech) |
| Deep-dived (data + valuation) | 19 | **every** deep-band survivor, no sampling — 0 errors |
| **Mechanical BUY** | **0** | none cleared MoS≥30 + buy_eligible + 0 kill-flags |

`recall@gold`: **n/a** — restaurants is not one of the four seeded gold themes
(water-utilities / railcar-leasing / regional-gaming / deathcare). `track_forward.py --recall-gold`
returns "no gold list for theme 'restaurants' → not measurable", and `theme_gold('restaurants')` → `[]`.
There is also no SIC recall floor for SIC 5812 in `THEME_SIC`, so discovery here is FTS+mktcap-fallback
only (no SIC reverse-recall channel fired). This is by design for an unseeded theme.

---

## 2. Theme-fit gate (LLM membership judgment)

I judged true membership from the Item-1 business blurbs.

**KEEP — pure-play restaurant operators (16):**
JACK (Jack in the Box + Del Taco, QSR), PTLO (Portillo's, fast casual), NATH (Nathan's Famous,
QSR/franchise), DIN (Dine Brands — IHOP/Applebee's franchisor, casual), LOCO (El Pollo Loco, QSR),
KRUS (Kura Sushi, casual), CBRL (Cracker Barrel, casual), BJRI (BJ's Restaurants, casual),
PZZA (Papa John's, QSR pizza), WEN (Wendy's, QSR), SG (Sweetgreen, fast casual), BDL (Flanigan's,
restaurants + package liquor — majority restaurant), NDLS (Noodles & Co, fast casual),
BRCB (Black Rock Coffee Bar, drive-thru QSR), FWRG (First Watch, daytime casual), DNUT (Krispy Kreme,
QSR doughnut — no blurb, classified on well-known business).

**KEEP — partial (restaurant exposure material) (3):**
PLAY (Dave & Buster's — eatertainment, large dining revenue), RICK (RCI Hospitality — adult
entertainment + dining), BH (Biglari Holdings — holding co whose largest subs are restaurants
(Steak 'n Shake), but also P&C insurance — the insurance leg is exactly what the guard catches).

**MISRECALL — dropped (17):**
WFCF (food-verification SaaS, SIC 7372), TRC (Tejon Ranch real-estate dev), LYTS (LSI Industries
lighting), LUCK (Lucky Strike bowling/FEC), SENEA (Seneca Foods packaged-food mfr), SVC (Service
Properties Trust REIT), IDT (fintech/telecom), NTST (NETSTREIT net-lease REIT), GTY (Getty Realty
net-lease REIT), TACT (TransAct tech/printers), HAIN (Hain Celestial CPG), FVR (FrontView REIT),
KRT (Karat Packaging foodservice packaging), VYX (NCR Voyix commerce tech), ARKO (c-store/fuel),
PRHI (insurance holdco), AMTB (bank).

This is the canonical over-recall pattern the two-stage gate exists to catch: "restaurant"/"dining"
as an FTS term sweeps net-lease REITs (their tenants are restaurants), foodservice packaging,
restaurant-POS tech, and food manufacturers. Gate 1 (SIC) kept all of them as "review"; the LLM gate
removed them. Recorded via `candidates_gate2_survivors.json` so finalize_run treats the 17 as
resolved-by-gating (not missing deep-dives) — 0 missing reports.

---

## 3. BUY rule application — every deep-band survivor

BUY requires: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric MoS ≥ 30% **AND** `buy_eligible == true`
**AND** zero kill-flags. `buy_eligible` already ANDs the v0.3.0 guards.

| Tkr | KF | mos_basis | MoS% | buy_eligible | gating reason(s) |
|---|---:|---|---:|---|---|
| CBRL | 0 | fcf_cap | **−55.1** | ✅ true | fails MoS gate (overvalued) |
| KRUS | 0 | fcf_cap | null | ✅ true | fails MoS gate (no positive MoS) |
| NATH | 0 | nav | **−100.0** | ✅ true | fails MoS gate (overvalued vs NAV) |
| SG | 0 | fcf_cap | null | ✅ true | fails MoS gate |
| WEN | 0 | fcf_cap | −77.2 | ❌ false | `fcf_sustainability_uncertain` |
| PLAY | 0 | fcf_cap | −409.9 | ❌ false | `extreme_mos_review_required` |
| BJRI | 0 | fcf_cap | −93.7 | ❌ false | `cross_source_mismatch` |
| LOCO | 0 | fcf_cap | −65.1 | ❌ false | `cross_source_mismatch` |
| PTLO | 0 | fcf_cap | null | ❌ false | `cross_source_mismatch` |
| DIN | 0 | nav | −100.0 | ❌ false | `fundamental_decline_flag` |
| PZZA | 0 | nav | −100.0 | ❌ false | `fundamental_decline_flag` |
| JACK | 0 | nav | −100.0 | ❌ false | `debt_truncation_suspected`, `cross_source_mismatch` |
| BDL | 1 | fcf_cap | −23.9 | ❌ false | `cross_source_mismatch` + kill-flag (material weakness) |
| BH | 1 | nav | −66.1 | ❌ false | `financial_sic_forced_unsuitable`, `insurance_concepts_present` + kill-flag |
| BRCB | 1 | fcf_cap | null | ❌ false | `peak_contamination_flag`, `cross_source_mismatch` + kill-flag |
| DNUT | 1 | fcf_cap | null | ❌ false | `peak_contamination_flag` + kill-flag |
| FWRG | 1 | fcf_cap | null | ❌ false | `cross_source_mismatch` + kill-flag |
| NDLS | 1 | fcf_cap | null | ❌ false | `peak_contamination_flag` + kill-flag |
| RICK | 1 | fcf_cap | −167.8 | ❌ false | `extreme_mos_review_required`, `cross_source_mismatch` + kill-flag |

**mos_basis distribution:** fcf_cap = 14, nav = 5, abstain = 0.

**Decisive fact: there is not a single positive margin of safety in the cohort.** Every name with a
computable MoS is trading *above* its fcf-cap intrinsic band or NAV. So even the four `buy_eligible == true`
names (CBRL, KRUS, NATH, SG) fail the MoS≥30 leg. The 0-BUY result is driven first and foremost by
valuation (overvaluation), with guards/kill-flags as the second line.

**Ratings written into reports:** 0 BUY, 6 WATCH (CBRL, KRUS, NATH, PLAY, SG, WEN), 13 AVOID
(kill-flag or hard guard). `RANKING.md` sinks the 13 AVOIDs to the bottom.

---

## 4. Code-paths exercised

- **Discovery FTS + market-cap fallback band split** (deep<$2B / watch $2–5B) — fired; 67/10 split.
- **One FTS page error** — "casual dining" page 0 returned HTTP 500 from `efts.sec.gov`
  (data-quality issue, below). Discovery continued on the other two phrases; no crash.
- **cheap_pass kill-flags** — `kf_material_weakness` fired on BDL, BH, BRCB, DNUT, FWRG, RICK;
  `kf_reverse_split` fired on NDLS. (7 of 19 carry exactly 1 kill-flag.)
- **SIC Gate 1 tri-state** — keep=12, review=31, drop=0 (review correctly forwarded, not dropped).
- **LLM theme-fit Gate 2** — removed 17 misrecalls; `candidates_gate2_survivors.json` recorded.
- **Valuation routing** — three-way `mos_basis` (fcf_cap / nav / abstain); cyclical-CV path; NAV path
  on DIN/PZZA/JACK/NATH/BH.
- **buy_eligible guards that actually fired:** `fcf_sustainability_uncertain` (WEN),
  `extreme_mos_review_required` (PLAY, RICK), `cross_source_mismatch` (BDL, BJRI, BRCB, FWRG, JACK,
  LOCO, PTLO, RICK), `fundamental_decline_flag` (DIN, PZZA), `peak_contamination_flag`
  (BRCB, DNUT, NDLS), `debt_truncation_suspected` (JACK),
  `financial_sic_forced_unsuitable` + `insurance_concepts_present` (BH). This is broad guard coverage
  — the V-shape vetoes, the data-integrity cross-source gate, and the insurance-holdco gate all
  exercised on real names.
- **Signals side-channel (firewalled)** — emitted per name (e.g. CBRL `divergence_label: aligned`,
  `signals_meta.never_affects_buy: true`). Verified it does **not** touch `buy_eligible`: CBRL has
  `buy_eligible: true` from guards alone while its signals block sits inert. Firewall holds.
- **finalize_run** — verdicts emitted (19), `RANKING.md` rebuilt, trust banner present, 0 missing.

---

## 5. Adversarial verification of BUYs

**There are 0 mechanical BUYs, so there is nothing to adversarially confirm or reject.**
`n_buy_clean = 0`. The honest reading: this is not the tool failing to find an opportunity — it is the
tool correctly reporting that the neglected-small-cap restaurant universe contains no clean,
under-valued industrial beneficiary right now. Every operator is either (a) priced above its cash-flow/NAV
value, (b) carrying a data-integrity or value-trap flag, or (c) carrying a cheap_pass kill-flag.

Spot-check of the "closest to interesting" names (adversarial, for the record):
- **CBRL** (buy_eligible, but MoS −55%): genuinely overvalued on normalized FCF, not an artifact —
  Cracker Barrel's earnings are depressed mid-turnaround while the market caps a recovery. Correct AVOID-of-BUY.
- **BH** (Biglari): the `financial_sic_forced_unsuitable` + `insurance_concepts_present` gate is the
  *correct* call — BH consolidates a P&C insurer, so an FCF-cap restaurant valuation is structurally
  inappropriate. Not a false positive of the guard.
- **DIN / PZZA** (`fundamental_decline_flag`, NAV −100%): both are levered, declining-comp legacy
  franchisors; the V-shape/decline veto is doing exactly its job. No artifact.

---

## 6. Data-quality issues

1. **FTS page 500** — `efts.sec.gov` returned HTTP 500 on "casual dining" page 0. Recall for that one
   phrase is partially degraded; the other two phrases (and the union) still pulled 169 raw. For a
   theme with a real gold list this would warrant a retry, but with no SIC floor and no gold list here
   it is recorded as a known soft gap, not a measured miss.
2. **`cross_source_mismatch` on 8 of 19 names** (BDL, BJRI, BRCB, FWRG, JACK, LOCO, PTLO, RICK) — a
   >2.5× SEC-XBRL vs yfinance disagreement on debt/revenue/shares. For lease-heavy restaurant operators
   this is partly expected: operating-lease liabilities (ASC 842) inflate SEC "total debt" relative to
   yfinance's narrower debt field, so the cross-check is firing on a definitional gap as much as on bad
   data. It correctly blocks BUY (a corrupted/ambiguous input can't back a tradeable MoS), but a PM
   should read these as "needs a manual debt reconcile," not necessarily "the filing is wrong." This is
   the most load-bearing data-quality observation for the **lease-heavy code-path focus**.
3. **Null MoS on several names** (KRUS, SG, PTLO, BRCB, DNUT, FWRG, NDLS) — driven by negative/zero
   normalized FCF (these are growth or loss-making concepts), so no FCF-cap MoS is computable. Correct
   behavior; they cannot be BUYs regardless.
4. **DNUT had no Item-1 blurb** in the candidate record (classified on external knowledge). Minor.
5. **Encoding** — valuation.py prints a non-JSON summary to stdout and writes the JSON to a sidecar
   file itself; redirecting stdout to the JSON filename clobbers it. Operational note for the runner,
   not a model defect.

---

## 7. Market-intel / Trends context (T2 — labeled, never drives buy_eligible)

TrendsMCP quota was exhausted (5/5 daily, 100/100 monthly) so brand-momentum series could not be
pulled this run. Substituting third-party analyst context from current sector reporting:

- The sector enters 2026 with "measured optimism" — US restaurant sales ~$1.55T, modest real growth,
  but **margin pressure from beef inflation (+9.4%) and flat-to-low (0–1%) same-store sales** (RBC).
- **Casual dining is bifurcated**: a third of Black Box-tracked brands had positive comps; the rest
  negative. Winners (Chili's record comps; Dine Brands' Applebee's positive comps + first positive
  IHOP traffic since 2015; First Watch +64 units, positive comps; Texas Roadhouse) vs a wave of
  bankruptcies (Bar Louie, Pinstripes, Hooters, Razzoo's).
- **BJRI** specifically is cited as a small-cap showing operational improvement (traffic focus, new
  prototype) but with *modest* 2026 growth (sales +2.4%, EPS +3.3%) — consistent with our AVOID-of-BUY:
  improving but not cheap.
- Theme that matters for this cohort: **traffic-driven > price-driven growth**, and **K-shaped**
  consumer risk for chains skewed to lower-income guests.

This context corroborates the mechanical result: a fully-valued, margin-pressured group where the
quality names are not cheap and the cheap names carry flags. It does **not** alter any `buy_eligible`.

Sources:
[Restaurant Dive — casual dining 2026 outlook](https://www.restaurantdive.com/news/casual-dining-outlook-guest-experince-value-focus-2026/810406/),
[Nasdaq — 3 restaurant stocks despite pressures](https://www.nasdaq.com/articles/3-restaurant-stocks-buy-despite-ongoing-industry-pressures),
[CNBC — restaurant stocks struggling to start 2026](https://www.cnbc.com/2026/03/15/restaurant-stocks-are-struggling-to-start-2026-where-to-find-buying-opportunities.html),
[Finviz — breakout restaurant stock 2026](https://finviz.com/news/255213/which-restaurant-stock-could-be-the-breakout-star-of-2026).

---

## 8. Skeptical-PM verdict: **USABLE**

The run is usable. It did the one thing the scanner exists to do: it enumerated the small-cap restaurant
universe, threw out 17 keyword-sweep misrecalls, deep-dived all 19 true operators with zero crashes,
and returned a defensible **0-BUY** with an explicit, per-name reason for every rejection. The guard
coverage is genuinely broad here (V-shape vetoes, cross-source data-integrity, insurance-holdco gate,
extreme-MoS, FCF-sustainability all fired on real names), and the firewall on the diagnostic signals
held. The one caveat a PM should internalize: `cross_source_mismatch` is firing partly on the
operating-lease definitional gap for lease-heavy operators, so it is doing double duty as
"block BUY" and "flag for manual debt reconcile" — appropriate, but worth knowing. No BUY here is a
correct answer, not a coverage failure.

**Ranked WATCH shortlist (non-sink, not buys):** CBRL, KRUS, NATH, PLAY, SG, WEN.
