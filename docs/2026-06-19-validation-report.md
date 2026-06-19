# small-cap-deepdive v0.2.0 — Validation Synthesis Report

**Date:** 2026-06-19
**Scope:** 20 adversarial validation workers across 5 phases (A theme-signal ×8, B value-angle ×3, C event-driven ×3, D robustness ×4, E precision-gate ×2).
**Inputs verified:** all 20 JSON in `reports/smallcap/validation/`, cross-checked against `tools/valuation.py`, `tools/deepdive_data.py` (concept cascades + `data_quality_warn`), `tools/filter_by_sic.py`, `tools/cheap_pass.py`, `skills/small-cap-deepdive/reference/judgment-rubric.md`, `.../valuation.md`.

---

## Executive Verdict

v0.2.0 **produces real signal mechanically, is NOT yet safe to trust on robustness, and is honest about its 0-confirmed-BUY result.** Every confirmed BUY across all 20 workers is a false positive with an identifiable structural cause; no clean 30–60% MoS BUY survived adversarial review. The headline risk is not the trigger logic — it is the **XBRL balance-sheet extraction layer**, which fails in four distinct modes and silently corrupts EV, MoS, and NAV-vs-FCF routing. A **v0.2.1 remediation round is required before the tool's mechanical BUY output can be acted on without a human balance-sheet cross-check.**

---

## The Four Core Questions

### 1. SIGNAL — is the BUY trigger logically dead?

**No, the trigger is alive and correctly conservative — but every BUY it produced is a false positive with a structural cause. Confirmed: 0 clean 30–60% BUY survived adversarial review.**

The trigger fires by two paths and both work mechanically:
- **MoS path** (`margin_of_safety_pct >= 30%` AND zero kill-flags): fired on SIGA (76.1%, confirmed by both B_netnet and B_lowev and B_beatendown).
- **Event/catalyst path**: produced VSNT, ARDT, ABR, WHF, BAFN.

The 30% threshold demonstrably separated signal from noise — it held conservative ground against SIGA (superficially clean) and blocked the obvious traps. But **every BUY-tagged ticker is defective** (full catalog below). The closest-to-clean legitimate misses were MGPI (MoS −1.0%, 0 kill-flags) and SCVL (13.4%, 0 kill-flags) — i.e., the market simply did not offer a 30%+ discount on a clean name. **The trigger is not dead; the universe genuinely contains no clean cheap small-cap right now, and the few mechanical BUYs are all artifacts.**

### 2. ROBUSTNESS — is extreme MoS (>100%) trustworthy?

**No. Extreme MoS (>100%) is almost always a data/model pathology, never confirmed real cheapness.** Across all phases, every >100% MoS traces to one of: insurance/financial-structure model mismatch (HCI 118%), debt truncation (FSBW 104%, HRI +43% near-threshold, CISS 2355%), wrong-entity/unit anomaly (SNFCA 128.7%), micro-cap illiquidity + total-liabilities-proxy (QFIN 190%, BAFN 221% nav), or BDC/REIT structure on FCF-cap (WHF 137.9%, ARDT 168%, ABR 105% nav). **Not one >100% MoS is a clean operating business cheap on real numbers.** (Full catalog below.) This is the single most important finding: extreme MoS should be treated as a **data-error alarm, not a buy signal.**

### 3. EVENTS — does event-driven mode have guardrails?

**Partially, and the missing guards are material.** Event mode (spinoff + insider-cluster) is the only mode that produced multiple mechanical BUYs (VSNT, ARDT, ABR, WHF). Three structural gaps:
- **No small-cap ceiling.** VSNT ($5.4B) and ARDT ($6.3B) fired BUY despite being large-caps; the spinoff path explicitly notes "rubric does not exclude by market cap." For a *small*-cap tool this is a scope leak.
- **No financial-structure exclusion.** WHF (BDC) and ABR (mREIT) ran the FCF/NAV machinery; WHF's 137.9% rests on `revenue=null` + OCF-proxy on loan-portfolio cash flows — structurally meaningless.
- **No FCF-sustainability guard.** VSNT's 153% MoS capitalizes a structurally declining media business (reverse-DCF implies −24% growth) with a linear terminal value; ARDT/WHF rest on OCF-proxy FCF.

