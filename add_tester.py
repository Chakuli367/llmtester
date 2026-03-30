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

        # DEBUG — print all inputs after modal opens
        time.sleep(3)
        inputs = page.locator("input").all()
        for inp in inputs:
            print(f"[Input] type={inp.get_attribute('type')} placeholder={inp.get_attribute('placeholder')} id={inp.get_attribute('id')}")
        raise Exception("DEBUG STOP")
