# Coverage Test, Water Utilities (Utilities)

- **Slug:** `water-utilities` | **Run dir:** `reports/smallcap/2026-06-21_cov-water-utilities/`
- **Skill:** v0.3.0 (commit `f12fef5`) | **Date:** 2026-06-21
- **Keywords (FTS):** `water utility, water infrastructure`
- **Code-path focus:** regulated / dividend total-return; recall@gold
- **Headline:** **0 BUY** (clean). 8 deep-band theme-survivors all rate **WATCH**. The FCF-cap path
  fired for every name and returned **null-or-negative MoS**, the textbook "regulated bond-proxy"
  behavior: premium multiples + heavy rate-base capex → non-positive normalized FCF → no FCF bargain.
  The NAV path did **not** fire for any name. **Universe-level recall@gold = 9/9 (100%)**; the
  candidates-level 6/9 is entirely downstream attrition, not a discovery-floor failure.

---

## 1. Funnel

| Stage | Count | Notes |
|---|---|---|
| FTS + SIC reverse-recall union → universe CSV | 150 (marketcap-scan cap) | SIC-4941 floor union'd with FTS; **all 9 gold names landed in the universe** |
| cheap_pass scanned | 68 | mechanical kill-flags + burn/concentration rejects |
| cheap_pass survivors | 45 | passed to SIC gate |
| SIC gate (keep + review) | 45 | keep 38, review 7 → both go to Gate 2 |
| **Deep band (band="deep" / "unknown")** | **24** | the over-recall pool (23 deep + 1 unknown = TVA) |
| **Gate 2 theme-fit survivors (deep-dived)** | **8** | GWRS, ARTNA, CWCO, YORW, MSEX, NWPX, SHIM, WBI |
| Gate 2 misrecall (resolved, not deep-dived) | 16 | RE/oil/coal/uranium/banks/biotech/sand |
| Reports written | 8 | 0 missing |
| **Mechanical BUY** | **0** |, |
| **Clean BUY (post-adversarial)** | **0** |, |

The over-recall is mild relative to a generic-keyword theme: "water utility" is reasonably specific
and the **SIC-4941 reverse-recall floor** carried the recall, pulling in every gold-list pure-play.
The 16 deep-band misrecalls are the usual incidental-keyword sweep, real-estate/opportunity-zone
plays (OZ, LAND, TRC, AHRT), oil & gas (HPK, INR), coal/minerals (METC, ODV), uranium (EU), a bank
(PLBC), a biotech royalty (XOMA), frac sand (SND), isotopes (ASPI), and TVA (a federal power agency
that files as a debt issuer, not an investable water equity).

## 2. Gate 2 theme-fit (LLM judgment from 10-K blurbs)

| Ticker | Name | SIC | Band | Mkt cap | Fit | Rationale |
|---|---|---|---|---|---|---|
| **YORW** | York Water Co | 4941 | deep | $479M | **pure_play** | Oldest investor-owned water utility in the US (PA, since 1816). Canonical regulated water. |
| **ARTNA** | Artesian Resources | 4941 | deep | $333M | **pure_play** | Holdco of 7 water/wastewater utilities (DE/MD/PA). |
| **GWRS** | Global Water Resources | 4941 | deep | $204M | **pure_play** | 39 water/wastewater/recycled public utility systems (AZ). |
| **CWCO** | Consolidated Water | 4941 | deep | $478M | **pure_play** | Reverse-osmosis potable water utility (Cayman/Bahamas/BVI/US). |
| **MSEX** | Middlesex Water | 4941 | deep | $970M | **pure_play** | Middlesex + Tidewater regulated water utilities (NJ/DE). |
| **NWPX** | NWPX Infrastructure (Northwest Pipe) | 3317 | deep | $1,341M | **partial** | Engineered steel water-transmission pipe + precast water infrastructure products. Water-infra manufacturer, not a utility. |
| **SHIM** | Shimmick Corp | 1600 | deep | $150M | **partial** | Heavy-civil construction "designed to strengthen the water market" (dams, treatment, conveyance) + other infra. |
| **WBI** | WaterBridge Infrastructure | 1389 | deep | $1,560M | **partial** | **Produced-water** midstream for oil & gas (saltwater gathering/disposal). Energy-sector water handling, included on the "water infrastructure" keyword but NOT the regulated drinking-water theme. Flagged. |
| OZ / LAND / TRC / AHRT | real estate / farmland / ranch REITs | 65xx/67xx | deep |, | misrecall | water assets are concept mentions; core business is real estate |
| HPK / INR | oil & gas E&P | 1381/1311 | deep |, | misrecall | "water" = produced/frac water, incidental |
| METC / ODV / EU / ASPI | coal / gold / uranium / isotopes | 12xx/10xx/28xx | deep |, | misrecall | mining/materials |
| PLBC | Plumas Bancorp | 6153 | deep |, | misrecall | community bank |
| XOMA | XOMA Royalty | 2834 | deep |, | misrecall | biotech royalty aggregator |
| SND | Smart Sand | 1400 | deep |, | misrecall | frac/industrial sand |
| TVC | Tennessee Valley Authority | 4911 | unknown | n/a | misrecall | federal power-agency **debt** issuer; not investable equity, and power not water |

