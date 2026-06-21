# Coverage Test — Lithium / Battery Materials (Materials)

- **Run:** `2026-06-21_cov-lithium-battery-materials`
- **Skill version:** v0.3.0 (commit `f12fef5`, dirty working tree)
- **Slug:** `lithium-battery-materials`
- **Sector:** Materials
- **Keywords:** `lithium, battery materials, cathode anode`
- **Code-path focus:** pre-revenue / `peak_contamination`
- **Verdict (skeptical PM):** USABLE. Clean, defensible **0-BUY** outcome — the discipline layer behaved correctly on a cooling hot theme dominated by pre-revenue developers. No data-artifact BUYs to scrub.

---

## 1. Funnel

| Stage | Count |
|---|---|
| FTS discovery universe (rows) | 185 |
| → small-cap candidates into cheap_pass | 101 |
| → cheap_pass survivors (56 eliminated on kill-flags / large-cap / illiquid) | 45 |
| → SIC gate (keep 43 + review 2) | 45 |
| candidates JSON: **deep band** | 34 |
| candidates JSON: watch band (>$2B, surfaced separately) | 11 |
| → LLM theme-fit gate KEEP (pure_play + partial) | **16** |
| → LLM theme-fit gate MISRECALL (dropped) | 18 |
| **Deep-dived (every deep-band survivor)** | **16** |
| deepdive ERROR files | 0 |
| **Mechanical BUYs** | **0** |
| **Adversarially-clean BUYs (`n_buy_clean`)** | **0** |

All 16 KEEP names received `deepdive_data` + `valuation` (with `--json` AND `--ticker`) + a
`report_<ticker>.md`. `finalize_run` confirms: *deep-band 34, reports 16, gate2-misrecall resolved 18,
missing 0*. Zero silent skips, zero crashes.

---

## 2. LLM theme-fit gate (membership judged from blurbs)

**KEEP (16)** — genuine lithium / battery-materials / cathode-anode membership:

| Ticker | Name | Membership basis |
|---|---|---|
| CVV | CVD Equipment | partial — CVD tooling incl. battery/Si-anode materials |
| ENVX | Enovix | pure_play — advanced Li-ion (silicon anode) batteries |
| SLDP | Solid Power | pure_play — solid-state battery + sulfide electrolyte material |
| WWR | Westwater Resources | pure_play — battery-grade natural graphite anode |
| IONR | ioneer | pure_play — lithium-boron mine (Rhyolite Ridge) |
| ELVA | Electrovaya | pure_play — Li-ion battery manufacturer |
| NMG | Nouveau Monde Graphite | pure_play — battery anode graphite |
| SLI | Standard Lithium | pure_play — lithium developer (Smackover brine) |
| SGML | Sigma Lithium | pure_play — lithium concentrate producer |
| ELVR | Elevra Lithium | pure_play — lithium developer |
| NEOV | NeoVolta | partial — LiFePO4 residential/C&I energy-storage systems |
| TTI | TETRA Technologies | partial — bromine/lithium from brine (+ oilfield) |
| LAC | Lithium Americas | pure_play — lithium developer (Thacker Pass) |
| FRSPF | First Phosphate | partial — apatite/phosphate for LFP cathode |
| CSIQ | Canadian Solar | partial — battery-storage arm (core = solar) |
| TMCR | Metals Royalty Co | partial — battery-metals royalty (blurb TOC-only; SIC 1040) |

**MISRECALL (18, dropped — keyword co-occurrence, not industrial membership):**
LVWR (e-motorcycle brand), NC (coal/aggregates), CLB (oilfield reservoir svcs), KODK (imaging/chems
concept-player), GHM (vacuum/heat-transfer), NRP (coal/mineral royalties), NVCR (oncology device),
STEM (energy-storage *software*), **EAF/GrafTech (graphite *electrodes for EAF steel* — not battery
anode)**, ASPI (isotope enrichment), NOA (mining/construction svcs), IPI (potash for ag), SCZM (silver
mining), GSBD (Goldman Sachs BDC — financial), CHNR (Nevada shell), FURY (gold mining), OPTX
(optics/photonics), CMP (salt + plant-nutrition; exited lithium).

The most instructive drop is **EAF**: it is a real graphite/carbon industrial name and trips the FTS
recall, but graphite *electrodes for electric-arc-furnace steelmaking* are not battery anode material —
a concept-adjacency the gate correctly rejected.

---

## 3. Ranked shortlist (RANKING.md)

