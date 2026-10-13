"""Click through every page, button and error path in a real browser.

Needs the app running and Playwright with WebKit:

    pip install playwright && playwright install webkit
    streamlit run app.py                      # in one terminal
    python scripts/browser_check.py           # in another (PASSPORT_URL overrides the address)

The "Genuine" sample reads a PDF, so that step needs ANTHROPIC_API_KEY set for the app.
Prints PASS or FAIL per check and exits 1 if any fail.
"""
import os, re, sys, pathlib, tempfile, pdfplumber
from reportlab.pdfgen import canvas
from playwright.sync_api import sync_playwright
URL = os.environ.get("PASSPORT_URL", "http://localhost:8501")
REPO = pathlib.Path(__file__).resolve().parent.parent
T = pathlib.Path(tempfile.mkdtemp(prefix="passport-check-"))
(T/"bad.csv").write_text("when,what\n1,2\n3,4\n")
(T/"one_row.csv").write_text("Date,Description,Withdrawal,Deposit,Balance\n01/04/2026,OPENING,,,100.00\n")
c = canvas.Canvas(str(T/"blank.pdf")); c.showPage(); c.save()
results = []; errors = []
def check(name, ok, extra=""):
    results.append((name, bool(ok), extra)); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra and not ok else ""), flush=True)
def body(pg): return pg.inner_text("body")
def clean(pg, name): t = body(pg); check(f"{name}: no error trace", "Traceback" not in t and "Error:" not in t, t[:200])
def start(b, **kw):
    pg = b.new_page(viewport={"width":1100,"height":850}, accept_downloads=True, **kw)
    pg.on("pageerror", lambda e: "Load failed" in str(e) or errors.append(str(e)))  # ignore requests cut off by navigation; pg.goto(URL); pg.wait_for_selector("text=Get started", timeout=30000); return pg
def to_upload(pg):
    pg.get_by_role("button", name="Get started").click(); pg.wait_for_selector("text=Add your bank statement")
def again(pg):
    pg.get_by_role("button", name="Check another statement").click(); pg.wait_for_selector("text=Add your bank statement")

