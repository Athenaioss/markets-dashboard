#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ATLAS NEXUS — MARKETS MASTER PIPELINE                     ║
║  Runs all 4 pipelines: Crypto + Commodities + Indices + FX ║
╚══════════════════════════════════════════════════════════════╝
"""

import subprocess, sys, os
from datetime import datetime
from pathlib import Path

PIPELINES = [
    ("../sprint4_pipeline.py", "Crypto"),
    ("commodities_pipeline.py", "Commodities"),
    ("indices_pipeline.py", "Indices"),
    ("forex_pipeline.py", "Forex"),
]

OUTPUT_DIR = Path("output")

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  🔮 ATLAS NEXUS — MARKETS PIPELINE           ║")
    print("║  Crypto · Commodities · Indices · Forex      ║")
    print("╚══════════════════════════════════════════════╝\n")
    
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    results = {}
    for script, name in PIPELINES:
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")
        
        try:
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True, timeout=120
            )
            print(result.stdout)
            if result.stderr:
                print(f"  STDERR: {result.stderr[:200]}")
            results[name] = "✅" if result.returncode == 0 else "❌"
        except subprocess.TimeoutExpired:
            print(f"  ⏰ TIMEOUT")
            results[name] = "⏰"
        except Exception as e:
            print(f"  ❌ {e}")
            results[name] = "❌"
    
    print(f"\n{'='*50}")
    print("  📋 RESULTS")
    print(f"{'='*50}")
    for name, status in results.items():
        print(f"  {status} {name}")
    
    # Generate index page
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🔮 Atlas Nexus — Markets Dashboard</title>
<style>
:root{{--bg:#080b16;--card:#0f1420;--border:#1a2040;--text:#e2e8f0;--muted:#64748b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center}}
.container{{text-align:center;padding:40px}}
h1{{font-size:3em;font-weight:800;background:linear-gradient(135deg,#38bdf8,#818cf8,#f59e0b,#22c55e);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}}
.subtitle{{color:var(--muted);margin-bottom:40px;font-size:1.1em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;max-width:1000px;margin:0 auto}}
.panel{{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:30px;text-align:center;text-decoration:none;color:var(--text);transition:all .2s}}
.panel:hover{{transform:translateY(-4px);border-color:var(--accent)}}
.panel .emoji{{font-size:3em;margin-bottom:12px}}
.panel h2{{font-size:1.3em;margin-bottom:8px}}
.panel .desc{{color:var(--muted);font-size:.9em}}
.panel-1:hover{{border-color:#38bdf8}}
.panel-2:hover{{border-color:#f59e0b}}
.panel-3:hover{{border-color:#818cf8}}
.panel-4:hover{{border-color:#22c55e}}
.footer{{margin-top:40px;color:var(--muted);font-size:.85em}}
</style></head>
<body>
<div class="container">
<h1>🔮 Atlas Nexus Markets</h1>
<p class="subtitle">Multi-asset intelligence pipeline · Real-time data · Automated analytics</p>
<div class="grid">
<a href="../enhanced_dashboard.html" class="panel panel-1">
<div class="emoji">🪙</div><h2>Crypto</h2>
<div class="desc">Bitcoin, Ethereum, Solana & 100+ tokens</div></a>
<a href="commodities_dashboard.html" class="panel panel-2">
<div class="emoji">🛢️</div><h2>Commodities</h2>
<div class="desc">Gold, Oil, Copper, Grains & Softs</div></a>
<a href="indices_dashboard.html" class="panel panel-3">
<div class="emoji">📈</div><h2>Indices</h2>
<div class="desc">S&P 500, Nasdaq, FTSE, DAX, Nikkei</div></a>
<a href="forex_dashboard.html" class="panel panel-4">
<div class="emoji">💱</div><h2>Forex</h2>
<div class="desc">Majors, Minors & Exotic currency pairs</div></a>
</div>
<div class="footer"><p>🔮 Built by <strong>Atlas Nexus</strong> · Multi-source pipeline · Updated daily</p>
<p style="margin-top:4px"><a href="https://github.com/AtlasNexusOps/birdeye-sprint4" style="color:#38bdf8">github.com/AtlasNexusOps/birdeye-sprint4</a></p>
</div></div></body></html>"""
    
    (OUTPUT_DIR / "index.html").write_text(index_html)
    print(f"\n✅ Master index: output/index.html")

if __name__ == "__main__":
    main()
