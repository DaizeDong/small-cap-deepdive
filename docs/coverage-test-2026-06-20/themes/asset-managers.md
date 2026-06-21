# Coverage Test — Theme: asset-managers

- **Slug:** `asset-managers`  |  **Sector:** Financials  |  **Keywords:** `asset management, investment manager`
- **Skill version:** v0.3.0, commit `f12fef5` (manifest records `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-asset-managers/`
  (note: tooling system date stamped the run `2026-06-21`; coverage-test campaign date is 2026-06-20)
- **Code-path focus:** financial / AUM-fee valuation routing
- **Headline result: 0 BUY (clean). Honest "nothing found."**

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| Raw discovery (FTS + SIC reverse-recall floor, UNIONed) | universe CSV written | `universe_asset_managers_2026-06-21.csv` (94 KB) |
| Small-cap candidates entering cheap_pass | 36 | after band + liquidity tagging |
| cheap_pass survivors | 22 | kill-flag scan (going-concern / death-spiral / material-weakness) |
| SIC gate (Gate 1) survivors | 22 | keep=1, review=21 → routed to LLM Gate 2 |
| **Deep-band (band="deep") survivors** | **14** | every one deep-dived (no sampling) |
| Watch-band (2.0B–5.0B, surfaced only) | 8 | NTB, APAM, SPNT, FG, SLG, AAMI, LAZ, AB — not deep-dived by design |
| Deep-dives completed | 14 / 14 | **0 ERROR files** |
| Valuations completed | 14 / 14 | SWIN required `--mktcap` override (yfinance null) |
| **Mechanical BUYs** | **0** | |
| **Clean BUYs (post-adversarial)** | **0** | |

Structured funnel: `raw=36` (small-cap entrants to cheap_pass), `deepdived=14`, `survivors=14`.

### Deep-band roster (14), with Gate-2 theme-fit judgment

| Ticker | SIC | Mcap | Gate-2 fit | Rating |
|---|---|---:|---|---|
| VALU Value Line | 6282 | $320M | partial (research + advisory) | 观察 WATCH |
| CHCI Comstock Holding | 6500 | $154M | partial (CRE asset-mgmt fees) | 观察 WATCH |
| KW Kennedy-Wilson | 6500 | $1521M | partial (RE investment-mgmt platform) | 观察 WATCH |
| PAX Patria Investments | 6282 | $1814M | **pure_play** (LatAm alt-AM) | 观察 WATCH |
| VINP Vinci Compass | 6282 | $639M | **pure_play** (LatAm alt-AM) | 观察 WATCH |
| BUR Burford Capital | 6199 | $992M | pure_play (litigation-finance AM) | 观察 WATCH |
| GSBD Goldman Sachs BDC | (BDC) | $1048M | partial (the *fund*, not the manager) | 观察 WATCH |
| BOC Boston Omaha | 6510 | $400M | partial (diversified holdco + small AM) | 避开 AVOID |
| BOW Bowhead Specialty | 6331 | $896M | misrecall (specialty insurer) | 避开 AVOID |
| ASIC Ategrity Specialty | 6331 | $1016M | misrecall (specialty insurer) | 避开 AVOID |
| LTC LTC Properties | 6798 | $1861M | misrecall (healthcare REIT) | 避开 AVOID |
| GTY Getty Realty | 6500 | $1976M | misrecall (net-lease REIT) | 避开 AVOID |
| SWIN Solowin Holdings | 6211 | $51M | partial but wrong-entity/data-broken | 避开 AVOID |
| RRGB Red Robin | 5812 | $116M | misrecall (restaurant chain) | 避开 AVOID |

Gate-2 verdict: 3 true pure-plays (PAX, VINP, BUR), 5 partials, 6 misrecalls. The misrecalls are
the expected single-keyword FTS over-recall (a restaurant, three insurers/REITs swept in by an
"asset management" mention in their filings). The v0.3.0 guards neutralize every one of them.

---

## 2. Ranked shortlist (non-sunk = WATCH candidates)

1. BUR — litigation-finance AM; buy_eligible=false (financial_sic), nav-MoS −44%
2. CHCI — CRE asset-mgmt fees; buy_eligible=true, nav-MoS −64%
3. GSBD — externally-managed BDC (the vehicle); buy_eligible=false, nav-MoS +4.6%
4. KW — RE investment-mgmt platform; buy_eligible=true, nav-MoS −21%, fcf_cap blocked (debt/assets 0.64)
5. PAX — LatAm alt-AM pure-play; buy_eligible=true, **MoS un-computable** (foreign-filer XBRL gap)
6. VALU — research/advisory; buy_eligible=true, nav-MoS −74%
7. VINP — LatAm alt-AM pure-play; buy_eligible=true, **MoS un-computable** (foreign-filer XBRL gap)

Sunk (避开): ASIC, BOC, BOW, GTY, LTC, RRGB, SWIN.

---

## 3. BUY analysis — honest 0-BUY

**No candidate satisfies the BUY rule** (`mos_basis ∈ {fcf_cap, nav}` AND numeric MoS ≥ 30 AND
`buy_eligible == true` AND zero kill-flags). The closest names and exactly why each fails:

| Ticker | basis | numeric MoS | buy_eligible | Fails on |
|---|---|---:|---|---|
| CHCI | nav | −63.6% | true | MoS far below +30 (trades above tangible book) |
| KW | nav | −21.4% | true | MoS below +30 (levered RE balance sheet) |
| VALU | nav | −74.3% | true | MoS far below +30 (fee franchise priced at big premium to book) |
| PAX | fcf_cap | **null** | true | no numeric MoS — intrinsic band unavailable (data gap) |
| VINP | fcf_cap | **null** | true | no numeric MoS — intrinsic band unavailable (data gap) |
| GSBD | nav | +4.6% | **false** | financial_sic_forced_unsuitable; and +4.6% < 30 anyway |
| BUR | nav | −44.1% | **false** | financial_sic_forced_unsuitable |

The five buy_eligible names all fail on MoS (three deeply negative, two un-computable). This is the
correct economic answer: **fee-based asset managers trade at premiums to tangible book by design**
(their value is the capitalized fee stream, not net assets), so a NAV-basis MoS is structurally
negative for a healthy AM. The two true pure-plays that could in principle support an fcf_cap
(fee-stream) valuation — PAX and VINP — are foreign filers whose SEC XBRL lacks revenue / cash /
debt / shares, so the fcf_cap intrinsic band cannot be built and MoS is honestly null rather than
fabricated.

**Adversarial check on the 0-BUY itself:** Is the tool wrongly suppressing a real opportunity?
No. Two independent reasons confirm the 0-BUY is a true negative, not a guard artifact:
(a) the buy_eligible names that *do* have a usable NAV-MoS are all negative by 21–74% — there is no
hidden discount being masked; (b) the financial-SIC guard is conservative-correct here: capitalizing
an AUM-fee stream for a small AM needs fee-rate / net-flow / performance-fee assumptions the
deterministic layer cannot safely make, so routing to NAV (and then honestly reporting a negative
NAV-MoS) is the right behaviour. A skeptical PM would not want a mechanical BUY printed on a litigation-
finance book (BUR, fair-value-of-claims accounting) or a foreign filer with no parseable financials.

There are therefore **no mechanical BUYs to adversarially "promote."** n_buy_clean = 0.

---

## 4. Code-paths exercised (financial / AUM-fee focus — the test target)

`buy_ineligible_reasons` tally across the 14 valuations:

- `financial_sic_forced_unsuitable` ×6 — fired on SIC 6199 (BUR), 6211-routing, 6282 (where NAV
  used), 6331 (ASIC/BOW), 6798 (LTC), and the no-SIC BDC structural detector (GSBD). **This is the
  core AUM-fee code path** — it correctly refuses to capitalize FCF for financial/fee entities and
  routes them to NAV.
- `insurance_concepts_present` ×4 — BOC, BOW, BUR, ASIC (PremiumsEarnedNet etc.)
- `cross_source_mismatch` ×2 — RRGB (debt SEC 171M vs yf 516M, 3.0×), SWIN (shares 16.1M vs 187.2M, 11.6×)
- `debt_truncation_suspected` ×1 — BOW (reported debt 146M vs implied 1562M, ratio 0.09)
- `extreme_mos_review_required` ×1 — GTY (fcf MoS −104% exceeds 100%)
- `fcf_sustainability_uncertain` ×1 — GTY (OCF proxy on capital-intensive, assets/rev 9.8)
- `wrong_entity_suspected` ×1 — SWIN (ticker absent from SEC company_tickers)

Other notable code paths fired (data_quality, non-killing): `fcf_cap_model_unsuitable:debt_to_assets`
(KW, 0.64 > 0.62 cap), `fcf_cap_blocked_by_c1_data_quality_guard` (CHCI, SWIN, VALU),
`intrinsic_band_null:normalized_fcf_*` (BOC, BUR, PAX, SWIN, VINP),
`nav_goodwill_or_intangibles_unavailable` (book-equity proxy on 8 names),
`low_revenue_loss_ratio` (SWIN — correctly classified as right-entity pre-revenue, not extreme),
`financial_structure_suspected_no_sic:revenue_absent_ocf_present` (GSBD — the BDC structural detector).

**MoS-basis distribution: nav=10, fcf_cap=4, abstain=0.** The financial code-path dominance (10 of
14 forced to NAV) is exactly what this theme should exercise, and it did.

---

## 5. Data-quality issues observed

1. **Foreign-filer XBRL gaps (PAX, VINP):** revenue / cash / debt / D&A / shares all unavailable in
   SEC XBRL → `intrinsic_band_null`, MoS null, `ev_is_market_cap_only`. These are real LatAm
   asset-manager pure-plays that the tool *cannot* value from SEC data alone. Handled gracefully
   (null, not crash) — correct, but it means the two best theme-fit names are un-valuable here.
2. **SWIN data integrity:** wrong_entity_suspected (ticker not in SEC company_tickers) + 11.6×
   share-count disagreement + 13× |NI|/rev. A $51M HK micro-cap; the guards correctly quarantined it.
3. **RRGB cross-source mismatch:** 3.0× total-debt disagreement (SEC vs yfinance) — flagged, not silently used.
4. **yfinance market-cap null (SWIN):** required manual `--mktcap 50840000` override (from SEC
   shares×price fallback) to complete the valuation — the P5 fallback chain worked as designed.
5. **Stale debt (CHCI, KW, VALU):** `debt_stale:>18_months_behind_latest_assets` — noted as data_quality.
6. **No business blurbs in candidate/universe records:** the `business_blurb` field was empty, so the
   LLM Gate-2 theme-fit judgment ran on company name + SIC + domain knowledge rather than 10-K
   business text. Sufficient here (names are unambiguous) but a coverage observation.

---

## 6. recall@gold

**n/a.** asset-managers is not one of the four gold-list themes (water-utilities, railcar-leasing,
regional-gaming, deathcare). `theme_gold("asset-managers")` returns `[]`, so `track_forward.py
--recall-gold` is a no-op for this theme and was not run. No recall floor to measure.

---

## 7. Market-intel / T2 analyst context (firewalled — does NOT drive buy_eligible)

- TrendsMCP enrichment was **unavailable** this run (daily + monthly request quota exhausted),
  so no quantitative search/news-sentiment trend was pulled. Recorded as a data-availability note.
- Qualitative T2 frame (domain knowledge, advisory only): listed asset managers are a fee-on-AUM
  business whose equity value is the capitalized management-fee stream; small-cap AMs (VALU, the
  LatAm alts PAX/VINP, litigation-finance BUR) carry idiosyncratic risk — net-flow direction,
  performance-fee lumpiness, and (for BUR) fair-value-of-claims mark volatility. None of this enters
  the mechanical pipeline; it only contextualizes why a NAV-basis screen structurally yields no BUY
  for healthy fee businesses.

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** The scanner did its job as a landmine detector:
- It enumerated the small-cap AM universe, deep-dived all 14 deep-band names with zero crashes.
- It correctly sank 6 misrecalls (a restaurant, three insurers/REITs swept by keyword) and 1
  broken-data micro-cap, via mechanical guards — no human attention wasted.
- It surfaced 3 genuine pure-plays (PAX, VINP, BUR) and 4 partials as WATCH, with honest reasons
  for non-BUY (negative NAV-MoS for premium-to-book fee franchises; null MoS for un-valuable
  foreign filers).
- The 0-BUY is a **correct true negative**: there is no clean small-cap asset manager trading at a
  ≥30% margin of safety on a usable valuation basis with zero kill-flags. A PM gets a vetted WATCH
  list (PAX/VINP to revisit once financials are parseable; KW/CHCI/VALU as priced-fairly-to-rich
  fee businesses) and a clean confirmation that there is nothing to buy mechanically today.

The financial/AUM-fee code path — the focus of this coverage test — fired on 10 of 14 names and
behaved correctly throughout (route fee businesses to NAV, refuse to fabricate fcf_cap on missing
data, quarantine wrong-entity/cross-source-mismatch names).
