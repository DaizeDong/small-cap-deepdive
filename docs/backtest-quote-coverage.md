# Backtest quote coverage

The default return lookup first resolves an entry close from the 14 days ending
on the as-of date. The exit query covers the resolved entry date through the
calendar-month target date, inclusive. The provider's exclusive end is the next
calendar day. A quote more than 14 days before the target can therefore still
contribute to the result.

The provider path uses `Ticker.history(..., raise_errors=True)` to retain raised
retrieval failures. Returned rows are checked before selection: dates must be
valid and inside the requested interval, and prices must be finite, positive
numbers. The latest valid date wins regardless of row order. Invalid rows and
out-of-window rows are counted. Conflicting prices for the same date make the
lookup invalid. Injected quote functions receive equivalent value/date checks.

| Result | Meaning |
| --- | --- |
| `ok`, `observed_close` | A valid adjusted close was observed within 45 days of the target. |
| `ok`, `stale_quote_proxy` | The last observed adjusted close is older than 45 days. |
| `no_entry_price` / `no_exit_price` | Retrieval succeeded without an eligible quote. |
| `invalid_entry_price` / `invalid_exit_price` | The returned quote or history failed validation. |
| `provider_error` | The provider raised an exception; `error_stage` identifies entry or exit. |

A stale quote does not establish that a company delisted or that an investor
received its quoted price. Results retain `exit_date`, `exit_quote_age_days`,
`return_kind`, and `terminal_status="unknown"`. The historical
`realized_to_last_close` field remains a compatibility alias for the stale-proxy
condition; its name must not be interpreted as evidence of a realized sale.

Cell, bucket and loss summaries expose the full population as fresh observations,
stale proxies, missing quotes, provider errors, invalid values and pipeline
errors. These categories sum to the population. Combined estimates retain valid
proxies and identify their inclusion through `estimate_basis`; separate cohort
statistics show how much of the return and loss evidence comes from proxies.
Missing and invalid observations remain in the population without becoming zero
returns. Loss counts measure endpoint losses, not maximum intra-period drawdown.

This change does not establish complete historical provider coverage, confirmed
terminal values, or executable sale prices. The separate market-cap contract uses
dated share evidence and split normalization; unresolved inputs prevent a usable
estimate. See `backtest-market-cap-basis.md`. This does not supply the missing dated
eligibility contract: historical eligibility currently abstains. Live provider
coverage and full backtest acceptance require separate validation.
