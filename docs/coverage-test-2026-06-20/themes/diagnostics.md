# Coverage Test — Theme: diagnostics (HealthCare)

- **Run batch:** `2026-06-21_cov-diagnostics` (`SMALLCAP_RUN`)
- **Skill version:** v0.3.0 @ commit `f12fef5`
- **Theme keywords:** `diagnostics, clinical testing, molecular`
- **Code-path focus:** growth / reimbursement
- **Date:** 2026-06-21 (run) / coverage-test dossier 2026-06-20
- **Verdict (headline):** **0 BUYs.** 7 deep-band survivors, all rated 观察 (WATCH). The
  pipeline correctly fired every relevant v0.3.0 guard; no name cleared the BUY rule.

> Research output, NOT investment advice. This is a landmine-scanner pass: the value is in what it
> eliminated, not in a buy list.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw hits (dedup) | 598 | `diagnostics` 175 + `clinical testing` 302 + `molecular` 297 → 598 dedup |
| Mktcap-resolved | 20 / 598 | yfinance mktcap; several delisted/no-data (AXDX, HOLX, AKYA, NANX, QIPT, SRDX) |
| Deep band (< $2.0B) | 23 | + 1 watch band ($2–5B: RCUS) |
| Cheap-passed (kill-flag scan) | 20 attempted → 11 survivors | 9 eliminated (kill-flag ≥3 or near-zero cash): APM, VNRX (kf3); BJDX, CDIO, PAVM, LUCD, CODX (kf2); VRAX, IMDX (kf1+cash) |
| SIC gate (Gate 1) | 11 → 11 | keep=2, review=9 → all to LLM Gate 2 |
| **Candidates JSON** | **11** | 10 deep-band + 1 watch (RCUS) |
| **LLM theme-fit (Gate 2)** | **7 deep-dived** | dropped 4 misrecall/watch: NCSM, TNDM, ALLO, RCUS |
| Deep-dive + valuation | 7 / 7 | zero `_ERROR.json` crashes |
| **Mechanical BUYs** | **0** | every survivor fails the BUY rule |

**Funnel object:** raw=598, deepdived=7, survivors=7 (all WATCH, 0 BUY).

### Gate 2 (LLM theme-fit) decisions — judged from business profile

| Ticker | Company | SIC | Class | Reason |
|---|---|---|---|---|
| QDEL | QuidelOrtho | 2835 | pure_play | In-vitro / molecular diagnostics (Sofia, Savanna) |
| NEO | NeoGenomics | 8734 | pure_play | Cancer molecular & clinical testing labs |
| QTRX | Quanterix | 3826 | pure_play | Simoa ultrasensitive biomarker detection dx |
| OSUR | OraSure | 3841 | pure_play | Specimen-collection + molecular/POC dx |
| OPK | OPKO Health | 2834 | partial | Owns BioReference clinical-lab dx + pharma |
| ZOMDF | Zomedica | 2834 | partial | Veterinary point-of-care dx (TRUFORMA) + devices |
| ALLR | Allarity | 2834 | partial | Oncology drug-rescue + DRP companion-dx lab services |
| NCSM | NCS Multistage | 1389 | **misrecall** | Oil/gas field completion tech — "multistage" false-positive |
| TNDM | Tandem Diabetes | 3841 | **misrecall** | Insulin-pump therapy device, not diagnostics |
| ALLO | Allogene | 2836 | **misrecall** | Allogeneic CAR-T cell therapy (therapeutics) |
| RCUS | Arcus Biosciences | 2834 | **misrecall** (watch-band) | Immuno-oncology therapeutics; also skipped by band guard |

The canonical "refractory swept all of biotech" failure mode showed up here in miniature: this is a
HealthCare theme, so the keyword over-recall sweeps adjacent therapeutics (ALLO, RCUS, partially
ALLR) and a hard false-positive from another sector entirely (NCSM, oilfield). Gate 2 caught all of
them. NCSM is the clean cautionary case — SIC 1389 with "multistage" keyword.

---

## 2. Ranked shortlist (all WATCH)

