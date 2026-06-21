# Coverage Test — for-profit-education

- **Run batch:** `reports/smallcap/2026-06-21_cov-for-profit-education/`
- **Skill version:** v0.3.0 (commit `f12fef5`)
- **Theme keywords:** `for-profit education, career training, online learning`
- **Sector:** Cross
- **Code-path focus:** regulatory / declining
- **Date:** 2026-06-21 (system clock; `today()=2026-06-21`)
- **recall@gold:** n/a (no gold list registered for this theme)

> **This is research output, not investment advice.** The pipeline is a landmine-scanner.
> Zero BUYs is a valid, informative result.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw FTS recall (universe, ≤ small-cap cap, after mktcap filter) | 114 | `universe_for_profit_education_2026-06-21.csv` (discover printed 114 small-caps into cheap_pass) |
| Candidates after cheap_pass + SIC gate | 88 | cheappass survivors 88 → SIC keep=43, review=45, drop=0 |
| Deep band (mktcap < market_cap_max) | 57 | watch band = 31 (surfaced, not deep-dived) |
| **LLM theme-fit gate (Gate 2) survivors** | **14** | 13 pure_play + 1 partial; 43 deep-band misrecalls dropped |
| Deep-dived (every survivor, no sampling) | 14 | 0 deepdive ERROR files, 0 missing reports |
| Valuated (`--json` + `--ticker`/`--mktcap`) | 14 | AMBO needed `--mktcap 90942873` (yfinance null) |
| **Mechanical BUYs** | **0** | — |

- **No dedicated SIC floor:** education (8200-series) is **not** in `THEME_SIC`, so SIC
  reverse-recall is a clean no-op and discovery ran FTS-only + mktcap fallback. This is correct,
  opt-in behavior (verified in `tools/filter_by_sic.py::theme_sics`).
- The discovery FTS keyword set ("online learning", "career training") over-recalled heavily into
  adjacent verticals (cyber/SaaS/video platforms that mention "learners", banks, crypto ETFs, a
  burger chain). Gate 2 carried the precision load: **43 of 57 deep-band names (75%) were
  misrecalls.** This is the expected over-recall → LLM-precision pattern (SKILL.md cites 6.8%
  precision on "AI agent").

### Gate-2 theme-fit decisions

**Pure-play (13):** APEI, PXED (University of Phoenix), LINC, STRA (Strayer+Capella), COUR
(Coursera), CHGG (Chegg), NRDY (Nerdy/Varsity Tutors), GOTU (Gaotu), DAO (Youdao), AMBO (Ambow),
JDZG (Jiade), SKIL (Skillsoft — corporate L&D), HSTM (HealthStream — healthcare workforce learning).

**Partial (1):** FC (Franklin Covey — leadership/corporate training content; adjacent but core
business is behavior-change training, retained for deep-dive).

