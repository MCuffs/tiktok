import asyncio
import sys
import os
import json
import pyperclip
from datetime import datetime
from playwright.async_api import async_playwright

# Configuration
USER_DATA_DIR = "./tiktok_user_data"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DM_STATUS_FILE = "dm_status.json"
BACKSTAGE_DM_URL = "https://live-backstage.tiktok.com/portal/anchor/instant-messages"

# Message templates
MESSAGE_KR = """[크리에이터 제안]
안녕하세요, 아서리안 스튜디오 입니다.
저희는 딱 10명의 잠재성을 지닌 크리에이터를 발굴하여 팀을 꾸려가고 있는데요!

저희가 파트너 크리에이터분들께
• 라이브 스트리밍 팁 및 방송 장비 지원
• 정산금 보너스
• 시청자 유입 / 성장 컨설팅
등을 지원해드리고 있어요.

{name}님께 참여를 제안드려보고 싶어서 안내 드립니다.
관심 있으시면 편하게 답장 부탁드려요!

공식 홈페이지: https://www.arthrian.cloud/"""

MESSAGE_EN = """[Arthurian Studio]
Hello {name}, we'd like to invite you to our exclusive creator team.

We support our partner creators with:
• Live streaming tips & equipment support
• Revenue bonus
• Viewer growth consulting

If interested, feel free to reply!

Official website: https://www.arthrian.cloud/"""


def load_dm_status():
    if os.path.exists(DM_STATUS_FILE):
        try:
            with open(DM_STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"sent": [], "failed": []}


