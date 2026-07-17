# Coverage Test, coal-metcoal (Energy)

- **Skill version:** v0.3.0 @ commit `f12fef5`
- **Run batch:** `2026-06-21_cov-coal-metcoal` (label routed via `SMALLCAP_RUN`)
- **Theme keywords:** `coal, metallurgical coal, thermal coal`
- **Code-path focus:** cyclical / going-concern
- **Date:** 2026-06-21 (run), coverage-test-2026-06-20 docset
- **Verdict in one line:** Clean **0-BUY**. Every deep-band theme survivor failed the mechanical
  `buy_eligible` gate; the single positive-MoS name (NRP, +36.9%) was correctly vetoed by the
  V-shape `peak_contamination` guard, exactly the cyclical code-path this theme was chosen to stress.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery (FTS ∪ SIC-recall, after cheap_pass + SIC gate) | **49** | candidates JSON, `candidates_coal_metcoal.json` |
|, band split | 30 deep / 17 watch / 2 unknown | watch/unknown not deep-dived by design |
|, kill-flag ≥1 in deep band | 8 | (LAKE, EAF, FWRD, METC, CHNR, CMCL, MFIC, SID) excluded from BUY set |
| Deep band, kill=0 | 22 | candidate pool for theme-fit |
| LLM theme-fit survivors (true coal membership) | **5** | NC, SXC, KOP, HNRG, NRP |
| Deep-dived (full data + valuation) | **5** | zero `*_ERROR.json` crash files |
| Mechanical BUYs | **0** | all `buy_eligible=False` |
| Adversarially-clean BUYs (`n_buy_clean`) | **0** | honest zero |

**Funnel object:** raw=49, deepdived=5, survivors=0 (BUYs).

### Theme-fit gate detail (I judged membership from 10-K blurbs)

True coal / met-coal members carried into deep-dive (deep band, kill=0):

| Ticker | SIC | Membership | Basis |
|---|---|---|---|
| NC (NACCO) | 1221 | partial-coal | Lignite/thermal coal miner (mine-mouth fuels) + minerals + environmental |
| SXC (SunCoke) | 3312 | pure met-coal | "largest independent producer of coke...heating metallurgical coal" |
| HNRG (Hallador) | 4911 | thermal coal | Indiana coal producer + integrated power |
| NRP (Natural Resource Partners) | 1221 | partial/pure coal | Coal & mineral royalty MLP (met + thermal + soda ash) |
| KOP (Koppers) | 2400 | partial (coal-derivative) | Carbon materials from coal-tar distillation, borderline; kept conservatively |

**Misrecalls pruned by theme-fit (NOT coal, correctly dropped, NOT silent-skipped):** RAIL (railcars),
RYAM (cellulose), ACDC (frac services), ODC (cat-litter sorbents), GEL (crude midstream), REX (ethanol),
CVEO (workforce lodging), NOA (construction services), MTAL (copper), ITRG (gold/silver), OBE/GFR/VET (oil),
OCS (pharma), SB (dry-bulk shipping), CPAC (cement), GOLD (Barrick gold; blurb itself was an A-Mark
data mismatch), plus the kill-flagged names. These 25 deep-band non-members were finalized with
`--allow-missing` (legitimate theme-fit pruning, not crash-skip).

> **NB, true large-cap coal sits in the WATCH band by design:** BTU (Peabody), ARLP (Alliance),
> CNR (Core Natural Resources) all SIC 1221/1220 but >$2B → watch band, no deep-dive. This is the
> tool working as intended (calibrated for micro/small-cap), not a recall miss. METC (Ramaco), the
> purest small-cap met-coal name, is in the deep band but carries kill_flag=1 and is therefore
> correctly excluded from the BUY set.

---

## 2. Ranked shortlist

