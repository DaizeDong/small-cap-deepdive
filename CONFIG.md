# small-cap-deepdive, Config

`small-cap-deepdive` is **config-bearing**: every tool reads its tuning parameters and the one
required EDGAR identity (`sec_user_agent`, your real name + email) from a JSON config resolved by
`tools/_common.py:load_config()`. This file is the authoritative config contract (config-spec E1).
Secrets / PII never enter git (Mode B, see below).

## Discovery convention (how the skill finds your config), E2

`load_config()` builds the effective config as:

> **`reference/config.example.json` defaults**  ◁overlaid by◁  **your `config.json`**  ◁then◁  **`SMALLCAP_*` env scalar overrides`**

Your `config.json` is located in this order; the **first that exists wins**:

1. `$SMALL_CAP_DEEPDIVE_CONFIG_DIR/config.json`, environment variable (recommended; location-independent).
2. `$SMALL_CAP_DEEPDIVE_CONFIG/config.json`, accepted alias.
3. `~/.small-cap-deepdive-config/config.json`, dotfile-in-home default.
4. `~/.config/small-cap-deepdive-config/config.json`, XDG-style default (Linux/macOS).
5. Nothing found: the skill is **NOT INITIALIZED**, and says so.

**There is no in-repo step, by design.** The list used to end with `reference/config.json`, described
as the zero-config in-repo default. That is the exact shape the data boundary bans: a real EDGAR
contact address once got committed through it. A fallback into the repo is not a convenience, it IS
the leak. `resolve_config_json()` returns `None` and `config_json_path()` raises
`ConfigNotInitialized` with setup instructions, mirroring `tools/datadir.py:data_path()`.

A **read** may degrade: with no `config.json`, `load_config()` runs on `config.example.json` defaults
alone, so import is never a hard crash, but EDGAR calls will 403 until `sec_user_agent` is set and
`verify_config.py` reports NOT READY. A **write** fails hard: `init_config.py` refuses a target
inside the repo.

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
| `schema_version` | int | no | `1` | Config-spec contract tag (E1; mirrors `registry.json`'s `schema_version`). Pins config major version; `verify_config.py` WARNs if it is not `1`. |
| `sec_user_agent` | string | **yes** (runtime) | none (placeholder in example) | EDGAR `User-Agent`; **PII** = real name + email, e.g. `"Jane Smith jane@example.com"`. Placeholder/empty → 403 from `efts.sec.gov`. `verify_config.py` reports it as a loud **WARN** (named, never echoed) so a freshly-stamped config is still structurally READY for the hot-swap test (E5); it is the one value you must fill before any live EDGAR call. |
| `output_dir` | string | no | `./reports/smallcap` | Report root. Repo-relative by default (no absolute-path leakage → portable). `SMALLCAP_RUN` adds a per-run subdir. |
| `market_cap_max` | int | no | `2000000000` | Deep-dive band ceiling (USD). |
| `watch_band_max` | int | no | `5000000000` | Watch band ceiling (USD). |
| `micro_cap_max` | int | no | `500000000` | Micro-cap tag threshold (USD). |
| `min_dollar_vol` | int | no | `100000` | Min avg daily dollar volume liquidity floor. |
| `sic_hard_exclude` | string[] | no | (regulated/biotech/financial SIC list) | Global SIC kill-list. Per-theme override via `sic_exclusion_blocks` (SKILL.md §Gate 1). |
| `python_cmd` | string | no | `python` | Interpreter used for spawned sub-tools. |
| `insider_source` | string | no | `openinsider` | `openinsider` (default, tested) or `edgar` (roadmap stub). |
| `wacc` | float | no | `0.10` | Reverse-DCF discount rate. |
| `cap_rate_low` | float | no | `0.09` | NAV cap-rate floor. |
| `cap_rate_high` | float | no | `0.12` | NAV cap-rate ceiling. |
| `normalize_years` | int | no | `5` | Earnings-normalization window. |
| `cyclical_cv_threshold` | float | no | `0.25` | Cyclicality CV gate for normalization. |

Optional API-key slots (`finnhub`, `fmp`, `alpha_vantage`) are documented in `reference/data-sources.md`
and are **not** part of `config.example.json`; if you use them, keep keys in `secrets/*.env` (Mode B),
never inline in `config.json`. The `twitterapi.io` credential is **reused from the `market-intel`
companion config** (out-of-repo), see `reference/data-sources.md §market-intel`; do not duplicate it here.

## Secrets / PII, Mode B (E6)

This skill keeps user state **out of git**, never as a committed file:

- `config.json` (holds your `sec_user_agent` PII) lives **outside this repo**, in
  `~/.small-cap-deepdive-config/` or wherever `$SMALL_CAP_DEEPDIVE_CONFIG_DIR` points. The repo
  tracks only `config.example.json`, the schema.
- `config.json` is also gitignored, but treat that as the backstop, not the control: `.gitignore` is
  advisory and `git add -f` walks straight through it. The control is that the file is not here.
- `secrets/*` and `*.env` are gitignored (`secrets/README.md` is the only tracked file there).
- Nothing resolves to a path inside the repo, so there is no in-repo config for a stray `git add`
  to catch. `verify_config.py` FAILs if `--config-dir` points inside the repo, and `init_config.py`
  refuses to write there.

## First-time setup (E3), succeeds on the first try

```bash
pip install -r tools/requirements.txt

# 1. Stamp a conformant config.json from the example template (deterministic, E4).
#    Default target is ~/.small-cap-deepdive-config, OUTSIDE this repo. A target inside the repo
#    is refused: config.json holds your EDGAR identity.
python scripts/init_config.py                       # -> ~/.small-cap-deepdive-config/config.json
#   python scripts/init_config.py --out ~/configs/aggressive   # any other out-of-repo dir

# 2. Edit config.json: set "sec_user_agent" to your real name + email (the one hard requirement).
#    ~/.small-cap-deepdive-config and the XDG dir are found automatically. For anywhere else:
#       export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/configs/aggressive

# 3. Confirm it is ready (PASS/FAIL per field; PII never echoed):
python scripts/verify_config.py
```

## Switching between two configs (hot-swap), E5

A config dir is self-contained (default `output_dir` is repo-relative, no hardcoded paths). Keep as
many config dirs as you like and switch by repointing the env var, nothing else changes:

```bash
export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/configs/conservative   # config A (e.g. lower market_cap_max)
export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/configs/aggressive     # config B — same skill, different state
```

Verify the swap: `python scripts/init_config.py --out ~/configs/A` and `--out ~/configs/B`, set
`sec_user_agent` in each, run `verify_config.py` against each (`--config-dir`), then flip the env var. Both must report
**READY**.
