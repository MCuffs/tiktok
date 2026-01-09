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
            "headless": False,  # Keep visible for better success rate
            "args": args,
            "viewport": {'width': 1280, 'height': 800},
            # Minimize window to reduce distraction
            "ignore_default_args": ["--enable-automation"]
        }
        
        if chrome_path:
            launch_args["executable_path"] = chrome_path
        
        context = await p.chromium.launch_persistent_context(**launch_args)
        
        # --- PHASE 1: Collect Streamer IDs from Multiple Categories ---
        print("\nPhase 1: Collecting Active Streamers from Live Feed...")
        page = context.pages[0] if context.pages else await context.new_page()
        
        seen_ids = set()
        
        # Multiple categories to crawl
        categories = [
            "https://www.tiktok.com/live",
            "https://www.tiktok.com/live/gaming",
            "https://www.tiktok.com/live/music",
            "https://www.tiktok.com/live/sports",
            "https://www.tiktok.com/live/entertainment"
        ]
        
        for category_url in categories:
            try:
                print(f"  📂 Visiting: {category_url}")
                await page.goto(category_url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                # Scroll more aggressively
                for i in range(10):  # Increased from 5 to 10
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)
                    
                    # Extract links after each scroll
                    links = await page.query_selector_all('a')
                    for link in links:
                        href = await link.get_attribute('href')
                        if href:
                            # Match both /live and regular profile links
                            match = re.search(r'/@([^/?]+)', href)
                            if match:
                                uid = match.group(1)
                                uid_lower = uid.lower()
                                
                                # Filter out unwanted IDs
                                # - Exclude official TikTok accounts
                                # - Exclude generic user IDs that START with 'user' (e.g., user123456)
                                if (uid not in seen_ids and 
                                    uid not in ['live', 'foryou', 'following'] and
                                    'tiktok' not in uid_lower and
                                    not uid_lower.startswith('user')):
                                    seen_ids.add(uid)
                    
                    print(f"    -> Found {len(seen_ids)} unique streamers so far...")
                    
                    # Early exit if we have enough
                    if len(seen_ids) >= 50:
                        break
                        
            except Exception as e:
                print(f"  ⚠️ Error visiting {category_url}: {e}")
                continue
            
            # Stop if we have enough candidates
            if len(seen_ids) >= 50:
                break
        
        streamer_ids_list = list(seen_ids)[:TARGET_COUNT]
        print(f"\n✅ Phase 1 Complete. Collected {len(streamer_ids_list)} streamers for detailed scraping.")
        
        if len(streamer_ids_list) == 0:
            print("❌ No streamers found. Check your login session or network connection.")
            await context.close()
            return
        
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
                    await worker_page.goto(f"https://www.tiktok.com/@{uid}", timeout=30000, wait_until="domcontentloaded")
                    await asyncio.sleep(2) # Wait for dynamic content
                    
                    # Extraction with multiple selector attempts
                    try:
                        # Nickname - try multiple selectors
                        nick_selectors = [
                            '[data-e2e="user-subtitle"]',
                            'h1[data-e2e="user-title"]',
                            'h2[data-e2e="user-title"]',
                            '[data-e2e="user-page-nickname"]'
                        ]
                        for selector in nick_selectors:
                            try:
                                nick_el = await worker_page.wait_for_selector(selector, timeout=3000)
                                if nick_el:
                                    result["nickname"] = await nick_el.inner_text()
                                    break
                            except:
                                continue
                        
                        # Followers
                        try:
                            fol_el = await worker_page.wait_for_selector('[data-e2e="followers-count"]', timeout=3000)
                            if fol_el:
                                result["followers"] = await fol_el.inner_text()
                        except:
                            pass
                        
                        # Likes
                        try:
                            like_el = await worker_page.wait_for_selector('[data-e2e="likes-count"]', timeout=3000)
                            if like_el:
                                result["likes"] = await like_el.inner_text()
                        except:
                            pass
                        
                    except Exception as e:
                        pass
                        
                except Exception as e:
                    print(f"  [Worker {worker_id}] ⚠️ Failed to load {uid}: {e}")
                
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
    print(f"\n✅ Crawling Finished! Saving {len(detailed_results)} profiles.")
    
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(detailed_results, f, ensure_ascii=False, indent=2)
            
        # Also update TXT
        with open(TXT_FILE, "w", encoding="utf-8") as f:
            for s in detailed_results:
                f.write(s["id"] + "\n")
                
        print(f"💾 Files saved successfully to {OUTPUT_FILE} and {TXT_FILE}")
        
    except Exception as e:
        print(f"❌ File Save Error: {e}")


if __name__ == "__main__":
    use_headless = "--headless" in sys.argv
    asyncio.run(crawl_tiktok_live(headless=use_headless))
