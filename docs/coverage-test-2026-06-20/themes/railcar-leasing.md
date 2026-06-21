# Coverage Test — Railcar Leasing (Industrials)

- **Slug:** `railcar-leasing` | **Run dir:** `reports/smallcap/2026-06-21_cov-railcar-leasing/`
- **Skill:** v0.3.0 (commit `f12fef5`, dirty) | **Date:** 2026-06-21
- **Keywords (FTS):** `railcar, equipment leasing, rolling stock`
- **Code-path focus:** asset-heavy NAV / recall@gold
- **Headline:** **0 BUY** (clean). 3 deep-band theme-survivors all rate WATCH. NAV path did **not** fire.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw recall (union of 3 keywords) | 426 | railcar 126, equipment leasing 203, rolling stock 135; deduped 426 |
| Small-cap candidates (< $2.0B, post liquidity/SPAC scrub) | 214 | cheap_pass input |
| cheap_pass survivors | 149 | mechanical kill-flags applied |
| SIC gate (keep + review) | 149 | keep 88, review 61 (0 hard-dropped) |
| **Deep band (band="deep", < $2B)** | **101** | the over-recall pool |
| **Gate 2 theme-fit survivors (deep-dived)** | **3** | RAIL, GBX, RVSN |
| Gate 2 misrecall (resolved, not deep-dived) | 146 | banks/miners/chem/oil/biotech/restaurants |
| Reports written | 3 | 0 missing |
| **Mechanical BUY** | **0** | — |
| **Clean BUY (post-adversarial)** | **0** | — |

The over-recall is the canonical precision-gate scenario. "equipment leasing" and "rolling stock"
are generic filing phrases — every bank ("we lease equipment"), miner, chemical company and
restaurant carries operating-lease language. The deep band of 101 broke down as: **30 banks (SIC 60xx),
11 miners (10xx), 9 chemicals (28xx), 5 oil/gas (13xx)**, and only **4 SIC-3743 (railroad equipment)**
names. Gate 2 (LLM theme-fit from 10-K blurbs) cut 146 → 3.

## 2. Gate 2 theme-fit (LLM judgment from blurbs)

| Ticker | Name | SIC | Band | Mkt cap | Fit | Rationale |
|---|---|---|---|---|---|---|
| **GBX** | Greenbrier Companies | 3743 | deep | $1,537M | **pure_play** | Railcar manufacturer + Leasing & Mgmt Services (~17,000-car lease fleet). Canonical railcar lessor. |
| **RAIL** | FreightCar America | 3743 | deep | $178M | **pure_play** | Railcar manufacturer + railcar leasing/repair/rebody/conversion. |
| **RVSN** | Rail Vision Ltd. | 3743 | deep | $10M | **partial** | Early-commercialization railway-safety AI for rolling stock. Rolling-stock adjacent, not a lessor/maker. |
| GEL | Genesis Energy LP | 4610 | deep | $1,772M | misrecall | Pipeline/midstream; "railcar" appears incidentally. |
| EVI | EVI Industries | 7200 | deep | $205M | misrecall | Leases *commercial laundry* equipment — literal "equipment leasing" but off-theme. |
| (146 total misrecalls) | banks, miners, chemicals, oil/gas, biotech, restaurants | — | — | — | misrecall | incidental keyword matches |

## 3. recall@gold (gold list: GATX, TRN, GBX, RAIL)

`python tools/track_forward.py --theme railcar-leasing --recall-gold <candidates>`:

```
recall@gold:   75.0% (3/4)
  recalled_gold: GBX, RAIL, TRN
  MISSING_gold:  GATX
  loss-stage breakdown:
    recalled_final   3  GBX, RAIL, TRN
    sic_recovered    0
    dropped_mktcap   0
    gated_out        0
    fts_missed       1  GATX
```

- **recall@gold = 0.75 (3/4).** GBX, RAIL, TRN recalled; **GATX missed at the FTS stage** (`fts_missed`).
- Caveat: TRN counts as recalled but is **watch-band ($2.74B > $2.0B small-cap cap)** — recalled into
  the universe yet excluded from the deep band by the size ceiling. GATX (~$5B+) is a large-cap and
  would also be size-excluded even if FTS had caught it. So of the gold cohort, only **GBX and RAIL**
  are genuinely small-cap and reach deep-dive — both did. **The recall floor for the actionable
  (small-cap) gold subset is effectively 2/2.**
- The GATX FTS miss is a real, recorded recall gap, not a model artifact: GATX's filings did not
  surface on the three keywords used. A dedicated SIC-3743 reverse-recall floor would have caught it
  (GATX is SIC 6726/4741-ish historically, so even SIC floor is uncertain) — noted as a coverage gap.

## 4. Deep-dive survivors — full BUY-rule reasoning

BUY rule: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric `MoS ≥ 30%` **AND** `buy_eligible == true`
**AND** zero kill-flags. All three FAIL. None has any cheap_pass kill-flag (going-concern / death-spiral
/ material-weakness all False), so none is AVOID — all default to **WATCH**.

