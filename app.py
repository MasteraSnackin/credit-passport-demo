"""Credit Passport: a foreign bank statement in, an evidence-backed summary out.

Run: streamlit run app.py
"""
from datetime import date
from html import escape
from pathlib import Path

import requests
import streamlit as st

from passport.parse import StatementError
from passport import registry
from passport.pipeline import run
from passport.report import build_pdf

SAMPLES = Path(__file__).parent / "samples"
FALLBACK_RATE = 0.58  # indicative SGD to GBP, used only if the live rate cannot be fetched
SAMPLES_ON_OFFER = {"A genuine sample": "genuine.pdf", "An edited sample": "tampered.csv",
                    "A missed-rent sample": "missed_rent.csv"}

st.set_page_config(page_title="Credit Passport", layout="centered")

# Design rules this stylesheet holds to:
#   type      six sizes only (34, 28, 20, 17, 15, 13 px)
#   spacing   multiples of 8 px
#   colour    black text, two greys, one blue for links; red and green mean status and nothing else
#   actions   one filled button per screen
st.markdown(
    """
<style>
:root {--ink: #1d1d1f; --grey: #6e6e73; --faint: #86868b; --line: #e8e8ed; --card: #f5f5f7; --link: #0066cc;
       --good: #30b158; --bad: #e3352b; --warn: #c98a00;}
header[data-testid="stHeader"], [data-testid="stToolbar"], footer, [data-testid="InputInstructions"] {display: none;}
html, body, [class*="st-"], .stMarkdown {font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Helvetica Neue", sans-serif;}
.block-container {max-width: 728px; padding: clamp(48px, 11vh, 112px) 24px 96px;}
[data-testid="stVerticalBlock"] {gap: 16px;}

.eyebrow {font-size: 13px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--faint);
          display: flex; align-items: center; gap: 8px; margin-bottom: 16px;}
.eyebrow.good {color: #1f8a41;} .eyebrow.bad {color: #c62a21;}
.hero {font-size: 34px; line-height: 1.1; font-weight: 600; letter-spacing: -.025em; color: var(--ink); white-space: nowrap;}
.title {font-size: 28px; line-height: 1.15; font-weight: 600; letter-spacing: -.022em; color: var(--ink);}
.lede {font-size: 17px; line-height: 1.5; color: var(--grey); margin: 8px 0 32px; max-width: 34em;}
.section {font-size: 20px; font-weight: 600; letter-spacing: -.015em; margin: 48px 0 8px;}
.caption {font-size: 13px; line-height: 1.5; color: var(--faint);}
.dot {width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none;}
.dot.good {background: var(--good);} .dot.bad {background: var(--bad);} .dot.warn {background: var(--warn);}

.grid {display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;}
.card {background: var(--card); border-radius: 20px; padding: 24px;}
.card .k {font-size: 13px; color: var(--grey);}
.card .h {font-size: 17px; font-weight: 600; margin: 8px 0 4px;}
.card .d {font-size: 15px; line-height: 1.45; color: var(--grey); text-wrap: balance;}
.card .v {font-size: 28px; font-weight: 600; letter-spacing: -.02em; margin-top: 8px; white-space: nowrap; font-variant-numeric: tabular-nums;}
.card .a {font-size: 13px; color: var(--faint); margin-top: 4px;}

.edit {display: flex; justify-content: space-between; gap: 24px; padding: 16px 0; border-top: 1px solid #dfdfe4; font-size: 15px;}
.edit:first-of-type {margin-top: 16px;}
.edit .m {color: var(--grey); font-size: 13px; margin-top: 4px;}
.edit .r {text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums;}
.edit .gap {color: var(--bad); font-weight: 600; margin-top: 4px;}

.check {display: flex; gap: 16px; padding: 16px 0 0; border-top: 1px solid var(--line); align-items: baseline;}
.check .h {font-size: 17px; font-weight: 600;} .check .d {font-size: 15px; color: var(--grey); margin-top: 4px;}
.limits {font-size: 15px; line-height: 1.6; color: var(--grey); max-width: 38em;}

div[data-testid="stExpander"] details {border: none; background: transparent;}
div[data-testid="stExpander"] summary {padding: 0 0 8px 24px; color: var(--link); font-size: 13px; min-height: 0;}
.stButton button, .stDownloadButton button {min-height: 44px;}
.stButton button[kind="primary"], .stDownloadButton button {border-radius: 980px; padding: 0 28px; font-size: 17px; font-weight: 500; border: none;}
.stButton button[kind="tertiary"] {color: var(--link); font-size: 15px;}
.stTextInput label p, .stFileUploader label p {font-size: 13px; color: var(--grey);}
.stTextInput div[data-baseweb="input"], .stTextInput div[data-baseweb="base-input"] {border-radius: 12px; min-height: 48px; align-items: center;}
.stTextInput input {font-size: 17px;}
.stButton button[kind="primary"]:disabled {background: var(--line); color: var(--faint);}
[data-testid="stFileUploaderDropzone"] {border-radius: 16px; padding: 24px;}

@media (max-width: 600px) {.grid {grid-template-columns: 1fr;} .hero {font-size: 28px; white-space: normal;}}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def gbp_rate(currency):
    try:
        reply = requests.get("https://api.frankfurter.dev/v1/latest",
                             params={"base": currency, "symbols": "GBP"}, timeout=5).json()
        return reply["rates"]["GBP"], f"European Central Bank rate, {reply['date']}"
    except Exception:
        return FALLBACK_RATE, "indicative rate, live rate unavailable"


@st.cache_data(show_spinner="Reading the statement")
def load(name, data):
    return run(name, data)


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def go(to, **values):
    st.session_state.update(step=to, **values)
    st.rerun()


def eyebrow(text, state=""):
    dot = f'<span class="dot {state}"></span>' if state else ""
    return f'<div class="eyebrow {state}">{dot}{text}</div>'


def card(*parts):
    return '<div class="card">' + "".join(f'<div class="{cls}">{text}</div>' for cls, text in parts) + "</div>"


# A landlord can arrive straight on the verify screen from a link: ?verify=CP-XXXX-XXXX
if "verify" in st.query_params and "step" not in st.session_state:
    st.session_state.update(step="verify", code=st.query_params["verify"])
step = st.session_state.setdefault("step", "welcome")

# 1. Welcome
if step == "welcome":
    html(eyebrow("Credit Passport")
         + '<div class="hero">Your financial record, wherever you move.</div>'
         '<div class="lede">New to the UK with no credit file? Turn your bank statement from home into proof '
         'a landlord can check.</div>'
         '<div class="grid">'
         + card(("k", "1"), ("h", "Add your statement"), ("d", "Six months of history, as a PDF or CSV."))
         + card(("k", "2"), ("h", "We check it"), ("d", "We confirm every balance adds up."))
         + card(("k", "3"), ("h", "Send your passport"), ("d", "One page your landlord can read."))
         + "</div>")
    st.write("")
    if st.button("Get started", type="primary"):
        go("upload")
    if st.button("I'm a landlord: verify a passport", type="tertiary"):
        go("verify")
    html('<div class="caption">Takes about a minute. Your statement is not stored. We keep only the one-page summary, so your landlord can check it is genuine.</div>')
    st.stop()

# 2. Add the statement
if step == "upload":
    html(eyebrow("Step 1 of 2")
         + '<div class="title">Add your bank statement</div>'
         '<div class="lede">Download it from your bank\'s app or website, then add it here.</div>')
    applicant = st.text_input("Your full name", placeholder="As it should appear on your passport")
    upload = st.file_uploader("Bank statement", type=["pdf", "csv"])
    st.write("")
    if st.button("Check my statement", type="primary", disabled=upload is None):
        go("result", applicant=applicant.strip(), file=(upload.name, upload.getvalue()))
    html('<div class="caption" style="margin-top:24px">No statement to hand? Try:</div>')
    for column, (label, sample) in zip(st.columns(3), SAMPLES_ON_OFFER.items()):
        if column.button(label, type="tertiary"):
            go("result", applicant=applicant.strip() or "Wei Ling Tan", file=(sample, (SAMPLES / sample).read_bytes()))
    st.stop()

# Landlord: check a passport is genuine
if step == "verify":
    html(eyebrow("For landlords and agents")
         + '<div class="title">Verify a passport</div>'
         '<div class="lede">Enter the verification code printed on the passport you were sent. You will see the '
         'summary exactly as it was issued.</div>')
    code = st.text_input("Verification code", value=st.session_state.get("code", ""), placeholder="CP-XXXX-XXXX")
    record = registry.lookup(code) if code.strip() else None
    if record:
        currency, ratio = record["currency"], record["rent_to_income"]
        start, end = (date.fromisoformat(d) for d in record["period"])
        issued = date.fromisoformat(record["issued"])
        amount = lambda v: "n/a" if v is None else f"{currency} {v:,.0f}"
        html(eyebrow(f"Genuine · issued {issued:%-d %b %Y}", "good")
             + f'<div class="title">{escape(record["applicant"]) or "Applicant name not given"}</div>'
             f'<div class="lede">Summary of a bank statement covering {start:%-d %b %Y} to {end:%-d %b %Y}. '
             'If the page you were sent shows different figures, it has been altered.</div>'
             '<div class="grid">'
             + card(("k", "Monthly income"), ("v", amount(record["monthly_income"])))
             + card(("k", "Monthly rent"), ("v", amount(record["monthly_rent"])))
             + card(("k", "Rent as share of income"), ("v", "n/a" if ratio is None else f"{ratio:.0%}"))
             + "</div>"
             + '<div class="section">What was checked</div>'
             + "".join(f'<div class="check"><span class="dot {"good" if c["ok"] else "warn"}"></span><div>'
                       f'<div class="h">{escape(c["label"])}</div><div class="d">{escape(c["detail"])}</div></div></div>'
                       for c in record["checks"]))
    elif code.strip():
        html(eyebrow("Not found", "bad") + '<div class="title">No passport has this code.</div>'
             '<div class="lede">Check the code for typing errors. If it still does not match, do not rely on the '
             'page you were sent.</div>')
    st.write("")
    if st.button("Back to start", type="tertiary"):
        st.query_params.clear()
        go("welcome", code="")
    st.stop()

# 3. Result
name, data = st.session_state["file"]
applicant = st.session_state.get("applicant", "")


def could_not_read(reason):
    html(eyebrow("Not read", "bad") + '<div class="title">We could not read this statement.</div>'
         f'<div class="lede">{escape(reason)}</div>')
    if st.button("Try another statement", type="primary"):
        go("upload")
    st.stop()


try:
    result = load(name, data)
except StatementError as error:
    could_not_read(str(error))
except Exception:
    could_not_read("The reading service did not respond. Check the connection and the ANTHROPIC_API_KEY, or try a CSV.")

tx, currency, passport = result.transactions, result.currency, result.passport
start, end = passport["period"]
integrity = passport["findings"][0]

if not passport["verified"]:
    # A failed statement shows the reason and one way forward. No figures: they cannot be trusted.
    broken = integrity.evidence
    rows = "".join(
        f'<div class="edit"><div>{escape(row.description.title())}'
        f'<div class="m">{row.date:%-d %b %Y} · amount {row.amount:,.2f}</div></div>'
        f'<div class="r">Balance shown {row.balance:,.2f}<div class="m">should be {row.expected_balance:,.2f}</div>'
        f'<div class="gap">{row.balance - row.expected_balance:+,.2f}</div></div></div>'
        for row in broken.itertuples()
    )
    html(eyebrow("Not verified", "bad")
         + '<div class="title">We could not issue a passport.</div>'
         '<div class="lede">The figures on this statement do not add up. Download a fresh copy directly from your '
         'bank and try again.</div>'
         f'<div class="card"><div class="h" style="margin-top:0">{len(broken)} rows where the balance does not '
         f'follow from the amount</div>{rows}</div>')
    st.write("")
    if st.button("Check another statement", type="primary"):
        go("upload")
    st.stop()

rate, rate_source = gbp_rate(currency)
code = registry.issue(passport, currency, applicant)


def money(label, value):
    if value is None:
        return card(("k", label), ("v", "n/a"))
    return card(("k", label), ("v", f"{currency} {value:,.0f}"), ("a", f"about £{value * rate:,.0f}"))


# A genuine statement can still carry bad news. It is shown to the applicant before the landlord sees it.
flagged = [f.label.lower() for f in passport["findings"] if not f.ok]
notes = f" It includes a note on {' and '.join(flagged)}, shown below." if flagged else ""
ratio = passport["rent_to_income"]
html(eyebrow(f"Verified · {start:%-d %b %Y} to {end:%-d %b %Y}", "good")
     + '<div class="title">Your passport is ready.</div>'
     f'<div class="lede">Download it and send it to your landlord or letting agent. They see this summary, '
     f'not your transactions.{notes}</div>'
     '<div class="grid">'
     + money("Monthly income", passport["monthly_income"])
     + money("Monthly rent", passport["monthly_rent"])
     + card(("k", "Rent as share of income"), ("v", "n/a" if ratio is None else f"{ratio:.0%}"))
     + "</div>"
     + f'<div class="caption" style="margin-top:8px">{"Prepared for " + escape(applicant) + ". " if applicant else ""}'
       f'1 {currency} = £{rate:.4f} ({rate_source}).</div>'
     + f'<div class="card" style="margin-top:16px"><div class="k">Verification code</div><div class="v">{code}</div>'
       '<div class="a">Printed on your passport. Your landlord enters it here to confirm the page is genuine.</div></div>')

st.write("")
left, right, _ = st.columns([1.3, 1.4, 1.3])
left.download_button("Download passport", build_pdf(passport, currency, rate, rate_source, applicant, code),
                     file_name="credit-passport.pdf", mime="application/pdf", type="primary")
if right.button("Check another statement", type="tertiary"):
    go("upload")

html('<div class="section">What we checked</div>')
for finding in passport["findings"]:
    html(f'<div class="check"><span class="dot {"good" if finding.ok else "warn"}"></span>'
         f'<div><div class="h">{escape(finding.label)}</div><div class="d">{escape(finding.detail)}</div></div></div>')
    if not finding.evidence.empty:
        with st.expander(f"Show the {len(finding.evidence)} rows behind this"):
            st.dataframe(finding.evidence.assign(date=finding.evidence["date"].dt.date), hide_index=True)

html('<div class="section">What this does not prove</div>'
     '<div class="limits">A carefully made fake that adds up will pass: the balance check catches edited figures, '
     'not a statement invented from scratch. The real fix is data pulled straight from the bank, through '
     "Singapore's SGFinDex or UK open banking. This is a summary of the past six months, not a credit score "
     'and not a lending decision.</div>')
