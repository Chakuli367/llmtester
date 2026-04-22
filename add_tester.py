import os
import json
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build

PACKAGE_NAME = "app.connect.mobile"
TRACK_NAME = "Alpha"

SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

MAX_ATTEMPTS = 8
BASE_DELAY_S = 2
MAX_DELAY_S = 60


def get_credentials():
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set")
    
    service_account_info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return credentials


def _create_edit(service) -> str:
    edit = service.edits().insert(
        packageName=PACKAGE_NAME,
        body={}
    ).execute()
    return edit["id"]


def _attempt_add_tester(email: str) -> dict:
    credentials = get_credentials()
    service = build("androidpublisher", "v3", credentials=credentials)

    edit_id = _create_edit(service)

    # Get current testers
    try:
        response = service.edits().testers().get(
            packageName=PACKAGE_NAME,
            editId=edit_id,
            track=TRACK_NAME
        ).execute()
        tester_emails = response.get("googleAccounts", [])
    except Exception:
        tester_emails = []

    if email in tester_emails:
        service.edits().commit(
            packageName=PACKAGE_NAME,
            editId=edit_id
        ).execute()
        return {"success": True, "email": email, "note": "Already a tester"}

    tester_emails.append(email)

    # Update testers
    service.edits().testers().update(
        packageName=PACKAGE_NAME,
        editId=edit_id,
        track=TRACK_NAME,
        body={
            "googleAccounts": tester_emails
        }
    ).execute()

    # Commit the edit
    service.edits().commit(
        packageName=PACKAGE_NAME,
        editId=edit_id
    ).execute()

    return {"success": True, "email": email}


def add_tester(email: str) -> dict:
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError(f"Invalid email address: {email}")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n[Retry] Attempt {attempt}/{MAX_ATTEMPTS}")

        try:
            return _attempt_add_tester(email)

        except Exception as e:
            last_error = e
            print(f"[Retry] Failed: {e}")

            if attempt < MAX_ATTEMPTS:
                delay = min(BASE_DELAY_S * (2 ** (attempt - 1)), MAX_DELAY_S)
                print(f"[Retry] Waiting {delay}s...")
                time.sleep(delay)

    raise Exception(f"Failed after {MAX_ATTEMPTS} attempts: {last_error}")
