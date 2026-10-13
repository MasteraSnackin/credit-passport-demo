# Credit Passport

Someone new to the UK has no credit file. This turns their bank statement from home into a
summary a landlord or lender can check: regular income, rent paid on time, never overdrawn.

## Run it

    pip install -r requirements.txt
    streamlit run app.py                                  # the page, at localhost:8501
    python -m passport samples/genuine.csv --pdf out.pdf  # the same pipeline from the command line
    python -m pytest                                      # tests, no API key needed

Reading a PDF statement needs `ANTHROPIC_API_KEY` in your shell (see `.env.example`). CSV statements need nothing.

## How it fits together

    statement ──> parse.py ──> rules.py ──> app.py (page) / report.py (one-page PDF)
                  read rows    check and    present
                               summarise
                  └────── pipeline.run() ──────┘

| File | Job |
| --- | --- |
| `passport/parse.py` | Reads the statement into four columns: date, description, amount, balance. For a PDF, a model copies the rows. It makes no judgements. |
| `passport/rules.py` | Fixed rules. Checks every running balance adds up, then finds income, rent and overdrafts, with the rows behind each. |
| `passport/pipeline.py` | `run(name, data)`: the one entry point the page, command line and tests share. |
| `passport/report.py` | The one-page PDF. Summary only, never the transactions. Refuses an unverified statement. |
| `app.py` | The Streamlit page. |
| `samples/make_samples.py` | Rebuilds the fictional demo statements. |

The balance check is the safety net: it catches edited figures and model copying errors alike.
Anything that cannot be read cleanly raises `StatementError` instead of guessing.

Tests run on every push through GitHub Actions (`.github/workflows/tests.yml`).
