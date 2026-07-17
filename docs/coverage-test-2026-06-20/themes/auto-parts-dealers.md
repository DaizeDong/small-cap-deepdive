# Coverage Test, auto-parts-dealers

- **Theme slug:** `auto-parts-dealers`
- **Sector:** Consumer Discretionary
- **Keywords:** `auto parts, automotive aftermarket, dealerships`
- **Code-path focus:** cyclical / floorplan-debt
- **Run batch:** `reports/smallcap/2026-06-21_cov-auto-parts-dealers/`
- **Skill version:** v0.3.0 (commit f12fef5, dirty)
- **Date:** 2026-06-21 (run executed under coverage-test-2026-06-20 docs tree)
- **Verdict:** **0 clean BUYs.** Usable to a skeptical PM as a landmine scanner: yes.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw universe (discover, FTS + mktcap bands) | 427 | deep=55, watch=10, large=33, unknown=329 (flow-through) |
| Small-cap candidates run through cheap_pass | 47 | deep band + adjacent |
| cheap_pass survivors (not rejected) | 32 | kill-flag eliminations applied |
| After SIC Gate-1 (tri-state) | 32 | keep=19, review=13 (review → LLM gate) |
| **LLM theme-fit gate (Gate 2)** | 14 retained / 18 misrecall | see §2 |
| **Deep-band survivors deep-dived (FULL, no sampling)** | **9** | PRTS, SMP, VRM, SRI, STRT, ADNT, THRM, MEI, MYE |
| Mechanical BUYs | **0** | none satisfy the 4-part BUY rule |
| Clean BUYs (post-adversarial) | **0** |, |

No SIC recall floor exists for this theme (`auto-parts-dealers` is not in `THEME_SIC`; dealer/parts
SICs 5013/5531/5500 are not seeded), so recall is FTS-only, expected. No gold list either, so
recall@gold is **n/a** (`track_forward.py --recall-gold` returned "no gold list … not measurable").

Deepdive errors: **0** (no `deepdive_*_ERROR.json` written). All 9 deep-dives + 9 valuations
completed synchronously.

---

## 2. Theme-fit gate (LLM judgment from Item-1 blurbs)

**Retained, deep band (deep-dived, 9):**

| Ticker | Name | SIC | Fit | Basis for membership |
|---|---|---|---|---|
| PRTS | CarParts.com | 5531 | pure_play | Aftermarket auto-parts e-commerce retailer, closest to a true "auto-parts dealer" |
| SMP | Standard Motor Products | 3714 | partial | Aftermarket replacement-parts mfr/distributor (Vehicle/Temperature Control) |
| VRM | Vroom | 5500 | partial | Used-vehicle dealer; wound down e-commerce in 2024, now finance/AI (UACC) |
| SRI | Stoneridge | 3714 | partial | Automotive electronics/electrical supplier (mostly OEM) |
| STRT | Strattec Security | 3714 | partial | Automotive access/security products (OEM-focused) |
| ADNT | Adient | 3714 | partial | Automotive seating, pure OEM tier-1 |
| THRM | Gentherm | 3714 | partial | Automotive thermal/comfort, OEM tier-1 |
| MEI | Methode Electronics | 3678 | partial | Mechatronics for OEMs (auto + cloud/industrial) |
| MYE | Myers Industries | 3089 | partial | Tire-service-supply origin; now diversified plastics/distribution |

**Retained, watch band (theme-fit only, NO deep-dive per dual-band rule, 5):**
AAP (Advance Auto Parts, pure_play), GPI (Group 1 Automotive, pure_play), ABG (Asbury Automotive,
pure_play), VC (Visteon, partial OEM electronics), IEP (Icahn Enterprises, partial, Auto segment).

**Misrecall, dropped (18):**
REITs whose tenants/keywords tripped FTS, PINE, OLP, SVC, BFS, NTST, UE, HIW, BNL, FVR;
BLMN (restaurants); SBH (beauty retail); HTZ (car rental, not parts/dealer); MAX (insurance
ad-tech); OI (glass containers); SLRC, BBDC, OCSL (BDCs); FGBI (bank). All recorded in
`gate2_results.json` with reasons so finalize_run resolves them (0 missing).

> Theme honesty note: the *true* "auto-parts dealer / dealership" pure-plays in the small/mid-cap
> band are the watch-band names (AAP/GPI/ABG), all > \$2B and therefore out of the deep band.
> The deep-band cohort is dominated by SIC-3714 OEM tier-1 component **suppliers**, which qualify
> under the "automotive aftermarket" keyword as *partial* but are not dealers. The only deep-band
> pure-play retailer is PRTS (\$51M). This is a real coverage observation, not a defect.

