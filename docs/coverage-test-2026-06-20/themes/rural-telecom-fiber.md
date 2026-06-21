# Coverage Test — rural-telecom-fiber (CommSvcs)

**Run:** `reports/smallcap/2026-06-21_cov-rural-telecom-fiber/`
**Skill:** small-cap-deepdive v0.3.0 (commit `f12fef5`, run flagged `skill_dirty=true`)
**Theme keywords:** `rural telecom, fiber broadband, local exchange carrier`
**Code-path focus:** capital-intensive / debt
**Date:** 2026-06-21 (batch dir under coverage-test-2026-06-20)

> Research output, not investment advice. This skill is a landmine-scanner; a survivor is a
> name worth human DD, not a buy. The headline result here is a clean, *true* **0-BUY**.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discover universe (FTS + mktcap filter) | 21 candidates written | discover → cheap_pass → SIC gate |
| After cheap_pass (mechanical de-risk) | 21 survivors | 0 hard kill-flag eliminations at this stage |
| After SIC Gate-1 (tri-state) | 21 (keep=16, review=5) | no `drop`; 5 routed to LLM as `review` |
| **Deep band (band="deep")** | **12** | the small-cap names that earn a full deep-dive |
| Watch band (band="watch", >$2B) | 8 | UNIT, RNG, LBRDA, TDS, PHI (+ dup UNIT rows) — not deep-dived |
| Unknown band (null mktcap) | 1 | NRUC (National Rural Utilities Coop Finance) |
| **LLM theme-fit survivors (deep band)** | **6** | pure_play/partial; 6 dropped as misrecall |
| Deep-dived (deepdive_data + valuation) | 6 | NUVR, ATNI, SHEN, CLFD, GLIBA, CABO — **0 ERROR files** |
| **Mechanical BUYs** | **0** | none clears mos_basis∈{fcf_cap,nav} AND MoS≥30 AND buy_eligible AND zero kill-flags |
| BUYs surviving adversarial verification | **0** | true 0-BUY, not artifact suppression |

**Note on funnel field `raw`:** the candidates JSON holds 21 rows (UNIT appears 4× from the
SIC reverse / dual-tier join). Distinct tickers = 17. I report raw=21 (rows written) for
auditability and deepdived=6.

### LLM theme-fit decisions (deep band, 12 names)

| Ticker | SIC | Decision | Rationale (from Item-1 blurb) |
|---|---|---|---|
| NUVR | 4813 | **pure_play** | New Ulm Rural Telephone — 120-yr rural ILEC, MN |
| ATNI | 4813 | **pure_play** | digital infra in smaller/rural/remote US + Alaska + Caribbean |
| SHEN | 4813 | **pure_play** | Shentel fiber/cable broadband, ~19k route-mi fiber, eastern US |
| CABO | 4841 | **pure_play** | Cable One / Sparklight broadband in smaller-market footprints |
| GLIBA | 4841 | **pure_play** | GCI — Alaska's largest telecom/broadband (rural Alaska) |
| CLFD | 3661 | **partial** | Clearfield — fiber mgmt/delivery *equipment* for Tier-2/3 telcos (enabler, not LEC) |
| CXDO | 4813 | misrecall | cloud UCaaS SaaS — not rural fiber/LEC infra |
| AIRG | 3663 | misrecall | wireless antenna/RF components — not rural telecom |
| KODK | 3861 | misrecall | print + chemicals conglomerate |
| GILT | 3663 | misrecall | satellite networking (Israel) — satellite sub-sector |
| AGM | 6111 | misrecall | Farmer Mac — ag secondary-mortgage finance (financial SIC; "rural" keyword only) |
| LILA | 4841 | misrecall | Liberty Latin America — intl LatAm/Caribbean carrier, not rural-US LEC |

All 6 misrecalls were resolved in `gate2_results.json`, so finalize_run reports **missing=0**
(12 deep-band = 6 reports + 6 gate2-misrecall resolved).