with sync_playwright() as p:
    b = p.webkit.launch()
    # ---------- welcome
    pg = start(b); t = body(pg)
    check("welcome: headline on one line", pg.locator(".hero").bounding_box()["height"] < 45)
    check("welcome: three step cards", pg.locator(".card").count() == 3)
    check("welcome: equal card heights", len({round(pg.locator(".card").nth(i).bounding_box()["height"]) for i in range(3)}) == 1)
    clean(pg, "welcome")
    pg.get_by_role("button", name="Verify a passport").click(); pg.wait_for_selector("text=Enter the verification code"); check("welcome -> Verify a passport", True)
    pg.get_by_role("button", name="Back to start").click(); pg.wait_for_selector("text=Get started"); check("verify -> Back to start", True)
    pg.get_by_role("button", name="Sign in").click(); pg.wait_for_selector("text=Sign in to keep your passports"); check("welcome -> Sign in", True)
    check("signin: button disabled without email", pg.get_by_role("button", name="Send me a sign-in link").is_disabled())
    pg.get_by_role("button", name="Back").click(); pg.wait_for_selector("text=Get started"); check("signin -> Back", True)

    # ---------- upload screen
    to_upload(pg)
    check("upload: Check button disabled with no file", pg.get_by_role("button", name="Check my statement").is_disabled())
    for label, expect in [("Genuine", "Your passport is ready"), ("Edited", "We could not issue a passport"), ("Missed rent", "Your passport is ready"), ("India, in rupees", "Your passport is ready")]:
        pg.get_by_role("button", name=label, exact=True).click(); pg.wait_for_selector(f"text={expect}", timeout=60000); pg.wait_for_timeout(700); t = body(pg)
        check(f"sample '{label}' -> {expect}", True); clean(pg, f"sample {label}")
        if label == "Edited":
            check("edited: two rows shown with -3,000.00 gap", t.count("-3,000.00") == 2)
            check("edited: no figures, no download, no code", "Monthly income" not in t and "Download passport" not in t and "CP-" not in t)
        if label == "Missed rent": check("missed rent: July named", "No payment found in Jul 2026" in t and "note on rent payments" in t)
        if label == "India, in rupees": check("india: rupee figures and name", "INR 145,000" in t and "INR 42,000" in t and "Priya Sharma" in t)
        if label == "Genuine": check("genuine pdf: figures", "SGD 6,200" in t and "SGD 2,400" in t and "39%" in t)
        again(pg)

    # ---------- real uploads
    pg.get_by_placeholder("As it should appear on your passport").fill("Test O'Brien <b>x</b>"); pg.keyboard.press("Tab")
    pg.set_input_files("input[type=file]", str(REPO/"samples/genuine.csv")); pg.wait_for_timeout(1200)
    check("upload: Check button enabled after file", pg.get_by_role("button", name="Check my statement").is_enabled())
    pg.get_by_role("button", name="Check my statement").click(); pg.wait_for_selector("text=Your passport is ready", timeout=30000); pg.wait_for_timeout(800); t = body(pg)
    check("upload csv: typed name shown literally (no HTML injection)", "Test O'Brien <b>x</b>" in t and pg.locator(".caption b").count() == 0)
    check("upload csv: source says uploaded by applicant", "uploaded by the applicant" in t and "name as given by the applicant" in t)
    code_csv = re.search(r"CP-[A-Z2-7]{4}-[A-Z2-7]{4}", t).group(0)
    # result buttons
    with pg.expect_download() as d: pg.get_by_role("button", name="Download passport").click()
    d.value.save_as(T/"out.pdf")
    with pdfplumber.open(T/"out.pdf") as pdf: pt = pdf.pages[0].extract_text(); pages = len(pdf.pages)
    check("pdf: one page with code, name, source, no transactions", pages == 1 and code_csv in pt and "Test O'Brien" in pt and "uploaded by the applicant" in pt and "NTUC" not in pt, pt[:150])
    href = pg.get_by_role("link", name="Email my landlord").get_attribute("href")
    check("email button: mailto with code and link", href.startswith("mailto:?subject=") and code_csv in href and "verify%3D" in href)
    link = re.search(r"http://\S+\?verify=CP-\S+", t).group(0)
    check("landlord link uses network address, not localhost", "localhost" not in link, link)
    check("QR image shown", pg.locator("img").count() >= 1)
    n = pg.locator("div[data-testid='stExpander']").count(); pg.locator("div[data-testid='stExpander'] summary").first.click(); pg.wait_for_timeout(900)
    check("evidence expanders present and open to a table", n >= 3 and pg.locator("div[data-testid='stDataFrame']").count() >= 1, str(n))
    # save to account
    pg.get_by_role("button", name="Save to my account").click(); pg.wait_for_selector("text=Sign in to keep your passports")
    pg.get_by_placeholder("you@example.com").fill("heavy-test@example.com"); pg.keyboard.press("Tab"); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Send me a sign-in link").click(); pg.wait_for_selector("text=Saved to your account", timeout=30000); check("save to account -> returns to result, saved", True)
    again(pg)

    # ---------- bad uploads
    for f, expect in [("bad.csv", "missing a column"), ("one_row.csv", "at least two rows"), ("blank.pdf", "no readable text")]:
        pg.set_input_files("input[type=file]", str(T/f)); pg.wait_for_timeout(1200); pg.get_by_role("button", name="Check my statement").click()
        pg.wait_for_selector("text=We could not read this statement", timeout=30000); t = body(pg)
        check(f"bad upload {f}: plain message", expect in t, t[:200]); clean(pg, f"bad upload {f}")
        pg.get_by_role("button", name="Try another statement").click(); pg.wait_for_selector("text=Add your bank statement")

    # ---------- bank connection, both banks
    for i, (bank, who) in enumerate([("Straits Example Bank, Singapore", "Wei Ling Tan"), ("Example Bank of India", "Priya Sharma")]):
        pg.get_by_text("Connect your bank (demo)").click(); pg.wait_for_selector("text=Simulated for this prototype")
        if i == 1:
            pg.locator("div[data-baseweb='select']").click(); pg.get_by_role("option", name=bank).click(); pg.wait_for_timeout(500)
        pg.get_by_role("button", name="Continue").click(); pg.wait_for_selector("text=We will receive"); t = body(pg)
        check(f"consent {bank}: names bank and says simulation", bank in t and "simulation" in t)
        if i == 0:
            pg.get_by_role("button", name="Cancel").click(); pg.wait_for_selector("text=Add your bank statement"); check("consent -> Cancel returns to upload", True)
            pg.get_by_text("Connect your bank (demo)").click(); pg.get_by_role("button", name="Continue").click(); pg.wait_for_selector("text=We will receive")
        pg.get_by_role("button", name="Allow").click(); pg.wait_for_selector("text=Your passport is ready", timeout=30000); pg.wait_for_timeout(800); t = body(pg)
        check(f"bank {bank}: holder name and simulated label", who in t and "name confirmed by the bank, simulated" in t and "bank connection (simulated)" in t); clean(pg, f"bank {bank}")
        bank_code = re.search(r"CP-[A-Z2-7]{4}-[A-Z2-7]{4}", t).group(0)
        again(pg)

    # ---------- account
    pg.goto(URL); pg.wait_for_selector("text=Get started"); pg.get_by_role("button", name="Sign in").click()
    pg.get_by_placeholder("you@example.com").fill("HEAVY-TEST@example.com"); pg.keyboard.press("Tab"); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Send me a sign-in link").click(); pg.wait_for_selector("text=My passports", timeout=30000); pg.wait_for_timeout(600); t = body(pg)
    check("account: lists the saved passport (email case-insensitive)", code_csv in t, t[:200]); clean(pg, "account")
    pg.get_by_role("button", name="Sign out").click(); pg.wait_for_selector("text=Get started"); check("account -> Sign out shows Sign in again", pg.get_by_role("button", name="Sign in").count() == 1)

    # ---------- landlord verify
    v = b.new_page(viewport={"width":390,"height":800}); v.on("pageerror", lambda e: "Load failed" in str(e) or errors.append(str(e)))
    v.goto(link.replace(re.search(r"CP-\S+", link).group(0), bank_code)); v.wait_for_selector("text=Genuine", timeout=30000); v.wait_for_timeout(800); t = body(v)
    check("verify link (phone width): opens on passport with source", "Priya Sharma" in t and "bank connection (simulated)" in t); clean(v, "verify")
    check("phone width: no sideways scroll on verify", v.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth + 1"))
    box = v.get_by_placeholder("CP-XXXX-XXXX")
    for entry, expect in [("cp-aaaa-aaaa", "No passport has this code"), ("  " + code_csv.lower() + " ", "Genuine"), ("<script>alert(1)</script>", "No passport has this code")]:
        box.fill(entry); v.keyboard.press("Enter"); v.wait_for_selector(f"text={expect}", timeout=15000); check(f"verify code entry {entry.strip()[:14]!r} -> {expect}", True)
    for path, sel, nm in [("", "text=Get started", "welcome")]:
        m = b.new_page(viewport={"width":390,"height":800}); m.goto(URL); m.wait_for_selector(sel, timeout=30000); m.wait_for_timeout(700)
        check("phone width: no sideways scroll on welcome", m.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth + 1"))
        m.get_by_role("button", name="Get started").click(); m.wait_for_selector("text=Add your bank statement"); m.wait_for_timeout(600)
        check("phone width: no sideways scroll on upload", m.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth + 1"))
        m.get_by_role("button", name="Genuine", exact=True).click(); m.wait_for_selector("text=Your passport is ready", timeout=60000); m.wait_for_timeout(900)
        check("phone width: no sideways scroll on result", m.evaluate("document.scrollingElement.scrollWidth <= window.innerWidth + 1"))
    check("no JavaScript page errors anywhere", not errors, "; ".join(errors)[:200])
    b.close()
bad = [r for r in results if not r[1]]
print(f"\n{len(results) - len(bad)} of {len(results)} checks passed"); [print("FAILED:", n, "|", e) for n, _, e in bad]
sys.exit(1 if bad else 0)
