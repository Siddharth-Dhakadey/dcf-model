"""
display.py — Formats tables for printing in the terminal.

Keeping formatting separate means calculation files contain only calculations.
"""

import pandas as pd

from src.assumptions import TerminalAssumptions, WaccAssumptions
from src.scenarios import ScenarioResult
from src.valuation import TerminalValueResult, ValuationResult, WaccResult, upside_downside

# Internal names (used in code) -> readable labels (shown to humans).
LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "gross_profit": "Gross Profit",
    "operating_expenses": "Operating Expenses (incl. D&A)",
    "ebit": "EBIT",
    "depreciation_amortization": "D&A",
    "ebitda": "EBITDA",
    "interest_expense": "Interest & Other Non-Op. (net)",
    "pretax_income": "Pre-Tax Income",
    "income_tax": "Income Tax",
    "net_income": "Net Income",
    "operating_taxes": "Taxes on EBIT",
    "nopat": "NOPAT",
    "less_operating_taxes": "(-) Taxes on EBIT",
    "plus_da": "(+) D&A",
    "less_capex": "(-) CapEx",
    "less_change_in_nwc": "(-) Increase in NWC",
    "ufcf": "Unlevered Free Cash Flow",
    "memo_nwc": "Memo: Net Working Capital",
    "capex": "CapEx",
    "net_working_capital": "Net Working Capital",
    "change_in_nwc": "Change in NWC",
    "cash": "Cash",
    "total_debt": "Total Debt",
    "diluted_shares": "Diluted Shares",
    "revenue_growth": "Revenue Growth",
    "gross_margin": "Gross Margin",
    "opex_pct_revenue": "OpEx % Revenue",
    "ebit_margin": "EBIT Margin",
    "ebitda_margin": "EBITDA Margin",
    "da_pct_revenue": "D&A % Revenue",
    "effective_tax_rate": "Effective Tax Rate",
    "tax_rate": "Tax Rate",
    "capex_pct_revenue": "CapEx % Revenue",
    "capex_to_da": "CapEx / D&A (x)",
    "nwc_pct_revenue": "NWC % Revenue",
    "discount_period": "Discount Period (t)",
    "discount_factor": "Discount Factor",
    "pv_ufcf": "PV of UFCF",
}

# Rows that need a special number format, whatever table they appear in.
ROW_STYLES: dict[str, str] = {
    "capex_to_da": "multiple",        # 1.29x
    "discount_period": "integer",     # 1, 2, 3
    "discount_factor": "factor",      # 0.9218
}


def _format_value(value: float, style: str) -> str:
    """Turn one number into text. NaN (no value) becomes 'n/a'."""
    if pd.isna(value):
        return "n/a"
    if style == "money":
        return f"{value:,.1f}"
    if style == "multiple":
        return f"{value:.2f}x"
    if style == "integer":
        return f"{value:.0f}"
    if style == "factor":
        return f"{value:.4f}"
    return f"{value:.1%}"


def print_table(df: pd.DataFrame, title: str, style: str = "money") -> None:
    """Print a table with readable labels. style: 'money' or 'percent'."""
    formatted = pd.DataFrame(index=df.index, columns=df.columns, dtype=object)
    for row in df.index:
        row_style = ROW_STYLES.get(row, style)
        formatted.loc[row] = [_format_value(v, row_style) for v in df.loc[row]]

    formatted = formatted.rename(index=LABELS)
    formatted.columns = [col if isinstance(col, str) else f"FY{col}" for col in df.columns]

    print(f"\n{title}")
    print("-" * len(title))
    print(formatted.to_string())


def print_warnings(title: str, warnings: list[str]) -> None:
    """Print a list of warning messages, or 'No warnings.' if the list is empty."""
    print(f"\n{title}")
    print("-" * len(title))
    if warnings:
        for message in warnings:
            print(f"WARNING: {message}")
    else:
        print("No warnings.")


