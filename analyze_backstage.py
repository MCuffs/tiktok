import time
import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"

def analyze():
    print("Launching Analyzer...")
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=chrome_path,
            headless=False,
            args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
            viewport={'width': 1280, 'height': 800}
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        url = "https://live-backstage.tiktok.com/"
        print(f"Navigating to {url}...")
        try:
            page.goto(url, timeout=60000)
            time.sleep(15) # Wait for SPA to render
            
            # Dump full content
            content = page.content()
            with open("backstage_full.html", "w") as f:
                f.write(content)
            print("Saved backstage_full.html")
            
            # Look for specific keywords in links
            links = page.query_selector_all('a')
            print(f"Found {len(links)} links.")
            for link in links:
                txt = link.inner_text()
                href = link.get_attribute('href')
                if txt and ("Invite" in txt or "초대" in txt or "Creator" in txt or "크리에이터" in txt):
                    print(f"Potential Menu: Text='{txt}', Href='{href}'")
                    
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    analyze()
