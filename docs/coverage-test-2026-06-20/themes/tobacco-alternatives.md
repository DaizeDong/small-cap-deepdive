# Coverage Test, Theme: tobacco-alternatives (Staples)

**Run:** `2026-06-21_cov-tobacco-alternatives` · skill commit `f12fef5` (v0.3.0, dirty)
**Keywords (FTS):** `tobacco, nicotine, vaping`
**Code-path focus:** declining / high-FCF candidate
**Verdict (skeptical PM):** **USABLE, 0 clean BUYs is the correct answer.** The scanner found the
true small-cap nicotine/tobacco members, deep-dived every one, and mechanically vetoed all of them
(no margin of safety; kill-flags; data-integrity vetoes). Nothing slipped through as a narrative BUY.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw universe (discover.py FTS + mktcap fallback) | **320 rows** | 119 `deep`, 15 `watch`, 37 `large`, 149 `unknown` (unpriced) |
| Small-band scanned by cheap_pass | 94 | deep + priceable unknown cohort |
| cheap_pass survivors | 58 | 36 rejected (GC 19 / kill-flags 16 / burn 10 / concentration 11; overlapping) |
| SIC Gate 1 (filter_by_sic) | 58 | keep=34, review=24 → all pass coarse gate; **no SIC recall floor** (tobacco SIC 2111 not wired into `THEME_SIC`) |
| **LLM theme-fit Gate 2 (this analyst)** | **4** | pure_play: TPB, ISPR · partial: UVV, MATV · **44 deep-band misrecalls dropped** |
| Deep-dived (every Gate-2 survivor) | **4** | TPB, ISPR, UVV, MATV, 0 crashes, 0 `_ERROR.json` |
| Mechanical BUYs (rule applied) | **0** | every survivor fails MoS≥30 and/or buy_eligible and/or zero-kill-flag |
| Clean BUYs (post-adversarial) | **0** | no BUY to adversarially test |

**funnel object:** raw=320, deepdived=4, survivors=0 (BUY-eligible clean).

### Why Gate 2 dropped 44 of 48 deep-band names
Single-keyword FTS on `tobacco/nicotine/vaping` over-recalled massively, the keywords appear in
risk factors, ESG screens, and "we do not invest in tobacco" boilerplate across unrelated sectors:

- **Biotech / pharma (misrecall):** PLX, SRPT, HRTX, CRDL, BCYC, OCS, AKBA, ATRC, BWAY, PROTALIX-class, SIC 283x/3841 swept on incidental keyword hits.
- **BDCs / lenders (misrecall):** CGBD, BBDC, MFIC, CICB, GOOD, SCM (BDC portfolio-company boilerplate).
- **Casinos / c-stores / grocers (misrecall):** FLL, MCRI(watch), ARKO, CAPL, YSWY, IMKTA, MNRO, convenience-store fuel/OTP retailers mention "tobacco" as a SKU, not a business.
- **Firearms / less-lethal (misrecall):** RGR, NPK, BYRN, AXIL, "vaping"/keyword false hits.
- **Distillers / ag-chem / other (misrecall):** MGPI (spirits), SAM (beer), FMC (crop chem), IPI (potash), IDT, UIS, ZIP, VYX, IDN, AMBO, BOC, HIPO.
- **Cannabis (related-but-distinct theme, dropped):** GTBIF, CWBHF, CRLBF, SNDL, OGI, HITI, cannabis is a separate theme; "vaping" overlaps but these are not tobacco/nicotine businesses. (Defensible to retain under a broader "smoking alternatives" mandate; held out here for theme precision.)

The 4 retained are the genuine nicotine/tobacco-supply-chain small caps in the universe.

---

## 2. Ranked shortlist (all sunk to AVOID)

