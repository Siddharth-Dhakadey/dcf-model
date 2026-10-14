"""
Unit tests for turning SEC facts into the model's historical table.
They use small made-up data, so they run without internet.
"""

import pytest

from src.sec_financials import annual_facts, build_sec_historicals

ENDS = ["2023-12-31", "2024-12-31"]
STARTS = ["2023-01-01", "2024-01-01"]


def year_entries(values, filed="2025-02-01", accn="new"):
    """Two full fiscal years of a duration item, in dollars."""
    return [
        {"start": s, "end": e, "val": v, "fy": 2024, "fp": "FY", "form": "10-K", "filed": filed, "accn": accn}
        for s, e, v in zip(STARTS, ENDS, values)
    ]


def balance_entries(values):
    """Two year-end balances of an instant item, in dollars."""
    return [
        {"end": e, "val": v, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "accn": "new"}
        for e, v in zip(ENDS, values)
    ]


def make_facts(**overrides):
    """A tiny company that reports every required tag (values in dollars)."""
    m = 1_000_000
    tags = {
        "Revenues": year_entries([1000 * m, 1100 * m]),
        "CostOfRevenue": year_entries([600 * m, 650 * m]),
        "OperatingIncomeLoss": year_entries([200 * m, 230 * m]),
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest":
            year_entries([190 * m, 225 * m]),
        "IncomeTaxExpenseBenefit": year_entries([40 * m, 45 * m]),
        "NetIncomeLoss": year_entries([150 * m, 180 * m]),
        "DepreciationAndAmortization": year_entries([30 * m, 33 * m]),
        "PaymentsToAcquirePropertyPlantAndEquipment": year_entries([35 * m, 38 * m]),
        "AccountsReceivableNetCurrent": balance_entries([80 * m, 90 * m]),
        "AccountsPayableCurrent": balance_entries([70 * m, 75 * m]),
        "CashAndCashEquivalentsAtCarryingValue": balance_entries([100 * m, 120 * m]),
        "LongTermDebtNoncurrent": balance_entries([300 * m, 280 * m]),
        "LongTermDebtCurrent": balance_entries([20 * m, 20 * m]),
    }
    tags.update(overrides)
    usgaap = {tag: {"units": {"USD": entries}} for tag, entries in tags.items()}
    usgaap["WeightedAverageNumberOfDilutedSharesOutstanding"] = {
        "units": {"shares": year_entries([50 * m, 49 * m])}
    }
    return {"facts": {"us-gaap": usgaap}}


def test_latest_filing_wins_when_a_year_is_reported_twice():
    old = year_entries([999, 999], filed="2024-02-01", accn="old")
    new = year_entries([1000, 1100], filed="2025-02-01", accn="new")
    table = annual_facts({"facts": {"us-gaap": {"Revenues": {"units": {"USD": old + new}}}}},
                         "Revenues", "duration")
    assert table["value"].tolist() == [1000, 1100]
    assert table["accn"].tolist() == ["new", "new"]


def test_values_are_converted_to_millions_and_labelled_by_year():
    sec = build_sec_historicals(make_facts(), years=2)
    assert list(sec.raw.columns) == [2023, 2024]
    assert sec.raw.loc["revenue", 2024] == pytest.approx(1100.0)
    assert sec.raw.loc["diluted_shares", 2024] == pytest.approx(49.0)


def test_debt_adds_its_components():
    sec = build_sec_historicals(make_facts(), years=2)
    assert sec.raw.loc["total_debt", 2024] == pytest.approx(300.0)     # 280 + 20


def test_derived_items_tie_to_reported_ebit_and_pretax():
    sec = build_sec_historicals(make_facts(), years=2)
    # operating expenses = 1,100 - 650 - 230 = 220 ; net non-operating = 230 - 225 = 5
    assert sec.raw.loc["operating_expenses", 2024] == pytest.approx(220.0)
    assert sec.raw.loc["interest_expense", 2024] == pytest.approx(5.0)


def test_absent_optional_items_become_zero_and_are_flagged():
    sec = build_sec_historicals(make_facts(), years=2)
    assert sec.raw.loc["inventory", 2024] == 0.0
    assert sec.provenance.loc["preferred_stock", "source"] == "ASSUMED 0"
    assert any("preferred_stock" in w for w in sec.warnings)


def test_missing_required_item_stops_with_clear_message():
    facts = make_facts()
    del facts["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]
    with pytest.raises(ValueError, match="capex"):
        build_sec_historicals(facts, years=2)