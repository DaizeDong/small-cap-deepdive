# Disclosure Discipline, Invariant C (Disciplines)

> The judgment layer's job is not to build the best story from the available data.
> Its job is to stay disciplined enough that the data can falsify the story.
> Every rule here is a structural defense against the known failure modes of LLM-based equity analysis.
>
> Violating any of these disciplines does not produce a "lower quality" report, it produces an invalid one.
> See `judgment-rubric.md` for the scoring template these disciplines govern.

---

## Discipline 1, Base Rate First

**Rule:** Before writing any claim about a specific company, state the reference class and its empirical base rates.

**Why:** LLMs are optimized to generate coherent, plausible narratives. Given financial data about any company, an unconstrained LLM will construct a plausible growth story, even for companies that are overwhelmingly likely to fail. Base rates are the prior that must be updated by evidence, not replaced by story.

**Implementation:**
- Choose the most specific reference class that describes this company: "pre-revenue micro-cap with AI exposure," "cash-flow-positive small-cap industrial," "de-SPAC with net cash," etc.
- State the empirical base rates for that class (see `cognitive-priors.md` for the prior table)
- From that prior, work toward the specific company using Tier-weighted evidence only
- If evidence is insufficient to move the prior materially, default to the prior

**Example anchor (acceptable):** "Reference class: pre-revenue micro-cap software company with AI positioning. Base rates: approximately 60 to 70% of companies in this class fail to achieve sustainable revenue within 5 years. This prior requires T1 evidence of customer traction before moving the rating above WATCH."

**Example anchor (unacceptable):** Starting the report with the growth narrative and later noting "risks include competition and execution." This is story-first, base-rate-never.

---

## Discipline 2, Forced Disconfirmation Search

**Rule:** Before synthesizing a conclusion, run a dedicated adversarial search for negative evidence.

**Mandatory search query pattern:**
```
<company name> short report OR fraud OR dilution OR lawsuit OR going concern
```

**Additional queries if the first returns nothing:**
```
<company name> SEC investigation OR restatement OR audit
<ticker> insiders selling OR secondary offering
```

**Required disclosure in every report:**
- If negative evidence was found: summarize it and include it in the bear case (Section 3 of the output template)
- If nothing was found: explicitly write "Disconfirmation search conducted; no short reports, fraud allegations, or significant litigation found as of [date]"

**Not acceptable:** Omitting this section. Not acceptable: claiming the search was run without stating what query was used and what was returned.

**Why:** LLMs exhibit confirmation bias, they tend to search for evidence consistent with an emerging thesis. The forced adversarial search structurally breaks this by requiring a dedicated contrary-evidence pass before synthesis begins.

---

## Discipline 3, Halo De-Bias (Management Dimension)

**Rule:** Management quality assessment must use only evidence that is independent of the company's stock price performance.

**The halo effect (Rosenzweig):** When a company performs well, all attributes of its leadership are retrospectively rated positively, "visionary," "execution-focused," "capital-disciplined." When it performs badly, the same leaders are "arrogant," "overextended," "distracted." The underlying leader did not change; only the observed outcome changed. LLMs trained on financial text have absorbed this pattern deeply, they will systematically reproduce halo bias when asked to assess management quality.

**Permitted evidence for management scoring:**
- Form 4 insider trades: open-market purchases at market prices (strongest buy signal); cluster selling during secondary offerings (strong sell signal)
- Historical guidance vs. actual results: last 4 to 6 quarters, using 10-K/10-Q filings to verify. Over-promising pattern = negative
- CEO/founder track record: what happened to the prior company they led? Search SEC EDGAR for their prior public company positions
- Compensation structure (DEF 14A): base salary vs. company cash burn; performance criteria for equity awards
- Capital allocation choices: buybacks, M&A, dividends, funded by cash flow or by dilutive offerings?

**Prohibited evidence:**
- "The CEO has a track record of building great companies" (circular, stock performance is the signal)
- Any quote from a press release, conference presentation, or media interview about the CEO's vision or strategy
- LinkedIn recommendations or employee reviews
- Any general impression of "strong management team" not traced to a specific measurable action

**Hard ceiling rule:** If insider_net_sell is strongly negative (cluster open-market selling, not option exercises) AND dilution rate exceeds 15% per year, management dimension is capped at 2 regardless of other evidence.

---

## Discipline 4, Evidence Tier Grading

**Rule:** Every load-bearing claim must be tagged with its evidence tier. A claim without a tier tag is inadmissible as a scoring basis.

| Tier | Sources | Usable as |
|---|---|---|
| T1 | SEC filings, audited statements, Form 4, court records | Load-bearing for any rating |
| T2 | Independent analyst research, short-seller reports (reputable), academic studies, verified journalism with named sources | Load-bearing with scrutiny |
| T3 | Press releases, earnings call transcripts (company-sourced), LinkedIn, unverified social media, company website | Lead for further investigation only |

**Hard rule from `judgment-rubric.md`:** A BUY rating cannot rest on T3 evidence. If the primary positive claim is "management says revenue will double" (T3), the rating must be WATCH or AVOID until T1/T2 corroboration exists.

**T3 handling:** When T3 evidence is the only source for a claim, note it explicitly: "(T3 only, not load-bearing; requires corroboration)" rather than silently downweighting.

---

## Discipline 5, Falsifiable Long and Short Arguments with Triggers

**Rule:** Every bull and bear argument must be stated as a falsifiable proposition with an explicit trigger that would overturn it.

**Format:**
```
Claim: [specific, measurable claim]
Evidence basis: [T1/T2/T3 source]
Falsification trigger: If [specific observable event] does/does not occur by [specific date or quarter], this argument is falsified.
```

