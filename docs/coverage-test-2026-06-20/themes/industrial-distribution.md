# Coverage Test - Industrial Distribution / MRO Supply

- Run: 2026-06-21_cov-industrial-distribution
- Skill: small-cap-deepdive v0.3.0 (commit f12fef5, skill_dirty=true)
- Theme keywords: "industrial distribution, MRO supply"
- Sector: Industrials | Code-path focus: working-capital
- Date: 2026-06-21
- recall@gold: n/a (no gold list for this theme)
- Headline: 0 BUYs (0 mechanical, 0 adversarially-clean). Both deep-band Gate-2 survivors are WATCH.

---

## 1. Funnel

| Stage | Count | Detail |
|---|---|---|
| FTS raw recall | 38 | "industrial distribution"=37, "MRO supply"=2, dedup 38 |
| Banded | 14 deep + 4 watch + 14 large + 5 unknown | mktcap fallback applied |
| cheap_pass scanned | 14 | deep survivors + watch-band added |
| candidates (post SIC gate) | 12 | keep=10, review=2 |
| Gate-2 pure_play/partial | 4 | GIC, ZKH (deep) + DXPE, DNOW (watch) |
| Deep-dived (deep-band Gate-2 survivors) | 2 | GIC, ZKH |
| Mechanical BUYs | 0 | - |
| Adversarially-clean BUYs | 0 | - |

No SIC reverse-recall floor fired. theme_sics("industrial-distribution") returns [] - the slug is
not in THEME_SIC, so discovery was FTS-only. Structural coverage finding: industrial distribution
HAS dedicated wholesale SICs (5063/5065/5072/5074/5084/5085 etc.) that are NOT wired as a recall
floor. The large true distributors (FAST, GPC, AIT, MSM, VSE) were all correctly out of scope
(large band), but the floor gap means a true small-cap distributor with weak keyword density could
be lost to FTS recall alone.

---

## 2. Gate-2 classifications (12 candidates)

Deep-dive set (deep band, in-theme):
- GIC Global Industrial Co (SIC 5084) - pure_play MRO/industrial products distributor.
- ZKH ZKH Group (SIC 5200, 20-F) - pure_play China MRO procurement platform.

Surfaced, not deep-dived (watch band, in-theme - band guard):
- DXPE DXP Enterprises (SIC 5084, $2.69B) - pure_play pump/MRO distributor.
- DNOW DNOW Inc (SIC 3533, $2.46B) - partial; energy PVF + MRO distribution.

Gate-2 misrecalls dropped (resolved, not missing):
GFF (diversified holdco), BNL (industrial-tenant REIT), RCKY (footwear mfr), BWMN (engineering
consulting), NRP (coal/mineral royalty LP), GNL (net-lease REIT), PNNT + PFLT (BDC lenders).
These keyword-matched "industrial distribution" incidentally. finalize_run resolved all 8 via
gate2_results.json (A5 path) -> 0 missing.

---

## 3. Ranked shortlist (RANKING.md)

Both deep-dive names land in the non-buy tier. 0 BUYs.

| Rank | Ticker | Verdict | mos_basis | MoS | buy_eligible | BUY? |
|---|---|---|---|---|---|---|
| 1 | GIC | WATCH | nav | -82.3% | True | NO (MoS << +30%) |
| 2 | ZKH | WATCH | fcf_cap | null | False | NO (cross_source_mismatch) |

---

## 4. Per-name detail

### GIC - Global Industrial Company (deep, $1.26B) - WATCH, not BUY
- Clean, debt-free distributor. Rev $1,379M, NI $72.1M, OCF $77.8M, debt $0.3M, cash $61.7M.
  EV/Sales 0.87x, EV/EBITDA 11.4x, FCF yield 5.9%. rev_slope +1, contamination 1.14 (latest ABOVE
  avg), no decline/peak flags. kill-flags 0.
- Valuation: FCF-cap model ruled unsuitable by the C1 data-quality guard
  (fcf_cap_blocked_by_c1_data_quality_guard via debt_stale:>18_months_behind_latest_assets), so
  mos_basis=nav. NAV MoS = -82.3% (mktcap $1,259M vs tangible equity $278M).
- BUY rule: basis=nav OK, buy_eligible=True OK, but MoS -82.3% << +30% FAIL -> NOT A BUY.
- Adversarial: Is the -82% a real overvaluation or an artifact? Artifact (model mismatch). NAV is
  the wrong lens for an asset-light distributor - its value is the earnings stream, not the
  warehouse. The model honestly abstains from a tradeable FCF MoS instead of fabricating one. On the
  relevant multiples GIC is fairly (not cheaply) priced. Verdict: legitimate WATCH, no BUY artifact.
- Disconfirmation: No fraud/SEC/short-seller vs Global Industrial Co. (The "GIC fraud lawsuit" noise
  online = Singapore SWF GIC suing NIO - unrelated entity.)

### ZKH - ZKH Group (deep, $403M, 20-F) - WATCH, buy_eligible=False
- buy_eligible = False, reason = cross_source_mismatch (P7 second-source gate). SEC shares 5,563.5M
  (ordinary) vs yfinance 129.7M -> 42.9x. Root cause: ADS = 35 ordinary shares each (per 20-F);
  yfinance reports ADS-level, SEC reports ordinary. Real data-integrity catch, NOT fraud - but a
  share count this ambiguous correctly cannot back a tradeable MoS.
