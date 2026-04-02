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
    session = client.sessions.create(session_context={
        "cookies": cleaned_cookies,
        "localStorage": local_storage
    })
    print(f"[Steel] Session created: {session.id}")
    print(f"[Steel] 👉 WATCH LIVE: https://app.steel.dev/sessions/{session.id}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                f"wss://connect.steel.dev?apiKey={STEEL_API_KEY}&sessionId={session.id}"
            )
            context = browser.contexts[0]
            page = context.pages[0]

            print("[Steel] Navigating...")
            page.goto(TESTERS_URL, wait_until="networkidle")
            page.wait_for_timeout(4000)

            print(f"[Steel] URL: {page.url}")
            print(f"[Steel] Title: {page.title()}")

            # Dump ALL buttons on page with full detail
            all_buttons = page.evaluate("""
                () => [...document.querySelectorAll('button')].map((b, i) => ({
                    index: i,
                    text: b.innerText.trim().replace(/\\n/g, ' ').substring(0, 80),
                    disabled: b.disabled,
                    visible: b.offsetParent !== null,
                    debugId: b.getAttribute('debug-id'),
                    classes: b.className.substring(0, 60)
                }))
            """)
            print(f"[Steel] Total buttons: {len(all_buttons)}")
            for b in all_buttons:
                print(f"  [{b['index']}] text='{b['text']}' visible={b['visible']} disabled={b['disabled']} debug-id={b['debugId']}")

            # Also dump page URL and any tab info
            tabs_info = page.evaluate("""
                () => [...document.querySelectorAll('[role="tab"]')].map(t => ({
                    text: t.innerText.trim(),
                    selected: t.getAttribute('aria-selected')
                }))
            """)
            print(f"[Steel] Tabs: {tabs_info}")

            raise Exception("DEBUG STOP — check button list above")

    finally:
        client.sessions.release(session.id)
        print("[Steel] Session released")

    return {"success": True, "email": email}