**Not acceptable:** "The company is well-positioned to benefit from the AI wave." This cannot be falsified. It is not an argument; it is a narrative.

**Acceptable example:**
```
Claim: The company will reach cash-flow breakeven by Q3 2026 based on current trajectory.
Evidence: T1 — 10-K shows OCF improving from -$3M to -$1.2M over past 4 quarters.
Falsification trigger: If OCF does not reach >$0 by Q3 2026 earnings, the bull case on financial quality is falsified.
```

**Why falsifiability matters:** Without falsification triggers, deep-dive reports become unfalsifiable narratives that survive any outcome. A company that misses every projection keeps generating "we remain bullish long-term." Requiring explicit triggers forces the agent (and the user tracking forward) to record specific conditions under which the thesis is wrong before it plays out.

---

## Discipline 6, Pre-Mortem

**Rule:** Every report must include a section titled "Pre-mortem: most likely path to -80%."

**Procedure:** Assume the position was taken, and 18 months later the stock is down 80%. Work backward: what happened? This is not a list of risks, it is a narrative of the most plausible specific failure sequence.

**Why it works (Gary Klein, decision research):** Pre-mortem forces the analyst to inhabit the failure scenario imaginatively before committing to the position. This breaks the commitment bias that builds during analysis. It also forces identification of the single most fragile assumption in the bull case.

**What makes a good pre-mortem:**
- Specific (names a mechanism, not just "execution risk")
- Traces from a plausible triggering event to the -80% outcome
- Identifies which bull-case assumption was wrong and why it seemed credible at the time

**Example (acceptable):** "Customer concentration was flagged as a risk. The single customer accounting for 38% of revenue did not renew in Q2 2026, revenue dropped 35% in one quarter. The company drew on its credit facility to fund operations, which triggered a covenant breach. The bank demanded full repayment. Unable to refinance, the company announced a large dilutive offering at -60% to current price. Stock fell further as existing holders sold to avoid further dilution."

---

## Discipline 7, Kill-Flag Mechanical Count (No Narrative Override)

**Rule:** Kill-flag counts come from `cheap_pass.py` / `deepdive_data.py` output. The judgment layer counts them; it does not override them with qualitative reasoning.

**Kill-flags tracked:**
- `has_going_concern` (double-hit required per `mechanical-checks.md` Guard 3)
- `has_material_weakness`
- `has_death_spiral`
- `customer_concentration_flag`
- Secondary: restatement, auditor resignation, serial dilution, reverse split, frequent name/ticker change (these are noted in the report but not counted in the primary kill-flag total for hard-rule purposes)

**Hard rule:** When kill-flag count ≥ 2, the default rating is AVOID. This default can be overridden only by strong T1 evidence that directly contradicts the kill-flag (e.g., going-concern mention is from a prior year and the auditor's subsequent year report contains no going-concern language). Document the override explicitly.

**Hard rule:** When kill-flag count ≥ 3, the company sinks to bottom of ranking regardless of aggregate scorecard total. No scorecard aggregate overrides this.

**When to cluster-flag:** If 5 or more secondary kill-flags appear together (e.g., serial dilution + reverse split + frequent ticker change + high-concentration insider + going concern), treat as a near-certain avoidance signal and note in the pre-mortem.

---

## Discipline 8, Machine Data May Be Stale, Verify with WebSearch

**Rule:** Mechanical data from `deepdive_data.py` has a retrieval date. Financial conditions can change rapidly. Before relying on any field for a hard rating decision, check whether material events have occurred since the data was pulled.

**Staleness triggers requiring WebSearch verification:**
- `data_may_be_stale: true` flag on any field
- More than 90 days between the data retrieval date and the current date
- Any field that a press search suggests may have changed (bankruptcy filing, merger announcement, major earnings miss)

**Mandatory WebSearch before scoring** if any of these are present:
```
<ticker> site:sec.gov OR site:businesswire.com recent news
```

**Disclosure in report:** State the mechanical data retrieval date and whether it was verified via WebSearch. If data was stale and WebSearch was used, cite the verification source (T2 at minimum; T1 if an SEC filing was found).

---

## Discipline 9, Honest Data-Gap Acknowledgment

**Rule:** Every report must explicitly list data that was sought but not obtained, distinguishing between "genuinely missing" and "means something positive."

**The critical disambiguation:**

| Field value | Meaning | What to write |
|---|---|---|
| `runway = null`, `runway_note = "ocf_positive"` | Company is cash-flow positive; no burn rate to compute | "Runway not computed, OCF is positive, which indicates the company is not burning cash. Verified via OCF trend." |
| `runway = null`, `runway_note = "insufficient_data"` | Data genuinely missing | "Runway could not be computed due to missing cash flow data. This is a genuine data gap." |
| `insider_trades = None` | openinsider returned no Form 4 data | "Insider trade data not retrieved. Flagged as unverified, treat management dimension as data-limited." |
| `revenue_growth_pct` from stale XBRL | May not reflect current trajectory | "Revenue growth computed from FY[X],FY[Y] data. Verified against 10-K MD&A: [result]." |

**The obligation:** Section 8 of the output template ("Known gaps and unverified items") must be populated. Writing "none" is acceptable only if all fields were verified against T1 sources.

---

## Cross-references

- `judgment-rubric.md`, the scorecard, output template, and hard-rules that these disciplines enforce
- `cognitive-priors.md`, the base-rate prior table used in Discipline 1
- `mechanical-checks.md`, the data-layer rules that govern what fields the judgment layer receives, and what `null` values mean
- `data-sources.md`, WebSearch and other verification tools available for Disciplines 2, 8
