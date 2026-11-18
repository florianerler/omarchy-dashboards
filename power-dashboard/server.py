#!/usr/bin/env python3
"""Web-Variante des Strom-Dashboards (http://127.0.0.1:8765)."""
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from power import sample

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/api"):
            body, ct = json.dumps(sample()).encode(), "application/json"
        else:
            with open(os.path.join(os.path.dirname(__file__), "index.html"), "rb") as f:
                body, ct = f.read(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print("Dashboard: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