| Rank | Ticker | Rating | Conf | mos_basis | MoS / NAV-MoS | buy_eligible | Hard kill | Why not BUY |
|---|---|---|---|---|---|---|---|---|
| 1 | NEO | 观察 | 45% | fcf_cap | null | true | none | No numeric MoS (normalized FCF ≤0 → abstain band); EV/EBITDA 138x |
| 2 | OSUR | 观察 | 40% | nav | −31.3% | true | MW | NAV MoS deeply negative; post-COVID revenue rolloff |
| 3 | ZOMDF | 观察 | 40% | nav | −22.6% | true | none | NAV MoS −22.6% (< 30); FY loss −$82M |
| 4 | OPK | 观察 | 35% | fcf_cap | null | **false** | none | `cross_source_mismatch` (debt 112x, revenue 3.9x) |
| 5 | QDEL | 观察 | 35% | fcf_cap | +0.9% | **false** | none | `peak_contamination_flag` + `cross_source_mismatch`; MoS 0.9% anyway |
| 6 | QTRX | 观察 | 35% | nav | −26.7% | **false** | MW | `cross_source_mismatch` (debt 17.7x); NAV MoS negative |
| 7 | ALLR | 观察 | 25% | nav | −75.7% | **false** | MW | 4 gates incl. extreme-loss + insurance-false-positive; NAV MoS −76% |

`mos_basis` distribution: **fcf_cap = 3** (QDEL, OPK, NEO); **nav = 4** (ZOMDF, QTRX, OSUR, ALLR);
**abstain = 0**.

---

## 3. BUY analysis — honest 0-BUY

**No candidate satisfied the BUY rule** (`mos_basis ∈ {fcf_cap,nav}` AND numeric MoS ≥ 30 AND
`buy_eligible == true` AND zero hard kill-flags). Two distinct reasons, neither a model failure:

**Group A — eligible but no margin of safety (NEO, OSUR, ZOMDF).** These passed every v0.3.0 guard
(`buy_eligible == true`, cross-source clean) but the valuation simply does not support a buy:
- **NEO** — fcf_cap basis but normalized FCF ≤ 0, so MoS is `null` (abstain band). EV/EBITDA 138x,
  EV/Sales 2.3x — richly priced for a still-loss-making molecular lab. Correct WATCH.
- **OSUR** — NAV MoS −31.3%. `rev_slope_sign = −1` (−38% revenue, the post-COVID specimen-collection
  rolloff). `fundamental_decline_flag` correctly did NOT fire (contamination_ratio = −6.56, a
  degenerate/negative base → A1 lower-bound guard suppresses the veto), so the WATCH comes from MoS,
  not a spurious veto. Carries a material weakness.
- **ZOMDF** — NAV MoS −22.6%. Real growing vet-dx revenue (+17%) but still −$82M FY loss; the asset
  base does not back a 30% NAV discount at the current $75M cap.

**Group B — gated out by `buy_eligible == false` (OPK, QDEL, QTRX, ALLR).** Every one is blocked by
the **P7 second-source sanity band** (`cross_source_mismatch`), plus QDEL's V-shape veto and ALLR's
stack of three more gates. These are the guards earning their keep:
- **QDEL** — would-be eligible (MoS +0.9%, but that is sub-30 anyway). Blocked by `peak_contamination_flag`
  (V-shape: contamination_ratio 0.244, latest_below_avg, latest NI −$1.13B) AND
  `cross_source_mismatch` (SEC debt $228M vs yfinance $2.83B, 12.4x). The firewalled P16 signal flags
  `unpriced_improvement` — and it was correctly IGNORED (see §6 firewall).
- **OPK** — `cross_source_mismatch` on BOTH debt (SEC $3.5M vs yf $397M, 112x) and revenue
  (SEC $149M vs yf $581M, 3.9x). Classic sub-entity-vs-consolidated XBRL tag confusion — exactly the
  HCI/AL pattern P7 was built to catch. A corrupted single-source input cannot back a tradeable MoS.
- **QTRX** — `cross_source_mismatch` on debt (SEC $2.0M vs yf $35.3M, 17.7x) + NAV MoS −26.7% +
  material weakness.
- **ALLR** — the heaviest block: `financial_sic_forced_unsuitable` + `insurance_concepts_present` +
  `low_revenue_loss_ratio_extreme` (|NI|/rev > 20, near-zero revenue) + `cross_source_mismatch`. NAV
  MoS −75.7%. WATCH/avoid-leaning.