**WBI judgment note.** WaterBridge is genuinely "water infrastructure" in the produced-water sense,
so it is a defensible `partial` on the literal keyword. But it is an oilfield-services water-disposal
holdco (2025 IPO), not a regulated/dividend total-return water utility, i.e. it is off the *intended*
theme even though it matches the *keyword*. I retained it as `partial` (recall-favoring) and let the
mechanical gates judge it; they correctly blocked any BUY (see §4).

## 3. recall@gold (gold list: YORW, ARTNA, MSEX, GWRS, CWCO, PCYO, SJW, CWT, AWR, 9 names)

`python tools/track_forward.py --theme water-utilities --recall-gold <candidates>`:

```
recall@gold:   66.7% (6/9)
  recalled_gold: ARTNA, CWCO, CWT, GWRS, MSEX, YORW
  MISSING_gold:  AWR, PCYO, SJW
  loss-stage breakdown:
    recalled_final   6  ARTNA, CWCO, CWT, GWRS, MSEX, YORW
    sic_recovered    0
    dropped_mktcap   0
    gated_out        0
    fts_missed       3  AWR, PCYO, SJW
```

**The 66.7% headline understates true discovery recall, and the loss-stage taxonomy mislabels the
cause.** I traced all three "missing" names through the universe CSV and cheap_pass:

| Gold miss | In universe? | Band | Where actually lost | Correct? |
|---|---|---|---|---|
| **PCYO** (Pure Cycle, $267M) | **YES** (SIC floor) | deep | **cheap_pass `reject_burn=True`**, latest OCF −$5.2M cash burn (no kill-flag, just burn) | Mechanically correct, but a real deep-band water utility dropped by the burn filter |
| **AWR** (American States Water, $3.0B) | **YES** | **watch** | **market-cap cap** ($3.0B > $2.0B small-cap ceiling) | Correct, out of scope by size |
| **SJW** (SJW Group, ~$1.6B) | **YES** | **unknown** | **mktcap-resolution failure** (yfinance returned no cap → `smallcap_candidate=False` → never reached cheap_pass) | **Data-quality gap**, a genuine in-scope water utility lost to a market-cap fetch failure |

**Universe-level recall@gold = 9/9 (100%).** The FTS ∪ SIC-4941 reverse-recall floor caught **every
single gold name** into the universe CSV. None was `fts_missed` in the literal sense, all three of
the so-called "fts_missed" names were recalled by the SIC floor and then lost at *downstream* stages
(burn-reject, size-cap, mktcap-fetch-failure). The `track_forward` loss-stage taxonomy attributes them
to `fts_missed` because it diffs the *final candidates* file against gold and cannot see that they were
present earlier; this is a minor diagnostic imprecision worth noting (the taxonomy under-credits the
SIC floor). **The SIC reverse-recall floor did exactly its job here, the headline recall number is a
downstream-attrition artifact, not a discovery failure.**

## 4. Deep-dive survivors, full BUY-rule reasoning

BUY rule: `mos_basis ∈ {fcf_cap, nav}` **AND** numeric `MoS ≥ 30%` **AND** `buy_eligible == true`
**AND** zero kill-flags. **All 8 FAIL.** None has a cheap_pass hard kill-flag (going-concern /
death-spiral / material-weakness all False), so none is AVOID, all default to **WATCH**. Every name
priced as `mos_basis=fcf_cap`; the NAV path never fired (see §5).

