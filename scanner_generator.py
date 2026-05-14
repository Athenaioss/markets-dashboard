#!/usr/bin/env python3
"""
🦅 Hawkeye v3 — Pressure Quality Scanner
Trend 30 · Momentum 25 · RSI 15 · Volume 15 · Structure 15
Swing proximity replaces data-quality proxy · no TP/SL/RR code path
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

# ── Hawkeye v3 Scoring ──

def _safe_price(a):
    try:
        return float(a.get("price") or a.get("current_price") or a.get("close") or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_hawkeye_scores(all_assets):
    """
    🦅 Hawkeye v3 — True /100 directional pressure scoring.

    Trend 30 · Momentum 25 · RSI/entry 15 · Volume/participation 15 · Structure 15.
    Chase penalty: extension from EMA20 > 2 ATR subtracts 10.
    No TP/SL/RR code path: this is a pressure/rank scanner, not a trade ticket generator.
    """
    for a in all_assets:
        price0 = _safe_price(a) or 1.0
        cp = [float(x) for x in (a.get("_close_prices") or []) if x is not None]
        hp = [float(x) for x in (a.get("_high_prices") or []) if x is not None]
        lp = [float(x) for x in (a.get("_low_prices") or []) if x is not None]
        if len(cp) < 10:
            cp = [price0] * 30
        if len(hp) < len(cp):
            hp = cp[:]
        if len(lp) < len(cp):
            lp = cp[:]

        price = cp[-1]
        ema20 = ema(cp, 20)
        ema50 = ema(cp, 50) if len(cp) >= 50 else ema(cp, min(50, len(cp)))
        slope = ema20_slope(cp)
        rsi14 = rsi(cp, 14)
        roc5 = roc(cp, 5)
        roc20 = roc(cp, 20)
        p_roc5 = prev_roc5(cp)
        macd_h = macd_hist(cp)
        atr = atr_val(hp, lp, cp, 14)
        if not atr or atr <= 0:
            atr = max(abs(price) * 0.01, 0.01)
        atr_pct = round(atr / price * 100, 2) if price else 0
        ema_extension_atr = abs(price - ema20) / atr if atr else 0
        sw_low = swing_low(lp)
        sw_high = swing_high(hp)
        dist_to_sw_low = (price - sw_low) / atr if atr else 99
        dist_to_sw_high = (sw_high - price) / atr if atr else 99
        vol_ratio = float(a.get("vol_ratio") or 0)
        has_volume = vol_ratio > 0
        candle_ratio = a.get("candle_ratio", None)
        try:
            candle_ratio = float(candle_ratio) if candle_ratio is not None else None
        except (TypeError, ValueError):
            candle_ratio = None
        candle_ok = candle_ratio is not None and candle_ratio <= 0.75

        bull = 0
        # Trend — 30
        if price > ema20: bull += 10
        if ema20 > ema50: bull += 10
        if slope > 0: bull += 10
        # Momentum — 25
        if roc5 > 0: bull += 7
        if roc20 > 0: bull += 7
        if macd_h > 0: bull += 6
        if roc5 > p_roc5: bull += 5
        # RSI / entry quality — 15; dead zone 47-53 gives 0
        if 53 <= rsi14 <= 66:
            bull += 15
        elif (45 <= rsi14 < 47) or (66 < rsi14 <= 72):
            bull += 8
        elif rsi14 > 72:
            bull -= 5
        # Volume / participation — 15
        if has_volume:
            if 1.1 <= vol_ratio <= 2.5:
                bull += 10
            elif vol_ratio > 2.5:
                bull += 5
            if candle_ok:
                bull += 5
        else:
            bull += 5  # no-volume assets, especially FX: strict neutral
        # Structure / tradeability — 15
        if 0.0 <= dist_to_sw_low <= 1.0:
            bull += 8
        elif 1.0 < dist_to_sw_low <= 2.0:
            bull += 4
        if ema_extension_atr <= 1.0:
            bull += 7
        elif ema_extension_atr <= 1.5:
            bull += 4
        elif ema_extension_atr <= 2.0:
            bull += 2
        if ema_extension_atr > 2.0:
            bull -= 10

        bear = 0
        # Mirrored Trend — 30
        if price < ema20: bear += 10
        if ema20 < ema50: bear += 10
        if slope < 0: bear += 10
        # Mirrored Momentum — 25
        if roc5 < 0: bear += 7
        if roc20 < 0: bear += 7
        if macd_h < 0: bear += 6
        if roc5 < p_roc5: bear += 5
        # Mirrored RSI / entry quality — 15; dead zone 47-53 gives 0
        if 34 <= rsi14 <= 47:
            bear += 15
        elif (28 <= rsi14 < 34) or (53 < rsi14 <= 55):
            bear += 8
        elif rsi14 < 28:
            bear -= 5
        # Volume / participation — 15
        if has_volume:
            if 1.1 <= vol_ratio <= 2.5:
                bear += 10
            elif vol_ratio > 2.5:
                bear += 5
            if candle_ok:
                bear += 5
        else:
            bear += 5
        # Mirrored Structure — 15
        if 0.0 <= dist_to_sw_high <= 1.0:
            bear += 8
        elif 1.0 < dist_to_sw_high <= 2.0:
            bear += 4
        if ema_extension_atr <= 1.0:
            bear += 7
        elif ema_extension_atr <= 1.5:
            bear += 4
        elif ema_extension_atr <= 2.0:
            bear += 2
        if ema_extension_atr > 2.0:
            bear -= 10

        bull = max(0, min(100, int(round(bull))))
        bear = max(0, min(100, int(round(bear))))

        a.update({
            "bull_score": bull,
            "bear_score": bear,
            "_atr": atr,
            "_atr_pct": atr_pct,
            "_ema20": ema20,
            "_ema50": ema50,
            "_ema20_slope": slope,
            "_rsi": rsi14,
            "_swing_low": sw_low,
            "_swing_high": sw_high,
            "_macd_h": macd_h,
            "_roc5": roc5,
            "_roc20": roc20,
            "_prev_roc5": p_roc5,
            "_extension_atr": round(ema_extension_atr, 2),
            "_dist_to_sw_low": round(dist_to_sw_low, 2),
            "_dist_to_sw_high": round(dist_to_sw_high, 2),
        })


# ── Tier labels ──

def score_tier(score):
    if score >= 90: return ("EXTREME", "⚡ EXTREME", "#22c55e")
    if score >= 80: return ("STRONG", "🦅 STRONG", "#22c55e")
    if score >= 65: return ("ACTIVE", "👁️ ACTIVE", "#f59e0b")
    return ("WATCH", "📡 WATCH", "#64748b")


def compact_forex_symbol(symbol):
    return (symbol or "").upper().replace("=X", "")


def display_asset_name(asset):
    if asset.get("source") == "forex":
        compact = compact_forex_symbol(asset.get("symbol", ""))
        if compact:
            return compact
    return asset.get("name", asset.get("symbol", "?"))


def _entry_precision(asset):
    symbol = (asset.get("symbol") or "").upper()
    source = asset.get("source", "")
    price = _safe_price(asset)
    if source == "forex":
        return 2 if "JPY" in symbol else 4
    return 2 if price >= 1 else 4


def pressure_label(score):
    tier, label, color = score_tier(score)
    if score < 65:
        return "IGNORE", "Ignore", "#64748b"
    if score < 80:
        return tier, "Watchlist", color
    return tier, "Strong setup", color


def _signal(asset, direction, score):
    tier, label, color = score_tier(score)
    return {
        "name": display_asset_name(asset),
        "source": asset.get("source", ""),
        "direction": direction,
        "symbol": asset.get("symbol", ""),
        "score": int(score),
        "tier": tier,
        "label": label,
        "color": color,
        "entry": round(_safe_price(asset), _entry_precision(asset)),
        "precision": _entry_precision(asset),
        "rsi": asset.get("_rsi", 50),
        "change_pct": asset.get("change_pct", asset.get("change_24h", 0)),
        "extension_atr": asset.get("_extension_atr", 0),
        "roc5": asset.get("_roc5", 0),
        "roc20": asset.get("_roc20", 0),
        "vol_ratio": asset.get("vol_ratio", 0),
        "motif": "bull pressure" if direction == "BULL" else "bear pressure",
    }


def build_pressure_signals(assets):
    """Build ranked pressure signals. Mixed assets are not duplicated in bull/bear."""
    bull, bear, mixed = [], [], []
    for a in assets:
        if not _safe_price(a):
            continue
        bs = int(a.get("bull_score", 0))
        rs = int(a.get("bear_score", 0))
        if bs >= 55 and rs >= 55:
            dominant = "BULL" if bs >= rs else "BEAR"
            sig = _signal(a, dominant, max(bs, rs))
            sig["bull_score"] = bs
            sig["bear_score"] = rs
            sig["motif"] = "mixed / volatile pressure"
            mixed.append(sig)
            continue
        if bs >= 65:
            bull.append(_signal(a, "BULL", bs))
        if rs >= 65:
            bear.append(_signal(a, "BEAR", rs))
    bull.sort(key=lambda x: x["score"], reverse=True)
    bear.sort(key=lambda x: x["score"], reverse=True)
    mixed.sort(key=lambda x: max(x.get("bull_score", 0), x.get("bear_score", 0)), reverse=True)
    return bull[:7], bear[:7], mixed[:5]


# Backward-compat alias for older imports/scripts.
build_setups = build_pressure_signals


# ── HTML Generation ──

def market_for_source(source):
    return {"actions": "stocks"}.get(source, source)


def setup_card(title, emoji, setups, color_class, empty_label="No active pressure signal"):
    if not setups:
        return f"""<div class="signal-card"><h3>{emoji} {title}</h3>
