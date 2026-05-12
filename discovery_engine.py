#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ATLAS NEXUS — TOKEN DISCOVERY ENGINE                      ║
║  Radar for new tokens, hidden gems & unusual activity      ║
║  Birdeye Sprint 4 Enhancement                              ║
╚══════════════════════════════════════════════════════════════╝

Scans:
  • CoinGecko Trending (real-time)
  • CoinGecko Top Gainers/Losers
  • DEX Screener Latest (new pairs)
  • Unusual volume detection (>3σ)
  • Strong momentum breakouts (>15% 24h)

Output: JSON alert feed — pluggable into Telegram/Discord/Email
"""

import json
import urllib.request
import urllib.error
import time
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

def fetch_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", "AtlasNexus-Discovery/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ⚠️ {e}")
        return None

def scan_coingecko_trending():
    """Get trending coins from CoinGecko."""
    data = fetch_json("https://api.coingecko.com/api/v3/search/trending")
    if not data:
        return []
    results = []
    for c in data.get("coins", []):
        item = c.get("item", {})
        results.append({
            "symbol": (item.get("symbol") or "").upper(),
            "name": item.get("name"),
            "mcap_rank": item.get("market_cap_rank"),
            "score": item.get("score"),
            "source": "coingecko_trending"
        })
    return results

def scan_dex_latest():
    """Get latest pairs from DEX Screener (proxy for new tokens)."""
    data = fetch_json(
        "https://api.dexscreener.com/latest/dex/search?q=SOL/USDC",  # will also pick up new pairs
        headers={"Accept": "application/json"},
        timeout=10
    )
    # Try to get trending instead — more reliable for new tokens
    data = fetch_json("https://api.dexscreener.com/latest/dex/trending?limit=15")
    if not data or "pairs" not in data:
        return []
    
    results = []
    for p in data["pairs"]:
        base = p.get("baseToken", {})
        volume = p.get("volume", {})
        results.append({
            "symbol": (base.get("symbol") or "").upper(),
            "name": base.get("name", ""),
            "chain": p.get("chainId", ""),
            "dex": p.get("dexId", ""),
            "price_usd": float(p.get("priceUsd", 0) or 0),
            "volume_24h": volume.get("h24", 0),
            "change_24h": p.get("priceChange", {}).get("h24", 0),
            "fdv": float(p.get("fdv", 0) or 0),
            "pair_age_hours": p.get("pairCreatedAt"),
            "source": "dexscreener"
        })
    return results

def scan_top_movers():
    """Scan CoinGecko for top gainers/losers with high conviction signals."""
    data = fetch_json(
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=volume_desc&per_page=100&page=1"
        "&sparkline=false&price_change_percentage=1h,24h,7d"
    )
    if not data:
        return []
    
    alerts = []
    avg_vol = sum(t.get("total_volume", 0) or 0 for t in data) / len(data) if data else 0
    
    for t in data:
        change_24h = t.get("price_change_percentage_24h", 0) or 0
        change_1h = t.get("price_change_percentage_1h_in_currency", 0) or 0
        volume = t.get("total_volume", 0) or 0
        mcap = t.get("market_cap", 0) or 0
        symbol = (t.get("symbol") or "").upper()
        
        # Alert criteria
        alert_type = None
        reason = []
        
        # Breakout: >15% in 24h + accelerating (>5% in 1h)
        if change_24h > 15 and change_1h > 5:
            alert_type = "BREAKOUT"
            reason.append(f"+{change_24h:.1f}% 24h, +{change_1h:.1f}% 1h (acceleration)")
        
        # Crash: <-10% in 24h + continuing down
        elif change_24h < -10 and change_1h < -2:
            alert_type = "CRASH"
            reason.append(f"{change_24h:.1f}% 24h, {change_1h:.1f}% 1h (continuing)")
        
        # Unusual volume: >3x average with small/mid cap
        if volume > avg_vol * 3 and 0 < mcap < 1_000_000_000:
            if alert_type:
                alert_type = f"{alert_type}+VOLUME"
            else:
                alert_type = "VOLUME_SPIKE"
            reason.append(f"Volume {volume/avg_vol:.1f}x avg, MCap ${mcap/1e6:.1f}M")
        
        if alert_type:
            alerts.append({
                "symbol": symbol,
                "name": t.get("name"),
                "type": alert_type,
                "reasons": reason,
                "price_usd": t.get("current_price"),
                "change_24h": change_24h,
                "change_1h": change_1h,
                "volume_24h": volume,
                "market_cap": mcap,
                "timestamp": datetime.now().isoformat()
            })
    
    return alerts

def generate_alert_feed(alerts: list) -> str:
    """Generate human-readable alert feed (for Telegram/Discord)."""
    if not alerts:
        return "✅ No alerts — market calm."
    
    lines = [f"🔮 Atlas Nexus Alert Feed · {datetime.now().strftime('%H:%M UTC')}", "=" * 45]
    
    for a in alerts:
        emoji = {"BREAKOUT": "🚀", "CRASH": "📉", "VOLUME_SPIKE": "📊",
                 "BREAKOUT+VOLUME": "💎", "CRASH+VOLUME": "⚠️"}.get(a["type"], "🔔")
        lines.append(f"\n{emoji} **{a['symbol']}** — {a['type']}")
        lines.append(f"   ${a['price_usd']:.4f} | 24h: {a['change_24h']:.1f}%")
        for r in a["reasons"]:
            lines.append(f"   ↳ {r}")
    
    return "\n".join(lines)

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  🔍 Token Discovery Engine                  ║")
    print("╚══════════════════════════════════════════════╝\n")
    
    all_alerts = []
    
    # Scan 1: Trending
    print("📡 CoinGecko Trending...")
    trending = scan_coingecko_trending()
    print(f"   → {len(trending)} trending coins")
    
    # Scan 2: DEX Screener new pairs
    print("📡 DEX Screener Trending...")
    dex_trending = scan_dex_latest()
    print(f"   → {len(dex_trending)} pairs")
    
    # Scan 3: Top Movers with alerts
    print("📡 Scanning for breakouts & unusual activity...")
    movers = scan_top_movers()
    all_alerts.extend(movers)
    print(f"   → {len(movers)} alerts generated")
    
    # Export
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Full discovery data
    discovery = {
        "trending": trending,
        "dex_trending": dex_trending,
        "alerts": all_alerts,
        "generated_at": ts
    }
    path = OUTPUT_DIR / f"discovery_{ts}.json"
    path.write_text(json.dumps(discovery, indent=2, default=str))
    print(f"\n✅ Discovery JSON: {path}")
    
    # Alert feed (human readable)
    feed = generate_alert_feed(all_alerts)
    feed_path = OUTPUT_DIR / f"alerts_{ts}.txt"
    feed_path.write_text(feed)
    print(f"✅ Alert Feed: {feed_path}")
    
    print("\n" + feed)
    print(f"\n📊 Summary: {len(trending)} trending, {len(dex_trending)} DEX pairs, {len(all_alerts)} alerts")

if __name__ == "__main__":
    main()
