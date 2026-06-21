# Coverage Test — Theme: Cybersecurity (InfoTech)

- **Slug:** `cybersecurity`
- **Sector:** InfoTech
- **Keywords (FTS):** `cybersecurity, network security, endpoint`
- **Code-path focus:** SaaS / OCF-proxy / growth
- **Skill version:** v0.3.0 (commit `f12fef5`)
- **Run batch:** `2026-06-21_cov-cybersecurity` (system clock ran one day ahead of the 2026-06-20 label)
- **Headline result:** **0 BUYS — clean.** A correct "nothing found" for the small-cap cybersecurity universe under v0.3.0 guards.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw universe (EDGAR FTS ∪ SIC-reverse-recall floor, mktcap-fallback) | **1132** | No dedicated SIC code for "cybersecurity" → discovery is FTS-dominated. The keyword `endpoint`/`security` is now near-universal in 10-Ks (every filer has an *Item 1C Cybersecurity* section), so FTS recall is enormous and precision is terrible. |
| After `cheap_pass` (hard kill-flags) → SIC gate | **34** | cheap_pass scanned 58 small-cap survivors; SIC filter kept 34 (13 `keep`, 21 `review`→LLM gate). ATER killed (kf=2). |
| Deep band (band=`deep`, ≤ small-cap ceiling) | **25** | Every one deep-dived — no sampling. |
| Watch band (band=`watch`, theme-fit only, no deep-dive) | 9 | NTCT, TDC, TENB, DAN, VTMX, RHI, FIZZ, CNS, RELY, IBOC, BB (mid-caps above deep ceiling). |
| Deep-dived (deepdive_data + valuation) | **25 / 25** | 0 ERROR files, 0 missing. |
| Reports + verdicts | **25** | finalize_run: 25 verdicts, RANKING rebuilt, 0 missing. |
| **Mechanical BUYS (rule below)** | **0** | |
| **Clean BUYs after adversarial verification** | **0** | |

**Funnel banner artifact:** RANKING.md prints "26 家逐一 deep dive" — a cosmetic off-by-one in the rank.py count line. Verified on disk: exactly 25 deepdive JSONs, 25 valuation JSONs, 25 reports. No coverage gap.

---

## 2. LLM theme-fit gate (true membership from blurbs)

The keyword set produced **massive misrecall** — the dominant failure mode of this theme. Of 25 deep-band names, the large majority are off-theme industrials/financials/biotech/consumer that merely contain "security", "endpoint" or an *Item 1C Cybersecurity* paragraph:

- **Off-theme misrecall (19):** EML (industrial hardware), PEBK/IBCP (banks), ESCA (sporting goods), FRD (steel), VALU (investment research pub), MSB (iron-ore royalty trust), IMMX (CAR-T biotech), AMWD (cabinets), GSG (commodity-index futures trust), NPK (housewares/defense), SENEA (canned food), FOR (residential land dev), GSHD (insurance brokerage), GOGO (in-flight connectivity), LDI (mortgage lender), plus NVEC (spintronics sensors), NEON (machine-perception optics — adjacent but not cyber), ASGN (IT staffing — adjacent).
- **Genuine / partial cybersecurity members (6):**
  - **OSPN** (OneSpan) — *pure-play*: authentication, fraud prevention, mobile-app protection + digital agreements. The cleanest true member.
  - **FATN** (FatPipe) — *pure-play/strong-partial*: secure SD-WAN + integrated single-stack cybersecurity. Micro-cap ($74M).
  - **QNC** (Quantum eMotion) — *partial/speculative*: quantum RNG for cyber/crypto. Pre-revenue micro.
  - **DMRC** (Digimarc) — *partial-adjacent*: digital watermarking / product authentication / anti-counterfeit.
  - **ZD** (Ziff Davis) — *partial*: diversified digital-media conglomerate; cybersecurity (VPN/consumer-security brands) is one vertical, not the business.
  - **NEON** (Neonode) — borderline; machine-perception, not security. Treated as adjacent, not a member.

Recall is unmeasurable here (no gold list — see §6), but precision is the visible problem: ≈ 6/25 true membership in the deep band.

---

## 3. BUY rule application — every deep-band survivor

**BUY rule (v0.3.0):** `mos_basis ∈ {fcf_cap, nav}` AND numeric **MoS ≥ 30%** AND `buy_eligible == true` AND **0 kill-flags**. `buy_eligible` already ANDs every v0.3.0 guard.

