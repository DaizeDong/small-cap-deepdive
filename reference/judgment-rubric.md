# Judgment Rubric — Invariant C

> This is the single source of truth for the deep-dive judgment layer.
> Every deep-dive subagent must score all 7 dimensions and produce the output template below.
> Deviating from this rubric — omitting dimensions, skipping the output template, substituting narrative for scores — renders the report invalid.
>
> Source disciplines: `disclosure-discipline.md` (bias controls) + `cognitive-priors.md` (base rates).
> Mechanical inputs: `deepdive_data.py` JSON (financial series, kill-flags, insider trades).

---

## Before Scoring: Required Preamble

Before touching the 7-dim scorecard, the subagent must complete these in order:

1. **Base rate anchor** — state the reference class and its base rates (see `cognitive-priors.md`)
2. **Disconfirmation search** — run WebSearch for `<company> short report OR fraud OR dilution OR lawsuit OR going concern`; record what was found or explicitly state "searched, nothing found"
3. **Data staleness check** — if any mechanical field has `data_may_be_stale: true`, use WebSearch to verify current values before scoring
4. **Valuation & margin of safety** — run `python tools/valuation.py --json <deepdive_json> --ticker <T>` (or read the pre-merged `valuation` block if already present in the deepdive JSON). Record `mos_basis`, `margin_of_safety_pct`, `nav_margin_of_safety_pct`, `ev_sales`, `ev_ebitda`, `reverse_dcf_implied_growth`, and any `data_quality` flags. **Also record the mechanical eligibility composite emitted by `valuation.py`: `buy_eligible` (bool) and `buy_ineligible_reasons` (list[str]); and the deepdive `derived` change-detection fields `concentration_flag` ("kill"/"watch"/null) and `fundamental_decline_flag` (bool).** These become mandatory inputs to the BUY trigger logic below; do not proceed to rating without them.

Only then open the 7-dim scorecard.

---

## 7-Dimension Scorecard

Each dimension: **score 1–5** + **evidence Tier** (T1/T2/T3) + **one-line basis**.

### Dimension 1 — Financial Quality

Covers: revenue growth quality, profitability path, cash flow, runway, dilution history.

**What to score:**
- Revenue growth: organic vs. acquisition-driven; revenue vs. accounts-receivable growth rate (AR growing faster = receivables stuffing red flag)
- Cash flow: OCF vs. net income divergence; sustained OCF negative with positive net income = red flag
- Runway: see `mechanical-checks.md` Guard 5 for `null` interpretation
- Dilution: share count history (S-3/ATM/death-spiral convertibles in SEC filings)
- Profitability path: clear GAAP breakeven visibility vs. perpetual "adjusted EBITDA"

**Score anchors:**
- 5: Cash-flow positive, organic growth, no dilution, clear profitability
- 3: Mixed signals; one structural concern but not fatal
- 1: Serial dilution, negative OCF, runway < 2 quarters, no path to profitability

**Hard ceiling:** If `has_death_spiral = True`, cap this dimension at 1. If net income is substantially driven by one-time items (e.g., deferred tax release), note it and score on OCF only.

### Dimension 2 — Business Model and Moat

Covers: revenue repeatability, defensibility against large competitors.

**What to score:**
- Revenue model: subscription/contract (recurring) vs. one-time/project-based
- Moat test: "If Microsoft or Google entered this space, would this company survive? Why?"
- Network effects, switching costs, patents, regulatory licenses, scale advantages
- For small-cap: "first-mover advantage" is not a moat answer unless paired with lock-in mechanism

**Score anchors:**
- 5: Demonstrable switching costs or regulatory moat; FANG-entry test passed convincingly
- 3: Niche position with some stickiness but attackable
- 1: No moat; revenue is one-time; product is commodity; FANG-entry would likely eliminate the company

### Dimension 3 — Growth and Unit Economics

Covers: revenue growth decomposition, customer concentration, margin trends.

