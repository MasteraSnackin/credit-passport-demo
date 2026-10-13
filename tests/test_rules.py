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


def test_missed_rent_month_is_named_and_not_reported_as_on_time():
    passport = build_passport(parse_csv(SAMPLES / "missed_rent.csv"))
    rent = passport["findings"][2]
    assert passport["verified"]  # the statement is genuine, so a passport is still issued
    assert not rent.ok
    assert "5 of 6 months paid" in rent.detail and "Jul 2026" in rent.detail


def test_landlord_can_look_up_an_issued_passport_by_its_code(tmp_path):
    import pytest

    from passport import registry

    store = tmp_path / "issued.json"
    genuine = build_passport(parse_csv(SAMPLES / "genuine.csv"))
    code = registry.issue(genuine, "SGD", "Wei Ling Tan", store=store)
    assert code == registry.issue(genuine, "SGD", "Wei Ling Tan", store=store)  # stable, no duplicates
    record = registry.lookup(code.lower() + " ", store=store)
    assert record["monthly_income"] == 6200.00 and record["applicant"] == "Wei Ling Tan"
    assert "transactions" not in record and "NTUC" not in store.read_text()
    assert registry.lookup("CP-AAAA-AAAA", store=store) is None
    with pytest.raises(ValueError):
        registry.issue(build_passport(parse_csv(SAMPLES / "tampered.csv")), "SGD", store=store)


def test_a_second_country_layout_reads_newest_first_rupees():
    from passport.pipeline import run

    result = run("india.csv", (SAMPLES / "india.csv").read_bytes(), "INR")
    assert result.currency == "INR"
    assert result.passport["verified"]
    assert result.passport["monthly_income"] == 145000.00  # written as 1,45,000.00 in the file
    assert result.passport["monthly_rent"] == 42000.00
    assert result.transactions["date"].is_monotonic_increasing


def test_simulated_bank_feed_is_labelled_as_simulated():
    from passport import bank, registry

    assert "simulated" in bank.SOURCE.lower()
    for name in bank.BANKS:
        feed = bank.fetch_statement(name)
        assert feed["data"] and feed["holder"] and feed["currency"] in {"SGD", "INR"}
    assert "simulated" in bank.name_note(bank.SOURCE)
    assert bank.name_note("Uploaded by the applicant") == "name as given by the applicant"
    assert "source" in registry._summary(build_passport(parse_csv(SAMPLES / "genuine.csv")), "SGD", "", bank.SOURCE)


def test_passports_saved_to_an_account_can_be_listed(tmp_path):
    from passport import registry

    store = tmp_path / "issued.json"
    genuine = build_passport(parse_csv(SAMPLES / "genuine.csv"))
    code = registry.issue(genuine, "SGD", "Wei Ling Tan", store=store)
    assert registry.owned_by("wei@example.com", store=store) == []
    assert registry.issue(genuine, "SGD", "Wei Ling Tan", owner="Wei@Example.com", store=store) == code
    assert [c for c, _ in registry.owned_by("wei@example.com", store=store)] == [code]
