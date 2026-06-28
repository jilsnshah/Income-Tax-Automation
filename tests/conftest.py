"""
conftest.py — Shared pytest fixtures for the 26AS automation test suite.

Credentials are loaded from environment variables. Set them before running:
    export IT_PAN=<your pan>
    export IT_PASSWORD=<your password>
    export IT_DOB=<ddmmyyyy>
"""

import os
import shutil
import pytest
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


# ---------------------------------------------------------------------------
# Credential fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def credentials():
    """
    Load IT portal credentials from environment variables.
    Skips the test if any variable is missing (so CI unit-test jobs
    don't fail when secrets aren't set).
    """
    pan = os.environ.get("IT_PAN", "")
    password = os.environ.get("IT_PASSWORD", "")
    dob = os.environ.get("IT_DOB", "")

    if not all([pan, password, dob]):
        pytest.skip(
            "Skipping: IT_PAN, IT_PASSWORD, and IT_DOB environment variables are required. "
            "Set them or create a .env file (see .env.example)."
        )

    return {"pan": pan, "password": password, "dob": dob}


# ---------------------------------------------------------------------------
# Browser fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture
def browser_context(playwright_instance):
    """
    Provides a stealth-enabled Chromium browser context.
    Tears down after each test.
    """
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    browser = playwright_instance.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        accept_downloads=True,
        ignore_https_errors=True,
    )
    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    yield context, page

    browser.close()


# ---------------------------------------------------------------------------
# Output directory fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_output_dir(tmp_path):
    """Provides a temporary output directory, cleaned up after the test."""
    out = tmp_path / "26as_output"
    out.mkdir()
    yield str(out)
    shutil.rmtree(str(out), ignore_errors=True)
