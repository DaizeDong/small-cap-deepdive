---
name: small-cap-deepdive
description: "Use to research neglected small-cap/microcap US equities by THEME or TICKER: SEC-filing universe, de-risk, falsifiable deep-dive DD, rank. NOT large-cap/quant/trading."
allowed-tools: Read, Glob, Grep, Bash, Agent, Skill, WebSearch, WebFetch
---

# small-cap-deepdive

A disciplined orchestration layer for neglected small-cap equity research. It does **only what no
plain web-search or LLM narrative pass can do**: enumerate the SEC-filing universe for a theme,
apply hard mechanical kill-flags before any qualitative judgment begins, run forced disconfirmation,
and produce a scored, ranked shortlist of candidates worth genuine attention.

---

## World-View (read before interpreting any output)

Four commitments govern every run. Full exposition and empirical citations: `reference/cognitive-priors.md`.

**1. 被忽视 ≠ 被低估 (Neglected does not equal undervalued).**
A company receiving zero analyst coverage has cleared a necessary but not sufficient condition.
Neglect is priced into small-caps efficiently — what creates inefficiency is delayed information
diffusion around a real fundamental change. Every output of this skill is a shortlist of companies
worth investigating, not a buy list.

**2. 热点主题 = 赌场 (Hot themes are the casino, not the edge).**
By the time a theme has a branded ETF and retail attention, the alpha has been captured.
Thematic ETF data (Ben-David et al. 2023) shows approximately -6% risk-adjusted annual returns
in the 5 years post-launch for themes that entered at peak popularity. The skill's value in a hot
theme is separating the handful of true industrial beneficiaries from the concept-players who
mentioned the theme keyword once in their investor-day deck.

**3. Edge = 纪律，不是叙事 (Edge is mechanical discipline, not narrative synthesis).**
The skill's advantage is systematic coverage (more companies than any human can read in the time
budget), consistent kill-flag application across all candidates, and elimination of human attention
bias. It has no advantage in judging founding teams, predicting market narrative resonance, or
forecasting macro catalysts. Do not ask it to do those things.

**4. 产出是避雷扫描器，不是买入清单 (Output is a landmine-scanner, not a buy list).**
A score-5 company at the top of the ranked output means it survived all kill flags, has real theme
exposure, and warrants full human due diligence. It does not mean buy it. The primary value of
this skill is in what it eliminates — the going-concern candidates, the death-spiral diluters, the
disclosure non-filers — before any analyst time is spent.

---

## Four Entry Workflows

> **Open a run batch first (all entries).** Before the first tool call of any run, open a
> timestamped batch so this run's candidates / cheappass / deepdive / valuation / report files
> stay together and runs stay comparable across skill versions:
> ```bash
> export SMALLCAP_RUN=$(python tools/new_run.py --label <theme-or-event>)
> # → all outputs now land in reports/smallcap/<date>_<label>/ with a _run.json manifest
> #   (records date, skill git commit, and the valuation config snapshot)
> ```
> Leaving `SMALLCAP_RUN` unset writes flat to `reports/smallcap/` (legacy behaviour).
>
> **Concurrency isolation (v0.3.2 #10).** Multiple theme runs may execute concurrently (the
> coverage harness fans out dozens of agents at once). Two collisions were closed: (a) the
> run-state file is now **PID-unique / per-`SMALLCAP_RUN`** — no single shared `/tmp` path that
> concurrent agents clobber; and (b) the SIC-reverse-recall sidecar is written **namespaced under
> the active run/slug** (into the current `SMALLCAP_RUN` batch dir, slug-prefixed), never a fixed
> cross-theme path — so one theme's floor output can never land in another theme's run dir. See the
> SIC reverse-recall floor note under "Two-Stage Precision Gate" and `tools/_common.py` /
> `tools/new_run.py` / `tools/filter_by_sic.py`.

### Entry 1 — `theme <主题>` (thematic universe screen)

**Use when:** you have an investment theme and want a ranked shortlist of small-cap pure-plays.

**Natural-language orchestration (primary path, works in any Claude Code session):**

1. **Universe enumeration.** Run `tools/discover.py --theme "<主题>"` to query SEC EDGAR full-text
   search and return candidate tickers. This over-recalls by design — expect hundreds of results.

2. **Two-stage precision gate (mandatory — see next section).** Pass the raw list through
   `tools/filter_by_sic.py` (Gate 1, coarse SIC exclusion **+ SIC reverse-recall floor**: for a
   theme with dedicated SIC code(s), enumerate ALL registrants in that SIC via EDGAR browse-by-SIC /
   EFTS `sic` filter and UNION with the FTS recall so SIC acts as a recall floor, not only a
   precision exclude — P8), then run the LLM theme-fit gate (Gate 2) on surviving candidates to
   classify each as `pure_play / partial / misrecall`. Drop `misrecall`. Retain `pure_play` and
   `partial` for deep-dive.

3. **Mechanical de-risk.** For each retained candidate, run `tools/cheap_pass.py --ticker <T>`.
   Any candidate that returns a hard kill-flag (`going_concern`, `death_spiral`, `material_weakness`
   in the most recent filing period) is eliminated. Do not deepdive eliminated candidates.

4. **Deep-dive.** For surviving candidates, run `tools/deepdive_data.py --ticker <T>` to retrieve
   the full financial series, insider trade record, and disclosure timeline. Spawn one Agent per
   candidate, instructing it to apply the 7-dimension scorecard from `reference/judgment-rubric.md`
   — preamble (base-rate anchor + disconfirmation search + staleness check) before any scoring.

5. **Rank.** Run `tools/rank.py` on the scored outputs to produce the ranked shortlist.
   Report includes: gate survival counts, kill-flag eliminations, score distribution,
   top candidates with dimension scores, and explicit coverage gaps.

**Optional accelerator:** when the Workflow tool is available in the session, `workflows/theme-fit-gate.js`
automates Gate 2 fan-out and `workflows/deepdive-fanout.js` automates the parallel deep-dive step.
These are convenience wrappers — the natural-language orchestration above is the primary and always-runnable path.

