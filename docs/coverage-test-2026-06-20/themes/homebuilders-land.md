# Coverage Test, Theme: Homebuilders & Land Development

- **Slug:** `homebuilders-land`
- **Sector:** Consumer Discretionary (cyclical)
- **Keywords (FTS):** `homebuilder, residential construction, land development`
- **Run batch:** `reports/smallcap/2026-06-21_cov-homebuilders-land/`
- **Skill version:** v0.3.0 @ commit `f12fef5` (skill_dirty=true per `_run.json`)
- **Code-path focus:** cyclical / inventory-NAV
- **Date:** 2026-06-21
- **Verdict in one line:** **0 BUYs. Clean, correct 0-buy.** The small-cap homebuilder/land universe is cyclically cheap but not 30% below conservative NAV; the single name that screened with a >30% NAV margin (OPAD) was correctly vetoed as a data artifact.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw FTS recall (3 keywords, 10-K/10-Q/20-F/40-F) | **370** | homebuilder 82 + residential construction 229 + land development 151, deduped to 370 |
| SIC reverse-recall floor | n/a | **No dedicated SIC floor** for this theme (not in `THEME_SIC`) → FTS-only recall, by design |
| Small-cap deep band (mktcap < $2.0B) | **66** | + 16 watch band ($2.0B,$5.0B, theme-fit only, no deep-dive) |
| cheap_pass examined | 67 | killed names with kill-flag ≥ 3 (ASBP biopharma misrecall) + concentration/death-spiral |
| cheap_pass survivors written to candidates | **57** | 21 SIC-keep + 36 SIC-review → LLM gate |
| **LLM theme-fit gate (Gate 2)** | **11 kept** | 8 pure_play + 2 partial + 1 borderline construction; **46 dropped as misrecall** |
| Deep-dived (data + valuation) | **11** | every theme-fit survivor; 0 ERROR files, 0 silent skips |
| Mechanical BUYs | **0** | none clears MoS ≥ 30% AND buy_eligible AND 0 kill-flags |
| BUYs surviving adversarial verification | **0** | n/a (no mechanical BUY to verify) |

**Recall@gold:** **n/a**, `homebuilders-land` has no hand-curated gold list in `THEME_GOLD`
(`track_forward.py --recall-gold` returns "no gold list for theme → not measurable"). Recall was
therefore not measured for this theme; the recall floors / gold lists exist for water-utilities,
railcar-leasing, regional-gaming, and deathcare only.

### Gate-2 contamination profile (why 46 of 57 were dropped)

The FTS keyword sweep was heavily contaminated, the precision gate is doing exactly the job it
exists for:

- **18 community banks** (SIC 60xx): FMBM, NRIM, ORRF, HTB, COSO, UNB, RVSB, FCAP, FNRN, UNTY, MPB,
  MBWM, FSBC, STEL, TCBX, BFST, EQBK, FBLA, matched on "residential construction" (their loan books).
- **2 water utilities** (SIC 4941): GWRS, ARTNA, coverage-test cross-theme bleed ("development").
- **4 insurers**: SNFCA, AII, HIPO (homeowners insurance), BWIN (insurance broker), "residential."
- **2 REITs / landlords**: UMH (manufactured-housing-community REIT, a landlord not a builder), MDV
  (industrial REIT), own homes/land, do not build/develop for sale.
- **4 incidental industrials**: IIIN (steel wire for concrete), APOG (architectural glass), ALOT
  (printers), DDD (3D printing).
- **1 agriculture**: LMNR (citrus/avocado farming with incidental land entitlement).

The canonical Gate-2 failure mode (keyword sweeping an unrelated sector wholesale) reproduced cleanly
here and was caught, without Gate 2, this theme would have surfaced ~18 banks and 2 water utilities
as "homebuilders."

---

## 2. Theme-fit classification (the 11 deep-dived survivors)

