"""
main.py — Runs the DCF model for one company.

How to run:
    python main.py              -> asks for a ticker (press Enter for the default)
    python main.py AAPL         -> Apple: SEC filings + Yahoo price + your assumptions in config/aapl.py
    python main.py MAPLE        -> the hypothetical Maple Coffee Co. from Stage A
    python main.py AAPL --short -> the one-page summary only

For another real company, first create config/<ticker>.py (copy config/aapl.py).
"""

import sys
from pathlib import Path

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
from src.report import print_summary_page, save_summary, summary_lines
from src.visualization import OUTPUT_DIR, save_all_charts

DEFAULT_TICKER = "AAPL"


def choose_ticker(args: list[str]) -> str:
    """Take the ticker from the command line, or ask for it."""
    tickers = [a for a in args if not a.startswith("--")]
    if tickers:
        return tickers[0].upper()
    answer = input(f"Enter ticker (press Enter for {DEFAULT_TICKER}): ").strip().upper()
    return answer or DEFAULT_TICKER


def with_estimate_labels(table):
    """Label forecast columns FY2026E, FY2027E, ..."""
    labelled = table.copy()
    labelled.columns = [f"FY{year}E" for year in table.columns]
    return labelled


def print_report(inputs: CompanyInputs, results: ModelResults) -> None:
    """Print the full valuation, section by section."""
    r = results
    print("\n" + "=" * 70)
    print(f"  DETAILED REPORT: {inputs.name} ({inputs.ticker})")
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
    args = sys.argv[1:]
    ticker = choose_ticker(args)
    try:
        inputs = load_company(ticker)
        results = run_model(inputs)
    except (RuntimeError, ValueError) as exc:
        # Fail safely: explain the problem instead of printing a misleading valuation.
        print(f"\nCould not value {ticker}.\n{type(exc).__name__}: {exc}")
        sys.exit(1)

    summary = summary_lines(inputs, results)
    print_summary_page(summary)
    if "--short" not in args:
        print_report(inputs, results)

    print("\nFiles saved:")
    saved = [save_summary(summary, OUTPUT_DIR / f"{inputs.ticker}_summary.txt")]
    saved += save_all_charts(inputs, results)
    for path in saved:
        print(f"  {Path(path).relative_to(OUTPUT_DIR.parent)}")


if __name__ == "__main__":
    main()
