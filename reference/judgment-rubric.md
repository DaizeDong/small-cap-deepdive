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
4. **Valuation & margin of safety** — run `python tools/valuation.py --json <deepdive_json> --ticker <T>` (or read the pre-merged `valuation` block if already present in the deepdive JSON). Record `mos_basis`, `margin_of_safety_pct`, `nav_margin_of_safety_pct`, `ev_sales`, `ev_ebitda`, `reverse_dcf_implied_growth`, and any `data_quality` flags. **Also record the mechanical eligibility composite emitted by `valuation.py`: `buy_eligible` (bool) and `buy_ineligible_reasons` (list[str]); and the deepdive `derived` change-detection fields `concentration_flag` ("kill"/"watch"/null), `fundamental_decline_flag` (bool), and `peak_contamination_flag` (bool — the V-shape value-trap veto, see §5 and the BUY trigger).** Also note the data-quality-only labels `low_revenue_loss_ratio` (bool), the advisory `concentration_unquantified` (bool — text concentration disclosed but no XBRL magnitude, A2), the insurance-routing flag `insurance_concepts_present` (bool — insurance XBRL concepts present → treat like a financial-SIC company regardless of SIC, A3), the extreme-tail gate `low_revenue_loss_ratio_extreme` (bool — `|net_income|/revenue > 20`, gates `buy_eligible`, A4), the second-source sanity-band fields `cross_source_checked` / `cross_source_mismatch` / `cross_source_detail` (P7 — a >2.5x SEC-vs-yfinance disagreement on debt/revenue/shares; `cross_source_mismatch` gates `buy_eligible` as a DATA-INTEGRITY gate, see §5 and the BUY trigger), the degenerate-base / current-loss-masking veto `normalization_masks_current_loss` (v0.3.1 #1 — `normalized_fcf > 0` AND (`latest_ocf < 0` OR `latest_fcf < 0` OR `contamination_ratio < 0`); the trailing average is masking current cash burn / a divested-segment stub, gates `buy_eligible` and downgrades BUY→WATCH, see §5 and the BUY trigger), and the provenance tag `form_used` (the filing form actually used — 10-K/20-F/40-F — surfaced in the trust banner). These become mandatory inputs to the BUY trigger logic below; do not proceed to rating without them.

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

**Text-only / pre-XBRL concentration advisory (A2, iteration 3) — `concentration_unquantified` (bool).** The magnitude `concentration_flag` above is XBRL-only and returns `null` for filers who disclose customer concentration in narrative text but never in machine-readable segment members (SIGA-class single-customer risk in text-only or pre-/early-XBRL filers — e.g. SWMR, LFCR). `deepdive_data.py` therefore emits a separate advisory boolean: `concentration_unquantified = (the 10-K text customer-concentration flag is True) AND (concentration_flag is None)` — i.e. the disclosure SAYS there is concentration but no machine-readable magnitude exists to quantify it. **This is advisory only**: it is surfaced in `data_quality` and in the Dim-3 basis / §5 kill-flag review, but it is NOT in the `buy_eligible` composite and does NOT gate or cap any dimension by itself. It closes the text-only / pre-XBRL blind spot the mechanical SIGA-kill is otherwise blind to (the exact cohort where single-customer risk concentrates). When set, the Dim-3 basis must read: "concentration disclosed in text but unquantified (no XBRL magnitude) — analyst must read the 10-K concentration footnote directly before relying on the absence of a `kill`."

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
- concentration_unquantified: [True/False] — <one line: text concentration flag True AND magnitude concentration_flag null — advisory only (A2), analyst must read 10-K footnote; does NOT gate>
- fundamental_decline_flag: [True/False] — <one line: rev_slope_sign, contamination_ratio (must satisfy 0<cr<1.0), latest_below_avg>
- peak_contamination_flag: [True/False] — <one line: contamination_ratio (must satisfy 0<cr<0.8 — negative/degenerate base never fires, A1), latest_below_avg, latest_net_income — V-shape value-trap, independent of rev_slope_sign>
- low_revenue_loss_ratio: [True/False] — <one line: revenue present-but-small + |net_income|/revenue>2.0 — data-quality label only, does not gate BUY>
- cross_source_mismatch: [True/False] — <one line: cross_source_checked + cross_source_detail (which of debt/revenue/shares disagreed >2.5x, both values, ratio) — P7 DATA-INTEGRITY gate, forces buy_eligible=false; "checked=False" means yfinance gave no comparable field and this NEVER blocks>
- normalization_masks_current_loss: [True/False] — <one line: normalized_fcf>0 while latest_ocf/latest_fcf<0 or contamination_ratio<0 — v0.3.1 #1 degenerate-base / divested-stub veto; trailing-avg is masking current cash burn, forces buy_eligible=false and downgrades BUY→WATCH (the TUSK hole the silenced cyclical vetoes miss)>

## 6. Valuation: implied assumptions
Current EV/Sales: __x   EV/EBITDA: __x   Peer median EV/Sales: __x
Reverse DCF implied growth (5-yr): __%   Actual trailing growth: __%
Assessment: <credible / stretched / heroic>
MoS basis: <fcf_cap / nav / abstain>   MoS: __%   [NAV MoS: __%]   data_quality flags: <list or none; include low_revenue_loss_ratio, concentration_unquantified, insurance_concepts_present, low_revenue_loss_ratio_extreme, cross_source_mismatch:<detail> if set>   form_used: <10-K / 20-F / 40-F / null>
buy_eligible: <true/false>   buy_ineligible_reasons: <list or none — includes peak_contamination_flag when the V-shape veto fires>
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

`buy_eligible = (not extreme_mos_review_required) AND (not large_cap_out_of_scope) AND (not fcf_sustainability_uncertain) AND (not financial_sic forced-unsuitable) AND (not debt_truncation_suspected) AND (not wrong_entity_suspected) AND (concentration_flag != "kill") AND (not fundamental_decline_flag) AND (not peak_contamination_flag) AND (not insurance_concepts_present) AND (not low_revenue_loss_ratio_extreme) AND (not cross_source_mismatch) AND (not normalization_masks_current_loss) AND (active MoS is not None)`

Iteration 3 adds two terms to the composite: `(not insurance_concepts_present)` (A3) and `(not low_revenue_loss_ratio_extreme)` (A4). Iteration 5 adds one more: `(not cross_source_mismatch)` (P7 — the second-source sanity band, the first composite term sourced from an INDEPENDENT feed rather than internal-consistency on SEC XBRL). **v0.3.1 adds two final terms:** `(not normalization_masks_current_loss)` (#1 — the degenerate-base / current-loss-masking veto that closes the TUSK hole the mechanical cyclical vetoes silence) and `(active MoS is not None)` (#9 — a null MoS can never be `buy_eligible`; absence of a numeric MoS emits the explicit reason `not_assessable_no_intrinsic_band` rather than leaving `buy_eligible` True-by-absence-of-data). All are detailed below.

When `buy_eligible` is false, `valuation.py` also emits `buy_ineligible_reasons` — a `list[str]` naming each guard that fired (e.g. `["concentration_kill", "fundamental_decline_flag"]`). The judgment layer MUST copy `buy_ineligible_reasons` verbatim into the §6 BUY-trigger line whenever BUY does not fire for an eligibility reason, so the report states *why* mechanically rather than via narrative. These guards previously existed only as advisory strings the trigger never blocked on (the v0.2.1 gap); they now bite by construction.

**Two of these guards were refined in iteration 2 to stop mislabeling genuine producers (P-B):**

- **`wrong_entity_suspected` (REFINED again in iteration 3, A4 — strictly unit-mistag / wrong-CIK).** Fires ONLY on a true entity-identity error: `shares_outstanding < 1000`, OR the ticker is absent from `company_tickers.json`, OR a CIK mismatch. The `|net_income|/revenue` ratio trigger is **REMOVED entirely** — a present-but-tiny-revenue + large-loss anomaly is a financial-shape signal, not an identity error, and conflating the two surfaced a misleading "wrong entity" reason-string on the *right* company (STSS/MVIS/TIPT in iteration 2 gated on `wrong_entity_suspected` when the accurate cause was an extreme loss-to-revenue ratio). That tail is now carried by the tiered `low_revenue_loss_ratio` / `low_revenue_loss_ratio_extreme` labels below — which preserve the block on STSS/MVIS/TIPT with the correct label instead of the misleading "wrong entity."
- **`debt_truncation_suspected` (same spirit).** Do NOT relabel a real producer's partial/stale XBRL debt tag as truncation when the debt magnitudes are plausible relative to the balance sheet; reserve it for genuinely truncated/implausible debt numerics.

**Tiered low-revenue-loss labels (A4, iteration 3) — advisory at the low tier, gating at the extreme tier:**

- **`low_revenue_loss_ratio` (bool) — advisory tier, `ratio > 2`.** Fires when revenue is present but small AND `|net_income|/revenue > 2.0` — the early/pre-revenue resource pattern (a large loss against tiny revenue). It is a **data-quality label surfaced in `data_quality` only**; it is NOT in the `buy_eligible` composite and does NOT by itself flip `buy_eligible` or downgrade a rating (unchanged from iteration 2). Names exhibiting this pattern stay blocked by their own null/negative-FCF MoS (`margin_of_safety_pct` null) exactly as before — the relabel changes the *explanation*, not the disposition. Surface it in the Dim-1 / §6 data-quality line so a PM reads "early/pre-revenue, large loss vs tiny revenue" rather than the misleading "wrong entity."
- **`low_revenue_loss_ratio_extreme` (bool) — gating tier, `ratio > 20`.** When the loss-to-revenue ratio is *extreme* (`|net_income|/revenue > 20`), `deepdive_data.py` ALSO emits `low_revenue_loss_ratio_extreme`, which IS ANDed into `buy_eligible` (forcing `buy_eligible = false`). This is the term that preserves the iteration-2 block on STSS (ratio ≈ 1,384x), MVIS (≈ 78.6x), and TIPT (≈ 71.6x) — names that previously gated on the misleading `wrong_entity_suspected`. The extreme tier provides the *correct* gating reason (`low_revenue_loss_ratio_extreme`) for the same outcome. The non-extreme `low_revenue_loss_ratio` stays label-only; only the extreme tier gates.

**Insurance-subsidiary holdco routing (A3, iteration 3) — `insurance_concepts_present` (bool):**

- **`insurance_concepts_present` (bool).** `deepdive_data.py` emits this when insurance XBRL concepts are present in the filing — e.g. `PremiumsEarned`, policy reserves, `LossesAndLossAdjustmentExpense`, `PolicyholderFunds`. It is ANDed into `buy_eligible` (forcing `buy_eligible = false`) and routes the company like `financial_sic` (NAV / abstain, never an fcf_cap BUY). It closes the latent hole exposed by BOC (Boston Omaha, SIC 6510 — a real-estate operator prefix NOT in the financial-SIC list, but owning a surety-insurance subsidiary): such an insurance-subsidiary holdco on a non-financial SIC otherwise routes to fcf_cap and would slip the financial gate on positive FCF. `insurance_concepts_present` catches it on the *presence of insurance accounting* rather than on the SIC, so a positive-FCF insurance holdco is now treated as financial regardless of its registered SIC.

**Second-source sanity band (P7, iteration 5) — `cross_source_mismatch` (bool), a DATA-INTEGRITY gate:**

- **`cross_source_mismatch` (bool).** Every other `buy_eligible` term above is an *internal-consistency* heuristic on a single feed — SEC XBRL — so all of them are structurally blind to a corruption that looks internally reasonable but is externally wrong (HCI's plausible $246M revenue behind a failed SIC fetch → +118% pseudo-BUY; AL's sub-entity $331M revenue + 200-share tag; HRI's truncated $11M debt). P7 adds the FIRST external check: on deepdive (survivors-only — at the deepdive level, after `cheap_pass`, to respect EDGAR/yfinance rate limits), `deepdive_data.py` fetches a SECOND, INDEPENDENT source for `total_debt` / `revenue` / `shares_outstanding` from **yfinance** (already a dependency, used until now only for the mktcap denominator — `Ticker(t).info` totalDebt/totalRevenue/sharesOutstanding, falling back to `.balance_sheet` / `.financials` / `.get_shares_full`) and compares it to the SEC-XBRL-derived `latest_total_debt` / `latest_revenue` / `latest_shares`. It emits three fields into the deepdive `derived` block, which `valuation.py` reads:
  - `cross_source_checked` (bool) — True if at least one field had BOTH a SEC and a yfinance value to compare.
  - `cross_source_mismatch` (bool) — True if, for ANY field where both values are present and non-trivial (`abs > $1M` floor), `max(a,b)/min(a,b) > 2.5` (a gross disagreement that means the single SEC value cannot be trusted).
  - `cross_source_detail` (str) — which field(s) disagreed, both values, and the ratio.
- **It is a DATA-INTEGRITY gate, not a signal — and it is therefore FINE for it to gate.** When `cross_source_mismatch == true`, `valuation.py` ANDs `(not cross_source_mismatch)` into `buy_eligible` (forcing `buy_eligible = false`), appends `"cross_source_mismatch"` to `buy_ineligible_reasons`, and appends `cross_source_mismatch:<detail>` to `data_quality`. A would-be static-MoS BUY is downgraded **BUY → WATCH** (AVOID if a hard kill-flag is also present), same downgrade-only discipline as the other composite terms. This is the deliberate, correct distinction from the iteration-4 firewalled diagnostic `signals` layer: the iter4 signals (P15/P16/P17) are between-filings *market* signals that may NEVER originate or up-weight a BUY and are firewalled out of the decision path; P7 is about *trusting the input numbers themselves*, so blocking BUY on a corrupted input is exactly what a data-integrity gate should do. P7 lives in `derived` (read by the decision path), NOT in the firewalled `signals` namespace.
- **Guard — it can NEVER block on an absent second source.** If yfinance is unavailable, returns None, or yields no comparable field (no ticker, import error, network error, all-null `.info`, every field one-sided or sub-floor), `cross_source_checked = false` and `cross_source_mismatch = false`, so the name flows through the gates exactly as before P7. The fetch is guarded end-to-end (returns None on ANY failure, never raises) and `_cross_source_check` is a pure comparator — the diagnostic check can never take down the T1 pipeline or false-block a name on missing data. Per the data contract, an absent second source is never a block.

**Degenerate-base / current-loss-masking veto (v0.3.1 #1) — `normalization_masks_current_loss` (bool):**

- **The hole it closes.** The A1 degenerate-base guard (`0 < contamination_ratio`) deliberately silences BOTH cyclical vetoes — `peak_contamination_flag` and `fundamental_decline_flag` — when the normalization base is negative or `contamination_ratio < 0`, because "well below a POSITIVE 5-yr average" is the only interpretable semantics for those vetoes. But the trailing-5yr-average normalization can still emit a **positive `normalized_fcf`** off a series whose latest period is in deep cash burn (a divested-segment stub, a one-time settlement, a continuing-ops remnant). With both cyclical vetoes silenced and a positive normalized FCF, the MoS goes mechanically positive and `buy_eligible` stays True — a phantom BUY no mechanical guard catches. **Worked example (TUSK, Mammoth Energy, oilsvc):** Mammoth divested its frac/sand/infra units in 2025, leaving a $44.3M continuing-ops stub; `latest_ocf = −$18.6M`, `latest_fcf = −$89.1M`, EBITDA `= −$29.7M`, yet trailing-avg `normalized_fcf > 0` produced a **+55.1% mechanical BUY** that only the human adversarial layer caught.
- **The flag.** `deepdive_data.py` emits `normalization_masks_current_loss = (normalized_fcf > 0) AND (latest_ocf < 0 OR latest_fcf < 0 OR contamination_ratio < 0)`. In words: the trailing average is masking current cash burn / a divested-segment stub — the normalized FCF the MoS rests on is not the cash the company is actually generating now.
- **The gate.** `valuation.py` ANDs `(not normalization_masks_current_loss)` into `buy_eligible` (forcing `buy_eligible = false`), appends `"normalization_masks_current_loss"` to `buy_ineligible_reasons`, appends a `normalization_masks_current_loss:…` detail string to `data_quality`, and downgrades a would-be BUY to **WATCH** (to **AVOID** if combined with a hard kill-flag) — the same downgrade-only discipline as `fundamental_decline_flag` / `peak_contamination_flag`. It is a measured-data veto, never a forward forecast, and it can ONLY lower a rating, never raise one. It is the v0.3.1 mechanical replacement for the human catch on TUSK: the machine now downgrades the degenerate-base phantom BUY that the silenced cyclical vetoes miss.

**Null-MoS eligibility guard (v0.3.1 #9) — `not_assessable_no_intrinsic_band`:**

- **The footgun it closes.** `buy_eligible` could previously be True-by-absence-of-data: a foreign filer / pre-revenue name with no intrinsic band yields `margin_of_safety_pct = None`, yet none of the blocking guards fired, so `buy_eligible` stayed True even though no MoS exists to back a BUY (DAVA, TV, QNC, BTQ, NUCL, RVSN, CVV, ELMT, NABL). The only thing that stopped a BUY was the downstream numeric `MoS ≥ 30` clause — `buy_eligible == true` alongside `MoS = null` is misleading to a human reader and is one mechanical edit away from a false BUY.
- **The gate.** `valuation.py` now requires the **active** MoS (the `margin_of_safety_pct` when `mos_basis == "fcf_cap"`, otherwise the `nav_margin_of_safety_pct`) to be non-null. When the active MoS is `None`, it appends `"not_assessable_no_intrinsic_band"` to `buy_ineligible_reasons`, forcing `buy_eligible = false`. **`buy_eligible` may NEVER be True with a null MoS.** This makes the eligibility composite self-consistent with the BUY trigger's MoS clause rather than relying on it as a backstop. (`mos_basis == "abstain"` continues to take no BUY/AVOID on MoS at all — see the abstain branch below.)

`buy_eligible` is a **necessary, not sufficient** condition: clearing it does not produce a BUY; the MoS / catalyst paths below still must independently pass.

### Three-Way `mos_basis` Decision Tree

#### `mos_basis = "fcf_cap"` — Normal operating company

**BUY requires ALL of the following:**
1. `margin_of_safety_pct ≥ 30%` (conservative intrinsic value band low-end exceeds market cap by ≥30%)
2. **Zero effective kill-flags** — kill-flag count must be 0. `going_concern`, `death_spiral`, and `material_weakness` all block BUY with no exception. There is no "one kill-flag of modest severity" escape hatch.
3. **No T3-load-bearing thesis** — the primary BUY argument must rest on T1 evidence (audited financials, Form 4, 10-K); T3-only claims (management guidance, PR) may not be load-bearing for the rating
4. **`buy_eligible == true`** — the mechanical eligibility gate above must pass. In particular this means `concentration_flag != "kill"`, `fundamental_decline_flag == false`, and `cross_source_mismatch == false`; a `kill` concentration, a fundamental-decline flag, or a >2.5x second-source disagreement (P7) forces `buy_eligible = false` and BUY may not fire on MoS regardless of how large the MoS is — a cross-source mismatch specifically means the SEC input behind the MoS cannot be trusted, so the large MoS is itself suspect. If `buy_eligible` is false, record `buy_ineligible_reasons` on the BUY-trigger line.
5. Confidence is capped by valuation `data_quality` robustness: each data-quality flag that is load-bearing for the MoS computation (e.g., `capex_unavailable_fcf_uses_ocf_proxy`, `normalized_fcf_unavailable`) reduces confidence by 10 percentage points each, floor 30%

**Downgrade rule (deterministic, downgrade-only):** if `margin_of_safety_pct ≥ 30%` and kill-flags = 0 but `buy_eligible == false`, the rating is **WATCH**, not BUY — except that if a hard kill-flag is also present the rating is **AVOID**. Specifically `fundamental_decline_flag == true` OR `peak_contamination_flag == true` OR `normalization_masks_current_loss == true` (v0.3.1 #1) OR `concentration_flag == "kill"` downgrades a would-be BUY to **WATCH** (to **AVOID** if combined with any `going_concern`/`death_spiral`/`material_weakness`). This is the melting-ice-cube defense (and, for `normalization_masks_current_loss`, the degenerate-base / divested-stub defense); it can only lower a rating, never raise one.

If `margin_of_safety_pct < 30%`, the company **cannot be rated BUY on MoS** — it is WATCH if fundamentals are clean, AVOID if kill-flags are present. The "cyclical turn not yet realized in T1" reasoning must NOT be used to veto a BUY when static MoS is already ≥30% — that perpetual-veto was the run-3 calibration bug; the threshold already uses conservative normalized FCF, so a realized turn that lifts MoS to ≥30% is sufficient.

**Narrow MECHANICAL carve-out to the perpetual-veto prohibition (P6).** The perpetual-veto ban above prohibits exactly one thing: the *qualitative forward judgment* "the cyclical turn has not yet been realized in T1, therefore I won't buy." That qualitative veto remains banned. It does NOT prohibit the deterministic, magnitude-based `fundamental_decline_flag` computed mechanically in the deepdive `derived` block. That flag fires only when ALL THREE conditions hold simultaneously:
- `rev_slope_sign < 0` — the multiyear revenue series is sloping down (decline magnitude, not a single point-to-point dip);
- `latest_below_avg == true` — the latest normalization base is below its own trailing average (the company is below its own normal, not merely below a peer); AND
- `0 < contamination_ratio < 1.0` — `contamination_ratio = latest normalization-base / 5yr-avg`, so the normalized FCF the MoS rests on is contaminated by higher prior-period values (the melting-ice-cube signature; SIGA contamination ≈ 0.68). The lower bound `0 <` (A1, iteration 3) rejects degenerate/negative normalization bases so the upper-bound test cannot pass trivially on a negative ratio.

When `fundamental_decline_flag == true`, the would-be BUY is downgraded to WATCH (deterministic, downgrade-only) even at MoS ≥ 30% — because the MoS is built on a normalization base the company is no longer earning. This is a measured-data veto, NOT the forward-looking cyclical-turn judgment the prohibition bans. The distinction is exact: the banned veto asks the analyst to *predict* that a future turn will not arrive; this carve-out only observes that the historical series already declined AND the latest period sits below its own average AND the normalization average is peak-contaminated. No qualitative forecast is permitted to extend it.

**Degenerate-base guard (A1, iteration 3) — the `contamination_ratio` lower bound.** Both decline vetoes require a *positive* normalization base. `contamination_ratio = latest normalization-base / 5yr-avg`; when the normalization base (or the average) is negative, this ratio goes negative, and a bare upper-bound test (`< 1.0` or `< 0.8`) passes *trivially* for any negative value — letting the flag fire on a degenerate input whose "deeply below average" semantics do not actually hold. Iteration 3 therefore ANDs a lower bound `0 < contamination_ratio` into both conditions:
- `fundamental_decline_flag` requires `0 < contamination_ratio < 1.0` (was `contamination_ratio < 1.0`);
- `peak_contamination_flag` requires `0 < contamination_ratio < 0.8` (was `contamination_ratio < 0.8`).

A NEGATIVE or zero contamination_ratio (negative/degenerate FCF-normalization base) can therefore NO LONGER trip either veto. **Worked example (BWIN, title-insurance):** BWIN fired `peak_contamination_flag` in iteration 2 at `contamination_ratio = −2.4618` — a negative normalization base, not a peak-contaminated one — which made the veto magnitude uninterpretable (outcome was still correct only because BWIN was independently blocked by `financial_sic` + `debt_truncation`). With the `0 <` lower bound the flag is now **False** for BWIN; degenerate negative bases fall through to the null/negative-FCF MoS path instead of mis-tripping a value-trap veto.

**V-shape sibling veto — `peak_contamination_flag` (P-A, mechanical, downgrade-only).** `fundamental_decline_flag` is gated on `rev_slope_sign < 0` and therefore MISSES the trough→peak→rollover V-shape: a company whose revenue troughed, spiked to a peak, then rolled over still has an *upward* whole-window linear fit (`rev_slope_sign = +1`), so the AND-of-three never fires even though the normalization base is peak-contaminated and the company has tipped back into losses. `peak_contamination_flag` is the independent catch. It fires when ALL THREE hold:
- `0 < contamination_ratio < 0.8` — the latest normalization base is positive but well below the 5-yr average (deeper than the `< 1.0` threshold `fundamental_decline_flag` uses, because here the slope offers no corroboration). The lower bound `0 <` (A1, iteration 3) is the degenerate-base guard: a negative/zero contamination_ratio (negative FCF-normalization base) can NO LONGER trip the veto, because "well below a POSITIVE 5-yr average" is the intended semantics and a negative base does not satisfy it (BWIN fired at `cr = −2.4618` in iteration 2 — now False);
- `latest_below_avg == true` — the latest period sits below its own trailing average; AND
- `latest_net_income < 0` — the company is now loss-making.

Critically, `peak_contamination_flag` is **independent of `rev_slope_sign`** — it fires regardless of slope direction, which is exactly why it catches what `fundamental_decline_flag` cannot. When `peak_contamination_flag == true` it is ANDed into `buy_eligible` (forcing `buy_eligible = false`) and downgrades a would-be BUY to **WATCH** even at MoS ≥ 30% (to **AVOID** if combined with a hard kill-flag) — same downgrade-only discipline as `fundamental_decline_flag`. It is likewise a measured-data veto, not a forward forecast. **Worked example (NRP, Natural Resource Partners):** revenue troughed 2020 ($120M) → peaked 2022 ($307M) → rolled over to 2024 ($232M), so `rev_slope_sign = +1` and `fundamental_decline_flag = false`; but `contamination_ratio = 0.7445`, `latest_below_avg = true`, `latest_net_income = −$84.8M` → `peak_contamination_flag = true`. NRP was a clean *mechanical* BUY (`buy_eligible = true`, MoS +36.8%) caught in iteration 1 only by analyst judgment; the flag now moves that catch onto the machine and downgrades it to WATCH.

#### `mos_basis = "nav"` — Asset-heavy company (finance, lessor, etc.)

**BUY requires ALL of the following:**
1. `nav_margin_of_safety_pct ≥ 30%`
2. Zero effective kill-flags (same zero-tolerance as fcf_cap; no exceptions)
3. No T3-load-bearing thesis
4. **`buy_eligible == true`** — the mechanical eligibility gate applies to the NAV path identically. A `concentration_flag == "kill"`, `fundamental_decline_flag == true`, `peak_contamination_flag == true`, `insurance_concepts_present == true` (A3), `low_revenue_loss_ratio_extreme == true` (A4), or `normalization_masks_current_loss == true` (v0.3.1 #1) forces `buy_eligible = false` and downgrades a would-be NAV BUY to WATCH (AVOID if also a hard kill-flag); record `buy_ineligible_reasons` on the BUY-trigger line. On the NAV path the active MoS for the #9 null-MoS guard is `nav_margin_of_safety_pct` — a null NAV MoS forces `buy_eligible = false` with `not_assessable_no_intrinsic_band`. **Insurance-subsidiary holdcos (A3):** when `insurance_concepts_present == true`, the company is routed here (NAV / abstain) like a financial-SIC name even if its registered SIC is non-financial (e.g. BOC, SIC-65) — never fcf_cap.
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
4. **Perpetual-veto prohibition (qualitative only).** The *qualitative forward* argument "cyclical turn not yet realized in T1 → cannot buy" is explicitly prohibited as a veto when `margin_of_safety_pct ≥ 30%`. Normalized FCF already accounts for cycle conservatism. Applying an additional qualitative veto on top of the conservative metric defeats the mechanical trigger and recreates the run-3 calibration gap. **Exception (carve-out):** this prohibition does NOT cover the deterministic, magnitude-based `fundamental_decline_flag` (rev_slope_sign<0 AND 0<contamination_ratio<1.0 AND latest_below_avg) NOR its V-shape sibling `peak_contamination_flag` (0<contamination_ratio<0.8 AND latest_below_avg AND latest_net_income<0, independent of rev_slope_sign). Both are measured-data downgrades — they observe a realized decline / peak-contaminated normalization base, not a forward prediction — and both are permitted to downgrade BUY→WATCH even at MoS ≥ 30%.

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
| `fundamental_decline_flag == true` (`rev_slope_sign<0` AND `0<contamination_ratio<1.0` AND `latest_below_avg`) | Forces `buy_eligible = false` → **downgrades would-be BUY to WATCH** even at MoS ≥ 30% (mechanical melting-ice-cube veto; AVOID if hard kill-flag also present). The `0<` lower bound (A1) rejects degenerate/negative normalization bases |
| `peak_contamination_flag == true` (`0<contamination_ratio<0.8` AND `latest_below_avg` AND `latest_net_income<0`; **independent of `rev_slope_sign`**) | Forces `buy_eligible = false` → **downgrades would-be BUY to WATCH** even at MoS ≥ 30% (V-shape value-trap veto — catches trough→peak→rollover that `fundamental_decline_flag` misses; AVOID if hard kill-flag also present). The `0<` lower bound (A1) rejects degenerate/negative bases (BWIN at `cr=−2.4618` no longer fires) |
| `low_revenue_loss_ratio == true` (revenue present-but-small AND `\|net_income\|/revenue > 2.0`) | **Data-quality label only** — surfaced in `data_quality`; does NOT gate `buy_eligible` or change the rating. Replaces the prior `wrong_entity_suspected` misfire for the early/pre-revenue resource pattern |
| `low_revenue_loss_ratio_extreme == true` (revenue present-but-small AND `\|net_income\|/revenue > 20`) | Forces `buy_eligible = false` → **blocks BUY** (A4). The gating extreme tier of the loss-to-revenue label; preserves the block on STSS/MVIS/TIPT with the correct reason-string instead of the misleading `wrong_entity_suspected` |
| `insurance_concepts_present == true` (insurance XBRL concepts present — `PremiumsEarned` / policy reserves / `LossesAndLossAdjustmentExpense` / `PolicyholderFunds`) | Forces `buy_eligible = false` → routed like `financial_sic` (NAV / abstain, never fcf_cap BUY) (A3). Catches insurance-subsidiary holdcos on non-financial SICs (e.g. BOC, SIC-65) that would otherwise slip the financial gate on positive FCF |
| `cross_source_mismatch == true` (P7 — `max(SEC,yfinance)/min > 2.5` on debt, revenue, OR shares; both present & `> $1M`) | Forces `buy_eligible = false` → **blocks BUY** (downgrade to WATCH; AVOID if hard kill-flag also present). **DATA-INTEGRITY gate** (distinct from the iter4 firewalled diagnostic `signals` — this one legitimately gates because a corrupted single-source SEC input cannot back a tradeable MoS, it is not a market signal). Survivors-only (deepdive level). `cross_source_checked == false` (yfinance unavailable / no comparable field) NEVER blocks |
| `normalization_masks_current_loss == true` (v0.3.1 #1 — `normalized_fcf > 0` AND (`latest_ocf < 0` OR `latest_fcf < 0` OR `contamination_ratio < 0`)) | Forces `buy_eligible = false` → **downgrades would-be BUY to WATCH** even at MoS ≥ 30% (AVOID if hard kill-flag also present). Degenerate-base / divested-stub veto: the trailing-avg normalized FCF is masking current cash burn, so the positive MoS is phantom. Catches the TUSK +55.1% hole the A1-silenced cyclical vetoes (`peak_contamination_flag`/`fundamental_decline_flag`) miss; measured-data downgrade, never raises a rating |
| active MoS is `None` (`margin_of_safety_pct` null on `fcf_cap`, or `nav_margin_of_safety_pct` null on `nav`) | Forces `buy_eligible = false` with reason `not_assessable_no_intrinsic_band` (v0.3.1 #9). **`buy_eligible` may NEVER be True with a null MoS** — closes the True-by-absence-of-data footgun (DAVA/TV/QNC/BTQ). `mos_basis == "abstain"` is unaffected (no BUY/AVOID on MoS at all) |
| `wrong_entity_suspected == true` (A4-refined: `shares_outstanding < 1000` OR ticker absent from `company_tickers.json` OR CIK mismatch — the `\|net_income\|/revenue` trigger is REMOVED) | Forces `buy_eligible = false` → **blocks BUY**. Now strictly a unit-mistag / wrong-CIK identity error; the present-but-tiny-revenue tail moved to `low_revenue_loss_ratio` (advisory) / `low_revenue_loss_ratio_extreme` (gating) |
| T1-evidenced catalyst matching enumerated category (a)–(d) AND dated trigger AND kill-flags = 0 | **WATCH-with-catalyst** (catalyst MoS-waiver FROZEN, iteration 1) — does NOT lift sub-30% MoS to BUY; `catalyst` field must be populated with category, T1 source, dated trigger |
| `margin_of_safety_pct < 30%` with no catalyst | Cannot rate BUY on MoS basis |
| "Cyclical turn not yet realized in T1" used as QUALITATIVE forward veto when MoS ≥ 30% | **Prohibited** — perpetual-veto; normalized FCF already accounts for cycle conservatism. (Distinct from the mechanical `fundamental_decline_flag` and `peak_contamination_flag` carve-outs, which ARE permitted.) |
| Any key claim rests solely on T3 evidence | Cannot rate BUY |
| Any kill-flag present (`going_concern`, `death_spiral`, or `material_weakness`) | **Blocks BUY** — zero-tolerance, no adjudication escape hatch. `kill-flag count ≥ 2` → Default AVOID. |
| `death_spiral` convertible detected | Dim 1 capped at 1; composite max = 2 |
| `material_weakness` in ICFR | Dim 1 (financial quality) capped at 2 |
| Net income driven by deferred tax release (not OCF) | Score Dim 1 on OCF only; note the driver |
| AR growing faster than revenue | Required red flag note in Dim 1 basis |
| S-3 shelf / ATM program active with < 4 quarters of runway | Dim 1 score = 1 |
| Single customer > 40% of revenue OR single program > 60% (`concentration_flag == "kill"`) | Dim 3 (growth / unit economics) capped at 2; also forces `buy_eligible = false` (blocks BUY) |
| Single customer / program in the 40–60% band (`concentration_flag == "watch"`) | Surface in Dim 3 basis + §5 kill-flag review; does not block BUY by itself |
| `concentration_unquantified == true` (text customer-concentration flag True AND magnitude `concentration_flag == null`) | **Advisory only (A2)** — surface in `data_quality` + Dim 3 basis + §5; analyst must read the 10-K concentration footnote directly. Does NOT gate `buy_eligible` or cap any dimension by itself (closes the text-only / pre-XBRL SIGA-class blind spot) |
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
