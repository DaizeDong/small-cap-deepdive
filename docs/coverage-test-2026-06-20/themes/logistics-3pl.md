# Coverage Test, Theme: logistics-3pl (Industrials)

- **Slug:** `logistics-3pl`
- **Keywords (FTS):** `logistics, third-party logistics, supply chain`
- **Sector:** Industrials
- **Code-path focus:** asset-light vs asset-heavy logistics
- **Skill version:** v0.3.0 (commit `f12fef5`, `skill_dirty=true`)
- **Run batch:** `reports/smallcap/2026-06-21_cov-logistics-3pl/`
- **Date:** 2026-06-21 (run executed under a 2026-06-21 system clock; docs folder dated 2026-06-20 per harness)
- **Verdict (skeptical PM):** **USABLE.** 0 clean BUYs is the correct, honest answer, the universe contains no clean small-cap 3PL pure-play at a ≥30% margin of safety today, and every guard that fired was a true positive. The scanner's value here was elimination, not selection.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| Raw discovery universe (FTS, after mktcap resolve) | 685 | `discover.py`, FTS recall on 3 keywords; bands: 343 deep / 76 watch / 212 large / 54 unknown. **No SIC reverse-recall floor** (logistics-3pl is NOT in `THEME_SIC`), so FTS-only recall. |
| Small-cap candidates health-checked | 321 | deep + unknown bands sent to `cheap_pass.py` |
| `cheap_pass` survivors | 181 | hard kill-flag screen (going-concern / death-spiral / material-weakness / concentration) |
| After SIC Gate 1 | 181 | keep=114, review=67 (review forwarded to LLM gate; 0 hard-dropped) |
| Deep-band candidates (Gate-2 input) | 135 | the cohort that earned a theme-fit judgment |
| **Gate 2 (LLM theme-fit) survivors** | **11** | 8 pure_play + 3 partial; **124 misrecalls dropped** (8.1% precision) |
| Deep-dived (every survivor, no sampling) | 11 | 0 ERROR files |
| Mechanical BUYs | **0** | none reached numeric MoS ≥ 30% with `buy_eligible == true` |
| BUYs surviving adversarial check | **0** | honest 0-BUY |

**Gate-2 precision = 11/135 ≈ 8.1%**, textbook FTS over-recall. The keyword `supply chain` swept in the entire biotech sector ("temperature-controlled supply chain", "supply chain for our drug"), restaurants, apparel, consumer-products and medical-device names. This is exactly the canonical failure mode the two-stage gate exists to catch; without Gate 2, 124 off-theme names would have hit the deep-dive queue.

**Recall floor caveat:** because logistics-3pl has no dedicated-SIC reverse-recall floor, recall rests entirely on FTS. The dedicated transport/3PL SICs (4213 motor freight, 4412 deep-sea, 4731 freight forwarding) are NOT enumerated as a floor. A true small-cap 3PL with low keyword density in its 10-K could have been missed at discovery and would never appear in this funnel. This is a structural recall gap for the theme (see §6).

---

## 2. Ranked shortlist (all WATCH, full table in `RANKING.md`)

