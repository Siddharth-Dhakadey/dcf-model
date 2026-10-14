"""
company.py — Builds the CompanyInputs for a ticker.

    "MAPLE"  -> the hypothetical company from Stage A
    anything else -> SEC filings (facts) + Yahoo (price) + config/<ticker>.py (your judgements)
"""

import importlib

from src.assumptions import maple_base_case, maple_terminal_assumptions, maple_wacc_assumptions
from src.data import SAMPLE_COMPANY_NAME, load_sample_company, load_sample_market_data
from src.market import check_market_data, fetch_market_data
from src.model import CompanyInputs
from src.scenarios import maple_scenarios
from src.sec import download_company_facts
from src.sec_financials import build_sec_historicals, latest_balance_sheet, latest_cover_shares


def load_company(ticker: str) -> CompanyInputs:
    """Return everything the model needs for one company."""
    if ticker.upper() == "MAPLE":
        return load_maple()
    return load_public_company(ticker)


def load_maple() -> CompanyInputs:
    """The hypothetical Maple Coffee Co. from Stage A."""
    raw = load_sample_company()
    market = load_sample_market_data()
    year = int(raw.columns[-1])
    bridge = {item: float(raw.loc[item, year]) for item in
              ["cash", "total_debt", "preferred_stock", "minority_interest", "diluted_shares"]}
    return CompanyInputs(
        name=SAMPLE_COMPANY_NAME, ticker="MAPLE", raw=raw,
        share_price=market.share_price, price_date=market.price_date,
        bridge=bridge, bridge_date=f"FY{year} balance sheet",
        forecast=maple_base_case(), wacc=maple_wacc_assumptions(), terminal=maple_terminal_assumptions(),
        scenarios=maple_scenarios,
        notes=["Hypothetical company with hand-entered data (Stage A)."],
    )


def load_public_company(ticker: str) -> CompanyInputs:
    """A real company: SEC facts + market data + the analyst's config file."""
    ticker = ticker.upper()
    module_name = f"config.{ticker.lower()}"
    try:
        config = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name not in (module_name, "config"):
            raise      # the config file exists but something IT imports is missing: show the real error
        raise RuntimeError(
            f"No assumptions file for {ticker}: expected config/{ticker.lower()}.py in the project folder\n"
            "  (with an empty config/__init__.py next to it). For a new company, copy config/aapl.py."
        ) from None

    # --- Facts ---
    download = download_company_facts(ticker)
    sec = build_sec_historicals(download.facts, years=config.HISTORY_YEARS)
    quote, _ = fetch_market_data(ticker)
    cover_shares, cover_date = latest_cover_shares(download.facts)
    latest_year = int(sec.raw.columns[-1])
    notes: list[str] = []

    # --- Balance sheet for the equity bridge ---
    groups = {
        "cash": sec.provenance.loc["cash", "tags"].split(" + "),
        "total_debt": sec.provenance.loc["total_debt", "tags"].split(" + "),
    }
    if config.INCLUDE_LONG_TERM_SECURITIES_IN_CASH:
        groups["long_term_securities"] = ["MarketableSecuritiesNoncurrent"]

    if config.USE_LATEST_BALANCE_SHEET:
        balances, bs_date, form = latest_balance_sheet(download.facts, groups)
    else:
        balances = {"cash": float(sec.raw.loc["cash", latest_year]),
                    "total_debt": float(sec.raw.loc["total_debt", latest_year])}
        if "long_term_securities" in groups:
            balances["long_term_securities"] = float(sec.memo.loc["long_term_marketable_securities", latest_year])
        bs_date, form = sec.period_ends[latest_year], "10-K"
    bridge_date = f"{bs_date} ({form})"

    cash = balances["cash"]
    debt = balances["total_debt"]
    notes.append(f"Balance sheet date for cash and debt: {bridge_date}")
    notes.append(f"Cash = {' + '.join(groups['cash'])}: {cash:,.0f}")
    notes.append(f"Debt = {' + '.join(groups['total_debt'])}: {debt:,.0f} (lease liabilities NOT included)")
    if "long_term_securities" in balances:
        cash += balances["long_term_securities"]
        notes.append(f"OVERRIDE: long-term marketable securities added to cash: +{balances['long_term_securities']:,.0f}")

    if config.SHARE_COUNT == "latest_cover":
        shares = cover_shares
        notes.append(f"OVERRIDE: shares = latest cover-page count {shares:,.1f}m ({cover_date}); "
                     "basic shares, so a small dilution effect is ignored")
    else:
        shares = float(sec.raw.loc["diluted_shares", latest_year])
        notes.append(f"Shares = FY{latest_year} weighted-average diluted: {shares:,.1f}m")

    bridge = {
        "cash": cash,
        "total_debt": debt,
        "preferred_stock": float(sec.raw.loc["preferred_stock", latest_year]),
        "minority_interest": float(sec.raw.loc["minority_interest", latest_year]),
        "diluted_shares": shares,
    }

    return CompanyInputs(
        name=config.COMPANY_NAME, ticker=ticker, raw=sec.raw,
        share_price=quote.share_price, price_date=quote.price_date,
        bridge=bridge, bridge_date=bridge_date,
        forecast=config.FORECAST, wacc=config.WACC, terminal=config.TERMINAL,
        scenarios=config.scenarios,
        notes=notes,
        data_warnings=sec.warnings + check_market_data(quote, cover_shares),
    )