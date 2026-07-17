# Coverage Test, `refiners` (Energy)

> small-cap-deepdive **v0.3.0** (`f12fef5`) · run `2026-06-21_cov-refiners`
> THEME: `petroleum refining, fuel distribution` · code-path focus: **cyclical / thin-margin**
> **Verdict: honest 0-BUY.** All deep-band theme members fail `buy_eligible` on real guards, not on neglect.
> Research output, not investment advice.

---

## 1. Funnel

| Stage | Count | Note |
|---|---:|---|
| Raw discover (FTS + SIC reverse-recall + mktcap-fallback) | 36 candidates written | over-recall by design |
| cheap_pass survivors | 36 | (35 keep + 1 review), SIC gate kept 36 |
| Band split | 19 deep / 14 watch / 3 unknown | deep = <$2B small-cap band |
| LLM theme-fit gate (deep band) | **4 survive** / 15 misrecall | pure_play: CAPL, WKC, APC · partial: ARKO |
| Deep-dive (data + valuation) | 4 | every deep-band theme survivor, no sampling |
| `buy_eligible` BUYs | **0** | all 4 blocked |
| Adversarially-verified clean BUYs | **0** | |

**Discover funnel raw = 36, deep-dived = 4, survivors (BUY) = 0.**

The 14 watch-band names (DK, CVI, SUNC, PARR, CLMT etc., the actual mid-cap refiners at $2.5 to 5B) sit
*above* the small-cap ceiling by design; this skill is a small-cap scanner, so the true pure-play
refiners (Delek, CVR Energy, Par Pacific, Calumet) are correctly out of the deep band. What remains
small-cap-and-on-theme is **fuel distribution / convenience-retail**, not refining proper.

### Theme-fit gate detail (deep band, 19 → 4)

| Ticker | Name | SIC | Verdict | Why |
|---|---|---|---|---|
| **CAPL** | CrossAmerica Partners LP | 5172 | pure_play | wholesale motor-fuel distribution + retail fuel real estate |
| **WKC** | World Kinect Corp | 5172 | pure_play | global fuel fulfillment (aviation/marine/land) |
| **APC** | ARKO Petroleum Corp | 5172 | pure_play | wholesale fuel distributor, ~3,500 locations |
| **ARKO** | ARKO Corp | 5412 | partial | c-stores + wholesale fuel |
| UAN | CVR Partners LP | 2870 | misrecall | nitrogen fertilizer (not refining) |
| GHM | Graham Corp | 3560 | misrecall | equipment *supplier* to refiners |
| BOOM | DMC Global | 3390 | misrecall | perforating/clad-metal/construction |
| XNET | Xunlei | 7372 | misrecall | Chinese software |
| OEC | Orion SA | 2890 | misrecall | carbon black |
| HTZ | Hertz | 7510 | misrecall | car rental |
| FLNG | Flex LNG | 4400 | misrecall | LNG shipping |
| LPG | Dorian LPG | 4412 | misrecall | VLGC gas-carrier shipping |
| NMM | Navios Maritime | 4412 | misrecall | dry-bulk/tanker shipping |
| ULH | Universal Logistics | 4213 | misrecall | trucking/logistics (kf=1) |
| REEMF | Rare Element Res. | 1040 | misrecall | rare-earth mining |
| GPRK | GeoPark | 1311 | misrecall | upstream oil & gas E&P |
| CPAC | Cementos Pacasmayo | 3241 | misrecall | cement |
| ELVR | Elevra Lithium | 1400 | misrecall | lithium mining |
| AZUL | Azul SA | 4512 | misrecall | Brazilian airline in reorg (kf=1) |

The "fuel distribution" keyword is the recall driver here, SIC 5172 (petroleum bulk stations &
terminals) and 5412 (convenience stores) are the on-theme codes. "petroleum refining" pulled in a
long tail of shipping (4400/4412), E&P (1311), and equipment/materials names that the gate correctly
drops. 15/19 misrecall rate is high but expected for a broad two-keyword energy theme.

---

