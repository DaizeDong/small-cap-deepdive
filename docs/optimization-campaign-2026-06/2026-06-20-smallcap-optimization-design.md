# Iteration 1 Design, small-cap-deepdive core-capability optimization

> Derived from a 10-lens independent reflection audit (synthesis: `.git/sdd/reflection/_synthesis.md`).
> Every claim is code/ticker/number-verified. This is the approval artifact + implementation plan for
> iteration 1 of the optimization campaign.

## 1. Diagnosis (the core finding)

**The skill's central edge claim, "delayed information diffusion" (a real fundamental change the market
hasn't priced yet), is operationalized nowhere.** Five lenses converged on the structural fact:

- `MoS_fcf_cap` (valuation.py:428-430) and `reverse_dcf_implied_growth` (valuation.py:401) are **the same
  function** of equity FCF yield `norm_fcf/market_cap`. They are not two confirmations, they are algebraically
  identical. So **19/19 mechanical BUYs price decline by construction** → the engine is a value-trap generator.
  SIGA fired a clean +76% BUY (revenue −31.8% YoY, ~90% BARDA-dependent) while clean growers MGPI/SCVL scored
  below threshold. It lands right or wrong by price-level luck, never by measuring the change.
- The only "change" computation in the repo is a display-only `pct_growth` (deepdive_data.py:171) that gates
  nothing. No between-filings channel, no trajectory term, no price-response data.
- The v0.2.1 guards (extreme-MoS, large-cap, FCF-sustainability) are **advisory strings the BUY trigger never
  blocks on** (valuation.py:594-602 emit; judgment-rubric.md:285 only −10pt confidence, floored at 30%). A
  $5.4B (VSNT) and $6.3B (ARDT) name cleared BUY in a small-cap tool.
- The calibration loop built to catch this is **inert**: 40 verdicts all `abstain`/p=0.50, 0 BUY, 0 catalyst;
  intersection with the 19 validation BUYs = ∅.
- Robustness is **internal-consistency on one corrupted SEC feed** (no second source); concentration detection
  is a literal English substring; ~47% of names have null EV/EBITDA from a single-concept EBIT pull; recall is
  never measured and yfinance-null silently drops 91-100% of some themes before any gate.

## 2. Philosophy split

- **Philosophy-safe (tighten screen / restore trust / measure what was unmeasured / restore recall, ship
  freely):** P1-P14. None can *manufacture* a BUY; they remove false positives, make guards bite, or make
  "honest zero" trustworthy. P6 (deterministic, downgrade-only trajectory veto) is the philosophy-faithful way
  to operationalize the conservative half of the thesis.
- **Philosophy-gated (needs explicit human approval):** P15/P16/P17 (between-filings alt-data, price-return
  divergence, ownership/short-interest), they import the T2/T3 signals T1-purism exists to suppress; and the
  catalyst MoS-waiver (existing but unverified/uncalibrated). → §5 decisions.

## 3. Iteration-1 program (philosophy-safe, ships regardless of §5 answers)

Sequenced by dependency; effort S/M/L; all verified against code.

**Tier 1, trust spine (make v0.2.1 guards bite + decision-ready output + honest zero):**
- **P2** (S) Fix the dead `elif fcf_is_proxy` (valuation.py:541-552) so every OCF-proxy FCF is flagged + penalized (~18% of universe currently silent).
- **P3** (M) Concentration → magnitude-based BUY-blocking kill-flag from XBRL `RevenueFromContractWithCustomer` segment members (>60% single-program/>40% single-customer = kill-flag), replacing the substring (deepdive_data.py:659). Catches SIGA.
- **P1** (S) Promote guards (extreme-MoS / large-cap / FCF-sustainability / financial-SIC / debt-truncation/wrong-entity / concentration) into one mechanical `buy_eligible` boolean the BUY trigger ANDs in. Consumes P2,P3.
- **P5** (M) Decouple mktcap from yfinance: fallback chain (SEC companyfacts×price → free APIs) + `band=unknown` flow-through instead of drop; resolve ceiling in cheap_pass. Prerequisite for trusting any 0-BUY.
- **P4** (M) `finalize_run.py`: deterministic report scaffolder (with a data-quality TRUST BANNER under each rating) + verdict emitter (auto-feeds track_forward) + deterministic RANKING rebuild + rank.py regex fix (5/11 failed) + UTF-8 read helper.