**Representative misrecalls dropped:** LEE (newspapers), CNDT (Conduent BPO), OPRT (lending),
RPD (Rapid7 cyber), EVH (Evolent healthcare), WEN (Wendy's), GTY (Getty Realty), JSM/Navient
(student-loan *servicer* — education-finance adjacent, not an education provider), FLYW (Flywire —
education *payments*, not education), DHX (Dice job board), UPWK (Upwork freelance), KLTR (Kaltura
video SaaS), the Bitwise crypto ETFs (CLNK/ETHW/XRP), and a string of banks. Each cleared an FTS
keyword but fails true theme membership.

---

## 2. Ranked shortlist

| # | Ticker | Rating | MoS basis | MoS % | buy_eligible | kill-flags | Read |
|---|--------|--------|-----------|-------|--------------|-----------|------|
| 1 | HSTM | 观察 (watch) | nav | -92.1 | true | 0 | Healthcare-workforce SaaS; quality but rich (P/E 40.8, EV/EBITDA 11.4). NAV path because C1 data-quality guard blocked FCF-cap. |
| 2 | NRDY | 观察 (watch) | fcf_cap | null | true | 0 | Nerdy/Varsity Tutors; FCF negative, no intrinsic band → MoS null. Not investable on a value basis. |
| 3 | PXED | 观察 (watch) | fcf_cap | null | true | 0 | University of Phoenix; XBRL too thin (DA/capex/normalized-FCF all unavailable) → band null. Data gap, not a value call. |
| 4 | STRA | 观察 (watch) | fcf_cap | -35.1 | true | 0 | **Closest to BUY.** Profitable (P/E 13.5, FCF yield 9.0%), zero flags, but priced ~35% above conservative FCF-cap intrinsic. Fairly-to-richly valued. |
| 5 ⬇ | AMBO | 避开 (avoid) | fcf_cap | null | false | 0 | cross_source_mismatch. Cayman micro-holdco, yfinance had no mktcap. |
| 6 ⬇ | APEI | 避开 | fcf_cap | -70.0 | false | 0 | cross_source_mismatch; also deeply overvalued vs intrinsic. |
| 7 ⬇ | CHGG | 避开 | fcf_cap | +578.8 | false | 0 | **The textbook artifact.** Raw MoS looks spectacular; vetoed by extreme-MoS + fundamental_decline + peak_contamination + fcf_sustainability_uncertain. See §3. |
| 8 ⬇ | COUR | 避开 | fcf_cap | -51.0 | false | 0 | fcf_sustainability_uncertain + cross_source_mismatch. |
| 9 ⬇ | DAO | 避开 | abstain | — | false | 0 | cross_source_mismatch; MoS abstained (China VIE, loss-making). |
| 10 ⬇ | FC | 避开 | nav | -100.0 | false | 0 | debt_truncation_suspected. |
| 11 ⬇ | GOTU | 避开 | nav | -65.1 | false | 0 | debt_truncation_suspected + cross_source_mismatch (China VIE). |
| 12 ⬇ | JDZG | 避开 | fcf_cap | null | false | 1 | cross_source_mismatch; ~-99% dilution flag (micro China name). |
| 13 ⬇ | LINC | 避开 | nav | -90.2 | false | 0 | debt_truncation_suspected + cross_source_mismatch. |
| 14 ⬇ | SKIL | 避开 | nav | -100.0 | false | 0 | financial_sic_forced_unsuitable + insurance_concepts_present (DeferredPolicyAcquisitionCosts XBRL tag). See §3. |

**Tiering:** 4 watch (HSTM, NRDY, PXED, STRA) · 10 avoid · **0 buy.**

---

## 3. BUY analysis — honest 0-BUY

**There are zero mechanical BUYs.** No candidate cleared the rule
`mos_basis ∈ {fcf_cap, nav} AND MoS ≥ 30 AND buy_eligible AND zero kill-flags`.

This is the correct answer for this theme today, and the failure modes are instructive — they map
directly onto the **regulatory/declining code-path focus**:

- **The only positive raw MoS belongs to a declining company, and the guards caught it.**
  CHGG shows `margin_of_safety_pct = +578.8%` — at face value an enormous "bargain." It is a pure
  artifact: Chegg's revenue collapsed (rev_slope = -1, latest below trailing average,
  contamination_ratio = 0.085, latest net income = -$103M). The conservative FCF-cap divides a
  market cap that has already de-rated by a trailing-average FCF inflated by peak (pre-AI) years.
  Four independent guards fired to veto it:
  `extreme_mos_review_required` (MoS > 100%), `fundamental_decline_veto`, `peak_contamination_veto`,
  and `fcf_sustainability_uncertain` (reverse-DCF implied growth -80.6%). **`buy_eligible=False`.**
  This is exactly the V-shape / declining-business trap the v0.3.0 guards exist to kill.

- **The genuinely healthy names are simply not cheap.** STRA (the best-quality survivor:
  profitable, 9% FCF yield, P/E 13.5, zero flags) prices ~35% *above* its conservative FCF-cap
  intrinsic band ($1.11–1.43B vs $1.71B cap). HSTM is high-quality but rich (P/E 40.8). APEI sits
  ~70% above intrinsic. The market is **not** mispricing the clean for-profit-education operators;
  they are efficiently-to-richly valued. "Neglected ≠ undervalued" in its purest form.

