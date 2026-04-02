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
    print(f"[Steel] Loaded {len(cleaned_cookies)} cookies")

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

            print("[Steel] Navigating to testers page...")
            page.goto(TESTERS_URL, wait_until="networkidle")
            page.wait_for_timeout(3000)

            current_url = page.url
            print(f"[Steel] Current URL: {current_url}")

            if "accounts.google.com" in current_url or "signin" in current_url.lower():
                raise Exception(f"Session expired — redirected to: {current_url}")
            if "play.google.com/console" not in current_url:
                raise Exception(f"Unexpected redirect to: {current_url}")

            # Click Create email list
            print("[Steel] Waiting for 'Create email list' button...")
            page.wait_for_selector("button:has-text('Create email list')", state="visible", timeout=15000)
            page.locator("button:has-text('Create email list')").first.click()

            # Wait for modal Save changes button to appear
            print("[Steel] Waiting for modal...")
            page.wait_for_selector("button:has-text('Save changes')", state="visible", timeout=15000)
            page.wait_for_timeout(1500)

            # Debug — print all visible inputs in modal
            inputs = page.locator("input:visible").all()
            print(f"[Steel] Visible inputs in modal: {len(inputs)}")
            for i, inp in enumerate(inputs):
                try:
                    t = inp.get_attribute("type")
                    p2 = inp.get_attribute("placeholder")
                    print(f"  Input {i}: type={t} placeholder={p2}")
                except:
                    pass

            # Fill list name — type slowly to trigger Angular change detection
            list_name = "Beta Testers"
            print(f"[Steel] Filling list name: '{list_name}'")
            name_input = page.locator("input:visible").first
            name_input.click()
            name_input.fill("")
            page.keyboard.type(list_name, delay=50)
            page.wait_for_timeout(500)

            # Fill email
            print(f"[Steel] Filling email: {email}")
            # Try to find email input — if not found fall back to second visible input
            email_inputs = page.locator("input[type='email']:visible").all()
            if email_inputs:
                email_input = email_inputs[0]
            else:
                email_input = page.locator("input:visible").nth(1)
            email_input.click()
            email_input.fill("")
            page.keyboard.type(email, delay=50)
            page.wait_for_timeout(500)

            # Press Enter to confirm the email tag
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Wait for Save changes to become enabled
            print("[Steel] Waiting for Save changes to become enabled...")
            page.wait_for_function(
                "() => !document.querySelector('button[debug-id=\"create-button\"]')?.disabled",
                timeout=10000
            )

            print("[Steel] Clicking Save changes...")
            page.locator("button[debug-id='create-button']").click()

            # Wait for modal to close
            print("[Steel] Waiting for modal to close...")
            page.wait_for_selector("button:has-text('Save changes')", state="hidden", timeout=15000)
            page.wait_for_timeout(1500)

            # Check checkbox for this email list
            print(f"[Steel] Looking for checkbox row matching: Beta Testers")
            checkbox = page.locator("tr:has-text('Beta Testers') input[type='checkbox']")
            checkbox.wait_for(state="visible", timeout=10000)
            checkbox.click()
            page.wait_for_timeout(1000)

            # Save on main page
            print("[Steel] Clicking main page Save...")
            page.locator("button:has-text('Save')").first.click()

            try:
                page.wait_for_selector("mat-snack-bar-container", state="visible", timeout=8000)
                print("[Steel] Save confirmed via snackbar.")
            except Exception:
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
