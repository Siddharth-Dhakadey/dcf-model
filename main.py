"""
main.py — Runs the DCF model for one company.

Change TICKER and run:  python main.py
    "AAPL"  -> Apple: SEC filings + Yahoo price + your assumptions in config/aapl.py
    "MAPLE" -> the hypothetical Maple Coffee Co. from Stage A
For another real company, first create config/<ticker>.py (copy config/aapl.py).
"""

from src.company import load_company
from src.display import (
    print_scenarios,
    print_sensitivity,
    print_table,
    print_terminal_value,
    print_valuation,
    print_wacc,
    print_warnings,
)
from src.model import CompanyInputs, ModelResults, run_model

TICKER = "AAPL"


def with_estimate_labels(table):
    """Label forecast columns FY2026E, FY2027E, ..."""
    labelled = table.copy()
    labelled.columns = [f"FY{year}E" for year in table.columns]
    return labelled


def print_report(inputs: CompanyInputs, results: ModelResults) -> None:
    """Print the full valuation, section by section."""
    r = results
    print("=" * 70)
    print(f"  DCF VALUATION: {inputs.name} ({inputs.ticker})")
    print("=" * 70)
    print("Data decisions:")
    for note in inputs.notes:
        print(f"  - {note}")
    print_warnings("Data checks", r.warnings["Data checks"])

    print_table(r.financials, "Historical Financials ($ millions, shares in millions)")
    print_table(r.ratios, "Historical Ratios", style="percent")
    print_table(r.assumption_review, "Forecast Assumptions vs History (A = actual, E = estimate)", style="percent")
    print_warnings("Assumption checks", r.warnings["Assumption checks"])

    print_table(with_estimate_labels(r.forecast), "Forecast Income Statement ($ millions)")
    print_table(with_estimate_labels(r.ufcf), "Unlevered Free Cash Flow ($ millions)")

    print(f"\nShare price ${inputs.share_price:,.2f} as of {inputs.price_date}")
    print_wacc(inputs.wacc, inputs.share_price, inputs.bridge["diluted_shares"], r.wacc)
    print_warnings("WACC checks", r.warnings["WACC checks"])

    print_table(with_estimate_labels(r.discounted), f"Discounted Cash Flows ($ millions, WACC {r.wacc.wacc:.2%})")
    print_terminal_value(
        inputs.terminal, r.wacc.wacc, float(r.ufcf.loc["ufcf"].iloc[-1]),
        float(r.forecast.loc["ebitda"].iloc[-1]), r.terminal,
    )
    print_warnings("Terminal value checks", r.warnings["Terminal value checks"])

    print_valuation(
        r.valuation, inputs.share_price, inputs.price_date, inputs.bridge_date,
        int(inputs.raw.columns[-1]), r.dcf_ev_to_ebitda, r.market_ev_to_ebitda,
    )
    print_warnings("Valuation checks", r.warnings["Valuation checks"])

    print_sensitivity(r.grid_growth, "Implied Share Price: WACC vs Terminal Growth Rate", "percent", inputs.share_price)
    print_sensitivity(r.grid_multiple, "Implied Share Price: WACC vs Exit EV/EBITDA Multiple", "multiple",
                      inputs.share_price)
    print_scenarios(r.scenario_results, inputs.share_price, inputs.terminal.method)
    print_warnings("Scenario checks", r.warnings["Scenario checks"])


def main() -> None:
    inputs = load_company(TICKER)
    results = run_model(inputs)
    print_report(inputs, results)


if __name__ == "__main__":
    main()