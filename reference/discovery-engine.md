# Discovery Engine, Invariant A

> Single-keyword FTS over-recall is the most severe structural flaw in small-cap theme discovery.
> This doc is mandatory reading before invoking `discover.py` or designing new theme keywords.

---

## The Core Problem: Single-Keyword FTS Over-Recalls Severely

SEC full-text search (`efts.sec.gov`) returns every 10-K filing that mentions your keyword anywhere in the document. This sounds useful. In practice, precision is catastrophically low for short natural-language terms.

**Measured result from real runs:**
- Theme "AI agent" with natural keywords → 192 candidate tickers returned
- After the two-stage precision gate → 13 true theme members (6.8% precision)
- 94% of filings mentioned the keyword in unrelated contexts

**Real case, refractory swept all of biotech:**
The keyword `refractory` was used for a railcar insulation theme (refractory linings). In oncology, "refractory" means treatment-resistant cancer, every biotech and oncology company uses this word. The single-keyword FTS returned the entire biotech sector. Zero of these were railcar companies. **Gate 1 did not cut them:** a pharma SIC is in `sic_hard_exclude`, so Gate 1 tagged those names `review` and forwarded them anyway. Gate 2 is the step that cleared the field, and with Gate 2 skipped the entire biotech sector would have reached the deep-dive queue. This is the case that shows Gate 2 can never be skipped or merged into Gate 1: Gate 1 has no power to remove a keyword hit. Full step-by-step below, §Refractory Case: Full Reconstruction.

**Real case, railcar swept commodity logistics:**
`railcar` is used by grain, ethanol, potash, and other commodity shippers to describe their logistics. Build-A-Bear's annual report mentions railcar delivery. The term does not uniquely identify railcar manufacturers or lessors.

**Lesson: keyword match is not theme membership.** A company that mentions your keyword once in a risk factor or logistics discussion is not a theme member.

---

## The Two-Stage Precision Gate (Mandatory, Not Optional)

These two gates run sequentially before any deepdive computation. They cannot be skipped or combined.

### Gate 1, SIC Coarse Review (`filter_by_sic.sic_classify`, applied inline by `run_theme.py`)

**What it does:** tags each company with a `sic_tier` so Gate 2 knows how suspicious its SIC is.
**It does not drop anything.** `sic_classify` is tri-state and returns only two values in practice:

- `keep`, the SIC is not in `sic_hard_exclude`. Passes to Gate 2 normally.
- `review`, the SIC **is** in `sic_hard_exclude`. The company is tagged `sic_tier="review"` and
  **still passes to Gate 2**, because a hard-excluded SIC on a company that already matched the
  theme keywords is a question for the LLM, not a verdict. TITN (SIC 5990, a farm-equipment dealer)
  and SNFCA (SIC 6199, a real deathcare segment) are why.
- `drop` is reserved for future explicit-drop logic and **is never returned**. The
  `sic_tier != "drop"` filter in `run_theme.py` is therefore a no-op today. Do not read it as
  evidence that Gate 1 removes anything.

**Caller contract:** `sic_classify` does not check theme-keyword membership itself, so `review` is
safe to forward only because `run_theme.py` calls it on a post-FTS universe. A caller that skips the
FTS pre-filter reopens the over-recall hole.

**Invocation:** `filter_by_sic.py` is a library module, not a pipeline step. The invocation rule and
its self-test are stated once, in `SKILL.md` §Entry 1 step 1c.

**SIC review blocks (hard-coded defaults):**

| SIC Range | Description | Why excluded |
|---|---|---|
| 2833 to 2836 | Pharmaceutical preparations | Almost never industrial theme members |
| 38xx | Medical instruments | Medical devices, not industrial |
| 80xx | Health services | Hospitals, clinics |
| 737x | Computer programming/software | Excluded for non-tech themes |
| 6xxx | Finance, insurance, real estate | No industrial revenue |
| 5xxx | Retail trade | Distribution only |
| 3944 | Games, toys, children's vehicles | Appears in railcar/industrial recall |

**SIC missing → keep for LLM:** Companies with no SIC code on file are retained and passed to Gate 2. Do not auto-exclude them. Historical examples: NL Industries (NL, SIC 2810 chemicals) and VHI were initially misflagged, they are legitimate theme candidates with unusual SIC codes.

**Important:** These blocks are defaults and should be reviewed for each theme. A software theme has no business sending 737x to the `review` tier. The config key is **`sic_hard_exclude`** (`string[]` of SIC prefixes); there is no key named `sic_exclusion_blocks`. It is global, with no per-theme override: to run a theme against a different list, point `$SMALL_CAP_DEEPDIVE_CONFIG_DIR` at a second config dir whose `config.json` sets its own `sic_hard_exclude`. See `CONFIG.md`.

### Gate 2, LLM Theme-Fit (`theme-fit-gate.js` / natural language subagent)

**What it does:** Reads the actual business description from the most recent 10-K and classifies each company as:
- `pure_play`, primary revenue source is directly from the theme
- `partial`, meaningful revenue exposure but not the core business
- `misrecall`, keyword appeared in unrelated context; not a theme member

**Only `pure_play` and `partial` pass to deepdive.**

**What to read:** The "Business" section (Item 1) of the most recent 10-K, not just the filing header. The SIC code and ticker are insufficient, the business description is authoritative.

**Required output per company:**
```
TICKER: <ticker>
classification: pure_play | partial | misrecall
reason: <one sentence citing specific business activity>
```

---

## FTS Keyword Design Rules

These rules prevent the zero-hit and over-recall failure modes.

**Rule 1: Use short, natural words, not multi-word exact phrases.**

