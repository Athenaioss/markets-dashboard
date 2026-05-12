#!/usr/bin/env python3
"""
Atlas Nexus — Markets API Proxy
Serves Yahoo Finance data to browser dashboards via CORS
Usage: python3 proxy_server.py [--port 8765]
"""

import json, urllib.request, http.server, os, sys
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--port" else 8765

class Proxy(http.server.HTTPServer):
    allow_reuse_address = True

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        
        # CORS
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "max-age=60")
        self.end_headers()
        
        try:
            if path.startswith("/chart/"):
                symbol = path.split("/chart/")[1]
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    result = data.get("chart", {}).get("result", [{}])[0]
                    meta = result.get("meta", {})
                    quotes = result.get("indicators", {}).get("quote", [{}])[0]
                    clean = [p for p in quotes.get("close", []) if p is not None]
                    
                    payload = {
                        "price": meta.get("regularMarketPrice"),
                        "change": meta.get("regularMarketPrice", 0) - meta.get("previousClose", meta.get("regularMarketPrice", 0)),
                        "changePct": (meta.get("regularMarketPrice", 0) - meta.get("previousClose", meta.get("regularMarketPrice", 0))) / meta.get("previousClose", 1) * 100,
                        "high": meta.get("regularMarketDayHigh"),
                        "low": meta.get("regularMarketDayLow"),
                        "prevClose": meta.get("previousClose"),
                        "history": clean[-5:] if clean else []
                    }
                    self.wfile.write(json.dumps(payload).encode())
            elif path == "/health":
                self.wfile.write(json.dumps({"status":"ok"}).encode())
            else:
                self.wfile.write(json.dumps({"error":"unknown endpoint"}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def log_message(self, format, *args):
        pass  # Silence logs

print(f"🔮 Atlas Nexus API Proxy → http://localhost:{PORT}")
print(f"   Endpoints: /chart/SYMBOL")
httpd = Proxy(("", PORT), Handler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\n👋 Done")