**What to score:**
- Growth decomposition: volume vs. price vs. M&A contribution
- Customer / program concentration: read the mechanical `concentration_flag`, `top_customer_pct`, `top_program_pct`, and `concentration_detail` from the deepdive `derived` block. These are magnitude-based, sourced from XBRL `RevenueFromContractWithCustomer` segment members / concentration-footnote numerics — they replace the old English-substring detector. Cross-check against the 10-K "accounted for" disclosures only if the mechanical fields are null.
- Net retention or churn (SaaS companies: from earnings call transcripts or 10-K)
- Gross margin trend: expanding = operating leverage; shrinking during growth = subsidized growth

**Concentration kill/watch rule (mechanical, magnitude-based):**
- `concentration_flag = "kill"` when `top_program_pct > 60` OR `top_customer_pct > 40`. A `kill` makes the company **not `buy_eligible`** (see BUY trigger) and caps this dimension at 2.
- `concentration_flag = "watch"` when either ratio falls in the 40–60 band (and neither crosses the kill threshold). A `watch` does not block BUY by itself, but must be surfaced in the Dim-3 basis and in §5 kill-flag review.
- `concentration_flag = null` when neither threshold is approached or the numerics are unavailable.

**Hard ceiling:** If single customer >40% of revenue (equivalently `concentration_flag = "kill"` via the customer threshold), cap this dimension at 2 regardless of growth rate.

### Dimension 4 — Management

Covers: insider trading signals, dilution behavior, track record, guidance accuracy.

**Bias control: this dimension is the highest-risk halo-bias zone. See `disclosure-discipline.md` for mandatory halo de-bias rules.**

**What to score — only evidence independent of stock price performance:**
- Insider trades (openinsider.com or edgartools Form 4): net buy or net sell over past 12 months; cluster selling during fundraising = negative signal
- Historical guidance accuracy: did management hit guidance in the past 4–6 quarters?
- Founder/CEO prior company outcome: what happened to the last company they ran?
- Capital allocation: are buybacks/dividends funded by cash flow or debt? Is compensation aligned with shareholder returns (DEF 14A)?
- Salary vs. company performance: executives drawing large salaries at cash-burning micro-caps is a red flag

**Prohibited sources for this dimension:** Any narrative based on press interviews, conference presentations, LinkedIn profiles, or subjective impressions of "vision" or "execution ability."

**Hard ceiling:** If `insider_net_sell` is materially negative (strong cluster selling) AND dilution rate is high, cap this dimension at 2.

### Dimension 5 — Theme Fit and Timing

Covers: real revenue exposure to the stated theme vs. keyword-only association.

**What to score:**
- Revenue already derived from theme vs. only mentioned in PR/earnings calls
- Time to meaningful theme revenue: already happening vs. 3+ years out
- Whether the theme exposure is already priced in (compare to peers; check if the stock re-rated on AI/theme narrative)
- Crowdedness of the thesis: is this a widely discussed "hidden gem" that is no longer hidden?

**Hard ceiling:** If the company has zero current revenue from the theme and the theme connection appears only in PR/call transcripts (no 10-K business description evidence), cap this dimension at 2. This is the "pure-concept-playing" ceiling.

**Note:** This dimension maps to Gate 2 of `discovery-engine.md`. A company that barely passed Gate 2 as `partial` should score 2–3 here, not 4–5.

### Dimension 6 — Valuation

Covers: current price reasonableness relative to fundamentals and implied assumptions.

**What to score:**
- For revenue-positive, pre-profit companies: EV/Sales vs. comparable peers
- Reverse DCF: what revenue growth rate does the current EV/Sales imply over 5 years? Is that credible given current growth rate and TAM?
- Use fully diluted share count (include options, warrants, convertible debt)
- For asset-heavy businesses: EV/EBITDA, Price/Book if applicable