| # | Ticker | Name | Asset model | mos_basis | MoS (basis) | buy_eligible | Rating | Primary block |
|---|---|---|---|---|---|---|---|---|
| 1 | CRGO | Freightos Ltd | asset-light (digital freight platform) | fcf_cap | n/a (intrinsic band unavailable) | true* | 观察 | 20-F XBRL extraction failure → no MoS |
| 2 | CVLG | Covenant Logistics Group | asset-heavy (truckload carrier) | nav | −75.6% | **false** | 观察 | financial_sic + **insurance_concepts_present** |
| 3 | CYRX | Cryoport | asset-light (cold-chain life-sci 3PL) | nav | −50.0% | **false** | 观察 | **cross_source_mismatch** (debt 178x) |
| 4 | FWRD | Forward Air | asset-light (forwarding/3PL) | nav | −100.0% | true | 观察 | negative NAV MoS; fcf_cap unsuitable (D/A 0.63) |
| 5 | ILPT | Industrial Logistics Properties Trust | asset-heavy (logistics REIT) | nav | −28.9% | **false** | 观察 | financial_sic + cross_source_mismatch |
| 6 | LPA | Logistic Properties of the Americas | asset-heavy (LatAm logistics real estate) | fcf_cap | n/a (intrinsic band unavailable) | true* | 观察 | 20-F XBRL extraction failure → no MoS |
| 7 | PANL | Pangaea Logistics Solutions | asset-heavy (owned/chartered drybulk fleet) | fcf_cap | **+26.1%** | **false** | 观察 | fcf_sustainability_uncertain + cross_source_mismatch |
| 8 | RLGT | Radiant Logistics | asset-light (non-asset 3PL) | nav | −80.8% | true | 观察 | negative NAV MoS |
| 9 | SLGB | Smart Logistics Global | asset-heavy (China line-haul trucking) | fcf_cap | n/a (normalized FCF ≤ 0) | **false** | 观察 | cross_source_mismatch (debt 4x, rev 7x) |
| 10 | SRTA | Strata Critical Medical (ex-Blade) | asset-light/mixed (time-critical medical logistics) | nav | −76.3% | true | 观察 | negative NAV MoS; SEC debt=0 (stale) |
| 11 | ULH | Universal Logistics Holdings | mixed (asset-based trucking + value-added 3PL) | fcf_cap | n/a (normalized FCF ≤ 0) | true | 观察 | no positive normalized FCF → no MoS |

\* `buy_eligible==true` is hollow for CRGO/LPA: it merely means no *gating* guard fired, but the foreign-filer XBRL pull yielded no revenue/debt/cash at all, so there is **no intrinsic band and no MoS to test**. They are WATCH-by-abstain, not viable BUY candidates.

**BUY rule applied** (BUY ⟺ `mos_basis∈{fcf_cap,nav}` AND numeric MoS ≥ 30% AND `buy_eligible==true` AND 0 hard kill-flags): **no candidate satisfies all four.** The single name with a positive numeric MoS (PANL, +26.1%) is both below the 30% threshold AND `buy_eligible==false`.

---

## 3. The 0-BUY decision, honest accounting

No mechanical BUY fired. The decision is robust along two independent axes:

1. **No name reached MoS ≥ 30%.** The fcf_cap names with a *computable* MoS: PANL +26.1% (below threshold). Every NAV-basis name returned a deeply negative NAV margin of safety (−28.9% to −100%), i.e. trading at a premium to tangible/book equity, the opposite of a NAV bargain. The remaining fcf_cap names (CRGO, LPA, SLGB, ULH) had no computable intrinsic band (XBRL gaps or non-positive normalized FCF).
2. **Eligibility guards independently blocked the closest names.** Even if PANL had cleared 30%, `buy_eligible==false` would have stopped it.

This is the designed-for outcome: "the small-cap universe for this theme does not contain a clean industrial beneficiary at a margin of safety right now." Asset-heavy logistics (drybulk, trucking, REITs) trades on cyclical/asset value where the fcf_cap model is correctly ruled unsuitable; asset-light 3PLs (FWRD, RLGT) are valued *above* NAV with no FCF-discount cushion.

### Adversarial verification of the marginal case (PANL)

PANL is the only name with a positive numeric MoS, so it is the one that could plausibly be a missed BUY. Verdict: **the gate correctly blocked a data artifact + an unsuitable model, not a real opportunity.**

