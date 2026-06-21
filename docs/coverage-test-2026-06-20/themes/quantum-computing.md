# Coverage Test — Quantum Computing / Quantum Hardware

**Theme slug:** `quantum-computing` · **Sector:** Information Technology · **Keywords:** quantum computing, quantum hardware
**Code-path focus:** pre-revenue abstain · low_revenue_loss
**Skill version:** v0.3.0 (commit f12fef5) · **Run batch:** `2026-06-21_cov-quantum-computing` · **Run date:** 2026-06-21

> **Research output, not investment advice.** This is a landmine-scanner: it tells you what to *eliminate* and what survived
> mechanical de-risking. A surviving name is a candidate for human DD, never a buy signal.
> **Headline result: 0 mechanical BUYs.** No name cleared the BUY rule (mos_basis ∈ {fcf_cap, nav} AND numeric MoS ≥ 0.30 AND
> buy_eligible == true AND zero kill-flags). Every theme-fit survivor is pre-revenue or early-commercialization with a **null
> intrinsic band** — MoS is unquantifiable, so no BUY is mechanically possible. This is the correct, honest output for a
> pre-revenue theme, and it is exactly what the pre-rev-abstain code-path is built to enforce.

---

## 1. Funnel

| Stage | Count | Note |
|---|---:|---|
| Raw discover (FTS + mktcap filter) | 405 | EDGAR full-text over-recall on "quantum"; **no SIC recall floor exists** for this theme (FTS-only) |
| Small-cap cheap-pass input | 143 | after market-cap band tag (deep ≤ $2.0B; watch $2.0–5.0B) |
| Cheap-pass survivors (no hard kill-flag) | 83 | 60 eliminated on going-concern / death-spiral / material-weakness / burn / concentration |
| After SIC Gate-1 | 83 | keep=21, review=62 (review goes to LLM Gate-2) |
| **Deep band (band="deep", ≤ $2.0B)** | **67** | the deep-dive-eligible universe |
| Watch band (band="watch", $2.0–5.0B) | 16 | surfaced for human review only, not deep-dived (incl. **QUBT** — a true quantum pure-play, $2.4B) |
| **Gate-2 theme-fit survivors (deep-dived)** | **4** | 63 deep-band names dropped as misrecalls |
| Valuation + BUY-rule applied | 4 | all 4 valued (--json + --ticker), **0 deepdive ERROR files** |
| **Mechanical BUYs (clean)** | **0** | all 4 have null MoS (no intrinsic band) → BUY mechanically impossible |

**SIC recall floor:** none. `quantum-computing` is not in `filter_by_sic.THEME_SIC` (only water-utilities, railcar-leasing,
regional-gaming, deathcare have floors). There is no single dedicated SIC for quantum — true members scatter across SIC 7372
(software), 7370 (computer services), 3080 (plastics/polymers), 2890 (chemicals/isotopes), 3674 (semiconductors). The P8
reverse-recall channel was correctly a no-op; recall was FTS-only. This is correct behavior, not a gap.

**recall@gold:** **n/a** — no gold list exists for this theme. `track_forward.py --recall-gold ... --theme quantum-computing`
returns `"no gold list for theme 'quantum-computing' — not measurable"`.

---

## 2. Gate-2 theme-fit (LLM judgment from Item-1 blurbs)

The FTS keyword "quantum" is one of the most contaminated terms in the small-cap universe. The single largest false cohort is
**crypto-asset ETFs / statutory trusts (SIC 6221)** — these 10-K/20-F filings name "quantum computing" only as a *risk factor*
("a sufficiently powerful quantum computer could break the cryptography securing this digital asset"). The keyword fires on the
risk paragraph, not the business.

**Dropped as misrecalls (63 of 67 deep-band):**

- **22 crypto-asset trusts / ETFs (SIC 6221):** QSOL, GDOG, GTAO, QETH, CLNK, GSUI, CETH, GXRP, ETCG, GLNK, GSOL, ETHV, ZCSH,
  BTCW, XRP, BRRR, BTCO, BSOL, BITW, HODL, ETHE, ETH — pure passive digital-asset vehicles; "quantum" = risk-factor boilerplate.
- **6 additional crypto-treasury / digital-asset operating cos (SIC 6199):** TRON, BRR (ProCap), EXOD (Exodus), ASST (Strive),
  FETH (Fidelity ETH), XXI (Twenty One Capital) — bitcoin/crypto treasuries, same risk-factor mechanism.
- **10 community banks (SIC 6021/6022/6035):** PEBK, BHB, TCBK, BOTJ, CBNA, FNRN, AVBH, FMAO, STBA, EBMT — "quantum" appears in
  cybersecurity risk disclosures; pure financial entities (also caught by the financial-SIC exclusion downstream).
