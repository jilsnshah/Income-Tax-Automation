"""
visual_ais_test.py — Step-by-step visual debug test capturing screenshots at each AIS download stage.

Reads credentials from environment variables (see .env.example).
Run with:
    IT_PAN=<pan> IT_PASSWORD=<pwd> python visual_ais_test.py
"""

import os
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

LOGIN_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"


def run_visual_test():
    pan = os.environ.get("IT_PAN", "")
    password = os.environ.get("IT_PASSWORD", "")

    if not pan or not password:
        raise EnvironmentError(
            "Set IT_PAN and IT_PASSWORD environment variables before running this test. "
            "See .env.example for reference."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        logger.info("Logging in...")
        page.goto(LOGIN_URL, timeout=60000)

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
            logger.error("Timed out waiting for e-File. Taking screenshot.")
            page.screenshot(path="login_error.png")
            raise e
        try:
            page.wait_for_selector('button:has-text("Skip")', timeout=5000, state='visible')
            page.click('button:has-text("Skip")')
        except PlaywrightTimeout:
            pass

        logger.info("Opening AIS tab...")
        with context.expect_page(timeout=30000) as ais_page_info:
            page.click('a#AIS', force=True)
            try:
                proceed_btn = page.wait_for_selector('button:has-text("Proceed")', timeout=3000, state='visible')
                if proceed_btn:
                    proceed_btn.click()
            except PlaywrightTimeout:
                pass

        ais_page = ais_page_info.value
        ais_page.wait_for_load_state('networkidle')
        ais_page.wait_for_timeout(5000)

        logger.info("Clicking Download AIS/TIS button...")
        ais_page.click('button:has-text("Download AIS/TIS")', force=True)
        ais_page.wait_for_timeout(3000)

        logger.info("Taking Step 1 Screenshot: The Download Modal")
        ais_page.screenshot(path="step1_modal.png")

        row = ais_page.locator('.d-flex').filter(has_text="Annual Information Statement (AIS) - PDF")

        if row.locator('button', has_text="Download").count() > 0:
            logger.info("Button says 'Download'. Clicking it...")
            row.locator('button', has_text="Download").click()
            ais_page.wait_for_timeout(3000)
            logger.info("Taking Step 2 Screenshot: After clicking Download")
            ais_page.screenshot(path="step2_clicked.png")

        if row.locator('button', has_text="Go to Activity History").count() > 0:
            logger.info("Button says 'Go to Activity History'. Clicking it...")
            row.locator('button', has_text="Go to Activity History").click()
            ais_page.wait_for_timeout(4000)
            logger.info("Taking Step 3 Screenshot: The Activity History View")
            ais_page.screenshot(path="step3_activity.png")

            # Now let's try the refresh trick to see what happens
            logger.info("Doing refresh trick...")
            ais_page.locator('text="AIS"').first.click(force=True)
            ais_page.wait_for_timeout(2000)
            ais_page.locator('text="Activity history"').first.click(force=True)
            ais_page.wait_for_timeout(4000)
            logger.info("Taking Step 4 Screenshot: After Refresh")
            ais_page.screenshot(path="step4_refresh.png")

        browser.close()
        logger.info("Visual test completed.")


if __name__ == "__main__":
    run_visual_test()
