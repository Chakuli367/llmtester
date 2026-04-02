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

            # Click by debug-id
            print("[Steel] Clicking 'Create email list'...")
            page.wait_for_selector("button[debug-id='create-list-button']", state="visible", timeout=15000)
            page.evaluate("document.querySelector(\"button[debug-id='create-list-button']\").click()")
            page.wait_for_timeout(2000)

            # Wait for modal
            print("[Steel] Waiting for modal...")
            page.wait_for_selector("mat-dialog-container", state="visible", timeout=15000)
            print("[Steel] Modal opened!")
            page.wait_for_timeout(1000)

            # Debug inputs inside modal
            modal_inputs = page.evaluate("""
                () => [...document.querySelectorAll('mat-dialog-container input')].map(e => ({
                    type: e.type,
                    placeholder: e.placeholder,
                    visible: e.offsetParent !== null,
                    name: e.name
                }))
            """)
            print(f"[Steel] Modal inputs: {modal_inputs}")

            # Fill list name via JS to trigger Angular
            list_name = "Beta Testers"
            print(f"[Steel] Filling list name: '{list_name}'")
            page.evaluate(f"""
                () => {{
                    const modal = document.querySelector('mat-dialog-container');
                    const input = [...modal.querySelectorAll('input')].find(i => i.offsetParent !== null && i.type !== 'radio' && i.type !== 'checkbox');
                    if (!input) throw new Error('No visible text input found in modal');
                    input.focus();
                    input.value = '{list_name}';
                    input.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: '{list_name}'}}));
                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)
            page.wait_for_timeout(500)

            # Fill email via JS
            print(f"[Steel] Filling email: {email}")
            page.evaluate(f"""
                () => {{
                    const modal = document.querySelector('mat-dialog-container');
                    const inputs = [...modal.querySelectorAll('input')].filter(i => i.offsetParent !== null && i.type !== 'radio' && i.type !== 'checkbox');
                    const input = inputs.find(i => i.type === 'email') || inputs[1];
                    if (!input) throw new Error('No email input found in modal');
                    input.focus();
                    input.value = '{email}';
                    input.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: '{email}'}}));
                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Wait for Save changes button to become enabled
            print("[Steel] Waiting for Save changes to enable...")
            page.wait_for_function(
                "() => { const btn = document.querySelector('mat-dialog-container button[debug-id=\"create-button\"]'); return btn && !btn.disabled; }",
                timeout=10000
            )
            print("[Steel] Clicking Save changes...")
            page.evaluate("document.querySelector('mat-dialog-container button[debug-id=\"create-button\"]').click()")

            # Wait for modal to close
            print("[Steel] Waiting for modal to close...")
            page.wait_for_selector("mat-dialog-container", state="hidden", timeout=15000)
            page.wait_for_timeout(1500)

            # Check checkbox for Beta Testers row
            print("[Steel] Checking checkbox for 'Beta Testers'...")
            checkbox = page.locator("tr:has-text('Beta Testers') input[type='checkbox']")
            checkbox.wait_for(state="visible", timeout=10000)
            checkbox.evaluate("el => el.click()")
            page.wait_for_timeout(1000)

            # Click main Save button
            print("[Steel] Clicking main Save...")
            page.evaluate("document.querySelector(\"button[debug-id='main-button']\").click()")

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
