"""
explore_market.py — Step 17: get a company's market data and cross-check it with the SEC data.

Change TICKER to try another company. Run with:  python explore_market.py
"""

from src.display import print_summary, print_warnings
from src.market import check_market_data, fetch_market_data
from src.sec import download_company_facts
from src.sec_financials import build_sec_historicals, latest_cover_shares

TICKER = "AAPL"


def main() -> None:
    # Facts from the SEC (cached from Steps 15-16).
    download = download_company_facts(TICKER)
    sec = build_sec_historicals(download.facts)
    cover_shares_m, shares_date = latest_cover_shares(download.facts)
    latest_year = sec.raw.columns[-1]

    # Market data from Yahoo Finance.
    quote, source = fetch_market_data(TICKER)
    warnings = check_market_data(quote, cover_shares_m)

    # The market's view of the whole company: the equity bridge in reverse (Step 9).
    market_cap = quote.share_price * cover_shares_m
    cash = sec.raw.loc["cash", latest_year]
    debt = sec.raw.loc["total_debt", latest_year]
    market_ev = market_cap - cash + debt
    ebitda = (sec.raw.loc["revenue", latest_year] - sec.raw.loc["cogs", latest_year]
              - sec.raw.loc["operating_expenses", latest_year]
              + sec.raw.loc["depreciation_amortization", latest_year])

    def optional(value, fmt):
        return "n/a" if value is None else format(value, fmt)

    rows = [
        ("Price (RETRIEVED from Yahoo)", ""),
        ("  Last close", f"${quote.share_price:,.2f}"),
        ("  Price date", quote.price_date),
        ("  Currency", optional(quote.currency, "")),
        ("  Data source this run", source),
        ("Beta", ""),
        ("  Our beta (5y monthly vs S&P 500)", optional(quote.calculated_beta, ".2f")),
        ("  Monthly returns used", str(quote.beta_months)),
        ("  Yahoo's published beta", optional(quote.yahoo_beta, ".2f")),
        ("Shares (millions)", ""),
        (f"  SEC 10-K cover page ({shares_date})", f"{cover_shares_m:,.1f}"),
        ("  Yahoo", optional(quote.yahoo_shares_m, ",.1f")),
        (f"Market valuation ($ millions, balance sheet FY{latest_year})", ""),
        ("  Market cap (price x SEC shares)", f"{market_cap:,.0f}"),
        ("  - Cash (SEC)", f"{cash:,.0f}"),
        ("  + Debt (SEC)", f"{debt:,.0f}"),
        ("  = Market enterprise value", f"{market_ev:,.0f}"),
        (f"  EV / FY{latest_year} EBITDA", f"{market_ev / ebitda:.1f}x"),
    ]
    print_summary(f"Market Data: {download.company_name} ({TICKER})", rows)
    print(f"Source: {quote.source}")
    print_warnings("Market data checks", warnings)


if __name__ == "__main__":
    main()