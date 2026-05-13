#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ATLAS NEXUS — COMMODITIES PIPELINE                        ║
║  Multi-source commodities analytics + dashboard            ║
║  Sources: Yahoo Finance v8 API                             ║
╚══════════════════════════════════════════════════════════════╝

Tracks: Gold, Silver, Crude Oil, Natural Gas, Copper, Wheat,
        Corn, Soybeans, Coffee, Sugar, Platinum, Palladium
"""

import json, csv, urllib.request, os, sys, time, statistics
from datetime import datetime
from pathlib import Path
from sentiment import compute_sentiment, hawk_eye_html

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

# ── Commodity symbols ──
COMMODITIES = {
    "GC=F":  {"name": "Gold",          "category": "Precious Metals", "unit": "USD/oz"},
    "SI=F":  {"name": "Silver",        "category": "Precious Metals", "unit": "USD/oz"},
    "PL=F":  {"name": "Platinum",      "category": "Precious Metals", "unit": "USD/oz"},
    "PA=F":  {"name": "Palladium",     "category": "Precious Metals", "unit": "USD/oz"},
    "CL=F":  {"name": "Crude Oil WTI", "category": "Energy",          "unit": "USD/barrel"},
    "BZ=F":  {"name": "Brent Crude",   "category": "Energy",          "unit": "USD/barrel"},
    "NG=F":  {"name": "Natural Gas",   "category": "Energy",          "unit": "USD/MMBtu"},
    "HG=F":  {"name": "Copper",        "category": "Industrial Metals","unit": "USD/lb"},
    "ZC=F":  {"name": "Corn",          "category": "Agriculture",     "unit": "USD/bushel"},
    "ZW=F":  {"name": "Wheat",         "category": "Agriculture",     "unit": "USD/bushel"},
    "ZS=F":  {"name": "Soybeans",      "category": "Agriculture",     "unit": "USD/bushel"},
    "KC=F":  {"name": "Coffee",        "category": "Softs",           "unit": "USD/lb"},
    "SB=F":  {"name": "Sugar",         "category": "Softs",           "unit": "USD/lb"},
    "CT=F":  {"name": "Cotton",        "category": "Softs",           "unit": "USD/lb"},
    "LE=F":  {"name": "Live Cattle",   "category": "Livestock",       "unit": "USD/lb"},
}

def fetch_yahoo(symbol, range_="3mo", interval="1d"):
    """Fetch data from Yahoo Finance v8 API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": "AtlasNexus/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ {symbol}: {e}")
        return None

