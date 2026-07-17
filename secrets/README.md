# secrets/, Mode B (gitignored)

Active storage mode: **B** (gitignored + out-of-band backup). Real secret/PII values never enter git.

This skill's per-user identity (`sec_user_agent`, your real name + email for the EDGAR User-Agent)
lives in **`config.json`** (gitignored), not here, see [../CONFIG.md](../CONFIG.md). For full repo
separation, keep `config.json` in an out-of-repo dir pointed to by `$SMALL_CAP_DEEPDIVE_CONFIG_DIR`.

Use this `secrets/` dir only for **optional API keys** (e.g. `finnhub`, `fmp`, `alpha_vantage`, see
`../reference/data-sources.md`). Create `secrets/<provider>.env` with `KEY=VALUE` pairs; files MUST be
UTF-8 without BOM. Everything under `secrets/` except this README is gitignored.

The `twitterapi.io` credential is **not** stored here, it is reused from the `market-intel`
companion config (out-of-repo); see `../reference/data-sources.md §market-intel`.

Back secrets up out-of-band (cloud sync / encrypted drive). Restore on a new machine by copying the
`*.env` files back, then run `python scripts/verify_config.py`.