**Score anchors:**
- 5: Implied growth rate is below current growth rate; trading at discount to peers
- 3: Fair value; priced in line with fundamentals
- 1: Implied growth rate requires heroic assumptions; priced for perfection; EV/Sales >10x with no path to margin

### Dimension 7 — Risk and Counterargument

Covers: the best argument against ownership; zero-path scenarios.

**What to score:**
- Strength of the bear case (can it be falsified, or is it structural?)
- Zero/wipeout scenarios: shelf offering exhausts market demand → bankruptcy; customer concentration → loss of contract → revenue cliff; going-concern finding followed by bank covenant breach
- Short-seller research (if found in mandatory disconfirmation search)
- Regulatory risk, litigation, audit changes
- Liquidity risk: average daily volume — can you exit without moving the price significantly?

**Score anchors:**
- 5: Bear case is weak; main risk is general market downturn; no structural zero path
- 3: Meaningful risks exist but are manageable or partially hedged by business model
- 1: Multiple independent zero paths; short research exists and is factually grounded; kill-flags cluster

---

## Output Template

Every deep-dive report must produce this structure exactly. No field may be omitted; write "N/A — [reason]" if genuinely unavailable.

```
# [TICKER] Deep Dive — <date> (timestamp-locked)

评级: [买入 / 观察 / 避开]   置信度: __%   持有期: __

## 0. One-line thesis + base-rate anchor
<One sentence stating the core thesis.>
Reference class: <e.g., "pre-revenue micro-cap with AI exposure"> — base rates: ~X% zero/wipeout within 5 years, ~Y% mediocre outcomes, ~Z% acquisition/upside.

## 1. Scorecard

| Dimension | Score (1–5) | Tier | Basis (one line) |
|---|---|---|---|
| 1. Financial quality | | | |
| 2. Business model / moat | | | |
| 3. Growth / unit economics | | | |
| 4. Management | | | |
| 5. Theme fit / timing | | | |
| 6. Valuation | | | |
| 7. Risk / counterargument | | | |
| **Scorecard total (unweighted sum)** | **/35** | | |

> The scorecard total is a plain unweighted sum of the 7 dimension scores — there are no per-dimension weights. The scorecard does NOT by itself produce the rating; the rating is determined by the mechanical decision layer below: **rating = f(MoS / NAV MoS, kill-flags, hard-ceilings, `buy_eligible`)**. The scorecard total is a diagnostic summary and a tiebreaker, not a weighted composite.

Kill-flag count: __ (from mechanical-checks layer)
Mechanical eligibility: `buy_eligible` = __   `buy_ineligible_reasons` = [__]   `concentration_flag` = __   `fundamental_decline_flag` = __

## 2. Bull case (falsifiable)
- Claim: <specific claim>
  Trigger to flip: <if X does not happen by Q__ , this argument is falsified>

## 3. Bear case (falsifiable) + disconfirmation search results
- Claim: <specific claim>
  Trigger to flip: <if X happens by Q__ , this argument is falsified>

Disconfirmation search: [results or "searched, nothing found"]

## 4. Pre-mortem: most likely path to -80%
<Two or three sentences. Assume you are already wrong — what happened?>

## 5. Kill-flag review
- has_going_concern: [True/False] — <one line on auditor context>
- has_material_weakness: [True/False] — <one line>
- has_death_spiral: [True/False] — <one line on instrument terms>
- concentration_flag: [kill/watch/null] — <one line: top_customer_pct / top_program_pct and concentration_detail>
- fundamental_decline_flag: [True/False] — <one line: rev_slope_sign, contamination_ratio, latest_below_avg>

## 6. Valuation: implied assumptions
Current EV/Sales: __x   EV/EBITDA: __x   Peer median EV/Sales: __x
Reverse DCF implied growth (5-yr): __%   Actual trailing growth: __%
Assessment: <credible / stretched / heroic>
MoS basis: <fcf_cap / nav / abstain>   MoS: __%   [NAV MoS: __%]   data_quality flags: <list or none>
buy_eligible: <true/false>   buy_ineligible_reasons: <list or none>
Catalyst: <one sentence with dated trigger, or "none"> — note: catalyst MoS-waiver FROZEN (iteration 1) → a verified catalyst yields WATCH-with-catalyst, not BUY
BUY trigger fires: <YES — state basis (MoS ≥ 30% AND buy_eligible AND zero kill-flags AND no T3) | NO — state which condition fails; if buy_eligible=false, list buy_ineligible_reasons verbatim>

## 7. Monitor triggers (which 8-Ks / data points change the rating)
- <trigger 1: e.g., "next earnings: if gross margin < X%, WATCH → AVOID">
- <trigger 2: e.g., "Form 4 cluster buying by insiders → re-evaluate rating upward">

## 8. Known gaps and unverified items
- <data point that could not be obtained, with reason>
- <assumption that is load-bearing but unverified>
```