---

## 2. Ranked shortlist (all sunk)

From `RANKING.md` — every name sinks (non-bottom tier = 0).

| Rank | Ticker | mc | Rev | NI | OCF | norm_FCF | EV/EBITDA | buy_eligible | mos_basis | MoS | kill-flag |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1↓ | ATNI | $396M | $667M | -$24M | $134M | **-$12.7M** | 5.3x | True | fcf_cap | **null** | 0 |
| 2↓ | CABO | $233M | $1501M | -$357M | $563M | $358M | 0.7x* | False | nav | -1.0 | 1 |
| 3↓ | CLFD | $550M | $150M | -$8M | $22M | $6.6M | 65.9x | False | fcf_cap | -0.89 | 0 |
| 4↓ | GLIBA | $838M | $1046M | -$309M | $370M | $122M | None | False | fcf_cap | -0.44 | 0 |
| 5↓ | NUVR | $93M | $54M | $0M | $19M | **-$14.1M** | 7.9x | True | fcf_cap | **null** | 0 |
| 6↓ | SHEN | $784M | $358M | -$33M | $101M | **-$236.2M** | 13.5x | True | fcf_cap | **null** | 0 |

\* CABO's 0.7x EV/EBITDA, 0.06x EV/Sales and 1.20 FCF-yield are **artifacts** of debt truncation
(SEC total_debt $24.9M vs Yahoo $3.1B — 125x mismatch); the guards correctly voided the BUY.

---

## 3. The BUY rule, applied name-by-name (honest 0-BUY)

BUY = `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30` AND `buy_eligible == True` AND zero kill-flags.

- **ATNI** — buy_eligible=True, mos_basis=fcf_cap, **MoS=null** (`intrinsic_band_unavailable`).
  Normalized FCF = **-$12.7M** (5-yr trailing avg) → no fcf_cap band → no numeric MoS. Fails "MoS≥30". **NOT BUY.**
- **NUVR** — buy_eligible=True, mos_basis=fcf_cap, **MoS=null**. Normalized FCF = **-$14.1M** (latest). **NOT BUY.**
- **SHEN** — buy_eligible=True, mos_basis=fcf_cap, **MoS=null**. Normalized FCF = **-$236.2M** (5-yr avg; heavy fiber capex). **NOT BUY.**
- **CLFD** — buy_eligible=**False** (`cross_source_mismatch`: total_debt SEC $2.4M vs yf $10.9M, 4.6x). Also MoS=-0.89 (overvalued vs FCF floor). **NOT BUY.**
- **GLIBA** — buy_eligible=**False** (`cross_source_mismatch`: shares_out SEC 31.0M vs yf 3.7M, 8.5x). MoS=-0.44. **NOT BUY.**
- **CABO** — buy_eligible=**False** (`debt_truncation_suspected` + `cross_source_mismatch`). nav MoS=-1.0. **NOT BUY.**

**Result: 0 mechanical BUYs.** `n_buy_clean = 0`.

---

## 4. Code-paths that fired (capital-intensive / debt focus — the test's target)

This theme was chosen to stress the debt / capex guards, and they fired exactly as designed:

1. **`intrinsic_band_null:normalized_fcf_nonpositive`** (ATNI, NUVR, SHEN) — the central
   capital-intensive path. Fiber/LEC operators burn operating cash into capex; the 5-yr
   normalized FCF goes negative → fcf_cap intrinsic band is legitimately *unavailable* →
   MoS abstains rather than fabricating a number. mos_basis stays `fcf_cap` but MoS=null,
   so the BUY rule's "numeric MoS≥30" requirement blocks the BUY. **This is the headline
   correct behavior** — the model abstains on capex-heavy names instead of mis-buying them.