- Financials unusable: 20-F XBRL extraction returned latest_revenue / net_income / OCF / debt =
  None (foreign-filer XBRL blind spot). Web cross-check of the 20-F: FY2025 net LOSS ~US$20M on
  ~US$1,285M revenue, OCF ~ -US$2M -> unprofitable, no FCF MoS possible even with clean data.
- BUY rule: buy_eligible=False -> NOT A BUY.
- Adversarial: No BUY to contest. The non-BUY is doubly correct (P7 gate + unprofitable + HFCAA
  delisting overhang + PRC cash-transfer restrictions). Correct rejection.

---

## 5. Which code-paths fired

- P5 mktcap fallback + 4-band tagging - deep/watch/large/unknown all populated; null-mktcap names
  (CMPO/PLYM/AHH/MRC/IVP) banded unknown not silently dropped.
- P3 concentration kill - fired correctly AND incorrectly (see section 6): killed DSGR.
- C1 FCF-model-unsuitable guard - fired on GIC (debt_stale) -> routed to NAV basis.
- P7 cross-source sanity band - fired on ZKH (42.9x shares) -> buy_eligible=False. The decisive
  gate this run. GIC passed P7 ("within 2.5x on all comparable fields").
- NAV-basis path - exercised on GIC.
- fcf_cap abstain path (intrinsic band unavailable) - exercised on ZKH.
- A5 Gate-2 misrecall resolution - 8 misrecalls resolved at finalize, 0 spurious "missing".
- Firewalled signals side-channel (P16/P17) - emitted as top-level signals sibling of derived on
  both names; verified NOT leaked into derived and NOT read by buy_eligible.
- SIC reverse-recall floor - did NOT fire (theme not in THEME_SIC) - coverage gap, see section 6.
- Working-capital focus - GIC working capital is the live lever (asset-light, debt-free,
  inventory+AR funded distributor); OCF $77.8M ~ NI $72.1M (healthy conversion, no AR/inventory
  bloat divergence). ZKH working-capital signal unreadable (XBRL extraction failed).

---

## 6. Data-quality issues

1. DSGR false-positive concentration kill (most serious). Distribution Solutions Group ($1.32B,
   deep band, a TRUE industrial distributor) was rejected at cheap_pass with concentration_flag=kill,
   top_customer_pct=100%. The 100% was mis-parsed from a 10-K footnote fragment that actually reads
   "[one customer] accounted for approximately 5% of consolidated revenue. Approximately 100% of
   Canada Branch Division's revenue..." - the extractor grabbed the division's internal 100%, not a
   customer concentration. This wrongly killed a real theme member before deep-dive. P3 magnitude
   extractor needs a guard against "X% of [Division]'s revenue" phrasing. (kf otherwise 0, health 85.)
2. EACO dropped (defensible). EACO Corp ($481M, SIC 5065 electronics distributor, deep band) was
   dropped pre-cheap_pass for flag_illiquid=True (~$7k/day volume). Legitimate liquidity drop, but
   note smallcap_candidate=False silently removes it before the cheap_pass scan.
3. ZKH 20-F XBRL extraction empty - all financial series None (foreign-filer blind spot); P7 shares
   mismatch (ADS vs ordinary 42.9x). Both correctly block, but the name is effectively
   un-analyzable from T1 alone.
4. MRC Global banded unknown - yfinance 404 (transient delisting-style error) left mktcap null; MRC
   is a major PVF/MRO distributor that should have been a deep candidate. mktcap fallback did not
   recover it within the run.
5. finalize_run MD-parser artifacts - auto-verdicts show mos_basis=abstain for both (couldn't parse
   basis from terse reports; true basis GIC=nav/ZKH=fcf_cap in valuation JSON) and a spurious
   kill_flags=[material_weakness] on GIC (regex pulled the word from the de-risk checklist line;
   GIC has 0 kill-flags). Neither affects the BUY outcome.

---

## 7. recall@gold

n/a - industrial-distribution has no hand-built gold list in THEME_GOLD. track_forward --recall-gold
returns "no gold list ... not measurable." (Not a failure; simply unmeasured.)

---

## 8. Market-intel / T2 context (does NOT drive buy_eligible)

- TrendsMCP (Google Search): "industrial distribution MRO supply" -> flat/zero search interest 12M &
  3M; "MRO distribution" -> near-zero (6/100). Cold, unhyped theme - no retail/ETF crowding. Per the
  skill's world-view (hot themes = the casino), a low-attention theme is the favorable setup; the
  edge, if any, is in the mechanical survivor, not the narrative. No alt-data signal up-weights any
  name (firewall holds).

---

## 9. Skeptical-PM usable verdict

Usable run, honest 0-BUY. The funnel correctly separated 2 genuine small-cap distributors (GIC, ZKH)
from 8 incidental keyword matches and 4 out-of-band large/watch distributors, and returned neither
as a BUY for defensible reasons (GIC = clean but not cheap; ZKH = broken data + unprofitable +
delisting risk). GIC is the one name a PM would put on a WATCH list and revisit on a drawdown.

Two findings temper the "usable" verdict and should be fixed before trusting recall on this theme:
(a) the missing SIC reverse-recall floor (wholesale SICs 50xx not wired) means recall rests on FTS
alone; and (b) the DSGR false-positive concentration kill silently removed a real $1.3B deep-band
member before it could be deep-dived. Both are recall-side risks: this run's 0-BUY is trustworthy on
the names it SAW, but its universe coverage for industrial distribution is under-floored.
