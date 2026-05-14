#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  BIRDEYE DATA BIP — SPRINT 4                              ║
║  Atlas Nexus Submission                                   ║
║  Multi-source crypto analytics pipeline + dashboard       ║
╚══════════════════════════════════════════════════════════════╝

Sprint 4 Enhancements (vs Sprint 3):
  • Multi-source: CoinGecko + Birdeye BDS + DEX Screener
  • Advanced enrichment: volatility, momentum, liquidity scoring
  • Time-series tracking: 7-day trends, volume patterns
  • Interactive HTML dashboard export
  • Token discovery: top gainers, hidden gems, unusual volume
  • Correlation matrix & market regime detection

Usage:
  python sprint4_pipeline.py                    # Multi-source, all exports
  python sprint4_pipeline.py --birdeye KEY       # Add Birdeye BDS
  python sprint4_pipeline.py --html dashboard    # Interactive dashboard
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error
from dashboard_theme import enhance_dashboard_html
from sentiment import momentum_scanner_html, tools_section_html

# ════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════

BIRDEYE_API = "https://public-api.birdeye.so"
COINGECKO_API = "https://api.coingecko.com/api/v3"
DEXSCREENER_API = "https://api.dexscreener.com/latest"
OUTPUT_DIR = Path("output")

NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

# ════════════════════════════════════════════════════════════
# DATA FETCHING — Multi-Source
# ════════════════════════════════════════════════════════════