| # | Ticker | Rating | Rev | NI | OCF | MoS (basis) | buy_eligible | kill-flag |
|---|---|---|---|---|---|---|---|---|
| 1 | CSIQ | 观察 WATCH | $5,595M | -$104M | -$253M | +1.0% (nav) | **false** | 0 |
| 2 | CVV | 观察 WATCH | $26M | -$2M | -$4M | N/A (fcf_cap) | true | 0 |
| 3 | ELVA | 观察 WATCH | $0M | $0M | $0M | N/A (fcf_cap) | true | 0 |
| 4 | ELVR | 观察 WATCH | $0M | $0M | $0M | N/A (fcf_cap) | **false** | 0 |
| 5 | ENVX | 观察 WATCH | $32M | -$157M | -$95M | -0.9% (nav) | true | 0 |
| 6 | IONR | 观察 WATCH | $0M | $0M | $0M | N/A (fcf_cap) | **false** | 0 |
| 7 | LAC | 观察 WATCH | $0M | -$86M | -$61M | N/A (fcf_cap) | true | 0 |
| 8 | NMG | 观察 WATCH | $0M | $0M | $0M | N/A (fcf_cap) | true | 0 |
| 9 | SGML | 观察 WATCH | $0M | $0M | $0M | N/A (fcf_cap) | true | 0 |
| 10 | SLDP | 观察 WATCH | $18M | -$93M | -$73M | -0.4% (nav) | true | 0 |
| 11 | SLI | 观察 WATCH | $0M | $0M | $0M | N/A (fcf_cap) | true | 0 |
| 12 | TTI | 观察 WATCH | $631M | +$3M | +$100M | -1.0% (fcf_cap) | true | 0 |
| 13 | WWR | 观察 WATCH | $0M | -$27M | -$10M | +1.1% (nav) | **false** | 0 |
| 14 ⬇ | FRSPF | 避开 AVOID | $0M | $0M | $0M | N/A (fcf_cap) | true | 1 (gc+mw) |
| 15 ⬇ | NEOV | 避开 AVOID | $8M | -$5M | -$4M | -0.9% (nav) | true | 1 (gc+mw) |
| 16 ⬇ | TMCR | 避开 AVOID | $0M | $0M | $0M | N/A (fcf_cap) | true | 1 (gc+mw) |

13 WATCH, 3 AVOID (sunk), **0 BUY**.

---

## 4. BUY rule — honest 0-BUY

**Rule:** BUY ⇔ `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30` AND `buy_eligible == true`
AND zero kill-flags. Applied to all 16:

- **No name has a numeric MoS ≥ 30.** Two structural reasons, both expected for this theme:
  1. **FCF-cap unsuitable / pre-revenue (9 names: ELVA, NMG, SLI, SGML, ELVR, IONR, LAC, FRSPF, TMCR,
     plus CVV).** Development-stage lithium miners and graphite/anode developers have $0 revenue and
     non-positive normalized FCF → `fcf_cap` MoS is `null` (model refuses to invent a number). MoS≥30
     can never be met → no BUY. This is the **pre-revenue code path** firing exactly as designed.
  2. **NAV basis, no discount (ENVX -0.9%, SLDP -0.4%, NEOV -0.9%, CSIQ +1.0%, WWR +1.1%).** The
     cash-burning battery developers trade at/above tangible equity; NAV MoS is ~0. No margin of safety.
- **`buy_eligible == false` on 4 names** (independent of MoS): WWR & CSIQ hit `extreme_mos_review_required`
  (degenerate/extreme MoS the guard refuses to trust), CSIQ also `debt_truncation_suspected` +
  `cross_source_mismatch`; IONR & ELVR hit `cross_source_mismatch` (>2.5× SEC-vs-yfinance disagreement).
- **Even the one profitable name fails.** TTI (norm-FCF +$19.5M, OCF +$100M) prices at fcf_cap MoS
  **−1.0%** — fair value, no edge. Correct WATCH.

There is **nothing to adversarially defend** — 0 mechanical BUYs ⇒ `n_buy_clean = 0`.

### Adversarial check on the 0-BUY itself (false-negative audit)
Is the discipline layer *suppressing a real opportunity*? No. I re-examined the five names closest to an
edge (TTI, CSIQ, ENVX, SLDP, WWR). TTI sits at fair value on real cash flow; the rest are pre-revenue or
above-book cash-burners. None is a wrongly-killed buy. The 0-BUY is the substantively correct read of a
universe of cyclical-trough lithium developers after a price crash — not a model failure.

---

## 5. Code paths exercised

- **Discovery FTS + SIC gate** (no SIC reverse-recall floor: lithium/battery has no single dedicated SIC;
  names spread across 1000/1040/1221/1311/1400/2800/2890/3559/3690/3674/3751/3827... — recall rests on FTS,
  a noted floor risk for this theme).
- **mktcap-fallback banding** — deep(34)/watch(11)/large(excluded); null-mktcap flow-through path.
- **cheap_pass kill-flag scan** — going_concern / substantial_doubt / material_weakness / death_spiral /
  reverse_split (going-concern text-hit on 7 dev-stage names; gc+mw pair on NEOV/FRSPF/TMCR → sunk to AVOID).
- **valuation FCF-cap reverse-DCF → `fcf_model_unsuitable` / `normalized_fcf_nonpositive`** (dominant path — pre-rev).
- **NAV path** (5 names) when FCF unsuitable.
- **`buy_eligible` composite guards that bit:** `extreme_mos_review_required` (WWR, CSIQ),
  `debt_truncation_suspected` (CSIQ), `cross_source_mismatch` / P7 second-source sanity band (IONR, ELVR, CSIQ).
