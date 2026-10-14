"""
valuation.py — Turns forecast cash flows into value.

Step 7: WACC, the discount rate.
Step 8: discounting the forecast cash flows, and the terminal value.
Step 9: enterprise value, the equity bridge and the implied share price.
"""

from dataclasses import dataclass

import pandas as pd

from src.assumptions import TerminalAssumptions, WaccAssumptions


@dataclass
class WaccResult:
    """Every piece of the WACC calculation, kept so it can be shown and checked."""

    cost_of_equity: float
    after_tax_cost_of_debt: float
    equity_value: float
    debt_value: float
    equity_weight: float
    debt_weight: float
    wacc: float


def cost_of_equity(risk_free_rate: float, beta: float, equity_risk_premium: float) -> float:
    """CAPM: Cost of Equity = Risk-Free Rate + Beta x Equity Risk Premium."""
    return risk_free_rate + beta * equity_risk_premium


def after_tax_cost_of_debt(pre_tax_cost_of_debt: float, tax_rate: float) -> float:
    """Interest is tax-deductible, so debt really costs: Pre-Tax Cost x (1 - Tax Rate)."""
    return pre_tax_cost_of_debt * (1 - tax_rate)


def calculate_wacc(w: WaccAssumptions, equity_value: float, debt_value: float) -> WaccResult:
    """
    WACC = E/(D+E) x Cost of Equity + D/(D+E) x Cost of Debt x (1 - Tax Rate)

    equity_value: market value of equity (share price x diluted shares), $ millions
    debt_value:   value of total debt, $ millions
    """
    if equity_value <= 0:
        raise ValueError("Equity value (market capitalization) must be greater than zero.")
    if debt_value < 0:
        raise ValueError("Debt cannot be negative.")

    total_capital = equity_value + debt_value
    equity_weight = equity_value / total_capital
    debt_weight = debt_value / total_capital

    ke = cost_of_equity(w.risk_free_rate, w.beta, w.equity_risk_premium)
    kd = after_tax_cost_of_debt(w.pre_tax_cost_of_debt, w.tax_rate)

    wacc = equity_weight * ke + debt_weight * kd

    return WaccResult(
        cost_of_equity=ke,
        after_tax_cost_of_debt=kd,
        equity_value=equity_value,
        debt_value=debt_value,
        equity_weight=equity_weight,
        debt_weight=debt_weight,
        wacc=wacc,
    )


def discount_cash_flows(ufcf: pd.Series, wacc: float) -> pd.DataFrame:
    """
    Discount each year's UFCF back to today (end-of-year convention):

        Discount Factor_t = 1 / (1 + WACC)^t
        PV of UFCF_t      = UFCF_t x Discount Factor_t
    """
    periods = pd.Series(range(1, len(ufcf) + 1), index=ufcf.index)   # t = 1, 2, 3, ...
    discount_factors = 1 / (1 + wacc) ** periods
    present_values = ufcf * discount_factors

    table = {
        "ufcf": ufcf,
        "discount_period": periods,
        "discount_factor": discount_factors,
        "pv_ufcf": present_values,
    }
    return pd.DataFrame(table).T


def terminal_value_perpetuity(final_ufcf: float, wacc: float, growth: float) -> float:
    """
    Perpetuity growth method:
        TV = Final-Year UFCF x (1 + g) / (WACC - g)
    Only valid when WACC is greater than g.
    """
    if wacc <= growth:
        raise ValueError(
            f"WACC ({wacc:.2%}) must be greater than the terminal growth rate ({growth:.2%}).\n"
            "  The formula divides by (WACC - g). If g reaches WACC, the result is infinite or\n"
            "  negative, which is meaningless. Lower the terminal growth rate or check the WACC."
        )
    if final_ufcf <= 0:
        raise ValueError(
            f"Final-year UFCF is {final_ufcf:,.1f}. The perpetuity method needs a positive cash flow\n"
            "  (a negative one would mean losing money forever). Revisit the final-year assumptions\n"
            "  or use the exit multiple method."
        )
    return final_ufcf * (1 + growth) / (wacc - growth)


def terminal_value_exit_multiple(final_ebitda: float, multiple: float) -> float:
    """
    Exit multiple method:
        TV = Final-Year EBITDA x Exit EV/EBITDA Multiple
    """
    if multiple <= 0:
        raise ValueError("Exit multiple must be greater than zero.")
    return final_ebitda * multiple


@dataclass
class TerminalValueResult:
    """Both terminal value methods side by side, plus the cross-checks between them."""

    method: str
    tv_perpetuity: float
    tv_exit_multiple: float
    implied_multiple: float          # EV/EBITDA implied by the perpetuity TV
    implied_growth: float            # perpetual growth implied by the exit multiple TV
    discount_factor: float           # for the final forecast year
    pv_tv_perpetuity: float
    pv_tv_exit_multiple: float
    selected_tv: float
    selected_pv_tv: float


