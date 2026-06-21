# Coverage Test — Theme: regbank (REGRESSION)

- **Slug:** `regbank`
- **Sector tag:** REGRESSION
- **Keywords (FTS):** `community bank, regional bank, deposits`
- **Code-path focus:** financial-SIC exclusion firewall + P5 recall
- **Run batch:** `reports/smallcap/2026-06-21_cov-regbank/`
- **Skill commit:** f12fef5 (v0.3.0, dirty workspace)
- **Date:** 2026-06-21
- **Headline result:** **0 BUYs (correct).** The financial-SIC firewall blocked every one of
  the 37 theme-fit community/regional banks from `buy_eligible`, including banks with NAV margin
  of safety well above the 30% threshold. This is the intended regression behavior.

---

## 1. Why this is a regression theme

Community/regional banks are SIC 60xx (6020/6021/6022 commercial banks, 6035/6036 savings
institutions). The valuation layer's `_FINANCIAL_SIC_PREFIXES = ("60","61","63","64","67")`
guard is designed to make **FCF-capitalization structurally invalid** for these names (a bank's
"FCF" is not a meaningful intrinsic-value input — deposits are funding, not revenue, and balance
sheet leverage is the business model, not a red flag). The test asks: does the firewall hold
end-to-end, from discovery through the BUY gate, when the *entire* candidate set is banks?

Answer: yes. Every bank routed to `mos_basis="nav"` (or abstain), and every bank carried
`financial_sic_forced_unsuitable` in `buy_ineligible_reasons`, forcing `buy_eligible=False`.
Since the BUY rule requires `buy_eligible==true`, **no bank can mechanically BUY regardless of
its NAV discount.**

---

## 2. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS raw recall (UNION) | **429** | community bank 244 + regional bank 164 + deposits 219, deduped on CIK |
| SIC reverse-recall floor | n/a | regbank has **no** entry in `THEME_SIC` → no dedicated-SIC floor; FTS-only recall (P5 fallback path exercised) |
| Small-cap candidates (post mktcap + liquidity) | 48 deep + watch | <$2.0B deep band; $2–5B watch band (UCB, WSBC, CBU, DAVE, MAIN) |
| cheap_pass survivors | 47 | eliminations shown: CBU (kf1), FF (kf2), MSBI (kf2) flagged; hard-kill ≥3 sink |
| Gate 1 (SIC coarse) | 47 (keep=3, review=44) | banks are SIC 60xx = in HARD_EXCLUDE → classified **"review"** (forwarded to LLM, not dropped). Safe because every row already passed FTS keyword filter. |
| Candidate JSON written | 47 rows | 44 deep rows (41 unique tickers; LSBK duplicated ×4 across 2 CIKs + name variants), 3 watch |
| **Deep-dived (deduped deep band)** | **41** | all 41 deepdive JSONs written, **0 ERROR files**, no silent skips |
| Gate 2 (LLM theme-fit, my judgment) | 37 pure-play / 4 misrecall | misrecalls: ICCC, SMID, CVU, LGIH (see §4) |
| **Theme-fit survivors with reports** | **37** | all banks |
| finalize_run | deep=41, reports=37, gate2-misrecall=4, missing=0 | clean close |
| **Clean BUYs** | **0** | see §5 |

Funnel object: `{raw: 429, deepdived: 41, survivors: 37}`.

> Note: `RANKING.md`'s funnel header ("88 → 85 → 42 → 37") aggregates `candidates_*.json` across
> the shared reports dir; the regbank-specific numbers above are the authoritative ones.

---

## 3. mos_basis distribution (the firewall fingerprint)

| mos_basis | count | meaning |
|---|---|---|
| **nav** | 38 | 37 banks + CVU (asset-heavy aerospace). Financial-SIC → `fcf_cap_model_unsuitable=True` → routed to NAV. |
| **fcf_cap** | 3 | ICCC, LGIH, SMID — the 3 non-financial-SIC names (SIC captured as None or non-60xx) |
| abstain | 0 | — |

`buy_ineligible_reasons` frequency across the 41 valuations:

| reason | count |
|---|---|
| **financial_sic_forced_unsuitable** | **37** | (every theme-fit bank — the firewall) |
| cross_source_mismatch | 32 | SEC-XBRL vs yfinance >2.5× disagreement (data-integrity gate; common for banks where yfinance "revenue" ≠ SEC net interest income) |
| debt_truncation_suspected | 13 | C1 data guard (bank "debt" XBRL tags are noisy) |
| low_revenue_loss_ratio_extreme | 2 | FNWB, FCCO |
| fundamental_decline_flag | 2 | PLBC, + 1 |
| peak_contamination_flag | 1 | |
| insurance_concepts_present | 1 | LARK (A3 insurance-bearing holdco guard) |
| wrong_entity_suspected | 1 | LSBK |
| extreme_mos_review_required | 1 | SMID |

