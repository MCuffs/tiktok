import time
from playwright.sync_api import sync_playwright
import os

USER_DATA_DIR = "./tiktok_user_data"

def setup_login():
    print("Starting Login Setup with real Chrome...")
    
    # Common paths for Google Chrome on Mac
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    if not os.path.exists(chrome_path):
        print(f"Start failed: Google Chrome not found at {chrome_path}")
        print("Please ensure Google Chrome is installed in the default location.")
        return

    with sync_playwright() as p:
        # Use launch_persistent_context to maintain a real profile
        # We point to the executable_path of the real Chrome
        # We assume the user has not modified the default path
        
        args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled" # Helps hide automation
        ]

        print(f"Launching Chrome from: {chrome_path}")
        print(f"User Data Directory: {USER_DATA_DIR}")
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=chrome_path,
            headless=False,
            args=args,
            viewport=None # Let window decide size
        )
        
        page = browser.pages[0]
        
        print("Navigating to TikTok Login (KR)...")
        # Go to KR main first then login, or direct KR login
        page.goto("https://www.tiktok.com/ko-KR/")
        time.sleep(2)
        
        # Click login button or go to url
        page.goto("https://www.tiktok.com/login?lang=ko-KR")
        
        print("\n" + "="*50)
        print("PLEASE LOG IN MANUALLY IN THE OPEN BROWSER WINDOW.")
        print("Google Login should work better now.")
        print("Once you are logged in successfully, press ENTER in this terminal to save and exit.")
        print("="*50 + "\n")
        
        # Wait for user confirmation in terminal (since we can't reliably detect login success for google 100% without flake)
        # But since I am running this via tool, I can't interact with stdin easily in real-time for the user.
        # Instead, I will poll for a success indicator or just wait a long time.
        
        # Better approach for this environment:
        # Loop check for login success indicator.
        
        for i in range(120): # Wait up to 10 minutes (120 * 5s)
            try:
                if page.is_closed():
                    break
                    
                # Check for profile icon
                if page.query_selector('[data-e2e="profile-icon"]'):
                    print("Login detected! Profile icon found.")
                    break
                
                # Check URL
                if page.url == "https://www.tiktok.com/" or "/foryou" in page.url:
                     # Double check we aren't just on homepage guest
                     if page.query_selector('[data-e2e="profile-icon"]'):
                         print("Login detected!")
                         break

                print(f"Waiting for login... ({i*5}s)")
                time.sleep(5)
            except Exception as e:
                print(f"Browser might be closed: {e}")
                break
                
        print("Closing browser and saving state to disk (via persistent context)...")
        browser.close()
        print("Setup complete.")

if __name__ == "__main__":
    setup_login()
