import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright
from datetime import datetime

USER_DATA_DIR = "./tiktok_user_data"
VERIFICATION_FILE = "verified_creators.json"
STREAMERS_FILE = "streamers_data.json"

async def verify_creators_on_backstage(headless=False):
    """
    Opens backstage invitation page, pastes creator IDs, and filters for "사용 가능" (available) creators.
    """
    print("🚀 Starting Creator Verification on Backstage...")
    
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        chrome_path = None
    
    try:
        # Load current streamers
        streamers = []
        if os.path.exists(STREAMERS_FILE):
            with open(STREAMERS_FILE, 'r', encoding='utf-8') as f:
                streamers = json.load(f)
        else:
            print(f"❌ {STREAMERS_FILE} not found. Run crawler.py first.")
            return
        
        if not streamers:
            print("❌ No streamers to verify. Run crawler.py first.")
            return
        
        creator_ids = [s['id'] for s in streamers]
        print(f"📋 Loaded {len(creator_ids)} creators for verification")
        
        async with async_playwright() as p:
            # Launch browser
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
                "viewport": {'width': 1920, 'height': 1080},
                "ignore_default_args": ["--enable-automation"]
            }
            
            if chrome_path:
                launch_args["executable_path"] = chrome_path
            
            context = await p.chromium.launch_persistent_context(**launch_args)
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Navigate to backstage invitation page
            backstage_url = "https://live-backstage.tiktok.com/portal/anchor/relation"
            print(f"\n🌐 Opening: {backstage_url}")
            await page.goto(backstage_url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            # Wait for page to fully load
            try:
                await page.wait_for_selector('button, input[type="text"]', timeout=10000)
            except:
                print("⚠️  Page elements might not be visible yet, continuing...")
            
            # Step 1: Navigate through backstage to get verification status
            print("🔍 Step 1: Navigating backstage invitation flow...")
            await asyncio.sleep(3)
            
            # Step 2: Click on each creator ID and check their status
            print("\n📋 Step 2: Clicking on creator IDs to check status...")
            available_creators = []
            
            for idx, creator_id in enumerate(creator_ids[:30]):  # Limit to first 30
                try:
                    print(f"\n  [{idx+1}/{min(len(creator_ids), 30)}] Checking: {creator_id}")
                    
                    # Try to find and click the creator ID link/button
                    clicked = await click_creator_id(page, creator_id)
                    
                    if clicked:
                        await asyncio.sleep(2)
                        
                        # Check the status after clicking
                        status = await check_creator_status(page, creator_id)
                        
                        if status == "사용 가능":
                            print(f"  ✅ Available: {creator_id}")
                            
                            # Find matching creator info
                            for streamer in streamers:
                                if streamer['id'].lower() == creator_id.lower():
                                    available_creators.append({
                                        "id": streamer['id'],
                                        "nickname": streamer.get('nickname', streamer['id']),
                                        "followers": streamer.get('followers', '-'),
                                        "status": "사용 가능"
                                    })
                                    break
                        else:
                            print(f"  ❌ Not available or pending: {creator_id} (Status: {status})")
                        
                        # Go back to the list to check next creator
                        try:
                            await page.go_back()
                            await asyncio.sleep(1)
                        except:
                            pass
                    else:
                        print(f"  ⚠️  Could not click on {creator_id}")
                
                except Exception as e:
                    print(f"  ⚠️  Error processing {creator_id}: {e}")
                    continue
            
            # Save verification results
            if available_creators:
                verification_data = {
                    "verified_at": datetime.now().isoformat(),
                    "total_checked": len(creator_ids),
                    "available_count": len(available_creators),
                    "available_creators": available_creators
                }
                
                with open(VERIFICATION_FILE, 'w', encoding='utf-8') as f:
                    json.dump(verification_data, f, ensure_ascii=False, indent=2)
                
                print(f"\n✅ Verification complete!")
                print(f"📊 Available creators: {len(available_creators)} / {len(creator_ids)}")
                print(f"💾 Results saved to {VERIFICATION_FILE}")
                
                # Print available creators
                print("\n🎉 Available Creators:")
                for creator in available_creators[:10]:  # Show first 10
                    print(f"  - {creator['id']} ({creator['nickname']})")
                if len(available_creators) > 10:
                    print(f"  ... and {len(available_creators) - 10} more")
            else:
                print("❌ No available creators found. Status page might have different layout.")
            
            # Keep browser open for manual verification if needed
            if not headless:
                print("\n👀 Browser will remain open for manual verification. Press Ctrl+C to close.")
                try:
                    await asyncio.sleep(300)  # Keep open for 5 minutes
                except KeyboardInterrupt:
                    print("Closing browser...")
            
            await context.close()
    
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

async def extract_available_creators(page, streamers):
    """
    Parse the backstage page to extract creators with "사용 가능" status.
    """
    available = []
    
    try:
        # Wait for results to load
        await asyncio.sleep(2)
        
        # Get page HTML for debugging
        page_content = await page.content()
        
        # Try multiple selectors to find creator rows/cards
        selectors = [
            'div[class*="relation"]',
            'div[class*="creator"]',
            'div[class*="host"]',
            'tr',  # If it's a table
            'li[class*="item"]',
            'div[role="listitem"]',
            '[class*="card"]',
            '[class*="row"]',
            'div[class*="status"]'
        ]
        
        found_any = False
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    print(f"Found {len(elements)} elements with selector: {selector}")
                    found_any = True
                    
                    for elem in elements:
                        try:
                            text_content = await elem.text_content()
                            
                            # Check if this element contains "사용 가능" (available)
                            if text_content and "사용 가능" in text_content:
                                # Try to extract creator ID from the element
                                creator_id = extract_creator_id_from_text(text_content)
                                
                                if creator_id:
                                    # Find matching creator in streamers list
                                    for streamer in streamers:
                                        if streamer['id'].lower() == creator_id.lower():
                                            available.append({
                                                "id": streamer['id'],
                                                "nickname": streamer.get('nickname', streamer['id']),
                                                "followers": streamer.get('followers', '-'),
                                                "status": "사용 가능"
                                            })
                                            break
                        except:
                            continue
            except:
                continue
        
        if not found_any:
            print("⚠️  No matching selectors found. Trying to extract from page text...")
            # Last resort: search entire page content for "사용 가능" mentions
            page_text = await page.text_content()
            if "사용 가능" in page_text:
                print("Found '사용 가능' in page content")
                # Try to match creator IDs from the streamers list
                for streamer in streamers:
                    if streamer['id'] in page_text:
                        available.append({
                            "id": streamer['id'],
                            "nickname": streamer.get('nickname', streamer['id']),
                            "followers": streamer.get('followers', '-'),
                            "status": "사용 가능"
                        })
    
    except Exception as e:
        print(f"Error extracting available creators: {e}")
    
    return available

def extract_creator_id_from_text(text):
    """
    Extract creator ID from text content.
    Looks for @username or plain username patterns.
    """
    import re
    
    # First, try to match @username pattern
    match = re.search(r'@([a-zA-Z0-9._-]+)', text)
    if match:
        return match.group(1)
    
    # Try to match username at the start of lines (common pattern in tables)
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip common status/label words
        skip_words = ['status', 'available', 'pending', '사용', '가능', 'followers', '팔로워', '상태', 
                      'name', '이름', 'user', 'nickname', 'id', 'id:', 'username', 'account']
        
        # If line is too short or contains spaces, likely not a username
        if 3 <= len(line) <= 50 and not any(word.lower() in line.lower() for word in skip_words):
            # Check if it looks like a username (alphanumeric, dots, underscores, hyphens)
            if re.match(r'^[a-zA-Z0-9._-]+$', line):
                return line
    
    return None

async def click_creator_id(page, creator_id):
    """
    Try to find and click on a creator ID link/button on the backstage page.
    Returns True if successfully clicked, False otherwise.
    """
    try:
        # Try multiple selector strategies to find the creator ID element
        selectors = [
            f'a:has-text("{creator_id}")',  # Link with creator ID text
            f'button:has-text("{creator_id}")',  # Button with creator ID text
            f'div:has-text("{creator_id}")',  # Div with creator ID text
            f'span:has-text("{creator_id}")',  # Span with creator ID text
        ]
        
        # Try to find element by text content first
        all_elements = await page.query_selector_all('a, button, div, span')
        for elem in all_elements:
            try:
                text = await elem.text_content()
                if text and creator_id in text:
                    # Check if element is clickable
                    is_visible = await elem.is_visible()
                    if is_visible:
                        await elem.click()
                        return True
            except:
                continue
        
        return False
    
    except Exception as e:
        print(f"Error clicking creator ID {creator_id}: {e}")
        return False

async def check_creator_status(page, creator_id):
    """
    Check the status of a creator after clicking on their profile.
    Returns the status string (e.g., "사용 가능", "초대 대기 중", "초대됨", etc.)
    """
    try:
        await asyncio.sleep(1)
        
        # Get page content to find status
        page_text = await page.text_content()
        
        # Look for status keywords
        if "사용 가능" in page_text:
            return "사용 가능"
        elif "초대 대기 중" in page_text:
            return "초대 대기 중"
        elif "초대됨" in page_text:
            return "초대됨"
        elif "요청됨" in page_text:
            return "요청됨"
        elif "거절됨" in page_text:
            return "거절됨"
        else:
            # Try to find status in specific elements
            status_elements = await page.query_selector_all('[class*="status"], [class*="badge"], [class*="tag"]')
            for elem in status_elements:
                text = await elem.text_content()
                if text and any(keyword in text for keyword in ["사용", "대기", "초대", "요청", "거절"]):
                    return text.strip()
            
            return "알 수 없음"
    
    except Exception as e:
        print(f"Error checking status for {creator_id}: {e}")
        return "오류"

if __name__ == "__main__":
    headless = "--headless" in sys.argv
    asyncio.run(verify_creators_on_backstage(headless=headless))
