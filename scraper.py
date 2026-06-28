import os
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth
from config import LOGIN_URL, TIMEOUT_MS, ASSESSMENT_YEAR
from crypto_utils import process_client_files

def download_ais_tis_file(ais_page, pan: str, document_name: str, output_path: str, timeout: int = 60000):
    """
    Helper to download either AIS or TIS PDF.
    Handles the case where the file is generated synchronously (Download button) 
    and asynchronously (Go to Activity History button).
    """
    logger.info(f"[{pan}] Locating '{document_name}' download row...")
    row = ais_page.locator('.d-flex').filter(has_text=document_name)
    row.wait_for(state='visible', timeout=timeout)
    
    # 1. Check if it already says "Go to Activity History"
    activity_btn = row.locator('button', has_text="Go to Activity History")
    download_btn = row.locator('button', has_text="Download")
    
    if download_btn.count() > 0:
        logger.info(f"[{pan}] Found direct Download button for {document_name}. Clicking it...")
        try:
            # We use a 30s timeout. If it's an instant download, it will start quickly.
            # If the portal decides it's too large, it won't start a download; instead, the button changes to "Go to Activity History".
            with ais_page.expect_download(timeout=30000) as dl_info:
                download_btn.click()
            dl_info.value.save_as(output_path)
            logger.info(f"[{pan}] Saved {document_name} to {output_path}")
            ais_page.screenshot(path=f"{output_path.rsplit('/', 1)[0]}/{pan}_smooth_success.png")
            return
        except Exception:
            logger.info(f"[{pan}] Did not start direct download within 30s. Checking if button changed to Activity History...")
            # Fall through to Activity History logic below
    
    # Refresh locators in case DOM changed
    activity_btn = row.locator('button', has_text="Go to Activity History")
    
    # 2. Activity History Async Generation
    if activity_btn.count() > 0:
        logger.info(f"[{pan}] Document is generating async. Clicking 'Go to Activity History'...")
        activity_btn.click()
        
        # Polling Loop for Activity History
        poll_max_attempts = 15 # Approx 2-3 minutes total
        for attempt in range(poll_max_attempts):
            logger.info(f"[{pan}] Polling Activity History (Attempt {attempt+1}/{poll_max_attempts})...")
            ais_page.wait_for_timeout(3000) # Give it time to load the table
            
            page_text = ais_page.locator('body').inner_text().lower()
            if "in progress" in page_text:
                logger.info(f"[{pan}] File is 'in progress'. Refreshing Activity History...")
                # To refresh: Click AIS tab on header, then click Activity history tab
                try:
                    ais_page.click('div.tab-header:has-text("AIS"), a:has-text("AIS"), text="AIS"', timeout=2000, force=True)
                except Exception:
                    pass
                ais_page.wait_for_timeout(2000)
                try:
                    ais_page.click('text=/Activity history/i', force=True)
                except Exception:
                    pass
                continue
            
            # Try to find the download button or icon for the top-most row
            dl_icon = ais_page.locator('.pi-download, i[class*="download"], span[class*="download"], button:has-text("Download")').first
            
            if dl_icon.count() > 0:
                logger.info(f"[{pan}] File is ready! Clicking Download icon from Activity History...")
                with ais_page.expect_download(timeout=timeout) as dl_info:
                    dl_icon.click(force=True)
                dl_info.value.save_as(output_path)
                logger.info(f"[{pan}] Saved {document_name} to {output_path}")
                ais_page.screenshot(path=f"{output_path.rsplit('/', 1)[0]}/{pan}_edge_success.png")
                
                # Navigate back to AIS tab to be ready for the next file
                logger.info(f"[{pan}] Navigating back to main AIS tab...")
                try:
                    ais_page.click('div.tab-header:has-text("AIS"), a:has-text("AIS"), text="AIS"', timeout=2000, force=True)
                except Exception:
                    pass
                ais_page.wait_for_timeout(2000)
                # Ensure we click the "Download AIS/TIS" button again to reopen the modal for the next file
                ais_page.click('button:has-text("Download AIS/TIS")', force=True)
                ais_page.wait_for_selector('text=Annual Information Statement (AIS) - PDF', timeout=timeout)
                return
    
    else:
        raise Exception(f"Failed to download {document_name}: 'Download' button timed out after 30s, and 'Go to Activity History' never appeared.")