| Ticker | basis | MoS (used) | buy_eligible | kf | BUY? | Dominant ineligibility / fail reason |
|---|---|---:|:--:|:--:|:--:|---|
| EML | fcf_cap | -89.1% | False | 0 | No | fundamental_decline_flag |
| DMRC | nav | -96.3% | False | 0 | No | wrong_entity_suspected |
| PEBK | nav | -43.9% | False | 0 | No | financial_sic_forced_unsuitable, cross_source_mismatch |
| ESCA | fcf_cap | -35.8% | **True** | 0 | No | MoS negative (well below +30%) |
| FRD | fcf_cap | -149.8% | False | 0 | No | extreme_mos_review_required |
| VALU | nav | -74.3% | **True** | 0 | No | NAV MoS negative |
| MSB | abstain | n/a | False | 0 | No | financial_sic_forced_unsuitable, cross_source_mismatch (royalty trust → abstain) |
| NVEC | fcf_cap | -77.5% | False | 0 | No | cross_source_mismatch (rev SEC 1.1M vs yf 26.3M, 23.7×) |
| IMMX | fcf_cap | null | False | 0 | No | cross_source_mismatch (clinical biotech) |
| AMWD | nav | -81.2% | False | 0 | No | debt_truncation, fundamental_decline, cross_source_mismatch |
| ASGN | nav | -100% | False | 0 | No | wrong_entity_suspected |
| GSG | fcf_cap | -0.4% | False | 0 | No | fcf_sustainability_uncertain (futures trust, lumpy OCF) |
| NPK | fcf_cap | null | False | 0 | No | cross_source_mismatch |
| SENEA | fcf_cap | null | False | 0 | No | cross_source_mismatch |
| BLKB | fcf_cap | -40.5% | **True** | 0 | No | MoS negative |
| FATN | fcf_cap | null | **True** | 0 | No | MoS null (no usable FCF cap) |
| IBCP | nav | -45.5% | False | 0 | No | financial_sic_forced_unsuitable, cross_source_mismatch |
| FOR | fcf_cap | null | False | 0 | No | cross_source_mismatch |
| NEON | fcf_cap | null | **True** | 1 | No | MoS null AND kf=1 |
| OSPN | fcf_cap | -92.9% | False | 1 | No | cross_source_mismatch (debt SEC 111M vs yf 8M) + kf=1 |
| GSHD | nav | -100% | False | 1 | No | financial_sic_forced_unsuitable + kf=1 |
| **ZD** | fcf_cap | **+21.0%** | **True** | 1 | No | **highest MoS in theme but < 30% gate AND kf=1** |
| QNC | fcf_cap | null | **True** | 0 | No | MoS null (pre-revenue, no FCF) |
| GOGO | nav | -100% | **True** | 1 | No | NAV MoS negative + kf=1 |
| LDI | abstain | n/a | False | 0 | No | financial_sic_forced_unsuitable, cross_source_mismatch |

**Result: 0 mechanical BUYS.** The single name with positive MoS (ZD, +21%) sits below the +30% gate and also carries a kill-flag. Every `buy_eligible==true` name fails on MoS (negative or null). No adversarial verification needed for any name (none cleared the mechanical bar), so `n_buy_clean = 0`.

---

## 4. Code-paths exercised (vs the SaaS/OCF-proxy/growth focus)

- **SaaS / fcf_cap path:** fired on the software/SaaS-style names (OSPN, BLKB, ZD, FATN, QNC, ESCA, NVEC, GSG, NPK, SENEA, FOR, IMMX, EML, FRD, NEON). This is the intended code-path focus and it ran on every applicable name.
- **OCF-proxy path:** explicitly fired on capital-intensive / no-capex names — GSG (`capex_unavailable_fcf_uses_ocf_proxy`, `fcf_equals_ocf_proxy_no_capex`), and the `lumpy_ocf_normalization_suspect` guard tripped on GSG (peak-year OCF 565M > 2× median).
- **NAV path:** fired on asset-heavy / financial names (DMRC, PEBK, VALU, AMWD, ASGN, IBCP, GSHD, GOGO).
- **abstain path:** MSB (royalty trust) and LDI (mortgage) correctly routed to abstain.
- **Guards that fired:** `financial_sic_forced_unsuitable` (PEBK, MSB, IBCP, GSHD, LDI), `cross_source_mismatch` (10 names — the single most common BUY-blocker), `wrong_entity_suspected` (DMRC, ASGN), `debt_truncation_suspected` (AMWD), `fundamental_decline_flag` (EML, AMWD), `extreme_mos_review_required` (FRD), `fcf_sustainability_uncertain` (GSG), `lumpy_ocf_normalization_suspect` (GSG), `peak_contamination` (GSG contamination_ratio computed), `large_cap_out_of_scope` ceiling held the band split.
- **Diagnostic signals (firewalled):** emitted per-ticker in the T2 section of each report; verified `diagnostic_only=True, never_affects_buy=True`. Did not touch any buy_eligible.

---

## 5. Data-quality issues

