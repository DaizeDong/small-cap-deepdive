# Coverage-test theme report, animal-health

- **Slug:** `animal-health`  (discover slug normalized to `animal_health`)
- **Sector:** HealthCare
- **Keywords:** `animal health, veterinary, pet care`
- **Run batch:** `2026-06-21_cov-animal-health`  (skill commit f12fef5, dirty)
- **Code-path focus:** niche
- **Date:** 2026-06-21
- **Verdict:** **0 BUY (honest zero).** Usable for a skeptical PM as a landmine-scan; no actionable longs.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw FTS recall (distinct, after mktcap lookup) | 417 | EDGAR full-text on the 3 keywords, forms 10-K/10-Q/20-F/40-F, 2-yr window |
| Universe bands | deep 259 / watch 38 / large 78 / unknown 42 | dual-band tagging in discover |
| Cheap-pass evaluated | 136 small-cap candidates | mechanical health check |
| Cheap-pass survivors (not rejected) | 75 | 61 rejected (going-concern/death-spiral/MW/illiquid/no-mktcap) |
| After SIC tri-state filter -> candidates JSON | 75 | keep=20, review=55, drop=0 |
| Deep band in candidates | 56 | watch band 19 (theme-fit only, no deep-dive) |
| **LLM theme-fit gate (Gate 2)** | **8 survivors** | 48 misrecall, 5 pure_play, 3 partial |
| Deep-dived (deepdive_data + valuation) | **8 / 8** | every theme-fit survivor; zero ERROR files |
| **Mechanical BUYs** | **0** | none clears MoS>=30 + buy_eligible + zero kill-flags |

**SIC recall floor:** NONE. `animal-health` is not in `THEME_SIC`, so there is no dedicated-SIC
reverse-recall, recall is FTS-only (no `recall_channel` column in the universe). This is the
expected **niche** code path: a theme whose true members are scattered across many SIC codes
(2834 pharma, 2835/2836 biologics, 5990 retail, 6324 insurance, 3990 misc-mfg, 7372 software,
0100 agriculture) with no single dedicated industry classification to floor against.

**Funnel object:** raw=417, deepdived=8, survivors=8.

---

## 2. LLM theme-fit gate (my independent judgment)

The FTS over-recalled massively: 48 of 56 deep-band candidates are **misrecalls**, companies
where "animal health", "veterinary", or "pet care" appears once in a risk factor, a TAM aside,
or an unrelated context. Examples: oncology/biopharma (ATNM, ARVN, ZYME, NUVB, MNKD, PCRX, GERN,
ABCL, EYPT, KLRS, PROK, VALN, COAG), restaurants (RRGB, PLAY, DIN, LOCO, CBRL, WEN, BRCB),
BDCs (SLRC, MSDL, MFIC), lithium (LAC), used-car finance (CRMT), diagnostics/proteomics (SEER,
QTRX, PSNL, OSUR), fresh produce (DOLE), beauty (OLPX, EOLS).

My classification was **identical** to the recorded `gate2_results.json` (8/8 survivors match,
zero diff), corroboration, not circularity, since I judged from blurbs independently.

**8 theme-fit survivors deep-dived:**

