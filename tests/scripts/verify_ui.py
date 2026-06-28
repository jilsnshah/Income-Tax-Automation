from playwright.sync_api import sync_playwright
import time

def run_ui_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Navigating to http://localhost:5173")
        page.goto("http://localhost:5173")
        page.wait_for_selector('text=1. Upload Excel File', state='visible')
        
        # Take screenshot of initial state
        page.screenshot(path="/Users/jils/dad/screenshot_1_initial.png")
        print("Captured initial state.")
        
        # Upload file
        # The input is hidden, so we need to set the files directly
        print("Uploading test_browser.xlsx")
        page.locator('input[type="file"]').set_input_files("/Users/jils/dad/test_browser.xlsx")
        
        # Wait for Step 2
        page.wait_for_selector('text=2. Configuration & Mapping')
        page.screenshot(path="/Users/jils/dad/screenshot_2_mapping.png")
        print("Captured mapping state.")
        
        # Set absolute output directory
        page.fill('input[placeholder="/Users/jils/dad/output"]', "/Users/jils/dad/output_test")
        
        # Click Review Queue
        page.click('button:has-text("Review Queue")')
        
        # Wait for Step 3
        page.wait_for_selector('text=3. Processing Queue')
        page.screenshot(path="/Users/jils/dad/screenshot_3_queue.png")
        print("Captured queue state.")
        
        # Ensure 'Run Headless Mode' is checked
        if not page.locator('input[type="checkbox"]').is_checked():
            page.locator('input[type="checkbox"]').check()
            
        # Start Processing
        print("Starting processing...")
        page.click('button:has-text("Start Processing")')
        
        # Wait for the first client to be done (success or error)
        # We can poll the logs or the table
        # Since it takes ~4 mins, we will wait a bit
        print("Waiting for processing to complete. This may take 5-10 minutes...")
        
        # Wait until the 'Stop Processing' button disappears or changes, or queue is done
        # Actually, let's just wait until the table rows say "success" or "error"
        # Since there are 2 rows, we wait for both to not say "pending" or "running"
        
        max_wait = 1200  # 20 mins max
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            time.sleep(10)
            page.screenshot(path="/Users/jils/dad/screenshot_4_processing.png")
            
            # Check if any row says 'running' or 'pending'
            html = page.inner_html('body')
            if 'running' not in html.lower() and 'pending' not in html.lower():
                print("Processing completed!")
                page.screenshot(path="/Users/jils/dad/screenshot_5_finished.png")
                break
                
        browser.close()

if __name__ == "__main__":
    run_ui_test()