## 2. Ranked shortlist (all sink-band, 0 in watch/buy tier)

| Rank | Ticker | mos_basis | MoS | buy_eligible | Rev | NI | OCF | RevGr | kf |
|---:|---|---|---:|:---:|---:|---:|---:|---:|---:|
| 1 | APC | fcf_cap | n/a (band null) | ❌ | $0M* | $0M* | $0M* |, | 0 |
| 2 | ARKO | fcf_cap | **−103.5%** | ❌ | $7,644M | $23M | $193M | −12% | 0 |
| 3 | CAPL | abstain | n/a | ❌ | $3,662M | $9M | $92M | −11% | 0 |
| 4 | WKC | nav | **−92.0%** | ❌ | $36,917M | −$614M | $293M | −12% | 0 |

\* APC was carved out of ARKO in **July 2025**, no full standalone financial history yet, so the
data layer reports near-null financials and a null intrinsic band.

---

## 3. Per-name: full `buy_eligible` reasoning + adversarial verdict

### APC, ARKO Petroleum Corp (fuel distribution pure-play)
- **mos_basis** = `fcf_cap`; **intrinsic_value_band = null** → no numeric MoS.
- **buy_ineligible_reasons**: `cross_source_mismatch` (SEC total_debt 184.5M vs yf 754.6M, 4.1x).
- **Data quality**: `dep_amort_unavailable`, `capex_unavailable_fcf_uses_ocf_proxy`,
  `net_income_nonpositive_pe_null`, `normalized_ebitda_unavailable`, `normalized_fcf_unavailable`,
  `intrinsic_band_null`.
- **Why not BUY**: BUY needs mos_basis∈{fcf_cap,nav} AND numeric MoS≥30 AND buy_eligible. APC has no
  computable MoS and buy_eligible=false. Fails on two independent gates.
- **Adversarial verdict, NOT an opportunity, data-thin artifact.** APC is a 2025 carve-out; the
  filing covers a partial/predecessor period, so the financial series is structurally incomplete
  (this is the *wrong-entity / insufficient-history* failure mode the skill is built to catch, not a
  hidden mispricing). Correctly abstained. No re-band warranted.

### ARKO, ARKO Corp (c-stores + fuel, partial)
- **mos_basis** = `fcf_cap`; **MoS = −103.5%** (conservative fcf_cap equity band −$29M to +$105M vs
  $840M market cap → negative intrinsic equity at the low end).
- **buy_ineligible_reasons**: `extreme_mos_review_required` (|MoS|>100%), `cross_source_mismatch`
  (SEC 704.4M vs yf 2,353.1M debt, 3.3x, lease/debt classification gap typical of c-store roll-ups).
- **Why not BUY**: MoS is deeply negative (the opposite of ≥30 cheap) and the extreme-MoS guard fires.
- **Adversarial verdict, NOT an opportunity; genuinely expensive on conservative FCF cap.** ARKO is
  a debt+lease-heavy convenience-store roll-up; thin merchandise margins on $7.6B revenue produce only
  $23M NI. The negative intrinsic band is *directionally correct*, capitalizing trough-ish fuel-margin
  FCF at 9 to 12% against the lease-laden capital structure leaves little for equity. Not a data artifact;
  the cross_source_mismatch is a real lease-vs-debt classification issue but does not flip the sign.

### CAPL, CrossAmerica Partners LP (wholesale fuel distribution, pure-play MLP)
- **mos_basis** = `abstain` (fcf_cap blocked by C1 data-quality guard; NAV also unavailable).
- **kill flag**: `fundamental_decline`, `rev_slope_sign=-1, contamination_ratio=0.83, latest_below_avg`.
- **buy_ineligible_reasons**: `fundamental_decline_flag`, `cross_source_mismatch` (SEC 2.9M vs yf
  848.4M debt, **294x**, a gross SEC-XBRL debt-truncation miss; CAPL is a levered MLP, real debt ≈ yf).
