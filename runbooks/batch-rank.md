# Runbook: Batch Re-Rank

> Entry mode 3 — `rank`. Use when you have already run a theme screen and want to re-sort or
> re-weight an existing scored candidate set without re-running discovery or deep-dive.

This entry mode is instant (no network, no LLM). It operates on the scored JSON output from
a prior theme run. Use it to: apply a different weight profile, surface candidates by a
specific dimension, or produce a clean ranked table from a prior session's output.

---

## Prerequisites

You must have a prior theme run's scored outputs. These live in the directory you passed
to the deep-dive step — typically `reports/<theme>_scores/` or a single consolidated JSON.

```
reports/
  railcar_scores/
    GBX.json
    RAIL.json
    ...
```

No installation beyond `pip install -r tools/requirements.txt` is needed for re-ranking.
No network access or config required.

---

## Step 1 — Basic Re-Rank (default weights)

```bash
python tools/rank.py \
  --scores-dir reports/railcar_scores/ \
  --out reports/railcar_ranked.md
```

Or from a consolidated JSON (the output of `deepdive-fanout.js`):

```bash
python tools/rank.py \
  --input reports/railcar_all_scores.json \
  --out reports/railcar_ranked.md
```

Expected output (Markdown table):

```
# Ranked Candidates — railcar leasing (2025-06-18)

Rank  Ticker  Composite  Dim1  Dim2  Dim3  Dim4  Dim5  Dim6  Dim7  Flags
1     GBX     4.1        4     5     4     3     4     4     4     —
2     RAIL    3.8        4     4     3     4     4     3     4     —
3     TRN     3.5        4     3     3     3     4     3     4     —
4     AMER    3.2        3     4     3     3     3     3     3     —
5     FREYR   2.6        3     3     2     2     3     2     3     material_weakness(dim5)
...

Gate funnel: 187 raw → 98 (Gate 1) → 22 (Gate 2) → 19 (cheap_pass) → 19 scored
Eliminated at gate: 3 (going_concern: 1, death_spiral: 1, cheap_pass: 1)
Composite ≤ 2 (omitted from shortlist): 2
Coverage gaps: 2 tickers — partial XBRL, Dim 1 confidence capped at 40%
```

**Token magnitude:** Zero — deterministic sort + table generation.
Runtime: <5 seconds.

---

## Step 2 — Re-Rank with Custom Weights

Override dimension weights to change what the ranking optimizes for:

```bash
python tools/rank.py \
  --scores-dir reports/railcar_scores/ \
  --weight-overrides '{"dim1": 0.30, "dim4": 0.25, "dim2": 0.15, "dim3": 0.10, "dim5": 0.10, "dim6": 0.05, "dim7": 0.05}' \
  --out reports/railcar_ranked_financial_heavy.md
```

Default weights and dimension definitions are in `reference/judgment-rubric.md`.
Weights must sum to 1.0; the tool validates and errors if they do not.

**When to override weights:**

- **Increase Dim 4 (insider behavior):** when you are specifically interested in management
  alignment signals — useful for deep cyclicals where insiders have a track record of
  buying near cycle troughs.
- **Increase Dim 1 (financial quality):** when cash-generation discipline is the primary
  screen — useful for themes where speculative concept-players dominate the field.
- **Increase Dim 2 (theme fit):** rarely needed, but useful if Gate 2 let through a large
  number of `tangential` companies and you want to surface the `pure_play` tier.

---

## Step 3 — Sort by a Single Dimension

```bash
python tools/rank.py \
  --scores-dir reports/railcar_scores/ \
  --sort-by dim4 \
  --out reports/railcar_ranked_by_insider.md
```

Useful for targeted review: "Which of these passed candidates have the strongest insider buy
signal?" or "Which have the cleanest balance sheets?"

---

## Step 4 — Show Only Top-N

```bash
python tools/rank.py \
  --scores-dir reports/railcar_scores/ \
  --top 5 \
  --out reports/railcar_top5.md
```

Produces the shortlist only, with the same gate funnel summary footer.

---

## Step 5 — Include Eliminated Candidates

By default `rank.py` omits candidates eliminated at `cheap_pass` and those with composite ≤ 2.
To include them (useful for reviewing the full field):

```bash
python tools/rank.py \
  --scores-dir reports/railcar_scores/ \
  --include-eliminated \
  --out reports/railcar_full.md
```

Eliminated candidates appear with a `ELIMINATED` composite and the kill-flag reason.
Candidates with composite ≤ 2 appear with a `BELOW-THRESHOLD` marker.

---

## Step 6 — Re-Rank After Manual Score Override

If you manually revised a score (e.g., after human research uncovered additional information),
update the candidate's JSON file:

```json
{
  "ticker": "GBX",
  "dim1": 4,
  "dim2": 5,
  "dim3": 4,
  "dim4": 3,
  "dim5": 4,
  "dim6": 4,
  "dim7": 4,
  "manual_override": true,
  "override_note": "Revised Dim 4 down from 4 to 3: confirmed CEO sold $2.1M in Dec 2024 concurrent with secondary offering (Form 4 cross-check)."
}
```

Then re-run `rank.py`. The `manual_override` flag is surfaced in the table output so the
override is visible and auditable.

---

## When to Use Each Mode

| Situation | Command |
|---|---|
| First ranking after a theme run | `rank.py --scores-dir <dir>` |
| Testing a different weight profile | Add `--weight-overrides` |
| Quick glance at top candidates | Add `--top 5` |
| Presenting a clean shortlist | Add `--top 10 --out report.md` |
| Auditing the full field including eliminated | Add `--include-eliminated` |
| Surfacing insider-alignment leaders | `--sort-by dim4` |

---

## Interpreting the Funnel Summary

The funnel summary at the bottom of every `rank.py` output is as important as the ranking
table itself:

```
Gate funnel: 187 raw → 98 (Gate 1) → 22 (Gate 2) → 19 (cheap_pass) → 19 scored
Eliminated: 3 | Composite ≤ 2: 2 | Shortlist: 17
```

- **High Gate 2 drop rate** (>80% false-positives): the theme keyword is generic. The FTS
  over-recall is working as designed; the precision gate is doing real work.
- **High cheap_pass elimination rate** (>30% of Gate 2 survivors): the theme's small-cap
  universe is structurally distressed — many of these companies exist because they raised
  cheap capital on theme hype. Zero or few shortlist survivors is a valid output.
- **High composite ≤ 2 rate**: the Gate 2 survivors that passed cheap_pass are nonetheless
  weak on fundamentals. This is the "0-buy" scenario — a completely valid and informative result.

The funnel numbers are machine-verifiable truth. The ranking is judgment applied to that truth.
Both matter; the funnel tells you whether the judgment is operating on a clean or compromised
candidate set.

---

## Troubleshooting

**`rank.py: no scores found`:** Confirm the path to `--scores-dir` is correct and that the
JSON files have the expected schema (at minimum: `ticker`, `dim1`–`dim7` keys).

**Weights do not sum to 1.0:** The tool errors with a clear message. Adjust and rerun.

**Candidate appears in scores dir but not in output:** The candidate was eliminated at
`cheap_pass` (kill-flag) or scored composite ≤ 2. Run with `--include-eliminated` to confirm.
