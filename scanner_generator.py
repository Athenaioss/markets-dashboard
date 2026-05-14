#!/usr/bin/env python3
"""
🦅 Hawkeye v2 — Directional Scanner with True /100 Scoring
Trend 30 · Momentum 25 · RSI 15 · Volume 15 · Structure 15
Chase penalty: extension > 2 ATR → -10
Data: Yahoo Finance OHLCV daily
"""

import json, os, math, statistics
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
GENERATED_AT = datetime.now().astimezone()
NOW = GENERATED_AT.strftime("%Y%m%d-%H%M%S")
UPDATED_AT_LABEL = GENERATED_AT.strftime("%d/%m/%Y %H:%M %Z")

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
    if len(highs) < period + 1: return 0.01
    trs = []
    for i in range(-period, 0):
        h, l, pc = highs[i], lows[i], closes[i-1] if i > -len(closes) else closes[i]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period

def swing_low(lows, window=10):
    if len(lows) < window: return min(lows)
    return min(lows[-window:])

def swing_high(highs, window=10):
    if len(highs) < window: return max(highs)
    return max(highs[-window:])

def ema20_slope(cp):
    """EMA20 slope: (current - 5 bars ago) / 5 bars ago * 100, sign-preserving pct"""
    if len(cp) < 25: return 0
    ema_now = ema(cp, 20)
    ema_prev = ema(cp[:-5], 20)
    if ema_prev == 0: return 0
    return round((ema_now - ema_prev) / ema_prev * 100, 2)

def prev_roc5(cp):
    """ROC5 computed 1 bar before current"""
    if len(cp) < 7: return 0
    return roc(cp[:-1], 5)

# ── Loading ──

def load_latest(pattern):
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files: return []
    with open(files[0]) as f:
        data = json.load(f)
    if isinstance(data, list): return data
    if isinstance(data, dict) and "data" in data: return data["data"]
    return []

# ── Hawkeye v2 Scoring ──

def compute_hawkeye_scores(all_assets):
    """
    🦅 Hawkeye v2 — True /100 Directional Scoring
    
    Trend         30 pts  (price > EMA20, EMA20 > EMA50, EMA20 slope+)
    Momentum      25 pts  (ROC5+, ROC20+, MACD hist+, ROC5 improving)
    RSI / Entry   15 pts  (52-66 optimal, 45-52/66-72 neutral, >72 penalty)
    Volume        15 pts  (vol ratio 1.1-2.5x optimal, >2.5x exhaustion, <0.8x zero)
    Structure     15 pts  (RR check, extension from EMA20)
    
    Penalty: extension from EMA20 > 2 ATR → -10 (chase penalty)
    
    Tiers: 80-100 = Strong · 65-79 = Watchlist · <65 = Ignore
    """
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
        
        slope = ema20_slope(cp)
        p_roc5 = prev_roc5(cp)
        
        vol_ratio = a.get("vol_ratio", 0)
        has_volume = bool(vol_ratio and vol_ratio > 0)
        candle_ratio = a.get("candle_ratio", None)
        
        extension_atr = abs(price - ema20) / atr if atr > 0 else 0
        
        # ═══════════════════════════════════════
        # BULL SCORE
        # ═══════════════════════════════════════
        bull = 0
        
        # ── Trend (30 pts) ──
        if price > ema20:   bull += 10
        if ema20 > ema50:   bull += 10
        if slope > 0:       bull += 10
        
        # ── Momentum (25 pts) ──
        if roc5 > 0:        bull += 7
        if roc20 > 0:       bull += 7
        if macd_h > 0:      bull += 6
        if roc5 > p_roc5:   bull += 5  # ROC5 accelerating
        
        # ── RSI / Entry quality (15 pts) ──
        if 52 <= rsi14 <= 66:
            bull += 15
        elif (45 <= rsi14 < 52) or (66 < rsi14 <= 72):
            bull += 8
        # RSI > 72 → 0 (overbought — no bull points)
        # RSI < 45 → 0 (too weak for bull)
        
        # ── Volume / Participation (15 pts) ──
        if has_volume:
            if 1.1 <= vol_ratio <= 2.5:
                bull += 10
            elif vol_ratio > 2.5:
                bull += 5  # possible exhaustion
            # vol_ratio < 0.8 → 0
            
            # Candle body not overextended (healthy participation)
            if candle_ratio is not None and candle_ratio < 0.75:
                bull += 5
            elif candle_ratio is not None:
                pass  # large body relative to range = possible exhaustion or gap
            else:
                bull += 3  # no candle data → neutral
        else:
            # Forex & assets without volume → neutral volume score
            bull += 7
        
        # ── Structure / Tradeability (15 pts) ──
        # RR check: does the asset have enough data to build a setup?
        if atr > 0 and len(cp) >= 20:
            bull += 8  # data quality gate — real RR computed at setup time
        
        # Price proximity to EMA20 / support
        if extension_atr <= 1.5:
            bull += 7
        elif extension_atr <= 2.0:
            bull += 3
        # > 2.0 → 0 points (chasing)
        
        # ── Chase / Extension Penalty ──
        if extension_atr > 2.0:
            bull -= 10
        
        bull = max(0, min(100, bull))
        
        # ═══════════════════════════════════════
        # BEAR SCORE (Mirrored)
        # ═══════════════════════════════════════
        bear = 0
        
        # ── Trend (30 pts) ──
        if price < ema20:   bear += 10
        if ema20 < ema50:   bear += 10
        if slope < 0:       bear += 10
        
        # ── Momentum (25 pts) ──
        if roc5 < 0:        bear += 7
        if roc20 < 0:       bear += 7
        if macd_h < 0:      bear += 6
        if roc5 < p_roc5:   bear += 5  # ROC5 accelerating downward
        
        # ── RSI / Entry quality (15 pts) ──
        if 34 <= rsi14 <= 48:
            bear += 15
        elif (28 <= rsi14 < 34) or (48 < rsi14 <= 55):
            bear += 8
        # RSI < 28 → 0 (oversold — no bear points)
        # RSI > 55 → 0 (too strong for bear)
        
        # ── Volume / Participation (15 pts) ──
        if has_volume:
            if 1.1 <= vol_ratio <= 2.5:
                bear += 10
            elif vol_ratio > 2.5:
                bear += 5
            if candle_ratio is not None and candle_ratio < 0.75:
                bear += 5
            elif candle_ratio is not None:
                pass
            else:
                bear += 3
        else:
            bear += 7
        
        # ── Structure / Tradeability (15 pts) ──
        if atr > 0 and len(cp) >= 20:
            bear += 8
        
        if extension_atr <= 1.5:
            bear += 7
        elif extension_atr <= 2.0:
            bear += 3
        
        if extension_atr > 2.0:
            bear -= 10
        
        bear = max(0, min(100, bear))
        
        # Store
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


