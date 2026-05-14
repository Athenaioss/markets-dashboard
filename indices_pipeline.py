#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ATLAS NEXUS — INDICES PIPELINE                            ║
║  Global stock indices analytics + dashboard                ║
╚══════════════════════════════════════════════════════════════╝

Tracks: S&P 500, Nasdaq, Dow Jones, FTSE 100, DAX, CAC 40,
        Nikkei 225, Hang Seng, Shanghai Composite, Bovespa,
        ASX 200, Nifty 50, Kospi
"""

import json, csv, urllib.request, os, time, statistics
from datetime import datetime
from pathlib import Path
from sentiment import compute_sentiment, hawk_eye_html
from dashboard_theme import enhance_dashboard_html

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

INDICES = {
    "^GSPC":  {"name": "S&P 500",        "region": "US",      "currency": "USD"},
    "^IXIC":  {"name": "Nasdaq",         "region": "US",      "currency": "USD"},
    "^DJI":   {"name": "Dow Jones",      "region": "US",      "currency": "USD"},
    "^RUT":   {"name": "Russell 2000",   "region": "US",      "currency": "USD"},
    "^FTSE":  {"name": "FTSE 100",       "region": "UK",      "currency": "GBP"},
    "^GDAXI": {"name": "DAX",            "region": "Germany", "currency": "EUR"},
    "^FCHI":  {"name": "CAC 40",         "region": "France",  "currency": "EUR"},
    "^STOXX50E": {"name": "Euro Stoxx 50","region": "EU",     "currency": "EUR"},
    "^N225":  {"name": "Nikkei 225",     "region": "Japan",   "currency": "JPY"},
    "^HSI":   {"name": "Hang Seng",      "region": "HK",      "currency": "HKD"},
    "000001.SS": {"name": "Shanghai Comp","region": "China",  "currency": "CNY"},
    "^BSESN": {"name": "BSE Sensex",     "region": "India",   "currency": "INR"},
    "^NSEI":  {"name": "Nifty 50",       "region": "India",   "currency": "INR"},
    "^KS11":  {"name": "KOSPI",          "region": "Korea",   "currency": "KRW"},
    "^AXJO":  {"name": "ASX 200",        "region": "Australia","currency": "AUD"},
    "^BVSP":  {"name": "Bovespa",        "region": "Brazil",  "currency": "BRL"},
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
        # Trend with threshold — NEUTRAL when MAs are within 0.5%
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
        
        return {
            "symbol": symbol, "name": INDICES[symbol]["name"],
            "region": INDICES[symbol]["region"], "currency": INDICES[symbol]["currency"],
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

def export_html(indices):
    # Compute sentiment
    sentiment = compute_sentiment(indices)
    dir_colors = {"BULLISH":("#22c55e","#14532d"),"SLIGHTLY BULLISH":("#86efac","#14532d"),"NEUTRAL":("#f59e0b","#78350f"),"SLIGHTLY BEARISH":("#fca5a5","#7f1d1d"),"BEARISH":("#ef4444","#7f1d1d")}
    sent_color, sent_bg = dir_colors.get(sentiment["direction"], ("#94a3b8","#1e293b"))
    emoji = {"BULLISH":"🚀","SLIGHTLY BULLISH":"📈","NEUTRAL":"⚖️","SLIGHTLY BEARISH":"📉","BEARISH":"🐻"}.get(sentiment["direction"],"📊")
    
    sent_html = f"""<div class="sentiment-banner" style="background:{sent_bg};border:1px solid {sent_color};border-radius:14px;padding:24px;margin-bottom:20px;text-align:center">
    <div style="font-size:1.8em;margin-bottom:6px">{emoji}</div>
    <div style="font-size:1.5em;font-weight:700;color:{sent_color}">{sentiment['direction']}</div>
    <div style="font-size:2.2em;font-weight:800;color:{sent_color};margin:4px 0">{sentiment['confidence']}%</div>
    <div style="color:var(--muted);font-size:.9em">confidence</div>
    <div style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;font-size:.85em">
    {''.join(f'<div><span style="color:var(--muted)">{v["label"]}</span><br><strong>{v["value"]}</strong></div>' for v in sentiment['signals'].values())}
    </div></div>"""
    
    rows = ""
    for idx in indices:
        color = "#22c55e" if idx["change_pct"] > 0 else "#ef4444" if idx["change_pct"] < 0 else "#6b7280"
        arrow = "▲" if idx["change_pct"] > 0 else "▼" if idx["change_pct"] < 0 else "—"
        rows += f"""<tr>
            <td><strong>{idx['name']}</strong> <small style="color:var(--muted)">{idx['region']}</small></td>
            <td class="price">{idx['price']:,.0f}</td>
            <td style="color:{color}">{arrow} {abs(idx['change_pct']):.2f}%</td>
            <td>{idx['ma5']:,.0f}</td><td>{idx['ma20']:,.0f}</td>
            <td><span style="color:{'#22c55e' if idx['trend']=='BULLISH' else '#ef4444' if idx['trend']=='BEARISH' else '#94a3b8'}">{idx['trend']}</span></td>
            <td>{idx['volatility_20d']:.1f}%</td>
        </tr>"""

    up = sum(1 for i in indices if i["change_pct"] > 0)
    down = sum(1 for i in indices if i["change_pct"] < 0)
    avg = round(sum(i["change_pct"] for i in indices) / len(indices), 2) if indices else 0

    hawk_html = hawk_eye_html(indices)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📈 Atlas Nexus — Indices Dashboard</title>
<style>
:root{{--bg:#080b16;--card:#0f1420;--border:#1a2040;--accent:#38bdf8;--accent2:#818cf8;--green:#22c55e;--red:#ef4444;--text:#e2e8f0;--muted:#64748b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;background-image:radial-gradient(ellipse at 30% 0%,rgba(56,189,248,.06) 0%,transparent 50%)}}
.header{{text-align:center;padding:40px 20px 30px;border-bottom:1px solid var(--border)}}
.title-emoji{{font-size:2.8em;margin-bottom:0;line-height:1}}
.header h1{{font-size:2.4em;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header p{{color:var(--muted);margin-top:8px}}
.container{{max-width:1200px;margin:0 auto;padding:20px}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:24px;text-align:center}}
.card .value{{font-size:1.5em;font-weight:800}}
.card .label{{color:var(--muted);margin-top:4px}}
.table-wrapper{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:.92em}}
th{{background:rgba(15,20,40,.6);padding:14px 16px;text-align:left;font-weight:600;color:var(--accent);font-size:.82em;text-transform:uppercase}}
td{{padding:12px 16px;border-bottom:1px solid rgba(26,32,64,.5)}}
tr:hover{{background:rgba(56,189,248,.03)}}
.price{{font-weight:600;font-variant-numeric:tabular-nums}}
.footer{{text-align:center;padding:30px;color:var(--muted);border-top:1px solid var(--border)}}
</style></head>
<body>
<div class="header">
<div class="title-emoji">📈</div>
<h1>Atlas Nexus — Global Indices</h1>
<p>Real-time stock index tracking · S&P 500, Nasdaq, FTSE, DAX, Nikkei & more | {NOW}</p>
</div>
<div class="container">
<div class="stats-grid">
<div class="card"><div class="value" style="color:var(--accent)">{len(indices)}</div><div class="label">Indices Tracked</div></div>
<div class="card"><div class="value" style="color:var(--green)">{up}</div><div class="label">Up Today</div></div>
<div class="card"><div class="value" style="color:var(--red)">{down}</div><div class="label">Down Today</div></div>
<div class="card"><div class="value" style="color:var(--accent2)">{avg}%</div><div class="label">Avg Change</div></div>
</div>
{sent_html}
{hawk_html}
<h2 style="color:var(--accent);margin-bottom:12px">🌍 Index Leaderboard</h2>
<div class="table-wrapper"><div style="overflow-x:auto">
<table><thead><tr>
<th>Index</th><th>Price</th><th>Change</th><th>MA(5)</th><th>MA(20)</th><th>Trend</th><th>Volatility</th>
</tr></thead><tbody>{rows}</tbody></table></div></div>
<div class="footer"><p>📈 Built by <strong>Atlas Nexus</strong> · Data: Yahoo Finance · Generated: {NOW}</p></div>
</div></body></html>"""

    html = enhance_dashboard_html(html, "indices")

    path = OUTPUT_DIR / f"indices_{NOW}.html"
    path.write_text(html)
    print(f"✅ HTML: {path} ({os.path.getsize(path)} bytes)")

    # Also write live copy at repo root for GH Pages
    live_path = Path("indices_dashboard.html")
    live_path.write_text(html)
    print(f"✅ Live: {live_path} ({os.path.getsize(live_path)} bytes)")