<div class="no-signal">{empty_label}</div></div>"""
    rows = ""
    for s in setups:
        score = s["score"]
        tier = s["tier"]
        label = s["label"]
        badge_color = s["color"]
        market = market_for_source(s.get("source", ""))
        score_class = "score-hot" if score >= 80 else "score-warm" if score >= 65 else "score-muted"
        entry = s["entry"]
        precision = int(s.get("precision", 2 if entry > 1 else 4))
        price_fmt = f"${entry:,.{precision}f}"
        direction_tag = s.get("direction", "")
        ext = s.get("extension_atr", 0)
        chase = " · chase risk" if ext and ext > 2 else ""
        rows += f"""<div class="signal-row" data-market="{market}">
<div>
<span class="asset-name">{s['name']}</span>
<span class="asset-tag">{direction_tag}</span>
<span class="asset-meta">{s.get('source','')} · {s.get('motif','pressure')}{chase}</span>
<span class="asset-levels">
<span style="color:#bae6fd">🎟️ {price_fmt}</span>
<span style="color:#a7f3d0">ROC5 {s.get('roc5',0):+.1f}%</span>
<span style="color:#fbbf24">RSI {s.get('rsi',50)}</span>
<span style="color:#c4b5fd">Ext {ext:.1f} ATR</span>
</span>
</div>
<div style="text-align:right">
<span class="score-pill {score_class}">{score}/100</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">Δ {s.get('change_pct',0):+.1f}% · Vol {s.get('vol_ratio',0):.1f}x</div>
<div style="font-size:.7em;color:{badge_color};margin-top:2px">{s.get('label', label)}</div>
<div><span class="session-led asset-session" data-session-label>Session check…</span></div>
</div>
</div>"""
    return f"""<div class="signal-card"><h3>{emoji} {title} ({len(setups)})</h3>{rows}</div>"""


def mixed_card(mixed):
    if not mixed:
        return ""
    rows = ""
    for s in mixed:
        entry = s["entry"]
        precision = int(s.get("precision", 2 if entry > 1 else 4))
        price_fmt = f"${entry:,.{precision}f}"
        market = market_for_source(s.get("source", ""))
        rows += f"""<div class="signal-row" data-market="{market}">