# ── Tier labels ──

def score_tier(score):
    if score >= 80: return ("STRONG", "#22c55e")
    if score >= 65: return ("WATCHLIST", "#f59e0b")
    return ("IGNORE", "#64748b")


# ── Source Profiles (unchanged) ──

def source_profile(source, symbol=""):
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
    return (symbol or "").upper().replace("=X", "")

def display_asset_name(asset):
    if asset.get("source") == "forex":
        compact = compact_forex_symbol(asset.get("symbol", ""))
        if compact:
            return compact
    return asset.get("name", asset.get("symbol", "?"))


def build_setups(assets):
    """
    Build tradeable setups using Hawkeye v2 tiers.
    Strong (80-100) → always included
    Watchlist (65-79) → included, labeled WATCH
    Ignore (<65) → excluded
    """
    setups_long = []
    setups_short = []
    
    for a in assets:
        price = a.get("price", 0)
        atr = a.get("_atr", 0.01)
        if not price or not atr: continue
        
        name = display_asset_name(a)
        bull = a["bull_score"]
        bear = a["bear_score"]
        
        # ── LONG setup ──
        if bull >= 65:
            levels = contextual_levels(a, "LONG")
            if levels and levels["stop"] < levels["entry"] and levels["tp"] > levels["entry"] and levels["rr"] >= 1.0:
                tier, _ = score_tier(bull)
                setups_long.append(dict(
                    name=name, source=a.get("source", ""), direction="LONG",
                    symbol=a.get("symbol", ""), score=bull, tier=tier, **levels,
                    rsi=a.get("_rsi", 50), change_pct=a.get("change_pct", 0),
                    motif=f"{tier} setup",
                    status="TRADEABLE" if tier == "STRONG" else "WATCHLIST"
                ))
        
        # ── SHORT setup ──
        if bear >= 65:
            levels = contextual_levels(a, "SHORT")
            if levels and levels["stop"] > levels["entry"] and levels["tp"] < levels["entry"] and levels["rr"] >= 1.0:
                tier, _ = score_tier(bear)
                setups_short.append(dict(
                    name=name, source=a.get("source", ""), direction="SHORT",
                    symbol=a.get("symbol", ""), score=bear, tier=tier, **levels,
                    rsi=a.get("_rsi", 50), change_pct=a.get("change_pct", 0),
                    motif=f"{tier} setup",
                    status="TRADEABLE" if tier == "STRONG" else "WATCHLIST"
                ))
    
    # Sort by score descending, take top 7
    setups_long.sort(key=lambda s: s["score"], reverse=True)
    setups_short.sort(key=lambda s: s["score"], reverse=True)
    
    return setups_long[:7], setups_short[:7]


# ── HTML Generation ──

def market_for_source(source):
    return {"actions": "stocks"}.get(source, source)

