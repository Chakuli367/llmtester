import os
import json
from steel import Steel
from playwright.sync_api import sync_playwright

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/4699824931279130112?tab=testers"
SESSION_JSON = os.environ.get("PLAY_CONSOLE_SESSION")
STEEL_API_KEY = os.environ.get("STEEL_API_KEY")


def add_tester(email: str) -> dict:
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

            # Wait for modal — scoped to the dialog that has a close button
            print("[Steel] Waiting for modal...")
            page.wait_for_selector("[role='dialog'] button.close, [role='dialog'] [debug-id='cancel-button'], [role='dialog'] input", state="visible", timeout=15000)
            page.wait_for_timeout(1000)

            # Fill list name using Playwright native fill (triggers Angular properly)
            list_name = "Beta Testers"
            print(f"[Steel] Filling list name: '{list_name}'")
            name_input = page.locator("[role='dialog'] input").first
            name_input.click()
            name_input.fill(list_name)
            page.wait_for_timeout(500)

            # Fill email
            print(f"[Steel] Filling email: {email}")
            # Try email type first, fall back to second input
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

            # Log button state for debugging
            btn_disabled = page.evaluate("""
                () => {
                    const btn = document.querySelector("button[debug-id='create-button']");
                    return btn ? btn.disabled : 'not found';
                }
            """)
            print(f"[Steel] create-button disabled: {btn_disabled}")

            # Click Save changes with force regardless
            print("[Steel] Clicking 'Save changes'...")
            page.locator("button[debug-id='create-button']").click(force=True)
            page.wait_for_timeout(3000)

            # Check checkbox for the new list
            print("[Steel] Checking checkbox for 'Beta Testers'...")
            checkbox = page.locator("tr:has-text('Beta Testers') input[type='checkbox']")
            checkbox.wait_for(state="visible", timeout=10000)
            checkbox.evaluate("el => el.click()")
            page.wait_for_timeout(1000)

            # Save main page
            print("[Steel] Clicking main Save...")
            main_save_btn = page.locator("button:has-text('Save')").first
            main_save_btn.wait_for(state="visible", timeout=5000)
            main_save_btn.click(force=True)

            try:
                page.wait_for_selector("mat-snack-bar-container", state="visible", timeout=8000)
                print("[Steel] Save confirmed via snackbar!")
            except Exception:
                print("[Steel] No snackbar, assuming save succeeded.")

            page.wait_for_timeout(2000)
            print("[Steel] All done!")
            browser.close()

    except Exception as e:
        print(f"[Steel] ERROR: {e}")
        raise

    finally:
        client.sessions.release(session.id)
        print("[Steel] Session released")

    return {"success": True, "email": email}