The catalyst-detection plumbing itself works (CIK-first path resolves ticker-less spinoffs; openinsider cluster signal present for all). The gaps are downstream filters, not discovery.

### 4. PRECISION — does the SIC/theme gate work?

**It works when the theme maps to a dedicated SIC range; it collapses when it does not.**
- **regbank (E_regbank): review-tier precision 89.8%, over-recall 10.2%, ZERO mis-drops.** All 177 banks correctly routed to `sic_tier="review"` via the `60`/`61` hard-exclude prefixes. This is the designed-for case and it passes cleanly.
- **deathcare (E_deathcare): over-recall ~85–88%, keep-tier precision 8%, review-tier precision 10%.** Funeral/cremation/cemetery has no dedicated SIC, so non-excluded codes (pulp, airlines, food, beverages, mining) default to `keep` and pass Gate 1 untouched. **29 of 34 candidates are misrecalls.**

**Clarification of the "SIC keeps airlines/pulp" complaint — mostly by-design, one real bug:**
- *By-design:* `sic_classify` returns `keep` for any SIC **not** in the hard-exclude list (`filter_by_sic.py:43-65`). "keep" means "not coarse-excluded," NOT "affirmatively a deathcare company." RYAM/RJET/AZUL land in `keep` because pulp/airline SICs aren't hard-excluded; the design relies on Gate 2 (LLM theme-fit) to drop them. The workers calling this a "SIC gate error" mostly misread `keep` as a positive classification. It is over-recall by construction, handled downstream.
- *Real bug:* **MATW (Matthews International, a genuine death-care memorialization supplier, ~$840M segment) was MIS-DROPPED by `cheap_pass` `reject_burn`** (`cheap_pass.py:271-272`). `reject_burn = runway<1.0 AND net_income<0`; MATW's GAAP net loss (driven by non-cash impairment) plus a short cash/OCF runway tripped the filter. A true member was silently eliminated before the LLM gate ever saw it. This IS a real defect — the burn filter conflates non-cash GAAP losses with cash-burn distress.

---

## Per-Phase Summary

### Phase A — Theme signal (8 themes)

| Theme | FTS raw | survivors | deep-dived | BUY | misrecall rate | key defect |
|---|---|---|---|---|---|---|
| specchem | 473 | 22 | 7 | 0 | 59% | RYAM debt truncation 779M→21.5M → false MoS 63.4% |
| oilsvc | 366 | 38 | 11 | 0 | ~42% | TUSK 55.1% = FEMA one-time OCF in 5yr avg |
| buildmat | 620 | 16 | 3 | 0 | 81% | LOMA 20-F all-null; misrecall dominant |
| food | 227 | 34 | 14 | 0 | 47% | leverage→nav→−100%; FDP +6% on OCF-proxy |
| freight | 415 | 121 | 8 | 0 | 80% | HTLD revenue $58M (sub-entity); 4× material_weakness |
| regbank(A) | 429 | (yf failed) | 15 | 1* | 0% | total_assets fails on all 15 banks; FSBW false 104% |
| shipping | 410 | 6 | 6 | 0 | 0% | IFRS gaps; CISS 2355% micro-cap artifact |
| aginput | 300 | 36 | 5 | 0 | 86% | UAN +10.7% best; efficiently-priced cyclicals |

\* regbank(A) BAFN BUY(nav,0.6conf) is a $20.4M illiquid micro-cap; flagged for human validation.

### Phase B — Value angles (3)

| Angle | screened | BUY mechanical | BUY confirmed | closest clean miss |
|---|---|---|---|---|
| net-net | 13 | 1 (SIGA 76.1%) | 0 | MGPI −1.0% / TORM (sub-tool micro-cap) |
| low EV/EBITDA | 10 | 2 (SIGA, HCI) | 0 (HCI pseudo) | MGPI −1.0% |
| beaten-down | 15 | 0 clean | 0 | SCVL 13.4% |