- **Why not BUY**: abstain basis (no MoS) + an active fundamental_decline kill-flag. Two-gate failure.
- **Adversarial verdict, NOT an opportunity; correct abstain.** Even if the 294x debt mis-pull were
  hand-repaired, the fundamental_decline veto (declining revenue, latest below trailing average) stands,
  and CAPL as an MLP routes its cash to distributions, not retained FCF, exactly the thin-margin
  cyclical decay this code-path is meant to flag. The data artifact (debt truncation) is real and
  noted as a v0.3.1 backlog item, but it is **not** masking value.

### WKC, World Kinect Corp (global fuel fulfillment, pure-play)
- **mos_basis** = `nav` (fcf_cap unsuitable → NAV); **NAV MoS = −92.0%**.
- **buy_ineligible_reasons**: `debt_truncation_suspected` (reported 13.1M vs implied liab−equity
  4,387.5M, ratio≈0), `cross_source_mismatch` (SEC 13.1M vs yf 798.7M, 61x).
- **Data quality**: `concentration_unquantified` (text flag true, XBRL magnitude null),
  `net_income_nonpositive_pe_null`, `ebitda_nonpositive_ev_ebitda_null`, `fcf_cap_blocked`.
- **Why not BUY**: NAV MoS is −92% (price trades at ~12.5x tangible book after $740M goodwill +
  $305M intangibles deducted). Negative MoS, buy_eligible=false.
- **Adversarial verdict, NOT an opportunity; genuine no-buy.** WKC posted a −$614M net loss; its
  tangible equity ($159M) is dwarfed by its $1.6B market cap, so NAV gives −92%, a true premium to
  liquidation value, not an artifact. The debt-truncation flag is a real SEC-XBRL pull failure (a
  v0.3.1 item), but repairing it would *worsen* the picture (more debt → lower NAV), so it cannot
  hide upside.

---

## 4. Code-paths exercised (v0.3.0 mechanisms that fired)

| Code-path | Fired? | Where |
|---|:---:|---|
| Discover FTS over-recall | ✅ | 36 raw candidates from 2 keywords |
| SIC reverse-recall floor | ✅ | SIC 5172/5412/2911 enumerated + unioned (refining/fuel-dist SIC) |
| mktcap-fallback band assignment | ✅ | 3 unknown-cap (Entergy LLCs) demoted; deep/watch split at $2B |
| cheap_pass kill-flags | ✅ | flagged ULH/BCO/CLMT/AZUL/CSAN/BIPC (kf=1) at cheap stage |
| LLM theme-fit Gate 2 (misrecall drop) | ✅ | 19→4; survivors file written, finalize resolved 15 |
| **cyclical / thin-margin routing** (focus) | ✅ | fcf_cap chosen for APC/ARKO/CAPL; cap-rate 9 to 12% on normalized cyclical FCF |
| `fundamental_decline` veto | ✅ | CAPL (contamination 0.83) → kill-flag |
| `fcf_cap_blocked_by_c1_data_quality_guard` | ✅ | CAPL (abstain), WKC |
| NAV fallback routing | ✅ | WKC (fcf unsuitable → NAV, MoS −92%) |
| `extreme_mos_review_required` guard | ✅ | ARKO (MoS −103.5%) |
| `cross_source_mismatch` guard | ✅ | **all 4** (SEC-vs-yfinance debt disagreement) |
| `debt_truncation_suspected` guard | ✅ | WKC (implied debt 4.4B vs reported 13.1M) |
| wrong-entity / insufficient-history (intrinsic_band_null) | ✅ | APC (July-2025 carve-out) |
| `concentration_unquantified` | ✅ | WKC (text flag, XBRL null) |
| Trust banner in reports | ✅ | report_*.md headers carry data_quality + buy_ineligible |
| Signals firewall (price-divergence diagnostic) | ✅ | embedded in every deepdive JSON, did **not** affect buy_eligible |
| finalize_run completeness assert + gate2-misrecall resolution | ✅ | 19 deep / 4 reports / 15 resolved / 0 missing |