---

### Entry 2 — `ticker <代码> [--theme X]` (single-company deep-dive)

**Use when:** you have a specific ticker and want a rigorous, falsifiable deep-dive report.
Optionally pass `--theme X` to anchor the theme-fit scoring.

**Natural-language orchestration:**

1. **Mechanical de-risk first.** Run `tools/cheap_pass.py --ticker <代码>`. If any hard kill-flag
   fires, report the flag and stop — do not proceed to full deep-dive.

2. **Data pull.** Run `tools/deepdive_data.py --ticker <代码>` to retrieve financial series,
   insider trades, filing timeline, and kill-flag detail.

3. **Judgment pass.** Apply the 7-dimension scorecard from `reference/judgment-rubric.md` in full.
   Required preamble: (a) state the reference-class base rates from `reference/cognitive-priors.md`;
   (b) run disconfirmation WebSearch; (c) check data staleness.

4. **Output.** Single-company report with dimension scores, evidence tier per claim, kill-flag
   detail, disconfirmation findings, and a composite rating with the hard-rule ceiling applied
   (see Rating Hard-Rules below).

**Optional accelerator:** `workflows/deepdive-fanout.js` supports single-ticker mode.

---

### Entry 3 — `rank` (re-rank existing scored outputs)

**Use when:** you have already run a theme screen and want to re-sort or re-weight an existing
scored candidate set without re-running discovery or deep-dive.

**Natural-language orchestration:**

1. Locate the existing scored output directory from a prior `theme` run.
2. Run `tools/rank.py [--slug <slug>] [--input <dir>]` to produce a ranked table.
3. Report the ranking with kill-flag eliminations and explicit coverage gaps.

---

### Entry 4 — `events <spinoffs|insider-clusters>` (event-driven discovery)

**Use when:** you want to hunt for mis-priced small-caps via a structural catalyst rather than a
theme keyword.  Two event axes are supported; both are structurally high-precision (no
theme-fit gate needed — form-type enumeration replaces keyword over-recall):

- `spinoffs` — enumerate recent **Form 10-12B / 10-12B/A** registrations (spinoff / carve-out).
  Catalyst: passive index-fund holders of the parent are forced to sell the spun-off child if it
  falls outside their index mandate.  This forced-selling window is the mis-pricing mechanism.

- `insider-clusters` — enumerate recent **cluster open-market insider buys** from
  openinsider.com.  Catalyst: multiple insiders buying at market price within a short window
  is the strongest available management-conviction signal (Form 4, open-market cash only).

**Rationale and honest caveats:** `reference/event-driven.md`.

**Natural-language orchestration:**

1. **Enumerate the event.** Run `tools/discover_events.py --spinoffs` or
   `tools/discover_events.py --insider-clusters`.
   Output: `reports/smallcap/candidates_event_<mode>_<date>.json` — same shape as
   theme-mode `candidates_<slug>.json`.

2. **Kill-flag scan (mandatory).** Run `tools/cheap_pass.py --universe <candidates_json>`.
   Kill-flags (`going_concern`, `death_spiral`, `material_weakness`) apply identically to
   event candidates.  A compelling catalyst does not excuse a going-concern filing.

3. **Deep-dive data pull.** Run `tools/deepdive_data.py --candidates <candidates_json>`.
   **Band guard (four explicit bands — C3):**
   - `band="deep"` (mktcap < market_cap_max): **process** — full deep-dive.
   - `band="watch"` (market_cap_max..watch_band_max): **skip** — surfaced separately for human review only; not deep-dived.
   - `band="large"` (> watch_band_max): **skip** — out of scope.
   - `band="unknown"` (mktcap unavailable / pre-listing): **process** — likely a pre-listing spinoff, highest-catalyst cohort; worth the deep-dive.

4. **Rank and rate.** Spawn one Agent per `band="deep"` or `band="unknown"` survivor, applying
   `reference/judgment-rubric.md` in full (including preamble: base-rate anchor +
   disconfirmation search + valuation + MoS check).
   The catalyst field in each record is pre-populated — the rubric's catalyst modifier
   (categories a and b) maps directly to spinoff and insider-cluster events respectively.
   **Catalyst re-verify (mandatory):** the pre-populated `catalyst` field is a
   discovery-stage hint (T2), NOT rubric-compliant evidence.  The agent MUST independently
   verify the forced-trading mechanism + T1 source (EDGAR 10-12B / Form 4) and re-populate
   the rubric catalyst field per `judgment-rubric.md`'s five-requirement checklist.
   **Catalyst MoS-waiver FROZEN (iteration 1):** even a fully re-verified catalyst yields
   **WATCH-with-catalyst, not BUY** — it no longer waives the MoS threshold. A BUY here still
   requires the MoS / NAV path AND `buy_eligible == true`. (Freeze is temporary, pending
   mechanism-verification + per-category Brier in iteration 2.)
   **No theme-fit gate:** skip Gate 1 (SIC) and Gate 2 (LLM theme-fit) — form-type
   precision replaces keyword precision; every record is a valid event by construction.

5. **Output.** Ranked shortlist per `tools/rank.py --slug event_<mode>`.

---

## Two-Stage Precision Gate (Mandatory in Theme Flow)

> Full spec: `reference/discovery-engine.md`. This section is a navigational summary only.

Single-keyword FTS over-recalls severely. Measured production result: 192 raw candidates for
"AI agent" → 13 true theme members after the gate (6.8% precision; 94% false-positives).

**The canonical cautionary case:** the keyword `refractory` was used for a railcar insulation
theme. In oncology, "refractory" means treatment-resistant cancer — the single-keyword search
swept the entire biotech sector. Zero of these were railcar companies. Only the SIC coarse gate
and LLM theme-fit gate cleared the field. Skipping either gate would have sent the entire biotech
sector to the deep-dive queue.

