"""Issued passports, so a landlord can check that the page they were sent is genuine.

Only the one-page summary is kept, never the statement or its transactions.
A local JSON file is enough for the prototype; a real service would use a database.
"""
import hashlib
import json
from base64 import b32encode
from datetime import date
from pathlib import Path

STORE = Path(__file__).parent.parent / "data" / "issued.json"


def _summary(passport, currency, applicant):
    start, end = passport["period"]
    return {
        "applicant": applicant,
        "currency": currency,
        "period": [start.isoformat(), end.isoformat()],
        "monthly_income": passport["monthly_income"],
        "monthly_rent": passport["monthly_rent"],
        "rent_to_income": passport["rent_to_income"],
        "checks": [{"label": f.label, "ok": f.ok, "detail": f.detail} for f in passport["findings"]],
    }


def _load(store):
    return json.loads(store.read_text()) if store.exists() else {}


def issue(passport, currency, applicant="", store=STORE):
    """Record a verified passport and return its code. The same passport always gets the same code."""
    if not passport["verified"]:
        raise ValueError("No passport is issued for a statement that does not add up.")
    summary = _summary(passport, currency, applicant)
    digest = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).digest()
    letters = b32encode(digest).decode()[:8]
    code = f"CP-{letters[:4]}-{letters[4:]}"
    issued = _load(store)
    if code not in issued:
        issued[code] = {**summary, "issued": date.today().isoformat()}
        store.parent.mkdir(exist_ok=True)
        store.write_text(json.dumps(issued, indent=2))
    return code


def lookup(code, store=STORE):
    """The summary as it was issued, or None if no passport has this code."""
    return _load(store).get(code.strip().upper())
