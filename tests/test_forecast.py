"""
Unit tests for the forecast: revenue, income statement, NOPAT and UFCF.

Every expected number here can be checked by hand with a calculator.
Run all tests from the project folder with:  python -m pytest -v
"""

from dataclasses import replace

import pytest

from src.assumptions import ForecastAssumptions, validate_assumptions
from src.forecast import (
    forecast_free_cash_flow,
    forecast_income_statement,
    forecast_ratios,
    forecast_revenue,
)


def one_year_assumptions() -> ForecastAssumptions:
    """A simple 1-year test company with round numbers."""
    return ForecastAssumptions(
        revenue_growth=[0.10],      # revenue 1,000 -> 1,100
        gross_margin=[0.50],        # gross profit 550
        ebit_margin=[0.20],         # EBIT 220
        tax_rate=[0.25],            # taxes on EBIT 55 -> NOPAT 165
        da_pct_revenue=[0.05],      # D&A 55
        capex_pct_revenue=[0.06],   # CapEx 66
        nwc_pct_revenue=[0.10],     # NWC 110
    )


# --- Revenue ---------------------------------------------------------------

def test_revenue_compounds_year_by_year():
    # 100 x 1.10 = 110, then 110 x 1.20 = 132
    assert forecast_revenue(100.0, [0.10, 0.20]) == pytest.approx([110.0, 132.0])


def test_zero_growth_keeps_revenue_flat():
    assert forecast_revenue(500.0, [0.0, 0.0, 0.0]) == pytest.approx([500.0, 500.0, 500.0])


# --- Income statement ------------------------------------------------------

def test_income_statement_lines():
    fc = forecast_income_statement(1000.0, one_year_assumptions(), first_year=2026)
    year = fc[2026]

    assert year["revenue"] == pytest.approx(1100.0)
    assert year["gross_profit"] == pytest.approx(550.0)       # 1,100 x 50%
    assert year["cogs"] == pytest.approx(550.0)               # 1,100 - 550
    assert year["ebit"] == pytest.approx(220.0)               # 1,100 x 20%
    assert year["operating_expenses"] == pytest.approx(330.0) # 550 - 220
    assert year["depreciation_amortization"] == pytest.approx(55.0)
    assert year["ebitda"] == pytest.approx(275.0)             # 220 + 55


def test_nopat_is_ebit_after_tax():
    fc = forecast_income_statement(1000.0, one_year_assumptions(), first_year=2026)
    assert fc.loc["operating_taxes", 2026] == pytest.approx(55.0)   # 220 x 25%
    assert fc.loc["nopat", 2026] == pytest.approx(165.0)            # 220 - 55


def test_forecast_ratios_match_the_assumptions():
    a = one_year_assumptions()
    fc = forecast_income_statement(1000.0, a, first_year=2026)
    ratios = forecast_ratios(fc, last_actual_revenue=1000.0)

    assert ratios.loc["revenue_growth", 2026] == pytest.approx(0.10)
    assert ratios.loc["gross_margin", 2026] == pytest.approx(0.50)
    assert ratios.loc["ebit_margin", 2026] == pytest.approx(0.20)
    assert ratios.loc["tax_rate", 2026] == pytest.approx(0.25)


# --- Unlevered free cash flow ----------------------------------------------

def test_ufcf_formula():
    a = one_year_assumptions()
    fc = forecast_income_statement(1000.0, a, first_year=2026)
    ufcf = forecast_free_cash_flow(fc, a, last_actual_nwc=100.0)

    # NWC rises from 100 to 110, so 10 of cash is tied up.
    # UFCF = NOPAT 165 + D&A 55 - CapEx 66 - increase in NWC 10 = 144
    assert ufcf.loc["less_change_in_nwc", 2026] == pytest.approx(-10.0)
    assert ufcf.loc["ufcf", 2026] == pytest.approx(144.0)


def test_falling_nwc_releases_cash():
    a = one_year_assumptions()
    fc = forecast_income_statement(1000.0, a, first_year=2026)
    ufcf = forecast_free_cash_flow(fc, a, last_actual_nwc=130.0)

    # NWC falls from 130 to 110: 20 of cash is released, so UFCF = 165 + 55 - 66 + 20 = 174
    assert ufcf.loc["ufcf", 2026] == pytest.approx(174.0)


# --- Validation ------------------------------------------------------------

def test_ebit_margin_above_gross_margin_is_rejected():
    bad = replace(one_year_assumptions(), ebit_margin=[0.60])   # above the 50% gross margin
    with pytest.raises(ValueError, match="must be below gross margin"):
        validate_assumptions(bad)


def test_lists_of_different_lengths_are_rejected():
    bad = replace(one_year_assumptions(), tax_rate=[0.25, 0.25])   # 2 values, others have 1
    with pytest.raises(ValueError, match="one value per forecast year"):
        validate_assumptions(bad)