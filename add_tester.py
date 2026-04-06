import os
import json
import secrets
import string
import time
from steel import Steel
from playwright.sync_api import sync_playwright

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/4699824931279130112?tab=testers"
SESSION_JSON = os.environ.get("PLAY_CONSOLE_SESSION")
STEEL_API_KEY = os.environ.get("STEEL_API_KEY")

MAX_ATTEMPTS = 8
BASE_DELAY_S = 2
MAX_DELAY_S = 60


def get_random_list_name(length=6):
    chars = string.ascii_letters + string.digits
    return "List_" + ''.join(secrets.choice(chars) for _ in range(length))


def _attempt_add_tester(email: str) -> dict:
    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")

    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")

    session_data = json.loads(SESSION_JSON)

    cleaned_cookies = [
        {k: v for k, v in cookie.items() if k != "partitionKey"}
        for cookie in session_data["cookies"]
    ]

    local_storage = session_data.get("localStorage", {})
    if isinstance(local_storage, str):
        try:
            local_storage = json.loads(local_storage)
        except json.JSONDecodeError:
            local_storage = {}

    client = Steel(steel_api_key=STEEL_API_KEY)
    print("[Steel] Creating session...")

    session = client.sessions.create(session_context={
        "cookies": cleaned_cookies,
        "localStorage": local_storage
    })

    print(f"[Steel] Session created: {session.id}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
            )

            context = browser.contexts[0]
            page = context.pages[0]

            print("[Steel] Navigating...")
            page.goto(TESTERS_URL, wait_until="networkidle")
            page.wait_for_timeout(3000)

            if "accounts.google.com" in page.url:
                raise Exception("Session expired — re-run save_session.py locally")

            # =========================
            # FIXED BUTTON HANDLING
            # =========================
            print("[Steel] Locating 'Create email list' button...")

            btn = page.locator("button[debug-id='create-list-button']")

            for _ in range(5):
                try:
                    btn.wait_for(state="visible", timeout=3000)
                    break
                except:
                    print("[Steel] Button not visible, scrolling...")
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(1000)
            else:
                raise Exception("Create email list button not found even after scrolling")

            btn.scroll_into_view_if_needed()
            btn.click()

            page.wait_for_timeout(3000)

            # =========================
            # MODAL
            # =========================
            print("[Steel] Waiting for modal...")
            page.wait_for_selector("[role='dialog'] input", state="visible", timeout=15000)

            list_name = get_random_list_name()
            print(f"[Steel] Filling list name: {list_name}")

            name_input = page.locator("[role='dialog'] input").first
            name_input.fill(list_name)

            print(f"[Steel] Filling email: {email}")

            email_inputs = page.locator("[role='dialog'] input[type='email']")
            if email_inputs.count() > 0:
                email_input = email_inputs.first
            else:
                email_input = page.locator("[role='dialog'] input").nth(1)

            email_input.fill(email)
            page.keyboard.press("Enter")

            page.wait_for_timeout(1000)

            create_btn = page.locator("button[debug-id='create-button']")

            print("[Steel] Clicking 'Save changes'...")
            create_btn.scroll_into_view_if_needed()
            create_btn.click()

            # =========================
            # CONFIRMATION
            # =========================
            print("[Steel] Waiting for confirmation dialog...")
            page.wait_for_selector("text='Create email list?'", timeout=10000)

            print("[Steel] Confirming...")
            page.locator("button:has-text('Create')").last.click()

            # Wait for modal to close
            print("[Steel] Waiting for modal to close...")
            for _ in range(30):
                if page.locator("button[debug-id='create-button']").count() == 0:
                    break
                page.wait_for_timeout(500)
            else:
                raise Exception("Modal did not close")

            # =========================
            # FINAL SAVE
            # =========================
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

            browser.close()

    except Exception:
        client.sessions.release(session.id)
        print("[Steel] Session released (error)")
        raise

    client.sessions.release(session.id)
    print("[Steel] Session released")

    return {"success": True, "email": email}


def add_tester(email: str) -> dict:
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")

    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")

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
