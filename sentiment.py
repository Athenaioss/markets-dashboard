"""
🦅 Hawkeye v2 Sentiment Engine — True /100 Directional Scoring
Used by all Atlas Nexus pipelines (crypto, commodities, indices, forex, actions, etf).

Trend 30 · Momentum 25 · RSI 15 · Volume 15 · Structure 15
Chase penalty: extension > 2 ATR → -10
Tiers: 80-100 Strong · 65-79 Watchlist · <65 Ignored
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
# 🦅 Hawkeye v2 — True /100 Scoring
# ═══════════════════════════════════════════════════════════════

def _hawkeye_score(a: dict) -> dict:
    """
    Compute Hawkeye v2 directional score (0-100) for a single asset.
    Returns bull_score, bear_score, and metadata for display.
    """
    cp = a.get("_close_prices", [])
    hp = a.get("_high_prices", [])
    lp = a.get("_low_prices", [])

    if not cp or len(cp) < 10:
        # Fallback: minimal score from summary fields
        trend = str(a.get("trend", "NEUTRAL")).upper()
        ch = _change_pct(a)
        bull = 65 if trend == "BULLISH" else 50 if ch > 0 else 30
        bear = 65 if trend == "BEARISH" else 50 if ch < 0 else 30
        return {
            "bull_score": bull, "bear_score": bear,
            "rsi": 50, "roc5": ch, "ema20_ext": 0,
            "tier_bull": "WATCHLIST", "tier_bear": "WATCHLIST",
            "tags": [("Trend", trend.title())],
        }

    if not hp: hp = [a.get("price", 1)] * 20
    if not lp: lp = [a.get("price", 1)] * 20

    price = cp[-1] if cp else a.get("price", 1)
    ema20 = _ema(cp, 20)
    ema50 = _ema(cp, min(50, len(cp)))
    rsi14 = _rsi(cp, 14)
    macd_h = _macd_hist(cp)
    roc5 = _roc(cp, 5)
    roc20 = _roc(cp, 20)
    atr = _atr_val(hp, lp, cp, 14)
    slope = _ema20_slope(cp)
    p_roc5 = _prev_roc5(cp)
    vol_ratio = _num(a.get("vol_ratio"), 0)
    has_volume = bool(vol_ratio and vol_ratio > 0)
    candle_ratio = a.get("candle_ratio")
    extension_atr = abs(price - ema20) / atr if atr > 0 else 0

    # ═══ BULL SCORE ═══
    bull = 0
    # Trend (30)
    if price > ema20:   bull += 10
    if ema20 > ema50:   bull += 10
    if slope > 0:       bull += 10
    # Momentum (25)
    if roc5 > 0:        bull += 7
    if roc20 > 0:       bull += 7
    if macd_h > 0:      bull += 6
    if roc5 > p_roc5:   bull += 5
    # RSI (15)
    if 52 <= rsi14 <= 66:        bull += 15
    elif (45 <= rsi14 < 52) or (66 < rsi14 <= 72): bull += 8
    # Volume (15)
    if has_volume:
        if 1.1 <= vol_ratio <= 2.5:   bull += 10
        elif vol_ratio > 2.5:         bull += 5
        if candle_ratio is not None and candle_ratio < 0.75: bull += 5
        elif candle_ratio is None:    bull += 3
    else:
        bull += 7
    # Structure (15)
    if atr > 0 and len(cp) >= 20: bull += 8
    if extension_atr <= 1.5:      bull += 7
    elif extension_atr <= 2.0:    bull += 3
    if extension_atr > 2.0:       bull -= 10
    bull = max(0, min(100, bull))

    # ═══ BEAR SCORE ═══
    bear = 0
    if price < ema20:   bear += 10
    if ema20 < ema50:   bear += 10
    if slope < 0:       bear += 10
    if roc5 < 0:        bear += 7
    if roc20 < 0:       bear += 7
    if macd_h < 0:      bear += 6
    if roc5 < p_roc5:   bear += 5
    if 34 <= rsi14 <= 48:        bear += 15
    elif (28 <= rsi14 < 34) or (48 < rsi14 <= 55): bear += 8
    if has_volume:
        if 1.1 <= vol_ratio <= 2.5:   bear += 10
        elif vol_ratio > 2.5:         bear += 5
        if candle_ratio is not None and candle_ratio < 0.75: bear += 5
        elif candle_ratio is None:    bear += 3
    else:
        bear += 7
    if atr > 0 and len(cp) >= 20: bear += 8
    if extension_atr <= 1.5:      bear += 7
    elif extension_atr <= 2.0:    bear += 3
    if extension_atr > 2.0:       bear -= 10
    bear = max(0, min(100, bear))

    # Tiers
    def _tier(s):
        if s >= 80: return "STRONG"
        if s >= 65: return "WATCHLIST"
        return "IGNORE"

    # Tags for display
    tags = []
    if price > ema20:   tags.append(("Trend", "MA bull"))
    elif price < ema20: tags.append(("Trend", "MA bear"))
    if has_volume:
        if vol_ratio >= 1.5: tags.append(("Vol", f"{vol_ratio:.1f}×"))
    else:
        tags.append(("Vol", "fx"))
    if extension_atr > 2.0: tags.append(("Ext", "chase"))
    if rsi14 > 70:     tags.append(("RSI", "overbought"))
    elif rsi14 < 30:   tags.append(("RSI", "oversold"))

    return {
        "bull_score": bull,
        "bear_score": bear,
        "rsi": rsi14,
        "roc5": roc5,
        "ema20_ext": round(extension_atr, 1),
        "tier_bull": _tier(bull),
        "tier_bear": _tier(bear),
        "tags": tags[:3],
    }


def _tier_badge(tier: str) -> tuple:
    if tier == "STRONG":    return ("🦅 STRONG", "#22c55e", "score-hot")
    if tier == "WATCHLIST": return ("👁️ WATCH", "#f59e0b", "score-warm")
    return ("⏳ IGNORE", "#64748b", "score-muted")


# ═══════════════════════════════════════════════════════════════
# Trade levels — same as scanner_generator.py contextual_levels
# ═══════════════════════════════════════════════════════════════

def _source_profile(source="", symbol=""):
    symbol = (symbol or "").upper()
    if source == "forex":
        return {"decimals": 2 if "JPY" in symbol else 4, "stop_atr": 1.15, "target_rr": 1.8, "min_risk_pct": 0.25, "max_risk_pct": 1.20}
    if source == "crypto":
        return {"decimals": 2, "stop_atr": 1.8, "target_rr": 1.8, "min_risk_pct": 2.00, "max_risk_pct": 12.0}
    if source in ("actions", "stocks", "etf"):
        return {"decimals": 2, "stop_atr": 1.25, "target_rr": 1.7, "min_risk_pct": 0.80, "max_risk_pct": 6.00}
    if source == "indices":
        return {"decimals": 2, "stop_atr": 1.20, "target_rr": 1.7, "min_risk_pct": 0.60, "max_risk_pct": 5.00}
    if source == "commodities":
        return {"decimals": 2, "stop_atr": 1.15, "target_rr": 1.6, "min_risk_pct": 0.70, "max_risk_pct": 5.00}
    return {"decimals": 2, "stop_atr": 1.30, "target_rr": 1.7, "min_risk_pct": 0.80, "max_risk_pct": 6.00}

def _swing_low(lows, window=10):
    if not lows or len(lows) < window: return min(lows) if lows else 0
    return min(lows[-window:])

def _swing_high(highs, window=10):
    if not highs or len(highs) < window: return max(highs) if highs else 0
    return max(highs[-window:])

def _trade_levels(asset, direction, source=""):
    """Return entry, stop, target, RR for display ticket."""
    entry = _num(asset.get("price"))
    cp = asset.get("_close_prices", [])
    hp = asset.get("_high_prices", [])
    lp = asset.get("_low_prices", [])
    if not cp: cp = [entry] * 20
    if not hp: hp = [entry] * 20
    if not lp: lp = [entry] * 20
    
    atr = _atr_val(hp, lp, cp, 14)
    if not entry or not atr or atr <= 0:
        return None
    
    profile = _source_profile(source, asset.get("symbol", ""))
    atr_risk = atr * profile["stop_atr"]
    min_risk = entry * profile["min_risk_pct"] / 100
    max_risk = entry * profile["max_risk_pct"] / 100
    risk = min(max(atr_risk, min_risk), max_risk)
    
    if direction == "LONG":
        structure_stop = _swing_low(lp) - atr * 0.15
        structure_risk = entry - structure_stop
        if min_risk <= structure_risk <= max_risk:
            risk = max(risk, structure_risk)
        stop = entry - risk
        tp = entry + risk * profile["target_rr"]
        rr = round((tp - entry) / risk, 1) if risk > 0 else 0
        tp_pct = round((tp - entry) / entry * 100, 1)
    else:
        structure_stop = _swing_high(hp) + atr * 0.15
        structure_risk = structure_stop - entry
        if min_risk <= structure_risk <= max_risk:
            risk = max(risk, structure_risk)
        stop = entry + risk
        tp = entry - risk * profile["target_rr"]
        rr = round((entry - tp) / risk, 1) if risk > 0 else 0
        tp_pct = round((entry - tp) / entry * 100, 1)
    
    return {
        "entry": round(entry, profile["decimals"]),
        "stop": round(stop, profile["decimals"]),
        "tp": round(tp, profile["decimals"]),
        "rr": rr,
        "risk_pct": round(risk / entry * 100, 2),
        "tp_pct": tp_pct,
        "precision": profile["decimals"],
    }


# ═══════════════════════════════════════════════════════════════
# HTML Cards — Ticket format (entry, stop, target, RR)
# ═══════════════════════════════════════════════════════════════

def _pick_card(asset: dict, side: str, source: str = "") -> str:
    m = _hawkeye_score(asset)
    bullish = side == "bull"
    direction = "LONG" if bullish else "SHORT"
    score = m["bull_score"] if bullish else m["bear_score"]
    tier = m["tier_bull"] if bullish else m["tier_bear"]
    badge, badge_color, score_class = _tier_badge(tier)
    
    levels = _trade_levels(asset, direction, source)
    
    title = escape(_asset_name(asset))
    symbol = escape(_asset_symbol(asset))
    
    if levels:
        precision = levels["precision"]
        entry_fmt = f"${levels['entry']:,.{precision}f}"
        stop_fmt = f"${levels['stop']:,.{precision}f}"
        tp_fmt = f"${levels['tp']:,.{precision}f}"
        rr_str = f"RR {levels['rr']}:1"
        risk_str = f"−{levels['risk_pct']}%"
    else:
        entry_fmt = f"${asset.get('price',0):,.2f}"
        stop_fmt = "—"
        tp_fmt = "—"
        rr_str = ""
        risk_str = ""
    
    return f"""<div class="signal-row hawk-row">
