# Coverage Test, Theme: healthcare-services (HealthCare)

- **Run batch:** `2026-06-21_cov-healthcare-services` (`SMALLCAP_RUN`)
- **Skill version:** v0.3.0 @ commit `f12fef5`
- **Theme keywords:** `healthcare services, clinics, physician practice`
- **Code-path focus:** leverage / roll-up debt
- **Date:** 2026-06-21 (run) / coverage-test dossier 2026-06-20
- **recall@gold:** n/a (no gold list for this theme; only water-utilities / railcar-leasing / regional-gaming / deathcare have one)
- **Verdict (headline):** **0 BUYs.** 25 deep-band theme-fit survivors deep-dived, all rated
  观察 (WATCH, 15) or 避开 (AVOID, 10). The pipeline fired every relevant v0.3.0 guard,
  with the leverage/roll-up-debt code-paths heavily exercised. No name cleared the BUY rule.

> Research output, NOT investment advice. This is a landmine-scanner pass: the value is in what it
> eliminated, not in a buy list. A 0-BUY result for a richly-valued, capital-intensive, debt-heavy
> roll-up sector is the expected and correct answer.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw hits (dedup) | 401 | `healthcare services` + `clinics` + `physician practice` UNIONed and deduped |
| Smallcap candidates (≤ cap or unknown band) | 111 | bands: deep 133, unknown 207, watch 21, large 40 (over full 401 universe; 111 flagged smallcap_candidate for cheap-pass) |
| Cheap-passed (kill-flag scan) | 111 attempted → **73 survivors** | 38 eliminated by kill-flag/health screen |
| SIC gate (Gate 1, tri-state) | 73 → 73 | keep=15, review=58, `sic_classify` returns no `drop` in this config, so SIC is a keep/review tag, not a precision exclude here |
| **Candidates JSON** | **73** | 55 deep-band + 18 watch-band |
| **LLM theme-fit (Gate 2, my judgment)** | **25 deep-dived** | of 55 deep-band: 25 true theme members kept, 30 misrecall dropped |
| Deep-dive + valuation | 25 / 25 | zero `deepdive_*_ERROR.json` crashes; zero valuation failures |
| **Mechanical BUYs** | **0** | every survivor fails the BUY rule |

**Funnel object:** raw=401, deepdived=25, survivors=25 (15 WATCH + 10 AVOID, 0 BUY).

### Critical structural finding, the SIC config quirk for this theme

The repo `sic_hard_exclude` list contains the entire health-services 8000 block
(`8000, 8011, 8060, 8062, 8071, 8090, 805, 806, 807, 80`). On a railcar/water theme these
exist to *exclude* off-theme noise. For a **healthcare-services** theme these codes ARE the
theme's core SIC codes (8000 health services, 8011 physician offices, 8060/8062 hospitals,
8071 medical labs, 8082 home health, 8090 allied health). Had Gate 1 actually dropped on
`hard_exclude`, it would have nuked the true pure-plays (USPH, PNTG, ARDT, AVAH, MD, ASTH,
INNV, …) and retained only off-theme survivors (BDCs, REITs, pharma). It did **not**, because
`sic_classify()` is tri-state and never returns `drop` in the shipped config, it only tags
keep/review and hands everything to the LLM Gate 2. So the recall floor was saved by the LLM
gate, not the SIC machinery. **This is a latent landmine:** if a future config wired
`hard_exclude` to a hard drop, this theme would silently lose its entire true cohort. Recorded
as a data-quality issue.

### Gate 2 (LLM theme-fit) decisions, judged from 10-K business blurb

**Kept (25 true members, care delivery / clinics / physician practice / staffing / home-health / DSO):**

