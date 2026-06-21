# Coverage test — steel-fab (Materials)

- **Theme slug:** `steel-fab`
- **Sector:** Materials
- **Keywords:** `steel, steelmaking, metal fabrication`
- **Code-path focus:** cyclical / EBIT-cascade
- **Skill version:** v0.3.0 @ `f12fef5` (skill_dirty=true)
- **Run batch:** `reports/smallcap/2026-06-21_cov-steel-fab/`
- **Date:** run executed 2026-06-21 (system clock); coverage-test cohort 2026-06-20
- **Result headline:** **0 BUY** (0 clean after adversarial review). Highest clean MoS = BOOM +24.8%, below the 30% gate. The funnel is healthy: cyclical/EBIT-cascade vetoes and the P7 data-integrity gate did the bulk of the work.

---

## 1. Funnel

| Stage | Count |
|---|---|
| Raw discovery universe (FTS ∪ SIC reverse-recall floor, after mktcap fallback) | 87 |
| Small-cap deep band (band=`deep`) | 45 |
| Watch band (band=`watch`, mktcap 2–5B — surfaced, not deep-dived) | 21 |
| Cheap-pass survivors (deep band, 0 hard kill-flags) | 45 |
| **Gate 2 LLM theme-fit survivors (deep-dived)** | **21** |
| Gate 2 misrecall (resolved, not deep-dived) | 24 |
| deepdive_data + valuation completed (no ERROR files) | 21 / 21 |
| Mechanical BUY (mos_basis∈{fcf_cap,nav} ∧ MoS≥30 ∧ buy_eligible ∧ 0 kill-flags) | **0** |
| BUY surviving adversarial review | **0** |

Note: `cheap_pass` removed 0 of the deep band — every name had killflag_count=0 at discovery, so the
mechanical de-risk gate passed all 45; precision work fell to Gate 2 and to the valuation guards.

### Gate 2 (LLM theme-fit) — drop reasoning (24 misrecall)
The keyword set `steel / steelmaking / metal fabrication` over-recalled into adjacent commodity, mining,
financial, and consumer pockets. Dropped as misrecall:

- **Mining / royalty / commodity upstream (not steel/fab):** MSB (iron-ore royalty trust), NRP (coal/mineral royalty LP), METC (met-coal miner — a steel *input*, not a steelmaker), WWR (graphite), LGO (vanadium miner), LAC (lithium), TMCR (gold royalty), KOP (carbon/treated-wood chemicals).
- **Financial / insurance:** KFS (insurance holdco), PROV (savings bank).
- **Consumer / food / other industry:** HELE (housewares), SENEA (packaged food), RGR (firearms), POWW (ammunition), LYTS (lighting), VPG (precision sensors), MSEX (water utility), CVEO (workforce lodging), SKYH (aviation-hangar real estate), SMID (precast concrete), ARRY (solar trackers — steel content but a solar concept-play).
- **Construction equipment (machinery, not the steel/fab theme):** ASTE, GENC (asphalt/road-building heavy machinery).

### Gate 2 — retained (21, deep-dived)
- **pure_play (5):** FRD (flat-roll & tubular steel), IIIN (steel wire reinforcing), NWPX (steel pipe), SID (integrated steelmaker, Brazil), LUD (steel pipe fittings).
- **partial (16):** BOOM (explosion-clad metal), AP (specialty steel rolls), TWI (steel wheels/undercarriage), JBI (steel buildings/doors), SXC (metallurgical coke — steelmaking input/SIC 3312), EAF (graphite electrodes for EAF steelmaking), PPIH (engineered metal pipe), MLR (towing/recovery steel bodies), PLOW (snowplow/work-truck steel attachments), LEG (steel rod/wire components), TRS (metal stampings/forming), RAIL (railcar steel fabrication), OFLX (corrugated metal hose), HLP (cold-roll-formed steel profiles), ACNT (legacy stainless tubular, now specialty-chem), AEBI (specialty-vehicle metal fabrication).

---

## 2. Ranked shortlist (all WATCH — research output, not buy list)

