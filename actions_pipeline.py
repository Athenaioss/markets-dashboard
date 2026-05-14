#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ATLAS NEXUS - ACTIONS (STOCKS) PIPELINE                   ║
║  Global stock analytics + dashboard                        ║
║  Sources: Yahoo Finance v8 API                             ║
╚══════════════════════════════════════════════════════════════╝

Tracks: 30 major stocks across Technology, Finance, Healthcare,
        Consumer, Industrial, Energy, Luxury & Auto sectors
"""

import json, csv, urllib.request, os, time, statistics
from datetime import datetime
from pathlib import Path
from sentiment import compute_sentiment, hawk_eye_html, back_to_dashboard_html, unusual_activity_html
from dashboard_theme import enhance_dashboard_html

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

ACTIONS = {
    "AAPL":  {"name": "Apple",          "sector": "Technology",   "country": "US", "currency": "USD"},
    "MSFT":  {"name": "Microsoft",      "sector": "Technology",   "country": "US", "currency": "USD"},
    "GOOGL": {"name": "Alphabet",       "sector": "Technology",   "country": "US", "currency": "USD"},
    "AMZN":  {"name": "Amazon",         "sector": "Technology",   "country": "US", "currency": "USD"},
    "META":  {"name": "Meta",           "sector": "Technology",   "country": "US", "currency": "USD"},
    "NVDA":  {"name": "NVIDIA",         "sector": "Technology",   "country": "US", "currency": "USD"},
    "TSLA":  {"name": "Tesla",          "sector": "Technology",   "country": "US", "currency": "USD"},
    "ASML":  {"name": "ASML",           "sector": "Technology",   "country": "NL", "currency": "EUR"},
    "AVGO":  {"name": "Broadcom",       "sector": "Technology",   "country": "US", "currency": "USD"},
    "JPM":   {"name": "JPMorgan Chase", "sector": "Finance",      "country": "US", "currency": "USD"},
    "BAC":   {"name": "Bank of America","sector": "Finance",      "country": "US", "currency": "USD"},
    "GS":    {"name": "Goldman Sachs",  "sector": "Finance",      "country": "US", "currency": "USD"},
    "V":     {"name": "Visa",           "sector": "Finance",      "country": "US", "currency": "USD"},
    "MA":    {"name": "Mastercard",     "sector": "Finance",      "country": "US", "currency": "USD"},
    "JNJ":   {"name": "Johnson & Johnson","sector": "Healthcare", "country": "US", "currency": "USD"},
    "UNH":   {"name": "UnitedHealth",   "sector": "Healthcare",   "country": "US", "currency": "USD"},
    "LLY":   {"name": "Eli Lilly",      "sector": "Healthcare",   "country": "US", "currency": "USD"},
    "NVO":   {"name": "Novo Nordisk",   "sector": "Healthcare",   "country": "DK", "currency": "DKK"},
    "WMT":   {"name": "Walmart",        "sector": "Consumer",     "country": "US", "currency": "USD"},
    "KO":    {"name": "Coca-Cola",      "sector": "Consumer",     "country": "US", "currency": "USD"},
    "PG":    {"name": "Procter & Gamble","sector": "Consumer",    "country": "US", "currency": "USD"},
    "MCD":   {"name": "McDonald's",     "sector": "Consumer",     "country": "US", "currency": "USD"},
    "NKE":   {"name": "Nike",           "sector": "Consumer",     "country": "US", "currency": "USD"},
    "CAT":   {"name": "Caterpillar",    "sector": "Industrial",   "country": "US", "currency": "USD"},
    "BA":    {"name": "Boeing",         "sector": "Industrial",   "country": "US", "currency": "USD"},
    "GE":    {"name": "GE Aerospace",   "sector": "Industrial",   "country": "US", "currency": "USD"},
    "XOM":   {"name": "Exxon Mobil",    "sector": "Energy",       "country": "US", "currency": "USD"},
    "SHEL":  {"name": "Shell",          "sector": "Energy",       "country": "UK", "currency": "GBP"},
    "MC.PA": {"name": "LVMH",           "sector": "Luxury",       "country": "FR", "currency": "EUR"},
    "RMS.PA":{"name": "Hermès",         "sector": "Luxury",       "country": "FR", "currency": "EUR"},
}

def fetch_yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3mo&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "AtlasNexus/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ {symbol}: {e}")
        return None

def extract_metrics(symbol, data):
    try:
        chart = data["chart"]["result"][0]
        meta = chart["meta"]
        quotes = chart.get("indicators", {}).get("quote", [{}])[0]
        close_prices = [p for p in quotes.get("close", []) if p is not None]
        close_raw = [p for p in quotes.get("close", []) if p is not None]
        high_raw = [h for h in quotes.get("high", []) if h is not None]
        low_raw = [l for l in quotes.get("low", []) if l is not None]
        open_prices = [o for o in quotes.get("open", []) if o is not None]
        volumes = [v for v in quotes.get("volume", []) if v is not None]

        current = meta.get("regularMarketPrice", meta.get("previousClose", 0))
        prev_close = meta.get("previousClose", meta.get("chartPreviousClose", current))
        change = current - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

        ma5 = sum(close_prices[-5:]) / min(len(close_prices[-5:]), 5) if close_prices else 0
        ma20 = sum(close_prices[-20:]) / min(len(close_prices[-20:]), 20) if close_prices else 0
        diff_pct = abs(ma5 - ma20) / ma20 * 100 if ma20 else 0
        if diff_pct < 0.5:
            trend = "NEUTRAL"
        elif ma5 > ma20:
            trend = "BULLISH"
        else:
            trend = "BEARISH"

        if len(close_prices) >= 20:
            returns = [(close_prices[i]-close_prices[i-1])/close_prices[i-1]*100 for i in range(-20, 0) if close_prices[i-1] != 0]
            volatility = round(sum(abs(r) for r in returns) / len(returns), 2) if returns else 0
        else:
            volatility = 0

        avg_vol = sum(volumes[-20:]) / min(len(volumes[-20:]), 20) if volumes else 0
        current_vol = volumes[-1] if volumes else 0
        vol_ratio = current_vol / avg_vol if avg_vol else 1
        
        # Candle body ratio (vertical candle detection)
        today_open = open_prices[-1] if open_prices else current
        candle_body = abs(current - today_open)
        candle_range = meta.get("regularMarketDayHigh", current) - meta.get("regularMarketDayLow", current)
        candle_ratio = round(candle_body / candle_range, 2) if candle_range > 0 else 0
        
        # Distance to 52W high (resistance proximity)
        wh = meta.get("fiftyTwoWeekHigh", 0)
        dist_to_52w_high = round((wh - current) / wh * 100, 1) if wh > 0 else 0
        
        # Correct change_pct to actual daily close (prev_close from Yahoo may be stale)
        if len(close_prices) >= 2 and close_prices[-2] != 0:
            change = close_prices[-1] - close_prices[-2]
            change_pct = change / close_prices[-2] * 100
        
        return {
            "symbol": symbol, "name": ACTIONS[symbol]["name"],
            "sector": ACTIONS[symbol]["sector"], "country": ACTIONS[symbol]["country"],
            "currency": ACTIONS[symbol]["currency"],
            "price": round(current, 2), "change": round(change, 2),
            "change_pct": round(change_pct, 2), "prev_close": round(prev_close, 2) if prev_close else None,
            "day_high": round(meta.get("regularMarketDayHigh", current), 2),
            "day_low": round(meta.get("regularMarketDayLow", current), 2),
            "week_high_52": round(meta.get("fiftyTwoWeekHigh", 0), 2),
            "week_low_52": round(meta.get("fiftyTwoWeekLow", 0), 2),
            "volume": current_vol, "avg_volume_20d": round(avg_vol),
            "vol_ratio": round(vol_ratio, 2),
            "candle_ratio": candle_ratio, "dist_to_52w_high": dist_to_52w_high,
            "ma5": round(ma5, 2), "ma20": round(ma20, 2),
            "trend": trend, "volatility_20d": round(volatility, 2),
            "timestamp": NOW,
            "_close_prices": close_raw, "_high_prices": high_raw, "_low_prices": low_raw
        }
    except Exception as e:
        print(f"  ⚠️ Parse {symbol}: {e}")
        return None

def export_html(actions):
    sentiment = compute_sentiment(actions)
    dir_colors = {"BULLISH":("#22c55e","#14532d"),"SLIGHTLY BULLISH":("#86efac","#14532d"),"NEUTRAL":("#f59e0b","#78350f"),"SLIGHTLY BEARISH":("#fca5a5","#7f1d1d"),"BEARISH":("#ef4444","#7f1d1d")}
    sent_color, sent_bg = dir_colors.get(sentiment["direction"], ("#94a3b8","#1e293b"))
    emoji_map = {"BULLISH":"🚀","SLIGHTLY BULLISH":"📈","NEUTRAL":"⚖️","SLIGHTLY BEARISH":"📉","BEARISH":"🐻"}
    emoji = emoji_map.get(sentiment["direction"], "📊")

    sent_html = f"""<div class="sentiment-banner" style="background:{sent_bg};border:1px solid {sent_color};border-radius:14px;padding:24px;margin-bottom:20px;text-align:center">
    <div style="font-size:1.8em;margin-bottom:6px">{emoji}</div>
    <div style="font-size:1.5em;font-weight:700;color:{sent_color}">{sentiment['direction']}</div>
    <div style="font-size:1.6em;font-weight:800;color:{sent_color};margin:4px 0">{sentiment['confidence']}%</div>
    <div style="color:var(--muted);font-size:.9em">confidence</div>
    <div style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;font-size:.85em">
    {''.join(f'<div><span style="color:var(--muted)">{v["label"]}</span><br><strong>{v["value"]}</strong></div>' for v in sentiment['signals'].values())}
    </div></div>"""

    rows = ""
    for s in sorted(actions, key=lambda x: x.get("sector","") + x.get("name","")):
        color = "#22c55e" if s["change_pct"] > 0 else "#ef4444" if s["change_pct"] < 0 else "#6b7280"
        arrow = "▲" if s["change_pct"] > 0 else "▼" if s["change_pct"] < 0 else "-"
        rows += f"""<tr>
            <td><strong>{s['name']}</strong> <small style="color:var(--muted)">{s['sector']}</small></td>
            <td><small style="color:var(--muted)">{s['currency']}</small></td>
            <td class="price">{s['price']:,.2f}</td>
            <td style="color:{color}">{arrow} {abs(s['change_pct']):.2f}%</td>
            <td><span style="color:{'#22c55e' if s['trend']=='BULLISH' else '#ef4444' if s['trend']=='BEARISH' else '#94a3b8'}">{s['trend']}</span></td>
            <td>{s['volatility_20d']:.1f}%</td>
            <td style="color:var(--muted)">{s['day_high']:,.2f} / {s['day_low']:,.2f}</td>
        </tr>"""

    up = sum(1 for s in actions if s["change_pct"] > 0)
    down = sum(1 for s in actions if s["change_pct"] < 0)
    avg = round(sum(s["change_pct"] for s in actions) / len(actions), 2) if actions else 0

    sectors = {}
    for s in actions:
        sec = s["sector"]
        sectors.setdefault(sec, {"count":0,"up":0,"total_change":0})
        sectors[sec]["count"] += 1
        sectors[sec]["total_change"] += s["change_pct"]
        if s["change_pct"] > 0:
            sectors[sec]["up"] += 1
    sector_cards = ""
    sector_colors = {"Technology":"#38bdf8","Finance":"#22c55e","Healthcare":"#f59e0b","Consumer":"#a78bfa","Industrial":"#6b7280","Energy":"#ef4444","Luxury":"#ec4899"}
    for sec_name, sec_data in sorted(sectors.items()):
        c = sector_colors.get(sec_name, "#94a3b8")
        sec_avg = round(sec_data["total_change"]/sec_data["count"], 2)
        sector_cards += f"""<div class="card" style="border-left:3px solid {c}"><div class="value" style="color:{c}">{sec_avg:+.1f}%</div><div class="label">{sec_name} ({sec_data['up']}/{sec_data['count']})</div></div>"""

    hawk_html = hawk_eye_html(actions)
    unusual_html = unusual_activity_html(actions)
    back_html = back_to_dashboard_html()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📊 Atlas Nexus - Stocks Dashboard</title>
<style>
:root{{--bg:#080b16;--card:#0f1420;--border:#1a2040;--accent:#22c55e;--accent2:#4ade80;--green:#22c55e;--red:#ef4444;--text:#e2e8f0;--muted:#64748b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;background-image:radial-gradient(ellipse at 30% 0%,rgba(34,197,94,.06) 0%,transparent 50%)}}
.header{{text-align:center;padding:40px 20px 30px;border-bottom:1px solid var(--border)}}
.title-emoji{{font-size:2.8em;margin-bottom:0;line-height:1}}
.header h1{{font-size:2.4em;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2),#38bdf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
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
tr:hover{{background:rgba(34,197,94,.03)}}
.price{{font-weight:600;font-variant-numeric:tabular-nums}}
.footer{{text-align:center;padding:30px;color:var(--muted);border-top:1px solid var(--border)}}
.footer a{{color:#38bdf8;text-decoration:none}}
</style></head>
<body>
<div class="header">
<div class="title-emoji">📊</div>
<h1>Atlas Nexus - Global Stocks</h1>
<p>30 major stocks across 7 sectors · Technology, Finance, Healthcare, Consumer, Industrial, Energy, Luxury | {NOW}</p>
</div>
<div class="container">
<div class="stats-grid">
<div class="card"><div class="value" style="color:var(--accent)">{len(actions)}</div><div class="label">Stocks Tracked</div></div>
<div class="card"><div class="value" style="color:var(--green)">{up}</div><div class="label">Up Today</div></div>
<div class="card"><div class="value" style="color:var(--red)">{down}</div><div class="label">Down Today</div></div>
<div class="card"><div class="value" style="color:var(--accent2)">{avg}%</div><div class="label">Avg Change</div></div>
</div>
{sent_html}
{hawk_html}
<h2 style="color:var(--accent);margin-bottom:12px">🏭 Sector Breakdown</h2>
<div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">{sector_cards}</div>
<h2 style="color:var(--accent);margin:24px 0 12px">📋 Stock Leaderboard</h2>
<div class="table-wrapper"><div style="overflow-x:auto">
<table><thead><tr>
<th>Stock</th><th>Curr.</th><th>Price</th><th>Change</th><th>Trend</th><th>Volatility</th><th>Day Range</th>
</tr></thead><tbody>{rows}</tbody></table></div></div>
{unusual_html}
{back_html}
<div class="footer">
<p>📊 Built by <strong>Atlas Nexus</strong> · Data: Yahoo Finance · Generated: {NOW}</p>
<p style="margin-top:4px"><a href="index.html">← Back to Dashboard</a></p>
</div>
</div></body></html>"""

    html = enhance_dashboard_html(html, "stocks")

    path = OUTPUT_DIR / f"actions_{NOW}.html"
    path.write_text(html)
    print(f"✅ HTML: {path} ({os.path.getsize(path)} bytes)")

    # Also write live copy at repo root for GH Pages
    live_path = Path("actions_dashboard.html")
    live_path.write_text(html)
    print(f"✅ Live: {live_path} ({os.path.getsize(live_path)} bytes)")

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  📊 Atlas Nexus - Stocks Pipeline           ║")
    print("╚══════════════════════════════════════════════╝\n")

    all_data = []
    for symbol, info in ACTIONS.items():
        print(f"  📡 {info['name']} ({symbol}) [{info['currency']}]...")
        data = fetch_yahoo(symbol)
        if data:
            metrics = extract_metrics(symbol, data)
            if metrics:
                all_data.append(metrics)
                print(f"     → {metrics['currency']} {metrics['price']:,.2f} ({metrics['change_pct']:+.2f}%)")
        time.sleep(0.3)

    if not all_data:
        print("❌ No data!")
        return

    path_json = OUTPUT_DIR / f"actions_{NOW}.json"
    path_json.write_text(json.dumps(all_data, indent=2, default=str))
    print(f"\n✅ JSON: {path_json}")

    path_csv = OUTPUT_DIR / f"actions_{NOW}.csv"
    with open(path_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=["name","symbol","sector","country","currency","price","change_pct","trend","volatility_20d","vol_ratio"], extrasaction='ignore')
        w.writeheader(); w.writerows(all_data)
    print(f"✅ CSV: {path_csv}")

    export_html(all_data)

    up = sum(1 for s in all_data if s["change_pct"] > 0)
    down = sum(1 for s in all_data if s["change_pct"] < 0)
    sectors = len(set(s["sector"] for s in all_data))
    print(f"\n📊 {len(all_data)} stocks | {sectors} sectors | {up}▲ {down}▼")
    return all_data

if __name__ == "__main__":
    main()
