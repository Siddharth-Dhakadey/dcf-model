"""
Tests for the full model pipeline.

The Maple Coffee results from Stage A are used as a REGRESSION test: if a future
change accidentally alters any formula, these known answers will stop matching.
"""

import pytest

from src.company import load_company
from src.model import run_model
from src.sec_financials import latest_balance_sheet


def test_maple_valuation_is_unchanged():
    results = run_model(load_company("MAPLE"))
    assert results.wacc.wacc == pytest.approx(0.0849, abs=0.0001)
    assert results.valuation.enterprise_value == pytest.approx(2837.0, abs=0.1)
    assert results.valuation.implied_share_price == pytest.approx(52.74, abs=0.01)


def test_maple_scenarios_are_unchanged():
    prices = {r.name: r.implied_share_price for r in run_model(load_company("MAPLE")).scenario_results}
    assert prices["Bear"] == pytest.approx(33.52, abs=0.01)
    assert prices["Base"] == pytest.approx(52.74, abs=0.01)
    assert prices["Bull"] == pytest.approx(67.39, abs=0.01)


def test_unknown_company_without_config_gives_clear_error():
    with pytest.raises(RuntimeError, match="No assumptions file"):
        load_company("ZZZZ")


def test_latest_balance_sheet_uses_one_common_date():
    def entry(end, val, form="10-Q"):
        return {"end": end, "val": val, "form": form, "filed": end}

    facts = {"facts": {"us-gaap": {
        "Cash": {"units": {"USD": [entry("2026-03-31", 10_000_000), entry("2026-06-30", 12_000_000)]}},
        # debt has no June figure yet, so March is the latest date where BOTH exist
        "Debt": {"units": {"USD": [entry("2026-03-31", 5_000_000)]}},
    }}}
    values, as_of, form = latest_balance_sheet(facts, {"cash": ["Cash"], "total_debt": ["Debt"]})
    assert as_of == "2026-03-31"
    assert values == {"cash": pytest.approx(10.0), "total_debt": pytest.approx(5.0)}
    assert form == "10-Q"