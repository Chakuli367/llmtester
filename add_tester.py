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

MAX_ATTEMPTS = 8          # total tries before giving up
BASE_DELAY_S = 2          # seconds — doubles each attempt, capped at 60s
MAX_DELAY_S = 60


def get_random_list_name(length=6):
    chars = string.ascii_letters + string.digits
    return "List_" + ''.join(secrets.choice(chars) for _ in range(length))


def _attempt_add_tester(email: str) -> dict:
    """
    Single attempt to add a tester via Steel + Playwright.
    Raises on any failure so the caller can retry.
    """
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

            # Click 'Create email list'
            print("[Steel] Clicking 'Create email list'...")
            btn = page.locator("button[debug-id='create-list-button']")
            btn.wait_for(state="visible", timeout=15000)
            btn.click(force=True)
            page.wait_for_timeout(3000)

            # Wait for modal
            print("[Steel] Waiting for modal...")
            page.wait_for_selector("[role='dialog'] input", state="visible", timeout=15000)
            page.wait_for_timeout(1000)

            # Fill list name
            list_name = get_random_list_name()
            print(f"[Steel] Filling list name: '{list_name}'")
            name_input = page.locator("[role='dialog'] input").first
            name_input.click()
            name_input.fill(list_name)
            page.wait_for_timeout(500)

            # Fill email
            print(f"[Steel] Filling email: {email}")
            email_inputs = page.locator("[role='dialog'] input[type='email']")
            if email_inputs.count() > 0:
                email_input = email_inputs.first
            else:
                email_input = page.locator("[role='dialog'] input").nth(1)
            email_input.click()
            email_input.fill(email)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Log button state
            create_btn = page.locator("button[debug-id='create-button']")
            is_disabled = create_btn.get_attribute("disabled")
            print(f"[Steel] create-button disabled: {is_disabled}")

            # Click Save changes
            print("[Steel] Clicking 'Save changes'...")
            create_btn.click(force=True)
            page.wait_for_timeout(2000)

            # Handle confirmation dialog
            print("[Steel] Waiting for confirmation dialog...")
            page.wait_for_selector("text='Create email list?'", state="visible", timeout=10000)
            print("[Steel] Clicking 'Create' in confirmation dialog...")
            page.locator("button:has-text('Create')").last.click()

            # Wait for modal to close
            print("[Steel] Waiting for modals to close...")
            for _ in range(30):
                count = page.locator("button[debug-id='create-button']").count()
                if count == 0:
                    break
                page.wait_for_timeout(500)
            else:
                raise Exception("Modal did not close in time")
            page.wait_for_timeout(2000)

            # Final Save
            print("[Steel] Waiting for Save button to become enabled...")
            final_save = page.locator("button[debug-id='main-button']")
            final_save.wait_for(state="visible", timeout=10000)

            for _ in range(20):
                is_disabled = final_save.get_attribute("disabled")
                if is_disabled is None:
                    break
                page.wait_for_timeout(500)
            else:
                raise Exception("Save button never became enabled")

            print("[Steel] Clicking final Save...")
            final_save.scroll_into_view_if_needed()
            final_save.click(force=True)

            page.wait_for_timeout(2000)
            print("[Steel] All done!")
            browser.close()

    except Exception:
        # Always release the session, even on failure
        client.sessions.release(session.id)
        print("[Steel] Session released (after error)")
        raise  # re-raise so the retry wrapper can catch it

    client.sessions.release(session.id)
    print("[Steel] Session released")
    return {"success": True, "email": email}


def add_tester(email: str) -> dict:
    """
    Calls _attempt_add_tester with exponential backoff retry.
    Retries on ANY exception except hard validation errors.
    Max attempts: MAX_ATTEMPTS. Never raises — returns error dict on total failure.
    """
    # Hard-fail immediately for bad input — no point retrying
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")
    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n[Retry] Attempt {attempt}/{MAX_ATTEMPTS} for {email}")
        try:
            result = _attempt_add_tester(email)
            print(f"[Retry] ✅ Success on attempt {attempt}")
            return result

        except Exception as e:
            last_error = e
            print(f"[Retry] ❌ Attempt {attempt} failed: {e}")

            if attempt < MAX_ATTEMPTS:
                delay = min(BASE_DELAY_S * (2 ** (attempt - 1)), MAX_DELAY_S)
                print(f"[Retry] Waiting {delay}s before next attempt...")
                time.sleep(delay)

    # All attempts exhausted
    print(f"[Retry] 💀 All {MAX_ATTEMPTS} attempts failed for {email}. Last error: {last_error}")
    raise Exception(
        f"add_tester failed after {MAX_ATTEMPTS} attempts for {email}. "
        f"Last error: {last_error}"
    )
