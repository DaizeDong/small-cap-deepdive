# Coverage Test — Theme: niche-reits (Real Estate / specialty REITs)

- **Slug:** `niche-reits`
- **Sector:** RealEstate
- **Keywords (as specified):** `data center REIT, cell tower REIT, specialty REIT`
- **Skill version:** v0.3.0 (commit f12fef5, run manifest `skill_dirty: true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-niche-reits/`
- **Code-path focus:** REIT routing / FFO-not-FCF
- **Headline:** **0 mechanical BUYs.** Every REIT routed to `mos_basis=nav` and was set `buy_eligible=false` by the financial-SIC exclusion (SIC 6798 → prefix 67). This is the intended, correct behavior for the REIT routing / FFO-not-FCF code path. A pure REIT can never produce a mechanical BUY under v0.3.0.

---

## 1. Funnel

The literal keyword set collapsed discovery to ~1 name, so an effective-keyword re-run was used to
actually exercise the REIT routing code path (both runs documented below; same run batch dir).

| Stage | Count | Note |
|---|---|---|
| Raw FTS recall (effective keywords) | 399 | `data center, cell tower, real estate investment trust` |
| Small-cap candidates (<$2.0B) | 176 | deep 171 + watch 51 pre-SIC; 176 flagged smallcap_candidate |
| cheap_pass scanned | 176 | mechanical kill-flag health check |
| cheap_pass survivors + SIC gate | 116 | 25 SIC-keep + 91 SIC-review → LLM Gate 2 |
| ...of which **deep band** (<$2.0B) | **74** | the names that earn a full deep-dive |
| ...watch band ($2.0–5.0B) | 42 | theme-fit only, no deep-dive |
| **Gate 2 theme-fit KEEP (specialty REITs)** | **9** | 65 deep-band names dropped as misrecalls |
| Deep-dived + valued | 9 | SILA UHT LTC ILPT UMH SVC PINE GNL OLP |
| **Mechanical BUYs** | **0** | all `buy_eligible=false`, all NAV MoS negative |

`recall@gold`: **n/a** — niche-reits is not in `THEME_GOLD` (only deathcare / water-utilities /
railcar-leasing / regional-gaming have gold lists). `track_forward.py --recall-gold` is a no-op here.

### 1a. Two discovery findings (data-quality)

**Finding A — literal keywords recall almost nothing (FTS exact-phrase brittleness).**
The specified phrases are matched by EDGAR FTS as *exact bigrams*. Direct test:
`"data center REIT"`→1, `"cell tower REIT"`→1, `"specialty REIT"`→0. The full pipeline on the
literal keywords yielded a 1-company universe (BRST, a $0.2M micro-cap shell on PNK). niche-reits
has **no SIC recall floor wired in** (`THEME_SIC` has no `6798` entry for this slug), so there is
no reverse-recall channel to backstop the FTS collapse. The effective re-run used broader unigrams
plus the literal `real estate investment trust` term to recover a realistic universe. This is a
genuine recall gap for the as-specified keyword set.

**Finding B — `cheap_pass.py` crashes on an empty universe.**
With the 1-company universe, all rows were filtered out before scoring and `cheap_pass.score()`
raised `AttributeError: 'int' object has no attribute 'fillna'` at line 290
(`df.get("kf_going_concern", 0).fillna(...)` returns a scalar `0` when the column is absent on an
empty frame). The literal-keyword run therefore aborted with EXIT=1 before producing candidates.
Edge-case robustness bug; only fires on an empty/degenerate small-cap set.

---

## 2. Code-paths exercised (the point of this test)

**REIT routing / FFO-not-FCF — fired exactly as designed on all 9 names.**

| Ticker | Property type | mos_basis | NAV MoS | buy_eligible | buy_ineligible_reasons |
|---|---|---|---|---|---|
| SILA | data center + healthcare net-lease | nav | -37.5% | false | financial_sic_forced_unsuitable |
| UHT | healthcare facilities | nav | -78.3% | false | financial_sic_forced_unsuitable |
| LTC | senior housing / SNF | nav | -52.6% | false | financial_sic_forced_unsuitable |
| ILPT | industrial / logistics | nav | -28.9% | false | financial_sic_forced_unsuitable, cross_source_mismatch |
| UMH | manufactured-housing communities | nav | -44.2% | false | financial_sic_forced_unsuitable, cross_source_mismatch |
| SVC | service-retail net lease + hotels | nav | -71.2% | false | financial_sic_forced_unsuitable, peak_contamination_flag |
| PINE | commercial net lease | nav | -26.4% | false | financial_sic_forced_unsuitable, cross_source_mismatch |
| GNL | global net lease | nav | -57.5% | false | financial_sic_forced_unsuitable, debt_truncation_suspected |
| OLP | net lease (diversified) | nav | -54.6% | false | financial_sic_forced_unsuitable, cross_source_mismatch |

Code paths that fired:
- **`_FINANCIAL_SIC_PREFIXES` C2 exclusion** (`valuation.py:252`, prefixes `60/61/63/64/67`):
  SIC 6798 starts with `67` → `_financial_sic_forced_unsuitable=True` →
  (a) `fcf_cap_model_unsuitable=True` forcing the **NAV path** instead of FCF-capitalization
  ("FCF capitalization is structurally invalid for these business models" — this is the
  FFO-not-FCF guard: the tool refuses to capitalize REIT FCF because GAAP OCF/CapEx is not the
  right cash metric for a REIT; it falls back to asset NAV), and
  (b) `financial_sic_forced_unsuitable` added to `_buy_ineligible_reasons` → `buy_eligible=False`.
- **NAV path** (`valuation.py:498-522`): `nav_tangible_equity` and `nav_margin_of_safety_pct`
  computed for all 9; every one is **negative** (names trade above tangible NAV).
- **Three-way `mos_basis` routing** (`valuation.py:524-545`): all routed to `nav` (asset-heavy +
  equity available), none to `fcf_cap` or `abstain`.
- **Defense-in-depth guards co-fired** as second blockers: `cross_source_mismatch` (P7),
  `peak_contamination_flag` (P-A V-shape veto on SVC), `debt_truncation_suspected` (C1 on GNL).
- **Firewall:** signals side-channel did not auto-emit a file in this flow and is irrelevant —
  `buy_eligible` is composed solely from the guard list with zero signal references.

**Net:** the BUY rule (`mos_basis∈{fcf_cap,nav}` AND MoS≥30 AND `buy_eligible` AND 0 kill-flags)
is unsatisfiable for a pure REIT on two independent grounds: `buy_eligible=false` (financial-SIC)
AND NAV MoS negative (overvalued vs NAV). Correct double-lock.

---

## 3. Gate 2 theme-fit (LLM membership judgment from blurbs)

The effective keywords (`real estate investment trust` + `data center`) over-recalled the entire
small/mid REIT complex plus tech/finance keyword bystanders. THEME = niche/specialty REITs
(data-center, cell-tower, and non-traditional property types). Classification of the 74 deep-band
names:

- **KEEP — specialty/niche REIT property types (9):** SILA (data center + healthcare — the single
  closest data-center match), UHT + LTC (healthcare specialty), ILPT (industrial/logistics niche),
  UMH (manufactured housing niche), SVC + PINE + GNL + OLP (net-lease, a recognized specialty REIT
  sub-type).
- **DROP — traditional equity REITs (not specialty):** office (FSP, NLOP, BDN, AAT, ALX), apartment
  (CLPR, ELME, AIV, CSR, VRE), retail/shopping-center (FREVS, BRT, WSR, BFS, SITC, FVR, WHLR),
  hotel/lodging (IHT, BHR, CLDT, RLJ), diversified/non-traded (CFTR-PA, ADAM, NXDT).
- **DROP — mortgage / specialty-finance REITs (debt, not property niche):** SUNS, SEVN, REFI,
  BRSP, NREF, ABR.
- **DROP — outright misrecalls (non-REIT keyword bystanders):** SaaS/tech (DOMO, CXDO, EGHT, OOMA,
  FIVN, BLZE, PUBM, CRTO, RXT, VYX, SIFY, ITMSF, CLVT), banks/BDCs (HWBK, AROW, LKFN, EQBK, CGBD,
  ABTS), broadband/telecom (CABO, CCOI), energy (HNRG, SLNG, TGEN, DGXX, ACFN), crypto/ETF (DTCX,
  ETHV), other (RMR asset-manager, PAYS prepaid, BBCP concrete, SUUN, LWLG, PROF medical device,
  SNDA senior-living operator).

**Honest coverage note:** the literal theme (data-center / cell-tower pure-plays) has **no clean
small-cap pure-play** — AMT, CCI, SBAC (towers) and EQIX, DLR (data centers) are all large-cap and
correctly excluded by the $2B ceiling. SILA is the only genuine data-center-adjacent specialty REIT
that clears the small-cap band; the rest are healthcare / industrial / mfd-housing / net-lease
specialty sub-types. This is the tool correctly reporting that the niche has no clean small-cap
industrial beneficiary.

---

## 4. BUYs

**None.** 0 mechanical BUYs. `n_buy_clean = 0`.

There is nothing to adversarially defend on the long side. The adversarial question is inverted:
*could any of these be a false NEGATIVE — a real opportunity the financial-SIC blanket wrongly
kills?* Verdict: **no.** Two reasons.
1. The financial-SIC NAV routing is the methodologically correct choice for REITs (FCF-cap is
   invalid; FFO/NAV is the right lens). The tool declines to issue a mechanical BUY on a REIT by
   design, leaving REIT valuation to human FFO/AFFO/NAV diligence — appropriate humility, not a bug.
2. Independently, **every** name's NAV MoS is negative (-26% to -78%), i.e. each trades at a
   premium to tangible book. Even with a hypothetical NAV-basis BUY allowed, none would clear
   MoS≥30. So the financial-SIC veto is not masking a hidden bargain here.

---

## 5. Data-quality issues

1. **FTS exact-phrase brittleness** — literal keywords recalled ~1 name; no SIC recall floor for
   `6798` on this slug to backstop it (Finding A). Recommend wiring a `niche-reits → ["6798"]`
   floor OR documenting that multi-word REIT phrases must be decomposed.
2. **`cheap_pass.py` empty-universe crash** (Finding B) — `AttributeError` on `df.get(col,0).fillna`
   when the small-cap frame is empty. Robustness bug.
3. **`cross_source_mismatch` on 4 of 9** (ILPT, UMH, PINE, OLP) — SEC-XBRL vs yfinance revenue/debt
   disagree >2.5x (e.g. ILPT revenue SEC=62.2M vs yf=453.4M, 7.3x; UMH debt SEC=145.9M vs yf=762.5M).
   The SEC side is pulling a partial/segment/quarterly concept rather than the consolidated TTM
   figure — an XBRL concept-selection weakness in `deepdive_data.py`. Correctly gated BUY, but it
   means the NAV/EV numbers for these names are not trustworthy on the SEC side.
4. **`debt_truncation_suspected` on GNL** — reported_total_debt=0.0M vs implied (liab−equity)=1029.8M;
   the total-debt XBRL concept was missed entirely. Same root cause as #3.
5. **`peak_contamination_veto` on SVC** — latest NI=-202M below the 5yr trough→peak→rollover pattern;
   correct V-shape value-trap veto.
6. **Mojibake** in `business_blurb` / report text (SEC smart-quotes decoded under the GBK console
   codepage). Cosmetic; does not affect numeric routing.
7. **65 deep-band names without reports** is expected (Gate 2 misrecall drops); `finalize_run
   --allow-missing` handled it and labeled them resolved.

---

## 6. recall@gold

**n/a** — no gold list exists for `niche-reits` (`THEME_GOLD` covers only deathcare,
water-utilities, railcar-leasing, regional-gaming). `track_forward.py --recall-gold` is a no-op.

---

## 7. Market-intel / TrendsMCP context (T2 — analyst color only, never drives buy_eligible)

TrendsMCP daily+monthly quota was exhausted at run time (5/5 daily, 100/100 monthly), so no live
trend pull. T2 narrative context from general knowledge: the data-center REIT sub-sector has been in
a multi-quarter demand upcycle driven by AI/hyperscaler capex through 2025–2026, which is precisely
why the listed pure-plays (EQIX, DLR) re-rated to large-cap and sit above this tool's $2B small-cap
ceiling. The small-cap residue (SILA et al.) trading **above** NAV is consistent with that
sentiment having already been priced in — supportive, but explicitly non-binding on the mechanical
verdict.

---

## 8. Skeptical-PM usable verdict

**Usable: yes — as a negative/landmine result, which is the tool's designed output.**

A skeptical PM gets a clean, defensible answer: *the small-cap universe contains no clean
data-center/cell-tower pure-play (they are all large-cap), and the specialty/healthcare/net-lease
REITs that do clear the band all trade above tangible NAV and are mechanically ineligible because
FCF-cap is invalid for REITs.* The REIT routing / FFO-not-FCF guard is the load-bearing behavior and
it worked: it refused to fabricate a FCF-based BUY on an asset that should be valued on FFO/NAV, and
it double-locked with negative NAV MoS. The two caveats a PM must hear: (1) the as-specified keyword
set under-recalls badly and there is no SIC floor for this slug, so the universe had to be widened
manually — discovery completeness is keyword-fragile here; (2) SEC-side XBRL numbers for ILPT/UMH/
PINE/OLP/GNL are unreliable (cross-source mismatch / debt truncation), so anyone overriding the
mechanical AVOID to do FFO diligence must re-pull financials from the filings directly. Net: trust
the 0-BUY conclusion; do not trust the per-name SEC financial line items without verification.

---

### Artifacts
- Run dir: `reports/smallcap/2026-06-21_cov-niche-reits/`
- `RANKING.md`, `deepdive_verdicts.json` (9 verdicts, all 避开/AVOID, 0 BUY)
- `deepdive_<TKR>_2026-06-21.json`, `valuation_<TKR>_2026-06-21.json`, `report_<TKR>.md` for the 9
- `universe_niche_reits_2026-06-21.csv` (399), `cheappass_niche_reits_2026-06-21.csv` (176),
  `candidates_niche_reits.json` (116)