---

## Symmetric BUY Trigger (Phase 3)

> This section is the single source of truth for when a BUY rating is mechanically permitted.
> The trigger is based entirely on T1 valuation data from `tools/valuation.py`.
> Scorecard aggregate alone cannot produce a BUY; the MoS threshold must also clear.
>
> **Conservatism note:** The BUY trigger is intentionally conservative — it requires the market cap to be ≥30% below the low end of the intrinsic value band, which itself already uses a conservative 12% cap rate on normalized (cycle-average) FCF. BUY rarely or never firing in a given run is expected and correct, not a calibration bug.

### The `buy_eligible` mechanical gate (Phase 3.1)

`tools/valuation.py` composes and emits a single mechanical boolean, `buy_eligible`, that the BUY trigger below ANDs in. It is the OR of every BUY-blocking guard, negated — i.e. `buy_eligible` is true only when **none** of the following fire:

`buy_eligible = (not extreme_mos_review_required) AND (not large_cap_out_of_scope) AND (not fcf_sustainability_uncertain) AND (not financial_sic forced-unsuitable) AND (not debt_truncation_suspected) AND (not wrong_entity_suspected) AND (concentration_flag != "kill") AND (not fundamental_decline_flag)`

When `buy_eligible` is false, `valuation.py` also emits `buy_ineligible_reasons` — a `list[str]` naming each guard that fired (e.g. `["concentration_flag=kill", "fundamental_decline_flag"]`). The judgment layer MUST copy `buy_ineligible_reasons` verbatim into the §6 BUY-trigger line whenever BUY does not fire for an eligibility reason, so the report states *why* mechanically rather than via narrative. These guards previously existed only as advisory strings the trigger never blocked on (the v0.2.1 gap); they now bite by construction.

`buy_eligible` is a **necessary, not sufficient** condition: clearing it does not produce a BUY; the MoS / catalyst paths below still must independently pass.

### Three-Way `mos_basis` Decision Tree

#### `mos_basis = "fcf_cap"` — Normal operating company

**BUY requires ALL of the following:**
1. `margin_of_safety_pct ≥ 30%` (conservative intrinsic value band low-end exceeds market cap by ≥30%)
2. **Zero effective kill-flags** — kill-flag count must be 0. `going_concern`, `death_spiral`, and `material_weakness` all block BUY with no exception. There is no "one kill-flag of modest severity" escape hatch.
3. **No T3-load-bearing thesis** — the primary BUY argument must rest on T1 evidence (audited financials, Form 4, 10-K); T3-only claims (management guidance, PR) may not be load-bearing for the rating
4. **`buy_eligible == true`** — the mechanical eligibility gate above must pass. In particular this means `concentration_flag != "kill"` and `fundamental_decline_flag == false`; a `kill` concentration or a fundamental-decline flag forces `buy_eligible = false` and BUY may not fire on MoS regardless of how large the MoS is. If `buy_eligible` is false, record `buy_ineligible_reasons` on the BUY-trigger line.
5. Confidence is capped by valuation `data_quality` robustness: each data-quality flag that is load-bearing for the MoS computation (e.g., `capex_unavailable_fcf_uses_ocf_proxy`, `normalized_fcf_unavailable`) reduces confidence by 10 percentage points each, floor 30%

