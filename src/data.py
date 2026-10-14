"""
data.py — Where the model gets its raw historical facts.

Stage A (now): a hypothetical company, Maple Coffee Co., typed in by hand.
Stage B (later): functions that fetch real companies' data and return it in
exactly the same format, so nothing else in the model has to change.

Conventions (important!):
- All money values are in $ millions. Shares are in millions.
- Costs and cash outflows are stored as POSITIVE numbers
  (e.g. COGS = 328, not -328). Formulas subtract them explicitly.
- Columns are fiscal years, oldest on the left.
"""

from dataclasses import dataclass

import pandas as pd

SAMPLE_COMPANY_NAME = "Maple Coffee Co. (hypothetical)"
UNITS = "$ millions, shares in millions"

# Items that can legitimately be negative in real companies:
#   interest_expense - for real companies this is NET non-operating expense; interest income can exceed it
#   income_tax       - a tax benefit (refund) is negative
CAN_BE_NEGATIVE = {"interest_expense", "income_tax"}

# Every line item the model needs from the three financial statements.
REQUIRED_ITEMS: list[str] = [
    # Income statement
    "revenue",
    "cogs",
    "operating_expenses",        # includes D&A, as on most real income statements
    "interest_expense",          # interest + other non-operating expense, net
    "income_tax",
    # Cash flow statement
    "depreciation_amortization",
    "capex",
    # Balance sheet (value at fiscal year end)
    "accounts_receivable",
    "inventory",
    "accounts_payable",
    "cash",
    "total_debt",
    "preferred_stock",           # enter 0 if the company has none (never leave it out)
    "minority_interest",         # enter 0 if the company has none (never leave it out)
    # Share data
    "diluted_shares",
]


def load_sample_company() -> pd.DataFrame:
    """Return Maple Coffee Co.'s raw historical data (rows = line items, columns = years)."""
    years = [2022, 2023, 2024, 2025]

    raw = {
        # --- Income statement ---
        "revenue":                   [800.0, 880.0, 950.0, 1020.0],
        "cogs":                      [328.0, 356.0, 380.0,  403.0],
        "operating_expenses":        [336.0, 366.0, 395.0,  423.0],
        "interest_expense":          [ 23.0,  22.0,  20.0,   20.0],
        "income_tax":                [ 28.0,  34.0,  39.0,   44.0],
        # --- Cash flow statement ---
        "depreciation_amortization": [ 32.0,  35.0,  38.0,   41.0],
        "capex":                     [ 44.0,  48.0,  50.0,   53.0],
        # --- Balance sheet ---
        "accounts_receivable":       [ 40.0,  44.0,  47.0,   51.0],
        "inventory":                 [ 60.0,  65.0,  70.0,   74.0],
        "accounts_payable":          [ 50.0,  55.0,  58.0,   62.0],
        "cash":                      [150.0, 170.0, 185.0,  200.0],
        "total_debt":                [450.0, 430.0, 400.0,  400.0],
        "preferred_stock":           [  0.0,   0.0,   0.0,    0.0],
        "minority_interest":         [  0.0,   0.0,   0.0,    0.0],
        # --- Share data ---
        "diluted_shares":            [ 52.0,  51.5,  50.8,   50.0],
    }

    return pd.DataFrame.from_dict(raw, orient="index", columns=years)


def validate_historicals(df: pd.DataFrame) -> None:
    """Stop with a clear error if the raw data is incomplete or clearly wrong."""
    missing = [item for item in REQUIRED_ITEMS if item not in df.index]
    if missing:
        raise ValueError(f"Missing required line items: {missing}")

    if len(df.columns) < 2:
        raise ValueError("At least 2 historical years are needed to calculate growth.")

    if list(df.columns) != sorted(df.columns):
        raise ValueError("Years must be in order, oldest first.")

    required = df.loc[REQUIRED_ITEMS]

    has_blanks = required.isna().any(axis=1)
    if has_blanks.any():
        raise ValueError(f"Missing values in: {required.index[has_blanks].tolist()}")

    must_be_positive = required.drop(index=list(CAN_BE_NEGATIVE))
    has_negatives = (must_be_positive < 0).any(axis=1)
    if has_negatives.any():
        raise ValueError(
            f"Negative values in: {must_be_positive.index[has_negatives].tolist()}. "
            "Enter costs and outflows as positive numbers."
        )

    for item in ["revenue", "diluted_shares"]:
        if (df.loc[item] <= 0).any():
            raise ValueError(f"'{item}' must be greater than zero in every year.")


@dataclass
class MarketData:
    """Market information. It changes every trading day, so it always has a date."""

    share_price: float   # $ per share
    price_date: str      # the date the share price refers to


def load_sample_market_data() -> MarketData:
    """Return an illustrative share price for Maple Coffee Co."""
    return MarketData(share_price=30.00, price_date="2026-09-30")