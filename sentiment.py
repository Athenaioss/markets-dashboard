"""
Sentiment engine — composite market regime detection + Hawk Eye picks
Used by all Atlas Nexus pipelines (crypto, commodities, indices, forex, actions, etf)
"""

def hawk_eye_html(assets: list, top_n: int = 3) -> str:
    """
    Generate Hawk Eye HTML block showing top confidence bullish & bearish picks.
    Score = |change_pct| + trend bonus (BULLISH: +2, BEARISH: +2, NEUTRAL: 0)
    """
    if len(assets) < 2:
        return ""
    
    def pick_score(a):
        ch = abs(a.get("change_pct", 0))
        trend = a.get("trend", "NEUTRAL")
        bonus = 2 if trend in ("BULLISH", "BEARISH") else 0
        return ch + bonus
    
    bullish = sorted(
        [a for a in assets if a.get("change_pct", 0) > 0],
        key=lambda a: a.get("change_pct", 0), reverse=True
    )[:top_n]
    
    bearish = sorted(
        [a for a in assets if a.get("change_pct", 0) < 0],
        key=lambda a: a.get("change_pct", 0)
    )[:top_n]
    
    def pick_card(p, color, arrow):
        return (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:8px 0;border-bottom:1px solid rgba(26,32,64,.3)">'
            f'<strong>{p["name"]}</strong>'
            f'<span style="color:{color};font-weight:600">{arrow} {abs(p["change_pct"]):.1f}%</span>'
            f'</div>'
        )
    
    bull_cards = "".join(pick_card(p, "#22c55e", "▲") for p in bullish) if bullish else '<div style="color:var(--muted);padding:8px 0">No bullish picks</div>'
    bear_cards = "".join(pick_card(p, "#ef4444", "▼") for p in bearish) if bearish else '<div style="color:var(--muted);padding:8px 0">No bearish picks</div>'
    
    return f"""<div style="background:rgba(56,189,248,.02);border:1px solid var(--border);border-radius:14px;padding:20px;margin-bottom:20px">
<h3 style="margin:0 0 14px 0;font-size:1.1em">🦅 Hawk Eye <span style="color:var(--muted);font-weight:400;font-size:.85em">— Top confidence picks</span></h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
<div>
<h4 style="margin:0 0 10px 0;color:#22c55e">🔥 Bullish</h4>
{bull_cards}
</div>
<div>
<h4 style="margin:0 0 10px 0;color:#ef4444">🧊 Bearish</h4>
{bear_cards}
</div>
</div>
</div>"""

def compute_sentiment(assets: list) -> dict:
    """
    Compute composite market sentiment from multiple signals.
    
    Signals:
      1. Breadth: % of assets moving up
      2. Momentum: average change magnitude
      3. Trend alignment: % with bullish MA crossover
      4. Volume conviction: % with elevated volume (>1.5x avg)
      5. Volatility regime: elevated or suppressed vol
    
    Returns:
      { direction, confidence, score, signals, summary }
    """
    n = len(assets)
    if n == 0:
        return {"direction": "NEUTRAL", "confidence": 0, "score": 0, "signals": {}, "summary": "No data"}

    # ── Signal 1: Breadth (0-100) ──
    up = sum(1 for a in assets if a.get("change_pct", 0) > 0)
    breadth = (up / n) * 100

    # ── Signal 2: Momentum ──
    avg_change = sum(a.get("change_pct", 0) for a in assets) / n
    # Normalize: 0-100 scale, where ±2% = ±50, ±5% = ±100
    momentum_score = max(-100, min(100, avg_change * 20))

    # ── Signal 3: Trend alignment (bullish = MA5 > MA20) ──
    bullish_trend = sum(1 for a in assets if a.get("trend") == "BULLISH")
    trend_score = (bullish_trend / n) * 100

    # ── Signal 4: Volume conviction ──
    high_vol = sum(1 for a in assets if a.get("vol_ratio", 0) > 1.5)
    vol_conviction = (high_vol / n) * 100

    # ── Signal 5: Volatility regime ──
    avg_volatility = sum(a.get("volatility_20d", 0) for a in assets) / n
    # High vol without clear direction = uncertainty
    if avg_volatility > 3:
        volatility_signal = -20  # Penalty for high vol
    elif avg_volatility < 1:
        volatility_signal = 10   # Bonus for low vol (calm trend)
    else:
        volatility_signal = 0

    # ── Composite score ──
    # Weights: breadth (35%), momentum (30%), trend (20%), volume (10%), volatility (5%)
    raw_score = (
        (breadth - 50) * 0.35 +      # center at 0
        (momentum_score) * 0.30 +
        (trend_score - 50) * 0.20 +
        (vol_conviction - 15) * 0.10 +  # 15% is baseline for >1.5x vol
        volatility_signal * 0.05
    )

    # Map to direction
    if raw_score > 20:
        direction = "BULLISH"
    elif raw_score > 7:
        direction = "SLIGHTLY BULLISH"
    elif raw_score >= -7:
        direction = "NEUTRAL"
    elif raw_score > -20:
        direction = "SLIGHTLY BEARISH"
    else:
        direction = "BEARISH"

    # ── Confidence ──
    # Based on signal agreement and magnitude
    signals_list = [
        breadth,                          # 0-100, higher = bullish
        momentum_score + 50,              # normalize to 0-100
        trend_score,
        vol_conviction,
    ]
    
    # Agreement: std deviation of bullish/bearish signals
    # Lower std = higher agreement = higher confidence
    import statistics
    sig_std = statistics.stdev(signals_list) if len(signals_list) > 1 else 0
    agreement_bonus = max(0, 30 - sig_std)  # Lower spread = higher bonus
    
    # Magnitude: stronger signal = more conviction
    magnitude = abs(raw_score)
    magnitude_score = min(40, magnitude * 1.2)
    
    # Base confidence
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
        "summary": f"{direction} ({confidence}% confidence) — {up}/{n} assets up, "
                   f"{avg_change:+.1f}% avg, {bullish_trend}/{n} bullish trend"
    }