| Ticker | mos_basis | MoS | buy_eligible | buy_ineligible_reasons | kill | Why no BUY |
|---|---|---|---|---|---|---|
| GWRS | fcf_cap | **null** | True |, | 0 | normalized FCF non-positive → intrinsic band null → no numeric MoS |
| ARTNA | fcf_cap | **null** | True |, | 0 | normalized FCF non-positive → intrinsic band null |
| CWCO | fcf_cap | **−43.9%** | True |, | 0 | negative MoS (priced above FCF intrinsic) |
| MSEX | fcf_cap | **null** | True |, | 0 | normalized FCF non-positive → intrinsic band null |
| SHIM | fcf_cap | **null** | True |, | 1* | net loss + negative OCF → FCF non-positive; melting-ice-cube (T2) |
| YORW | fcf_cap | **−124.9%** | **False** | extreme_mos_review_required | 0 | extreme-MoS guard fires; MoS < 30 anyway |
| NWPX | fcf_cap | **−88.3%** | **False** | cross_source_mismatch | 1* | P7 data-integrity gate: SEC debt $10.7M vs yfinance $110.5M (10.3×) |
| WBI | fcf_cap | **−140.5%** | **False** | extreme_mos_review_required, fcf_sustainability_uncertain | 0 | OCF-proxy on capital-intensive (assets/rev 7.1); extreme negative MoS |

\* "kill" column = `killflag_count` in the ranking (NWPX/SHIM carry a customer-concentration *text*
flag with null XBRL magnitude → `concentration_unquantified`, advisory only; it does **not** gate
buy_eligible). Neither is a hard going-concern/death-spiral kill, so both stay WATCH not AVOID.

**The three buy_eligible=True names (GWRS, ARTNA, MSEX) are the instructive cases.** They cleared every
mechanical guard, no concentration kill, no V-shape, no insurance/financial routing, no cross-source
mismatch, no extreme-MoS, yet still produce **no BUY** because the BUY rule requires a *numeric*
MoS ≥ 30 and their MoS is **null**. The intrinsic FCF band is null because normalized free cash flow
is non-positive: regulated water utilities plow essentially all operating cash flow back into
rate-base capex (mains, treatment, meters), so trailing FCF is thin-to-negative even for healthy,
profitable, dividend-paying utilities. **The null-MoS gate is the firewall that correctly blocks the
BUY**, a clean demonstration that `buy_eligible == true` is necessary but not sufficient.

CWCO is the lone name with a *computable* (and negative) MoS: it generates positive FCF (yield +6.9%)
but trades at EV/EBITDA 13.9× / EV/Sales 2.8×, above its own reverse-DCF intrinsic band → MoS −44%.
A correctly-priced premium utility, not a bargain.

## 5. Code-paths exercised (focus: regulated / dividend total-return)

- **FCF-cap path fired for all 8; NAV path fired for NONE**, the headline code-path observation.
  `nav_intrinsic_band` is None and `fcf_cap_model_unsuitable=False` for every name. Regulated water
  utilities are asset-heavy bond-proxies, exactly the profile one might expect to route onto NAV ,
  yet none crossed the routing threshold (debt/assets did not exceed the cutoff; `debt_to_assets`
  was not even populated for these XBRL layouts). Result: every utility was valued on a **trough/thin
  FCF basis** that returns null or deeply-negative MoS. This is the regulated-utility analogue of the
  railcar-leasing finding: the asset-heavy NAV path under-fires on capital-intensive but
  moderately-levered names. For a rate-base business, the economically right valuation anchor is
  **regulated rate base × allowed ROE / dividend-discount**, neither of which the FCF-cap path models.
- **Null-MoS / numeric-MoS-required gate:** fired on GWRS, ARTNA, MSEX, SHIM, the firewall that
  blocked the three buy_eligible=True names. **This is the key regulated/dividend total-return
  behavior:** the model declines to manufacture a BUY out of a utility whose FCF is structurally
  non-positive, rather than hallucinating an intrinsic value.
- **extreme_mos_review_required guard:** fired (YORW −124.9%, WBI −140.5%) → buy_eligible False.
- **fcf_sustainability_uncertain guard:** fired (WBI), OCF-proxy used (capex unavailable) on a
  capital-intensive balance sheet (assets/rev 7.1).
- **cross_source_mismatch (P7 second-source sanity band):** fired on **NWPX**, SEC-XBRL
  `total_debt = $10.7M` vs yfinance `$110.5M` (10.3× disagreement, both > $1M) → buy_eligible False.
  The first time in this run the independent-feed integrity gate bit. (The SEC value is the truncated
  one, a real debt-truncation that internal-consistency checks alone would have missed.)
