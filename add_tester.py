import os
import secrets
import string
import time
from steel import Steel
from playwright.sync_api import sync_playwright

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/4699824931279130112?tab=testers"
STEEL_API_KEY = os.environ.get("STEEL_API_KEY")
STEEL_SESSION_ID = os.environ.get("STEEL_SESSION_ID")  # ← replaces PLAY_CONSOLE_SESSION

MAX_ATTEMPTS = 8
BASE_DELAY_S = 2
MAX_DELAY_S = 60


def get_random_list_name(length=6):
    chars = string.ascii_letters + string.digits
    return "List_" + ''.join(secrets.choice(chars) for _ in range(length))


def _attempt_add_tester(email: str) -> dict:
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")
    if not STEEL_SESSION_ID:
        raise ValueError("STEEL_SESSION_ID env var not set — run setup_session.py first")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")

    client = Steel(steel_api_key=STEEL_API_KEY)

    # Reuse existing persistent session — never create a new one
    print(f"[Steel] Reusing session {STEEL_SESSION_ID}...")
    session = client.sessions.retrieve(STEEL_SESSION_ID)

    if session.status != "live":
        raise Exception(f"Session is {session.status} — re-run setup_session.py to get a new one")

    # ⚠️ No try/finally that releases — session must stay alive
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(
            f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={STEEL_SESSION_ID}"
        )

        context = browser.contexts[0]
        page = context.pages[0]

        print("[Steel] Navigating...")
        page.goto(TESTERS_URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        if "accounts.google.com" in page.url:
            raise Exception("Session expired — re-run setup_session.py locally")

        # === Create email list button ===
        print("[Steel] Locating 'Create email list' button...")
        btn = page.locator("button[debug-id='create-list-button']")

        for _ in range(5):
            try:
                btn.wait_for(state="visible", timeout=3000)
                break
            except Exception:
                print("[Steel] Button not visible, scrolling...")
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1000)
        else:
            raise Exception("Create email list button not found even after scrolling")

        btn.scroll_into_view_if_needed()
        btn.click()
        page.wait_for_timeout(3000)

        # === Modal ===
        print("[Steel] Waiting for modal...")
        page.wait_for_selector("[role='dialog'] input", state="visible", timeout=15000)

        list_name = get_random_list_name()
        print(f"[Steel] Filling list name: {list_name}")
        name_input = page.locator("[role='dialog'] input").first
        name_input.fill(list_name)

        print(f"[Steel] Filling email: {email}")
        email_inputs = page.locator("[role='dialog'] input[type='email']")
        email_input = email_inputs.first if email_inputs.count() > 0 else page.locator("[role='dialog'] input").nth(1)
        email_input.fill(email)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)

        # === Save ===
        create_btn = page.locator("button[debug-id='create-button']")
        print("[Steel] Clicking 'Save changes'...")
        create_btn.scroll_into_view_if_needed()
        create_btn.click()

        # === Confirm ===
        print("[Steel] Waiting for confirmation dialog...")
        page.wait_for_selector("text='Create email list?'", timeout=10000)
        print("[Steel] Confirming...")
        page.locator("button:has-text('Create')").last.click()

        print("[Steel] Waiting for modal to close...")
        for _ in range(30):
            if page.locator("button[debug-id='create-button']").count() == 0:
                break
            page.wait_for_timeout(500)
        else:
            raise Exception("Modal did not close")

        # === Final save ===
        print("[Steel] Final save...")
        final_save = page.locator("button[debug-id='main-button']")
        final_save.wait_for(state="visible", timeout=10000)

        for _ in range(20):
            if final_save.get_attribute("disabled") is None:
                break
            page.wait_for_timeout(500)
        else:
            raise Exception("Final save button never enabled")

        final_save.scroll_into_view_if_needed()
        final_save.click()
        page.wait_for_timeout(2000)

        # ✅ Close browser but NEVER release session
        browser.close()
        print("[Steel] Done. Session kept alive.")

    return {"success": True, "email": email}


def add_tester(email: str) -> dict:
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")
    if not STEEL_SESSION_ID:
        raise ValueError("STEEL_SESSION_ID env var not set — run setup_session.py first")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n[Retry] Attempt {attempt}/{MAX_ATTEMPTS}")
        try:
            return _attempt_add_tester(email)
        except Exception as e:
            last_error = e
            print(f"[Retry] Failed: {e}")
            if attempt < MAX_ATTEMPTS:
                delay = min(BASE_DELAY_S * (2 ** (attempt - 1)), MAX_DELAY_S)
                print(f"[Retry] Waiting {delay}s...")
                time.sleep(delay)

    raise Exception(f"Failed after {MAX_ATTEMPTS} attempts: {last_error}")