| Rank | Ticker | Name | Rating | mos_basis | MoS | buy_eligible | kill-flags | Theme fit |
|---|---|---|---|---|---|---|---|---|
| 1 | ISPR | Ispire Technology | 避开 AVOID | nav | -100% | **false** (cross_source_mismatch) | 1 (MW; cheap_pass also flagged GC) | pure_play (vape hardware) |
| 2 | TPB | Turning Point Brands | 避开 AVOID | fcf_cap | **-80%** | true | 1 (material_weakness) | pure_play (OTP + FRE/ALP pouches) |
| 3 | UVV | Universal Corp | 避开 AVOID | fcf_cap | **-91%** | true | 1 (material_weakness) | partial (leaf-tobacco merchant) |
| 4 | MATV | Mativ Holdings | 避开 AVOID | fcf_cap | -177% | **false** (extreme_mos_review) | 0 | partial (tobacco papers / RTL) |

**Non-sunk (WATCH/BUY candidates): 0.** This is a clean "nothing found."

---

## 3. BUY rule applied to each survivor (full reasoning)

BUY requires ALL of: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric MoS ≥ 30 **AND** `buy_eligible == true`
**AND** zero kill-flags. No survivor clears even the MoS leg.

### TPB, Turning Point Brands (the headline case)
- mos_basis=`fcf_cap`, **MoS = -80.0%** → fails MoS≥30 by a wide margin. Market cap $1,589M vs FCF-intrinsic equity band $318M,$458M ($16.44,$23.67/sh). The market prices ~3× the disciplined-FCF intrinsic ceiling.
- `buy_eligible=true`, but **killflag_count=1** (`material_weakness`) → BUY-ineligible on the zero-kill-flag leg.
- EV/EBITDA **54.6×**, EV/Sales 3.65×, P/E 27×, a premium-multiple grower, the opposite of a margin-of-safety setup.
- **Reported rev growth +394% is a data artifact** (XBRL period/restatement edge, likely segment-scope, not company-wide). T2 corroboration: TPB's *oral* (ALP nicotine-pouch) segment grew 627.6% in Q3 2025 off a tiny base; total company is mid-single-digit. The deepdive growth field over-reads this, logged as a data-quality issue.
- **Verdict: AVOID.** Real theme leader, real cash flow, but no price discount. Not a BUY; not even a value WATCH at this multiple.

### ISPR, Ispire Technology
- mos_basis=`nav` (FCF model unsuitable: debt/assets 1.21 > 0.62), **MoS = -100%** (tangible equity ≈ $0). FCF-negative (norm FCF -$16M), runway 2.4 yrs.
- **`buy_eligible=false`, reason `cross_source_mismatch`**: SEC total_debt $92.1M vs yfinance $4.9M (18.8× disagreement) → second-source guard fires and **blocks BUY**.
- killflag_count=1 (material_weakness in cheap_pass; cheap_pass also flagged going_concern, though deepdive `tenk.has_going_concern=False`, see data-quality note).
- **Verdict: AVOID.** Loss-making, near-zero tangible equity, hard data-integrity veto. Textbook landmine, the scanner caught it.

### UVV, Universal Corp
- mos_basis=`fcf_cap`, **MoS = -91.2%**. Mktcap $1,300M vs FCF-intrinsic band $114M,$337M ($4.59,$13.54/sh). EV/Sales 0.64× (cheap on sales, but it is a $2.9B-revenue, razor-thin-margin leaf merchant: NI $33M on $2.9B = ~1.1% net margin).
- `buy_eligible=true`, but **killflag_count=1** (`material_weakness`) → zero-kill-flag leg fails.
- Non-cyclical (CV 0.19), norm EBITDA $222M, P/E 39.8×, fully priced for a structurally declining combustible-leaf supplier.
- **Verdict: AVOID.** A "declining / high-OCF" candidate (the code-path focus), but the FCF-cap path assigns no margin of safety and the MW kill-flag bars it regardless.

### MATV, Mativ Holdings
- mos_basis=`fcf_cap`, **MoS = -177.4%** → **`buy_eligible=false` reason `extreme_mos_review_required`** (MoS magnitude > 100% triggers the extreme-MoS guard). FCF-intrinsic equity is *negative* ($-338M to $-133M).
- killflag_count=0 (the only clean-on-kill-flags name), but the valuation gate vetoes it anyway.
- Data-quality: **`lumpy_ocf_normalization_suspect`** (peak-year OCF $202M > 2× median $101M), the normalized-FCF base is unreliable; CV 4.64 (extremely cyclical/volatile). NI -$337M (large impairment).
- **Verdict: AVOID.** Negative intrinsic equity under disciplined FCF normalization + unreliable OCF series. Even with 0 kill-flags, this is mechanically uninvestable.

