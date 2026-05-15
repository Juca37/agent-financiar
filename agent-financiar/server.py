#!/usr/bin/env python3
"""
Server web pentru dashboard-ul financiar.
Ruleaza agentul zilnic si serveste datele catre frontend.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, subprocess, threading, time
from datetime import datetime
from agent import ruleaza, get_stats_json, init_db

def ruleaza_periodic():
    """Ruleaza agentul o data pe zi."""
    init_db()
    while True:
        try:
            print(f"[{datetime.now()}] Rulare agent...")
            ruleaza()
        except Exception as e:
            print(f"Eroare agent: {e}")
        # Asteapta 24 ore
        time.sleep(86400)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suprima logurile HTTP

    def do_GET(self):
        if self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            try:
                stats = get_stats_json()
                self.wfile.write(json.dumps(stats).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error":str(e)}).encode())

        elif self.path == "/api/ruleaza":
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            try:
                stats = ruleaza()
                self.wfile.write(json.dumps({"ok":True,"stats":stats}).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())

        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            with open("dashboard.html","rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    init_db()

    # Porneste agentul in background
    t = threading.Thread(target=ruleaza_periodic, daemon=True)
    t.start()

    print(f"Server pornit pe portul {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
