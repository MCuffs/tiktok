import time
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"

def debug_page_inputs():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    with sync_playwright() as p:
        print("Connecting to browser...")
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                executable_path=chrome_path,
                headless=False,
                args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
                viewport=None
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            print("dumping page info...")
            print(f"URL: {page.url}")
            
            inputs = page.query_selector_all('input')
            print(f"Found {len(inputs)} inputs:")
            for i, inp in enumerate(inputs):
                try:
                    ph = inp.get_attribute('placeholder')
                    typ = inp.get_attribute('type')
                    cls = inp.get_attribute('class')
                    vis = inp.is_visible()
                    print(f"  [{i}] Type: {typ}, Placeholder: '{ph}', Class: '{cls}', Visible: {vis}")
                except:
                    pass
                    
            textareas = page.query_selector_all('textarea')
            print(f"Found {len(textareas)} textareas:")
            for i, ta in enumerate(textareas):
                 print(f"  [{i}] Textarea")

        except Exception as e:
            print(f"Error: {e}")
            
        print("Closing in 5s...")
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    debug_page_inputs()
