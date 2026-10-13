"""The whole pipeline in one call: statement in, passport out.

    read (parse.py)  ->  check and summarise (rules.py)  ->  present (app.py or report.py)

The page, the command line and the tests all go through run(), so they cannot drift apart.
"""
import io
from dataclasses import dataclass

import pandas as pd

from .parse import StatementError, parse_csv, parse_pdf
from .rules import build_passport

DEFAULT_CURRENCY = "SGD"  # CSV exports do not name their currency, so the caller says


@dataclass
class Result:
    transactions: pd.DataFrame
    currency: str
    passport: dict


def run(name: str, data: bytes, currency: str = DEFAULT_CURRENCY) -> Result:
    if name.lower().endswith(".pdf"):
        tx, detected = parse_pdf(data)
        currency = detected or currency
    elif name.lower().endswith(".csv"):
        try:
            tx = parse_csv(io.BytesIO(data))
        except (KeyError, ValueError) as error:
            raise StatementError(f"This CSV is missing a column or has an unreadable value: {error}") from error
    else:
        raise StatementError("Only CSV and PDF statements are supported.")
    if len(tx) < 2:
        raise StatementError("The statement needs at least two rows to check.")
    return Result(tx, currency or DEFAULT_CURRENCY, build_passport(tx))
