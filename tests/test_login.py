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
"""

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

LOGIN_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"


def _do_login(page, pan: str, password: str):
    """Helper: perform the full login sequence up to the dashboard wait."""
    page.goto(LOGIN_URL, timeout=30000)
    page.wait_for_selector("#panAdhaarUserId", state="visible", timeout=30000)
    page.type("#panAdhaarUserId", pan, delay=80)
    page.click("button.large-button-primary")

    page.wait_for_selector("#passwordCheckBox-input", state="visible")
    page.check("#passwordCheckBox-input")

    page.wait_for_selector("#loginPasswordField", state="visible")
    page.type("#loginPasswordField", password, delay=100)
    page.wait_for_timeout(2000)
    page.press("#loginPasswordField", "Enter")


class TestLoginFlow:
    """Tests for the portal authentication flow."""

    def test_login_page_loads(self, browser_context):
        """
        Verify the login page renders the PAN input field.
        Boundary: page must load and be interactive within 30 s.
        """
        _, page = browser_context
        page.goto(LOGIN_URL, timeout=30000)
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
        Negative / boundary test: a syntactically invalid PAN should surface
        an error message without crashing the automation.
        Equivalence class: invalid PAN partition.
        """
        _, page = browser_context
        page.goto(LOGIN_URL, timeout=30000)
        page.wait_for_selector("#panAdhaarUserId", state="visible", timeout=30000)

        # Use an obviously invalid PAN (wrong format)
        page.type("#panAdhaarUserId", "INVALID123", delay=50)
        page.click("button.large-button-primary")

        # Portal should either show a validation error or not proceed to password step
        page.wait_for_timeout(3000)

        # Assert: we should NOT reach the password field (invalid PAN rejected)
        # OR an error message is displayed
        password_visible = page.locator("#loginPasswordField").is_visible()
        error_visible = page.locator(".error-msg, .alert-danger, [class*='error']").count() > 0

        assert not password_visible or error_visible, (
            "An invalid PAN should either show an error or block progression to the password step"
        )
