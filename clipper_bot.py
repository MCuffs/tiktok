import time
import re
import json
import os
import sys
import subprocess
import ctypes
import argparse
from pynput import keyboard
from pynput.keyboard import Controller, Key

# Configuration
TIKTOK_REGEX = r"tiktok\.com/@([a-zA-Z0-9_.]+)"
PENDING_FILE = "pending_creators.json"
HOTKEY = keyboard.Key.ctrl_r  # Right Ctrl key (macOS/Linux)
WINDOWS_HOTKEY_LABEL = "Ctrl + Space"
# Speed tuning
HOTKEY_COOLDOWN = 0.25
NEXT_DELAY = 0.05
DUPLICATE_DELAY = 0.02
ENABLE_NICKNAME = True
BATCH_MAX = 30
BATCH_STEP_DELAY = 0.08
LOG_FILE = "clipper.log"

IS_WINDOWS = sys.platform.startswith("win")
kb = Controller()

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def show_notification(title, message, sound="Pop"):
    if IS_WINDOWS:
        print(f"[Notify] {title}: {message}")
        return
    script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)

def _get_clipboard_text_windows():
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        if not user32.OpenClipboard(0):
            return ""
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            locked = kernel32.GlobalLock(handle)
            if not locked:
                return ""
            try:
                size = kernel32.GlobalSize(handle)
                if not size:
                    return ""
                wchar_count = max(int(size // ctypes.sizeof(ctypes.c_wchar)) - 1, 0)
                return ctypes.wstring_at(locked, wchar_count)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""

def _get_clipboard_text_powershell():
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            timeout=1.5
        )
        if result.returncode == 0:
            return (result.stdout or "").strip()
    except Exception:
        pass
    return ""

def _set_clipboard_text_windows(text):
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        if not user32.OpenClipboard(0):
            return
        try:
            user32.EmptyClipboard()
            size = (len(text) + 1) * ctypes.sizeof(ctypes.c_wchar)
            h_global = kernel32.GlobalAlloc(0x0002, size)
            if not h_global:
                return
            locked = kernel32.GlobalLock(h_global)
            if not locked:
                return
            try:
                ctypes.memmove(locked, ctypes.create_unicode_buffer(text), size)
            finally:
                kernel32.GlobalUnlock(h_global)
            user32.SetClipboardData(CF_UNICODETEXT, h_global)
        finally:
            user32.CloseClipboard()
    except Exception:
        return

def _find_chrome_windows():
    user32 = ctypes.windll.user32
    titles = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title:
            titles.append((hwnd, title))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return titles

def focus_chrome_window():
    try:
        user32 = ctypes.windll.user32
        titles = _find_chrome_windows()
        if not titles:
            return False
        target = None
        for hwnd, title in titles:
            t = title.lower()
            if "tiktok" in t and "chrome" in t:
                target = hwnd
                break
        if not target:
            for hwnd, title in titles:
                if "chrome" in title.lower():
                    target = hwnd
                    break
        if not target:
            return False
        user32.ShowWindow(target, 9)  # SW_RESTORE
        user32.SetForegroundWindow(target)
        time.sleep(0.05)
        return True
    except Exception:
        return False

def get_chrome_url():
    """Get URL directly from Chrome without simulating keystrokes."""
    if IS_WINDOWS:
        return get_chrome_url_windows()
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
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1.5)
        return result.stdout.strip()
    except:
        return ""

def get_chrome_url_windows():
    """Read URL from Chrome address bar using clipboard."""
    if not focus_chrome_window():
        log("Warn: Could not focus Chrome window")
    prev_clipboard = _get_clipboard_text_windows()
    def copy_address_bar():
        # Try multiple shortcuts to focus the address bar reliably.
        for mode in ("alt_d", "ctrl_l", "f6"):
            if mode == "alt_d":
                with kb.pressed(Key.alt_l):
                    kb.press('d')
                    kb.release('d')
            elif mode == "ctrl_l":
                with kb.pressed(Key.ctrl):
                    kb.press('l')
                    kb.release('l')
            else:
                kb.press(Key.f6)
                kb.release(Key.f6)
            time.sleep(0.12)
            # Ensure text is selected and copied
            with kb.pressed(Key.ctrl):
                kb.press('a')
                kb.release('a')
            time.sleep(0.05)
            with kb.pressed(Key.ctrl):
                kb.press('c')
                kb.release('c')
            time.sleep(0.12)
            candidate = _get_clipboard_text_windows().strip()
            if not candidate:
                candidate = _get_clipboard_text_powershell()
            if candidate:
                return candidate
        return ""

    url = copy_address_bar()
    if not url:
        time.sleep(0.15)
        url = copy_address_bar()
    if not url:
        log("Warn: Clipboard empty after address bar copy")
    # Exit address bar focus so arrow keys act on the page
    kb.press(Key.esc)
    kb.release(Key.esc)
    time.sleep(0.05)
    if prev_clipboard is not None:
        _set_clipboard_text_windows(prev_clipboard)
    return url

