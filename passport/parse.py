"""Turn a bank statement (CSV or PDF) into one tidy table of transactions.

Output columns: date, description, amount (credits positive, debits negative), balance.
"""
import io
import os

import pandas as pd

COLUMNS = ["date", "description", "amount", "balance"]
MODEL = os.environ.get("PASSPORT_MODEL", "claude-haiku-4-5-20251001")

PROMPT = (
    "Copy every row of this bank statement, including the opening balance row. "
    "Do not skip, merge, correct or invent rows.\n"
    "Reply with the ISO currency code on the first line, then one line per row and nothing else:\n"
    "YYYY-MM-DD|description|amount|balance\n"
    "Amount is positive for money in, negative for money out, 0 for a balance-only row. "
    "No thousands separators.\n\n"
)


class StatementError(ValueError):
    """The statement could not be read into rows. The message is safe to show the user."""


def _num(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0.0)


def _tidy(df):
    df = df[COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["description"] = df["description"].astype(str).str.strip()
    df["amount"] = df["amount"].astype(float).round(2)
    df["balance"] = df["balance"].astype(float).round(2)
    return df.reset_index(drop=True)


def parse_csv(file):
    raw = pd.read_csv(file)
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "amount" in raw.columns:
        amount = _num(raw["amount"])
    else:
        amount = _num(raw["deposit"]) - _num(raw["withdrawal"])
    return _tidy(
        pd.DataFrame(
            {
                "date": pd.to_datetime(raw["date"], dayfirst=True),
                "description": raw["description"],
                "amount": amount,
                "balance": _num(raw["balance"]),
            }
        )
    )


def parse_pdf(data: bytes):
    """Read the PDF text, then have the model copy the rows out as plain lines.

    The model only transcribes. Every judgement is made later by rules, and the
    balance check in rules.py will catch a row the model copied wrongly.
    Plain lines rather than JSON roughly halve the wait (about 12s for 6 months).
    """
    import anthropic
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    if not text.strip():
        raise StatementError("This PDF has no readable text. Scanned images are not supported yet.")

    response = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=16000, messages=[{"role": "user", "content": PROMPT + text}]
    )
    if response.stop_reason != "end_turn":
        raise StatementError("The statement is too long to read in one go.")
    return parse_lines(response.content[0].text)


def parse_lines(reply: str):
    """Turn the model's reply into the table. Any line that is not a clean row is an error, never a guess."""
    currency, *lines = [line.strip() for line in reply.strip().splitlines() if line.strip()]
    rows = []
    for line in lines:
        date, _, rest = line.partition("|")
        parts = rest.rsplit("|", 2)  # a description may itself contain "|"
        if len(parts) != 3:
            raise StatementError(f"Could not read this row: {line!r}")
        rows.append([date, *parts])
    if not rows:
        raise StatementError("No transactions were found in this statement.")
    try:
        return _tidy(pd.DataFrame(rows, columns=COLUMNS)), currency.upper()
    except (ValueError, TypeError) as error:
        raise StatementError(f"A row has a date or amount that could not be read: {error}") from error
