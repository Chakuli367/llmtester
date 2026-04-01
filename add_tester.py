"""
Playwright script to add a tester email to Play Console closed testing.
Creates a new email list for each tester, checks it, and saves.
Called by Flask endpoint — do not run directly.
"""

import os
import json
import time
from steel import Steel
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/4699824931279130112?tab=testers"
SESSION_JSON = os.environ.get("PLAY_CONSOLE_SESSION")
STEEL_API_KEY = os.environ.get("STEEL_API_KEY")


def add_tester(email: str) -> dict:
    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")

    session = json.loads(SESSION_JSON)
    steel_client = steel.Steel(steel_api_key=STEEL_API_KEY)
    steel_session = steel_client.sessions.create()

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={steel_session.id}"
            )

            context = browser.contexts[0]
            context.add_cookies(session["cookies"])
            page = context.new_page()

            # Step 1 — Navigate
            print("[Playwright] Navigating to testers page...")
            page.goto(TESTERS_URL, wait_until="networkidle", timeout=60000)
            time.sleep(4)

            if "accounts.google.com" in page.url:
                raise Exception("Session expired — re-run save_session.py locally")

            print(f"[Playwright] Page loaded: {page.title()}")

            # Step 2 — Click "Create email list"
            print("[Playwright] Clicking Create email list...")
            try:
                create_btn = page.get_by_role("button", name="Create email list").first
                create_btn.wait_for(state="visible", timeout=15000)
                create_btn.click()
                print("[Playwright] Clicked Create email list")
                time.sleep(3)
            except PlaywrightTimeout:
                raise Exception("Could not find Create email list button")

            # Step 3 — Fill list name
            print(f"[Playwright] Filling list name: {email}")
            filled = False
            for i in range(5):
                try:
                    inp = page.locator("input[type='text']").nth(i)
                    inp.click(force=True)
                    inp.fill(email, force=True)
                    actual = inp.input_value()
                    if actual == email:
                        print(f"[Playwright] List name filled via input index {i}")
                        filled = True
                        break
                except Exception:
                    continue

            if not filled:
                raise Exception("None of the text inputs accepted the email value")

            time.sleep(1)

            # Step 4 — Fill email address
            print(f"[Playwright] Filling email address: {email}")
            try:
                email_input = page.locator("input[type='email']").first
                email_input.wait_for(state="visible", timeout=10000)
                email_input.click()
                email_input.fill(email)
                page.keyboard.press("Enter")
                print("[Playwright] Email entered and Enter pressed")
                time.sleep(2)
            except PlaywrightTimeout:
                raise Exception("Could not find email input")

            # Step 5 — Click "Save changes" on modal
            print("[Playwright] Clicking Save changes on modal...")
            saved = False
            buttons = page.locator("button").all()
            for btn in buttons:
                try:
                    if btn.inner_text().strip() == "Save changes" and btn.is_visible():
                        btn.click()
                        print("[Playwright] Modal saved")
                        saved = True
                        break
                except Exception:
                    continue

            if not saved:
                raise Exception("Could not find Save changes button on modal")

            time.sleep(4)

            # Step 6 — Check the checkbox
            print(f"[Playwright] Checking checkbox for list: {email}")
            try:
                checkbox = page.locator(f"tr:has-text('{email}') input[type='checkbox']").first
                checkbox.wait_for(state="visible", timeout=15000)
                if not checkbox.is_checked():
                    checkbox.click()
                    print("[Playwright] Checkbox checked")
                else:
                    print("[Playwright] Checkbox already checked")
                time.sleep(2)
            except PlaywrightTimeout:
                raise Exception("Could not find checkbox for new list")

            # Step 7 — Click "Save" on main page
            print("[Playwright] Clicking Save on main page...")
            try:
                save_main_btn = page.get_by_role("button", name="Save").last
                save_main_btn.wait_for(state="visible", timeout=10000)
                save_main_btn.click()
                print("[Playwright] Main page saved!")
                time.sleep(3)
            except PlaywrightTimeout:
                raise Exception("Could not find Save button on main page")

            print("[Playwright] All done!")
            browser.close()

    finally:
        steel_client.sessions.release(steel_session.id)
        print("[Steel] Session released")

    return {"success": True, "email": email}
