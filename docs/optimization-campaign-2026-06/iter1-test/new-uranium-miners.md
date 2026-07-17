# Theme Deep-Dive, Uranium Miners / Nuclear Fuel / Enrichment

**Run:** `2026-06-20_uranium-miners` · skill post-commit e0f0039 (iteration-1) · date 2026-06-20
**Theme keywords:** `uranium, nuclear fuel, enrichment`
**Entry workflow:** Entry 1 (thematic universe screen)
**Stress-test focus:** tricky cyclical + foreign (20-F/40-F/IFRS) + pre-revenue, does the pipeline correctly handle cyclical normalization, IFRS/foreign capex gaps (OCF-proxy flagging), pre-revenue abstain, and foreign/de-SPAC entity resolution?

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw FTS recall (discover.py, 10-K/10-Q/20-F/40-F, 2yr) | **482** | severe over-recall by design |
| └ band split | deep 105 · unknown 292 · watch 22 · large 63 | |
| cheap_pass survivors (not rejected) | **68** | killed going-concern×2 / kill-flag clusters / concentration-kill |
| └ of which deep+unknown (deep-dive queue) | 47 | watch 21 surfaced-only; large skipped |
| **Gate 2 (LLM theme-fit)** survivors | **9** | 38 of 47 dropped as `misrecall` (see §2) |
| Full deep-dive (deepdive_data + valuation) | **9** | every Gate-2 survivor, no sampling |
| **BUY** | **0** | none clears MoS≥30 + buy_eligible + zero kill-flags |
| WATCH (观察) | 9 | |
| AVOID (避开) | 0 | (no kill-flag cluster ≥2) |

Precision of the raw keyword search was extremely low: of 47 deep/unknown survivors only 9 (~19%) are genuine theme members, and within those only 8 are fuel-cycle pure-plays. This is the canonical "hot theme over-recall" the skill is built to handle, the FTS keyword `uranium` is name-dropped in the risk-factor / forward-looking boilerplate of dozens of gold, silver, copper, lithium, rare-earth, cannabis, pharma, REIT, and reinsurance filings.

---

## 2. Two-stage precision gate

**Gate 1 (SIC).** Tri-state `keep`/`review`; never drops in the current config (`sic_hard_exclude` only tags pharma/finance SICs `review`, which still pass to Gate 2). So Gate 1 did no cutting here, all real precision came from Gate 2.

**Gate 2 (LLM theme-fit), on the 47 deep+unknown survivors, using each candidate's 10-K Item-1 `business_blurb`:**

- **pure_play (8):** AEC (Anfield, U+V developer, Shootaring mill), EU (enCore, TX ISR producer), URG (Ur-Energy, WY ISR producer), ISOU (IsoEnergy, Athabasca/US explorer), UROY (Uranium Royalty, royalty + physical U), NUCL (Eagle Nuclear, Aurora deposit, OR), ASPI (ASP Isotopes, isotope **enrichment** platform / HALEU), LTBR (Lightbridge, nuclear **fuel** technology).
- **partial (1, deep-dived):** IMSR (Terrestrial Energy, IMSR advanced reactor; a fuel *consumer*, not a miner/enricher → theme-fit dimension capped).
- **partial, not deep-dived (5):** TVC (Tennessee Valley Authority), EMP/ELC/EAI (Entergy subsidiaries), GPJA (Georgia Power), all `band=unknown` because they are debt-only / non-equity SEC filers (utilities that *operate* nuclear plants); not investable small-cap equities, so excluded from the deep-dive queue with reason recorded.
- **misrecall, dropped (33):** STKE (Solana treasury), CVV (CVD semis equipment), FURY/USGO/GLDG/VGZ/VOXR/MTA/GROY/GOLD/VZLA/CNL/IDR/TMQ/CMCL/REEMF (gold/silver/copper/rare-earth miners), GRUSF/GTBIF (cannabis), BCYC (pharma), IONR/LAC (lithium), XNET (Chinese internet), GWRS (water utility), GLRE (reinsurance), PFLT/TWO (BDC / mortgage REIT), SPPP (platinum trust), SUPV (Argentine bank), PDS (oil-&-gas drilling), MTAL/VMET (copper / precious-metal royalty), TROX (TiO2 pigment), WWR (Westwater, self-describes as now graphite-focused; "originally" uranium → dropped on the *current* theme).

---

## 3. Shortlist (all 9 deep-dived), mechanical decision matrix

