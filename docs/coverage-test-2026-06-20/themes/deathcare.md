# Coverage Test - Theme: deathcare (REGRESSION)

- Run: `2026-06-21_cov-deathcare` | skill commit f12fef5 (dirty) | keywords: funeral, cremation, cemetery
- Code-path focus: recall@gold baseline (expected 100%)
- Result headline: **0 clean BUYs.** 2 true deathcare members (CSV, SNFCA) both correctly WATCH. recall@gold = 33.3% on the candidates file BUT the raw FTS recall floor is 5/6 - the gap is post-recall band/burn/liquidity filtering plus one genuine delisting, not an FTS recall failure.

## Funnel

| Stage | Count |
|---|---|
| Raw universe (FTS + SIC floor, deduped) | 141 |
| Small-cap candidates (deep+watch+unknown bands) | 61 |
| cheap_pass survivors | 48 |
| SIC-gate candidates JSON | 48 (deep=33, watch=15) |
| Gate-2 theme-fit survivors (deep-band) | 2 (CSV pure_play, SNFCA partial) |
| Deep-dived (every deep-band survivor) | 2 |
| Mechanical BUYs | 0 |
| Clean BUYs (post-adversarial) | 0 |

Gate-2 dropped 31 of 33 deep-band names as misrecalls: banks (PEBK, UBCP, FMAO, SRCE, LOB, AGBK, BBAR, TBBK), biotech/pharma (BNR, PRCT, KMTS, ARDX, CHRS), airlines (RJET, AZUL), restaurants (BJRI), REIT (LAND), chemicals (RYAM, OLN), media/adtech (MNTN, NMAX, WLY), insurers (CIA, LIFE), staffing (AMN), mining (NEWP), and assorted micro-cap foreign filers (ZGM, EPSM, LFS, SAGT, LSAK, HAIN, PAX, ISSC). All incidental "funeral"/"cemetery" keyword hits (risk-factor / death-benefit / boilerplate context), confirmed by SIC + 10-K blurb.

## Ranked shortlist

| Rank | Ticker | Name | Rating | mos_basis | MoS | buy_eligible | kill-flags |
|---|---|---|---|---|---|---|---|
| 1 | CSV | Carriage Services | WATCH | nav | -100.0% (artifact) | False | 0 |
| 2 | SNFCA | Security National Financial | WATCH | nav | +35.1% (artifact) | False | 1 (material_weakness) |

## BUYs

**None.** Both true members are mechanically blocked by `buy_eligible == False`. This is the correct "nothing found" answer for the live small-cap deathcare universe.

### CSV - why NOT a BUY (buy_eligible reasoning)
- mos_basis = nav; FCF model flagged unsuitable by the C1 data-quality guard.
- Ineligible reasons: `debt_truncation_suspected`, `cross_source_mismatch`.
- Debt-truncation: SEC total_debt = $6.2M vs implied debt (liab - equity) = $814.4M (ratio 0.01) - XBRL debt tag truncated/mis-scoped.
- Cross-source mismatch: SEC $6.2M vs yfinance $546.0M = 87.9x disagreement (>2.5x) - blocks BUY by design.
- MoS(NAV) = -100% is a pure artifact of the corrupted tangible-equity computation, not economics.
- **Adversarial verdict (data artifact):** The negative MoS is a balance-sheet data artifact. Reconstructing with the yfinance debt (~$546M) gives EV ~$1.15B and EV/EBITDA ~9.4x - not obviously cheap. Rejection is NOT suppressing a real opportunity; the C1 guard correctly abstains on corrupted input. A human should re-pull CSV debt from the 10-K MD&A before any judgment.

### SNFCA - why NOT a BUY (despite MoS >= 30)
- mos_basis = nav; MoS(NAV) = +35.1% (clears the 30 threshold) - yet still ineligible.
- Ineligible reasons: `financial_sic_forced_unsuitable` (SIC 6199), `insurance_concepts_present`, `low_revenue_loss_ratio_extreme`, `cross_source_mismatch`. Plus a `material_weakness` kill-flag (killflag_count=1).
- low_revenue_loss_ratio_extreme: latest NI = $32,152M vs revenue $344.6M (|NI|/rev = 93.3x) - confirmed XBRL unit mis-tag; flagged EXTREME (>20x).
- cross_source_mismatch: SEC debt $280.3M vs yfinance $108.9M (2.6x).
- **Adversarial verdict (artifact + class exclusion):** The +35.1% NAV MoS is an artifact of applying industrial NAV logic to an insurance balance sheet (book equity embeds reserves/float the tool does not risk-adjust; goodwill/intangibles unavailable so it uses a book-equity proxy). Combined with the NI mis-tag, the material weakness, and the debt mismatch, the apparent margin of safety is not investable. Correctly excluded - this is exactly the financial/insurance carve-out working as designed.

## Code-paths exercised (the point of the regression)

