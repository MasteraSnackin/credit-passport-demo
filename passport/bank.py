"""A pretend bank connection, to show where bank-sourced data would plug in.

THIS IS SIMULATED. No real bank is contacted. A real version would call an open banking
provider (UK) or SGFinDex (Singapore) and receive the transactions directly, so the
applicant never handles the file. That is the only complete answer to forged statements.
"""
from pathlib import Path

SAMPLES = Path(__file__).parent.parent / "samples"
SOURCE = "Bank connection (simulated)"
BANKS = {
    "Straits Example Bank, Singapore": ("genuine.csv", "SGD"),
    "Example Bank of India": ("india.csv", "INR"),
}


def fetch_statement(bank):
    """Stand-in for the provider call. Returns (file name, bytes, currency) like an upload would."""
    name, currency = BANKS[bank]
    return name, (SAMPLES / name).read_bytes(), currency
