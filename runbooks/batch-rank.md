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

Install `tools/requirements.txt` and follow [CONFIG.md](../CONFIG.md#secrets--pii-mode-b-e6)
for PRIVATE storage and current visibility receipts. Refresh the receipt during setup
when needed; ranking uses Git and the local receipt without invoking `gh` or the network.
Filesystem aliases, PUBLIC or unproved routes, and unversioned destinations are refused.

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

Set `REPORTS_ROOT` to the absolute path of an existing report directory in the PRIVATE
companion, or select an existing active run. Do not run `new_run.py` for re-ranking:
a new batch contains no prior reports. This command reads `report_*.md` from the selected
directory and writes the fresh ranking basename there under the same CONFIG rules.
Directory links and other filesystem aliases are refused.

To finalize a run and rebuild its ranking, use `tools/finalize_run.py` with the same `--input`.
Finalization chooses a fresh `RANKING.md` or `RANKING.finalized-<index>.md` artifact/receipt pair.
It proves the destination before repairing doubled output trees or writing verdicts.
Repair preserves duplicates and skips nested repositories and directory links. If the ranking
child fails, finalization exits nonzero and keeps the verdict file already written. `--no-rank`
skips the ranking child.

---

## Interpreting the Funnel Summary

Read the funnel summary with the ranking. Its counts describe the artifacts present in
the selected directory; completeness still depends on the associated source and stage receipts:

- **High sink rate (>50%):** Many deep-dive subjects rated AVOID or have kill-flags. Zero or
  few shortlist survivors can be a valid result for that observed set. Report scope and
  missing work before drawing conclusions about the wider theme.
- **Low candidate count:** Check FTS and configured SIC recall coverage, cheap-pass rejection
  reasons and explicit Gate 2 decisions. Gate 1 adds SIC review hints; it does not remove candidates.

---

## Troubleshooting

**`rank.py` produces empty output:** No `report_*.md` files found in the reports directory.
Confirm the path and that the deep-dive step has completed.

**Candidate appears in reports dir but not in output:** The candidate's report may not have
a parseable `评级:` line. Check the report format against `reference/judgment-rubric.md §Output Template`.
