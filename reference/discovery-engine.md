# Discovery Engine, Invariant A

> Single-keyword FTS over-recall is the most severe structural flaw in small-cap theme discovery.
> This doc is mandatory reading before invoking `discover.py` or designing new theme keywords.

---

## The Core Problem: Single-Keyword FTS Over-Recalls Severely

SEC full-text search (`efts.sec.gov`) returns every 10-K filing that mentions your keyword anywhere in the document. This sounds useful. In practice, precision is catastrophically low for short natural-language terms.

Short terms are ambiguous across sectors. For example, a materials term may also describe
a treatment response, and a transport term may appear in a customer's logistics discussion.
These are semantic ambiguities, not evidence of theme membership or population error rates.

Gate 1 tags SIC review context without dropping candidates. Gate 2 independently evaluates
the core business through its bound host result. A completed keyword search does not replace
that evaluation, and a cap or failed page limits the recall that can be claimed.

**Lesson: keyword match is not theme membership.** A company that mentions your keyword once in a risk factor or logistics discussion is not a theme member.

---

## The Two-Stage Precision Gate (Mandatory, Not Optional)

These two gates run sequentially before any deepdive computation. They cannot be skipped or combined.

### Gate 1, SIC Coarse Review (`filter_by_sic.sic_classify`, applied inline by `run_theme.py`)

**What it does:** tags each company with a `sic_tier` so Gate 2 knows how suspicious its SIC is.
**It does not drop anything.** `sic_classify` is tri-state and returns only two values in practice:

- `keep`, the SIC is not in `sic_hard_exclude`. Passes to Gate 2 normally.
- `review`, the SIC **is** in `sic_hard_exclude`. The company is tagged `sic_tier="review"` and
  **still passes to Gate 2**, because an SIC review hint on a company recalled by FTS or the
  configured SIC floor requires business-level review. A mixed operating business can have an
  SIC that is a poor description of the theme-relevant segment.
- `drop` is reserved for future explicit-drop logic and **is never returned**. The
  `sic_tier != "drop"` filter in `run_theme.py` is therefore a no-op today. Do not read it as
  evidence that Gate 1 removes anything.

**Caller contract:** `run_theme.py` applies SIC review after cheap-pass to the union of FTS
matches and any configured SIC reverse-recall floor. SIC-only candidates need not match an FTS
keyword. Neither recall source nor `sic_tier` proves theme membership: every survivor requires
an explicit Gate 2 decision before deep-dive data or judgment.

**Invocation:** `filter_by_sic.py` is a library module, not a pipeline step. The invocation rule and
its self-test are stated once, in `SKILL.md` §Entry 1 step 1c.

**SIC review blocks (hard-coded defaults):**

| SIC Range | Description | Reason for review |
|---|---|---|
| 2833 to 2836 | Pharmaceutical preparations | Almost never industrial theme members |
| 38xx | Medical instruments | Medical devices, not industrial |
| 80xx | Health services | Hospitals, clinics |
| 737x | Computer programming/software | Check the actual business for non-tech themes |
| 6xxx | Finance, insurance, real estate | No industrial revenue |
| 5xxx | Retail trade | Distribution only |
| 3944 | Games, toys, children's vehicles | Appears in railcar/industrial recall |

**SIC missing -> keep for LLM:** Retain companies without a SIC code and pass them to Gate 2. A missing or unusual classification does not establish that the operating business falls outside the theme.

**Important:** These blocks are defaults and should be reviewed for each theme. A software theme has no business sending 737x to the `review` tier. The config key is **`sic_hard_exclude`** (`string[]` of SIC prefixes); there is no key named `sic_exclusion_blocks`. It is global, with no per-theme override: to run a theme against a different list, point `$SMALL_CAP_DEEPDIVE_CONFIG_DIR` at a second config dir whose `config.json` sets its own `sic_hard_exclude`. See `CONFIG.md`.

### Gate 2, LLM Theme-Fit (`workflows/theme-fit-gate.js` through the Workflow host)

**What it does:** Reads the actual business description from the selected annual filing (10-K, 20-F or 40-F) and classifies each company as:
- `pure_play`, primary revenue source is directly from the theme
- `partial`, meaningful revenue exposure but not the core business
- `misrecall`, keyword appeared in unrelated context; not a theme member

**Only `pure_play` and `partial` pass to deepdive.**

**What to read:** The business section of the selected annual filing (Item 1 for a 10-K), not just the filing header. The SIC code and ticker are insufficient; the business description is authoritative.

**Classification summary per company (human-readable, not an ingestion artifact):**
```
TICKER: <ticker>
classification: pure_play | partial | misrecall
reason: <one sentence citing specific business activity>
```

For ingestion, retain the complete structured host response bound to the original Gate 2
request. This summary alone cannot establish a completed Gate 2 stage; use the request and
result commands in `runbooks/theme-run.md`.

---

## FTS Keyword Design Rules

These rules prevent the zero-hit and over-recall failure modes.

**Rule 1: Use short, natural words, not multi-word exact phrases.**

