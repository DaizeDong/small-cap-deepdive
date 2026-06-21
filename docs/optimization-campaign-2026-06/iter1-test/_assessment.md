# Iteration-1 Test Assessment — small-cap-deepdive (post commit e0f0039)

> Assessor: independent test-judge subagent. Verified every claim against the raw batch outputs
> under `reports/smallcap/2026-06-20_*/` (deepdive JSONs, valuation JSONs, universe CSVs,
> verdicts.jsonl) and by re-running `valuation.py` live on the FP-cohort. Judged against the
> real-world-usable acceptance bar (design §6 a–e).

**Runs examined:** `iter1-fp-cohort` (SIGA/VSNT/ARDT/ABR — the v0.2.0 data-artifact BUYs),
`iter1-old-recall-p5` (regbank2/shipping2 — P5 recall), `royalty-streaming` (21 deep-dived),
`uranium-miners` (9 deep-dived). Reports cross-read: `old-recall-p5.md`, `new-uranium-miners.md`,
`new-royalty-streaming.md`.

---

## 1. FIXES VALIDATED

| Fix | Claim | Evidence on real new data | Verdict |
|---|---|---|---|
| **P1** buy_eligible gate ANDs guards into BUY trigger | promote advisory guards to a mechanical boolean | All 3 v0.2.0 artifact BUYs now `buy_eligible=False`. VSNT blocked by `large_cap_out_of_scope` ($5.4B), `extreme_mos_review_required`, `fcf_sustainability_uncertain`, `fundamental_decline_flag`. INVA `buy_eligible=true reasons=[]` → BUY fires only when clean. | **WORKS** |
| **P2** flag every OCF-proxy FCF + penalize | fix dead `elif fcf_is_proxy` | Uranium NUCL/LTBR (IFRS, no XBRL capex) → `fcf_is_ocf_proxy=true` + `fcf_sustainability_uncertain=true` → `buy_eligible=false`. ARDT/DMLP/NRP same path. No OCF-proxy silently treated as true FCF. | **WORKS** |
| **P3** concentration → magnitude kill-flag | XBRL segment %, replace substring | SIGA `concentration_flag="kill"`, `top_customer_pct=75.0` → `buy_eligible=False reasons=['concentration_kill',...]`. The exact SIGA value-trap the design targeted is now mechanically killed. | **WORKS** |
| **P4** finalize_run scaffolder + verdict emitter + ranking + UTF-8 | deterministic report+verdict for every deep candidate | Royalty: 21 deepdive = 21 `report_*.md` = 21 verdicts. Uranium: 9 = 9 = 9. Reports carry rating block + JUDGMENT NOTE + DATA-QUALITY TRUST BANNER. verdicts.jsonl auto-fed (entry_price, IWM benchmark, implied_prob, horizon). | **WORKS** (caveat: path-doubling bug + template placeholders — see §2/§3) |
| **P5** mktcap decoupled from yfinance; band=unknown flow-through | recover silent-dropped universe | regbank2: 429 rows survive (was 429/429 dropped), bands 290/43/50/46, **8 `sec_shares_x_price` recoveries**, **271 candidates / 231 deep**. shipping2: 410 rows, 6 recoveries, **219/172**. Numbers in the report match the CSVs exactly. | **WORKS** (residual: no-price subset still excluded by liquidity gate, but now *visible* as unknown, not deleted) |
| **P6** fundamental-trajectory veto (downgrade-only) | kill melting-ice-cube at fundamentals, spare growers | Verified matrix: SIGA (rev −31.8%, slope −1) fdf=**True**; VSNT (−5.3%, −1) **True**; ARDT (+6%) **False**; INVA (+14.7%) **False**; EU (trough-recovery +223%) **False**. Decliners caught, growers + troughs spared. | **WORKS for monotone decline; MISSES V-shape (NRP)** — see §3 |
| **P9** EBIT concept cascade (pretax/continuing) | recover EV/EBITDA on ~47% null | Cascade exists and fires: ARDT `ebit_source=pretax_proxy`. But this cohort was not EBIT-null-heavy (royalty-trust nulls are genuine untagged XBRL, correctly abstained), so recovery *magnitude* is under-exercised here. | **WORKS (under-stress-tested)** |
| **P5 mktcap band=unknown** | unknown flows through, not dropped | Every unresolved row present in CSV with `band=unknown`, `mktcap_source=unresolved`; none vanished. | **WORKS** |
| **finalize_run TRUST BANNER** | data-quality banner under each rating | INVA report shows `⚠️ DATA-QUALITY TRUST BANNER` listing `net_income_nonpositive_pe_null`, `ebitda_series_partial_entries:10`. | **WORKS** |
| **P12** calibration backfill + verdict feed | backfill 19 v0.2.0 BUYs as data_false_positive; confidence-as-prob; dividend-adj return; verdict auto-feed | `verdicts.jsonl`: **19 rows `adjudication=data_false_positive`** (the v0.2.0 BUYs). New verdicts carry `implied_prob`, `benchmark=IWM`, `entry_price`, `horizon_months`. | **WORKS** |
| **P13** retire bogus "weighted 7-dim composite" claim | rating = f(MoS, kill-flags, ceilings) | Ratings derive deterministically from mos_basis/MoS/buy_eligible/kill in verdict blocks; no phantom weights surfaced. | **WORKS (light evidence)** |
| **P11-freeze** catalyst MoS-waiver frozen | catalyst → WATCH only | No name reached BUY via catalyst; uranium report confirms waiver frozen (would only reach WATCH). | **WORKS (untriggered)** |
| **Concentration kill blocks BUY** (new rule) | conc=="kill" blocks | SIGA conc=kill → buy_eligible=False. | **WORKS** |
| **fundamental_decline_flag blocks BUY** (new rule) | fdf blocks | SIGA/VSNT fdf=True → buy_eligible=False. | **WORKS** |