| # | Ticker | Name | Theme | mos_basis | MoS / NAV-MoS | buy_eligible | kill-flags | Rating |
|---|---|---|---|---|---|---|---|---|
| 1 | ISOU | IsoEnergy | pure | fcf_cap | null | true | 0 | 观察 |
| 2 | NUCL | Eagle Nuclear | pure | fcf_cap | null | true | 0 | 观察 |
| 3 | UROY | Uranium Royalty | pure | fcf_cap | null | true | 0 | 观察 |
| 4 | AEC | Anfield Energy | pure | fcf_cap | null | true* | 0** (gc=1 single) | 观察 |
| 5 | LTBR | Lightbridge | pure | nav | NAV −46% | **false** (debt_truncation) | gc=1 single | 观察 |
| 6 | ASPI | ASP Isotopes | pure (enrich) | nav | NAV −75% | **false** (wrong_entity) | mw=1 | 观察 |
| 7 | EU | enCore Energy | pure | fcf_cap | null | true* | mw=1 | 观察 |
| 8 | URG | Ur-Energy | pure | nav | NAV −89% | **false** (debt_trunc+wrong_entity) | 0 | 观察 |
| 9 | IMSR | Terrestrial Energy | partial | nav | NAV −79% | **false** (wrong_entity) | gc=1 single | 观察 |

\* `buy_eligible=true` in the valuation block, but a single going-concern (AEC) or material-weakness (EU) kill-flag from cheap_pass independently blocks BUY under the rubric's zero-tolerance rule. The deepdive/valuation `killflag_count` (0 for AEC) does not see cheap_pass's per-flag detail, see §5 data-quality note 4.
\*\* AEC's going-concern is a single hit, which cheap_pass does not count toward `killflag_count` (it requires a double-hit to increment), so it survives cheap_pass but still blocks BUY at the judgment layer.

---

## 4. BUY / 0-BUY with buy_eligible reasoning

**0 BUYs, and mechanically correct.** Two independent walls stop every name:

1. **No positive intrinsic value exists for the pure developers.** ISOU, NUCL, UROY, AEC, EU are pre-revenue or pre-FCF; `normalized_fcf` is unavailable or non-positive, so the FCF-cap intrinsic band is null → `margin_of_safety_pct = null`. A BUY requires `MoS ≥ 30`; null can never clear it. This is the **pre-revenue abstain behavior working**, the model declines to manufacture a value where the cash flows don't exist, rather than printing a spurious deep-discount.

2. **The asset-heavy names route to NAV and are all deeply negative.** URG (−89%), IMSR (−79%), ASPI (−75%), LTBR (−46%) trade far above tangible book; NAV MoS is sharply negative → no BUY even before eligibility. And `buy_eligible=false` on all four (debt_truncation / wrong_entity data-quality guards), which would block BUY regardless.

No `mos_basis=fcf_cap` name has both `MoS ≥ 30` and `buy_eligible=true` and zero kill-flags, so the BUY trigger never fires. No qualifying catalyst (no 10-12B spinoff, no Form-4 cluster cash buys, no court-ordered sale, no delisting-deficiency) exists for any name, and the catalyst MoS-waiver is frozen in iteration 1 anyway (would only reach WATCH-with-catalyst).

**Best-of-cohort for a watchlist (still not buys):** NUCL and UROY, both 0 kill-flags, `buy_eligible=true`, cleanest balance sheets (NUCL: $31M cash, no debt post-PIPE; UROY: royalty model, no operating mine). They are WATCH purely because there is no positive computable intrinsic value to discount yet, exactly the right reason.

---

## 5. Data-quality observations (the focus stress-test)

The sector-specific failure modes in the focus were **handled correctly, conservatively, and visibly**, with two labeling caveats worth recording:

1. **IFRS / foreign capex gap → OCF-proxy flagging (the P2 fix): WORKS.** NUCL and LTBR have no XBRL capex concept; the model set `fcf_is_ocf_proxy=true`, appended `capex_unavailable_fcf_uses_ocf_proxy` + `fcf_equals_ocf_proxy_no_capex`, and (P2) forced `fcf_sustainability_uncertain=true` → `buy_eligible=false` wherever it mattered. Every OCF-proxy FCF is flagged, not silently treated as true FCF. This is the precise IFRS/20-F failure mode the test targeted.

2. **Pre-revenue abstain: WORKS.** Developers with no positive normalized FCF correctly produce `intrinsic_band_null:normalized_fcf_unavailable` / `_nonpositive` and `margin_of_safety_pct=null`, no fabricated MoS. Asset-heavy ones with equity available route to NAV (URG/ASPI/LTBR/IMSR); the rest stay fcf_cap-with-null. No name was forced into a false BUY.

3. **Cyclical handling: not exercised (correctly).** None of the 9 had a long enough positive EBITDA/FCF series to be tagged `cyclical` or to build a normalized base, they are too early in life. So the cyclical-normalization and the P6 `fundamental_decline_flag` melting-ice-cube veto did not need to fire here. (URG is the only real producer with a multi-year series; its revenue is declining −19% and EV/Sales 17.9x, but with non-positive normalized FCF it routes to NAV before the P6 carve-out is relevant. `fundamental_decline_flag=false` for it because the normalization base is non-positive, not contaminated-peak.) This is appropriate, the cyclical machinery is built for established producers (the WLFC/LNN reference class), and the uranium cohort is structurally pre-cyclical.