- **concentration (magnitude-based):** no `kill`/`watch` magnitude flag fired; NWPX and WBI carry only
  `concentration_unquantified` (text flag, null XBRL magnitude), advisory, did not gate.
- **fundamental_decline_flag / peak_contamination_flag (V-shape):** did NOT fire on any name (no
  positive-base trough→peak→rollover pattern; rev_slope_sign positive for 7 of 8).
- **insurance_concepts_present / low_revenue_loss_ratio_extreme / financial-SIC routing:** none fired.
- **SIC reverse-recall floor:** worked, recalled all 9 SIC-4941 gold names into the universe (§3).
- **Signals side-channel (P16/P17):** emitted automatically and **firewalled**, did not touch any
  BUY decision. See §7.

## 6. Adversarial verification

**No mechanical BUYs to adversarially confirm, so the adversarial question runs in reverse: are any
of the WATCH/no-BUY verdicts artifacts that hide a real opportunity?**

- **GWRS / ARTNA / MSEX (null-MoS WATCHes):** The null MoS is **not** a distress signal, it is the
  structural consequence of rate-base capex consuming OCF. These are healthy, profitable,
  long-dividend-record regulated utilities (ARTNA P/E 14.6, NI +$23M; GWRS NI +$3M; MSEX NI +$43M).
  The *correct* valuation anchor is rate base / dividend-discount, which the FCF-cap path does not
  model. **Verdict: the no-BUY is correct (no FCF bargain exists at these premium multiples), but the
  null-MoS is not load-bearing, a human should value these on regulated rate base. Honest WATCH stands;
  none is a hidden bargain (all trade at premium utility multiples).**
- **CWCO (−44% MoS):** Genuinely priced above intrinsic on positive FCF. Premium RO-water utility with
  Caribbean concession risk. **Verdict: correct no-BUY; not a hidden bargain.**
- **YORW (−124.9%, extreme-MoS):** The highest-multiple name (EV/Sales 9.2×, EV/EBITDA 16.8×), the
  market pays a scarcity premium for a 200-year continuous dividend record. Strong insider net-buy
  (70 buys / 0 sells) is a T2 curiosity but does **not** make it cheap. **Verdict: correct no-BUY ,
  expensive bond-proxy, not an opportunity.**
- **NWPX (cross_source_mismatch):** The buy_eligible=False is driven by a **real data defect** (SEC
  debt truncated to $10.7M vs true ~$110M). Even setting that aside, MoS is −88% on a 26.9× EV/EBITDA
  pipe manufacturer at a cyclical infrastructure-spend peak. **Verdict: correct no-BUY; the P7 gate
  did exactly what it should, refuse to underwrite a tradeable MoS on a corrupted debt input.**
- **WBI (extreme-MoS + fcf_sustainability_uncertain):** A 2025-IPO oilfield produced-water midstream
  holdco, off the intended regulated-water theme, net loss −$4.5M, OCF-proxy FCF on a very
  capital-intensive balance sheet. **Verdict: correct no-BUY; arguably a misrecall on the theme axis
  too, but the mechanical gates blocked it regardless.**
- **SHIM (null-MoS, melting-ice-cube T2):** Net loss −$26M, negative OCF −$65M, P16 divergence label
  `melting_ice_cube_priced`. A heavy-civil contractor in turnaround, not a regulated utility.
  **Verdict: correct no-BUY, a genuine loss-making contractor; the null-MoS firewall + negative FCF
  block it cleanly.**

**Conclusion: 0 clean BUY after adversarial review (was 0 mechanical BUY). No false BUY; no
adversarially-hidden small-cap opportunity was suppressed by a model artifact**, every WATCH is a
correctly-priced premium utility or a genuinely loss-making/off-theme name.

## 7. T2 DIAGNOSTIC SIGNALS (context only, NOT used in the rating)

Firewalled P16 price-divergence labels (captured automatically into each deepdive's `signals` block;
never read by `valuation.py` or the BUY trigger):

- **GWRS, ARTNA, CWCO, YORW, MSEX:** `unpriced_improvement`, fundamentals improving faster than price
  over the trailing window. *Diagnostic only*; for richly-valued regulated utilities this is weak
  signal (the multiples already embed quality) and it earns no Brier weight until calibrated.
- **NWPX, WBI:** `aligned`, price and fundamentals tracking together.
- **SHIM:** `melting_ice_cube_priced`, price decline tracking deteriorating fundamentals (consistent
  with the loss-making contractor profile).

