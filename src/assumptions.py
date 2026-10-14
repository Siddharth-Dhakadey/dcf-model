"""
assumptions.py — The analyst's forecast assumptions, kept separate from the facts.

Everything in this file is an OPINION about the future, not a fact.
Change these numbers to change the forecast; never edit the historical data to do it.

All rates are decimals: 0.07 means 7%.
Each list has one value per forecast year. The length of the lists sets the
forecast period (5 values = 5-year forecast, 7 values = 7-year forecast).
"""

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass
class ForecastAssumptions:
    """Year-by-year operating assumptions for the forecast period."""

    revenue_growth: list[float]      # % change in revenue vs the previous year
    gross_margin: list[float]        # gross profit / revenue
    ebit_margin: list[float]         # EBIT / revenue
    tax_rate: list[float]            # tax rate applied to EBIT (used for NOPAT in Step 6)
    da_pct_revenue: list[float]      # depreciation & amortization / revenue
    capex_pct_revenue: list[float]   # capital expenditures / revenue
    nwc_pct_revenue: list[float]     # net working capital / revenue


def maple_base_case() -> ForecastAssumptions:
    """Illustrative base-case assumptions for Maple Coffee Co. (edit freely)."""
    return ForecastAssumptions(
        revenue_growth=[0.070, 0.065, 0.060, 0.050, 0.040],
        gross_margin=[0.605, 0.610, 0.610, 0.610, 0.610],
        ebit_margin=[0.190, 0.195, 0.200, 0.200, 0.200],
        tax_rate=[0.25] * 5,
        da_pct_revenue=[0.040] * 5,
        capex_pct_revenue=[0.052, 0.050, 0.048, 0.046, 0.045],
        nwc_pct_revenue=[0.062] * 5,
    )


def validate_assumptions(a: ForecastAssumptions) -> list[str]:
    """
    Check the assumptions.

    Impossible values raise a ValueError (the model stops).
    Unusual-but-possible values are returned as a list of warning messages.
    """
    lengths = {name: len(values) for name, values in asdict(a).items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"Every assumption needs one value per forecast year. Found: {lengths}")

    n_years = len(a.revenue_growth)
    if n_years < 1:
        raise ValueError("The forecast needs at least 1 year.")

    errors: list[str] = []
    warnings: list[str] = []

    for i in range(n_years):
        year = f"Year {i + 1}"
        growth, gross, ebit = a.revenue_growth[i], a.gross_margin[i], a.ebit_margin[i]
        tax, da, capex = a.tax_rate[i], a.da_pct_revenue[i], a.capex_pct_revenue[i]

        # --- Impossible: stop the model ---
        if growth <= -1:
            errors.append(f"{year}: revenue growth of {growth:.0%} would make revenue zero or negative.")
        if not 0 < gross < 1:
            errors.append(f"{year}: gross margin {gross:.1%} must be between 0% and 100%.")
        if ebit >= gross:
            errors.append(
                f"{year}: EBIT margin ({ebit:.1%}) must be below gross margin ({gross:.1%}), "
                "otherwise operating expenses would be zero or negative."
            )
        if not 0 <= tax < 1:
            errors.append(f"{year}: tax rate {tax:.1%} must be between 0% and 100%.")
        if da < 0 or capex < 0:
            errors.append(f"{year}: D&A and CapEx percentages cannot be negative.")

        # --- Unusual: allow, but warn ---
        if growth > 0.30:
            warnings.append(f"{year}: revenue growth of {growth:.1%} is very high. Is it sustainable?")
        if ebit < 0:
            warnings.append(f"{year}: negative EBIT margin ({ebit:.1%}); the company is loss-making.")
        if not 0.10 <= tax <= 0.40:
            warnings.append(f"{year}: tax rate of {tax:.1%} is outside the usual 10%-40% range.")

    if a.capex_pct_revenue[-1] < a.da_pct_revenue[-1]:
        warnings.append(
            "Final year: CapEx is below D&A. The terminal value would assume the asset base "
            "shrinks forever, which rarely fits a company that is still growing."
        )

    if errors:
        raise ValueError("Invalid assumptions:\n  - " + "\n  - ".join(errors))

    return warnings


def assumptions_to_frame(a: ForecastAssumptions, first_year: int) -> pd.DataFrame:
    """Turn the assumptions into a table (rows = assumptions, columns = forecast years)."""
    n_years = len(a.revenue_growth)
    years = list(range(first_year, first_year + n_years))
    return pd.DataFrame.from_dict(asdict(a), orient="index", columns=years)


def build_assumption_review(
    ratios: pd.DataFrame, forecast: pd.DataFrame, history_years: int = 3
) -> pd.DataFrame:
    """Place recent historical ratios next to the forecast assumptions for comparison."""
    history = ratios.rename(index={"effective_tax_rate": "tax_rate"}).loc[forecast.index]
    history = history.iloc[:, -history_years:]

    history.columns = [f"FY{year}A" for year in history.columns]
    forecast = forecast.copy()
    forecast.columns = [f"FY{year}E" for year in forecast.columns]

    return pd.concat([history, forecast], axis=1)


