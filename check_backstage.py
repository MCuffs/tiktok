import time
import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"

def explore_backstage():
    print("Launching Explore Script...")
    
    # Same path as before
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        print("Chrome not found, cannot use saved session properly if it was created with Chrome.")
        return

    with sync_playwright() as p:
        args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled"
        ]
        
        # Use existing user data with the CORRECT executable
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                executable_path=chrome_path,
                headless=False,
                args=args,
                viewport={'width': 1280, 'height': 800}
            )
        except Exception as e:
            print(f"Failed to launch browser: {e}")
            print("Suggest running: pkill -f Chrome")
            return
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        # Taking a safer approach: go to main Live page first to see if login holds
        print("Checking login on main page...")
        page.goto("https://www.tiktok.com/live", timeout=60000)
        time.sleep(3)
        
        target_url = "https://live-backstage.tiktok.com/"
        print(f"Navigating to {target_url}...")
        page.goto(target_url, timeout=60000)
        time.sleep(10) # Wait for redirect
        
        print(f"Current URL: {page.url}")
        
        page.screenshot(path="backstage_check.png")
        with open("backstage_dump.html", "w") as f:
            f.write(page.content())
            
        browser.close()

if __name__ == "__main__":
    explore_backstage()
