"""
historicals.py — Turns raw historical facts into a full set of financials and ratios.

data.py answers "what are the numbers?".
historicals.py answers "what do the numbers tell us?".
This file works the same whether the data is hypothetical or real.
"""

import pandas as pd


def build_historical_statements(raw: pd.DataFrame) -> pd.DataFrame:
    """Calculate subtotals (gross profit, EBIT, EBITDA, net income, NWC) from raw inputs."""
    revenue = raw.loc["revenue"]
    cogs = raw.loc["cogs"]
    opex = raw.loc["operating_expenses"]
    d_and_a = raw.loc["depreciation_amortization"]

    gross_profit = revenue - cogs
    ebit = gross_profit - opex
    ebitda = ebit + d_and_a
    pretax_income = ebit - raw.loc["interest_expense"]
    net_income = pretax_income - raw.loc["income_tax"]

    nwc = raw.loc["accounts_receivable"] + raw.loc["inventory"] - raw.loc["accounts_payable"]

    statements = {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "operating_expenses": opex,
        "ebit": ebit,
        "depreciation_amortization": d_and_a,
        "ebitda": ebitda,
        "interest_expense": raw.loc["interest_expense"],
        "pretax_income": pretax_income,
        "income_tax": raw.loc["income_tax"],
        "net_income": net_income,
        "capex": raw.loc["capex"],
        "net_working_capital": nwc,
        "change_in_nwc": nwc.diff(),
        "cash": raw.loc["cash"],
        "total_debt": raw.loc["total_debt"],
        "diluted_shares": raw.loc["diluted_shares"],
    }

    return pd.DataFrame(statements).T


def calculate_ratios(fin: pd.DataFrame) -> pd.DataFrame:
    """Calculate growth, margins and other ratios. Values are decimals (0.25 = 25%)."""
    revenue = fin.loc["revenue"]

    # A tax rate only makes sense when there is a positive profit to tax.
    # .where() replaces zero/negative pre-tax income with NaN, avoiding division by zero.
    taxable_income = fin.loc["pretax_income"].where(fin.loc["pretax_income"] > 0)

    ratios = {
        "revenue_growth": revenue.pct_change(),
        "gross_margin": fin.loc["gross_profit"] / revenue,
        "opex_pct_revenue": fin.loc["operating_expenses"] / revenue,
        "ebit_margin": fin.loc["ebit"] / revenue,
        "ebitda_margin": fin.loc["ebitda"] / revenue,
        "da_pct_revenue": fin.loc["depreciation_amortization"] / revenue,
        "effective_tax_rate": fin.loc["income_tax"] / taxable_income,
        "capex_pct_revenue": fin.loc["capex"] / revenue,
        "capex_to_da": fin.loc["capex"] / fin.loc["depreciation_amortization"],
        "nwc_pct_revenue": fin.loc["net_working_capital"] / revenue,
    }

    return pd.DataFrame(ratios).T