---

## 3. BUY rule application (the 4-part contract)

BUY requires: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric `MoS ≥ 30` **AND** `buy_eligible == true`
**AND** zero kill-flags.

| Ticker | basis | active MoS | buy_eligible | killflags | BUY? | Blocking factor |
|---|---|---|---|---|---|---|
| PRTS | nav | -9.8% | False | 0 | No | MoS<30 **and** cross_source_mismatch (shares 80.6M vs yf 8.1M = 9.9x) |
| SMP | fcf_cap | -147.3% | False | 1 (mat_weak) | No | MoS<30; extreme_mos_review_required; material_weakness |
| VRM | nav | **+30.8%** | **False** | 0 | No | **buy_eligible=False (cross_source_mismatch, rev 129x)** |
| SRI | nav | -68.8% | False | 0 | No | MoS<30; debt_truncation_suspected |
| STRT | fcf_cap | -46.3% | True | 0 | No | MoS<30 |
| ADNT | nav | -100.0% | False | 0 | No | MoS<30; cross_source_mismatch |
| THRM | fcf_cap | -57.6% | True | 0 | No | MoS<30 |
| MEI | fcf_cap | -44.9% | False | 0 | No | MoS<30; peak_contamination_flag |
| MYE | fcf_cap | -85.6% | True | 0 | No | MoS<30 |

**Zero names pass.** The three buy_eligible=True names (STRT, THRM, MYE) all fail on deeply negative
MoS (overvalued on our model basis). The one name that clears the MoS≥30 bar (VRM) is correctly
blocked by the data-integrity gate.

### Honest 0-BUY rationale
There is no clean BUY in this theme at this date. The cohort is either (a) overvalued on a
normalized-FCF/NAV basis (STRT/THRM/MYE/SMP/SRI/ADNT/MEI) or (b) a data/transition artifact whose
single-source number cannot back a tradeable MoS (VRM, PRTS). This is the expected and correct
behavior of a landmine scanner on a mature, well-covered, cyclical sub-industry, the alpha is not
here.

---

## 4. Adversarial verification of the closest call (VRM)

VRM is the only name that mechanically cleared MoS≥30, so it is the one worth adversarially probing
for a *false negative* (did the gate wrongly suppress a real opportunity?).

- **Claim under test:** NAV MoS +30.8% (tangible equity \$86.5M vs market cap \$52.9M) looks like a
  net-net.
- **Disconfirming evidence (decisive):** SEC revenue series shows the e-commerce collapse ,
  \$3.18B (2021) → \$1.95B (2022) → \$0.89B (2023, the stale FY in the pull). Vroom **discontinued
  its used-vehicle e-commerce operation in January 2024** and now runs essentially UACC (auto
  finance) + an AI/analytics arm. yfinance TTM revenue is \$6.9M (the runoff entity), a 129x
  disagreement vs the SEC figure. The XBRL/yfinance shares also disagree.
- **Verdict:** the `cross_source_mismatch` block is **correct, not an artifact suppression.** The
  NAV figure is computed against a balance sheet in active wind-down/transition; the "net-net"
  optics are a snapshot of a company mid-restructuring, not a stable asset base. **A real
  data/transition artifact, NOT a real opportunity.** The firewall did its job.

(No mechanical BUY existed, so no BUY required adversarial *confirmation*; the above is the
defensive check that the 0-BUY outcome is honest rather than a recall miss.)

---

## 5. Code-paths exercised (cyclical / floorplan-debt focus)

The requested focus paths all fired with real, interpretable effect:

- **`_is_cyclical` (CV>0.25) → cyclical normalization (trailing-avg FCF/EBITDA):** fired True on
  PRTS (0.55), VRM (0.94), SRI (0.61), STRT (0.63), MEI (0.71), MYE (0.38); False on SMP/ADNT/THRM.
- **Cyclical static-MoS lumpy-OCF guard (valuation.py ~L611):** fired on **STRT** ,
  `lumpy_ocf_normalization_suspect: peak_year_ocf=35.1M > 2x median 11.4M`. The cyclical guard
  surfaced the peak-year distortion in the data_quality block.
- **`debt_truncation_suspected` (floorplan/inventory-financing-relevant XBRL debt truncation):**
  fired on **SRI**, reported_total_debt \$0.9M vs implied (liab−equity) \$355.8M (ratio 0.00).
  Gated buy_eligible, exactly the floorplan-debt code path this test targets. (debt-as-total-
  liabilities proxy also fired on STRT.)
- **`peak_contamination_flag` (V-shape value trap, rev_slope=+1 but contamination<0.8):** fired on
  **MEI**, contamination_ratio 0.272, rev_slope +1. Downgraded/blocked buy_eligible.
