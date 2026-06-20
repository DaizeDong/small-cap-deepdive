# Cognitive Priors — Invariant D

> World-view commitments that govern how the skill is used and what it can honestly claim to do.
> These are not aspirational statements — they are hard constraints derived from empirical evidence and two real production runs.
> Anyone using this skill to generate investment ideas must internalize these before interpreting any output.

---

## The Five World-View Commitments

### 1. Neglected Does Not Equal Undervalued

A company that receives no analyst coverage and no retail investor attention is neglected. It is not, for that reason, undervalued.

The efficient market for small-caps and micro-caps prices available information efficiently even at low coverage. What creates pricing inefficiency is delayed information diffusion — a meaningful improvement in fundamentals that the market has not yet priced. Finding neglected companies is the starting point; proving the market has not yet priced a fundamental change is the hard work.

**Practical implication:** A company that screens well on neglect (low coverage, no media mentions, small market cap) has cleared a necessary but not sufficient condition. The report must identify a specific information gap — a financial improvement, a catalyst, a dislocation — not just assert that the company is "under the radar."

**Source:** Barber & Odean (2008) — retail investors systematically buy attention-grabbing stocks, pushing prices above fundamental value. The mechanism works in reverse: neglect is priced but neglect alone is not a return signal.

### 2. Hot Themes Are Not Good Hunting Grounds

A popular investment theme is, by definition, widely known. Stocks connected to popular themes have already been re-rated by investors who discovered the theme first. The alpha, if any existed, has largely been captured.

**The empirical record:** Ben-David, Franzoni et al. (2023) — thematic ETFs launched at the peak of theme popularity showed risk-adjusted annual returns of approximately -6% in the 5 years post-launch. The information that drives the theme narrative is already priced.

**What this means for theme selection:** The best themes for this skill are either:
(a) Obscure industrial niches with no retail attention (railcar retrofits, specialty chemicals, industrial refractory) — genuine neglect; or
(b) Large, well-known themes where the skill's value is separating the few true beneficiaries from the many concept-players.

A good theme is also **non-financial** (financials are SIC-excluded by Gate 1) and
**US-10-K-native** (foreign 20-F filers are invisible to discovery — see
`discovery-engine.md` Coverage Caveat). Precise, low-collision keywords matter too:
prefer specific terms (`cremation`, `aircraft engine`) over generic ones that sweep
unrelated industries.

**What this does not mean:** Avoid all "hot" themes entirely. A hot theme can still contain mis-priced companies — especially when the theme narrative has swept in companies with zero actual revenue from the theme. The skill's precision gate (see `discovery-engine.md`) is designed to find those.

### 3. Real Theme Members Are Often Fairly-Priced Cyclicals

After the two-stage precision gate, the companies that remain as true theme members are frequently small industrial, specialty chemical, or niche services companies that have always operated in this space. They did not get re-rated because the market already knew them. Their valuations reflect their historical cycle, not the theme premium.

This is a feature, not a bug. A railcar manufacturing company trading at historical-cycle valuations with legitimate exposure to new tank car regulations is a better risk/reward than a startup that mentioned "sustainable rail logistics" in its press release.

**Implication for scoring:** A company that is a true pure-play (Gate 2 = `pure_play`) but is trading at fair cyclical value should still be analyzed rigorously. Fair value on fundamentals + real theme exposure = the sweet spot. Do not penalize it for lacking a "story premium."

### 4. Agent Edge Is Mechanical Discipline, Not Narrative Synthesis

The skill's comparative advantage over unaided human analysis is:
- Systematic coverage of more companies than a human can read in the time budget
- Consistent application of the kill-flag rules, disclosure disciplines, and scoring rubric across all companies
- Elimination of human attention bias (humans focus on companies they have heard of)

The skill has **no** comparative advantage in:
- Judging whether a founding team is exceptional
- Predicting whether a product narrative will resonate with the market
- Synthesizing qualitative impressions into a forward-looking story