**Downgrade rule (deterministic, downgrade-only):** if `margin_of_safety_pct ≥ 30%` and kill-flags = 0 but `buy_eligible == false`, the rating is **WATCH**, not BUY — except that if a hard kill-flag is also present the rating is **AVOID**. Specifically `fundamental_decline_flag == true` OR `concentration_flag == "kill"` downgrades a would-be BUY to **WATCH** (to **AVOID** if combined with any `going_concern`/`death_spiral`/`material_weakness`). This is the melting-ice-cube defense; it can only lower a rating, never raise one.

If `margin_of_safety_pct < 30%`, the company **cannot be rated BUY on MoS** — it is WATCH if fundamentals are clean, AVOID if kill-flags are present. The "cyclical turn not yet realized in T1" reasoning must NOT be used to veto a BUY when static MoS is already ≥30% — that perpetual-veto was the run-3 calibration bug; the threshold already uses conservative normalized FCF, so a realized turn that lifts MoS to ≥30% is sufficient.

**Narrow MECHANICAL carve-out to the perpetual-veto prohibition (P6).** The perpetual-veto ban above prohibits exactly one thing: the *qualitative forward judgment* "the cyclical turn has not yet been realized in T1, therefore I won't buy." That qualitative veto remains banned. It does NOT prohibit the deterministic, magnitude-based `fundamental_decline_flag` computed mechanically in the deepdive `derived` block. That flag fires only when ALL THREE conditions hold simultaneously:
- `rev_slope_sign < 0` — the multiyear revenue series is sloping down (decline magnitude, not a single point-to-point dip);
- `latest_below_avg == true` — the latest normalization base is below its own trailing average (the company is below its own normal, not merely below a peer); AND
- `contamination_ratio < 1.0` — `contamination_ratio = latest normalization-base / 5yr-avg`, so the normalized FCF the MoS rests on is contaminated by higher prior-period values (the melting-ice-cube signature; SIGA contamination ≈ 0.68).

When `fundamental_decline_flag == true`, the would-be BUY is downgraded to WATCH (deterministic, downgrade-only) even at MoS ≥ 30% — because the MoS is built on a normalization base the company is no longer earning. This is a measured-data veto, NOT the forward-looking cyclical-turn judgment the prohibition bans. The distinction is exact: the banned veto asks the analyst to *predict* that a future turn will not arrive; this carve-out only observes that the historical series already declined AND the latest period sits below its own average AND the normalization average is peak-contaminated. No qualitative forecast is permitted to extend it.

#### `mos_basis = "nav"` — Asset-heavy company (finance, lessor, etc.)

**BUY requires ALL of the following:**
1. `nav_margin_of_safety_pct ≥ 30%`
2. Zero effective kill-flags (same zero-tolerance as fcf_cap; no exceptions)
3. No T3-load-bearing thesis
4. **`buy_eligible == true`** — the mechanical eligibility gate applies to the NAV path identically. A `concentration_flag == "kill"` or `fundamental_decline_flag == true` forces `buy_eligible = false` and downgrades a would-be NAV BUY to WATCH (AVOID if also a hard kill-flag); record `buy_ineligible_reasons` on the BUY-trigger line.
5. **Confidence must be multiplied by 0.6 before populating the `confidence` field.** NAV basis inherently carries accounting-convention and collateral-haircut uncertainty. Example: an 80% conviction NAV BUY is recorded as `confidence: 48`. This down-weight must be applied mechanically so `rank.py`'s `combined` score actually reflects it.
6. Surface in the report explicitly as: "**Asset-heavy / NAV basis — human NAV judgment advised**"

