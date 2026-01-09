import http.server
import socketserver
import json
import subprocess
import os
import threading
import time
import uuid
import urllib.parse

PORT = 8000
DIRECTORY = "."
VERIFY_TIMEOUT_SECONDS = 1800
JOBS_DIR = "verification_jobs"
LOG_FILE = "verification_jobs.log"
JOBS = {}


def ensure_jobs_dir():
    os.makedirs(JOBS_DIR, exist_ok=True)


def log_line(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def job_path(job_id):
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def save_job(job_id, payload):
    ensure_jobs_dir()
    with open(job_path(job_id), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_job(job_id):
    if job_id in JOBS:
        return JOBS[job_id]
    path = job_path(job_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def run_verify_job(job_id):
    job = JOBS[job_id]
    job["status"] = "running"
    job["started_at"] = time.time()
    save_job(job_id, job)
    log_line(f"verify start job_id={job_id}")

    try:
        process = subprocess.Popen(
            ["python3", "verify_creators.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        job["pid"] = process.pid
        save_job(job_id, job)

        stdout, stderr = process.communicate(timeout=VERIFY_TIMEOUT_SECONDS)
        job["exit_code"] = process.returncode
        job["stdout"] = stdout
        job["stderr"] = stderr
        job["finished_at"] = time.time()

        if process.returncode == 0:
            job["status"] = "success"
        else:
            job["status"] = "error"
    except subprocess.TimeoutExpired:
        job["status"] = "timeout"
        job["finished_at"] = time.time()
        job["stderr"] = (job.get("stderr") or "") + "Verification timed out."
    except Exception as e:
        job["status"] = "error"
        job["finished_at"] = time.time()
        job["stderr"] = str(e)

    save_job(job_id, job)
    log_line(f"verify end job_id={job_id} status={job['status']}")

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/streamers':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            streamers_data = []
            verified_creators_map = {}
            
            # Load verified creators if available
            if os.path.exists('verified_creators.json'):
                try:
                    with open('verified_creators.json', 'r', encoding='utf-8') as f:
                        verification_data = json.load(f)
                        for creator in verification_data.get('available_creators', []):
                            verified_creators_map[creator['id']] = creator
                except:
                    pass
            
            # Prefer JSON file
            if os.path.exists('streamers_data.json'):
                try:
                    with open('streamers_data.json', 'r', encoding='utf-8') as f:
                        streamers_data = json.load(f)
                        # Add verification status to each streamer
                        for streamer in streamers_data:
                            if streamer['id'] in verified_creators_map:
                                streamer['verified_status'] = 'available'
                            else:
                                streamer['verified_status'] = 'unverified'
                except:
                    pass
            # Fallback to text file (convert to objects)
            elif os.path.exists('active_streamers.txt'):
                 with open('active_streamers.txt', 'r') as f:
                    for line in f:
                        if line.strip():
                            streamer = {"id": line.strip(), "nickname": line.strip(), "followers": "-", "likes": "-", "verified_status": "unverified"}
                            if line.strip() in verified_creators_map:
                                streamer['verified_status'] = 'available'
                            streamers_data.append(streamer)
            
            self.wfile.write(json.dumps({"streamers": streamers_data}).encode())
        
        elif self.path == '/verified':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            verified_data = {"available_creators": []}
            
            # Load verified creators if available
            if os.path.exists('verified_creators.json'):
                try:
                    with open('verified_creators.json', 'r', encoding='utf-8') as f:
                        verified_data = json.load(f)
                except:
                    pass
            
            self.wfile.write(json.dumps(verified_data).encode())

        elif self.path.startswith('/verify/status'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            job_id = (params.get("job_id") or [None])[0]

            if not job_id:
                self.send_error(400, "Missing job_id")
                return

            job = load_job(job_id)
            if not job:
                self.send_error(404, "Unknown job_id")
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"job": job}).encode())
        
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/crawl':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Run the crawler script in headless mode (background)
            try:
                
                print("Running crawler...")
                subprocess.run(["python3", "crawler.py", "--headless"], check=True)
                
                self.wfile.write(json.dumps({"status": "success", "message": "Crawling finished"}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        
        elif self.path == '/verify':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Run the verification script (opens browser for interactive verification)
            try:
                print("Starting creator verification on backstage...")
                job_id = uuid.uuid4().hex
                job = {
                    "job_id": job_id,
                    "status": "queued",
                    "created_at": time.time(),
                    "started_at": None,
                    "finished_at": None,
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "",
                    "pid": None,
                }
                JOBS[job_id] = job
                save_job(job_id, job)

                thread = threading.Thread(target=run_verify_job, args=(job_id,), daemon=True)
                thread.start()

                self.wfile.write(json.dumps({
                    "status": "success",
                    "job_id": job_id,
                    "message": "Verification started. A browser window will open for manual verification.",
                }).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())

        elif self.path == '/send_dm':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            handle = data.get("handle")
            message = data.get("message")
            
            if not handle or not message:
                self.wfile.write(json.dumps({"status": "error", "message": "Missing handle or message"}).encode())
                return

            try:
                print(f"Requesting DM send to @{handle}...")
                # Run the send_dm.py script
                # We use subprocess.run to wait for it (synchronous for simpler error handling)
                # Headed mode is default in the script.
                result = subprocess.run(
                    ["python3", "send_dm.py", handle, message],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    self.wfile.write(json.dumps({"status": "success", "message": "Message process completed."}).encode())
                else:
                    self.wfile.write(json.dumps({"status": "error", "message": f"Script failed: {result.stdout} {result.stderr}"}).encode())
            
            except Exception as e:
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        
        else:
            self.send_error(404)

print(f"Server started at http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