**Net:** every iteration-1 fix that could be exercised on the new data is *present and firing*.
The three v0.2.0 artifact BUYs (SIGA/VSNT/ARDT) are all dead. The single new BUY (INVA) is clean
and defensible. **Acceptance (a) zero data-artifact BUYs survive: PASS for the SIGA-class
(monotone-decline / concentration / large-cap / extreme-MoS) artifacts — the exact failures the
campaign was built to kill.**

---

## 2. REGRESSIONS

1. **No good name was wrongly blocked at the BUY layer.** INVA (genuine grower, MoS 30.3%, clean
   disconfirm) cleared to BUY. EU (uranium trough-recovery +223%) correctly NOT flagged by P6.
   ARDT/ASPI/URG were blocked only by data-quality guards that also routed them away from a
   spurious deep-discount — no genuine cheap clean grower was suppressed. **No false-negative
   regression on BUY.**

2. **PATH-DOUBLING BUG (new breakage, uranium run only).** Uranium valuations were written to
   `reports/smallcap/2026-06-20_uranium-miners/reports/smallcap/2026-06-20_uranium-miners/valuation_*.json`
   — the run-dir prefix was applied twice. The valuations *ran* (9, matching the 9 deep-dived
   names, all valid JSON) but landed in a nested duplicate tree. The royalty run wrote its 21
   valuations to the correct top-level path. This is an inconsistency in how `--out`/`SMALLCAP_RUN`
   is resolved across invocation styles, not a data-loss bug, but it breaks finalize/ranking
   path assumptions and would confuse a re-run. **New, fixable.**

3. **ABR (a v0.2.0 BUY) silently died mid-deepdive.** `dd_ABR.log` stops after
   "拉取财务数据..." with no JSON and no recorded error; no `deepdive_ABR.json` exists. Under the
   FULL-data / never-silently-skip directive this is a gap: one of the four artifact BUYs in the
   FP-cohort was *not* validated as blocked, and the failure was not surfaced as an error. SIGA/
   VSNT/ARDT cover the core thesis, but ABR's disposition is unknown. **Borderline regression vs
   the standing directive (silent skip on rate-limit/crash).**