def print_summary(title: str, rows: list[tuple[str, str]]) -> None:
    """Print (label, value) pairs in two lined-up columns. A value of "" makes a heading."""
    width = max(len(label) for label, _ in rows) + 2
    print(f"\n{title}")
    print("-" * len(title))
    for label, value in rows:
        print(f"{label:<{width}}{value:>12}")


def print_wacc(w: WaccAssumptions, share_price: float, diluted_shares: float, result: WaccResult) -> None:
    """Print the WACC build-up table, from inputs to final WACC."""
    rows = [
        ("Cost of equity (CAPM)", ""),
        ("  Risk-free rate", f"{w.risk_free_rate:.2%}"),
        ("  Beta", f"{w.beta:.2f}"),
        ("  Equity risk premium", f"{w.equity_risk_premium:.2%}"),
        ("  = Cost of equity", f"{result.cost_of_equity:.2%}"),
        ("Cost of debt", ""),
        ("  Pre-tax cost of debt", f"{w.pre_tax_cost_of_debt:.2%}"),
        ("  Tax rate", f"{w.tax_rate:.2%}"),
        ("  = After-tax cost of debt", f"{result.after_tax_cost_of_debt:.2%}"),
        ("Capital structure ($ millions)", ""),
        ("  Share price", f"${share_price:,.2f}"),
        ("  x Diluted shares (millions)", f"{diluted_shares:,.1f}"),
        ("  = Equity value (market cap)", f"{result.equity_value:,.1f}"),
        ("  + Debt", f"{result.debt_value:,.1f}"),
        ("  = Total capital", f"{result.equity_value + result.debt_value:,.1f}"),
        ("  Equity weight  E/(D+E)", f"{result.equity_weight:.1%}"),
        ("  Debt weight    D/(D+E)", f"{result.debt_weight:.1%}"),
        ("WACC", f"{result.wacc:.2%}"),
    ]
    print_summary("WACC Build-Up", rows)


def print_terminal_value(t: TerminalAssumptions, wacc: float, final_ufcf: float,
                         final_ebitda: float, result: TerminalValueResult) -> None:
    """Print both terminal value methods, their cross-checks, and their present values."""
    rows = [
        ("Perpetuity growth method", ""),
        ("  Final-year UFCF", f"{final_ufcf:,.1f}"),
        ("  Terminal growth rate (g)", f"{t.terminal_growth_rate:.2%}"),
        ("  WACC", f"{wacc:.2%}"),
        ("  = Terminal value", f"{result.tv_perpetuity:,.1f}"),
        ("  Implied EV/EBITDA multiple", f"{result.implied_multiple:.1f}x"),
        ("Exit multiple method", ""),
        ("  Final-year EBITDA", f"{final_ebitda:,.1f}"),
        ("  Exit EV/EBITDA multiple", f"{t.exit_multiple:.1f}x"),
        ("  = Terminal value", f"{result.tv_exit_multiple:,.1f}"),
        ("  Implied perpetual growth", f"{result.implied_growth:.2%}"),
        ("Discounting to today", ""),
        ("  Final-year discount factor", f"{result.discount_factor:.4f}"),
        ("  PV of TV (perpetuity growth)", f"{result.pv_tv_perpetuity:,.1f}"),
        ("  PV of TV (exit multiple)", f"{result.pv_tv_exit_multiple:,.1f}"),
        ("Selected method", t.method),
        ("PV of terminal value (selected)", f"{result.selected_pv_tv:,.1f}"),
    ]
    print_summary("Terminal Value ($ millions)", rows)