Convergent finding across all three: **SIGA is the only zero-kill-flag mechanical BUY, and it is a trap** — ~90% revenue from a single BARDA government contract, revenue −31.8% YoY, Q1 2026 operating loss. The tool's `customer_concentration_flag` is a false-negative because SIGA discloses concentration via risk-factor narrative, not the "customers accounted for X%" phrase the NLP scans (`deepdive_data.py:474-475`).

### Phase C — Event-driven (3)

| Batch | processed | BUY | defect |
|---|---|---|---|
| spinoff | 12 | 1 (VSNT 153.4%) | large-cap ($5.4B) + structural decline + linear TV |
| insider cluster 1 | 15 | 1 (WHF 137.9%) | BDC; revenue=null; OCF-proxy; conf floor 50% |
| insider cluster 2 | 15 | 2 (ARDT 168%, ABR 105% nav) | ARDT OCF-proxy; ABR mREIT on nav |

### Phase D — Robustness (4 batches, 39 tickers, crash rate 0%)

| Batch | tickers | crash | valuation-fail | key defects |
|---|---|---|---|---|
| assetheavy | 9 | 0 | 2 (AL, TRTN) | FTAI debt=0, HRI stale $11M→false +43%, AL wrong entity, URI/TRTN revenue unit, GATX debt inflated |
| foreign20f | 10 | 0 | 2 (GOGL, EGLE) | GOGL→Golden Star, EGLE→Global X ETF; SBLK stale 2016 debt; STNG total blackout; capex empty 7/10 |
| cyclical | 10 | 0 | 2 (HAYN/USAP delisted) | normalization works; no absurd MoS; CIK lookup needed |
| microcap | 10 | 0 | 0 | SNFCA NI 32B unit anomaly caught by dqw but NOT propagated to valuation |

### Phase E — Precision gate (2)

| Theme | over-recall | keep-precision | review-precision | mis-drop |
|---|---|---|---|---|
| regbank | 10.2% | (21 non-bank keeps, by design) | 89.8% | 0 (PASS) |
| deathcare | ~85–88% | 8% | 10% | MATW (real bug) |

---

## BUY-Defect Catalog (every BUY-tagged ticker, all phases)

| Ticker | Phase | MoS | Basis | kill-flags | Defect / why it is a false positive |
|---|---|---|---|---|---|
| SIGA | B (×3) | 76.1% | fcf_cap | none detected | ~90% single-customer BARDA concentration; tool NLP false-negative (risk-factor narrative, not "% of revenue"); rev −31.8%, Q1'26 op loss; 5yr-avg FCF over-normalized on peak years |
| HCI | B | 118.3% | fcf_cap | none | Insurance company — FCF/EV model conceptually invalid (income includes float returns; OCF includes premium liabilities). `fcf_cap_model_unsuitable` doesn't exclude SIC 6xxx. Pseudo-BUY |
| VSNT | C spinoff | 153.4% | fcf_cap | none | Large-cap ($5.4B, scope leak); structurally declining media (rev −5.3%, reverse-DCF −24%); linear terminal value on a melting ice cube |
| WHF | C cluster1 | 137.9% | fcf_cap | none | BDC — `revenue=null`, FCF=OCF-proxy on loan-portfolio flows; 5 data-quality flags → conf floored at 50%; FCF model structurally unsuitable |
| ARDT | C cluster2 | 168% | fcf_cap | none | OCF-proxy FCF (no capex); large-cap ($6.3B per orchestrator); food distribution thin-margin, EV/Sales 0.28 plausibly real but FCF basis unverified |
| ABR | C cluster2 | 105% | nav | none | Commercial mortgage REIT priced at ~31–39% of tangible book; NAV-of-an-mREIT is mark-to-model, not liquidation value; financial-structure mismatch |
| BAFN | A regbank | 221% | nav | none | $20.4M micro-cap, P/B 0.25; extreme illiquidity; nav rests on bank book equity that the tool cannot even extract total_assets for; 0.6conf + human-validation flag |
| TUSK | A oilsvc | 55.1% | fcf_cap | none | ABSTAINed by worker: FEMA Puerto Rico one-time $180M receipt inflates 5yr OCF avg; revenue collapsed $362M→$44M; shell holding cash |
| SIGA-adjacent blocked: GIII (72.5%, material_weakness), RYAM (63.4%, debt truncation), QFIN (190%, china VIE + debt proxy), GNE (96.9%, 3 kill-flags), FVRR (82.3%, material_weakness), AII (290%, material_weakness), GRNT (209%, material_weakness), ESEA (86.6%, going_concern), FSBW (104%, stale debt → abstain) — all correctly blocked by kill-flags or flagged as data errors. |

