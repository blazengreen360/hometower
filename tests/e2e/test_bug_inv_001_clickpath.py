"""Focused click-path regression proof for BUG-INV-001.

Runs a real Playwright browser flow:
1. Login
2. Open /inventory
3. Click the row delete icon in the Actions column
4. Assert placements lookup request is fired
5. Assert delete confirmation dialog opens

Run directly:
    python tests/e2e/test_bug_inv_001_clickpath.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from playwright.sync_api import Page, sync_playwright

BASE = os.getenv("HT_E2E_BASE_URL", "http://localhost:8080")
ADMIN_EMAIL = os.getenv("HT_E2E_ADMIN_EMAIL", "admin@hometower.local")
ADMIN_PASSWORD = os.getenv("HT_E2E_ADMIN_PASSWORD", "changeme_on_first_boot")


def fetch_access_token() -> str:
    """Authenticate through API and return JWT token."""
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


def fetch_placements_count(device_id: str, token: str) -> int:
    """Fetch live placement count for a device through API."""
    req = urllib.request.Request(
        f"{BASE}/api/devices/{device_id}/placements",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
        if not isinstance(payload, list):
            raise AssertionError("Placements API payload was not a list")
        return len(payload)
    except urllib.error.HTTPError as exc:
        raise AssertionError(f"Placements API returned HTTP {exc.code}") from exc


def login(page: Page) -> None:
    """Login using configured admin credentials."""
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_timeout(1500)

    email_input = page.locator('input[type="text"], input[type="email"]').first
    password_input = page.locator('input[type="password"]').first
    login_button = page.locator(
        'button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")'
    ).first

    if email_input.count() == 0 or password_input.count() == 0 or login_button.count() == 0:
        raise AssertionError("Login form controls were not found")

    email_input.fill(ADMIN_EMAIL)
    password_input.fill(ADMIN_PASSWORD)
    login_button.click()
    page.wait_for_timeout(2000)

    if "/login" in page.url:
        raise AssertionError("Login did not complete successfully")


def run_regression() -> None:
    """Execute the end-to-end click-path check for inventory delete."""
    token = fetch_access_token()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        login(page)
        page.goto(f"{BASE}/inventory", wait_until="networkidle")
        page.wait_for_timeout(2500)

        rows = page.locator(".q-table tbody tr")
        if rows.count() == 0:
            raise AssertionError("Inventory table rendered with zero rows")

        delete_button = page.locator('[data-testid^="inventory-delete-"]').first
        if delete_button.count() == 0:
            raise AssertionError("No in-place inventory delete icon button was found")

        delete_test_id = delete_button.get_attribute("data-testid") or ""
        if not delete_test_id.startswith("inventory-delete-"):
            raise AssertionError("Delete icon data-testid did not include the device id")
        delete_id = delete_test_id.replace("inventory-delete-", "", 1)
        if not delete_id:
            raise AssertionError("Could not parse device id from delete icon data-testid")

        expected_placements = fetch_placements_count(delete_id, token)

        rows_before = rows.count()
        current_url = page.url
        post_click_document_requests: list[str] = []

        def _capture_request(req: object) -> None:
            req_url = str(getattr(req, "url", ""))
            req_type = str(getattr(req, "resource_type", ""))
            if req_type == "document":
                post_click_document_requests.append(req_url)

        page.on("request", _capture_request)

        delete_button.click()

        dialog_delete_button = page.locator('button:has-text("Delete device")').first
        dialog_delete_button.wait_for(timeout=10000)
        page.wait_for_timeout(500)

        if "delete_id=" in page.url:
            raise AssertionError("Delete click used query-parameter navigation instead of in-place dialog")
        if page.url != current_url:
            raise AssertionError("Delete click triggered a page navigation instead of opening in-place")
        if any("delete_id=" in url for url in post_click_document_requests):
            raise AssertionError("Delete click triggered a document navigation with delete_id query")

        title_match = page.locator('text=/Delete .*\\?/')
        if title_match.count() == 0:
            raise AssertionError("Delete confirmation title was not rendered")

        dialog_text = page.locator(".q-dialog").first.inner_text()
        if expected_placements > 0:
            expected_line = f"This device appears in {expected_placements} topology diagram(s)."
            if expected_line not in dialog_text:
                raise AssertionError(
                    f"Dialog did not reflect placement lookup result: expected '{expected_line}'"
                )
        else:
            if "This device has no topology placements." not in dialog_text:
                raise AssertionError("Dialog did not show zero-placement message")

        page.locator('button:has-text("Cancel")').first.click()
        page.wait_for_timeout(500)

        rows_after_cancel = page.locator(".q-table tbody tr").count()
        if rows_after_cancel != rows_before:
            raise AssertionError("Inventory row count changed after canceling delete dialog")

        browser.close()


if __name__ == "__main__":
    try:
        run_regression()
        print("PASS: BUG-INV-001 click path verified (delete icon -> placements lookup -> confirmation dialog)")
        sys.exit(0)
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