SEC full-text search does not reliably match multi-word exact phrases. "DOT-117 tank car retrofit" will return zero hits because companies write "DOT-117" and "tank car" separately. Use `railcar` or `tank car` as separate short terms.

**Rule 2: Zero-hit guard is mandatory.**

If all keywords for a theme return zero filing hits, `discover.py` must write a placeholder result and exit cleanly, not crash with KeyError or attempt to proceed with an empty DataFrame. The zero-hit guard was added after a live crash encountered during development.

**Rule 3: Never sample, process full results.**

If a keyword returns 200 filings, process all 200 through the SIC gate and theme-fit gate. Sampling to save compute introduces survivorship bias and may drop true theme members that appear late in the result list. The `--full` flag is on by default; never override it to `--sample`.

**Rule 4: Use multiple keywords per theme.**

A theme about specialty chemicals should use 2 to 4 keywords covering different terminology the target companies use (e.g., `titanium dioxide`, `pigment`, `TiO2`). Merge by CIK after FTS to deduplicate.

**Rule 5: Use words companies actually put in their 10-K business description, not academic or analyst terminology.**

Run-3 lessons from the crop-inputs theme audit:

- `crop inputs` was too academic → missed LXU (nitrogen fertilizer), IPI (potash), AVD (crop protection). These companies write `fertilizer`, `potash`, `crop protection`, `plant nutrition` in their Item 1. Use those words.
- `facility services` was over-broad → swept unrelated building-services and outsourcing companies. Prefer the specific sub-sector term (e.g. `industrial cleaning`, `grounds maintenance`).
- `engine` is over-broad → every manufacturer, automotive, and aerospace company mentions engines. Use `diesel engine`, `gas turbine`, or the specific model name.
- `deathcare` / `funeral services` / `cremation` / `cemetery` are all used interchangeably by actual operators; use at least two of these to maximize recall without over-broadening.

**Per-theme keyword heuristics (run-3 lessons):**

| Theme | Good keywords | Bad keywords |
|---|---|---|
| Crop inputs / ag chemicals | `fertilizer`, `potash`, `crop protection`, `plant nutrition` | `crop inputs`, `agricultural inputs` |
| Funeral / deathcare | `funeral`, `cremation`, `cemetery`, `deathcare` | `end-of-life services` |
| Industrial filters | `filtration`, `industrial filter`, `filter media` | `filtration services` (too broad) |
| Tanker shipping | `product tanker`, `crude tanker`, `chemical tanker` | `shipping` (entire maritime sector) |
| Farm equipment dealers | `farm equipment`, `agricultural equipment dealer`, `Case IH`, `John Deere dealer` | `equipment`, `dealer` |

The pattern: use the noun+modifier that appears in the company's own product or service description, not the analyst category label.

---

## Refractory Case: Full Reconstruction

For reference, the complete failure mode and fix:

1. Keyword `refractory` submitted to FTS
2. FTS returns ~80 hits including biotech, oncology, pharma companies
3. Gate 1 (SIC 2833-2836, 80xx in `sic_hard_exclude`): the field **does not shrink**. Those SICs
   yield `sic_tier="review"`, and a `review` company still passes to Gate 2. What Gate 1 buys is a
   label on ~50 of the 80 saying "this SIC has no business being in this theme, look hard."
4. Gate 2 (LLM reads business descriptions): field drops to 3 to 5 true members. **This is the only
   step that removes anything.**
5. True members: companies manufacturing refractory ceramics, castables, or high-temperature industrial linings

The case established Gate 2 as a mandatory invariant, not an optional enhancement: with Gate 2
skipped, all ~80 names reach the deep-dive queue no matter how confidently Gate 1 tagged them, and
Gate 1 alone can never prevent that.

---

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
- XBRL concept_series (`us-gaap/companyfacts`): already works for foreign filers with
  SEC EDGAR registration. No change needed.

**Known gap / untested:** XBRL concept differences between 10-K and 20-F filers are
not systematically validated. Foreign filers may tag revenue under different us-gaap
concepts or use IFRS concepts (not covered by us-gaap companyfacts). If a 20-F filer
returns empty financials, this is the likely cause. Treat XBRL data for 20-F filers
as best-effort and flag for manual review.

**Verification:** killflag_scan tested on STNG (Scorpio Tankers, Marshall Islands
domicile, files 20-F), returns kf_scanned=True with filing_form="20-F" without crashing.

**Theme-selection note:** Themes whose pure-plays are structurally foreign-domiciled
(e.g. Marshall Islands tanker operators) now have partial coverage. Accept remaining
gaps explicitly or supplement with a manual list of known 20-F filers for the theme.

---

## Integration with Workflow

The discovery flow for `theme <keyword>` is:

```
discover.py (FTS, all keywords, merge by CIK)
    ↓
filter_by_sic.py (Gate 1: hard SIC exclusion)
    ↓
theme-fit-gate.js / subagent (Gate 2: LLM business-description classification)
    ↓
[pure_play + partial only] → cheap_pass.py → deepdive_data.py → deepdive-fanout
```

Do not insert any deepdive computation between FTS and Gate 2 completion. Do not run `deepdive_data.py` on a ticker that has not passed both gates.

---

## Cross-references

- `mechanical-checks.md`, Gate 2 depends on full 10-K text being read, not sampled; the "full-not-sampled" rule from invariant B also applies here.
- `judgment-rubric.md`, theme-fit dimension (dim 5) maps to Gate 2 output; `misrecall` companies should never appear in the rubric scoring phase.
- `data-sources.md`, EDGAR FTS rate limits and retry-backoff discipline apply to all FTS calls in `discover.py`.
- `event-driven.md`, for event-driven discovery (Form 10-12B spinoffs, cluster insider buys) that bypasses the theme-fit gate by using form-type enumeration instead of keyword FTS.