- **`peak_contamination_flag` (focus path): evaluated on all 16, fired on NONE.** Most names have $0
  revenue (degenerate base — A1 lower-bound `0 < contamination_ratio` correctly rejects), and the revenue-bearing
  names (ENVX contamination 1.08, others) are not in the V-shape 0<cr<0.8 + below-avg + NI<0 window. So the
  V-shape veto was exercised and correctly stayed silent — no false positives, the A1 degenerate-base guard
  did its job on the zero-revenue cohort.
- **`fundamental_decline_flag`** — false on all (gated on rev_slope<0; zero-rev names don't qualify).
- **finalize_run gate2-misrecall resolution** — required writing `gate2_results.json` (explicit verdicts)
  + `candidates_gate2_survivors.json` **as list-of-dicts** (a bare string list yields an empty survivor
  set; see Data-quality issue #2).
- **track_forward** — 14 verdicts recorded to `metrics/verdicts.jsonl` (2 dupes skipped); recall@gold n/a.
- **signals side-channel** — emitted into each deepdive JSON `signals` namespace; firewalled (valuation
  `buy_eligible` reads only T1 fields; confirmed it does not touch the `signals` namespace).

---

## 6. Data-quality issues found

1. **Kill-flag count disagreement (deepdive vs cheap_pass).** Report rating contracts show
   `killflag_count: 0` (from deepdive) while the cheap_pass CSV records `kf_going_concern=1` on 7 names
   (ENVX, IONR, ELVR, NEOV, LAC, FRSPF, TMCR) and `kf_material_weakness=1` on 3 (NEOV, FRSPF, TMCR).
   cheap_pass scanned these as text-hits but did **not** hard-eliminate them (they reached candidates),
   so the two counters measure different things. For dev-stage lithium/battery filers, boilerplate
   "substantial doubt / going concern" language is near-universal, so the text-hit alone is weakly
   informative. Did not affect BUY (no MoS≥30 anyway) but the inconsistency should be reconciled.
2. **`finalize_run` survivor-file format trap.** `candidates_gate2_survivors.json` must be a list of
   **objects** (`[{"ticker": "..."}]`); a bare `["TICK", ...]` string list is silently parsed to an
   empty survivor set, making finalize report all 18 misrecalls as "missing." Worth a doc note or a
   string-list acceptance fix.
3. **Empty / TOC-only business blurbs.** CVV, ELVA, NMG, SGML, NRP returned empty blurbs; ELVR, TMCR,
   CSIQ returned filing table-of-contents instead of a business description (foreign-filer 20-F/40-F
   parsing). Theme-fit for these relied on name + SIC + prior knowledge rather than the blurb.
4. **cross_source_mismatch on 3 names** (IONR, ELVR, CSIQ) — genuine >2.5× SEC-vs-yfinance disagreement
   on debt/shares/revenue; the P7 guard correctly gated them. For zero-revenue developers this is partly
   expected (yfinance trailing fields vs SEC dev-stage filings).
5. **No SIC recall floor for this theme** — lithium/battery materials has no single dedicated SIC, so
   discovery recall rests entirely on the FTS arm. Without a gold list (below), recall is unaudited;
   a capped FTS arm could silently miss true members.

---

## 7. recall@gold

**n/a** — `lithium-battery-materials` has no hand-built gold list (only water-utilities, railcar-leasing,
regional-gaming, deathcare carry one in `track_forward.py`). `track_forward.py --recall-gold` returns
"no gold list for theme … not measurable." Discovery recall for this theme is therefore unaudited.

---

## 8. Market-intel / Trends context (T2 — analyst color only, never drives buy_eligible)

- **TrendsMCP, Google Search "lithium battery materials":** +125% YoY (2025-06 → 2026-06) but **−65% over
  the last 6 months** (rolling over from a Dec-2025 spike).
- **TrendsMCP, Google News "lithium price":** news attention **−33% over the last 3 months**.

Read: a theme that spiked and is now cooling — precisely the post-peak regime where SKILL.md World-View #2
("hot themes are the casino") and value-trap / `peak_contamination` risk are elevated. The mechanical
layer's refusal to issue any BUY into a cyclical-trough developer cohort is consistent with that prior.
This context is explicitly **not** an input to any eligibility gate.

---

## 9. Skeptical-PM usable verdict

**USABLE.** The run is complete (16/16 deep-dived, 0 errors), the gate cleanly separated 16 true
battery-materials names from 18 keyword-coincidence misrecalls (incl. the instructive EAF graphite-electrode
drop), and the 0-BUY outcome is *substantively* correct, not a coverage gap: the universe is overwhelmingly
pre-revenue lithium developers and above-book battery cash-burners with no margin of safety, plus one
fairly-valued profitable name (TTI). The focus paths (pre-revenue FCF-unsuitability, `peak_contamination`
V-shape veto with A1 degenerate-base guard) both fired as designed. Main caveats for the PM: (a) discovery
recall is unaudited (no gold list, no SIC floor — FTS-only), and (b) the deepdive-vs-cheap_pass kill-flag
counter disagreement should be reconciled. Neither undermines the 0-BUY conclusion.
