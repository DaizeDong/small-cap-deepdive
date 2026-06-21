# Iteration-1 Test — RECALL before/after (P5 mktcap fix)

**Run:** `2026-06-20_iter1-old-recall-p5` (skill commit `e0f0039`, clean tree)
**Stage tested:** `discover.py` + `cheap_pass.py` recall path only (no theme-fit gate, no rank — this is a recall test).
**Outputs:** `reports/smallcap/2026-06-20_iter1-old-recall-p5/`
**Date:** 2026-06-20

## Bottom line

The P5 fix **recovers the universe**. Both themes that under v0.2.0 returned ~0 viable
candidates (regbank 100% silent-drop, shipping 97%) now produce hundreds of resolved-mktcap
candidates:

| Theme | Raw FTS (dedup) | v0.2.0 candidates (before) | P5 candidates (after) | deep-band candidates |
|---|---|---|---|---|
| **regbank2** (`community bank,regional bank,deposits`) | **429** | **~0** (429/429 yfinance 429 → all dropped) | **271** | 231 |
| **shipping2** (`drybulk,tanker,shipping`) | **410** | **~12** (398/410 dropped) | **219** | 172 |

**Is the 100% / 97% silent-drop fixed? YES at the universe/band level** — null-mktcap rows are
no longer deleted from the frame; they survive as `band="unknown"` and the SEC
`shares x price` fallback now reconstructs a real mktcap for rows where yfinance gave only a
null marketCap but a live price. **Candidates went from ~0 → 271 (regbank) and ~12 → 219
(shipping).** The recall recovery is real and large.

**One important nuance (not a regression, but a residual gap):** `band="unknown"` rows where
yfinance returned **nothing at all** (no marketCap AND no price AND no volume — the pure
rate-limit / quote-404 case) flow through as `band="unknown"` (good — they are visible, not
silently dropped), but they get `smallcap_candidate=False` because the **illiquidity gate** (`avg_dollar_vol.fillna(0) < min_dollar_vol`) fires on their null volume. So the *band-drop* is
fixed; a *liquidity-gate drop* now stands in front of the no-price subset. See "Where the
remaining unknowns go" below.

---

## 1. regbank2 — `community bank,regional bank,deposits`

Raw FTS hits (dedup by CIK): **429**

Band / mktcap-source breakdown after `discover.py`:

| band | count | meaning |
|---|---|---|
| deep | 290 | mktcap < $2B → full deep-dive scope |
| watch | 43 | $2B–$5B → surfaced, no deep-dive |
| large | 50 | > $5B → out of scope (flagged, NOT dropped) |
| unknown | 46 | mktcap unresolved → flows through as band, NOT dropped |

| mktcap_source | count |
|---|---|
| yfinance | 375 |
| sec_shares_x_price (P5 fallback fired) | 8 |
| unresolved | 46 |

- `smallcap_candidate == True`: **271** (deep + watch + the resolvable subset, not SPAC, not illiquid)
- deep-band candidates: **231**
- The **8 `sec_shares_x_price`** rows are direct P5 recoveries: yfinance returned null marketCap
  but a price existed, so SEC companyfacts shares-outstanding × price reconstructed the cap and
  the row banded normally (e.g. preferreds/funds banded deep/watch and became candidates).

**Before (v0.2.0):** the changelog/task baseline records regbank as 429/429 yfinance-429
→ zero candidates: every row had null mktcap, `apply_filters` set `flag_no_mktcap` and the
`mktcap <= max_mcap` ceiling silently dropped all of them before any gate. **After (P5): 271
candidates.** Silent-drop fixed.

## 2. shipping2 — `drybulk,tanker,shipping`

Raw FTS hits (dedup by CIK): **410**

| band | count |
|---|---|
| deep | 241 |
| watch | 48 |
| large | 83 |
| unknown | 38 |

| mktcap_source | count |
|---|---|
| yfinance | 366 |
| sec_shares_x_price (P5 fallback fired) | 6 |
| unresolved | 38 |

- `smallcap_candidate == True`: **219**
- deep-band candidates: **172**
- 6 P5 fallback recoveries (e.g. **BDRY** $106M, **BNO** $691M, **GLOP-PA** $1.20B → all
  `smallcap_candidate=True`; SEAL-PA / TRTN-PA reconstructed into `watch`).

**Before (v0.2.0):** 398/410 dropped → ~12 candidates. **After (P5): 219 candidates.**

---

## 3. Where the remaining "unknown" rows go (the confirmation the task asks for)

**Confirmed: band="unknown" names DO flow into the frame instead of being silently dropped.**
Every one of the 46 (regbank) / 38 (shipping) unresolved rows is present in the output CSV with
`band="unknown"` — none vanished. This is the core P5 behavior, and it holds.

**Why those specific unknowns are still NOT in the candidate set:** in this run, yfinance was
hard-down for them — they returned `marketCap=None`, `price=None`, AND `avg_dollar_vol=None`
(spot-checked VBTX/BRKL/HONE directly: yfinance returns null marketCap and null price, BRKL even
404s). Because price is null, the SEC `shares x price` fallback cannot fire (it needs a price), so
mktcap stays unresolved → `band="unknown"`. Then the illiquidity gate
(`avg_dollar_vol.fillna(0) < min_dollar_vol`) sees null volume → `flag_illiquid=True` →
`smallcap_candidate=False`.

So for the no-data subset the disposition changed from **"deleted from the frame"** (v0.2.0
silent mktcap drop) to **"present, banded unknown, excluded by the liquidity gate"** (P5). That
is strictly better — the names are now visible/auditable and would re-enter the candidate set on a
re-run once yfinance serves a price (the SEC fallback would then reconstruct the cap). But it
means the *full* recovery of the no-price subset depends on yfinance returning at least a price.