| Ticker | Company | SIC | Class | Basis |
|---|---|---|---|---|
| USPH | U.S. Physical Therapy | 8000 | pure_play | PT-clinic operator/roll-up |
| PNTG | Pennant Group | 8000 | pure_play | Home health / hospice / senior living operator |
| INNV | InnovAge | 8000 | pure_play | PACE capitated senior care delivery |
| ARDT | Ardent Health | 8062 | pure_play | Hospital / health-system operator (levered) |
| AVAH | Aveanna Healthcare | 8082 | pure_play | Home health / private-duty nursing (levered) |
| CYH | Community Health Systems | 8062 | pure_play | Hospital operator (heavily levered roll-up) |
| MD | Pediatrix Medical Group | 8060 | pure_play | Physician-services / practice management |
| ASTH | Astrana Health | 8742 | pure_play | Physician-centric risk-bearing care delivery |
| HCSG | Healthcare Services Group | 8050 | pure_play | Facility / clinical services to providers |
| CCRN | Cross Country Healthcare | 7363 | pure_play | Healthcare staffing / workforce |
| AMN | AMN Healthcare | 7363 | pure_play | Healthcare staffing / workforce |
| PARK | Park Dental Partners | 8090 | pure_play | Dental DRO/DSO roll-up (clinics) |
| JYNT | Joint Corp | 6794 | pure_play | Franchisor/operator chiropractic clinics |
| SBC | SBC Medical Group | 8011 | pure_play | Aesthetic medical clinic management |
| SRTA | Strata Critical Medical | 8000 | partial | Time-critical medical logistics/services |
| VMD | Viemed Healthcare | 8090 | partial | Home medical equipment + post-acute services |
| AHCO | AdaptHealth | 8082 | partial | Home medical equipment / healthcare-at-home |
| INFU | InfuSystem | 3841 | partial | Infusion-pump services to providers |
| LFMD | LifeMD | 8011 | partial | Direct-to-patient virtual care + pharmacy |
| TDOC | Teladoc | 8011 | partial | Virtual care delivery |
| TALK | Talkspace | 8000 | partial | Virtual behavioral-health delivery |
| BMGL | Basel Medical Group | 8011 | partial | Singapore medical-services micro-cap |
| RYOJ | rYojbaba | 8742 | partial | Japanese seikotsuin (clinic) operator |
| NEO | NeoGenomics | 8734 | partial | Cancer lab-testing services |
| BTMD | biote | 2833 | partial | HRT clinic-affiliated practitioner network |

**Dropped (30 misrecall), keyword over-recall into adjacent sectors:**
REITs (STRW, MDV, NLCP, CHCT, UHT, landlords, not operators); BDCs/finance (TPVG, HRZN,
KFS, FDUS, MSDL, JSM/Navient); pharma/biopharma (AMRN, AVBP); medical-device makers (STIM,
FONR, KRMD, KIDS, ATRC); healthcare-IT/SaaS (HCAT, CCTC, PHR, TBRG, NRC); insurance dist.
(SLQT); cannabis (TLRY); 3D printing (DDD); industrials (TRS); BPO (CNXC); career education
(LINC).

The canonical "refractory swept all of biotech" over-recall appears here as the HealthCare
neighbour-sweep: a healthcare-services keyword pulls in REITs that *own* hospitals, BDCs that
*lend* to providers, devices *used* by clinics, and IT that *bills* for clinics. Gate 2 removed
all of them. This is precisely the precision work the SIC gate could not do (the relevant SIC
codes split true operators and adjacents indistinguishably).

---

## 2. Ranked shortlist (all non-BUY)