- **cross_source_mismatch (TRUE POSITIVE).** Model: SEC-XBRL `total_debt = $97.2M` vs yfinance `$360M` (3.7×). Independent check (Q4-2025 / FY2025 results, filed 2026-03-16): **total debt incl. finance leases ≈ $375.6M**, long-term debt ≈ $330.9M mid-2025, D/E ≈ 0.80. The SEC pull captured only a fraction of consolidated vessel debt. With true debt ~$375M (not $97M), EV is understated by ~$280M and the displayed +26.1% fcf_cap MoS is materially overstated, corrected, it collapses toward zero/negative. The P7 second-source band caught exactly the corruption it was built for.
- **fcf_sustainability_uncertain (TRUE POSITIVE).** PANL is asset-heavy cyclical drybulk. The model flagged lumpy OCF (peak-year OCF $134.8M vs $57.8M median of other years, contamination_ratio 0.73) and used an OCF proxy with capex unknown. A reverse-DCF off a peak-cycle FCF on a shipping name is precisely the melting-ice-cube / peak-contamination trap; blocking it is correct discipline, not over-caution.
- **Conclusion:** PANL is not a clean BUY the machine missed; it is a name whose apparent cheapness depended on a corrupted debt figure and a peak-cycle FCF. **0 BUYs survives adversarial review.**

---

## 4. Code-paths exercised (the point of this coverage test)

The asset-light vs asset-heavy split was the focus, and both branches plus most v0.3.0 guards fired on real names:

- **Asset-heavy → fcf_cap ruled unsuitable → NAV path.** `fcf_cap_model_unsuitable:debt_to_assets>0.62` fired on **FWRD** (D/A 0.627) routing it to NAV. NAV path then produced negative NAV-MoS on CVLG, CYRX, FWRD, ILPT, RLGT, SRTA (6 names), the NAV branch is live and discriminating.
- **Asset-light → fcf_cap path.** CRGO, LPA, SLGB, ULH routed to fcf_cap; ULH/SLGB returned non-positive normalized FCF (`intrinsic_band_null:normalized_fcf_nonpositive`), CRGO/LPA returned no band (XBRL gap). Path exercised; none produced a passable MoS.
- **P7 second-source sanity band (cross_source_mismatch), fired 4×, all true positives:** PANL (debt 3.7×), CYRX (debt 178×, SEC $1.3M vs yf $230.5M), ILPT (revenue 7.3×, REIT rental income mis-tag), SLGB (debt 4.0× AND revenue 7.0×). This is the most-exercised guard in the run and the decisive one, it blocked 4 of the 11 survivors. Strong evidence the external-feed integrity gate is doing real work on small/foreign filers.
- **insurance_concepts_present (A3), fired on CVLG.** A truckload carrier (SIC 4213) flagged insurance XBRL concepts and was routed like a financial holdco (NAV/abstain). True positive: Covenant operates a captive-insurance / risk-retention subsidiary (Transport Enterprise Leasing / insurance accounting present), exactly the holdco-on-non-financial-SIC case A3 was designed to catch.
- **financial_sic_forced_unsuitable, fired on ILPT (SIC 6798 REIT)** and contributed to CVLG.
- **Concentration (P3):** `customer_concentration_flag=true` with `concentration_flag==null` (magnitude unquantified) on several names (CVLG 35%, SLGB 37%, FWRD 26%), all in the advisory band (`concentration_unquantified`), none reached the 40%/60% kill threshold. Advisory-only path exercised, correctly did not gate.
- **V-shape / fundamental-decline vetoes:** evaluated on PANL (contamination_ratio 0.73, but `latest_below_avg=false` / positive latest NI) → neither `fundamental_decline_flag` nor `peak_contamination_flag` fired. Correct (PANL is at/above its 5-yr average, not in a trough→peak rollover).
- **Foreign-filer (20-F) provenance + XBRL fragility:** `form_used=20-F` correctly populated for CRGO, LPA, SLGB. Surfaced the real weakness, 20-F XBRL extraction is far less reliable (CRGO/LPA: revenue/debt/cash all null).
- **Firewall (signals side-channel):** P16 price-divergence emitted for all (FWRD = `unpriced_improvement`, price −38%/−46% vs improving fundamentals; others `aligned`). Verified `valuation_*.json` contains **no** `signals` key, the diagnostic channel never touched `buy_eligible`. FWRD's `unpriced_improvement` did NOT rescue its −100% NAV-MoS into a BUY. Firewall holds end-to-end.

---

## 5. Data-quality issues