**Honest characterization of the fix:**
- Silent **band-level** drop of null-mktcap rows: **FIXED** (rows flow through as `unknown`).
- SEC `shares x price` mktcap reconstruction when yfinance gives a price: **WORKING** (8 + 6 rows recovered).
- No-price / no-volume rows (pure yfinance outage): still excluded, but now by the **liquidity
  gate**, not by a blanket mktcap drop — visible in the CSV with `band="unknown"`, not deleted.
  Residual hardening idea (not in scope here): give `resolve_mktcap` a price fallback (e.g. SEC
  last close or a second quote source) so the no-price subset can also reconstruct a cap and clear
  the liquidity gate.

The dramatic numbers in the task framing (429/429, 398/410) were *total-universe* drops; under P5
those become **271 / 219 candidates**, so the headline regression is resolved.

---

## 4. Spot-check — full deepdive + valuation on 3 recovered names

Names chosen as genuine theme-member small-cap operators that the P5 path now surfaces and can
process end-to-end (under v0.2.0's regbank silent-drop, BAFN/MBBC would never have reached the
deepdive stage at all). Each ran `deepdive_data.py --ticker` then `valuation.py --json --ticker`.

| Ticker | Theme | mktcap (P5) | mos_basis | NAV MoS | buy_eligible | buy_ineligible_reasons / kill | Verdict |
|---|---|---|---|---|---|---|---|
| **BAFN** (BayFirst Financial) | regbank | ~$20M (yfinance) | nav | +221.5% | **False** | `extreme_mos_review_required`, `financial_sic_forced_unsuitable` (SIC 6022) | NOT BUY |
| **MBBC** (Marathon Bancorp) | regbank | ~$45M (yfinance) | nav | −15.8% | **False** | `financial_sic_forced_unsuitable` (SIC 6036) | NOT BUY |
| **ICON** (Icon Energy Corp) | shipping | ~$3M (yfinance) | nav | +414.5% | **False** | `extreme_mos_review_required`, `wrong_entity_suspected`; **10-K going_concern=True** | NOT BUY (kill-flag) |

Observations:
- **All three correctly fail the new BUY rule.** A BUY needs `mos_basis ∈ {fcf_cap,nav}` AND
  MoS≥30 AND `buy_eligible==true` AND zero kill-flags. None clear `buy_eligible`, so none can be
  a BUY — exactly as designed.
- **BAFN/MBBC**: the financial-SIC guard (`financial_sic_forced_unsuitable`, banks SIC 6022/6036)
  forces FCF-model-unsuitable → NAV basis; BAFN's +221% NAV MoS trips `extreme_mos_review_required`
  (book-equity proxy used for tangible equity — exactly why the extreme-MoS guard exists for banks).
  Both `buy_eligible=False`. Concentration/decline flags clean.
- **ICON**: shipping microcap with a real **going-concern** flag in its latest filing plus
  `wrong_entity_suspected` (NI/revenue ratio absurd 2.5) and −68% share dilution → the kill path
  fires. Demonstrates the mechanical de-risk still bites on a recovered name.
- The point for *this* test is recall, not the verdicts: these are names the P5 universe now
  carries through discover → cheap_pass → deepdive → valuation. The recall fix is what made the
  spot-check possible.

Spot-check artifacts:
- `reports/smallcap/2026-06-20_iter1-old-recall-p5/deepdive_BAFN_2026-06-20.json` + `valuation_BAFN_2026-06-20.json`
- `reports/smallcap/2026-06-20_iter1-old-recall-p5/deepdive_MBBC_2026-06-20.json` + `valuation_MBBC_2026-06-20.json`
- `reports/smallcap/2026-06-20_iter1-old-recall-p5/deepdive_ICON_2026-06-20.json` + `valuation_ICON_2026-06-20.json`

---

## 5. Supplementary T2 market-intel context (analyst color only — NOT decisional)

> Labeled supplementary per the market-intel enrichment allowance. This did NOT and must NOT
> drive any `buy_eligible`/BUY decision (those stay anchored to T1 filings above).

- **Dry-bulk shipping** (TrendsMCP, Google search interest): 12M growth **+62.5%** (16 → 26,
  volume 140 → 227) — demand interest up year-over-year; but 3M **−72.6%** (off a March spring
  spike of 95). Read: cyclical theme, recently cooled from a peak — consistent with the "hot
  theme = casino" world-view (the spring spike is the crowd; the names worth attention are the
  real operators, separable only by the T1 gate above).
- **Community bank**: TrendsMCP returned `data_unavailable` for the keyword at run time; no T2
  color recorded. (No decision impact — regbank verdicts are T1-anchored.)

---

## 6. Data-completeness / errors log (per FULL-data rule)

- No themes sampled; both full FTS universes enumerated (429 and 410 dedup hits) and every row
  market-cap-resolved via the P5 fallback chain.
- yfinance was rate-limited/outage for a subset this run (the 46 / 38 unresolved no-price rows).
  Per the standing directive these were **not silently skipped**: they are recorded in the output
  CSVs with `mktcap_source="unresolved"`, `band="unknown"`, and the reason they sit out of the
  candidate set (`flag_illiquid=True` from null volume). A re-run when yfinance serves prices
  would reconstruct their caps via the SEC fallback.
- `discover.py --selftest` and `_common.py --selftest` both PASS (P5 null→unknown flow-through +
  resolve_mktcap fallback chain assertions).
