"""Fixed rules that turn transactions into the passport. No model is involved here.

Every finding carries the statement rows it was worked out from.
"""
import re
from dataclasses import dataclass, field

import pandas as pd

RENT_WORDS = ("RENT", "LANDLORD", "TENANCY", "LEASE")
MIN_MONTHS = 3  # a payment must show up in at least this many months to count as regular
INCOME_TOLERANCE = 0.15
RENT_TOLERANCE = 0.05
ON_TIME_DAYS = 3


@dataclass
class Finding:
    label: str
    ok: bool
    detail: str
    evidence: pd.DataFrame = field(default_factory=pd.DataFrame)


def _key(description):
    """Group 'SALARY APR 2026' with 'SALARY MAY 2026' by dropping digits and month names."""
    text = re.sub(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\b", " ", description.upper())
    return " ".join(re.sub(r"[^A-Z ]+", " ", text).split())


def _recurring(rows, tolerance):
    """Groups of similar payments seen in MIN_MONTHS or more separate months."""
    groups = []
    for _, group in rows.groupby(rows["description"].map(_key)):
        typical = group["amount"].abs().median()
        steady = group[(group["amount"].abs() - typical).abs() <= tolerance * typical]
        if steady["date"].dt.to_period("M").nunique() >= MIN_MONTHS:
            groups.append(steady)
    return groups


def check_balances(tx):
    """Each row's balance must equal the previous balance plus this row's amount."""
    expected = tx["balance"].shift(1) + tx["amount"]
    broken = tx[expected.notna() & ((expected - tx["balance"]).abs() > 0.005)]
    out_of_order = not tx["date"].is_monotonic_increasing
    if broken.empty and not out_of_order:
        return Finding("Statement adds up", True, f"All {len(tx) - 1} rows match the running balance.")
    detail = f"{len(broken)} row(s) do not match the running balance."
    if out_of_order:
        detail += " Dates are out of order."
    show = broken.assign(expected_balance=expected[broken.index].round(2))
    return Finding("Statement does not add up", False, detail, show)


def find_income(tx):
    groups = _recurring(tx[tx["amount"] > 0], INCOME_TOLERANCE)
    if not groups:
        return Finding("Regular income", False, "No regular income found."), None
    best = max(groups, key=lambda g: g["amount"].sum())
    monthly = float(best["amount"].median())
    months = best["date"].dt.to_period("M").nunique()
    return Finding("Regular income", True, f"Paid in {months} separate months, typically {monthly:,.2f}.", best), monthly


def find_rent(tx):
    groups = _recurring(tx[tx["amount"] < 0], RENT_TOLERANCE)
    named = [g for g in groups if any(w in g["description"].iloc[0].upper() for w in RENT_WORDS)]
    pool = named or groups
    if not pool:
        return Finding("Rent payments", False, "No regular rent payment found."), None
    best = max(pool, key=lambda g: g["amount"].abs().median())
    rent = float(best["amount"].abs().median())
    usual_day = int(best["date"].dt.day.mode().iloc[0])
    on_time = int(((best["date"].dt.day - usual_day).abs() <= ON_TIME_DAYS).sum())
    active = tx[tx["amount"] != 0]["date"]  # ignore a balance-brought-forward row
    span = len(pd.period_range(active.min(), active.max(), freq="M"))
    paid = best["date"].dt.to_period("M").nunique()
    how = "labelled as rent" if named else "largest regular payment, assumed to be rent"
    detail = (
        f"{paid} of {span} months paid, {on_time} within {ON_TIME_DAYS} days of the usual day "
        f"({usual_day}). Typically {rent:,.2f} ({how})."
    )
    return Finding("Rent payments", paid == span and on_time == paid, detail, best), rent


def check_buffer(tx):
    negative = tx[tx["balance"] < 0]
    low = tx.loc[[tx["balance"].idxmin()]]
    detail = f"Lowest balance {float(low['balance'].iloc[0]):,.2f}. {len(negative)} row(s) below zero."
    return Finding("Never overdrawn" if negative.empty else "Went overdrawn", negative.empty, detail,
                   negative if not negative.empty else low)


def build_passport(tx):
    balances = check_balances(tx)
    income, monthly_income = find_income(tx)
    rent, monthly_rent = find_rent(tx)
    buffer = check_buffer(tx)
    ratio = monthly_rent / monthly_income if monthly_income and monthly_rent else None
    return {
        # If the statement does not add up, nothing built on it can be trusted.
        "verified": balances.ok,
        "period": (tx["date"].min().date(), tx["date"].max().date()),
        "monthly_income": monthly_income,
        "monthly_rent": monthly_rent,
        "rent_to_income": ratio,
        "findings": [balances, income, rent, buffer],
    }
