"""End-to-end check for Settings → Data export click path.

Verifies two flows:
1. Admin: clicking "Export JSON" issues a request to `/api/export` and does not render the export error banner.
2. Reader: export button is disabled and clicking it does not trigger an export request.

Run directly:
    python tests/e2e/test_export_clickpath.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error

from playwright.sync_api import Page, sync_playwright

BASE = os.getenv("HT_E2E_BASE_URL", "http://localhost:8080")
ADMIN_EMAIL = os.getenv("HT_E2E_ADMIN_EMAIL", "admin@hometower.local")
ADMIN_PASSWORD = os.getenv("HT_E2E_ADMIN_PASSWORD", "changeme_on_first_boot")


def fetch_access_token() -> str:
    payload = json.dumps({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        body = response.read().decode("utf-8")
    token = json.loads(body).get("access_token", "")
    if not token:
        raise AssertionError("API login did not return an access token")
    return str(token)


def create_user(admin_token: str, username: str, email: str, password: str, role: str = "Reader") -> None:
    payload = json.dumps({"username": username, "email": email, "password": password, "role": role}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/users/",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as response:
            if response.status not in (200, 201):
                raise AssertionError(f"User creation returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        # Surface body for debug
        body = exc.read().decode("utf-8") if exc.fp is not None else ""
        raise AssertionError(f"User creation failed {exc.code}: {body}") from exc


def login(page: Page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_timeout(1000)

    email_input = page.locator('input[type="text"], input[type="email"]').first
    password_input = page.locator('input[type="password"]').first
    login_button = page.locator(
        'button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")'
    ).first

    if email_input.count() == 0 or password_input.count() == 0 or login_button.count() == 0:
        raise AssertionError("Login form controls were not found")

    email_input.fill(email)
    password_input.fill(password)
    login_button.click()
    page.wait_for_timeout(2000)

    if "/login" in page.url:
        raise AssertionError("Login did not complete successfully")


def run_regression() -> None:
    admin_token = fetch_access_token()

    reader_suffix = uuid.uuid4().hex[:8]
    reader_email = f"reader-{reader_suffix}@test.local"
    reader_password = f"ReaderPass-{reader_suffix}"
    reader_username = f"reader-{reader_suffix}"

    # Create a Reader user via API so we can validate role gating in the browser
    create_user(admin_token, reader_username, reader_email, reader_password, role="Reader")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # --- Admin flow: export should trigger /api/export and NOT show error banner ---
        login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
        page.goto(f"{BASE}/settings/data", wait_until="networkidle")
        page.wait_for_timeout(1500)

        export_requests: list[str] = []

        def _capture_request(req: object) -> None:
            req_url = str(getattr(req, "url", ""))
            req_type = str(getattr(req, "resource_type", ""))
            if "/api/export" in req_url:
                export_requests.append(req_url)

        page.on("request", _capture_request)

        export_button = page.locator('button:has-text("Export JSON")').first
        if export_button.count() == 0:
            raise AssertionError("Export button not found on /settings/data for Admin")

        export_button.click()
        page.wait_for_timeout(2000)

        # If the server failed to create the export, the page may render the export error banner
        err_count = page.locator('#ht-export-error').count()
        if err_count > 0:
            text = page.locator('#ht-export-error').first.inner_text()
            raise AssertionError(f"Admin export produced an error banner: {text}")

        if not any('/api/export' in u for u in export_requests):
            raise AssertionError("Admin Export click did not issue a request to /api/export")

        # --- Reader flow: export button must be disabled and must NOT issue the export request ---
        # Log out by navigating to /logout if available, otherwise open login and re-login
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(500)

        # Login as Reader
        login(page, reader_email, reader_password)
        page.goto(f"{BASE}/settings/data", wait_until="networkidle")
        page.wait_for_timeout(1500)

        reader_export_button = page.locator('button:has-text("Export JSON")').first
        if reader_export_button.count() == 0:
            raise AssertionError("Export button not found on /settings/data for Reader")

        # Element disabled property check
        is_disabled = reader_export_button.evaluate("el => el.disabled === true")
        if not is_disabled:
            # Try clicking and ensure no network request is made
            export_requests.clear()
            reader_export_button.click()
            page.wait_for_timeout(1500)
            if any('/api/export' in u for u in export_requests):
                raise AssertionError("Reader was able to trigger /api/export")
            raise AssertionError("Reader export button is not disabled in the UI")

        browser.close()


def test_export_clickpath_regression() -> None:
    """Pytest-collected wrapper to run the export click-path regression.

    This keeps the existing script runnable directly while making the proof
    enforceable by the verify-gate's pytest runs.
    """
    run_regression()


if __name__ == "__main__":
    try:
        run_regression()
        print("PASS: Settings Data export click path verified (Admin export triggers request; Reader gated)")
        sys.exit(0)
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
