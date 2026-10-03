# Mechanical Checks, Invariant B

> Mechanical guards for annual filing selection, disclosure context and financial evidence.
> The contracts below describe current producer behavior.
> The machine layer outputs data, never narrative. Judgment belongs to the LLM layer.

---

## The Machine-Layer Contract

`tools/*.py` obeys one inviolable rule: **output data structures, never investment conclusions.**

Every JSON field produced by `cheap_pass.py` and `deepdive_data.py` is a measured fact, a count, or a structured flag. No field may contain text like "management appears strong," "revenue growth is impressive," or any claim that requires judgment. The LLM layer in `workflows/` and subagents reads the JSON and provides judgment, this boundary must never blur.

If a Python tool cannot determine a value from authoritative data, it outputs `null` / `None` / `nan` with a documented reason, not a narrative substitute.

---

## Guard 1, Annual Filing Selection

Annual disclosure retrieval tries exact forms in order: 10-K, then 20-F, then 40-F.
Amendments are excluded from this selection. Record the selected filing identity and
source-completion state; failure to retrieve any supported annual filing remains unknown.

An amendment can change a specific disclosure without representing an independent annual
report. Review amendment history separately when needed, preserving its relationship to
the original filing. The generated filing controls exercise annual fallback and unavailable
sources without treating a missing filing as clear.

---

## Guard 2, Kill-Flag Full-Text Context, Not Market-Wide Count

A market-wide keyword count does not establish a company-specific disclosure.
Retrieve the issuer's selected annual filing and inspect the assertion in context.
Boilerplate and negated statements must not become affirmative findings.

**Current rule:** The filing-disclosure parser in `tools/_filing_disclosures.py`
evaluates local assertions and their polarity. It keeps evidence offsets and distinguishes
affirmative, negated, remediated, conditional, historical and ambiguous statements.
An unavailable or unresolved observation remains unknown rather than clear.

## Guard 3, Going-Concern Assertion Evidence

Two phrases anywhere in a document are insufficient. The parser must connect substantial
doubt to going-concern language in the relevant assertion and account for negation and
remediation. It does not join unrelated sentences to manufacture a finding. Conditional
and unresolved historical language retains a null flag for review.

The same evidence discipline applies to material weakness. The synthetic filing-disclosure
regressions exercise current assertions, negation, remediation and unrelated clauses.
Historical false-positive rates are not a current validation result; see
[the evidence status](../docs/evidence-status.md).

---

## Guard 3b, Material-Weakness Assertion Evidence

Current disclosure extraction uses `tools/_filing_disclosures.py` for both the cheap
screen and deep-dive filing context. A bare phrase or an unrelated affirmative sentence
does not establish a finding. The parser distinguishes negated and remediated statements
from current unresolved findings; conditional, ambiguous or unavailable evidence remains
unknown for review. See the synthetic filing-disclosure regressions for the supported
statement forms. This rule does not certify that an issuer has no other financial risk.

---

## Guard 4, `concept_series` Multi-Concept Merge

The selector validates fact shape and filing dates against the requested as-of date.
For flow concepts, _annual_entry accepts periods of 330 to 400 days. Registered instant
concepts use the separate instant-balance path. An annual flow is not defined by a
10-K-only form predicate.

Within each concept, the latest eligible filing supplies each period end; across the configured cascade, later concepts override earlier concepts for the same period end, sorted ascending
by end, and truncated to the most recent requested periods. The latest returned point
is at index -1. Preserve the underlying end and filed dates when interpreting changes;
do not assume a documented warning field exists unless the producer emits it.

An unsorted or mismatched-period response can anchor growth to an old interval.
Cross-check the selected annual filing and its MD&A against the dated series before
using the derived result.

---

## Guard 5, Runway Periods and Missing Evidence

The producer field is runway_periods. When the latest OCF is negative and cash is
available, it is cash divided by the absolute latest OCF, rounded to one decimal place.
The unit is the period covered by that OCF observation, commonly a year for annual data;
it is not automatically a quarter.

The field is null when OCF is nonnegative or required cash/OCF evidence is missing.
These producers do not emit a runway_note. Inspect the accompanying cash, OCF and
source evidence to distinguish no measured cash burn from missing inputs. A null
runway alone proves neither financial health nor a data gap.

---

## The Boundary: Machine Layer Outputs Data, Not Narrative

This rule deserves its own section because it is the most frequently violated in informal use.

**Prohibited in any `tools/*.py` output:**
- Qualitative adjectives: "strong," "weak," "impressive," "concerning"
- Investment conclusions: "buy," "avoid," "overvalued," "promising"
- Narrative synthesis: "the company appears to be executing well on its strategy"
- Conditional recommendations: "if runway improves, this could be attractive"

**Required:** All outputs are numeric fields, boolean flags, structured strings (tickers, dates, SIC codes), or explicitly annotated null values with reason codes.

**Why this matters:** When narrative bleeds into mechanical output, the LLM judgment layer loses the ability to form independent opinions. The entire `reference/disclosure-discipline.md` discipline depends on the LLM arriving at the JSON with no pre-formed narrative, only structured facts that it must interpret with the required biases and checks.

---

## Summary Table

| Guard | Evidence | Key rule |
|---|---|---|
| Annual filing selection | Generated filing controls | 10-K, then 20-F, then 40-F; exclude amendments |
| Disclosure context | Synthetic filing disclosures | Evaluate the connected assertion and its polarity |
| Going concern | Synthetic filing disclosures | Preserve timing, negation and uncertainty |
| Material weakness | Synthetic filing disclosures | Distinguish current, remediated and ambiguous assertions |
| Concept series | Generated concept fixtures | Annual flow duration, instant classification, ascending end dates |
| Runway periods | Cash and latest OCF | State the OCF period and distinguish nonnegative OCF from missing data |

---

## Cross-references

- `discovery-engine.md`, Gate 2 reads the selected annual filing text; same edgartools retrieval pipeline used here.
- `judgment-rubric.md`, kill-flag counts from Guard 2/3 feed directly into the rubric's kill-flag hard-rules (effective count ≥2 → avoid; AVOID or effective count ≥2 → forced bottom of ranking).
- `disclosure-discipline.md`, runway null disambiguation (Guard 5) is explicitly called out as a required honest data-gap disclosure.
- `valuation.md`, Phase 2 valuation module; consumes the financial series produced by `deepdive_data.py` and applies the same data-only contract (no narrative, no buy/sell rating).
- `event-driven.md`, kill-flag scan (`cheap_pass.py`) applies **equally** to event-mode candidates (spinoffs and insider-cluster buys).  A compelling catalyst does not excuse a going-concern filing.  Guards 1 to 5 are not relaxed for event candidates.
