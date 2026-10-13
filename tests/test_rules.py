from pathlib import Path

from passport.parse import parse_csv
from passport.rules import build_passport

SAMPLES = Path(__file__).parent.parent / "samples"


def test_genuine_statement_is_verified():
    passport = build_passport(parse_csv(SAMPLES / "genuine.csv"))
    assert passport["verified"]
    assert passport["monthly_income"] == 6200.00
    assert passport["monthly_rent"] == 2400.00
    assert all(f.ok for f in passport["findings"])


def test_tampered_statement_is_caught_with_the_edited_rows():
    passport = build_passport(parse_csv(SAMPLES / "tampered.csv"))
    balances = passport["findings"][0]
    assert not passport["verified"]
    assert len(balances.evidence) == 2
    assert set(balances.evidence["amount"]) == {9200.00}
