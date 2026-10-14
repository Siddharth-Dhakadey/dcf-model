"""
main.py — Runs the DCF model.

Current progress: Step 11 — scenario analysis.
"""

from src.assumptions import (
    assumptions_to_frame,
    build_assumption_review,
    maple_base_case,
    maple_terminal_assumptions,
    maple_wacc_assumptions,
    validate_assumptions,
    validate_terminal_assumptions,
    validate_wacc_assumptions,
)
from src.data import (
    SAMPLE_COMPANY_NAME,
    UNITS,
    load_sample_company,
    load_sample_market_data,
    validate_historicals,
)
from src.display import (
    print_scenarios,
    print_table,
    print_sensitivity,
    print_terminal_value,
    print_valuation,
    print_wacc,
    print_warnings,
)
from src.forecast import (
    add_last_actual,
    forecast_free_cash_flow,
    forecast_income_statement,
    forecast_ratios,
)
from src.historicals import build_historical_statements, calculate_ratios
from src.scenarios import maple_scenarios, run_scenario
from src.sensitivity import (
    centered_values,
    sensitivity_wacc_vs_growth,
    sensitivity_wacc_vs_multiple,
)
from src.valuation import (
    calculate_equity_value,
    calculate_terminal_value,
    calculate_wacc,
    check_valuation,
    discount_cash_flows,
    market_enterprise_value,
)