- **The China VIE cohort is correctly distrusted.** GOTU, DAO, JDZG, AMBO all carry
  `cross_source_mismatch` and/or `debt_truncation_suspected` — the cross-source and debt guards
  flag the unreliable/structurally-opaque financials of Cayman-holdco / VIE filers. None are
  eligible.

- **The SIC/insurance firewall fired correctly on SKIL.** Skillsoft's XBRL contains a
  `DeferredPolicyAcquisitionCosts` concept, tripping `insurance_concepts_present` →
  `financial_sic_forced_unsuitable`, forcing NAV and marking it ineligible. (Mild false-positive
  risk noted in §5 — this is an insurance-vocabulary tag in a non-insurer — but the guard behaved
  as designed and the name was richly valued anyway.)

**Adversarial verification:** Not required — there are no mechanical BUYs to stress-test.
For completeness, the closest-to-BUY name (STRA) was examined adversarially and **confirmed a
genuine non-opportunity, not a data suppression**: its negative MoS comes from a clean,
cross-source-validated valuation (P/E 13.5, EV/EBITDA 7.0, reverse-DCF implied growth 3.3% vs
actual 4.0% — internally consistent). The tool is correctly saying "fairly valued," not erroneously
hiding value.

**n_buy_clean = 0.**

---

## 4. Code-paths exercised

- `discover.py` FTS recall + mktcap filter; **SIC reverse-recall no-op path** (theme has no
  dedicated SIC → FTS-only, the opt-in fallback).
- `cheap_pass.py` mechanical health screen (114 → 88 survivors; Item-1 blurb extraction).
- Inline **SIC tri-state gate** (`sic_classify`): keep=43, review=45, drop=0.
- **Gate 2 LLM theme-fit** (orchestrator judgment from blurbs): 57 deep-band → 14 survivors,
  43 misrecalls resolved (recorded in `candidates_gate2_survivors.json` so finalize counts them
  as resolved-by-gating, not missing).
- `deepdive_data.py` x14 (financials + 10-K/20-F + insider + **firewalled `signals` block**).
- `valuation.py` x14 with the full v0.3.0 guard battery; **`--mktcap` override path** exercised
  on AMBO (yfinance null).
- **Guard paths that actually fired:** `extreme_mos_review_required`, `fundamental_decline_veto`,
  `peak_contamination_veto`, `fcf_sustainability_uncertain`, `cross_source_mismatch`,
  `debt_truncation_suspected`, `financial_sic_forced_unsuitable` + `insurance_concepts_present`,
  `fcf_cap_model_unsuitable → use_nav`, `fcf_cap_blocked_by_c1_data_quality_guard`,
  `intrinsic_band_null` (data-gap abstain).
- `make_report.py` x14 (deterministic pre-fill + data-quality trust banner + firewalled T2
  signals section).
- `finalize_run.py` (completeness assert PASS, 14 verdicts emitted, RANKING rebuilt, trust banner).
- `track_forward.py --recall-gold` → "no gold list for theme — not measurable" (clean no-op).
- **Signals side-channel:** confirmed embedded inside each deepdive JSON (`signals` key) and the
  report's firewalled "T2 DIAGNOSTIC SIGNALS" section, explicitly NOT read by valuation /
  buy_eligible / BUY trigger. Firewall intact.

---

## 5. Data-quality issues

- **AMBO** market cap unavailable from yfinance (`yfinance_returned_null`); resolved with the
  discovery-stage mktcap via `--mktcap`. AMBO is a Cayman micro-holdco — financials are thin and it
  carries `cross_source_mismatch` regardless.
- **PXED (University of Phoenix)** XBRL is severely thin: DA, capex, normalized EBITDA and
  normalized FCF all unavailable → intrinsic band null → MoS null. The single largest US
  for-profit university is effectively un-valuable from its filings here. Ineligible by abstention,
  not by judgment.