**Conclusion:** 0 of the BUY-tagged names is a clean, real, actionable small-cap BUY. The kill-flag gate correctly caught the high-MoS-with-flags cases; the residual false positives (SIGA, HCI, VSNT, WHF, ARDT, ABR, BAFN) escaped because the defect is structural (customer concentration, financial-firm model mismatch, large-cap scope, OCF-proxy) rather than a named kill-flag.

---

## Extreme-MoS Catalog (every |MoS| > ~100%, root cause)

| Ticker | MoS | Root cause | Category |
|---|---|---|---|
| CISS | 2355% | market cap collapsed to $1.2M post reverse-split vs $3.8M FCF; debt=total-liabilities proxy | micro-cap + proxy |
| AII | 290% | material_weakness present; cash unavailable so EV excludes cash | kill-flag + data gap |
| BAFN | 221% (nav) | $20.4M illiquid micro-cap, P/B 0.25; bank total_assets unextractable | micro-cap + bank extraction |
| GRNT | 209% | material_weakness; cash unavailable → EV understated | kill-flag + data gap |
| QFIN | 190% | debt=total-liabilities proxy understates leverage; capex unavailable → FCF overstated; China VIE | proxy + OCF-proxy |
| ARDT | 168% | OCF-proxy FCF (no capex deducted) | OCF-proxy |
| VSNT | 153.4% | structural-decline business, OCF − capex but linear TV; market pricing decline | sustainability gap |
| WHF | 137.9% | BDC; revenue=null; OCF-proxy on loan flows | financial-structure |
| SNFCA | 128.7% | latest NI $32.15B vs rev $344.6M (93×) pulled from DEF 14A in unit=1; dqw caught it, didn't propagate | unit anomaly / wrong form |
| HCI | 118.3% | insurer; net income > revenue (float returns); OCF includes premium liabilities | financial-structure |
| ABR | 105% (nav) | mREIT NAV mark-to-model | financial-structure |
| FSBW | 104% | total_debt stale (last 2022), total_assets unavailable → false fcf_cap routing | debt truncation |
| HRI | +43%* | total_debt XBRL=$11M (stale 2020-22) vs real ~$4-5B; EV=mktcap only | debt truncation |

\* HRI is below 100% but is the clearest **debt-truncation false-positive that would mislead a buyer** — included because its +43% reads as a genuine BUY-adjacent signal but is entirely spurious.

**Pattern:** every extreme MoS is a pathology. None is real cheapness. The model should treat |MoS|>100% as an automatic data-quality halt.

---

## Prioritized Fix List

### CRITICAL (silently corrupts EV/MoS/routing; blocks trustworthy output)

**C1. XBRL balance-sheet extraction — shared root cause, four failure modes.**
The debt/assets/revenue/entity cascades in `deepdive_data.py` are the single biggest liability. Group fix:

