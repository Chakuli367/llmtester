"""
Playwright script to add a tester email to Play Console internal testing.
Called by Flask endpoint — do not run directly.
"""

import os
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Your Play Console package name
PACKAGE_NAME = os.environ.get("PACKAGE_NAME", "app.connect.mobile")

# Session JSON stored as env var (paste full contents of play_console_session.json)
SESSION_JSON = os.environ.get("PLAY_CONSOLE_SESSION")

# Internal testing testers URL
TESTERS_URL = (
    f"https://play.google.com/console/u/0/developers/"
    f"app/{PACKAGE_NAME}/tracks/internal-testing/testers"
)


def add_tester(email: str) -> dict:
    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")

    session = json.loads(SESSION_JSON)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        context = browser.new_context()

        # Restore cookies
        context.add_cookies(session["cookies"])

        page = context.new_page()

        print(f"[Playwright] Navigating to testers page...")
        page.goto(TESTERS_URL, wait_until="networkidle", timeout=30000)

        # Check if still logged in
        if "accounts.google.com" in page.url:
            browser.close()
            raise Exception("Session expired — re-run save_session.py locally")

        print(f"[Playwright] Looking for email input...")

        # Click the email input field / add testers area
        try:
            # Try finding the "Add email addresses" or similar input
            email_input = page.locator('input[type="email"], input[placeholder*="email" i], textarea[placeholder*="email" i]').first
            email_input.wait_for(timeout=10000)
            email_input.click()
            email_input.fill(email)
        except PlaywrightTimeout:
            # Fallback: look for an "Add testers" button first
            add_btn = page.locator('button:has-text("Add testers"), button:has-text("Add email")')
            add_btn.first.click()
            time.sleep(1)
            email_input = page.locator('input[type="email"]').first
            email_input.fill(email)

        # Press Enter or click Save
        page.keyboard.press("Enter")
        time.sleep(1)

        # Look for Save button
        try:
            save_btn = page.locator('button:has-text("Save"), button:has-text("Apply")').first
            save_btn.wait_for(timeout=5000)
            save_btn.click()
            print(f"[Playwright] Clicked Save")
        except PlaywrightTimeout:
            print(f"[Playwright] No save button found, may have auto-saved")

        # Wait for confirmation
        time.sleep(2)

        # Take screenshot for debugging
        screenshot_path = f"/tmp/screenshot_{email.replace('@','_')}.png"
        page.screenshot(path=screenshot_path)
        print(f"[Playwright] Screenshot saved: {screenshot_path}")

        browser.close()

        return {"success": True, "email": email}
