# Theme Deep-Dive, Royalty / Streaming / Mineral Rights / Music Royalties

**Run:** `2026-06-20_royalty-streaming` · skill commit `e0f0039` · iteration-1 test
**Theme keywords:** `royalty, streaming, mineral rights, music royalties`
**Entry:** `theme` (thematic universe screen)
**Output is a landmine-scanner + research shortlist, NOT a buy list.**

This run was designed to stress-test **tricky valuation** (royalty/streaming have unusual cash-flow
shapes), **abstain discipline**, and whether the model **over-abstains on legitimately analyzable
names**. The verdict: it does NOT over-abstain (it found and BUY-rated a genuinely analyzable name,
INVA), it abstains correctly on structurally unmodelable trusts, and it surfaced one
**mechanical-vs-judgment value-trap (NRP)** that the deterministic gate would have passed.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---:|---|
| EDGAR FTS raw recall | 694 | broad keyword recall (`royalty/streaming/mineral rights/music royalties`) |
| Small-cap candidates (mktcap band) | 114 | 530 `unknown`-band (no tradeable US mktcap: delisted/foreign shells) + 22 `large` dropped by discover.py |
| cheap_pass survivors | 66 | 48 killed (going-concern 61 / substantial-doubt 39 / material-weakness 24 / reverse-split 27 across the full scanned set) |
| → deep band | 54 | watch band (12) surfaced separately, not deep-dived |
| **Gate 2 (LLM theme-fit) on 54 deep** | | **pure_play 17 · partial 4 · misrecall 33** |
| **Deep-dive queue (pure + partial)** | **21** | EVERY one deep-dived (full-data rule, no sampling) |
| Valuation computed | 21 | mos_basis: fcf_cap 11 · abstain 7 · nav 3 |
| Reports written | 21 | finalize_run emitted 21 verdicts |
| **BUY** | **1** | INVA |
| WATCH (观察) | 20 | |
| Sink (AVOID / kill≥2) | 0 | kill-flags already removed at cheap_pass |

### The dominant failure mode this theme triggers: pharma keyword-collision

33 of 54 deep-band names (61%) were **misrecall**, operating biotechs (SIC 2834/2836: ZYME, SNDX,
ANAB, VIR, KALV, ABUS, ARVN, ...) swept in because pharma companies routinely have **"drug royalty"**
out-licensing language and "streaming" is ambiguous. This is the documented `refractory`-class
over-recall (single-keyword FTS sweeping an adjacent sector). **Gate 2 caught all 33**, without it,
the entire small-cap biotech complex would have hit the valuation/deep-dive queue. The two-stage gate
worked exactly as specified; this is the strongest evidence in the run that the precision gate is
load-bearing, not ceremonial.

Other misrecalls correctly dropped: CEVA (semiconductor IP licensing), MOV (Movado watches),
GSHD (insurance brokerage), CERS/OBIO (medical devices), VGZ (gold *developer*, not a royalty co),
MXC (oil E&P operator), plus diversified operators NACCO-adjacent names.

---

## 2. Shortlist (21 deep-dived royalty/streaming names)

Ranked output: `reports/smallcap/2026-06-20_royalty-streaming/RANKING.md`.

| # | Ticker | Name | Theme fit | mktcap | mos_basis | MoS / NAV-MoS | buy_eligible | Rating |
|---|---|---|---|---:|---|---|---|---|
| 1 | **INVA** | Innoviva | partial | $1,660M | fcf_cap | **+30.3%** | **true** | **买入 / BUY** |
| 2 | NRP | Natural Resource Partners | partial | $1,336M | fcf_cap | +36.8% | true (mech.) | 观察 (judgment downgrade) |
| 3 | DMLP | Dorchester Minerals | pure | $1,206M | fcf_cap | −12.1% | false (`fcf_sustainability_uncertain`) | 观察 |
| 4 | KRP | Kimbell Royalty Partners | pure | $1,592M | abstain |, | true | 观察 |
| 5 | CRT | Cross Timbers Royalty Trust | pure | $54M | abstain |, | false (`financial_sic`) | 观察 |
| 6 to 18 | ELE, GROY, MTA, TMCR, UROY, VOXR (gold/metals royalty); NRT, PBT, SBR, PVL, PRT (oil royalty trusts); MSB (iron-ore trust); VMET (metals royalty) | | pure | $28M,$1,307M | fcf_cap (null FCF) / abstain |, | mixed | 观察 |
| 19 | FRPH | FRP Holdings | partial | $455M | nav | ~0% | true | 观察 |
| 20 | NC | NACCO Industries | partial | $376M | nav | ~0% | true | 观察 |
| 21 | XOMA | XOMA Royalty | pure | $741M | nav | −94.7% | false (`wrong_entity_suspected`) | 观察 |

