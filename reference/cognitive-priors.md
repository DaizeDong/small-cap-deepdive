# Cognitive Priors, Invariant D

> Research assumptions and operating constraints for interpreting the output. Empirical
> reference notes and two historical production runs informed these choices; applying a
> cited result still requires source verification and a matching population.

---

## The Five World-View Commitments

### 1. Neglected Does Not Equal Undervalued

A company that receives no analyst coverage and no retail investor attention is neglected. It is not, for that reason, undervalued.

The working hypothesis is delayed information diffusion: a meaningful fundamental improvement may not yet be reflected in price. Neglect identifies companies to examine; a specific information gap still needs evidence.

**Practical implication:** A company that screens well on neglect (low coverage, no media mentions, small market cap) has cleared a necessary but not sufficient condition. The report must identify a specific information gap, a financial improvement, a catalyst, a dislocation, not just assert that the company is "under the radar."

**Source:** Barber & Odean (2008), retail investors systematically buy attention-grabbing stocks, pushing prices above fundamental value. The mechanism works in reverse: neglect is priced but neglect alone is not a return signal.

### 2. Hot Themes Are Not Good Hunting Grounds

A popular investment theme is, by definition, widely known. Stocks connected to popular themes have already been re-rated by investors who discovered the theme first. The alpha, if any existed, has largely been captured.

**The empirical record:** Ben-David, Franzoni et al. (2023), thematic ETFs launched at the peak of theme popularity showed risk-adjusted annual returns of approximately -6% in the 5 years post-launch. The information that drives the theme narrative is already priced.

**What this means for theme selection:** The best themes for this skill are either:
(a) Obscure industrial niches with no retail attention (railcar retrofits, specialty chemicals, industrial refractory), genuine neglect; or
(b) Large, well-known themes where the skill's value is separating the few true beneficiaries from the many concept-players.

A theme should also fit the tool's financial models and available filing coverage.
Financial SICs receive Gate 1 review hints and still reach Gate 2; separate valuation rules
can make them ineligible for BUY. Discovery includes 20-F/40-F filers, with partial downstream
financial coverage (see `discovery-engine.md` Coverage Caveat). Precise, low-collision keywords matter too:
prefer specific terms (`cremation`, `aircraft engine`) over generic ones that sweep
unrelated industries.

**What this does not mean:** Avoid all "hot" themes entirely. A hot theme can still contain mis-priced companies, especially when the theme narrative has swept in companies with zero actual revenue from the theme. The skill's precision gate (see `discovery-engine.md`) is designed to find those.

### 3. Real Theme Members Are Often Fairly-Priced Cyclicals

After the two-stage precision gate, the companies that remain as true theme members are frequently small industrial, specialty chemical, or niche services companies that have always operated in this space. They did not get re-rated because the market already knew them. Their valuations reflect their historical cycle, not the theme premium.

Established cyclical businesses remain valid research subjects. Verify both their operating exposure and valuation; a theme reference in a press release is insufficient for that comparison.

**Implication for scoring:** A company that is a true pure-play (Gate 2 = `pure_play`) but is trading at fair cyclical value should still be analyzed rigorously. Fair cyclical value and real theme exposure warrant analysis without adding a narrative premium or penalty.

### 4. Agent Edge Is Mechanical Discipline, Not Narrative Synthesis

The design objectives are:
- Systematic coverage of the admitted candidate set within the stated budget
- Consistent application of kill-flags, disclosure disciplines and scoring
- Reduced selection bias from familiarity with particular companies

The skill has **no** comparative advantage in:
- Judging whether a founding team is exceptional
- Predicting whether a product narrative will resonate with the market
- Synthesizing qualitative impressions into a forward-looking story

Any part of the output that relies on narrative synthesis should be treated with suspicion. The parts that rely on systematic application of T1 data and mechanical rules are the parts worth trusting.

**Historical design rationale:** Adversarial development review proposed: "Agent's advantage is scaling structured quality signal across the full market, maintaining consistent discipline, not qualitative synthesis of people and narratives. The latter is the heaviest halo-bias zone."