- **NRDY** intrinsic band null (normalized FCF non-positive).
- **SKIL** `insurance_concepts_present` is a plausible **false-positive**: the
  `DeferredPolicyAcquisitionCosts` tag in a corporate-learning company likely reflects a legacy or
  mis-mapped XBRL element rather than a real insurance line. The guard is conservative-by-design;
  worth a human override check in a real workflow, though the name was richly valued so the verdict
  (避开) is unaffected.
- **China VIE cohort** (GOTU/DAO/JDZG/AMBO): pervasive `cross_source_mismatch` /
  `debt_truncation_suspected` — structural opacity, correctly distrusted.
- **HSTM** `debt_stale:>18_months_behind_latest_assets` and the C1 guard blocking FCF-cap → forced
  to NAV.
- Several names had `concentration_unquantified` (text flag true but XBRL magnitude null) and
  `debt_is_total_liabilities_proxy` — standard small-cap disclosure gaps, all surfaced in the trust
  banner.

---

## 6. recall@gold

**n/a.** `for-profit-education` is not in `track_forward.THEME_GOLD` (the gold lists are
water-utilities, railcar-leasing, regional-gaming, deathcare). `--recall-gold` returned
"no gold list for theme — not measurable." Recall is therefore not quantifiable for this run; the
funnel above is the only coverage evidence.

---

## 7. Market-intel / T2 context (labeled — does NOT drive any verdict)

- **TrendsMCP enrichment was unavailable** this run (daily + monthly request quota exhausted).
  No Trends time-series could be attached.
- **No cached market-intel report** exists for an education vertical in
  `~/CodesSelf/market-intel/reports/`.
- **Domain T2 read (analyst context only):** the US for-profit postsecondary sector is structurally
  *declining and regulation-shadowed* — enrollment at the legacy degree-granting players (Phoenix,
  Strayer/Capella, APEI) has been flat-to-down for a decade under Title IV / gainful-employment /
  90-10 / borrower-defense regulatory pressure, while the consumer-edtech names (Chegg, Coursera,
  Nerdy) face an AI-driven demand shock (Chegg's collapse is the extreme case). This macro is
  *consistent with* the pipeline's mechanical output — the survivors that are healthy are richly
  priced (no growth thesis to underwrite cheaply), and the optically-cheap one (Chegg) is cheap
  because it is structurally impaired. The "regulatory/declining" code-path focus is well-matched
  to this theme. **This paragraph is context; it influenced no buy_eligible value.**

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** A skeptical PM gets exactly what a scanner should produce on a structurally
challenged theme: a clean **0-BUY** with the reasoning legible at every node.

- The funnel did real work: 114 → 88 → 57 deep-band → 14 true members, with 43 misrecalls
  explicitly resolved (75% of deep-band FTS recall was noise — the LLM gate, not SIC, carried
  precision here because education has no dedicated-SIC floor).
- Every guard that mattered fired and is auditable: the lone "spectacular bargain" (Chegg, +579%
  MoS) was vetoed by four independent decline/contamination guards — the single most important
  thing this tool can do, and it did it.
- The healthy operators (STRA, HSTM) are correctly tagged "fairly-to-richly valued," not falsely
  promoted — "neglected ≠ undervalued" holds.
- Honest gaps are surfaced, not hidden: PXED un-valuable from filings, SKIL's likely insurance-tag
  false-positive, the China-VIE distrust cohort, AMBO's mktcap fallback.

The only caveat a PM should carry forward: this theme has **no recall@gold instrument**, so the
recall *floor* is unmeasured — coverage confidence rests on the FTS+Gate-2 funnel alone. That is a
known limitation of the theme, not a defect of the run.

---

### Artifacts

- `reports/smallcap/2026-06-21_cov-for-profit-education/RANKING.md`
- `reports/smallcap/2026-06-21_cov-for-profit-education/deepdive_verdicts.json` (14 verdicts)
- `report_<T>.md`, `deepdive_<T>_2026-06-21.json`, `valuation_<T>_2026-06-21.json` for all 14 survivors
- `candidates_for_profit_education.json` (88), `candidates_gate2_survivors.json` (14)