| Ticker | Name | SIC | Class | Rationale |
|---|---|---|---|---|
| AXR | AMREP Corp | 6552 | pure_play | "primarily engaged in land development and homebuilding" |
| BZH | Beazer Homes USA | 1531 | pure_play | national homebuilder |
| HOV | Hovnanian Enterprises | 1531 | pure_play | national homebuilder + captive mortgage |
| DFH | Dream Finders Homes | 1531 | pure_play | asset-light single-family homebuilder |
| FOR | Forestar Group | 6500 | pure_play | residential **lot development**, sells finished lots to builders |
| SDHC | Smith Douglas Homes | 1531 | pure_play | land-light single-family homebuilder (SE/S US) |
| LGIH | LGI Homes | 1531 | pure_play | entry-level homebuilder, 22 states |
| CCS | Century Communities | 1531 | pure_play | national homebuilder |
| FRPH | FRP Holdings | 6500 | partial | diversified RE (mining royalties, multifamily, industrial) + land dev |
| OPAD | Offerpad Solutions | 6531 | partial | iBuyer, buys/resells homes (housing-inventory NAV exposure, not a builder) |
| JFB | JFB Construction Holdings | 1540 | borderline | nonresidential general contractor; included to avoid silent-skip; carries a material-weakness kill-flag |

Watch band (theme-fit only, NOT deep-dived, $2 to 5B): GRBK, MHO, KBH, JOE, HHH, SKY, MRP, TPH are
genuine theme members above the small-cap ceiling; BCC (Boise Cascade) is building products; the rest
(UCB, TCBI, NIC banks; FOUR, RUN, ATKR, WOR) are watch-band misrecalls.

---

## 3. Mechanical BUY decision, all 11

BUY rule: `mos_basis ∈ {fcf_cap, nav}` AND **numeric MoS ≥ 0.30 (30%)** (NAV MoS for nav basis,
FCF MoS for fcf_cap) AND `buy_eligible == true` AND `killflag_count == 0`.

| Ticker | basis | active MoS | buy_eligible | kill-flags | BUY? | Why not |
|---|---|---|---|---|---|---|
| OPAD | nav | **+52.9%** | **false** | 0 | NO | cross_source_mismatch (buy_eligible=false) |
| BZH | nav | +25.4% | true | 0 | NO | MoS < 30% (closest near-miss) |
| CCS | nav | +10.4% | false | 0 | NO | MoS < 30% + cross_source_mismatch |
| AXR | fcf_cap | +4.7% | true | 0 | NO | MoS < 30% |
| HOV | fcf_cap | −0.4% | true | 0 | NO | MoS < 30% |
| FRPH | nav | −25.9% | true | 0 | NO | NAV MoS negative (trades above NAV-low) |
| DFH | nav | −42.1% | false | 0 | NO | MoS < 30% + insurance-concepts + financial-SIC-forced + xsource |
| FOR | fcf_cap | null | false | 0 | NO | normalized FCF non-positive → no MoS + xsource |
| LGIH | fcf_cap | null | true | 0 | NO | normalized FCF non-positive → no MoS |
| SDHC | fcf_cap | null | true | **1** (material_weakness) | NO | no MoS + kill-flag |
| JFB | fcf_cap | null | true | **1** (material_weakness) | NO | no MoS + kill-flag |

**Mechanical BUYs: 0. Adversarially-verified BUYs (n_buy_clean): 0.**

---

## 4. Code-paths exercised (cyclical / inventory-NAV focus)

This theme is the designed stress-test for the **cyclical + asset-heavy NAV** path, and it fired:

- **Cyclical detection** (`cv_ebitda > 0.25`): 8 of 11 classed cyclical → EBITDA normalized via
  `cyclical:trailing_5yr_avg` (AXR 0.54, BZH 0.59, HOV 0.43, DFH 0.61, FOR 0.58, LGIH 0.51, OPAD 1.09,
  FRPH 0.30). 3 classed non-cyclical (CCS 0.25 just under threshold, SDHC 0.13 and JFB null, both
  recent IPOs with < 5y history → `non_cyclical:latest`).
- **Asset-heavy NAV path**: homebuilders carry large land/WIP inventory and high debt-to-assets, so
  the FCF-cap model was ruled **unsuitable** (`fcf_cap_model_unsuitable` / `c1_data_quality_guard`)
  and valuation routed to the **NAV intrinsic band** (tangible-equity proxy, cap-rate band) for
  OPAD, BZH, CCS, DFH, FRPH. This is the correct path for inventory-heavy builders.
- **Reverse-DCF null cascade**: `normalized_fcf_nonpositive` for OPAD/DFH/FOR/LGIH/FRPH/JFB/SDHC ,
  trailing-5yr-average FCF is negative because builders consumed cash buying land/building inventory
  into the cycle. Correctly produces a null FCF MoS rather than a fabricated one.
