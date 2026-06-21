# Coverage Test - timber-forest (Materials)

- Run batch: reports/smallcap/2026-06-21_cov-timber-forest/
- Skill version: v0.3.0, commit f12fef5
- Theme keywords: timber, forest products, lumber
- Code-path focus: REIT-NAV / cyclical
- Date: 2026-06-21 (config date); session 2026-06-19
- Verdict headline: 0 mechanical BUYs (clean). Every Gate-2 theme survivor was correctly
  rejected by the v0.3.0 valuation guards. No data-artifact BUY slipped through.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discover (FTS + mktcap, no SIC floor) | 22 | timber-forest has NO dedicated-SIC recall floor in THEME_SIC -> FTS+mktcap fallback (expected) |
| Bands | 14 deep / 8 watch | deep = mktcap <= $2.0B |
| cheap_pass survivors | 22 | 0 hard kill-flags among the 22 |
| SIC gate (Gate 1) | 22 (14 keep + 8 review) | review tier -> LLM, none auto-dropped |
| LLM theme-fit (Gate 2), deep band | 4 survivors / 10 misrecall | blurb+SIC judgment |
| Deep-dived | 4 (KOP, MERC, MBC, FOR) | every deep-band Gate-2 survivor, no sampling |
| Mechanical BUY | 0 | all 4 buy_eligible=false |
| Adversarially-clean BUY | 0 | vacuous (no BUY to verify) |

Watch-band (8, not deep-dived per band rule): GRND, JOE, CNR, BCC, VAC, HHH, SKY, GEF.
BCC (Boise Cascade, EWP/plywood, $2.63B) and GEF (Greif, industrial packaging, $3.92B) are
real forest-products-adjacent names above the $2.0B deep cutoff. JOE (St. Joe, $3.79B) is a
FL land/real-estate developer (REIT-NAV-relevant, watch band, weak theme tie).

### Gate-2 theme-fit ledger (all 14 deep-band)

| Ticker | SIC | Verdict | Rationale |
|---|---|---|---|
| KOP | 2400 | pure_play | treated wood / wood preservation / railroad ties |
| MERC | 2611 | pure_play | NBSK market pulp + lumber + mass timber |
| MBC | 2511 | partial | largest NA residential wood cabinet maker (downstream) |
| FOR | 6500 | partial (weak) | residential lot developer; legacy Forestar timberland name, now D.R. Horton land bank; kept only to exercise real-estate/NAV path |
| MDV | 6798 | misrecall | industrial net-lease REIT |
| TSNDF | 100 | misrecall | cannabis cultivator |
| IDR | 1040 | misrecall | gold/REE miner |
| APEI | 8200 | misrecall | online education |
| NRP | 1221 | misrecall | coal/soda-ash royalty LP; timber <1% (incidental WV acreage) |
| NXRT | 6798 | misrecall | apartment REIT |
| AAT | 6798 | misrecall | diversified REIT |
| TILE | 2273 | misrecall | carpet tile (textile) |
| ISOU | 1090 | misrecall | uranium explorer |
| SLI | 2800 | misrecall | lithium developer |

NRP note: web-verified - NRP reports only Mineral Rights (99% coal-dominant) + Soda Ash;
timber is a non-segment incidental WV holding. Correctly dropped despite the timber FTS hit.

---

## 2. Ranked shortlist (RANKING.md)

| Rank | Ticker | Rating | Conf | mos_basis | MoS | buy_eligible | Kill-flags |
|---|---|---|---|---|---|---|---|
| 1 | KOP | 观察 | 3 | fcf_cap | -182.2% | false | extreme_mos_review_required |
| 2 | MBC | 观察 | 3 | fcf_cap | -97.2% | false | fundamental_decline |
| 3 | FOR | 观察 | 2 | fcf_cap | null | false | cross_source_mismatch |
| 4 (sunk) | MERC | 避开 | 3 | nav | -100% | false | fundamental_decline + peak_contamination |

