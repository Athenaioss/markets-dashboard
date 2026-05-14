#!/usr/bin/env python3
"""
⚡ Market Pulse Scanner v3 — Tradeable Setups
ATR-based targets/stops · Separate bull/bear scores · RR ≥ 1.0 · No padding
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

def source_profile(source, symbol=""):
    """Asset-class aware risk model for entry/SL/TP display.

    The scanner mixes FX pairs, CFDs/commodities, indices, equities, ETFs and crypto.
    A single ATR multiplier plus 2-decimal rounding creates nonsensical FX levels
    (e.g. AUD/USD 0.7257 rendered as 0.7300). Profiles keep precision and risk
    bands aligned with the asset context.
    """
    symbol = (symbol or "").upper()
    if source == "forex":
        return {"decimals": 2 if "JPY" in symbol else 4, "stop_atr": 1.15, "target_rr": 1.8, "min_risk_pct": 0.25, "max_risk_pct": 1.20}
    if source == "crypto":
        return {"decimals": 2, "stop_atr": 1.8, "target_rr": 1.8, "min_risk_pct": 2.00, "max_risk_pct": 12.0}
    if source in ("actions", "etf"):
        return {"decimals": 2, "stop_atr": 1.25, "target_rr": 1.7, "min_risk_pct": 0.80, "max_risk_pct": 6.00}
    if source == "indices":
        return {"decimals": 2, "stop_atr": 1.20, "target_rr": 1.7, "min_risk_pct": 0.60, "max_risk_pct": 5.00}
    if source == "commodities":
        return {"decimals": 2, "stop_atr": 1.15, "target_rr": 1.6, "min_risk_pct": 0.70, "max_risk_pct": 5.00}
    return {"decimals": 2, "stop_atr": 1.30, "target_rr": 1.7, "min_risk_pct": 0.80, "max_risk_pct": 6.00}

def rounded_price(value, profile):
    return round(value, profile["decimals"])

def contextual_levels(a, direction):
    """Return context-aware entry, stop, target, RR and risk %."""
    entry = a.get("price", 0)
    atr = a.get("_atr", 0.01)
    src = a.get("source", "")
    profile = source_profile(src, a.get("symbol", ""))
    if not entry or not atr:
        return None

    atr_risk = atr * profile["stop_atr"]
    min_risk = entry * profile["min_risk_pct"] / 100
    max_risk = entry * profile["max_risk_pct"] / 100
    risk = min(max(atr_risk, min_risk), max_risk)

    # Respect nearby market structure when it is plausible, without letting
    # stale candles create absurdly wide stops for volatile/mixed instruments.
    if direction == "LONG":
        structure_stop = a.get("_swing_low", entry) - atr * 0.15
        structure_risk = entry - structure_stop
        if min_risk <= structure_risk <= max_risk:
            risk = max(risk, structure_risk)
        stop = entry - risk
        tp = entry + risk * profile["target_rr"]
        rr = round((tp - entry) / risk, 1) if risk > 0 else 0
        tp_pct = round((tp - entry) / entry * 100, 1)
    else:
        structure_stop = a.get("_swing_high", entry) + atr * 0.15
        structure_risk = structure_stop - entry
        if min_risk <= structure_risk <= max_risk:
            risk = max(risk, structure_risk)
        stop = entry + risk
        tp = entry - risk * profile["target_rr"]
        rr = round((entry - tp) / risk, 1) if risk > 0 else 0
        tp_pct = round((entry - tp) / entry * 100, 1)

    return {
        "entry": rounded_price(entry, profile),
        "stop": rounded_price(stop, profile),
        "tp": rounded_price(tp, profile),
        "rr": rr,
        "risk_pct": round(risk / entry * 100, 2),
        "tp_pct": tp_pct,
        "atr_pct": round(atr / entry * 100, 2),
        "precision": profile["decimals"],
    }

def compact_forex_symbol(symbol):
    """Compact FX pair label for scanner rows: EURUSD, GBPJPY, etc."""
    return (symbol or "").upper().replace("=X", "")

def display_asset_name(asset):
    if asset.get("source") == "forex":
        compact = compact_forex_symbol(asset.get("symbol", ""))
        if compact:
            return compact
    return asset.get("name", asset.get("symbol", "?"))


def build_setups(assets):
    """Build tradeable setups with asset-contextual stops/targets"""
    setups_long = []
    setups_short = []
    
    for a in assets:
        price = a.get("price", 0)
        atr = a.get("_atr", 0.01)
        if not price or not atr: continue
        
        name = display_asset_name(a)
        bull = a["bull_score"]
        bear = a["bear_score"]
        src = a.get("source", "")
        trend = a.get("trend", "NEUTRAL")
        
        # ── LONG setup ──
        if bull >= 50 and trend == "BULLISH" and a.get("change_pct", 0) > 0:
            levels = contextual_levels(a, "LONG")
            if levels and levels["stop"] < levels["entry"] and levels["tp"] > levels["entry"] and levels["rr"] >= 1.0:
                setups_long.append(dict(
                    name=name, source=src, direction="LONG", symbol=a.get("symbol", ""),
                    score=bull, **levels,
                    rsi=a.get("_rsi", 50),
                    motif="trend + contextual risk",
                    status="TRADEABLE"
                ))
        
        # ── SHORT setup ──
        if bear >= 50 and trend == "BEARISH" and a.get("change_pct", 0) < 0:
            levels = contextual_levels(a, "SHORT")
            if levels and levels["stop"] > levels["entry"] and levels["tp"] < levels["entry"] and levels["rr"] >= 1.0:
                setups_short.append(dict(
                    name=name, source=src, direction="SHORT", symbol=a.get("symbol", ""),
                    score=bear, **levels,
                    rsi=a.get("_rsi", 50),
                    motif="downtrend + contextual risk",
                    status="TRADEABLE"
                ))
    
    # Sort and take top 7 — NO PADDING
    setups_long.sort(key=lambda s: s["score"], reverse=True)
    setups_short.sort(key=lambda s: s["score"], reverse=True)
    
    return setups_long[:7], setups_short[:7]


# ── HTML Generation ──

def market_for_source(source):
    return {"actions": "stocks"}.get(source, source)

def setup_card(title, emoji, setups, color_class, is_bullish=True):
    if not setups:
        return f"""<div class="signal-card"><h3>{emoji} {title}</h3><div class="no-signal">No valid {title.lower()} setup</div></div>"""
    
    rows = ""
    for s in setups:
        score = s["score"]
        entry = s["entry"]; stop = s["stop"]; tp = s["tp"]
        rr = s["rr"]; risk_pct = s["risk_pct"]; status = s["status"]
        motif = s.get("motif", "")
        market = market_for_source(s.get("source", ""))
        
        badge_color = "#22c55e" if status == "TRADEABLE" else "#f59e0b"
        badge_text = "✅ TRADEABLE" if status == "TRADEABLE" else "⏳ WATCHLIST"
        
        precision = int(s.get("precision", 2 if entry > 1 else 4))
        price_fmt = f"${entry:,.{precision}f}"
        stop_fmt = f"${stop:,.{precision}f}"
        tp = s.get("tp", 0)
        tp_fmt = f"${tp:,.{precision}f}"
        tp_pct = s.get("tp_pct", 0)
        
        rows += f"""<div class="signal-row" data-market="{market}">