**Not exercised** (no on-theme name triggered): foreign/IFRS routing on a *survivor* (the IFRS names
were all misrecalls), pre-rev abstain, peak_contamination V-shape veto, low_revenue_loss_extreme,
financial-SIC/insurance kill, large-cap truncation on a survivor.

---

## 5. Data-quality issues found (→ v0.3.1 backlog)

1. **Pervasive SEC-XBRL debt truncation / cross_source_mismatch on all 4 survivors.** CAPL 294x,
   WKC 61x, APC 4.1x, ARKO 3.3x. The SEC `total_debt` pull is systematically *under*-reading debt for
   levered MLPs and lease-heavy c-store operators (likely picking a single debt tag instead of summing
   current+long-term + finance leases). yfinance is closer to truth. **This is the highest-yield finding:**
   the guard correctly *blocks* BUY on mismatch, but the underlying SEC pull should be fixed so the guard
   stops firing on legitimately-financeable names. Right now it would block even a genuinely cheap MLP.
2. **debt_truncation_suspected (WKC)**: reported 13.1M vs implied (liab−equity) 4.39B. Same root cause
   as #1, confirms the debt-tag selection bug.
3. **Carve-out / partial-period entities (APC)** produce null intrinsic bands. The skill abstains
   correctly, but a `recent_carveout` explicit flag (date-of-incorporation < 12mo) would make the abstain
   reason cleaner than the current cascade of `*_unavailable` warnings.
4. **MLP distribution vs retained-FCF**: CAPL/UAN are pass-through partnerships; fcf_cap on retained FCF
   understates the cash actually returned to LPs. A distribution-aware MLP routing branch (noted in spec
   as "midstream-mlp / financial-ish routing") would value these more faithfully, though it would not
   have changed CAPL's no-buy (fundamental_decline stands).

None of these data issues *caused a false BUY*; they caused correct abstentions. The risk they pose is
**false negatives** (blocking a clean MLP), which is the right error to make for a landmine scanner.

---

## 6. recall@gold

**n/a**, `refiners` is not one of the four gold-list themes (water-utilities, railcar-leasing,
regional-gaming, deathcare). `track_forward.py --recall-gold --theme refiners` not applicable (no
`THEME_GOLD` entry). No measured recall floor for this theme.

---

## 7. Market-intel / TrendsMCP context (T2 analyst color, does NOT drive any buy_eligible)

- TrendsMCP, "gas prices" Google-search interest: **+150% YoY** but **−62% over trailing 3 months**
, the classic spring-peak → summer decay seasonal pattern in retail attention. Soft macro color only.
- Refining/fuel-distribution is a **thin-margin cyclical**: crack spreads and fuel margins are the swing
  variable, and 2025 to 26 has been a normalizing (down) margin year off the 2022 to 23 peak. This is *consistent*
  with the fundamental_decline / declining-revenue signatures the data layer flagged on CAPL (−11%) and
  the negative-NI on WKC. The cyclical framing supports the skill's caution rather than contradicting it.
- market-intel local repo has no refining/energy sector report in its catalog at run time, so no T2
  deep report to cite. This is enrichment context only and was firewalled from the buy decision.

---

## 8. Skeptical-PM usable verdict

**USABLE, and a clean demonstration of the skill's core value (eliminating, not picking).**

For a small-cap PM, this run correctly tells you: in the *small-cap* slice of refining + fuel
distribution, there is **nothing to buy** today. The real refiners (DK, CVI, PARR, CLMT) are mid-caps
above the band and were routed to watch; what remains small-cap is fuel-distribution/c-store roll-ups
(ARKO, CAPL) trading at-or-above conservative intrinsic value, a brand-new carve-out with no history
(APC), and a money-losing fuel-services name at a steep premium to tangible book (WKC). Every exclusion
is defensible on a real guard, every adversarial check confirms the no-buy, and the only data bugs found
(SEC debt truncation) push toward *over*-caution, not toward false positives.

**0 BUYs, 0 adversarially-verified BUYs, honest, decision-ready output.** The v0.3.1 backlog item worth
escalating is the systematic SEC `total_debt` under-read on MLP / lease-heavy issuers.
