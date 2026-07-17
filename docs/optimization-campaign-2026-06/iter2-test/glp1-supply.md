# iteration-2 test report, theme `glp1-supply`

**Theme keywords:** `GLP-1,obesity drug,contract manufacturing,drug delivery device`
**Theme interpretation (load-bearing):** the obesity-drug **SUPPLY CHAIN**, CDMO / contract
manufacturing of injectables, drug-delivery devices (autoinjectors / pens / syringes / needles /
infusion), fill-finish and sterile components. **NOT** the drug developers themselves: a clinical-stage
biotech advancing its *own* GLP-1/obesity molecule is a principal/competitor, not a picks-and-shovels
supplier, and is a **misrecall for this theme**.
**Focus:** obesity-drug supply chain (a hot theme that has *recently cooled* per TrendsMCP).
**Run batch:** `2026-06-20_glp1-supply-iter2` (skill commit `2599d66`, post `peak_contamination_flag`
V-shape veto + `low_revenue_loss_ratio` label + hygiene).
**Date:** 2026-06-20. **Verdict horizon:** matures 2027-06 (calibration unknown until then, honest state).
**Stress objectives:** (1) **concentration kill**, does a single-pharma-customer dependence get caught;
(2) **growth handling vs the V-shape veto**, does `peak_contamination_flag` correctly fire / stay silent
on a declining-vs-ramping cohort; (3) discipline of Gate 2 under a keyword set that sweeps the entire
biotech/pharma sector.

> **This is a research landmine-scanner output, not a buy list.** A `观察`/WATCH means "survived the
> mechanical gates, warrants human DD." Nothing here clears the iter2 BUY bar.

---

## 1. Funnel (raw → survivors → deep-dived)

| Stage | Count | Note |
|---|---|---|
| SEC FTS raw recall (10-K/10-Q/20-F/40-F) | ~497 hits across 4 keywords | `GLP-1`=203, `obesity drug`=8, `contract manufacturing`=283, `drug delivery device`≈small; heavy keyword overlap |
| After market-cap filter (small-cap ≤ $2.0B) | 476 universe rows → 207 small-cap | universe CSV |
| After `cheap_pass` mechanical health check | 113 survivors | going-concern / death-spiral / material-weakness scan |
| After Gate 1 (SIC coarse) | 113 (keep=22, review=91) | SIC alone removed nothing; pharma/biotech SICs (2834/2836) passed to Gate 2 |
| Band split | deep=93 (≤$2.0B), watch=20 ($2.0 to 5.0B) | watch-band surfaced, **not** deep-dived per band guard |
| **Gate 2 (LLM theme-fit) on 93 deep-band** | **5 retained** (pure_play/partial), 88 misrecall | **5.4% precision**, in line with the documented ~6.8% "AI agent" FTS over-recall |
| Deep-dived (every retained survivor) | **5 / 5** | LFCR, STSS, KRMD, EMBC, AMPH, all valuated, **no** `deepdive_*_ERROR.json` |

**Why the precision is so low.** `GLP-1` and `obesity drug` are pharmacology terms that match the *entire*
clinical-stage biotech sector, and `contract manufacturing` is a generic phrase that appears in any 10-K
risk factor. The 93-name deep band was dominated by **drug developers** (~60 SIC-2834/2836 biotechs:
KROS, SGMT, ALT, VTVT, CRBP, AMRN, VNDA, LXRX, MNKD, ESPR, RIGL, IOVA, SRPT, GERN, KMDA, AKBA, MAZE,
ARDX, VIR, GLUE, MGTX, INBX…), **weight-loss services / consumer** (WW, MED/Medifast, XPOF, LFMD, GDRX),
**foods** (LWAY, NOMD, MGPI, FTLF, LFVN), **apparel/retail** (CURV, RCKY, DXLG), **non-GLP devices**
(OM dialysis, CARL spine, MOBI vagus-nerve, AORT cardiac, TNDM/insulin, TCMD), **EMS** (KTCC, KE, NSYS),
a **battery** maker (ELVA), a restaurant (PZZA) and an **insurer** (ANG-PD). Classic FTS over-recall ,
Gate 2 is load-bearing; skipping it would have sent the whole small-cap biopharma sector to deep-dive.