def press_down_arrow():
    """Press down arrow key to go to next live."""
    if IS_WINDOWS:
        kb.press(Key.esc)
        kb.release(Key.esc)
        time.sleep(0.05)
        kb.press(Key.down)
        kb.release(Key.down)
        return
    script = 'tell application "System Events" to key code 125'
    subprocess.run(["osascript", "-e", script], capture_output=True)

def get_live_nickname():
    """Get streamer nickname from Chrome tab title."""
    if IS_WINDOWS:
        return ""
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
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1.0)
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
is_running = False
ctrl_l_down = False

def capture_once():
    log("Capturing...")

    url = get_chrome_url()
    if not url:
        log("Error: Could not get Chrome URL")
        show_notification("Error", "Open TikTok in Chrome", "Basso")
        press_down_arrow()
        log("Auto: Next live (no URL)")
        return False, "no_url"

    log(f"URL: {url[:50]}...")

    match = re.search(TIKTOK_REGEX, url)
    if not match:
        log("Skip: Not a TikTok URL")
        return False, "not_tiktok"

    username = match.group(1)

    if username in session_ids:
        log(f"Skip: @{username} already captured")
        if DUPLICATE_DELAY > 0:
            time.sleep(DUPLICATE_DELAY)
        press_down_arrow()
        return False, "duplicate"

    session_ids.add(username)

    nickname = ""
    if ENABLE_NICKNAME:
        nickname = get_live_nickname()
        if nickname:
            log(f"Nickname: {nickname}")

    added = add_creator(username, nickname)
    if added:
        if NEXT_DELAY > 0:
            time.sleep(NEXT_DELAY)
        press_down_arrow()
        log("Auto: Next live")
        return True, "added"

    return False, "not_added"

def on_hotkey():
    global session_ids, last_trigger, is_running

    now = time.time()
    if now - last_trigger < HOTKEY_COOLDOWN:
        return
    last_trigger = now
    if is_running:
        log("Skip: Batch already running")
        return
    is_running = True

    log("Hotkey pressed. Starting batch...")
    run_batch(BATCH_MAX)
    is_running = False

def run_batch(max_count):
    added_count = 0
    for i in range(max_count):
        added, reason = capture_once()
        if added:
            added_count += 1
        if reason == "no_url":
            break
        if BATCH_STEP_DELAY > 0:
            time.sleep(BATCH_STEP_DELAY)

    log(f"Batch done. Added {added_count}/{max_count}")
    show_notification("Batch Done", f"Added {added_count}/{max_count}", "Pop")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true", help="Run one batch without hotkey")
    parser.add_argument("--max", type=int, default=BATCH_MAX, help="Max creators to capture in batch")
    args = parser.parse_args()

    log("=" * 50)
    log("Clipper Bot - One Key Capture")
    log("=" * 50)

    if args.batch:
        log(f"Batch mode: capturing up to {args.max}")
        log("(Use Chrome for TikTok live)")
        run_batch(args.max)
        return

    if IS_WINDOWS:
        log(f"Press {WINDOWS_HOTKEY_LABEL} to auto-capture up to {BATCH_MAX}")
    else:
        log(f"Press Right Ctrl to auto-capture up to {BATCH_MAX}")
    log("(Use Chrome for TikTok live)")
    log("Press Ctrl+C to stop")

    def on_press(key):
        global ctrl_l_down
        if IS_WINDOWS:
            if key == Key.ctrl_l:
                ctrl_l_down = True
                return
            if ctrl_l_down and key == Key.space:
                on_hotkey()
        else:
            if key == HOTKEY:
                on_hotkey()

    def on_release(key):
        global ctrl_l_down
        if IS_WINDOWS and key == Key.ctrl_l:
            ctrl_l_down = False

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n\nClipper Bot stopped.")

if __name__ == "__main__":
    main()
