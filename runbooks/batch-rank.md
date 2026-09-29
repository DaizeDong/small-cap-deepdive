# Runbook: Batch Re-Rank

> Entry mode 3, `rank`. When to use it: `SKILL.md` §Entry 3.
> This runbook is the operational how-to for that entry, not a second statement of it.

This entry mode makes no model or finance-data calls. It operates on `report_*.md` files written
by the deep-dive judgment step. Use it to produce a clean ranked table from a prior session's
output.

---

## Prerequisites

You must have a prior theme run's deep-dive report files in the configured PRIVATE companion.
The default REPORTS directory combines that companion's output directory with the active
`SMALLCAP_RUN`, if set. Report files use the name `report_<ticker>.md`.

```
<private-companion>/<configured-output>/<active-run>/
  report_<ticker>.md
  deepdive_<ticker>_<date>.json
  ...
```

Install `tools/requirements.txt` and configure the companion as described in `CONFIG.md`.
Working Git and authenticated `gh` commands are required to prove the canonical output
destination belongs to a PRIVATE GitHub worktree. Visibility verification can use the
network. PUBLIC, unknown, unusable, or unversioned destinations are refused before writing.

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

Output: `RANKING.md` inside the selected companion run directory.

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
python tools/rank.py --input "<private-companion>/reports/smallcap/<run>"
```

Replace the placeholders with your companion path and run name. Reads `report_*.md` from
that directory and writes `<input_dir>/RANKING.md`. The actual destination repository must
be PRIVATE, including when the supplied path contains a directory link.

To finalize a run and rebuild its ranking, use `tools/finalize_run.py` with the same `--input`.
Finalization proves the destination before repairing doubled output trees or writing verdicts.
Repair preserves duplicates and skips nested repositories and directory links. If the ranking
child fails, finalization exits nonzero and keeps the verdict file already written. `--no-rank`
skips the ranking child.

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
