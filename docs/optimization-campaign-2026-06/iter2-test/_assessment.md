# Iteration-2 Test Assessment, small-cap-deepdive (post commit `2599d66`)

> Assessor: independent test-judge subagent. Verified every load-bearing claim against the raw batch
> outputs under `reports/smallcap/2026-06-20_*/` (deepdive JSONs, valuation JSONs, RANKING.md), not
> just the prose reports. Scope: the 4 iter2 theme runs (`ai-dc-power`, `defense-drones`,
> `glp1-supply-iter2`, `title-insurance`) + the targeted `iter2-regression` (NRP/INVA/EU/SIGA).
> Judged against the real-world-usable bar and the iter1 carry-forward (P-A…P-H + deferred P7/8/14/11/15-17).
> No new pipeline run was launched: this is an assessment of completed, on-disk batches; all counts and
> flags below were re-derived directly from JSON.

---

## 1. Did iter2 CLOSE the gaps? (V-shape veto P-A, label fix P-B, did the 4 themes complete?)

**YES on all three. The two headline fixes work on real new data, and all 4 themes completed this time.**

### P-A, V-shape veto (`peak_contamination_flag`), CLOSED, surgical, no over-block
Verified directly from valuation JSONs:

| Name | contam_ratio | rev_slope | below_avg | latest_NI | peak_contam | buy_eligible | MoS/basis | Outcome | Correct? |
|---|---|---|---|---|---|---|---|---|---|
| **NRP** (reg) | 0.7445 | +1 | True | −$84.8M | **True** | **False** (`['peak_contamination_flag']`) | **+36.4% fcf_cap** | 避开 | ✅ V-shape trap KILLED by machine |
| **INVA** (reg) | 0.9015 | +1 |, | + | False | True (`[]`) | **+30.2% fcf_cap** | **买入 BUY** | ✅ clean grower NOT over-blocked |
| **EU** (reg) | 0.8808 | +1 | False | loss | False | True | null fcf_cap | 观察 | ✅ genuine trough-recovery spared |
| **SIGA** (reg) | 0.9051 | −1 | True | + | False | False (`['concentration_kill','fundamental_decline_flag']`) | null→nav −61% | 避开 | ✅ still double-blocked |

- **The decisive proof:** NRP's `margin_of_safety_pct = 0.3639` is *real*, without P-A it is a 36.4%-MoS
  mechanical BUY (the exact melting-ice-cube the iter1 assessment flagged as the human-only catch). P-A is
  now the *only* thing that catches it (`fundamental_decline_flag` stays False because whole-window slope = +1).
  The flag fires **independent of rev_slope_sign**, exactly as designed.
- **No over-block on growers/troughs:** across **all 31 deep-dived names** in the 4 themes + regression,
  `peak_contamination_flag` fired on exactly **2** (NRP in regression; **BWIN** in title-insurance) and
  `fundamental_decline_flag` on exactly **2** (SIGA; **EMBC** in glp1). On the two deliberately
  fast-growth-heavy cohorts (ai-dc-power, defense-drones) it fired **0/8 and 0/14**, including on the
  strongest growers (HYLN +130%, UMAC +101%, KRMD +22%). The three V-shape guard conditions each blocked a
  potential false fire: NI>0 spared ESOA (+$2.2M) and KOPN; `contam ≥ 0.8` spared TGEN (6.56) and the
  defense decliners (SPAI/KOPN/MVIS); `latest_below_avg=False` spared OSS and EU. **Veto is a precision
  instrument, not a blanket loss-making screen.**
- **EMBC is the bonus confirmation** the sibling `fundamental_decline_flag` still works on a *monotone*
  decliner (rev_slope −1, contam 0.824 < 1, below_avg True), fired correctly and gated buy_eligible.

### P-B, `low_revenue_loss_ratio` label, CLOSED for the intended cases, ONE borderline persists
- **Intended re-casing works:** the label fired (advisory, did not gate) on the right names, HYLN
  (ai-dc-power, |NI|/rev 16.5x), and ODYS/SPAI/SWMR/MVIS (defense). These are real companies with tiny
  revenue vs large loss; the PM now reads "early/pre-revenue, right entity" instead of the old misleading
  "wrong entity." Correct.
- **EU stayed False** (consistent across both the regression and uranium-miners batches), the ratio was
  not extreme enough to trip; not a spec requirement, correctly silent.
- **The remaining seam (still a real, recurring issue):** on *extreme* NI/rev anomalies the OLD
  `wrong_entity_suspected` STILL co-fires and is the field that actually gates buy_eligible. Confirmed in
  `buy_ineligible_reasons` on **STSS** (glp1, ratio 1,384x), **MVIS** (defense, 78.6x), and **TIPT**
  (title, 71.6x, a discontinued-ops reclass artifact). The *decision* is correct every time (all → WATCH/
  AVOID, never a spurious BUY), but the gating reason-string a PM reads is the less-accurate one. P-B
  added the better label but did not raise the `wrong_entity` threshold high enough to *cede* gating to it
  on these tails. **Partial close, outcome-safe, label-cosmetic gap.**