**Tier 2, conservative thesis fix + recall:**
- **P6+P10** (M) Deterministic fundamental-trajectory + `contamination = latest/5yr-avg` veto: downgrade-only BUY→WATCH when trajectory materially negative AND latest below its own trailing average (SIGA contamination 0.68). Implements the specced-but-uncoded lumpy-OCF guard. **Kills the melting-ice-cube false positive at the fundamentals.** (Requires rubric:222 carve-out, see §4.)
- **P9** (S) EBIT concept cascade (pretax/continuing-ops, `ebit_source`-tagged) to recover EV/EBITDA on the ~47% null.
- **P7** (L) Second-source sanity band (free FMP/yahoo MCP) on debt/revenue/shares, survivors only, repair-or-confirm, never the primary number; catches externally-wrong-but-internally-plausible (HCI/AL).
- **P8** (L) SIC-seeded reverse-recall UNIONed with FTS + `recall@gold` metric (vs the validation's hand-built true-member lists) + FTS pagination. Depends on P5.

**Tier 3, calibration + honest docs + forensics spine:**
- **P12** (M) Fix calibration: confidence-as-probability by direction + dividend-adjusted total return + de-risk-native metrics (blowup-avoidance/downside-capture) + backfill the 19 validation BUYs as `adjudication=data_false_positive`. Depends on P4.
- **P13** (S) Stop the "weighted 7-dim composite" claim (no weights exist in repo): either assign explicit weights overweighting change-detection, or retire it and state rating = f(MoS, kill-flags, ceilings).
- **P14** (L) Management/capital-allocation/earnings-quality spine from XBRL (Sloan accruals, diluted-share CAGR, SBC%, NI−FCF gap) with hard-ceiling triggers, moves the highest-halo dimensions onto T1 ground.

**Catalyst integrity:**
- **P11** (M-L) Verified mechanism + `{mechanism_verified, trigger_date, days_remaining}` + complete the whitelist + small-cap ceiling on events + pagination + forward-track catalyst verdicts by category. **MoS-waiver frozen** (catalyst → WATCH) pending §5-Q3.

## 4. Methodology SSOT edits (flagged, these touch the single source of truth)
- **rubric:222 carve-out**: currently bans vetoing a 30%+ MoS on "cyclical-turn-not-realized" grounds. P6 needs a narrow MECHANICAL carve-out (decline magnitude + latest-below-own-average + contamination<1), explicitly NOT the qualitative forward judgment rubric:222 bans.
- **data-sources.md:90 correction**: the "alt-data = paid-vendors-only" claim is stale (free TrendsMCP/GDELT exist). Correcting the doc is philosophy-neutral; *acting* on it is §5-Q2.

## 5. Decisions for human approval (the campaign's one gate)
- **Q1, doc/code split**: operationalize the thesis (approve conservative P6 now; decide expansive separately) vs retract the diffusion claim and describe the skill honestly as a static value+de-risk screen.
- **Q2, between-filings data (P15/P16/P17)**: build as a quarantined diagnostic side-channel (strict firewall: corroboration-only, never originates/up-weights a BUY, track-forward-gated until its own Brier exists) vs keep the data layer T1-only.
- **Q3, catalyst MoS-waiver**: freeze (catalyst→WATCH until mechanism-verified + per-category Brier) vs keep.

## 6. Test plan (campaign step 4, after implementation)
- **Old-theme reruns**: re-run the validation-v0.2.0 themes under the new code; produce a before/after diff (which BUYs are now correctly downgraded, which names newly recalled, MoS deltas, guard-bite count).
- **New diverse themes**: brainstorm a diverse set (cutting-edge hotspots + obscure/tricky domains); full skill invocation using market-intel tools for information gathering; parallel subagent evaluation; one independent report per theme.
- **Acceptance / real-world-usable bar**: (a) zero data-artifact BUYs survive; (b) every deep-band candidate has a deterministic report + verdict; (c) recall@gold measured and floored on SIC-backed themes; (d) trajectory veto correctly downgrades known value-traps (SIGA-like) while sparing genuine troughs; (e) a skeptical-PM read of ≥3 reports finds them decision-ready and trustworthy.

## 7. Sequencing
P2→P3→P1 ; P5 ; P4 → (P6+P10) , P9 , P7 , P8 → P12 , P13 , P14 → P11(frozen) → [§5 gated items if approved] → TEST.