| Rank | Ticker | Rating | Conf | MoS | mos_basis | buy_eligible | kill | Why not BUY |
|---|---|---|---|---|---|---|---|---|
| 1 | NRP | 观察 WATCH | 45% | **+36.9%** | fcf_cap | False | 0 | `peak_contamination_veto` (V-shape value trap) |
| 2 ⬇ | HNRG | 避开 AVOID | 35% | −94.0% | fcf_cap | False | 0 | negative MoS + cross_source_mismatch (debt 4.8×) |
| 3 ⬇ | NC | 避开 AVOID | 35% | null | nav | False | 0 | NAV unquantifiable + fcf blocked by C1 guard + cross_source_mismatch (debt 5.8×) |
| 4 ⬇ | SXC | 避开 AVOID | 35% | −51.7% | fcf_cap | False | 0 | negative MoS + `peak_contamination_veto` |
| 5 ⬇ | KOP | 避开 AVOID | 30% | −182.2% | fcf_cap | False | 0 | extreme-negative MoS (`extreme_mos_review_required`) |

`RANKING.md` and `deepdive_verdicts.json` both written by `finalize_run.py`.

---

## 3. BUYs

**None.** This is an honest 0-BUY theme. No name cleared
`mos_basis∈{fcf_cap,nav}` AND MoS≥30 AND `buy_eligible==true` AND 0 kill-flags simultaneously.

### Closest call, NRP (the only positive-MoS name), adversarial autopsy

NRP is the case worth examining because it is the one place the gate could plausibly have leaked a
false BUY: MoS = **+36.9%** on an `fcf_cap` basis, 0 kill-flags. It was blocked solely by
`peak_contamination_flag` (`buy_ineligible_reasons: ['peak_contamination_flag']`).

- **Why the veto fired:** `contamination_ratio=0.7445`, `latest_below_avg=True`, normalized 5-yr
  FCF = $223M while the cyclical EBITDA CV = **1.07** (>> 0.25 threshold; `cyclical=True`). The
  +36.9% MoS is computed against peak-cycle normalized FCF inflated by the 2022 to 2023 coal-royalty
  boom; the company has since rolled over.
