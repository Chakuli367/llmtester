"""
Playwright script to add a tester email to Play Console internal testing.
Called by Flask endpoint — do not run directly.
"""

import os
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Exact Play Console testers URL
TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/internal-testing?tab=testers"

# Session JSON stored as env var
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

        context = browser.new_context()

        # Restore cookies
        context.add_cookies(session["cookies"])

        page = context.new_page()

        print(f"[Playwright] Navigating to testers page...")
        page.goto(TESTERS_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)  # let the page settle

        # Check if still logged in
        if "accounts.google.com" in page.url:
            browser.close()
            raise Exception("Session expired — re-run save_session.py locally")

        print(f"[Playwright] Page loaded: {page.url}")
        print(f"[Playwright] Page title: {page.title()}")

        # Take screenshot to see what we're working with
        page.screenshot(path="/tmp/before_action.png")
        print(f"[Playwright] Screenshot saved")

        # Try to find and click "Add email addresses" or similar button
        try:
            page.locator("button:has-text('Add email addresses')").first.click(timeout=10000)
            print("[Playwright] Clicked 'Add email addresses'")
            time.sleep(1)
        except PlaywrightTimeout:
            try:
                page.locator("button:has-text('Add testers')").first.click(timeout=5000)
                print("[Playwright] Clicked 'Add testers'")
                time.sleep(1)
            except PlaywrightTimeout:
                print("[Playwright] No add button found, looking for direct textarea...")

        # Now find the textarea/input for emails
        try:
            textarea = page.locator("textarea").first
            textarea.wait_for(timeout=10000)
            textarea.click()
            textarea.fill(email)
            print(f"[Playwright] Filled email: {email}")
        except PlaywrightTimeout:
            try:
                input_field = page.locator('input[type="email"]').first
                input_field.wait_for(timeout=5000)
                input_field.fill(email)
                print(f"[Playwright] Filled email input: {email}")
            except PlaywrightTimeout:
                page.screenshot(path="/tmp/error_state.png")
                raise Exception("Could not find email input field — check screenshot")

        time.sleep(1)

        # Click Save/Add button
        try:
            save_btn = page.locator("button:has-text('Save changes')").first
            save_btn.wait_for(timeout=5000)
            save_btn.click()
            print("[Playwright] Clicked Save changes")
        except PlaywrightTimeout:
            try:
                page.locator("button:has-text('Add')").last.click(timeout=5000)
                print("[Playwright] Clicked Add")
            except PlaywrightTimeout:
                print("[Playwright] No save button found")

        time.sleep(2)
        page.screenshot(path="/tmp/after_action.png")
        print("[Playwright] Done")

        browser.close()

        return {"success": True, "email": email}
