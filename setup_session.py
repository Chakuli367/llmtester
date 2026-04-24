# setup_session.py
import os
import json
from steel import Steel
from playwright.sync_api import sync_playwright

STEEL_API_KEY = os.environ.get("STEEL_API_KEY")

def setup_session():
    client = Steel(steel_api_key=STEEL_API_KEY)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("[Setup] Opening Play Console...")
        page.goto("https://play.google.com/console", wait_until="networkidle")

        print("\n👉 Log in manually in the browser window.")
        print("👉 Complete 2FA if asked.")
        print("👉 Make sure you can see the Play Console dashboard.")
        input("\n✅ Press Enter here once you're fully logged in...\n")

        if "accounts.google.com" in page.url:
            print("❌ Not logged in yet. Re-run and try again.")
            browser.close()
            return

        cookies = context.cookies()
        browser.close()
        print("✅ Login confirmed, transferring session to Steel...")

    # ✅ Clean cookies only — skip localStorage entirely
    cleaned_cookies = [
        {k: v for k, v in cookie.items() if k != "partitionKey"}
        for cookie in cookies
    ]

    session = client.sessions.create(session_context={
        "cookies": cleaned_cookies
    })

    print(f"[Steel] Session created: {session.id}")

    print(f"""
✅ Done! Save this to your server environment:

    STEEL_SESSION_ID={session.id}

⚠️  Do NOT release this session ID anywhere in your code.
⚠️  Only re-run this script if the session dies.
""")

if __name__ == "__main__":
    setup_session()
