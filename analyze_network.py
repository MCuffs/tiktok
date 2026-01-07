import json
from playwright.sync_api import sync_playwright

def inspect_network():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("Listening to network traffic on TikTok Live...")
        
        def handle_response(response):
            # TikTok live feed endpoints usually contain 'webcast' or 'room/list'
            if "webcast" in response.url and "json" in response.headers.get("content-type", ""):
                print(f"Captured Response: {response.url}")
                try:
                    data = response.json()
                    # Print keys to see if we have user stats
                    # Usually data['data']['user'] or similar
                    print("Keys:", data.keys())
                    
                    # Dump a sample to file
                    with open("network_sample.json", "w") as f:
                        json.dump(data, f, indent=2)
                        
                except:
                    pass

        page.on("response", handle_response)
        page.goto("https://www.tiktok.com/live")
        
        # Scroll a bit
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(5000)
        
        browser.close()

if __name__ == "__main__":
    inspect_network()