- **C1a. Debt truncation (under-report).** `_debt_series` (`deepdive_data.py:171-218`) takes the latest value of whichever concept tier returns data, with no staleness or magnitude sanity check. FTAI returns `LongTermDebt`=0 across 8 quarters (uses non-standard SeniorNotes/TermLoan concepts → debt cascade returns 0); HRI returns stale 2020-22 `$11M`; SBLK stale 2016 `$761M`; FSBW stale 2022. **Fix:** after selecting `latest_total_debt`, cross-check against `Liabilities - StockholdersEquity` (implied liabilities); if `reported_debt < 0.5 × implied_liabilities` OR the debt series' latest end-date lags the assets series' latest end-date by >1 year, emit `debt_truncation_suspected` into `data_quality` AND force `mos_basis="abstain"`. Add `LongTermDebtAndCapitalLeaseObligations`, `DebtLongtermAndShorttermCombinedAmount`, `SeniorNotes` to the cascade.
- **C1b. Debt inflation (over-report).** GATX XBRL $12.5B vs real ~$8B (ASC 842 operating leases capitalized into the debt concept). **Fix:** when debt is sourced from `Liabilities`-adjacent concepts, note lease-inclusion risk; lower-priority than C1a but same cross-check surfaces it (reported ≫ implied financial debt).
- **C1c. total_assets extraction failure → NAV routing fails.** All 15 regbanks returned `debt_to_assets=None` because `Assets` concept was empty, so `fcf_cap_model_unsuitable` (which gates on `latest_assets and latest_assets>0`, `valuation.py:332`) never fired and banks misrouted to fcf_cap. **Fix:** add `LiabilitiesAndStockholdersEquity` as an `Assets` fallback (balance-sheet identity); and add the SIC-based financial exclusion in C2 as a backstop.
- **C1d. Wrong-entity resolution + revenue unit/quarterly confusion.** `Company(ticker)` / name-search resolves AL→Sumisho Air Lease (shares=200), GOGL→Golden Star Resources, EGLE→Global X ETF (`deepdive_data.py:431`). Revenue cascade returns quarterly-as-annual or sub-entity figures: URI $3.7B (real ~$14B), TRTN $59.5M (real ~$1.8B), HTLD $58M (real ~$800M), SNFCA NI from DEF 14A. **Fix:** (1) pre-validate ticker→CIK against SEC `company_tickers.json` before name-search fallback; reject if resolved CIK's entity name doesn't fuzzy-match the requested ticker's known name. (2) Sanity-check `OCF > revenue` for non-financials → emit `revenue_series_suspect`; (3) for revenue, prefer `fp=FY` annual frames and reject entries whose period length <300 days when an annual frame exists.

**C2. Financial-structure companies wrongly run FCF-cap.** `fcf_cap_model_unsuitable` only checks `debt_to_assets > 0.62` (`valuation.py:331-336`); it does NOT exclude by SIC. Banks (HCI insurer, WHF BDC, ABR/banks mREIT) thus produce FCF-cap pseudo-BUYs. **Fix:** in `compute_valuation`, read SIC from the deepdive (`tenk`/financials); if SIC starts with `60`/`61`/`63`/`64`/`67`, set `mos_basis="abstain"` with reason `financial_sector_fcf_model_invalid` (or route to NAV only for asset-backed REITs with reliable book equity). One line of routing logic; eliminates HCI/WHF/ABR false positives.

### IMPORTANT (inflates MoS or leaks scope; needed before BUY output is reliable)

**I1. FCF-cap has no sustainability/quality guard.** Three sub-cases all inflate MoS:
- structural-decline + linear terminal value (VSNT) — reverse-DCF already computes implied growth; **fix:** when `reverse_dcf_implied_growth < −0.15`, cap MoS or downgrade BUY→WATCH with `terminal_value_unsupported`.
- lumpy government/one-time receipts in 5yr OCF avg (SIGA, TUSK FEMA) — **fix:** flag when any single year's OCF > 2× the median of the other years (`lumpy_ocf_normalization_suspect`).
- IFRS/capex-missing → OCF-proxy universal in shippers + Ryder (`fcf_equals_ocf_proxy_no_capex` already emitted) — **fix:** for capital-intensive SICs, treat OCF-proxy FCF as disqualifying for BUY (downgrade to WATCH), since true FCF after capex is materially lower. Add IFRS capex fallbacks: `ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities`.