**The crucial theme-discipline call (developer ≠ supplier).** Several names are GLP-1/obesity *plays* but
the *wrong side* of the trade for a supply-chain theme and were therefore dropped as misrecall:
**VANI** (Vivani, develops its own GLP-1 exenatide/semaglutide *implant* NPM-115/139), **ALT**
(Altimmune, own GLP-1/glucagon dual agonist pemvidutide), **CRBP** (Corbus, own obesity candidate),
**VTVT / SGMT / MNKD / CORBUS** (own metabolic drugs), **OPK** (OPKO, supplies its *own* GLP-2 peptide to a
partner; primarily diagnostics + own pharma). These are drug developers/principals; they belong in a
"GLP-1 drug" theme, not a "GLP-1 supply chain" theme.

**Recall audit (did Gate 2 drop a genuine supplier?).** I re-scanned all 93 deep-band blurbs for
high-signal supply-chain terms (`cdmo`, `contract development/manufactur`, `fill-finish`, `aseptic`,
`prefilled`, `autoinjector`, `pen needle`, `syringe`, `cartridge`, `injection device`, `drug delivery`,
`subcutaneous`, `sterile inject`, `device assembly`). Eight non-retained names hit ≥1 term; on inspection
**all 8 were false hits**: ICCC (animal-health biologics, fill-finish of its *own* calf product),
RCKY (footwear "contract manufacturing"), DCTH (liver-cancer device, incidental "subcutaneous"),
MNKD / GRCE / MGNX / KRRO (drug developers delivering their *own* molecules), KTCC (electronics EMS).
**Zero genuine suppliers were dropped → no add-backs. Final deep set = 5.**

---

## 2. Ranked shortlist (from `RANKING.md`)

| # | Ticker | Name | Theme role | Rating | Conf | Mktcap | Rev | NI | OCF | Rev growth | EV/Sales | EV/EBITDA | MoS basis | MoS | kill |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AMPH | Amphastar | injectable / prefilled-syringe mfr + CMO (partial) | 观察 WATCH | 55% | $829M | $720M | +$98M | +$156M | −2% | 1.78x | **5.74x** | fcf_cap | **−38.6%** | 1 (MW) |
| 2 | EMBC | Embecta | pen needles / injection devices (partial) | 观察 WATCH | 50% | $185M | $1,080M | +$95M | +$192M | −4% | 1.23x | **4.69x** | nav | −100% | 2 (MW + fund-decline) |
| 3 | KRMD | KORU Medical | subcutaneous infusion drug-delivery (partial) | 观察 WATCH | 45% | $179M | $41M | −$3M | +$0M | +22% | 4.15x | n/a | nav | −92.5% | 0 |
| 4 | LFCR | Lifecore Biomedical | **fully-integrated CDMO, aseptic fill-finish** (pure) | 观察 WATCH | 45% | $208M | $76M | −$18M | +$7M | +772%* | 2.49x | n/a | nav | −100% | 1 (MW) |
| 5 | STSS | Sharps Technology | syringes / drug-delivery systems (pure) | 观察 WATCH | 35% | $78M | $0.2M | −$282M† | −$11M |, | 332x | n/a | nav | +83.6%† | 0 |

\* LFCR's +772% "revenue growth" is an XBRL artifact of a fiscal-year/segment-reclassification base, not
real organic growth, read with the `debt_truncation_suspected` and data-quality caveats below.
† STSS's −$282M NI and the +83.6% NAV MoS are **both artifacts** (see §3 and §5), STSS is a near-shell
($0.2M revenue) with a large non-cash paper loss; the NAV MoS rests on a book-equity proxy.

EV/EBITDA via the EBIT cascade (`OperatingIncomeLoss` + D&A) populated only for the two **profitable**
names, **AMPH 5.74x** and **EMBC 4.69x**, and correctly returned `null` for the three loss-makers
(KRMD, LFCR, STSS) whose EBITDA series was non-positive (`ebitda_nonpositive_ev_ebitda_null` fired as
designed) rather than fabricating a multiple.

---

## 3. BUY decision (full `buy_eligible` reasoning), **honest 0-BUY**

**iter2 BUY rule:** `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30%` AND `buy_eligible == true`
AND zero kill-flags. `buy_eligible` now also requires `not peak_contamination_flag`.

**Result: 0 BUY.** The single name that clears the *MoS* threshold (STSS, NAV MoS +83.6%) is exactly the
name the eligibility gate vetoes, a clean demonstration that the mechanical layer is doing its job.

