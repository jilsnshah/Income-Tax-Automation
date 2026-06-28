"""
test_ais.py — Exploratory/debug test for the AIS tab navigation flow.

Reads credentials from environment variables (see .env.example).
Run with:
    IT_PAN=<pan> IT_PASSWORD=<pwd> python test_ais.py
"""

import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth


def test_ais():
    pan = os.environ.get("IT_PAN", "")
    pwd = os.environ.get("IT_PASSWORD", "")

    if not pan or not pwd:
        raise EnvironmentError(
            "Set IT_PAN and IT_PASSWORD environment variables before running this test. "
            "See .env.example for reference."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--start-maximized'
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
        )

        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        print("Navigating to login...")
        page.goto("https://eportal.incometax.gov.in/iec/foservices/#/login")
        page.wait_for_selector("input[name='pan']", state='visible', timeout=60000)
        page.fill("input[name='pan']", pan)
        page.click("button:has-text('Continue')")
        page.wait_for_selector("input[type='checkbox']", state='visible')
        page.check("input[type='checkbox']")
        page.fill("input[name='password']", pwd)
        page.click("button:has-text('Continue')")

        # Wait for dashboard
        print("Waiting for dashboard to load...")
        try:
            page.wait_for_url("**/dashboard*", timeout=30000)
        except PlaywrightTimeout:
            if page.locator('button:has-text("Login Here")').is_visible():
                page.click('button:has-text("Login Here")')
                page.wait_for_url("**/dashboard*", timeout=30000)

        page.wait_for_timeout(2000)
        print("Logged in. Clicking AIS...")

        # Click the AIS menu link
        page.click('a#AIS')
        page.wait_for_timeout(2000)

        # Check if there is a proceed button in the disclaimer modal
        if page.locator('button:has-text("Proceed")').is_visible():
            print("Found Proceed button, clicking it...")
            with context.expect_page(timeout=60000) as ais_page_info:
                page.click('button:has-text("Proceed")')

            ais_page = ais_page_info.value
            print("AIS tab opened. Waiting for load...")
            ais_page.wait_for_load_state('networkidle')
            ais_page.wait_for_timeout(5000)  # wait for angular to load

            with open("output/ais_tab.html", "w", encoding="utf-8") as f:
                f.write(ais_page.content())
            print("Dumped AIS tab HTML to output/ais_tab.html")

            # Optionally take a screenshot
            ais_page.screenshot(path="output/ais_tab.png", full_page=True)
            print("Saved screenshot to output/ais_tab.png")

        else:
            with open("output/ais_popup.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("No proceed button found. Dumped current HTML to output/ais_popup.html")
            page.screenshot(path="output/ais_popup.png", full_page=True)


if __name__ == "__main__":
    test_ais()
