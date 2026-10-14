"""
explore_sec.py — Step 16: turn a company's SEC data into the model's historical table.

Change TICKER to try another US company that files 10-Ks with the SEC.
Run with:  python explore_sec.py
"""

import pandas as pd

from src.data import validate_historicals
from src.display import print_table, print_warnings
from src.historicals import build_historical_statements, calculate_ratios
from src.sec import download_company_facts
from src.sec_financials import build_sec_historicals

TICKER = "AAPL"
YEARS = 5


def main() -> None:
    download = download_company_facts(TICKER)
    sec = build_sec_historicals(download.facts, years=YEARS)

    validate_historicals(sec.raw)                        # the same checks Maple Coffee gets
    financials = build_historical_statements(sec.raw)    # the same code Maple Coffee uses
    ratios = calculate_ratios(financials)

    print("=" * 70)
    print(f"  {download.company_name} ({download.ticker}) - historical data from SEC 10-K filings")
    print("=" * 70)
    print("Fiscal years end on: " + ", ".join(f"FY{y} = {d}" for y, d in sec.period_ends.items()))

    print_table(financials, "Historical Financials ($ millions, shares in millions)", style="money")
    print_table(ratios, "Historical Ratios", style="percent")
    print_table(sec.memo, "Memo: items that need an analyst decision ($ millions)", style="money")

    print("\nProvenance: where each number came from")
    print("---------------------------------------")
    with pd.option_context("display.max_colwidth", 70, "display.width", 200):
        print(sec.provenance.to_string())

    print_warnings("Data checks", sec.warnings)


if __name__ == "__main__":
    main()