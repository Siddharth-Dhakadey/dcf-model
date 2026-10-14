"""
explore_sec.py — Step 15: download a company's filed financial data from the SEC and look at it.

Change TICKER to try another US company that files 10-Ks with the SEC.
Run with:  python explore_sec.py
"""

from src.sec import annual_values, download_company_facts, summarize_company_facts

TICKER = "AAPL"
PEEK_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"   # Apple's revenue tag
YEARS_TO_SHOW = 5


def main() -> None:
    download = download_company_facts(TICKER)
    summary = summarize_company_facts(download.facts)

    print("=" * 60)
    print(f"  SEC data for {download.ticker}: {download.company_name}")
    print("=" * 60)
    print(f"CIK (SEC company ID):   {download.cik}")
    print(f"Data source:            {download.source}")
    print(f"Saved at:               {download.cache_file}")
    print(f"Entity name in filing:  {summary['entity_name']}")
    for taxonomy, count in summary["concepts_per_taxonomy"].items():
        print(f"Concepts ({taxonomy + '):':<10}   {count}")
    print(f"10-K filings included:  {summary['number_of_10k_filings']}")
    print(f"Latest 10-K filed on:   {summary['latest_10k_filed']}")

    table = annual_values(download.facts, PEEK_CONCEPT)
    print(f"\nPeek: '{PEEK_CONCEPT}' as reported in 10-Ks ($ millions, raw)")
    print("-" * 60)
    if table.empty:
        print(f"{TICKER} does not use this tag. (Step 16 will handle different tags.)")
        return
    recent_periods = sorted(table["period_end"].unique())[-YEARS_TO_SHOW:]
    print(table[table["period_end"].isin(recent_periods)].to_string(index=False))


if __name__ == "__main__":
    main()