- **`cross_source_mismatch` (P7 second-source data-integrity gate):** fired on **VRM** (rev 129x),
  **ADNT** (debt), **PRTS** (shares 9.9x / debt 3.0x). Each gated buy_eligible.
- **`extreme_mos_review_required` (G1 defense-in-depth, |MoS|>100%):** fired on **SMP** (−147%).
- **`large_cap_out_of_scope`:** not triggered on deep-band names (ADNT is \$1.6B mktcap deep-band
  despite \$14.5B revenue, the band is mktcap-based, correctly kept in scope).
- **`fundamental_decline_flag`:** not fired on any (NRP, none had whole-window rev_slope<0 with the
  contamination/below-avg combination).

The **signals side-channel** (T2 diagnostic, price-divergence / fundamental-trajectory) is embedded
in each `deepdive_*.json` under the `signals` key, **firewalled**: `valuation.buy_eligible` is
composed solely from `derived` flags + MoS, never from `signals`. Verified the firewall held (no
BUY, and the one buy_eligible=True chain had no signal input).

---

## 6. Data-quality issues observed

- **VRM**, SEC vs yfinance revenue 129x (company mid-transition; e-commerce discontinued 2024).
  Latest FY revenue in the pull is the stale 2023 \$893M figure. NI series mixes DEF 14A and 10-K
  sources.
- **PRTS**, shares_outstanding SEC 80.6M vs yf 8.1M (9.9x, likely a reverse-split / yf staleness),
  total_debt SEC \$17.9M vs yf \$52.8M (3.0x); debt_stale >18 months; negative EBITDA/NI → all
  FCF-cap and EV/EBITDA outputs nulled; NAV used as fallback basis.
- **SRI**, XBRL total_debt tag truncated to \$0.9M (debt_truncation); debt-as-total-liabilities
  proxy used.
- **STRT**, lumpy OCF (peak 3x median); debt proxy.
- **SMP**, material_weakness present in latest 10-K; extreme negative MoS.
- **SMP/MYE/STRT**, partial EBITDA-series entries (single-component year-ends skipped in CV calc),
  expected handling.
- `openinsider` header-row fallback warning during insider pull (cosmetic; data still parsed).

---

## 7. Market-intel / TrendsMCP (T2 analyst context)

**Unavailable this run.** TrendsMCP daily+monthly request quota was exhausted (5/5 daily, 100/100
monthly) before this theme; market-intel has no cached auto-aftermarket domain pack. T2 context did
not and cannot drive `buy_eligible` by design, its absence has zero effect on the mechanical
verdict. General sector prior (analyst knowledge, not a tool call): the auto aftermarket is a
classic late-cycle defensive sub-industry (parts demand rises as new-vehicle affordability falls and
vehicle age rises), while franchised-dealer and OEM-tier-1 names are pro-cyclical and floorplan-debt
sensitive, consistent with the cyclical CV signatures observed. This is narrative color only.

---

## 8. Skeptical-PM usable verdict

**Usable, yes, as designed.** The run did exactly what the skill claims: enumerated a 427-name FTS
universe, mechanically de-risked to 32, applied a defensible theme-fit gate (dropping 18 REIT/finance
/restaurant misrecalls), deep-dived all 9 deep-band theme members with zero sampling and zero
crashes, and returned an honest **0-BUY** with every block attributable to a named, inspectable
guard. The closest call (VRM) survived adversarial scrutiny as a correct suppression. A PM gets a
clean "nothing to do here, and here is precisely why each candidate was eliminated", which is the
landmine-scanner value proposition, not a buy list.

Caveats a PM should note: (1) the true small/mid-cap dealer pure-plays (AAP/GPI/ABG) sit in the
watch band (>\$2B) and were not deep-dived, if the mandate allows up to ~\$4B, those merit a
separate run; (2) no SIC recall floor for this theme means FTS recall is the only channel (no
measured floor); (3) PRTS/VRM both carry serious single-source data-integrity problems that would
need primary-filing reconciliation before any thesis.

---

### Artifacts
- `reports/smallcap/2026-06-21_cov-auto-parts-dealers/RANKING.md`
- `reports/smallcap/2026-06-21_cov-auto-parts-dealers/deepdive_verdicts.json`
- `reports/smallcap/2026-06-21_cov-auto-parts-dealers/gate2_results.json`
- `reports/smallcap/2026-06-21_cov-auto-parts-dealers/report_{PRTS,SMP,VRM,SRI,STRT,ADNT,THRM,MEI,MYE}.md`
- `reports/smallcap/2026-06-21_cov-auto-parts-dealers/{deepdive,valuation}_*.json`