```
ticker  mos_basis  MoS%     buy_eligible  buy_ineligible_reasons        blocks BUY because…
AMPH    fcf_cap    -38.6%   true          []                            MoS < 30% (overvalued vs reverse-DCF) + MW (kill=1)
EMBC    nav        -100%    false         [fundamental_decline_flag]    NAV MoS < 30% AND fund-decline veto AND MW (kill=2)
KRMD    nav        -92.5%   true          []                            NAV MoS < 30%
LFCR    nav        -100%    false         [debt_truncation_suspected]   NAV MoS < 30% AND debt-truncation guard AND MW (kill=1)
STSS    nav        +83.6%   false         [wrong_entity_suspected]      MoS ≥ 30% but buy_eligible=false → DOWNGRADE to WATCH
```

**STSS is the cleanest decision-layer demonstration in this run.** Its NAV MoS of +83.6% would, on the
MoS test *alone*, be a BUY. But `buy_eligible == false` (the `wrong_entity_suspected` /
`low_revenue_loss_ratio` unit-anomaly guard fired on the implausible NI/revenue ratio of 1,384x), so the
rating is mechanically **downgraded to WATCH**, and because no *hard* kill-flag (going-concern /
death-spiral) is present, it lands at WATCH, not AVOID. This is precisely the iter2 design intent: the
eligibility composite now *bites* on a would-be-BUY rather than letting a data artifact drive a buy
recommendation. (Caveat: see §5, `wrong_entity_suspected` firing on a *real but tiny* producer is the
borderline P-B case; the correct downstream outcome, WATCH, not BUY, was nonetheless achieved.)

**Why no catalyst waiver applies:** none of the 5 carries a closed-list catalyst (spinoff 10-12B /
cluster Form-4 buys / court-ordered sale / delisting-forced selling). EMBC is technically a 2022 spinoff
from BD, but that index-forced-selling window is long closed (no dated, current trigger), and a verified
catalyst is frozen to WATCH-not-BUY in iter1/iter2 regardless.

**The signal is exactly what PHILOSOPHY #2 predicts.** In a hot theme that the whole market can name, the
genuine industrial beneficiaries trade with no margin of safety. The two *real, profitable* picks-and-
shovels names here, **AMPH** (injectables/prefilled-syringe manufacturer, $98M NI, $156M OCF) and
**EMBC** (the dominant pen-needle maker, $95M NI, $192M OCF), are *not* expensive on the multiple
(AMPH 5.7x, EMBC 4.7x EV/EBITDA), yet still print **negative MoS / negative NAV** because (a) AMPH's
reverse-DCF prices in a *decline* its trailing −2% top-line corroborates, and (b) EMBC carries
debt > assets (debt-to-assets 1.29) so its tangible NAV is negative. Cheap-on-earnings is not the same as
margin-of-safety, and the model correctly refuses to confuse the two.

---

## 4. Stress objective #1, concentration kill (single pharma customer), **PARTIAL PASS (one gap surfaced)**

This run was chosen partly because the obesity-supply-chain CDMOs are textbook single-/few-customer
businesses. The result is informative, and exposes one real seam between the two concentration signals.

| Ticker | text customer-concentration flag (`tenk`) | magnitude `concentration_flag` (XBRL) | `top_customer_pct` | `top_program_pct` | net effect |
|---|---|---|---|---|---|
| **LFCR** | **True** (10-K risk-factor language) | **null** | null | null | buy_eligible blocked by `debt_truncation_suspected`, NOT by concentration |
| STSS | False | null | null | null |, |
| KRMD | False | null | null | null |, |
| EMBC | False | null | null | null |, |
| AMPH | False | null | null | null |, |