def setup_card(title, emoji, setups, color_class, is_bullish=True):
    if not setups:
        return f"""<div class="signal-card"><h3>{emoji} {title}</h3>
<div class="no-signal">No valid {title.lower()} setup (all assets scored < 65)</div></div>"""
    
    rows = ""
    for s in setups:
        score = s["score"]
        entry = s["entry"]
        tier = s["tier"]
        status = s["status"]
        motif = s.get("motif", "")
        market = market_for_source(s.get("source", ""))
        
        if tier == "STRONG":
            badge = "🦅 STRONG"
            badge_color = "#22c55e"
            score_class = "score-hot"
        elif tier == "WATCHLIST":
            badge = "👁️ WATCH"
            badge_color = "#f59e0b"
            score_class = "score-warm"
        else:
            badge = "⏳ IGNORE"
            badge_color = "#64748b"
            score_class = "score-muted"
        
        precision = int(s.get("precision", 2 if entry > 1 else 4))
        price_fmt = f"${entry:,.{precision}f}"
        
        rows += f"""<div class="signal-row" data-market="{market}">
<div>
<span class="asset-name">{s['name']}</span>
<span class="asset-tag">{s.get('direction','')}</span>
<span class="asset-meta">{s.get('source','')} · {motif}</span>
<span class="asset-levels">
<span style="color:#bae6fd">🎟️ {price_fmt}</span>
</span>
</div>
<div style="text-align:right">
<span class="score-pill {score_class}">{score}</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">Δ {s.get('change_pct',0):+.1f}% · RSI {s.get('rsi',50)}</div>
<div style="font-size:.7em;color:{badge_color};margin-top:2px">{badge}</div>
<div><span class="session-led asset-session" data-session-label>Session check…</span></div>
</div>
</div>"""
    
    return f"""<div class="signal-card"><h3>{emoji} {title} ({len(setups)})</h3>{rows}</div>"""


def main():
    print("🦅 Hawkeye v2 — True /100 Directional Scanner")
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
    
    compute_hawkeye_scores(assets_clean)
    
    # Score distribution
    bulls = [a["bull_score"] for a in assets_clean]
    bears = [a["bear_score"] for a in assets_clean]
    strong_bulls = sum(1 for s in bulls if s >= 80)
    watch_bulls = sum(1 for s in bulls if 65 <= s < 80)
    strong_bears = sum(1 for s in bears if s >= 80)
    watch_bears = sum(1 for s in bears if 65 <= s < 80)
    
    print(f"  🦅 Bull: {strong_bulls} Strong · {watch_bulls} Watch · {len(bulls)-strong_bulls-watch_bulls} Ignore")
    print(f"  🐻 Bear: {strong_bears} Strong · {watch_bears} Watch · {len(bears)-strong_bears-watch_bears} Ignore")
    
    setups_long, setups_short = build_setups(assets_clean)
    
    print(f"  📈 LONG setups: {len(setups_long)}")
    print(f"  📉 SHORT setups: {len(setups_short)}")
    
    long_card  = setup_card("Long Setups", "📈", setups_long, "score-hot", True)
    short_card = setup_card("Short Setups", "📉", setups_short, "score-risk", False)
    
    scanner_html = f"""<!-- 🦅 Hawkeye v2 — {NOW} -->
<section id="scanner" class="scanner">
<div class="scanner-head">
<div>
<h2>🦅 Hawkeye v2 — Directional Scanner</h2>
<p>True /100 scoring · Trend 30 · Momentum 25 · RSI 15 · Volume 15 · Structure 15<br>
<strong>80-100 Strong</strong> · 65-79 Watchlist · &lt;65 Ignored · Chase penalty at &gt;2 ATR extension</p>
<div class="formula">
<span class="chip">Trend 30</span>
<span class="chip">Momentum 25</span>
<span class="chip">RSI 15</span>
<span class="chip">Volume 15</span>
<span class="chip">Structure 15</span>
<span class="chip">Chase -10</span>
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
<span>🦅 STRONG 80-100 — tradeable directional setup</span>
<span>👁️ WATCH 65-79 — monitor for entry</span>
<span class="demo-tag">Updated {UPDATED_AT_LABEL}</span>
<span class="demo-tag">Yahoo Finance · {NOW}</span>
</div>
</section>"""
    
    frag_path = OUTPUT_DIR / f"scanner_{NOW}.html"
    frag_path.write_text(scanner_html)
    print(f"\n✅ Scanner: {frag_path}")
    
    # Report
    report = {
        "generated": NOW,
        "scoring": "Hawkeye v2 — True /100",
        "total": len(assets_clean),
        "distribution": {
            "bull_strong": strong_bulls, "bull_watch": watch_bulls,
            "bear_strong": strong_bears, "bear_watch": watch_bears,
        },
        "long_setups": [{"name": s["name"], "score": s["score"], "tier": s["tier"],
                         "entry": s["entry"], "stop": s["stop"], "tp": s["tp"],
                         "tp_pct": s["tp_pct"], "rr": s["rr"]} for s in setups_long],
        "short_setups": [{"name": s["name"], "score": s["score"], "tier": s["tier"],
                          "entry": s["entry"], "stop": s["stop"], "tp": s["tp"],
                          "tp_pct": s["tp_pct"], "rr": s["rr"]} for s in setups_short],
    }
    (OUTPUT_DIR / f"scanner_{NOW}.json").write_text(json.dumps(report, indent=2))
    
    return scanner_html

if __name__ == "__main__":
    main()