2. **`debt_truncation_suspected`** (CABO) — reported total_debt $24.9M vs implied
   (liab−equity) $2,572M, ratio 0.01 → debt clearly truncated in the XBRL pull → fcf_cap
   blocked, forced to NAV basis. Tangible-equity NAV band = $0 (goodwill+intangibles of
   $2.79B fully deducted) → NAV MoS = -1.0. Guard prevented a fake deep-value BUY on a
   leveraged cable operator.
3. **`cross_source_mismatch`** (CLFD total_debt 4.6x; GLIBA shares_out 8.5x; CABO total_debt 125x)
   — SEC-vs-Yahoo gross disagreement (>2.5x) is a buy_eligible kill. Three of six survivors
   tripped it, all on debt or share-count fields, i.e. precisely the leverage-sensitive inputs.
4. **`debt_stale:>18_months_behind_latest_assets`** (CABO) — staleness flag on the debt series.
5. **`rdcf_implied_growth_very_negative:market_pricing_in_decline`** (CABO) — reverse-DCF reads
   the market as pricing structural decline.
6. **`fcf_cap_blocked_by_c1_data_quality_guard`** (CABO) — C1 data-quality guard hard-blocks
   the fcf_cap path before it can emit a MoS.
7. **SIC `review` routing** (5 names incl. AGM 6111 financial, UNIT 6798 REIT, RNG 7374, NRUC 6159)
   — tri-state Gate-1 didn't auto-drop financial-SIC hits; it forwarded them to the LLM gate,
   which correctly classified AGM and LILA as misrecall.
8. **band gating** — 8 watch-band names (>$2B: UNIT, RNG, LBRDA, TDS, PHI) were correctly held
   out of the deep-dive (large-cap-out-of-scope precursor).

**Not fired (correctly):** going_concern / death_spiral / material_weakness (0 cheap_pass kills);
peak_contamination / fundamental_decline / extreme-MoS / insurance / concentration-kill /
low_revenue_loss_extreme (all False on the 6 survivors).

---

## 5. Adversarial verification (mandatory for any BUY; here: verifying the 0-BUY)

There are no mechanical BUYs, so the adversarial question inverts: **did a guard wrongly
suppress a genuine bargain?** The most plausible "wrongly-killed BUY" is **ATNI** (positive
trailing FCF-yield 11%, low EV/EBITDA 5.3x, buy_eligible=True).

- ATNI's 11% FCF yield is a **single-year snapshot**; the 5-yr *normalized* FCF is **-$12.7M**
  because the rural-fiber build cycle consumes OCF. The fcf_cap abstention is therefore
  *correct*, not a bug — a capex-cycle business should not be valued off one good cash year.
- NUVR (-$14.1M norm FCF) and SHEN (-$236.2M norm FCF) are unambiguously capex-negative; no
  reasonable FCF-cap band exists. Correct abstention.
- CLFD / GLIBA / CABO were killed by cross-source/debt-truncation guards on the *exact* fields
  (debt, shares) where a leveraged small-cap value trap hides. CABO's 0.7x EV/EBITDA "bargain"
  is a pure data artifact of a 125x debt mismatch — the guard caught a landmine.

**Adversarial verdict: the 0-BUY is real.** No survivor is a suppressed opportunity; the guards
abstained on capex-heavy or data-broken names rather than minting an artifact BUY. This is the
designed-for outcome of the capital-intensive code path. `n_buy_clean = 0`.

---

## 6. Data-quality issues observed

- **Cross-source (SEC vs Yahoo) mismatches on leverage fields** — 3 of 6 survivors: CLFD
  total_debt 4.6x, GLIBA shares_outstanding 8.5x, CABO total_debt 125x. Endemic to this
  capital-intensive sector; the guard is load-bearing here.
- **CABO debt truncation** — XBRL total_debt $24.9M vs implied $2.57B; the most severe
  single data defect in the run. Correctly downgraded to NAV and then blocked.
- **Negative normalized FCF → null intrinsic band** on the 3 pure-play LECs (ATNI/NUVR/SHEN) —
  not a defect, but it means the fcf_cap model is structurally non-informative for this theme;
  a NAV-first or EV/EBITDA-relative lens would be the right T1 valuation basis for these names.