- **Cross-source data-integrity gate (P7)**: fired on OPAD (shares 10x), DFH, FOR, CCS, blocked BUY
  on those four. See §5.
- **Insurance / financial-SIC routing (A3)**: DFH tripped `insurance_concepts_present` +
  `financial_sic_forced_unsuitable` (captive mortgage/title insurance XBRL concepts) → forced FCF
  model unsuitable, correct.
- **V-shape value-trap vetoes**: `fundamental_decline_flag = false` and `peak_contamination_flag =
  false` for **all 11**, no monotone-decline or trough→peak→rollover names, so these vetoes did not
  need to bind.
- **Material-weakness kill-flag (cheap_pass)**: SDHC and JFB carry kill-flag=1 (ICFR material weakness
, both are 2024 IPOs/SPAC-deals). Below the 2/3 elimination threshold so they survived to deep-dive,
  but each is a hard kill-flag that independently blocks BUY.
- **Diagnostic signals side-channel (firewalled)**: emitted for all 11 (`price_divergence` +
  `ownership`). Labels: DFH/SDHC/FRPH = `unpriced_improvement`; CCS/OPAD = `melting_ice_cube_priced`;
  the rest `aligned`. **Confirmed it did NOT touch buy_eligible**, these never enter the decision path
  and are recorded for future per-signal calibration only.

---

## 5. Near-misses, adversarially examined

There are no mechanical BUYs to verify. Two names came closest and each is worth a skeptical note.

### OPAD (Offerpad), NAV MoS +52.9% but buy_eligible=false. **Verdict: DATA ARTIFACT, correctly vetoed.**

The screen computed a $24M market cap from **yfinance's 4.7M share count**, while SEC reports
**47.3M shares**, a 10.0× disagreement (`cross_source_mismatch`). OPAD executed a 1-for-15 reverse
split in 2024; yfinance's unadjusted/stale share count is the near-certain culprit. If SEC's 47.3M is
correct, the true market cap is ~$240M, the EV/NAV math inverts, and the 52.9% "margin" evaporates.
The P7 gate is a **data-integrity** gate (it questions whether the input number can be trusted at all,
distinct from the firewalled market-signals layer), and it did precisely its job: a large MoS built on
a corrupted denominator is itself suspect. Additionally OPAD is an iBuyer (housing-inventory flipper),
the most cyclically fragile model in this set, with `melting_ice_cube_priced` divergence (+243% 6m /
+434% 12m price, a tiny illiquid post-reverse-split float). **Not a real opportunity; the artifact
veto is correct.**

### BZH (Beazer Homes), NAV MoS +25.4%, buy_eligible=true, 0 kill-flags. **Verdict: genuine but sub-threshold; correct WATCH.**

The single cleanest near-miss. Trades ~25% below the low end of its tangible-NAV band ($928M low vs
$739M cap), is buy-eligible, has no kill-flags, and shows insider net-buying. It simply does not clear
the conservative 30% bar, exactly the "cyclically cheap but not 30% below conservative NAV" outcome
the threshold is calibrated to gate. The NAV uses a book-equity proxy (no goodwill/intangibles
breakout) and debt is `>18 months stale`, so even the 25.4% carries data caveats. A PM watching the
housing cycle should keep BZH on the WATCH list, but the tool is right not to call it a BUY. Price is
`aligned` (+26% 12m), the modest discount is partly already worked off by the tape.

---

## 6. Data-quality issues observed

1. **OPAD shares 10× cross-source mismatch** (SEC 47.3M vs yf 4.7M), reverse-split staleness in
   yfinance; corrupts market cap and any MoS derived from it. Gate correctly blocked BUY.
2. **mos_pct display rounding in the rating block.** `make_report.py::_mos_field` prints the MoS
   **ratio** (0..1) formatted to 1 decimal, so BZH's 0.2545 NAV-MoS renders as `mos_pct: 0.3`. A
   careless reader could misread this as 0.3% or as clearing a "0.3" threshold. The mechanical BUY
   decision uses the raw ratio (0.2545 < 0.30 → no BUY) and is unaffected, but the **display is
   misleading** and should show a percent (e.g. `25.4%`) or be labeled as a ratio.