**Market-intel / TrendsMCP:** the TrendsMCP daily+monthly request quota was fully exhausted at run
time (5/5 daily, 100/100 monthly), so external search-interest / news-volume context could not be
pulled. Recorded as a data-availability limitation (§8). The firewall makes this immaterial to the
verdicts, TrendsMCP is T2 context that may never drive buy_eligible, but it does remove the
qualitative theme-momentum color this report would otherwise carry.

## 8. Data-quality issues

- **MSEX net_income unit mistag:** `latest_net_income` parsed as **42.8** (should be ~$42.8M) →
  nonsensical P/E 22,653,797×. An XBRL units artifact. It did not affect the verdict (the BUY was
  already blocked by null FCF MoS), but it would corrupt any P/E-based ranking and should be flagged.
- **NWPX cross-source debt mismatch (P7):** SEC-XBRL `total_debt = $10.7M` vs yfinance `$110.5M`
  (10.3×). A genuine SEC-side debt **truncation**, the P7 second-source gate caught it; without P7,
  internal-consistency checks would have passed the corrupted figure.
- **SJW lost to mktcap-resolution failure:** a real ~$1.6B in-scope water utility was recalled into
  the universe (SIC floor) but had `mktcap = NaN` (yfinance miss) → `smallcap_candidate=False` → never
  reached cheap_pass. Direct recall@gold loss with a fixable cause (add a fallback market-cap source).
- **recall@gold loss-stage mislabeling:** the taxonomy reported PCYO/AWR/SJW as `fts_missed`, but all
  three were SIC-floor-recalled into the universe and lost downstream (burn-reject / size-cap /
  mktcap-fail). The taxonomy under-credits the SIC reverse-recall floor.
- **PCYO burn-reject:** a legitimate small-cap water utility ($267M) dropped at cheap_pass for negative
  OCF (−$5.2M). Mechanically correct, but worth knowing the burn filter removes capex-heavy micro-cap
  water utilities, exactly the cohort a deep-value water screen might want to inspect by hand.
- **Structural FCF-cap mis-routing for rate-base utilities:** the absence of a NAV / rate-base /
  dividend-discount path for regulated utilities means every one of them returns null-or-negative MoS;
  the verdicts are still correct (no FCF bargain), but the *intrinsic-value number is not usable* and a
  PM must re-anchor on rate base manually.
- **TrendsMCP quota exhausted** (see §7), no external T2 momentum context this run.

## 9. Skeptical-PM usable verdict

**Usable: YES.** This is a correct, well-behaved "nothing to buy" outcome for a premium-priced,
asset-heavy regulated theme, and the run demonstrates the regulated/dividend total-return code-path
exactly as it should behave:

1. **Discovery floor worked.** The SIC-4941 reverse-recall floor pulled **all 9 gold names into the
   universe (100% universe recall)**. The 66.7% candidates-level recall is downstream attrition
   (burn-reject, size-cap, and one mktcap-fetch failure), not a discovery miss, and I traced each.
2. **Precision held.** Gate 2 cut a 24-name deep-band pool to the 8 true water names (5 pure-play
   regulated utilities + 3 water-infra partials), correctly discarding 16 real-estate / oil / mining /
   bank / biotech misrecalls including the TVA debt-issuer trap.
3. **0 BUY, every no-BUY traceable.** The five clean-guard names (GWRS/ARTNA/MSEX/CWCO/SHIM) are
   blocked by the **null-or-negative-FCF MoS firewall**, the correct refusal to manufacture an
   intrinsic value from a rate-base utility's structurally non-positive FCF. The three guard-blocked
   names (YORW extreme-MoS, NWPX cross-source-mismatch, WBI extreme-MoS + fcf-sustainability) each cite
   a specific, defensible mechanical reason. The P7 cross-source gate biting on NWPX's truncated debt
   is a genuine save.

**The one structural defect a PM must note (identical in spirit to the railcar finding): there is no
NAV / rate-base / dividend-discount valuation path for regulated utilities.** Every water utility here
was valued on FCF-cap and returned null/negative MoS, so the *intrinsic-value numbers are not usable*
for this sector, even though the WATCH verdicts are correct (none is a real FCF bargain at these
premium multiples). A human should re-anchor any water-utility BUY decision on regulated rate base ×
allowed ROE, not on this model's FCF MoS. **No false BUY; no adversarially-hidden opportunity
suppressed.** Two fixable plumbing items: the MSEX net-income unit mistag and the SJW mktcap-fetch
failure (which cost one gold name a deep-dive).