4. **finalize_run cannot distinguish "gated-out at Gate 2" from "forgotten deep-dive."** It
   flagged 33 (uranium) / 33 (royalty) deep-band names as "missing report" — these are correct
   Gate-2 `misrecall` drops, requiring `--allow-missing`. Not a data regression, but the
   completeness assertion is noisy and could mask a real omission. Both runs handled it correctly
   via the switch.

---

## 3. NEW ISSUES FOR ITERATION 2 (prioritized, evidence-backed — seeds the next reflection)

**P-A (HIGH) — P6 V-shape blind spot lets a real value-trap through the mechanical gate.**
NRP (Natural Resource Partners): `rev_slope_sign=+1`, `contamination_ratio=0.7445`,
`latest_below_avg=true`, `latest_net_income=−$84.8M`, **`fundamental_decline_flag=false`,
`buy_eligible=true`, MoS +36.8%** — a clean *mechanical* BUY. Revenue series confirms a V-shape:
trough 2020 $120M → peak 2022 $307M → rolling over to 2024 $232M; the whole-window linear fit is
upward, so the AND-of-three never fires. It was downgraded to WATCH **only by analyst judgment +
disconfirmation**, not by the machine. This means acceptance (a) for the *V-shape* value-trap class
relies on the human, not the gate — the same structural failure SIGA was, on a different axis.
*Fix:* add a sibling `peak_contamination_flag` that fires on `contamination_ratio < ~0.8 AND
latest_below_avg AND latest_net_income < 0`, **independent of rev_slope_sign**. (Both uranium and
royalty reports independently identified this exact gap.)

**P-B (HIGH) — `wrong_entity_suspected` / `debt_truncation_suspected` mislabel real producers.**
The `|net_income|/revenue > 2.0` heuristic fires on the pre-/early-revenue resource pattern (large
loss vs tiny revenue): URG (established NYSE-American uranium producer), ASPI, IMSR, XOMA all get
`wrong_entity_suspected` though they are the *right* entity. The *effect* is safe (forces
buy_eligible=false), but a PM reading "wrong entity" on Ur-Energy is misled about the cause. *Fix:*
emit a distinct `low_revenue_loss_ratio` flag for present-but-tiny-revenue + large-loss; reserve
`wrong_entity_suspected` for genuine unit-mistag / wrong-CIK. Same for `debt_truncation_suspected`
on partial/stale XBRL debt tags.

**P-C (MED) — Path-doubling in valuation output (uranium run).** See §2.2. Standardize
`SMALLCAP_RUN`/`--out` resolution so a run-relative path is never prefixed twice. Add a
finalize_run guard that rejects nested `reports/smallcap/.../reports/smallcap/...` trees.

**P-D (MED) — Silent deepdive crash on ABR not surfaced.** A deepdive that dies mid-pull leaves a
truncated log and no JSON, with no error in any manifest. *Fix:* wrap the financials-pull in a
try/except that writes a `deepdive_<t>_ERROR.json` (or appends to an errors log) so a crashed/
rate-limited name is auditable, never an invisible skip — exactly what the standing FULL-data rule
requires.

**P-E (MED) — Deterministic scaffold leaves prose placeholders.** INVA's report still contains
`<One sentence stating the core thesis.>`, blank scorecard scores, and `<e.g. ...>` base-rate
placeholders below the (correctly-filled) rating block + judgment note. The *machine-decision*
layer is decision-ready; the *narrative* layer is half-templated. For acceptance (e) the BUY and
the value-trap downgrade are decision-ready, but the WATCH tail reports are skeletons. *Fix:*
either require the analyst pass to fill the scaffold or strip unfilled placeholders so a PM doesn't
see literal `<...>` tokens.