<div>
<span class="asset-name">{title}</span>
<span class="asset-tag">{direction}</span>
<span class="asset-meta">{source or _asset_group(asset)} · {badge.strip('🦅👁️⏳ ')}</span>
<span class="asset-levels">
<span style="color:#bae6fd">🎟️ {entry_fmt}</span>
<span style="color:#ef4444">🛑 {stop_fmt}</span>
<span style="color:#22c55e">🎯 {tp_fmt}</span>
</span>
</div>
<div style="text-align:right">
<span class="score-pill {score_class}">{score}</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">{rr_str} {risk_str}</div>
<div style="font-size:.7em;color:{badge_color};margin-top:2px">{badge}</div>
</div>
</div>"""


# ═══════════════════════════════════════════════════════════════
# Public API — momentum_scanner_html / hawk_eye_html
# ═══════════════════════════════════════════════════════════════

def momentum_scanner_html(assets: list, top_n: int = 4, source: str = "") -> str:
    """Hawkeye v2 scanner — identical to main dashboard format with entry/stop/target."""
    if len(assets) < 2:
        return ""

    scored = [(a, _hawkeye_score(a)) for a in assets]

    bullish_pool = [(a, m) for a, m in scored if m["bull_score"] >= 65]
    bearish_pool = [(a, m) for a, m in scored if m["bear_score"] >= 65]

    bullish = [a for a, _ in sorted(bullish_pool, key=lambda x: x[1]["bull_score"], reverse=True)[:top_n]]
    bearish = [a for a, _ in sorted(bearish_pool, key=lambda x: x[1]["bear_score"], reverse=True)[:top_n]]

    strong_bull = sum(1 for _, m in scored if m["bull_score"] >= 80)
    strong_bear = sum(1 for _, m in scored if m["bear_score"] >= 80)
    watch_bull = sum(1 for _, m in scored if 65 <= m["bull_score"] < 80)
    watch_bear = sum(1 for _, m in scored if 65 <= m["bear_score"] < 80)

    def empty(text: str) -> str:
        return f'<div class="momentum-empty">{escape(text)}</div>'

    bull_html = "".join(_pick_card(a, "bull", source) for a in bullish) or empty("No Strong or Watchlist bullish signal")
    bear_html = "".join(_pick_card(a, "bear", source) for a in bearish) or empty("No Strong or Watchlist bearish signal")

    return f"""
