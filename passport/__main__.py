"""Command line: python -m passport samples/genuine.csv [--pdf passport.pdf]

Exit code 0 means the statement adds up, 1 means it does not, 2 means it could not be read.
"""
import argparse
import sys
from pathlib import Path

from .parse import StatementError
from .pipeline import run
from .report import build_pdf

INDICATIVE_RATE = 0.58


def main():
    parser = argparse.ArgumentParser(prog="passport", description="Check a bank statement and summarise it.")
    parser.add_argument("statement", type=Path)
    parser.add_argument("--pdf", type=Path, help="write the one-page passport here (verified statements only)")
    args = parser.parse_args()
    try:
        result = run(args.statement.name, args.statement.read_bytes())
    except (StatementError, OSError) as error:
        print(f"Could not read the statement: {error}", file=sys.stderr)
        return 2
    passport = result.passport
    print("VERIFIED" if passport["verified"] else "CANNOT VERIFY")
    for finding in passport["findings"]:
        print(f"  [{'pass' if finding.ok else 'note'}] {finding.label}: {finding.detail}")
    if args.pdf and passport["verified"]:
        args.pdf.write_bytes(build_pdf(passport, result.currency, INDICATIVE_RATE, "indicative rate"))
        print(f"Passport written to {args.pdf}")
    return 0 if passport["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
