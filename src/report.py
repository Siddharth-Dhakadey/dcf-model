"""
report.py — The one-page valuation summary: the headline numbers on a single screen.

The detailed tables (display.py) show HOW we got the answer.
This page shows WHAT the answer is, the range around it, and how many warnings to read.
"""

from pathlib import Path

from src.model import CompanyInputs, ModelResults
from src.valuation import upside_downside

WIDTH = 62                                   # characters per line of the summary


def _money(value_m: float) -> str:
    """$ millions -> '$1,864,731m'."""
    return f"${value_m:,.0f}m"


def _row(label: str, value: str, note: str = "") -> str:
    """One aligned line: label, value, optional note in brackets."""
    if note:
        return f"{label:<26}{value:<12}({note})"
    return f"{label:<26}{value}"


def _rule(char: str = "-") -> str:
    return char * WIDTH


def _heading(text: str) -> list[str]:
    return [_rule(), text, _rule()]


def summary_lines(inputs: CompanyInputs, results: ModelResults) -> list[str]:
    """Build the one-page summary as a list of text lines (easy to print, save and test)."""
    v = results.valuation
    t = inputs.terminal
    price = inputs.share_price
    method = "perpetuity growth" if t.method == "perpetuity_growth" else "exit multiple"

    lines = [_rule("="), "DCF VALUATION".center(WIDTH), _rule("=")]
    lines += [
        _row("Company:", inputs.name),
        _row("Ticker:", inputs.ticker),
        _row("Price date:", inputs.price_date),
        _row("Balance sheet date:", inputs.bridge_date),
        "",
        _row("Current share price:", f"${price:,.2f}"),
        _row("Enterprise value:", _money(v.enterprise_value)),
        _row("Equity value:", _money(v.equity_value)),
        _row("Implied share price:", f"${v.implied_share_price:,.2f}"),
        _row("Upside / (downside):", f"{upside_downside(v.implied_share_price, price):+.1%}"),
        "",
        _row("WACC:", f"{results.wacc.wacc:.2%}"),
        _row("Terminal growth:", f"{t.terminal_growth_rate:.2%}"),
        _row("Exit multiple:", f"{t.exit_multiple:.1f}x"),
        _row("Terminal method used:", method),
        _row("Terminal value % of EV:", f"{v.tv_share_of_ev:.1%}"),
    ]

    lines += _heading("SCENARIO ANALYSIS")
    for s in results.scenario_results:
        lines.append(_row(f"{s.name} case:", f"${s.implied_share_price:,.2f}",
                          f"{upside_downside(s.implied_share_price, price):+.1%}"))

    lines += _heading("SENSITIVITY RANGE (implied share price)")
    for grid, name in [(results.grid_growth, "WACC x terminal growth"),
                       (results.grid_multiple, "WACC x exit multiple")]:
        low, high = grid.min().min(), grid.max().max()
        lines.append(_row(f"{name}:", f"${low:,.2f} - ${high:,.2f}"))

    lines += _heading("WARNINGS")
    total = 0
    for section, warnings in results.warnings.items():
        if warnings:
            lines.append(_row(f"{section}:", str(len(warnings))))
            total += len(warnings)
    if total == 0:
        lines.append("No warnings.")
    else:
        lines.append(f"{total} warning(s) in total - read them in the detailed report.")

    lines += [
        _rule(),
        "A DCF estimates value from YOUR assumptions; it is not a",
        "prediction. A large gap to the market price means: re-check",
        "the assumptions and data before concluding anything.",
        _rule("="),
    ]
    return lines


def print_summary_page(lines: list[str]) -> None:
    print("\n".join(lines))


def save_summary(lines: list[str], path: Path) -> Path:
    """Save the summary as a text file (for example outputs/AAPL_summary.txt)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
