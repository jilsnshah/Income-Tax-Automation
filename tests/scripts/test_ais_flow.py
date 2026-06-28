"""
test_ais_flow.py — Full AIS flow debug test: login → AIS tab → Download modal inspection.

Reads credentials from environment variables (see .env.example).
Run with:
    IT_PAN=<pan> IT_PASSWORD=<pwd> python test_ais_flow.py
"""

import os
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

LOGIN_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"


def test_ais():
    pan = os.environ.get("IT_PAN", "")
    password = os.environ.get("IT_PASSWORD", "")

    if not pan or not password:
        raise EnvironmentError(
            "Set IT_PAN and IT_PASSWORD environment variables before running this test. "
            "See .env.example for reference."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        logger.info("Logging in...")
        page.goto(LOGIN_URL)

        page.wait_for_selector('#panAdhaarUserId', state='visible')
        page.type('#panAdhaarUserId', pan, delay=100)
        page.click('button.large-button-primary')

        page.wait_for_selector('#passwordCheckBox-input', state='visible')
        page.check('#passwordCheckBox-input')

        page.wait_for_selector('#loginPasswordField', state='visible')
        page.type('#loginPasswordField', password, delay=100)
        page.wait_for_timeout(2000)
        page.press('#loginPasswordField', 'Enter')

        logger.info("Waiting for dashboard...")
        try:
            login_here_btn = page.wait_for_selector('button:has-text("Login Here")', timeout=5000, state='visible')
            if login_here_btn:
                login_here_btn.click()
        except PlaywrightTimeout:
            pass

        try:
            page.wait_for_selector('text=e-File', state='attached', timeout=25000)
        except PlaywrightTimeout as e:
            logger.error(f"Failed to wait for e-File: {e}")
            page.screenshot(path="login_error.png")
            with open("login_error_dom.html", "w") as f:
                f.write(page.content())
            browser.close()
            return

        try:
            page.wait_for_selector('button:has-text("Skip")', timeout=5000, state='visible')
            page.click('button:has-text("Skip")')
        except PlaywrightTimeout:
            pass

        logger.info("Clicking AIS menu...")
        with context.expect_page(timeout=30000) as ais_page_info:
            page.click('a#AIS', force=True)
            try:
                proceed_btn = page.wait_for_selector('button:has-text("Proceed")', timeout=3000, state='visible')
                if proceed_btn:
                    proceed_btn.click()
            except PlaywrightTimeout:
                pass

        ais_page = ais_page_info.value
        logger.info("Waiting for AIS networkidle...")
        ais_page.wait_for_load_state('networkidle')
        ais_page.wait_for_timeout(5000)

        logger.info("Clicking initial Download AIS/TIS button...")
        ais_page.click('button:has-text("Download AIS/TIS")', force=True)

        # Wait for the modal
        ais_page.wait_for_timeout(3000)
        ais_page.screenshot(path="ais_modal.png")
        with open("ais_modal_dom.html", "w") as f:
            f.write(ais_page.content())

        logger.info("Dumped ais_modal_dom.html and ais_modal.png")

        # Check if Go to activity history exists
        if ais_page.locator('button:has-text("Go to Activity History")').count() > 0:
            logger.info("Found Go to Activity History!")

        browser.close()


if __name__ == "__main__":
    test_ais()
