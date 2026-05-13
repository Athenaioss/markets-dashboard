#!/usr/bin/env python3
"""
⚡ Market Pulse Scanner v3 — Tradeable Setups
ATR-based targets/stops · Separate bull/bear scores · RR ≥ 1.5 · No padding
Data: Yahoo Finance OHLCV daily
"""

import json, os, math, statistics
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

# ── Indicators ──

def ema(data, period):
    if len(data) < period: return data[-1] if data else 0
    k = 2 / (period + 1)
    val = sum(data[:period]) / period
    for x in data[period:]: val = x * k + val * (1 - k)
    return val

def rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains, losses = [], []
    for i in range(-period, 0):
        ch = prices[i] - prices[i-1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
    avg_gain = sum(gains)/period; avg_loss = sum(losses)/period
    if avg_loss == 0: return 100
    return round(100 - 100/(1 + avg_gain/avg_loss))

def roc(prices, period):
    if len(prices) < period + 1: return 0
    old = prices[-period-1]
    return (prices[-1] - old) / old * 100 if old else 0

def macd_hist(prices):
    if len(prices) < 26: return 0
    e12 = ema(prices, 12); e26 = ema(prices, 26)
    return round((e12 - e26) / e26 * 100, 2) if e26 else 0

def atr_val(highs, lows, closes, period=14):
    """Average True Range in absolute terms"""
    if len(highs) < period + 1: return 0.01
    trs = []
    for i in range(-period, 0):
        h, l, pc = highs[i], lows[i], closes[i-1] if i > -len(closes) else closes[i]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period

def swing_low(lows, window=10):
    """Recent swing low"""
    if len(lows) < window: return min(lows)
    return min(lows[-window:])

def swing_high(highs, window=10):
    if len(highs) < window: return max(highs)
    return max(highs[-window:])

# ── Loading ──

def load_latest(pattern):
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files: return []
    with open(files[0]) as f:
        data = json.load(f)
    if isinstance(data, list): return data
    if isinstance(data, dict) and "data" in data: return data["data"]
    return []

# ── Scoring ──

def compute_scores(all_assets):
    for a in all_assets:
        cp = a.get("_close_prices", [])
        hp = a.get("_high_prices", [])
        lp = a.get("_low_prices", [])
        if not cp or len(cp) < 10: cp = [a.get("price", 1)] * 20
        if not hp: hp = [a.get("price", 1)] * 20
        if not lp: lp = [a.get("price", 1)] * 20
        
        price = cp[-1] if cp else a.get("price", 1)
        ema20 = ema(cp, 20)
        ema50 = ema(cp, min(50, len(cp)))
        rsi14 = rsi(cp, 14)
        macd_h = macd_hist(cp)
        roc5 = roc(cp, 5)
        roc20 = roc(cp, 20)
        atr = atr_val(hp, lp, cp, 14)
        atr_pct = round(atr / price * 100, 2) if price else 2
        
        # ── BULL SCORE (0-100) ──
        bull = 0
        if price > ema20: bull += 15
        if ema20 > ema50: bull += 10
        if roc5 > 0: bull += 10
        if roc20 > 0: bull += 10
        if macd_h > 0: bull += 8
        if 50 <= rsi14 <= 70: bull += 7
        bull = min(100, bull)
        
        # ── BEAR SCORE (0-100) ──
        bear = 0
        if price < ema20: bear += 15
        if ema20 < ema50: bear += 10
        if roc5 < 0: bear += 10
        if roc20 < 0: bear += 10
        if macd_h < 0: bear += 8
        if 30 <= rsi14 <= 55: bear += 7
        bear = min(100, bear)
        
        a["bull_score"] = bull
        a["bear_score"] = bear
        a["_atr"] = atr
        a["_atr_pct"] = atr_pct
        a["_ema20"] = ema20
        a["_rsi"] = rsi14
        a["_swing_low"] = swing_low(lp)
        a["_swing_high"] = swing_high(hp)
        a["_macd_h"] = macd_h
        a["_roc5"] = roc5
        a["_roc20"] = roc20

def build_setups(assets):
    """Build tradeable setups with ATR-based stops/targets"""
    setups_long = []
    setups_short = []
    
    for a in assets:
        price = a.get("price", 0)
        atr = a.get("_atr", 0.01)
        if not price or not atr: continue
        
        name = a.get("name", a.get("symbol", "?"))
        bull = a["bull_score"]
        bear = a["bear_score"]
        src = a.get("source", "")
        trend = a.get("trend", "NEUTRAL")
        
        # ── LONG setup ──
        if bull >= 50 and trend == "BULLISH" and a.get("change_pct", 0) > 0:
            entry = price
            stop = min(a.get("_swing_low", price * 0.95), a.get("_ema20", price)) - atr * 0.5
            stop = min(stop, entry * 0.93)  # Cap max stop at -7%
            risk = entry - stop
            tp1 = entry + risk * 1.5
            tp2 = entry + risk * 3.0
            rr = 1.5  # Fixed target RR for TP1
            
            if stop < entry and tp1 > entry:
                setups_long.append(dict(
                    name=name, source=src, direction="LONG",
                    score=bull, entry=round(entry, 2),
                    stop=round(stop, 2), tp1=round(tp1, 2), tp2=round(tp2, 2),
                    rr=rr, risk_pct=round(risk/entry*100, 1),
                    atr_pct=round(atr/entry*100, 2),
                    rsi=a.get("_rsi", 50), macd=a.get("_macd_h", 0),
                    roc5=a.get("_roc5", 0),
                    motif=f"trend + momentum",
                    status="TRADEABLE" if rr >= 1.5 else "WATCHLIST"
                ))
        
        # ── SHORT setup ──
        if bear >= 50 and trend == "BEARISH" and a.get("change_pct", 0) < 0:
            entry = price
            stop = max(a.get("_swing_high", price * 1.05), a.get("_ema20", price)) + atr * 0.5
            stop = max(stop, entry * 1.07)
            risk = stop - entry
            tp1 = entry - risk * 1.5
            tp2 = entry - risk * 3.0
            rr = 1.5
            
            if stop > entry and tp1 < entry:
                setups_short.append(dict(
                    name=name, source=src, direction="SHORT",
                    score=bear, entry=round(entry, 2),
                    stop=round(stop, 2), tp1=round(tp1, 2), tp2=round(tp2, 2),
                    rr=rr, risk_pct=round(risk/entry*100, 1),
                    atr_pct=round(atr/entry*100, 2),
                    rsi=a.get("_rsi", 50), macd=a.get("_macd_h", 0),
                    roc5=a.get("_roc5", 0),
                    motif=f"downtrend + volume",
                    status="TRADEABLE" if rr >= 1.5 else "WATCHLIST"
                ))
    
    # Sort and take top 7 — NO PADDING
    setups_long.sort(key=lambda s: s["score"], reverse=True)
    setups_short.sort(key=lambda s: s["score"], reverse=True)
    
    return setups_long[:7], setups_short[:7]


# ── HTML Generation ──

def setup_card(title, emoji, setups, color_class, is_bullish=True):
    if not setups:
        return f"""<div class="signal-card"><h3>{emoji} {title}</h3><div class="no-signal">No valid {title.lower()} setup</div></div>"""
    
    rows = ""
    for s in setups:
        score = s["score"]
        entry = s["entry"]; stop = s["stop"]; tp1 = s["tp1"]; tp2 = s["tp2"]
        rr = s["rr"]; risk_pct = s["risk_pct"]; status = s["status"]
        motif = s.get("motif", "")
        
        badge_color = "#22c55e" if status == "TRADEABLE" else "#f59e0b"
        badge_text = "✅ TRADEABLE" if status == "TRADEABLE" else "⏳ WATCHLIST"
        
        price_fmt = f"${entry:,.2f}" if entry > 1 else f"${entry:,.4f}"
        stop_fmt = f"${stop:,.2f}" if stop > 1 else f"${stop:,.4f}"
        tp1_fmt = f"${tp1:,.2f}" if tp1 > 1 else f"${tp1:,.4f}"
        tp2_fmt = f"${tp2:,.2f}" if tp2 > 1 else f"${tp2:,.4f}"
        
        rows += f"""<div class="signal-row">
<div>
<span class="asset-name">{s['name']}</span>
<span class="asset-tag">{s.get('direction','')}</span>
<span class="asset-meta">{s.get('source','')} · {motif}</span>
<span class="asset-levels">
<span style="color:#bae6fd">Entry {price_fmt}</span>
<span style="color:#ef4444">SL {stop_fmt}</span>
<span style="color:#22c55e">TP1 {tp1_fmt}</span>
<span style="color:#14F195">TP2 {tp2_fmt}</span>
</span>
</div>
<div style="text-align:right">
<span class="score-pill {color_class}">{score}</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">RR {rr}:1 · −{risk_pct}%</div>
<div style="font-size:.7em;color:{badge_color};margin-top:2px">{badge_text}</div>
</div>
</div>"""
    
    return f"""<div class="signal-card"><h3>{emoji} {title} ({len(setups)})</h3>{rows}</div>"""

def main():
    print("⚡ Market Pulse Scanner v3 — Tradeable Setups")
    print("-" * 50)
    
    sources = {
        "crypto": "crypto_*.json", "commodities":"commodities_*.json",
        "indices":"indices_*.json", "forex":"forex_*.json",
        "actions":"actions_*.json", "etf":"etf_*.json",
    }
    
    all_assets = []
    for src, pattern in sources.items():
        assets = load_latest(pattern)
        for a in assets: a["source"] = src
        all_assets.extend(assets)
        print(f"  {src}: {len(assets)} assets")
    
    # Filter outliers
    def is_playable(a):
        ch = a.get("change_pct", 0)
        return 0.2 < abs(ch) < 20 and a.get("_close_prices")
    
    assets_clean = [a for a in all_assets if is_playable(a)]
    skipped = len(all_assets) - len(assets_clean)
    if skipped: print(f"  ⚠️ Filtered {skipped} artifacts")
    
    compute_scores(assets_clean)
    setups_long, setups_short = build_setups(assets_clean)
    
    print(f"  🚀 LONG setups: {len(setups_long)}")
    print(f"  🐻 SHORT setups: {len(setups_short)}")
    
    long_card  = setup_card("Long Setups", "🚀", setups_long, "score-hot", True)
    short_card = setup_card("Short Setups", "🐻", setups_short, "score-risk", False)
    
    scanner_html = f"""<!-- ⚡ Market Pulse Scanner v3 — {NOW} -->
<section id="scanner" class="scanner">
<div class="scanner-head">
<div>
<h2>⚡ Market Pulse Scanner</h2>
<p>Tradeable setups from Yahoo Finance OHLCV daily data.<br>ATR-based stops/targets · Bull/Bear scoring · RR ≥ 1.5 required</p>
<div class="formula">
<span class="chip">Entry = current</span>
<span class="chip">SL = swing ± ATR</span>
<span class="chip">TP1 = 1.5R</span>
<span class="chip">TP2 = 3R</span>
<span class="chip">RR ≥ 1.5</span>
</div>
</div>
<div class="scanner-score">
<div class="num">{len(assets_clean)}</div>
<div class="label">assets scored</div>
</div>
</div>

<div class="scanner-board" style="grid-template-columns:repeat(2,1fr)">
{long_card}
{short_card}
</div>

<div class="legend">
<span>✅ TRADEABLE — RR ≥ 1.5, levels valid</span>
<span>⏳ WATCHLIST — needs confirmation</span>
<span class="demo-tag">Yahoo Finance · ATR-based · {NOW}</span>
</div>
</section>"""
    
    frag_path = OUTPUT_DIR / f"scanner_{NOW}.html"
    frag_path.write_text(scanner_html)
    print(f"\n✅ Scanner: {frag_path}")
    
    # Report
    report = {
        "generated": NOW, "total": len(assets_clean),
        "longs": [{"name": s["name"], "entry": s["entry"], "stop": s["stop"], "tp1": s["tp1"], "tp2": s["tp2"], "rr": s["rr"]} for s in setups_long],
        "shorts": [{"name": s["name"], "entry": s["entry"], "stop": s["stop"], "tp1": s["tp1"], "tp2": s["tp2"], "rr": s["rr"]} for s in setups_short],
    }
    (OUTPUT_DIR / f"scanner_{NOW}.json").write_text(json.dumps(report, indent=2))
    
    return scanner_html

if __name__ == "__main__":
    main()
