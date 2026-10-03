# Documentation index

The current operating contract lives in [SKILL.md](../SKILL.md), the
[runbooks](../runbooks), and the [reference guides](../reference).

## Data and evidence boundaries

Real-run observations, decisions, reports, and research results are DATA. Keep them
versioned in the initialized PRIVATE companion. The distributable contains generic
methodology and generated synthetic examples; it has no repository fallback for DATA.

Read [evidence status](evidence-status.md) before making a performance or coverage claim.
Historical reports do not establish current implementation acceptance, unattended
completion, calibrated predictions, or a population error rate.

## Current contracts

- [Quote coverage and stale-price proxies](backtest-quote-coverage.md) distinguishes
  unavailable/error outcomes from observed returns and stale-price proxies.
- [Historical market-cap basis](backtest-market-cap-basis.md) describes dated shares,
  split normalization, and unresolved evidence that prevents a BUY.
- [Forward tracking](../reference/track-forward.md) describes precise return outcomes,
  unknown legacy rounding cases, review receipts, and calibration coverage.

Backtest cells retain point-in-time universe completion, observed and selected counts,
scope, and truncation. An incomplete or capped universe remains distinguishable from a
complete empty observation. Return coverage is a separate measure.

Forward-tracking writers retrieve quotes before the protected ledger update. A concurrent
ledger change rejects a stale score or backfill; reload and retry. If a crashed writer
leaves a private sibling lock, verify that no tracker writer is active before removing it.

## Historical analysis tools

The Python analysis tools in [backtest-2026-06](backtest-2026-06) read cells and write
features through the PRIVATE companion resolver. Retaining a tool does not validate
earlier results produced by it.

`distress_oos_validate.py` fits a logistic model on 2020 to 2022 and evaluates 2023 to 2024.
`distress_oos_validate2.py` ranks within each year. These are distinct protocols; neither
establishes the claimed leave-one-year-out refit protocol. Corrected bootstrap code still
requires a fresh run on validated private inputs.

A resume of the fast feature puller retains previous observations, including empty-series
failures that are absent from the current panel. Successful keys may be skipped, and a
retry replaces its keyed observation. This retention contract does not certify provider
availability or historical financial evidence.
