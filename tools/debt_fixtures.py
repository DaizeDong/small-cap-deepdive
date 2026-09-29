"""Generate synthetic contractual-debt evidence, independent of company data."""


def debt_scenarios():
    """Balanced statements with debt, non-debt liabilities, and missing-tag controls."""
    million = 1_000_000
    end = "2025-12-31"

    def series(amount, date=end):
        return [{"end": date, "val": amount}]

    components = {
        "LongTermDebtNoncurrent": 16 * million,
        "LongTermDebtCurrent": 2 * million,
        "ShortTermBorrowings": million,
        "FinanceLeaseLiabilityNoncurrent": 750_000,
        "FinanceLeaseLiabilityCurrent": 250_000,
    }
    reported = sum(components.values())
    assets = series(500 * million)
    equity = series(100 * million)
    liabilities = series(400 * million)
    concepts = {
        name: series(amount) for name, amount in components.items()
    }
    concepts.update({
        "Assets": assets,
        "StockholdersEquity": equity,
        "Liabilities": liabilities,
        "CashAndCashEquivalentsAtCarryingValue": series(30 * million),
    })
    return {
        "ticker": "SYNTH",
        "cik": "0000000001",
        "date": end,
        "old_date": "2020-12-31",
        "reported": reported,
        "assets": assets,
        "equity": equity,
        "liabilities": liabilities,
        "components": concepts,
        "component_names": list(components),
        "unknown": {name: rows for name, rows in concepts.items() if name not in components},
        "lease": 10 * million,
        "second_debt": 300 * million,
        "amount_cases": [
            {"name": "small", "amount": reported, "expected": reported},
            {"name": "zero", "amount": 0, "expected": 0},
            {"name": "missing", "amount": None, "expected": None},
            {"name": "large", "amount": 300 * million, "expected": 300 * million},
            {"name": "negative", "amount": -million, "expected": None},
        ],
    }