def fetch_coingecko_markets(per_page=100):
    """Fetch top tokens by market cap from CoinGecko (free tier)."""
    url = f"{COINGECKO_API}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={per_page}&page=1&sparkline=true&price_change_percentage=24h,7d"
    req = urllib.request.Request(url, headers={"User-Agent": "AtlasNexus-Sprint4/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"⚠️ CoinGecko: {e}")
        return []

def fetch_coingecko_trending():
    """Fetch trending tokens from CoinGecko."""
    url = f"{COINGECKO_API}/search/trending"
    req = urllib.request.Request(url, headers={"User-Agent": "AtlasNexus-Sprint4/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [c['item'] for c in data.get('coins', [])]
    except Exception as e:
        print(f"⚠️ CoinGecko trending: {e}")
        return []

def fetch_coingecko_global():
    """Fetch global market stats."""
    url = f"{COINGECKO_API}/global"
    req = urllib.request.Request(url, headers={"User-Agent": "AtlasNexus-Sprint4/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}

def fetch_dexscreener_trending():
    """Fetch trending pairs from DEX Screener."""
    url = f"{DEXSCREENER_API}/dex/trending?limit=20"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get('pairs', [])
    except Exception as e:
        print(f"⚠️ DEX Screener: {e}")
        return []

def fetch_birdeye_tokenlist(api_key):
    """Fetch token list from Birdeye BDS."""
    url = f"{BIRDEYE_API}/v1/tokenlist"
    headers = {"X-API-KEY": api_key, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"⚠️ Birdeye BDS: {e}")
        return []

# ════════════════════════════════════════════════════════════
# DATA NORMALIZATION — Unified Schema
# ════════════════════════════════════════════════════════════

def normalize_coingecko(coins):
    """Normalize CoinGecko data to unified schema."""
    normalized = []
    for c in coins:
        normalized.append({
            "id": c.get("id"),
            "symbol": (c.get("symbol") or "").upper(),
            "name": c.get("name"),
            "source": "coingecko",
            "price_usd": c.get("current_price"),
            "market_cap": c.get("market_cap"),
            "volume_24h": c.get("total_volume"),
            "change_24h": c.get("price_change_percentage_24h"),
            "change_7d": c.get("price_change_percentage_7d_in_currency"),
            "ath": c.get("ath"),
            "ath_change_pct": c.get("ath_change_percentage"),
            "circulating_supply": c.get("circulating_supply"),
            "total_supply": c.get("total_supply"),
            "sparkline_7d": c.get("sparkline_in_7d", {}).get("price", []),
            "timestamp": NOW
        })
    return normalized

def normalize_dexscreener(pairs):
    """Normalize DEX Screener data to unified schema."""
    normalized = []
    for p in pairs:
        normalized.append({
            "id": p.get("pairAddress"),
            "symbol": (p.get("baseToken", {}).get("symbol") or "").upper(),
            "name": p.get("baseToken", {}).get("name"),
            "source": "dexscreener",
            "price_usd": float(p.get("priceUsd", 0) or 0),
            "market_cap": float(p.get("fdv", 0) or 0),
            "volume_24h": p.get("volume", {}).get("h24"),
            "change_24h": p.get("priceChange", {}).get("h24"),
            "liquidity_usd": float(p.get("liquidity", {}).get("usd", 0) or 0),
            "txns_24h": (p.get("txns", {}).get("h24", {}).get("buys", 0) or 0) + 
                        (p.get("txns", {}).get("h24", {}).get("sells", 0) or 0),
            "dex": p.get("dexId"),
            "chain": p.get("chainId"),
            "timestamp": NOW
        })
    return normalized

# ════════════════════════════════════════════════════════════
# DATA CLEANING
# ════════════════════════════════════════════════════════════

def clean_data(data: list) -> list:
    """Clean and deduplicate token data."""
    cleaned = []
    seen = set()
    
    for item in data:
        # Skip null tokens
        if not item.get("symbol") or not item.get("name"):
            continue
        # Deduplicate
        key = (item["symbol"], item.get("source", ""))
        if key in seen:
            continue
        seen.add(key)
        
        # Fill nulls with sensible defaults
        for field in ["price_usd", "market_cap", "volume_24h", "change_24h", "change_7d"]:
            if item.get(field) is None:
                item[field] = 0.0
        
        # Skip 0-value tokens
        if item.get("price_usd", 0) == 0 and item.get("market_cap", 0) == 0:
            continue
            
        cleaned.append(item)
    
    return cleaned

# ════════════════════════════════════════════════════════════
# ENRICHMENT — Sprint 4 Advanced Analytics
# ════════════════════════════════════════════════════════════

def enrich_data(data: list) -> list:
    """Add advanced metrics to each token."""
    prices = [d.get("price_usd", 0) for d in data if d.get("price_usd")]
    volumes = [d.get("volume_24h", 0) for d in data if d.get("volume_24h")]
    mcap_values = [d.get("market_cap", 0) for d in data if d.get("market_cap")]
    
    avg_vol = sum(volumes) / len(volumes) if volumes else 0
    avg_mcap = sum(mcap_values) / len(mcap_values) if mcap_values else 0
    
    for token in data:
        price = token.get("price_usd", 0) or 0
        change_24h = token.get("change_24h", 0) or 0
        change_7d = token.get("change_7d", 0) or 0
        volume = token.get("volume_24h", 0) or 0
        mcap = token.get("market_cap", 0) or 0
        
        # Volatility classification
        if abs(change_24h) > 10:
            token["volatility"] = "HIGH"
        elif abs(change_24h) > 3:
            token["volatility"] = "MEDIUM"
        else:
            token["volatility"] = "LOW"
        
        # Market cap tier
        if mcap and mcap > 10_000_000_000:
            token["mcap_tier"] = "LARGE_CAP"
        elif mcap and mcap > 1_000_000_000:
            token["mcap_tier"] = "MID_CAP"
        elif mcap and mcap > 100_000_000:
            token["mcap_tier"] = "SMALL_CAP"
        elif mcap and mcap > 0:
            token["mcap_tier"] = "MICRO_CAP"
        else:
            token["mcap_tier"] = "UNKNOWN"
        
        # Volume/MCap ratio (liquidity proxy)
        if mcap and mcap > 0:
            token["volume_mcap_ratio"] = round(volume / mcap, 4)
        else:
            token["volume_mcap_ratio"] = 0
        
        # Momentum score (weighted: 24h + 7d)
        token["momentum_score"] = round((change_24h * 0.6) + (change_7d * 0.4), 2)
        
        # Unusual volume flag (2x average)
        token["unusual_volume"] = volume > (avg_vol * 2) if avg_vol else False
        
        # Trend direction
        if change_24h > 5:
            token["trend"] = "STRONG_UP"
        elif change_24h > 1:
            token["trend"] = "UP"
        elif change_24h < -5:
            token["trend"] = "STRONG_DOWN"
        elif change_24h < -1:
            token["trend"] = "DOWN"
        else:
            token["trend"] = "FLAT"
    
    return data

# ════════════════════════════════════════════════════════════
# ANALYTICS — Market Intelligence
# ════════════════════════════════════════════════════════════

def compute_market_summary(data: list) -> dict:
    """Generate market intelligence summary."""
    trends = [t["trend"] for t in data]
    volatilities = [t["volatility"] for t in data]
    tiers = [t["mcap_tier"] for t in data]
    
    gainers = sorted(
        [t for t in data if t.get("change_24h", 0) and t["change_24h"] > 0],
        key=lambda x: x["change_24h"], reverse=True
    )[:10]
    
    losers = sorted(
        [t for t in data if t.get("change_24h", 0) and t["change_24h"] < 0],
        key=lambda x: x["change_24h"]
    )[:10]
    
    unusual = [t for t in data if t.get("unusual_volume")]
    
    return {
        "total_tokens": len(data),
        "market_sentiment": {
            "strong_up": trends.count("STRONG_UP"),
            "up": trends.count("UP"),
            "flat": trends.count("FLAT"),
            "down": trends.count("DOWN"),
            "strong_down": trends.count("STRONG_DOWN")
        },
        "volatility_distribution": {
            "high": volatilities.count("HIGH"),
            "medium": volatilities.count("MEDIUM"),
            "low": volatilities.count("LOW")
        },
        "market_cap_distribution": {t: tiers.count(t) for t in set(tiers)},
        "top_gainers": gainers,
        "top_losers": losers,
        "unusual_volume_tokens": unusual[:10],
        "total_market_cap": sum(t.get("market_cap", 0) or 0 for t in data),
        "avg_24h_change": round(sum(t.get("change_24h", 0) or 0 for t in data) / len(data), 2) if data else 0,
        "generated_at": NOW
    }

# ════════════════════════════════════════════════════════════
# EXPORT — Multiple Formats
# ════════════════════════════════════════════════════════════

def export_json(data: dict, filename: str):
    """Export to JSON."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"✅ JSON: {path} ({os.path.getsize(path)} bytes)")

def export_csv(tokens: list, filename: str):
    """Export tokens to CSV."""
    if not tokens:
        return
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    
    # Select key fields for CSV
    fields = ["symbol", "name", "source", "price_usd", "market_cap", "volume_24h",
              "change_24h", "change_7d", "volatility", "mcap_tier", "trend", "momentum_score"]
    
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(tokens)
    print(f"✅ CSV: {path} ({os.path.getsize(path)} bytes)")

def export_html_dashboard(tokens: list, summary: dict, filename: str):
    """Generate an interactive HTML dashboard."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    
    # Build token rows
    rows = ""
    for t in tokens[:50]:
        change_24h = t.get("change_24h", 0) or 0
        color = "#22c55e" if change_24h > 0 else "#ef4444" if change_24h < 0 else "#6b7280"
        arrow = "▲" if change_24h > 0 else "▼" if change_24h < 0 else "—"
        
        rows += f"""
        <tr>
            <td><strong>{t.get('symbol','?')}</strong> <small>{t.get('name','')[:20]}</small></td>
            <td>{t.get('source','?')}</td>
            <td>${t.get('price_usd',0) or 0:.4f}</td>
            <td>${(t.get('market_cap',0) or 0)/1e6:.1f}M</td>
            <td style="color:{color}">{arrow} {change_24h:.2f}%</td>
            <td><span class="badge badge-{t.get('volatility','LOW').lower()}">{t.get('volatility','?')}</span></td>
            <td><span class="badge badge-tier">{t.get('mcap_tier','?')}</span></td>
            <td>{t.get('momentum_score',0):.1f}</td>
        </tr>"""
    
    momentum_html = momentum_scanner_html(tokens)
    tools_html = tools_section_html()
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Atlas Nexus — Crypto Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
        .header {{ text-align: center; padding: 30px; background: linear-gradient(135deg, #1e293b, #0f172a); border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }}
        .header h1 {{ font-size: 2em; background: linear-gradient(90deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header p {{ color: #94a3b8; margin-top: 8px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; text-align: center; }}
        .card .value {{ font-size: 2em; font-weight: bold; }}
        .card .label {{ color: #94a3b8; font-size: 0.9em; margin-top: 5px; }}
        .up {{ color: #22c55e; }} .down {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }}
        th {{ background: #334155; padding: 12px; text-align: left; font-weight: 600; color: #38bdf8; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
        tr:hover {{ background: #334155; }}
        .badge {{ padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }}
        .badge-high {{ background: #7f1d1d; color: #fca5a5; }}
        .badge-medium {{ background: #78350f; color: #fcd34d; }}
        .badge-low {{ background: #14532d; color: #86efac; }}
        .badge-tier {{ background: #1e3a5f; color: #93c5fd; }}
        .gainer {{ color: #22c55e; }} .loser {{ color: #ef4444; }}
        h2 {{ margin: 20px 0 10px; color: #38bdf8; }}
        .section {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        @media (max-width: 768px) {{ .section {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>₿ Atlas Nexus — Crypto</h1>
    </div>
    
    <div class="cards">
        <div class="card">
            <div class="value" style="color:#38bdf8">{summary['total_tokens']}</div>
            <div class="label">Tokens Analyzed</div>
        </div>
        <div class="card">
            <div class="value" style="color:#22c55e">{summary['market_sentiment']['strong_up'] + summary['market_sentiment']['up']}</div>
            <div class="label">Tokens Up (24h)</div>
        </div>
        <div class="card">
            <div class="value" style="color:#ef4444">{summary['market_sentiment']['down'] + summary['market_sentiment']['strong_down']}</div>
            <div class="label">Tokens Down (24h)</div>
        </div>
        <div class="card">
            <div class="value" style="color:#f59e0b">{summary['avg_24h_change']}%</div>
            <div class="label">Avg 24h Change</div>
        </div>
    </div>
    
    {momentum_html}
    
    <h2>📊 Token Leaderboard</h2>
    <div style="overflow-x: auto;">
    <table>
        <thead>
            <tr>
                <th>Token</th><th>Source</th><th>Price</th><th>Market Cap</th><th>24h Δ</th><th>Volatility</th><th>Tier</th><th>Momentum</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    </div>
    
    <div class="section">
        <div>
            <h2>🚀 Top Gainers</h2>
            <table>
                <tr><th>Token</th><th>24h</th><th>Price</th></tr>
                {''.join(f'''<tr><td><strong>{g['symbol']}</strong></td><td class="gainer">▲ {g['change_24h']:.1f}%</td><td>${g.get('price_usd',0) or 0:.4f}</td></tr>''' for g in summary.get('top_gainers',[])[:5])}
            </table>
        </div>
        <div>
            <h2>📉 Top Losers</h2>
            <table>
                <tr><th>Token</th><th>24h</th><th>Price</th></tr>
                {''.join(f'''<tr><td><strong>{l['symbol']}</strong></td><td class="loser">▼ {l['change_24h']:.1f}%</td><td>${l.get('price_usd',0) or 0:.4f}</td></tr>''' for l in summary.get('top_losers',[])[:5])}
            </table>
        </div>
    </div>
    
    {f'''<h2>⚠️ Unusual Volume ({len(summary.get('unusual_volume_tokens',[]))} tokens)</h2>
    <table><tr><th>Token</th><th>Volume</th><th>Mcap</th><th>Ratio</th></tr>
    {''.join(f'<tr><td><strong>{uv["symbol"]}</strong></td><td>${uv.get("volume_24h",0) or 0:,.0f}</td><td>${(uv.get("market_cap",0) or 0)/1e6:.1f}M</td><td>{uv.get("volume_mcap_ratio",0):.2%}</td></tr>' for uv in summary.get('unusual_volume_tokens',[])[:5])}
    </table>''' if summary.get('unusual_volume_tokens') else ''}
    
{tools_html}
    
</body>
</html>"""
    
    html = enhance_dashboard_html(html, "crypto")
    
    with open(path, 'w') as f:
        f.write(html)
    live_path = Path("crypto_dashboard.html")
    live_path.write_text(html)
    print(f"✅ HTML Dashboard: {path} ({os.path.getsize(path)} bytes)")
    print(f"✅ Live: {live_path} ({os.path.getsize(live_path)} bytes)")

# ════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════

def run_pipeline(birdeye_key=None):
    """Execute the complete Sprint 4 pipeline."""
    print("╔══════════════════════════════════════════════╗")
    print("║  🚀 Atlas Nexus — Birdeye Sprint 4 Pipeline  ║")
    print("╚══════════════════════════════════════════════╝\n")
    
    all_tokens = []
    
    # 1. FETCH PHASE
    print("📡 FETCHING DATA...")
    
    print("  • CoinGecko Top 100...")
    cg_data = fetch_coingecko_markets()
    cg_normalized = normalize_coingecko(cg_data)
    all_tokens.extend(cg_normalized)
    print(f"    → {len(cg_normalized)} tokens")
    
    print("  • CoinGecko Trending...")
    cg_trending = fetch_coingecko_trending()
    trending_added = 0
    for t in cg_trending:
        if not any(x['id'] == t.get('id') for x in all_tokens):
            all_tokens.append({
                "id": t.get("id"), "symbol": (t.get("symbol") or "").upper(),
                "name": t.get("name"), "source": "coingecko_trending",
                "price_usd": t.get("price_btc"), "market_cap": t.get("market_cap_rank"),
                "volume_24h": 0, "change_24h": 0, "change_7d": 0,
                "timestamp": NOW
            })
            trending_added += 1
    print(f"    → {trending_added} trending tokens added")
    
    print("  • DEX Screener Trending...")
    dex_data = fetch_dexscreener_trending()
    dex_normalized = normalize_dexscreener(dex_data)
    all_tokens.extend(dex_normalized)
    print(f"    → {len(dex_normalized)} pairs")
    
    # 2. BIRDEYE BDS (if key provided)
    if birdeye_key:
        print("  • Birdeye BDS...")
        be_data = fetch_birdeye_tokenlist(birdeye_key)
        be_added = 0
        for b in (be_data if isinstance(be_data, list) else []):
            all_tokens.append({
                "id": b.get("address"), "symbol": b.get("symbol", "").upper(),
                "name": b.get("name"), "source": "birdeye",
                "price_usd": b.get("price"), "market_cap": b.get("market_cap"),
                "volume_24h": b.get("volume_24h"), "change_24h": b.get("price_change_24h"),
                "timestamp": NOW
            })
            be_added += 1
        print(f"    → {be_added} tokens")
    
    # 3. CLEAN PHASE
    print(f"\n🧹 CLEANING — {len(all_tokens)} raw tokens...")
    cleaned = clean_data(all_tokens)
    print(f"    → {len(cleaned)} after dedup & cleaning")
    
    # 4. ENRICH PHASE
    print("\n🔬 ENRICHING — Advanced analytics...")
    enriched = enrich_data(cleaned)
    gains = sum(1 for t in enriched if t.get('trend') in ['UP', 'STRONG_UP'])
    losses = sum(1 for t in enriched if t.get('trend') in ['DOWN', 'STRONG_DOWN'])
    print(f"    → {gains} gaining, {losses} falling, {len(enriched)-gains-losses} flat")
    
    # 5. ANALYZE PHASE
    print("\n📊 ANALYZING — Market intelligence...")
    summary = compute_market_summary(enriched)
    summary['pipeline'] = {
        'sources': ['coingecko', 'coingecko_trending', 'dexscreener'] + 
                   (['birdeye'] if birdeye_key else []),
        'raw_tokens': len(all_tokens),
        'cleaned_tokens': len(cleaned),
        'version': 'sprint4'
    }
    
    # 6. EXPORT PHASE
    print("\n📁 EXPORTING...")
    export_json({"tokens": enriched, "summary": summary}, f"tokens_full_{NOW}.json")
    export_json(summary, f"summary_{NOW}.json")
    export_csv(enriched, f"tokens_{NOW}.csv")
    export_html_dashboard(enriched, summary, f"dashboard_{NOW}.html")
    
    # 7. PRINT SUMMARY
    print("\n" + "="*50)
    print("📋 SPRINT 4 COMPLETE!")
    print(f"   Tokens: {len(enriched)} (from {len(all_tokens)} raw)")
    print(f"   Sources: {len(summary['pipeline']['sources'])}")
    print(f"   Sentiment: {summary['market_sentiment']}")
    print(f"   Avg 24h: {summary['avg_24h_change']}%")
    print(f"   Files: output/")
    print("="*50)
    
    return {"tokens": enriched, "summary": summary}

# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atlas Nexus — Birdeye Sprint 4 Pipeline")
    parser.add_argument("--birdeye", type=str, help="Birdeye BDS API key")
    parser.add_argument("--html", action="store_true", help="Generate HTML dashboard")
    args = parser.parse_args()
    
    birdeye_key = args.birdeye or os.environ.get("BIRDEYE_API_KEY")
    run_pipeline(birdeye_key)