3. **Stale debt for NAV** (`debt_stale:>18_months_behind_latest_assets`) on BZH and FRPH, the NAV
   band mixes a recent asset figure with an older debt figure; widens NAV uncertainty.
4. **Book-equity NAV proxy** for OPAD/BZH/CCS/DFH/FRPH (`nav_goodwill_or_intangibles_unavailable`) ,
   tangible equity falls back to book equity; for builders this is usually fine (little goodwill) but
   is a proxy.
5. **3 recent IPOs with < 5y history** (SDHC, JFB, and partly DFH/OPAD) → cyclical normalization
   degrades to `non_cyclical:latest`, which understates cycle risk for an inherently cyclical sector.
6. **CCS market cap ($4.1B revenue but $739M,$1.8B cap reported in different stages)**, CCS appears at
   $1.82B in discovery (deep band) and its fundamentals are large; it is a borderline small-cap and
   its `cross_source_mismatch` also blocked it. Watch for the small-cap ceiling here.
7. **No SIC recall floor** for this theme: low-keyword-density true members in SIC 1531/1540/6552 that
   never used the FTS phrases verbatim could be missed. FTS recall of homebuilders is generally good
   (the SIC 1531 names all appeared), but a dedicated `homebuilders → 1531/1540/6552` floor would
   harden recall and is a recommended add to `THEME_SIC`.

---

## 7. T2 analyst context (advisory, does NOT drive buy_eligible)

- TrendsMCP was rate-exhausted at run time (0/5 daily, 0/100 monthly remaining), so no live
  search-volume series was pulled. Recorded as a data-availability gap, not a signal.
- market-intel (`~/CodesSelf/market-intel`) has no homebuilder-specific dataset (generic
  source catalog only).
- Qualitative cycle context (T2, public-domain, advisory only): US homebuilders entered 2026 trading
  at low-but-not-distressed P/B after the 2023 to 24 rate-driven affordability squeeze; entry-level
  builders (LGIH, SDHC) carry the most volume-sensitivity, asset-light/lot-developer models (DFH, FOR)
  the least balance-sheet risk. None of this enters the mechanical decision; it frames why the NAV/FCF
  paths produced sub-threshold margins (the market has already priced the trough discount into ~25% of
  NAV, not the ~30%+ a mechanical BUY would require).

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** The run is a textbook clean 0-buy on a contaminated cyclical theme:

- Discovery over-recalled (370) and the **Gate-2 precision filter removed 46 misrecalls** (18 banks,
  2 water utilities, 4 insurers, REITs, incidental industrials), the single most important thing the
  scanner did here.
- The **cyclical + asset-heavy NAV code-path fired correctly** end-to-end (CV detection → trailing-5yr
  normalization → FCF-cap-unsuitable → NAV-band routing → reverse-DCF null cascade).
- The one name that screened with a > 30% margin (OPAD) was a **data artifact** and the data-integrity
  gate killed it for the right reason. The cleanest fundamental name (BZH, +25.4% NAV MoS, eligible, no
  kill-flags) is correctly held at WATCH for being sub-threshold, not BUY.
- 0 ERROR files, 0 silent skips, 11/11 deep-band reports present, verdicts emitted and recorded.

A skeptical PM gets an honest answer: *the clean small-cap homebuilders are cyclically cheap but the
market has not left a 30%-below-conservative-NAV margin on the table, and the one name that looked like
it had is a reverse-split share-count glitch.* That is the correct and useful output. The only genuine
product gaps are cosmetic/recall-hardening: the `mos_pct` ratio-vs-percent display, and the absence of
a `homebuilders → SIC 1531/1540/6552` recall floor.

---

## Appendix, artifacts

- Run dir: `reports/smallcap/2026-06-21_cov-homebuilders-land/`
- `RANKING.md`, `deepdive_verdicts.json` (11 WATCH), `candidates_homebuilders_land.json` (11 gate-2 survivors)
- `universe_candidates_homebuilders_land_RAW.json` (57 pre-gate-2 cheap_pass survivors)
- Per-ticker: `deepdive_<T>_2026-06-21.json`, `valuation_<T>_2026-06-21.json`, `report_<T>.md`
- Verdicts also appended to `metrics/verdicts.jsonl` (theme=homebuilders-land, 12m horizon, IWM=$295.59)
