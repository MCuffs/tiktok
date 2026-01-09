import asyncio
import sys
import os
from playwright.async_api import async_playwright

# Configuration
USER_DATA_DIR = "./tiktok_user_data"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def send_dm(handle, message):
    print(f"🚀 Starting DM automation for @{handle}...")
    
    if not os.path.exists(CHROME_PATH):
        print("❌ Chrome executable not found.")
        sys.exit(1)

    async with async_playwright() as p:
        # Launch browser with user profile to stay logged in
        launch_args = {
            "user_data_dir": USER_DATA_DIR,
            "headless": False, # Headless might trigger more captchas, headed is safer for DMs
            "executable_path": CHROME_PATH,
            "args": [
                "--no-first-run",
                "--no-default-browser-check",
                "--ignore-certificate-errors",
                "--disable-blink-features=AutomationControlled",
            ],
            "viewport": {"width": 1280, "height": 800},
            "ignore_default_args": ["--enable-automation"],
        }
        
        try:
            context = await p.chromium.launch_persistent_context(**launch_args)
            page = context.pages[0] if context.pages else await context.new_page()
            
            # 1. Provide a direct timeout
            page.set_default_timeout(15000)

            # 2. Go to Profile
            print(f"🌐 Navigating to profile: https://www.tiktok.com/@{handle}")
            await page.goto(f"https://www.tiktok.com/@{handle}", wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 3. Find "Message" button
            # It could be "Message" (EN) or "메시지" (KR)
            # Strategy: Look for primary button that acts as message
            print("🔍 Looking for Message button...")
            
            # Common selectors for the message button on profile
            # Usually distinct from "Follow" button
            msg_btn = page.locator('button:has-text("메시지")').first
            if not await msg_btn.count():
                msg_btn = page.locator('button:has-text("Message")').first
            
            # Fallback: Try to find by hierarchy if text fails (e.g. icon only)
            # But usually it has text.
            
            if await msg_btn.count() and await msg_btn.is_visible():
                await msg_btn.click()
                print("✅ Clicked Message button")
            else:
                print("❌ Could not find Message button. (Maybe privacy settings or already requested?)")
                # Sometimes it's inside the "..." menu if not friends? 
                # For now, duplicate the error.
                sys.exit(1)

            # 4. Wait for Chat Interface
            # We look for the editor
            print("⏳ Waiting for chat input...")
            editor_selector = 'div[contenteditable="true"]'
            
            try:
                await page.wait_for_selector(editor_selector, state="visible")
            except:
                print("❌ Chat input not found. (Maybe popup blocked or different UI)")
                sys.exit(1)
            
            # 5. Type and Send
            print("✍️  Typing message...")
            await page.fill(editor_selector, message)
            await asyncio.sleep(0.5)
            
            print("📨 Sending (Pressing Enter)...")
            await page.press(editor_selector, "Enter")
            
            # Optional: Wait a bit to ensure send happens
            await asyncio.sleep(2)
            
            # 6. Check for failure indicators (e.g. "Not sent", red icons)
            # This is hard to generalize, but we assume success if no immediate alert.
            
            print("✨ Message sequence finished.")
        
        except Exception as e:
            print(f"❌ Error during automation: {e}")
            sys.exit(1)
            
        finally:
            await asyncio.sleep(1)
            await context.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python send_dm.py <handle> <message>")
        sys.exit(1)
    
    handle = sys.argv[1]
    # Message can be multiline, pass as single string
    message = sys.argv[2]
    
    asyncio.run(send_dm(handle, message))
