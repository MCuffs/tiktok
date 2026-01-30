import asyncio
import json
import os
import time
import sys
from datetime import datetime
from playwright.async_api import async_playwright

USER_DATA_DIR = "./tiktok_user_data"
PENDING_FILE = "pending_creators.json"
VERIFIED_FILE = "verified_creators.json"
BACKSTAGE_URL = "https://live-backstage.tiktok.com/portal/anchor/relation"
LOG_FILE = "verify.log"


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def _find_chrome_executable():
    if sys.platform.startswith("win"):
        candidates = [
            os.environ.get("CHROME_PATH", ""),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return ""
    if sys.platform == "darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return path if os.path.exists(path) else ""
    for path in ("/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"):
        if os.path.exists(path):
            return path
    return ""


def load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []


def save_pending(data):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_verified():
    if os.path.exists(VERIFIED_FILE):
        try:
            with open(VERIFIED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"available": [], "unavailable": []}


def save_verified(data):
    with open(VERIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


MAX_VERIFY_COUNT = 30  # TikTok Backstage limit

async def verify_all():
    pending = load_pending()
    if not pending:
        log("No pending creators to verify")
        return
    # Snapshot to ensure we never delete pending entries automatically
    pending_snapshot = list(pending)

    # Limit to 30 creators max
    to_verify = pending[:MAX_VERIFY_COUNT]
    remaining = pending[MAX_VERIFY_COUNT:]

    ids = [c["id"] for c in to_verify]
    # Create lookup for nicknames
    nickname_map = {c["id"]: c.get("nickname", "") for c in to_verify}
    log(f"Verifying {len(ids)} creators (max {MAX_VERIFY_COUNT})")
    if remaining:
        log(f"  ({len(remaining)} more will be verified next time)")

    async with async_playwright() as p:
        log("Launching browser...")

        launch_args = {
            "user_data_dir": os.path.abspath(USER_DATA_DIR),
            "headless": False,
            "viewport": {"width": 1280, "height": 800},
            "args": [
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        }

        chrome_path = _find_chrome_executable()
        if chrome_path:
            launch_args["executable_path"] = chrome_path
            log(f"Using Chrome executable: {chrome_path}")
        elif sys.platform.startswith("win"):
            launch_args["channel"] = "chrome"
            log("Using Playwright Chrome channel")

        context = await p.chromium.launch_persistent_context(**launch_args)
        page = context.pages[0] if context.pages else await context.new_page()

        results = {"available": [], "unavailable": []}

        try:
            # Navigate to backstage
            log(f"Navigating to {BACKSTAGE_URL}...")
            await page.goto(BACKSTAGE_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Check login
            if "login" in page.url.lower():
                log("Not logged in. Please log in to Backstage in the opened browser...")
                login_wait_start = time.time()
                while "login" in page.url.lower():
                    if time.time() - login_wait_start > 300:
                        log("Login timeout after 5 minutes")
                        return
                    await asyncio.sleep(2)
                log("Login detected. Continuing...")

            # Click Add Host button
            log("Clicking Add Host button...")
            add_btn = 'button[data-e2e-tag="host_manageRelationship_addHostBtn"]'

            try:
                await page.wait_for_selector(add_btn, timeout=300000)
                await page.click(add_btn)
            except:
                log("ERROR: Add Host button not found")
                await page.screenshot(path="debug_batch_error.png")
                return

            await asyncio.sleep(2)

            # Enter all IDs
            log(f"Entering {len(ids)} IDs...")
            textarea = 'textarea[data-testid="inviteHostTextArea"]'

            try:
                await page.wait_for_selector(textarea, timeout=5000)
                ids_text = "\n".join(ids)
                await page.fill(textarea, ids_text)
            except:
                log("ERROR: Textarea not found")
                return

            await asyncio.sleep(1)

            # Click Next
            log("Clicking Next...")
            for selector in ["button:has-text('다음')", "button:has-text('Next')", ".semi-modal-content button.semi-button-primary"]:
                try:
                    if await page.query_selector(selector):
                        await page.click(selector)
                        break
                except:
                    continue

            await asyncio.sleep(4)

            # Parse results
            log("Parsing results...")
            await page.screenshot(path="debug_batch_results.png")

            try:
                await page.wait_for_selector(".semi-table-tbody", timeout=10000)
            except:
                log("ERROR: Results table not found")
                return

            rows = await page.query_selector_all('.semi-table-tbody tr[role="row"]')
            log(f"Found {len(rows)} rows")

            for row in rows:
                try:
                    text = await row.inner_text()

                    # Find matching ID
                    matched_id = None
                    for uid in ids:
                        if uid.lower() in text.lower():
                            matched_id = uid
                            break

                    if not matched_id:
                        continue

                    # Determine status
                    now = int(time.time() * 1000)

                    nickname = nickname_map.get(matched_id, "")

                    if "사용 가능" in text or "Available" in text:
                        log(f"  OK {matched_id}: Available")
                        results["available"].append({
                            "id": matched_id,
                            "nickname": nickname,
                            "reason": "사용 가능",
                            "verified_at": now
                        })
                    elif "부적격" in text or "Ineligible" in text:
                        log(f"  NO {matched_id}: Ineligible")
                        results["unavailable"].append({
                            "id": matched_id,
                            "nickname": nickname,
                            "reason": "부적격",
                            "verified_at": now
                        })
                    elif "바인딩" in text or "Bound" in text or "에이전시" in text:
                        log(f"  NO {matched_id}: Already bound")
                        results["unavailable"].append({
                            "id": matched_id,
                            "nickname": nickname,
                            "reason": "이미 소속됨",
                            "verified_at": now
                        })
                    elif "자격 없음" in text:
                        log(f"  NO {matched_id}: Not qualified")
                        results["unavailable"].append({
                            "id": matched_id,
                            "nickname": nickname,
                            "reason": "자격 없음",
                            "verified_at": now
                        })
                    else:
                        log(f"  ?? {matched_id}: Unknown status")
                        results["unavailable"].append({
                            "id": matched_id,
                            "nickname": nickname,
                            "reason": "알 수 없음",
                            "verified_at": now
                        })

                except Exception as e:
                    log(f"  Error parsing row: {e}")

            # Save results
            verified = load_verified()
            verified["available"].extend(results["available"])
            verified["unavailable"].extend(results["unavailable"])
            save_verified(verified)

            # Keep pending list intact (do not remove verified)
            log(f"\nDone! Available: {len(results['available'])}, Unavailable: {len(results['unavailable'])}")
            log(f"Pending kept: {len(pending_snapshot)}")

        except Exception as e:
            log(f"ERROR: {e}")
            await page.screenshot(path="debug_batch_exception.png")

        finally:
            # Merge snapshot with any new pending entries added during verification
            try:
                current_pending = load_pending()
                merged = {c.get("id"): c for c in current_pending if c.get("id")}
                for c in pending_snapshot:
                    cid = c.get("id")
                    if cid and cid not in merged:
                        merged[cid] = c
                save_pending(list(merged.values()))
            except Exception as e:
                log(f"ERROR: Failed to restore pending list: {e}")
            await asyncio.sleep(2)
            await context.close()


if __name__ == "__main__":
    asyncio.run(verify_all())
