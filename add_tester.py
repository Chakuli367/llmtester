"""
Steel-only script to add a tester email to Play Console closed testing.
No Playwright — uses Steel SDK + requests directly.
"""

import os
import json
import time
import requests

TESTERS_URL = "https://play.google.com/console/u/0/developers/8552461033442694717/app/4975749607400132591/tracks/4699824931279130112?tab=testers"
SESSION_JSON = os.environ.get("PLAY_CONSOLE_SESSION")
STEEL_API_KEY = os.environ.get("STEEL_API_KEY")

STEEL_BASE = "https://api.steel.dev/v1"
HEADERS = {"Steel-Api-Key": STEEL_API_KEY}


def steel_post(path, body={}):
    r = requests.post(f"{STEEL_BASE}{path}", headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()

def steel_get(path):
    r = requests.get(f"{STEEL_BASE}{path}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def add_tester(email: str) -> dict:
    if not SESSION_JSON:
        raise ValueError("PLAY_CONSOLE_SESSION env var not set")
    if not STEEL_API_KEY:
        raise ValueError("STEEL_API_KEY env var not set")

    session_data = json.loads(SESSION_JSON)

    # Create Steel session
    print("[Steel] Creating session...")
    sess = steel_post("/sessions")
    session_id = sess["id"]
    print(f"[Steel] Session created: {session_id}")

    try:
        # Load cookies into Steel session
        print("[Steel] Loading cookies...")
        steel_post(f"/sessions/{session_id}/cookies", {"cookies": session_data["cookies"]})

        # Navigate to testers page
        print("[Steel] Navigating to testers page...")
        steel_post(f"/sessions/{session_id}/navigate", {"url": TESTERS_URL})
        time.sleep(5)

        # Check current URL (session expired check)
        current = steel_get(f"/sessions/{session_id}")
        if "accounts.google.com" in current.get("currentUrl", ""):
            raise Exception("Session expired — re-run save_session.py locally")

        # Click "Create email list"
        print("[Steel] Clicking Create email list...")
        steel_post(f"/sessions/{session_id}/click", {
            "selector": "button[aria-label='Create email list'], button:has-text('Create email list')"
        })
        time.sleep(3)

        # Fill list name
        print(f"[Steel] Filling list name: {email}")
        steel_post(f"/sessions/{session_id}/type", {
            "selector": "input[type='text']",
            "text": email
        })
        time.sleep(1)

        # Fill email address
        print(f"[Steel] Filling email: {email}")
        steel_post(f"/sessions/{session_id}/type", {
            "selector": "input[type='email']",
            "text": email
        })
        steel_post(f"/sessions/{session_id}/key", {"key": "Enter"})
        time.sleep(2)

        # Click Save changes on modal
        print("[Steel] Clicking Save changes...")
        steel_post(f"/sessions/{session_id}/click", {
            "selector": "button:has-text('Save changes')"
        })
        time.sleep(4)

        # Check checkbox for the new list
        print(f"[Steel] Checking checkbox for: {email}")
        steel_post(f"/sessions/{session_id}/click", {
            "selector": f"tr:has-text('{email}') input[type='checkbox']"
        })
        time.sleep(2)

        # Click Save on main page
        print("[Steel] Clicking Save on main page...")
        steel_post(f"/sessions/{session_id}/click", {
            "selector": "button:has-text('Save')"
        })
        time.sleep(3)

        print("[Steel] All done!")

    finally:
        steel_post(f"/sessions/{session_id}/release")
        print("[Steel] Session released")

    return {"success": True, "email": email}
    