**I2. Event-driven mode has no small-cap ceiling.** VSNT $5.4B, ARDT $6.3B fired BUY. **Fix:** in `discover_events.py`/rank, hard-exclude `market_cap > small_cap_ceiling` (e.g. $2B) from BUY eligibility, or tag `large_cap_out_of_scope` and block the trigger. One filter.

**I3. `data_quality_warn` does not propagate to valuation.** `deepdive_data.py:567-581` computes the NI unit-anomaly warning into `derived.data_quality_warn`, but `compute_valuation` never reads it (caught SNFCA in deepdive, invisible at valuation layer). **Fix:** in `compute_valuation`, `if der.get("data_quality_warn"): dq.append(der["data_quality_warn"])`. Also extend the dqw detector to fire on the C1a debt-truncation and C1d wrong-entity heuristics so they surface at both layers.

**I4. cheap_pass `reject_burn` mis-drops non-cash-loss companies (MATW).** `cheap_pass.py:271-272`: `runway<1.0 AND net_income<0`. **Fix:** use OCF (cash burn), not GAAP net_income, in the burn condition — `reject_burn = runway<1.0 AND latest_ocf<0`. A company with positive OCF and a non-cash impairment loss is not burning cash and must not be dropped.

### MINOR (correctness/by-design clarifications; infra/environment)

**M1. Precision gate over-recall on no-dedicated-SIC themes is by-design, not a bug.** `keep` = "not coarse-excluded"; relies on Gate 2. Document this in the rubric so future workers stop flagging it as a SIC error. Optionally add theme-specific positive-SIC allowlists for high-noise themes (deathcare → SIC 7261).

**M2. Infra / environment (not code-logic bugs):**
- yfinance rate-limit is a single point of failure in `run_theme` (`_get_market_cap`, `valuation.py:72-80` is the only market-cap source) — regbank/food got zero candidates. **Fix:** add Finviz/FMP fallback (regbank worker already did this manually) and respect `--mktcap` override end-to-end.
- delisted tickers (TRTN, HAYN, USAP, AL) need manual `--cik`; tool should detect null market cap and record `delisted` rather than failing silently.
- cheappass CSV lacks a SIC column → requires join back to universe CSV for theme-fit filtering.
- kill-flags are nested under `tenk.*` not root; downstream consumers must read `tenk.has_material_weakness`. Document or surface at root.

---

## Top-5 Fixes (priority order)

1. **C1a/C1d — debt-truncation + wrong-entity guard** (`deepdive_data.py`): cross-check `reported_debt` vs `Liabilities−Equity` and ticker→CIK against `company_tickers.json`; force `abstain` on failure. *Eliminates FTAI/HRI/SBLK/FSBW false positives and AL/GOGL/EGLE wrong-entity corruption — the largest single source of bad output.*
2. **C2 — exclude financial-sector SIC (60/61/63/64/67) from FCF-cap** (`valuation.py:331`): one routing branch → `abstain`. *Kills HCI/WHF/ABR pseudo-BUYs.*
3. **I3 — propagate `data_quality_warn` into valuation `dq`** (`valuation.py` compute_valuation): one line. *Makes SNFCA-class corruption visible where the BUY decision is made.*
4. **I1 — FCF-sustainability guard** (`valuation.py`): downgrade BUY→WATCH on `reverse_dcf_implied_growth<−0.15`, lumpy-OCF, or OCF-proxy for capital-intensive names. *Kills VSNT/SIGA/TUSK/shipper inflation.*
5. **I4 — fix `reject_burn` to use OCF not net_income** (`cheap_pass.py:271`): *stops mis-dropping real members with non-cash losses (MATW).*

**Verdict on a v0.2.1 round:** **Required.** Items C1, C2, I3, I4 are small, localized, high-impact edits. Until they land, the tool's mechanical BUY/MoS output cannot be trusted without a manual balance-sheet cross-check, and the precision funnel will silently drop real members in no-dedicated-SIC themes.