def main() -> None:
    """Load the data, check it, calculate history, forecast, build WACC, and print."""
    # --- Facts: historical data and market data ---
    raw = load_sample_company()
    validate_historicals(raw)
    financials = build_historical_statements(raw)
    ratios = calculate_ratios(financials)
    market = load_sample_market_data()

    # --- Opinions: forecast assumptions ---
    assumptions = maple_base_case()
    warnings = validate_assumptions(assumptions)
    first_forecast_year = int(raw.columns[-1]) + 1
    forecast_assumptions = assumptions_to_frame(assumptions, first_forecast_year)
    review = build_assumption_review(ratios, forecast_assumptions)

    # --- Calculated: forecast ---
    last_actual_revenue = float(financials.loc["revenue"].iloc[-1])
    forecast = forecast_income_statement(last_actual_revenue, assumptions, first_forecast_year)
    forecast_check = forecast_ratios(forecast, last_actual_revenue)

    last_actual_nwc = float(financials.loc["net_working_capital"].iloc[-1])
    ufcf = forecast_free_cash_flow(forecast, assumptions, last_actual_nwc)

    # --- Discount rate: WACC ---
    wacc_inputs = maple_wacc_assumptions()
    wacc_warnings = validate_wacc_assumptions(wacc_inputs)
    diluted_shares = float(financials.loc["diluted_shares"].iloc[-1])
    total_debt = float(financials.loc["total_debt"].iloc[-1])
    market_cap = market.share_price * diluted_shares
    wacc = calculate_wacc(wacc_inputs, market_cap, total_debt)

    # --- Discounting and terminal value ---
    terminal_inputs = maple_terminal_assumptions()
    terminal_warnings = validate_terminal_assumptions(terminal_inputs)
    discounted = discount_cash_flows(ufcf.loc["ufcf"], wacc.wacc)
    final_ufcf = float(ufcf.loc["ufcf"].iloc[-1])
    final_ebitda = float(forecast.loc["ebitda"].iloc[-1])
    terminal = calculate_terminal_value(
        final_ufcf, final_ebitda, wacc.wacc, terminal_inputs, years_to_discount=len(ufcf.columns)
    )

    # --- Enterprise value -> equity value -> implied share price ---
    latest_year = int(raw.columns[-1])          # balance sheet date used for the bridge
    cash = float(raw.loc["cash", latest_year])
    preferred_stock = float(raw.loc["preferred_stock", latest_year])
    minority_interest = float(raw.loc["minority_interest", latest_year])

    valuation = calculate_equity_value(
        pv_forecast_ufcf=float(discounted.loc["pv_ufcf"].sum()),
        pv_terminal_value=terminal.selected_pv_tv,
        cash=cash,
        total_debt=total_debt,
        preferred_stock=preferred_stock,
        minority_interest=minority_interest,
        diluted_shares=diluted_shares,
    )
    valuation_warnings = check_valuation(valuation, market.share_price)

    # Sanity check: compare EV / EBITDA implied by the DCF with the one implied by the market.
    last_actual_ebitda = float(financials.loc["ebitda"].iloc[-1])
    market_ev = market_enterprise_value(market_cap, cash, total_debt, preferred_stock, minority_interest)
    dcf_multiple = valuation.enterprise_value / last_actual_ebitda
    market_multiple = market_ev / last_actual_ebitda

    # --- Sensitivity analysis: re-run the valuation over a grid of assumptions ---
    bridge = {
        "cash": cash,
        "total_debt": total_debt,
        "preferred_stock": preferred_stock,
        "minority_interest": minority_interest,
        "diluted_shares": diluted_shares,
    }
    wacc_values = centered_values(wacc.wacc, step=0.005)                          # base +/- 1.5%
    growth_values = centered_values(terminal_inputs.terminal_growth_rate, step=0.005)
    multiple_values = centered_values(terminal_inputs.exit_multiple, step=1.0)      # base +/- 3x
    grid_growth = sensitivity_wacc_vs_growth(
        ufcf.loc["ufcf"], final_ebitda, bridge, wacc_values, growth_values
    )
    grid_multiple = sensitivity_wacc_vs_multiple(
        ufcf.loc["ufcf"], final_ebitda, bridge, wacc_values, multiple_values
    )

    # --- Scenario analysis: bear / base / bull, each run through the full model ---
    scenarios = maple_scenarios(assumptions, terminal_inputs)
    scenario_results = [
        run_scenario(s, last_actual_revenue, last_actual_nwc, first_forecast_year, wacc.wacc, bridge)
        for s in scenarios
    ]

    # Self-check: the base scenario must reproduce the main valuation exactly.
    base_result = next(r for r in scenario_results if r.name == "Base")
    if abs(base_result.implied_share_price - valuation.implied_share_price) > 0.005:
        raise RuntimeError("Base scenario does not match the main valuation. Check the scenario setup.")

    scenario_warnings = [f"{r.name}: {w}" for r in scenario_results for w in r.warnings]

    # --- Output ---
    print("=" * 60)
    print(f"  {SAMPLE_COMPANY_NAME}")
    print("=" * 60)
    print_table(financials, f"Historical Financials ({UNITS})", style="money")
    print_table(ratios, "Historical Ratios", style="percent")
    print_table(review, "Forecast Assumptions vs History (A = actual, E = estimate)", style="percent")
    print_warnings("Assumption checks", warnings)

    history_ratios = ratios.rename(index={"effective_tax_rate": "tax_rate"})
    print_table(add_last_actual(forecast, financials), f"Forecast Income Statement ({UNITS})")
    print_table(add_last_actual(forecast_check, history_ratios), "Forecast Ratios (check)", style="percent")

    ufcf_display = ufcf.copy()
    ufcf_display.columns = [f"FY{year}E" for year in ufcf.columns]
    print_table(ufcf_display, "Unlevered Free Cash Flow ($ millions)")

    print(f"\nShare price ${market.share_price:,.2f} as of {market.price_date}")
    print_wacc(wacc_inputs, market.share_price, diluted_shares, wacc)
    print_warnings("WACC checks", wacc_warnings)

    discounted_display = discounted.copy()
    discounted_display.columns = [f"FY{year}E" for year in discounted.columns]
    print_table(discounted_display, f"Discounted Cash Flows ($ millions, WACC {wacc.wacc:.2%})")
    print(f"Sum of PV of forecast UFCF: {discounted.loc['pv_ufcf'].sum():,.1f}")

    print_terminal_value(terminal_inputs, wacc.wacc, final_ufcf, final_ebitda, terminal)
    print_warnings("Terminal value checks", terminal_warnings)

    print_valuation(
        valuation, market.share_price, market.price_date, latest_year, dcf_multiple, market_multiple
    )
    print_warnings("Valuation checks", valuation_warnings)

    print_sensitivity(
        grid_growth, "Implied Share Price: WACC vs Terminal Growth Rate", "percent", market.share_price
    )
    print_sensitivity(
        grid_multiple, "Implied Share Price: WACC vs Exit EV/EBITDA Multiple", "multiple", market.share_price
    )

    print_scenarios(scenario_results, market.share_price, terminal_inputs.method)
    print_warnings("Scenario checks", scenario_warnings)


if __name__ == "__main__":
    main()