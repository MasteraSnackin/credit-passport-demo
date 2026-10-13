# Demonstrating and testing Credit Passport

Everything here uses the fictional statements in `samples/`. Results were last confirmed on 13 October 2026.

## The three-minute demo

Start the app with `streamlit run app.py`, then follow these in order.

| # | Do this | You should see | What it shows |
| --- | --- | --- | --- |
| 1 | **Get started**, then the **Edited** sample | "We could not issue a passport", with two salary rows each showing a −3,000.00 gap | Edited figures are caught and pinpointed. No passport, no figures. |
| 2 | **Check another statement**, **Connect your bank (demo)**, **Continue**, **Allow** | A consent screen, then "Your passport is ready" for Wei Ling Tan with SGD 6,200 income and SGD 2,400 rent | The intended route: data straight from the bank, name confirmed by the bank. Simulated here. |
| 3 | **Download passport** | A one-page PDF with the figures, four checks and a verification code | The landlord gets a summary, never the transactions. |
| 4 | Scan the QR code with a phone on the same wifi, or open **Verify a passport** and type the code | "Genuine", with the same figures | A landlord can confirm the page they were sent has not been altered. |

## More ways to show what it can do

| Scenario | How | Expected result |
| --- | --- | --- |
| Honest bad news | **Missed rent** sample | Passport issued, with an amber note: "5 of 6 months paid… No payment found in Jul 2026". The landlord sees the same note. |
| Another country and layout | **India, in rupees** sample | INR 145,000 income and INR 42,000 rent. The file uses different column names, lists the newest row first and writes 1,45,000.00. |
| AI reading a PDF | **Genuine** sample (needs `ANTHROPIC_API_KEY`, about 12 seconds) | The same figures as the CSV version, row for row. |
| Evidence | On any passport, open "Show the 6 rows behind this" | The exact statement rows a finding was worked out from. |
| A wrong code | **Verify a passport**, enter `CP-AAAA-AAAA` | "No passport has this code." |
| A file that is not a statement | Upload a CSV with the wrong columns, or a PDF with no text | A plain message saying why it could not be read. No crash, no guess. |
| Saved passports | **Save to my account**, enter an email, then **My passports** | The passport listed with its code. Sign-in is simulated: no email is sent. |
| Working offline | Turn wifi off and use any CSV sample | Still works. Pounds are shown at a fixed indicative rate, labelled as such. |

## From the command line

No browser or API key needed.

```sh
python -m passport samples/genuine.csv --pdf passport.pdf
```
```text
VERIFIED
  [pass] Statement adds up: All 66 rows match the running balance.
  [pass] Regular income: Paid in 6 separate months, typically 6,200.00.
  [pass] Rent payments: 6 of 6 months paid, 6 within 3 days of the usual day (1). Typically 2,400.00 (labelled as rent).
  [pass] Never overdrawn: Lowest balance 5,524.82. 0 row(s) below zero.
Passport written to passport.pdf
```

```sh
python -m passport samples/tampered.csv
```
```text
CANNOT VERIFY
  [note] Statement does not add up: 2 row(s) do not match the running balance.
```

| Command | Exit code | Meaning |
| --- | --- | --- |
| `python -m passport samples/genuine.csv` | 0 | The statement adds up |
| `python -m passport samples/tampered.csv` | 1 | It does not add up; no report is written |
| `python -m passport missing.csv` | 2 | The file could not be read |

## Automated tests

`python -m pytest -q` runs 16 tests in about five seconds. They also run on every push through GitHub Actions.

| Area | Test | What it proves |
| --- | --- | --- |
| Catching edits | `test_tampered_statement_is_caught_with_the_edited_rows` | Two inflated salaries are flagged, and only those two rows |
| | `test_a_single_edited_balance_is_pinpointed` | One nudged balance is located to the exact row |
| | `test_rows_out_of_date_order_cannot_be_verified` | Reordered rows fail the check |
| Findings | `test_genuine_statement_is_verified` | Income 6,200, rent 2,400, all four checks pass |
| | `test_missed_rent_month_is_named_and_not_reported_as_on_time` | A missed month is named, and the passport is still issued |
| | `test_overdraft_is_reported_but_does_not_block_a_genuine_statement` | Negative balances are reported with their rows |
| | `test_income_that_appears_in_too_few_months_is_not_called_regular` | Two months of pay is not called regular income |
| Reading | `test_pipeline_reads_a_model_reply_into_the_same_table_as_the_csv` | AI-read rows match the CSV exactly |
| | `test_model_reply_with_a_pipe_in_the_description_still_parses` | An awkward description does not break a row |
| | `test_a_second_country_layout_reads_newest_first_rupees` | The Indian layout, ordering and number format read correctly |
| | `test_unreadable_input_is_refused_not_guessed` | Bad files raise a clear error |
| Passport and sharing | `test_passport_pdf_is_one_page_summary_without_the_transactions` | One page, no everyday spending, refused for a failed statement |
| | `test_landlord_can_look_up_an_issued_passport_by_its_code` | Codes are stable, lookups work, transactions are never stored |
| | `test_passports_saved_to_an_account_can_be_listed` | Saved passports are listed per email |
| | `test_simulated_bank_feed_is_labelled_as_simulated` | The pretend bank is always labelled as such |
| Command line | `test_command_line_exit_code_reports_the_verdict` | Exit codes 0 and 1 match the verdict |

## Browser walkthrough

`scripts/browser_check.py` clicks through every page, button and error path in a real browser (WebKit) and prints PASS or FAIL for each of about 58 checks. Setup is in the file's header.

It covers the welcome links, all four samples, real CSV uploads, three bad files, both demo banks with consent and cancel, the PDF download and its contents, the email link, the landlord link and QR code, evidence tables, saving to an account, sign in and out, wrong and oddly typed verification codes, a name containing HTML, and phone-width layout on every screen.

On 13 October 2026, 56 of 58 passed. The two failures were in the script, not the app: one check expected the wrong count of saved passports, and one flagged a browser message about a request cut off by navigation. Both are corrected in the version in this repository, which has not been re-run since.

## What the tests do not show

- **A forged statement that adds up will pass.** The balance check catches edits, not a statement invented from scratch.
- **Only two made-up bank layouts are tested.** Real statements vary far more.
- **AI reading is checked on one PDF.** That is one matching result, not a measured error rate.
- **Bank connection and sign-in are simulated.** No real bank or email service is contacted.
