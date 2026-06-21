# Coverage Test — Gold & Silver Miners (Materials)

- **Slug:** `gold-silver-miners`
- **Sector:** Materials
- **Keywords:** `gold mining, silver mining, precious metals`
- **Skill version:** small-cap-deepdive v0.3.0 (commit `f12fef5`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-gold-silver-miners/`
- **Date:** 2026-06-21 (UTC run; coverage-test bucket 2026-06-20)
- **Code-path focus:** foreign-IFRS (20-F / 40-F), pre-revenue / development-stage, `low_revenue_loss`
- **Verdict:** **0 BUY** (honest zero). 31 deep-dived survivors → all **WATCH (观察)**.

> Research output, not investment advice. This skill is a landmine-scanner, not a buy list.

---

## 1. Funnel

| Stage | Count | Note |
|---|---:|---|
| Raw discovery (FTS + mktcap filter) | 123 | `discover.py` over FTS keywords; no SIC reverse-recall floor exists for this theme (gold/silver SIC 1040/1000 not in `THEME_SIC`) |
| `cheap_pass` survivors | 83 | 40 eliminated on hard kill-flags (going-concern / death-spiral / material-weakness in cheap-pass scan) |
| SIC gate (keep + review) | 83 | keep=58, review=25 (review → LLM gate) |
| **Deep band** (mktcap < $2.0B) | **54** | 29 names sat in the watch band ($2.0B–$4.6B) — surfaced, not deep-dived |
| Gate-2 theme-fit **keep** (pure_play / partial) | **31** | 23 deep-band names dropped as misrecall (resolved, not missing) |
| Deep-dived (deepdive_data + valuation) | **31** | 0 crashes, 0 `deepdive_*_ERROR.json` |

**Discovery floor note.** `gold-silver-miners` has **no SIC reverse-recall floor** (only water-utilities / railcar-leasing / regional-gaming / deathcare are mapped in `THEME_SIC`). Recall here rests entirely on the FTS arm + mktcap fallback. The FTS arm did **not** hit the 1000-hit cap (123 raw), so recall is not cap-truncated, but a true small member with an unlucky keyword phrasing and SIC 1040 is **not** backstopped by a SIC enumeration for this theme. This is a known coverage gap for an unmapped theme.

### Gate-2 misrecalls dropped (23) — why each is off-theme

| Bucket | Tickers | Reason |
|---|---|---|
| Physical-metal / commodity ETF trusts (SIC 6221) | PALL, PLTM, PPLT, DBP, SPPP, FGDL, GSG, CPER, BAR, DBC | Delaware statutory trusts holding bullion / commodity indices — not operating miners |
| Crypto / unrelated ETF | QSOL, QETH | Solana / Ethereum trusts |
| Non-PM minerals | IONR (lithium-boron), CMP (salt/plant-nutrition), CPAC (cement), LXU (nitrogen chem) | Mineral keyword hit, not gold/silver |
| Services / non-miner | NOA (mining construction services), EZPW (pawn lender), NVEC (semiconductor) | Touch the supply chain or "gold" loan collateral, do not mine |
| Sector bleed | HPAI (AI), JRSH (apparel), FLL (casino), TRC (real estate) | Pure keyword false-positives |

This is the canonical small-cap thematic problem: single-keyword FTS over-recall. The two-stage gate worked — 43% of the deep band (23/54) was off-theme and was removed before any deep-dive computation.

---

## 2. Code-paths exercised (the test target)

| Path | Fired on | Evidence |
|---|---|---|
| **Foreign-IFRS (20-F / 40-F)** | **24 of 31** survivors | `form_used`: 16 × 40-F (Canadian), 8 × 20-F; only 7 × 10-K. Almost every 40-F/20-F development-stage miner returned `reverse_dcf_null_reason = normalized_fcf_unavailable` → `mos_null_reason = intrinsic_band_unavailable` → MoS null. IFRS XBRL tags don't populate the FCF-cap model's expected concepts. |
| **Pre-revenue / development-stage** | ~24 of 31 | Revenue = $0M in the financial series for the explorers/developers; no positive normalized FCF → no intrinsic band → `mos_basis = fcf_cap` with `margin_of_safety_pct = null`. |
| **`fcf_cap_model_unsuitable` → NAV fallback** | IDR, GOLD | The only two that reached a NAV band. Both negative/tiny NAV MoS (IDR −0.8%, GOLD +7.9%). |
| **`financial_sic_fcf_unsuitable` → abstain** | VMET (SIC 6795 mineral-royalty trader) | Routed to NAV/abstain, never fcf_cap BUY. |
| **`cross_source_mismatch` (P7 second-source gate)** | **MUX, GOLD** | The data-integrity guard fired on the two names where yfinance had a comparable field that disagreed >2.5x. |
| **`wrong_entity_suspected`** | GOLD, SLSR | GOLD: shares SEC 1,675.4M vs yf 29.0M (57.8x); SLSR: sub-1000-share / entity tag issue. |
| **`extreme_mos_review_required`** | GOLD | extreme NAV MoS artifact from the mistagged Barrick-scale financials. |
| **`low_revenue_loss_ratio` (the named focus)** | **did NOT fire** on any survivor | These are zero-revenue explorers (ratio undefined) rather than the "small-revenue + large-loss" pattern P-B targets; the producers with revenue (IDR, MUX, CTGO, GOLD) had `|NI|/rev` below the >2.0 advisory threshold. Reported as a true negative for this theme. |
| **`peak_contamination_flag` / `fundamental_decline_flag`** | did not fire | All false — no V-shape value-trap or measured decline in the survivor set. |

**Signals firewall verified.** Every deepdive carries a top-level `signals` sibling of `derived` (P16 `price_divergence`, P17 ownership). `valuation.py` / `buy_eligible` read **no** `signals.*` field (confirmed: no signal key in the valuation block). The firewall held end-to-end — diagnostic side-channel only.

---

## 3. BUY rule applied to all 31 survivors

**BUY = `mos_basis ∈ {fcf_cap, nav}` AND numeric MoS ≥ 30 AND `buy_eligible == true` AND zero hard kill-flags.**

| `mos_basis` | n | Outcome |
|---|---:|---|
| `fcf_cap` | 27 | 26 have `margin_of_safety_pct = null` (no positive normalized FCF → no band). 1 (CTGO) had a tiny negative MoS (−0.5%). None ≥ 30. |
| `nav` | 2 | IDR (`nav_margin_of_safety_pct = −0.8%`), GOLD (`+7.9%`, and `buy_eligible = false`). Neither ≥ 30. |
| `abstain` | 2 | VMET (financial-SIC), SLSR (wrong-entity). No MoS basis. |

**`buy_eligible = false` on 4 names** (the guards bit, as designed):
- **MUX** — `cross_source_mismatch` (revenue SEC $64.6M vs yfinance $235.9M, 3.7x).
- **GOLD** — `extreme_mos_review_required`, `wrong_entity_suspected`, `cross_source_mismatch`.
- **VMET** — `financial_sic_forced_unsuitable` (SIC 6795).
- **SLSR** — `wrong_entity_suspected`.

**Hard kill-flags present (material-weakness) on 6 survivors:** MUX, FURY, NAMM, CMCL, MAKO, SLSR. Zero going-concern, zero death-spiral. Under the BUY rule's "zero kill-flags" clause these 6 are BUY-ineligible independent of MoS.

**Result: numeric MoS ≥ 30 was reached by exactly 0 of 31. Mechanical BUYs = 0.**

Because the gate is conjunctive, even the cleanest names fail on the first clause (no computable MoS ≥ 30), so no name ever depended on a guard to be blocked. The guards are a redundant second line here, not the binding constraint.

---

## 4. Ranked shortlist (all WATCH)

All 31 carry rating **观察 / WATCH**, confidence null (no MoS basis), and sink to the bottom tier by construction (no BUY/AVOID differentiation). Full table: `reports/smallcap/2026-06-21_cov-gold-silver-miners/RANKING.md`. The handful of names with real operating revenue (the only ones an analyst could even attempt to value) are the most-watchable subset:

| Ticker | Name | Form | Revenue | EV/EBITDA | P/E | FCF yield | Why still WATCH |
|---|---|---|---:|---:|---:|---:|---|
| IDR | Idaho Strategic Resources | 10-K | $42M | 31.0 | 33.5 | 2.2% | Only profitable domestic producer here, but NAV MoS −0.8% (priced ≥ asset value); rich EV/EBITDA |
| MUX | McEwen Inc. | 10-K | $65M | 40.3 | 30.4 | −4.8% | `cross_source_mismatch` + material-weakness; negative FCF |
| CTGO | Contango ORE | 10-K | n/a | — | — | 4.9% | Positive normalized FCF but no intrinsic band computed; development-stage |
| GOLD | (mistag — see §5) | 10-K | $3,274M NI | 0.65 | 0.37 | 46% | Data artifact; not investable as scanned |

Everything else is a zero-revenue explorer/developer or royalty shell where the model correctly abstains.

---

## 5. Adversarial verification

No mechanical BUYs, so no BUY required adversarial defence. The two most interesting *data-quality* cases were adversarially examined and confirmed as **artifacts the guards correctly neutralised**:

- **GOLD (ticker = Barrick Gold).** The deepdive pulled an internally inconsistent record: business blurb names "A-Mark" (a precious-metals dealer), SEC XBRL shows Barrick-scale financials (revenue $3.3B, OCF $4.1B, 1,675M shares), and yfinance shows 29M shares (A-Mark scale). The `cross_source_mismatch` (shares 57.8x, debt 4.0x), `wrong_entity_suspected`, and `extreme_mos_review_required` guards all fired → `buy_eligible = false`. Verdict: **data artifact (entity/CIK cross-contamination), correctly killed.** Had the guards not bitten, the spurious 46% FCF yield / 0.37 P/E would have looked like a screaming BUY. This is the P7 second-source gate doing exactly its job.
- **MUX (McEwen).** SEC revenue $64.6M vs yfinance $235.9M (3.7x). Likely a sub-entity / single-segment SEC tag vs consolidated yfinance. `cross_source_mismatch` → `buy_eligible = false`. Verdict: **input untrustworthy, correctly blocked.**

`n_buy_clean` (BUYs surviving adversarial verification) = **0**.

---

## 6. Data-quality issues

1. **mktcap unit mislabel.** Discovery `mktcap` values are in **raw dollars**, not millions, despite some downstream report strings printing them with an "M" suffix (e.g. RANKING note math). The band logic (deep < $2.0B) is correct on the raw-dollar values; the cosmetic label is misleading. (Recommend normalizing the unit in the report layer.)
2. **GOLD entity cross-contamination** (see §5) — blurb/SEC/yfinance point at different entities under ticker GOLD. Caught by P7 + wrong-entity guards.
3. **Foreign-IFRS FCF blindness.** 24/31 names are 20-F/40-F IFRS filers for which the reverse-DCF returns `normalized_fcf_unavailable`. This is honest (no false MoS) but means the skill is effectively **non-discriminating on the Canadian junior-miner cohort** — it can only WATCH them. A NAV path that works off IFRS balance-sheet tags would add signal here.
4. **rank.py funnel recount** prints "114 → 85 → 32 → 31", which differs slightly from the authoritative run_theme funnel (123 → 83 → 54 → 31) due to rank.py recounting across mixed file globs. The authoritative numbers are in §1.
5. **Zero revenue series for explorers** — many survivors show $0M revenue / $0M NI in the financial extract (development-stage), which is genuine, not a pull failure.

---

## 7. recall@gold

**n/a.** `gold-silver-miners` has no hand-built gold true-member list (only water-utilities, railcar-leasing, regional-gaming, deathcare do). `track_forward.py --recall-gold --theme gold-silver-miners` returns *"no gold list for theme — not measurable."* Recall floor for this theme is therefore unmeasured and, with no SIC reverse-recall mapping, rests entirely on the FTS arm.

---

## 8. Market-intel / T2 analyst context (NEVER drives buy_eligible)

From TrendsMCP (Google Search interest, normalized 0–100):

- **"gold mining stocks":** +80% YoY but **−76% over the last 3 months** — interest peaked ~Mar 2026 (value 38) and has cooled to 9.
- **"silver mining stocks":** +50% YoY but **−81% over the last 3 months** — same crest-and-fade shape, peak ~Mar 2026.

T2 read: the retail-attention wave in precious-metal miners **crested in Q1 2026 and is now fading**. This is textbook "hot theme = casino" — by the time a theme has branded ETFs (and this universe is *full* of them: PALL/PLTM/BAR/SIVR/GLTR/AAAU/OUNZ all surfaced), the alpha has been captured. The fading attention does **not** create a value edge by itself; it is context only and has zero bearing on `buy_eligible`. The skill's value here was the elimination work (43% of the deep band was off-theme; the two value-trap data artifacts were caught), not the discovery of a hidden compounder.

---

## 9. Skeptical-PM usable verdict

**Usable: YES — as a correctly-functioning landmine scanner returning an honest 0-BUY.**

A skeptical PM should read this run as a *clean negative*, and a high-information one:
- The pipeline ran end-to-end on a hard cohort (mostly foreign-IFRS, mostly pre-revenue) with **0 crashes and 0 silent skips**.
- The two-stage gate removed 23 misrecalls (ETF trusts, crypto, sector bleed) — exactly the failure mode this skill exists to prevent.
- The P7 second-source gate caught a textbook data artifact (GOLD) that would otherwise have screened as a 0.37 P/E BUY.
- The 0-BUY is **honest, not a model failure**: there is genuinely no small-cap gold/silver miner in this universe with a computable ≥30% margin of safety and zero kill-flags, and the dominant reason (foreign-IFRS FCF blindness + pre-revenue) is transparently reported.

The one caveat a PM must internalise: for this *unmapped* theme the skill is **strong on precision, weak on the recall floor** (no SIC reverse-recall, recall@gold unmeasurable) and **structurally unable to value the Canadian junior-miner cohort** (IFRS FCF gap). So "0 BUY" means "0 BUY among the names the model can value," not "0 opportunity in gold/silver mining." For the IFRS juniors, this run is a coverage list, not a verdict. The mapped-theme recall floor (and an IFRS NAV path) are the two upgrades that would make this theme fully trustworthy.

---

### Artifacts
- Candidates: `reports/smallcap/2026-06-21_cov-gold-silver-miners/candidates_gold_silver_miners.json`
- Gate-2 survivors: `.../candidates_gate2_survivors.json` (31)
- Gate-2 results: `.../gate2_results.json`
- Deepdives: `.../deepdive_<T>_2026-06-21.json` (31)
- Valuations: `.../valuation_<T>_2026-06-21.json` (31)
- Reports: `.../report_<T>.md` (31)
- Verdicts: `.../deepdive_verdicts.json` (31, all 观察)
- Ranking: `.../RANKING.md`