**Adversarial verification:** N/A, there were **0 mechanical BUYs** to stress-test. The honest outcome
is recorded: the small-cap nicotine/tobacco universe at this snapshot contains no clean, discounted
industrial beneficiary. The category's growth (see §6) is being captured by large caps (PMI/ZYN, BAT/VELO)
and priced into the one small-cap leader (TPB) at 54× EBITDA.

---

## 4. Code-paths exercised

- `discover.py` FTS over-recall + **mktcap fallback** (149 unpriced → `band=unknown`, not dropped) ✓
- **SIC recall-floor NOT triggered**, tobacco SIC 2111 is absent from `THEME_SIC`; recall rests on FTS alone. (Code path: `theme_sics("tobacco-alternatives") == []` → no-floor branch.) ✓ (negative path exercised)
- `cheap_pass.py` mechanical kill-flags, 36/94 rejected across going-concern / kill-flags / burn / concentration ✓
- `filter_by_sic.py` Gate 1 keep/review classification ✓
- LLM Gate 2 theme-fit (pure_play/partial/misrecall) → `candidates_gate2_survivors.json` consumed by finalize ✓
- `deepdive_data.py` XBRL + Form 4 + shelf + **second-source cross-check** (fired on ISPR) ✓
- `valuation.py` buy_eligible gate paths fired:
  - **fcf_cap** path (TPB, UVV, MATV)
  - **nav** path / FCF-model-unsuitable on debt/assets>0.62 (ISPR)
  - **cross_source_mismatch** veto (ISPR)
  - **extreme_mos_review_required** veto (MATV)
  - **lumpy_ocf_normalization_suspect** data flag (MATV)
  - cyclical-trough EBITDA normalization (all)
- `signals.py` firewalled diagnostic side-channel, emitted into all 4 deepdive JSONs (price_divergence + ownership); did **not** touch any buy_eligible ✓
- `finalize_run.py` completeness assert with Gate-2-misrecall subtraction (48 deep, 4 reports, 44 resolved, **0 missing**) ✓
- `make_report.py` trust-banner scaffold ✓ · `rank.py` RANKING rebuild ✓
- `track_forward.py --recall-gold` → **no gold list** branch (n/a) ✓

**mos_basis distribution:** fcf_cap=3, nav=1, abstain=0.

---

## 5. Data-quality issues

1. **TPB growth artifact:** deepdive reports rev growth +394%, an XBRL period/scope edge, not real company-wide growth (true total growth is mid-single-digit; the 600%+ figure is the tiny oral/ALP segment). Over-reads the growth dimension.
2. **ISPR cross-source debt mismatch:** SEC $92.1M vs yfinance $4.9M (18.8×). Guard correctly blocked BUY; root cause is yfinance under-reporting debt. Also `debt_is_total_liabilities_proxy`.
3. **ISPR going-concern discrepancy:** cheap_pass `kf_going_concern=1` but deepdive `tenk.has_going_concern=False`. The two detectors disagree (cheap_pass likely matched a risk-factor phrase; deepdive looks for the auditor paragraph). Net effect benign (ISPR is AVOID either way) but the detectors should reconcile.
4. **MATV lumpy-OCF:** peak-year OCF >2× median → normalized FCF base unreliable; CV 4.64. Extreme-MoS guard caught the downstream nonsense (negative intrinsic equity).
5. **Concentration unquantified (TPB, ISPR):** text flag true but XBRL magnitude null, concentration could not be sized numerically.
6. **No SIC recall floor for tobacco:** if a low-keyword-density true member (e.g., a pure leaf processor that never says "vaping") exists, FTS alone could miss it. Recall is unmeasured here (no gold list). **Recommend wiring SIC 2111 into `THEME_SIC`** before treating this theme's recall as trustworthy.

