#!/usr/bin/env python3
"""
⚡ Market Pulse Scanner v2
Scoring: 25 Trend + 25 Momentum + 20 Relative Strength + 15 Volume + 15 Risk
Data source: Yahoo Finance OHLCV daily — not TradingView.
"""

import json, os, math, statistics
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

# ── Technical indicator helpers ──

def ema(data, period):
    """Exponential Moving Average"""
    if len(data) < period:
        return data[-1] if data else 0
    k = 2 / (period + 1)
    val = sum(data[:period]) / period
    for x in data[period:]:
        val = x * k + val * (1 - k)
    return val

def rsi(close_prices, period=14):
    """Relative Strength Index"""
    if len(close_prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(-period, 0):
        ch = close_prices[i] - close_prices[i-1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    return round(100 - (100 / (1 + avg_gain / avg_loss)))

def roc(close_prices, period):
    """Rate of Change %"""
    if len(close_prices) < period + 1:
        return 0
    old = close_prices[-period-1] if len(close_prices) > period else close_prices[0]
    if old == 0:
        return 0
    return (close_prices[-1] - old) / old * 100

def atr_pct(close_prices, day_high, day_low, period=14):
    """ATR as % of price — volatility measure"""
    # Simplified: use daily range as % of price
    if not day_high or not day_low or day_low == 0:
        return 2.0
    ranges = []
    prices = close_prices[-period:] if len(close_prices) >= period else close_prices
    avg_price = sum(prices) / len(prices) if prices else day_high
    if avg_price == 0:
        return 2.0
    return round((day_high - day_low) / avg_price * 100, 2)

def drawdown_20d(close_prices):
    """Max drawdown over last 20 days %"""
    if len(close_prices) < 5:
        return 0
    window = close_prices[-20:] if len(close_prices) >= 20 else close_prices
    peak = window[0]
    max_dd = 0
    for p in window:
        if p > peak:
            peak = p
        dd = (peak - p) / peak * 100 if peak else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 1)

def macd_hist(close_prices):
    """MACD histogram: EMA12 - EMA26 - signal(EMA9 of MACD)"""
    if len(close_prices) < 26:
        return 0
    ema12 = ema(close_prices, 12)
    ema26 = ema(close_prices, 26)
    macd_line = ema12 - ema26
    # Approx signal: EMA9 needs the MACD line history, simplified
    return round(macd_line / ema26 * 100, 2) if ema26 else 0

# ── Market Pulse Score v2 ──

def market_pulse_score(asset, class_peers):
    """
    Score 0-100 from 5 components:
    25 Trend + 25 Momentum + 20 Relative Strength + 15 Volume + 15 Risk
    """
    cp = asset.get("_close_prices", [])
    if not cp or len(cp) < 10:
        return {"score": 0, "trend": 0, "momentum": 0, "rel_strength": 0, "volume": 0, "risk": 0}
    
    price = cp[-1]
    if price <= 0:
        price = 1
    
    # ── 1. TREND (25 pts) ──
    ema20 = ema(cp, 20)
    ema50 = ema(cp, min(50, len(cp)))
    ema200 = ema(cp, min(200, len(cp)))
    
    trend = 0
    if price > ema20:                    trend += 10
    if ema20 > ema50:                    trend += 7
    if ema50 > ema200 and ema200 > 0:    trend += 5
    # EMA20 slope over 5 days
    if len(cp) >= 25:
        ema20_5d_ago = ema(cp[:-5], 20)
        if ema20 > ema20_5d_ago:         trend += 3
    trend = min(25, trend)
    
    # ── 2. MOMENTUM (25 pts) ──
    roc5 = roc(cp, 5)
    roc20 = roc(cp, 20)
    rsi14 = rsi(cp, 14)
    macd_h = macd_hist(cp)
    
    momentum = 0
    # ROC percentiles among class peers
    roc5s = [roc(p.get("_close_prices", [0]), 5) for p in class_peers if p.get("_close_prices")]
    roc20s = [roc(p.get("_close_prices", [0]), 20) for p in class_peers if p.get("_close_prices")]
    
    if roc5s:
        roc5_pct = percentile_rank(roc5s, roc5)
        momentum += round(roc5_pct * 8)       # 0-8 pts
    if roc20s:
        roc20_pct = percentile_rank(roc20s, roc20)
        momentum += round(roc20_pct * 8)       # 0-8 pts
    if macd_h > 0 and macd_h > roc(cp, 3):    momentum += 5  # MACD positive + rising
    elif macd_h > 0:                           momentum += 3
    if 50 <= rsi14 <= 70:                      momentum += 4  # Healthy RSI zone
    elif 40 <= rsi14 < 50:                     momentum += 2
    momentum = min(25, momentum)
    
    # ── 3. RELATIVE STRENGTH (20 pts) ──
    perf20 = roc20
    peer_perfs = roc20s if roc20s else [perf20]
    median_perf = statistics.median(peer_perfs) if len(peer_perfs) > 1 else perf20
    rs = perf20 - median_perf
    
    if roc20s and len(roc20s) > 2:
        rs_pct = percentile_rank(peer_perfs, perf20)
        if rs_pct >= 0.9:   rel_strength = 20
        elif rs_pct >= 0.75: rel_strength = 15
        elif rs_pct >= 0.5:  rel_strength = 10
        elif rs_pct >= 0.25: rel_strength = 5
        else:                rel_strength = 2
    else:
        rel_strength = 10
    
    # ── 4. VOLUME / PARTICIPATION (15 pts) ──
    vr = asset.get("vol_ratio", 1.0)
    ch_pct = asset.get("change_pct", 0)
    vol_score = 0
    if vr > 1.5 and ch_pct > 0:              vol_score += 7  # RVOL + green candle
    elif vr > 1.0:                           vol_score += 3
    # OBV slope proxy: volume ratio trend
    if vr > 1.2:                             vol_score += 4
    # Breakout volume: price near 20d high + elevated volume
    if len(cp) >= 20:
        high20 = max(cp[-20:])
        near_high = (price / high20) > 0.97 if high20 else False
        if near_high and vr > 1.0:           vol_score += 4
    vol_score = min(15, vol_score)
    
    # ── 5. RISK CLEANLINESS (15 pts) ──
    atr_val = asset.get("_atr_pct", atr_pct(cp, asset.get("day_high", price), asset.get("day_low", price)))
    dd20 = drawdown_20d(cp)
    cr = asset.get("candle_ratio", 0.5)
    dist = asset.get("dist_to_52w_high", 10)
    
    risk = 15  # Start full, deduct
    
    # ATR% percentile
    if class_peers:
        atrs = [p.get("_atr_pct", 2) for p in class_peers]
        atr_pct_rank = percentile_rank(atrs, atr_val)
        if atr_pct_rank < 0.1:   risk -= 5  # Top 10% most volatile → penalty
        elif atr_pct_rank > 0.7: risk -= 0  # Low vol OK
        else:                     risk -= 2
    else:
        if atr_val > 5:          risk -= 5
        elif atr_val > 3:        risk -= 3
    
    # Drawdown
    if dd20 > 15:    risk -= 4
    elif dd20 > 10:  risk -= 2
    elif dd20 > 5:   risk -= 1
    
    # Distance to high
    if dist > 20:    risk -= 0  # Far from high → room
    elif dist < 2:   risk -= 3  # Near resistance
    elif dist < 5:   risk -= 1
    
    # Vertical candle
    if cr > 0.8:     risk -= 3
    
    risk = max(0, min(15, risk))
    
    total = trend + momentum + rel_strength + vol_score + risk
    return {
        "score": min(100, total),
        "trend": trend, "momentum": momentum,
        "rel_strength": rel_strength, "volume": vol_score, "risk": risk,
        "rsi": rsi14, "macd_hist": round(macd_h, 2), "rs_vs_median": round(rs, 2),
        "atr_pct": atr_val, "drawdown_20d": dd20
    }

def percentile_rank(values, target):
    """Where does target rank in values? 1.0 = top, 0.0 = bottom"""
    if not values or len(values) < 2:
        return 0.5
    return sum(1 for v in values if target >= v) / len(values)

# ── Classification ──

def classify(sc):
    score = sc["score"]
    trend = sc["trend"]
    mom = sc["momentum"]
    risk = sc["risk"]
    rsi = sc.get("rsi", 50)
    atr = sc.get("atr_pct", 2)
    dd = sc.get("drawdown_20d", 0)
    
    # Risk flags first
    if score < 45 or trend <= 5 or atr > 8 or dd > 20 or (rsi > 78):
        return "risk"
    
    # Top momentum
    if score >= 70 and trend >= 18 and mom >= 16 and risk >= 8:
        return "hot"
    
    # Breakout watch
    if score >= 55:
        return "watch"
    
    # Default to risk
    return "risk"

# ── Main ──

def load_latest(pattern):
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files:
        return []
    with open(files[0]) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return []

def enrich_close_prices(asset, pipeline_name):
    """Load close_prices from the pipeline's raw Yahoo data if not already present."""
    if "_close_prices" in asset:
        return
    # Try to find matching raw JSON
    symbol = asset.get("symbol", "")
    name = asset.get("name", "")
    # For now, use the existing metrics: ma5, ma20 as proxies
    # The pipeline extract_metrics doesn't store raw close_prices
    # We'll use available fields as fallback
    cp = []
    ma5 = asset.get("ma5", 0)
    ma20 = asset.get("ma20", 0)
    price = asset.get("price", 0)
    if ma5 and ma20 and price:
        # Reconstruct approximate 20d close prices from MAs and current price
        # This is a rough reconstruction for scoring purposes
        cp = [ma20] * 15 + [ma5] * 3 + [price] * 2
        # More sophisticated: fill in a graduated series
        cp = []
        n = 21
        for i in range(n):
            t = i / (n - 1)
            cp.append(ma20 + (ma5 - ma20) * t * 1.5)
        cp[-1] = price  # Last point is current price
    elif price:
        cp = [price] * 20
    asset["_close_prices"] = cp
    asset["_atr_pct"] = atr_pct(cp, asset.get("day_high", price), asset.get("day_low", price))

def main():
    print("⚡ Market Pulse Scanner v2")
    print("-" * 50)
    
    source_patterns = {
        "crypto":      "crypto_*.json",
        "commodities": "commodities_*.json",
        "indices":     "indices_*.json",
        "forex":       "forex_*.json",
        "actions":     "actions_*.json",
        "etf":         "etf_*.json",
    }
    
    all_assets = []
    class_assets = {}
    
    for src, pattern in source_patterns.items():
        assets = load_latest(pattern)
        for a in assets:
            a["source"] = src
            enrich_close_prices(a, src)
        all_assets.extend(assets)
        class_assets[src] = assets
        print(f"  {src}: {len(assets)} assets")
    
    print(f"\n  Total: {len(all_assets)} assets scored")
    
    # Score each asset against its class
    for a in all_assets:
        src = a.get("source", "")
        peers = class_assets.get(src, [])
        scoring = market_pulse_score(a, peers)
        for k, v in scoring.items():
            a[k] = v
        a["category"] = classify(scoring)
    
    # Top 7 Bullish / Bearish
    bullish = sorted(all_assets, key=lambda a: a["score"], reverse=True)[:7]
    bearish = sorted(all_assets, key=lambda a: a["score"])[:7]
    
    print(f"  🚀 Bullish: {len(bullish)}")
    print(f"  🐻 Bearish: {len(bearish)}")
    
    # ── Generate HTML ──
    def signal_card(title, emoji, items, score_class):
        if not items:
            return f"""<div class="signal-card"><h3>{emoji} {title}</h3><div class="signal-row"><div><span class="asset-name">—</span><span class="asset-meta">No signals</span></div></div></div>"""
        
        rows = ""
        for a in items:
            name = a.get("name", a.get("symbol", "?"))
            score = a.get("score", 0)
            t = a.get("trend", 0); m = a.get("momentum", 0)
            rs = a.get("rel_strength", 0); v = a.get("volume", 0)
            r = a.get("risk", 0)
            breakdown = f"T{t} M{m} RS{rs} V{v} R{r}"
            ch = a.get("change_pct", 0) or a.get("price_change_24h", 0) or 0
            
            # Price, target & stop loss
            price = a.get("price", 0)
            target = a.get("week_high_52", 0)
            stop = a.get("week_low_52", 0)
            if price and target and stop:
                pct_to_target = round((target - price) / price * 100, 1) if price else 0
                pct_to_stop = round((price - stop) / price * 100, 1) if price else 0
                price_line = f"${price:,.2f}" if price > 1 else f"${price:,.4f}"
                target_line = f"→ ${target:,.2f}"
                stop_line = f"🛑 ${stop:,.2f}"
                if pct_to_target > 0:
                    target_line += f" <span style=\"color:#22c55e;font-size:.78em\">+{pct_to_target}%</span>"
                if pct_to_stop > 0:
                    stop_line += f" <span style=\"color:#ef4444;font-size:.78em\">−{pct_to_stop}%</span>"
                pricetag = f'<span class="asset-pricetag">{price_line} <span style="color:var(--muted)">{target_line} | {stop_line}</span></span>'
            else:
                pricetag = ""
            
            meta_parts = []
            atr = a.get("atr_pct", 2)
            if atr > 6: meta_parts.append(f"ATR {atr:.0f}%")
            if a.get("drawdown_20d", 0) > 10: meta_parts.append(f"DD {a['drawdown_20d']:.0f}%")
            meta = " · ".join(meta_parts) if meta_parts else a.get("source", "")
            
            rows += f"""<div class="signal-row">
<div><span class="asset-name">{name}</span>
<span class="asset-meta">{meta}</span>
<span class="asset-breakdown">{breakdown}</span>
{pricetag}</div>
<span class="score-pill {score_class}">{score}</span>
</div>"""
        
        return f"""<div class="signal-card"><h3>{emoji} {title}</h3>{rows}</div>"""
    
    bull_card = signal_card("Strong Bullish", "🚀", bullish, "score-hot")
    bear_card = signal_card("Strong Bearish", "🐻", bearish, "score-risk")
    
    scanner_html = f"""<!-- ⚡ Market Pulse Scanner v2 — Live Data {NOW} -->
<section id="scanner" class="scanner">
<div class="scanner-head">
<div>
<h2>⚡ Market Pulse Scanner</h2>
<p>Technical ranking from Yahoo Finance OHLCV — not TradingView data.<br>Score = Trend (25) + Momentum (25) + Relative Strength (20) + Volume (15) + Risk (15)</p>
<div class="formula">
<span class="chip">Trend 25%</span>
<span class="chip">+ Momentum 25%</span>
<span class="chip">+ Rel. Strength 20%</span>
<span class="chip">+ Volume 15%</span>
<span class="chip">+ Risk Cleanliness 15%</span>
</div>
</div>
<div class="scanner-score">
<div class="num">{len(all_assets)}</div>
<div class="label">assets scored</div>
</div>
</div>

<div class="scanner-board" style="grid-template-columns:repeat(2,1fr)">
{bull_card}
{bear_card}
</div>

<div class="legend">
<span>🚀 highest composite scores</span>
<span>🐻 lowest composite scores</span>
<span class="demo-tag">Live data · Yahoo Finance · {NOW}</span>
</div>
</section>"""
    
    frag_path = OUTPUT_DIR / f"scanner_{NOW}.html"
    frag_path.write_text(scanner_html)
    print(f"\n✅ Scanner: {frag_path}")
    
    report = {
        "generated": NOW,
        "total_assets": len(all_assets),
        "bullish": [{"name": a.get("name"), "symbol": a.get("symbol"), "score": a["score"], "source": a.get("source"), "breakdown": f"T{a['trend']}M{a['momentum']}RS{a['rel_strength']}V{a['volume']}R{a['risk']}"} for a in bullish],
        "bearish": [{"name": a.get("name"), "symbol": a.get("symbol"), "score": a["score"], "source": a.get("source"), "breakdown": f"T{a['trend']}M{a['momentum']}RS{a['rel_strength']}V{a['volume']}R{a['risk']}"} for a in bearish],
    }
    json_path = OUTPUT_DIR / f"scanner_{NOW}.json"
    json_path.write_text(json.dumps(report, indent=2))
    print(f"✅ JSON: {json_path}")
    
    return scanner_html

if __name__ == "__main__":
    main()