### Did the 4 themes complete?, YES (iter1's async failure is fixed)
All 4 ran fully synchronous to completion. Counts re-verified from disk: ai-dc-power **8 deepdive / 8
valuation / RANKING.md**; defense-drones **14/14/RANKING**; glp1-supply-iter2 **5/5/RANKING**;
title-insurance **5/5/RANKING**. **Zero `deepdive_*_ERROR.json` in any batch** (no crashes/rate-limit
kills; the P-D mechanism in `tools/deepdive_data.py:1693` exists but was not needed). Every survivor was
deep-dived; no silent skips. This directly closes the iter1 gap where these same 4 themes failed to finish.

---

## 2. NEW regressions or issues

No correctness regression. Four issues, all logged, **none produced a wrong BUY**:

1. **(NEW, real product bug, MED) `peak_contamination_flag` fires on degenerate NEGATIVE contamination
   ratios.** BWIN (title) fired with `contamination_ratio = −2.4618`. The `contam < 0.8` test passes
   *trivially* for any negative ratio (negative FCF-normalization base), so the flag's intended semantics
   ("latest base well below a POSITIVE 5-yr avg") do not hold. Outcome was still correct (BWIN already
   blocked by `financial_sic` + `debt_truncation`), but the veto's magnitude is uninterpretable on a
   degenerate input. **Fix: guard against negative/degenerate normalization bases before the V-shape test.**
   (Note: KRMD/LFCR in glp1 also carry negative contam ratios but had `latest_below_avg=False`, so they did
   not trip, the bug only bites when below_avg + NI<0 co-occur with a negative base.)

2. **(carry-forward, NOT closed, LOW/cosmetic) `wrong_entity_suspected` over-gating on extreme tails**
   (see §1 P-B): STSS/MVIS/TIPT. Outcome-safe, reason-string only.

3. **(carry-forward, LOW) Gate-2 denominator mismatch persists.** `finalize_run` still counts every
   `band=deep` row and cannot natively distinguish Gate-2 `misrecall` drops from forgotten deep-dives;
   every theme had to either re-band to `misrecall` (ai-dc-power, glp1 → `_raw_*_preGate2.json` preserved)
   or pass `--allow-missing`. This is iter1's P-F, still open. Operational friction, not data loss.

4. **(NEW, surfaced gap, MED for the concentration objective) The magnitude concentration-kill is XBRL-
   only and silently returns `null` for filers who disclose concentration in narrative text but not in
   machine-readable segment members.** Two clean exposures: **LFCR** (glp1, text `customer_concentration_
   flag=True` but magnitude `concentration_flag=null`, the canonical few-customer CDMO) and **SWMR**
   (defense, the textbook SIGA single-customer-non-renewal pattern, but a March-2026 micro-IPO with no
   mature 10-K XBRL, so the magnitude rule could not fire). In both the right rating was reached by analyst
   reading of the disclosure / other guards, but the *mechanical* SIGA kill is blind to the text-only and
   pre-/early-XBRL cohort, which is exactly where the most concentrated names cluster. **Fix: a
   `concentration_unquantified` advisory when text=True AND magnitude=null, and S-1/early-filer ingestion.**

---

## 3. Financial-SIC path on title-insurance (nav/abstain, no fcf_cap BUY?)

**PASS. The HCI failure mode (an fcf_cap BUY on a financial company) did NOT recur.** Re-verified from
the 5 valuation JSONs:

| Name | SIC | mos_basis | buy_eligible | gating reason | NAV MoS |
|---|---|---|---|---|---|
| ITIC | 6361 (title) | **nav** | False | `financial_sic_forced_unsuitable` | −57.0% |
| TIPT | 6331 | **nav** | False | financial_sic + debt_trunc + wrong_entity + fund_decline | −75.3% |
| BWIN | 6411 | **nav** | False | financial_sic + debt_trunc + peak_contamination | −100% |
| SLQT | 6411 | **nav** | False | `financial_sic_forced_unsuitable` | **+62.6%** |
| BOC | 6510 | fcf_cap | True | (none), blocked downstream by **null MoS** |, |

- **All four insurance-SIC carriers routed to NAV with `financial_sic_forced_unsuitable` → buy_eligible=
  False.** No financial reached fcf_cap.
- **SLQT is the marquee save:** NAV MoS **+62.6% ≥ 30**, it clears the MoS bar and on a naive NAV screen
  would be a BUY, but `financial_sic_forced_unsuitable` forces buy_eligible=False → WATCH/AVOID. The
  disconfirmation (DOJ False Claims Act suit) independently confirmed the value trap. **Guard and evidence
  agreed; the gate alone was sufficient.**
