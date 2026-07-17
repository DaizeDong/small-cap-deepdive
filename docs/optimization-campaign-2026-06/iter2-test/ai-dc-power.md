# iteration-2 test report, theme `ai-dc-power`

**Theme keywords:** `data center power,cooling,electrical infrastructure`
**Focus:** AI-datacenter picks-and-shovels (a deliberately *hot* theme, the casino).
**Run batch:** `2026-06-20_ai-dc-power` (skill commit `2599d66`, post V-shape veto + low-rev-loss label).
**Date:** 2026-06-20. **Verdict horizon:** matures 2027-06 (calibration unknown until then, honest state).
**Stress objectives:** (1) recall under an extremely noisy keyword set; (2) the new `peak_contamination_flag`
V-shape veto must NOT over-block genuine fast-growers; (3) EV/EBITDA via the EBIT cascade.

> **This is a research landmine-scanner output, not a buy list.** A `观察`/WATCH means "survived the
> mechanical gates, warrants human DD." Nothing here clears the iter2 BUY bar.

---

## 1. Funnel (raw → survivors → deep-dived)

| Stage | Count | Note |
|---|---|---|
| SEC FTS raw recall (10-K/10-Q/20-F/40-F) | ~917 hits across 3 keywords | `data center power`=54, plus `cooling` + `electrical infrastructure` (both extremely generic) |
| After market-cap filter (small-cap ≤ $2.0B) | 463 | universe CSV |
| After `cheap_pass` mechanical health check | 289 survivors | going-concern / death-spiral / material-weakness scan |
| After Gate 1 (SIC coarse) | 289 (keep=131, review=158) | SIC alone removed nothing here, financial/biotech SICs passed to Gate 2 |
| Band split | deep=220 (≤$2.0B), watch=69 ($2.0 to 5.0B) | watch-band surfaced, **not** deep-dived per band guard |
| **Gate 2 (LLM theme-fit) on 220 deep-band** | **8 retained** (pure_play/partial), 212 misrecall | **2.8% precision**, even noisier than the documented ~6.8% "AI agent" case |
| Deep-dived (every retained survivor) | **8 / 8** | BWMN, ESOA, HYLN, LMB, LTRX, OSS, SLNG, TGEN, all valuated, no `deepdive_*_ERROR.json` |

**Why the precision is so low.** `cooling` and `electrical infrastructure` are English-common substrings.
The deep band was dominated by community banks (~40 names: STEL, SRCE, DCOM, GABC, TCBK, QCRH…),
biotech/pharma (ZYME, INVA, ARVN, ENTA, ADCT, CTMX…), REITs (GNL, BFS, CHCT, ACRE), restaurants
(CBRL, KRUS), insurers (AMSF, AII, NODK, IGIC), grocery/retail (IMKTA, BBW, CATO, LOVE), shipping
(DSX, GLOP-PA) and consumer brands (SAM, HELE, RGR). Classic FTS over-recall, Gate 2 is load-bearing;
skipping it would have sent the entire regional-bank and biotech sectors to the deep-dive queue.

