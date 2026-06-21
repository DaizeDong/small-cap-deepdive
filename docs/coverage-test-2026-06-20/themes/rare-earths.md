# Coverage Test — Theme: rare-earths

- **Slug:** `rare-earths` (run dir normalizes to `rare_earths`)
- **Sector:** Materials
- **Keywords:** `rare earth, critical minerals, permanent magnets`
- **Code-path focus:** pre-revenue / concentration
- **Skill version:** v0.3.0 @ commit `f12fef5` (run manifest `skill_dirty: true`)
- **Batch:** `reports/smallcap/2026-06-21_cov-rare-earths/`
- **Date:** 2026-06-20 (run executed 2026-06-21 per tool clock)

> **Research output, not investment advice.** This is a landmine-scanner and coverage audit of the
> mechanical pipeline, not a buy list.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw universe (discover, FTS + mktcap) | 449 | FTS over-recall on 3 broad keywords |
| Band split | deep 74 / watch 16 / large 46 / unknown 313 | 313 "unknown" = pre-listing / no mktcap |
| cheap_pass survivors → SIC gate | 36 | keep 33 / review 3 (no SIC `drop`) |
| Deep-band candidates (band="deep") | 25 | the deep-dive universe before Gate 2 |
| Gate 2 LLM theme-fit retained (pure_play+partial) | 12 | 4 pure_play, 8 partial |
| Gate 2 misrecall (dropped, resolved per A5) | 13 | |
| Deep-dived (every retained survivor) | 12 | 0 ERROR files |
| Valuated | 12 | --json + --ticker on each |
| **Mechanical BUYs** | **0** | no name has numeric MoS ≥ 30 on any basis |

**Gate-2 retained (12):** REA, REEMF, IDR, METC (pure_play); ASPI, EU, ISOU, TMCR, VOXR, UMAC, TROX, WWR (partial).

**Gate-2 misrecall dropped (13):** AMPH (pharma), BBSI (PEO/HR), DC (gold), FURY (gold), IHT (hotels),
LEG (furniture), LPTH (IR optics), MRDN (software), NOA (oilsands construction), OESX (LED lighting),
SRI (auto electronics), STRT (auto locks), VRM (used-car ecommerce). All are classic single-keyword
FTS false-positives (e.g. "critical" / "permanent" / "materials" substring noise).

---

## 2. Ranked shortlist (all WATCH — 0 BUY)

| # | Ticker | Name | Gate2 | mos_basis | MoS used | buy_eligible | Rating |
|---|---|---|---|---|---|---|---|
| 1 | ASPI | ASP Isotopes | partial | fcf_cap | null (no FCF) | false | 观察 |
| 2 | EU | enCore Energy (U) | partial | fcf_cap | null (no FCF) | true | 观察 |
| 3 | IDR | Idaho Strategic | pure_play | nav | −83.3% | true | 观察 |
| 4 | ISOU | IsoEnergy (U) | partial | fcf_cap | null | true | 观察 |
| 5 | METC | Ramaco Resources | pure_play | nav | −61.7% | false | 观察 |
| 6 | REA | Rare Earths Americas | pure_play | nav | −97.8% | false | 观察 |
| 7 | REEMF | Rare Element Resources | pure_play | nav | −87.9% | true | 观察 |
| 8 | TMCR | The Metals Royalty Co | partial | fcf_cap | null | true | 观察 |
| 9 | TROX | Tronox Holdings | partial | nav | −38.0% | false | 观察 |
| 10 | UMAC | Unusual Machines | partial | fcf_cap | null | true | 观察 |
| 11 | VOXR | Vox Royalty | partial | fcf_cap | null | true | 观察 |
| 12 | WWR | Westwater Resources | partial | nav | +1.1% | false | 观察 |

Best NAV margin of safety in the entire cohort is WWR at **+1.1%** — a country mile from the 30% gate.
Every other NAV name is deeply negative; every fcf_cap name has null MoS (pre-revenue, no positive
FCF to cap). The theme is structurally a pre-revenue exploration/royalty cohort, so the abstain/NAV
machinery is doing exactly what it should: refusing to manufacture a tradeable MoS from no cash flow.

