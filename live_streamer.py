#!/usr/bin/env python3
"""
🔄 Live Price Streamer — fetches Yahoo prices, commits to GitHub every 5min
Frontend polls live_prices.json from GitHub Pages.
Designed to run as a cron job or systemd timer.
"""

import json, os, urllib.request, time, subprocess, sys
from datetime import datetime
from pathlib import Path

# Symbols to track (from scanner + dashboards)
SYMBOLS = [
    "^GSPC","^IXIC","^DJI","^FTSE","^GDAXI","^FCHI","^N225",
    "GC=F","SI=F","CL=F",
    "AAPL","MSFT","NVDA","TSLA","GOOGL","AMZN",
    "SPY","QQQ","GLD","ARKK",
    "BTC-USD","ETH-USD",
]

OUTPUT_FILE = Path("live_prices.json")
BATCH_SIZE = 10

def fetch_batch(symbols):
    """Fetch current prices from Yahoo v8 chart API (1d range)."""
    prices = {}
    for sym in symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=5m"
        req = urllib.request.Request(url, headers={"User-Agent": "AtlasNexus/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                result = data.get("chart", {}).get("result", [{}])[0]
                meta = result.get("meta", {})
                prices[sym] = {
                    "price": meta.get("regularMarketPrice", 0),
                    "change": meta.get("regularMarketPrice", 0) - meta.get("previousClose", 0),
                    "change_pct": round(
                        (meta.get("regularMarketPrice", 0) - meta.get("previousClose", 1))
                        / meta.get("previousClose", 1) * 100, 2
                    ) if meta.get("previousClose") else 0,
                    "prev_close": meta.get("previousClose", 0),
                }
        except Exception as e:
            pass  # Skip failed symbols
        time.sleep(0.15)  # Rate limit
    return prices

def main():
    print(f"🔄 Live Price Streamer — {datetime.now().strftime('%H:%M:%S')}")
    
    all_prices = {}
    for sym in SYMBOLS:
        prices = fetch_batch([sym])  # Using single-symbol fetch
        all_prices.update(prices)
    
    all_prices["_updated"] = datetime.now().isoformat()
    
    # Write JSON
    OUTPUT_FILE.write_text(json.dumps(all_prices, indent=2))
    print(f"  ✅ {len(all_prices)-1} prices → {OUTPUT_FILE}")
    
    # Git commit + push (skip in CI — handled by workflow)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("  ⏭️ CI mode — skipping git push (handled by workflow)")
    else:
        try:
            subprocess.run(["git", "add", str(OUTPUT_FILE)], capture_output=True, timeout=10)
            r = subprocess.run(
                ["git", "commit", "-m", f"live prices {datetime.now().strftime('%H:%M')}"],
                capture_output=True, timeout=10
            )
            subprocess.run(["git", "push"], capture_output=True, timeout=15)
            print("  ✅ Pushed to GitHub")
        except Exception as e:
            print(f"  ⚠️ Git push failed: {e}")

if __name__ == "__main__":
    main()