| Rank | Ticker | Rating | Conf | mos_basis | MoS / NAV-MoS | buy_eligible | Hard kill | Why not BUY |
|---|---|---|---|---|---|---|---|---|
| 1 | AHCO | 观察 | 60% | fcf_cap | −156% | false | none | Extreme-negative MoS; `extreme_mos_review_required` |
| 2 | ARDT | 观察 | 60% | fcf_cap | +168% | **false** | none | High raw MoS is a value-trap artifact → gated by `extreme_mos_review_required` + `fcf_sustainability_uncertain` (hospital, $1.1B debt, lumpy FCF) |
| 3 | AVAH | 观察 | 60% | nav | −100% | true | none | Negative tangible equity (goodwill-heavy levered home-health roll-up); EV/EBITDA 10.5x |
| 4 | CYH | 观察 | 60% | nav | −100% | true | none | $10.1B debt, negative NAV; classic over-levered hospital roll-up |
| 5 | HCSG | 观察 | 60% | fcf_cap | −68% | true | none | Negative FCF MoS; no margin of safety |
| 6 | INFU | 观察 | 60% | fcf_cap | −5% | true | none | Slightly negative MoS, well short of 30% |
| 7 | INNV | 观察 | 60% | fcf_cap | null | true | none | No numeric MoS (normalized FCF ≤0 → abstain band) |
| 8 | MD | 观察 | 60% | nav | −100% | false | none | `cross_source_mismatch` (SEC vs yf debt/shares); negative NAV |
| 9 | NEO | 观察 | 60% | fcf_cap | null | true | none | No numeric MoS (negative normalized FCF) |
| 10 | PARK | 观察 | 60% | nav | −92% | false | none | `debt_truncation_suspected` + `cross_source_mismatch`; near-zero reported financials (recent SPAC/shell-stage DSO) |
| 11 | PNTG | 观察 | 60% | fcf_cap | −92% | false | none | `cross_source_mismatch`; richly valued home-health/hospice |
| 12 | TALK | 观察 | 60% | nav | −90% | true | none | Negative NAV MoS; cash-rich but no asset backing for the price |
| 13 | TDOC | 观察 | 60% | nav | −100% | false | none | `debt_truncation_suspected`; negative NAV; persistent GAAP losses |
| 14 | USPH | 观察 | 60% | fcf_cap | −55% | false | none | `fcf_sustainability_uncertain` (capital-intensive PT roll-up); MoS deeply negative |
| 15 | VMD | 观察 | 60% | fcf_cap | −84% | true | none | Negative FCF MoS; richly priced HME operator |
| 16 ⬇ | AMN | 避开 | 70% | nav | −100% | false | fundamental_decline | `debt_truncation_suspected` + `fundamental_decline_flag` + `peak_contamination_flag` (post-COVID staffing rollover) |
| 17 ⬇ | ASTH | 避开 | 70% | nav | −100% | false | material_weakness | `financial_sic_forced_unsuitable` + `insurance_concepts_present` (risk-bearing capitated entity routed to insurance path) |
| 18 ⬇ | BMGL | 避开 | 70% | fcf_cap | null | true | material_weakness | Micro-cap, near-zero financials, ICFR material weakness |
| 19 ⬇ | BTMD | 避开 | 70% | nav | −100% | true | material_weakness | Negative NAV; ICFR material weakness |
| 20 ⬇ | CCRN | 避开 | 70% | nav | −58% | false | fundamental_decline | `financial_sic_forced_unsuitable` + `insurance_concepts_present` + `fundamental_decline_flag` + `peak_contamination_flag` + `cross_source_mismatch` (5 guards) |
| 21 ⬇ | JYNT | 避开 | 70% | nav | −93% | false | material_weakness | `financial_sic_forced_unsuitable` + `debt_truncation_suspected` + `cross_source_mismatch` (franchise gross-vs-net rev: SEC $15.2M vs yf $56.6M) |
| 22 ⬇ | LFMD | 避开 | 70% | nav | −99% | true | material_weakness | Negative NAV; ICFR material weakness |
| 23 ⬇ | RYOJ | 避开 | 70% | fcf_cap | −75% | true | material_weakness | Foreign micro-cap; material weakness; revenue declining |
| 24 ⬇ | SBC | 避开 | 70% | fcf_cap | +2% | true | material_weakness | MoS ~2% (far below 30) + ICFR material weakness |
| 25 ⬇ | SRTA | 避开 | 70% | nav | −76% | true | material_weakness | Negative OCF; ICFR material weakness; recently de-SPAC'd (ex-Blade) |