---

## 6. recall@gold

**n/a**, `tobacco-alternatives` has no hand-built gold cohort (only water-utilities, railcar-leasing,
regional-gaming, deathcare are seeded in `THEME_GOLD`). `track_forward.py --recall-gold` returned
"no gold list for theme … not measurable." Recall floor for this theme is therefore unverified.

---

## 7. Market-intel / TrendsMCP context (T2, labeled, never drives buy_eligible)

> TrendsMCP quota was exhausted for the day; substituted independent third-party market research (T2).

The nicotine-alternatives category is one of the strongest *secular* (structural, not cyclical) growth
stories in Staples, consumer migration from combustibles to modern oral nicotine, with independent
analysts converging on **~20 to 26% CAGR** through the early-2030s:

- Polaris: $3.39B (2025) → $26.8B (2034), 25.2% CAGR.
- Grand View: $6.9B (2025) → $42.4B (2033), 24.7% CAGR; synthetic-nicotine sub-segment ~38.7% CAGR.
- Global Market Insights: $8.6B (2025) → $56.7B (2035), 19.4% CAGR.
- Top-5 manufacturers (~51% share): **PMI (ZYN), BAT (VELO/Lyft), Imperial, Turning Point Brands, Moxy.**
- **TPB's ALP** pouch (launched late-2024) is the cited disruptor, oral segment +627.6% in Q3 2025.

**PM read of the T2 context:** the growth is real and durable, *and that is exactly why there is no
small-cap bargain.* The category leader available in small-cap form (TPB) trades at 54× EBITDA, the
secular tailwind is fully (over-) priced. UVV/MATV are the *combustible*-supply-chain losers of the same
migration (declining leaf / cigarette-paper demand), correctly read by the FCF-cap path as no-margin-of-safety.
This is a hot-theme casino (World-View commitment #2): the alpha was captured by mega-caps; the residual
small-cap exposure is either over-priced (TPB) or structurally declining (UVV, MATV) or a data-flagged
landmine (ISPR). **T2 context confirms the mechanical 0-BUY rather than contradicting it.**

Sources:
- [Polaris, Nicotine Pouches Market](https://www.polarismarketresearch.com/industry-analysis/nicotine-pouches-market)
- [Grand View, Nicotine Pouches Market](https://www.grandviewresearch.com/industry-analysis/nicotine-pouches-market-report)
- [Global Market Insights, Nicotine Pouches Market](https://www.gminsights.com/industry-analysis/nicotine-pouches-market)
- [Future Market Insights, Nicotine Pouches Market](https://www.futuremarketinsights.com/reports/nicotine-pouches-market)
- [Prilla, ZYN competitor analysis (VELO / ALP)](https://prilla.com/us/blog/zyn-competitor-analysis-velo-alp)

---

## 8. Skeptical-PM usable verdict

**USABLE.** The run did the job a landmine-scanner is supposed to do:

- Enumerated the universe and surfaced the genuine small-cap nicotine/tobacco members (TPB, ISPR, UVV, MATV) while discarding 44 keyword false-positives at the LLM gate.
- Deep-dived **every** Gate-2 survivor (no sampling), with zero crashes.
- Mechanically vetoed all four with auditable reasons: negative MoS on every name, plus a cross-source-mismatch veto (ISPR), an extreme-MoS veto (MATV), and material-weakness kill-flags (TPB/UVV/ISPR).
- Produced an honest **0-BUY**, consistent with the World-View that a hot, fully-priced secular theme rarely yields a discounted small-cap.

**Caveats a PM must hold:** (1) recall is **unmeasured** here, no gold list and no SIC floor, so a
quiet low-keyword pure-play could be missing; wiring SIC 2111 would close this. (2) The cannabis cohort
was held out by theme definition; a broader "smoking alternatives" mandate would re-include 6 names.
(3) TPB is the one name worth a *manual* revisit if the price ever de-rates toward its FCF-intrinsic band
(~$16 to 24/sh), it is the real category participant, just not at this multiple.

*Research output, not investment advice. Every line ends at "merits human diligence."*