Any part of the output that relies on narrative synthesis should be treated with suspicion. The parts that rely on systematic application of T1 data and mechanical rules are the parts worth trusting.

**Evidence:** Adversarial stress testing during development established: "Agent's advantage is scaling structured quality signal across the full market, maintaining consistent discipline — not qualitative synthesis of people and narratives. The latter is the heaviest halo-bias zone."

### 5. Output Is a De-Risk Scanner, Not a Stock Picker

This skill does not identify the next ten-bagger. It identifies which companies in a theme have the fewest structural red flags and the most credible fundamental cases — relative to each other.

A batch ranking that produces "0 BUY, 3 WATCH, 7 AVOID" is not a failed run. It is the honest result when the theme quality is low. The absence of BUY candidates on bad batches is the strongest proof that the skill is not in the business of generating bullish stories.

**Empirical regularity (3 real runs, ~40 deep dives):** theme quality correlates with
*survivor cleanliness*, not with buy count. A hot, crowded theme (AI-agent) yielded many
AVOIDs (going-concern / death-spiral garbage). Well-chosen boring, neglected themes
(industrials, deathcare, ag, uniforms, aerospace aftermarket) yielded ~0 AVOIDs and mostly
WATCH — clean, fairly-priced cyclicals. Across all three runs the BUY count was **0**.
The first-order takeaway: better theme selection buys you a *cleaner* candidate set (less
garbage to wade through), not more buys.

**The run-3 calibration gap has been closed (Phase 3).** A post-run audit found that while
~70-75% of WATCH ratings were genuinely correct (efficiently priced cyclicals, no margin of
safety), the rubric had **no symmetric BUY trigger** — only downward hard-ceilings — and the
"cyclical turn not yet realized in T1" reasoning became a perpetual veto. Phase 3 adds the
symmetric BUY trigger: `margin_of_safety_pct ≥ 30%` (FCF-cap basis) or `nav_margin_of_safety_pct ≥ 30%`
(NAV basis), both with zero kill-flags and no T3 load-bearing thesis. A catalyst modifier
(T1-evidenced forced-trading event with dated trigger) can also reach BUY at MoS < 30%.
The perpetual-veto ("cyclical turn not yet realized") is now explicitly prohibited when
static MoS ≥ 30% — normalized FCF already accounts for cycle conservatism.

**However, buys remain rare and market efficiency means most names are still WATCH.** The
BUY trigger is correctly conservative: it requires the conservative intrinsic value band
(12% cap rate) to exceed market cap by ≥30% — a high bar. Most clean, fairly-priced
cyclicals will still not clear it. "0 BUY" on a given run may still be the honest result;
it is no longer automatically a calibration artifact, but it is also not evidence the trigger
is broken. Do not expect the BUY rate to jump materially — the goal was to eliminate false
negatives on genuinely cheap names, not to manufacture buys on fairly-priced ones.

**Where buys actually live (if anywhere):** the same audit found theme/industry hunting is
efficiently priced in the >$200M band; the mispricing that small capital can still capture is
overwhelmingly *event-driven / forced-trading* (spinoffs — Form 10-12B; cluster open-market
insider buys — Form 4), not static "cheap neglected value." Pivoting the discovery axis from
theme to event is a candidate next direction (ROADMAP), with the honest caveat that these
anomalies are decaying and liquidity eats much of the gross edge — so 0 BUY may still be the
correct output even after the pivot.

---

## Calibration Loop

Whether the conservatism in prior runs is *correct* (market efficient) or *miscalibrated* (rubric
too strict) cannot be resolved by argument — only by forward tracking. The calibration feedback
loop lives in `reference/track-forward.md`. See `tools/track_forward.py` for the implementation.
Do not tune this rubric based on narrative inspection — wait for scored verdicts.

**Practical implication:** Do not ask the skill to MANUFACTURE a BUY rating — BUY fires only when the mechanical margin-of-safety conditions are met. Ask it to produce the most disciplined ranking available from the data. Use the ranking as a triage for further human review, not as a trading signal.