1. **20-F XBRL extraction failure (high severity).** CRGO and LPA (both foreign filers) returned NO revenue/debt/cash, fcf_cap MoS is unmeasurable. Their `buy_eligible==true` is misleading (no gate fired only because there was nothing to evaluate). RANKING.md shows them as `$0M revenue`, which is an extraction artifact, not a real zero. Any consumer must treat CRGO/LPA as "insufficient data," not "clean."
2. **cross_source_mismatch on 4/11, but note SEC was the wrong number in at least PANL/CYRX.** The mismatch correctly *blocked* BUY, but it leaves the SEC-XBRL pull as untrustworthy for debt on shipping/cold-chain/REIT names. CYRX debt 178× and SEC `latest_total_debt=$1.3M` is implausible for a company yfinance puts at $230M.
3. **SRTA SEC debt = $0 with `debt_stale:>18_months_behind`** and no cross-source flag (yfinance also null), a silent gap; SRTA's NAV is built on a possibly incomplete debt figure. navMoS −76% is far from BUY regardless, so no decision risk, but flagged.
4. **No SIC reverse-recall floor** for this theme → recall is FTS-only; structural risk of missing low-keyword-density true 3PLs (see §6).
5. **TrendsMCP quota exhausted** (5/5 daily, 100/100 monthly) → no live alt-data T2 enrichment available this run (see §7).

---

## 6. Recall@gold

**n/a**, logistics-3pl has no hand-built gold true-member list (`THEME_SIC` / gold lists exist only for water-utilities, railcar-leasing, regional-gaming, deathcare). `track_forward.py --recall-gold ... --theme logistics-3pl` returns: *"no gold list for theme 'logistics-3pl' → not measurable."* Discovery recall for this theme is therefore unmeasured. Given the absence of a SIC reverse-recall floor, recall is the weakest link in this run and cannot be quantified, a known coverage limitation, not a pass.

---

## 7. Market-intel / T2 analyst context (NEVER drives buy_eligible)

- **TrendsMCP:** unavailable this run (daily + monthly quota exhausted). No search-volume / news-volume momentum series could be pulled for "third party logistics" or constituent tickers.
- **Qualitative T2 (analyst knowledge, labeled non-T1, NOT in the decision path):** The freight cycle in 2025 to 26 has been in a prolonged downturn ("freight recession"), soft truckload rates pressured asset-heavy carriers (CVLG, ULH) and asset-light forwarders alike (FWRD's restructuring post-Omni merger; RLGT's organic softness). Drybulk (PANL) rode a 2024 fleet-expansion / rate spike that the model flagged as peak-contaminated. This macro context is consistent with the mechanical output, depressed/cyclical earnings, premiums to NAV on the asset-light names, and no clean ≥30% MoS, but it is context only and was firewalled out of every eligibility decision.
- Firewall reminder: none of the above, and none of the P16/P17 `signals`, were read by `valuation.py`, the `buy_eligible` composite, or the BUY trigger.

---

## 8. Skeptical-PM usable verdict

**USABLE, and a good demonstration of the scanner working as designed.**

- The funnel did real elimination: 685 → 11 true members → 0 clean BUYs, with 124 off-theme misrecalls auditably dropped at Gate 2 (resolved, not "missing").
- The 0-BUY is honest and survives adversarial review: the one positive-MoS name (PANL) was blocked by a guard that turned out to be a true positive (its real debt is ~4× what the SEC pull captured).
- Multiple distinct guards fired on real names (P7 cross-source ×4, A3 insurance on CVLG, financial-SIC on ILPT, fcf_cap-unsuitable on FWRD), and the asset-light/asset-heavy routing split behaved correctly.
- The firewall held: the diagnostic signals (incl. FWRD's `unpriced_improvement`) never leaked into a BUY.

**What a PM must NOT do with this output:** treat CRGO/LPA as analyzed, they are data-incomplete (20-F XBRL failure), not clean. And treat the recall side as unverified: with no SIC floor and no gold list, a genuinely cheap, low-keyword small-cap 3PL could be absent from this list entirely. The deliverable is a clean *eliminated* set plus a watchlist of 11 real members, none currently a buy, not proof that nothing cheap exists.
