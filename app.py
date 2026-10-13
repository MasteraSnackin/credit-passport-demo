"""Credit Passport: a foreign bank statement in, an evidence-backed summary out.

Run: streamlit run app.py
"""
from pathlib import Path

import requests
import streamlit as st

from passport.parse import parse_csv, parse_pdf
from passport.rules import build_passport

SAMPLES = Path(__file__).parent / "samples"
FALLBACK_RATE = 0.58  # indicative SGD to GBP, used only if the live rate cannot be fetched

st.set_page_config(page_title="Credit Passport", page_icon="🛂", layout="centered")


@st.cache_data(ttl=3600)
def gbp_rate(currency):
    try:
        reply = requests.get("https://api.frankfurter.dev/v1/latest",
                             params={"base": currency, "symbols": "GBP"}, timeout=5).json()
        return reply["rates"]["GBP"], f"European Central Bank rate, {reply['date']}"
    except Exception:
        return FALLBACK_RATE, "indicative rate, live rate unavailable"


@st.cache_data(show_spinner="Reading the statement...")
def load(name, data):
    if name.lower().endswith(".pdf"):
        return parse_pdf(data)
    import io
    return parse_csv(io.BytesIO(data)), "SGD"


st.title("Credit Passport")
st.caption("New to the UK with no credit file? Turn your bank statement from home into a summary "
           "a landlord or lender can check.")

choice = st.radio("Statement", ["Genuine sample (PDF)", "Genuine sample (CSV)", "Tampered sample (CSV)", "Upload my own"],
                  horizontal=True)
files = {"Genuine sample (PDF)": "genuine.pdf", "Genuine sample (CSV)": "genuine.csv",
         "Tampered sample (CSV)": "tampered.csv"}
if choice in files:
    name, data = files[choice], (SAMPLES / files[choice]).read_bytes()
else:
    upload = st.file_uploader("Bank statement (CSV or PDF)", type=["csv", "pdf"])
    if not upload:
        st.stop()
    name, data = upload.name, upload.getvalue()

tx, currency = load(name, data)
currency = currency or "SGD"
passport = build_passport(tx)
rate, rate_source = gbp_rate(currency)
start, end = passport["period"]

if passport["verified"]:
    st.success(f"**Statement adds up.** {len(tx)} rows, {start:%d %b %Y} to {end:%d %b %Y}.")
else:
    st.error("**Cannot verify.** This statement does not add up, so the figures below should not be relied on.")


def money(value):
    return "n/a" if value is None else f"{currency} {value:,.0f}"


def pounds(value):
    return None if value is None else f"about £{value * rate:,.0f}"


income, rent, ratio = passport["monthly_income"], passport["monthly_rent"], passport["rent_to_income"]
a, b, c = st.columns(3)
a.metric("Monthly income", money(income), pounds(income), delta_color="off")
b.metric("Monthly rent", money(rent), pounds(rent), delta_color="off")
c.metric("Rent as share of income", "n/a" if ratio is None else f"{ratio:.0%}")
st.caption(f"1 {currency} = £{rate:.4f} ({rate_source}).")

st.subheader("What we checked")
for finding in passport["findings"]:
    with st.expander(f"{'✅' if finding.ok else '⚠️'} {finding.label}: {finding.detail}"):
        if finding.evidence.empty:
            st.write("No rows to show.")
        else:
            st.dataframe(finding.evidence.assign(date=finding.evidence["date"].dt.date), hide_index=True)

st.subheader("What this does not prove")
st.markdown(
    "- **A carefully made fake that adds up will pass.** The balance check catches edited figures, not a statement invented from scratch.\n"
    "- **The real fix is bank-sourced data**, for example Singapore's SGFinDex or UK open banking, so the applicant never handles the file.\n"
    "- **This is a summary of the past six months**, not a credit score and not a lending decision."
)
