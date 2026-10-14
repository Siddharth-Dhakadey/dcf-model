"""
sec.py — Downloads a company's filed financial data from the SEC (EDGAR XBRL API).

Source:  https://data.sec.gov  (official, free, no API key)
Rules:   identify yourself with a name + email (User-Agent), and stay well below
         10 requests per second. Every download is cached in data/raw/ so
         re-running the model does not contact the SEC again.

All numbers in the SEC data are in RAW units (dollars, shares), NOT millions.
"""

import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def get_sec_user_agent() -> str:
    """Read your name + email from local_settings.py (a file that is never uploaded to GitHub)."""
    try:
        from local_settings import SEC_USER_AGENT
    except ImportError:
        raise RuntimeError(
            "local_settings.py not found. Create it from the template:\n"
            "  cp local_settings.example.py local_settings.py\n"
            "then put your name and email in it."
        ) from None

    if "@" not in SEC_USER_AGENT or "example.com" in SEC_USER_AGENT:
        raise RuntimeError(
            "Please put your real name and email address in local_settings.py.\n"
            "The SEC requires it to identify who is downloading data."
        )
    return SEC_USER_AGENT


def _download_json(url: str) -> dict:
    """Download one JSON file from the SEC, with clear error messages."""
    headers = {"User-Agent": get_sec_user_agent(), "Accept-Encoding": "gzip, deflate"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Could not connect to the SEC. Check your internet connection.") from None

    if response.status_code == 403:
        raise RuntimeError(
            "The SEC refused the request (403 Forbidden). This usually means the User-Agent in\n"
            "local_settings.py is missing a real name and email, or too many requests were sent."
        )
    if response.status_code == 404:
        raise RuntimeError(f"The SEC has no file at {url} (404 Not Found).")
    response.raise_for_status()      # any other HTTP error stops here

    time.sleep(0.2)                  # be polite: at most ~5 requests per second
    return response.json()


def load_json(url: str, cache_file: Path, max_age_days: float, refresh: bool = False) -> tuple[dict, str]:
    """
    Return the JSON at `url`, using the cached copy in data/raw/ if it is recent enough.
    Also returns where the data came from: "cache" or "downloaded".
    """
    if cache_file.exists() and not refresh:
        age_days = (time.time() - cache_file.stat().st_mtime) / 86_400
        if age_days <= max_age_days:
            return json.loads(cache_file.read_text()), "cache"

    data = _download_json(url)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data))
    return data, "downloaded"


def find_cik(tickers: dict, ticker: str) -> tuple[str, str]:
    """
    Look up a ticker in the SEC's ticker list. Returns (10-digit CIK, company name).
    The SEC list looks like: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    """
    wanted = ticker.strip().upper()
    for entry in tickers.values():
        if entry["ticker"].upper() == wanted:
            return f"{int(entry['cik_str']):010d}", entry["title"]
    raise ValueError(
        f"Ticker '{ticker}' was not found in the SEC's company list.\n"
        "  Check the spelling. Only companies that file with the SEC are listed\n"
        "  (e.g. companies listed only on the TSX are not)."
    )


@dataclass
class SecDownload:
    """A company's SEC data plus where it came from."""

    ticker: str
    cik: str
    company_name: str
    facts: dict
    cache_file: Path
    source: str          # "cache" or "downloaded"


def download_company_facts(ticker: str, refresh: bool = False) -> SecDownload:
    """Ticker -> CIK -> all XBRL facts the company has filed, cached in data/raw/."""
    tickers, _ = load_json(TICKERS_URL, RAW_DATA_DIR / "sec_company_tickers.json", max_age_days=7)
    cik, name = find_cik(tickers, ticker)

    cache_file = RAW_DATA_DIR / f"{ticker.upper()}_companyfacts.json"
    facts, source = load_json(
        COMPANY_FACTS_URL.format(cik=cik), cache_file, max_age_days=1, refresh=refresh
    )
    return SecDownload(ticker.upper(), cik, name, facts, cache_file, source)


def summarize_company_facts(facts: dict) -> dict:
    """Count what is in the download and find the annual reports (10-Ks) it covers."""
    taxonomies = facts.get("facts", {})
    filings_10k: dict[str, str] = {}          # accession number -> filing date
    for concepts in taxonomies.values():
        for concept in concepts.values():
            for entries in concept.get("units", {}).values():
                for entry in entries:
                    if entry.get("form") == "10-K":
                        filings_10k[entry["accn"]] = entry["filed"]

    return {
        "entity_name": facts.get("entityName", "unknown"),
        "concepts_per_taxonomy": {name: len(concepts) for name, concepts in taxonomies.items()},
        "number_of_10k_filings": len(filings_10k),
        "latest_10k_filed": max(filings_10k.values()) if filings_10k else None,
    }


def annual_values(facts: dict, concept: str, taxonomy: str = "us-gaap", unit: str = "USD") -> pd.DataFrame:
    """
    Every full-year value of one concept reported in a 10-K, exactly as filed (raw, with duplicates).
    Values are converted to $ millions for readability.
    """
    try:
        entries = facts["facts"][taxonomy][concept]["units"][unit]
    except KeyError:
        return pd.DataFrame()      # this company does not use that tag

    rows = []
    for e in entries:
        if e.get("form") != "10-K" or e.get("fp") != "FY" or "start" not in e:
            continue
        days = (date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days
        if not 350 <= days <= 380:        # keep full fiscal years only (not quarters)
            continue
        rows.append({
            "period_end": e["end"],
            "value_$m": e["val"] / 1_000_000,
            "filing_fy": e["fy"],
            "filed": e["filed"],
            "accession": e["accn"],
        })

    return pd.DataFrame(rows).sort_values(["period_end", "filed"]).reset_index(drop=True)