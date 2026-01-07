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
            
            # Run the crawler script in headless mode (background)
            try:
                
                print("Running crawler...")
                subprocess.run(["python3", "crawler.py", "--headless"], check=True)
                
                self.wfile.write(json.dumps({"status": "success", "message": "Crawling finished"}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        else:
            self.send_error(404)

print(f"Server started at http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