- discover.py: FTS recall (funeral/cremation/cemetery) UNION SIC-reverse-recall floor (SIC 7200).
- Market-cap fallback chain + band tagging (deep / watch / unknown / large). SCI tagged `large` ($10B); HI tagged `unknown` (no price).
- cheap_pass.py burn guard: `reject_burn=True` fired on MATW (runway 0.5, OCF -$67M).
- Illiquidity guard: HI dropped (flag_illiquid=True - yfinance returned no price/volume).
- filter_by_sic.py tri-state (`keep`/`review`): SNFCA SIC 6199 -> review -> LLM gate (kept); financial SICs flowed through to LLM.
- valuation.py guards FIRED: `debt_truncation_suspected` (CSV), `cross_source_mismatch` (both), `financial_sic_forced_unsuitable` + `insurance_concepts_present` + `low_revenue_loss_ratio_extreme` (SNFCA), C1 data-quality FCF block, NAV fallback path.
- deepdive_data.py XBRL implausibility guard: caught SNFCA NI mis-tag, noted OCF unaffected.
- finalize_run.py: completeness assert with gate2_results.json resolving 31 misrecalls (missing=0); verdict emission; RANKING rebuild.
- track_forward.py: recall@gold + verdict recording (Brier capture vs IWM).
- signals.py: firewalled diagnostic (library-only in this path; never touched buy_eligible). Confirmed no BUY influence.

## recall@gold (REGRESSION baseline - KEY FINDING)

Gold cohort (6): SCI, CSV, MATW, HI, STON, SNFCA.

**Tool-reported recall@gold = 33.3% (2/6)** - recalled_final = {CSV, SNFCA}; the tool buckets the other four as `fts_missed`.

**This is a measurement artifact of `--recall-gold` reading the post-filter candidates JSON, not the raw recall set.** The expected-100% baseline does NOT hold at the candidate stage, but the true loss-stage breakdown (reconstructed from the universe CSV) is:

| Gold | In raw FTS universe? | True loss stage |
|---|---|---|
| CSV | yes | recalled_final OK |
| SNFCA | yes | recalled_final OK |
| SCI | yes (SIC 7200, $10.0B) | dropped_mktcap (large-cap, by design - out of small-cap scope) |
| MATW | yes (SIC 3360, $822M) | cheap_pass burn-reject (runway 0.5) - defensible mechanical kill |
| HI | yes (SIC 3990, "cemetery") | illiquidity guard (yfinance price-fetch miss; also questionable membership post-Batesville) |
| STON | NO | genuinely fts_missed (StoneMor delisted ~2022; no recent filings in the live universe) |

**Raw FTS recall floor = 5/6 (83%); only STON is a true miss, and STON is no longer a live filer.** So FTS recall is healthy; the 33.3% figure conflates recall with downstream band/burn/liquidity filtering.

Recommended fix for the regression harness: `--recall-gold` should compute against the universe CSV (pre-band-filter recall set) so dropped_mktcap / cheap_pass / illiquid loss-stages are attributed correctly instead of collapsing into fts_missed. As written, the metric understates recall and mislabels its loss stages.

## Data-quality issues

1. CSV debt XBRL truncation: SEC total_debt $6.2M vs implied $814M vs yfinance $546M (87.9x cross-source). Blocks valuation; needs manual 10-K pull.
2. SNFCA net-income XBRL unit mis-tag: $32,152M vs $344.6M revenue (93x). Caught by guards; OCF used instead.
3. SNFCA debt cross-source 2.6x (SEC $280.3M vs yf $108.9M) + debt_stale (>18mo).
4. HI (Hillenbrand): yfinance returned no price/volume for a ~$2B NYSE name -> mis-classified illiquid/unknown and dropped at universe stage. Ticker-resolution / price-fetch fragility.
5. ZGM killflag scan failed ("Company not found: 'ZGM'") - non-fatal, name excluded downstream.
6. recall@gold metric reads the wrong (post-filter) file - see above; counts as a harness data-quality issue.

## Market-intel / T2 context

TrendsMCP quota exhausted (5/5 daily, 100/100 monthly) - no live search/trend pull available this run; recorded as a limitation. market-intel catalog has no deathcare-specific source file. General industry context (tier T2, never drives buy_eligible): US deathcare is a slow-growth, demographically-supported, consolidation-driven industry; the cremation-rate secular shift (now >60% of US dispositions) compresses per-call revenue and is the structural headwind every operator faces. CSV is the only listed small-cap pure-play funeral/cemetery operator; SCI is the large-cap leader (out of scope by size). This context is descriptive only and did not affect any mechanical gate.

## Skeptical-PM usable verdict

**Usable.** The pipeline ran end-to-end with zero crashes/ERROR files, correctly enumerated the deathcare universe, isolated the only two true small-cap members, and refused to issue a BUY on either - once for corrupted balance-sheet data (CSV) and once for the insurance-class exclusion plus a confirmed unit mis-tag (SNFCA). That is the landmine-scanner working: "nothing clean here" is the correct answer. The one substantive caveat for a PM is the recall@gold harness: the headline 33.3% is misleading - actual FTS recall is 5/6, with the misses explained by size/burn/liquidity/delisting, not by a discovery gap. Fix the metric input file before trusting it as a regression gate.