4. **Foreign / de-SPAC entity resolution: CONSERVATIVE-CORRECT, but mislabeled.** The `wrong_entity_suspected` guard fired on URG, ASPI, and IMSR via heuristic 3 (`|net_income| / revenue > 2.0`). For these names it is a **false positive of the *reason***: they are the right entities, but a large net loss against tiny/near-zero revenue trips a ratio meant to catch unit mis-tags or wrong CIKs. IMSR additionally raised a genuine XBRL unit-mis-tag warning (NI −28M vs rev 0.2M = 112x). The *effect* is correct and safe (forces `buy_eligible=false`, prevents a spurious valuation on a shaky de-SPAC entity), but a PM reading `wrong_entity_suspected` on Ur-Energy, an established NYSE-American producer, would be misled about *why*. **Recommendation for iteration 2:** when revenue is present-but-tiny and net income is a large loss (the pre-/early-revenue resource pattern), emit a distinct `low_revenue_loss_ratio` flag rather than overloading `wrong_entity_suspected`. Same applies to `debt_truncation_suspected` on URG/LTBR, which reflects partial/stale XBRL debt tags rather than a real truncation.

5. **`form_used=None` on all 9.** The deepdive resolved XBRL via companyfacts but did not tag the underlying filing form (10-K vs 20-F vs 40-F). For a foreign-filer stress-test this is a gap: the report cannot show whether the financials came from a 20-F/IFRS filer or a 10-K filer. The 40-F/20-F *fallback* logic exists and the XBRL pulled fine, but the provenance tag is empty, worth fixing so the trust banner can surface "foreign IFRS filer" explicitly.

6. **finalize_run completeness vs Gate-2 drops.** `finalize_run` asserts a report for every `band=deep` candidate (42) and flagged 33 missing, but those 33 were intentionally dropped at Gate 2 as theme misrecalls, not skipped deep-dives. `--allow-missing` is the correct switch, but the tool cannot distinguish "gated out" from "forgotten." Iteration 2 could persist the Gate-2 `misrecall` set into the run manifest so finalize treats them as resolved rather than missing.

---

## 6. Market-intel context (T2, supplementary, NOT used in the mechanical decision)

Clearly labeled analyst context only; this did **not** touch any `buy_eligible`/BUY decision (those are anchored to T1 filings).

- **Broad "uranium" search interest is past its peak and cooling fast** (Google Trends): 12M −8.8%, 6M −16.2%, **3M −52.3%** off a March-2026 spike. "uranium price" search collapsed −82% over 3M (still +12.5% YoY). Uranium does not appear in the current Google Trends top-30. This is textbook "hot theme = casino, post-peak" per the skill's world-view, the retail attention that would create a diffusion edge has already drained.
- **The enrichment sub-theme bucks the trend:** ASP Isotopes search interest +117% YoY (volume +117%), and ASPI is the cohort's only genuine *enrichment* play. This is the one pocket with positive attention momentum, but ASPI is blocked by a material-weakness kill-flag and NAV MoS −75%, so the T2 hotness does not rescue it.
- Ur-Energy and enCore show flat-to-modest single-name interest; nothing suggesting a delayed-diffusion mispricing.

**Net T2 read:** the theme is cooling into a down-leg of attention; nothing here argues for *more* aggression than the mechanical layer already allows (which is none).

---

## 7. Skeptical-PM verdict

**Usable: YES.** A skeptical value PM gets exactly what this skill is supposed to deliver on a hot, over-hyped theme: a clean landmine-scan that (a) cut a 482-name keyword swamp down to 9 genuine fuel-cycle names with auditable reasons for every drop, (b) refused to print a single BUY because no name has a positive computable intrinsic value at a ≥30% discount, and (c) surfaced *why* mechanically, pre-revenue null-MoS for the developers, deeply-negative NAV for the asset-heavy producers, and kill-flags (going-concern on AEC/AEC-class, material-weakness on EU/ASPI) blocking the rest.

The 0-BUY outcome is the *correct* outcome for a pre-revenue, post-attention-peak developer cohort, not a calibration failure. The watchlist ordering (NUCL/UROY/ISOU at the top on clean balance sheets and zero kill-flags) is sensible for "where to look first if the cycle and the financials turn."

The one thing a PM must read past is the **mislabeled `wrong_entity_suspected` / `debt_truncation_suspected` flags** on real producers (URG especially), the §5 data-quality notes in each report correct this in plain language, but the raw flag names would otherwise be alarming. With those notes, the report is trustworthy and decision-ready.

**Bottom line:** the sector-specific failure modes (IFRS/20-F OCF-proxy, pre-revenue abstain, foreign/de-SPAC entity resolution) are handled correctly; the labeling of the entity/debt guards is the only thing that needs polish before iteration 2.