### GBX — Greenbrier (WATCH, NOT BUY)
- Rev $3,240M (−8.6%), NI +$204M, OCF +$266M, P/E 7.5, EV/EBITDA 5.8, FCF yield 17.3%.
- `mos_basis=fcf_cap`, **MoS = −129.2%**, `buy_eligible=False`.
- `buy_ineligible_reasons = [extreme_mos_review_required, fcf_sustainability_uncertain]`.
- **Why no BUY:** negative MoS (intrinsic FCF band is negative because normalized FCF uses a
  trough-cycle / lumpy-OCF average against a high market cap), and FCF-sustainability is uncertain
  because capex is unavailable (FCF uses OCF proxy; assets/rev=1.3 → capital-intensive). Both guards
  fire → buy_eligible False, and MoS < 30 anyway.
- Data-quality flags: `concentration_unquantified` (text flag, no XBRL magnitude),
  `capex_unavailable_fcf_uses_ocf_proxy`, `ebitda_series_partial_entries:4`, `extreme_mos_review_required`,
  `lumpy_ocf_normalization_suspect` (peak-yr OCF $329.6M > 2× median $15.3M).

### RAIL — FreightCar America (WATCH, NOT BUY)
- Rev $501M (−10.2%), NI −$41M, OCF +$35M, EV/EBITDA 5.3, FCF yield 17.6%.
- `mos_basis=fcf_cap`, **MoS = −111.3%**, `buy_eligible=False`.
- `buy_ineligible_reasons = [extreme_mos_review_required]`.
- **Why no BUY:** negative MoS + extreme-MoS guard. The reported net loss is driven by **non-cash
  warrant-liability accounting** (T2: a +$49M non-cash warrant gain in Q1 inflated GAAP NI elsewhere;
  the trailing window here shows the loss side). The deterministic model cannot un-distort warrant
  accounting, so the FCF intrinsic band is unreliable.
- Data-quality flags: `concentration_unquantified`, `net_income_nonpositive_pe_null`,
  `extreme_mos_review_required`, `lumpy_ocf_normalization_suspect` (peak OCF $44.9M > 2× median $8.1M).

### RVSN — Rail Vision (WATCH, NOT BUY) — the instructive near-miss
- Rev $1.5M (+14%), NI −$11M, OCF −$9M, cash $20M, runway ~2.2 periods, dilution +8.8%.
- `mos_basis=fcf_cap`, **MoS = null** (`mos_null_reason=intrinsic_band_unavailable`,
  normalized FCF nonpositive), **`buy_eligible=True`**.
- **Why no BUY despite buy_eligible=True:** the BUY rule requires a *numeric* MoS ≥ 30. MoS is **null**
  (no intrinsic band — FCF is negative so reverse-DCF returns null). buy_eligible passed only because
  the `low_revenue_loss_ratio` guard correctly recognized this as a legitimate **early/pre-revenue
  entity (right entity)** rather than a data error, EV is negative so multiples are null, and there are
  no kill-flags. The **null-MoS gate is the firewall that correctly blocks the BUY** — a clean
  demonstration that buy_eligible alone is not sufficient.
- Data-quality flags: `low_revenue_loss_ratio` (|NI|/rev=7.5×, early-stage right entity),
  `debt_is_total_liabilities_proxy`, `ev_nonpositive_multiples_null`, `intrinsic_band_null`.

## 5. Code-paths exercised (focus: asset-heavy NAV)

- **Asset-heavy NAV path: did NOT fire for any survivor** — the key finding. `mos_basis="nav"` is gated
  on `fcf_cap_model_unsuitable`, which requires `debt/assets > 0.62` (or financial-SIC). Observed:
  - GBX debt/assets = **0.406** → fcf_cap (NAV skipped)
  - RAIL debt/assets = **0.351** → fcf_cap (NAV skipped)
  - RVSN debt/assets = **0.098** → fcf_cap (NAV skipped)
  All three are capital-intensive railcar businesses (GBX runs a 17,000-car lease fleet financed with
  non-recourse railcar-backed notes), yet none crosses the 0.62 threshold, so the NAV intrinsic band
  was never populated (`nav_intrinsic_band=None` for all). **The 0.62 debt/assets threshold is too high
  to route moderately-levered railcar lessors onto the asset-heavy NAV path** — they get valued on a
  trough-cycle FCF basis that produces the spurious deeply-negative MoS. This is the headline
  code-path observation for this theme.
- **fcf_cap path:** fired for all three; cyclical detection True for GBX/RAIL (CV 0.53 / 3.98),
  trailing-5yr-avg normalization.
- **extreme_mos guard:** fired (GBX, RAIL).
- **fcf_sustainability_uncertain guard:** fired (GBX, capex unavailable).
- **lumpy_ocf_normalization_suspect:** fired (GBX, RAIL).
- **low_revenue_loss_ratio (early-entity, right-entity):** fired (RVSN) — correctly did NOT block buy_eligible.
- **intrinsic_band_null / numeric-MoS-required:** the gate that blocked RVSN's BUY.
- **cross_source_mismatch:** checked, no mismatch on any.
- **SIC reverse-recall floor:** universe shows SIC 3743 names recalled (RVSN, RAIL, GBX) but the
  floor did not recover GATX (FTS-missed, large-cap regardless).
