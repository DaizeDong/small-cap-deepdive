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
| `--input <dir>` | REPORTS from config | Initialized absolute path to the reports directory in a verified PRIVATE companion |
| `--output <name>` | `RANKING.md` | Fresh ranking basename within that run; the artifact and its receipt must not already exist |

**AVOID/kill-flag sink logic:** Candidates rated AVOID or with kill-flag count ≥ 2 are
automatically sunk to the bottom of the ranking, this cannot be overridden by other flags.
This is the primary guard against narrative-driven score inflation.

---

## Step 1, Basic Re-Rank (default weights, all reports)

```bash
python tools/rank.py --output RANKING-rerun-01.md
```

Output: `RANKING-rerun-01.md` inside the selected companion run directory, with its
stage receipt. Choose a new basename for each re-rank. Omitting `--output` selects
`RANKING.md` and is suitable only when that output and its receipt do not already exist.
The table includes ratings, financial evidence, kill flags, and the funnel coverage summary.

**Token magnitude:** Zero, deterministic sort + table generation.
Runtime: <5 seconds.

---

## Step 2, Re-Rank by Theme Slug

```bash
python tools/rank.py --slug railcar --output RANKING-railcar-rerun-01.md
```

Includes only `report_railcar_*.md` files (slug-scoped). If no slug-scoped files exist,
falls back gracefully to all `report_*.md`.

---

## Step 3, Re-Rank from a Custom Directory

```bash
python tools/rank.py --input "${REPORTS_ROOT}" --output RANKING-rerun-02.md
```

Initialize `REPORTS_ROOT` to the absolute PRIVATE run path as shown in `theme-run.md` before
running this command. It reads `report_*.md` from that directory and writes the specified
fresh ranking basename there. The actual destination repository must be PRIVATE, including
when the supplied path contains a directory link.

To finalize a run and rebuild its ranking, use `tools/finalize_run.py` with the same `--input`.
Finalization chooses a fresh `RANKING.md` or `RANKING.finalized-<index>.md` artifact/receipt pair.
It proves the destination before repairing doubled output trees or writing verdicts.
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
- **Low candidate count:** Check FTS and configured SIC recall coverage, cheap-pass rejection
  reasons and explicit Gate 2 decisions. Gate 1 adds SIC review hints; it does not remove candidates.

---

## Troubleshooting

**`rank.py` produces empty output:** No `report_*.md` files found in the reports directory.
Confirm the path and that the deep-dive step has completed.

**Candidate appears in reports dir but not in output:** The candidate's report may not have
a parseable `评级:` line. Check the report format against `reference/judgment-rubric.md §Output Template`.
