"""
tests/test_login.py — E2E tests for the Income Tax portal login flow.

Tests cover:
  - Successful login with valid credentials (happy path)
  - Dual-login prompt bypass ("Login Here" button)
  - Graceful error surface on invalid PAN format (negative / boundary test)

These tests require valid IT_PAN, IT_PASSWORD, and IT_DOB environment variables.
They are gated behind the `credentials` fixture which auto-skips if vars are missing,
so they are safe to include in CI and will only run when secrets are configured.

Test design: equivalence partitioning — one representative from the valid partition
and one from the invalid partition for each input dimension.

NOTE: The IT portal rate-limits consecutive requests from the same IP.
A 3-second inter-test cooldown (via the `rate_limit_pause` autouse fixture)
prevents ERR_EMPTY_RESPONSE on back-to-back test runs.
"""

import time
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

LOGIN_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"


# ---------------------------------------------------------------------------
# Rate-limit guard: pause 3 s between tests to avoid portal throttling
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def rate_limit_pause():
    """
    The IT portal throttles back-to-back browser sessions from the same IP.
    A small pause between each test prevents ERR_EMPTY_RESPONSE on the second test.
    """
    yield
    time.sleep(3)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _navigate_to_login(page):
    """
    Navigate to the login page, retrying once on ERR_EMPTY_RESPONSE.
    The portal occasionally drops the first connection; a single retry
    covers the vast majority of transient failures.
    """
    try:
        page.goto(LOGIN_URL, timeout=30000)
    except Exception as e:
        if "ERR_EMPTY_RESPONSE" in str(e) or "net::" in str(e):
            time.sleep(5)
            page.goto(LOGIN_URL, timeout=30000)
        else:
            raise


def _do_login(page, pan: str, password: str):
    """Helper: perform the full login sequence up to submitting the password."""
    _navigate_to_login(page)
    page.wait_for_selector("#panAdhaarUserId", state="visible", timeout=30000)
    page.type("#panAdhaarUserId", pan, delay=80)
    page.wait_for_timeout(1000)  # let client-side validation enable the button
    page.click("button.large-button-primary")

    page.wait_for_selector("#passwordCheckBox-input", state="visible")
    page.check("#passwordCheckBox-input")

    page.wait_for_selector("#loginPasswordField", state="visible")
    page.type("#loginPasswordField", password, delay=100)
    page.wait_for_timeout(2000)
    page.press("#loginPasswordField", "Enter")


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestLoginFlow:
    """Tests for the portal authentication flow."""

    def test_login_page_loads(self, browser_context):
        """
        Verify the login page renders the PAN input field.
        Boundary: page must load and be interactive within 30 s.
        """
        _, page = browser_context
        _navigate_to_login(page)
        page.wait_for_selector("#panAdhaarUserId", state="visible", timeout=30000)
        assert page.locator("#panAdhaarUserId").is_visible(), (
            "PAN input field should be visible on the login page"
        )

    def test_login_with_valid_credentials(self, browser_context, credentials):
        """
        Happy path: valid PAN + password reaches the dashboard (e-File menu visible).
        Validates the entire authentication state transition.
        """
        _, page = browser_context
        _do_login(page, credentials["pan"], credentials["password"])

        # Handle dual-login prompt if it appears
        try:
            login_here = page.wait_for_selector(
                'button:has-text("Login Here")', timeout=5000, state="visible"
            )
            if login_here:
                login_here.click()
        except PlaywrightTimeout:
            pass

        # Assert: dashboard loaded — e-File menu is the canonical signal
        page.wait_for_selector("text=e-File", state="attached", timeout=25000)
        assert page.locator("text=e-File").count() > 0, (
            "Dashboard should show the e-File menu after successful login"
        )

    def test_login_handles_dual_login_prompt(self, browser_context, credentials):
        """
        Regression test: if portal shows a 'Login Here' dual-session prompt,
        clicking it should still reach the dashboard.
        This guards against silent breakage of the bypass logic.
        """
        _, page = browser_context
        _do_login(page, credentials["pan"], credentials["password"])

        # The bypass should handle the prompt transparently
        try:
            btn = page.wait_for_selector(
                'button:has-text("Login Here")', timeout=5000, state="visible"
            )
            if btn:
                btn.click()
        except PlaywrightTimeout:
            pass  # No dual-login prompt — that's fine too

        page.wait_for_selector("text=e-File", state="attached", timeout=25000)
        assert page.locator("text=e-File").count() > 0

    def test_login_with_invalid_pan_shows_error(self, browser_context):
        """
        Negative / boundary test: a syntactically invalid PAN (wrong length/format)
        should be rejected by the portal's client-side validation.

        Equivalence class: invalid PAN partition.

        Expected behavior (confirmed by manual observation):
        - The portal validates PAN format in the browser before enabling the submit button.
        - "INVALID123" (9 chars, wrong pattern) keeps the button DISABLED.
        - A disabled button IS the correct error signal — no separate error message needed.
        - We must NOT try to click a disabled button; instead assert it stays disabled.
        """
        _, page = browser_context
        _navigate_to_login(page)
        page.wait_for_selector("#panAdhaarUserId", state="visible", timeout=30000)

        # Type a PAN that fails the format check (wrong length, wrong pattern)
        page.type("#panAdhaarUserId", "INVALID123", delay=50)

        # Wait for client-side validation to run
        page.wait_for_timeout(2000)

        # The submit button should be DISABLED — that is the portal's validation response
        submit_btn = page.locator("button.large-button-primary")
        submit_btn.wait_for(state="visible", timeout=5000)

        assert submit_btn.is_disabled(), (
            "Submit button should remain disabled for an invalid PAN format — "
            "the portal performs client-side format validation before allowing progression"
        )

        # Also confirm we have NOT advanced to the password step
        assert not page.locator("#loginPasswordField").is_visible(), (
            "Password field should not appear when PAN format is invalid"
        )