---

## The Deep-Dive Falsifiability Problem

A deep-dive of 20–50 companies over a 3–5 year holding period cannot be back-tested. There is no historical analog. You cannot distinguish skill from luck statistically at this sample size.

**This creates an obligation:** Track forward. Every verdict issued by this skill must be logged with a date, a specific trigger (from Section 7 of the output template), and a check-in date. When the check-in arrives, update the record. Over time, a calibration record emerges.

**What track-forward reveals:** If a company rated WATCH reaches the trigger condition for BUY upgrade and the subsequent returns are systematically positive, the skill's trigger calibration is working. If they are random, the verdicts are noise. Without track-forward records, there is no way to know.

**The honest position:** Until a substantial track-forward record exists (minimum 30–50 verdicts across multiple market cycles), treat all ratings as structured hypotheses, not alpha signals.

---

## Base-Rate Prior Table

These are empirical base rates to use when anchoring Section 0 of the deep-dive output template. Source each to the reference when stating it in a report.

| Reference class | Zero / wipeout rate | Mediocre outcome rate | Reasonable return rate | Source / Notes |
|---|---|---|---|---|
| Micro-cap universe (all, 5-yr) | ~40–50% fail, delist, or go to zero | ~35% flat / minimal return | ~15–25% meaningful return | Shumway (1997) + Kailash 35-yr study; delisting bias understates failure rate in standard databases |
| Lowest-quality-quintile small-cap growth | ~70% underperform Russell 2000 over 5 years | — | — | Kailash Capital research on small-cap quality |
| De-SPAC companies (2–3 yr post-merger) | Median return: -29% from SPAC price | — | — | Klausner, Ohlrogge & Ruan (2022) |
| Going-concern finding → bankruptcy correlation | ~85% of companies with going-concern audit opinion file for bankruptcy within 3 years | — | — | Standard audit research |
| Companies with ≥3 kill-flags (cluster) | Near-certain value destruction | — | — | Empirical from real run: BNAI, CXApp, Fusemachines all had ≥3 kill-flags and subsequently collapsed |
| Pre-revenue micro-cap with AI/theme positioning (2025–2026) | High; exact rate unclear but theme ETF data suggests significant premium has been paid by retail | — | — | Ben-David et al. (2023) thematic ETF study |

**Usage instruction:** Pick the most specific applicable reference class. Do not use "micro-cap universe (all)" for a company that clearly belongs to the "going-concern" or "de-SPAC" class — those have worse base rates and the specific class must be used.

---

## What This Skill Will Not Do

These are not limitations to be fixed in future versions. They are principled exclusions.

**Will not:** Predict stock prices or provide price targets. Reverse-DCF implied growth rates are diagnostics, not predictions.

**Will not:** Assess founding team quality based on qualitative impressions. See `disclosure-discipline.md` Discipline 3.

**Will not:** Skip a full batch to save compute. Sampling introduces survivorship bias. "Never sample to save compute" is an invariant from `discovery-engine.md`.

**Will not:** Generate optimistic reports on high-kill-flag companies because the theme story is compelling. The mechanical rules override narrative.

**Will not:** Be the final decision maker. Every output is a de-risk scan for human review. The user decides whether to invest.

---

## Cross-references

- `disclosure-discipline.md` — Disciplines 1, 3, 5, and 6 implement the world-view commitments above
- `judgment-rubric.md` — the base-rate prior table feeds Section 0 of the output template; commitment #5 (scanner not picker) governs what "rating" means
- `discovery-engine.md` — commitment #1 (neglect ≠ undervalued) governs what the precision gate is looking for
- `mechanical-checks.md` — commitment #4 (agent edge = mechanical discipline) defines why the machine layer exists and must not be bypassed
- `event-driven.md` — Phase 5 event discovery axis (spinoffs + cluster insider buys); implements the run-3 audit finding that remaining edge is event-driven, not theme-static