---

## 3. The one BUY: INVA (Innoviva), buy_eligible reasoning

**Mechanical gate (all pass):**
- `mos_basis = fcf_cap`, `margin_of_safety_pct = +30.3%` (≥30 threshold, just clears)
- `buy_eligible = true`, `buy_ineligible_reasons = []`
- kill-flags = 0 (no going-concern / material-weakness / death-spiral)
- `fundamental_decline_flag = false`; `concentration_flag = null`
- Revenue genuinely **growing**: 337→392→331→310→359→**411M** (rev_slope +1, rev_accel **+1**),
  OCF stable ~$190 to 200M, EV/EBITDA **3.4x**, EV/Sales 3.2x, cheap on the cash-generative royalty core.

**Disconfirmation search (mandatory, run):** clean. No short report, no securities litigation.
Critically, the only "going concern" hit belonged to **Inventiva S.A. (IVA)**, a *different* French
biopharma, a real-world name-collision that mirrors the model's own `wrong_entity` guard. Innoviva
is well-capitalized ($567M cash > $320M debt, $1.2B equity), Q1-2026 net income +$186.6M, and is
**buying back stock** ($125M authorization) rather than diluting. The one watch-item is a $208M
ESOP-related shelf (potential future dilution), which is a monitor trigger, not a thesis-breaker.

**Why BUY survives judgment, not just the gate:** the thesis rests on T1 audited financials (royalty
revenue, OCF, buyback authorization in filings), not on management guidance (T3). The MoS is built
on a norm_fcf whose contamination_ratio is 0.90 (only mildly below the trailing average) on a *rising*
revenue line, i.e., the normalization base is NOT peak-contaminated. Confidence held at 55%
(not higher) because `data_quality` carries `net_income_nonpositive_pe_null` (NI lumpy from the Armata
equity stake) and `ebitda_series_partial_entries:10`, and theme fit is **partial** (royalties are the
core but IST operating platform + healthcare-asset stakes dilute the pure-play characterization).

---

## 4. The zero-other-BUYs: why each non-BUY did NOT clear (the abstain-discipline core)

This theme is the abstain test. Three structurally distinct non-BUY buckets, each handled correctly:

### 4a. NRP, mechanical BUY, JUDGMENT DOWNGRADE to WATCH (the value-trap the gate missed)

NRP is the single most important finding in this run. The deterministic layer rated it
**buy_eligible = true, MoS +36.8%, fcf_cap, 0 kill-flags, fundamental_decline_flag = false**, a clean
mechanical BUY. It is a value trap:

- The MoS rests on `norm_fcf = $223M` (trailing-5yr avg). **`contamination_ratio = 0.7445`** and
  **`latest_below_avg = true`**, the normalization base is propped up by the 2022 to 2023 coal-price
  peak the company is no longer earning.
- Latest reported **net income = −$84.8M**; revenue −16.6% YoY (2022 peak $307M → 2024 $232M).
- Disconfirmation (T1/T2): the 49% Sisecam Wyoming **soda-ash JV is in a "generational bear market"**,
  has paid **no distributions since Q2-2025**, required a $39.2M capital contribution; **Q1-2026 free
  cash flow turned negative (−$5.4M)**. Coal in structural decline.

**Why `fundamental_decline_flag` (P6) did not fire:** it requires ALL THREE of
`rev_slope_sign < 0` AND `contamination_ratio < 1.0` AND `latest_below_avg`. NRP has 2 of 3:
contamination 0.74 and latest_below_avg true, but **rev_slope_sign = +1** because the linear fit over
2019 to 2024 is upward (it is recovering off the 2020 COVID coal trough of $120M). The single positive
slope term masks the 2022-peak deterioration, a **shape the P6 flag is blind to** (V-shaped series:
trough → peak → rolling over, with the latest point still above the trough).

**This is a permitted judgment downgrade, NOT the banned perpetual-veto.** The rubric bans the
*qualitative forward* "cyclical turn not yet realized → won't buy." NRP's downgrade rests on
**realized, T1-documented facts**: latest NI already negative, JV distributions already suspended,
Q1-2026 FCF already negative, and the arithmetic fact that norm_fcf is peak-contaminated. No forecast
is required. Recorded as a judgment override on the report with full reasoning.

