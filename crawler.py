import re
import random
import asyncio
import sys
import os
import json
import math
from playwright.async_api import async_playwright

USER_DATA_DIR = "./tiktok_user_data"
OUTPUT_FILE = "streamers_data.json"

# 🌊 SIMULATED LIVE FEED KEYWORDS (Fallback)
FEED_CLUSTERS = [
    "라이브", "소통", "수다", "잡담", 
    "게임", "리그오브레전드", "발로란트", "배그", "마인크래프트", 
    "노래", "연주", "버스킹", "피아노", 
    "먹방", "요리", "음식", 
    "그림", "공부", "운동", 
    "Just Chatting", "Live", "Gaming", "Kpop", "Dance"
]

# --- 🎭 HUMAN SIMULATION UTILS ---
async def human_like_mouse_move(page, start_x, start_y, end_x, end_y, steps=25):
    # Simple Bezier Curve simulation
    # Control point for curve
    ctrl_x = (start_x + end_x) / 2 + random.randint(-100, 100)
    ctrl_y = (start_y + end_y) / 2 + random.randint(-100, 100)
    
    for i in range(steps + 1):
        t = i / steps
        # Quadratic Bezier
        x = (1 - t)**2 * start_x + 2 * (1 - t) * t * ctrl_x + t**2 * end_x
        y = (1 - t)**2 * start_y + 2 * (1 - t) * t * ctrl_y + t**2 * end_y
        
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.005, 0.015))

async def human_scroll(page):
    # Variable speed scroll
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(300, 700)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.5, 1.5))

async def crawl_tiktok_live():
    print("🚀 Starting Crawler (Human Simulation Mode)...")
    collected_streamers = {}
    
    async with async_playwright() as p:
        args = [
            "--no-first-run", "--disable-blink-features=AutomationControlled", 
            "--disable-infobars", "--exclude-switches=enable-automation",
            "--disable-dev-shm-usage", "--disable-gpu",
        ]
        launch_args = {
            "user_data_dir": USER_DATA_DIR,
            "headless": False,
            "args": args,
            "viewport": {'width': 1280 + random.randint(0, 50), 'height': 800 + random.randint(0, 50)},
            "ignore_default_args": ["--enable-automation"]
        }
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(chrome_path): launch_args["executable_path"] = chrome_path
        
        context = await p.chromium.launch_persistent_context(**launch_args)
        page = context.pages[0] if context.pages else await context.new_page()
        
        # --- 🕵️‍♂️ DEEP STEALTH INJECTION v2 ---
        await page.add_init_script("""
            // 1. Mask WebDriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // 2. Mask Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: 'denied' }) :
                originalQuery(parameters)
            );
            
            // 3. Mock Plugins
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            
            // 4. Mock Chrome Runtime
            window.chrome = { runtime: {} };
        """)
        
        # --- [CORE] Network Interception ---
        async def handle_response(response):
            try:
                url = response.url
                if "json" not in response.headers.get("content-type", ""): return

                if "/api/search/item" in url or "/api/search/user" in url or "webcast" in url:
                    try:
                        data = await response.json()
                        extract_live_users(data)
                    except: pass
            except: pass

        def extract_live_users(obj):
            if isinstance(obj, dict):
                if "owner" in obj and ("roomId" in obj or "room_id" in obj):
                    process_user(obj["owner"], obj)
                elif "user" in obj:
                    process_user(obj["user"], obj)
                elif "user_info" in obj:
                    process_user(obj["user_info"], obj)
                for v in obj.values():
                    extract_live_users(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_live_users(item)

        def process_user(owner, source_obj):
            if not owner or not isinstance(owner, dict): return
            uid = owner.get("uniqueId") or owner.get("display_id")
            if not uid: return
            
            room_id = str(source_obj.get("room_id") or source_obj.get("roomId", "") or owner.get("roomId", "") or "0")
            if not room_id or room_id == "0": return 
            
            # Simplified Agency Filter
            nickname = owner.get("nickname", "")
            if "Official" in nickname or "Shop" in nickname: return

            if uid not in collected_streamers:
                collected_streamers[uid] = {
                    "id": uid, 
                    "nickname": nickname, 
                    "room_id": room_id,
                    "url": f"https://www.tiktok.com/@{uid}"
                }
                print(f"    ✨ Captured: {uid}")
                if len(collected_streamers) % 2 == 0:
                     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(list(collected_streamers.values()), f, ensure_ascii=False, indent=2)

        page.on("response", handle_response)
        
        # --- STRATEGY: HUMAN TRY /LIVE FIRST ---
        print("🧠 Phase 1: Attempting Human-like /live access...")
        try:
            await page.goto("https://www.tiktok.com/live", timeout=45000, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(4, 7)) # Human pause
            
            # Human Mouse Move to Center
            await human_like_mouse_move(page, 100, 100, 640, 400)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Human Scroll
            await human_scroll(page)
            await asyncio.sleep(random.uniform(2, 4))
            
            if len(collected_streamers) > 0:
                print("✅ /live Feed Success! (Stealth Worked)")
        except Exception as e:
            print(f"⚠️ /live access failed: {e}")
            
        # --- FALLBACK: SIMULATED FEED ---
        if len(collected_streamers) == 0:
            print("\n🔄 Switching to Phase 2: Simulated Feed (Fallback)...")
            random.shuffle(FEED_CLUSTERS)
            for keyword in FEED_CLUSTERS:
                if len(collected_streamers) >= 200: break
                
                print(f"   🔍 Cluster: '{keyword}'")
                try:
                    await page.goto(f"https://www.tiktok.com/search/user?q={keyword}", timeout=30000, wait_until="domcontentloaded")
                    await asyncio.sleep(random.uniform(3, 5))
                    await human_scroll(page)
                except: pass

        await context.close()

if __name__ == "__main__":
    asyncio.run(crawl_tiktok_live())
