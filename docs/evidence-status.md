# Evidence status

Code review, synthetic controls, current execution, and historical research answer
different questions. Report their scope separately.

## Current implementation

A static review can establish what the inspected source does and identify defects.
A synthetic regression can show behavior for its constructed cases. Neither proves
current provider behavior, successful installation, or valid investment conclusions.

The deepdive_data and valuation legacy selftest wrappers use generated financial inputs
and synthetic acquisition envelopes. They cannot establish live provider availability.
The cheap_pass selftest still initializes EDGAR and requests issuer filings; it includes
live acquisition and must not be described as offline or synthetic-only. Provider acceptance
requires explicit inputs, source-completion checks and the initialized PRIVATE companion.

An execution report must bind the tested source, collect the current test roster, and
reconcile every required result. A partial run, an empty observation set, or an unexecuted
lane is not full acceptance. State unresolved external-source and installation checks.

## Historical research

Real-run inputs and reports belong in the versioned PRIVATE companion. Preserve originals
and their provenance before recomputation; do not silently edit past decisions or present
renamed real observations as synthetic fixtures.

Historical claims require complete dated issuer eligibility, universe scope, financial
provenance, quote coverage, and the exact evaluation protocol. The existing logistic
train/test script and the separate within-year ranking script must not be described as
a proved leave-one-year-out refit evaluation.

Keep these limitations distinct:

- **Units:** `margin_of_safety_pct` is a fraction with market cap as denominator.
  Display it as a percentage only after multiplying by 100. Conflicting units in a report
  invalidate inferences about threshold crossings until the private inputs are reconciled.
- **Interventions:** interrupted processes, manual state changes, changed queries, and
  `--allow-missing` completion affect the observed protocol. Disclose them; a later output
  does not establish unattended success of the original run.
- **Coverage:** caps, missing keyword pages, unavailable sources, and selection limits
  restrict the observed universe. Processing all retained rows does not prove uncapped
  population coverage.

Do not invent corrected historical outcomes from a prose report. Recompute against the
preserved source artifacts and record the resulting differences.

## Calibration

Calibration tooling and adjudication receipts do not establish realized calibration.
Use observed forward returns, precise outcomes, and explicit known/missing coverage.
Legacy rounded values at a decision boundary remain unknown. An unscored cohort cannot
support a calibrated-scanner or predictive-edge claim.