<div>
<span class="asset-name">{s['name']}</span>
<span class="asset-tag">{s.get('direction','')}</span>
<span class="asset-meta">{s.get('source','')} · {motif}</span>
<span class="asset-levels">
<span style="color:#bae6fd">🚪 {price_fmt}</span>
<span style="color:#ef4444">🛑 {stop_fmt}</span>
<span style="color:#22c55e">🎯 {tp_fmt} <small>{is_bullish and '+' or '-'}{tp_pct}%</small></span>
</span>
</div>
<div style="text-align:right">
<span class="score-pill {color_class}">{score}</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">RR {rr}:1 · −{risk_pct}%</div>
<div style="font-size:.7em;color:{badge_color};margin-top:2px">{badge_text}</div>
<div><span class="session-led asset-session" data-session-label>Session check…</span></div>
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
<p>Tradeable setups from Yahoo Finance OHLCV daily data.<br>ATR-based stops/targets · Bull/Bear scoring · RR ≥ 1.0 required</p>
<div class="formula">
<span class="chip">Entry = current</span>
<span class="chip">SL = contextual ATR + structure</span>
<span class="chip">TP = class-aware RR</span>
<span class="chip"></span>
<span class="chip">RR ≥ 1.0</span>
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
<span>✅ TRADEABLE — RR ≥ 1.0, levels valid</span>
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
        "longs": [{"name": s["name"], "entry": s["entry"], "stop": s["stop"], "tp": s["tp"], "tp_pct": s["tp_pct"], "rr": s["rr"]} for s in setups_long],
        "shorts": [{"name": s["name"], "entry": s["entry"], "stop": s["stop"], "tp": s["tp"], "tp_pct": s["tp_pct"], "rr": s["rr"]} for s in setups_short],
    }
    (OUTPUT_DIR / f"scanner_{NOW}.json").write_text(json.dumps(report, indent=2))
    
    return scanner_html

if __name__ == "__main__":
    main()