- **~25 other off-theme operating cos:** RVSN (rail AI vision), SNT (perimeter security), RGP (consulting), WW (WeightWatchers),
  UIS (Unisys IT services), SILC/LTRX (network adapters/IoT), URG (uranium), ANGX (media), RYAM (cellulose), HSTM (healthcare
  SaaS), PSTL (postal REIT), STRS (real estate), TACT (transaction terminals), WNW/RBNE/ZOOZ/ICG/VBIX/STSS/BKTI/OSPN/BWAY/
  SKYT/SVCO — none operate in quantum. SKYT (semiconductor foundry) and SVCO (EDA software) are the most defensible "almost"
  cases but are conventional semiconductors, not quantum hardware/computing.

**Retained for deep-dive (4) — genuine quantum membership:**

| Ticker | Class | Why in theme | Verified via |
|---|---|---|---|
| **QNC** (Quantum eMotion) | pure_play | Electron-tunneling Quantum Random Number Generator (QRNG) in CMOS + quantum-safe security stack; pre-revenue | 40-F + web (quantumemotion.com) |
| **BTQ** (BTQ Technologies) | pure_play | Post-quantum-crypto hardware (QCIM secure chips) + neutral-atom quantum computing (QPerfect/MIMIQ); pre-revenue | web (btq.tech), SEC 6-K |
| **ASPI** (ASP Isotopes) | partial | Enriched **silicon-28** (spin-free → longer qubit coherence) for quantum chips; also nuclear medicine/isotopes; early-rev | 10-K + web (thequantuminsider) |
| **LWLG** (Lightwave Logic) | partial | Electro-optic (Perkinamine) polymer modulators for photonics/datacom; quantum-photonics adjacent, not QC per se; ~pre-rev | 10-K Item 1 |

> **Note on the empty-blurb names.** QNC, BTQ, LWLG, URG, STRS, VBIX, CETH had empty `business_blurb` fields (foreign filers
> with non-standard 10-K structure, or trusts). I fetched each Item-1 directly via edgartools + web to avoid a false drop —
> this is what saved QNC and BTQ (both real quantum pure-plays) from being silently misclassified by an absent blurb.

---

## 3. Code-paths fired (pre-rev abstain · low_revenue_loss focus)

This theme is the cleanest exercise of the **pre-revenue / abstain discipline** in the test:

- **Pre-rev abstain → null intrinsic band → BUY blocked (all 4).** Every survivor returns `mos_pct = None`
  (`intrinsic_band_unavailable` for QNC/BTQ; `intrinsic_band_null:normalized_fcf_*` for LWLG/ASPI). The BUY rule requires a
  *numeric* MoS ≥ 30; `None` can never satisfy it. So even QNC and BTQ — which pass `buy_eligible == true` — are **not BUYs**,
  because `buy_eligible` is necessary but not sufficient. This is the central anti-narrative guard for a hot pre-rev theme.
- **`low_revenue_loss_ratio_extreme` (LWLG):** latest NI −$20.3M vs revenue $0.2M (|NI|/rev = **85.8×**, > 20× threshold) →
  flagged EXTREME and **gates `buy_eligible` to False**. The guard also caught a likely XBRL unit mis-tag on NI and noted the
  valuation correctly falls back to OCF (unaffected). This is the low_revenue_loss code-path firing exactly as designed.
- **`low_revenue_loss_ratio` non-extreme (ASPI):** NI −$159.8M vs rev $23.8M (6.7×) — flagged as early/pre-revenue pattern,
  right entity, *not* extreme (does not by itself gate; ASPI is gated by cross_source instead — see below).
- **Zero-XBRL pre-rev (QNC, BTQ):** both foreign filers (Form **40-F**) with **no XBRL financials at all** — $0 rev / $0 NI /
  $0 cash surfaced, EV = market-cap only. Here the low_revenue_loss ratio can't even be computed (`Low-rev-loss: False`), so the
  block comes purely from the null intrinsic band. The data-quality banner enumerates all the unavailable concepts. The data
  layer degraded gracefully (no crash, no ERROR file) and routed the names to abstain — the correct outcome for a name the
  XBRL layer cannot see.
- **`cross_source_mismatch` (ASPI):** SEC total_debt $58.3M vs yfinance $261.8M (**4.5×** disagreement, > 2.5× threshold) →
  gates `buy_eligible` to False. Even if ASPI had a numeric MoS, this second-source guard would independently block it.