### 5. Output Is a De-Risk Scanner, Not a Stock Picker

This skill does not identify the next ten-bagger. It identifies which companies in a theme have the fewest structural red flags and the most credible fundamental cases, relative to each other.

A batch ranking that produces "0 BUY, 3 WATCH, 7 AVOID" describes the observed candidates under the current policy. Report retrieval coverage, unavailable inputs and abstentions with those counts. Zero BUY alone proves neither low theme quality nor market efficiency; completeness and investment outcomes require separate evidence.

**Interpreting rank:** Read the rating, kill-flags, source completion and evidence alongside rank. A high-ranked report supports human due diligence only to the extent those fields support it. Admission follows `cheap_pass.rejected`; a surviving individual risk flag can still block BUY.

**Historical observations are hypotheses.** The earlier runs and post-run audits do not
establish a market-wide relationship between theme choice, survivor quality and returns.
They included coverage limits and analyst interventions. No performance conclusion follows
from the count of BUY outputs alone.

**Current decision policy.** The rubric requires the active margin of safety to meet its
threshold, zero effective kill-flags, the applicable eligibility checks and supported
evidence. The catalyst MoS waiver is frozen: an event may justify WATCH with a catalyst,
but does not permit a sub-threshold BUY. The authoritative policy is
`judgment-rubric.md`; the event route changes discovery, not the BUY requirements.

Ratings remain structured hypotheses. Forward outcome observations, with coverage and
selection limits reported, are needed to assess calibration. No fixed number of verdicts
alone proves a predictive edge. See [evidence status](../docs/evidence-status.md).

---

## Base-Rate Prior Table

These are historical reference notes, not validated mandatory numeric priors. Before using
a number in Section 0, retrieve a traceable study, verify the target population, outcome and
time window, and cite that evidence. If this cannot be done, state that the prior is unknown
or explicitly identify an assumption; do not present the table as a measured base rate.

| Reference class | Zero / wipeout rate | Mediocre outcome rate | Reasonable return rate | Source / Notes |
|---|---|---|---|---|
| Micro-cap universe (all, 5-yr) | ~40 to 50% fail, delist, or go to zero | ~35% flat / minimal return | ~15 to 25% meaningful return | Shumway (1997) + Kailash 35-yr study; delisting bias understates failure rate in standard databases |
| Lowest-quality-quintile small-cap growth | ~70% underperform Russell 2000 over 5 years | n/a | n/a | Kailash Capital research on small-cap quality |
| De-SPAC companies (2 to 3 yr post-merger) | Median return: -29% from SPAC price | n/a | n/a | Klausner, Ohlrogge & Ruan (2022) |
| Going-concern finding and bankruptcy | No validated numeric prior supplied | n/a | n/a | The earlier 85% within-three-years claim had only a generic research attribution and is withdrawn pending traceable population-matched evidence. |
| Companies with multiple kill-flags | Unknown | n/a | n/a | Selected historical cases do not establish a population failure probability. |
| Pre-revenue micro-cap with AI/theme positioning (2025 to 2026) | High; exact rate unclear but theme ETF data suggests significant premium has been paid by retail | n/a | n/a | Ben-David et al. (2023) thematic ETF study |

**Usage instruction:** Select a relevant reference class only after verifying the cited study and population match. Missing evidence is an unknown prior; it must not become a mandatory percentage through a table lookup.

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

- `disclosure-discipline.md`, Disciplines 1, 3, 5, and 6 implement the world-view commitments above
- `judgment-rubric.md`, the base-rate prior table feeds Section 0 of the output template; commitment #5 (scanner not picker) governs what "rating" means
- `discovery-engine.md`, commitment #1 (neglect ≠ undervalued) governs what the precision gate is looking for
- `mechanical-checks.md`, commitment #4 (agent edge = mechanical discipline) defines why the machine layer exists and must not be bypassed
- `event-driven.md`, event discovery through spinoffs and cluster insider purchases; this is a discovery route with no established comparative return advantage.