---

## 3. BUY analysis - none. Per-name reasoning + adversarial read.

Zero mechanical BUYs, so the adversarial requirement (for ANY mechanical BUY) is vacuously
satisfied. Honest 0-BUY accounting below.

### KOP (rank 1) - rejected by extreme_mos guard. CORRECT (artifact, not bargain).
- buy_eligible=false; reasons=['extreme_mos_review_required']. Fails MoS>=30 (MoS=-182%).
- fcf_cap intrinsic equity negative: normalized FCF ($22M, capex-depressed) capitalized at
  9-12% (~$180-245M EV) cannot cover ~$875M net debt.
- Adversarial: NOT an opportunity AND NOT real distress - a model-fit artifact. KOP is
  profitable (P/E 15, +8% FCF yield, positive NI). FCF-cap is the wrong lens for a
  capex-heavy debt-financed industrial. Re-anchor on EV/EBITDA 7.1x (unremarkable for cycle)
  -> fairly valued, not a buy. Insider net_sell (0/14) corroborates no-edge. 观察.

### MERC (rank 4, sunk) - rejected by decline + peak-contamination. CORRECT.
- buy_eligible=false; reasons=['fundamental_decline_flag','peak_contamination_flag'].
- NAV path (debt/assets 0.77>0.62 -> fcf_cap unsuitable). NAV tangible equity=0, NAV MoS=-100%.
  Latest NI -$498M; normalized FCF negative; CV 1.61 (deep cyclical).
- Adversarial: NOT an opportunity. Lone contrarian positive is heavy insider net_buy (21/1,
  $6.5M) - a real T2 signal - but it cannot and does not override the mechanical vetoes. T2
  macro corroborates: fourth straight sub-$800 China NBSK year, Brazil/China oversupply
  (ResourceWise/ERA 2026). Avoid now; re-check IF the pulp cycle turns.

### MBC (rank 2) - rejected by fundamental_decline. CORRECT.
- buy_eligible=false; reasons=['fundamental_decline_flag']. Revenue FY23->FY25 $2.86B->$2.73B,
  latest below 5yr avg.
- P/E 43, reverse-DCF implied growth ~0%, fcf_cap MoS -97%.
- Adversarial: NOT an opportunity. Cabinet demand levered to weak R&R/housing (T2 +0.4% 2026
  lumber consumption). Mild insider net_buy (7/4) weak positive. 观察.

### FOR (rank 3) - rejected by cross_source_mismatch. CORRECT (data integrity).
- buy_eligible=false; reasons=['cross_source_mismatch']. SEC total_debt $793.5M vs yfinance
  $111.7M (7.1x). Normalized FCF negative -> intrinsic band & MoS null.
- Adversarial: data-artifact, not opportunity. With a 7x debt discrepancy no valuation can be
  certified; the guard correctly abstains rather than print a fake MoS. Negative normalized
  FCF is structural to a land developer (working-capital land buys), not distress, but with
  the debt mismatch there is no clean read. Weak theme tie. 观察, lowest confidence.

---

## 4. Code-paths fired (REIT-NAV / cyclical focus)

- Cyclical normalization (CV>0.25 -> trailing-5yr-avg): KOP 0.29, MERC 1.61, FOR 0.58. MBC non-cyclical (0.08).
- NAV fallback: MERC (fcf_cap unsuitable via debt/assets 0.77>0.62 -> mos_basis=nav, NAV tangible-equity, NAV MoS).
- fcf_cap intrinsic w/ net-debt subtraction -> negative equity: KOP (headline cyclical-industrial artifact).
- fundamental_decline veto: MERC, MBC.
- peak_contamination veto: MERC.
- extreme_mos_review guard (|MoS|>100%): KOP.
- cross_source_mismatch guard (>2.5x): FOR (debt 7.1x).
- reverse-DCF null on non-positive normalized FCF: MERC, FOR.
- signals firewall (P16 price_divergence + P17 ownership) emitted under signals namespace on
  all 4 deepdives; buy_eligible derived purely from T1 valuation (firewall held).
