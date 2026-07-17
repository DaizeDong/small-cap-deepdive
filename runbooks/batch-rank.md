# Runbook: Batch Re-Rank

> Entry mode 3, `rank`. Use when you have already run a theme screen and want to re-sort
> an existing scored candidate set without re-running discovery or deep-dive.

This entry mode is instant (no network, no LLM). It operates on `report_*.md` files written
by the deep-dive judgment step. Use it to produce a clean ranked table from a prior session's
output.

---

## Prerequisites

You must have a prior theme run's deep-dive report files. These live in the REPORTS directory
(default `reports/smallcap/`) as `report_<ticker>.md` files.

```
reports/smallcap/
  report_GBX.md
  report_RAIL.md
  deepdive_GBX_2026-06-18.json
  deepdive_RAIL_2026-06-18.json
  ...
```

No installation beyond `pip install -r tools/requirements.txt` is needed for re-ranking.
No network access or config required.

---

## Available Flags

`rank.py` supports the following flags:

| Flag | Default | Description |
|---|---|---|
| `--slug <s>` | (none) | Filter to `report_<slug>_*.md` files; falls back to all `report_*.md` if none match |
| `--input <dir>` | REPORTS from config | Path to the reports directory |

**AVOID/kill-flag sink logic:** Candidates rated AVOID or with kill-flag count ≥ 2 are
automatically sunk to the bottom of the ranking, this cannot be overridden by other flags.
This is the primary guard against narrative-driven score inflation.

---

## Step 1, Basic Re-Rank (default weights, all reports)

```bash
python tools/rank.py
```

Output: `reports/smallcap/RANKING.md`

Expected output (Markdown table):

```
# 小盘深度调研排序 — 2026-06-18

> 漏斗: 19 召回 → 19 小盘候选 → cheap pass 幸存 19 →
> 19 家微盘逐一 deep dive。AVOID/kill-flag≥2 一律沉底。

## 排序
| 排名 | 代码 | 评级 | 置信 | 营收 | 净利 | OCF | 增速 | 稀释 | 内部人 | kill-flag |
...
```

**Token magnitude:** Zero, deterministic sort + table generation.
Runtime: <5 seconds.

---

## Step 2, Re-Rank by Theme Slug

```bash
python tools/rank.py --slug railcar
```

Includes only `report_railcar_*.md` files (slug-scoped). If no slug-scoped files exist,
falls back gracefully to all `report_*.md`.

---

## Step 3, Re-Rank from a Custom Directory

```bash
python tools/rank.py --input reports/railcar_scores/
```

Reads `report_*.md` from the specified directory instead of the default REPORTS path.
Output is written to `<input_dir>/RANKING.md`.

---

## Interpreting the Funnel Summary

The funnel summary at the bottom of every `rank.py` output is as important as the ranking
table itself. The numbers are machine-verifiable truth computed from actual files present:

- **High sink rate (>50%):** Many deep-dive subjects rated AVOID or have kill-flags. Zero or
  few shortlist survivors is a completely valid output, a theme's small-cap universe may
  simply be structurally distressed.
- **Low candidate count:** The Gate 1/2 filters were aggressive. Check theme keywords and
  SIC exclusion blocks if the funnel is unexpectedly empty.

---

## Troubleshooting

**`rank.py` produces empty output:** No `report_*.md` files found in the reports directory.
Confirm the path and that the deep-dive step has completed.

**Candidate appears in reports dir but not in output:** The candidate's report may not have
a parseable `评级:` line. Check the report format against `reference/judgment-rubric.md §Output Template`.
