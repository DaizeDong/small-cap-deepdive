# Discovery Engine — Invariant A

> Single-keyword FTS over-recall is the most severe structural flaw in small-cap theme discovery.
> This doc is mandatory reading before invoking `discover.py` or designing new theme keywords.

---

## The Core Problem: Single-Keyword FTS Over-Recalls Severely

SEC full-text search (`efts.sec.gov`) returns every 10-K filing that mentions your keyword anywhere in the document. This sounds useful. In practice, precision is catastrophically low for short natural-language terms.

**Measured result from real runs:**
- Theme "AI agent" with natural keywords → 192 candidate tickers returned
- After the two-stage precision gate → 13 true theme members (6.8% precision)
- 94% of filings mentioned the keyword in unrelated contexts

**Real case — refractory swept all of biotech:**
The keyword `refractory` was used for a railcar insulation theme (refractory linings). In oncology, "refractory" means treatment-resistant cancer — every biotech and oncology company uses this word. The single-keyword FTS returned the entire biotech sector. Zero of these were railcar companies. The SIC gate reduced the field substantially, and the LLM theme-fit gate eliminated the remainder.

**Real case — railcar swept commodity logistics:**
`railcar` is used by grain, ethanol, potash, and other commodity shippers to describe their logistics. Build-A-Bear's annual report mentions railcar delivery. The term does not uniquely identify railcar manufacturers or lessors.

**Lesson: keyword match is not theme membership.** A company that mentions your keyword once in a risk factor or logistics discussion is not a theme member.

---

## The Two-Stage Precision Gate (Mandatory, Not Optional)

These two gates run sequentially before any deepdive computation. They cannot be skipped or combined.

### Gate 1 — SIC Coarse Exclusion (`filter_by_sic.py`)

**What it does:** Drops companies whose SIC code definitively places them outside plausible theme membership.

**SIC exclusion blocks (hard-coded defaults):**

| SIC Range | Description | Why excluded |
|---|---|---|
| 2833–2836 | Pharmaceutical preparations | Almost never industrial theme members |
| 38xx | Medical instruments | Medical devices, not industrial |
| 80xx | Health services | Hospitals, clinics |
| 737x | Computer programming/software | Excluded for non-tech themes |
| 6xxx | Finance, insurance, real estate | No industrial revenue |
| 5xxx | Retail trade | Distribution only |
| 3944 | Games, toys, children's vehicles | Appears in railcar/industrial recall |

**SIC missing → keep for LLM:** Companies with no SIC code on file are retained and passed to Gate 2. Do not auto-exclude them. Historical examples: NL Industries (NL, SIC 2810 chemicals) and VHI were initially misflagged — they are legitimate theme candidates with unusual SIC codes.

**Important:** These exclusion blocks are defaults and should be reviewed for each theme. A software theme would not exclude 737x. Config key `sic_exclusion_blocks` in `config.json` overrides defaults.

### Gate 2 — LLM Theme-Fit (`theme-fit-gate.js` / natural language subagent)

**What it does:** Reads the actual business description from the most recent 10-K and classifies each company as:
- `pure_play` — primary revenue source is directly from the theme
- `partial` — meaningful revenue exposure but not the core business
- `misrecall` — keyword appeared in unrelated context; not a theme member

**Only `pure_play` and `partial` pass to deepdive.**

**What to read:** The "Business" section (Item 1) of the most recent 10-K, not just the filing header. The SIC code and ticker are insufficient — the business description is authoritative.

**Required output per company:**
```
TICKER: <ticker>
classification: pure_play | partial | misrecall
reason: <one sentence citing specific business activity>
```

---

## FTS Keyword Design Rules

These rules prevent the zero-hit and over-recall failure modes.

**Rule 1: Use short, natural words — not multi-word exact phrases.**

SEC full-text search does not reliably match multi-word exact phrases. "DOT-117 tank car retrofit" will return zero hits because companies write "DOT-117" and "tank car" separately. Use `railcar` or `tank car` as separate short terms.

**Rule 2: Zero-hit guard is mandatory.**

If all keywords for a theme return zero filing hits, `discover.py` must write a placeholder result and exit cleanly — not crash with KeyError or attempt to proceed with an empty DataFrame. The zero-hit guard was added after a live crash encountered during development.

**Rule 3: Never sample — process full results.**

If a keyword returns 200 filings, process all 200 through the SIC gate and theme-fit gate. Sampling to save compute introduces survivorship bias and may drop true theme members that appear late in the result list. The `--full` flag is on by default; never override it to `--sample`.

**Rule 4: Use multiple keywords per theme.**

A theme about specialty chemicals should use 2–4 keywords covering different terminology the target companies use (e.g., `titanium dioxide`, `pigment`, `TiO2`). Merge by CIK after FTS to deduplicate.

---

## Refractory Case: Full Reconstruction

For reference, the complete failure mode and fix:

1. Keyword `refractory` submitted to FTS
2. FTS returns ~80 hits including biotech, oncology, pharma companies
3. Without Gate 1: all 80 pass to deepdive (wasted compute, contaminated ranking)
4. With Gate 1 (SIC 2833-2836, 80xx excluded): field drops to ~30
5. With Gate 2 (LLM reads business descriptions): field drops to 3–5 true members
6. True members: companies manufacturing refractory ceramics, castables, or high-temperature industrial linings

The case established the two-stage gate as a mandatory invariant, not an optional enhancement.

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

- `mechanical-checks.md` — Gate 2 depends on full 10-K text being read, not sampled; the "full-not-sampled" rule from invariant B also applies here.
- `judgment-rubric.md` — theme-fit dimension (dim 5) maps to Gate 2 output; `misrecall` companies should never appear in the rubric scoring phase.
- `data-sources.md` — EDGAR FTS rate limits and retry-backoff discipline apply to all FTS calls in `discover.py`.