def download_26as_for_client(pan: str, password: str, dob: str, output_dir: str, headless: bool = True):
    current_stage = "Initializing Playwright"
    with sync_playwright() as p:
        try:
            # Launch CHROMIUM with stealth plugin
            logger.info(f"[{pan}] Launching Chromium with stealth (headless={headless})...")
            current_stage = "Launching Browser"
            browser = p.chromium.launch(headless=headless, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                accept_downloads=True,
                ignore_https_errors=True
            )
            
            # Stealth: Bypass webdriver detection using playwright-stealth
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            page.set_default_timeout(TIMEOUT_MS)

            current_stage = "Navigating to Login Page"
            logger.info(f"[{pan}] Navigating to Login Page...")
            try:
                page.goto(LOGIN_URL, timeout=30000)
            except PlaywrightTimeout:
                logger.warning(f"[{pan}] Timeout waiting for full page load, checking if input is ready anyway...")
            
            # 1. Login Flow
            # Wait for the PAN input field
            current_stage = "Entering PAN"
            page.wait_for_selector('#panAdhaarUserId', state='visible', timeout=TIMEOUT_MS)
            page.wait_for_timeout(500)
            page.type('#panAdhaarUserId', pan, delay=100)
            page.wait_for_timeout(500)
            page.click('button.large-button-primary')
            
            # Secure access message checkbox
            current_stage = "Handling Login Checkbox"
            page.wait_for_selector('#passwordCheckBox-input', state='visible')
            page.wait_for_timeout(1500)
            page.check('#passwordCheckBox-input')
            
            # Password
            current_stage = "Entering Password"
            logger.info(f"[{pan}] Entering password...")
            page.wait_for_selector('#loginPasswordField', state='visible')
            page.wait_for_timeout(1000)
            page.type('#loginPasswordField', password, delay=150)
            page.wait_for_timeout(3000) # Give JS time to encrypt the payload
            page.press('#loginPasswordField', 'Enter')

            # Wait for dashboard to load
            current_stage = "Waiting for Dashboard"
            logger.info(f"[{pan}] Waiting for dashboard to load...")
            
            # Check for Dual Login prompt before or during wait
            try:
                login_here_btn = page.wait_for_selector('button:has-text("Login Here")', timeout=5000, state='visible')
                if login_here_btn:
                    login_here_btn.click()
                    logger.info(f"[{pan}] Clicked 'Login Here' to bypass Dual Login Warning.")
            except Exception:
                pass

            try:
                # We wait for either the e-file menu or an error popup
                page.wait_for_selector('text=e-File', state='attached', timeout=25000)
            except Exception:
                # Might be an invalid password or locked account
                error_txt = page.locator('.error-msg').text_content() if page.locator('.error-msg').count() > 0 else "Unknown login error"
                raise Exception(f"Login failed: {error_txt}")

            # Handle potential skip/update popups
            current_stage = "Handling Popups"
            try:
                page.wait_for_selector('button:has-text("Skip")', timeout=5000, state='visible')
                page.click('button:has-text("Skip")')
                logger.info(f"[{pan}] Skipped update profile popup.")
            except Exception:
                pass

            # 2. Navigate to Form 26AS
            current_stage = "Navigating to Form 26AS"
            logger.info(f"[{pan}] Navigating to Form 26AS...")
            
            # Click e-File menu
            page.click('text=e-File')
            
            # Click Income Tax Returns
            page.hover('text=Income Tax Returns')
            
            # Click View Form 26AS
            logger.info(f"[{pan}] Clicking 'View Form 26AS' and waiting for TRACES tab...")
            with context.expect_page(timeout=TIMEOUT_MS) as new_page_info:
                page.click('text=View Form 26AS')
                
                # Check for disclaimer popup on main page and click Confirm if present
                try:
                    disclaimer_btn = page.wait_for_selector('button:has-text("Confirm")', timeout=10000, state='visible')
                    if disclaimer_btn:
                        logger.info(f"[{pan}] Disclaimer popup appeared. Clicking Confirm...")
                        disclaimer_btn.click()
                except PlaywrightTimeout:
                    logger.info(f"[{pan}] No disclaimer popup appeared. Proceeding...")
                    
            traces_page = new_page_info.value
            traces_page.set_default_timeout(TIMEOUT_MS)
            
            # Listen to dialogs (like alerts for "no data") to avoid silent blocking
            traces_page.on("dialog", lambda dialog: logger.warning(f"[{pan}] TRACES Dialog: {dialog.message}") or dialog.accept())
            
            # 3. TRACES Workflow
            current_stage = "TRACES Workflow"
            logger.info(f"[{pan}] Handling TRACES website...")
            traces_page.wait_for_selector('#Details', state='visible')
            traces_page.click('#Details', force=True)
            traces_page.click('#btn', force=True)
            
            logger.info(f"[{pan}] Navigating to View Tax Credit page...")
            traces_page.goto("https://traces61services.tdscpc.gov.in/serv/tapn/view26AS.xhtml")
            
            current_stage = "Selecting Assessment Year"
            logger.info(f"[{pan}] Waiting for Assessment Year dropdown...")
            traces_page.wait_for_selector('#AssessmentYearDropDown', state='visible')
            logger.info(f"[{pan}] Selecting Assessment Year value {ASSESSMENT_YEAR}...")
            traces_page.select_option('#AssessmentYearDropDown', value=ASSESSMENT_YEAR)
            
            # --- Download HTML as PDF ---
            current_stage = "Downloading HTML PDF"
            logger.info(f"[{pan}] Fetching HTML view...")
            traces_page.select_option('#viewType', label="HTML")
            traces_page.locator('text="View / Download"').first.click(force=True)
            
            logger.info(f"[{pan}] Clicking Export as PDF for HTML...")
            with traces_page.expect_download(timeout=120000) as html_pdf_info:
                traces_page.click('#pdfBtn')
            
            html_pdf_filename = f"{output_dir}/{pan}_html.pdf"
            html_pdf_info.value.save_as(html_pdf_filename)
            logger.info(f"[{pan}] Saved HTML PDF to {html_pdf_filename}")
            
            # --- Download Text ---
            current_stage = "Downloading Text File"
            logger.info(f"[{pan}] Fetching Text view...")
            try:
                traces_page.select_option('#viewType', label="Text")
                
                logger.info(f"[{pan}] Clicking View / Download to get Text file...")
                with traces_page.expect_download(timeout=10000) as text_info:
                    traces_page.locator('text="View / Download"').first.click(force=True)
                
                text_filename = f"{output_dir}/{pan}_text.zip"
                text_info.value.save_as(text_filename)
                logger.info(f"[{pan}] Saved Text file to {text_filename}")
            except Exception as e:
                logger.warning(f"[{pan}] Failed to download Text file from TRACES (error: {e}). Skipping Text download.")
            
            # --- 4. AIS Workflow ---
            current_stage = "Starting AIS extraction"
            logger.info(f"[{pan}] Starting AIS extraction. Navigating back to Dashboard...")
            page.bring_to_front()
            
            # AIS Tab Navigation with Retry for random network errors
            max_ais_retries = 5
            ais_page = None
            for attempt in range(max_ais_retries):
                logger.info(f"[{pan}] Clicking AIS menu item (Attempt {attempt+1})...")
                page.bring_to_front()
                page.wait_for_timeout(1000)
                with context.expect_page(timeout=TIMEOUT_MS) as ais_page_info:
                    page.click('a#AIS', force=True)
                    try:
                        proceed_btn = page.wait_for_selector('button:has-text("Proceed")', timeout=3000, state='visible')
                        if proceed_btn:
                            logger.info(f"[{pan}] Found Proceed button, clicking it...")
                            proceed_btn.click()
                    except PlaywrightTimeout:
                        pass
                
                ais_page = ais_page_info.value
                ais_page.set_default_timeout(TIMEOUT_MS)
                
                current_stage = "Waiting for AIS load"
                logger.info(f"[{pan}] AIS tab opened. Waiting for load...")
                ais_page.wait_for_load_state('networkidle')
                ais_page.wait_for_timeout(3000)
                
                # Check for "network issue" popup
                try:
                    network_error = ais_page.wait_for_selector('text=/network issue currently/i', timeout=3000)
                    if network_error:
                        logger.warning(f"[{pan}] Hit random AIS network error popup. Clicking Ok...")
                        try:
                            ais_page.click('button:has-text("Ok")', force=True, timeout=1000)
                        except Exception:
                            pass
                        logger.info(f"[{pan}] Closing tab and retrying AIS navigation...")
                        try:
                            if not ais_page.is_closed():
                                ais_page.close()
                        except Exception:
                            pass
                        continue
                except PlaywrightTimeout:
                    pass
                
                # Verify that the AIS dashboard actually loaded by waiting for the Download button
                try:
                    logger.info(f"[{pan}] Verifying AIS load by waiting for Download button...")
                    download_btn = ais_page.wait_for_selector('button:has-text("Download AIS/TIS")', timeout=20000, state='visible')
                    if download_btn:
                        logger.info(f"[{pan}] AIS dashboard loaded successfully!")
                        break
                except PlaywrightTimeout:
                    logger.warning(f"[{pan}] AIS dashboard failed to load properly (blank screen or stuck). Retrying...")
                    try:
                        if not ais_page.is_closed():
                            ais_page.close()
                    except Exception:
                        pass
                    continue
                
            if not ais_page or ais_page.is_closed():
                raise Exception("Failed to open AIS tab after multiple attempts due to portal network issues.")
            
            current_stage = "Downloading AIS/TIS"
            logger.info(f"[{pan}] Clicking Download AIS/TIS button...")
            try:
                # Try clicking normally first, wait for modal. If it fails, click again.
                for _ in range(3):
                    ais_page.click('button:has-text("Download AIS/TIS")')
                    try:
                        ais_page.wait_for_selector('text=Annual Information Statement (AIS) - PDF', timeout=5000, state='visible')
                        break
                    except PlaywrightTimeout:
                        logger.warning(f"[{pan}] Modal didn't appear. Retrying click...")
                        continue
                
                # Final check if modal loaded
                ais_page.wait_for_selector('text=Annual Information Statement (AIS) - PDF', timeout=5000, state='visible')
                
                # 1. Download AIS PDF
                current_stage = "Downloading AIS PDF"
                ais_pdf_path = f"{output_dir}/{pan}_ais.pdf"
                download_ais_tis_file(ais_page, pan, "Annual Information Statement (AIS) - PDF", ais_pdf_path, timeout=TIMEOUT_MS)
                
                # 2. Download TIS PDF
                current_stage = "Downloading TIS PDF"
                logger.info(f"[{pan}] Downloading TIS PDF directly...")
                tis_pdf_path = f"{output_dir}/{pan}_tis.pdf"
                download_ais_tis_file(ais_page, pan, "Taxpayer Information Summary (TIS) - PDF", tis_pdf_path, timeout=TIMEOUT_MS)
                
            except Exception as e:
                logger.error(f"[{pan}] Failed to download AIS/TIS. Taking screenshot...")
                try:
                    if not ais_page.is_closed():
                        ais_page.screenshot(path=f"{output_dir}/{pan}_ais_error.png", full_page=True)
                except Exception:
                    pass
                raise e
            
            # 3. Decrypt all files
            current_stage = "Decrypting files"
            process_client_files(pan, dob, output_dir)
            
            import glob
            for f in glob.glob(os.path.join(output_dir, f"{pan}*.html")):
                try:
                    os.remove(f)
                except Exception:
                    pass
            
            return True, "OK"

        except Exception as e:
            err_msg = f"Failed at stage '{current_stage}': {str(e)}"
            logger.error(f"[{pan}] {err_msg}")
            
            # Take a screenshot for debugging
            try:
                if 'page' in locals() and not page.is_closed():
                    page.screenshot(path=f"{output_dir}/{pan}_error_page.png", full_page=True)
                if 'traces_page' in locals() and not traces_page.is_closed():
                    traces_page.screenshot(path=f"{output_dir}/{pan}_error_traces.png", full_page=True)
                if 'ais_page' in locals() and ais_page is not None and not ais_page.is_closed():
                    ais_page.screenshot(path=f"{output_dir}/{pan}_error_ais.png", full_page=True)
            except Exception as ss_err:
                logger.warning(f"[{pan}] Failed to take error screenshot: {ss_err}")
                
            return False, err_msg