**Adversarial verdict (overall):** with 0 mechanical BUYs there is no BUY to attack. The relevant
adversarial question is inverted — *did any guard wrongly create a WATCH that should have been a BUY?*
The only candidate with any positive MoS was QDEL (+0.9%, immaterial). No name had MoS ≥ 30 before
the guards bit, so no real opportunity was suppressed by a guard. The 0-BUY is an honest reflection
of a hot, fully-priced HealthCare theme, consistent with the World-View prior ("hot themes are the
casino"). Adversarial verdict: **0-BUY is real, not a data artifact suppressing a true opportunity.**

---

## 4. Code-paths exercised (the point of this coverage test)

Focus was growth / reimbursement; the guards that actually fired:

1. **SIC reverse-recall + Gate 1** — `filter_by_sic.py` ran (11→11, keep=2/review=9). Diagnostics has
   no single dedicated SIC floor wired into THEME_GOLD, so this was precision-exclude only.
2. **Gate 2 LLM theme-fit** — dropped 4 (NCSM oilfield, TNDM pump, ALLO CAR-T, RCUS IO) → resolved in
   `gate2_results.json`, recognized by `finalize_run` (0 missing).
3. **`peak_contamination_flag` (P-A V-shape veto)** — fired on **QDEL** (cr 0.244 < 0.8,
   latest_below_avg, latest NI < 0; independent of rev_slope_sign). Forced `buy_eligible=false`.
4. **A1 degenerate-base guard** — on **OSUR** (cr −6.56) and **NEO** (cr −0.317) the negative base
   correctly SUPPRESSED both vetoes (no spurious WATCH-by-veto); WATCH there comes from MoS only.
5. **`cross_source_mismatch` (P7 second-source sanity band)** — fired on **4 of 7** survivors (OPK,
   QDEL, QTRX, ALLR). The single most active guard this run. All four are debt or revenue tag
   mismatches > 2.5x vs yfinance.
6. **`insurance_concepts_present` (A3)** — fired on **ALLR** — a **FALSE POSITIVE** (see §5).
7. **`low_revenue_loss_ratio` tiering (P-B / A4)** — advisory on **ZOMDF** (ratio > 2, non-extreme);
   extreme+gating on **ALLR** (|NI|/rev > 20).
8. **`financial_sic_forced_unsuitable`** — fired on **ALLR** (routed financial-style).
9. **material_weakness hard-ceiling** — present on **QTRX, OSUR, ALLR** (Dim 1 capped ≤ 2; not an
   eliminate-flag, so they were deep-dived, not killed at cheap_pass).
10. **Firewalled diagnostic signals (P16/P17)** — emitted as a sibling `signals` key on all 7;
    `valuation.py` reads NONE of them (verified by grep — only contrast comments). See §6.
11. **abstain band** — NEO's null MoS routed to abstain ranking (EV/Sales + EV/EBITDA only).

Code-paths NOT exercised this run: NAV path producing a positive ≥30 MoS; `fundamental_decline_flag`
(rev_slope_sign<0 path — OPK and OSUR had slope −1 but contamination conditions not met / base
degenerate); `concentration_flag == "kill"`; `debt_truncation_suspected`; `wrong_entity_suspected`;
`large_cap_out_of_scope` (RCUS handled at band stage, not valuation).

---

## 5. Data-quality issues

1. **ALLR `insurance_concepts_present` = TRUE is a false positive.** Allarity is a clinical-stage
   oncology biotech with a companion-diagnostic (DRP) lab-services business — it has no insurance
   operations. The XBRL insurance-concept detector (PremiumsEarned / loss-reserve concepts) likely
   matched an oncology "LossesAnd…"-style or reserve-like tag. **Outcome unaffected** (ALLR fails on
   3 other gates + NAV MoS −76%), but this is a precision bug in the A3 detector that could
   mis-route a legitimate non-insurance holdco. Worth a targeted unit test.
2. **Pervasive `cross_source_mismatch` (4/7).** SEC-XBRL vs yfinance disagree > 2.5x on debt for
   QDEL/QTRX/ALLR and on debt+revenue for OPK. For OPK the SEC $149M vs yf $581M revenue split is the
   sub-entity-vs-consolidated pattern; these are genuine input-integrity flags, doing their job, but
   they also mean the SEC numbers behind several names are not trustworthy enough to value — a
   coverage gap on the *input* side, not the model.
3. **`killflag_count` under-counts material weakness.** RANKING shows kill-flag 0 for QDEL while the
   report contract's `killflag_count` field reads 0 for QTRX/OSUR/ALLR even though
   `has_material_weakness = True`. The MW shows in the cheap_pass column (1) and in `tenk.*`, but the
   contract's `killflag_count` appears to count only the hard-elimination set. Minor reporting
   inconsistency; does not change ratings.
4. **Mktcap resolution thin** — only 20/598 FTS hits got a yfinance mktcap (many micro/delisted).
   Deep band may under-enumerate truly tiny names that failed price lookup. Recall risk at the very
   bottom of the cap range.
5. **No blurbs in candidates JSON** — Gate 2 had to be run from analyst knowledge of each company
   rather than a stored 10-K business description; two ambiguous names (ALLR, ZOMDF) were
   web-verified before classification.

---

## 6. Firewall verification (signals must NOT drive BUY)

`grep "signals" tools/valuation.py` returns only two **comment** lines that explicitly contrast the
P7 cross-source gate against the firewalled signals — **no code reads any `signals.*` field.** The
cleanest demonstration this run: **QDEL** carries P16 `divergence_label = unpriced_improvement`
(price −53% 6m / −52% 12m while fundamentals improving) — exactly the kind of bullish diffusion
signal a naive model would chase — yet QDEL is correctly WATCH (peak_contamination + cross_source).
The signal did not, and structurally cannot, originate or up-weight a BUY. **Firewall holds.**

T2 signal snapshot (context only): QDEL & QTRX `unpriced_improvement`; OPK & OSUR
`melting_ice_cube_priced`; NEO, ZOMDF, ALLR `aligned`. No 13D/13G in last ~12mo for any; short
interest unavailable (FINRA bi-monthly, not pulled).

---

## 7. recall@gold

**n/a.** "diagnostics" is not in `THEME_GOLD` (only water-utilities / railcar-leasing /
regional-gaming / deathcare-funeral-cemetery have gold lists). `track_forward --recall-gold --theme
diagnostics` returns "no gold list for theme 'diagnostics' → not measurable". No discovery-floor
measurement available for this theme.

---

## 8. Market-intel / T2 analyst context

- **TrendsMCP:** quota exhausted for the day/month (5/5 daily, 100/100 monthly) — could not pull
  search-volume growth for "molecular diagnostics". Noted as a data gap, not a blocker; it would only
  be T2 corroboration and may never drive `buy_eligible`.
- **market-intel skill present** at `~/CodesSelf/market-intel` (catalog reuse available)
  but not invoked — with 0 BUYs there is no thesis requiring competitive-pricing / X-sentiment
  enrichment. The firewalled P16 price-divergence signals already supply the relevant T2 read.
- **Sector read (qualitative, T2):** the diagnostics small-cap cohort here is dominated by
  post-COVID normalizers (OSUR specimen collection −38%, QDEL respiratory rolling off a −$1.1B loss
  year) and still-unprofitable platform stories (NEO, QTRX). This matches the World-View prior that a
  branded/hot HealthCare theme has its alpha captured — the survivors are either fully priced (NEO at
  138x EV/EBITDA) or value-traps in revenue decline. Consistent with 0 BUY.

---

## 9. Skeptical-PM usable verdict

**Usable: YES.** A skeptical PM gets exactly what this skill is supposed to deliver: a clean
landmine-scan that (a) enumerated ~600 FTS hits down to 7 genuine small-cap diagnostics names, (b)
killed the oilfield/CAR-T/insulin-pump false positives at Gate 2, (c) refused to hand over a single
BUY because none has a real margin of safety, and (d) demonstrably did not let a tempting
"unpriced_improvement" signal (QDEL) override the discipline. The one bug surfaced
(`insurance_concepts_present` false-positive on ALLR) is cosmetic for this run. The honest 0-BUY,
the active P7 cross-source gate (4/7), and the correctly-suppressed A1 degenerate-base vetoes are all
signs the v0.3.0 guards are biting as designed. A PM would shelve all 7 to WATCH and move on — which
is the correct action.

---

### Artifacts (absolute paths)
- Run dir: `C:\Users\<username>\CodesSelf\small-cap-deepdive\reports\smallcap\2026-06-21_cov-diagnostics\`
- RANKING: `…\RANKING.md`
- Verdicts: `…\deepdive_verdicts.json` (7) + appended to `metrics\verdicts.jsonl`
- Per-name: `report_{QDEL,OPK,NEO,ZOMDF,QTRX,OSUR,ALLR}.md`, `deepdive_<t>_2026-06-21.json`,
  `valuation_<t>_2026-06-21.json`
- Gate 2: `gate2_results.json`
