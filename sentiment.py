"""
Sentiment engine — composite market regime detection + premium momentum scanner.
Used by all Atlas Nexus pipelines (crypto, commodities, indices, forex, actions, etf).
"""

from __future__ import annotations

from html import escape
import statistics


def _num(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _asset_name(a: dict) -> str:
    return str(a.get("name") or a.get("symbol") or a.get("base") or "Asset")


def _asset_symbol(a: dict) -> str:
    sym = a.get("symbol")
    if sym:
        return str(sym)
    if a.get("base") and a.get("quote"):
        return f"{a['base']}{a['quote']}"
    return _asset_name(a)


def _asset_group(a: dict) -> str:
    for key in ("sector", "category", "region", "group", "mcap_tier", "source"):
        if a.get(key):
            return str(a[key])
    return "Market"


def _change_pct(a: dict) -> float:
    if "change_pct" in a:
        return _num(a.get("change_pct"))
    if "change_24h" in a:
        return _num(a.get("change_24h"))
    return _num(a.get("change"))


def _trend(a: dict) -> str:
    raw = str(a.get("trend") or "NEUTRAL").upper()
    if raw in {"STRONG_UP", "UP"}:
        return "BULLISH"
    if raw in {"STRONG_DOWN", "DOWN"}:
        return "BEARISH"
    if raw in {"FLAT", "SIDEWAYS"}:
        return "NEUTRAL"
    return raw


def _volatility(a: dict) -> float:
    if "volatility_20d" in a:
        return _num(a.get("volatility_20d"))
    raw = str(a.get("volatility") or "").upper()
    return {"LOW": 1.0, "MEDIUM": 2.2, "HIGH": 4.2}.get(raw, _num(a.get("volatility")))


def _vol_ratio(a: dict) -> float:
    if "vol_ratio" in a:
        return _num(a.get("vol_ratio"), 1.0)
    if "volume_mcap_ratio" in a:
        # Crypto liquidity proxy: 10% of market cap traded is already meaningful.
        return max(0.0, min(4.0, _num(a.get("volume_mcap_ratio")) * 10))
    return 1.0


def _dist_to_high(a: dict) -> float:
    return _num(a.get("dist_to_52w_high"), 10.0)


def _candle_ratio(a: dict) -> float:
    return _num(a.get("candle_ratio"), 0.45)


def _score_asset(a: dict) -> dict:
    ch = _change_pct(a)
    trend = _trend(a)
    trend_bonus = {"BULLISH": 4.0, "NEUTRAL": 0.0, "BEARISH": -4.0}.get(trend, 0.0)

    vr = _vol_ratio(a)
    vol_bonus = 2.5 if vr >= 2.0 else 1.3 if vr >= 1.5 else 0.0

    dist = _dist_to_high(a)
    if dist > 8:
        room_bonus = 2.4
        resistance_label = "room"
    elif dist > 3:
        room_bonus = 1.0
        resistance_label = "mid"
    elif dist < 1.5:
        room_bonus = -2.8
        resistance_label = "resistance"
    else:
        room_bonus = -0.4
        resistance_label = "near high"

    candle = _candle_ratio(a)
    candle_penalty = -2.0 if candle > 0.82 else -0.8 if candle > 0.68 else 0.0

    vol = _volatility(a)
    vol_penalty = -max(0.0, vol - 3.0) * 0.9
    stability_bonus = 0.8 if vol and vol < 1.2 else 0.0

    score = ch + trend_bonus + vol_bonus + room_bonus + candle_penalty + vol_penalty + stability_bonus
    score = round(score, 2)
    conviction = min(100, max(0, round(abs(score) * 7.5 + min(abs(ch), 20) * 1.2)))

    tags = []
    if trend == "BULLISH":
        tags.append(("Trend", "MA bull"))
    elif trend == "BEARISH":
        tags.append(("Trend", "MA bear"))
    if vr >= 1.5:
        tags.append(("Volume", f"{vr:.1f}×"))
    if dist < 2:
        tags.append(("52W", "résistance"))
    elif dist > 8:
        tags.append(("52W", "room"))
    if candle > 0.8:
        tags.append(("Candle", "vertical"))
    if vol and vol < 1.2:
        tags.append(("Vol", "stable"))
    elif vol > 3:
        tags.append(("Vol", "hot"))

    return {
        "score": score,
        "conviction": conviction,
        "change": ch,
        "trend": trend,
        "vol_ratio": vr,
        "volatility": vol,
        "dist": dist,
        "resistance_label": resistance_label,
        "candle": candle,
        "tags": tags[:4],
    }


def _fmt_score(score: float) -> str:
    return f"{score:+.1f}"


def _tag_html(tags: list[tuple[str, str]]) -> str:
    if not tags:
        return '<span class="momentum-tag muted">Clean read</span>'
    return "".join(f'<span class="momentum-tag"><b>{escape(k)}</b> {escape(v)}</span>' for k, v in tags)


def _pick_card(asset: dict, side: str) -> str:
    m = _score_asset(asset)
    bullish = side == "bull"
    color_class = "score-hot" if bullish else "score-risk"
    arrow = "▲" if bullish else "▼"
    change_color = "#22c55e" if m["change"] >= 0 else "#ef4444"
    title = escape(_asset_name(asset))
    symbol = escape(_asset_symbol(asset))
    group = escape(_asset_group(asset))
    score = _fmt_score(m["score"])
    tag_text = " · ".join(f"{k}: {v}" for k, v in m["tags"][:3]) or "clean read"
    width = max(8, min(100, m["conviction"]))
    return f"""<div class="signal-row hawk-row" data-market="{group.lower()}">
<div>
<span class="asset-name">{title}</span>
<span class="asset-tag">{symbol}</span>
<span class="asset-meta">{group} · {tag_text}</span>
<span class="asset-levels">
<span style="color:{change_color}">{arrow} {m['change']:.1f}%</span>
<span style="color:#bae6fd">Trend {escape(m['trend'].title())}</span>
<span style="color:#fbbf24">Vol {m['vol_ratio']:.1f}×</span>
<span style="color:#a7f3d0">52W {m['dist']:.0f}%</span>
</span>
<div class="hawk-conviction"><span style="width:{width}%"></span></div>
</div>
<div style="text-align:right">
<span class="score-pill {color_class}">{score}</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">conviction {m['conviction']}%</div>
<div style="font-size:.7em;color:{change_color};margin-top:2px">{escape(m['resistance_label'])}</div>
</div>
</div>"""


def momentum_scanner_html(assets: list, top_n: int = 4) -> str:
    """Premium multi-signal scanner for every category page."""
    if len(assets) < 2:
        return ""

    scored = [(a, _score_asset(a)) for a in assets]
    bullish_pool = [(a, m) for a, m in scored if m["score"] > 0]
    bearish_pool = [(a, m) for a, m in scored if m["score"] < 0]
    bullish = [a for a, _ in sorted(bullish_pool, key=lambda x: x[1]["score"], reverse=True)[:top_n]]
    bearish = [a for a, _ in sorted(bearish_pool, key=lambda x: x[1]["score"])[:top_n]]

    # Neutral radar: strongest setups that are not already in the directional columns.
    used = {id(a) for a in bullish + bearish}
    radar = [a for a, m in sorted(scored, key=lambda x: x[1]["conviction"], reverse=True) if id(a) not in used][:3]

    n = len(assets)
    up = sum(1 for a in assets if _change_pct(a) > 0)
    avg_score = sum(m["score"] for _, m in scored) / n
    avg_vol = sum(_volatility(a) for a in assets) / n
    high_volume = sum(1 for a in assets if _vol_ratio(a) >= 1.5)
    near_resistance = sum(1 for a in assets if _dist_to_high(a) < 2)
    leader = max(scored, key=lambda x: x[1]["score"])
    pressure = min(scored, key=lambda x: x[1]["score"])

    regime = "Risk-on" if avg_score > 5 else "Risk-off" if avg_score < -5 else "Mixed"
    regime_cls = "bull" if avg_score > 5 else "bear" if avg_score < -5 else "neutral"

    def empty(text: str) -> str:
        return f'<div class="momentum-empty">{escape(text)}</div>'

    bull_html = "".join(_pick_card(a, "bull") for a in bullish) or empty("No clean bullish momentum signal")
    bear_html = "".join(_pick_card(a, "bear") for a in bearish) or empty("No clean bearish pressure signal")
    radar_html = "".join(_pick_card(a, "bull" if _score_asset(a)["score"] >= 0 else "bear") for a in radar) or empty("Radar is clean")

    return f"""
<section class="momentum-scanner-v2 scanner hawkeye-scanner" aria-label="Hawkeye">
  <style>
    .hawkeye-scanner{{margin:0 0 24px;padding:24px;border:1px solid rgba(56,189,248,.20);border-radius:28px;position:relative;overflow:hidden;text-align:left;background:linear-gradient(135deg,rgba(16,22,34,.92),rgba(18,14,33,.86) 48%,rgba(29,22,10,.76));box-shadow:0 22px 70px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.06)}}
    .hawkeye-scanner:before{{content:"";position:absolute;inset:-1px;background:radial-gradient(circle at 16% 0%,rgba(56,189,248,.18),transparent 35%),radial-gradient(circle at 92% 14%,rgba(245,158,11,.12),transparent 28%);pointer-events:none}}
    .hawkeye-scanner>*{{position:relative}}
    .scanner-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}}
    .scanner-head h2{{margin:0;color:var(--atlas-text,var(--text));font-size:1.18rem;font-weight:950;letter-spacing:-.04em}}
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
    .score-hot{{color:#bbf7d0;background:rgba(34,197,94,.13);border-color:rgba(34,197,94,.22)}}.score-risk{{color:#fecaca;background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.22)}}
    .hawk-conviction{{height:4px;max-width:220px;border-radius:999px;background:rgba(148,163,184,.16);overflow:hidden;margin-top:9px}}
    .hawk-conviction span{{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#38bdf8,#22c55e,#f59e0b);box-shadow:0 0 18px rgba(56,189,248,.35)}}
    .momentum-radar-title{{margin:14px 0 0!important;color:var(--atlas-muted,var(--muted))!important;font-size:.82rem!important;grid-column:1/-1}}
    .momentum-radar{{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}
    .momentum-empty{{padding:16px;border:1px dashed var(--atlas-border,var(--border));border-radius:18px;color:var(--atlas-muted,var(--muted));background:rgba(255,255,255,.025)}}
    @media(max-width:860px){{.scanner-head{{display:block}}.scanner-board{{grid-template-columns:1fr}}.momentum-radar{{grid-template-columns:1fr}}}}
    @media(max-width:520px){{.hawkeye-scanner{{padding:16px;border-radius:22px}}.signal-row{{display:block}}.signal-row>div:last-child{{text-align:left!important;margin-top:10px}}}}
  </style>
  <div class="scanner-head"><div><h2>🦅 Hawkeye</h2></div></div>
  <div class="scanner-board hawk-board">
    <div class="signal-card"><h3>🚀 Bullish momentum ({len(bullish)})</h3>{bull_html}</div>
    <div class="signal-card"><h3>🐻 Bearish pressure ({len(bearish)})</h3>{bear_html}</div>
    <h4 class="momentum-radar-title">◇ Cross-market radar</h4>
    <div class="momentum-radar">{radar_html}</div>
  </div>
</section>"""


# Backward compat alias
hawk_eye_html = momentum_scanner_html


def compute_sentiment(assets: list) -> dict:
    """
    Compute composite market sentiment from multiple signals.

    Signals:
      1. Breadth: % of assets moving up
      2. Momentum: average change magnitude
      3. Trend alignment: % with bullish MA crossover
      4. Volume conviction: % with elevated volume (>1.5x avg)
      5. Volatility regime: elevated or suppressed vol
    """
    n = len(assets)
    if n == 0:
        return {"direction": "NEUTRAL", "confidence": 0, "score": 0, "signals": {}, "summary": "No data"}

    up = sum(1 for a in assets if _change_pct(a) > 0)
    breadth = (up / n) * 100

    avg_change = sum(_change_pct(a) for a in assets) / n
    momentum_score = max(-100, min(100, avg_change * 20))

    bullish_trend = sum(1 for a in assets if _trend(a) == "BULLISH")
    trend_score = (bullish_trend / n) * 100

    high_vol = sum(1 for a in assets if _vol_ratio(a) > 1.5)
    vol_conviction = (high_vol / n) * 100

    avg_volatility = sum(_volatility(a) for a in assets) / n
    if avg_volatility > 3:
        volatility_signal = -20
    elif avg_volatility < 1:
        volatility_signal = 10
    else:
        volatility_signal = 0

    raw_score = (
        (breadth - 50) * 0.35 +
        momentum_score * 0.30 +
        (trend_score - 50) * 0.20 +
        (vol_conviction - 15) * 0.10 +
        volatility_signal * 0.05
    )

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
