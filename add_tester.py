"""
Steel + Playwright script to add a tester email to Play Console closed testing.
"""
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

    session_data = json.loads(SESSION_JSON)

    # Clean cookies — fix partitionKey to be an object or remove it
    cleaned_cookies = []
    for cookie in session_data["cookies"]:
        if "partitionKey" in cookie:
            pk = cookie["partitionKey"]
            if not isinstance(pk, dict):
                del cookie["partitionKey"]
        cleaned_cookies.append(cookie)

    print(f"[Steel] Loaded {len(cleaned_cookies)} cookies")

    client = Steel(steel_api_key=STEEL_API_KEY)

    print("[Steel] Creating session with auth context...")
    session = client.sessions.create(session_context={
        "cookies": cleaned_cookies,
        "localStorage": session_data.get("localStorage", {})
    })
    print(f"[Steel] Session created: {session.id}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
            )

            # Fix: pages is a property, not a method
            context = browser.contexts()[0]
            page = context.pages[0]

            print("[Steel] Navigating to testers page...")
            page.goto(TESTERS_URL, wait_until="networkidle")

            # Check if session expired
            if "accounts.google.com" in page.url:
                raise Exception("Session expired — re-run save_session.py locally")

            print("[Steel] Clicking Create email list...")
            page.click("button:has-text('Create email list')")
            page.wait_for_timeout(2000)

            print(f"[Steel] Filling list name: {email}")
            page.fill("input[type='text']", email)
            page.wait_for_timeout(500)

            print(f"[Steel] Filling email: {email}")
            page.fill("input[type='email']", email)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)

            print("[Steel] Clicking Save changes...")
            page.click("button:has-text('Save changes')")
            page.wait_for_timeout(3000)

            print(f"[Steel] Checking checkbox for: {email}")
            page.click(f"tr:has-text('{email}') input[type='checkbox']")
            page.wait_for_timeout(1500)

            print("[Steel] Clicking Save on main page...")
            page.click("button:has-text('Save')")
            page.wait_for_timeout(3000)

            print("[Steel] All done!")
            browser.close()

    finally:
        client.sessions.release(session.id)
        print("[Steel] Session released")

    return {"success": True, "email": email}