<div>
<span class="asset-name">{s['name']}</span>
<span class="asset-tag">MIXED</span>
<span class="asset-meta">{s.get('source','')} · contradictory pressure / volatile tape</span>
<span class="asset-levels"><span style="color:#bae6fd">🎟️ {price_fmt}</span><span style="color:#22c55e">Bull {s.get('bull_score',0)}</span><span style="color:#ef4444">Bear {s.get('bear_score',0)}</span></span>
</div>
<div style="text-align:right"><span class="score-pill score-warm">{s['score']}/100</span><div style="font-size:.7em;color:#f59e0b;margin-top:2px">⚠️ MIXED / VOLATILE</div></div>
</div>"""
    return f"""<div class="signal-card mixed-card"><h3>⚠️ Mixed / Volatile ({len(mixed)})</h3>{rows}</div>"""


SOURCE_META = {
    "crypto": ("🪙", "Crypto"),
    "commodities": ("🛢️", "Commo"),
    "indices": ("🌍", "Indices"),
    "forex": ("💱", "Forex"),
    "actions": ("🏛️", "Stocks"),
    "etf": ("💼", "ETF"),
}


def bias_label(net):
    if net >= 12:
        return "🟢 Bullish"
    if net >= 4:
        return "🟡 Slight Bullish"
    if net <= -12:
        return "🔴 Bearish"
    if net <= -4:
        return "🟠 Slight Bearish"
    return "⚪ Neutral"


def macro_pulse_html(assets):
    by_source = []
    total_bull = sum(1 for a in assets if a.get("bull_score", 0) >= 65 and a.get("bear_score", 0) < 55)
    total_bear = sum(1 for a in assets if a.get("bear_score", 0) >= 65 and a.get("bull_score", 0) < 55)
    avg_net = 0
    if assets:
        avg_net = sum(a.get("bull_score", 0) - a.get("bear_score", 0) for a in assets) / len(assets)
    for src, (emoji, label) in SOURCE_META.items():
        subset = [a for a in assets if a.get("source") == src]
        if not subset:
            by_source.append(f"<span>{emoji} {label} ⚪ No data</span>")
            continue
        net = sum(a.get("bull_score", 0) - a.get("bear_score", 0) for a in subset) / len(subset)
        by_source.append(f"<span>{emoji} {label} {bias_label(net)}</span>")
    return f"""<div class="macro-pulse">