mos_basis distribution across survivors: **fcf_cap 12, nav 13, abstain 0.**

---

## 3. BUY analysis, none

**Zero names cleared the mechanical BUY rule** (mos_basis∈{fcf_cap,nav} AND numeric MoS≥30 AND
buy_eligible==true AND zero kill-flags). The failure modes split cleanly:

1. **No margin of safety (the dominant cause).** 22 of 25 carry negative or near-zero MoS.
   This sector trades at full prices: hospital/home-health/staffing roll-ups are priced for
   their growth-by-acquisition stories, leaving no discount to filing-derived intrinsic value.
   Neglect ≠ undervaluation, exactly as the world-view predicts.

2. **The one apparent exception is a value-trap artifact, ARDT.** Ardent showed a fat
   fcf_cap MoS of **+168%**, which would superficially scream BUY. v0.3.0 caught it: a
   hospital operator carrying ~$1.1B debt with lumpy/thin trailing FCF produces an unstable
   normalized-FCF denominator → `extreme_mos_review_required` (>100% MoS defense-in-depth) AND
   `fcf_sustainability_uncertain` both fired, setting `buy_eligible=false`. This is the
   single most important code-path result of the run: the leverage/roll-up-debt focus is
   exactly where a naive reverse-DCF over-states intrinsic value, and the guard stack vetoed it.

3. **Leverage / roll-up-debt code-paths fired broadly** (the requested focus):
   - `debt_truncation_suspected`: AMN, JYNT, PARK, TDOC (4), NAV debt read as $0 or truncated
     on goodwill/intangible-heavy levered balance sheets.
   - `cross_source_mismatch`: CCRN, JYNT, MD, PARK, PNTG (5), SEC-XBRL vs yfinance >2.5×
     disagreement on debt/shares/revenue (franchise net-vs-gross, recent SPAC restatements).
   - NAV routing (13 names), asset/debt-heavy operators correctly routed off the FCF path.
   - `fcf_sustainability_uncertain`: ARDT, USPH, (HCSG advisory), capital-intensive operators.
   - `financial_sic_forced_unsuitable` + `insurance_concepts_present`: ASTH, CCRN, JYNT, the
     risk-bearing/capitated and franchise-finance entities correctly pushed to NAV/abstain and
     gated.

**Adversarial verification:** not applicable to any mechanical BUY (there were none). The one
name that *looked* like an opportunity (ARDT) was adversarially examined above and is judged a
**data/model artifact** of a thin-FCF, high-debt hospital roll-up, the guard veto is correct,
not a false negative. Its EV/EBITDA of 4.0× is cheap-ish on a multiples basis but that is a
WATCH thesis for a human, not a filing-derived MoS BUY.

---

## 4. Code-paths exercised

- SIC reverse-recall floor: present in pipeline but **no dedicated SIC floor for this theme** ,
  the 8000-block is in `hard_exclude`, and `sic_classify` tri-state keep/review (no drop).
- Mktcap fallback chain (SEC shares×price when yfinance null) + four-band tagging (deep 133 /
  unknown 207 / watch 21 / large 40).
- cheap_pass kill-flag scan (38 eliminated of 111).
- LLM theme-fit Gate 2 (55 deep → 25 kept / 30 misrecall).
- deepdive XBRL pull with EBIT cascade, debt/shares fallbacks (25/25, 0 crashes).
- Second-source cross-check (P7): fired on 5 names → blocked BUY.
- valuation: reverse-DCF, EV/EBITDA, cyclical-trough, NAV path; mos_basis three-way routing.
- buy_eligible guard composite: `extreme_mos_review_required`, `fcf_sustainability_uncertain`,
  `financial_sic_forced_unsuitable`, `insurance_concepts_present`, `debt_truncation_suspected`,
  `cross_source_mismatch`, `fundamental_decline_flag`, `peak_contamination_flag` all fired.