1. **Theme-keyword precision collapse.** `cybersecurity/network security/endpoint` is a low-specificity keyword set in the post-*Item 1C* era — every 10-K mentions cybersecurity. ≈ 6/25 deep-band names are true members. The LLM theme-fit gate is doing real work here, but the discovery floor (1132 raw) is dominated by noise. A dedicated SIC floor does not exist for this theme.
2. **cross_source_mismatch is the dominant blocker (10/25).** SEC-vs-yfinance disagreements >2.5× (e.g. NVEC revenue 23.7×, OSPN debt 13.9×). This is the guard working as designed, but it also means yfinance coverage for micro-caps is unreliable enough that the second-source check vetoes many names on a *data* artifact rather than a *fundamental* one. For the true cyber names (OSPN especially) this is the binding constraint, not valuation.
3. **GSG (commodity-index futures trust)** required a `--mktcap` override (yfinance returned null mktcap). Correctly handled; the trust is off-theme noise regardless.
4. **MoS null on several SaaS/micro names** (FATN, QNC, NPK, SENEA, FOR, IMMX, NEON) — no usable FCF cap (pre-revenue, lumpy, or loss-making), so fcf_cap yields no MoS. Correct null, not a crash.
5. **T2 enrichment unavailable:** TrendsMCP daily+monthly quota exhausted at run time; no pre-built cybersecurity market-intel catalog. T2 context below is domain-knowledge, labeled as such.

---

## 6. recall@gold

**n/a.** Cybersecurity is not in `THEME_GOLD` (the four gold themes are water-utilities, railcar-leasing, regional-gaming, deathcare). `track_forward.py --recall-gold ... --theme cybersecurity` returns "no gold list for theme 'cybersecurity' — not measurable." Recall floor is therefore not quantified for this theme; precision (≈6/25 true membership) is the observable, and it is poor by construction of the keyword set.

---

## 7. Market-intel / T2 analyst context (labeled — never drives buy_eligible)

> Source caveat: TrendsMCP quota exhausted this run; the following is general domain context, T2 only.

- The small/mid-cap pure-play cybersecurity cohort that *would* be interesting (TENB Tenable, NTCT NetScout, BB BlackBerry, RPD, S-1-stage names) mostly sits in the **watch band** above the deep-band ceiling — i.e., the genuine listed cyber names are not micro-caps. The deep band is left with sub-scale players (OSPN, FATN, QNC) and noise.
- **OSPN (OneSpan)** is the one structurally-real candidate: profitable ($73M NI, $60M OCF on $243M rev), genuine cybersecurity portfolio, undergoing a SaaS transition. It was blocked by a *data* guard (debt cross-source mismatch) and negative computed fcf_cap MoS + 1 kill-flag — worth a human re-pull of clean financials, but mechanically it is a non-BUY and the negative MoS suggests it is not cheap on a normalized-FCF basis.
- **ZD (Ziff Davis)** carries the only positive MoS (+21%) but is a diversified media holdco, not a cyber pure-play; the theme attribution is weak and it does not clear the 30% gate.

This context is illustrative only; it did not and cannot move any BUY decision.

---

## 8. Adversarial verdict

No name cleared the mechanical BUY bar, so there is no BUY to adversarially defend. The closest objects of suspicion — ZD (+21% MoS) and OSPN (real cyber, profitable) — are **correctly excluded**: ZD by the sub-30% gate + theme-mismatch + kill-flag; OSPN by a cross-source data mismatch and negative normalized-FCF MoS. Neither is a missed opportunity hiding behind an over-strict guard; both are genuinely either not-cheap or not-clean. The 0-BUY outcome is a true negative, not a guard false-positive.

---

## 9. Skeptical-PM usability verdict

**USABLE.** For a skeptical PM, this run delivers exactly what the scanner is supposed to: it enumerated a noisy 1132-name universe, mechanically eliminated the off-theme and unfinanceable names, and returned an honest **0 BUYS** with a transparent reason for each rejection. The landmine-scanner value is high (it killed banks, trusts, biotech, and a futures ETF that the keyword swept in), and it did not manufacture a narrative BUY from the one marginally-positive-MoS name. The one caveat a PM should internalize: the binding constraint on the genuine cyber names was **data quality (cross-source mismatch), not valuation** — so "0 BUYS" here partly reflects unreliable micro-cap second-source data, and OSPN specifically merits a manual clean-data re-pull before being dismissed.

---

### Artifacts (absolute paths)
- Run dir: `C:\Users\dzdon\CodesSelf\small-cap-deepdive\reports\smallcap\2026-06-21_cov-cybersecurity\`
- Candidates: `...\candidates_cybersecurity.json`
- RANKING: `...\RANKING.md`
- Verdicts: `...\deepdive_verdicts.json`
- Per-ticker: `deepdive_<T>_*.json`, `valuation_<T>_*.json`, `report_<T>.md` (25 each)