def extract_metrics(symbol, data):
    """Extract key metrics from Yahoo Finance response."""
    try:
        chart = data["chart"]["result"][0]
        meta = chart["meta"]
        quotes = chart.get("indicators", {}).get("quote", [{}])[0]
        timestamps = chart.get("timestamp", [])
        close_prices = quotes.get("close", [])
        open_prices = quotes.get("open", [])
        
        # Filter None values
        clean_prices = [p for p in close_prices if p is not None]
        clean_opens = [o for o in open_prices if o is not None]
        clean_volumes = [v for v in quotes.get("volume", []) if v is not None]
        
        current = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("previousClose", meta.get("chartPreviousClose", current))
        
        # Calculate changes
        change = current - prev_close if prev_close and current else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        # 5-day and 20-day MA
        ma5 = sum(clean_prices[-5:]) / min(len(clean_prices[-5:]), 5) if clean_prices else 0
        ma20 = sum(clean_prices[-20:]) / min(len(clean_prices[-20:]), 20) if clean_prices else 0
        # Trend with threshold — NEUTRAL when MAs are within 0.5%
        diff_pct = abs(ma5 - ma20) / ma20 * 100 if ma20 else 0
        if diff_pct < 0.5:
            trend = "NEUTRAL"
        elif ma5 > ma20:
            trend = "BULLISH"
        else:
            trend = "BEARISH"
        
        # Volatility (20-day)
        if len(clean_prices) >= 20:
            returns = [(clean_prices[i]-clean_prices[i-1])/clean_prices[i-1]*100 for i in range(-20, 0) if clean_prices[i-1] != 0]
            volatility = round(sum(abs(r) for r in returns) / len(returns), 2) if returns else 0
        else:
            volatility = 0
        
        # High/Low range
        day_high = meta.get("regularMarketDayHigh", current)
        day_low = meta.get("regularMarketDayLow", current)
        week_high_52 = meta.get("fiftyTwoWeekHigh", 0)
        week_low_52 = meta.get("fiftyTwoWeekLow", 0)
        
        # Volume analysis
        avg_vol = sum(clean_volumes[-20:]) / min(len(clean_volumes[-20:]), 20) if clean_volumes else 0
        current_vol = clean_volumes[-1] if clean_volumes else 0
        vol_ratio = current_vol / avg_vol if avg_vol else 1
        
        # Candle body ratio (vertical candle detection)
        today_open = clean_opens[-1] if clean_opens else current
        candle_body = abs(current - today_open)
        candle_range = meta.get("regularMarketDayHigh", current) - meta.get("regularMarketDayLow", current)
        candle_ratio = round(candle_body / candle_range, 2) if candle_range > 0 else 0
        
        # Distance to 52W high (resistance proximity)
        wh = meta.get("fiftyTwoWeekHigh", 0)
        dist_to_52w_high = round((wh - current) / wh * 100, 1) if wh > 0 else 0
        
        return {
            "symbol": symbol,
            "name": COMMODITIES.get(symbol, {}).get("name", symbol),
            "category": COMMODITIES.get(symbol, {}).get("category", ""),
            "unit": COMMODITIES.get(symbol, {}).get("unit", ""),
            "price": round(current, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 4) if prev_close else None,
            "day_high": round(day_high, 4),
            "day_low": round(day_low, 4),
            "week_high_52": round(week_high_52, 4),
            "week_low_52": round(week_low_52, 4),
            "volume": current_vol,
            "avg_volume_20d": round(avg_vol),
            "vol_ratio": round(vol_ratio, 2),
            "candle_ratio": candle_ratio, "dist_to_52w_high": dist_to_52w_high,
            "ma5": round(ma5, 4),
            "ma20": round(ma20, 4),
            "trend": trend,
            "volatility_20d": volatility,
            "timestamp": NOW
        }
    except (KeyError, IndexError, TypeError) as e:
        print(f"  ⚠️ Parse error {symbol}: {e}")
        return None

def classify_strength(change_pct):
    if change_pct > 3: return "STRONG_UP"
    if change_pct > 0.5: return "UP"
    if change_pct < -3: return "STRONG_DOWN"
    if change_pct < -0.5: return "DOWN"
    return "FLAT"

def generate_summary(commodities):
    gainers = [c for c in commodities if c["change_pct"] > 0]
    losers = [c for c in commodities if c["change_pct"] < 0]
    unusual = [c for c in commodities if c["vol_ratio"] > 2]
    
    return {
        "total": len(commodities),
        "gainers": len(gainers),
        "losers": len(losers),
        "avg_change": round(sum(c["change_pct"] for c in commodities) / len(commodities), 2) if commodities else 0,
        "total_value": round(sum(c["price"] for c in commodities), 2),
        "top_gainer": max(commodities, key=lambda x: x["change_pct"]) if commodities else None,
        "top_loser": min(commodities, key=lambda x: x["change_pct"]) if commodities else None,
        "unusual_volume": unusual[:5],
        "categories": {},
        "generated_at": NOW
    }

