# Coverage Test — Household Products / Personal Care (Staples)

- **Slug:** `household-personal`
- **Sector:** Consumer Staples
- **Keywords:** `household products, personal care`
- **Code-path focus:** mature / low-growth
- **Skill version:** v0.3.0, commit `f12fef5`
- **Run batch:** `reports/smallcap/2026-06-21_cov-household-personal/`
- **Date:** 2026-06-21
- **Verdict:** **0 clean BUYs** — disciplined, expected outcome for a mature low-growth staples basket.

---

## 1. Funnel

| Stage | Count | Note |
|---|---|---|
| Discovery union (FTS ∪ SIC reverse-recall), full universe CSV | 246 | `universe_household_personal_2026-06-21.csv` |
| Small-caps routed through cheap_pass | 95 | mktcap-banded subset run through mechanical de-risk |
| cheap_pass survivors → candidates | 65 | 45 SIC-keep + 20 SIC-review → LLM gate |
| **deep band** (mktcap < $2.0B) | **43** | watch band (>$2.0B..$5.0B) = 22, skipped |
| **Gate-2 LLM theme-fit survivors (deep band)** | **14** | 7 pure_play + 7 partial; 29 misrecall dropped (resolved, not missing) |
| **Deep-dived** | **14** | every deep-band Gate-2 survivor, no sampling |
| deepdive ERROR files | 0 | clean run |
| **Mechanical BUYs** | **0** | none cleared MoS≥30% AND buy_eligible AND 0 kill-flags |
| **Adversarially-clean BUYs** | **0** | nothing to verify; 0-BUY confirmed |

`finalize_run`: deep-band 43, reports 14, gate2-misrecall (resolved) 29, **missing 0** — the A5 misrecall-resolution path fired correctly (no spurious "missing" warning, no `--allow-missing` needed).

### Gate-2 theme-fit decisions (deep band, 43 names)