EV/EBITDA and EV/Sales should be reported alongside for relative comparison. Do NOT use `margin_of_safety_pct` (FCF MoS) for these companies; it will be null with `mos_null_reason = "fcf_cap_model_unsuitable_use_nav"`.

#### `mos_basis = "abstain"` — Asset-heavy but NAV cannot be computed

**Do NOT apply a BUY or AVOID trigger on MoS.** Rank only on EV/EBITDA and EV/Sales relative to peers. Never penalize the ranking for the model mismatch — a company that is asset-heavy is not automatically bad. Do not report either `margin_of_safety_pct` or `nav_margin_of_safety_pct` as meaningful signals.

---

## Catalyst / Forced-Trading Modifier

A fairly-priced company (MoS < 30%) with a specific, T1-evidenced, un-priced catalyst is surfaced as **WATCH-with-catalyst**. This is not a narrative override — it is an additional evidence dimension. **In iteration 1 the catalyst no longer reaches BUY (MoS-waiver frozen, see below).**

**Qualifying catalyst categories (CLOSED ENUMERATED LIST — no other categories qualify):**

Only the following four catalyst types are recognized. An event that does not fit one of these four categories is NOT a catalyst, regardless of whether it appears in an SEC filing.

- **(a) Spinoff filings:** Form 10-12B or 15-12B on file, with a documented index-fund / mandate forced-selling mechanism (e.g., the spinoff will not be eligible for inclusion in the index the parent is in, forcing passive holders to sell).
- **(b) Cluster open-market insider purchases:** Form 4 filings showing ≥2–3 insiders purchasing shares at market prices within any rolling 90-day window. Option exercises, RSU vesting, and any grant-related acquisitions do NOT qualify — only open-market cash purchases.
- **(c) Court-ordered asset sales or special distributions:** documented in an 8-K with a court order or settlement agreement reference AND a scheduled completion date on record.
- **(d) Delisting-avoidance / exchange-deficiency events:** an 8-K or exchange notice documenting a minimum-bid or minimum-equity deficiency, which creates forced selling by holders who cannot hold below-standard securities.

**Events that explicitly do NOT qualify as catalysts — regardless of SEC filing:**
Earnings guidance, revenue guidance, product launches, new product announcements, customer wins, contract announcements, partnership announcements, market expansion narratives, and any organic-growth or forward-looking management narrative. These are NOT catalysts even if disclosed in an 8-K, 10-Q, or earnings call transcript.

**Requirements to apply the catalyst modifier:**
1. **Category match:** the catalyst must fit one of the four enumerated categories above
2. **T1-evidenced:** documented in the specific T1 source listed for that category (Form 10-12B/15-12B, Form 4, 8-K with court order, exchange deficiency notice)
3. **Dated trigger:** a specific expected resolution date or filing deadline must be recorded (e.g., "spinoff effective Q3 2026 per 10-12B filing dated 2026-03-15")
4. **Forced-trading or information-diffusion mechanism:** name the specific mechanism by which this catalyst creates mis-pricing
5. **Catalyst field populated:** the `catalyst` field in the output schema must be filled with a one-sentence description of the catalyst category, T1 source, and dated trigger; null if no qualifying catalyst applies

**Catalyst modifier logic — FROZEN (iteration 1).** The catalyst MoS-waiver is **temporarily frozen**: a qualifying catalyst no longer waives the MoS threshold and may NOT lift a sub-30% MoS company to BUY. If all five requirements are met, the rating is **WATCH-with-catalyst** — surface the verified catalyst (category, T1 source, dated trigger) in the report and populate the `catalyst` field, but the rating stays WATCH, not BUY. BUY remains reachable only via the MoS / NAV paths above (which require `buy_eligible == true`).

