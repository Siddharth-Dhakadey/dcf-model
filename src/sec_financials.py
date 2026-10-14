"""
sec_financials.py — Turns a company's raw SEC XBRL facts into the model's historical table.

The output has exactly the same shape as Maple Coffee's data (rows = REQUIRED_ITEMS,
columns = fiscal years, values in $ millions / shares in millions), so the rest of
the model works unchanged.

Every number also gets a PROVENANCE record: which XBRL tag(s) it came from, which
filing, and how it was obtained:
    FILED     - taken directly from a 10-K
    DERIVED   - calculated from filed numbers (e.g. operating expenses)
    ASSUMED 0 - no tag found for an item that many companies simply don't have
                (e.g. preferred stock). Always verify these in the 10-K.
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.data import REQUIRED_ITEMS


@dataclass
class TagRule:
    """How to find one line item in the SEC data."""

    kind: str                    # "duration" (over a year: income & cash flow) or "instant" (balance sheet)
    alternatives: list[list[str]]  # tried in order; each alternative is a list of tags that are ADDED together
    unit: str = "USD"
    may_be_absent: bool = False  # if True and no tag is found, use 0 and flag it


# =============================================================================
# THE MAPPING: our line items -> possible us-gaap tags (first match wins).
# When a company uses a tag that is not listed, add it here.
# =============================================================================
TAG_RULES: dict[str, TagRule] = {
    # --- Income statement ---
    "revenue": TagRule("duration", [
        ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        ["Revenues"],
        ["SalesRevenueNet"],
    ]),
    "cogs": TagRule("duration", [
        ["CostOfGoodsAndServicesSold"],
        ["CostOfRevenue"],
        ["CostOfGoodsSold"],
    ]),
    "operating_income": TagRule("duration", [["OperatingIncomeLoss"]]),
    "pretax_income": TagRule("duration", [
        ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
        ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    ]),
    "income_tax": TagRule("duration", [["IncomeTaxExpenseBenefit"]]),
    "net_income_reported": TagRule("duration", [["NetIncomeLoss"]]),
    # --- Cash flow statement ---
    "depreciation_amortization": TagRule("duration", [
        ["DepreciationDepletionAndAmortization"],
        ["DepreciationAndAmortization"],
        ["DepreciationAmortizationAndAccretionNet"],
    ]),
    "capex": TagRule("duration", [["PaymentsToAcquirePropertyPlantAndEquipment"]]),
    # --- Balance sheet ---
    "accounts_receivable": TagRule("instant", [["AccountsReceivableNetCurrent"]]),
    "inventory": TagRule("instant", [["InventoryNet"]], may_be_absent=True),
    "accounts_payable": TagRule("instant", [["AccountsPayableCurrent"]]),
    # Cash = cash & equivalents + SHORT-TERM marketable securities (a common, conservative definition).
    "cash": TagRule("instant", [
        ["CashAndCashEquivalentsAtCarryingValue", "MarketableSecuritiesCurrent"],
        ["CashAndCashEquivalentsAtCarryingValue", "ShortTermInvestments"],
        ["CashAndCashEquivalentsAtCarryingValue"],
    ]),
    # Debt = long-term debt (non-current + current portion) + commercial paper. Leases NOT included.
    "total_debt": TagRule("instant", [
        ["LongTermDebtNoncurrent", "LongTermDebtCurrent", "CommercialPaper"],
        ["LongTermDebtNoncurrent", "LongTermDebtCurrent", "ShortTermBorrowings"],
        ["LongTermDebtNoncurrent", "LongTermDebtCurrent"],
        ["LongTermDebt"],
    ]),
    "preferred_stock": TagRule("instant", [["PreferredStockValue"]], may_be_absent=True),
    "minority_interest": TagRule("instant", [["MinorityInterest"]], may_be_absent=True),
    # --- Share data ---
    "diluted_shares": TagRule("duration", [["WeightedAverageNumberOfDilutedSharesOutstanding"]], unit="shares"),
    # --- Memo items (shown for judgement, not used automatically) ---
    "memo_long_term_securities": TagRule("instant", [["MarketableSecuritiesNoncurrent"]], may_be_absent=True),
}


def annual_facts(facts: dict, tag: str, kind: str, unit: str = "USD") -> pd.DataFrame:
    """
    All annual (10-K) values of one tag, ONE row per period end.
    When the same period was reported in several 10-Ks, the most recently filed value wins
    (it includes any restatement or stock-split adjustment).
    """
    entries = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get(unit, [])
    rows = []
    for e in entries:
        if e.get("form") != "10-K" or e.get("fp") != "FY":
            continue
        if kind == "duration":
            if "start" not in e:
                continue
            days = (date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days
            if not 350 <= days <= 380:          # full fiscal years only
                continue
        elif "start" in e:                      # balance sheet items have no start date
            continue
        rows.append({"end": e["end"], "value": e["val"], "filed": e["filed"], "accn": e["accn"]})

    if not rows:
        return pd.DataFrame(columns=["value", "filed", "accn"])
    table = pd.DataFrame(rows).sort_values("filed").drop_duplicates("end", keep="last")
    return table.set_index("end").sort_index()


def _find_item(facts: dict, rule: TagRule, period_ends: list[str]) -> tuple[pd.Series, list[str], str] | None:
    """Try each alternative; return (values by period end, tags used, latest accession) for the first that works."""
    for tags in rule.alternatives:
        tables = [annual_facts(facts, t, rule.kind, rule.unit) for t in tags]
        anchor = tables[0]                                  # the first tag must cover every year
        if not set(period_ends).issubset(anchor.index):
            continue
        total = pd.Series(0.0, index=period_ends)
        used = []
        for tag, table in zip(tags, tables):
            if set(period_ends).issubset(table.index):
                total += table.loc[period_ends, "value"].astype(float)
                used.append(tag)
        latest_accn = anchor.loc[period_ends[-1], "accn"]
        return total, used, latest_accn
    return None


@dataclass
class SecHistoricals:
    """The model-ready historical table plus where every number came from."""

    raw: pd.DataFrame                        # REQUIRED_ITEMS x fiscal years ($m, shares in m)
    provenance: pd.DataFrame                 # one row per line item
    period_ends: dict[int, str]              # fiscal year label -> exact period end date
    memo: pd.DataFrame                       # extra items shown for judgement
    warnings: list[str] = field(default_factory=list)


def build_sec_historicals(facts: dict, years: int = 5) -> SecHistoricals:
    """Map, de-duplicate and convert a company's SEC facts into the model's historical format."""
    # 1. Which fiscal years? Use the period ends of annual revenue.
    revenue_rule = TAG_RULES["revenue"]
    revenue_table = None
    for tags in revenue_rule.alternatives:
        revenue_table = annual_facts(facts, tags[0], "duration")
        if not revenue_table.empty:
            break
    if revenue_table is None or revenue_table.empty:
        raise ValueError("No annual revenue found in the SEC data. Is this a company that files 10-Ks?")
    period_ends = list(revenue_table.index[-years:])

    # 2. Find every line item.
    values: dict[str, pd.Series] = {}
    provenance_rows = []
    missing = []
    for item, rule in TAG_RULES.items():
        found = _find_item(facts, rule, period_ends)
        if found is not None:
            series, used, accn = found
            divisor = 1_000_000                              # dollars -> $ millions, shares -> millions
            values[item] = series / divisor
            provenance_rows.append({"item": item, "source": "FILED", "tags": " + ".join(used), "latest_filing": accn})
        elif rule.may_be_absent:
            values[item] = pd.Series(0.0, index=period_ends)
            provenance_rows.append({"item": item, "source": "ASSUMED 0",
                                    "tags": "no tag found - verify in 10-K", "latest_filing": "-"})
        else:
            missing.append(f"{item} (tried: {[' + '.join(a) for a in rule.alternatives]})")

    if missing:
        raise ValueError(
            "These line items could not be found in the SEC data:\n  - " + "\n  - ".join(missing)
            + "\nFind them in the 10-K and add the company's tag to TAG_RULES (or use an override)."
        )

    # 3. Derived items, so that EBIT and pre-tax income match the 10-K exactly.
    values["operating_expenses"] = values["revenue"] - values["cogs"] - values["operating_income"]
    values["interest_expense"] = values["operating_income"] - values["pretax_income"]
    provenance_rows += [
        {"item": "operating_expenses", "source": "DERIVED",
         "tags": "revenue - cogs - OperatingIncomeLoss", "latest_filing": "-"},
        {"item": "interest_expense", "source": "DERIVED",
         "tags": "OperatingIncomeLoss - pre-tax income (net non-operating)", "latest_filing": "-"},
    ]

    # 4. Assemble in the model's format: rows = REQUIRED_ITEMS, columns = fiscal years.
    year_labels = [int(end[:4]) for end in period_ends]
    raw = pd.DataFrame({item: values[item].to_numpy() for item in REQUIRED_ITEMS}, index=year_labels).T
    memo = pd.DataFrame(
        {"long_term_marketable_securities": values["memo_long_term_securities"].to_numpy()},
        index=year_labels,
    ).T

    provenance = pd.DataFrame(provenance_rows).set_index("item")
    warnings = check_sec_historicals(values, provenance, year_labels)

    return SecHistoricals(
        raw=raw,
        provenance=provenance,
        period_ends=dict(zip(year_labels, period_ends)),
        memo=memo,
        warnings=warnings,
    )


def check_sec_historicals(values: dict[str, pd.Series], provenance: pd.DataFrame, years: list[int]) -> list[str]:
    """Analyst-style checks on the retrieved numbers."""
    warnings: list[str] = []

    # Tie-out: our net income (pre-tax - tax) should equal the net income the company reported.
    computed = values["pretax_income"] - values["income_tax"]
    reported = values["net_income_reported"]
    for year, c, r in zip(years, computed, reported):
        if abs(c - r) > 0.005 * abs(r):
            warnings.append(
                f"FY{year}: pre-tax income - tax = {c:,.0f} but reported net income = {r:,.0f}. "
                "Check for discontinued operations or minority interest."
            )

    # One-off tax items: an effective tax rate far from the company's usual level.
    rates = (values["income_tax"] / values["pretax_income"]).to_numpy()
    typical = float(pd.Series(rates).median())
    for year, rate in zip(years, rates):
        if abs(rate - typical) > 0.05:
            warnings.append(
                f"FY{year}: effective tax rate {rate:.1%} vs typical {typical:.1%}. "
                "Possible one-off tax item - read the 10-K tax note before using it in the forecast."
            )

    for item in provenance.index[provenance["source"] == "ASSUMED 0"]:
        if item.startswith("memo_"):
            continue
        warnings.append(f"'{item}' was not found and set to 0. Confirm in the 10-K balance sheet.")

    return warnings


def latest_cover_shares(facts: dict) -> tuple[float, str]:
    """
    The most recent share count from the cover page of a 10-K or 10-Q
    (dei:EntityCommonStockSharesOutstanding). Returns (shares in millions, as-of date).
    This is more up to date than the year's weighted-average diluted share count.
    """
    dei = facts.get("facts", {}).get("dei", {})
    entries = dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if not entries:
        raise ValueError("No cover-page share count (EntityCommonStockSharesOutstanding) in the SEC data.")
    latest = max(entries, key=lambda e: (e["end"], e["filed"]))
    return latest["val"] / 1_000_000, latest["end"]


def latest_balance_sheet(facts: dict, groups: dict[str, list[str]]) -> tuple[dict[str, float], str, str]:
    """
    Balance-sheet values on the MOST RECENT date where EVERY requested tag was reported,
    looking at quarterly reports (10-Q) as well as annual ones (10-K). Using one common
    date keeps cash, debt and securities consistent with each other.

    groups example: {"cash": ["CashAndCashEquivalentsAtCarryingValue", "MarketableSecuritiesCurrent"],
                     "total_debt": ["LongTermDebtNoncurrent", "LongTermDebtCurrent"]}
    Returns ({group name: value in $ millions}, balance sheet date, form).
    """
    all_tags = [tag for tags in groups.values() for tag in tags]
    by_tag: dict[str, dict[str, tuple[float, str]]] = {}
    for tag in all_tags:
        entries = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
        values: dict[str, tuple[float, str]] = {}
        for e in sorted(entries, key=lambda e: e["filed"]):          # later filings overwrite earlier ones
            if "start" not in e and e.get("form") in ("10-K", "10-Q"):
                values[e["end"]] = (e["val"], e["form"])
        by_tag[tag] = values

    common_dates = set.intersection(*(set(v) for v in by_tag.values()))
    if not common_dates:
        raise ValueError(f"No single balance sheet date reports all of: {all_tags}")
    latest = max(common_dates)
    totals = {
        name: sum(by_tag[tag][latest][0] for tag in tags) / 1_000_000
        for name, tags in groups.items()
    }
    return totals, latest, by_tag[all_tags[0]][latest][1]