<section class="momentum-scanner-v2 scanner hawkeye-scanner" aria-label="Hawkeye v2">
  <style>
    .hawkeye-scanner{{margin:0 0 24px;padding:24px;border:1px solid rgba(56,189,248,.20);border-radius:28px;position:relative;overflow:hidden;text-align:left;background:linear-gradient(135deg,rgba(16,22,34,.92),rgba(18,14,33,.86) 48%,rgba(29,22,10,.76));box-shadow:0 22px 70px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.06)}}
    .hawkeye-scanner:before{{content:"";position:absolute;inset:-1px;background:radial-gradient(circle at 16% 0%,rgba(56,189,248,.18),transparent 35%),radial-gradient(circle at 92% 14%,rgba(245,158,11,.12),transparent 28%);pointer-events:none}}
    .hawkeye-scanner>*{{position:relative}}
    .scanner-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}}
    .scanner-head h2{{margin:0;color:var(--atlas-text,var(--text));font-size:1.18rem;font-weight:950;letter-spacing:-.04em}}
    .scanner-head .tier-legend{{display:flex;gap:10px;flex-wrap:wrap;font-size:.74em;color:var(--muted)}}
    .scanner-head .tier-legend span{{padding:3px 8px;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.04)}}
    .scanner-board{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
    .signal-card{{border:1px solid var(--atlas-border,var(--border));border-radius:22px;padding:14px;background:rgba(7,9,20,.38);box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}}
    .signal-card h3{{margin:0 0 12px;color:var(--atlas-text,var(--text));font-size:.98rem;font-weight:950;letter-spacing:-.025em}}
    .signal-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px;border:1px solid rgba(148,163,184,.16);border-radius:16px;background:rgba(255,255,255,.035);margin-top:9px}}
    .signal-row:first-of-type{{margin-top:0}}
    .asset-name{{display:inline;font-weight:900;color:var(--atlas-text,var(--text));line-height:1.15;margin-right:6px}}
    .asset-tag{{display:inline-flex;vertical-align:middle;padding:2px 7px;border-radius:999px;background:rgba(56,189,248,.10);border:1px solid rgba(56,189,248,.22);color:#bae6fd;font-size:.66rem;font-weight:900;text-transform:uppercase}}
    .asset-meta{{display:block;color:var(--atlas-muted,var(--muted));font-size:.74rem;margin-top:4px;line-height:1.35}}
    .asset-levels{{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px;font-size:.72rem;font-weight:850}}
    .asset-levels span{{padding:4px 7px;border-radius:999px;background:rgba(15,23,42,.55);border:1px solid rgba(148,163,184,.16)}}
    .score-pill{{display:inline-flex;align-items:center;justify-content:center;min-width:48px;padding:7px 9px;border-radius:999px;font-weight:950;font-size:.86rem;border:1px solid transparent}}
    .score-hot{{color:#bbf7d0;background:rgba(34,197,94,.13);border-color:rgba(34,197,94,.22)}}
    .score-risk{{color:#fecaca;background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.22)}}
    .score-warm{{color:#ffd699;background:rgba(245,158,11,.14);border-color:rgba(245,158,11,.22)}}
    .score-muted{{color:#cbd5e1;background:rgba(100,116,139,.10);border-color:rgba(100,116,139,.18)}}
    .momentum-empty{{padding:16px;border:1px dashed var(--atlas-border,var(--border));border-radius:18px;color:var(--atlas-muted,var(--muted));background:rgba(255,255,255,.025)}}
    @media(max-width:860px){{.scanner-head{{display:block}}.scanner-board{{grid-template-columns:1fr}}}}
    @media(max-width:520px){{.hawkeye-scanner{{padding:16px;border-radius:22px}}.signal-row{{display:block}}.signal-row>div:last-child{{text-align:left!important;margin-top:10px}}}}
  </style>
  <div class="scanner-head">
    <div><h2>🦅 Hawkeye v2</h2></div>
    <div class="tier-legend">
      <span>🦅 Strong 80+</span><span>👁️ Watch 65-79</span><span>🟊 {strong_bull+strong_bear} strong · {watch_bull+watch_bear} watch</span>
    </div>
  </div>
  <div class="scanner-board hawk-board">
    <div class="signal-card"><h3>🚀 Bullish setups ({len(bullish)})</h3>{bull_html}</div>
    <div class="signal-card"><h3>🐻 Bearish setups ({len(bearish)})</h3>{bear_html}</div>
  </div>
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