> Why frozen: the waiver is uncalibrated — the forced-trading mechanism is not yet mechanically verified and there is no per-category Brier score to justify overriding a conservative valuation. This freeze is **temporary, pending mechanism-verification + per-category Brier in iteration 2**; it is a methodology decision (§5-Q3 of the iteration-1 design), not a permanent rule. The zero-kill-flag and no-T3-load-bearing-thesis guardrails continue to apply to the WATCH-with-catalyst surfacing.

---

## BUY-Rating Guardrails (All Apply Regardless of Path)

These apply to every BUY outcome. In iteration 1 the only path to BUY is the MoS / NAV threshold (the catalyst MoS-waiver is frozen → WATCH-with-catalyst):

1. **T1 valuation only.** MoS is computed from SEC/XBRL inputs (T1). Market cap from yfinance is acceptable (labeled T2-adjacent; override with `--mktcap` for audit reproducibility). No T3 data may be substituted.
2. **Cyclicals use normalized EBITDA/FCF.** `tools/valuation.py` enforces this in code; the judgment layer must not un-normalize.
3. **BUY still requires pre-mortem + forced disconfirmation.** The anti-story protections (Disciplines 2 and 6 of `disclosure-discipline.md`) are not relaxed for BUY candidates. A BUY report with no pre-mortem section is invalid.
4. **Perpetual-veto prohibition (qualitative only).** The *qualitative forward* argument "cyclical turn not yet realized in T1 → cannot buy" is explicitly prohibited as a veto when `margin_of_safety_pct ≥ 30%`. Normalized FCF already accounts for cycle conservatism. Applying an additional qualitative veto on top of the conservative metric defeats the mechanical trigger and recreates the run-3 calibration gap. **Exception (carve-out):** this prohibition does NOT cover the deterministic, magnitude-based `fundamental_decline_flag` (rev_slope_sign<0 AND contamination_ratio<1.0 AND latest_below_avg). That flag is a measured-data downgrade — it observes a realized decline that contaminates the normalization base — not a forward prediction, and it is permitted to downgrade BUY→WATCH even at MoS ≥ 30%.

5. **Mechanical eligibility required.** Every BUY also requires `buy_eligible == true` (see "The `buy_eligible` mechanical gate"). The catalyst path no longer reaches BUY in iteration 1 (catalyst MoS-waiver frozen → WATCH-with-catalyst).

---

## Rating Hard-Rules

These rules override scorecard totals. A high aggregate score does not rescue a report from a hard-rule violation.

