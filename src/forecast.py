"""
forecast.py — Builds the forecast financial statements from the assumptions.

Inputs:  the last actual year's revenue (a fact) + ForecastAssumptions (opinions)
Output:  forecast income statement lines for each forecast year (calculated values)

Nothing in this file is typed in by hand: every number is calculated.
"""

import pandas as pd

from src.assumptions import ForecastAssumptions


def forecast_revenue(last_actual_revenue: float, growth_rates: list[float]) -> list[float]:
    """
    Grow revenue one year at a time:
        Revenue_t = Revenue_(t-1) x (1 + Growth_t)
    """
    revenues = []
    previous = last_actual_revenue
    for growth in growth_rates:
        current = previous * (1 + growth)
        revenues.append(current)
        previous = current
    return revenues


def forecast_income_statement(
    last_actual_revenue: float, a: ForecastAssumptions, first_year: int
) -> pd.DataFrame:
    """Forecast revenue down to NOPAT (rows = line items, columns = forecast years)."""
    years = list(range(first_year, first_year + len(a.revenue_growth)))

    def by_year(values: list[float]) -> pd.Series:
        """Attach forecast years to a list of values so pandas can line them up."""
        return pd.Series(values, index=years)

    revenue = by_year(forecast_revenue(last_actual_revenue, a.revenue_growth))

    gross_profit = revenue * by_year(a.gross_margin)
    cogs = revenue - gross_profit

    ebit = revenue * by_year(a.ebit_margin)
    operating_expenses = gross_profit - ebit      # the costs implied by the two margins

    d_and_a = revenue * by_year(a.da_pct_revenue)
    ebitda = ebit + d_and_a

    # Taxes on EBIT: the tax the business would pay if it had no debt.
    # (Interest is ignored on purpose; debt is handled later, in the equity bridge.)
    operating_taxes = ebit * by_year(a.tax_rate)
    nopat = ebit - operating_taxes

    forecast = {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "operating_expenses": operating_expenses,
        "ebit": ebit,
        "depreciation_amortization": d_and_a,
        "ebitda": ebitda,
        "operating_taxes": operating_taxes,
        "nopat": nopat,
    }
    return pd.DataFrame(forecast).T


def forecast_ratios(forecast: pd.DataFrame, last_actual_revenue: float) -> pd.DataFrame:
    """Recalculate growth and margins FROM the forecast, as a check that the formulas connect."""
    revenue = forecast.loc["revenue"]

    previous_revenue = revenue.shift(1)            # each year's previous-year revenue
    previous_revenue.iloc[0] = last_actual_revenue  # year 1 compares to the last actual year

    ebit = forecast.loc["ebit"]

    ratios = {
        "revenue_growth": revenue / previous_revenue - 1,
        "gross_margin": forecast.loc["gross_profit"] / revenue,
        "opex_pct_revenue": forecast.loc["operating_expenses"] / revenue,
        "ebit_margin": ebit / revenue,
        "ebitda_margin": forecast.loc["ebitda"] / revenue,
        "da_pct_revenue": forecast.loc["depreciation_amortization"] / revenue,
        "tax_rate": forecast.loc["operating_taxes"] / ebit.where(ebit != 0),
    }
    return pd.DataFrame(ratios).T


def add_last_actual(forecast: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Put the last actual year in front of the forecast so the transition is visible."""
    last_year = history.columns[-1]

    actual = history[[last_year]].reindex(forecast.index)   # rows it lacks become n/a
    actual.columns = [f"FY{last_year}A"]

    estimates = forecast.copy()
    estimates.columns = [f"FY{year}E" for year in forecast.columns]

    return pd.concat([actual, estimates], axis=1)

def forecast_free_cash_flow(
    forecast: pd.DataFrame, a: ForecastAssumptions, last_actual_nwc: float
) -> pd.DataFrame:
    """
    Build Unlevered Free Cash Flow (UFCF) for each forecast year:

        UFCF = EBIT - Taxes on EBIT + D&A - CapEx - Increase in NWC

    In this table, cash outflows are shown as NEGATIVE numbers,
    so each column simply adds up from NOPAT down to UFCF.
    """
    years = forecast.columns
    revenue = forecast.loc["revenue"]

    capex = revenue * pd.Series(a.capex_pct_revenue, index=years)
    nwc = revenue * pd.Series(a.nwc_pct_revenue, index=years)

    previous_nwc = nwc.shift(1)              # each year's previous-year NWC
    previous_nwc.iloc[0] = last_actual_nwc   # year 1 compares to the last actual NWC
    change_in_nwc = nwc - previous_nwc       # positive = more cash tied up

    nopat = forecast.loc["nopat"]
    d_and_a = forecast.loc["depreciation_amortization"]

    ufcf = nopat + d_and_a - capex - change_in_nwc

    bridge = {
        "ebit": forecast.loc["ebit"],
        "less_operating_taxes": -forecast.loc["operating_taxes"],
        "nopat": nopat,
        "plus_da": d_and_a,
        "less_capex": -capex,
        "less_change_in_nwc": -change_in_nwc,
        "ufcf": ufcf,
        "memo_nwc": nwc,
    }
    return pd.DataFrame(bridge).T