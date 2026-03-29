"""
Run this ONCE locally to save your Google session.
Usage: python save_session.py

It will open a real browser window — log in manually,
complete 2FA, then press Enter in terminal. Done.
"""

import json
from playwright.sync_api import sync_playwright

def save_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible browser
        context = browser.new_context()
        page = context.new_page()

        print("Opening Play Console...")
        page.goto("https://play.google.com/console")

        print("\n👉 Log in manually in the browser window.")
        print("👉 Complete 2FA if asked.")
        print("👉 Make sure you can see the Play Console dashboard.")
        input("\n✅ Press Enter here once you're fully logged in...\n")

        # Save cookies + storage
        cookies = context.cookies()
        storage = page.evaluate("() => JSON.stringify(window.localStorage)")

        session = {
            "cookies": cookies,
            "localStorage": storage
        }

        with open("play_console_session.json", "w") as f:
            json.dump(session, f)

        print("✅ Session saved to play_console_session.json")
        print("📤 Upload this file to Render as a secret file or paste contents into env var PLAY_CONSOLE_SESSION")

        browser.close()

if __name__ == "__main__":
    save_session()