- finalize_run: 25 verdicts emitted, RANKING.md rebuilt, completeness check (55 deep, 25
  reports, 30 gate2-resolved, 0 missing).
- signals.py T2 side-channel emitted (diagnostic-only, firewalled, did not touch buy_eligible).

---

## 5. Data-quality issues

1. **SIC `hard_exclude` collision (latent landmine).** The 8000-series codes that *define* this
   theme sit in the exclude list. Only the tri-state `sic_classify` (no-drop) prevented a
   total recall wipeout. Any future change wiring `hard_exclude` to a hard Gate-1 drop would
   silently delete the entire true cohort for healthcare-services. Recommend a per-theme SIC
   allow-list / recall-floor for HealthCare-services themes.
2. **No recall@gold gold list** for healthcare-services → recall floor is unmeasured; the
   funnel relies entirely on the LLM Gate 2 for precision and on FTS+mktcap-fallback for recall.
3. **Cross-source debt/share/revenue mismatches** on 5 names (recent SPACs/franchise net-vs-gross)
, correctly blocked BUY but flag stale/ambiguous market data.
4. **Near-zero / shell-stage financials** for recently de-SPAC'd or micro names (PARK, BMGL,
   SRTA, SBC) make filing-derived valuation unreliable; all landed non-BUY anyway.
5. **TrendsMCP / market-intel T2 enrichment unavailable this run**, TrendsMCP daily+monthly
   quota exhausted; no pre-existing market-intel healthcare report. Sector context below is
   analyst knowledge, clearly labeled, and does not (and cannot) drive buy_eligible.

---

## 6. Market-intel / T2 analyst context (labeled, NEVER drives buy_eligible)

- Healthcare-services small/mid-caps are structurally a **roll-up sector**: hospital systems
  (CYH, ARDT), home health/hospice (PNTG, AVAH, AHCO), PT/dental/chiro clinic chains (USPH,
  PARK, JYNT) and physician-practice management (MD, ASTH) all grow by debt-funded acquisition.
  This is why the leverage/NAV/FCF-sustainability guard cluster dominated the run, it is the
  defining financial risk of the cohort.
- Post-COVID, the **staffing names (AMN, CCRN) are in a fundamental down-cycle** (bill-rate
  normalization off 2021 to 22 peaks), the pipeline independently flagged both with
  `fundamental_decline` + `peak_contamination`, matching the well-known narrative without
  needing it as an input.
- Reimbursement/policy overhang (Medicare Advantage rate pressure on capitated risk-bearers
  like ASTH/INNV; site-of-care shifts) is a live qualitative risk a human should weigh, but it
  is a WATCH-list reason, not a filing-derived MoS, and the tool correctly does not price it.

---

## 7. Skeptical-PM usable verdict

**Usable: YES.** For a hot, fully-priced, debt-heavy roll-up sector the disciplined answer is
"nothing clears the bar," and the tool delivered exactly that with the *right* guards firing for
the *right* reasons, most importantly, it refused the one superficially-cheap name (ARDT,
+168% MoS) because the high MoS was an artifact of thin FCF over a heavily levered hospital
balance sheet. Recall was preserved (25 genuine operators surfaced) and precision was clean (30
adjacent REIT/BDC/device/IT/pharma misrecalls removed). The single actionable defect is the
config landmine in §5.1, which did not bite this run only because of the tri-state SIC behaviour.

**0-BUY is the honest, correct output.** A PM would use this as a vetted WATCH list (top of which
is ARDT on a multiples-cheap-but-FCF-fragile thesis, plus CYH/USPH/PNTG as quality operators to
revisit on a price pullback) and would not have been handed a single data-artifact BUY.