**Gate 1 — SIC Coarse Exclusion + Reverse-Recall Floor** (`tools/filter_by_sic.py`)
Drops companies whose SIC code definitively places them outside plausible theme membership.
Hard-coded default exclusion blocks (pharma, medical devices, finance, retail, toys) are in
`discovery-engine.md §Gate 1`. Override per-theme via `sic_exclusion_blocks` in `config.json`.
Companies with no SIC on file: **keep** for Gate 2 — do not auto-exclude.

**SIC reverse-recall floor (P8, iteration 3).** For a theme that maps to dedicated SIC code(s),
SIC is no longer used *only* as a precision coarse-exclude — it is also a recall **FLOOR**.
`filter_by_sic.py` ENUMERATES every registrant in the theme's dedicated SIC code(s) via EDGAR
browse-by-SIC / EFTS `sic` filter, and UNIONs that set with the FTS keyword recall. This guarantees
that a true member with the right SIC but an unlucky keyword phrasing cannot be lost by FTS recall
alone — the SIC enumeration backstops it. The union is the deep-dive universe (still passed through
Gate 2 for theme-fit). **FTS top-1000 cap warning:** EDGAR full-text search caps at 1000 hits, so
on a broad keyword the FTS arm may be truncated; the SIC reverse-recall arm is the floor that keeps
recall from collapsing under that cap, and `track_forward` warns when the FTS arm hit the cap.

**Sidecar isolation (v0.3.2 #10).** The SIC-floor sidecar file (the enumerated SIC candidate set
the floor writes alongside the FTS recall) is namespaced under the **active run/slug** — written
into the current `SMALLCAP_RUN` batch dir, slug-prefixed — never a fixed cross-theme path. v0.3.1
could write a stale cross-theme `candidates_<other-theme>.json` into the wrong run dir (the
machinery run dir picked up a 63-name `candidates_railcar_leasing.json`, which `finalize_run` would
have falsely demanded reports for). With slug-namespacing each concurrent agent's floor output is
isolated to its own run, and the shared-`/tmp` run-state collision is closed in parallel (see
"Concurrency isolation" in the run-batch setup above). Files: `tools/filter_by_sic.py` +
`tools/_common.py` / `tools/new_run.py`.

**Gate 2 — LLM Theme-Fit Gate**
For each Gate 1 survivor, prompt an LLM subagent with the company's 10-K business description.
Classify: `pure_play` / `partial` / `misrecall`. Use the prompt template in
`reference/discovery-engine.md §Gate 2`. Drop `misrecall` before any deep-dive computation.

Both gates are mandatory. Neither can be skipped or merged into a single pass.

---

## Rating Hard-Rules Quick Reference

> Full scoring rubric, evidence-tier definitions, and output template: `reference/judgment-rubric.md`.
> Authoritative source for all rules below is `reference/judgment-rubric.md`; this section is a navigational subset.

### Symmetric BUY Trigger (Phase 3) — three-way `mos_basis` handling

