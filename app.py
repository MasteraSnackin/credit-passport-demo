"""Credit Passport: a foreign bank statement in, an evidence-backed summary out.

Run: streamlit run app.py
"""
from pathlib import Path

import requests
import streamlit as st

from passport.parse import StatementError
from passport.pipeline import run
from passport.report import build_pdf
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
    return run(name, data)


st.title("Credit Passport")
st.caption("New to the UK with no credit file? Turn your bank statement from home into a summary "
           "a landlord or lender can check.")

# The tampered sample comes first: the demo opens on a fake being caught.
files = {"Tampered sample (CSV)": "tampered.csv", "Genuine sample (CSV)": "genuine.csv",
         "Genuine sample (PDF)": "genuine.pdf"}
choice = st.radio("Statement", [*files, "Upload my own"], horizontal=True)
if choice in files:
    name, data = files[choice], (SAMPLES / files[choice]).read_bytes()
else:
    upload = st.file_uploader("Bank statement (CSV or PDF)", type=["csv", "pdf"])
    if not upload:
        st.stop()
    name, data = upload.name, upload.getvalue()

try:
    result = load(name, data)
except StatementError as error:
    st.error(f"**Could not read this statement.** {error}")
    st.stop()
except Exception:
    st.error("**Could not read this statement.** The reading service did not respond. Check the connection "
             "and the ANTHROPIC_API_KEY, or try a CSV.")
    st.stop()
tx, currency, passport = result.transactions, result.currency, result.passport
rate, rate_source = gbp_rate(currency)
start, end = passport["period"]

if passport["verified"]:
    st.success(f"**Statement adds up.** {len(tx)} rows, {start:%d %b %Y} to {end:%d %b %Y}.")
else:
    st.error("**Cannot verify.** This statement does not add up, so the figures below should not be relied on.")
    broken = passport["findings"][0].evidence
    if not broken.empty:
        st.markdown(f"**{len(broken)} row(s) where the balance does not follow from the amount:**")
        st.dataframe(
            broken.assign(date=broken["date"].dt.date, gap=(broken["balance"] - broken["expected_balance"]).round(2))
            .rename(columns={"balance": "balance on statement", "expected_balance": "balance it should be"}),
            hide_index=True,
        )


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

if passport["verified"]:
    st.download_button("Download the one-page passport (PDF)", build_pdf(passport, currency, rate, rate_source),
                       file_name="credit-passport.pdf", mime="application/pdf", type="primary")
else:
    st.info("No passport is issued for a statement that cannot be verified.")

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