**Finding (the seam).** **LFCR is the canonical few-customer CDMO**, it historically derives a large
share of revenue from a handful of HA/aesthetic-injectable customers, and its 10-K *risk-factor text*
correctly trips the qualitative `customer_concentration_flag = True`. But the **new P3 magnitude-based
kill** (`concentration_flag = "kill"` when `top_customer_pct > 40` OR `top_program_pct > 60`) returned
**null**, because the XBRL `RevenueFromContractWithCustomer` segment members that the magnitude gate reads
did not expose a per-customer percentage for LFCR. So the magnitude gate could not *quantify* a
concentration it qualitatively knows exists. In this instance the outcome was still correct, LFCR's
`buy_eligible` is already `false` (via `debt_truncation_suspected`) and the rating is WATCH, so **no
wrong BUY slipped through**. But had LFCR's balance sheet been clean, the magnitude gate's null would have
left the concentration risk un-penalized at the eligibility layer, relying only on the analyst reading the
text flag. **This is the one genuine gap the stress test was designed to find:** the magnitude-based
concentration kill is only as good as the XBRL segment tagging, and for filers who disclose customer
concentration in narrative text but not in machine-readable segment members, the kill silently does not
fire. Recommended follow-up: when `customer_concentration_flag (text) == True` AND magnitude
`concentration_flag == null`, surface an explicit `concentration_unquantified` advisory so the PM is told
the text flag exists but could not be magnitude-confirmed (today the two signals live in separate fields
and a fast reader could miss the text flag entirely).

Net: **the kill machinery behaved correctly where it could read the data, and the right rating was
reached on every name, but the run surfaced a real text-vs-XBRL coverage gap on the single best
concentration example in the universe.** Honest partial pass.

---

## 5. Stress objective #2, growth handling vs the V-shape veto, **PASS, no over-block; one correct fire**

The second stress target was whether `peak_contamination_flag` (the V-shape value-trap veto) and its
sibling `fundamental_decline_flag` fire correctly on a cohort that mixes a decliner (EMBC), flat
mature names (AMPH), a real grower (KRMD), an artifact-grower (LFCR) and a near-shell (STSS).

| Ticker | rev_slope | contam_ratio | latest_below_avg | latest_NI | `fundamental_decline_flag` | `peak_contamination_flag` | Correct? |
|---|---|---|---|---|---|---|---|
| **EMBC** | **−1** | **0.824** | **True** | +$95.4M | **TRUE** | false | ✓ **fired correctly**, declining mature device co. |
| AMPH | +1 | 1.055 | False | +$98.1M | false | false | ✓ flat/up, profitable → no veto |
| KRMD | +1 | −0.160 | False | −$2.6M | false | false | ✓ genuine +22% grower not strangled |
| LFCR | +1 | −1.452 | False | −$18.0M | false | false | ✓ artifact-grower; flag correctly silent |
| STSS | 0 | 1.641 | True | −$282.5M | false | false | ✓ flat slope → neither veto applies |

**`fundamental_decline_flag` fired on EMBC, and only EMBC, and it was right.** EMBC satisfies all three
AND-conditions (`rev_slope_sign = −1`, `contamination_ratio 0.824 < 1.0`, `latest_below_avg = True`): a
mature pen-needle business whose top line is shrinking (−3.8%) into a contaminated trailing average. The
veto correctly downgraded what would otherwise be a *cheap* name (4.7x EV/EBITDA, $192M OCF), the
melting-ice-cube defense doing exactly its job on a real decliner. This is the iter2 mechanical
carve-out working as specified (a measured-data veto, distinct from the banned qualitative cyclical-turn
perpetual veto).

**`peak_contamination_flag` fired on zero of the 5, the desired no-over-block result.** The one name that
*looks* superficially V-shaped, **STSS**, has `rev_slope_sign = 0` (flat, a near-zero revenue base), so
the whole-window fit is flat and the V-shape pattern legitimately does not apply; the flag stayed silent
and STSS was instead governed by its eligibility veto (§3). **KRMD** is the cleanest "do-not-strangle"
demonstration: a genuine +22% subcutaneous-infusion grower with `latest_below_avg = False`, neither veto
fired, so the machine did **not** punish real growth. **Both mechanical vetoes behaved as conservative,
correctly-targeted downgrade-only guards: one true fire (EMBC, a real decliner), zero false positives on
the grower (KRMD) and the profitable mature name (AMPH).** Stress objective met.

---

## 6. Data-quality observations (which guards fired, and were they right)

