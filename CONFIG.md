# small-cap-deepdive — Config

`small-cap-deepdive` is **config-bearing**: every tool reads its tuning parameters and the one
required EDGAR identity (`sec_user_agent`, your real name + email) from a JSON config resolved by
`tools/_common.py:load_config()`. This file is the authoritative config contract (config-spec E1).
Secrets / PII never enter git (Mode B, see below).

## Discovery convention (how the skill finds your config) — E2

`load_config()` builds the effective config as:

> **`reference/config.example.json` defaults**  ◁overlaid by◁  **your `config.json`**  ◁then◁  **`SMALLCAP_*` env scalar overrides`**

Your `config.json` is located in this order; the **first that exists wins**:

1. `$SMALL_CAP_DEEPDIVE_CONFIG_DIR/config.json` — environment variable (recommended; location-independent).
2. `$SMALL_CAP_DEEPDIVE_CONFIG/config.json` — accepted alias.
3. `~/.small-cap-deepdive-config/config.json` — dotfile-in-home fallback.
4. `~/.config/small-cap-deepdive-config/config.json` — XDG-style fallback (Linux/macOS).
5. `reference/config.json` — **in-repo legacy/default** (zero-config; what a fresh `cp` produces).

If none exists, the skill runs on `config.example.json` defaults alone — but EDGAR calls will 403
until `sec_user_agent` is set. Config is never a hard crash on import; the doctor tells you what's missing.

Per-scalar env overrides apply on top of whichever `config.json` won: `SMALLCAP_<KEY>` (UPPER_SNAKE of
the field), e.g. `SMALLCAP_MARKET_CAP_MAX=1000000000`. Run batching uses `SMALLCAP_RUN` (see SKILL.md).

## Schema — `config.json` (E1)

This skill uses a **flat `config.json`** rather than the MCP-tool `registry.json` shape from the
generalized config-spec — it ships no MCP-tool entries, only scalar tuning plus the one EDGAR identity.
The `schema_version` integer is the same contract tag `registry.json` carries (`schema_version`
top-level int): it pins the config major version so a future breaking change is detectable. The E1
requirement is that every field is documented (name · type · required? · default); a simpler skill MAY
define a smaller schema than `registry.json`'s `tools[]` so long as every field it reads is written down.

Only `sec_user_agent` is required at runtime; every other field has a default in `config.example.json`.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `schema_version` | int | no | `1` | Config-spec contract tag (E1; mirrors `registry.json`'s `schema_version`). Pins config major version; `verify_config.py` WARNs if it is not `1`. |
| `sec_user_agent` | string | **yes** (runtime) | — (placeholder in example) | EDGAR `User-Agent`; **PII** = real name + email, e.g. `"Jane Smith jane@x.com"`. Placeholder/empty → 403 from `efts.sec.gov`. `verify_config.py` reports it as a loud **WARN** (named, never echoed) so a freshly-stamped config is still structurally READY for the hot-swap test (E5); it is the one value you must fill before any live EDGAR call. |
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
companion config** (out-of-repo) — see `reference/data-sources.md §market-intel`; do not duplicate it here.

## Secrets / PII — Mode B (E6)

This skill keeps user state **out of git**, never as a committed file:

- `config.json` (holds your `sec_user_agent` PII) is **gitignored**; only `config.example.json` is tracked.
- `secrets/*` and `*.env` are gitignored (`secrets/README.md` is the only tracked file there).
- For full **repo separation**, point `$SMALL_CAP_DEEPDIVE_CONFIG_DIR` at a dir **outside** this public
  skill repo (e.g. `~/.small-cap-deepdive-config/`) — then no config/PII lives inside the repo at all.

## First-time setup (E3) — succeeds on the first try

```bash
pip install -r tools/requirements.txt

# 1. Stamp a conformant config.json from the example template (deterministic — E4).
#    Default writes the in-repo reference/config.json (zero-config); or pass --out for a private dir:
python scripts/init_config.py                       # -> reference/config.json
#   python scripts/init_config.py --out ~/.small-cap-deepdive-config   # out-of-repo (Mode B separation)

# 2. Edit config.json: set "sec_user_agent" to your real name + email (the one hard requirement).
#    If you used --out, point the skill at it:
#       export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/.small-cap-deepdive-config

# 3. Confirm it is ready (PASS/FAIL per field; PII never echoed):
python scripts/verify_config.py
```

## Switching between two configs (hot-swap) — E5

A config dir is self-contained (default `output_dir` is repo-relative, no hardcoded paths). Keep as
many config dirs as you like and switch by repointing the env var — nothing else changes:

```bash
export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/configs/conservative   # config A (e.g. lower market_cap_max)
export SMALL_CAP_DEEPDIVE_CONFIG_DIR=~/configs/aggressive     # config B — same skill, different state
```

Verify the swap: `python scripts/init_config.py --out ~/configs/A` and `--out ~/configs/B`, set
`sec_user_agent` in each, run `verify_config.py` against each (`--config-dir`), then flip the env var —
both must report **READY**.