- **Signals side-channel:** emitted automatically; firewalled — did not touch any BUY decision.

## 6. Adversarial verification

No mechanical BUYs to adversarially confirm. The adversarial question instead runs in reverse — *are
the WATCH/no-BUY verdicts themselves artifacts that hide a real opportunity?*

- **GBX:** The deeply-negative MoS (−129%) **is a model artifact** of trough-cycle FCF normalization
  against a high market cap, NOT a real distress signal. T2 (Seeking Alpha / BofA / Simply Wall St)
  shows a cyclical FY2026 downturn (rev −23% QoQ, lowered guidance, BofA Underperform $43 PT), a
  **healthy & growing leasing book** ($425M non-recourse term loan extended to 2032; secured railcar
  notes at 5.13%), 48 consecutive quarterly dividends. No fraud / SEC / short-seller. **Verdict: the
  tool correctly did not BUY (cyclical trough + uncertain FCF), but for partly the wrong mechanical
  reason — the negative-MoS number is not load-bearing. A human should value GBX on lease-fleet NAV,
  exactly the path the 0.62 threshold skipped.** Honest WATCH stands.
- **RAIL:** Negative MoS is an artifact of **warrant-liability accounting** distorting GAAP earnings
  (T2: Macro Ops / Motley Fool). No going-concern; cash $64M, low net leverage; reaffirmed 2026
  guidance ($500–550M rev, $41–50M adj EBITDA). Real risk is warrant + preferred dilution, plus 100%
  Mexico manufacturing (tariff/USMCA exposure). **Verdict: correct no-BUY — the dilution overhang and
  warrant-distorted earnings are genuine reasons to abstain; the model landed on the right answer.**
- **RVSN:** Reverse 1-for-30 split (Feb 2026) to cure Nasdaq min-bid; 69% rev decline H1'25; multiple
  active F-3/S-8 shelves (dilution machinery); 75% of reverse-split firms fail within 3yr. **Verdict:
  correct no-BUY — a textbook early-stage cash-burn / dilution profile. The null-MoS firewall caught
  the buy_eligible=True near-miss exactly as designed.**

## 7. Market-intel / T2 context (does NOT drive buy_eligible)

- **TrendsMCP (google search interest, "railcar"):** +26.1% YoY (recent 29 vs baseline 23; volume
  5,872 vs 4,658). Rising public interest, consistent with the replacement-cycle narrative
  (150k–200k railcars retiring over ~4 yrs per RAIL mgmt). T2 sentiment only — never load-bearing.
- TrendsMCP multi-source growth call (google search + news volume) errored once (proxy
  "Invalid content from server"); single-source retry succeeded. Logged as a data-quality issue.
- T2 disconfirmation searches: no fraud / SEC investigation / short-seller report on GBX, RAIL, or RVSN.

## 8. Data-quality issues

- **Over-recall via generic keywords:** "equipment leasing" / "rolling stock" swept 146 misrecalls
  (banks dominate). Precision rests entirely on Gate 2; SIC gate hard-dropped 0.
- **NAV-path gating gap:** debt/assets > 0.62 threshold excludes moderately-levered railcar lessors
  (GBX 0.41, RAIL 0.35) from the asset-heavy NAV path → spurious deeply-negative fcf_cap MoS.
- **Lumpy/trough-cycle OCF normalization:** flagged on GBX and RAIL; the normalized-FCF intrinsic
  band is suspect (peak-year OCF >> 2× median of other years).
- **Concentration unquantified:** GBX/RAIL/RVSN all carry a text concentration flag with null XBRL
  magnitude — cannot confirm/deny magnitude-based kill.
- **GATX recall miss:** FTS-stage miss (recorded in loss-stage taxonomy).
- **TrendsMCP multi-source transient error** (see §7).

## 9. Skeptical-PM usable verdict

**Usable: YES.** The run is a correct, well-behaved "nothing to buy" outcome for a niche
asset-heavy theme. The scanner (a) recalled the entire small-cap gold subset (GBX, RAIL both
deep-dived; recall@gold 3/4 with the one miss being a large-cap FTS gap), (b) cut a 146-name
keyword-driven misrecall pool down to the 3 true rolling-stock names via Gate 2, and (c) produced
**0 BUY** with each no-BUY traceable to an explicit, defensible guard. The null-MoS firewall on RVSN
(buy_eligible=True but MoS null → no BUY) is a clean demonstration that the BUY rule is conjunctive,
not buy_eligible-driven. The one actionable defect a PM should note: the **asset-heavy NAV path never
fired** despite this being the archetypal NAV theme — railcar lessors at debt/assets 0.35–0.41 fall
below the 0.62 routing threshold, so GBX (the textbook lease-fleet NAV candidate) was mis-valued on
trough-cycle FCF. The verdicts are still correct (GBX/RAIL are cyclical-trough abstains regardless),
but a human should re-value GBX on lease-fleet NAV before concluding. No false BUY; no missed clean
small-cap opportunity.