- **`fundamental_decline_flag` (EMBC)**, fired correctly (§5); the only mechanical growth-veto fire in the run.
- **`wrong_entity_suspected` + `low_revenue_loss_ratio` (STSS)**, **both** fired on STSS's NI/revenue
  ratio of 1,384x ($−282.5M NI on $0.2M revenue). The P-B refinement (changelog) was supposed to move
  real-but-tiny producers off `wrong_entity_suspected` and onto the advisory-only `low_revenue_loss_ratio`
  label. Here STSS *is* a real entity (Sharps Technology, a real near-pre-revenue syringe distributor with
  a large non-cash loss), so the *correct* label is `low_revenue_loss_ratio`, yet `wrong_entity_suspected`
  **also** fired and is the field that actually blocked `buy_eligible`. The downstream outcome was still
  right (WATCH, not a spurious BUY off the +83.6% NAV MoS), but this is a **borderline P-B case worth
  logging**: on an extreme NI/rev anomaly (1,384x) the unit-anomaly guard still classifies a real tiny
  producer as `wrong_entity`. Not a failure, the rating is correct, but the *reason string* a PM reads
  ("wrong entity") is less accurate than the co-fired `low_revenue_loss_ratio` ("early/pre-revenue
  pattern, right entity"). The two labels co-firing is the diagnostic; an analyst should trust the
  `low_revenue_loss_ratio` framing here.
- **`debt_truncation_suspected` (LFCR)**, fired: reported total debt $1.0M vs implied (liab − equity)
  $233.2M, ratio ≈ 0.00. This is a genuine XBRL truncation / tag-coverage problem (LFCR's reported
  `LongTermDebt` member does not capture its full liability stack), and it correctly forced
  `buy_eligible = false` rather than letting a clean-looking $1M-debt balance sheet drive a NAV BUY.
  Correct conservative bite.
- **`material_weakness` (ICFR) fired on AMPH, EMBC, LFCR**, three of five carry `killflag_count ≥ 1`
  and are capped (Dim 1 ≤ 2). EMBC additionally carries the fund-decline veto → effective kill-count 2.
  All three MWs are genuine (each disclosed in the most recent 10-K), not artifacts.
- **`fcf_cap_model_unsuitable` (EMBC)**, `debt_to_assets = 1.29 > 0.62` → the model correctly switched
  EMBC off the FCF-cap path and onto NAV (where its negative tangible equity then drove NAV MoS −100%).
  The over-levered carve-out is exactly the case the FCF-cap suitability guard exists to catch.
- **`ebitda_nonpositive_ev_ebitda_null` (KRMD, LFCR, STSS)**, the EBITDA cascade declined to print a
  multiple for the loss-makers rather than fabricating one. Correct.
- **`debt_stale` (KRMD)** and **`debt_is_total_liabilities_proxy` (STSS)**, disclosure-vintage / proxy
  notes, surfaced not silently swallowed.

**No silent skips. No `deepdive_*_ERROR.json` written** (no crashes / rate-limit kills, the tools'
retry held). All 5 valuations required and received **both** `--json` AND `--ticker`.

---

## 7. Market-intel T2 analyst context (labeled T2, did NOT drive buy_eligible/BUY)

Source: TrendsMCP (Google search normalized 0-100 + volume where available). **Analyst color only.**

| Keyword | 12M growth | trailing 3M growth | read |
|---|---|---|---|
| Ozempic | **−21.1%** (vol −21%) | **−20.0%** | off peak, still the most-searched brand |
| Wegovy | **+93.0%** (vol +93%) | −1.2% (flat) | strong YoY, now plateaued at peak |
| tirzepatide | +100.0% | **−30.8%** | secular up, sharp near-term rollover |
| semaglutide | +5.4% | **−50.6%** | flat YoY, steepest near-term drop |
| "weight loss drug" | +23.3% | −38.3% (6M −54.9%) | up YoY, rolling over hard near-term |

**Interpretation (PHILOSOPHY #2, hot theme = casino).** Every brand/molecule shows the same late-cycle
signature: explosive 12-month interest **already rolling over from its recent attention peak** (every
trailing-3M reading is negative or flat). This is precisely the "recently cooled" regime the brief flags
and the profile under which thematic ETFs historically deliver ~−6% risk-adjusted post-launch. It
**corroborates** the mechanical 0-BUY: the obvious supply-chain names are priced for the boom even as
attention fades, leaving no neglect discount. **This signal informed narrative framing only**, every
rating in §2/§3 was produced by the deterministic MoS / kill-flag / `buy_eligible` layer with the
market-intel feed switched off.

---

## 8. Skeptical-PM verdict (usable)

**Actionable conclusion: nothing to buy today; one name worth a watchlist, the rest are flawed or artifacts.**

- **Pass / no action on all 5.** Zero clear the MoS bar; the eligibility gate vetoes the only name that does
  (STSS, on a data artifact). The obesity-supply-chain theme is fully priced, there is no neglect discount.
- **Watchlist (re-underwrite on a drawdown): AMPH.** Amphastar is the one *real, profitable, defensible*
  picks-and-shovels business in the universe, a vertically-integrated sterile-injectable / prefilled-syringe
  manufacturer with genuine contract-manufacturing capacity and a GLP-1 generic in the pipeline (AMP-018),
  trading at only 5.7x EV/EBITDA with $156M OCF. It is *not* a BUY: reverse-DCF prices in a modest decline
  that its trailing −2% top line corroborates (MoS −38.6%), the insider tape is **net_sell** (26 sells, 0
  buys), and it carries a material weakness. But if the fading-attention regime (§7) drags the multiple down
  another 30 to 40%, the MoS math flips, this is the name to keep on a pullback list.
- **Quality-but-impaired, avoid for now: EMBC.** Embecta is the dominant pen-needle maker ($1.08B revenue,
  $192M OCF, 4.7x EV/EBITDA, optically the cheapest) but it is a **shrinking** mature business (−3.8%) with
  **debt > assets** (negative tangible NAV), it correctly trips *both* the fundamental-decline veto and the
  FCF-cap-unsuitable guard. Cheap on earnings, but a levered melting ice cube; not investable until the top
  line stabilizes and leverage comes down.
- **Story / not yet quality: KRMD** (real +22% subcutaneous-drug-delivery grower, but unprofitable, NAV MoS
  −92%, EV/Sales 4.2x, a growth story priced as one) and **LFCR** (a genuine, differentiated fill-finish
  **CDMO**, the purest theme fit, but loss-making, MW, a known few-customer concentration that the
  magnitude gate couldn't quantify, and XBRL debt-truncation noise; too many data seams to underwrite).
- **Near-shell, avoid: STSS.** $0.2M revenue, $282M non-cash paper loss, negative OCF, syringe *distribution*
  (not manufacturing), the +83.6% NAV MoS is a book-equity-proxy artifact, correctly vetoed to WATCH by the
  eligibility gate. Not a real business yet.

**Process verdict on the skill (iter2).** The run is clean and the new machinery largely behaved as
designed: **(a)** the V-shape / fundamental-decline vetoes were correctly targeted, one true fire on the
real decliner (EMBC) and **zero false positives** on the genuine grower (KRMD) and the profitable mature
name (AMPH), the explicit growth-handling stress objective; **(b)** the `buy_eligible` composite *bit* on
the one MoS-passing name (STSS, +83.6% NAV) and downgraded it to WATCH rather than emitting an artifact
BUY, exactly the iter2 hardening; **(c)** the EBITDA cascade refused to fabricate multiples for
loss-makers; **(d)** no silent skips, no crashes, no `ERROR.json`. **Two rough edges, both worth a future
tool change, neither of which produced a wrong rating here:** (1) the **concentration seam** (§4), the
magnitude-based kill returns null for filers (LFCR) who disclose customer concentration in narrative text
but not in XBRL segment members, so the text flag and the magnitude flag can disagree silently; a
`concentration_unquantified` advisory would close it; and (2) the **STSS reason-string** (§6) ,
`wrong_entity_suspected` co-firing with `low_revenue_loss_ratio` on a real-but-tiny producer gives the PM
a slightly misleading "wrong entity" label even though the *decision* (WATCH) is correct. The 0-BUY output
is the honest, defensible answer for a hot, cooling theme.

---

### Artifacts (all under `reports/smallcap/2026-06-20_glp1-supply-iter2/`)
`RANKING.md` · `deepdive_verdicts.json` · `report_<TICKER>.md` (×5) ·
`deepdive_<TICKER>_2026-06-20.json` (×5) · `valuation_<TICKER>_2026-06-20.json` (×5) ·
`_gate2_themefit.json` (Gate-2 audit, 93 classified) · `_survivors_for_deepdive.json` (5 retained) ·
`_decision_table.json` (extracted decision fields) · `candidates_glp1_supply.json` (post-Gate-2 re-band) ·
`_raw_candidates_glp1_supply_preGate2.json` (pre-Gate-2 raw, 113 rows) · `_deepband_blurbs.tsv` ·
`universe_glp1_supply_2026-06-20.csv` · `cheappass_glp1_supply_2026-06-20.csv` · `run_theme.log`.
