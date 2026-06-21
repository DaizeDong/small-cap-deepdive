# Coverage Test — Semiconductor Capital Equipment / Wafer Fab Tools

- **Slug:** `semicap-equipment`
- **Sector:** InfoTech
- **Keywords:** `semiconductor equipment`, `wafer fab tools`
- **Skill version:** v0.3.0 (commit `f12fef5`, run dir reports `_run.json` records `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-semicap-equipment/`
- **Code-path focus:** cyclical peak/trough
- **Date:** 2026-06-21 (run executed; coverage-test folder dated 2026-06-20)
- **Verdict headline:** **0 BUY.** Four deep-band theme-fit survivors, all rated 观察 (WATCH). No name produced a numeric MoS ≥ 30% with `buy_eligible == true`. This is a correct, expected "nothing clean found" result for a hot, late-cycle equipment theme dominated by large-caps.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw FTS recall | 87 | `semiconductor equipment` 87 hits; `wafer fab tools` 0 hits. De-duped to 87. FTS arm did NOT hit the 1000-cap. |
| Priced + banded | 87 | deep band (<$2.0B): 37 · watch band ($2–5B): 9 · rest large/out-of-scope. 5 tickers unpriceable on yfinance (IVAC, ZRCN, PIF, GSRT, XTKG) — flowed as `unknown`/dropped. |
| Into cheap_pass | 33 | small-cap survivors scanned for hard kill-flags |
| cheap_pass survivors | 14 | 19 eliminated (kill-flags / not-small-cap) |
| SIC gate (Gate 1) | 14 | keep=12, review=2 → all 14 to LLM gate |
| **Gate 2 (LLM theme-fit)** | **6 pass** | pure_play / partial retained; 8 misrecall dropped |
| **Deep-band theme-fit survivors deep-dived** | **4** | CVV, ELMT, ASYS, SKYT (deep-band ∩ {pure_play, partial}) |
| Deep-dive crashes (`_ERROR.json`) | 0 | all 4 deepdive + valuation completed |
| **Mechanical BUYs** | **0** | none cleared the v0.3.0 BUY rule |
| BUYs surviving adversarial review | 0 | n/a |

**Deep-band vs deep-dived reconciliation:** candidates JSON marks 11 names `band=deep`. Of those, 8 were Gate-2 **misrecall** (resolved-by-gating, not forgotten) and 4 were deep-dived. `finalize_run` reconciled cleanly: *"deep-band candidates: 11, reports: 4, gate2-misrecall (resolved, not deep-dived): 8, missing: 0."*

### Gate 2 theme-fit decisions (the precision gate doing its job)

| Ticker | Name | SIC | Band | Decision | Why |
|---|---|---|---|---|---|
| **CVV** | CVD Equipment | 3559 | deep | **pure_play** | CVD/PVT/thermal-process deposition tools for SiC & microelectronics fabrication |
| **ASYS** | Amtech Systems | 3559 | deep | **pure_play** | equipment/consumables/services for semiconductor packaging, wafer production, device fabrication |
| **ELMT** | Elmet Group | 3490 | deep | **partial** | refractory tungsten/moly materials & components; semicap is one named end-market; defense-heavy supply-chain member |
| **SKYT** | SkyWater | 3674 | deep | **partial** | pure-play semiconductor *foundry* (fab operator that *uses* tools; does not *sell* them) |
| ICHR | Ichor Holdings | 3674 | watch | pure_play | fluid-delivery subsystems for semicap OEMs — true member but $3.4B > $2B cap → watch only, no deep-dive |
| LASR | nLIGHT | 3674 | watch | partial | high-power lasers into advanced-manufacturing tools + directed energy — watch band |
| NEGG | Newegg | 5990 | deep | **misrecall** | e-commerce retailer; FTS blurb was wrong-entity medical-device text; no semicap |
| ICG | Intchains | 3674 | deep | **misrecall** | blockchain ASIC / Web3 computing, not fab tools |
| BTDR | Bitdeer | 6199 | watch | **misrecall** | crypto mining / hosting / ASIC |
| NMFC / KBDC / MSDL / PFLT / MFIC | (5 BDCs) | nan | deep | **misrecall** | business-development-company middle-market lenders — pure false-positives on `equipment`/`semiconductor` financing language |

**Gate-2 value demonstrated:** of 11 deep-band names, **7 were non-theme false positives** (5 BDC lenders + Newegg + Intchains). Without the LLM gate, five lending vehicles and a retailer would have been deep-dived as "semiconductor equipment." This is the canonical over-recall pattern (cf. the `refractory`→oncology case in SKILL.md) — here `semiconductor`/`equipment` swept BDC loan-portfolio language.

---

## 2. MoS-basis distribution (the 4 deep-dived survivors)

| mos_basis | Count | Tickers |
|---|---|---|
| `fcf_cap` | 3 | CVV, ELMT, SKYT |
| `nav` | 1 | ASYS |
| `abstain` | 0 | — |

No survivor produced a numeric MoS at all: every `fcf_cap` name had a null intrinsic band (normalized FCF non-positive or unavailable), and the single `nav` name (ASYS) had a deeply negative NAV MoS.

---

## 3. Per-survivor results + full `buy_eligible` reasoning

### CVV — CVD Equipment Corp ($54M mkt cap) — WATCH
- **mos_basis:** `fcf_cap` · **MoS:** `null` (intrinsic_band_unavailable — `normalized_fcf_nonpositive`)
- **buy_eligible:** `true` · **buy_ineligible_reasons:** `[]` · **kill-flags:** 0
- **Cyclical:** True (CV=0.56); Norm. EBITDA −$2M, Norm. FCF −$2M (trough). EV/Sales 1.79x.
- Latest: rev $25.8M, NI −$1.6M, OCF −$3.7M. rev_slope_sign=+1, contamination 1.95 (>1 → above-trough? no V-shape veto). peak_contam=False, fundamental_decline=False.
- cross_source_checked=True, **mismatch=False**. Insider net_sell (1 small sale $26k).
- **Why not BUY:** `buy_eligible` is true and no flags bite, but there is **no numeric MoS** — normalized FCF is negative at the trough so the reverse-DCF intrinsic band is null. BUY rule requires numeric MoS ≥ 30; null fails it. Correct WATCH.
- **Data-quality:** `concentration_unquantified` (text flag true, XBRL magnitude null — one customer ~29.5% of 2024 revenue per 10-K, but not machine-quantified), `net_income_nonpositive_pe_null`, `ebitda_nonpositive_ev_ebitda_null`.

### ELMT — Elmet Group ($583M mkt cap) — WATCH (data-limited)
- **mos_basis:** `fcf_cap` · **MoS:** `null` (intrinsic_band_unavailable — `normalized_fcf_unavailable`)
- **buy_eligible:** `true` · **buy_ineligible_reasons:** `[]` · **kill-flags:** 0
- Newly IPO'd (Nasdaq, ~April 2026; ~$120M raise). XBRL series essentially empty in EDGAR: rev/NI/OCF all null in derived; EV/Sales/EBITDA all None; no cyclical computation possible.
- cross_source_checked=True, mismatch=False. Insider **net_buy** (2 open-market buys, $168k).
- **Why not BUY:** insufficient reported financial history to compute any intrinsic value. The `fcf_cap`/`null` outcome is honest — the machine cannot value a company with no XBRL series yet.
- **Data-quality:** `dep_amort_unavailable`, `capex_unavailable_fcf_uses_ocf_proxy`, `normalized_ebitda_unavailable`, `normalized_fcf_unavailable`. Theme membership is **partial** (refractory-metals supplier; semicap is one of many end-markets, defense/aerospace dominant per FY2025 ~$201.6M rev, ~$5.5M NI from public filings).

### ASYS — Amtech Systems ($385M mkt cap) — WATCH
- **mos_basis:** `nav` (FCF model unsuitable) · **NAV MoS:** **−88.8%** · **FCF MoS:** null
- **buy_eligible:** `FALSE` · **buy_ineligible_reasons:** `['cross_source_mismatch']` · **kill-flags:** 1
- **Cyclical:** True (CV=4.65, very high). NAV band $43M–$57M equity vs $385M mkt cap → NAV MoS −88.8% (trades at a huge premium to tangible book — the opposite of an asset-backed value setup).
- Latest: rev $79.4M, NI −$30.3M, OCF +$7.9M. rev_slope_sign=+1, contamination 4.25, latest_below_avg=False. Insider **net_buy** (8 open-market buys, $1.13M — a notable cluster, but does NOT waive any gate).
- **Why not BUY (two independent reasons):** (1) `buy_eligible=false` via **`cross_source_mismatch`** — SEC total_debt $4.6M vs yfinance $18.8M (4.1x disagreement, P7 data-integrity gate); (2) even absent that, NAV MoS −88.8% is the wrong sign. Correct WATCH.
- **Data-quality:** `debt_stale:>18_months_behind_latest_assets`, `concentration_unquantified`, `ebitda_series_partial_entries:6`, `fcf_cap_blocked_by_c1_data_quality_guard`, plus the cross-source debt mismatch.

### SKYT — SkyWater Technology ($1,799M mkt cap) — WATCH
- **mos_basis:** `fcf_cap` · **MoS:** `null` (intrinsic_band_unavailable — `normalized_fcf_nonpositive`)
- **buy_eligible:** `FALSE` · **buy_ineligible_reasons:** `['cross_source_mismatch']` · **kill-flags:** 1
- **Cyclical:** True (CV=2.60). EV/Sales 4.1x, EV/EBITDA 54.8x, headline P/E 15.1x. Norm. EBITDA $8M, **Norm. FCF −$32M**.
- Latest: rev $442M, **NI +$119M but OCF −$29M** — reported net income is NOT cash-backed (driven by non-operating / non-cash items, classic Dim-1 "NI not from OCF" red flag). Insider **net_sell** (40 sales, $90.2M — heavy distribution).
- **Why not BUY (two independent reasons):** (1) `buy_eligible=false` via **`cross_source_mismatch`** — SEC total_debt $37.5M vs yfinance $238.3M (6.4x, P7 gate); (2) `fcf_cap` MoS is null (normalized FCF negative). Correct WATCH.
- **Data-quality:** `intrinsic_band_null:normalized_fcf_nonpositive` + the cross-source debt mismatch.

---

## 4. Code-paths exercised

This run exercised a broad slice of the v0.3.0 machine — the requested **cyclical peak/trough** path fired on 3 of 4 names:

- **SIC reverse-recall floor (P8):** no dedicated semicap SIC code is hard-mapped → FTS recall carried the universe; SIC acted as Gate-1 coarse exclude only. (Confirmed by `track_forward --recall-gold`: no gold list for this theme.)
- **Gate-2 LLM theme-fit (mandatory):** dropped 8/14 (5 BDCs + NEGG + ICG + BTDR) — the precision gate's core job.
- **Cyclical normalization / trough EBITDA (focus path):** fired on CVV (CV=0.56), ASYS (CV=4.65), SKYT (CV=2.60) — all `is_cyclical=True`, all normalized to **trailing_5yr_avg**; ELMT could not be evaluated (no series).
- **Reverse-DCF intrinsic band → null on non-positive normalized FCF:** all 3 fcf_cap names — the trough defense (no fabricated MoS off a negative FCF base).
- **NAV path (asset-heavy fallback):** ASYS routed to `nav` after `fcf_cap` deemed unsuitable; tangible-equity band computed; NAV MoS −88.8%.
- **P7 second-source cross-check (yfinance vs SEC):** fired on BOTH ASYS (debt 4.1x) and SKYT (debt 6.4x), forcing `buy_eligible=false` on each — the data-integrity gate doing exactly what it is for.
- **V-shape / fundamental-decline vetoes:** evaluated on all (peak_contamination_flag and fundamental_decline_flag both False everywhere — no degenerate-base or trough→peak→rollover trap triggered here).
- **Concentration (P3):** `concentration_unquantified` advisory on CVV and ASYS (text flag true, XBRL magnitude null) — surfaced, did NOT gate.
- **cheap_pass kill-flags:** 19 eliminations pre-deep-dive.
- **Firewalled diagnostic signals (P16/P17):** emitted automatically — divergence labels CVV/ASYS/SKYT = `aligned`, ELMT = `unclear`; ownership null. Verified these did NOT touch any `buy_eligible` (all four `buy_eligible` outcomes are fully explained by T1 fields). Snapshotted into verdicts for future Brier calibration.
- **finalize_run A5 (gate2 misrecall = resolved):** 8 misrecalls correctly excluded from the "missing" denominator.

---

## 5. Data-quality issues observed

1. **Two cross-source debt mismatches (ASYS 4.1x, SKYT 6.4x).** Both are SEC-XBRL `total_debt` materially below the yfinance figure. For SKYT in particular, $37.5M (SEC) vs $238.3M (yf) is a large gap on a $1.8B name — the P7 gate is right to block, but the *true* debt level needs manual reconciliation before any human DD; the SEC tag may be a single-instrument or current-portion truncation rather than total debt.
2. **SKYT net income not cash-backed:** NI +$119M vs OCF −$29M. A naive P/E of 15x is misleading; the cash engine is negative. The machine correctly refused a BUY via null normalized FCF.
3. **ELMT has no usable XBRL series** (post-IPO, EDGAR XBRL not yet populated) → every valuation field null. Honest "cannot value yet."
4. **`concentration_unquantified` on CVV and ASYS:** customer-concentration text exists in the 10-K (CVV: one customer ~29.5% of 2024 rev) but XBRL segment magnitude is null, so the P3 magnitude gate could not bite. Advisory only — an analyst must read the footnote.
5. **5 unpriceable tickers** at discovery (IVAC, ZRCN, PIF, GSRT, XTKG) — yfinance delisted/404. IVAC (Intevac) is a *genuine* semicap name lost to a pricing gap; with a SIC reverse-recall floor for SIC 3559/3674 it might have been retained via SEC shares×price fallback. Minor recall leak.
6. **cheap_pass warning:** one `killflag nan: CIK must be string or integer, got float` (a row with a NaN CIK) — non-fatal, one universe row skipped its kill-flag scan.
7. **edgartools cache lock** (`WinError 32`/`145` on `~/.edgar/_tcache`) during CVV/ELMT valuation — non-fatal (the tool fell through), but indicates a stale-cache contention when valuations run back-to-back.

---

## 6. recall@gold

**n/a.** `semicap-equipment` has no hand-built gold true-member list in `THEME_GOLD` (only deathcare/funeral/cemetery, water-utilities, railcar-leasing, regional-gaming are gold-listed). `track_forward --recall-gold` returned: *"no gold list for theme 'semicap-equipment' — not measurable."* Recall floor was therefore not quantified for this theme; the FTS arm did not hit the 1000-cap, and the BDC/crypto false-positive load suggests **precision** (not recall) was the binding constraint here.

---

## 7. Market-intel / T2 analyst context (labeled — does NOT drive any BUY)

- **TrendsMCP (search interest):** `wafer fab equipment` Google-search interest **−59% over the trailing 3 months** (value 56→23; volume 134→55). This independent T2 signal is *consistent with the machine's cyclical-trough read* on CVV/ASYS — equipment attention and (by inference) order momentum are cooling. (12M comparison was degenerate — baseline ~0 — so ignored.) The broader `semiconductor equipment` and `semiconductor shortage` pulls were blocked by daily/monthly TrendsMCP quota and the proxy returned an invalid payload — noted as a gap.
- **Cycle framing:** semicap is a textbook cyclical (WFE spend swings with fab capex). The four survivors are all sub-scale: two are at/near trough profitability (CVV, ASYS), one (SKYT) is a capacity-building foundry burning operating cash, one (ELMT) is a just-IPO'd materials supplier. The bellwether large-caps (AMAT, LRCX, KLA, ASML) sit far outside the small-cap universe by design — this skill is structurally fishing in the residual, sub-$2B tail where pure-plays are scarce and mostly money-losing at trough.
- **Why the small-cap tail is thin here:** the genuine small/mid pure-plays (ICHR fluid-delivery, AEHR test, COHU test-handling, PDFS yield software, PLAB photomasks) all sit in the **watch band ($2–5B) or just above** — exactly where a hot, well-covered theme parks its quality. The deep band (<$2B) is left with trough-cyclicals, a foundry, a fresh IPO, and a wall of misrecalled lenders. That is the theme telling you the clean names are not neglected.

---

## 8. Adversarial review

No mechanical BUY was produced, so there is no BUY to adversarially defend. The adversarial lens instead asks: *did the machine wrongly SUPPRESS a real opportunity?* Findings:

- **ASYS** is the only name a bull might call "suppressed" (insider cluster: 8 open-market buys, $1.13M; positive OCF $7.9M). But the suppression is correct: NAV MoS is −88.8% (trades at ~7x tangible book, not a value setup), and the P7 debt mismatch means the input numbers themselves are not trustworthy. Insider buying is a T2 signal that, per the frozen-catalyst / firewall rules, may not originate a BUY. **Suppression upheld.**
- **CVV** is a clean pure-play with zero flags — but it is a sub-$55M company burning cash at the trough with no computable intrinsic value. A WATCH (not BUY, not AVOID) is the honest verdict; nothing to override.
- **SKYT**'s headline P/E (15x) and +$119M NI would tempt a screen-driven BUY; the machine's refusal (negative OCF, null normalized FCF, 6.4x debt mismatch) is the *correct* defense against an accounting-income artifact.

**Conclusion:** the 0-BUY outcome is a true negative, not a coverage failure. The vetoes that fired (P7 cross-source on ASYS+SKYT; null-FCF-at-trough on all three fcf_cap names) are all legitimate.

---

## 9. Skeptical-PM usable verdict

**Usable: YES.** A skeptical PM gets exactly what this scanner is for: a clean "nothing to buy in the sub-$2B semicap tail right now," with the reasoning auditable end-to-end. Specifically valuable:

1. It **eliminated 7 false positives** (5 BDC lenders + Newegg + Intchains) that a keyword screen would have surfaced as semicap — the landmine-scanner working.
2. It **refused to fabricate a MoS** off negative trough FCF (CVV, SKYT) and off a −88.8% NAV (ASYS) — no narrative-driven BUY.
3. It **flagged two untrustworthy debt inputs** (ASYS, SKYT) before a human wasted time, and **flagged SKYT's non-cash net income**.
4. The one honest gap a PM should action manually: **IVAC (Intevac) and 4 other unpriceable tickers** dropped at discovery — worth a manual check, since IVAC is a genuine small-cap semicap name lost to a yfinance pricing gap, not to a kill-flag.

The two watch-band pure-plays a PM would actually want to track next (ICHR, and from the watch list AEHR/COHU/PDFS) are surfaced in the discovery log but correctly NOT deep-dived (out of the <$2B mandate). That is the right boundary, clearly stated.

---

## Artifacts

- Run dir: `reports/smallcap/2026-06-21_cov-semicap-equipment/`
- `RANKING.md`, `deepdive_verdicts.json`, `gate2_results.json`, `_run.json`
- `deepdive_{CVV,ELMT,ASYS,SKYT}_2026-06-21.json` (+ embedded valuation blocks), `valuation_*.json`, `report_*.md`
- `universe_semicap_equipment_2026-06-21.csv`, `cheappass_semicap_equipment_2026-06-21.csv`, `candidates_semicap_equipment.json`, `run_theme.log`
