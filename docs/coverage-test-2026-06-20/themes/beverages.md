# Coverage Test, Beverages (Staples)

- **Slug:** `beverages`
- **Sector:** Consumer Staples
- **Keywords:** `beverages, non-alcoholic, craft beverage`
- **Code-path focus:** mature / brand
- **Skill version:** v0.3.0 (commit `f12fef5`, run manifest reports `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-beverages/`
  (`new_run.py` stamped the dir `2026-06-21` from the system clock; the task label was `cov-beverages`)
- **Outcome:** **0 BUY.** Correct, expected scanner result. Of six genuine beverage names that survived
  every mechanical gate, none cleared the BUY contract, every one is fully valued (negative or near-zero
  MoS) or carries a v0.3.0 guard flag. No mechanical BUY fired, so there was nothing to adversarially
  rescue or reject.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| FTS raw recall | 321 | EDGAR full-text on the 3 keyword phrases (forms 10-K/10-Q/20-F/40-F) |
|, deep band (<$2.0B) | 109 | market-cap resolved to small-cap |
|, watch band ($2.0 to 5.0B) | 14 | theme-fit only, no deep-dive (out of small-cap scope) |
|, large (>$5.0B) | 63 | excluded |
|, unknown mktcap | 135 | mktcap-fallback could not resolve (illiquid / no price / foreign) |
| cheap_pass scanned | 82 | mechanical health screen rows produced |
| cheap_pass survivors | 54 | going-concern / death-spiral / ICFR / concentration screen |
| SIC gate (Gate 1) | 54 | keep=32, review=22, **no drops** (review forwarded to LLM gate) |
| **Deep band into theme-fit** | **44** | of the 54 survivors, those that are small-cap (band=deep) |
| **LLM theme-fit KEEP** | **6** | true beverage members (pure-play + partial) |
| LLM theme-fit MISRECALL | 38 | off-theme keyword sweeps (restaurants, casinos, BDCs, REITs, etc.) |
| Deep-dived (data + valuation) | 6 | **every** deep-band survivor, no sampling, 0 errors, 0 `*_ERROR.json` |
| **Mechanical BUY** | **0** | none cleared MoS≥30 + buy_eligible + 0 kill-flags |

**Code-paths fired:** FTS recall + **mktcap-fallback** (135 of 321 hits had no resolvable cap and were
banded `unknown`); cheap_pass mechanical kill-flags; SIC Gate 1 (keep/review, no hard drop); LLM theme-fit
Gate 2; deepdive_data + valuation on all 6 survivors; finalize_run completeness assert + verdict emission +
RANKING rebuild + trust banner; rank.py.

**Code-path that did NOT fire:** the **SIC reverse-recall floor**. `beverages` is **not** in
`filter_by_sic.THEME_SIC` (`theme_sics('beverages') → []`), so there is no dedicated-SIC recall floor for
beverage SICs 2080/2082/2084/2086. Discovery here is FTS + mktcap-fallback only. This is by design for an
unseeded theme, and it has a real recall cost (see §6 data-quality).

`recall@gold`: **n/a**, beverages is not one of the four seeded gold themes
(water-utilities / railcar-leasing / regional-gaming / deathcare).
`track_forward.py --recall-gold reports/.../candidates_beverages.json --theme beverages` →
`"no gold list for theme 'beverages' — not measurable"`, and `theme_gold('beverages') → []`.

---

## 2. Theme-fit gate (LLM membership judgment)

I judged true membership from the Item-1 business blurbs. "Beverages / non-alcoholic / craft beverage"
is a notoriously leaky FTS term: every restaurant, casino, c-store and grocer describes "food and
beverage" operations, so the raw recall is dominated by hospitality and retail, not beverage producers.

**KEEP, deep band, true beverage members (6):**

- **SUJA** (Suja Life, SIC 2080), cold-pressed organic juice / functional shots. Non-alcoholic craft
  beverage **pure-play**. (Blurb empty in fixture, classified on SIC 2080 + well-known business.)
- **LWAY** (Lifeway Foods, SIC 2020), largest US producer of kefir (cultured probiotic drink).
  Non-alcoholic beverage **pure-play**.
- **SAM** (Boston Beer, SIC 2082), Sam Adams / Twisted Tea / Truly / Dogfish Head. Craft-beverage
  pure-play; **alcoholic**, so it matches "craft beverage" but not "non-alcoholic", kept as a true member
  of the craft-beverage keyword leg, flagged as alcoholic.
- **SMPL** (Simply Good Foods, SIC 2000), **partial.** Self-describes as "consumer packaged food and
  **beverage** company" (Atkins / Quest), but the revenue is dominated by snacks/bars, not drinks.
- **HAIN** (Hain Celestial, SIC 2000), **partial.** Health/wellness CPG; beverage exposure (teas,
  plant-based drinks) is one slice of a diversified better-for-you portfolio.
- **TLRY** (Tilray Brands, SIC 2833), **partial.** Cannabis company "at the nexus of cannabis, **beverage**,
  wellness," with a material US craft-beer/beverage segment (SweetWater, Montauk, Breckenridge, Shock Top).

**MISRECALL, dropped (38):** the canonical over-recall pattern.
Restaurants (BDL, BJRI, BLMN, BRCB, FWRG, KRUS, LOCO, NATH, PLAY, PTLO, RICK, RRGB, WEN);
casinos / gaming / entertainment (ACEL, CNTY, FLL, SEG); c-store / grocery / distribution (ARKO, IMKTA);
BDCs / specialty finance (BCIC, GSBD, MFIC, OCSL); REITs (BHR, STRS); cannabis non-beverage (OGI, TCNNF);
packaging (KRT, foodservice, OI, glass containers); apparel (OXM); shipping / lodging svcs (DSX, CVEO);
lithium (LAC); flavors-supplier-by-text (none in deep band); shells / micro-foreign (EPSM, RUBI, TKLF, WNW);
e-commerce SaaS (VTEX).

Gate 1 (SIC) kept all of these as `keep`/`review`, note that several genuine off-theme names
(restaurants at SIC 5812, casinos at 7011/7900, BDCs with nan SIC) sailed through the SIC gate untouched;
the LLM gate is what removed them. Recorded via `candidates_gate2_survivors.json` (the 6 KEEP) so
finalize_run treats the 38 as resolved-by-gating, not missing deep-dives → **0 missing reports**.

**Watch band ($2.0 to 5.0B, theme-fit only, no deep-dive):** two true beverage members were caught here but
are above small-cap scope, **FIZZ** (National Beverage, SIC 2086, LaCroix, the cleanest non-alcoholic
pure-play in the whole recall) at ~$3.4B, and **CCU** (United Breweries, SIC 2082) at ~$2.1B. The rest of
the watch band is off-theme (CSAN, CVCO, FUN, SFNC, SHAK, SKYW, SXT, UNFI). **SXT** (Sensient, SIC 2860)
is a beverage-industry **supplier** (flavors/colors), not a beverage producer, correctly left off-theme.

---

## 3. BUY rule application, every deep-band survivor

BUY requires: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric MoS ≥ 30% **AND** `buy_eligible == true`
**AND** zero kill-flags. `buy_eligible` already ANDs the v0.3.0 guards. (For `nav` basis the effective MoS
is `nav_margin_of_safety_pct`; for `fcf_cap` it is `margin_of_safety_pct`.)

| Tkr | KF | mos_basis | effective MoS% | buy_eligible | Why it fails the BUY contract |
|---|---:|---|---:|---|---|
| SUJA | 0 | fcf_cap | **null** | ✅ true | fails MoS gate, intrinsic band unavailable (no shares/cash/EBITDA in fixture; recent IPO) |
| LWAY | 0 | nav | **−0.8** | ✅ true | fails MoS gate, trades ~at NAV, no discount |
| SAM  | 0 | nav | **−0.8** | ✅ true | fails MoS gate, trades ~at NAV (fcf_cap blocked by C1 data-quality guard → fell back to NAV) |
| SMPL | 0 | fcf_cap | **−0.2** | ✅ true | fails MoS gate, fully valued on normalized FCF |
| HAIN | 1 | nav | **−1.0** | ❌ false | `fundamental_decline_flag` + `peak_contamination_flag` (rev slope −1, latest NI −$531M) + material-weakness kill-flag |
| TLRY | 0\* | nav | **+0.1** | ❌ false | `cross_source_mismatch` (SEC total_debt 64.1M vs yf 343.9M, 5.4x); also `low_revenue_loss_ratio` (|NI|/rev=2.7x) |

\* TLRY shows `killflag_count=1` in the cheap_pass candidates row but the valuation/verdict kill-flag set
resolves to the guard list; either way `buy_eligible=false` blocks it, so the BUY decision is unchanged.

**mos_basis distribution (the 6 deep-dived):** `fcf_cap` = 2 (SUJA, SMPL), `nav` = 4 (LWAY, SAM, HAIN, TLRY),
`abstain` = 0. Note the FCF→NAV fallback is heavily exercised: SAM, LWAY, HAIN, TLRY all had `fcf_cap`
blocked (C1 data-quality guard / model-unsuitable / debt>0.62 assets) and fell back to a NAV basis, exactly
the mature/brand code-path this theme was meant to stress.

**Mechanical BUYs: 0.** Two filters did the work: the four `buy_eligible==true` names all failed the
MoS≥30 gate (none trades at a discount, beverage brands are priced as quality compounders, not value),
and the two with a potential surface story (HAIN cheap on a wipeout, TLRY at +0.1% NAV) were both vetoed
by guards. There is no mechanical BUY to verify.

---

## 4. Adversarial verification

No mechanical BUY fired, so there is no artifact-vs-opportunity call to make. For completeness, the two
names a naive screen might have flagged, and why the guards were right to kill them:

- **HAIN**, surface "deep value": a one-time household health-CPG name down ~90% in cap (mktcap ~$55M
  vs revenue ~$1.56B). The `fundamental_decline_flag` + `peak_contamination_flag` + material-weakness
  kill-flag correctly refuse to treat a −$531M net-income, declining-revenue, control-weakness business as
  a NAV bargain. **Guard verdict: correct kill, this is a melting-ice-cube, not a cigar butt.**
- **TLRY**, the only positive MoS in the set (+0.1% on NAV), which is itself a tell: a marginally-positive
  NAV "discount" on a cannabis roll-up burning −$95M OCF on $821M revenue with a 5.4x cross-source debt
  disagreement is exactly the data-artifact `cross_source_mismatch` exists to catch.
  **Guard verdict: correct kill, the MoS is noise, not signal.**

**n_buy_clean = 0.**

---

## 5. Market-intel / T2 analyst context (does NOT drive buy_eligible)

TrendsMCP quota was exhausted for the day (daily + monthly pool both at 0), so no live demand-trend pull
was available for this run; this is a T2 enrichment gap only, it has zero bearing on the mechanical funnel
or the 0-BUY result. Qualitative category context (knowledge-based, label it T2):
the non-alcoholic / "better-for-you" beverage category (functional sodas, prebiotic/probiotic drinks,
sparkling water, energy) has been a structurally hot sub-theme, which is precisely why the survivors are
priced for growth, not value. SUJA is a recent IPO (incomplete fundamentals, no intrinsic band). FIZZ and
CCU, the cleanest pure-plays, both sit *above* small-cap scope, reinforcing the worldview point that the
genuine industrial beneficiaries of a hot consumer theme have already been bid out of the neglected
small-cap pond. No name in this theme is a neglected, mispriced compounder on the mechanical evidence.

---

## 6. Data-quality issues

- **No SIC recall floor (recall risk).** beverages is absent from `THEME_SIC`, so discovery never enumerated
  registrants in beverage SICs (2080 to 2086) as a floor. Recall depends entirely on the keyword hitting an
  Item-1 phrase. This is the single biggest coverage risk for the theme, a small non-alcoholic producer
  that does not use the literal words "beverage / non-alcoholic / craft beverage" in its 10-K narrative would
  never enter the funnel. Seeding `beverages → [2080, 2082, 2084, 2086]` would convert SIC into a recall floor.
- **135/321 raw hits had unresolved market cap** (`band=unknown`) and were dropped pre-cheap-pass. Some may
  be genuine illiquid micro-cap beverage names; mktcap-fallback could not place them.
- **SUJA**, fixture has no shares / cash / D&A / capex; intrinsic band is null, MoS unmeasurable. Recent IPO
  pattern, not a data error per se, but it means the name cannot be valued mechanically yet.
- **Pervasive `debt_stale` / FCF→NAV fallback**, SAM, LWAY, HAIN, TLRY all carry `debt_stale:>18_months`
  and had `fcf_cap` blocked, forcing a NAV basis. Mature-brand balance sheets with intangible-heavy NAV make
  the NAV MoS conservative (tangible-equity based), which is appropriate but means these names structurally
  show deep-negative NAV MoS regardless of FCF quality.
- **TLRY**, `cross_source_mismatch` (SEC vs yfinance total_debt 5.4x apart) and `low_revenue_loss_ratio`.
- **RANKING banner count quirk**, the auto-generated banner reads "44 → 7 家逐一 deep dive → cheap pass 幸存 6";
  the actual deep-dived count is 6 (all 6 KEEP survivors). Cosmetic only; the table lists exactly 6 rows.

---

## 7. Skeptical-PM usable verdict

**Usable: yes.** This is a clean, correct landmine-scan of a hot consumer-staples sub-theme. The pipeline
ran end-to-end with zero deep-dive errors, correctly stripped 38 hospitality/finance/REIT misrecalls that a
keyword screen would have buried the analyst in, found the 6 genuine beverage members, and returned an honest
**0 BUY**, none trades at a value discount, and the two superficially-cheap names were correctly vetoed by
v0.3.0 guards (HAIN decline/peak-contamination/material-weakness; TLRY cross-source-mismatch). The result is
consistent with the skill's worldview: a hot theme is the casino, the true pure-plays (FIZZ, CCU) have already
escaped the small-cap pond, and the small-cap residue is fairly-to-fully priced. The one substantive caveat a
PM should note is the **missing SIC recall floor**, for a definitive universe sweep of beverage producers,
seed `THEME_SIC['beverages']` before trusting the recall as complete.
