"""
Unit tests for the SEC helpers. These use small made-up data,
so they run without internet and never contact the SEC.
"""

import pytest

from src.sec import annual_values, find_cik

FAKE_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}


def test_find_cik_pads_to_ten_digits():
    assert find_cik(FAKE_TICKERS, "AAPL") == ("0000320193", "Apple Inc.")


def test_find_cik_ignores_case_and_spaces():
    assert find_cik(FAKE_TICKERS, " msft ")[0] == "0000789019"


def test_unknown_ticker_is_rejected():
    with pytest.raises(ValueError, match="not found"):
        find_cik(FAKE_TICKERS, "ZZZZ")


def test_annual_values_keeps_only_full_years_from_10k():
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        # a full fiscal year in a 10-K -> kept
        {"start": "2024-01-01", "end": "2024-12-31", "val": 1_000_000_000,
         "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "accn": "a"},
        # a single quarter reported inside the same 10-K -> dropped
        {"start": "2024-10-01", "end": "2024-12-31", "val": 300_000_000,
         "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01", "accn": "a"},
        # a quarterly report (10-Q) -> dropped
        {"start": "2025-01-01", "end": "2025-03-31", "val": 250_000_000,
         "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": "2025-05-01", "accn": "b"},
    ]}}}}}

    table = annual_values(facts, "Revenues")

    assert len(table) == 1
    assert table.loc[0, "value_$m"] == pytest.approx(1000.0)   # converted from dollars to millions


def test_missing_concept_returns_empty_table():
    assert annual_values({"facts": {"us-gaap": {}}}, "Revenues").empty