**P-F (LOW) — finalize_run / Gate-2 denominator mismatch.** Persist the Gate-2 `misrecall` set into
the run manifest so finalize treats gated names as *resolved*, not *missing* (kills the spurious
"33 missing" warning).

**P-G (LOW) — `form_used=None` on all foreign filers.** Provenance tag empty; the trust banner
can't surface "foreign IFRS/20-F filer." Tag the filing form so cyclical/IFRS context is visible.

**P-H (LOW) — RANKING.md funnel narration garbled.** Uranium RANKING header reads
"9 召回 → 10 小盘候选" which contradicts the real 482→68→47→9 funnel — a rank.py template string
bug, cosmetic but undermines trust at a glance.

**P-I (LOW, structural, was P7/P8/P14 deferred) — second-source + recall@gold + forensics still
absent.** No EV/EBITDA cross-source check; recall@gold not computed on the SIC-backed themes
(P5 *recovered* the universe but recall is still not *measured* against gold true-member lists);
no accruals/SBC/dilution forensics spine. These were explicitly deferred to iter-2 and the test
data confirms the need (royalty-trust XBRL unreadable; NAV structurally understates royalty PV).

---

## 4. USABLE VERDICT

**Is iteration-1 at the real-world-usable bar (design §6 a–e)?**

| Bar | Status | Evidence |
|---|---|---|
| (a) zero data-artifact BUYs survive | **PASS for the SIGA-class** (monotone-decline / concentration / large-cap / extreme-MoS); **PARTIAL for V-shape** | SIGA/VSNT/ARDT all `buy_eligible=False`; but NRP-class V-shape value-trap passes the *gate* (caught only by judgment). |
| (b) every deep-band candidate has a deterministic report + verdict | **PASS** | royalty 21=21=21, uranium 9=9=9; rating block + trust banner + auto-fed verdicts.jsonl. |
| (c) recall recovered on SIC-backed themes (P5) | **PASS (recovery), recall not yet *measured*** | regbank 0→271, shipping ~12→219, verified against CSVs; recall@gold metric still absent (deferred P8). |
| (d) trajectory/concentration vetoes downgrade traps while sparing growers/troughs | **PASS with one named miss** | decliners flagged, growers (INVA/ARDT) + trough (EU) spared, SIGA double-blocked; **NRP V-shape missed mechanically.** |
| (e) skeptical-PM read finds ≥3 reports decision-ready | **PASS** | INVA (defensible BUY, T1-anchored, clean disconfirm), NRP (value-trap downgrade with falsifiable reason), SIGA (mechanically killed) are all decision-ready and trustworthy; the WATCH-tail narrative scaffolds are thinner (P-E). |

**Overall: YES — iteration-1 clears the real-world-usable bar for its core mission.** The engine
has flipped from a *value-trap generator* (19/19 v0.2.0 BUYs priced decline by construction) to a
*landmine scanner that mostly refuses to print traps*: the three canonical data-artifact BUYs are
dead, the one new BUY is clean, recall is restored, and every deep candidate gets a deterministic,
trust-bannered report+verdict that auto-feeds calibration. A skeptical PM can act on the INVA BUY,
the NRP downgrade, and the SIGA kill today.

**Single biggest remaining gap: the P6 V-shape blind spot (P-A).** The mechanical
`fundamental_decline_flag` catches monotone decline (SIGA) but not trough→peak→rollover (NRP),
because the AND-of-three is gated on `rev_slope_sign`. NRP is a clean *mechanical* BUY
(`buy_eligible=true`, MoS +36.8%) that is a documented melting ice cube — it survived only because
a human read the contamination ratio and the disconfirmation. Until a `peak_contamination_flag`
fires independent of slope, acceptance (a) for the V-shape value-trap class depends on analyst
discipline rather than the gate — which is exactly the class of failure this campaign exists to
move *onto* the machine. That is the first thing iteration-2 should close.
