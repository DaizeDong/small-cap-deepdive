# Coverage test — `adtech` (Advertising Technology / Digital Advertising)

- **Run batch:** `2026-06-21_cov-adtech`  (`reports/smallcap/2026-06-21_cov-adtech/`)
- **Skill version:** v0.3.0 @ `f12fef5` (config-dirty: only `config.json` UA override present — expected)
- **Theme:** slug `adtech`, sector CommSvcs, keywords `advertising technology, digital advertising`
- **Code-path focus:** growth / cyclical ad-spend valuation (FCF-cap normalization, cyclical CV gate, peak-contamination guard)
- **Date:** 2026-06-21 (UTC)
- **Status:** COMPLETE — 24/24 deep-band survivors deep-dived + valued, 0 ERROR files, RANKING + verdicts emitted.

> **Bottom line:** **0 clean BUYs.** Exactly one name (SCOR / Comscore) passed the mechanical BUY rule
> (fcf_cap MoS 39.8%, buy_eligible, zero kill-flags) but **fails adversarial review** and is downgraded
> to WATCH. The adtech small-cap universe screens as a no-edge cohort: the survivors are GAAP-lossmaking,
> ad-cyclical, or trade at/above intrinsic value (most MoS are deeply negative). This is the expected
> outcome for a *hot, ETF-covered theme* (PHILOSOPHY commitment #2: hot themes are the casino).

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw FTS hits (SEC full-text, 10-K/10-Q/20-F/40-F) | **348** | No SIC recall floor — `adtech` is **not** in `THEME_SIC`, so discovery is pure FTS over-recall. |
| Market-cap banded | 105 deep / 19 watch / 31 large / 193 unknown | deep = mktcap < $2.0B; 193 unknown (no resolvable mktcap) dropped pre-cheap-pass. |
| Into cheap_pass | 93 | banded deep+watch rows with a resolvable ticker. |
| cheap_pass survivors | **53** | 40 rejected on hard kill-flags (going-concern / death-spiral / material-weakness / not-found). |
| SIC tri-state gate | 53 (keep=19, review=34) | `sic_classify` returned no `drop`; all 53 forwarded (review → LLM gate). |
| **Candidates JSON** | **53** (37 deep + 16 watch) | watch-band (16) surfaced for human review only — not deep-dived (band guard C3). |
| LLM theme-fit (Gate 2, this agent) on 37 deep | **24 survivors** | 9 pure_play + 15 partial; **13 misrecall dropped**. |
| Deep-dive + valuation | **24 / 24** | 0 ERROR files; all wrote `deepdive_*` + `valuation_*` JSON. |
| Mechanical BUY rule | **1** (SCOR) | mos_basis∈{fcf_cap,nav} ∧ MoS≥30 ∧ buy_eligible ∧ 0 kill-flags. |
| **Clean BUY after adversarial** | **0** | SCOR downgraded — see §4. |

**Gate-2 theme-fit decisions (37 deep-band):**
- **pure_play (9):** DV, TBLA, DSP, MNTN, PUBM, CRTO, NEXN, PERI, SCOR — true adtech platforms/measurement/programmatic.
- **partial (15):** STGW, OPRA, EVC, ZD, TSQ, NCMI, XPER, YELP, IHRT, GTN, SOHU, LEE, SGA, AMCX, VBIX — meaningful ad/adtech segment but mixed (agency networks, media owners selling ads, browsers, broadcasters).
- **misrecall, dropped (13):** COUR (e-learning), NMAX (news media), GDRX (Rx-savings/healthcare), VTEX (e-commerce SaaS), DDI (mobile casino games), MDRX (healthcare IT), OOMA (VoIP), TMCR (metals royalty), CHGG (edu), SKIN (medical aesthetics), EHTH (insurance marketplace), RVYL (payments), RSKD (e-commerce fraud-prevention — not advertising).

---

## 2. Ranked shortlist (non-bottom = 观察/WATCH; no 买入/BUY exists)

| # | Ticker | Name | Rating | MoS% (basis) | buy_eligible | Why not BUY |
|---|---|---|---|---:|---|---|
| 1 | SCOR | Comscore | 观察 | **+39.8 (fcf_cap)** | ✅ | mechanical BUY → **adversarial downgrade** (thin/fragile FCF, see §4) |
| 2 | LEE | Lee Enterprises | 观察 | -100 (nav) | ✅ | NAV MoS deeply negative; FCF-cap unsuitable; OCF negative |
| 3 | NEXN | Nexxen Intl (20-F) | 观察 | None | ✅ | MoS unavailable — `intrinsic_band_unavailable` (FCF not extractable from 20-F) |
| 4 | OPRA | Opera (20-F) | 观察 | None | ✅ | MoS unavailable — same 20-F extraction gap (also has 1 advisory flag) |
| 5 | STGW | Stagwell | 观察 | -84.0 (fcf_cap) | ✅ | MoS deeply negative (trades far above FCF-cap intrinsic) |
| 6 | TBLA | Taboola | 观察 | -40.6 (fcf_cap) | ✅ | MoS negative; cyclical |
| 7 | XPER | Xperi | 观察 | None | ✅ | MoS unavailable — `intrinsic_band_unavailable` |
| 8 | ZD | Ziff Davis | 观察 | +21.0 (fcf_cap) | ✅ | eligible but **MoS 21 < 30** threshold |
| 9–24 | (bottom) | AMCX, CRTO, DSP, DV, EVC, GTN, IHRT, MNTN, NCMI, PERI, PUBM, SGA, SOHU, TSQ, VBIX, YELP | 避开 | various | ❌ | buy_eligible=false — a guard fired (see §5) |

Full per-name DD: `report_<ticker>.md` in the run dir. Machine ranking: `RANKING.md`.

---

## 3. BUYs — full reasoning

There are **no clean BUYs**. The single name that cleared the mechanical rule is documented here in full,
followed by its adversarial verdict.

### SCOR — Comscore, Inc. (mechanical BUY → adversarial DOWNGRADE → WATCH)

**Mechanical BUY rule, term by term (all satisfied):**
- `mos_basis = fcf_cap` ∈ {fcf_cap, nav} ✅
- numeric MoS = **+39.75%** ≥ 30 ✅ (intrinsic equity band $167.7M–$228.4M vs market cap $120.0M)
- `buy_eligible = true` ✅ — and `buy_ineligible_reasons = []` (zero guards fired)
- zero kill-flags: no going-concern, no material-weakness, no death-spiral, `concentration_flag=null`,
  `fundamental_decline_flag=false`, `peak_contamination_flag=false` (contamination_ratio 0.99 — latest FCF ≈ 5yr-avg, not peak),
  `cross_source_mismatch=false` (2nd source within 2.5x), `extreme_mos_review_required=false` ✅

So the deterministic guard-composite half of the contract is genuinely clean — this is **not** a guard miss.

### 4. Adversarial verdict on SCOR — **DATA/MODEL-FRAGILE, not a real opportunity → WATCH**

The 39.75% MoS is mechanically valid but economically thin. The skeptical-PM cross-exam:

1. **GAAP losses every single year.** Net income: -$10M (2025), -$60M (2024), -$79M (2023), -$67M (2022), -$50M (2021).
   The "value" is entirely a function of non-cash add-backs (stock-comp + D&A on $248M goodwill). The FCF-cap model
   capitalizes OCF–capex while the business has never earned a GAAP profit.
2. **Declining, no-growth top line.** Revenue fell $376M (2022) → $356M (2024) → $357M (2025); `rev_slope_sign=-1`,
   `rev_accel_sign=-1`. Reverse-DCF implied growth = **-8.2%** — the market is correctly pricing decline, and the
   FCF-cap model assumes a flat perpetuity. The decline is mild enough to stay *below* the `fundamental_decline_flag`
   threshold, which is exactly why the guard did not catch it.
3. **Freshly-and-barely-positive, volatile OCF.** OCF went -$73M (2018) → +$0.7M (2020) → +$35M (2022) → $18–23M (2024–25).
   The trailing-5yr-avg normalization ($21.85M FCF) capitalizes a stream the company only recently produced and that
   carries `cv_ebitda=0.55` (flagged cyclical). A PM cannot trust "$22M sustainable FCF" for a shrinking measurement
   business facing cookie-deprecation / measurement-commoditization pressure.
4. **Insider signal is net-sell** (0 buys / 3 open-market sells) — no management conviction to offset the above.
5. **Data gaps:** `normalized_ebitda_unavailable`, `dep_amort_unavailable` — the FCF proxy rests on OCF–capex with no
   D&A cross-check (trust-banner surfaced).

**Verdict:** the MoS is a real-but-fragile artifact of FCF-capitalizing a recently-positive cash stream on a
structurally declining, perpetually-GAAP-lossmaking, ad-cyclical measurement business with insider selling. It does
**not** survive "is sustainable FCF really $22M?" → **WATCH, not BUY.** `n_buy_clean = 0`.

---

## 5. Which code-paths fired (coverage evidence)

The growth/cyclical ad-spend focus exercised the intended valuation machinery. Guard-fire tally across the 24 valuations:

| Guard / code-path | Fired on | Role |
|---|---:|---|
| `peak_contamination_flag` (V-shape / peak-FCF) | 7 (EVC, GTN, IHRT, NCMI, PERI, SGA, TSQ) | cyclical ad-spend peak guard — **central to this theme** |
| `cross_source_mismatch` (SEC vs yfinance >2.5x) | 7 (CRTO, DV, PERI, PUBM, VBIX, YELP, +) | data-integrity gate on buy_eligible |
| `fundamental_decline_flag` | 4 (EVC, PERI, SGA, SOHU) | declining-revenue downgrade |
| `fcf_sustainability_uncertain` | 3 (AMCX, GTN, MNTN) | FCF-quality flag |
| `financial_sic_forced_unsuitable` + `insurance_concepts_present` | 2 each (DSP, TSQ) | SIC/insurance NAV-route + concept guard |
| `extreme_mos_review_required` (|MoS|>100%) | 1 (GTN, -835%) | extreme-MoS backstop |
| `wrong_entity_suspected` | 1 (VBIX) | entity-mismatch guard |
| `debt_truncation_suspected` | 1 (DSP) | debt-truncation guard |

Other paths exercised: **SIC tri-state** `sic_classify` (keep=19/review=34, no drop); **mktcap fallback** banding
(105 deep / 19 watch / 31 large / 193 unknown); **band guard C3** (16 watch-band candidates surfaced but not deep-dived);
**cyclical CV gate** (`cyclical=true` on TBLA, SCOR, STGW, LEE, GTN, NCMI, …); **NAV route** for 9 names where
`fcf_cap_model_unsuitable`; **abstain** route = 0 (every name resolved to fcf_cap or nav). The **signals side-channel**
was emitted into each deepdive JSON and is firewalled — it does not appear in any `buy_ineligible_reasons` or rating block.

**MoS-basis distribution:** fcf_cap = 15, nav = 9, abstain = 0.

---

## 6. Data-quality issues

1. **No SIC recall floor for adtech.** `adtech` is absent from `THEME_SIC`, so discovery is pure FTS over-recall
   (348 raw, ~35% true-membership after Gate 2). Adtech is genuinely SIC-scattered (7311/7370/7372/7374/7389/4832/4833/4841/2711/8200),
   so a single-SIC floor would not help much — but there is **no recall floor**, so any pure-play that never used the
   exact keyword phrase in a 10-K is silently missed. Recall is unmeasured (no gold list — see §7).
2. **20-F FCF extraction gap.** 3 of 4 foreign filers (NEXN, OPRA, SOHU; XPER is a 10-K but same symptom) returned
   `intrinsic_band_unavailable` → MoS = None because `normalized_fcf` could not be extracted. These names are
   buy_eligible (no guard fired) yet **uninvaluable** — a coverage hole that lets a foreign adtech name sit at WATCH
   with no MoS rather than being properly ranked. ~17% of survivors (4/24) are MoS-blind.
3. **MoS stored as fraction.** `margin_of_safety_pct` is a fraction (0.3975 = 39.75%); the BUY rule's "MoS≥30" must
   compare `frac*100`. A naive reader comparing the raw 0.3975 to 30 would wrongly conclude 0 BUYs for the wrong reason.
   (Confirmed against valuation.py line 555 `_active_mos*100`.) Noted so the funnel number is trustworthy.
4. **GAAP-loss adtech names get FCF-cap "value."** SCOR/MNTN/etc. carry `net_income_nonpositive_pe_null` yet the
   FCF-cap model still produces an intrinsic band. The guards downgrade most via cross-source/contamination/decline,
   but SCOR slipped through to a mechanical BUY — the adversarial layer (human) is doing real work here.
5. **cross_source_mismatch on 7 names** indicates SEC-vs-yfinance market-cap/financial disagreement >2.5x on common
   adtech names (DV, CRTO, YELP, PUBM) — likely ADR/share-class/units issues; correctly blocks BUY rather than trusting a corrupt number.

---

## 7. recall@gold

**n/a** — `adtech` has no gold list in `THEME_GOLD` (gold lists exist only for water-utilities, railcar-leasing,
regional-gaming, deathcare). Verified: `track_forward.py --recall-gold candidates_adtech.json --theme adtech` →
*"no gold list for theme 'adtech' — not measurable."* Recall is therefore unquantified for this theme.

---

## 8. Market-intel / TrendsMCP context (T2 — analyst color only, does NOT drive buy_eligible)

- **TrendsMCP:** quota exhausted for the day (5/5 daily, 100/100 monthly) — no fresh trend pull available this run.
- **market-intel (`/c/Users/dzdon/CodesSelf/market-intel`):** no pre-built adtech report in the catalog.
- **Analyst color (domain knowledge, T2, non-load-bearing):** digital-advertising small-caps are a textbook
  "hot theme = casino" cohort — heavily ETF-indexed, cyclically levered to ad budgets, and facing structural
  pressure (cookie deprecation, measurement commoditization, walled-garden share gains by Google/Meta/Amazon).
  The screen result (every survivor either lossmaking, declining, or trading at/above intrinsic value) is consistent
  with a theme whose alpha was captured pre-coverage. None of this changed any `buy_eligible` value.

---

## 9. Skeptical-PM usable verdict

**USABLE — as a landmine-scanner, not a buy generator.** The run did exactly what the skill claims: systematic coverage
(348 → 24 fully deep-dived, 0 errors), consistent guard application, and a defensible 0-BUY. The cyclical/peak guards
fired on the right names (7 peak-contamination on broadcasters/cinema/ad-cyclicals), and the one name that beat the
mechanical rule (SCOR) is a genuinely close call that the adversarial layer correctly downgraded — not a slam-dunk the
model missed, nor a garbage artifact it waved through. **Honest 0-BUY.**

Caveats a PM must hold: (a) recall is unmeasured (no SIC floor, no gold) — treat the universe as a *floor*, not complete;
(b) 4/24 survivors are MoS-blind (20-F extraction gap) and should be hand-valued before any are dismissed; (c) the theme
itself is structurally low-edge, so even the WATCH list (ZD at +21% MoS is the most interesting) warrants skepticism
about FCF durability before any capital.
