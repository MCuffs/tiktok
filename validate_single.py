import asyncio
import sys
import json
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright

USER_DATA_DIR = "./tiktok_user_data"
HISTORY_FILE = "scan_history.json"
OUTPUT_FILE = "streamers_data.json"
BACKSTAGE_URL = "https://live-backstage.tiktok.com/portal/anchor/relation"

def log_debug(msg):
    """Log to console and file."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open("validation_debug.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def show_notification(title, message, sound="Ping"):
    """Display macOS notification."""
    import subprocess
    script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)

def save_history(entry):
    """Save result to history file."""
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass

    history.insert(0, entry)
    history = history[:50]  # Keep last 50

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def save_to_streamers(username, status):
    """Save qualified user to streamers file."""
    existing = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            pass

    if not any(e.get("id") == username for e in existing):
        existing.append({
            "id": username,
            "nickname": username,
            "url": f"https://www.tiktok.com/@{username}",
            "source": "clipper_bot",
            "backstage": status,
            "verified_at": datetime.now().isoformat()
        })
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

async def validate_on_backstage(username):
    """Validate a single user on TikTok Backstage."""
    log_debug(f"Starting validation for: {username}")

    result = {
        "id": username,
        "nickname": username,
        "followers": "-",
        "verified": False,
        "status": "FAIL",
        "reason": "",
        "check_time": int(time.time() * 1000)
    }

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    try:
        async with async_playwright() as p:
            log_debug("Launching browser...")

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

            if os.path.exists(chrome_path):
                launch_args["executable_path"] = chrome_path

            context = await p.chromium.launch_persistent_context(**launch_args)
            page = context.pages[0] if context.pages else await context.new_page()

            try:
                # 1. Navigate to Backstage
                log_debug(f"Navigating to {BACKSTAGE_URL}...")
                await page.goto(BACKSTAGE_URL, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(3)

                current_url = page.url
                log_debug(f"Current URL: {current_url}")

                # Check if redirected to login
                if "login" in current_url.lower() or "signin" in current_url.lower():
                    log_debug("Login required!")
                    result["reason"] = "Backstage 로그인 필요"
                    show_notification("로그인 필요", "Backstage 로그인이 필요합니다", "Basso")
                    return result

                # 2. Click "Add Host" button
                log_debug("Looking for Add Host button...")
                add_btn = 'button[data-e2e-tag="host_manageRelationship_addHostBtn"]'

                try:
                    await page.wait_for_selector(add_btn, timeout=10000)
                    await page.click(add_btn)
                    log_debug("Clicked Add Host button")
                except Exception as e:
                    log_debug(f"Add Host button not found: {e}")
                    await page.screenshot(path="debug_no_button.png")
                    result["reason"] = "Add Host 버튼 없음 (로그인 확인)"
                    return result

                await asyncio.sleep(2)

                # 3. Enter username in textarea
                log_debug(f"Entering username: {username}")
                textarea = 'textarea[data-testid="inviteHostTextArea"]'

                try:
                    await page.wait_for_selector(textarea, timeout=5000)
                    await page.fill(textarea, username)
                except Exception as e:
                    log_debug(f"Textarea not found: {e}")
                    result["reason"] = "입력창 없음"
                    return result

                await asyncio.sleep(1)

                # 4. Click Next button
                log_debug("Clicking Next button...")
                clicked = False

                for selector in ["button:has-text('다음')", "button:has-text('Next')", ".semi-modal-content button.semi-button-primary"]:
                    try:
                        if await page.query_selector(selector):
                            await page.click(selector)
                            clicked = True
                            log_debug(f"Clicked: {selector}")
                            break
                    except:
                        continue

                if not clicked:
                    log_debug("Next button not found")
                    result["reason"] = "다음 버튼 없음"
                    return result

                await asyncio.sleep(4)

                # 5. Analyze results table
                log_debug("Analyzing results...")
                await page.screenshot(path="debug_results.png")

                # Wait for table
                try:
                    await page.wait_for_selector(".semi-table-tbody", timeout=8000)
                except:
                    log_debug("Results table not found")
                    result["reason"] = "결과 테이블 없음"
                    return result

                rows = await page.query_selector_all('.semi-table-tbody tr[role="row"]')
                log_debug(f"Found {len(rows)} rows")

                found_status = None
                for row in rows:
                    try:
                        text = await row.inner_text()
                        log_debug(f"Row text: {text[:100]}...")

                        if username.lower() in text.lower():
                            if "사용 가능" in text or "Available" in text:
                                found_status = "Available"
                            elif "부적격" in text or "Ineligible" in text:
                                found_status = "Ineligible"
                            elif "바인딩" in text or "Bound" in text:
                                found_status = "Already Bound"
                            else:
                                found_status = "Unknown"
                            break
                    except Exception as e:
                        log_debug(f"Error parsing row: {e}")

                # Set result based on status
                if found_status == "Available":
                    result["status"] = "PASS"
                    result["reason"] = "✅ 사용 가능 (Backstage)"
                    result["verified"] = True
                    save_to_streamers(username, "Available")
                    show_notification("✅ 영입 가능!", f"@{username} 사용 가능", "Glass")
                elif found_status == "Ineligible":
                    result["reason"] = "❌ 부적격 (Ineligible)"
                    show_notification("❌ 부적격", f"@{username} 부적격", "Basso")
                elif found_status == "Already Bound":
                    result["reason"] = "❌ 이미 바인딩됨"
                    show_notification("❌ 바인딩됨", f"@{username} 이미 소속", "Basso")
                elif found_status:
                    result["reason"] = f"❌ {found_status}"
                    show_notification("❌ 확인 필요", f"@{username}: {found_status}", "Basso")
                else:
                    result["reason"] = "❌ 테이블에서 찾을 수 없음"
                    show_notification("❌ 검증 실패", f"@{username} 결과 없음", "Basso")

                log_debug(f"Result: {result['status']} - {result['reason']}")

            finally:
                await asyncio.sleep(2)
                await context.close()

    except Exception as e:
        log_debug(f"Exception: {e}")
        result["reason"] = f"오류: {str(e)[:50]}"
        show_notification("오류 발생", str(e)[:30], "Basso")

    return result

async def main(username):
    # Clear previous debug log
    with open("validation_debug.log", "w") as f:
        f.write("")

    log_debug(f"=== Validation Start: {username} ===")

    result = await validate_on_backstage(username)
    save_history(result)

    log_debug(f"=== Validation End ===")
    print(f"\nResult: {result['status']} - {result['reason']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
        asyncio.run(main(target))
    else:
        print("Usage: python3 validate_single.py <username>")