def export_html(commodities, summary):
    sent = summary.get("sentiment", {})
    dir_colors = {
        "BULLISH": ("#22c55e", "#14532d"),
        "SLIGHTLY BULLISH": ("#86efac", "#14532d"),
        "NEUTRAL": ("#f59e0b", "#78350f"),
        "SLIGHTLY BEARISH": ("#fca5a5", "#7f1d1d"),
        "BEARISH": ("#ef4444", "#7f1d1d"),
    }
    sent_color, sent_bg = dir_colors.get(sent.get("direction", "NEUTRAL"), ("#94a3b8", "#1e293b"))
    sent_emoji = {"BULLISH": "🚀", "SLIGHTLY BULLISH": "📈", "NEUTRAL": "⚖️", "SLIGHTLY BEARISH": "📉", "BEARISH": "🐻"}
    emoji = sent_emoji.get(sent.get("direction", "NEUTRAL"), "📊")
    
    sent_html = f"""<div class="sentiment-banner" style="background:{sent_bg};border:1px solid {sent_color};border-radius:14px;padding:24px;margin-bottom:20px;text-align:center">
    <div style="font-size:1.8em;margin-bottom:6px">{emoji}</div>
    <div style="font-size:1.5em;font-weight:700;color:{sent_color}">{sent.get('direction','—')}</div>
    <div style="font-size:2.2em;font-weight:800;color:{sent_color};margin:4px 0">{sent.get('confidence','—')}%</div>
    <div style="color:var(--muted);font-size:.9em">confidence</div>
    <div style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;font-size:.85em">
        {''.join(f'<div><span style="color:var(--muted)">{v["label"]}</span><br><strong>{v["value"]}</strong></div>' for v in sent.get('signals',{}).values())}
    </div></div>"""
    
    rows = ""
    for c in commodities:
        color = "#22c55e" if c["change_pct"] > 0 else "#ef4444" if c["change_pct"] < 0 else "#6b7280"
        arrow = "▲" if c["change_pct"] > 0 else "▼" if c["change_pct"] < 0 else "—"
        vol_color = "#f59e0b" if c["vol_ratio"] > 2 else "#64748b"
        
        rows += f"""<tr>
            <td><strong>{c['name']}</strong> <small style="color:var(--muted)">{c['symbol']}</small></td>
            <td>{c['category']}</td>
            <td class="price">{c['price']:.2f} {c['unit'].split('/')[-1] if '/' in c['unit'] else ''}</td>
            <td style="color:{color}">{arrow} {abs(c['change_pct']):.2f}%</td>
            <td>{c['ma5']:.2f}</td><td>{c['ma20']:.2f}</td>
            <td><span style="color:{'#22c55e' if c['trend']=='BULLISH' else '#ef4444' if c['trend']=='BEARISH' else '#94a3b8'};font-weight:600">{c['trend']}</span></td>
            <td>{c['volatility_20d']:.1f}%</td>
            <td style="color:{vol_color}">{c['vol_ratio']:.1f}x</td>
        </tr>"""

    hawk_html = hawk_eye_html(commodities)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🛢️ Atlas Nexus — Commodities Dashboard</title>
