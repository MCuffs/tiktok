import time
import re
import json
import os
import subprocess
from pynput import keyboard

# Configuration
TIKTOK_REGEX = r"tiktok\.com/@([a-zA-Z0-9_.]+)"
PENDING_FILE = "pending_creators.json"

# Track pressed keys for combo detection
pressed_keys = set()

def show_notification(title, message, sound="Pop"):
    """Display a native macOS notification."""
    script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)

def get_browser_url():
    """Get current URL from Chrome or Safari."""
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell

    if frontApp is "Google Chrome" then
        tell application "Google Chrome"
            return URL of active tab of front window
        end tell
    else if frontApp is "Safari" then
        tell application "Safari"
            return URL of front document
        end tell
    else if frontApp is "Arc" then
        tell application "Arc"
            return URL of active tab of front window
        end tell
    else
        return ""
    end if
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()

def get_live_nickname():
    """Get streamer nickname from TikTok live page via JavaScript."""
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell

    if frontApp is "Google Chrome" then
        tell application "Google Chrome"
            set jsResult to execute front window's active tab javascript "
                (function() {
                    // Try multiple selectors for nickname
                    var selectors = [
                        '[data-e2e=\\"live-nickname\\"]',
                        '.tiktok-live-nickname',
                        '[class*=\\"DivNicknameContainer\\"] span',
                        '[class*=\\"nickname\\"]',
                        'h1[data-e2e]',
                        '.live-room-nickname'
                    ];
                    for (var i = 0; i < selectors.length; i++) {
                        var el = document.querySelector(selectors[i]);
                        if (el && el.textContent.trim()) {
                            return el.textContent.trim();
                        }
                    }
                    return '';
                })()
            "
            return jsResult
        end tell
    else
        return ""
    end if
    '''
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except:
        return ""

def press_down_arrow():
    """Press down arrow key to go to next live."""
    script = 'tell application "System Events" to key code 125'  # 125 = down arrow
    subprocess.run(["osascript", "-e", script], capture_output=True)

def load_pending():
    """Load pending creators list."""
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_pending(creators):
    """Save pending creators list."""
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(creators, f, ensure_ascii=False, indent=2)

def add_creator(username, nickname=""):
    """Add a creator to pending list."""
    creators = load_pending()

    # Check if already exists
    if any(c["id"] == username for c in creators):
        print(f"[Skip] @{username} already in list")
        show_notification("Already Added", f"@{username}", "Basso")
        return False

    # Add new creator with nickname
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

# Track session IDs
session_ids = set()

def on_hotkey():
    """Handle hotkey press - get URL, extract ID, save, next."""
    global session_ids

    url = get_browser_url()
    if not url:
        print("[Error] Could not get browser URL")
        show_notification("Error", "Could not get URL", "Basso")
        return

    match = re.search(TIKTOK_REGEX, url)
    if match:
        username = match.group(1)

        if username not in session_ids:
            session_ids.add(username)

            # Get nickname from live page
            nickname = get_live_nickname()
            if nickname:
                print(f"[Nickname] {nickname}")

            added = add_creator(username, nickname)

            if added:
                # Wait a bit then press down arrow for next live
                time.sleep(0.3)
                press_down_arrow()
                print("[Auto] → Next live")
        else:
            print(f"[Skip] @{username} already captured this session")
            # Still go to next
            time.sleep(0.2)
            press_down_arrow()
    else:
        print(f"[Skip] Not a TikTok profile URL: {url[:50]}...")

def main():
    global pressed_keys

    print("=" * 50)
    print("   Clipper Bot - Quick Capture Mode")
    print("=" * 50)
    print(f"\nPress Q+W to capture creator and go to next live")
    print("Press Ctrl+C to stop\n")
    print("Waiting for hotkey...")

    # Set up hotkey listener for Q+W
    def on_press(key):
        global pressed_keys

        # Get character for letter keys
        try:
            pressed_keys.add(key.char.lower())
        except AttributeError:
            pressed_keys.add(key)

        # Check for Q+W combo
        if 'q' in pressed_keys and 'w' in pressed_keys:
            pressed_keys.clear()
            on_hotkey()

    def on_release(key):
        global pressed_keys
        try:
            pressed_keys.discard(key.char.lower())
        except AttributeError:
            pressed_keys.discard(key)

    # Start listener
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n\nClipper Bot stopped.")

if __name__ == "__main__":
    main()
