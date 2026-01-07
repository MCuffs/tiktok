import time
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"

def inspect():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with sync_playwright() as p:
        print("Attaching to browser...")
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                executable_path=chrome_path,
                headless=False,
                args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
                viewport=None
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            print(f"URL: {page.url}")
            print("Looking for visible inputs...")
            
            inputs = page.locator("input:visible").all()
            print(f"Found {len(inputs)} visible inputs.")
            
            for i, inp in enumerate(inputs):
                try:
                    ph = inp.get_attribute("placeholder") or "No placeholder"
                    cls = inp.get_attribute("class") or "No class"
                    outer = inp.evaluate("el => el.outerHTML")
                    print(f"Input {i}: Placeholder='{ph}', Class='{cls}'")
                    print(f"   HTML: {outer[:100]}...") 
                except:
                    pass
            
            print("Looking for visible buttons in dialogs...")
            btns = page.locator("div[role='dialog'] button:visible").all()
            for i, btn in enumerate(btns):
                 txt = btn.inner_text()
                 print(f"Button {i} in dialog: '{txt}'")
                 
        except Exception as e:
            print(f"Error: {e}")
            
        print("Closing debug...")
        browser.close()

if __name__ == "__main__":
    inspect()