| Ticker | Name | Fit | Basis for inclusion |
|---|---|---|---|
| ICCC | ImmuCell | pure_play | animal-health biologics; neonatal calf scour prevention (First Defense) |
| PAHC | Phibro Animal Health | pure_play | diversified global animal health + mineral nutrition, 800 product lines |
| WOOF | Petco | pure_play | pet specialty retailer, ~1,400 pet-care centers |
| TRUP | Trupanion | pure_play | pet medical insurance for cats and dogs |
| ZOMDF | Zomedica | pure_play | veterinary diagnostics / animal-health pharma microcap |
| ODC | Oil-Dri | partial | cat-litter (Cat's Pride / Jonny Cat) pet-care segment |
| SPB | Spectrum Brands | partial | Global Pet Care reporting segment |
| WFCF | Where Food Comes From | partial | animal-handling / welfare third-party verification (weak/adjacent) |

---

## 3. Ranked shortlist (final RANKING.md)

| Rank | Ticker | Rating | MoS | Basis | buy_eligible | kill-flag |
|---:|---|---|---:|---|---|---|
| 1 | ICCC | 观察 WATCH | n/a | fcf_cap | True | 0 |
| 2 | ODC | 观察 WATCH | -94.3% | fcf_cap | True | 0 |
| 3 | PAHC | 观察 WATCH | -92.1% | fcf_cap | False | 0 |
| 4 | WFCF | 观察 WATCH | -92.9% | nav | True | 0 |
| 5 | SPB | 避开 AVOID | -95.0% | nav | False | 0 |
| 6 | TRUP | 避开 AVOID | -74.1% | nav | False | 1 (material_weakness) |
| 7 | WOOF | 避开 AVOID | -184.5% | fcf_cap | False | 0 |
| 8 | ZOMDF | 避开 AVOID | -22.6% | nav | True | 0 |

Every survivor has a **negative** margin of safety (or a null band). Not one is within reach of
the +30% BUY threshold. The cleanest names (ICCC, ODC, WFCF, ZOMDF clear buy_eligible) still
fail purely on price, the true animal-health/pet members trade at premium multiples
(ICCC EV/EBITDA ~20x, ODC ~16x, WFCF ~29x, PAHC PE ~27x, WOOF PE ~82x, TRUP EV/EBITDA ~33x).

This is exactly the PHILOSOPHY thesis #2 in action: **a recognizable, retail-loved theme
(pet care / "pet humanization") is a casino, not an edge.** The discipline layer correctly
finds no mispriced small-cap long.

---

## 4. BUY analysis, honest 0-BUY

No candidate satisfies the BUY rule (`mos_basis in {fcf_cap,nav}` AND numeric `MoS>=30` AND
`buy_eligible==true` AND zero kill-flags). Per-name reason it is NOT a BUY:

- **ICCC**, buy_eligible True, clean flags, but **MoS null** (`intrinsic_band_unavailable`:
  normalized 5-yr FCF is nonpositive -$2.5M, so the fcf_cap intrinsic band cannot be built). No
  numeric MoS -> fails MoS>=30. (Reverse-DCF also null for the same reason.)
- **ODC**, buy_eligible True, clean flags, **MoS -94.3%** (fcf_cap). Far below 30. Data-quality:
  `lumpy_ocf_normalization_suspect` (peak OCF 80.2M > 2x median 31.7M) and debt is a
  total-liabilities proxy, but even so it is grossly above intrinsic.
- **PAHC**, **buy_eligible False** (`fcf_sustainability_uncertain`: capex unavailable, FCF uses
  OCF proxy), MoS -92.1%.
- **WFCF**, buy_eligible True, clean flags, **MoS -92.9%** (nav basis; fcf_cap blocked by the
  C1 data-quality guard due to stale debt). Below 30.
- **SPB**, **buy_eligible False** (`financial_sic_forced_unsuitable` + `insurance_concepts_present`),
  MoS -95.0%. See data-quality note: this is a guard **false-positive** (SPB is a consumer-products
  company, not an insurer) triggered by a `PremiumsEarnedNet` XBRL concept, but the NAV-basis MoS
  is deeply negative regardless, so the BUY outcome is unaffected.
- **TRUP**, **buy_eligible False** (`financial_sic_forced_unsuitable`, SIC 6324 insurance +
  `insurance_concepts_present`), MoS -74.1%, plus a `material_weakness` kill-flag surfaced in the
  verdict build. Correctly an AVOID, pet insurer, FCF model unsuitable.
- **WOOF**, **buy_eligible False** (`extreme_mos_review_required`: MoS -184.5% exceeds the 100%
  guard), PE 82x, levered retailer.
- **ZOMDF**, buy_eligible True, clean flags, but **MoS -22.6%** (nav; still negative) and FCF
  yield -24%, a cash-burning pre/early-revenue microcap (`low_revenue_loss_ratio` flag noted
  the |NI|/rev = 2.6x early-stage pattern, correct entity). Below 30.

**Adversarial verification:** not required, there are zero mechanical BUYs to stress-test.
`n_buy_clean = 0`.

---

## 5. Code-paths exercised

- `discover.py` FTS recall + dual-band tagging + market-cap/liquidity filter
- **niche path: no SIC reverse-recall** (`theme_sics("animal-health") == []`, FTS-only floor)
- `cheap_pass.py` mechanical kill-flags + business_blurb extraction (61 rejects)
- inline SIC tri-state filter (`sic_classify`: keep=20 / review=55 / drop=0)
- LLM theme-fit Gate 2 (8 survivors / 48 misrecall)
- `deepdive_data.py` x8 (financials + 10-K flags + insider + **signals side-channel** embedded
  in deepdive JSON under `signals.{price_divergence,ownership,signals_meta}`, diagnostic-only,
  firewalled from buy_eligible)
- `valuation.py` x8 with `--json --ticker` (deterministic fcf_cap / nav / abstain selection)
- **BUY-guard paths fired:** `financial_sic_forced_unsuitable` (TRUP, SPB),
  `insurance_concepts_present` (TRUP, SPB), `extreme_mos_review_required` (WOOF),
  `fcf_sustainability_uncertain` (PAHC), `fcf_cap_blocked_by_c1_data_quality_guard` (WFCF, ZOMDF),
  `intrinsic_band_null:normalized_fcf_nonpositive` (ICCC, SPB, ZOMDF),
  `low_revenue_loss_ratio` (ZOMDF), `lumpy_ocf_normalization_suspect` (ODC),
  `debt_is_total_liabilities_proxy` (ODC), `debt_stale` (ZOMDF, WFCF),
  `cross_source_checked` (all pass, no mismatch)
- `finalize_run.py`: completeness assert (56 deep-band, 8 reports, 48 gate2-resolved, **0 missing**),
  verdict emission, RANKING rebuild, trust banner
- `track_forward.py --recall-gold`: **not measurable** (no gold list for this theme)
- `rank.py`: 8 ranked, 4 sunk (AVOID)

---

## 6. Data-quality issues

1. **SPB insurance-guard false-positive.** Spectrum Brands (consumer products, SIC 3690) tripped
   `insurance_concepts_present` / `financial_sic_forced_unsuitable` on a `PremiumsEarnedNet` XBRL
   concept. The guard forced NAV basis and correctly blocked BUY, but the trigger reason is wrong
   for the entity. Outcome unaffected (NAV MoS -95%), but worth a guard-precision note.
2. **ICCC null intrinsic band.** Normalized 5-yr FCF nonpositive -> no fcf_cap band -> MoS null.
   The cleanest pure-play by flags is un-valuable on the cash-flow model (cyclical, CV 4.4).
3. **OCF-proxy FCF for PAHC and capex-unavailable** -> `fcf_sustainability_uncertain`. Phibro's
   capex was not separable in the pulled series.
4. **ODC lumpy OCF + total-liabilities debt proxy** -> normalization suspect; intrinsic likely
   understated, but a -94% MoS is robust to that.
5. **Stale debt (>18 months)** for ZOMDF and WFCF -> fcf_cap blocked by C1 guard, forced to NAV.
6. **ZOMDF** is a foreign-listed (TSXV/OTC `ZOMDF`) cash-burn microcap; FCF yield -24%, NI -$82M
   on $32M revenue. Right entity, early-stage pattern correctly flagged.
7. Log buffering on Windows: `run_theme.log` froze at "90/223" while the candidates JSON was
   fully written, completion was confirmed by the artifact, not the log tail.

---

## 7. recall@gold

**n/a.** `animal-health` has no hand-curated gold cohort in `THEME_GOLD`
(`track_forward.py --recall-gold ... --theme animal-health` -> "no gold list ... not measurable").
Gold lists exist only for water-utilities / railcar-leasing / regional-gaming / deathcare.

---

## 8. Market-intel / T2 analyst context (does NOT drive buy_eligible)

TrendsMCP quota was exhausted for the day (5/5 daily, 100/100 monthly, consumed by parallel
coverage agents), so no fresh trend pull. Labeled-T2 domain context only:

- The pet-care / "pet humanization" theme is a well-branded, ETF-covered consumer narrative
  (PAWZ exists). Per PHILOSOPHY #2, branded thematic attention historically erodes risk-adjusted
  returns post-launch, consistent with the premium multiples seen here and the 0-BUY result.
- Structural sub-segments differ: pet **insurance** (TRUP) is a low-penetration secular grower but
  valued as such (EV/EBITDA 33x); pet **retail** (WOOF) is a margin-pressured, levered turnaround
  (PE 82x); **animal-health pharma/biologics** (ICCC, PAHC, ZOMDF) is the genuinely "neglected"
  small-cap pocket but either un-valuable on FCF (ICCC), capex-opaque (PAHC), or cash-burning
  (ZOMDF). None offers a margin of safety today.
- This is analyst color for the report only; it touched nothing in the mechanical BUY path.

---

## 9. Skeptical-PM usable verdict

**USABLE, as a landmine-scanner that returned an honest zero, which is the correct answer.**

The run did the one thing a web-search/LLM narrative pass cannot: it enumerated 417 FTS hits,
mechanically killed 61 unhealthy names, separated 8 true theme members from 48 keyword
misrecalls, and valued every survivor on a deterministic model, concluding that the pet/animal-
health small-cap pocket offers no mispriced long today (every MoS negative). A PM gets a clean,
defensible "nothing to do here, and here is exactly why" plus a watchlist of the 4 buy_eligible
pure/partial-plays (ICCC, ODC, WFCF, ZOMDF) to revisit if prices fall materially. The SPB
insurance-guard false-positive is the only blemish and it did not change any outcome.

**n_buy_clean = 0.**
