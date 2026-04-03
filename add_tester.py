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

            # Wait for modal
            print("[Steel] Waiting for modal...")
            page.wait_for_selector("[role='dialog'] input", state="visible", timeout=15000)
            page.wait_for_timeout(1000)

            # Fill list name
            list_name = "alexa Testers"
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

            # Log button state using locator instead of evaluate (avoids Trusted Types)
            create_btn = page.locator("button[debug-id='create-button']")
            is_disabled = create_btn.get_attribute("disabled")
            print(f"[Steel] create-button disabled: {is_disabled}")

            # Click Save changes
            print("[Steel] Clicking 'Save changes'...")
            create_btn.click(force=True)
            page.wait_for_timeout(2000)

            # Handle confirmation dialog "Create email list?"
            print("[Steel] Waiting for confirmation dialog...")
            page.wait_for_selector("text='Create email list?'", state="visible", timeout=10000)
            print("[Steel] Clicking 'Create' in confirmation dialog...")
            page.locator("button:has-text('Create')").last.click()

            # Wait for modal to close — poll using native locator (avoids Trusted Types CSP issue)
            print("[Steel] Waiting for modals to close...")
            for _ in range(30):  # 15 seconds max
                count = page.locator("button[debug-id='create-button']").count()
                if count == 0:
                    break
                page.wait_for_timeout(500)
            else:
                raise Exception("Modal did not close in time")
            page.wait_for_timeout(2000)

            # Wait for testers table to reload
            print("[Steel] Waiting for testers table to load...")
            page.wait_for_selector("tr:has(input[type='checkbox'])", state="visible", timeout=15000)
            page.wait_for_timeout(2000)

            # Log checkbox rows
            row_texts = page.locator("tr:has(input[type='checkbox'])").all_text_contents()
            print(f"[Steel] Row texts: {row_texts}")

            # Find and click checkbox by list name
            # Find and click checkbox by list name
            print("[Steel] Looking for checkbox...")
            checkbox = page.locator(f"tr:has-text('{list_name}') input[type='checkbox']")
            checkbox.wait_for(state="visible", timeout=15000)
            checkbox.click()
            page.wait_for_timeout(2000)  # Wait longer for button to enable

            # Click final Save button - wait for it to be ENABLED first
            print("[Steel] Waiting for Save button to become enabled...")
            final_save = page.locator("button[debug-id='main-button']")
            final_save.wait_for(state="visible", timeout=10000)

            # Wait until the disabled attribute is removed
            for _ in range(20):  # up to 10 seconds
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

    except Exception as e:
        print(f"[Steel] ERROR: {e}")
        raise

    finally:
        client.sessions.release(session.id)
        print("[Steel] Session released")

    return {"success": True, "email": email}
