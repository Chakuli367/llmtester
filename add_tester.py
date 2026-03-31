"""
Playwright script to add a tester email to Play Console closed testing.
Creates a new email list for each tester, checks it, and saves.
Called by Flask endpoint — do not run directly.
"""

import os
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/4699824931279130112?tab=testers"
SESSION_JSON = os.environ.get("PLAY_CONSOLE_SESSION")


def add_tester(email: str) -> dict:
    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")

    session = json.loads(SESSION_JSON)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        context.add_cookies(session["cookies"])
        page = context.new_page()

        # Step 1 — Navigate
        print("[Playwright] Navigating to testers page...")
        page.goto(TESTERS_URL, wait_until="networkidle", timeout=60000)
        time.sleep(4)

        if "accounts.google.com" in page.url:
            browser.close()
            raise Exception("Session expired — re-run save_session.py locally")

        print(f"[Playwright] Page loaded: {page.title()}")
        page.screenshot(path="/tmp/step1.png")

        # Step 2 — Click "Create email list"
        print("[Playwright] Clicking Create email list...")
        try:
            create_btn = page.get_by_role("button", name="Create email list").first
            create_btn.wait_for(state="visible", timeout=15000)
            create_btn.click()
            print("[Playwright] Clicked Create email list")
            time.sleep(3)
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step2_error.png")
            raise Exception("Could not find Create email list button")

        page.screenshot(path="/tmp/step2_modal.png")

        # Step 3 — Fill list name (use email as list name)
        print(f"[Playwright] Filling list name: {email}")
        try:
            time.sleep(3)
            # Try nth(0) first (hidden list name field), force interact
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
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step3_error.png")
            raise Exception("Could not find list name input")

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
            page.screenshot(path="/tmp/step4_error.png")
            raise Exception("Could not find email input")

        page.screenshot(path="/tmp/step4_filled.png")

        # Step 5 — Click "Save changes" on modal
        print("[Playwright] Clicking Save changes on modal...")
        try:
            time.sleep(2)
            buttons = page.locator("button").all()
            for btn in buttons:
                print(f"[Button] text={repr(btn.inner_text())} visible={btn.is_visible()}")

            # Try multiple ways to find and click Save changes
            saved = False
            attempts = [
                lambda: page.get_by_role("button", name="Save changes").first,
                lambda: page.get_by_role("button", name="Save changes").last,
                lambda: page.locator("button:has-text('Save changes')").first,
                lambda: page.locator("button:has-text('Save changes')").last,
                lambda: page.locator("button:has-text('Save')").last,
            ]

            for attempt in attempts:
                try:
                    btn = attempt()
                    if btn.is_visible():
                        btn.click()
                        print("[Playwright] Modal saved")
                        saved = True
                        break
                    else:
                        btn.click(force=True)
                        print("[Playwright] Modal saved (force)")
                        saved = True
                        break
                except Exception:
                    continue

            if not saved:
                page.screenshot(path="/tmp/step5_error.png")
                raise Exception("Could not find Save changes button on modal")

        time.sleep(4)
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step5_error.png")
            raise Exception("Could not find Save changes button on modal")

        page.screenshot(path="/tmp/step5_after_save.png")

        # Step 6 — Check the checkbox next to the new list
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
            page.screenshot(path="/tmp/step6_error.png")
            raise Exception("Could not find checkbox for new list")

        page.screenshot(path="/tmp/step6_checked.png")

        # Step 7 — Click "Save" on main page
        print("[Playwright] Clicking Save on main page...")
        try:
            save_main_btn = page.get_by_role("button", name="Save").last
            save_main_btn.wait_for(state="visible", timeout=10000)
            save_main_btn.click()
            print("[Playwright] Main page saved!")
            time.sleep(3)
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step7_error.png")
            raise Exception("Could not find Save button on main page")

        page.screenshot(path="/tmp/step7_done.png")
        print("[Playwright] All done!")

        browser.close()
        return {"success": True, "email": email}
