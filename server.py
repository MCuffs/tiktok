import http.server
import socketserver
import json
import subprocess
import os

PORT = 8000
DIRECTORY = "."

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/streamers':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            streamers_data = []
            # Prefer JSON file
            if os.path.exists('streamers_data.json'):
                try:
                    with open('streamers_data.json', 'r') as f:
                        streamers_data = json.load(f)
                except:
                    pass
            # Fallback to text file (convert to objects)
            elif os.path.exists('active_streamers.txt'):
                 with open('active_streamers.txt', 'r') as f:
                    for line in f:
                        if line.strip():
                            streamers_data.append({"id": line.strip(), "nickname": line.strip(), "followers": "-", "likes": "-"})
            
            self.wfile.write(json.dumps({"streamers": streamers_data}).encode())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/crawl':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Run the crawler script
            try:
                # We assume crawler.py is in the current directory and runnable
                # Running in headless mode for the server background task usually, 
                # but user might want to see browser. Let's force headless=False as per previous context?
                # Or maybe headless=True is better for a "background" button effect. 
                # Let's use the default (which currently uses saved session and defaults to headless=False in script if not arg provided).
                
                # To make it "background" feel, perhaps we return immediately? 
                # But the user probably wants to wait.
                
                print("Running crawler...")
                subprocess.run(["python3", "crawler.py"], check=True)
                
                self.wfile.write(json.dumps({"status": "success", "message": "Crawling finished"}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        else:
            self.send_error(404)

print(f"Server started at http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