- **Concentration unquantified** (text flag true, XBRL magnitude null) on NUVR/ATNI/SHEN —
  flagged, did not kill.
- **CLFD lumpy-OCF** (peak-year OCF $18.4M > 2× median $8.8M) — normalization-suspect flag.
- **UNIT duplicated 4×** in candidates JSON (SIC-reverse / dual-tier join) — cosmetic; watch
  band, not deep-dived.

---

## 7. recall@gold

**n/a.** `rural-telecom-fiber` has no gold list (gold cohorts exist only for water-utilities,
railcar-leasing, regional-gaming, deathcare). It also has **no SIC recall-floor** (THEME_SIC has
no rural-telecom entry), so discovery ran on FTS + mktcap-fallback only, with no SIC reverse-recall
union. Tool output verbatim:

```
recall@gold: no gold list for theme 'rural-telecom-fiber' — not measurable
```

---

## 8. Market-intel / TrendsMCP (T2 analyst context)

**Unavailable this run** — TrendsMCP returned `5/5 daily, 100/100 monthly requests` exhausted;
market-intel was not invoked. Per skill rules, T2 enrichment is decorative and **never drives
buy_eligible**, so its absence does not affect the 0-BUY result. Qualitative T2 context (analyst
prior, not data): US rural fiber is in a heavy government-subsidized build phase (BEAD-era capex),
which is *consistent* with the model's finding that these operators are FCF-negative on a normalized
basis — capital is going into the ground, not to owners. This supports, rather than contradicts,
the abstention.

---

## 9. Signals side-channel (firewall check)

The signals diagnostic is firewalled by construction: `tools/signals.py` documents that its
output "MUST NOT be read by valuation.py, the buy_eligible composite, or the BUY trigger… Signals
can NEVER originate or up-weight a BUY." No signal file was emitted into this run dir; regardless,
buy_eligible on all 6 names is derived purely from T1 filing valuation + guards. **No BUY was
affected by signals.** Confirmed.

---

## 10. Skeptical-PM usable verdict

**USABLE — and a good test of the machine.** The pipeline ran end-to-end synchronously with
zero crashes (0 ERROR files), correctly enumerated the rural-telecom/fiber universe, used the
LLM gate to strip 6 obvious misrecalls (a SaaS UCaaS player, an antenna maker, Kodak, an Israeli
satellite co, Farmer Mac, and a LatAm carrier), and then **refused to manufacture a BUY** out of
six capex-heavy / data-broken operators. The capital-intensive code path did its job: it abstained
on negative-normalized-FCF LECs and killed the cross-source/debt-truncation artifacts (notably
CABO's 0.7x "EV/EBITDA bargain"). A skeptical PM gets exactly what they should from a hot,
subsidy-driven, capital-intensive theme — a clean, defensible **0-BUY** with a full audit trail,
not a list of leverage traps dressed as value. The one caveat for a human: fcf_cap is the wrong
primary lens for rural LECs (structurally FCF-negative in build phase); a follow-up NAV / EV-EBITDA
relative pass on ATNI/SHEN/NUVR would be the sensible next human step — but that is a deeper-DD
question, not a defect in the screen.

---

### Artifacts (all under `reports/smallcap/2026-06-21_cov-rural-telecom-fiber/`)
- `candidates_rural_telecom_fiber.json` (21 rows / 17 distinct)
- `deepdive_{NUVR,ATNI,CLFD,SHEN,GLIBA,CABO}_2026-06-21.json` (6, no ERROR files)
- `valuation_{…}_2026-06-21.json` (6)
- `report_{…}.md` (6, with data-quality trust banners)
- `gate2_results.json` (12 rows — 6 survivors + 6 misrecall resolutions)
- `deepdive_verdicts.json` (6)
- `RANKING.md` (trust banner + ranked shortlist, 0 non-bottom)
