import time
import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./tiktok_user_data"
CREATOR_FILE = "active_streamers.txt"
RESULTS_FILE = "agency_status_results.txt"

def interactive_checker():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=chrome_path,
            headless=False,
            args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
            viewport=None
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://live-backstage.tiktok.com/", timeout=60000)
        
        print("\n" + "="*50)
        print("ACTION REQUIRED:")
        print("1. In the open browser, navigate to 'Relationship Management' -> 'Invite Creators'.")
        print("2. Make sure the input field for 'Username' or 'ID' is visible.")
        print("3. come back here and press ENTER to continue.")
        print("="*50 + "\n")
        
        # In this environment, I cannot read stdin.
        # I will use a loop that checks for a specific file trigger or just wait a long time loop.
        # I'll wait for a file "ready.trigger" to be created by me or just wait for 45 seconds.
        # Since I can't ask user to create a file easily...
        # I will loop and print "Waiting..." every 5 seconds for 60 seconds.
        # BUT I can attempt to 'detect' the page.
        
        input_selector = None
        
        for i in range(12): # 60 seconds
            print(f"Waiting for you to navigate... ({i*5}s)")
            content = page.content()
            
            # Simple heuristic detection of the invite page inputs
            # Look for placeholders
            if "Enter username" in content or "Enter ID" in content or "초대할" in content or "크리에이터 검색" in content:
                print("Potential Invite page detected!")
                # Try to find the input selector
                # Common inputs have type="text" and maybe specific classes
                pass
            
            time.sleep(5)
            
        print("Time is up. I will now attempt to identify the input field automatically.")
        
        # 1. Try to find the main search input
        # We look for an input that is likely the user search box.
        try:
            # Try generic selectors first
            inputs = page.query_selector_all('input[type="text"]')
            target_input = None
            
            # Filter inputs to find the relevant one
            print(f"Found {len(inputs)} text inputs.")
            for inp in inputs:
                ph = inp.get_attribute('placeholder') or ""
                print(f"Input placeholder: {ph}")
                if "name" in ph.lower() or "id" in ph.lower() or "search" in ph.lower() or "검색" in ph:
                    target_input = inp
                    break
            
            if not target_input and inputs:
                target_input = inputs[0] # Fallback to first input
            
            if target_input:
                print("Target input found. Starting checks...")
                target_input.click()
                
                # Load streamers
                if os.path.exists(CREATOR_FILE):
                    with open(CREATOR_FILE, "r") as f:
                        streamers = [line.strip() for line in f if line.strip()]
                else:
                    streamers = ["test_user"]
                
                not_in_agency_list = []
                
                for streamer in streamers:
                    print(f"Checking {streamer}...")
                    target_input.fill("")
                    target_input.type(streamer, delay=50)
                    target_input.press("Enter")
                    time.sleep(3) # Wait for search result
                    
                    # Capture result
                    # Heuristic: look for text indicating status
                    body_text = page.inner_text("body")
                    
                    # Save status to file
                    # We look for keywords like "Invited", "Signed", "Available"
                    # This part is tricky without seeing the UI. 
                    # Assuming we just log the presence of keywords.
                    
                    status = "Unknown"
                    if "Already" in body_text or "가입" in body_text:
                        status = "In Agency"
                    elif "Invite" in body_text or "초대" in body_text: 
                        status = "Not in Agency" #(likely)
                        not_in_agency_list.append(streamer)
                    else:
                        status = "Investigate"
                        
                    print(f"  -> Status: {status}")
                
                # Save results
                with open(RESULTS_FILE, "w") as f:
                    for s in not_in_agency_list:
                        f.write(s + "\n")
                print(f"Saved candidate list to {RESULTS_FILE}")
                
            else:
                print("Could not find a suitable input field. Please check the screenshot 'page_debug.png'.")
                page.screenshot(path="page_debug.png")
                
        except Exception as e:
            print(f"Error during automation: {e}")
            page.screenshot(path="error_debug.png")

        browser.close()

if __name__ == "__main__":
    interactive_checker()