Sorted by effective margin-of-safety (the BUY-trigger MoS for each name's mos_basis).

| # | Tkr | SIC | fit | mos_basis | eff MoS% | buy_eligible | gating reason(s) |
|---|-----|-----|-----|-----------|----------|--------------|------------------|
| 1 | SID  | 3310 | pure_play | fcf_cap | +377.9 | **False** | extreme_mos_review_required (data artifact — see §4) |
| 2 | BOOM | 3390 | partial   | fcf_cap | +24.8  | True  | clean — but below 30% gate |
| 3 | TWI  | 3312 | partial   | nav     | −25.3  | False | fundamental_decline, peak_contamination |
| 4 | JBI  | 3442 | partial   | fcf_cap | −29.1  | True  | negative MoS |
| 5 | TRS  | 3460 | partial   | nav     | −45.0  | True  | negative NAV MoS |
| 6 | OFLX | 3430 | partial   | fcf_cap | −49.4  | False | fundamental_decline, cross_source_mismatch |
| 7 | ACNT | 3317 | partial   | nav     | −50.0  | True  | negative NAV MoS |
| 8 | SXC  | 3312 | partial   | fcf_cap | −51.7  | False | peak_contamination_flag |
| 9 | IIIN | 3310 | pure_play | nav     | −56.0  | False | debt_truncation, fundamental_decline |
| 10 | MLR | 3713 | partial   | fcf_cap | −88.0  | True  | negative MoS |
| 11 | NWPX| 3317 | pure_play | fcf_cap | −88.3  | False | cross_source_mismatch |
| 12 | LEG | 2510 | partial   | nav     | −89.1  | True  | negative NAV MoS |
| 13 | LUD | 3317 | pure_play | fcf_cap | −93.9  | False | cross_source_mismatch |
| 14 | PPIH| 3564 | partial   | fcf_cap | −95.9  | False | cross_source_mismatch |
| 15 | PLOW| 3531 | partial   | nav     | −96.7  | False | debt_truncation, cross_source_mismatch |
| 16 | AP  | 3561 | partial   | nav     | −100.0 | True  | negative NAV MoS |
| 17 | EAF | 3620 | partial   | nav     | −100.0 | True  | negative NAV MoS |
| 18 | RAIL| 3743 | partial   | fcf_cap | −111.3 | False | extreme_mos_review_required |
| 19 | FRD | 3310 | pure_play | fcf_cap | −149.8 | False | extreme_mos_review_required |
| 20 | AEBI| 3531 | partial   | fcf_cap | null   | True  | FCF model produced no MoS (norm FCF ≈ −$5.2M) |
| 21 | HLP | 3569 | partial   | fcf_cap | null   | False | fundamental_decline_flag |

mos_basis distribution: **fcf_cap = 13, nav = 8, abstain = 0.** Every name flagged Cyclical=True
(CV above threshold), so all ran through cyclical-trough normalization (trailing-5yr-avg EBITDA/FCF).

---

## 3. BUY analysis — honest 0-BUY

**No name passes the mechanical BUY rule.** The rule requires `mos_basis ∈ {fcf_cap, nav}` AND numeric
effective MoS ≥ 30 AND `buy_eligible == true` AND zero kill-flags. The two ways a name could have qualified
both failed cleanly:

1. **Positive-MoS + buy_eligible names:** only **BOOM** is both buy_eligible and positive-MoS, and its
   +24.8% sits below the 30% threshold. It is the single best name in the funnel and the natural first
   stop for human DD, but the gate correctly withholds a BUY label.
2. **Large-MoS name (SID, +377.9%):** blocked by `extreme_mos_review_required` — this is the guard
   working, not a missed BUY (see adversarial review §4).

Every other buy_eligible name (JBI, TRS, ACNT, MLR, LEG, AP, EAF, AEBI) has negative or null effective MoS:
the market is paying *above* normalized intrinsic for these cyclicals at a point where the cycle has
already rolled over. That is the EBIT-cascade code-path doing its job — normalized (mid-cycle) FCF/EBITDA
is well below the trailing peak these prices were set against.

This is a textbook "correct nothing-found" outcome for a cyclical theme that is past its momentum peak
(see §6 T2 context: steel search interest −14.5% over the trailing 3 months).

---

## 4. Adversarial verification (near-misses & the one extreme-MoS name)

Because there are 0 mechanical BUYs, there is no BUY to confirm-or-reject. I adversarially examined the
two names that came closest to a BUY to confirm the gates are true-positives, not artifacts masking a real
opportunity.

### SID — National Steel (Companhia Siderúrgica Nacional, Brazil, 20-F) — MoS +377.9%, blocked
**Verdict: data artifact, correctly blocked. Not a real opportunity at this MoS.**
- EV computed as **−$2,611M** with `debt_unavailable` / `ev_excludes_debt` — the 20-F XBRL debt concept
  could not be pulled, so EV is nonsensically negative (net cash > market cap on paper). RANKING shows
  **revenue $0M** (revenue concept unmapped for the foreign filer) while net income is tagged $1,281M —
  internally inconsistent.
- `lumpy_ocf_normalization_suspect` (peak-year OCF $2,067M > 2× median $652M) and
  `normalized_uses_3yr_insufficient` both fire. The +377.9% MoS is built on a corrupted single-source
  input. `extreme_mos_review_required` blocks it; this is exactly the >100%-MoS tail the guard exists for.
  A foreign integrated steelmaker trading at a true 4.8x normalized FCF is not implausible, but this number
  cannot back a tradeable MoS — the block is correct.

### BOOM — DMC Global (explosion-clad metal / DynaEnergetics) — MoS +24.8%, clean, just short
**Verdict: real, clean, but legitimately not a BUY.**
- buy_eligible=True, no kill-flags, no veto flags (contamination ratio 1.35 — above trough, not peak-
  contaminated). EV/EBITDA 4.91, FCF yield 25.7%, P/E null (net income negative TTM).
- The +24.8% MoS is honest and below the 30% gate by ~5pts. With negative TTM net income and a high
  cyclical CV (1.92), the conservative gate is appropriate. This is the right name for a human PM to pick
  up first — but the machine should not, and did not, call it a BUY. No artifact; the threshold simply was
  not met.

### Cross-source-mismatch cohort (LUD, NWPX, OFLX, PPIH, PLOW) — P7 gate spot-check
**Verdict: legitimate data-integrity blocks, not false negatives.** All five show >2.5× SEC-vs-yfinance
debt disagreement (PLOW worst: SEC debt $7.4M vs yfinance $235M = 31.7×, plus revenue 3.7×). These are
single-source SEC XBRL extraction failures (partial-liability concept picked up as total debt); a tradeable
MoS cannot rest on a number an independent feed disputes by an order of magnitude. Even had any of these had
a positive MoS, blocking is the correct call. (None did — all negative — so the block is moot for BUY, but
it correctly suppresses a spurious MoS that a corrupted small denominator could otherwise inflate.)

---

## 5. Which code-paths fired

- **discover.py:** FTS recall UNION SIC reverse-recall floor for the steel SICs (3310/3312/3317) + mktcap
  fallback chain (deep/watch/unknown banding). 87 raw → 45 deep / 21 watch.
- **cheap_pass.py:** hard-kill scan (going_concern / death_spiral / material_weakness) — 0 fired.
- **Gate 1 (filter_by_sic):** coarse SIC exclusion + reverse-recall floor (keep=61, review=5).
- **Gate 2 (LLM theme-fit):** 45 deep → 21 retained, 24 misrecall (the precision workhorse here).
- **deepdive_data.py:** XBRL financial series, derived change-detection, insider record, P7 second-source
  sanity band (yfinance), and the firewalled T2 `signals` side-channel (price_divergence + ownership).
- **valuation.py — cyclical / EBIT-cascade focus (the targeted path):**
  - Cyclical=True on **all 21** → cyclical-trough normalization (trailing-5yr-avg) engaged everywhere.
  - mos_basis routing: fcf_cap ×13, nav ×8.
  - EBIT source = `OperatingIncomeLoss` (EBIT-cascade) across the board.
- **buy_eligible guards that bit (the v0.3.0 guards under test):**
  - `extreme_mos_review_required` — SID, RAIL, FRD
  - `fundamental_decline_flag` — HLP, IIIN, OFLX, TWI
  - `peak_contamination_flag` (V-shape) — SXC, TWI
  - `cross_source_mismatch` (P7) — LUD, NWPX, OFLX, PPIH, PLOW
  - `debt_truncation_suspected` — IIIN, PLOW
  - Not exercised this run: concentration kill, insurance_concepts_present, low_revenue_loss_ratio_extreme,
    wrong_entity_suspected, large_cap_out_of_scope, financial_sic-forced-unsuitable.

---

## 6. T2 diagnostic / market-intel context (context only — NEVER used in the rating)

Firewall verified: `valuation.py` references `signals` only in two explanatory comments (lines 687, 1484)
and reads **no** `signals.*` field; `signals` is a top-level sibling of `derived`, never nested inside it.
No BUY could originate or up-weight from these. Provided purely as analyst color:

- **TrendsMCP — Google search "steel":** +38.2% YoY (12M) but **−14.5% over the trailing 3M** — interest is
  elevated year-over-year yet cooling off a recent peak. Consistent with the cyclical-rollover picture the
  mechanical EBIT-cascade vetoes (peak_contamination on SXC/TWI, fundamental_decline on HLP/IIIN/OFLX/TWI)
  independently flagged from the filings.
- **TrendsMCP — "metal fabrication":** +22.9% YoY, ~flat over 6M (+1.7%). Demand interest steady, not
  accelerating.
- **Read-through:** a hot-but-cooling cyclical theme is exactly where the skill's discipline should produce
  a 0-BUY — the alpha (if any) was in the run-up, and current prices sit above normalized mid-cycle FCF for
  the buy_eligible names. Nothing in the T2 layer argues for overriding a single mechanical verdict.

---

## 7. Data-quality issues observed

1. **SID (foreign 20-F):** `debt_unavailable`, `ev_excludes_debt` (EV = −$2.6B), revenue unmapped ($0M in
   RANKING) while NI tagged $1,281M — foreign-filer XBRL concept-mapping gap. Correctly quarantined by
   `extreme_mos_review_required`, but the underlying SID financials are not usable as-is.
2. **P7 cross-source mismatches (5 names):** SEC XBRL `total_debt` diverges >2.5× from yfinance on LUD
   (7.4×), NWPX (10.3×), OFLX (4.1×), PPIH (2.9×), PLOW (31.7× + revenue 3.7×). Indicates the SEC debt
   extraction is picking a partial-liability concept on these names; flagged and gated correctly.
3. **debt_truncation_suspected (IIIN, PLOW):** implausibly small debt magnitudes from XBRL.
4. **Lumpy-OCF normalization suspect (FRD, SID, and others):** peak-year OCF >2× median of other years —
   normalization correctly flags but the FCF MoS on these should be treated as low-confidence.
5. **AEBI / HLP:** FCF model produced `mos = null` (normalized FCF ≈ −$5.2M for AEBI; HLP also veto'd by
   fundamental_decline) — abstain-like outcome surfaced as WATCH.
6. **Slug normalization quirk (cosmetic):** `--slug steel-fab` was written to disk as `steel_fab`
   (hyphen→underscore) in filenames; candidates file is `candidates_steel_fab.json`. Not a correctness
   issue but worth noting for any downstream path-matching.
7. Output JSONs are UTF-8 with non-ASCII (Chinese log strings + smart quotes); must be read with
   `encoding='utf-8'` (default GBK on this Windows box raises UnicodeDecodeError).

---

## 8. recall@gold

**n/a** — steel-fab has no hand-built gold true-member list (`track_forward.py` THEME_GOLD covers only
deathcare / water-utilities / railcar-leasing / regional-gaming). `track_forward --recall-gold` returned
"no gold list for theme 'steel-fab' — not measurable." Discovery recall for this theme is therefore audited
only structurally (SIC reverse-recall floor on 3310/3312/3317 plus FTS), not numerically.

---

## 9. Skeptical-PM usable verdict

**Usable: YES — as a landmine-scanner, and the scan came back clean (0 BUY).**

The run is internally coherent and the cyclical/EBIT-cascade machinery behaved exactly as designed on a
hot-but-cooling Materials theme: it normalized every name to mid-cycle, found that current prices sit above
normalized FCF for the eligible names, and used the EBIT-cascade vetoes (peak_contamination, fundamental_
decline) plus the P7 data-integrity gate to suppress every spurious or rollover-contaminated candidate. The
two near-misses both resolve correctly under adversarial scrutiny — SID is a foreign-filer data artifact the
extreme-MoS guard caught; BOOM is a genuine but sub-threshold name.

A skeptical PM gets exactly what this tool is supposed to deliver: a defensible "nothing clears the bar right
now," a single name worth a human look (BOOM), and an explicit, reason-tagged list of why the other 20 were
withheld. The honest caveat is the data-quality tail (SID unusable, 5 names with cross-source debt
disagreement) — those are flagged, not hidden, which is the correct behavior.

**0 BUY, 0 clean BUY. Theme cohort is real but offers no clean mechanical entry at current prices.**