- **Cyclical normalization fired (LWLG CV=0.51, ASPI CV=1.59):** both > 0.25 → normalized on trailing-5yr-avg EBITDA. Both
  normalized EBITDA negative (−$19M, −$42M) → reverse-DCF growth null (`normalized_fcf_nonpositive`). Correct.
- **MoS basis routing:** all 4 stayed on **fcf_cap** basis (`fcf_cap_model_unsuitable=False` everywhere — none are asset-heavy
  NAV businesses; QRNG/PQC/photonics/isotope-enrichment are IP/operating businesses, not real-estate/leasing balance sheets).
- **Not fired (clean):** peak_contamination / V-shape fundamental_decline (none monotone-declining — these are *rising* burn
  pre-revs, the opposite failure mode), concentration kill (text flag true but XBRL magnitude null → unquantified, not killed),
  large-cap ceiling, debt-truncation, wrong-entity, financial-SIC forced-unsuitable (the banks were dropped at Gate-2 before
  valuation, so the financial-SIC guard didn't need to fire on a survivor here).

---

## 4. Ranked shortlist (RANKING.md)

| Rank | Ticker | Rating | Conf | Rev | NI | OCF | Growth | Dilution | Insider | kill-flag |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | ASPI | 观察 (WATCH) | 40% | $24M | −$160M | −$38M | +476% | +0% | net_sell | 1 |
| 2 | LWLG | 观察 (WATCH) | 40% | $0M | −$20M | −$14M | +1623% | +2% | net_sell | 0 |
| 3 | BTQ | 观察 (WATCH) | 35% | $0M | $0M | $0M | — | — | neutral | 0 |
| 4 | QNC | 观察 (WATCH) | 35% | $0M | $0M | $0M | — | — | neutral | 0 |

All 4 rated **WATCH** — survived mechanical de-risk and have genuine theme membership, but none can clear the BUY bar (null MoS).
None sank (no AVOID / kill-flag ≥ 2). ASPI's 1 kill-flag was carried from cheap-pass but did not sink it.

**Watch-band (not deep-dived, surfaced for human review):** QUBT (Quantum Computing Inc., $2.4B) is a real quantum pure-play
but sits in the $2.0–5.0B watch band — correctly above the deep-dive ceiling. A human reviewing this theme should look at QUBT,
IONQ, RGTI etc. in the watch/large cohort; the tool deliberately does not deep-dive them (calibrated for micro/small-cap).

---

## 5. Every "BUY" with full reasoning — honest 0-BUY

**There are zero mechanical BUYs.** Per-name BUY-rule disposition:

| Ticker | mos_basis | numeric MoS | buy_eligible | buy_ineligible_reasons | BUY? | Why not |
|---|---|---|---|---|---|---|
| QNC | fcf_cap | **null** | true | (none) | **NO** | MoS is null (intrinsic_band_unavailable) — pre-rev, no XBRL; numeric MoS ≥ 30 unsatisfiable |
| BTQ | fcf_cap | **null** | true | (none) | **NO** | same — null intrinsic band, $0 XBRL financials |
| LWLG | fcf_cap | **null** | **false** | low_revenue_loss_ratio_extreme | **NO** | gated by extreme |NI|/rev (85.8×) AND null MoS |
| ASPI | fcf_cap | **null** | **false** | cross_source_mismatch | **NO** | gated by SEC-vs-yf debt 4.5× AND null MoS |

QNC and BTQ are the instructive cases: `buy_eligible == true` would tempt a naive pipeline into a BUY, but the **numeric-MoS
requirement is the backstop** — a pre-revenue company with no computable intrinsic value cannot produce a margin of safety, and
the rule correctly refuses to manufacture one. This is the "zero buys is a feature" principle operating on the single hottest
narrative theme in the test.

### Adversarial check (applied to the two `buy_eligible==true` names, the only ones that could be mistaken for opportunities)

- **QNC (Quantum eMotion):** *Is this a real opportunity or an artifact?* It is a real, validated quantum-security company
  (electron-based QRNG, TSMC 65nm tape-out, NYSE-American uplist Feb-2026) — **not a data artifact**. But it is **not a mechanical
  opportunity**: $0 revenue, $711M market cap on a pre-commercial QRNG, valuation is 100% narrative/option-value. The tool's
  abstain (null MoS, WATCH) is the correct verdict. Adversarial verdict: **artifact-free name, but correctly NOT a BUY — a
  $711M pre-revenue valuation is a speculation, not a margin-of-safety entry.**
- **BTQ (BTQ Technologies):** Real post-quantum-crypto + neutral-atom QC company, but $0 XBRL financials (40-F, edgartools could
  not parse a business body), $804M cap, pre-commercial. Same disposition. Adversarial verdict: **real company, correctly NOT a
  BUY; the $0-everything data picture is a foreign-filer XBRL gap, not evidence of value.**

**n_buy_clean = 0.** No BUY survived adversarial verification because no BUY existed.

---

## 6. Data-quality issues found (→ v0.3.1 backlog candidates)

1. **Foreign-filer (40-F/20-F) XBRL blackout.** QNC and BTQ returned **$0 revenue / $0 NI / $0 cash / null shares** — the entire
   financial picture is unavailable because the XBRL extraction does not handle these Canadian filers' tagging. The pipeline
   *correctly* abstained (so no false BUY), but for a hot theme dominated by foreign-domiciled quantum names this means the deep
   band is partly blind. **Backlog:** add a 40-F/20-F financial-statements fallback (e.g. parse the financial-report exhibit) so
   pre-rev foreign names get at least a cash/runway read rather than all-null.
2. **Empty `business_blurb` on real theme members.** QNC, BTQ, LWLG had blank blurbs from discover/cheap-pass — a blank blurb is
   a silent theme-fit hazard (an absent description reads as "no quantum content" and risks an automatic drop). I recovered them
   manually. **Backlog:** when `business_blurb` is empty, the Gate-2 stage should auto-fetch Item-1 rather than rely on the
   pre-extracted blurb.
3. **LWLG net-income XBRL unit mis-tag.** Data layer flagged NI −$20.3M implausibly large vs revenue $0.2M (possible unit
   mis-tag); valuation correctly fell back to OCF. The guard worked, but the underlying mis-tag should be logged for the XBRL
   concept-cascade backlog.
4. **Massive SIC-6221 crypto-trust contamination on "quantum".** 22 of 67 deep-band names (33%) were crypto ETFs/trusts that
   name quantum only as a risk factor. Gate-1 SIC exclusion did *not* drop SIC 6221 (it routed them to Gate-2 "review"), so the
   full LLM theme-fit pass had to clean them. **Backlog:** consider adding SIC 6221 (and 6199 crypto-treasury) to the Gate-1
   coarse-exclude list for non-crypto themes, or a "risk-factor-only keyword" heuristic — this would cut Gate-2 LLM load by ~40%.
5. **ASPI cross-source debt disagreement (4.5×).** SEC $58.3M vs yfinance $261.8M. Likely yfinance is rolling convertible notes
   / total liabilities into debt. The guard correctly blocked BUY; worth confirming which source is right for the trust banner.

---

## 7. Market-intel / T2 analyst context (never drives buy_eligible)

TrendsMCP quota was exhausted for the day (5/5 daily, 100/100 monthly), so no fresh trend pull was available. Qualitative T2
context from public knowledge through the Jan-2026 cutoff: quantum-computing search and news interest has been structurally
elevated through 2025–2026 on the back of hardware-milestone announcements (IBM/Google error-correction claims) and a retail
"quantum ETF" rotation that pulled IONQ/RGTI/QUBT/QBTS sharply higher. That narrative heat is precisely *why* the abstain
discipline matters here: the small-cap quantum cohort is priced on option value and momentum, not cash flows. None of this
context touched `buy_eligible` — it is recorded as analyst color only. The signals diagnostic side-channel (P16 price-divergence
/ P17 ownership) was emitted automatically and is firewalled: `valuation.py` contains zero references to the `signals` module
(the 4 grep hits for "signal" are generic comments about corroborating/data-integrity gates, not the P16/P17 channel), so
`buy_eligible` is byte-identical with vs without signals.

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** This run is decision-ready and behaved exactly as a disciplined scanner should on a hyped pre-revenue theme:

- It correctly **eliminated 63 of 67** deep-band names (crypto trusts, banks, off-theme tech) and isolated the **4 genuine
  quantum members** — including rescuing QNC and BTQ from empty-blurb false-drops.
- It returned **0 BUYs** for the right reason: a numeric margin of safety is unquantifiable for pre-revenue / zero-XBRL names,
  and the tool refused to fabricate one even where `buy_eligible == true`. This is the headline robustness result for the
  pre-rev-abstain path.
- The two real data limitations (foreign-filer XBRL blackout; empty-blurb auto-fetch) are **conservatively biased** — they push
  toward abstain, never toward a false BUY — so they degrade recall, not precision. For a skeptical PM, that is the correct
  failure direction.

**Bottom line for a PM:** the quantum small-cap universe contains no clean mechanical BUY at this time. The names worth a human's
attention (QNC, BTQ pure-plays; ASPI, LWLG enablers; QUBT in the watch band) are all speculations on commercialization, not
margin-of-safety entries — and the tool says so plainly.
