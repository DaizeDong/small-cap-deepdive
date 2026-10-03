# Optional provider credentials

This source directory contains documentation only. Real configuration, identity and credentials
belong in an initialized, versioned PRIVATE companion outside the public tool checkout.

Follow [the configuration setup](../CONFIG.md#first-time-setup-e3) to select and verify that
companion. Its `config.json` holds the EDGAR `sec_user_agent`. Optional provider credentials may
be stored in a `secrets/` directory inside the verified PRIVATE companion and loaded through the
provider's supported configuration interface. The skill does not automatically load arbitrary
`.env` files. Public-source ignore rules do not establish private storage.

The `twitterapi.io` credential is reused through the `market-intel` companion configuration;
see [data sources](../reference/data-sources.md). Do not duplicate that credential in this checkout.

Commit and push operational configuration and credentials only in the PRIVATE companion to retain
history and a recovery copy. Restore that private repository on a new machine, select it through
`SMALL_CAP_DEEPDIVE_CONFIG_DIR`, and run `python scripts/verify_config.py`. Never copy its real
configuration or credential files into this source directory.
