"""
scenarios.py — Bear, base and bull cases.

A sensitivity table changes WACC and terminal assumptions while keeping the
forecast fixed. A scenario changes the BUSINESS OUTCOME itself: growth,
margins, reinvestment and the terminal assumptions, all together, as one
coherent story. Each scenario is run through the same valuation engine.

The scenario assumptions below are OPINIONS. They are illustrative, not
"correct". Edit them freely.
"""

from dataclasses import dataclass, replace

import pandas as pd

from src.assumptions import (
    ForecastAssumptions,
    TerminalAssumptions,
    validate_assumptions,
    validate_terminal_assumptions,
)
from src.forecast import forecast_free_cash_flow, forecast_income_statement
from src.valuation import calculate_equity_value, calculate_terminal_value, discount_cash_flows


@dataclass
class Scenario:
    """One coherent story about the future: operating assumptions + terminal assumptions."""

    name: str
    forecast: ForecastAssumptions
    terminal: TerminalAssumptions


# =============================================================================
# SCENARIO ASSUMPTIONS (opinions — edit freely)
# Bear and bull start from the base case and change only what is listed.
# =============================================================================
def maple_scenarios(base: ForecastAssumptions, base_terminal: TerminalAssumptions) -> list[Scenario]:
    """Illustrative bear / base / bull cases for Maple Coffee Co."""
    bear = Scenario(
        name="Bear",
        forecast=replace(
            base,
            revenue_growth=[0.040, 0.035, 0.030, 0.025, 0.020],   # growth fades quickly
            ebit_margin=[0.180] * 5,                              # competition squeezes margins
            capex_pct_revenue=[0.055] * 5,                        # stores need more reinvestment
            nwc_pct_revenue=[0.065] * 5,                          # more cash tied up in operations
        ),
        terminal=replace(base_terminal, terminal_growth_rate=0.015, exit_multiple=7.0),
    )

    base_case = Scenario(name="Base", forecast=base, terminal=base_terminal)

    bull = Scenario(
        name="Bull",
        forecast=replace(
            base,
            revenue_growth=[0.090, 0.085, 0.075, 0.065, 0.050],   # successful expansion
            ebit_margin=[0.195, 0.205, 0.210, 0.215, 0.220],      # scale benefits
        ),
        terminal=replace(base_terminal, terminal_growth_rate=0.030, exit_multiple=12.0),
    )

    return [bear, base_case, bull]


@dataclass
class ScenarioResult:
    """The key assumptions and outputs of one scenario, ready to compare side by side."""

    name: str
    average_growth: float
    final_revenue: float
    final_ebit_margin: float
    final_capex_pct: float
    final_nwc_pct: float
    terminal_growth: float
    exit_multiple: float
    enterprise_value: float
    tv_share_of_ev: float
    equity_value: float
    implied_share_price: float
    warnings: list[str]


def run_scenario(
    scenario: Scenario,
    last_actual_revenue: float,
    last_actual_nwc: float,
    first_forecast_year: int,
    wacc: float,
    bridge: dict[str, float],
) -> ScenarioResult:
    """Run one scenario through the full model: forecast -> UFCF -> discounting -> TV -> equity."""
    warnings = validate_assumptions(scenario.forecast)
    warnings += validate_terminal_assumptions(scenario.terminal)

    forecast = forecast_income_statement(last_actual_revenue, scenario.forecast, first_forecast_year)
    ufcf = forecast_free_cash_flow(forecast, scenario.forecast, last_actual_nwc)

    discounted = discount_cash_flows(ufcf.loc["ufcf"], wacc)
    terminal = calculate_terminal_value(
        final_ufcf=float(ufcf.loc["ufcf"].iloc[-1]),
        final_ebitda=float(forecast.loc["ebitda"].iloc[-1]),
        wacc=wacc,
        t=scenario.terminal,
        years_to_discount=len(ufcf.columns),
    )
    valuation = calculate_equity_value(
        float(discounted.loc["pv_ufcf"].sum()), terminal.selected_pv_tv, **bridge
    )

    growth = pd.Series(scenario.forecast.revenue_growth)
    return ScenarioResult(
        name=scenario.name,
        average_growth=float(growth.mean()),
        final_revenue=float(forecast.loc["revenue"].iloc[-1]),
        final_ebit_margin=scenario.forecast.ebit_margin[-1],
        final_capex_pct=scenario.forecast.capex_pct_revenue[-1],
        final_nwc_pct=scenario.forecast.nwc_pct_revenue[-1],
        terminal_growth=scenario.terminal.terminal_growth_rate,
        exit_multiple=scenario.terminal.exit_multiple,
        enterprise_value=valuation.enterprise_value,
        tv_share_of_ev=valuation.tv_share_of_ev,
        equity_value=valuation.equity_value,
        implied_share_price=valuation.implied_share_price,
        warnings=warnings,
    )