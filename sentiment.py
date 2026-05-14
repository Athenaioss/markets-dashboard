"""
🦅 Hawkeye v3 Sentiment Engine — Quality Pressure Scoring
Used by all Atlas Nexus pipelines (crypto, commodities, indices, forex, actions, etf).

Trend 30 · Momentum 25 · RSI 15 · Volume 15 · Structure 15
Swing proximity replaces data-quality proxy · no TP/SL/RR ticket levels
Chase penalty: extension > 2 ATR → -10
Tiers: 90+ Extreme · 80-89 Strong · 65-79 Active · <65 Ignore
"""

from __future__ import annotations

from html import escape
import statistics, math


# ═══════════════════════════════════════════════════════════════
# Technical Indicators (same as scanner_generator.py)
# ═══════════════════════════════════════════════════════════════

def _ema(data, period):
    if len(data) < period: return data[-1] if data else 0
    k = 2 / (period + 1)
    val = sum(data[:period]) / period
    for x in data[period:]: val = x * k + val * (1 - k)
    return val

def _rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains, losses = [], []
    for i in range(-period, 0):
        ch = prices[i] - prices[i-1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
    avg_gain = sum(gains)/period; avg_loss = sum(losses)/period
    if avg_loss == 0: return 100
    return round(100 - 100/(1 + avg_gain/avg_loss))

def _roc(prices, period):
    if len(prices) < period + 1: return 0
    old = prices[-period-1]
    return (prices[-1] - old) / old * 100 if old else 0

def _macd_hist(prices):
    if len(prices) < 26: return 0
    e12 = _ema(prices, 12); e26 = _ema(prices, 26)
    return round((e12 - e26) / e26 * 100, 2) if e26 else 0

def _atr_val(highs, lows, closes, period=14):
    if len(highs) < period + 1: return 0.01
    trs = []
    for i in range(-period, 0):
        h, l = highs[i], lows[i]
        pc = closes[i-1] if i > -len(closes) else closes[i]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period

def _ema20_slope(cp):
    """EMA20 slope: (current - 5 bars ago) as % of 5-bars-ago value"""
    if len(cp) < 25: return 0
    ema_now = _ema(cp, 20)
    ema_prev = _ema(cp[:-5], 20)
    if ema_prev == 0: return 0
    return round((ema_now - ema_prev) / ema_prev * 100, 2)

def _prev_roc5(cp):
    """ROC5 computed 1 bar before current"""
    if len(cp) < 7: return 0
    return _roc(cp[:-1], 5)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _num(value, default=0.0) -> float:
    try:
        if value is None: return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _asset_name(a: dict) -> str:
    return str(a.get("name") or a.get("symbol") or a.get("base") or "Asset")

def _asset_symbol(a: dict) -> str:
    sym = a.get("symbol")
    if sym: return str(sym)
    if a.get("base") and a.get("quote"): return f"{a['base']}{a['quote']}"
    return _asset_name(a)

def _asset_group(a: dict) -> str:
    for key in ("sector", "category", "region", "group", "mcap_tier", "source"):
        if a.get(key): return str(a[key])
    return "Market"

def _change_pct(a: dict) -> float:
    if "change_pct" in a: return _num(a.get("change_pct"))
    if "change_24h" in a: return _num(a.get("change_24h"))
    return _num(a.get("change"))


# ═══════════════════════════════════════════════════════════════
# 🦅 Hawkeye v3 — Quality Pressure Scoring
# ═══════════════════════════════════════════════════════════════

def _swing_low(lows, window=10):
    if not lows: return 0
    return min(lows[-window:]) if len(lows) >= window else min(lows)


def _swing_high(highs, window=10):
    if not highs: return 0
    return max(highs[-window:]) if len(highs) >= window else max(highs)


def _hawkeye_score(a: dict) -> dict:
    """Hawkeye v3: rank directional pressure quality /100, not TP/SL/RR trade tickets."""
    price0 = _num(a.get("price") or a.get("current_price") or a.get("close"), 1.0)
    cp = [float(x) for x in (a.get("_close_prices") or []) if x is not None]
    hp = [float(x) for x in (a.get("_high_prices") or []) if x is not None]
    lp = [float(x) for x in (a.get("_low_prices") or []) if x is not None]
    if len(cp) < 10:
        trend = str(a.get("trend", "NEUTRAL")).upper()
        ch = _change_pct(a)
        bull = 65 if trend == "BULLISH" and ch > 0 else 50 if ch > 0 else 30
        bear = 65 if trend == "BEARISH" and ch < 0 else 50 if ch < 0 else 30
        return {"bull_score": bull, "bear_score": bear, "rsi": 50, "roc5": ch, "roc20": ch, "ema20_ext": 0, "tier_bull": _tier(bull), "tier_bear": _tier(bear), "tags": [("Trend", trend.title())]}
    if len(hp) < len(cp): hp = cp[:]
    if len(lp) < len(cp): lp = cp[:]
    price = cp[-1]
    ema20 = _ema(cp, 20)
    ema50 = _ema(cp, 50) if len(cp) >= 50 else _ema(cp, min(50, len(cp)))
    rsi14 = _rsi(cp, 14)
    macd_h = _macd_hist(cp)
    roc5 = _roc(cp, 5)
    roc20 = _roc(cp, 20)
    p_roc5 = _prev_roc5(cp)
    atr = _atr_val(hp, lp, cp, 14)
    if not atr or atr <= 0: atr = max(abs(price) * 0.01, 0.01)
    slope = _ema20_slope(cp)
    vol_ratio = _num(a.get("vol_ratio"), 0)
    has_volume = vol_ratio > 0
    candle_ratio = a.get("candle_ratio")
    try:
        candle_ratio = float(candle_ratio) if candle_ratio is not None else None
    except (TypeError, ValueError):
        candle_ratio = None
    candle_ok = candle_ratio is not None and candle_ratio <= 0.75
    extension_atr = abs(price - ema20) / atr if atr else 0
    dist_to_sw_low = (price - _swing_low(lp)) / atr if atr else 99
    dist_to_sw_high = (_swing_high(hp) - price) / atr if atr else 99

    bull = 0
    if price > ema20: bull += 10
    if ema20 > ema50: bull += 10
    if slope > 0: bull += 10
    if roc5 > 0: bull += 7
    if roc20 > 0: bull += 7
    if macd_h > 0: bull += 6
    if roc5 > p_roc5: bull += 5
    if 53 <= rsi14 <= 66: bull += 15
    elif (45 <= rsi14 < 47) or (66 < rsi14 <= 72): bull += 8
    elif rsi14 > 72: bull -= 5
    if has_volume:
        if 1.1 <= vol_ratio <= 2.5: bull += 10
        elif vol_ratio > 2.5: bull += 5
        if candle_ok: bull += 5
    else:
        bull += 5
    if 0 <= dist_to_sw_low <= 1: bull += 8
    elif 1 < dist_to_sw_low <= 2: bull += 4
    if extension_atr <= 1.0: bull += 7
    elif extension_atr <= 1.5: bull += 4
    elif extension_atr <= 2.0: bull += 2
    if extension_atr > 2.0: bull -= 10

    bear = 0
    if price < ema20: bear += 10
    if ema20 < ema50: bear += 10
    if slope < 0: bear += 10
    if roc5 < 0: bear += 7
    if roc20 < 0: bear += 7
    if macd_h < 0: bear += 6
    if roc5 < p_roc5: bear += 5
    if 34 <= rsi14 <= 47: bear += 15
    elif (28 <= rsi14 < 34) or (53 < rsi14 <= 55): bear += 8
    elif rsi14 < 28: bear -= 5
    if has_volume:
        if 1.1 <= vol_ratio <= 2.5: bear += 10
        elif vol_ratio > 2.5: bear += 5
        if candle_ok: bear += 5
    else:
        bear += 5
    if 0 <= dist_to_sw_high <= 1: bear += 8
    elif 1 < dist_to_sw_high <= 2: bear += 4
    if extension_atr <= 1.0: bear += 7
    elif extension_atr <= 1.5: bear += 4
    elif extension_atr <= 2.0: bear += 2
    if extension_atr > 2.0: bear -= 10

    bull = max(0, min(100, int(round(bull))))
    bear = max(0, min(100, int(round(bear))))
    tags = []
    if price > ema20: tags.append(("Trend", "MA bull"))
    elif price < ema20: tags.append(("Trend", "MA bear"))
    if has_volume and vol_ratio >= 1.5: tags.append(("Vol", f"{vol_ratio:.1f}×"))
    elif not has_volume: tags.append(("Vol", "neutral"))
    if extension_atr > 2: tags.append(("Ext", "chase"))
    if rsi14 > 72: tags.append(("RSI", "extended"))
    elif rsi14 < 28: tags.append(("RSI", "extended"))
    return {"bull_score": bull, "bear_score": bear, "rsi": rsi14, "roc5": roc5, "roc20": roc20, "ema20_ext": round(extension_atr, 1), "tier_bull": _tier(bull), "tier_bear": _tier(bear), "tags": tags[:3]}


def _tier(score: int) -> str:
    if score >= 90: return "EXTREME"
    if score >= 80: return "STRONG"
    if score >= 65: return "ACTIVE"
    return "WATCH"


def _tier_badge(tier: str) -> tuple:
    if tier == "EXTREME": return ("⚡ EXTREME", "#22c55e", "score-hot")
    if tier == "STRONG":  return ("🦅 STRONG", "#22c55e", "score-hot")
    if tier == "ACTIVE":  return ("👁️ ACTIVE", "#f59e0b", "score-warm")
    return ("📡 WATCH", "#64748b", "score-muted")


# ═══════════════════════════════════════════════════════════════
# HTML Cards — pressure rows, no stop/target/RR
# ═══════════════════════════════════════════════════════════════

def _entry_precision(asset, source=""):
    symbol = str(asset.get("symbol") or "").upper()
    price = _num(asset.get("price"))
    if source == "forex": return 2 if "JPY" in symbol else 4
    return 2 if price >= 1 else 4


def _pick_card(asset: dict, side: str, source: str = "") -> str:
    m = _hawkeye_score(asset)
    bullish = side == "bull"
    direction = "BULL" if bullish else "BEAR"
    score = m["bull_score"] if bullish else m["bear_score"]
    tier = m["tier_bull"] if bullish else m["tier_bear"]
    badge, badge_color, score_class = _tier_badge(tier)
    title = escape(_asset_name(asset))
    symbol = escape(_asset_symbol(asset))
    precision = _entry_precision(asset, source)
    entry = _num(asset.get("price"))
    entry_fmt = f"${entry:,.{precision}f}"
    ext = m.get("ema20_ext", 0)
    motif = "bull pressure" if bullish else "bear pressure"
    if ext > 2: motif += " · chase risk"
    return f"""<div class="signal-row hawk-row">
<div>
<span class="asset-name">{title}</span>
<span class="asset-tag">{direction}</span>
<span class="asset-meta">{source or _asset_group(asset)} · {motif}</span>
<span class="asset-levels">
<span style="color:#bae6fd">📍 {entry_fmt}</span>
<span style="color:#a7f3d0">ROC5 {m.get('roc5',0):+.1f}%</span>
<span style="color:#fbbf24">RSI {m.get('rsi',50)}</span>
<span style="color:#c4b5fd">Ext {ext:.1f} ATR</span>
</span>
</div>
<div style="text-align:right">
<span class="score-pill {score_class}">{score}/100</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">{symbol}</div>
<div style="font-size:.7em;color:{badge_color};margin-top:2px">{badge}</div>
</div>
</div>"""


# ═══════════════════════════════════════════════════════════════
# Public API — momentum_scanner_html / hawk_eye_html
# ═══════════════════════════════════════════════════════════════

def momentum_scanner_html(assets: list, top_n: int = 4, source: str = "") -> str:
    """Hawkeye v3 scanner — quality pressure rows, no TP/SL/RR."""
    if len(assets) < 2:
        return ""
    scored = [(a, _hawkeye_score(a)) for a in assets]
    mixed_pool = [(a, m) for a, m in scored if m["bull_score"] >= 55 and m["bear_score"] >= 55]
    mixed_ids = {id(a) for a, _ in mixed_pool}
    bullish_pool = [(a, m) for a, m in scored if id(a) not in mixed_ids and m["bull_score"] >= 65]
    bearish_pool = [(a, m) for a, m in scored if id(a) not in mixed_ids and m["bear_score"] >= 65]
    bullish = [a for a, _ in sorted(bullish_pool, key=lambda x: x[1]["bull_score"], reverse=True)[:top_n]]
    bearish = [a for a, _ in sorted(bearish_pool, key=lambda x: x[1]["bear_score"], reverse=True)[:top_n]]
    mixed = [a for a, _ in sorted(mixed_pool, key=lambda x: max(x[1]["bull_score"], x[1]["bear_score"]), reverse=True)[:3]]
    strong_bull = sum(1 for _, m in scored if m["bull_score"] >= 80)
    strong_bear = sum(1 for _, m in scored if m["bear_score"] >= 80)
    active_bull = sum(1 for _, m in scored if 65 <= m["bull_score"] < 80)
    active_bear = sum(1 for _, m in scored if 65 <= m["bear_score"] < 80)
    def empty(text: str) -> str:
        return f'<div class="momentum-empty">{escape(text)}</div>'
    bull_html = "".join(_pick_card(a, "bull", source) for a in bullish) or empty("No active bullish pressure")
    bear_html = "".join(_pick_card(a, "bear", source) for a in bearish) or empty("No active bearish pressure")
    mixed_html = ""
    if mixed:
        rows = []
        for a in mixed:
            m = _hawkeye_score(a)
            rows.append(f"<div class='signal-row hawk-row'><div><span class='asset-name'>{escape(_asset_name(a))}</span><span class='asset-tag'>MIXED</span><span class='asset-meta'>{escape(source or _asset_group(a))} · contradictory pressure / volatile tape</span><span class='asset-levels'><span style='color:#bae6fd'>📍 ${_num(a.get('price')):,.2f}</span><span style='color:#22c55e'>Bull {m['bull_score']}</span><span style='color:#ef4444'>Bear {m['bear_score']}</span></span></div><div style='text-align:right'><span class='score-pill score-warm'>{max(m['bull_score'],m['bear_score'])}/100</span><div style='font-size:.7em;color:#f59e0b;margin-top:2px'>⚠️ MIXED / VOLATILE</div></div></div>")
        mixed_html = f"<div class='signal-card mixed-card'><h3>⚠️ Mixed / Volatile ({len(mixed)})</h3>{''.join(rows)}</div>"
    return f"""
<section class="momentum-scanner-v2 scanner hawkeye-scanner" aria-label="Hawkeye v3">
  <style>
    .hawkeye-scanner{{margin:0 0 24px;padding:24px;border:1px solid rgba(56,189,248,.20);border-radius:28px;position:relative;overflow:hidden;text-align:left;background:linear-gradient(135deg,rgba(16,22,34,.92),rgba(18,14,33,.86) 48%,rgba(29,22,10,.76));box-shadow:0 22px 70px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.06)}}
    .hawkeye-scanner:before{{content:"";position:absolute;inset:-1px;background:radial-gradient(circle at 16% 0%,rgba(56,189,248,.18),transparent 35%),radial-gradient(circle at 92% 14%,rgba(245,158,11,.12),transparent 28%);pointer-events:none}}
    .hawkeye-scanner>*{{position:relative}}.scanner-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}}.scanner-head h2{{margin:0;color:var(--atlas-text,var(--text));font-size:1.18rem;font-weight:950;letter-spacing:-.04em}}
    .scanner-head .tier-legend{{display:flex;gap:10px;flex-wrap:wrap;font-size:.74em;color:var(--muted)}}.scanner-head .tier-legend span{{padding:3px 8px;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.04)}}.scanner-board{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
    .signal-card{{border:1px solid var(--atlas-border,var(--border));border-radius:22px;padding:14px;background:rgba(7,9,20,.38);box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}}.mixed-card{{grid-column:1/-1}}.signal-card h3{{margin:0 0 12px;color:var(--atlas-text,var(--text));font-size:.98rem;font-weight:950;letter-spacing:-.025em}}
    .signal-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px;border:1px solid rgba(148,163,184,.16);border-radius:16px;background:rgba(255,255,255,.035);margin-top:9px}}.signal-row:first-of-type{{margin-top:0}}.asset-name{{display:inline;font-weight:900;color:var(--atlas-text,var(--text));line-height:1.15;margin-right:6px}}
    .asset-tag{{display:inline-flex;vertical-align:middle;padding:2px 7px;border-radius:999px;background:rgba(56,189,248,.10);border:1px solid rgba(56,189,248,.22);color:#bae6fd;font-size:.66rem;font-weight:900;text-transform:uppercase}}.asset-meta{{display:block;color:var(--atlas-muted,var(--muted));font-size:.74rem;margin-top:4px;line-height:1.35}}
    .asset-levels{{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px;font-size:.72rem;font-weight:850}}.asset-levels span{{padding:4px 7px;border-radius:999px;background:rgba(15,23,42,.55);border:1px solid rgba(148,163,184,.16)}}.score-pill{{display:inline-flex;align-items:center;justify-content:center;min-width:58px;padding:7px 9px;border-radius:999px;font-weight:950;font-size:.86rem;border:1px solid transparent}}
    .score-hot{{color:#bbf7d0;background:rgba(34,197,94,.13);border-color:rgba(34,197,94,.22)}}.score-risk{{color:#fecaca;background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.22)}}.score-warm{{color:#ffd699;background:rgba(245,158,11,.14);border-color:rgba(245,158,11,.22)}}.score-muted{{color:#cbd5e1;background:rgba(100,116,139,.10);border-color:rgba(100,116,139,.18)}}.momentum-empty{{padding:16px;border:1px dashed var(--atlas-border,var(--border));border-radius:18px;color:var(--atlas-muted,var(--muted));background:rgba(255,255,255,.025)}}
    @media(max-width:860px){{.scanner-head{{display:block}}.scanner-board{{grid-template-columns:1fr}}.mixed-card{{grid-column:auto}}}}@media(max-width:520px){{.hawkeye-scanner{{padding:16px;border-radius:22px}}.signal-row{{display:block}}.signal-row>div:last-child{{text-align:left!important;margin-top:10px}}}}
  </style>
  <div class="scanner-head"><div><h2>🦅 Hawkeye v3</h2></div><div class="tier-legend"><span>⚡ Extreme 90+</span><span>🦅 Strong 80-89</span><span>👁️ Active 65-79</span><span>🟊 {strong_bull+strong_bear} strong · {active_bull+active_bear} active</span></div></div>
  <div class="scanner-board hawk-board"><div class="signal-card"><h3>🚀 Bullish pressure ({len(bullish)})</h3>{bull_html}</div><div class="signal-card"><h3>🐻 Bearish pressure ({len(bearish)})</h3>{bear_html}</div>{mixed_html}</div>
</section>"""


# Backward compat alias — accepts source as kwarg for existing callers
def hawk_eye_html(assets: list, top_n: int = 4, source: str = "") -> str:
    return momentum_scanner_html(assets, top_n, source)


# ═══════════════════════════════════════════════════════════════
# Shared sections — Back link + Unusual Activity Alert
# ═══════════════════════════════════════════════════════════════

def back_to_dashboard_html() -> str:
    """Simple '← Back to Dashboard' link, uniform across all pages."""
    return """
<div style="margin-top:28px;text-align:center">
  <a href="index.html" style="display:inline-block;padding:12px 24px;border:1px solid var(--border);border-radius:12px;color:var(--muted);text-decoration:none;font-size:.88em;font-weight:700;transition:all .15s">← Retour Dashboard</a>
</div>"""


def unusual_activity_html(assets: list) -> str:
    """
    🚨 Unusual Activity Alert — detects extreme readings across all assets.
    Flags: volume spike (vol_ratio > 3x), vertical candle (>0.85), 
           chase (>2.5 ATR), RSI extreme (>78 or <22), volatility spike (>4%).
    """
    alerts = []
    
    for a in assets:
        name = _asset_name(a)
        symbol = _asset_symbol(a)
        vol_ratio = _num(a.get("vol_ratio"), 0)
        candle = _num(a.get("candle_ratio"), 0.3)
        ch = _change_pct(a)
        vol20 = _num(a.get("volatility_20d"), 0)
        
        # Get RSI and extension from Hawkeye scoring
        hk = _hawkeye_score(a)
        rsi = hk["rsi"]
        ext = hk["ema20_ext"]
        
        flags = []
        if vol_ratio > 3.5:
            flags.append(f"Vol {vol_ratio:.1f}× avg")
        if candle > 0.85:
            flags.append("Vertical candle")
        if ext > 2.5:
            flags.append(f"Chase {ext:.1f} ATR")
        if rsi > 78:
            flags.append(f"RSI {rsi} overbought")
        elif rsi < 22:
            flags.append(f"RSI {rsi} oversold")
        if vol20 > 4:
            flags.append(f"Volatility {vol20:.1f}%")
            
        if flags:
            ch_color = "#22c55e" if ch >= 0 else "#ef4444"
            arrow = "▲" if ch >= 0 else "▼"
            alerts.append({
                "name": name, "symbol": symbol,
                "change": ch, "arrow": arrow, "ch_color": ch_color,
                "flags": flags, "rsi": rsi, "ext": ext,
            })
    
    if not alerts:
        return '<div class="unusual-alert" style="margin-top:28px;padding:18px;border:1px solid rgba(34,197,94,.16);border-radius:14px;background:rgba(34,197,94,.04);text-align:center;color:var(--muted);font-size:.88em">✅ No unusual activity detected</div>'
    
    rows = ""
    for a in alerts[:6]:
        flags_html = " · ".join(f'<span style="color:#f59e0b">{f}</span>' for f in a["flags"])
        rows += f"""<div class="alert-row" style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;border:1px solid rgba(245,158,11,.16);border-radius:10px;background:rgba(245,158,11,.04);margin-top:8px">
<div>
<span style="font-weight:800;color:var(--text)">{a['name']}</span>
<span style="color:var(--muted);font-size:.78em;margin-left:6px">{a['symbol']}</span>
</div>
<div style="font-size:.82em;text-align:right">
<div style="color:{a['ch_color']};font-weight:700">{a['arrow']} {a['change']:.1f}%</div>
<div style="color:var(--muted);font-size:.74em;margin-top:2px">{flags_html}</div>
</div>
</div>"""
    
    return f"""
<section class="unusual-section" aria-label="Unusual Activity" style="margin:28px 0 0;padding:24px;border:1px solid rgba(245,158,11,.22);border-radius:22px;background:rgba(245,158,11,.03)">
  <h2 style="margin:0 0 4px;font-size:1.05rem;font-weight:950;color:#f59e0b;letter-spacing:-.025em">🚨 Unusual Activity Alert</h2>
  <p style="color:var(--muted);font-size:.78em;margin:0 0 12px">{len(alerts)} asset{'' if len(alerts)==1 else 's'} flagged — extreme readings</p>
  {rows}
</section>"""


# ═══════════════════════════════════════════════════════════════
# Composite Market Sentiment (unchanged logic, enriched with Hawkeye)
# ═══════════════════════════════════════════════════════════════

def compute_sentiment(assets: list) -> dict:
    """Composite market sentiment from multi-signal analysis."""
    n = len(assets)
    if n == 0:
        return {"direction": "NEUTRAL", "confidence": 0, "score": 0, "signals": {}, "summary": "No data"}

    up = sum(1 for a in assets if _change_pct(a) > 0)
    breadth = (up / n) * 100

    avg_change = sum(_change_pct(a) for a in assets) / n
    momentum_score = max(-100, min(100, avg_change * 20))

    bullish_trend = sum(1 for a in assets if str(a.get("trend", "")).upper() == "BULLISH")
    trend_score = (bullish_trend / n) * 100

    high_vol = sum(1 for a in assets if _num(a.get("vol_ratio"), 1.0) > 1.5)
    vol_conviction = (high_vol / n) * 100

    avg_volatility = sum(_num(a.get("volatility_20d")) for a in assets) / n
    if avg_volatility > 3:       volatility_signal = -20
    elif avg_volatility < 1:     volatility_signal = 10
    else:                        volatility_signal = 0

    raw_score = (
        (breadth - 50) * 0.35 +
        momentum_score * 0.30 +
        (trend_score - 50) * 0.20 +
        (vol_conviction - 15) * 0.10 +
        volatility_signal * 0.05
    )

    if raw_score > 20:          direction = "BULLISH"
    elif raw_score > 7:         direction = "SLIGHTLY BULLISH"
    elif raw_score >= -7:       direction = "NEUTRAL"
    elif raw_score > -20:       direction = "SLIGHTLY BEARISH"
    else:                       direction = "BEARISH"

    signals_list = [breadth, momentum_score + 50, trend_score, vol_conviction]
    sig_std = statistics.stdev(signals_list) if len(signals_list) > 1 else 0
    agreement_bonus = max(0, 30 - sig_std)
    magnitude = abs(raw_score)
    magnitude_score = min(40, magnitude * 1.2)
    confidence = min(95, max(25, magnitude_score + agreement_bonus))

    return {
        "direction": direction,
        "confidence": round(confidence),
        "score": round(raw_score, 1),
        "signals": {
            "breadth": {"value": round(breadth), "label": f"{up}/{n} assets up"},
            "avg_change": {"value": round(avg_change, 2), "label": "Avg change"},
            "trend_alignment": {"value": round(trend_score), "label": f"{bullish_trend}/{n} bullish MA"},
            "volume_conviction": {"value": round(vol_conviction), "label": f"{high_vol}/{n} elevated vol"},
            "volatility_20d": {"value": round(avg_volatility, 1), "label": "Avg volatility %"},
        },
        "summary": f"{direction} ({round(confidence)}% confidence) — {up}/{n} assets up, "
                   f"{avg_change:+.1f}% avg, {bullish_trend}/{n} bullish trend"
    }
