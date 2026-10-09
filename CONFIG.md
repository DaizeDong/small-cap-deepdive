# small-cap-deepdive, Config

`small-cap-deepdive` is **config-bearing**: every tool reads its tuning parameters and the one
required EDGAR identity (`sec_user_agent`, your real name + email) from a JSON config resolved by
`tools/_common.py:load_config()`. This file is the authoritative config contract (config-spec E1).
Secrets stay outside the tool source; runtime DATA is versioned only in PRIVATE companions.

## Discovery convention (how the skill finds your config), E2

`load_config()` builds the effective config as:

> `reference/config.example.json` defaults → selected private `config.json` → `SMALLCAP_*` scalar environment overrides

The pinned `guards/tools/datadir.py` resolver selects one root for configuration,
reports, initialization and tracking. The order is `SMALL_CAP_DEEPDIVE_DATA_DIR`,
`SMALL_CAP_DEEPDIVE_CONFIG`, `SMALL_CAP_DEEPDIVE_CONFIG_DIR`, a sibling
`small-cap-deepdive-config`, `~/.small-cap-deepdive-config`, then
`~/.small-cap-deepdive-data`. A DATA override must name the exact `data/` child;
root lookup removes that terminal component. Tracking always uses
`<companion>/data/metrics`, even before `data/` exists. Explicit initializer
`--out` and doctor `--config-dir` select the root for that command before the environment.

Each selected configuration root must be the exact root of an existing PRIVATE
Git worktree. Nested configuration profiles are unsupported and are refused
before writes. All physical and effective fetch/push destinations need current
PRIVATE receipts. Missing explicit directories, config, resolver or proof fail.
Initialize the kit with `git submodule update --init --recursive -- guards`.

Importing shared code and writers does not load configuration or create directories.
`load_config()` explicitly requires initialized configuration. `output_root()` returns
the absolute canonical PRIVATE reports root without creating output. Relative
`output_dir` values are relative to the companion; absolute paths and
`SMALLCAP_OUTPUT_DIR` undergo the same actual-destination proof, including links.
`make_report.py --out` can select a different verified PRIVATE companion, subject to the
same destination proof and declared report-artifact ownership. Runtime DATA remains
versioned in PRIVATE companions.

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
| `sec_user_agent` | string | **yes** (runtime) | none (placeholder in example) | EDGAR `User-Agent`; **PII** = real name + email, e.g. the synthetic `"AcmeCorp user1@example.com"`. Placeholder/empty → 403 from `efts.sec.gov`. `verify_config.py` returns **NOT READY** for a blank or example identity without echoing its value. Fill it privately before live EDGAR use; offline readiness does not establish SEC acceptance. |
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

The destination proof resolves the actual enclosing Git worktree and checks all effective fetch and push URLs for every configured remote. It uses the shared current visibility receipt and resolves Git destinations locally; no network request is part of artifact admission. No configured remotes, PUBLIC visibility and unknown visibility are errors. Existing `config.json` links, reparse points and hardlinks are refused before replacement.

SSH companion origins may use aliases declared by ordinary `Host` and `HostName github.com`
rules in `~/.ssh/config`. Verification reads the file locally, uses the first matching
`HostName`, and never runs SSH or configured commands. Literal `github.com` hosts are also
checked for local rewrites. Configurations using `Include`, `Match` or hostname
canonicalization are refused; use a literal HTTPS GitHub origin in those cases. HTTPS
origins must name `github.com` directly. Existing hardlinked output files are refused.

## First-time setup (E3)

Run from the tool checkout. Create or clone the PRIVATE companion first; initialization does not create an unmanaged directory for personal data.

```bash
pip install -r tools/requirements.txt
gh repo create small-cap-deepdive-config --private --add-readme
gh repo clone small-cap-deepdive-config "$HOME/.small-cap-deepdive-config"
export SMALL_CAP_DEEPDIVE_CONFIG_DIR="$HOME/.small-cap-deepdive-config"
python scripts/init_config.py
# After successful PRIVATE verification, edit sec_user_agent in the private config.
python scripts/verify_config.py --json
```

`--out` selects an existing PRIVATE worktree root. Without it, initialization uses the runtime discovery order above, including the DATA override. Existing configuration is preserved unless `--force` is supplied. Repeated forced initialization writes the same template bytes; a complete temporary write precedes replacement.

After editing, commit and push the configuration in the PRIVATE companion. Runtime reports and observations belong in that same versioned private storage. A successful doctor checks local configuration and dependencies; it does not establish live service readiness.

## Switching between two configs (hot-swap), E5

Each profile belongs to a separate PRIVATE worktree root. For example, select
`~/configs/smallcap-conservative` or `~/configs/smallcap-aggressive` after creating
and proving each independent PRIVATE worktree. Do not place these as subdirectories
inside one companion. Unset DATA and unused CONFIG aliases when switching, then set
`SMALL_CAP_DEEPDIVE_CONFIG` to the intended root. Initialize with `--out`, fill
`sec_user_agent` privately, and run `verify_config.py --config-dir <root> --json`.

The JSON doctor returns `ready`, `status`, `resolved_root`, `reports_root` and named `checks`. A ready result
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
Retirement review does not require a new report archive or migration copy and does not
authorize cleanup or restoration. A budget excess remains a failed check until working
storage meets its reviewed bound.

The machine-readable lifecycle adapter is [config.contract.json](config.contract.json).
Writers call the pinned Guards artifact admission before creating a destination:
undeclared, retired and ignored durable paths fail. Configuration and verdict
staging files have narrow transient owners; they remain protected while a writer
or interrupted recovery needs them. Supported report writes stay within declared
`reports/smallcap/**`; custom locations need a reviewed source contract first.
Report writers are bound to the current-report artifact and cannot replace
configuration or tracking files. Configuration and tracking writers bind their
own artifact IDs. Path aliases are refused before canonical path resolution.
