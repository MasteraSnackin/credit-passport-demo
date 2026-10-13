"""Turn a bank statement (CSV or PDF) into one tidy table of transactions.

Output columns: date, description, amount (credits positive, debits negative), balance.
"""
import io
import os

import pandas as pd

COLUMNS = ["date", "description", "amount", "balance"]
MODEL = os.environ.get("PASSPORT_MODEL", "claude-haiku-4-5-20251001")

TOOL = {
    "name": "record_transactions",
    "description": "Record every row of the bank statement exactly as printed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "currency": {"type": "string", "description": "ISO code, e.g. SGD"},
            "transactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "YYYY-MM-DD"},
                        "description": {"type": "string"},
                        "amount": {
                            "type": "number",
                            "description": "Money in is positive, money out is negative, 0 for a balance-only row",
                        },
                        "balance": {"type": "number", "description": "Running balance printed on the row"},
                    },
                    "required": ["date", "description", "amount", "balance"],
                },
            },
        },
        "required": ["currency", "transactions"],
    },
}


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
    """Read the PDF text, then have the model copy the rows into a fixed shape.

    The model only transcribes. Every judgement is made later by rules, and the
    balance check in rules.py will catch a row the model copied wrongly.
    """
    import anthropic
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    response = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=16000,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "record_transactions"},
        messages=[
            {
                "role": "user",
                "content": "Copy every row of this bank statement, including the opening balance row. "
                "Do not skip, merge, correct or invent rows.\n\n" + text,
            }
        ],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return _tidy(pd.DataFrame(block.input["transactions"])), block.input.get("currency", "")
