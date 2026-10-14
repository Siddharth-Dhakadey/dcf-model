"""
Unit tests for market-data calculations and checks.
They use made-up prices, so they run without internet and never contact Yahoo.
"""

from datetime import date

import pandas as pd
import pytest

from src.market import MarketQuote, calculate_beta, check_market_data
from src.sec_financials import latest_cover_shares

MONTHS = pd.period_range("2021-01", periods=37, freq="M")


def market_prices() -> pd.Series:
    """A made-up index that zig-zags: +2%, -1%, +2%, -1%, ..."""
    returns = [0.02 if i % 2 == 0 else -0.01 for i in range(36)]
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return pd.Series(prices, index=MONTHS)


def test_stock_that_moves_twice_as_much_has_beta_two():
    market = market_prices()
    stock = 50 * (1 + 2 * market.pct_change().fillna(0)).cumprod()    # every return doubled
    beta, months = calculate_beta(stock, market)
    assert beta == pytest.approx(2.0)
    assert months == 36


def test_too_little_history_is_rejected():
    market = market_prices().iloc[:10]
    with pytest.raises(ValueError, match="at least 24"):
        calculate_beta(market, market)


def make_quote(**changes) -> MarketQuote:
    values = dict(
        ticker="TEST", share_price=100.0, price_date="2026-10-12", currency="USD",
        calculated_beta=1.1, beta_months=60, yahoo_beta=1.2, yahoo_shares_m=1000.0,
        retrieved_on="2026-10-13",
    )
    values.update(changes)
    return MarketQuote(**values)


def test_clean_quote_has_no_warnings():
    assert check_market_data(make_quote(), sec_shares_m=1000.0, today=date(2026, 10, 13)) == []


def test_stale_price_and_share_mismatch_are_flagged():
    quote = make_quote(price_date="2026-09-01", yahoo_shares_m=4000.0)
    warnings = check_market_data(quote, sec_shares_m=1000.0, today=date(2026, 10, 13))
    assert any("days old" in w for w in warnings)
    assert any("differ from the SEC" in w for w in warnings)


def test_non_usd_price_is_flagged():
    warnings = check_market_data(make_quote(currency="CAD"), 1000.0, today=date(2026, 10, 13))
    assert any("CAD" in w for w in warnings)


def test_latest_cover_shares_picks_most_recent_date():
    facts = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2024-10-18", "val": 15_115_823_000, "filed": "2024-11-01"},
        {"end": "2025-10-17", "val": 14_776_353_000, "filed": "2025-10-31"},
    ]}}}}}
    shares_m, as_of = latest_cover_shares(facts)
    assert shares_m == pytest.approx(14776.353)
    assert as_of == "2025-10-17"