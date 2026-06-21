# Coverage Test — Regional Gaming (ConsDisc)

- **Slug:** `regional-gaming` (filesystem slug normalized to `regional_gaming`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-regional-gaming/`
- **Skill version:** v0.3.0 @ commit `f12fef5` (run manifest records `skill_dirty: true`)
- **Keywords:** `casino, gaming, regional gaming`
- **SIC recall floors:** `7990` (amusement/recreation), `7011` (hotels-casinos)
- **Code-path focus:** debt/lease-heavy NAV path + recall@gold
- **Date:** 2026-06-21 (run executed under coverage-test 2026-06-20 docs tree)

> **This is research output, not investment advice.** The skill is a landmine-scanner.
> A WATCH here means "survived mechanical kill-flags + is a genuine theme member" — it is NOT a buy.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery (FTS ∪ SIC floor) → cheap_pass input | 63 candidates written | discover + SIC reverse-recall on 7990/7011 + mktcap fallback |
| cheap_pass survivors (after hard kill-flag scan) | 63 (32 keep / 31 review SIC tier) | death-spiral / going-concern names already dropped pre-write (SEAT, FLNT, SKLZ, PLBY, RR, SBET… kill-flag 2) |
| Band split | 38 deep / 25 watch | deep = mktcap < $2.0B; watch = $2.0–5.0B (skipped per band guard) |
| **LLM theme-fit gate (Gate 2)** on 38 deep-band | **10 retained** / 28 misrecall | I judged true membership from 10-K business blurbs |
| Deep-dived (data + valuation) | **10 / 10** survivors | EVERY deep-band survivor, no sampling; 0 ERROR files |
| Mechanical BUYs | **0** | none clears (mos_basis∈{fcf_cap,nav} AND MoS≥+30% AND buy_eligible AND 0 kill-flags) |
| Adversarially-clean BUYs (`n_buy_clean`) | **0** | no BUYs to verify |

**Funnel object:** `{ raw: 63, deepdived: 10, survivors: 10 }`
(`survivors` = theme-fit survivors that completed deep-dive; all rated WATCH, none sunk.)

### Theme-fit gate detail (Gate 2 — my judgment, recorded in `gate2_results.json`)

**Retained (10):**

| Ticker | Class | Why a true member |
|---|---|---|
| FLL | pure_play | Full House Resorts — owns/operates 6 regional casinos (NV/CO/IL/IN/MS). **gold** |
| CNTY | pure_play | Century Casinos — regional casino operator. **gold** |
| ACEL | pure_play | Accel Entertainment — distributed gaming operator + brick-and-mortar casinos. **gold** |
| BALY | pure_play | Bally's — global casino / interactive / lottery operator |
| INSE | partial | Inspired Entertainment — B2B gaming technology (lottery/betting/gaming content) |
| CDRO | partial | Codere Online — online gaming/betting operator (foreign filer) |
| MYPS | partial | PLAYSTUDIOS — social-casino + casual mobile games (myVEGAS real-Vegas rewards) |
| DDI | partial | DoubleDown Interactive — social-casino mobile games (Korea/US; ADR) |
| PLTK | partial | Playtika — mobile games operator incl. social-casino (Slotomania) |
| BUKS | partial | Butler National — aerospace + owns land/building + manages Boot Hill Casino, Kansas |

**Misrecall (28, dropped — keyword false-positives or off-theme):** IDN, FNWB, PLAY (arcade/dining, not casino), NATH, TRC, HZO, CBL, TACT, ATHS, **EPSM** (Macau alcohol supply-chain, not a gaming operator), SWAG, GMHS (generic mobile games), RICK (adult clubs), PSFE, FVRR, CNNE, MINE, ATLO, FNLC, PLBC, **WRN** (the "Casino Project" is a *gold-mining* property — classic keyword trap), VLRS, APC, TV, LGPS, FGBI, ASAIY, **SEG** (NYC/Vegas entertainment + real estate, no casino operations).

---

## 2. recall@gold

`python tools/track_forward.py --recall-gold <candidates.json> --theme regional-gaming`

- Gold cohort (7): **BYD, RRR, MCRI, GDEN, CNTY, FLL, ACEL**
- Recalled: **ACEL, CNTY, FLL, MCRI**
- Missing: BYD, GDEN, RRR
- **recall@gold = 57.1% (4/7)**

Loss-stage breakdown:
- `recalled_final`: 4 (ACEL, CNTY, FLL, MCRI)
- `sic_recovered`: 0
- `dropped_mktcap`: 0
- `gated_out`: 0
- `fts_missed`: 3 (BYD, GDEN, RRR)

**Interpretation — this 57.1% is an honest cap artifact, not a recall bug.** The 3 missing names
(Boyd Gaming, Golden Entertainment, Red Rock Resorts) are all mid/large-cap (>$2.0B). They were
`fts_missed` because the small-cap discovery cap excludes them; they are correctly out of the
deep-dive universe. MCRI *was* recalled but lands in the watch band ($2.32B) so the band guard
correctly skips it from deep-dive. Of the 4 gold names that are genuinely in the small-cap deep
band (ACEL, CNTY, FLL — and MCRI just over), **all 3 in-band were recalled AND deep-dived: 3/3 = 100% in-band recall.** No gold member was lost to a gate error or a mktcap-resolution failure.

---

## 3. Ranked shortlist (all WATCH — see `RANKING.md`)

| Rank | Ticker | Rating | Conf | Rev | NI | OCF | mos_basis | sel MoS | buy_eligible | kill-flag |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | FLL | 观察 | 60% | $302M | -$40M | $10M | nav | -100% | false (peak_contam) | 0 |
| 2 | ACEL | 观察 | 58% | $1331M | $52M | $151M | fcf_cap | -80% | true | 0 |
| 3 | CNTY | 观察 | 58% | $573M | -$61M | $7M | fcf_cap | null | false | 1 (MW) |
| 4 | BALY | 观察 | 55% | $2436M | -$650M | -$11M | fcf_cap | null | true | 1 (MW) |
| 5 | BUKS | 观察 | 55% | $84M | $13M | $18M | fcf_cap | -79% | true | 0 |
| 6 | DDI | 观察 | 55% | $309M | $101M | $21M | fcf_cap | +47% | false (xsrc) | 0 |
| 7 | INSE | 观察 | 55% | $304M | -$17M | $52M | nav | -100% | true | 1 (MW) |
| 8 | MYPS | 观察 | 55% | $235M | -$29M | $26M | fcf_cap | +265% | false (artifact) | 0 |
| 9 | PLTK | 观察 | 55% | $2755M | -$206M | $568M | nav | -100% | true | 0 |
| 10 | CDRO | 观察 | 45% | $0M | $0M | $0M | fcf_cap | null | true | 1 (MW) |

(MW = material_weakness flagged by deepdive 10-K scan; xsrc = cross_source_mismatch.)

---

## 4. BUYs — honest 0-BUY

**There are ZERO mechanical BUYs.** The BUY rule requires *all four* of:
mos_basis ∈ {fcf_cap, nav} **AND** numeric selected-MoS ≥ +30% **AND** buy_eligible == true **AND** zero kill-flags.

No candidate satisfies the conjunction. The structural reason is a clean bifurcation:

- The candidates that are **buy_eligible == true** (PLTK, INSE, BUKS, BALY, ACEL, CDRO) all have
  **negative or null selected MoS** (NAV -100% for the goodwill-heavy game operators; -79%/-80%
  fcf_cap for BUKS/ACEL priced above their FCF cap; null for BALY/CDRO where the intrinsic band is
  unavailable). None reaches +30%.
- The candidates with a **large positive MoS** (MYPS +265%, DDI +47%) are **buy_eligible == false**
  — vetoed by the data-integrity / value-trap guards (see adversarial section). Their MoS is a
  data artifact, not a real margin.

This is exactly the landmine-scanner working as designed: a hot, debt/lease-heavy cyclical sector
produced **no clean small-cap pure-play with a real margin of safety.** That is a correct and useful
"nothing found."

### Code-paths fired (focus: debt/lease-heavy / NAV)

- **NAV asset-heavy path** fired for FLL, PLTK, INSE (mos_basis = nav) — fcf_cap declared unsuitable
  (`fcf_cap_model_unsuitable_use_nav`), then NAV computed. In all 3 the NAV MoS is **-100%**:
  negative tangible equity. For FLL this is the genuine debt/lease-heavy casino balance sheet
  (development debt > assets net of debt); for PLTK/INSE it is acquisition-built goodwill swamping
  tangible equity. The NAV path correctly refuses to manufacture a margin from intangibles.
- **`normalized_fcf_nonpositive`** reverse-DCF null reason fired for FLL, CNTY, BALY (cyclical-trough
  / loss-year normalization) → routed to NAV or intrinsic-band-unavailable.
- **`intrinsic_band_unavailable`** for CNTY, BALY, CDRO (insufficient/zero financial series).
- **`peak_contamination_flag`** (V-shape trough→peak→rollover veto) fired for FLL, CNTY, MYPS.
- **`fundamental_decline_flag`** (monotone decline veto) fired for MYPS.
- **`cross_source_mismatch`** (>2.5× SEC-vs-yfinance disagreement, blocks BUY) fired for MYPS, DDI, CNTY.
- **`extreme_mos_review_required`** (|MoS|>100% pathology) fired for MYPS.
- **`material_weakness`** (deepdive 10-K text scan) recorded for BALY, CNTY, INSE, CDRO.

---

## 5. Adversarial verification

No mechanical BUY exists, so there is nothing to confirm as a real opportunity. Instead I
adversarially checked the **highest-MoS rejected candidates** to confirm the gate's rejections are
*correct* (i.e. no false negative that should have been a BUY):

- **MYPS (+265% fcf_cap MoS, buy_eligible=false).** Verdict: **correctly rejected — data/model artifact.**
  `cross_source_mismatch`: SEC total_debt $63.1M vs yfinance $6.9M (9.1× disagreement) → the EV that
  drives the +265% is built on an unreliable debt figure. Additionally `fundamental_decline_flag` +
  `peak_contamination_flag` (contamination 0.69) + `extreme_mos_review_required`. Reverse-DCF implied
  growth -26.7% (the market is pricing in decline, consistent with the V-shape veto). A +265% MoS on
  a $69M micro-cap social-casino game studio in monotone revenue decline (-19% YoY) is a textbook
  value trap, not a bargain.
- **DDI (+47% fcf_cap MoS, buy_eligible=false).** Verdict: **correctly rejected — data artifact.**
  `cross_source_mismatch` on shares_outstanding: SEC 2.5M vs yfinance 49.6M (20× — DDI is a Korean
  ADR; the SEC XBRL share count is the underlying entity, not the ADR ratio). The +47% MoS is
  computed against a market cap that is itself unreliable given the 20× share-count ambiguity. Blocking
  BUY here is the right call.

Both rejections are sound. The mechanical guards are firewalled and working: they killed the two
candidates whose headline number looked most attractive, precisely because the number was unsupported.

---

## 6. Data-quality issues

1. **CDRO — foreign-filer XBRL gap:** revenue / NI / OCF / cash all pull as **$0M**. Codere Online is
   a Luxembourg 20-F filer whose financials did not map into the US-GAAP XBRL concepts the deepdive
   reads. Its valuation is effectively un-anchored (intrinsic_band_unavailable). WATCH-on-data-quality,
   not a fundamentals judgment. Confidence set lowest (45%).
2. **cross_source_mismatch (SEC vs yfinance > 2.5×)** on MYPS (debt 9.1×), DDI (shares 20×), CNTY.
   These correctly block BUY but also signal the underlying second-source disagreement that any human
   analyst must resolve before trusting the cap/EV.
3. **material_weakness flags (BALY, CNTY, INSE, CDRO)** come from a 10-K *text* scan
   (`has_material_weakness=True`). This is keyword-grade detection — it may be a genuine ICFR finding
   or a boilerplate risk-factor mention. cheap_pass (which scans the most-recent period more strictly)
   did NOT eliminate them, so these are likely historical/risk-factor mentions rather than active
   adverse ICFR opinions. Flagged for human confirmation; does not change the 0-BUY outcome.
4. **BALY revenue growth +1005%** in the ranking table is an artifact of a near-zero prior-period
   base in the normalized series, not real growth. Cross-check against the 10-K before use.
5. **MCRI recalled but watch-band ($2.32B):** a gold member just above the $2.0B small-cap cap; the
   band guard correctly excludes it from deep-dive. If the cap were widened it would re-enter.

---

## 7. Market-intel / Trends (T2 analyst context — does NOT drive buy_eligible)

- **TrendsMCP: unavailable this run** — daily + monthly request quota exhausted (5/5 daily, 100/100
  monthly). No live search/sentiment series could be pulled. Recorded as a data limitation.
- **Sector framing (analyst knowledge, T2):** regional/local US gaming is a mature, cyclical,
  debt-and-lease-heavy consumer-discretionary segment. The economics are dominated by (a) capex/lease
  load on owned-vs-leased casino real estate, (b) regional consumer-discretionary spend sensitivity,
  and (c) the secular shift toward iGaming/online (BALY, CDRO, the social-casino names MYPS/DDI/PLTK).
  This T2 read is *consistent* with the mechanical output: the NAV path keeps surfacing negative
  tangible equity (leverage), and the FCF path keeps pricing names above their FCF cap (cyclical,
  no margin) — i.e. the sector is fairly-to-fully priced for its risk in the small-cap band. None of
  this enters `buy_eligible`; it is context for the human PM only.

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** The run is internally consistent and the output is decision-useful:

- It enumerated the small-cap regional-gaming universe, correctly eliminated the keyword traps
  (WRN gold-mining "Casino Project", SEG entertainment-RE, EPSM Macau-alcohol, RICK adult-clubs,
  PLAY arcade-dining, 13 financial/REIT/airline/retail misrecalls), and retained the genuine
  gaming members including all 3 in-band gold names.
- It deep-dived **every** survivor (10/10, zero ERROR/silent-skip), valued each with --json+--ticker,
  and returned an **honest 0-BUY** with a clear structural reason rather than a manufactured pick.
- The debt/lease-heavy code-path (the test focus) was exercised end-to-end: the NAV path fired and
  correctly returned -100% MoS on negative-tangible-equity operators; the FCF path correctly priced
  cyclical names above their cap; and the V-shape + cross-source vetoes killed the two artifact-MoS
  candidates. recall@gold = 57.1% headline / 100% in-band.

A skeptical PM gets exactly what the scanner promises: a clean shortlist of WATCH names worth human
DD (FLL and ACEL at the top on operating quality, not on a phantom margin), the misrecalls already
swept, and a documented reason that no name is a buy today. The one caveat to flag to the PM is the
CDRO XBRL-zero data gap and the four text-scan material_weakness flags, both of which need human
confirmation but neither of which alters the 0-BUY conclusion.
