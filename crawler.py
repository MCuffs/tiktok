import re
import asyncio
import sys
import os
import json
from playwright.async_api import async_playwright

USER_DATA_DIR = "./tiktok_user_data"
OUTPUT_FILE = "streamers_data.json"
TXT_FILE = "active_streamers.txt"

# Limit concurrent pages to avoid detection/resource issues
CONCURRENT_PAGES = 3
TARGET_COUNT = 30

async def crawl_tiktok_live(headless=False):
    print(f"🚀 Starting Async Crawler (Headless: {headless})...")
    
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        chrome_path = None
    
    async with async_playwright() as p:
        # Launch Browser
        args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled"
        ]
        
        launch_args = {
            "user_data_dir": USER_DATA_DIR,
            "headless": headless,
            "args": args,
            "viewport": {'width': 1280, 'height': 800}
        }
        
        if chrome_path:
            launch_args["executable_path"] = chrome_path
        
        context = await p.chromium.launch_persistent_context(**launch_args)
        
        # --- PHASE 1: Collect Streamer IDs ---
        print("\nPhase 1: Collecting Active Streamers from Live Feed...")
        page = context.pages[0] if context.pages else await context.new_page()
        
        seen_ids = set()
        
        try:
            await page.goto("https://www.tiktok.com/live", timeout=60000)
            await asyncio.sleep(5)
            
            # Scroll loop
            for i in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                # Extract links
                # We do this in browser context for speed? Or simple Python parsing
                # Python parsing of hrefs is fine
                links = await page.query_selector_all('a')
                for link in links:
                    href = await link.get_attribute('href')
                    if href:
                         match = re.search(r'/@([^/?]+)', href)
                         if match:
                            uid = match.group(1)
                            if uid not in seen_ids:
                                seen_ids.add(uid)
                
                print(f"  -> Found {len(seen_ids)} unique streamers so far...")
                if len(seen_ids) >= 40: # Buffer
                    break
                    
        except Exception as e:
            print(f"Phase 1 Error: {e}")
            
        streamer_ids_list = list(seen_ids)[:TARGET_COUNT]
        print(f"\nPhase 1 Complete. Target List ({len(streamer_ids_list)}): {streamer_ids_list}")
        
        # --- PHASE 2: Parallel Detail Scraping ---
        print(f"\nPhase 2: Scraping details in parallel ({CONCURRENT_PAGES} tabs)...")
        
        detailed_results = []
        
        # Queue for workers
        queue = asyncio.Queue()
        for uid in streamer_ids_list:
            queue.put_nowait(uid)
            
        async def worker(worker_id):
            # Each worker gets its own page
            worker_page = await context.new_page()
            
            while not queue.empty():
                uid = await queue.get()
                print(f"  [Worker {worker_id}] Processing: {uid}")
                
                result = {
                    "id": uid,
                    "nickname": uid, # Default
                    "followers": "-",
                    "likes": "-",
                    "bio": "",
                    "url": f"https://www.tiktok.com/@{uid}"
                }
                
                try:
                    await worker_page.goto(f"https://www.tiktok.com/@{uid}", timeout=30000)
                    await asyncio.sleep(1.5) # Short wait
                    
                    # Extraction
                    try:
                        # Nickname
                        # Try multiple selectors
                        nick_loc = worker_page.locator('[data-e2e="user-subtitle"]').or_(worker_page.locator('h1[data-e2e="user-title"]')) 
                        if await nick_loc.first.is_visible():
                            result["nickname"] = await nick_loc.first.inner_text()
                            
                        # Followers
                        fol_loc = worker_page.locator('[data-e2e="followers-count"]')
                        if await fol_loc.is_visible():
                            result["followers"] = await fol_loc.inner_text()
                            
                        # Likes
                        like_loc = worker_page.locator('[data-e2e="likes-count"]')
                        if await like_loc.is_visible():
                            result["likes"] = await like_loc.inner_text()
                            
                    except Exception as e:
                        # print(f"    Extract error for {uid}: {e}")
                        pass
                        
                except Exception as e:
                    print(f"  [Worker {worker_id}] Failed to load {uid}: {e}")
                
                detailed_results.append(result)
                queue.task_done()
                
            await worker_page.close()

        # Start workers
        tasks = []
        for i in range(CONCURRENT_PAGES):
            tasks.append(asyncio.create_task(worker(i)))
            
        await asyncio.gather(*tasks)
        
        # Close browser
        await context.close()
        
    # --- Save Results ---
    print(f"\nCrawling Finished! Saving {len(detailed_results)} profiles.")
    
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(detailed_results, f, ensure_ascii=False, indent=2)
            
        # Also update TXT
        with open(TXT_FILE, "w", encoding="utf-8") as f:
            for s in detailed_results:
                f.write(s["id"] + "\n")
                
        print("Files saved successfully.")
        
    except Exception as e:
        print(f"File Save Error: {e}")


if __name__ == "__main__":
    use_headless = "--headless" in sys.argv
    asyncio.run(crawl_tiktok_live(headless=use_headless))
