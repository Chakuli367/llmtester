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

            # Wait for testers table to load
            print("[Steel] Waiting for testers table...")
            page.wait_for_selector(
                "tr:has(input[type='checkbox']), mat-checkbox, [role='checkbox']",
                state="visible", timeout=15000
            )
            page.wait_for_timeout(1000)

            # Find ANY Details button on the page and click it
            print("[Steel] Looking for any Details button on the page...")
            all_details_btns = page.locator("button:has-text('Details'), a:has-text('Details'), button.text-button:has-text('Details')")
            count = all_details_btns.count()
            print(f"[Steel] Found {count} Details button(s)")

            if count == 0:
                raise Exception("No Details buttons found on the testers page")

            clicked = False
            for i in range(count):
                btn = all_details_btns.nth(i)
                try:
                    btn.scroll_into_view_if_needed()
                    page.wait_for_timeout(300)
                    btn.click(force=True)
                    print(f"[Steel] Clicked Details button #{i}")
                    clicked = True
                    break
                except Exception as e:
                    print(f"[Steel] Could not click Details button #{i}: {e}")
                    continue

            if not clicked:
                raise Exception("Could not click any Details button")

            page.wait_for_timeout(3000)

            # Wait for the list edit page to load
            print("[Steel] Waiting for email input...")
            page.wait_for_selector(
                "input[type='email'], input[placeholder*='email'], input[placeholder*='Email']",
                state="visible", timeout=15000
            )
            page.wait_for_timeout(1000)

            # Fill email
            print(f"[Steel] Adding email: {email}")
            email_input = page.locator(
                "input[type='email'], input[placeholder*='email'], input[placeholder*='Email']"
            ).first
            email_input.click()
            email_input.fill(email)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Check for red error (duplicate/invalid email)
            error_count = page.locator(".error, [class*='error'], mat-error").count()
            if error_count > 0:
                raise Exception(f"Email rejected by Play Console (duplicate or invalid): {email}")

            # Click Save changes inside the list editor
            print("[Steel] Saving list...")
            save_list_btn = page.locator(
                "button[debug-id='save-button'], button:has-text('Save changes')"
            ).first
            save_list_btn.scroll_into_view_if_needed()
            save_list_btn.wait_for(state="visible", timeout=10000)
            save_list_btn.click(force=True)
            page.wait_for_timeout(2000)

            # Go back to testers page
            print("[Steel] Going back to testers page...")
            page.go_back()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # Wait for testers table to reload
            print("[Steel] Waiting for testers table to reload...")
            page.wait_for_selector(
                "tr:has(input[type='checkbox']), mat-checkbox, [role='checkbox']",
                state="visible", timeout=15000
            )
            page.wait_for_timeout(2000)

            # Log checkbox rows
            row_texts = page.locator("tr:has(input[type='checkbox'])").all_text_contents()
            print(f"[Steel] Row texts: {row_texts}")

            # Find and check any unchecked checkbox (or confirm first one is checked)
            print("[Steel] Looking for checkboxes...")
            checkboxes = page.locator("tr:has(input[type='checkbox']) input[type='checkbox']")
            checkbox_count = checkboxes.count()
            print(f"[Steel] Found {checkbox_count} checkbox(es)")

            checked_any = False
            for i in range(checkbox_count):
                cb = checkboxes.nth(i)
                try:
                    is_checked = cb.is_checked()
                    print(f"[Steel] Checkbox #{i} checked: {is_checked}")
                    if not is_checked:
                        cb.click()
                        page.wait_for_timeout(500)
                        print(f"[Steel] Checked checkbox #{i}")
                        checked_any = True
                        break
                    else:
                        print(f"[Steel] Checkbox #{i} already ticked, using this list.")
                        checked_any = True
                        break
                except Exception as e:
                    print(f"[Steel] Could not interact with checkbox #{i}: {e}")
                    continue

            if not checked_any:
                print("[Steel] Warning: could not find/check any checkbox, proceeding anyway...")

            # Click final Save button (bottom right sticky bar)
            print("[Steel] Clicking final Save...")
            page.wait_for_timeout(2000)

            final_save = page.locator(
                "div.footer button:has-text('Save'), "
                "[class*='footer'] button:has-text('Save'), "
                "button[debug-id='save-button']"
            )
            if final_save.count() == 0:
                print("[Steel] Footer selector not found, falling back to last Save button...")
                final_save = page.locator("button:has-text('Save')").last

            final_save.scroll_into_view_if_needed()
            final_save.wait_for(state="visible", timeout=10000)
            final_save.click(force=True)

            try:
                page.wait_for_selector("mat-snack-bar-container", state="visible", timeout=8000)
                print("[Steel] Final save confirmed via snackbar!")
            except Exception:
                print("[Steel] No snackbar, assuming final save succeeded.")

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
