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
TARGET_QUALIFIED_COUNT = 50

def parse_count(count_str):
    """
    Parses follower/like count strings like "1.2K", "300", "5M" into integers.
    Returns 0 if parsing fails or input is invalid.
    """
    if not count_str or count_str == '-':
        return 0
    
    count_str = count_str.upper().strip()
    multiplier = 1
    
    if 'K' in count_str:
        multiplier = 1000
        count_str = count_str.replace('K', '')
    elif 'M' in count_str:
        multiplier = 1000000
        count_str = count_str.replace('M', '')
    elif 'B' in count_str:
        multiplier = 1000000000
        count_str = count_str.replace('B', '')
        
    try:
        return int(float(count_str) * multiplier)
    except:
        return 0

async def crawl_tiktok_live(headless=False):
    print(f"🚀 Starting Simple Crawler (Headless: {headless})...")
    
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        chrome_path = None
    
    async with async_playwright() as p:
        args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--ignore-certificate-errors",
            "--disable-blink-features=AutomationControlled",
            "--window-size=500,600",
            "--window-position=5000,5000" # Bottom-right (clamped)
        ]
        
        launch_args = {
            "user_data_dir": USER_DATA_DIR,
            "headless": False, 
            "args": args,
            "viewport": {'width': 1280, 'height': 800},
        }
        
        if chrome_path:
            launch_args["executable_path"] = chrome_path
        
        context = await p.chromium.launch_persistent_context(**launch_args)
        
        # Block unnecessary resources for speed
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,mp4,woff,woff2}", lambda route: route.abort())
        
        # --- PHASE 1: Collect Candidates ---
        print("\nPhase 1: collecting candidates...")
        page = context.pages[0] if context.pages else await context.new_page()
        
        candidates = set()
        
        # Only visit main categories once
        categories = [
            "https://www.tiktok.com/live",
            "https://www.tiktok.com/live/gaming",
            "https://www.tiktok.com/live/music"
        ]
        
        for url in categories:
            try:
                print(f"  📂 Visiting: {url}")
                await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                # Scroll 5 times per category
                for i in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)
                    
                    links = await page.query_selector_all('a')
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and '/@' in href:
                             match = re.search(r'/@([^/?]+)', href)
                             if match:
                                 uid = match.group(1)
                                 if uid not in candidates:
                                     candidates.add(uid)
                    
                    if len(candidates) > 70: break
            except Exception as e:
                print(f"Error visiting {url}: {e}")
            
            if len(candidates) > 70: break
            
        candidate_list = list(candidates)[:70] # Max 70 candidates to process
        print(f"✅ Found {len(candidate_list)} candidates. Starting details scrape...")
        
        # --- PHASE 2: Scrape Details ---
        detailed_results = []
        queue = asyncio.Queue()
        for uid in candidate_list:
            queue.put_nowait(uid)
            
        async def worker(wid):
            wpage = await context.new_page()
            while not queue.empty():
                uid = await queue.get()
                try:
                    await wpage.goto(f"https://www.tiktok.com/@{uid}", timeout=30000, wait_until="domcontentloaded")
                    await asyncio.sleep(1)
                    
                    # Extract Data
                    nick = uid
                    followers = "0"
                    likes = "-"
                    
                    try:
                        el = await wpage.query_selector('[data-e2e="user-subtitle"]') or await wpage.query_selector('h1[data-e2e="user-title"]')
                        if el: nick = await el.inner_text()
                    except: pass
                    
                    try:
                        el = await wpage.query_selector('[data-e2e="followers-count"]')
                        if el: followers = await el.inner_text()
                    except: pass
                    
                    try:
                        el = await wpage.query_selector('[data-e2e="likes-count"]')
                        if el: likes = await el.inner_text()
                    except: pass
                    
                    # Check Filter
                    count = parse_count(followers)
                    if count >= 150:
                        print(f"  [{wid}] ✅ {uid} ({followers})")
                        detailed_results.append({
                            "id": uid,
                            "nickname": nick,
                            "followers": followers,
                            "likes": likes,
                            "url": f"https://www.tiktok.com/@{uid}"
                        })
                    else:
                        print(f"  [{wid}] ❌ {uid} (Too few followers: {followers})")
                        
                except Exception as e:
                    print(f"  [{wid}] Error {uid}: {e}")
                
                queue.task_done()
            await wpage.close()
            
        tasks = [asyncio.create_task(worker(i)) for i in range(CONCURRENT_PAGES)]
        await asyncio.gather(*tasks)
        
        await context.close()
        
    # --- Save ---
    # Take top 50
    final_results = detailed_results[:50]
    print(f"\n✅ Finished. Saving {len(final_results)} profiles.")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
        
    with open(TXT_FILE, "w", encoding="utf-8") as f:
        for s in final_results:
            f.write(s["id"] + "\n")


if __name__ == "__main__":
    use_headless = "--headless" in sys.argv
    asyncio.run(crawl_tiktok_live(headless=use_headless))