<div class="macro-bias">{bias_label(avg_net)} Bias</div>
<div class="macro-sources">{' '.join(by_source)}</div>
<div class="macro-counts"><span>🟢 {total_bull} bullish pressure</span><span>🔴 {total_bear} bearish pressure</span><span>📡 {len(assets)} actifs analysés</span></div>
</div>"""


def main():
    print("🦅 Hawkeye v3 — Pressure Quality Scanner")
    print("-" * 50)
    sources = {
        "crypto": "crypto_*.json", "commodities":"commodities_*.json",
        "indices":"indices_*.json", "forex":"forex_*.json",
        "actions":"actions_*.json", "etf":"etf_*.json",
    }
    all_assets = []
    for src, pattern in sources.items():
        assets = load_latest(pattern)
        for a in assets:
            a["source"] = src
        all_assets.extend(assets)
        print(f"  {src}: {len(assets)} assets")

    def is_playable(a):
        ch = a.get("change_pct", a.get("change_24h", 0))
        return abs(ch) < 80 and a.get("_close_prices")

    assets_clean = [a for a in all_assets if is_playable(a)]
    skipped = len(all_assets) - len(assets_clean)
    if skipped:
        print(f"  ⚠️ Filtered {skipped} artifacts")

    compute_hawkeye_scores(assets_clean)
    bulls = [a["bull_score"] for a in assets_clean]
    bears = [a["bear_score"] for a in assets_clean]
    strong_bulls = sum(1 for s in bulls if s >= 80)
    active_bulls = sum(1 for s in bulls if 65 <= s < 80)
    strong_bears = sum(1 for s in bears if s >= 80)
    active_bears = sum(1 for s in bears if 65 <= s < 80)
    print(f"  🟢 Bull: {strong_bulls} Strong · {active_bulls} Active")
    print(f"  🔴 Bear: {strong_bears} Strong · {active_bears} Active")

    bullish, bearish, mixed = build_pressure_signals(assets_clean)
    print(f"  📈 Bull pressure: {len(bullish)}")
    print(f"  📉 Bear pressure: {len(bearish)}")
    print(f"  ⚠️ Mixed/Volatile: {len(mixed)}")

    pulse = macro_pulse_html(assets_clean)
    bull_card = setup_card("Bullish Pressure", "📈", bullish, "score-hot")
    bear_card = setup_card("Bearish Pressure", "📉", bearish, "score-risk")
    mixed_html = mixed_card(mixed)

    scanner_html = f"""<!-- 🦅 Hawkeye v3 — {NOW} -->
<section id="scanner" class="scanner hawkeye-v3">
<div class="scanner-head">
<div>
<h2>🦅 Hawkeye v3 — Pressure Scanner</h2>
{pulse}
</div>
<div class="scanner-score">
<div class="num">{len(assets_clean)}</div>
<div class="label">assets scored</div>
</div>
</div>

<div class="scanner-board" style="grid-template-columns:repeat(2,1fr)">
{bull_card}
{bear_card}
{mixed_html}
</div>

<div class="legend">
<span>⚡ EXTREME 90-100</span>
<span>🦅 STRONG 80-89 — Strong setup</span>
<span>👁️ ACTIVE 65-79 — Watchlist</span>
<span>📡 &lt;65 — Ignore</span>
<span class="demo-tag">Updated {UPDATED_AT_LABEL}</span>
<span class="demo-tag">Yahoo Finance · quality pressure score /100 · {NOW}</span>
</div>
</section>"""

    frag_path = OUTPUT_DIR / f"scanner_{NOW}.html"
    frag_path.write_text(scanner_html)
    print(f"\n✅ Scanner: {frag_path}")

    report = {
        "generated": NOW,
        "scoring": "Hawkeye v3 — quality pressure /100",
        "total": len(assets_clean),
        "distribution": {
            "bull_strong": strong_bulls, "bull_active": active_bulls,
            "bear_strong": strong_bears, "bear_active": active_bears,
            "mixed": len(mixed),
        },
        "bullish_pressure": [{"name": s["name"], "score": s["score"], "tier": s["tier"], "entry": s["entry"]} for s in bullish],
        "bearish_pressure": [{"name": s["name"], "score": s["score"], "tier": s["tier"], "entry": s["entry"]} for s in bearish],
        "mixed_volatile": [{"name": s["name"], "bull_score": s.get("bull_score"), "bear_score": s.get("bear_score"), "entry": s["entry"]} for s in mixed],
    }
    (OUTPUT_DIR / f"scanner_{NOW}.json").write_text(json.dumps(report, indent=2))
    return scanner_html


if __name__ == "__main__":
    main()