<style>
:root{{--bg:#080b16;--card:#0f1420;--border:#1a2040;--accent:#f59e0b;--accent2:#f97316;--green:#22c55e;--red:#ef4444;--text:#e2e8f0;--muted:#64748b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;background-image:radial-gradient(ellipse at 30% 0%,rgba(245,158,11,0.06) 0%,transparent 50%)}}
.header{{text-align:center;padding:40px 20px 30px;border-bottom:1px solid var(--border)}}
.title-emoji{{font-size:2.8em;margin-bottom:0;line-height:1}}
.header h1{{font-size:2.4em;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header p{{color:var(--muted);margin-top:8px}}
.container{{max-width:1300px;margin:0 auto;padding:20px}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:24px;text-align:center}}
.card .value{{font-size:1.5em;font-weight:800}}
.card .label{{color:var(--muted);margin-top:4px}}
.table-wrapper{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:.92em}}
th{{background:rgba(15,20,40,.6);padding:14px 16px;text-align:left;font-weight:600;color:var(--accent);font-size:.82em;text-transform:uppercase}}
td{{padding:12px 16px;border-bottom:1px solid rgba(26,32,64,.5)}}
tr:hover{{background:rgba(245,158,11,.03)}}
.gainers-losers{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
.gl-card{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px}}
.gl-card h3{{margin-bottom:14px;color:var(--accent)}}
.gl-item{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(26,32,64,.4)}}
.price{{font-weight:600;font-variant-numeric:tabular-nums}}
.footer{{text-align:center;padding:30px;color:var(--muted);border-top:1px solid var(--border)}}
@media(max-width:768px){{.gainers-losers{{grid-template-columns:1fr}}}}
</style></head>
<body>
<div class="header">
<div class="title-emoji">🛢️</div>
<h1>Atlas Nexus — Commodities</h1>
<p>Real-time commodity futures tracking · Gold, Oil, Copper, Grains, Softs | {NOW}</p>
</div>
<div class="container">
<div class="stats-grid">
<div class="card"><div class="value" style="color:var(--accent)">{summary['total']}</div><div class="label">Commodities Tracked</div></div>
<div class="card"><div class="value" style="color:var(--green)">{summary['gainers']}</div><div class="label">Up Today</div></div>
<div class="card"><div class="value" style="color:var(--red)">{summary['losers']}</div><div class="label">Down Today</div></div>
<div class="card"><div class="value" style="color:var(--accent2)">{summary['avg_change']}%</div><div class="label">Avg Change</div></div>
</div>
{sent_html}
{hawk_html}
<h2 style="color:var(--accent);margin-bottom:12px">📊 Commodity Leaderboard</h2>
<div class="table-wrapper"><div style="overflow-x:auto">
<table><thead><tr>
<th>Commodity</th><th>Category</th><th>Price</th><th>Change</th><th>MA(5)</th><th>MA(20)</th><th>Trend</th><th>Volatility</th><th>Vol Ratio</th>
</tr></thead><tbody>{rows}</tbody></table>
</div></div>
<div class="gainers-losers">
<div class="gl-card"><h3>🚀 Top Gainers</h3>
{''.join(f'<div class="gl-item"><span><strong>{g["name"]}</strong></span><span style="color:var(--green)">▲ {g["change_pct"]:.1f}%</span></div>' for g in sorted(commodities,key=lambda x:x['change_pct'],reverse=True)[:5])}
</div>
<div class="gl-card"><h3>📉 Top Losers</h3>
{''.join(f'<div class="gl-item"><span><strong>{l["name"]}</strong></span><span style="color:var(--red)">▼ {abs(l["change_pct"]):.1f}%</span></div>' for l in sorted(commodities,key=lambda x:x['change_pct'])[:5])}
</div></div>
<div class="footer"><p>🛢️ Built by <strong>Atlas Nexus</strong> · Data: Yahoo Finance · Generated: {NOW}</p></div>
</div></body></html>"""

    path = OUTPUT_DIR / f"commodities_{NOW}.html"
    path.write_text(html)
    print(f"✅ HTML: {path} ({os.path.getsize(path)} bytes)")

    # Also write live copy at repo root for GH Pages
    live_path = Path("commodities_dashboard.html")
    live_path.write_text(html)
    print(f"✅ Live: {live_path} ({os.path.getsize(live_path)} bytes)")
    return html

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  🛢️  Atlas Nexus — Commodities Pipeline     ║")
    print("╚══════════════════════════════════════════════╝\n")
    
    all_data = []
    
    for symbol, info in COMMODITIES.items():
        print(f"  📡 {info['name']} ({symbol})...")
        data = fetch_yahoo(symbol)
        if data:
            metrics = extract_metrics(symbol, data)
            if metrics:
                all_data.append(metrics)
                print(f"     → ${metrics['price']:.2f} ({metrics['change_pct']:+.2f}%)")
        time.sleep(0.3)  # Rate limit
    
    if not all_data:
        print("❌ No data fetched!")
        return None
    
    # Classify
    for c in all_data:
        c["strength"] = classify_strength(c["change_pct"])
    
    # Sentiment
    sentiment = compute_sentiment(all_data)
    summary = generate_summary(all_data)
    summary["sentiment"] = sentiment
    
    # Export
    path_json = OUTPUT_DIR / f"commodities_{NOW}.json"
    path_json.write_text(json.dumps({"data": all_data, "summary": summary}, indent=2, default=str))
    print(f"\n✅ JSON: {path_json} ({os.path.getsize(path_json)} bytes)")
    
    path_csv = OUTPUT_DIR / f"commodities_{NOW}.csv"
    with open(path_csv, 'w', newline='') as f:
        fields = ["name","symbol","category","price","change_pct","trend","volatility_20d","vol_ratio"]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_data)
    print(f"✅ CSV: {path_csv} ({os.path.getsize(path_csv)} bytes)")
    
    export_html(all_data, summary)
    
    print(f"\n📊 {len(all_data)} commodities | Avg {summary['avg_change']}% | {summary['gainers']}▲ {summary['losers']}▼")
    return all_data

if __name__ == "__main__":
    main()
