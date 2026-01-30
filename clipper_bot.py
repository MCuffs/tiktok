import time
import re
import json
import os
import subprocess
from pynput import keyboard

# Configuration
TIKTOK_REGEX = r"tiktok\.com/@([a-zA-Z0-9_.]+)"
PENDING_FILE = "pending_creators.json"
HOTKEY = keyboard.Key.ctrl_r  # Right Ctrl key

def show_notification(title, message, sound="Pop"):
    script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)

def get_chrome_url():
    """Get URL directly from Chrome without simulating keystrokes."""
    script = '''
    tell application "Google Chrome"
        if (count of windows) > 0 then
            return URL of active tab of front window
        else
            return ""
        end if
    end tell
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except:
        return ""

def press_down_arrow():
    """Press down arrow key to go to next live."""
    script = 'tell application "System Events" to key code 125'
    subprocess.run(["osascript", "-e", script], capture_output=True)

def get_live_nickname():
    """Get streamer nickname from Chrome tab title."""
    # Get page title - usually "닉네임 is LIVE | TikTok" or "닉네임의 LIVE | TikTok"
    script = '''
    tell application "Google Chrome"
        if (count of windows) > 0 then
            return title of active tab of front window
        else
            return ""
        end if
    end tell
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        title = result.stdout.strip()

        if not title or "tiktok" not in title.lower():
            return ""

        # Extract nickname from title
        # Format: "오하나 (@oshioshiotea) 님 라이브 중 | TikTok" -> "오하나"
        # Format: "Name is LIVE | TikTok" -> "Name"

        # First try to extract name before " (@" (Korean format with username)
        if " (@" in title:
            nickname = title.split(" (@")[0].strip()
            if nickname and len(nickname) < 50:
                return nickname

        # Then try other patterns
        patterns = [
            r'^(.+?)\s+is\s+LIVE',      # "Name is LIVE"
            r'^(.+?)의\s+LIVE',          # "Name의 LIVE"
            r'^(.+?)\s+님\s+라이브',      # "Name 님 라이브"
            r'^(.+?)\s+LIVE',            # "Name LIVE"
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                nickname = match.group(1).strip()
                if nickname and len(nickname) < 50:
                    return nickname

        return ""
    except:
        return ""

def load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_pending(creators):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(creators, f, ensure_ascii=False, indent=2)

def add_creator(username, nickname=""):
    creators = load_pending()

    if any(c["id"] == username for c in creators):
        print(f"[Skip] @{username} already in list")
        return False

    creator_data = {
        "id": username,
        "status": "pending",
        "added_at": int(time.time() * 1000)
    }
    if nickname:
        creator_data["nickname"] = nickname

    creators.append(creator_data)
    save_pending(creators)

    display_name = f"@{username}" + (f" ({nickname})" if nickname else "")
    print(f"[Added] {display_name}")
    show_notification("Creator Added", display_name, "Pop")
    return True

session_ids = set()
last_trigger = 0

def on_hotkey():
    global session_ids, last_trigger

    now = time.time()
    if now - last_trigger < 0.8:
        return
    last_trigger = now

    print("\n[Capturing...]")

    # Get URL directly from Chrome
    url = get_chrome_url()

    if not url:
        print("[Error] Could not get Chrome URL")
        show_notification("Error", "Open TikTok in Chrome", "Basso")
        return

    print(f"[URL] {url[:50]}...")

    match = re.search(TIKTOK_REGEX, url)
    if match:
        username = match.group(1)

        if username not in session_ids:
            session_ids.add(username)

            nickname = get_live_nickname()
            if nickname:
                print(f"[Nickname] {nickname}")

            added = add_creator(username, nickname)

            if added:
                time.sleep(0.3)
                press_down_arrow()
                print("[Auto] → Next live")
        else:
            print(f"[Skip] @{username} already captured")
            time.sleep(0.2)
            press_down_arrow()
    else:
        print("[Skip] Not a TikTok URL")

def main():
    print("=" * 50)
    print("   Clipper Bot - One Key Capture")
    print("=" * 50)
    print("\n>>> Press Right Ctrl to capture & next <<<")
    print("\n(Use Chrome for TikTok live)")
    print("Press Ctrl+C to stop\n")

    def on_press(key):
        if key == HOTKEY:
            on_hotkey()

    with keyboard.Listener(on_press=on_press) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n\nClipper Bot stopped.")

if __name__ == "__main__":
    main()