def save_dm_status(data):
    with open(DM_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


async def send_dm(handle, nickname="", lang="kr", auto_send=True):
    """
    Send DM via TikTok Backstage.

    Args:
        handle: TikTok username (without @)
        nickname: Display name to use in message
        lang: "kr" or "en" for message template
        auto_send: If True, automatically send the message

    Returns:
        dict with status and message
    """
    log(f"Starting DM automation for @{handle} via Backstage...")

    if not os.path.exists(CHROME_PATH):
        return {"status": "error", "message": "Chrome not found"}

    # Prepare message
    name = nickname if nickname else handle
    if lang == "en":
        message = MESSAGE_EN.format(name=name)
    else:
        message = MESSAGE_KR.format(name=name)

    result = {"status": "error", "message": "Unknown error"}

    async with async_playwright() as p:
        launch_args = {
            "user_data_dir": os.path.abspath(USER_DATA_DIR),
            "headless": False,
            "executable_path": CHROME_PATH,
            "args": [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1200,800",
            ],
            "viewport": {"width": 1200, "height": 800},
            "ignore_default_args": ["--enable-automation"],
        }

        context = None
        try:
            context = await p.chromium.launch_persistent_context(**launch_args)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(15000)

            # Navigate to Backstage DM page
            log(f"Navigating to Backstage DM page...")
            await page.goto(BACKSTAGE_DM_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Check login
            if "login" in page.url.lower():
                log("ERROR: Not logged in to Backstage!")
                result = {"status": "error", "message": "Not logged in"}
                return result

            # Find and fill the search input
            log(f"Searching for creator: {handle}")
            search_input = 'input[placeholder="크리에이터 아이디"]'

            try:
                await page.wait_for_selector(search_input, timeout=10000)
                await page.fill(search_input, handle)
                await page.keyboard.press("Enter")
                log("Entered creator ID and pressed Enter")
            except Exception as e:
                log(f"Search input not found: {e}")
                await page.screenshot(path="debug_dm_search.png")
                result = {"status": "error", "message": "Search input not found"}
                return result

            await asyncio.sleep(2)

            # Click on the creator from search results
            log("Looking for creator in search results...")

            # Try to find and click the search result item
            search_result_selectors = [
                '[data-id="backstage_search_result_item"]',
                '.searchItem--qLzyR',
                '[class*="searchItem"]',
            ]

            clicked = False
            for sel in search_result_selectors:
                try:
                    item = await page.query_selector(sel)
                    if item:
                        await item.click()
                        clicked = True
                        log(f"Clicked search result: {sel}")
                        break
                except:
                    continue

            if not clicked:
                log("Could not find creator in search results")
                await page.screenshot(path="debug_dm_no_result.png")
                result = {"status": "error", "message": "Creator not found in search"}
                return result

            await asyncio.sleep(2)

            # Find the message input area
            log("Looking for message input...")
            editor_selectors = [
                '[contenteditable="true"]',
                'textarea[placeholder*="메시지"]',
                'div[role="textbox"]',
                '.im-editor-container [contenteditable="true"]',
            ]

            editor = None
            for sel in editor_selectors:
                try:
                    await page.wait_for_selector(sel, state="visible", timeout=5000)
                    editor = page.locator(sel).first
                    if await editor.count() > 0:
                        log(f"Found message editor: {sel}")
                        break
                except:
                    continue

            if not editor:
                log("Message editor not found")
                await page.screenshot(path="debug_dm_no_editor.png")
                result = {"status": "error", "message": "Message editor not found"}
                return result

            # Paste the message
            log("Pasting message...")
            await editor.click()
            await asyncio.sleep(0.3)

            # Copy message to clipboard and paste
            pyperclip.copy(message)
            await page.keyboard.press("Meta+v")  # Cmd+V on Mac
            await asyncio.sleep(0.5)

            if auto_send:
                # Find and click send button
                log("Sending message...")
                send_selectors = [
                    'button:has-text("보내기")',
                    'button:has-text("Send")',
                    '[class*="send-btn"]',
                    'button[type="submit"]',
                ]

                sent = False
                for sel in send_selectors:
                    try:
                        btn = page.locator(sel).first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            sent = True
                            log(f"Clicked send button: {sel}")
                            break
                    except:
                        continue

                if not sent:
                    # Try Ctrl+Enter or Enter as fallback
                    log("Trying keyboard shortcut to send...")
                    await page.keyboard.press("Control+Enter")
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    sent = True

                await asyncio.sleep(2)

                # Update status
                dm_status = load_dm_status()
                dm_status["sent"].append({
                    "id": handle,
                    "nickname": nickname,
                    "lang": lang,
                    "sent_at": int(datetime.now().timestamp() * 1000)
                })
                save_dm_status(dm_status)

                log(f"DM sent to @{handle}!")
                result = {"status": "success", "message": f"DM sent to @{handle}"}
            else:
                log("Message typed. Auto-send disabled.")
                result = {"status": "success", "message": "Message typed, ready to send manually"}
                # Keep browser open for manual action
                while not page.is_closed():
                    await asyncio.sleep(1)

        except Exception as e:
            log(f"Error: {e}")
            result = {"status": "error", "message": str(e)}

            # Record failure
            dm_status = load_dm_status()
            dm_status["failed"].append({
                "id": handle,
                "nickname": nickname,
                "error": str(e),
                "failed_at": int(datetime.now().timestamp() * 1000)
            })
            save_dm_status(dm_status)

        finally:
            if context:
                await asyncio.sleep(1)
                await context.close()

    return result


async def send_dm_batch(creators, lang="kr", delay=3):
    """
    Send DMs to multiple creators with delay between each.
    Uses a single browser session for efficiency.

    Args:
        creators: List of {"id": "handle", "nickname": "name"}
        lang: "kr" or "en"
        delay: Seconds to wait between DMs

    Returns:
        dict with results
    """
    log(f"Starting batch DM for {len(creators)} creators...")

    if not os.path.exists(CHROME_PATH):
        return {"success": [], "failed": [{"id": "all", "error": "Chrome not found"}]}

    results = {"success": [], "failed": []}

    async with async_playwright() as p:
        launch_args = {
            "user_data_dir": os.path.abspath(USER_DATA_DIR),
            "headless": False,
            "executable_path": CHROME_PATH,
            "args": [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1200,800",
            ],
            "viewport": {"width": 1200, "height": 800},
            "ignore_default_args": ["--enable-automation"],
        }

        context = None
        try:
            context = await p.chromium.launch_persistent_context(**launch_args)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(15000)

            # Navigate to Backstage DM page
            log("Navigating to Backstage DM page...")
            await page.goto(BACKSTAGE_DM_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # Check login
            if "login" in page.url.lower():
                log("ERROR: Not logged in!")
                return {"success": [], "failed": [{"id": "all", "error": "Not logged in"}]}

            for i, creator in enumerate(creators):
                handle = creator.get("id")
                nickname = creator.get("nickname", "")
                name = nickname if nickname else handle

                log(f"\n[{i+1}/{len(creators)}] Processing @{handle}...")

                # Prepare message
                if lang == "en":
                    message = MESSAGE_EN.format(name=name)
                else:
                    message = MESSAGE_KR.format(name=name)

                try:
                    # Search for creator
                    search_input = 'input[placeholder="크리에이터 아이디"]'
                    await page.wait_for_selector(search_input, timeout=5000)

                    # Clear previous search and enter new
                    await page.fill(search_input, "")
                    await page.fill(search_input, handle)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1.5)

                    # Click on search result
                    search_item = await page.query_selector('[data-id="backstage_search_result_item"]')
                    if not search_item:
                        search_item = await page.query_selector('[class*="searchItem"]')
                    if not search_item:
                        raise Exception("Creator not found in search")

                    await search_item.click()
                    await asyncio.sleep(1)

                    # Find and fill message editor
                    editor = page.locator('[contenteditable="true"]').first
                    if await editor.count() == 0:
                        raise Exception("Message editor not found")

                    await editor.click()
                    await asyncio.sleep(0.3)

                    # Paste message
                    pyperclip.copy(message)
                    await page.keyboard.press("Meta+v")  # Cmd+V on Mac
                    await asyncio.sleep(0.3)

                    # Send
                    send_btn = page.locator('button:has-text("보내기")').first
                    if await send_btn.count() > 0:
                        await send_btn.click()
                    else:
                        await page.keyboard.press("Control+Enter")

                    await asyncio.sleep(1.5)

                    # Record success
                    dm_status = load_dm_status()
                    dm_status["sent"].append({
                        "id": handle,
                        "nickname": nickname,
                        "lang": lang,
                        "sent_at": int(datetime.now().timestamp() * 1000)
                    })
                    save_dm_status(dm_status)

                    results["success"].append(handle)
                    log(f"  ✅ DM sent to @{handle}")

                except Exception as e:
                    log(f"  ❌ Failed: {e}")
                    results["failed"].append({"id": handle, "error": str(e)})

                    dm_status = load_dm_status()
                    dm_status["failed"].append({
                        "id": handle,
                        "nickname": nickname,
                        "error": str(e),
                        "failed_at": int(datetime.now().timestamp() * 1000)
                    })
                    save_dm_status(dm_status)

                # Wait before next DM
                if i < len(creators) - 1:
                    log(f"  Waiting {delay}s...")
                    await asyncio.sleep(delay)

        except Exception as e:
            log(f"Batch error: {e}")

        finally:
            if context:
                await asyncio.sleep(1)
                await context.close()

    log(f"\nBatch complete: {len(results['success'])} sent, {len(results['failed'])} failed")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_dm.py <handle> [nickname] [lang]")
        print("  lang: kr (default) or en")
        sys.exit(1)

    handle = sys.argv[1]
    nickname = sys.argv[2] if len(sys.argv) > 2 else ""
    lang = sys.argv[3] if len(sys.argv) > 3 else "kr"

    result = asyncio.run(send_dm(handle, nickname, lang, auto_send=True))
    print(f"Result: {result}")
