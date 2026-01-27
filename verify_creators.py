import asyncio
import json
import os
import sys
import time
from datetime import datetime

from playwright.async_api import async_playwright

USER_DATA_DIR = "./tiktok_user_data"
VERIFICATION_FILE = "verified_creators.json"
STREAMERS_FILE = "streamers_data.json"
ACTIVE_STREAMERS_FILE = "active_streamers.txt"
BACKSTAGE_URL = "https://live-backstage.tiktok.com/portal/anchor/relation"
# Keywords to look for in the result list to confirm availability
RESULT_KEYWORDS = ("초대", "Invite", "Add") 

MAX_WAIT_SECONDS = 600


def load_streamer_ids():
    """Load streamer IDs from json or txt file."""
    ids = []
    
    # Try loading from the full json first (more data)
    if os.path.exists(STREAMERS_FILE):
        try:
            with open(STREAMERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                ids = [s["id"] for s in data if "id" in s]
                print(f"✅ Loaded {len(ids)} IDs from {STREAMERS_FILE}")
        except Exception as e:
            print(f"⚠️ Failed to load {STREAMERS_FILE}: {e}")

    # If that failed or was empty, try active_streamers.txt
    if not ids and os.path.exists(ACTIVE_STREAMERS_FILE):
        try:
            with open(ACTIVE_STREAMERS_FILE, "r", encoding="utf-8") as f:
                ids = [line.strip() for line in f if line.strip()]
            print(f"✅ Loaded {len(ids)} IDs from {ACTIVE_STREAMERS_FILE}")
        except Exception as e:
            print(f"⚠️ Failed to load {ACTIVE_STREAMERS_FILE}: {e}")

    return ids


async def verify_creators_on_backstage(headless=False):
    print("🚀 Auto Verification Process Started")
    print(f"Target URL: {BACKSTAGE_URL}")

    creator_ids = load_streamer_ids()
    if not creator_ids:
        print("❌ No creator IDs found to verify.")
        return

    print(f"📋 Verifying {len(creator_ids)} creators...")

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        chrome_path = None

    async with async_playwright() as p:
        # Launch options - Using persistent context to keep login session
        args = [
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
            "--window-size=500,600",
            "--window-position=5000,5000"
        ]
        
        launch_args = {
            "user_data_dir": USER_DATA_DIR,
            "headless": False, 
            "args": args,
            "viewport": {'width': 1280, 'height': 800},
        }

        # Check for Chrome executable
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(chrome_path):
             launch_args["executable_path"] = chrome_path

        context = await p.chromium.launch_persistent_context(**launch_args)
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            # 1. Go to URL
            print(f"\n🌐 Navigating to Backstage...")
            await page.goto(BACKSTAGE_URL, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5) # Wait for initial load

            # 2. Click "Add Host" / "Invite Creator" button
            print("👆 Clicking 'Add Host' button...")
            add_btn_selector = 'button[data-e2e-tag="host_manageRelationship_addHostBtn"]'
            
            # Wait separately for button
            try:
                await page.wait_for_selector(add_btn_selector, timeout=10000)
                await page.click(add_btn_selector)
            except Exception:
                print(f"⚠️ Could not find 'Add Host' button ({add_btn_selector}).")
                # Fallback: Try finding by text if selector fails?
                # But selector is very specific, so likely correct.
                # Just dumping a screenshot for debug if this part fails
                await page.screenshot(path="debug_no_button.png")
                raise

            await asyncio.sleep(2) # Wait for modal

            # 3. Paste IDs into Textarea
            print("📝 Pasting creator IDs...")
            textarea_selector = 'textarea[data-testid="inviteHostTextArea"]'
            await page.wait_for_selector(textarea_selector, timeout=10000)
            
            # Use chunks if too many, but textarea should handle it.
            # Format: one ID per line
            ids_text = "\n".join(creator_ids)
            await page.fill(textarea_selector, ids_text)
            
            await asyncio.sleep(1)

            # 4. Click Next
            print("➡️ Clicking Next...")
            # User provided: <span class="semi-button-content" x-semi-prop="children">다음</span>
            # We look for a button containing "다음" or "Next"
            # Attempt to find button with text "다음"
            next_btn_selector = "button:has-text('다음')"
            
            # Check if korean button exists
            if await page.query_selector(next_btn_selector):
                await page.click(next_btn_selector)
            elif await page.query_selector("button:has-text('Next')"):
                await page.click("button:has-text('Next')")
            else:
                # Try explicit class selector or look for primary button in modal footer
                # Sometimes the class structure is complex. 
                # Let's try to click the button that matches the structure provided by user if specific text fails.
                # User provided: class="semi-button semi-button-primary ..."
                # We can try clicking the LAST primary button in the dialog.
                print("⚠️ Specific text button not found, trying generic primary button...")
                await page.click('.semi-modal-content button.semi-button-primary')

            print("⏳ Waiting for validation results...")
            await asyncio.sleep(5) 
            
            # 5. Extract Results
            # Extract text and split by lines to check context
            body_text = await page.inner_text("body")
            lines = body_text.splitlines()
            
            # Keywords that imply the user is valid and can be invited
            # Based on previous logic and common UI patterns
            VALID_KEYWORDS = ["초대", "Invite", "Add", "사용 가능", "보내기"]
            
            available = []
            
            print("🔍 Analyzing constraints from table...")
            
            # Wait for the table to appear (based on user's HTML snippet class)
            try:
                await page.wait_for_selector(".semi-table-tbody", timeout=10000)
            except:
                print("⚠️ Table not found, might be empty results.")
            
            available = []
            
            # Select all rows in the results table
            rows = await page.query_selector_all('.semi-table-tbody tr[role="row"]')
            print(f"   found {len(rows)} rows in result table.")

            for row in rows:
                try:
                    # Column 2: Status (User explicitly pointed out: <div ...>사용 가능</div>)
                    status_cell = await row.query_selector('td[aria-colindex="2"]')
                    status_text = await status_cell.inner_text() if status_cell else ""
                    
                    if "사용 가능" in status_text:
                        # Column 1: User Info -> Extract ID
                        user_cell = await row.query_selector('td[aria-colindex="1"]')
                        user_text = await user_cell.inner_text() if user_cell else ""
                        
                        # Find which of our requested IDs matches this row
                        matched_id = None
                        for uid in creator_ids:
                            # user_text likely "7draw23dream\n드드" or similar
                            # Check if uid is in the text (case-insensitive just in case)
                            if uid.lower() in user_text.lower():
                                matched_id = uid
                                break
                        
                        if matched_id:
                            print(f"   ✓ {matched_id}: Available (Status: {status_text.strip()})")
                            available.append({
                                "id": matched_id,
                                "status": "available",
                                "verified_at": datetime.now().isoformat()
                            })
                        else:
                            # Sometimes the ID in the table might be slightly different or we missed it
                            # Log the raw text for debugging
                            cleaned_text = user_text.replace('\n', ' ').strip()
                            print(f"   ❓ Found 'Available' row but couldn't exact-match ID from text: '{cleaned_text}'")
                            # If we can't match exactly, we might want to try to extract the ID directly if possible
                            # But for now, safest is to match against our input list.
                            
                except Exception as e:
                    print(f"   ⚠️ Error parsing a row: {e}")
                    continue

            # Check for empty results
            if not available and not rows:
                 print("   ❌ No rows found in the result table.")
            elif not available:
                 print("   ❌ Rows found, but none were 'Available'.")

            # Save results
            verification_data = {
                "verified_at": datetime.now().isoformat(),
                "total_checked": len(creator_ids),
                "available_count": len(available),
                "available_creators": available,
            }

            with open(VERIFICATION_FILE, "w", encoding="utf-8") as f:
                json.dump(verification_data, f, ensure_ascii=False, indent=2)

            print(f"\n✅ Verification Success! Found {len(available)} potential matches.")
            print(f"💾 Saved to {VERIFICATION_FILE}")

        except Exception as e:
            print(f"❌ Error during verification: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="backstage_error.png")
        
        finally:
             await asyncio.sleep(2)
             await context.close()

if __name__ == "__main__":
    headless = "--headless" in sys.argv
    asyncio.run(verify_creators_on_backstage(headless=headless))