---

## 4. Gate-2 theme-fit (my judgment from 10-K blurbs)

**Misrecalls (off-theme; correctly resolved, not deep-dive failures):**

| Ticker | SIC | What it actually is | Why FTS hit it |
|---|---|---|---|
| ICCC | 2835 | ImmuCell — animal-health biologics | "deposits" / generic financial language in 10-K |
| SMID | 3272 | Smith-Midland — precast concrete | "regional" / generic |
| CVU | 3728 | CPI Aerostructures — aerospace structures | generic |
| LGIH | 1531 | LGI Homes — homebuilder | "regional"/"community" market language |

The remaining 37 are unambiguous community/regional bank holding companies (pure-play). DAVE
(SIC 6199, $4.0B fintech cash-advance app) landed in the **watch band** (>$2B), so it was never
deep-dived; it is also not a chartered deposit-taking community bank — correctly out of scope.

---

## 5. BUY-rule application — honest 0-BUY

BUY rule: `mos_basis ∈ {fcf_cap, nav}` AND numeric MoS ≥ 30 AND `buy_eligible==true` AND zero
kill-flags. Walking every path to a BUY:

1. **All 37 theme-fit banks:** `mos_basis=nav`, `buy_eligible=False`
   (`financial_sic_forced_unsuitable`). Fails the `buy_eligible` clause. **Not BUY.**
   - The strongest temptations the firewall correctly defused:
     - **FNWB**: NAV MoS **+40.2%** (>30) — blocked by financial_sic_forced_unsuitable (+
       low_revenue_loss_ratio_extreme, debt_truncation, cross_source_mismatch).
     - **OPHC**: NAV MoS **+41.4%** (>30) — blocked by financial_sic + cross_source_mismatch.
     - **BCBP** (+25.9%), **STLE** (+22.3%) — below 30 *and* blocked anyway.
   - These are the load-bearing regression assertions: a bank trading at a 40% discount to
     tangible book is exactly the kind of NAV name a naive screen would surface as a BUY. The
     firewall stops it because capitalizing a bank's balance sheet as if it were an industrial's
     NAV is not a valid intrinsic-value claim for this model.
2. **buy_eligible=True names (2): ICCC, LGIH** — both `fcf_cap` basis but **MoS = None**
   (intrinsic_band null). Both have **negative normalized FCF** (ICCC −$2.5M; LGIH −$138.8M,
   homebuilders burn cash into inventory), so no reverse-DCF intrinsic value could be computed →
   MoS can't be ≥30. Fails the MoS clause. Also off-theme. **Not BUY.**
3. **SMID** (`fcf_cap`, MoS −113%, extreme_mos_review_required) — **Not BUY.**
4. **CVU** (`nav`, MoS −69%, cross_source_mismatch) — **Not BUY.**

**Clean BUYs: 0. n_buy_clean: 0.** No adversarial verification of a BUY was required (there are
no mechanical BUYs to challenge).

### Adversarial note on the 0-BUY itself
Is "0 BUY" a data artifact (e.g. the pipeline crashed and produced no BUYs trivially)? No:
- 41/41 deepdives succeeded, 0 ERROR files, 41/41 valuations exit 0, 37/37 reports, finalize
  missing=0. The pipeline ran to completion with full data.
- The 0-BUY is produced by a *specific, named, expected* guard firing on every name
  (`financial_sic_forced_unsuitable` ×37), not by missing data. NAV MoS was successfully computed
  for the banks (e.g. FNWB +40.2%), so the abstention is a deliberate veto, not a
  can't-compute fallback. This is the firewall working, not failing.

---

## 6. Code-paths exercised (regression coverage)

- **financial-SIC exclusion (`valuation.py` C2):** `_FINANCIAL_SIC_PREFIXES` matched 60xx for all
  37 banks → `_financial_sic_forced_unsuitable=True` → `fcf_cap_model_unsuitable=True` →
  `mos_basis` routed to nav/abstain → `financial_sic_forced_unsuitable` appended to
  `buy_ineligible_reasons` → `buy_eligible=False`. End-to-end firewall confirmed.
- **Gate 1 tri-state "review" path (`filter_by_sic.py`):** banks in HARD_EXCLUDE → `sic_classify`
  returned "review" (not "drop"), forwarded to Gate 2. The caller-contract safety (FTS pre-filter
  already applied) held — no over-recall hole.