**RETAIN (14):**
- **pure_play (7):** HNST (Honest — personal care, baby/wipes/skin), HELE (Helen of Troy — housewares + health/beauty), EPC (Edgewell — wet shave / sun & skin / feminine care), OLPX (Olaplex — hair care), ENR (Energizer — "global diversified household" + auto care), SPB (Spectrum Brands — home & personal care, appliances, home & garden), NUS (Nu Skin — skin care + nutrition, direct-sell).
- **partial (7):** LFVN (nutrigenomics + personal care, direct-sell), FTLF (nutritional supplements/wellness), LCUT (Lifetime Brands — kitchenware / housewares), NATR (Nature's Sunshine — nutritional + personal care), AXIL (hair & skin care + hearing protection), SCL (Stepan — surfactants, the upstream ingredient backbone of detergents/personal care), BWMX (Betterware de México — DTC home-organization / household products).

**DROP — misrecall (29):** SOTK (ultrasonic coating systems), FOSL (fashion watches), ALTO (ethanol/fuels), CYH (hospitals), MATV/MAGN (B2B specialty materials / nonwovens), NGVC/WMK (grocery retailers), INNV/AVAH/SNDA/PNTG (senior-care / home-health services), PAHC (animal health), LEG (bedding/auto industrial components), TRS (packaging/aerospace/industrial), HAIN (better-for-you **food** — snacks/baby food/beverages, not HPC), VTEX (ecommerce SaaS), ACNT (broad specialty chemicals), IMUX (biotech), and 11 BDCs / finance shells (WHF, NMFC, SLRC, KBDC, GSBD, MSDL, BCIC, PFLT, MFIC, OCSL, plus the SIC=nan finance cluster). The BDC cluster is the canonical keyword over-recall (FTS swept "personal" / "products" mentions in finance prospectuses); SIC=nan + 1940-Act language made these unambiguous drops.

---

## 2. Ranked shortlist (all WATCH — see `RANKING.md`)

| # | Tkr | Rating | Rev | NI | OCF | RevGr | mos_basis | eff MoS% | buy_eligible | kill |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AXIL | 观察 | $26M | $1M | $2M | -4% | fcf_cap | -70.1 | True | 1 (rev-split) |
| 2 | BWMX | 观察 | n/a | n/a | n/a | — | fcf_cap | None | True | 1 (gc+mw) |
| 3 | ENR | 观察 | $2,953M | $239M | $147M | +2% | nav | -100.0 | False | 0 |
| 4 | EPC | 观察 | $2,224M | $25M | $118M | -1% | fcf_cap | -171.3 | False | 0 |
| 5 | FTLF | 观察 | $16M | $2M | $7M | -75% | fcf_cap | -89.1 | False | 0 |
| 6 | HELE | 观察 | $1,786M | -$899M | $171M | -6% | fcf_cap | **+30.6** | **False** | 0 |
| 7 | HNST | 观察 | $371M | -$16M | $15M | -2% | fcf_cap | None | False | 0 |
| 8 | LCUT | 观察 | $648M | -$27M | $8M | -5% | nav | -73.2 | False | 0 |
| 9 | LFVN | 观察 | $228M | $10M | $12M | +14% | nav | -70.6 | True | 0 |
| 10 | NATR | 观察 | $480M | $20M | $35M | +6% | nav | -69.2 | True | 0 |
| 11 | NUS | 观察 | $1,485M | $160M | $80M | -14% | fcf_cap | **+93.8** | **False** | 0 |
| 12 | OLPX | 观察 | $423M | -$9M | $59M | +0% | fcf_cap | -1.4 | False | 0 |
| 13 | SCL | 观察 | $2,332M | $47M | $148M | +7% | fcf_cap | None | True | 0 |
| 14 | SPB | 观察 | $2,809M | $100M | $204M | -5% | nav | -95.0 | False | 0 |

Note: `margin_of_safety_pct` is a fraction in the JSON; the table shows it ×100.

---

## 3. BUY analysis — honest 0-BUY

**No candidate satisfies the BUY rule** (mos_basis∈{fcf_cap,nav} AND numeric MoS≥30% AND buy_eligible==true AND zero kill-flags). The two failure clusters are mutually exclusive — and that disjointness is the whole story of this theme:

**Cluster A — buy_eligible==true but MoS fails (5 names: AXIL, BWMX, LFVN, NATR, SCL).**
These cleared every v0.3.0 guard, but their MoS is negative or None:
- AXIL fcf_cap MoS = -70.1% (priced above intrinsic; EV/EBITDA 28x — expensive micro-cap).
- LFVN/NATR route to NAV (direct-sell, asset-light); NAV MoS ≈ -70% (trade above tangible book).
- SCL / BWMX have None MoS (SCL: non-positive normalized FCF after cyclical-trough handling; BWMX: financials too thin to band — see data-quality).
None is close to a BUY on price.

**Cluster B — MoS≥30% but buy_eligible==false (2 names: HELE, NUS).**
These are the only two that clear the MoS threshold, and **both are correctly blocked by the v0.3.0 mechanical guards** — this is the headline finding of the test.

### Adversarial verification of the two MoS-passers (the would-be BUYs the machine refused)

**HELE (Helen of Troy) — MoS +30.6%, blocked by `fundamental_decline_flag` + `fcf_sustainability_uncertain`.**
- Adversarial question: is +30.6% MoS a real opportunity or an artifact?
- Verdict: **ARTIFACT — guard is correct.** Latest NI = **-$899M** (massive goodwill/intangible impairment), revenue -6.4% YoY, rev_slope_sign = -1, contamination_ratio 0.9108, latest_below_avg = True. The reverse-DCF "cheapness" is computed off a normalized FCF base that the most recent year sits below — a textbook melting-ice-cube. `fcf_sustainability_uncertain` additionally fired (capex proxied from OCF; reverse-DCF implied growth -20.5% < -15% → market is pricing in decline). The machine refusing this BUY is exactly right.

**NUS (Nu Skin) — MoS +93.8%, blocked by `fundamental_decline_flag`.**
- Adversarial question: 93.8% MoS is enormous — is the market wrong, or is the model?
- Verdict: **ARTIFACT — guard is correct.** Revenue -14.3% YoY in a structurally declining direct-sell beauty model (China + recruiting headwinds), rev_slope_sign = -1, contamination_ratio 0.7164, latest_below_avg = True. The 93.8% MoS is the canonical "neglected ≠ undervalued" trap: normalized FCF looks cheap against a price that has already fallen ~33% over 12m (P16 divergence = `aligned` — price is tracking the deterioration, not mispricing it). Buying on a normalized-FCF MoS while the top line melts 14%/yr is the precise error the fundamental-decline veto exists to prevent.

Both adversarial verdicts confirm: **0 BUY is the disciplined-PM-correct outcome.** There is no name here where the price is wrong about a stable business.

---

## 4. Code-paths exercised (the point of a coverage test)

**Discovery / gate paths:**
- FTS keyword discovery + SIC reverse-recall floor union (246-row universe).
- SIC coarse gate (Gate 1): 65 cheap_pass survivors → 45 keep / 20 review.
- LLM theme-fit (Gate 2): 43 deep-band → 14 retained / 29 misrecall.
- A5 misrecall-resolution in `finalize_run` (29 resolved, 0 missing) — **no `--allow-missing` required.**

**cheap_pass mechanical de-risk:**
- going_concern **double-hit** guard (going_concern AND substantial_doubt) — BWMX hit kf_going_concern=1 alone (no substantial_doubt) so it did NOT trigger elimination; intended FP-suppression behavior.
- killflag_count≥2 reject — BWMX (gc=1 + mw=1, but gc needs double-hit so count=1) and AXIL (reverse_split=1) both stayed in at count=1.

**valuation `buy_eligible` composite guards that fired (across the 14):**
- `fundamental_decline_flag` — **4x** (ENR, HELE, NUS, +1) — the melting-ice-cube veto, the dominant gate this theme.
- `cross_source_mismatch` (P7 second-source/yfinance) — **3x** (FTLF, HNST, LCUT) — SEC-XBRL vs yfinance >2.5x disagreement on revenue/debt; legitimately gated as a data-integrity failure (e.g. FTLF rev SEC $15.9M vs yf $90.8M = 5.7x; HNST debt 3.9x; LCUT debt 43.7x).
- `peak_contamination_flag` (V-shape value-trap) — **2x** (LCUT, OLPX).
- `extreme_mos_review_required` — 1x (EPC, MoS -171%).
- `fcf_sustainability_uncertain` — 1x (HELE).
- `debt_truncation_suspected` — 1x (LCUT).
- `financial_sic_forced_unsuitable` + `insurance_concepts_present` — 1x (**SPB** — Spectrum Brands carries insurance XBRL concepts via a subsidiary; the A3 insurance-holdco routing fired, routing it to NAV/abstain regardless of its 3690 SIC). Good catch — this is the BOC-hole closure path working on a real name.
- `cross_source_checked=True` on all 14 — the P7 external feed was reachable for every survivor.

**MoS-basis routing:** fcf_cap 9, nav 5, abstain 0 (every name banded; no abstains because each had enough data to route, though several produced None MoS within their basis).

**Firewall verification:** the T2 `signals` side-channel (P16 price_divergence, P17 ownership) was populated for all 14 and is rendered below as context only. **No `buy_ineligible_reasons` entry references any `signals.*` field** — the firewall held; no signal originated or up-weighted any verdict.

---

## 5. Data-quality issues

1. **`cross_source_mismatch` on 3 of 14 (FTLF, HNST, LCUT)** — SEC-XBRL vs yfinance disagree >2.5x on revenue or debt. For FTLF the SEC revenue ($15.9M) looks like a partial/segment tag vs yf's $90.8M consolidated; LCUT's SEC total_debt ($5.1M reported vs $330M implied liab-equity, 43.7x yf gap) is a clear truncation. These names' MoS numbers cannot be trusted and the guard correctly blocked them.
2. **BWMX financials too thin to band** — None MoS, EV/EBITDA/EV-Sales all None; foreign filer (Mexican S.A.P.I.), XBRL coverage sparse. Also carries an unresolved going-concern + material-weakness mention in cheap_pass that passed the double-hit guard. Treat any BWMX number with suspicion.
3. **Several large negative one-off NIs** (HELE -$899M, LCUT -$27M, OLPX -$9M) are impairment-driven; net-income-based ratios (PE) are null by design, EV/EBITDA partial. Reverse-DCF off normalized FCF is the right lens but produces the value-trap MoS the vetoes then catch.
4. **`concentration_unquantified` recurring** — text concentration flag True but no XBRL magnitude (HELE, OLPX, NUS, AXIL, NATR) — advisory only (A2), does not gate; analyst must read the 10-K footnote.
5. **T2 enrichment unavailable** — TrendsMCP daily+monthly quota exhausted at run time; no Google/Amazon trend series pulled. This is enrichment only and never drives buy_eligible — no impact on the verdict.

---

## 6. recall@gold

**n/a** — `household-personal` has no hand-built gold list in `tools/track_forward.py` (gold lists exist only for deathcare, water-utilities, railcar-leasing, regional-gaming). `track_forward.py --recall-gold <candidates>` returned: *"no gold list for theme 'household-personal' — not measurable."* Recall floor is therefore not quantifiable for this theme.

---

## 7. Market-intel / T2 diagnostic signals (context only — NOT used in the rating)

P16 price-divergence labels (firewalled, diagnostic):
- `melting_ice_cube_priced`: ENR, HELE, LCUT, SCL — price already reflects deterioration.
- `unpriced_improvement`: AXIL, FTLF, LFVN — fundamentals up vs price (would be the interesting cohort IF a real MoS existed; none does here).
- `aligned`: EPC, HNST, NATR, NUS, OLPX, SPB.
- `unclear`: BWMX.

Notable: NUS 12m price -32.8% (aligned — market is right about the decline); LCUT +132.8% 12m yet labeled melting_ice_cube_priced (run-up despite deteriorating fundamentals — a momentum/value-trap flag for any future BUY). These are calibration snapshots only; none gates anything until each signal earns its own Brier.

TrendsMCP commercial demand series: not retrieved (quota). market-intel skill not separately invoked for per-ticker sentiment given the 0-BUY outcome (no name warrants the spend).

---

## 8. Skeptical-PM usable verdict

**Usable: YES — as a landmine scanner, which is its job.** The run did exactly what the world-view promises: it enumerated a 246-name universe, mechanically separated 14 true HPC members from 29 keyword misrecalls (BDCs, hospitals, food, industrials), then refused to hand a PM a single BUY because every candidate either trades above intrinsic value or is a melting ice cube. The two names a naïve normalized-FCF screen would have flagged as "deep value" (HELE +31%, NUS +94% MoS) are precisely the two the v0.3.0 `fundamental_decline_flag` blocked, and adversarial review confirms both are genuine value traps, not model artifacts. The SPB insurance-holdco routing and the three cross_source_mismatch catches show the data-integrity layer biting on real names. A disciplined PM gets a clean, defensible "nothing to buy here, and here is mechanically why" — the most valuable output a staples basket at this point in the cycle can produce.
