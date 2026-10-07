# small-cap-deepdive, Config

`small-cap-deepdive` is **config-bearing**: every tool reads its tuning parameters and the one
required EDGAR identity (`sec_user_agent`, your real name + email) from a JSON config resolved by
`tools/_common.py:load_config()`. This file is the authoritative config contract (config-spec E1).
Secrets stay outside the tool source; runtime DATA is versioned only in PRIVATE companions.

## Discovery convention (how the skill finds your config), E2

`load_config()` builds the effective config as:

> **`reference/config.example.json` defaults**  ◁overlaid by◁  **your `config.json`**  ◁then◁  **`SMALLCAP_*` env scalar overrides`**

The pinned `guards/tools/datadir.py` resolver chooses the companion. Explicit
`SMALL_CAP_DEEPDIVE_CONFIG_DIR` and `SMALL_CAP_DEEPDIVE_CONFIG` selectors take priority;
the resolver also supports its documented sibling and home-directory conventions.
`config.json` must exist in the resolved, versioned PRIVATE companion. The enclosing
Git repository and every configured remote's effective GitHub fetch and push destinations
are verified before config or output is used; the remote need not be named `origin`.
Missing config, a missing resolver, PUBLIC visibility and unknown visibility fail
with setup diagnostics. Initialize the pinned kit with
`git submodule update --init --recursive -- guards`.

Importing shared code and writers does not load configuration or create directories.
`load_config()` explicitly requires initialized configuration. `output_root()` returns
the absolute canonical PRIVATE reports root without creating output. Relative
`output_dir` values are relative to the companion; absolute paths and
`SMALLCAP_OUTPUT_DIR` undergo the same actual-destination proof, including links.
Runtime data is retained and versioned in PRIVATE companions.

Per-scalar env overrides apply on top of whichever `config.json` won: `SMALLCAP_<KEY>` (UPPER_SNAKE of
the field), e.g. `SMALLCAP_MARKET_CAP_MAX=1000000000`. Run batching uses `SMALLCAP_RUN` (see SKILL.md).

## Schema, `config.json` (E1)

This skill uses a **flat `config.json`** rather than the MCP-tool `registry.json` shape from the
generalized config-spec, it ships no MCP-tool entries, only scalar tuning plus the one EDGAR identity.
The `schema_version` integer is the same contract tag `registry.json` carries (`schema_version`
top-level int): it pins the config major version so a future breaking change is detectable. The E1
requirement is that every field is documented (name · type · required? · default); a simpler skill MAY
define a smaller schema than `registry.json`'s `tools[]` so long as every field it reads is written down.

Only `sec_user_agent` is required at runtime; every other field has a default in `config.example.json`.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `schema_version` | int | no | `1` | Config-spec contract tag (E1; mirrors `registry.json`'s `schema_version`). Pins config major version; `verify_config.py` fails if it is not `1`. |
| `sec_user_agent` | string | **yes** (runtime) | none (placeholder in example) | EDGAR `User-Agent`; **PII** = real name + email, e.g. the synthetic `"AcmeCorp user1@example.com"`. Placeholder/empty → 403 from `efts.sec.gov`. `verify_config.py` reports it as a loud **WARN** (named, never echoed) so a freshly-stamped config is still structurally READY for the hot-swap test (E5); it is the one value you must fill before any live EDGAR call. |
| `output_dir` | string | no | `./reports/smallcap` | Report root, relative to the verified PRIVATE companion by default. `SMALLCAP_RUN` adds a per-run subdir. |
| `market_cap_max` | int | no | `2000000000` | Deep-dive band ceiling (USD). |
| `watch_band_max` | int | no | `5000000000` | Watch band ceiling (USD). |
| `micro_cap_max` | int | no | `500000000` | Micro-cap tag threshold (USD). |
| `min_dollar_vol` | int | no | `100000` | Min avg daily dollar volume liquidity floor. |
| `sic_hard_exclude` | string[] | no | (regulated/biotech/financial SIC list) | SIC prefixes that put a company in Gate 1's **`review` tier**, not a kill-list: a match still passes to Gate 2 (`filter_by_sic.sic_classify`; SKILL.md §Two-Stage Precision Gate). **Global, with no per-theme key.** To run a theme against a different list, point `$SMALL_CAP_DEEPDIVE_CONFIG_DIR` at a second config dir (see "Switching between two configs"). |
| `python_cmd` | string | no | `python` | Interpreter used for spawned sub-tools. |
| `insider_source` | string | no | `openinsider` | `openinsider` (default, tested) or `edgar` (roadmap stub). |
| `wacc` | float | no | `0.10` | Reverse-DCF discount rate. |
| `cap_rate_low` | float | no | `0.09` | NAV cap-rate floor. |
| `cap_rate_high` | float | no | `0.12` | NAV cap-rate ceiling. |
| `normalize_years` | int | no | `5` | Earnings-normalization window. |
| `cyclical_cv_threshold` | float | no | `0.25` | Cyclicality CV gate for normalization. |

Optional API-key slots (`finnhub`, `fmp`, `alpha_vantage`) are documented in `reference/data-sources.md`
and are **not** part of `config.example.json`. Keep optional credentials in the verified PRIVATE
companion and configure the provider through its supported interface; this skill does not
automatically load arbitrary `.env` files. The `twitterapi.io` credential is **reused from the
`market-intel` companion config**, see `reference/data-sources.md §market-intel`.

## Secrets / PII, Mode B (E6)

Configuration and real runtime DATA belong in a versioned PRIVATE companion, outside the public tool source. Commit and push them there to retain history and recovery copies. Public-source ignore rules are only a backstop; they do not make a public directory private.

The destination proof resolves the actual enclosing Git worktree and checks all effective fetch and push URLs for every configured remote. It queries GitHub using an explicit host, so an ambient `GH_HOST` cannot substitute another server. No configured remotes, PUBLIC visibility and unknown visibility are errors. Existing `config.json` links, reparse points and hardlinks are refused before replacement.

## First-time setup (E3)

Run from the tool checkout. Create or clone the PRIVATE companion first; initialization does not create an unmanaged directory for personal data.

```bash
pip install -r tools/requirements.txt
gh repo create small-cap-deepdive-config --private
gh repo clone small-cap-deepdive-config "$HOME/.small-cap-deepdive-config"
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config"
python scripts/init_config.py
# After successful PRIVATE verification, edit sec_user_agent in the private config.
python scripts/verify_config.py --json
```

`--out` selects a directory within an existing PRIVATE worktree. With no explicit argument or config selector, initialization uses the same companion discovery as the runtime. Existing configuration is preserved unless `--force` is supplied. Repeated forced initialization writes the same template bytes; a complete temporary write precedes replacement.

After editing, commit and push the configuration in the PRIVATE companion. Runtime reports and observations belong in that same versioned private storage. A successful doctor checks local configuration and dependencies; it does not establish live service readiness.

## Switching between two configs (hot-swap), E5

Each config belongs to a verified PRIVATE companion; its default `output_dir` is companion-relative. Keep as
many config dirs as you like and switch by repointing the env var, nothing else changes:

```bash
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config/conservative"
# Switch to a second profile in this same verified PRIVATE worktree:
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config/aggressive"
```

Initialize each profile with `python scripts/init_config.py --out "$SMALL_CAP_DEEPDIVE_CONFIG_DIR"`, set
`sec_user_agent` in each, run `verify_config.py` against each (`--config-dir`), then flip the env var. Both must report
**READY**.

The JSON doctor returns `status`, `reports_root` and named `checks`. A ready result
covers local configuration, PRIVATE destination proof and declared dependency versions.
It does not claim live SEC, market or model readiness. No run or report directories
are created by these checks.

## Companion storage and retention

[storage.contract.json](storage.contract.json) declares companion-relative paths, their producers, consumers, recovery requirements and retirement conditions. Existing domain schemas above remain authoritative for field validation. Privacy classification in `.dataclass.json` does not establish retention.

The 64 MiB worktree budget is a review threshold, excluding Git metadata. Exceeding it requires examining dependencies, not discarding core data. Use the shared `skill-smith` storage-contract checker with this source checkout and its PRIVATE companion; no copy of the checker is vendored here. It inventories structure and retention declarations, not live provider readiness or recovery.

Keep every verdict row and all evidence required by active runs or retained reviews. Scorecards are derived. Final reports and their deepdive/valuation inputs remain in the companion; completed screening tables, development backtests and process logs may be retired when no retained report, review or active run depends on them. Never fabricate report hashes or completed review evidence for legacy records.

### Reviewed migrated metrics

The exact `imports/legacy-migrated-20260820/data/metrics/` ledger and scorecard
paths are declared separately from canonical metrics. Preserve original
imported verdict rows until lossless reconciliation and their required reference
closure are established; the canonical ledger is not assumed to replace them.
The imported scorecard is derived, but its compatibility and any unique
interpretation or restoration notes need review before retirement. Storage
inventory does not validate historical rows or prove regeneration.

An external migration can require a temporary recovery hold inside the shared
PRIVATE companion. The contract separately declares one exact database snapshot
and one recovery note, each capped at 1 MiB, while cutover and delta validation
are pending. They are neither a live database nor a small-cap verdict ledger.
No additional snapshots or notes inherit this hold. Once migration validation
closes, the external source owner must decide retirement and retain any
necessary final recovery conclusions. The snapshot's payload and live migration
procedure are governed by that owner rather than this skill's metric schemas.

### Exact report closure and budget review

Before releasing a historical report path, record the selected final report,
original judgment payload, deepdive/valuation input and each necessary local
reference in the current PRIVATE maintenance receipt. Active batches and
unresolved finalization or rollback dependencies stay protected. Original
verdict rows, imported attribution and supported evidence must not be removed
to meet the 64 MiB review budget.

Completed backtests, repeated downloads, raw screening copies and unreferenced
process files need individual dependency review and a reviewed split of the
broad declaration into disjoint ownership. Every path must match exactly one
artifact; an exact non-core pattern overlaid on a core glob cannot override it.
The broad report core patterns protect files until that closure is proved;
their presence is not a policy to archive every historical process file.
Migration bundles require unique code and restoration conclusions to be retained
by exact PRIVATE revision and receipt references before retirement review.
No new report archive or migration copy is needed. No cleanup or restore occurs
in this contract change. A budget excess remains a failed check until working
storage meets its reviewed bound.
