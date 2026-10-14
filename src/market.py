"""
market.py — Market data (share price and beta) from Yahoo Finance, via the yfinance library.

IMPORTANT: yfinance is UNOFFICIAL. It is not affiliated with Yahoo, it is intended for
research and educational use, and Yahoo's data is for personal use. It can break or be
rate-limited without warning. So:
  - every value is stored together with the date it refers to,
  - results are cached in data/raw/ (we ask Yahoo at most once per day per ticker),
  - the numbers are cross-checked against the SEC filings.
"""

import json
from dataclasses import asdict, dataclass
from datetime import date

import pandas as pd
import yfinance as yf

from src.sec import RAW_DATA_DIR

MARKET_INDEX = "^GSPC"      # the S&P 500, the usual benchmark for US stocks
BETA_PERIOD = "5y"          # 5 years of monthly returns: the most common convention


@dataclass
class MarketQuote:
    """Market data for one company, with dates and sources."""

    ticker: str
    share_price: float               # last closing price, $ per share
    price_date: str                  # the trading day of that closing price
    currency: str | None
    calculated_beta: float | None    # OUR beta: 5 years of monthly returns vs the S&P 500
    beta_months: int                 # how many monthly returns the beta is based on
    yahoo_beta: float | None         # the beta Yahoo publishes (for comparison only)
    yahoo_shares_m: float | None     # shares outstanding according to Yahoo, in millions
    retrieved_on: str
    source: str = "yfinance (unofficial Yahoo Finance data)"


def calculate_beta(stock_prices: pd.Series, market_prices: pd.Series) -> tuple[float, int]:
    """
    Beta = Covariance(stock returns, market returns) / Variance(market returns)

    In words: when the market moves 1%, how much does this stock tend to move?
    Uses monthly price changes. Returns (beta, number of monthly returns used).
    """
    prices = pd.concat({"stock": stock_prices, "market": market_prices}, axis=1).dropna()
    returns = prices.pct_change().dropna()
    if len(returns) < 24:
        raise ValueError(f"Only {len(returns)} monthly returns available; at least 24 are needed for a beta.")
    beta = returns["stock"].cov(returns["market"]) / returns["market"].var()
    return float(beta), len(returns)


def _ask_yahoo(request, what: str):
    """Run one yfinance request and turn any failure into a clear message."""
    try:
        return request()
    except Exception as exc:     # yfinance can fail in many different ways
        raise RuntimeError(
            f"Could not get {what} from Yahoo Finance ({type(exc).__name__}).\n"
            "  yfinance is unofficial and is sometimes blocked or rate-limited.\n"
            "  Wait a few minutes and try again, or check your internet connection."
        ) from None


def _monthly_closes(ticker: str) -> pd.Series:
    """Monthly closing prices (adjusted for splits and dividends), indexed by month."""
    history = _ask_yahoo(
        lambda: yf.Ticker(ticker).history(period=BETA_PERIOD, interval="1mo", auto_adjust=True),
        f"monthly prices for {ticker}",
    )
    closes = history["Close"].dropna()
    closes.index = closes.index.tz_localize(None).to_period("M")   # e.g. 2025-09 for both series
    return closes


def fetch_market_data(ticker: str, refresh: bool = False) -> tuple[MarketQuote, str]:
    """Get price and beta for a ticker. Returns (quote, "cache" or "downloaded")."""
    ticker = ticker.upper()
    cache_file = RAW_DATA_DIR / f"{ticker}_market.json"
    today = date.today().isoformat()

    if cache_file.exists() and not refresh:
        cached = json.loads(cache_file.read_text())
        if cached.get("retrieved_on") == today:
            return MarketQuote(**cached), "cache"

    stock = yf.Ticker(ticker)

    # 1. Latest closing price (NOT adjusted: we want the actual price people pay today).
    recent = _ask_yahoo(lambda: stock.history(period="10d", auto_adjust=False), f"the price of {ticker}")
    if recent.empty:
        raise RuntimeError(f"Yahoo returned no prices for '{ticker}'. Check the ticker symbol.")
    share_price = float(recent["Close"].dropna().iloc[-1])
    price_date = recent.index[-1].date().isoformat()

    # 2. Descriptive info (optional: if Yahoo doesn't provide it, we carry on without it).
    try:
        info = stock.info
    except Exception:
        info = {}
    shares = info.get("sharesOutstanding")

    # 3. Our own beta from 5 years of monthly returns against the S&P 500.
    try:
        beta, months = calculate_beta(_monthly_closes(ticker), _monthly_closes(MARKET_INDEX))
    except ValueError:
        beta, months = None, 0

    quote = MarketQuote(
        ticker=ticker,
        share_price=share_price,
        price_date=price_date,
        currency=info.get("currency"),
        calculated_beta=beta,
        beta_months=months,
        yahoo_beta=info.get("beta"),
        yahoo_shares_m=shares / 1_000_000 if shares else None,
        retrieved_on=today,
    )
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(asdict(quote), indent=2))
    return quote, "downloaded"


def check_market_data(quote: MarketQuote, sec_shares_m: float, today: date | None = None) -> list[str]:
    """Cross-check the market data against common sense and against the SEC filing."""
    if quote.share_price <= 0:
        raise ValueError(f"Share price of {quote.share_price} is not valid.")

    today = today or date.today()
    warnings: list[str] = []

    if quote.currency not in (None, "USD"):
        warnings.append(f"Price is in {quote.currency}, but the SEC figures are in USD. Convert before valuing.")
    if quote.currency is None:
        warnings.append("Yahoo did not report a currency. Confirm the price is in USD.")

    age = (today - date.fromisoformat(quote.price_date)).days
    if age > 5:
        warnings.append(f"The price is {age} days old (from {quote.price_date}). Refresh it before valuing.")

    if quote.yahoo_shares_m:
        gap = quote.yahoo_shares_m / sec_shares_m - 1
        if abs(gap) > 0.05:
            warnings.append(
                f"Yahoo shares ({quote.yahoo_shares_m:,.0f}m) differ from the SEC filing "
                f"({sec_shares_m:,.0f}m) by {gap:.1%}. Check for a stock split or a units problem."
            )

    if quote.calculated_beta is None:
        warnings.append("Could not calculate a beta (not enough price history). Choose one from similar companies.")
    else:
        if not 0.4 <= quote.calculated_beta <= 2.5:
            warnings.append(f"Calculated beta of {quote.calculated_beta:.2f} is unusual. Compare with peers.")
        if quote.yahoo_beta is not None and abs(quote.calculated_beta - quote.yahoo_beta) > 0.3:
            warnings.append(
                f"Our beta ({quote.calculated_beta:.2f}) and Yahoo's ({quote.yahoo_beta:.2f}) differ a lot. "
                "Betas depend on the period and method used, so treat both as rough estimates."
            )
    return warnings