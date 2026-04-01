import os
import json
import base64
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

    # Basic email validation
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")

    session_data = json.loads(SESSION_JSON)

    # Clean cookies — always remove partitionKey entirely (safest approach)
    cleaned_cookies = [
        {k: v for k, v in cookie.items() if k != "partitionKey"}
        for cookie in session_data["cookies"]
    ]
    print(f"[Steel] Loaded {len(cleaned_cookies)} cookies")

    # localStorage must be a dict, not a string
    local_storage = session_data.get("localStorage", {})
    if isinstance(local_storage, str):
        try:
            local_storage = json.loads(local_storage)
        except json.JSONDecodeError:
            local_storage = {}

    client = Steel(steel_api_key=STEEL_API_KEY)
    print("[Steel] Creating session with auth context...")
    session = client.sessions.create(session_context={
        "cookies": cleaned_cookies,
        "localStorage": local_storage
    })
    print(f"[Steel] Session created: {session.id}")

    try:
        with sync_playwright() as p:
            print("[Steel] Connecting to browser...")
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
            )
            print("[Steel] Browser connected")

            context = browser.contexts[0]
            page = context.pages[0]

            # ── Navigate ──────────────────────────────────────────────────
            print("[Steel] Navigating to testers page...")
            page.goto(TESTERS_URL, wait_until="networkidle")
            page.wait_for_timeout(2000)  # Let Angular/Material fully settle

            # ── Session / redirect checks ─────────────────────────────────
            current_url = page.url
            print(f"[Steel] Current URL after navigation: {current_url}")

            if "accounts.google.com" in current_url or "signin" in current_url.lower():
                raise Exception(
                    f"Session expired — re-run save_session.py locally. "
                    f"Redirected to: {current_url}"
                )
            if "play.google.com/console" not in current_url:
                raise Exception(f"Unexpected redirect to: {current_url}")

            print(f"[Steel] Page title: {page.title()}")

            # ── Wait for page to be interactable ──────────────────────────
            print("[Steel] Waiting for 'Create email list' button to be visible...")
            try:
                page.wait_for_selector(
                    "button:has-text('Create email list')",
                    state="visible",
                    timeout=15000
                )
            except Exception:
                _dump_debug(page, "create_btn_not_found")
                raise Exception(
                    "'Create email list' button not found — "
                    "check debug screenshot and visible buttons in logs"
                )

            # ── Click 'Create email list' ─────────────────────────────────
            print("[Steel] Clicking 'Create email list'...")
            btn = page.locator("button:has-text('Create email list')").first
            btn.scroll_into_view_if_needed()
            btn.click(force=True)

            # ── Wait for modal ────────────────────────────────────────────
            print("[Steel] Waiting for modal dialog...")
            try:
                page.wait_for_selector(
                    "mat-dialog-container",
                    state="visible",
                    timeout=15000
                )
            except Exception:
                _dump_debug(page, "modal_not_opened")
                raise Exception(
                    "Modal did not open after clicking 'Create email list'. "
                    "Check debug screenshot and visible buttons in logs."
                )

            page.wait_for_timeout(1000)  # Modal animation settle

            # ── Fill list name (text input) ───────────────────────────────
            list_name = "Beta Testers"
            print(f"[Steel] Filling list name: '{list_name}'")
            name_input = page.locator(
                "mat-dialog-container input[type='text']:visible"
            ).first
            name_input.wait_for(state="visible", timeout=5000)
            name_input.fill(list_name)
            page.wait_for_timeout(300)

            # ── Fill email address ────────────────────────────────────────
            print(f"[Steel] Filling email: {email}")
            email_input = page.locator(
                "mat-dialog-container input[type='email']:visible"
            ).first
            email_input.wait_for(state="visible", timeout=5000)
            email_input.fill(email)
            page.keyboard.press("Enter")
            page.wait_for_timeout(800)

            # ── Save changes (inside modal) ───────────────────────────────
            print("[Steel] Clicking 'Save changes' in modal...")
            save_modal_btn = page.locator(
                "mat-dialog-container button:has-text('Save changes')"
            )
            save_modal_btn.wait_for(state="visible", timeout=5000)
            save_modal_btn.click()

            # Wait for modal to close
            print("[Steel] Waiting for modal to close...")
            page.wait_for_selector(
                "mat-dialog-container",
                state="hidden",
                timeout=15000
            )
            page.wait_for_timeout(1000)

            # ── Check the checkbox for this email list ────────────────────
            print(f"[Steel] Looking for checkbox row matching: {email}")
            try:
                checkbox = page.locator(
                    f"tr:has-text('{email}') input[type='checkbox']"
                )
                checkbox.wait_for(state="visible", timeout=10000)
                checkbox.click()
            except Exception:
                _dump_debug(page, "checkbox_not_found")
                raise Exception(
                    f"Could not find checkbox row for '{email}'. "
                    "Email list may not have been created successfully."
                )

            page.wait_for_timeout(1000)

            # ── Save on main page ─────────────────────────────────────────
            print("[Steel] Clicking main page 'Save'...")
            main_save_btn = page.locator("button:has-text('Save')").first
            main_save_btn.wait_for(state="visible", timeout=5000)
            main_save_btn.click()

            # Wait for save confirmation (snackbar or button state change)
            try:
                page.wait_for_selector(
                    "mat-snack-bar-container",
                    state="visible",
                    timeout=8000
                )
                print("[Steel] Save confirmed via snackbar.")
            except Exception:
                # Snackbar is optional — not all saves show one
                print("[Steel] No snackbar detected, assuming save succeeded.")

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


def _dump_debug(page, label: str):
    """Log visible buttons and a base64 screenshot for remote debugging."""
    try:
        buttons = page.locator("button:visible").all_text_contents()
        print(f"[Debug:{label}] Current URL : {page.url}")
        print(f"[Debug:{label}] Page title  : {page.title()}")
        print(f"[Debug:{label}] Visible buttons: {buttons}")

        screenshot_b64 = base64.b64encode(page.screenshot()).decode()
        # Paste the output into https://base64.guru/converter/decode/image
        print(f"[Debug:{label}] Screenshot (base64) — paste into base64 image viewer:")
        # Print in chunks so Render doesn't truncate
        chunk_size = 500
        for i in range(0, len(screenshot_b64), chunk_size):
            print(screenshot_b64[i:i + chunk_size])
    except Exception as debug_err:
        print(f"[Debug:{label}] Could not capture debug info: {debug_err}")