- REIT-NAV path proper (SIC 6798 REIT NAV): NOT exercised in deep band - all REIT names
  (MDV/NXRT/AAT, watch HHH) were Gate-2-dropped as off-theme before deepdive. FOR (SIC 6500
  real estate) is the closest land/real-estate NAV-adjacent name reached and it routed to
  fcf_cap (then abstained on data mismatch), not NAV. So REIT-NAV was reached only at the
  SIC/Gate level for this theme, not inside valuation.

---

## 5. Data-quality issues

1. FOR cross-source debt mismatch SEC $793.5M vs yfinance $111.7M (7.1x) - guard fired,
   blocked certification (yfinance likely capturing only current portion).
2. KOP & MERC concentration_unquantified - 10-K text flags concentration but XBRL magnitude
   null; concentration kill could not be quantitatively evaluated.
3. Partial EBITDA series: KOP 2, MERC 4, MBC 5, FOR 14 partial-entry warnings; MBC
   dep_amort_unavailable -> normalized_ebitda null (FCF used).
4. Revenue series carries duplicate/overlapping FY tags (cosmetic; did not corrupt normalization).
5. No SIC recall floor for timber-forest: a dedicated wood/pulp SIC set is NOT in THEME_SIC,
   so SIC acted as a precision filter only, not a recall floor. Expected v0.3.0 behavior for
   an un-seeded theme; BCC/GEF-class names rely on FTS recall (and landed in watch band by mktcap).

---

## 6. recall@gold

n/a - timber-forest has no gold cohort. track_forward.py --recall-gold returned
"no gold list for theme 'timber-forest' - not measurable". (Gold lists exist only for
water-utilities, railcar-leasing, regional-gaming, deathcare.)

---

## 7. Market-intel / Trends (T2 context - NEVER drives buy_eligible)

- TrendsMCP "lumber prices" growth query returned 404 (service temporarily unavailable) - no
  normalized search-trend leg this run.
- Web T2 (ResourceWise/ERA/Fastmarkets 2026): 2026 lumber prices rising on SUPPLY cuts (1-2
  BBF capacity out, BC/US-South closures, ~35% effective Canadian duty) NOT demand;
  consumption +0.4%; housing starts ~1.325MM. Pulp: fourth straight sub-$800 China NBSK year,
  Brazil/China oversupply. Paper/packaging down ~3%.
- Read-through: macro independently corroborates the model's decline/peak-contamination vetoes
  on the pulp/wood names (MERC especially). A timber-forest BUY would require a supply-driven
  cycle turn not yet visible in trailing fundamentals - the diffusion setup the signals
  side-channel is built to surface later, not a present buy.

---

## 8. Skeptical-PM usable verdict

USABLE - as a landmine-scanner, which is its job. The run (1) enumerated the small-cap
timber/forest universe and correctly separated 4 genuine forest-products/wood names from 10
keyword misrecalls (cannabis, uranium, lithium, gold, REITs, carpet, coal-royalty); (2)
refused to manufacture a BUY - every guard that fired (extreme-MoS on KOP, decline+peak-contam
on MERC, decline on MBC, cross-source on FOR) is defensible on inspection, zero false-positive
BUYs; (3) the one name a careless screen might flag as cheap (KOP, P/E 15, 8% FCF yield) was
correctly NOT certified because FCF-cap is the wrong lens - the guard caught a model artifact.
Honest limitation: the deep band is thin (4 names, all rejected) and the most theme-pure larger
names (BCC, GEF) sit just above the $2.0B cutoff in watch band, so a PM hunting timber exposure
would push the mktcap ceiling up. No actionable BUY, but a trustworthy "nothing to buy here
right now, and exactly why" - the correct, usable output for a late-cycle, weak-demand
forest-products tape.
