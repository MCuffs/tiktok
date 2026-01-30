import time
import os
import sys
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"
CREATOR_FILE = "active_streamers.txt"
RESULTS_FILE = "agency_status_results.txt"

def run_backstage_work():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    with sync_playwright() as p:
        print("Launching browser (Optimized Mode)...")
        # Add flags to try to restore session better?
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=chrome_path,
            headless=False,
            # Stealth args
            args=[
                "--no-first-run", 
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--ignore-certificate-errors",
                "--no-sandbox"
            ],
            viewport=None
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()

        # --- RESOURCE BLOCKING ---
        # Block heavy assets for speed
        page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["image", "media", "font"] 
            else route.continue_() # Keep CSS for layout visibility in headed mode
        )

        # --- STEALTH SCRIPT (Manual Injection) ---
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        
        print("\n" + "="*80)
        print(" SORRY! The browser had to restart.")
        print(" PLEASE NAVIGATE AGAIN TO:")
        print(" 1. Creator -> Relationship Management -> Invite Creators")
        print(" 2. Click 'Add Creator' to open the popup.")
        print("="*80 + "\n")
        
        target_input = None
        max_wait = 600
        start_time = time.time()
        
        print("Searching for inputs...")
        
        while time.time() - start_time < max_wait:
            elapsed = int(time.time() - start_time)
            
            try:
                # Find ALL visible text inputs
                inputs = page.locator("input[type='text']:visible, input[type='search']:visible, input:not([type]):visible").all()
                
                if len(inputs) > 0:
                    if elapsed % 5 == 0:
                        print(f"I see {len(inputs)} visible inputs.")
                    
                    # Heuristics
                    for i, inp in enumerate(inputs):
                        ph = (inp.get_attribute("placeholder") or "").lower()
                        lbl = (inp.get_attribute("aria-label") or "").lower()
                        
                        # Debug print first few times
                        if elapsed < 10:
                            print(f"  Input #{i}: placeholder='{ph}', label='{lbl}'")

                        # If we see obvious keywords
                        if any(x in ph for x in ["name", "id", "search", "검색", "초대", "invite", "username"]) or \
                           any(x in lbl for x in ["search", "검색"]):
                               target_input = inp
                               print(f"\nTARGET ACQUIRED: Input with placeholder '{ph}'")
                               break
                
                # If no obvious keyword but there is exactly 1 visible input in a dialog
                if not target_input:
                     dialog_inputs = page.locator("div[role='dialog'] input:visible").all()
                     if len(dialog_inputs) == 1:
                         target_input = dialog_inputs[0]
                         print("\nTARGET ACQUIRED: The only input in the dialog.")
                
                if target_input:
                    break
                    
            except Exception as e:
                # print(e)
                pass
            
            time.sleep(1)
            
        if not target_input:
            print("Timeout. Could not find search input.")
            browser.close()
            return

        print("Automation starting in 3s...")
        time.sleep(3)
        
        streamers = []
        if os.path.exists(CREATOR_FILE):
            with open(CREATOR_FILE, "r") as f:
                streamers = [line.strip() for line in f if line.strip()]
        
        results = []
        
        for streamer in streamers:
            print(f"Checking: {streamer}")
            try:
                target_input.click()
                target_input.fill("")
                target_input.type(streamer, delay=50)
                target_input.press("Enter")
                
                time.sleep(3)
                
                # Broad text content check
                content_text = page.inner_text("body")
                
                status = "Unknown"
                if "No results" in content_text or "검색 결과 없음" in content_text or "일치하는" in content_text:
                    status = "Not Found"
                elif any(x in content_text for x in ["Invited", "초대됨", "Joined", "가입됨", "Signed", "계약됨", "Bound"]):
                    status = "Already in Agency"
                elif any(x in content_text for x in ["Invite", "초대", "Add", "추가"]):
                     status = "Available"
                     results.append(streamer)
                else:
                    status = "Unclear"
                
                print(f"  -> Result: {status}")
                
            except Exception as e:
                print(f"  -> Error: {e}")
                
        with open(RESULTS_FILE, "w") as f:
            for r in results:
                f.write(r + "\n")
                
        print(f"\nSaved {len(results)} available creators to {RESULTS_FILE}")
        time.sleep(600) # Keep browser open for user to review
        browser.close()

if __name__ == "__main__":
    run_backstage_work()
