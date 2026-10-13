"""A pretend bank connection, to show where bank-sourced data would plug in.

THIS IS SIMULATED. No real bank is contacted. A real version would call an open banking
provider (UK) or SGFinDex (Singapore) and receive the transactions directly, so the
applicant never handles the file. That is the only complete answer to forged statements.
"""
from pathlib import Path

SAMPLES = Path(__file__).parent.parent / "samples"
SOURCE = "Bank connection (simulated)"
BANKS = {
    "Straits Example Bank, Singapore": {"file": "genuine.csv", "currency": "SGD", "holder": "Wei Ling Tan"},
    "Example Bank of India": {"file": "india.csv", "currency": "INR", "holder": "Priya Sharma"},
}
# What the applicant agrees to on the consent screen.
WE_RECEIVE = ["Your name, as your bank holds it", "Six months of transactions from one account"]
WE_NEVER = ["See your bank login or password", "Move money or change anything", "Keep your transactions after the check"]


def fetch_statement(bank):
    """Stand-in for the provider call. Returns what a real feed would: the statement and the holder's name."""
    account = BANKS[bank]
    return {"name": account["file"], "data": (SAMPLES / account["file"]).read_bytes(),
            "currency": account["currency"], "holder": account["holder"]}


def name_note(source):
    """How far the name on a passport can be trusted, given where the data came from."""
    return "name confirmed by the bank, simulated" if source == SOURCE else "name as given by the applicant"