def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  📈 Atlas Nexus — Indices Pipeline          ║")
    print("╚══════════════════════════════════════════════╝\n")
    
    all_data = []
    for symbol, info in INDICES.items():
        print(f"  📡 {info['name']} ({symbol})...")
        data = fetch_yahoo(symbol)
        if data:
            metrics = extract_metrics(symbol, data)
            if metrics:
                all_data.append(metrics)
                print(f"     → {metrics['price']:,.0f} ({metrics['change_pct']:+.2f}%)")
        time.sleep(0.3)
    
    if not all_data:
        print("❌ No data!")
        return
    
    # Export
    path_json = OUTPUT_DIR / f"indices_{NOW}.json"
    path_json.write_text(json.dumps(all_data, indent=2, default=str))
    print(f"\n✅ JSON: {path_json}")
    
    path_csv = OUTPUT_DIR / f"indices_{NOW}.csv"
    with open(path_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=["name","symbol","region","price","change_pct","trend","volatility_20d"], extrasaction='ignore')
        w.writeheader(); w.writerows(all_data)
    print(f"✅ CSV: {path_csv}")
    
    export_html(all_data)
    
    up = sum(1 for i in all_data if i["change_pct"] > 0)
    down = sum(1 for i in all_data if i["change_pct"] < 0)
    print(f"\n📊 {len(all_data)} indices | {up}▲ {down}▼")
    return all_data

if __name__ == "__main__":
    main()
