"""
Sentiment engine — composite market regime detection + Hawk Eye picks
Used by all Atlas Nexus pipelines (crypto, commodities, indices, forex, actions, etf)
"""

def hawk_eye_html(assets: list, top_n: int = 3) -> str:
    """
    🦅 Hawk Eye — Gem detection engine
    Finds hidden gems using a composite score inspired by crypto gem hunting:
      Gem Score = Trend + Momentum + Conviction − Volatility Penalty
    
    Signals:
      - Trend: BULLISH +4, NEUTRAL 0, BEARISH -4
      - Momentum: change_pct (daily %)
      - Conviction: vol_ratio > 2x → +3pts, > 1.5x → +2, > 1x → +1
      - Stability penalty: vol_20d > 3% → −1 per extra %
    
    Bullish gems: high positive gem_score (strong uptrend with conviction)
    Bearish alerts: high negative gem_score (confirmed downtrend with volume)
    """
    if len(assets) < 2:
        return ""
    
    def gem_score(a):
        ch = a.get("change_pct", 0)
        trend = a.get("trend", "NEUTRAL")
        trend_bonus = {"BULLISH": 4, "NEUTRAL": 0, "BEARISH": -4}.get(trend, 0)
        
        vr = a.get("vol_ratio", 1.0)
        if vr > 2.0: conv_bonus = 3
        elif vr > 1.5: conv_bonus = 2
        elif vr > 1.0: conv_bonus = 1
        else: conv_bonus = 0
        
        vol = a.get("volatility_20d", 0)
        stability_penalty = max(0, (vol - 3.0)) * 1.0 if vol > 3 else 0
        
        score = ch + trend_bonus + conv_bonus - stability_penalty
        return round(score, 2)
    
    # Bullish gems: top positive gem_score
    bullish = sorted(
        [a for a in assets if a.get("change_pct", 0) > 0 and a.get("trend", "") != "BEARISH"],
        key=lambda a: gem_score(a), reverse=True
    )[:top_n]
    
    # Bearish alerts: most negative gem_score
    bearish = sorted(
        [a for a in assets if a.get("change_pct", 0) < 0 and a.get("trend", "") != "BULLISH"],
        key=lambda a: gem_score(a)
    )[:top_n]
    
    def pick_card(p, color, arrow):
        score = gem_score(p)
        signals = []
        if p.get("vol_ratio", 0) > 1.5:
            signals.append("📊")
        if p.get("volatility_20d", 0) < 2:
            signals.append("💎")  # low vol = stable gem
        sig_str = " ".join(signals)
        return (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:8px 0;border-bottom:1px solid rgba(26,32,64,.3)">'
            f'<div><strong>{p["name"]}</strong>'
            f'<span style="color:var(--muted);font-size:.82em;margin-left:4px">{sig_str}</span></div>'
            f'<div style="text-align:right">'
            f'<span style="color:{color};font-weight:600">{arrow} {abs(p["change_pct"]):.1f}%</span>'
            f'<span style="color:var(--muted);font-size:.78em;margin-left:6px">★{score:.1f}</span>'
            f'</div></div>'
        )
    
    bull_cards = "".join(pick_card(p, "#22c55e", "▲") for p in bullish) if bullish else '<div style="color:var(--muted);padding:8px 0">En attente de signaux</div>'
    bear_cards = "".join(pick_card(p, "#ef4444", "▼") for p in bearish) if bearish else '<div style="color:var(--muted);padding:8px 0">En attente de signaux</div>'
    
    return f"""<div style="background:rgba(56,189,248,.02);border:1px solid var(--border);border-radius:14px;padding:20px;margin-bottom:20px">
<h3 style="margin:0 0 14px 0;font-size:1.1em">🦅 Hawk Eye <span style="color:var(--muted);font-weight:400;font-size:.85em">— Gem detection · Trend + Volume + Volatility</span></h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
<div>
<h4 style="margin:0 0 10px 0;color:#22c55e">💎 Bullish Gems</h4>
<div style="color:var(--muted);font-size:.75em;margin-bottom:6px">Score = momentum + trend + conviction − volatility</div>
{bull_cards}
</div>
<div>
<h4 style="margin:0 0 10px 0;color:#ef4444">🧊 Bearish Alerts</h4>
<div style="color:var(--muted);font-size:.75em;margin-bottom:6px">Confirmed downtrend with volume conviction</div>
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
