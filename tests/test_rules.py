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


def test_passport_pdf_is_one_page_summary_without_the_transactions():
    import io

    import pdfplumber
    import pytest

    from passport.report import build_pdf

    genuine = build_passport(parse_csv(SAMPLES / "genuine.csv"))
    with pdfplumber.open(io.BytesIO(build_pdf(genuine, "SGD", 0.58, "test rate"))) as pdf:
        assert len(pdf.pages) == 1
        text = pdf.pages[0].extract_text()
    assert "SGD 6,200" in text and "SGD 2,400" in text
    assert "NTUC FAIRPRICE" not in text  # everyday spending stays private

    tampered = build_passport(parse_csv(SAMPLES / "tampered.csv"))
    with pytest.raises(ValueError):
        build_pdf(tampered, "SGD", 0.58, "test rate")


def test_pipeline_reads_a_model_reply_into_the_same_table_as_the_csv():
    from passport.parse import parse_lines

    csv = parse_csv(SAMPLES / "genuine.csv")
    reply = "sgd\n" + "\n".join(
        f"{r.date:%Y-%m-%d}|{r.description}|{r.amount}|{r.balance}" for r in csv.itertuples()
    )
    table, currency = parse_lines(reply)
    assert currency == "SGD"
    assert table.equals(csv)


def test_unreadable_input_is_refused_not_guessed():
    import pytest

    from passport.parse import StatementError, parse_lines
    from passport.pipeline import run

    with pytest.raises(StatementError):
        parse_lines("SGD\n2026-04-01|RENT|-2400.00")  # a row with the balance missing
    with pytest.raises(StatementError):
        run("statement.docx", b"")
    with pytest.raises(StatementError):
        run("statement.csv", b"when,what\n1,2\n")


def test_command_line_exit_code_reports_the_verdict():
    import subprocess
    import sys

    root = SAMPLES.parent
    assert subprocess.run([sys.executable, "-m", "passport", "samples/genuine.csv"], cwd=root).returncode == 0
    assert subprocess.run([sys.executable, "-m", "passport", "samples/tampered.csv"], cwd=root).returncode == 1
