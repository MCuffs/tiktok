import time
import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"

def check_backstage_simple():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=chrome_path,
            headless=False,
            args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
            viewport={'width': 1280, 'height': 800}
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        print("Go to Backstage...")
        try:
            # Try a different URL that redirects to the same place or the main dashboard
            page.goto("https://live-backstage.tiktok.com/portal", timeout=30000) 
            # Or just the root
            
            print("Navigation started. Waiting 10s...")
            time.sleep(10)
            
            print(f"Final URL: {page.url}")
            page.screenshot(path="backstage_result.png")
            
            # Dump body text to check for keywords
            text = page.inner_text("body")
            if "Relationship Management" in text or "관계 관리" in text:
                print("SUCCESS: Found Relationship Management menu.")
            else:
                print("WARNING: 'Relationship Management' not found on page.")
                
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="backstage_error.png")

        browser.close()

if __name__ == "__main__":
    check_backstage_simple()
