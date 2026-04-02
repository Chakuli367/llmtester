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

            # JS-click the Create email list button to bypass overlay issues
            print("[Steel] Clicking 'Create email list' via JavaScript...")
            page.wait_for_selector("button:has-text('Create email list')", state="visible", timeout=15000)
            page.evaluate("""
                () => {
                    const btns = [...document.querySelectorAll('button')];
                    const btn = btns.find(b => b.innerText.includes('Create email list'));
                    if (btn) btn.click();
                    else throw new Error('Create email list button not found');
                }
            """)
            page.wait_for_timeout(2000)

            # Wait for modal
            print("[Steel] Waiting for modal (mat-dialog-container)...")
            page.wait_for_selector("mat-dialog-container", state="visible", timeout=15000)
            print("[Steel] Modal opened!")
            page.wait_for_timeout(1000)

            # Debug — what inputs are inside the modal?
            modal_inputs = page.eval_on_selector_all(
                "mat-dialog-container input",
                "els => els.map(e => ({type: e.type, placeholder: e.placeholder, visible: e.offsetParent !== null}))"
            )
            print(f"[Steel] Inputs in modal: {modal_inputs}")

            # Fill list name using JS directly on the Angular input
            list_name = "Beta Testers"
            print(f"[Steel] Filling list name: '{list_name}'")
            page.evaluate(f"""
                () => {{
                    const modal = document.querySelector('mat-dialog-container');
                    const input = modal.querySelector('input[type="text"]');
                    if (!input) throw new Error('List name input not found');
                    input.focus();
                    input.value = '{list_name}';
                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)
            page.wait_for_timeout(500)

            # Fill email using JS
            print(f"[Steel] Filling email: {email}")
            page.evaluate(f"""
                () => {{
                    const modal = document.querySelector('mat-dialog-container');
                    const input = modal.querySelector('input[type="email"]') 
                                  || modal.querySelectorAll('input')[1];
                    if (!input) throw new Error('Email input not found');
                    input.focus();
                    input.value = '{email}';
                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)
            page.wait_for_timeout(500)

            # Press Enter to confirm email tag
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Wait for Save changes to be enabled then JS-click it
            print("[Steel] Waiting for Save changes button to enable...")
            page.wait_for_function(
                "() => { const btn = document.querySelector('mat-dialog-container button[debug-id=\"create-button\"]'); return btn && !btn.disabled; }",
                timeout=10000
            )
            print("[Steel] Clicking Save changes...")
            page.evaluate("""
                () => {
                    const modal = document.querySelector('mat-dialog-container');
                    const btn = modal.querySelector('button[debug-id="create-button"]')
                                || [...modal.querySelectorAll('button')].find(b => b.innerText.includes('Save changes'));
                    if (!btn) throw new Error('Save changes button not found');
                    btn.click();
                }
            """)

            # Wait for modal to close
            print("[Steel] Waiting for modal to close...")
            page.wait_for_selector("mat-dialog-container", state="hidden", timeout=15000)
            page.wait_for_timeout(1500)

            # Check checkbox for the new list
            print(f"[Steel] Looking for checkbox row matching: Beta Testers")
            checkbox = page.locator("tr:has-text('Beta Testers') input[type='checkbox']")
            checkbox.wait_for(state="visible", timeout=10000)
            checkbox.evaluate("el => el.click()")
            page.wait_for_timeout(1000)

            # Save main page
            print("[Steel] Clicking main page Save...")
            page.evaluate("""
                () => {
                    const btns = [...document.querySelectorAll('button')];
                    const btn = btns.find(b => b.innerText.trim() === 'Save' && !b.disabled);
                    if (btn) btn.click();
                    else throw new Error('Save button not found');
                }
            """)

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