def calculate_terminal_value(
    final_ufcf: float,
    final_ebitda: float,
    wacc: float,
    t: TerminalAssumptions,
    years_to_discount: int,
) -> TerminalValueResult:
    """Calculate the terminal value both ways, cross-check them, and discount them to today."""
    tv_perp = terminal_value_perpetuity(final_ufcf, wacc, t.terminal_growth_rate)
    tv_exit = terminal_value_exit_multiple(final_ebitda, t.exit_multiple)

    # Cross-checks: what does each method imply about the other?
    implied_multiple = tv_perp / final_ebitda
    implied_growth = (tv_exit * wacc - final_ufcf) / (tv_exit + final_ufcf)

    # The terminal value sits at the END of the final forecast year,
    # so it is discounted with that year's discount factor.
    factor = 1 / (1 + wacc) ** years_to_discount
    pv_perp = tv_perp * factor
    pv_exit = tv_exit * factor

    if t.method == "perpetuity_growth":
        selected_tv, selected_pv = tv_perp, pv_perp
    else:
        selected_tv, selected_pv = tv_exit, pv_exit

    return TerminalValueResult(
        method=t.method,
        tv_perpetuity=tv_perp,
        tv_exit_multiple=tv_exit,
        implied_multiple=implied_multiple,
        implied_growth=implied_growth,
        discount_factor=factor,
        pv_tv_perpetuity=pv_perp,
        pv_tv_exit_multiple=pv_exit,
        selected_tv=selected_tv,
        selected_pv_tv=selected_pv,
    )


@dataclass
class ValuationResult:
    """Enterprise value -> equity value -> implied share price, with every step kept."""

    pv_forecast_ufcf: float
    pv_terminal_value: float
    enterprise_value: float
    tv_share_of_ev: float
    cash: float
    total_debt: float
    preferred_stock: float
    minority_interest: float
    equity_value: float
    diluted_shares: float
    implied_share_price: float


def calculate_equity_value(
    pv_forecast_ufcf: float,
    pv_terminal_value: float,
    cash: float,
    total_debt: float,
    preferred_stock: float,
    minority_interest: float,
    diluted_shares: float,
) -> ValuationResult:
    """
    Enterprise Value = PV of forecast UFCF + PV of terminal value
    Equity Value     = Enterprise Value + Cash - Debt - Preferred Stock - Minority Interest
    Implied Price    = Equity Value / Diluted Shares Outstanding
    """
    if diluted_shares <= 0:
        raise ValueError("Diluted shares outstanding must be greater than zero.")
    for name, value in {
        "cash": cash,
        "total debt": total_debt,
        "preferred stock": preferred_stock,
        "minority interest": minority_interest,
    }.items():
        if value < 0:
            raise ValueError(f"{name} cannot be negative (got {value}). Enter balances as positive numbers.")

    enterprise_value = pv_forecast_ufcf + pv_terminal_value
    equity_value = enterprise_value + cash - total_debt - preferred_stock - minority_interest

    return ValuationResult(
        pv_forecast_ufcf=pv_forecast_ufcf,
        pv_terminal_value=pv_terminal_value,
        enterprise_value=enterprise_value,
        tv_share_of_ev=pv_terminal_value / enterprise_value,
        cash=cash,
        total_debt=total_debt,
        preferred_stock=preferred_stock,
        minority_interest=minority_interest,
        equity_value=equity_value,
        diluted_shares=diluted_shares,
        implied_share_price=equity_value / diluted_shares,
    )


def market_enterprise_value(
    market_cap: float, cash: float, total_debt: float, preferred_stock: float, minority_interest: float
) -> float:
    """The same bridge in reverse: what the MARKET is paying for the whole business."""
    return market_cap - cash + total_debt + preferred_stock + minority_interest


def upside_downside(implied_price: float, current_price: float) -> float:
    """How far the implied price is above (+) or below (-) the current share price."""
    return implied_price / current_price - 1


def check_valuation(result: ValuationResult, current_price: float) -> list[str]:
    """Warn about results an analyst should investigate before trusting them."""
    warnings: list[str] = []

    if result.equity_value <= 0:
        warnings.append(
            "Equity value is zero or negative: debt and other claims exceed the value of the "
            "business. The implied share price is not meaningful."
        )
    if result.tv_share_of_ev > 0.75:
        warnings.append(
            f"Terminal value is {result.tv_share_of_ev:.0%} of enterprise value. Most of the value "
            "comes from years after the forecast, so test the terminal assumptions carefully."
        )

    gap = upside_downside(result.implied_share_price, current_price)
    if abs(gap) > 0.50:
        direction = "above" if gap > 0 else "below"
        warnings.append(
            f"Implied price is {abs(gap):.0%} {direction} the market price. Before concluding the "
            "stock is mispriced, re-check: growth and margin assumptions, WACC, terminal value, "
            "the data (cash, debt, shares) and the valuation date."
        )
    return warnings