SEC full-text search does not reliably match multi-word exact phrases. "DOT-117 tank car retrofit" will return zero hits because companies write "DOT-117" and "tank car" separately. Use `railcar` or `tank car` as separate short terms.

**Rule 2: Zero-hit guard is mandatory.**

If all keywords for a theme return zero filing hits, `discover.py` must write a placeholder result and exit cleanly, not crash with KeyError or attempt to proceed with an empty DataFrame. The zero-hit guard was added after a live crash encountered during development.

**Rule 3: Never sample, process full results.**

Process the complete observed, deduplicated recall set through cheap-pass, then send every survivor through SIC review and the theme-fit gate. Do not introduce sampling to save compute. The discovery CLI has no `--full` or `--sample` flags. Preserve the reported pagination limits, failed pages, and completion state: processing every observed row does not establish uncapped or complete historical coverage.

**Rule 4: Use multiple keywords per theme.**

A theme about specialty chemicals should use 2 to 4 keywords covering different terminology the target companies use (e.g., `titanium dioxide`, `pigment`, `TiO2`). Merge by CIK after FTS to deduplicate.

**Rule 5: Use words companies actually put in their 10-K business description, not academic or analyst terminology.**

Build the keyword set from the products and services described in eligible filings. Use a product noun with a useful modifier, include distinct terms for related activities, and inspect ambiguous matches at Gate 2.

Treat each keyword set as a recall hypothesis. Record its observed coverage and limits for the current run; historical examples do not establish that a query retrieves every relevant issuer.

---

## Ambiguous Keywords and Gate Responsibilities

A keyword can describe a product, a customer, a risk or an unrelated technical concept.
Treat the FTS result as a candidate observation. Gate 1 adds SIC context and forwards it;
Gate 2 evaluates the business against the requested theme through a bound host result.

Keep the original search scope, caps and failed pages with the candidate set. The number
that survives either gate does not prove population recall or a general false-positive rate.

## Coverage Caveat, Foreign Filers (20-F / 40-F)

**Phase 4 status: 20-F / 40-F is now graceful-fallback (not ignored).**

`discover.py` default `--forms` now includes `20-F,40-F` in addition to `10-K,10-Q`,
so foreign-domiciled filers are discovered at the FTS stage.

Downstream fallback chain (implemented in Phase 4):
- `cheap_pass.killflag_scan`: tries 10-K first; if empty, falls back to 20-F then 40-F.
  Same kill-flag phrases and business_blurb extraction are reused, going-concern and
  material-weakness language is structurally similar in 20-F/40-F.
- `deepdive_data.tenk_sections`: same fallback chain. Sets `filing_form` field so the
  caller knows which form type was actually read.
- XBRL extraction uses `us-gaap` concepts and a partial `ifrs-full` fallback cascade.
  Availability depends on the issuer's concepts, periods and units; SEC registration alone
  does not establish usable financial coverage.

**Known gap / untested:** Financial coverage across 20-F/40-F filers is not systematically
validated. The concept cascade may still leave fields unavailable, and unsupported currencies
are not converted into USD. Treat foreign-filer XBRL as best-effort, retain the missing-data
reasons and flag material gaps for manual review.

**Verification contract:** A successful foreign-filer scan must report the actual selected form and usable disclosure evidence. The live validation lane must establish that behavior for its current inputs; a retained example is not a current acquisition receipt.

**Theme-selection note:** Themes whose pure-plays are structurally foreign-domiciled
(e.g. Marshall Islands tanker operators) now have partial coverage. Accept remaining
gaps explicitly or supplement with a manual list of known 20-F filers for the theme.

---

## Integration with Workflow

The discovery flow for `theme <keyword>` is:

```
discover.py (FTS / configured SIC reverse-recall union, merge by CIK)
    ↓
cheap_pass.py (mechanical de-risk; keep only non-rejected candidates)
    ↓
run_theme.py calls sic_classify (Gate 1: SIC review hints, no theme-fit removal)
    ↓
explicit bound Gate 2 request → Workflow host → validated result ingestion
    ↓
[pure_play + partial only] → deepdive_data.py → bound deepdive-fanout
```

Complete cheap-pass and SIC review before preparing Gate 2. Retain the bound Gate 2 result and survivor receipt; run `deepdive_data.py` only on the validated survivor artifact. See `runbooks/theme-run.md` for the request, host and ingestion commands.

---

## Cross-references

- `mechanical-checks.md`, Gate 2 depends on full 10-K text being read, not sampled; the "full-not-sampled" rule from invariant B also applies here.
- `judgment-rubric.md`, theme-fit dimension (dim 5) maps to Gate 2 output; `misrecall` companies should never appear in the rubric scoring phase.
- `data-sources.md`, EDGAR FTS rate limits and retry-backoff discipline apply to all FTS calls in `discover.py`.
- `event-driven.md`, for event-driven discovery (Form 10-12B spinoffs, cluster insider buys) that bypasses the theme-fit gate by using form-type enumeration instead of keyword FTS.
