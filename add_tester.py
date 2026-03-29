"""
Playwright script to add a tester email to Play Console internal testing.
Called by Flask endpoint — do not run directly.
"""

import os
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/internal-testing?tab=testers"
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

        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.add_cookies(session["cookies"])
        page = context.new_page()

        print(f"[Playwright] Navigating to testers page...")
        page.goto(TESTERS_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        if "accounts.google.com" in page.url:
            browser.close()
            raise Exception("Session expired — re-run save_session.py locally")

        print(f"[Playwright] Page loaded: {page.title()}")
        page.screenshot(path="/tmp/step1.png")

        # Click the arrow (→) button next to the "123" email list to open modal
        print("[Playwright] Opening email list modal...")
        try:
            # Click the visible arrow_right_alt button for the "123" list
            arrow = page.locator("button[aria-label='Edit email list 123']").filter(has_text="arrow_right_alt")
            arrow.click(timeout=10000)
            print("[Playwright] Clicked edit button")
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step2_error.png")
            raise Exception("Could not click Edit email list button")
            
        time.sleep(3)
        page.screenshot(path="/tmp/step2_modal.png")
        print("[Playwright] Modal should be open")

        # Type in the "Add email addresses" input field
        print(f"[Playwright] Typing email: {email}")
        try:
            email_input = page.locator("input[placeholder*='user@example.com'], input[placeholder*='email']").first
            email_input.wait_for(timeout=10000)
            email_input.click()
            email_input.fill(email)
            page.keyboard.press("Enter")  # press Enter to add email to list
            print("[Playwright] Email entered and Enter pressed")
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step2_error.png")
            raise Exception("Could not find email input in modal")

        time.sleep(2)
        page.screenshot(path="/tmp/step3_filled.png")

        # Click "Save changes"
        print("[Playwright] Clicking Save changes...")
        try:
            page.locator("button:has-text('Save changes')").first.click(timeout=8000)
            print("[Playwright] Saved!")
        except PlaywrightTimeout:
            page.screenshot(path="/tmp/step3_error.png")
            raise Exception("Could not find Save changes button")

        time.sleep(2)
        page.screenshot(path="/tmp/step4_done.png")
        print("[Playwright] All done!")

        browser.close()
        return {"success": True, "email": email}