### 4b. Abstain bucket (7), royalty TRUSTS and the LP: correct refusal to fabricate

CRT, NRT, PBT, SBR (oil royalty trusts), MSB (iron-ore trust), VMET (metals royalty, SIC 6795),
KRP (oil&gas mineral LP). These routed to **abstain** via `financial_sic_forced_unsuitable` (or NAV
uncomputable for the LP). This is the **right** outcome: a royalty trust is a pass-through vehicle ,
its value is the PV of remaining reserves/streams, not book equity or an FCF-cap perpetuity, and its
XBRL uses trust-specific concepts (royalty income, distributable income) that `deepdive_data` does not
map. The ranking shows `$0M revenue/OCF` for these names precisely because the extractor cannot read
trust tags, and the model **abstains rather than computing a fake MoS off a zero**. That is abstain
discipline working: it does not over-abstain (it found INVA) and it does not under-abstain (it refuses
to pretend it can value a trust it cannot read). Ranked on EV multiples where available (KRP EV/EBITDA
6.7x, MSB EV/Sales 3.3x), never penalized for the model mismatch.

### 4c. NAV bucket (3) and fcf_cap-null bucket, analyzable but not ≥30% MoS

- **XOMA** (pharma royalty aggregator, a genuine pure-play royalty business model): routed `nav`,
  `buy_eligible = false` via **`wrong_entity_suspected`** (NI/revenue ratio 3.1x, absurd because the
  royalty holdco books milestone/royalty income in a way that breaks the heuristic). NAV MoS −94.7%
  (book equity $49M vs $741M mktcap, but book equity badly understates a royalty portfolio's PV).
  Correct to NOT BUY, though XOMA is a candidate where the NAV path *materially understates* value ,
  flagged as a data-quality limitation, not a thesis.
- **FRPH, NC** (partial: real-estate + mining royalty / coal operator + mineral royalty): `nav` basis,
  NAV MoS ~0% (< 30 threshold) → WATCH. Analyzable, just not cheap enough.
- **Gold/metals royalty pure-plays** (GROY, MTA, ELE, TMCR, UROY, VOXR) + small oil trusts (PRT, PVL):
  routed `fcf_cap` but `norm_fcf` is **null/non-positive**, these are early-stage royalty companies
  still deploying capital into streams with little/no positive FCF yet, so the intrinsic band is
  uncomputable and MoS is null. Cannot BUY (no MoS), not penalized. **DMLP**: `fcf_cap` MoS −12.1%,
  `buy_eligible = false` (`fcf_sustainability_uncertain`, OCF-proxy capex unknown), fully priced.

---

## 5. Is the sector-specific failure mode handled correctly?

**Focus = tricky royalty/streaming valuation + abstain discipline + over-abstention check. Verdict: MOSTLY YES, with one named gap.**

| Sub-test | Result |
|---|---|
| Does it over-abstain on legitimately analyzable names? | **No.** It found INVA (clean fcf_cap BUY) and computed real MoS for NRP, DMLP, FRPH, NC. It did not blanket-abstain the theme. |
| Does it abstain correctly on structurally unmodelable vehicles? | **Yes.** Royalty trusts → `financial_sic_forced_unsuitable` abstain; refuses to fabricate MoS off untagged $0 revenue. |
| Does the three-way mos_basis route royalty/streaming shapes sensibly? | **Yes.** fcf_cap for operating royalty cos, nav for asset-heavy, abstain for trusts/LPs, a clean separation that matches the cash-flow reality. |
| Does the keyword-collision precision gate hold? | **Yes, strongly.** Gate 2 cut 33/54 pharma+misc misrecalls; without it the biotech complex floods the queue. |
| **Does the P6 fundamental_decline veto catch the value trap?** | **NO, gap.** NRP (peak-contaminated norm_fcf, latest NI negative, JV impaired) passed `fundamental_decline_flag = false` because `rev_slope_sign = +1` on a V-shaped recovery-then-rollover series. The 3-condition AND is blind to "trough→peak→rolling-over." **Caught only by analyst judgment + disconfirmation, not mechanically.** |

**Actionable gap for iteration 2:** `fundamental_decline_flag` should also fire (or a sibling
`peak_contamination_flag` should) when `contamination_ratio < ~0.8` AND `latest_below_avg == true`
AND latest reported net income < 0, *independent of* `rev_slope_sign`. The current AND-of-three lets
a positive multiyear slope (driven by an old trough) override a clearly contaminated normalization
base. NRP is the canonical counterexample for the rev_slope dimension, exactly as SIGA was for the
contamination dimension.

---

## 6. Data-quality observations

1. **Royalty-trust XBRL is unreadable by `deepdive_data`.** CRT/NRT/PBT/SBR/PVL/MSB show
   $0M revenue/$0M OCF in RANKING because trusts tag royalty/distributable income under non-standard
   concepts. The abstain routing rescues this (no fake numbers), but EV multiples are partial. A
   trust-aware concept map (`RoyaltyIncome`, `DistributableIncome`) would let the model rank trusts on
   real distribution yield instead of abstaining blind.
2. **`wrong_entity_suspected` on royalty aggregators (XOMA).** The NI/revenue-ratio heuristic
   misfires on holdco royalty accounting where milestone income dwarfs reported "revenue." Correctly
   blocks a false BUY, but also blocks a name that may be genuinely undervalued, a known
   false-positive direction worth a royalty-holdco carve-out.
3. **NAV understates royalty-portfolio value structurally.** Book/tangible equity (XOMA $49M) is a
   poor proxy for a stream portfolio's PV; `nav` MoS for royalty businesses is systematically too
   conservative. Human NAV judgment flag is correctly surfaced.
4. **OCF-proxy for FCF when capex untagged** (NRP, DMLP): `fcf_uses_ocf_proxy` + the
   `fcf_sustainability_uncertain` guard (which correctly blocked DMLP). For royalty cos capex is near-
   zero so OCF≈FCF is usually fine, but the guard is appropriately cautious.
5. **finalize_run vs Gate 2 accounting mismatch.** finalize_run flagged "33 deep-band candidates
   without a report", these are the Gate-2 misrecalls correctly NOT deep-dived. For theme runs with
   heavy keyword over-recall, `--allow-missing` is required and the warning is expected, not an error.
   A cleaner design would have Gate 2 write a filtered queue that finalize_run reads as the denominator.
6. **No music-royalty name reached the deep band.** "music royalties" recalled into the unknown band
   only (the marquee names like music-royalty funds are UK/non-SEC listed or sub-scale). Coverage gap:
   this theme's "music royalties" leg is structurally invisible to an EDGAR-only universe.

---

## 7. Market-intel context (T2, supplementary, did NOT drive any buy_eligible/BUY decision)

Clearly labeled T2 analyst context (TrendsMCP, demand/attention only):

- **"gold royalty" search interest +66.7% YoY** (gold bull market pulling attention to the royalty
  model) but **−66% over the last 3 months**, the spike has faded. Consistent with the "hot theme =
  casino" prior: the gold-royalty narrative had its moment and is cooling, which raises the bar for the
  early-stage gold royalty pure-plays (GROY/MTA/ELE/VOXR) that are still pre-FCF.
- **"music royalties investment" rising off ~zero** (nascent retail interest, low absolute volume) ,
  a genuinely emerging theme, but with no SEC-listed small-cap pure-play to express it (see §6.6).
- **"soda ash" search interest flat YoY (+1.4%)**, attention-neutral industrial commodity; does not
  contradict the filing-documented oversupply/price collapse that underpins the NRP downgrade. T2
  neither rescues nor worsens NRP; the downgrade stands on T1 filings.

None of the above touched the mechanical gate. They are context for the written narrative only.

---

## 8. Skeptical-PM usable verdict

**USABLE: YES.**

A skeptical PM gets exactly what this skill is supposed to deliver: a 694→21 funnel that survives a
brutal keyword-collision (61% of the deep band was pharma noise, all caught), one defensible BUY
(INVA, cheap, growing, clean disconfirmation, T1-anchored), and a correctly-abstaining tail of
royalty trusts the model honestly admits it cannot value. The standout deliverable is the **NRP
value-trap catch**: the mechanical gate said BUY, and the disconfirmation + contamination reading
overrode it to WATCH with a precise, falsifiable reason (peak-contaminated norm_fcf, realized negative
FCF, JV impairment), this is the landmine-scanner doing its job at the exact point where a naive
screen would have handed the PM a melting ice cube.

The honest caveats a PM must carry forward: (a) INVA is a *partial* theme fit and a 30.3% MoS that
**just** clears, size it as a watch-to-starter, not a conviction position; (b) the P6 veto has a
documented V-shape blind spot (iteration-2 fix proposed); (c) royalty-trust and royalty-holdco
valuations are data-limited, abstain/NAV outputs there are floors, not fair values. Calibration
remains unknown (verdicts mature 2027-06); this is the correct honest state, not a defect.