- **The documented latent hole (BOC):** Boston Omaha is SIC 6510 (real-estate operator); prefix 65 is NOT
  in the financial-SIC list (60/61/63/64/67), so despite owning a surety-insurance sub it routed to
  fcf_cap with buy_eligible=True. It produced **no false BUY only because normalized FCF is negative → MoS
  null** (the second line of defense), NOT because the SIC gate caught it. A hypothetical positive-FCF
  holdco-with-insurance-sub on a non-financial SIC would slip the gate. **Realized? No. Latent? Yes** ,
  warrants a coarse-gate override (flag insurance subsidiaries / SIC-65 holdcos). This is the one genuine
  hole the financial stress theme exposed.

**Cross-check across the whole iter2 corpus: exactly ONE BUY exists** (INVA, regression), every one of
the 4 themes is an honest **0-BUY**, and no fcf_cap BUY appears on any financial-SIC name anywhere.

---

## 4. Updated USABLE verdict + prioritized iteration-3 work

### Verdict: **USABLE, iter2 hardens the core to a defensible standard.**
Iteration-1 turned the engine from a value-trap generator into a landmine-scanner. **Iteration-2 closes
its single biggest residual correctness gap (P-A V-shape blind spot) with a mechanical, surgical veto that
kills the real trap (NRP) without strangling growers/troughs (INVA/EU + 0 false fires on 22 fast-growth
names), re-cases the P-B label for the intended cases, ships the P-C/P-D hygiene (no path-doubling in any
batch; auditable crash mechanism present), and, critically, completes all 4 themes synchronously that
iter1 failed to finish.** The financial-SIC machinery held under a deliberate financial-sector trap
(SLQT save). The 0-BUY / 1-BUY split is the honest, mechanically-enforced answer. **The acceptance bar
(zero data-artifact BUYs survive; no genuine clean grower suppressed; financial path never fcf_cap-BUYs)
is met on real new data.** Calibration remains unmeasurable until verdicts mature (2027-06), an honest
unknown, not a failure.

### Prioritized remaining work for iteration 3

**Tier-A, new correctness/coverage gaps surfaced by iter2 (do first; small, high-value):**
- **A1. Degenerate-base guard for `peak_contamination_flag`** (§2.1, BWIN), reject negative/zero FCF-
  normalization bases before the V-shape `contam < 0.8` test so the flag can't fire trivially. Low effort.
- **A2. `concentration_unquantified` advisory + early-filer/S-1 ingestion** (§2.4, LFCR/SWMR), close the
  text-vs-XBRL concentration seam; the magnitude SIGA-kill is currently blind to text-only and pre-/early-
  XBRL filers, the exact cohort where single-customer risk concentrates. This is the most material new gap.
- **A3. Financial coarse-gate override for SIC-65 / insurance-subsidiary holdcos** (§3, BOC), close the
  latent fcf_cap-routing hole before a positive-FCF case realizes it.
- **A4. Finish P-B: raise the `wrong_entity_suspected` gating threshold so it cedes to
  `low_revenue_loss_ratio` on the present-but-tiny-revenue tail** (§1/§2.2, STSS/MVIS/TIPT), outcome
  already safe; this is a reason-string accuracy fix.
- **A5. P-F Gate-2 denominator**, persist the `misrecall` set into the run manifest so `finalize_run`
  treats gated names as resolved (kills the spurious "N missing" warning + the manual re-band step).

**Tier-B, the deferred iteration-1 expansions (the strategic agenda; larger):**
- **P7** secondary-source sanity band (independent cross-check of the single SEC-derived valuation ,
  addresses iter1 core diagnosis #4, no second source).
- **P8** SIC reverse-recall + `recall@gold`, the recall floor is still never *measured*; Gate-2 precision
  is documented (2.8 to 15.9%) but recall is audited only by manual blurb re-scan. This is the right next
  rigor step (addresses iter1 diagnosis #5).
- **P14** forensic spine (provenance/audit trail per number).
- **P11-full** catalyst-mechanism validation (currently frozen to WATCH; the mechanism is untested).
- **P15/16/17** firewalled intraday side-channels (strictly isolated diagnostic, must NOT touch
  buy_eligible).
- **P-G** `form_used=None` on foreign filers (provenance tag for IFRS/20-F context).

**The campaign's deepest unresolved question is unchanged and belongs to Tier-B: the "delayed-information-
diffusion" thesis is still not *measured* in code**, the engine is a rigorous cheapness+quality+landmine
filter, which is genuinely usable, but the original alpha hypothesis remains unoperationalized. P7/P8/P14
are the path to testing it. **Recommendation: ship Tier-A (quick correctness/hygiene), then commit
iteration-3 to P8 (recall measurement) + P7 (secondary source) as the first real test of the thesis.**