---

## 3. BUYs

**Zero BUYs — honest 0-BUY outcome.** No adversarial verification needed because nothing cleared the
mechanical trigger. The BUY rule requires `mos_basis ∈ {fcf_cap, nav}` AND numeric MoS ≥ 30 AND
`buy_eligible == true` AND zero kill-flags. Failure mode by group:

- **NAV names (REA, REEMF, IDR, METC, TROX, WWR):** all have NAV MoS far below 30 (−97.8% to +1.1%).
  Fails the numeric-MoS arm regardless of `buy_eligible`.
- **fcf_cap names (ASPI, EU, ISOU, TMCR, VOXR, UMAC):** MoS = null. These are pre-revenue or
  no-positive-FCF names; there is no FCF to capitalize, so the static-MoS arm is null and cannot
  reach 30. Fails the numeric-MoS arm.

This is the **correct** result for a hot, pre-revenue resource theme. Per PHILOSOPHY world-view #2,
the rare-earth theme already has branded attention; the skill's job here is to separate true
industrial beneficiaries from concept-players and then *decline to BUY* a cohort with no cash-flow
anchor — which it did.

---

## 4. Code-paths exercised (the point of this coverage test)

The pre-rev/concentration guards fired exactly as designed; multiple distinct `buy_eligible`
composite terms bit:

| Guard / path | Fired on | Effect |
|---|---|---|
| `cross_source_mismatch` (P7 second-source sanity, yfinance vs SEC) | REA (debt 35.6M vs 1.1M, 31.2x), TROX (39M vs 3514M, 90.1x), ASPI (58.3M vs 261.8M, 4.5x) | forced `buy_eligible=false`; data-integrity gate — would have blocked a static MoS BUY |
| `peak_contamination_flag` (P-A V-shape, `0<cr<0.8` ∧ latest_below_avg ∧ NI<0) | METC (cr=0.019), TROX (cr=0.159) | forced `buy_eligible=false` |
| `fundamental_decline_flag` (P6) | TROX (rev_slope −1, cr 0.16, latest_below_avg) | forced `buy_eligible=false` |
| `insurance_concepts_present` (A3) + `debt_truncation_suspected` | METC | routed like financial-SIC; `buy_eligible=false` |
| `extreme_mos_review_required` | WWR | `buy_eligible=false` |
| `concentration_unquantified` (A2 advisory) | EU, METC, TROX, ASPI | advisory only — surfaced, did NOT gate |
| `low_revenue_loss_ratio` (P-B advisory, ratio>2) | ASPI | advisory only |
| SIC gate tri-state (`review` not `drop`) | 3 names routed to LLM | correct Phase-4 behavior |
| A5 gate2-misrecall-resolved (finalize_run) | 13 names | 0 spurious "missing" warnings |

**Notable on the concentration focus:** the magnitude-based `concentration_flag == "kill"` path did
**NOT** fire on any survivor. TROX (top_customer 39.0%) and ASPI (32.2%) both sit *below* the 40%
watch/kill threshold, so `concentration_flag` stayed null and only the advisory
`concentration_unquantified` text-flag surfaced. EU showed a text "customer concentration: True" in the
deepdive log but with null magnitude → advisory (A2), correctly not gating. So the concentration
*kill* path is covered by construction (threshold logic present and evaluated) but had no in-theme
trigger this run; the concentration *advisory* path (A2) is positively exercised on 4 names.

The **pre-revenue path** is heavily exercised: 6 of 12 survivors have $0 revenue (ISOU, REA, REEMF,
TMCR, VOXR, and WWR near-zero), driving the fcf_cap→null-MoS / NAV-basis routing that produced the
0-BUY. This is the core code-path the test targeted, and it behaved correctly.

---

## 5. Data-quality issues

