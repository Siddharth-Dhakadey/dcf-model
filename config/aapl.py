"""
config/aapl.py — YOUR assumptions and data decisions for Apple Inc. (AAPL).

Everything in this file is an analyst JUDGEMENT, not a fact. Each choice has a note
saying why, so that you (or anyone reviewing your work) can challenge it later.
Change any number and run `python main.py` again.

Sources checked on 2026-10-13 (update them whenever you re-run the valuation):
  - 10-year US Treasury yield: about 5.19% (13 Oct 2026, market reports)
  - Implied equity risk premium: 4.23% (Damodaran, start of 2026)
  - Beta: 1.10, our own 5-year monthly calculation vs the S&P 500 (Step 17)
"""

from dataclasses import replace

from src.assumptions import ForecastAssumptions, TerminalAssumptions, WaccAssumptions
from src.scenarios import Scenario

COMPANY_NAME = "Apple Inc."
HISTORY_YEARS = 5

# =============================================================================
# DATA DECISIONS (how to treat items where analysts legitimately disagree)
# =============================================================================
# Apple's long-term marketable securities are mostly high-quality bonds it could sell.
# Many analysts count them as cash; set to False for the conservative view.
INCLUDE_LONG_TERM_SECURITIES_IN_CASH = True

# Use the most recent quarterly balance sheet (10-Q) for cash and debt, so the equity
# bridge is as close as possible to the share price date. False = last 10-K.
USE_LATEST_BALANCE_SHEET = True

# "latest_cover": most recent share count on a 10-K/10-Q cover page (reflects buybacks).
# "diluted_average": the last fiscal year's weighted-average diluted shares.
SHARE_COUNT = "latest_cover"

# =============================================================================
# FORECAST: FY2026E - FY2030E (illustrative; research Apple before relying on these)
# =============================================================================
FORECAST = ForecastAssumptions(
    revenue_growth=[0.060, 0.055, 0.050, 0.045, 0.040],  # history: -2.8% to +7.8%; FY2025 +6.4%
    gross_margin=[0.470] * 5,                            # FY2025: 46.9%, rising with Services mix
    ebit_margin=[0.320] * 5,                             # FY2025: 32.0%; held flat
    tax_rate=[0.160] * 5,                                # normal rate; FY2024's 24.1% was a one-off
    da_pct_revenue=[0.028] * 5,                          # FY2025: 2.8%
    capex_pct_revenue=[0.030] * 5,                       # FY2025: 3.1%; kept slightly above D&A
    nwc_pct_revenue=[-0.060] * 5,                        # Apple's NWC is negative: about -6% of revenue
)

# =============================================================================
# DISCOUNT RATE
# =============================================================================
WACC = WaccAssumptions(
    risk_free_rate=0.0519,        # 10-year Treasury, 13 Oct 2026
    beta=1.10,                    # our 5y monthly beta (Yahoo shows 1.07)
    equity_risk_premium=0.0423,   # Damodaran implied ERP, start of 2026
    pre_tax_cost_of_debt=0.0570,  # risk-free + ~0.5% for an AA+ rated borrower (judgement)
    tax_rate=0.16,                # same normal tax rate as the forecast
)

# =============================================================================
# TERMINAL VALUE
# =============================================================================
TERMINAL = TerminalAssumptions(
    terminal_growth_rate=0.030,   # long-run nominal growth; must stay below WACC
    exit_multiple=20.0,           # mature mega-cap EV/EBITDA; well below today's ~35x
    method="perpetuity_growth",
)


# =============================================================================
# SCENARIOS
# =============================================================================
def scenarios(base: ForecastAssumptions, base_terminal: TerminalAssumptions) -> list[Scenario]:
    """Illustrative bear / base / bull stories for Apple."""
    bear = Scenario(
        name="Bear",
        forecast=replace(
            base,
            revenue_growth=[0.030, 0.025, 0.025, 0.020, 0.020],   # iPhone saturation, slower Services
            gross_margin=[0.455] * 5,
            ebit_margin=[0.290] * 5,                              # regulation squeezes App Store fees
        ),
        terminal=replace(base_terminal, terminal_growth_rate=0.025, exit_multiple=16.0),
    )
    base_case = Scenario(name="Base", forecast=base, terminal=base_terminal)
    bull = Scenario(
        name="Bull",
        forecast=replace(
            base,
            revenue_growth=[0.080, 0.080, 0.070, 0.060, 0.050],   # strong product cycle + Services
            gross_margin=[0.480, 0.485, 0.490, 0.490, 0.490],
            ebit_margin=[0.330, 0.335, 0.340, 0.340, 0.340],
        ),
        terminal=replace(base_terminal, terminal_growth_rate=0.035, exit_multiple=24.0),
    )
    return [bear, base_case, bull]