def print_valuation(result: ValuationResult, share_price: float, price_date: str, bridge_date: str,
                    ebitda_year: int, dcf_ev_to_ebitda: float, market_ev_to_ebitda: float) -> None:
    """Print the valuation summary: EV -> equity bridge -> implied share price -> sanity check."""
    rows = [
        ("Enterprise value", ""),
        ("  PV of forecast UFCF", f"{result.pv_forecast_ufcf:,.1f}"),
        ("  + PV of terminal value", f"{result.pv_terminal_value:,.1f}"),
        ("  = Enterprise value", f"{result.enterprise_value:,.1f}"),
        ("  Terminal value as % of EV", f"{result.tv_share_of_ev:.1%}"),
        (f"Equity bridge (balance sheet: {bridge_date})", ""),
        ("  + Cash", f"{result.cash:,.1f}"),
        ("  - Total debt", f"{result.total_debt:,.1f}"),
        ("  - Preferred stock", f"{result.preferred_stock:,.1f}"),
        ("  - Minority interest", f"{result.minority_interest:,.1f}"),
        ("  = Equity value", f"{result.equity_value:,.1f}"),
        ("Per share", ""),
        ("  / Shares (millions)", f"{result.diluted_shares:,.1f}"),
        ("  = Implied share price", f"${result.implied_share_price:,.2f}"),
        (f"  Current share price ({price_date})", f"${share_price:,.2f}"),
        ("  Upside / (downside)", f"{upside_downside(result.implied_share_price, share_price):.1%}"),
        (f"Sanity check: EV / FY{ebitda_year} EBITDA", ""),
        ("  Implied by this DCF", f"{dcf_ev_to_ebitda:.1f}x"),
        ("  Implied by the market price", f"{market_ev_to_ebitda:.1f}x"),
    ]
    print_summary("DCF Valuation Summary ($ millions, except per share)", rows)


def print_sensitivity(table: pd.DataFrame, title: str, column_style: str, current_price: float) -> None:
    """
    Print a sensitivity grid of share prices.
    Rows are WACC values; columns are growth rates ('percent') or multiples ('multiple').
    The base case (the middle cell) is shown in [brackets].
    """
    middle_row = len(table.index) // 2
    middle_col = len(table.columns) // 2

    formatted = pd.DataFrame(index=table.index, columns=table.columns, dtype=object)
    for r, wacc in enumerate(table.index):
        for c, col in enumerate(table.columns):
            value = table.loc[wacc, col]
            text = "n/a" if pd.isna(value) else f"${value:,.2f}"
            if r == middle_row and c == middle_col:
                text = f"[{text}]"
            formatted.loc[wacc, col] = text

    formatted.index = [f"{w:.2%}" for w in table.index]
    if column_style == "percent":
        formatted.columns = [f"{c:.1%}" for c in table.columns]
    else:
        formatted.columns = [f"{c:.1f}x" for c in table.columns]
    formatted.index.name = "WACC"

    print(f"\n{title}")
    print("-" * len(title))
    print(formatted.to_string())
    print(f"Base case in [brackets]. Current share price: ${current_price:,.2f}")


def print_scenarios(results: list[ScenarioResult], current_price: float, method: str) -> None:
    """Print bear / base / bull side by side: key assumptions first, then the valuation."""
    rows = {
        "Avg revenue growth (forecast)": [f"{r.average_growth:.1%}" for r in results],
        "Final-year revenue": [f"{r.final_revenue:,.1f}" for r in results],
        "Final-year EBIT margin": [f"{r.final_ebit_margin:.1%}" for r in results],
        "Final-year CapEx % revenue": [f"{r.final_capex_pct:.1%}" for r in results],
        "Final-year NWC % revenue": [f"{r.final_nwc_pct:.1%}" for r in results],
        "Terminal growth rate": [f"{r.terminal_growth:.1%}" for r in results],
        "Exit multiple": [f"{r.exit_multiple:.1f}x" for r in results],
        "Enterprise value": [f"{r.enterprise_value:,.1f}" for r in results],
        "Terminal value % of EV": [f"{r.tv_share_of_ev:.1%}" for r in results],
        "Equity value": [f"{r.equity_value:,.1f}" for r in results],
        "Implied share price": [f"${r.implied_share_price:,.2f}" for r in results],
        "Upside / (downside)": [
            f"{upside_downside(r.implied_share_price, current_price):.1%}" for r in results
        ],
    }
    table = pd.DataFrame(rows, index=[r.name for r in results]).T

    title = f"Scenario Analysis ($ millions, except per share; terminal method: {method})"
    print(f"\n{title}")
    print("-" * len(title))
    print(table.to_string())
    print(f"Current share price: ${current_price:,.2f}")