- **Independent confirmation of the rollover (does NOT rely on the veto's own input):** OCF
  trajectory $311M (2023) → $248M (2024) → **$166M (2025)**; revenue −16.6% YoY. The trough→peak→
  rollover shape the veto is designed to catch is real in the raw cash-flow series.
- **Data-quality caveat I found (recorded, see §5):** the XBRL `net_income` series the veto quoted
  as "latest" (−$84.8M @ 2020-12-31) is mis-tagged, it is the **2020 COVID-trough loss**, not the
  most recent fiscal year (the NI series tail terminates at 2020 while revenue/OCF run to 2024/2025).
  So one veto input is stale/mislabeled.
- **Adversarial verdict on the verdict:** **The block is correct despite the stale NI datum.** The
  rollover is independently corroborated by the current OCF/revenue decline and the inflated
  peak-cycle FCF base. Lifting the veto would surface a backward-looking commodity-peak artifact as a
  BUY, precisely the v0.2.0 failure mode this guard was built to kill. NRP is a legitimate **WATCH
  for human diligence**, not a suppressed opportunity. **Not a false negative.**

---

## 4. Code-paths fired (coverage)

| Guard / path | Fired on | Role |
|---|---|---|
| SIC reverse-recall floor (1220/1221) | discovery | enumerated coal registrants incl. low-keyword names |
| Two-stage SIC gate (Gate 1) | 49→49 (keep 47 / review 2) | coarse off-theme exclusion |
| LLM theme-fit (Gate 2) | 22→5 | pruned 17 misrecalls (frac/cement/shipping/oil/precious-metals) |
| cheap_pass kill-flags | 12 of 49 killflag≥1 | mechanical de-risk before judgment |
| **peak_contamination_veto** (V-shape) | **NRP, SXC** | blocked positive/near-MoS cyclical trap, primary code-path under test |
| extreme_mos_review_required (>100%) | KOP (−182%) | blocked extreme-MoS artifact |
| cross_source_mismatch (>2.5× SEC vs yf debt) | NC (5.8×), HNRG (4.8×) | blocked BUY on debt disagreement |
| fcf_cap_blocked_by_c1_data_quality_guard | NC | C1 data-quality gate |
| nav path (tangible-equity proxy) | NC | NAV attempted, MoS null (goodwill/intangible unavailable) |
| net_income_nonpositive_pe_null | SXC, NRP | P/E suppressed on loss-makers |
| ebitda_series_partial_entries | KOP, HNRG, NRP | partial-series flag |
| Diagnostic signals side-channel (firewalled) | all 5 | recorded `price_divergence`/`ownership`; NRP labeled "aligned" with `diagnostic_only=true, never_affects_buy=true`, did NOT touch any buy_eligible |

The cyclical/going-concern focus path was exercised end-to-end: `cyclical=True` + high CV +
`peak_contamination` on the royalty/met-coal names is exactly the going-concern-adjacent cyclical
machinery, and it produced the correct 0-BUY.

---

## 5. Data-quality issues

1. **NRP net_income XBRL fiscal-year mis-tag**, NI series terminates at 2020-12-31 (−$84.8M, the
   COVID trough) and is consumed by the peak_contamination veto as "latest," while revenue/OCF series
   run correctly to 2024/2025. Outcome unaffected (rollover independently confirmed), but the veto's
   quoted datum is stale. Worth a deepdive_data fy-alignment fix.
2. **NC cross_source_mismatch**, total_debt SEC=$23.1M vs yfinance=$133.9M (5.8×); blocks BUY (correct
   conservative behavior) but flags an SEC XBRL debt-truncation / scope issue. Also `debt_stale:>18mo`.
3. **HNRG cross_source_mismatch**, total_debt SEC=$29.7M vs yfinance=$6.2M (4.8×).
4. **NC NAV path**, goodwill/intangibles unavailable; tangible equity falls back to book-equity proxy,
   MoS ends null → no NAV BUY possible.
5. **GOLD blurb data mismatch**, candidate "BARRICK GOLD CORP" (CIK) returned an A-Mark precious-metals
   business description. Off-theme either way (pruned), but a blurb/entity mismatch.
6. **Several partial EBITDA series** (KOP:2, HNRG:4, NRP:2), normalization on thin history.

No silent skips, no crash files (`deepdive_*_ERROR.json` = 0). Console GBK encoding noise on Windows
is cosmetic (handled with `PYTHONIOENCODING=utf-8`).

---

## 6. recall@gold

**n/a**, `coal-metcoal` is not in `THEME_GOLD` (only water-utilities / railcar-leasing /
regional-gaming / deathcare have gold lists). `track_forward.py --recall-gold` returned
"no gold list for theme 'coal-metcoal', not measurable." Not measurable for this theme.

---

## 7. Market-intel / Trends context (T2, firewalled, does NOT drive buy_eligible)

- **TrendsMCP, "metallurgical coal" Google search:** +50% YoY (12M, value 22→33; volume 923→1385)
  but **−44% over the last 3M** (59→33). A post-peak fade in attention.
- **Read-through:** the 3M momentum rollover corroborates the cyclical-peak interpretation that the
  `peak_contamination` veto reached mechanically on NRP/SXC. This is analyst color only; it had no
  effect on any `buy_eligible` decision (firewall intact).

---

## 8. Skeptical-PM usable verdict

**Usable: YES.** The scanner did its job as a landmine-detector. For a commodity theme at/just past a
cyclical peak, the correct answer is "no clean small-cap industrial beneficiary to underwrite right
now," and that is exactly what it returned, with the most dangerous case (a +37% MoS that a naive
screen would surface as a BUY) correctly quarantined by the V-shape veto and independently confirmed by
the cash-flow rollover. The only follow-up for a PM is NRP as a WATCH (re-check after the next
royalty cycle), and a fix ticket for the NRP NI fiscal-year tagging. No false BUY leaked.