| Condition | Hard consequence |
|---|---|
| `mos_basis="fcf_cap"` AND `margin_of_safety_pct ≥ 30%` AND kill-flags = 0 AND no T3 thesis AND `buy_eligible == true` | **BUY permitted** (full weight 1.0); confidence adjusted by data_quality flags |
| `mos_basis="nav"` AND `nav_margin_of_safety_pct ≥ 30%` AND kill-flags = 0 AND no T3 thesis AND `buy_eligible == true` | **BUY permitted**; multiply raw conviction by 0.6 before recording `confidence` field; surface as "asset-heavy / NAV basis" |
| `mos_basis="abstain"` | No BUY or AVOID on MoS; rank on EV/EBITDA and EV/Sales only; never penalize for model mismatch |
| `buy_eligible == false` (any guard fired) when MoS ≥ 30% and kill-flags = 0 | **Cannot rate BUY** — downgrade to WATCH; record `buy_ineligible_reasons`. AVOID if a hard kill-flag is also present |
| `concentration_flag == "kill"` (`top_program_pct > 60` OR `top_customer_pct > 40`) | Forces `buy_eligible = false` → **blocks BUY** (downgrade to WATCH; AVOID if hard kill-flag also present); Dim 3 capped at 2 |
| `fundamental_decline_flag == true` (`rev_slope_sign<0` AND `contamination_ratio<1.0` AND `latest_below_avg`) | Forces `buy_eligible = false` → **downgrades would-be BUY to WATCH** even at MoS ≥ 30% (mechanical melting-ice-cube veto; AVOID if hard kill-flag also present) |
| T1-evidenced catalyst matching enumerated category (a)–(d) AND dated trigger AND kill-flags = 0 | **WATCH-with-catalyst** (catalyst MoS-waiver FROZEN, iteration 1) — does NOT lift sub-30% MoS to BUY; `catalyst` field must be populated with category, T1 source, dated trigger |
| `margin_of_safety_pct < 30%` with no catalyst | Cannot rate BUY on MoS basis |
| "Cyclical turn not yet realized in T1" used as QUALITATIVE forward veto when MoS ≥ 30% | **Prohibited** — perpetual-veto; normalized FCF already accounts for cycle conservatism. (Distinct from the mechanical `fundamental_decline_flag` carve-out, which IS permitted.) |
| Any key claim rests solely on T3 evidence | Cannot rate BUY |
| Any kill-flag present (`going_concern`, `death_spiral`, or `material_weakness`) | **Blocks BUY** — zero-tolerance, no adjudication escape hatch. `kill-flag count ≥ 2` → Default AVOID. |
| `death_spiral` convertible detected | Dim 1 capped at 1; composite max = 2 |
| `material_weakness` in ICFR | Dim 1 (financial quality) capped at 2 |
| Net income driven by deferred tax release (not OCF) | Score Dim 1 on OCF only; note the driver |
| AR growing faster than revenue | Required red flag note in Dim 1 basis |
| S-3 shelf / ATM program active with < 4 quarters of runway | Dim 1 score = 1 |
| Single customer > 40% of revenue OR single program > 60% (`concentration_flag == "kill"`) | Dim 3 (growth / unit economics) capped at 2; also forces `buy_eligible = false` (blocks BUY) |
| Single customer / program in the 40–60% band (`concentration_flag == "watch"`) | Surface in Dim 3 basis + §5 kill-flag review; does not block BUY by itself |
| `insider_net_sell` strongly negative AND dilution rate ≥ 15%/yr | Dim 4 (management) capped at 2 |
| Critical data unavailable (runway, revenue, insider trades all null) | Confidence capped at 40% |
| Company has no current revenue from the stated theme (pure concept-playing) | Theme-fit dimension capped at 2; cannot rate BUY solely on theme story |
| Rating is AVOID OR kill-flag count ≥ 3 | Company sinks to bottom of ranking regardless of aggregate score |

---

## Evidence Tier Definitions

- **T1 — Primary / audited:** SEC filings (10-K, 10-Q, Form 4, DEF 14A, 8-K), audited financial statements, court records
- **T2 — Independent third-party:** Analyst reports from non-affiliated firms, short-seller research (reputable), academic studies, verified news reporting with named sources
- **T3 — Company-sourced / unverified:** Press releases, earnings call transcripts without third-party verification, company websites, LinkedIn, unverified social media

T3 evidence may be used as a lead for investigation. It may not be the load-bearing evidence for a BUY rating.

---

## Calibration Loop

Every verdict produced by this rubric must be logged via `python tools/track_forward.py --record`.
Rubric calibration (whether verdicts are systematically too conservative or too aggressive) can
only be evaluated after verdicts mature against realized returns. Full methodology in
`reference/track-forward.md`. **Do not tune the rubric thresholds until ≥~20 verdicts have
matured and the Brier/calibration table has been reviewed.**

---

## Cross-references

- `disclosure-discipline.md` — mandatory disciplines that govern how this rubric is applied (base-rate-first, forced disconfirmation, halo de-bias, pre-mortem procedure, honest data-gap)
- `cognitive-priors.md` — base-rate prior table (microcap zero rates, de-SPAC median, going-concern correlation) used in Section 0 of the output template
- `mechanical-checks.md` — kill-flag counts and data fields that feed into the hard-rules above
- `discovery-engine.md` — theme-fit score (dim 5) reflects Gate 2 classification