1. **No SIC reverse-recall floor for rare-earths.** `THEME_SIC` has no mapping for this theme, so
   discovery is FTS-only (no SIC enumeration backstop). Rare-earth miners cluster in SIC 1000/1040/1090
   (metal mining) — a dedicated floor (e.g. 1040, 1090, plus 3690/3674 for magnet makers) would harden
   recall. **Coverage gap, not a crash.**
2. **No gold list → recall@gold n/a.** rare-earths is not in `THEME_GOLD`; recall cannot be measured
   numerically this run (`track_forward --recall-gold` returns "not measurable").
3. **cross_source_mismatch on 3 names (REA, TROX, ASPI)** reflects genuine SEC-XBRL-vs-yfinance
   debt disagreements. For TROX (a real ~$3.5B-debt mid-cap) the SEC-side $39M debt is almost certainly
   a truncated/mistagged XBRL pull — the gate correctly distrusts the input. Good catch, but flags an
   XBRL extraction fragility worth noting.
4. **Slug normalization:** `--slug rare-earths` writes files as `rare_earths` (underscore). Cosmetic
   but worth knowing when globbing.
5. **TROX is large for "small-cap"** ($1.18B mktcap in band, but $2.9B revenue). It passed the band
   filter on market cap; revenue scale suggests it is a mid-cap industrial that surfaced via the
   "critical minerals" (titanium/zircon mineral sands) keyword — a partial, correctly WATCH.
6. **openinsider header-row warning** (non-fatal) on the insider-trade pull for some names; fell back
   to hardcoded column indices.

---

## 6. recall@gold

**n/a** — no gold true-member list exists for `rare-earths` in `THEME_GOLD` (only deathcare,
water-utilities, railcar-leasing, regional-gaming have gold lists). Not measurable this run.

---

## 7. T2 diagnostic signals & market-intel context (NOT used in any rating)

> Firewalled side-channel — diagnostic only. Did not and cannot drive `buy_eligible` or any BUY.

- **Fundamental-vs-price divergence (P16):** IDR/UMAC/ASPI = `aligned`; REA/REEMF = `unclear`
  (price-return series sparse on recent IPOs). No `unpriced_improvement` flags.
- **TrendsMCP (T2 analyst context):** Google search interest in "rare earth magnets" is **−5.9% YoY
  and −61% over the trailing 3 months** (off a Q1-2026 spike); news volume up YoY (from a ~0 baseline)
  but −10.6% over 3M. Reading: the theme had an early-2026 attention spike that is now **cooling** —
  textbook "hot theme = casino" (world-view #2). This *supports* the skeptical 0-BUY stance; it is
  explicitly NOT an input to the mechanical decision.

---

## 8. Skeptical-PM usable verdict

**Usable: YES (as a landmine-scanner and coverage audit).** The run is clean and the pipeline behaved
correctly end-to-end: 0 crashes, 0 missing reports, A5 gate-2 resolution working, P7/P6/P-A/A2/A3
guards all firing on the right names, and an honest 0-BUY for a pre-revenue resource cohort that a
disciplined PM *should* refuse to BUY on a cash-flow basis.

A skeptical PM gets real value from the **eliminations**: 13 keyword false-positives removed at Gate 2,
3 data-corruption catches (REA/TROX/ASPI cross-source), 2 V-shape value-trap downgrades (METC/TROX),
and a clear statement that no name in the cohort offers a ≥30% margin of safety. The genuine
pure-play REE explorers (REA, REEMF, IDR) survive as WATCH names worth human DD — IDR in particular
(profitable gold producer + largest US REE landholder) is the most defensible WATCH — but none is a
mechanical BUY, and the cooling search-trend corroborates patience.

**Caveat for the PM:** the missing SIC reverse-recall floor + missing gold list mean recall is
**unverified** for this theme. The 12 survivors are a precision-clean set, but I cannot certify the
discovery floor caught every true small-cap REE name. Recommend adding rare-earths SIC floor
(1040/1090 + magnet SICs) and a hand-built gold list before treating coverage as complete.
