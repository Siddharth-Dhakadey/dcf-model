"""
sensitivity.py — How much does the share price change when key assumptions change?

The forecast cash flows stay fixed. Only the discount rate (WACC) and the
terminal value assumption (growth rate or exit multiple) are varied, and the
whole valuation is recalculated for every combination.
"""

import pandas as pd

from src.valuation import (
    calculate_equity_value,
    discount_cash_flows,
    terminal_value_exit_multiple,
    terminal_value_perpetuity,
)


def centered_values(center: float, step: float, steps_each_side: int = 3) -> list[float]:
    """
    Values evenly spaced around a base case, e.g. center 0.025, step 0.005:
    [0.010, 0.015, 0.020, 0.025, 0.030, 0.035, 0.040]
    The base case is always the middle value.
    """
    return [round(center + i * step, 6) for i in range(-steps_each_side, steps_each_side + 1)]


def implied_share_price(
    ufcf: pd.Series,
    final_ebitda: float,
    wacc: float,
    method: str,
    growth: float,
    multiple: float,
    bridge: dict[str, float],
) -> float:
    """Run the whole valuation (discounting -> terminal value -> equity bridge) for one set of inputs."""
    pv_forecast = float(discount_cash_flows(ufcf, wacc).loc["pv_ufcf"].sum())

    if method == "perpetuity_growth":
        tv = terminal_value_perpetuity(float(ufcf.iloc[-1]), wacc, growth)
    else:
        tv = terminal_value_exit_multiple(final_ebitda, multiple)
    pv_tv = tv / (1 + wacc) ** len(ufcf)

    result = calculate_equity_value(pv_forecast, pv_tv, **bridge)
    return result.implied_share_price


def sensitivity_wacc_vs_growth(
    ufcf: pd.Series,
    final_ebitda: float,
    bridge: dict[str, float],
    wacc_values: list[float],
    growth_values: list[float],
) -> pd.DataFrame:
    """Implied share price for every WACC (rows) and terminal growth rate (columns)."""
    table = pd.DataFrame(index=wacc_values, columns=growth_values, dtype=float)
    for wacc in wacc_values:
        for growth in growth_values:
            try:
                table.loc[wacc, growth] = implied_share_price(
                    ufcf, final_ebitda, wacc, "perpetuity_growth", growth, 0.0, bridge
                )
            except ValueError:
                table.loc[wacc, growth] = float("nan")   # e.g. growth >= WACC: no valid answer
    return table


def sensitivity_wacc_vs_multiple(
    ufcf: pd.Series,
    final_ebitda: float,
    bridge: dict[str, float],
    wacc_values: list[float],
    multiple_values: list[float],
) -> pd.DataFrame:
    """Implied share price for every WACC (rows) and exit EV/EBITDA multiple (columns)."""
    table = pd.DataFrame(index=wacc_values, columns=multiple_values, dtype=float)
    for wacc in wacc_values:
        for multiple in multiple_values:
            try:
                table.loc[wacc, multiple] = implied_share_price(
                    ufcf, final_ebitda, wacc, "exit_multiple", 0.0, multiple, bridge
                )
            except ValueError:
                table.loc[wacc, multiple] = float("nan")
    return table