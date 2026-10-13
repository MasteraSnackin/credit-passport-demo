"""Write the demo statements: a genuine one (CSV and PDF) and a tampered copy.

All names are made up. Run: python samples/make_samples.py
"""
import random
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).parent
SALARY = "SALARY GIRO TEMBUSU ANALYTICS PTE LTD"
SPENDING = [("NTUC FAIRPRICE", 40, 140), ("EZ-LINK TOP UP", 20, 50), ("GRAB", 8, 35),
            ("HAWKER CENTRE PAYNOW", 5, 18), ("SHOPEE SG", 15, 120), ("KOPITIAM", 4, 12)]


def build(skip_rent=None):
    random.seed(7)
    rows = []
    for month in pd.period_range("2026-04", "2026-09", freq="M"):
        day = lambda d: pd.Timestamp(year=month.year, month=month.month, day=d)
        if str(month) != skip_rent:
            rows.append((day(1), "GIRO RENT TIONG BAHRU APT", -2400.00))
        rows.append((day(random.choice([1, 2])), "SP SERVICES UTILITIES", -round(random.uniform(95, 150), 2)))
        rows.append((day(12), "SINGTEL MOBILE", -48.00))
        rows.append((day(25), SALARY, 6200.00))
        for _ in range(7):
            name, low, high = random.choice(SPENDING)
            rows.append((day(random.randint(3, 28)), name, -round(random.uniform(low, high), 2)))
    rows.sort(key=lambda r: r[0])
    balance, out = 8450.00, [("31/03/2026", "BALANCE BROUGHT FORWARD", "", "", "8450.00")]
    for date, name, amount in rows:
        balance = round(balance + amount, 2)
        out.append((date.strftime("%d/%m/%Y"), name, f"{-amount:.2f}" if amount < 0 else "",
                    f"{amount:.2f}" if amount > 0 else "", f"{balance:.2f}"))
    return pd.DataFrame(out, columns=["Date", "Description", "Withdrawal", "Deposit", "Balance"])


def write_pdf(df, path):
    styles = getSampleStyleSheet()
    table = Table([list(df.columns)] + df.values.tolist(), repeatRows=1, colWidths=[65, 235, 70, 70, 75])
    table.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                               ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.grey)]))
    SimpleDocTemplate(str(path), pagesize=A4).build([
        Paragraph("Straits Example Bank (sample data)", styles["Title"]),
        Paragraph("Statement of account, SGD savings. Account holder: Wei Ling Tan (fictional). "
                  "1 April 2026 to 30 September 2026.", styles["Normal"]),
        Spacer(1, 12), table])


if __name__ == "__main__":
    genuine = build()
    genuine.to_csv(HERE / "genuine.csv", index=False)
    write_pdf(genuine, HERE / "genuine.pdf")
    # The fake: two salaries raised from 6,200 to 9,200 without redoing the balances.
    tampered = genuine.copy()
    rows = tampered.index[tampered["Description"] == SALARY][[1, 4]]
    tampered.loc[rows, "Deposit"] = "9200.00"
    tampered.to_csv(HERE / "tampered.csv", index=False)
    # Genuine and adds up, but July's rent was never paid. The passport must say so.
    build(skip_rent="2026-07").to_csv(HERE / "missed_rent.csv", index=False)
    print("wrote genuine.csv, genuine.pdf, tampered.csv, missed_rent.csv")
