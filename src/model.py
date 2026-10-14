"""
model.py — The complete DCF engine, for ANY company.

    CompanyInputs  (facts + market data + your assumptions)
          |
      run_model()  -> history -> forecast -> UFCF -> WACC -> terminal value
          |           -> EV -> equity value -> share price -> sensitivity -> scenarios
          v
    ModelResults   (every intermediate table, so it can be printed and checked)

Maple Coffee and Apple go through exactly the same code.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from src.assumptions import (
    ForecastAssumptions,
    TerminalAssumptions,
    WaccAssumptions,
    assumptions_to_frame,
    build_assumption_review,
    validate_assumptions,
    validate_terminal_assumptions,
    validate_wacc_assumptions,
)
from src.data import validate_historicals
from src.forecast import forecast_free_cash_flow, forecast_income_statement, forecast_ratios
from src.historicals import build_historical_statements, calculate_ratios
from src.scenarios import Scenario, ScenarioResult, run_scenario
from src.sensitivity import centered_values, sensitivity_wacc_vs_growth, sensitivity_wacc_vs_multiple
from src.valuation import (
    TerminalValueResult,
    ValuationResult,
    WaccResult,
    calculate_equity_value,
    calculate_terminal_value,
    calculate_wacc,
    check_valuation,
    discount_cash_flows,
    market_enterprise_value,
)


@dataclass
class CompanyInputs:
    """Everything the model needs about one company. Built by src/company.py."""

    name: str
    ticker: str
    raw: pd.DataFrame                    # historical facts (REQUIRED_ITEMS x years), $ millions
    share_price: float                   # $ per share
    price_date: str
    bridge: dict[str, float]             # cash, total_debt, preferred_stock, minority_interest, diluted_shares
    bridge_date: str                     # balance sheet date the bridge comes from
    forecast: ForecastAssumptions
    wacc: WaccAssumptions
    terminal: TerminalAssumptions
    scenarios: Callable[[ForecastAssumptions, TerminalAssumptions], list[Scenario]]
    notes: list[str] = field(default_factory=list)          # data decisions, shown in the report
    data_warnings: list[str] = field(default_factory=list)  # from the data checks


@dataclass
class ModelResults:
    """Every intermediate result of the valuation."""

    financials: pd.DataFrame
    ratios: pd.DataFrame
    assumption_review: pd.DataFrame
    forecast: pd.DataFrame
    forecast_check: pd.DataFrame
    ufcf: pd.DataFrame
    wacc: WaccResult
    discounted: pd.DataFrame
    terminal: TerminalValueResult
    valuation: ValuationResult
    dcf_ev_to_ebitda: float
    market_ev_to_ebitda: float
    grid_growth: pd.DataFrame
    grid_multiple: pd.DataFrame
    scenario_results: list[ScenarioResult]
    warnings: dict[str, list[str]]


def run_model(inputs: CompanyInputs) -> ModelResults:
    """Run the full DCF for one company."""
    raw = inputs.raw
    validate_historicals(raw)
    financials = build_historical_statements(raw)
    ratios = calculate_ratios(financials)

    # --- Forecast ---
    first_year = int(raw.columns[-1]) + 1
    review = build_assumption_review(ratios, assumptions_to_frame(inputs.forecast, first_year))
    last_revenue = float(financials.loc["revenue"].iloc[-1])
    last_nwc = float(financials.loc["net_working_capital"].iloc[-1])
    forecast = forecast_income_statement(last_revenue, inputs.forecast, first_year)
    forecast_check = forecast_ratios(forecast, last_revenue)
    ufcf = forecast_free_cash_flow(forecast, inputs.forecast, last_nwc)

    # --- WACC (market value of equity = price x shares used in the bridge) ---
    market_cap = inputs.share_price * inputs.bridge["diluted_shares"]
    wacc = calculate_wacc(inputs.wacc, market_cap, inputs.bridge["total_debt"])

    # --- Discounting, terminal value, equity bridge ---
    discounted = discount_cash_flows(ufcf.loc["ufcf"], wacc.wacc)
    final_ebitda = float(forecast.loc["ebitda"].iloc[-1])
    terminal = calculate_terminal_value(
        float(ufcf.loc["ufcf"].iloc[-1]), final_ebitda, wacc.wacc, inputs.terminal, len(ufcf.columns)
    )
    valuation = calculate_equity_value(
        float(discounted.loc["pv_ufcf"].sum()), terminal.selected_pv_tv, **inputs.bridge
    )

    # --- Sanity check against the market (EV / last actual EBITDA) ---
    last_ebitda = float(financials.loc["ebitda"].iloc[-1])
    b = inputs.bridge
    market_ev = market_enterprise_value(
        market_cap, b["cash"], b["total_debt"], b["preferred_stock"], b["minority_interest"]
    )

    # --- Sensitivity ---
    wacc_values = centered_values(wacc.wacc, step=0.005)
    growth_values = centered_values(inputs.terminal.terminal_growth_rate, step=0.005)
    multiple_values = centered_values(inputs.terminal.exit_multiple, step=1.0)
    grid_growth = sensitivity_wacc_vs_growth(ufcf.loc["ufcf"], final_ebitda, b, wacc_values, growth_values)
    grid_multiple = sensitivity_wacc_vs_multiple(ufcf.loc["ufcf"], final_ebitda, b, wacc_values, multiple_values)

    # --- Scenarios (the Base scenario must reproduce the main valuation) ---
    scenario_results = [
        run_scenario(s, last_revenue, last_nwc, first_year, wacc.wacc, b)
        for s in inputs.scenarios(inputs.forecast, inputs.terminal)
    ]
    base = next(r for r in scenario_results if r.name == "Base")
    if abs(base.implied_share_price - valuation.implied_share_price) > 0.005:
        raise RuntimeError("Base scenario does not match the main valuation. Check the scenario setup.")

    warnings = {
        "Data checks": inputs.data_warnings,
        "Assumption checks": validate_assumptions(inputs.forecast),
        "WACC checks": validate_wacc_assumptions(inputs.wacc),
        "Terminal value checks": validate_terminal_assumptions(inputs.terminal),
        "Valuation checks": check_valuation(valuation, inputs.share_price),
        "Scenario checks": [f"{r.name}: {w}" for r in scenario_results for w in r.warnings],
    }

    return ModelResults(
        financials=financials,
        ratios=ratios,
        assumption_review=review,
        forecast=forecast,
        forecast_check=forecast_check,
        ufcf=ufcf,
        wacc=wacc,
        discounted=discounted,
        terminal=terminal,
        valuation=valuation,
        dcf_ev_to_ebitda=valuation.enterprise_value / last_ebitda,
        market_ev_to_ebitda=market_ev / last_ebitda,
        grid_growth=grid_growth,
        grid_multiple=grid_multiple,
        scenario_results=scenario_results,
        warnings=warnings,
    )