# Mechanical Checks — Invariant B

> Five Python guards that prevent the most expensive data errors found in real production runs.
> Each guard corresponds to a specific class of bug encountered during development.
> The machine layer outputs data, never narrative. Judgment belongs to the LLM layer.

---

## The Machine-Layer Contract

`tools/*.py` obeys one inviolable rule: **output data structures, never investment conclusions.**

Every JSON field produced by `cheap_pass.py` and `deepdive_data.py` is a measured fact, a count, or a structured flag. No field may contain text like "management appears strong," "revenue growth is impressive," or any claim that requires judgment. The LLM layer in `workflows/` and subagents reads the JSON and provides judgment — this boundary must never blur.

If a Python tool cannot determine a value from authoritative data, it outputs `null` / `None` / `nan` with a documented reason, not a narrative substitute.

---

## Guard 1 — 10-K/A Amendment Exclusion

**Bug (fix #1 — from production run):** `discover.py` and `cheap_pass.py` were counting 10-K/A amendment filings alongside 10-K annual reports, leading to duplicate processing and inflated kill-flag counts.

**Rule:** When fetching filings for a company, filter to `form_type == "10-K"` only. Exclude `10-K/A` (amendments), `10-KT` (transition period), and `10-K405` (legacy variant).

**Why amendments cause harm:** A 10-K/A often amends only a single exhibit or disclosure. If it contains a going-concern mention that the original 10-K did not, you may attribute a kill-flag that belongs to an edge case, not the current annual position. Conversely, an amendment may correct a material weakness from the original — treating both as independent signals double-counts. Always use the original 10-K as the authoritative annual report; track 10-K/A separately if you need amendment history.

**Anchor test:** KOP (Koppers Holdings) — amendment exclusion verified to produce clean single-filing processing.

---

## Guard 2 — Kill-Flag Full-Text Context, Not Market-Wide Count

**Bug (fix #2 — from production run):** The original `cheap_pass.py` used `efts.sec.gov` with a `cik` parameter to count filings containing kill-flag keywords. Two failures:
1. The `cik` filter parameter silently did not work — counts reflected the entire SEC corpus, not the specific company.
2. Every 10-K risk section routinely mentions "going concern" in boilerplate disclaimers (e.g., "The Company does not have any going concern issues"). Counting keyword occurrences always over-reports.

**Rule:** Kill-flag detection reads the full text of the target company's most recent 10-K via `edgartools`, then checks for the flag keyword in context — not as a raw count.

**Going-concern requires double-hit:** A going-concern flag is valid only when both of the following appear in proximity within the same document:
- `going concern`
- `substantial doubt`

A filing that says "we have no going concern issues" should produce `has_going_concern = False`. A filing with both `going concern` and `substantial doubt` in the auditor's note or MD&A produces `has_going_concern = True`.

**Implementation:** `cheap_pass.py` uses `edgartools` to retrieve the 10-K text and applies the double-hit rule with a context window check — not a global string count.

**Anchor test:** IQST — going concern correctly flagged True; amendment exclusion (Guard 1) verified to not contaminate the result.

---

## Guard 3 — Going-Concern Double-Hit (Standalone Rule)

This guard is listed separately because it is the single most impactful mechanical check in terms of false-positive prevention.

**Rule (restatement for clarity):** `has_going_concern = True` requires simultaneous presence of:
- The phrase `going concern` AND
- The phrase `substantial doubt`

both present in the same 10-K filing (full text). No proximity constraint is applied in code —
both phrases must appear anywhere in the same document for the flag to fire.

**Why this matters:** Of the original kill-flag signals, going-concern had the highest false-positive rate when measured by raw keyword count. After applying the double-hit rule, false positives dropped from approximately 60% to under 10% in test runs.

**Other kill-flags use single-hit with context verification:**
- `has_material_weakness` — requires `material weakness` in an auditor report or management assessment section (not in a risk-factor boilerplate)
- `has_death_spiral` — requires `variable conversion` or `discount to VWAP` (or `discount to market`) in a debt instrument description

---

## Guard 4 — `concept_series` Multi-Concept Merge

**Bug (fix #4 — from production run):** `deepdive_data.py` uses the EDGAR `companyconcept` endpoint to fetch XBRL financial series (e.g., `us-gaap/Revenues`). The bug: when the endpoint returns multiple time periods including both annual and quarterly data, the "most recent two periods" selection was picking stale fiscal years (e.g., FY2017 → FY2018) because the data was not sorted by fiscal year end date.

**Rule:** When retrieving `concept_series`, filter to:
1. Annual periods only (`form == "10-K"`)
2. Sorted by `end` date descending
3. Take the N most recent **complete fiscal years** (not the N most recent rows)

The output field `revenue_growth_pct` (and any other derived growth metric) must be annotated with the fiscal year start and end dates it was computed from. If the retrieved data is older than 18 months from the current date, emit a warning flag `data_may_be_stale: true`.

**EGAN case:** EGAN's `revenue_growth_pct` was computed from FY2017–FY2018 data because the concept endpoint returned those as "most recent" without date sorting. The actual revenue trajectory since 2018 was completely different. This caused a materially incorrect mechanical score.

**LLM layer obligation:** Even after this guard is implemented, the LLM layer must independently verify revenue growth from the 10-K text, not trust the XBRL value blindly. The mechanical layer provides a starting point; the judgment layer cross-checks against the most recent 10-K MD&A.

---

## Guard 5 — `runway = nan` Semantic Disambiguation

**Bug (fix #5 — from production run):** When `operating_cash_flow > 0` (the company is cash-flow positive and not burning cash), `runway` is mathematically undefined — you cannot divide cash on hand by a negative outflow. The original code returned `nan` in this case, which was misread as "missing data" or "company has no runway."

**Rule:** The `runway` field must carry a semantic annotation distinguishing three cases:

| `runway` value | `runway_note` | Meaning |
|---|---|---|
| numeric (quarters) | `"computed: cash / quarterly_net_outflow"` | Company is burning cash; runway is real |
| `null` | `"ocf_positive: not burning cash"` | Company is cash-flow positive — `nan` here is a good sign |
| `null` | `"insufficient_data"` | Cannot compute because required fields are missing |

**LLM layer obligation:** The disclosure-discipline doc (`disclosure-discipline.md`) requires that the judgment agent explicitly distinguish these three cases. Seeing `runway = null` with `runway_note = "ocf_positive"` should be interpreted as a positive financial indicator, not a data gap. This is documented in `disclosure-discipline.md` under "honest data-gap."

---

## The Boundary: Machine Layer Outputs Data, Not Narrative

This rule deserves its own section because it is the most frequently violated in informal use.

**Prohibited in any `tools/*.py` output:**
- Qualitative adjectives: "strong," "weak," "impressive," "concerning"
- Investment conclusions: "buy," "avoid," "overvalued," "promising"
- Narrative synthesis: "the company appears to be executing well on its strategy"
- Conditional recommendations: "if runway improves, this could be attractive"

**Required:** All outputs are numeric fields, boolean flags, structured strings (tickers, dates, SIC codes), or explicitly annotated null values with reason codes.

**Why this matters:** When narrative bleeds into mechanical output, the LLM judgment layer loses the ability to form independent opinions. The entire `reference/disclosure-discipline.md` discipline depends on the LLM arriving at the JSON with no pre-formed narrative — only structured facts that it must interpret with the required biases and checks.

---

## Summary Table

| Guard | Bug Source | Key Rule | Anchor Test |
|---|---|---|---|
| 1: Amendment exclusion | Fix #1 (production run) | `form_type == "10-K"` only | KOP |
| 2: Kill-flag full context | Fix #2 (production run) | Read full text via edgartools, not FTS count | IQST |
| 3: Going-concern double-hit | Fix #2 (production run) | Requires both `going concern` + `substantial doubt` in same filing | IQST |
| 4: concept_series merge | Fix #4 (production run) | Filter to annual, sort by `end` date desc, annotate dates | EGAN |
| 5: runway nan | Fix #5 (production run) | Annotate `ocf_positive` vs `insufficient_data` | Multiple |

---

## Cross-references

- `discovery-engine.md` — Gate 2 reads full 10-K text; same edgartools retrieval pipeline used here.
- `judgment-rubric.md` — kill-flag counts from Guard 2/3 feed directly into the rubric's kill-flag hard-rules (≥2 → avoid, ≥3 → forced bottom of ranking).
- `disclosure-discipline.md` — runway null disambiguation (Guard 5) is explicitly called out as a required honest data-gap disclosure.
