"""
🦅 Hawkeye V4 — Market pressure radar core.

Doctrine:
- Not a trade placement tool.
- No automated trade levels, no execution promise, no placement language.
- Regime first, pressure second, signal family third, score last.
"""

from __future__ import annotations

import math
from typing import Any

RECOGNIZED_SOURCES = {"crypto", "commodities", "indices", "forex", "actions", "stocks", "etf"}
VOLUME_SOURCES = {"crypto", "actions", "stocks", "etf"}


def num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_price(asset: dict) -> float:
    return num(asset.get("price") or asset.get("current_price") or asset.get("close"), 0.0)


def series(asset: dict, key: str) -> list[float]:
    out = []
    for x in asset.get(key) or []:
        try:
            if x is not None:
                out.append(float(x))
        except (TypeError, ValueError):
            pass
    return out


def ema(data: list[float], period: int) -> float:
    if not data:
        return 0.0
    if len(data) < period:
        return data[-1]
    k = 2 / (period + 1)
    val = sum(data[:period]) / period
    for x in data[period:]:
        val = x * k + val * (1 - k)
    return val


def rsi(prices: list[float], period: int = 14) -> int:
    if len(prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(-period, 0):
        ch = prices[i] - prices[i - 1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    return round(100 - 100 / (1 + avg_gain / avg_loss))


def roc(prices: list[float], period: int) -> float:
    if len(prices) < period + 1:
        return 0.0
    old = prices[-period - 1]
    return (prices[-1] - old) / old * 100 if old else 0.0


def macd_hist(prices: list[float]) -> float:
    if len(prices) < 26:
        return 0.0
    e12 = ema(prices, 12)
    e26 = ema(prices, 26)
    return ((e12 - e26) / e26 * 100) if e26 else 0.0


def true_ranges(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    n = min(len(highs), len(lows), len(closes))
    if n < 2:
        return []
    h, l, c = highs[-n:], lows[-n:], closes[-n:]
    out = []
    for i in range(1, n):
        out.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return out


def atr_val(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    trs = true_ranges(highs, lows, closes)
    if len(trs) < period:
        return 0.0
    return sum(trs[-period:]) / period


def atr_percentile(highs: list[float], lows: list[float], closes: list[float], period: int = 14, lookback: int = 80) -> float:
    trs = true_ranges(highs, lows, closes)
    if len(trs) < period + 5:
        return 50.0
    atrs = [sum(trs[i - period:i]) / period for i in range(period, len(trs) + 1)]
    current = atrs[-1]
    sample = atrs[-lookback:]
    if not sample:
        return 50.0
    below = sum(1 for x in sample if x <= current)
    return round(below / len(sample) * 100, 1)


def slope_pct(closes: list[float], period: int, bars_back: int = 5) -> float:
    if len(closes) < period + bars_back:
        return 0.0
    now = ema(closes, period)
    prev = ema(closes[:-bars_back], period)
    return (now - prev) / prev * 100 if prev else 0.0


def asset_source(asset: dict) -> str:
    src = str(asset.get("source") or "").lower()
    return "actions" if src == "stocks" else src


def asset_name(asset: dict) -> str:
    if asset_source(asset) == "forex":
        sym = str(asset.get("symbol") or "").upper().replace("=X", "")
        if sym:
            return sym
    return str(asset.get("name") or asset.get("symbol") or asset.get("base") or "Asset")


def asset_symbol(asset: dict) -> str:
    sym = asset.get("symbol")
    if sym:
        return str(sym)
    if asset.get("base") and asset.get("quote"):
        return f"{asset['base']}{asset['quote']}"
    return asset_name(asset)


def data_quality(asset: dict) -> dict:
    src = asset_source(asset)
    price = safe_price(asset)
    cp = series(asset, "_close_prices")
    hp = series(asset, "_high_prices")
    lp = series(asset, "_low_prices")
    issues = []
    if src not in RECOGNIZED_SOURCES:
        issues.append("unrecognized class")
    if price <= 0:
        issues.append("invalid price")
    if len(cp) < 30:
        issues.append("short history")
    if not hp or not lp or len(hp) < min(20, len(cp)) or len(lp) < min(20, len(cp)):
        issues.append("incomplete OHLC")
    atr = atr_val(hp if hp else cp, lp if lp else cp, cp, 14) if cp else 0.0
    if atr <= 0:
        issues.append("ATR unavailable")
    volume_reliable = src in VOLUME_SOURCES and num(asset.get("vol_ratio"), 0) > 0
    return {
        "ok": not issues,
        "degraded": bool(issues),
        "issues": issues,
        "volume_reliable": volume_reliable,
        "atr": atr,
    }


def _score_norm_positive(x: float, max_points: int) -> int:
    if x >= 2.0:
        return max_points
    if x >= 1.0:
        return round(max_points * 0.75)
    if x >= 0.5:
        return round(max_points * 0.45)
    return 0


def _score_norm_negative(x: float, max_points: int) -> int:
    return _score_norm_positive(-x, max_points)


def classify_regime(m: dict) -> str:
    abs_n5 = abs(m["nroc5"])
    abs_n20 = abs(m["nroc20"])
    flat_emas = abs(m["ema20_slope"]) < 0.08 and abs(m["ema50_slope"]) < 0.05
    strong_candle = m["candle_ratio"] is not None and m["candle_ratio"] >= 0.72
    if abs_n5 > 2.5 or m["extension_atr"] > 2.5 or (m["atr_percentile"] > 90 and strong_candle):
        return "shock"
    if m["atr_percentile"] < 25 and abs_n5 < 0.5 and abs_n20 < 0.8 and flat_emas:
        return "compression"
    if (m["price"] > m["ema20"] and m["ema20"] > m["ema50"] and m["ema20_slope"] > 0 and m["ema50_slope"] >= 0 and m["nroc20"] > 0 and m["extension_atr"] <= 2):
        return "uptrend"
    if (m["price"] < m["ema20"] and m["ema20"] < m["ema50"] and m["ema20_slope"] < 0 and m["ema50_slope"] <= 0 and m["nroc20"] < 0 and m["extension_atr"] <= 2):
        return "downtrend"
    mixed = (
        (m["price"] > m["ema20"] and m["ema20"] < m["ema50"]) or
        (m["price"] < m["ema20"] and m["ema20"] > m["ema50"]) or
        (m["nroc5"] * m["nroc20"] < 0) or
        (m["macd_h"] > 0 and m["nroc20"] < 0) or
        (m["macd_h"] < 0 and m["nroc20"] > 0)
    )
    if mixed:
        return "mixed"
    if flat_emas and abs_n20 < 0.8 and 25 <= m["atr_percentile"] <= 75:
        return "range"
    return "range"


def signal_family(regime: str, direction: str, m: dict, net: int) -> str:
    if regime == "shock":
        return "shock / extended"
    if regime == "compression":
        return "compression watch"
    if regime == "mixed" or abs(net) < 15:
        return "mixed / no edge"
    if regime == "range":
        if m["rsi"] >= 65:
            return "overbought pullback watch"
        if m["rsi"] <= 35:
            return "oversold rebound watch"
        return "range pressure"
    if direction == "bullish":
        if regime == "uptrend":
            return "bullish continuation" if m["extension_atr"] <= 1.5 else "breakout pressure"
        return "oversold rebound watch" if m["rsi"] < 35 else "bullish pullback watch"
    if regime == "downtrend":
        return "bearish continuation" if m["extension_atr"] <= 1.5 else "breakdown pressure"
    return "overbought pullback watch" if m["rsi"] > 65 else "bearish pullback watch"


def tier(score: int) -> tuple[str, str, str]:
    if score >= 90:
        return "EXTREME", "⚡ Extreme pressure", "#22c55e"
    if score >= 75:
        return "STRONG", "🦅 Strong pressure", "#22c55e"
    if score >= 60:
        return "ACTIVE", "👁️ Active pressure", "#f59e0b"
    if score >= 40:
        return "WATCH", "📡 Watch", "#94a3b8"
    return "WEAK", "⚪ Weak", "#64748b"


def _participation_score(asset: dict, source: str, m: dict) -> tuple[int, str]:
    vol = num(asset.get("vol_ratio"), 0)
    candle = m["candle_ratio"]
    candle_ok = candle is not None and candle <= 0.75
    if source in VOLUME_SOURCES and vol > 0:
        pts = 0
        if 1.1 <= vol <= 2.5:
            pts += 10
        elif vol > 2.5:
            pts += 5
        elif vol >= 0.8:
            pts += 4
        if candle_ok:
            pts += 5
        return min(15, pts), f"Vol {vol:.1f}×"
    # Forex/indices/no reliable volume: use range expansion, never fake a volume ratio.
    pts = 0
    if 45 <= m["atr_percentile"] <= 85:
        pts += 8
    elif 25 <= m["atr_percentile"] < 45:
        pts += 5
    elif m["atr_percentile"] > 85:
        pts += 4
    if candle_ok:
        pts += 4
    label = f"Range pct {m['atr_percentile']:.0f}"
    return min(12, pts), label


def _relative_score(asset: dict, direction: str) -> tuple[int, str | None]:
    # Optional only. No placeholder points when benchmark fields are unavailable.
    keys = ["relative_strength", "rel_strength", "benchmark_rel", "vs_benchmark_pct"]
    val = None
    for k in keys:
        if k in asset and asset[k] is not None:
            val = num(asset[k], None)
            break
    if val is None:
        return 0, None
    if direction == "bullish":
        if val > 2: return 15, f"Rel +{val:.1f}"
        if val > 0: return 8, f"Rel +{val:.1f}"
    else:
        if val < -2: return 15, f"Rel {val:.1f}"
        if val < 0: return 8, f"Rel {val:.1f}"
    return 0, f"Rel {val:.1f}"


def analyze_asset(asset: dict) -> dict:
    source = asset_source(asset)
    q = data_quality(asset)
    cp = series(asset, "_close_prices")
    hp = series(asset, "_high_prices") or cp[:]
    lp = series(asset, "_low_prices") or cp[:]
    price = cp[-1] if cp else safe_price(asset)
    if price <= 0:
        price = safe_price(asset)
    if len(cp) < 10 and price > 0:
        cp = [price] * 30
        hp = cp[:]
        lp = cp[:]
    atr = q["atr"] or atr_val(hp, lp, cp, 14) or max(abs(price) * 0.01, 0.01)
    atr_pct = atr / price * 100 if price else 0.0
    ema20 = ema(cp, 20)
    ema50 = ema(cp, 50) if len(cp) >= 50 else ema(cp, max(2, min(50, len(cp))))
    e20s = slope_pct(cp, 20)
    e50s = slope_pct(cp, 50) if len(cp) >= 55 else slope_pct(cp, max(10, min(30, len(cp) - 5)))
    roc5 = roc(cp, 5)
    roc20 = roc(cp, 20)
    denom5 = atr_pct * math.sqrt(5) if atr_pct else 1.0
    denom20 = atr_pct * math.sqrt(20) if atr_pct else 1.0
    nroc5 = roc5 / denom5 if denom5 else 0.0
    nroc20 = roc20 / denom20 if denom20 else 0.0
    rsi14 = rsi(cp, 14)
    macd_h = macd_hist(cp)
    ext = abs(price - ema20) / atr if atr else 0.0
    atrp = atr_percentile(hp, lp, cp)
    candle = asset.get("candle_ratio")
    try:
        candle = float(candle) if candle is not None else None
    except (TypeError, ValueError):
        candle = None
    m = {
        "price": price, "ema20": ema20, "ema50": ema50,
        "ema20_slope": e20s, "ema50_slope": e50s,
        "atr": atr, "atr_pct": atr_pct, "atr_percentile": atrp,
        "roc5": roc5, "roc20": roc20, "nroc5": nroc5, "nroc20": nroc20,
        "rsi": rsi14, "macd_h": macd_h, "extension_atr": ext,
        "candle_ratio": candle,
    }
    regime = classify_regime(m)

    bull = 0
    # Trend /25
    bull += 7 if price > ema20 else 0
    bull += 7 if ema20 > ema50 else 0
    bull += 6 if e20s > 0 else 0
    bull += 5 if e50s >= 0 else 0
    # Momentum /20
    bull += _score_norm_positive(nroc5, 8)
    bull += _score_norm_positive(nroc20, 8)
    bull += 4 if macd_h > 0 else 0
    # RSI /10
    if 55 <= rsi14 <= 65: bull += 10
    elif 50 <= rsi14 < 55: bull += 5
    elif 65 < rsi14 <= 72: bull += 6
    elif rsi14 > 72: bull -= 6
    elif rsi14 < 35: bull = min(bull, 45)
    # Participation /15
    part_pts, part_label = _participation_score(asset, source, m)
    bull += part_pts
    # Location /15
    if ext <= 1.5: bull += 12
    elif ext <= 2.0: bull += 5
    elif ext > 2.0: bull -= 12
    if price >= ema20 and ext <= 1.0: bull += 3
    # Relative /15 optional
    rel_bull, rel_label = _relative_score(asset, "bullish")
    bull += rel_bull

    bear = 0
    bear += 7 if price < ema20 else 0
    bear += 7 if ema20 < ema50 else 0
    bear += 6 if e20s < 0 else 0
    bear += 5 if e50s <= 0 else 0
    bear += _score_norm_negative(nroc5, 8)
    bear += _score_norm_negative(nroc20, 8)
    bear += 4 if macd_h < 0 else 0
    if 35 <= rsi14 <= 45: bear += 10
    elif 45 < rsi14 <= 50: bear += 5
    elif 28 <= rsi14 < 35: bear += 6
    elif rsi14 < 28: bear -= 6
    elif rsi14 > 65: bear = min(bear, 45)
    bear += part_pts
    if ext <= 1.5: bear += 12
    elif ext <= 2.0: bear += 5
    elif ext > 2.0: bear -= 12
    if price <= ema20 and ext <= 1.0: bear += 3
    rel_bear, rel_label_bear = _relative_score(asset, "bearish")
    bear += rel_bear

    bull = max(0, min(100, int(round(bull))))
    bear = max(0, min(100, int(round(bear))))
    net = bull - bear
    direction = "mixed"
    if net >= 15:
        direction = "bullish"
    elif net <= -15:
        direction = "bearish"
    raw_final = max(bull, bear) if direction != "mixed" else max(bull, bear, 40)

    # Caps: regime first, contradiction second, data quality last.
    cap = 100
    if regime in {"mixed", "compression"}: cap = min(cap, 64)
    if regime == "range": cap = min(cap, 74)
    if regime == "shock": cap = min(cap, 84)
    if direction == "bullish" and regime == "downtrend": cap = min(cap, 64)
    if direction == "bearish" and regime == "uptrend": cap = min(cap, 64)
    if abs(net) < 15:
        cap = min(cap, 64)
    elif abs(net) < 25:
        cap = min(cap, 84)
    if q["degraded"]:
        cap = min(cap, 59)
    if raw_final >= 90:
        clear_regime = (direction == "bullish" and regime == "uptrend") or (direction == "bearish" and regime == "downtrend")
        if not (clear_regime and abs(net) >= 35 and ext <= 1.5 and not q["degraded"]):
            cap = min(cap, 89)
    final = min(raw_final, cap)
    if direction == "mixed":
        family = signal_family(regime, direction, m, net)
    else:
        family = signal_family(regime, direction, m, net)
    t, label, color = tier(final)
    if q["degraded"]:
        family = "degraded / unavailable"
        label = "Data degraded"
        color = "#94a3b8"
        t = "DEGRADED"
    return {
        "name": asset_name(asset),
        "symbol": asset_symbol(asset),
        "source": source,
        "data_quality": q,
        "regime": regime,
        "signal_family": family,
        "bull_pressure": bull,
        "bear_pressure": bear,
        "net_pressure": net,
        "direction": direction,
        "score": final,
        "tier": t,
        "label": label,
        "color": color,
        "price": price,
        "price_label": format_price(asset, price, source),
        "rsi": rsi14,
        "roc5": roc5,
        "roc20": roc20,
        "nroc5": nroc5,
        "nroc20": nroc20,
        "atr_pct": atr_pct,
        "atr_percentile": atrp,
        "extension_atr": ext,
        "participation_label": part_label,
        "relative_label": rel_label if direction == "bullish" else rel_label_bear,
    }


def format_price(asset: dict, price: float, source: str | None = None) -> str:
    source = source or asset_source(asset)
    symbol = str(asset.get("symbol") or "").upper()
    currency = str(asset.get("currency") or "USD").upper()
    if source == "forex":
        precision = 2 if "JPY" in symbol else 4
        return f"{price:,.{precision}f}"
    if source == "indices":
        return f"{price:,.2f} pts"
    prefix = "€" if currency == "EUR" else "$" if currency in {"USD", "USDT", "USDC"} else f"{currency} " if currency else ""
    if source == "commodities":
        unit = asset.get("unit") or asset.get("contract_unit") or "unit"
        return f"{prefix}{price:,.2f}/{unit}"
    precision = 2 if price >= 1 else 4
    return f"{prefix}{price:,.{precision}f}"


def analyze_assets(assets: list[dict]) -> list[dict]:
    out = []
    for a in assets:
        analysis = analyze_asset(a)
        a.update({
            "bull_score": analysis["bull_pressure"],
            "bear_score": analysis["bear_pressure"],
            "pressure_score": analysis["score"],
            "pressure_direction": analysis["direction"],
            "pressure_regime": analysis["regime"],
            "signal_family": analysis["signal_family"],
            "_rsi": analysis["rsi"],
            "_roc5": analysis["roc5"],
            "_roc20": analysis["roc20"],
            "_nroc5": analysis["nroc5"],
            "_nroc20": analysis["nroc20"],
            "_extension_atr": round(analysis["extension_atr"], 2),
            "_atr_pct": round(analysis["atr_pct"], 2),
            "_atr_percentile": analysis["atr_percentile"],
        })
        out.append(analysis)
    return out
