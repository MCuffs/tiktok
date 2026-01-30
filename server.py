import http.server
import socketserver
import json
import subprocess
import os
import threading
import time
import uuid
import urllib.parse

PORT = 8091
PENDING_FILE = "pending_creators.json"
VERIFIED_FILE = "verified_creators.json"
DM_STATUS_FILE = "dm_status.json"
LOG_FILE = "server.log"

VERIFY_PROCESS = None
CLIPPER_PROCESS = None
DM_PROCESS = None


def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(filepath, default=None):
    if default is None:
        default = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Handler(http.server.SimpleHTTPRequestHandler):

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Get pending creators
        if path == "/pending":
            data = load_json(PENDING_FILE, [])
            self.send_json({"creators": data})

        # Get verified creators
        elif path == "/verified":
            data = load_json(VERIFIED_FILE, {"available": [], "unavailable": []})
            self.send_json(data)

        # Get all creators (combined view)
        elif path == "/creators":
            pending = load_json(PENDING_FILE, [])
            verified = load_json(VERIFIED_FILE, {"available": [], "unavailable": []})

            all_creators = []

            # Add pending
            for c in pending:
                creator = {
                    "id": c["id"],
                    "status": "pending",
                    "added_at": c.get("added_at", 0)
                }
                if c.get("nickname"):
                    creator["nickname"] = c["nickname"]
                all_creators.append(creator)

            # Add verified (available) - support both formats
            available_list = verified.get("available", []) or verified.get("available_creators", [])
            for c in available_list:
                creator = {
                    "id": c["id"],
                    "status": "available",
                    "reason": c.get("reason", "사용 가능"),
                    "verified_at": c.get("verified_at", 0)
                }
                if c.get("nickname"):
                    creator["nickname"] = c["nickname"]
                all_creators.append(creator)

            # Add verified (unavailable) - support both formats
            unavailable_list = verified.get("unavailable", []) or verified.get("unavailable_creators", [])
            for c in unavailable_list:
                creator = {
                    "id": c["id"],
                    "status": "unavailable",
                    "reason": c.get("reason", ""),
                    "verified_at": c.get("verified_at", 0)
                }
                if c.get("nickname"):
                    creator["nickname"] = c["nickname"]
                all_creators.append(creator)

            # Sort: available first, then by time (newest first)
            def get_sort_key(x):
                # Priority: available=0, pending=1, unavailable=2
                status_priority = {"available": 0, "pending": 1, "unavailable": 2}
                priority = status_priority.get(x.get("status"), 1)

                # Time value
                val = x.get("added_at") or x.get("verified_at") or 0
                if isinstance(val, str):
                    val = 0

                return (priority, -val)  # Sort by priority first, then newest
            all_creators.sort(key=get_sort_key)

            self.send_json({"creators": all_creators})

        # Clipper status
        elif path == "/clipper/status":
            running = CLIPPER_PROCESS and CLIPPER_PROCESS.poll() is None
            self.send_json({"running": running})

        # Verify status
        elif path == "/verify/status":
            running = VERIFY_PROCESS and VERIFY_PROCESS.poll() is None
            self.send_json({"running": running})

        # DM status
        elif path == "/dm/status":
            dm_data = load_json(DM_STATUS_FILE, {"sent": [], "failed": []})
            running = DM_PROCESS and DM_PROCESS.poll() is None
            self.send_json({
                "running": running,
                "sent": dm_data.get("sent", []),
                "failed": dm_data.get("failed", [])
            })

        # Logs
        elif path == "/logs":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            content = ""
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        f.seek(0, os.SEEK_END)
                        size = f.tell()
                        f.seek(max(size - 4096, 0))
                        content = f.read()
                except:
                    content = "Error reading logs"
            self.wfile.write(content.encode())

        else:
            super().do_GET()

    def do_POST(self):
        global CLIPPER_PROCESS, VERIFY_PROCESS, DM_PROCESS

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Start clipper
        if path == "/clipper/start":
            if CLIPPER_PROCESS and CLIPPER_PROCESS.poll() is None:
                self.send_json({"status": "error", "message": "Already running"})
                return

            log("Starting clipper bot...")
            CLIPPER_PROCESS = subprocess.Popen(
                ["python3", "clipper_bot.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            self.send_json({"status": "success", "message": "Clipper started"})

        # Stop clipper
        elif path == "/clipper/stop":
            if CLIPPER_PROCESS and CLIPPER_PROCESS.poll() is None:
                CLIPPER_PROCESS.terminate()
                CLIPPER_PROCESS = None
                self.send_json({"status": "success", "message": "Clipper stopped"})
            else:
                self.send_json({"status": "error", "message": "Not running"})

        # Start verification
        elif path == "/verify":
            if VERIFY_PROCESS and VERIFY_PROCESS.poll() is None:
                self.send_json({"status": "error", "message": "Verification already running"})
                return

            pending = load_json(PENDING_FILE, [])
            if not pending:
                self.send_json({"status": "error", "message": "No pending creators"})
                return

            log(f"Starting verification for {len(pending)} creators...")
            VERIFY_PROCESS = subprocess.Popen(
                ["python3", "verify_batch.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            self.send_json({"status": "success", "message": f"Verifying {len(pending)} creators"})

        # Clear verified only (keep pending)
        elif path == "/clear":
            save_json(VERIFIED_FILE, {"available": [], "unavailable": []})
            self.send_json({"status": "success", "message": "Cleared verified creators"})

        # Login
        elif path == "/login":
            log("Opening login browser...")
            subprocess.Popen(["python3", "setup_login.py"])
            self.send_json({"status": "success", "message": "Login browser opened"})

        # Send DM to single creator
        elif path == "/dm/send":
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body)
                handle = data.get("id", "")
                nickname = data.get("nickname", "")
                lang = data.get("lang", "kr")

                if not handle:
                    self.send_json({"status": "error", "message": "No handle provided"})
                    return

                log(f"Sending DM to @{handle}...")
                DM_PROCESS = subprocess.Popen(
                    ["python3", "send_dm.py", handle, nickname, lang],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )
                self.send_json({"status": "success", "message": f"DM sending to @{handle}"})

            except json.JSONDecodeError:
                self.send_json({"status": "error", "message": "Invalid JSON"})

        # Send DM to all available creators
        elif path == "/dm/send-all":
            if DM_PROCESS and DM_PROCESS.poll() is None:
                self.send_json({"status": "error", "message": "DM process already running"})
                return

            # Read request body for lang preference
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

            try:
                data = json.loads(body) if body else {}
                lang = data.get("lang", "kr")

                # Get available creators that haven't been DMed
                verified = load_json(VERIFIED_FILE, {"available": [], "unavailable": []})
                dm_status = load_json(DM_STATUS_FILE, {"sent": [], "failed": []})

                available = verified.get("available", []) or verified.get("available_creators", [])
                sent_ids = set(s.get("id") for s in dm_status.get("sent", []))

                to_dm = [c for c in available if c.get("id") not in sent_ids]

                if not to_dm:
                    self.send_json({"status": "error", "message": "No creators to DM"})
                    return

                log(f"Starting batch DM to {len(to_dm)} creators...")

                # Write batch file for the DM script
                with open("dm_batch.json", "w", encoding="utf-8") as f:
                    json.dump({"creators": to_dm, "lang": lang}, f, ensure_ascii=False)

                DM_PROCESS = subprocess.Popen(
                    ["python3", "send_dm_batch.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
                )
                self.send_json({"status": "success", "message": f"DM batch started for {len(to_dm)} creators"})

            except json.JSONDecodeError:
                self.send_json({"status": "error", "message": "Invalid JSON"})

        # Clear DM status
        elif path == "/dm/clear":
            save_json(DM_STATUS_FILE, {"sent": [], "failed": []})
            self.send_json({"status": "success", "message": "DM status cleared"})

        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Delete specific creator
        if path.startswith("/pending/"):
            creator_id = path.replace("/pending/", "")
            pending = load_json(PENDING_FILE, [])
            pending = [c for c in pending if c["id"] != creator_id]
            save_json(PENDING_FILE, pending)
            self.send_json({"status": "success", "message": f"Deleted {creator_id}"})

        elif path.startswith("/verified/"):
            creator_id = path.replace("/verified/", "")
            verified = load_json(VERIFIED_FILE, {"available": [], "unavailable": []})
            verified["available"] = [c for c in verified["available"] if c["id"] != creator_id]
            verified["unavailable"] = [c for c in verified["unavailable"] if c["id"] != creator_id]
            save_json(VERIFIED_FILE, verified)
            self.send_json({"status": "success", "message": f"Deleted {creator_id}"})

        else:
            self.send_error(404)


if __name__ == "__main__":
    # Clear log on start
    with open(LOG_FILE, "w") as f:
        f.write("")

    log(f"Server starting on http://localhost:{PORT}")

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
