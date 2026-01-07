import time
import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"

def inspect_invite_page():
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
        
        print("\n" + "="*60)
        print("STEP 1: Please navigate MANUALLY to the 'Creator Invite' page.")
        print("Expected path: Relationship Management -> Invite Creators")
        print("Once you are on the page where you can type a username, come back here.")
        print("="*60 + "\n")
        
        # Wait for user signal. In this non-interactive env, I'll wait for a specific element or URL pattern change
        # OR just wait a fixed time (e.g., 60 seconds) and then dump the page.
        
        print("Waiting 60 seconds for you to navigate...")
        time.sleep(60)
        
        print("Time's up! capturing page info...")
        print(f"Current URL: {page.url}")
        
        # Save HTML so I can parse it for selectors
        with open("invite_page_dump.html", "w") as f:
            f.write(page.content())
            
        print("Saved invite_page_dump.html. I will analyze this to build the automator.")
        browser.close()

if __name__ == "__main__":
    inspect_invite_page()
