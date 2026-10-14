"""
Unit tests for the valuation: WACC, discounting, terminal value, the equity bridge
and the implied share price.

Every expected number here can be checked by hand with a calculator.
Run all tests from the project folder with:  python -m pytest -v
"""

import pandas as pd
import pytest

from src.assumptions import TerminalAssumptions, WaccAssumptions
from src.sensitivity import centered_values, implied_share_price
from src.valuation import (
    after_tax_cost_of_debt,
    calculate_equity_value,
    calculate_terminal_value,
    calculate_wacc,
    cost_of_equity,
    discount_cash_flows,
    terminal_value_exit_multiple,
    terminal_value_perpetuity,
)


# --- WACC ------------------------------------------------------------------

def test_cost_of_equity_capm():
    # 4.25% + 1.10 x 5.00% = 9.75%
    assert cost_of_equity(0.0425, 1.10, 0.05) == pytest.approx(0.0975)


def test_after_tax_cost_of_debt():
    # 5% x (1 - 25%) = 3.75%
    assert after_tax_cost_of_debt(0.05, 0.25) == pytest.approx(0.0375)


def test_wacc_weights_and_rate():
    # Cost of equity = 4% + 1.2 x 5% = 10%. After-tax cost of debt = 5% x (1 - 20%) = 4%.
    # Equity 600, debt 400 -> weights 60% / 40%.
    # WACC = 60% x 10% + 40% x 4% = 7.6%
    w = WaccAssumptions(
        risk_free_rate=0.04, beta=1.2, equity_risk_premium=0.05,
        pre_tax_cost_of_debt=0.05, tax_rate=0.20,
    )
    result = calculate_wacc(w, equity_value=600.0, debt_value=400.0)

    assert result.equity_weight == pytest.approx(0.60)
    assert result.debt_weight == pytest.approx(0.40)
    assert result.wacc == pytest.approx(0.076)


# --- Discounting -----------------------------------------------------------

def test_discount_factors_and_present_values():
    ufcf = pd.Series([110.0, 121.0], index=[2026, 2027])
    table = discount_cash_flows(ufcf, wacc=0.10)

    assert table.loc["discount_factor", 2026] == pytest.approx(1 / 1.10)     # 0.9091
    assert table.loc["discount_factor", 2027] == pytest.approx(1 / 1.21)     # 0.8264
    # 110 / 1.10 = 100 and 121 / 1.21 = 100
    assert table.loc["pv_ufcf"].tolist() == pytest.approx([100.0, 100.0])


# --- Terminal value --------------------------------------------------------

def test_terminal_value_perpetuity_growth():
    # 100 x 1.02 / (10% - 2%) = 102 / 0.08 = 1,275
    assert terminal_value_perpetuity(100.0, wacc=0.10, growth=0.02) == pytest.approx(1275.0)


def test_terminal_value_exit_multiple():
    # 50 x 8 = 400
    assert terminal_value_exit_multiple(50.0, 8.0) == pytest.approx(400.0)


def test_growth_equal_to_wacc_is_rejected():
    with pytest.raises(ValueError, match="must be greater than the terminal growth rate"):
        terminal_value_perpetuity(100.0, wacc=0.05, growth=0.05)


def test_growth_above_wacc_is_rejected():
    with pytest.raises(ValueError):
        terminal_value_perpetuity(100.0, wacc=0.05, growth=0.06)


# --- Enterprise value -> equity value -> share price -----------------------

def test_equity_bridge_and_share_price():
    # EV 1,000 = 400 + 600. Equity = 1,000 + 100 cash - 300 debt - 50 preferred - 25 minority = 725
    result = calculate_equity_value(
        pv_forecast_ufcf=400.0, pv_terminal_value=600.0,
        cash=100.0, total_debt=300.0, preferred_stock=50.0, minority_interest=25.0,
        diluted_shares=10.0,
    )
    assert result.enterprise_value == pytest.approx(1000.0)
    assert result.equity_value == pytest.approx(725.0)
    assert result.implied_share_price == pytest.approx(72.5)
    assert result.tv_share_of_ev == pytest.approx(0.60)


def test_zero_shares_is_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_equity_value(400.0, 600.0, 100.0, 300.0, 0.0, 0.0, diluted_shares=0.0)


def test_negative_debt_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_equity_value(400.0, 600.0, 100.0, -300.0, 0.0, 0.0, diluted_shares=10.0)


def test_step_2_worked_example_end_to_end():
    """The Maple Coffee example worked by hand in Step 2."""
    ufcf = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0], index=[2026, 2027, 2028, 2029, 2030])
    wacc = 0.10
    terminal_inputs = TerminalAssumptions(
        terminal_growth_rate=0.025, exit_multiple=10.0, method="perpetuity_growth"
    )

    pv_forecast = discount_cash_flows(ufcf, wacc).loc["pv_ufcf"].sum()
    # final_ebitda only matters for the exit multiple method; any positive number works here.
    tv = calculate_terminal_value(140.0, 1.0, wacc, terminal_inputs, years_to_discount=5)
    result = calculate_equity_value(pv_forecast, tv.selected_pv_tv, 200.0, 400.0, 0.0, 0.0, 50.0)

    assert pv_forecast == pytest.approx(447.7, abs=0.1)
    assert tv.tv_perpetuity == pytest.approx(1913.3, abs=0.1)
    assert result.enterprise_value == pytest.approx(1635.7, abs=0.1)
    assert result.equity_value == pytest.approx(1435.7, abs=0.1)
    assert result.implied_share_price == pytest.approx(28.71, abs=0.01)


# --- Sensitivity -----------------------------------------------------------

def test_centered_values_put_base_case_in_the_middle():
    values = centered_values(0.025, step=0.005)
    assert values == pytest.approx([0.010, 0.015, 0.020, 0.025, 0.030, 0.035, 0.040])
    assert values[len(values) // 2] == pytest.approx(0.025)


def test_sensitivity_engine_reproduces_step_2_example():
    ufcf = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0], index=[2026, 2027, 2028, 2029, 2030])
    bridge = {
        "cash": 200.0, "total_debt": 400.0, "preferred_stock": 0.0,
        "minority_interest": 0.0, "diluted_shares": 50.0,
    }
    price = implied_share_price(ufcf, 1.0, 0.10, "perpetuity_growth", 0.025, 0.0, bridge)
    assert price == pytest.approx(28.71, abs=0.01)