Run `python tools/valuation.py` before rating; read `mos_basis`, `margin_of_safety_pct`, `nav_margin_of_safety_pct`, the mechanical `buy_eligible` / `buy_ineligible_reasons` composite, and the deepdive `derived` change-detection fields `concentration_flag`, `fundamental_decline_flag`, and `peak_contamination_flag`. Also note the data-quality-only label `low_revenue_loss_ratio`, the P7 second-source sanity-band fields `cross_source_checked` / `cross_source_mismatch` / `cross_source_detail` (a >2.5x SEC-vs-yfinance disagreement on debt/revenue/shares — `cross_source_mismatch` gates `buy_eligible`), the v0.3.1 degenerate-base / current-loss-masking veto `normalization_masks_current_loss` (`normalized_fcf > 0` while current OCF/FCF is negative or `contamination_ratio < 0` — gates `buy_eligible`, downgrades BUY→WATCH), the v0.3.2 lessor-routing flag `lessor_asset_heavy` (#8 — when True forces `fcf_cap_model_unsuitable = true` → NAV basis even below the 0.62 debt/assets threshold, so an asset-heavy lessor values on lease-fleet NAV not trough FCF — GBX/RAIL), the v0.3.2 explicit foreign-filer abstain label `foreign_filer_unvaluable` (#11 — a 20-F/40-F filer still empty after the us-gaap + ifrs-full concept cascade, labeled clearly rather than a silent null), and the provenance tag `form_used` (10-K/20-F/40-F — populated for foreign filers too). The model (reverse-DCF, cyclical-trough normalization, NAV path, data-quality guards, eligibility composite) is specified in `reference/valuation.md` and `reference/judgment-rubric.md`. **The rating reads ONLY these T1 fields — it MUST NOT read the top-level `signals` namespace (see "T2 diagnostic signals" below).**

**T2 diagnostic signals (never drive BUY) — firewalled side-channel (iteration 4, §5-Q2).** The deepdive output carries a SEPARATE top-level `signals` key (a sibling of `derived`, NEVER inside it) populated by `tools/signals.py`: P16 `price_divergence` (fundamental-vs-price divergence label — `unpriced_improvement` / `melting_ice_cube_priced` / `aligned` / `unclear`, with trailing 6m/12m price return) and P17 `ownership` (recent 13D/13G + staleness-labeled short interest). The agent MAY ADDITIONALLY gather P15 alt-data (TrendsMCP / GDELT / news-volume) as labeled T2 corroboration at analysis time. **Firewall (non-negotiable):** these are DIAGNOSTIC-ONLY context an analyst reads — `valuation.py`, the `buy_eligible` composite, and the BUY trigger DO NOT and MUST NOT read any `signals.*` field. A BUY stays anchored to T1 filing-derived valuation + zero kill-flags + `buy_eligible`; a signal can NEVER originate or up-weight a BUY. They are **track-forward-gated**: `track_forward` snapshots them per verdict for FUTURE per-signal Brier calibration, and until each signal has earned its own Brier it gates nothing. Full layer spec: `reference/data-sources.md` ("The Firewalled Diagnostic Side-Channel") and `PHILOSOPHY.md` ("Operationalizing the diffusion thesis"). Render them in the report under "## T2 DIAGNOSTIC SIGNALS (context only — NOT used in the rating)".

| `mos_basis` | BUY condition | Notes |
|---|---|---|
| `fcf_cap` | `margin_of_safety_pct ≥ 30%` AND kill-flags = 0 AND no T3 thesis AND `buy_eligible == true` | Full confidence weight 1.0; capped by data_quality flags |
| `nav` | `nav_margin_of_safety_pct ≥ 30%` AND kill-flags = 0 AND no T3 thesis AND `buy_eligible == true` | Multiply raw conviction by 0.6 before recording `confidence` field; surface as "asset-heavy / NAV basis". **v0.3.2 #8:** a name reaches `nav` either via `debt/assets > 0.62` OR via `lessor_asset_heavy == true` (a leasing/rental business — GBX 0.41 / RAIL 0.35 route here despite sub-0.62 debt, valued on lease-fleet NAV not trough FCF) |
| `abstain` | No MoS BUY/AVOID trigger; rank on EV/EBITDA + EV/Sales only | Never penalize for model mismatch |

**`buy_eligible` mechanical gate (ANDed into every BUY):** `valuation.py` emits `buy_eligible = (not extreme_mos_review_required) AND (not large_cap_out_of_scope) AND (not fcf_sustainability_uncertain) AND (not financial_sic forced-unsuitable) AND (not debt_truncation_suspected) AND (not wrong_entity_suspected) AND (concentration_flag != "kill") AND (not fundamental_decline_flag) AND (not peak_contamination_flag) AND (not insurance_concepts_present) AND (not low_revenue_loss_ratio_extreme) AND (not cross_source_mismatch) AND (not normalization_masks_current_loss) AND (active MoS is not None)`, plus `buy_ineligible_reasons` (list[str]). These guards previously existed only as advisory strings the trigger never blocked on; they now bite. When `buy_eligible == false`, the rating downgrades to WATCH (AVOID if a hard kill-flag is also present) and the BUY-trigger line must list `buy_ineligible_reasons` verbatim. **Iteration 3 (A3/A4)** adds two composite terms — `(not insurance_concepts_present)` (insurance-subsidiary holdcos routed like financial-SIC regardless of SIC) and `(not low_revenue_loss_ratio_extreme)` (`|net_income|/revenue > 20` extreme tail) — and refines `wrong_entity_suspected` to fire ONLY on genuine unit-mistag / wrong-CIK (`shares_outstanding < 1000` OR ticker absent from `company_tickers.json` OR CIK mismatch); the `|net_income|/revenue` ratio trigger is REMOVED, that tail now carried by the tiered `low_revenue_loss_ratio` (advisory) / `low_revenue_loss_ratio_extreme` (gating) labels. `debt_truncation_suspected` continues to fire only on genuinely implausible/truncated debt magnitudes. **Iteration 5 (P7)** adds one further composite term — `(not cross_source_mismatch)` — the first term sourced from an INDEPENDENT feed (yfinance) rather than internal-consistency on SEC XBRL; see "Second-source sanity band" below. **v0.3.1 adds two final terms:** `(not normalization_masks_current_loss)` (#1 — degenerate-base / current-loss-masking veto; see "Degenerate-base veto" below) and `(active MoS is not None)` (#9 — a null MoS can never be `buy_eligible`, emitting `not_assessable_no_intrinsic_band` instead of leaving `buy_eligible` True-by-absence-of-data). Full source of truth: `reference/judgment-rubric.md`.

**Concentration kill/watch (P3):** `concentration_flag = "kill"` when `top_program_pct > 60` OR `top_customer_pct > 40` (forces `buy_eligible = false`, caps Dim 3 at 2); `"watch"` when either ratio is in the 40–60 band (surfaced, does not block BUY by itself); null otherwise. Magnitude-based from XBRL `RevenueFromContractWithCustomer` segment members — replaces the old English substring.

**Fundamental-decline veto (P6, mechanical carve-out):** `fundamental_decline_flag = true` when `rev_slope_sign < 0` AND `0 < contamination_ratio < 1.0` AND `latest_below_avg == true`. It downgrades a would-be BUY to WATCH even at MoS ≥ 30% — the melting-ice-cube defense. This is a measured-data veto, explicitly distinct from (and NOT) the qualitative cyclical-turn forward judgment the perpetual-veto prohibition still bans. The `0 <` lower bound (A1, iteration 3) is the degenerate-base guard — see V-shape veto below.

**V-shape value-trap veto (P-A, mechanical sibling) + degenerate-base guard (A1):** `peak_contamination_flag = true` when `0 < contamination_ratio < 0.8` AND `latest_below_avg == true` AND `latest_net_income < 0`, **independent of `rev_slope_sign`**. It is ANDed into `buy_eligible` and downgrades a would-be BUY to WATCH even at MoS ≥ 30% — same downgrade-only discipline as `fundamental_decline_flag`. It exists because `fundamental_decline_flag` is gated on `rev_slope_sign < 0` and therefore MISSES the trough→peak→rollover V-shape (the whole-window linear fit slopes up, so the AND-of-three never fires). NRP is the canonical catch: `rev_slope_sign = +1`, `contamination_ratio = 0.7445`, `latest_below_avg = true`, `latest_net_income = −$84.8M` → `fundamental_decline_flag = false` but `peak_contamination_flag = true`, so the clean mechanical BUY (MoS +36.8%) is now downgraded to WATCH by the machine rather than only by analyst judgment. **Degenerate-base guard (A1, iteration 3):** both vetoes now require a POSITIVE normalization base — the `0 <` lower bound on `contamination_ratio` rejects a negative/degenerate base (`contamination_ratio = latest base / 5yr-avg`; a negative base would let the bare `< 0.8` / `< 1.0` test pass trivially). BWIN fired `peak_contamination_flag` in iteration 2 at `contamination_ratio = −2.4618` (a negative base, uninterpretable as "peak-contaminated") — with the lower bound it is now **False**.

**Early/pre-revenue resource label (P-B, now TIERED — A4):** `low_revenue_loss_ratio = true` when revenue is present but small AND `|net_income|/revenue > 2.0` — the early/pre-revenue resource pattern (large loss vs tiny revenue). It is surfaced in `data_quality` ONLY (advisory tier); NOT part of the `buy_eligible` composite and does NOT change the rating (those names stay blocked by their own null/negative-FCF MoS as before). **Extreme tier (A4, iteration 3):** when `|net_income|/revenue > 20`, `deepdive_data.py` ALSO emits `low_revenue_loss_ratio_extreme`, which IS in the `buy_eligible` composite and gates BUY. This preserves the iteration-2 block on STSS (≈1,384x) / MVIS (≈78.6x) / TIPT (≈71.6x) with the *correct* gating reason instead of the misleading `wrong_entity_suspected`. The advisory `low_revenue_loss_ratio` (ratio>2, non-extreme) stays label-only.

**Insurance-subsidiary holdco routing (A3, iteration 3):** `insurance_concepts_present = true` when insurance XBRL concepts are present (e.g. `PremiumsEarned` / policy reserves / `LossesAndLossAdjustmentExpense` / `PolicyholderFunds`). It is ANDed into `buy_eligible` (forcing `buy_eligible = false`) and routes the company like `financial_sic` (NAV / abstain, never fcf_cap BUY). It closes the BOC hole — Boston Omaha is SIC 6510 (a non-financial real-estate prefix) but owns a surety-insurance subsidiary; on positive FCF it would otherwise slip the financial gate. `insurance_concepts_present` catches such holdcos on the *presence of insurance accounting* rather than on the SIC, so they are treated as financial regardless of registered SIC.

**Second-source sanity band (P7, iteration 5) — a DATA-INTEGRITY gate, NOT a signal:** every other `buy_eligible` term is an internal-consistency check on a single feed (SEC XBRL), so all are blind to a corruption that looks internally reasonable but is externally wrong (HCI's plausible $246M revenue behind a failed SIC fetch; AL's sub-entity $331M revenue + 200-share tag; HRI's truncated $11M debt). P7 adds the first external check: on **survivors only** (deepdive level, after `cheap_pass`, to respect rate limits) `deepdive_data.py` fetches a SECOND, INDEPENDENT source for `total_debt` / `revenue` / `shares_outstanding` from yfinance (`Ticker(t).info` totalDebt/totalRevenue/sharesOutstanding, falling back to `.balance_sheet` / `.financials` / `.get_shares_full`) and compares it to the SEC-XBRL `latest_total_debt` / `latest_revenue` / `latest_shares`, emitting `cross_source_checked` / `cross_source_mismatch` / `cross_source_detail` into `derived`. `cross_source_mismatch = true` when any field has both values present and non-trivial (`abs > $1M`) and `max(a,b)/min(a,b) > 2.5`. `valuation.py` ANDs `(not cross_source_mismatch)` into `buy_eligible` → a mismatch forces `buy_eligible = false`, adds `cross_source_mismatch` to `buy_ineligible_reasons`, and downgrades a would-be static-MoS BUY → WATCH/abstain (the corrupted SEC input cannot back a tradeable MoS). **This legitimately gates** — deliberately distinct from the iteration-4 firewalled diagnostic `signals` (P15/P16/P17), which are between-filings market signals that may NEVER gate; P7 is about *trusting the input numbers themselves*, so it lives in `derived` (the decision path), not in `signals`. **Never blocks on an absent second source:** if yfinance is unavailable or yields no comparable field, the fetch returns None (guarded end-to-end, never raises), `cross_source_checked = false` / `cross_source_mismatch = false`, and the name flows through exactly as before P7.

**Degenerate-base / current-loss-masking veto (v0.3.1 #1) — `normalization_masks_current_loss`:** when `contamination_ratio < 0` (or the latest normalization base is negative), the A1 degenerate-base guard correctly silences BOTH cyclical vetoes (`peak_contamination_flag` and `fundamental_decline_flag` — their "well below a POSITIVE 5-yr average" semantics don't hold on a negative base), yet the trailing-5yr-average normalization can still emit a POSITIVE `normalized_fcf` off a series whose latest period is in deep cash burn — a divested-segment stub, a one-time settlement, a continuing-ops remnant. The result is a phantom positive MoS that NO mechanical guard catches. **TUSK is the canonical hole:** Mammoth Energy divested its frac/sand/infra units in 2025 (continuing-ops a $44.3M stub); `latest_ocf = −$18.6M`, `latest_fcf = −$89.1M`, EBITDA `= −$29.7M`, yet `normalized_fcf > 0` produced a +55.1% mechanical BUY that only the human adversarial layer caught. `deepdive_data.py` now emits `normalization_masks_current_loss = (normalized_fcf > 0) AND (latest_ocf < 0 OR latest_fcf < 0 OR contamination_ratio < 0)` — the trailing average is masking current cash burn. `valuation.py` ANDs `(not normalization_masks_current_loss)` into `buy_eligible` (forcing `buy_eligible = false`), adds `normalization_masks_current_loss` to `buy_ineligible_reasons` and a detail line to `data_quality`, and downgrades a would-be BUY to **WATCH** (AVOID if a hard kill-flag is also present) — same downgrade-only discipline as `fundamental_decline_flag` / `peak_contamination_flag`. It is a measured-data veto that can only lower a rating, never raise one; it is the mechanical replacement for the human catch on the TUSK shape.

**Null-MoS eligibility guard (v0.3.1 #9) — `not_assessable_no_intrinsic_band`:** `buy_eligible` could previously be True-by-absence-of-data — a foreign filer / pre-revenue name with no intrinsic band yields `margin_of_safety_pct = null` while none of the blocking guards fired, so `buy_eligible` stayed True with MoS=null (DAVA, TV, QNC, BTQ, NUCL, RVSN, CVV, ELMT, NABL), caught only by the downstream numeric `MoS ≥ 30` clause and misleading to a human reader. `valuation.py` now requires the ACTIVE MoS (`margin_of_safety_pct` when `mos_basis == "fcf_cap"`, else `nav_margin_of_safety_pct`) to be non-null; when it is `None` it appends `not_assessable_no_intrinsic_band` to `buy_ineligible_reasons`, forcing `buy_eligible = false`. **`buy_eligible` may NEVER be True with a null MoS.** `mos_basis == "abstain"` is unaffected — it takes no BUY/AVOID on MoS at all.

**Asset-heavy lessor → NAV routing (v0.3.2 #8) — `lessor_asset_heavy`:** the NAV path was gated on `total_debt / total_assets > 0.62` alone, which mis-routes asset-heavy *lessors that fund their fleet with equity / moderate leverage*. Railcar lessors GBX (Greenbrier, debt/assets = 0.41) and RAIL (FreightCar America, 0.35) fell *below* 0.62 and were valued on trough-cycle FCF instead of lease-fleet NAV — GBX's 17,000-car fleet is a textbook NAV candidate left mis-valued. `deepdive_data.py` now emits `lessor_asset_heavy` (bool) — a leasing/rental-business signal that fires on a leasing/rental SIC (`{6726, 7377, 4741, 6159, 7359}`) OR an operating-/finance-lease-income revenue concept present OR a very high PP&E (or lease-fleet) / total-assets ratio combined with rental/lease revenue. `valuation.py` reads `derived.lessor_asset_heavy`; when True it forces `fcf_cap_model_unsuitable = true` (route to NAV — `mos_basis = "nav"`, or `"abstain"` when tangible equity is unavailable) EVEN IF `debt/assets < 0.62`, and appends `lessor_asset_heavy_fcf_unsuitable_route_nav:<detail>` to `data_quality`. This is a routing change only: it moves the basis from FCF-cap to lease-fleet NAV; it never manufactures a BUY (NAV-path requirements — MoS ≥ 30%, zero kill-flags, `buy_eligible == true`, 0.6 confidence down-weight — apply unchanged). A normal industrial with no leasing signals keeps `lessor_asset_heavy = false` and is unaffected. Full spec: `reference/valuation.md` ("Lessor NAV routing").

**Foreign-filer IFRS recovery + explicit label (v0.3.2 #11) — `foreign_filer_unvaluable`:** whole 20-F / 40-F cohorts returned empty financials → `intrinsic_band_unavailable` because their XBRL is tagged under the `ifrs-full` taxonomy, not `us-gaap`. (a) `deepdive_data.py` extends the XBRL concept cascade for the most common IFRS tags (`ifrs-full` `Revenue`, `ProfitLoss`, `CashFlowsFromUsedInOperatingActivities`, and equivalents) so SOME foreign filers recover (us-gaap is tried first; IFRS only fills genuine gaps). (b) When financials are STILL empty for a foreign filer after the cascade, it emits `foreign_filer_unvaluable` (bool) so the abstain is CLEARLY labeled rather than a silent null — `valuation.py` surfaces it in `data_quality` as `foreign_filer_unvaluable:<detail>` and the report/banner can say "foreign filer — un-valuable from EDGAR." This is label-only (no separate BUY gate): the null MoS already forces `buy_eligible = false` via `not_assessable_no_intrinsic_band` (#9), so it can never be a false BUY. Tractable XBRL-tag scope only — NO full financial-statement document parsing. The abstain stays graceful: never a crash, never a false BUY.

**Catalyst modifier (closed enumerated list — no other types qualify):** (a) spinoff filing Form 10-12B/15-12B with documented index-fund forced-selling mechanism; (b) cluster open-market insider purchases Form 4 ≥2–3 insiders within 90 days, cash purchases only — not option exercises/grants; (c) court-ordered asset sale or special distribution per 8-K with scheduled completion date; (d) exchange delisting-avoidance / deficiency event per 8-K creating forced selling. Each requires a dated trigger. Earnings guidance, product launches, customer wins, and any organic-growth narrative do NOT qualify. Populate `catalyst` field with category, T1 source, and dated trigger; null otherwise. **MoS-waiver FROZEN (iteration 1):** a verified catalyst yields **WATCH-with-catalyst, NOT BUY** — it no longer waives the MoS threshold. Temporary, pending mechanism-verification + per-category Brier in iteration 2 (§5-Q3 of the iteration-1 design).

**Perpetual-veto prohibition (qualitative only):** the *qualitative forward* "cyclical turn not yet realized in T1" may NOT veto a BUY when MoS ≥ 30%. Normalized FCF already accounts for cycle conservatism. This prohibition does NOT cover the mechanical `fundamental_decline_flag` carve-out above, which IS permitted to downgrade.

### Downward Hard-Ceilings

These are hard ceilings and floors — they override dimension scores and cannot be argued away
by narrative quality or management explanation:

| Condition | Hard rule |
|---|---|
| `going_concern` flag in most recent 10-K or 10-Q | **Eliminate before deep-dive** (cheap_pass gate) |
| `death_spiral` convertible detected | **Dim 1 capped at 1**, composite max = 2 |
| `material_weakness` in ICFR | **Dim 1 (financial quality) capped at 2** |
| Net income driven by deferred tax release (not OCF) | **Score Dim 1 on OCF only**; note the driver |
| AR growing faster than revenue | **Required red flag note** in Dim 1 basis |
| S-3 shelf / ATM program active with < 4Q runway | **Dim 1 score = 1** |
| Single customer > 40% OR single program > 60% (`concentration_flag == "kill"`) | **Dim 3 capped at 2**; forces `buy_eligible = false` (blocks BUY) |
| `peak_contamination_flag == true` (V-shape: `0<contamination_ratio<0.8` AND `latest_below_avg` AND `latest_net_income<0`; independent of `rev_slope_sign`) | Forces `buy_eligible = false` → **downgrades would-be BUY to WATCH** even at MoS ≥ 30% (AVOID if hard kill-flag also present). The `0<` lower bound (A1) rejects negative/degenerate bases — BWIN at `cr=−2.4618` no longer fires |
| `insurance_concepts_present == true` (insurance XBRL concepts: `PremiumsEarned` / policy reserves / `LossesAndLossAdjustmentExpense` / `PolicyholderFunds`) | Forces `buy_eligible = false` → routed like `financial_sic` (NAV / abstain, never fcf_cap BUY) (A3) — catches insurance-subsidiary holdcos on non-financial SICs (e.g. BOC, SIC-65) |
| `low_revenue_loss_ratio_extreme == true` (revenue present-but-small AND `\|net_income\|/revenue > 20`) | Forces `buy_eligible = false` → **blocks BUY** (A4) — gating extreme tier; preserves the STSS/MVIS/TIPT block with the correct reason-string vs the misleading `wrong_entity_suspected` |
| `cross_source_mismatch == true` (P7 — `max(SEC,yfinance)/min > 2.5` on debt, revenue, OR shares; both present & `> $1M`) | Forces `buy_eligible = false` → **blocks BUY** (downgrade to WATCH; AVOID if hard kill-flag also present). **DATA-INTEGRITY gate** — distinct from the iter4 firewalled diagnostic `signals`; it legitimately gates because a corrupted single-source SEC input cannot back a tradeable MoS. Survivors-only (deepdive level); `cross_source_checked == false` (no comparable yfinance field) NEVER blocks |
| `normalization_masks_current_loss == true` (v0.3.1 #1 — `normalized_fcf > 0` AND (`latest_ocf < 0` OR `latest_fcf < 0` OR `contamination_ratio < 0`)) | Forces `buy_eligible = false` → **downgrades would-be BUY to WATCH** even at MoS ≥ 30% (AVOID if hard kill-flag also present). Degenerate-base / divested-stub veto — the trailing-avg normalized FCF is masking current cash burn, so the positive MoS is phantom. Catches the TUSK +55.1% hole the A1-silenced cyclical vetoes miss; measured-data downgrade, never raises |
| active MoS is `None` (`margin_of_safety_pct` null on `fcf_cap`, or `nav_margin_of_safety_pct` null on `nav`) | Forces `buy_eligible = false` with reason `not_assessable_no_intrinsic_band` (v0.3.1 #9). **`buy_eligible` may NEVER be True with a null MoS** — closes the True-by-absence-of-data footgun (DAVA/TV/QNC/BTQ). `mos_basis == "abstain"` unaffected (no BUY/AVOID on MoS) |
| `lessor_asset_heavy == true` (v0.3.2 #8 — leasing/rental SIC `{6726,7377,4741,6159,7359}` OR lease-income revenue concept OR high PP&E/lease-fleet ratio + rental revenue) | **ROUTING rule, not a kill-flag.** Forces `fcf_cap_model_unsuitable = true` → `mos_basis = "nav"` / `"abstain"` even below the 0.62 debt/assets threshold; the asset-heavy lessor (GBX 0.41 / RAIL 0.35) values on lease-fleet NAV, not trough FCF. data_quality: `lessor_asset_heavy_fcf_unsuitable_route_nav:<detail>`. Moves the basis; never lifts a rating |
| `foreign_filer_unvaluable == true` (v0.3.2 #11 — 20-F/40-F filer STILL empty after the us-gaap + ifrs-full concept cascade) | **EXPLICIT abstain label, not a separate gate.** Surfaced in `data_quality` as `foreign_filer_unvaluable:<detail>` so the abstain reads "foreign filer — un-valuable from EDGAR" instead of a silent `intrinsic_band_null`; the null MoS already forces `buy_eligible = false` via `not_assessable_no_intrinsic_band` (#9). Graceful abstain — never a crash, never a false BUY |
| `concentration_unquantified == true` (text concentration flag True AND magnitude `concentration_flag == null`) | **Advisory only (A2)** — surface in `data_quality` + Dim 3; analyst must read the 10-K footnote. Does NOT gate `buy_eligible` or cap any dimension |
| `distress_kill == true` (v0.3.3 — CORE-4 PIT distress `score ≥ 3`: count of `neg_ocf`, `neg_margin` (operating loss), `accum_deficit` (retained earnings < 0), `low_altman` (Altman Z″ < 1.1)) | **KILL-FLAG — counts in `killflag_count` → routes the name to AVOID** (in both the live rating and the backtest grader), regardless of cheapness. The skill's one OOS-validated predictive de-risk signal: over a 25-cell survivorship-safe PIT panel (non-financial, n=412, 55 forward-12mo blowups <−40%), the `score ≥ 3` cutoff has blowup precision 35.4% vs 13.3% base (**lift 2.65×**), recall 62%, **ticker-cluster bootstrap 95% CI on top-quintile lift [1.73, 3.00]**, P(lift≤1)=0. Sharp cliff: score 0–2 ≈ 5–9% blowup, 3 = 25%, 4 = 41.7%. Banks/insurers out of scope (route to `financial_sic`/abstain upstream). Spec + evidence: `tools/_deepdive_flags.distress_core4`, `docs/backtest-2026-06/ROOT_CAUSE_AND_DERISK_EDGE.md` |
| `insider_net_sell` strongly negative AND dilution rate ≥ 15%/yr | **Dim 4 capped at 2** |
| Critical data unavailable (runway, revenue, insider trades all null) | **Confidence capped at 40%** |
| Company has no current theme revenue (pure concept-playing) | **Theme-fit dimension capped at 2**; cannot rate BUY |
| Rating is AVOID OR kill-flag count ≥ 3 | **Sinks to bottom of ranking** |

Full hard-rule source of truth: `reference/judgment-rubric.md §Rating Hard-Rules`.

Scorecard total = plain unweighted sum of the 7 dimension scores (no per-dimension weights exist in the repo). The scorecard does not by itself produce the rating: **rating = f(MoS / NAV MoS, kill-flags, hard-ceilings, `buy_eligible`)** — the mechanical decision layer in `reference/judgment-rubric.md` is authoritative. The scorecard total is a diagnostic summary reported as a /35 sum (or rescaled 1–5 with one decimal); ties broken by Dimension 1 (financial quality).

---

## Environment Prerequisites

Before running any tool, complete setup once:

```bash
# 1. Install Python dependencies
pip install -r tools/requirements.txt

# 2. Configure the tool — OUTSIDE the repo.
# Your SEC User-Agent is your real name + email. It is yours, so it lives in the private config
# dir, never in the working tree. A "just fill in reference/config.json" step is how a real
# contact address once got committed here; the config now resolves from outside by design.
mkdir -p ~/.small-cap-deepdive-config
cp reference/config.example.json ~/.small-cap-deepdive-config/config.json
# Edit ~/.small-cap-deepdive-config/config.json: set "sec_user_agent" to "Your Name you@example.com".
# EDGAR requires a valid User-Agent on every request (format: "Name email"); omission causes 403.
# (Override the location with $SMALL_CAP_DEEPDIVE_CONFIG_DIR. In-repo reference/config.json is a
#  deprecated legacy fallback — do not create it; a real identity in the tree is a leak waiting.)
```

The `sec_user_agent` field is the only hard requirement. All other config keys have defaults
documented in `config.example.json`. Theme-specific overrides (SIC exclusion blocks, keyword
sets, market-cap ceiling) are set per-run via the `--config` flag or inline JSON.

---

## Data-Source Reuse

Full routing guide, rate-limit discipline, blind spots, and anti-recursion rule:
`reference/data-sources.md`.

**Key routing decisions summarized:**

- **EDGAR** (EFTS + XBRL + Form 4): primary for all filing-derived data. `edgartools` wrapper
  handles rate discipline. Max 10 req/s, include User-Agent on every request.

- **market-intel skill (read-only catalog reuse):** for commercial/market data that complements
  SEC filings — competitor pricing, X/Twitter sentiment on a specific company, industry news
  volume — invoke the `market-intel` skill rather than re-implementing source detection.
  This skill does not duplicate the market-intel source matrix; it reuses it.

- **X sentiment route (twitterapi.io ② route):** when X investor sentiment is needed for a
  specific ticker, use the market-intel skill's X-twitter domain shard (`reference/domains/x-twitter.md`
  in the market-intel repo). The twitterapi.io route ② is the recommended resale source when
  direct API access is not connected. See `reference/data-sources.md §X Sentiment` for the
  anti-recursion guardrail (do not re-invoke this skill from within market-intel).

- **yfinance / openinsider:** convenience layers for market data and insider trades respectively.
  Both are free but fragile — label sources accordingly in reports.

---

## Track-forward (Phase 6 — Calibration Feedback Loop)

After any deep-dive run, log all verdicts so they can be scored against realized returns when
the horizon matures. This is the only way to determine if the rubric is correctly calibrated.

**Operational steps:**

1. **After each deep-dive run:** record verdicts from the output JSON:
   ```bash
   python tools/track_forward.py --record reports/smallcap/deepdive_verdicts.json
   ```
   Or record a single verdict via CLI flags:
   ```bash
   python tools/track_forward.py --record --ticker EGAN --rating 观察 --theme aeromro \
       --mos-pct null --mos-basis abstain --catalyst null
   ```

2. **Monthly (or ad hoc):** score matured verdicts (horizon elapsed) against realized prices:
   ```bash
   python tools/track_forward.py --score
   ```

3. **Generate calibration scorecard:**
   ```bash
   python tools/track_forward.py --scorecard   # writes metrics/scorecard.md
   python tools/track_forward.py --status      # quick count summary
   ```

4. **Tune the rubric ONLY when ≥~20 verdicts have matured.** Before that threshold the
   calibration table is statistically meaningless. See `reference/track-forward.md` for
   the full Brier / calibration methodology and the benchmark choice rationale (IWM, not SPY).

5. **Recall@gold (P8, iteration 3) — measure discovery recall, not just precision.** Gate-2
   precision is already documented (the 6.8%-precision FTS over-recall problem); recall has until
   now been audited only by manual blurb re-scan. `track_forward` now computes **`recall@gold`** for
   any theme that has a hand-built gold true-member list: the fraction of gold members the
   discovery union (FTS ∪ SIC reverse-recall, P8) actually recalled. Example gold list — deathcare:
   `{SCI, CSV, MATW, HI, STON, SNFCA}`. A miss in `recall@gold` is a direct discovery-floor failure
   (a true member the union dropped); `track_forward` **warns when the FTS arm hit the top-1000 cap**,
   since a capped FTS arm is the most likely cause of a sub-1.0 recall@gold and signals the SIC
   reverse-recall floor should be carrying more of the load.

6. **Signals snapshot (iteration 4) — track-forward-gated, NOT a calibration input yet.** When a
   verdict is recorded, `track_forward` snapshots the diagnostic `signals` into the verdict row under
   `signals_snapshot` (the P16 `divergence_label` + a P17 ownership summary). This is purely so the
   per-signal predictive value can be calibrated LATER — it is **diagnostic-gated**: it does NOT
   change `implied_prob` or the rating, and no signal gates anything until it has accumulated its own
   Brier score. The firewall holds end-to-end: signals enter the record only as a future-calibration
   snapshot, never as a driver of the verdict they are stored alongside.

**Note:** Verdicts from 2026-06 runs mature in 2027-06. The correct scorecard state until then
is "0 scored, N pending — calibration unknown." This is not a bug; it is the honest state.

**Run finalization — Gate-2 misrecall resolved, not missing (A5, iteration 3).** `finalize_run`
reads the run's `gate2_results.json` and treats names in the Gate-2 misrecall set as **resolved**,
NOT "missing." A `band=deep` candidate that was dropped at Gate 2 for theme-fit is an intentional,
auditable exclusion — not a forgotten deep-dive — so it no longer counts toward the spurious
"N missing" warning. This kills the manual re-band / `--allow-missing` step that every iteration-2
theme required, and the denominator now reflects genuine deep-dive coverage rather than raw
`band=deep` row count.