@dataclass
class WaccAssumptions:
    """Inputs for the discount rate (WACC). All rates are decimals (0.0425 = 4.25%)."""

    risk_free_rate: float         # market data: yield on the 10-year government bond
    beta: float                   # market data + judgement: how much the stock moves with the market
    equity_risk_premium: float    # judgement: extra return investors demand for owning stocks
    pre_tax_cost_of_debt: float   # market data + judgement: rate the company would pay to borrow today
    tax_rate: float               # judgement: should match the forecast tax rate


def maple_wacc_assumptions() -> WaccAssumptions:
    """Illustrative WACC inputs for Maple Coffee Co. (edit freely)."""
    return WaccAssumptions(
        risk_free_rate=0.0425,
        beta=1.10,
        equity_risk_premium=0.050,
        pre_tax_cost_of_debt=0.050,
        tax_rate=0.25,
    )


def validate_wacc_assumptions(w: WaccAssumptions) -> list[str]:
    """Raise a ValueError for impossible WACC inputs; return warnings for unusual ones."""
    rates = {
        "risk-free rate": w.risk_free_rate,
        "equity risk premium": w.equity_risk_premium,
        "pre-tax cost of debt": w.pre_tax_cost_of_debt,
        "tax rate": w.tax_rate,
    }

    errors: list[str] = []
    for name, value in rates.items():
        if not 0 <= value < 1:
            errors.append(f"{name} = {value} must be a decimal between 0 and 1 (e.g. 4.25% is 0.0425).")
    if w.beta <= 0:
        errors.append(f"beta = {w.beta} must be greater than zero.")
    if errors:
        raise ValueError("Invalid WACC inputs:\n  - " + "\n  - ".join(errors))

    warnings: list[str] = []
    if not 0.005 <= w.risk_free_rate <= 0.08:
        warnings.append(f"Risk-free rate of {w.risk_free_rate:.2%} is unusual. Check the current 10-year bond yield.")
    if not 0.03 <= w.equity_risk_premium <= 0.08:
        warnings.append(f"Equity risk premium of {w.equity_risk_premium:.2%} is outside the usual 3%-8% range.")
    if not 0.4 <= w.beta <= 2.5:
        warnings.append(f"Beta of {w.beta:.2f} is unusual. Compare it with similar companies' betas.")
    if w.pre_tax_cost_of_debt < w.risk_free_rate:
        warnings.append("Cost of debt is below the risk-free rate. Companies almost always borrow above it.")
    if not 0.10 <= w.tax_rate <= 0.40:
        warnings.append(f"Tax rate of {w.tax_rate:.1%} is outside the usual 10%-40% range.")
    return warnings


TERMINAL_METHODS = ("perpetuity_growth", "exit_multiple")


@dataclass
class TerminalAssumptions:
    """How to value everything after the final forecast year."""

    terminal_growth_rate: float   # judgement: growth of UFCF forever after the forecast (decimal)
    exit_multiple: float          # judgement: EV / EBITDA a buyer would pay at the end of the forecast
    method: str                   # which one drives the valuation: "perpetuity_growth" or "exit_multiple"


def maple_terminal_assumptions() -> TerminalAssumptions:
    """Illustrative terminal value inputs for Maple Coffee Co. (edit freely)."""
    return TerminalAssumptions(
        terminal_growth_rate=0.025,
        exit_multiple=10.0,
        method="perpetuity_growth",
    )


def validate_terminal_assumptions(t: TerminalAssumptions) -> list[str]:
    """Raise a ValueError for impossible terminal inputs; return warnings for unusual ones."""
    if t.method not in TERMINAL_METHODS:
        raise ValueError(f"Terminal method '{t.method}' is not recognised. Use one of: {TERMINAL_METHODS}")
    if t.terminal_growth_rate >= 1 or t.terminal_growth_rate <= -1:
        raise ValueError(
            f"Terminal growth rate = {t.terminal_growth_rate} must be a decimal (e.g. 2.5% is 0.025)."
        )
    if t.exit_multiple <= 0:
        raise ValueError("Exit multiple must be greater than zero.")

    warnings: list[str] = []
    if t.terminal_growth_rate > 0.04:
        warnings.append(
            f"Terminal growth of {t.terminal_growth_rate:.1%} is high. No company can outgrow "
            "the economy forever; 2%-3% is typical."
        )
    if t.terminal_growth_rate < 0:
        warnings.append("Negative terminal growth assumes the business shrinks forever.")
    if t.exit_multiple > 20:
        warnings.append(f"Exit multiple of {t.exit_multiple:.1f}x EBITDA is very high for a mature business.")
    return warnings