**Recall audit (did Gate 2 drop any genuine member?).** I re-scanned all 220 deep-band blurbs for
high-signal DC-infra terms (`data center`, `hyperscale`, `liquid cool`, `switchgear`, `busway`, `UPS`,
`transformer`, `chiller`, `substation`, `power distribution`, `colocation`…). 18 non-retained names hit
≥1 term; on inspection 16 were false hits (`rack`="track record", `ups`="groups", generic
"power generation"). Two were genuine and **added back**: **BWMN** (engineering firm explicitly serving
"data center developers and hyper-scalers") and **SLNG** (LNG-to-power for "data centers where the data
center does not have adequate access to the electrical grid"). One borderline (**MRAM**/Everspin) was
left as misrecall, it is a persistent-memory *chip* supplier (data center is one end-market), not
power/cooling/electrical infrastructure. **Final deep set = 8.**

---

## 2. Ranked shortlist (from `RANKING.md`)

| # | Ticker | Name | Rating | Conf | Mktcap | Rev | NI | OCF | Rev growth | EV/Sales | EV/EBITDA | MoS | kill |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BWMN | Bowman Consulting | 观察 WATCH | 55% | $528M | $490M | +$13M | +$36M | +15% | 1.16x | **15.4x** | −82% | 0 |
| 2 | LMB | Limbach Holdings | 观察 WATCH | 55% | $955M | $647M | +$39M | +$46M | +25% | 1.46x | **14.0x** | −75% | 0 |
| 3 | ESOA | Energy Services of America | 观察 WATCH | 50% | $316M | $411M | +$2M | +$4M | +17% | 0.81x | n/a | −96% | 0 |
| 4 | OSS | One Stop Systems | 观察 WATCH | 45% | $457M | $32M | +$5M | −$0M | +31% | 13.5x | n/a | null | 0 |
| 5 | LTRX | Lantronix | 观察 WATCH | 40% | $296M | $123M | −$11M | +$7M | −23% | 2.29x | n/a | −87% | 1 (MW) |
| 6 | SLNG | Stabilis Solutions | 观察 WATCH | 40% | $86M | $68M | −$1M | +$9M | ~0% | 1.30x | 31.3x | −99% | 0 |
| 7 ⬇ | HYLN | Hyliion Holdings | **避开 AVOID** | 60% | $1,444M | $4M | −$57M | −$46M | +130% | **410x** | n/a | −90% (NAV) | 0 |
| 8 ⬇ | TGEN | Tecogen | **避开 AVOID** | 55% | $180M | $27M | −$8M | −$10M | +20% | 6.87x | n/a | null | 1 (MW) |

EV/EBITDA via the EBIT cascade (`OperatingIncomeLoss` + D&A) populated for the two profitable
contractors (BWMN 15.4x, LMB 14.0x) and SLNG (31.3x). It correctly returned `null` for the
loss-makers whose EBITDA series was non-positive (OSS, LTRX, TGEN, HYLN) rather than fabricating a
multiple, the cascade's nonpositive guard fired as designed (`ebitda_nonpositive_ev_ebitda_null`).

---

## 3. BUY decision (full `buy_eligible` reasoning), **honest 0-BUY**

**iter2 BUY rule:** `mos_basis ∈ {fcf_cap, nav}` AND numeric `MoS ≥ 30%` AND `buy_eligible == true`
AND zero kill-flags. `buy_eligible` now also requires `not peak_contamination_flag`.

**Result: 0 BUY.** Every one of the 8 passes the *eligibility* gate but fails the *MoS* gate.

```
ticker  mos_basis  MoS%     buy_eligible  buy_ineligible_reasons   blocks BUY because…
BWMN    fcf_cap    -82.4%   true          []                       MoS < 30% (overvalued vs reverse-DCF)
LMB     fcf_cap    -75.2%   true          []                       MoS < 30%
ESOA    fcf_cap    -96.4%   true          []                       MoS < 30%
OSS     fcf_cap    null     true          []                       MoS null (normalized FCF non-positive)
LTRX    fcf_cap    -87.4%   true          []                       MoS < 30% AND material_weakness (kill=1)
SLNG    fcf_cap    -98.6%   true          []                       MoS < 30%
HYLN    nav        -90.0%   true          []                       NAV MoS < 30%; concept-player (see below)
TGEN    fcf_cap    null     true          []                       MoS null AND material_weakness (kill=1)
```

The signal is unambiguous and exactly what PHILOSOPHY commitment #2 predicts: **in a fully-priced hot
theme, the genuine industrial beneficiaries trade at a premium that eliminates any margin of safety.**
The two real, profitable picks-and-shovels names (BWMN, LMB) are quality businesses growing 15 to 25%
with positive OCF, and the market already pays 14 to 15x EV/EBITDA and prices in ~7% perpetual growth
(reverse-DCF implied). There is no neglect discount left; the alpha was captured before this screen ran.

**Why no catalyst waiver applies:** none of the 8 carries a closed-list catalyst (spinoff 10-12B /
cluster Form-4 buys / court-ordered sale / delisting-forced selling). The insider tape is `net_sell`
on the four most investable names (BWMN, LMB, ESOA, OSS) and `net_buy` only on the weakest four
(LTRX, SLNG, HYLN, TGEN), and even a verified catalyst is frozen to WATCH-not-BUY in iter1/iter2.

---

## 4. V-shape veto stress test (the headline iter2 objective), **PASS, no over-block**

The whole point of this run was to confirm `peak_contamination_flag` does not strangle fast-growers.
**It fired on zero of the 8 deep-dived names**, including the ones with the strongest top-line growth:

| Ticker | rev_slope | contam_ratio | latest_below_avg | latest_NI | peak_contam? | Correct? |
|---|---|---|---|---|---|---|
| HYLN | +1 | 0.557 | False | −$57M | **false** | ✓ latest not below avg → not a rollover |
| TGEN | +1 | 6.559 | True | −$8.2M | **false** | ✓ contam ≫ 0.8 → early-revenue ramp, not contaminated peak |
| ESOA | +1 | 0.391 | True | **+$2.2M** | **false** | ✓ **NI>0 guard saved a profitable contractor** from a false veto |
| OSS | −1 | 0.181 | False | +$5.1M | false | ✓ |
| BWMN/LMB/LTRX/SLNG | +1 | 0.9 to 2.1 | False | mixed | false | ✓ |

**ESOA is the cleanest demonstration of the discipline:** it satisfies *two* of the three V-shape
conditions (`contamination_ratio 0.391 < 0.8` AND `latest_below_avg = True`) but `latest_net_income`
is **positive** (+$2.2M), so the `latest_net_income < 0` guard correctly suppressed the veto. A naïve
contamination-only rule would have wrongly flagged a profitable, growing electrical contractor as a
melting ice cube. **TGEN** is the complementary case: deeply contaminated-looking (`contam 6.56`) but
because that ratio is *above* 0.8 (latest revenue is far above the 5-yr trough average, it's an early
grower, not a post-peak rollover) the veto stays silent and TGEN is instead correctly downgraded to
AVOID by its *material_weakness* kill-flag, not by a misfiring V-shape rule.

`fundamental_decline_flag` also fired on zero names (no name had `rev_slope<0` AND `contam<1.0` AND
`latest_below_avg` simultaneously). Both mechanical vetoes behaved as conservative downgrade-only
guards without a single false positive on this fast-growth-heavy cohort. **Stress objective met.**

---

## 5. Data-quality observations (which guards fired, and were they right)

- **`low_revenue_loss_ratio` (the new P-B label) fired on HYLN**, and only HYLN:
  `latest_net_income=-57.2M vs revenue=3.5M (|NI|/rev=16.5x) → early/pre-revenue resource pattern,
  right entity`. This is exactly the intended replacement for the old `wrong_entity_suspected` misfire:
  HYLN is a *real* company (Hyliion / KARNO generator) burning cash pre-commercialization, so the PM
  reads the correct cause ("early/pre-revenue, large loss vs tiny revenue") rather than a misleading
  "wrong entity." The label stayed advisory: it did **not** flip `buy_eligible` (HYLN was already
  blocked by NAV MoS −90%).
- **`material_weakness` (ICFR) fired on TGEN and LTRX**, both correctly carried `killflag_count: 1`
  and are capped (Dim 1 ≤ 2). TGEN combines MW with a 0.9-yr cash runway; LTRX has MW plus declining
  revenue (−23%). Genuine red flags, not artifacts.
- **`financial_sic` forced-unsuitable: did NOT fire** on any of the 8 (none is a bank/insurer by SIC ,
  Gate 2 already removed the ~40 banks and ~10 insurers that the financial-SIC guard is the backstop for).
  The guard's silence here is correct; its work was done upstream by Gate 2.
- **`peak_contamination_flag` / `fundamental_decline_flag`: did NOT fire** (section 4), the desired result.
- **EBITDA cascade partials:** `ebitda_series_partial_entries` and `ebitda_nonpositive_ev_ebitda_null`
  appeared on the loss-makers (OSS, LTRX, TGEN, HYLN, ESOA, SLNG), the cascade declined to print a
  multiple it could not support rather than fabricating one. Correct conservatism.
- **`lumpy_ocf_normalization_suspect`** flagged on BWMN, ESOA, LTRX (one peak OCF year > 2x the median
  of the others), a useful caution that the negative-MoS readings rest on a noisy FCF base; the
  direction (overvalued) is robust regardless.
- **`debt_stale` (HYLN)** and **`debt_is_total_liabilities_proxy` (TGEN)**, disclosure-vintage / proxy
  notes, surfaced not silently swallowed.

No silent skips. No `deepdive_*_ERROR.json` written (no crashes/rate-limit kills). All 8 valuations
required and received both `--json` and `--ticker`.

---

## 6. Market-intel T2 analyst context (labeled T2, did NOT drive buy_eligible/BUY)

Source: TrendsMCP (Google search / YouTube normalized 0-100 + volume). **Analyst color only.**

- **"data center" search volume: +240% YoY (12M)** but **−22.7% over the trailing 6M.** The theme is
  structurally on fire at the annual scale yet has rolled over from its recent attention peak.
- **"liquid cooling": +128% YoY (Google), −22% over trailing 3M;** YouTube +4% YoY / +26% 3M (mixed).
  Volume-weighted growth +53%. Secular up, near-term cooling.

**Interpretation (PHILOSOPHY #2, hot theme = casino):** the AI-DC-power narrative is exactly at the
late-cycle profile the skill warns about, explosive 12-month interest now fading from peak. This is
the regime where thematic ETFs historically deliver ~−6% risk-adjusted post-launch. It corroborates,
rather than contradicts, the mechanical 0-BUY: the market has already paid up for the obvious names.
**Note:** this signal informed *narrative framing only*; every rating above was produced by the
deterministic MoS / kill-flag / `buy_eligible` layer with the market-intel feed switched off.

---

## 7. Skeptical-PM verdict (usable)

**Actionable conclusion: nothing to buy today; two names worth a watchlist, two to avoid outright.**

- **Pass / no action on all 8.** Zero clear the MoS bar. The theme is fully priced; there is no
  neglect discount to harvest. A PM looking for an AI-DC-power small-cap entry should *wait for a
  drawdown*, not chase here.
- **Watchlist (re-underwrite on a 30 to 40% pullback): BWMN and LMB.** These are the only two real,
  profitable, growing picks-and-shovels businesses in the universe, engineering/MEP firms with
  genuine hyperscale/mission-critical exposure, clean kill-flag sheets, positive OCF. At 14 to 15x
  EV/EBITDA they are priced for ~7% perpetual growth; if the recent attention rollover (T2) drags the
  multiple toward ~9 to 10x EV/EBITDA, the MoS math flips and they become real BUY candidates. **The
  insider `net_sell` tape on both is a caution**, management is taking liquidity into the theme bid.
- **Tier-2 watch (story, not yet quality): ESOA** (cheap on sales at 0.81x but razor-thin $2M NI and
  lumpy OCF), **OSS** (legitimate edge-AI HPC + thermal at 31% growth, but EV/Sales 13.5x and FCF
  non-positive, a momentum story, not a value one), **SLNG** (real LNG-to-DC-power angle but tiny,
  $3M cash, EV/EBITDA 31x), **LTRX** (edge-AI/IoT but revenue −23% and a *material weakness*).
- **Avoid: HYLN and TGEN.** HYLN is the archetypal concept-player, $4M revenue, $1.44B market cap
  (**EV/Sales 410x**), $46M annual cash burn, ~0.4-yr runway; the +130% revenue growth is off a
  near-zero base. TGEN pairs a *material weakness* with a 0.9-yr runway and negative OCF. Neither is
  investable regardless of the theme tailwind.

**Process verdict on the skill (iter2):** the run is clean and the new machinery behaved correctly ,
the V-shape veto added zero false positives on a deliberately fast-growth-heavy cohort (the explicit
stress target), the `low_revenue_loss_ratio` label correctly re-cased HYLN instead of the old
"wrong entity" misfire, the EBITDA cascade refused to fabricate multiples for loss-makers, and the
0-BUY output is the honest, defensible answer for a hot theme. The one rough edge is operational, not
analytical: `finalize_run`'s completeness check counts *every* `band="deep"` row in `candidates_*.json`
and does not natively know about Gate-2 misrecall drops, so the analyst must either re-band the
Gate-2-dropped names (done here: `band` → `misrecall`, raw preserved as
`_raw_candidates_ai_dc_power_preGate2.json`) or pass `--allow-missing`. Worth a future tool change so
Gate-2 resolution is first-class rather than a manual re-band step.

---

### Artifacts (all under `reports/smallcap/2026-06-20_ai-dc-power/`)
`RANKING.md` · `deepdive_verdicts.json` · `report_<TICKER>.md` (×8) ·
`deepdive_<TICKER>_2026-06-20.json` (×8) · `valuation_<TICKER>_2026-06-20.json` (×8) ·
`_gate2_themefit.json` (Gate-2 audit trail) · `candidates_ai_dc_power.json` (post-Gate-2) ·
`_raw_candidates_ai_dc_power_preGate2.json` (pre-Gate-2 raw, 289 rows).