- **P5 / no-floor FTS-only recall:** regbank is absent from `THEME_SIC`, so `sic_reverse_recall`
  was a no-op and discovery fell back to pure FTS (429 raw). This exercises the "theme with no
  dedicated SIC" branch.
- **A3 insurance-concepts guard:** fired on LARK (insurance-bearing holdco) — distinct reason
  string from financial_sic, as designed.
- **P7 cross-source sanity (`deepdive_data.py` + `valuation.py`):** fired on 32 names — banks'
  yfinance "revenue" routinely disagrees >2.5× with SEC net-interest-income, correctly gating.
- **C1 debt-truncation guard:** fired on 13 names.
- **A4 low_revenue_loss_ratio_extreme:** fired on 2 (FNWB, FCCO).
- **V-shape vetoes:** fundamental_decline (×2), peak_contamination (×1).
- **Gate-2 misrecall resolution in finalize_run:** `candidates_gate2_survivors.json` +
  `gate2_results.json` resolved the 4 off-theme names so finalize reported missing=0 without
  `--allow-missing`.
- **Signals side-channel:** emitted automatically (diagnostic-only); confirmed it did **not**
  touch buy_eligible for any name.

---

## 7. recall@gold

**n/a.** regbank has no gold list (`THEME_GOLD` covers only deathcare, water-utilities,
railcar-leasing, regional-gaming). `track_forward.py --recall-gold --theme regbank` returned
`"no gold list for theme 'regbank' → not measurable"` — the correct no-op. Recall here is bounded
below only by the FTS 429-name recall; with no dedicated SIC floor, there is no measured floor for
this theme.

---

## 8. Data-quality issues observed

- **LSBK duplicated ×4** in the candidate set across 2 CIKs (1341318, 2059653) and two name
  spellings ("LAKE SHORE BANCORP, INC." vs "Lake Shore Bancorp, Inc. /MD/"). Deduped to 1 ticker
  for deep-dive. The /MD/ entity is a mid-tier holdco reorg of the same bank — a known
  second-step-conversion duplication pattern, not a data error per se, but the candidate writer
  should dedup on ticker.
- **SIC=None in valuation for ICCC / LGIH / SMID:** the deepdive→valuation handoff did not always
  carry SIC, so the financial-SIC guard depends on SIC being captured. For these 3 it didn't
  matter (none are banks; negative FCF / extreme-MoS killed them anyway), but a non-bank financial
  with a missing SIC could in principle slip the financial-SIC guard — worth a hardening note. The
  guard appends `sic_unavailable_cannot_confirm_nonfinancial` to dq in that case.
- **cross_source_mismatch on 32/41 names** is expected noise for banks (yfinance revenue model ≠
  SEC NII) rather than a real corruption signal — but because it correctly co-fires with
  financial_sic on every bank, it does not change any verdict. For a pure financial theme this gate
  is largely redundant with the financial-SIC gate.
- **Revenue shows $0M for most banks** in RANKING (XBRL "Revenues" concept absent — banks report
  net interest income, not a Revenues tag). Cosmetic; does not affect the firewall.

---

## 9. Market-intel / T2 analyst context

TrendsMCP was rate-exhausted at run time (daily + monthly quota spent), and market-intel was not
invoked. T2 enrichment is firewalled from buy_eligible and was not needed to reach the verdict.
For context only (analyst domain knowledge, **not** a buy input): small US community/regional
banks in 2025–26 have traded at depressed price-to-tangible-book on CRE-exposure and
deposit-cost concerns, which is precisely why several names here screen at large NAV discounts
(FNWB/OPHC > +40%). That is exactly the value-trap surface the financial-SIC firewall exists to
keep out of the mechanical BUY set — a deep discount to book is not, by itself, a valid intrinsic
margin of safety for a leveraged deposit-taking institution.

---

## 10. Skeptical-PM usable verdict

**Usable: YES — as a passed regression, not as an idea source.**

A skeptical PM gets the right answer for the right reason: the scanner refuses to emit a single
BUY across 37 community/regional banks, and the refusal is traceable to one named guard firing on
every name, *including* banks that look cheap on NAV. The pipeline ran fully (0 errors, 0 missing,
0 silent skips), the 0-BUY is a deliberate veto rather than a data failure, and the misrecalls
were correctly identified and resolved. There is no actionable shortlist here — by design, this
theme is outside the tool's competence (it does not value banks), and the tool says so cleanly.
The one hardening item a PM should flag back to engineering: ensure SIC always propagates into
valuation so the financial-SIC guard never relies on a possibly-missing field.

**Bottom line:** financial-SIC firewall PASS, P5 no-floor recall PASS, 0 clean BUYs (correct),
recall@gold n/a.
