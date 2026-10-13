# Credit Passport

Someone new to the UK has no credit file. This turns their bank statement from home into a
summary a landlord or lender can check: regular income, rent paid on time, never overdrawn.

    streamlit run app.py
    python -m pytest

How it works:

1. `passport/parse.py` reads the statement. For a PDF, a model copies the rows into a table. It makes no judgements.
2. `passport/rules.py` applies fixed rules and attaches the statement rows behind every finding.
3. The first rule checks that every running balance adds up. It catches edited figures and model copying errors alike.

`samples/make_samples.py` rebuilds the fictional demo statements. PDFs need `ANTHROPIC_API_KEY`.
