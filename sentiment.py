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
    accent = "var(--atlas-green,var(--green,#22c55e))" if bullish else "var(--atlas-red,var(--red,#ef4444))"
    arrow = "▲" if bullish else "▼"
    signed = abs(m["change"])
    title = escape(_asset_name(asset))
    symbol = escape(_asset_symbol(asset))
    group = escape(_asset_group(asset))
    score = _fmt_score(m["score"])
    width = max(8, min(100, m["conviction"]))
    return f"""
    <article class="momentum-pick {'bull' if bullish else 'bear'}">
      <div class="momentum-pick-top">
        <div>
          <div class="momentum-name">{title}</div>
          <div class="momentum-meta">{symbol} · {group}</div>
        </div>
        <div class="momentum-score" style="color:{accent}">{score}</div>
      </div>
      <div class="momentum-tags">{_tag_html(m['tags'])}</div>
      <div class="momentum-bar"><span style="width:{width}%;background:{accent}"></span></div>
      <div class="momentum-metrics">
        <span><b>{arrow} {signed:.1f}%</b><em>change</em></span>
        <span><b>{escape(m['trend'].title())}</b><em>trend</em></span>
        <span><b>{m['vol_ratio']:.1f}×</b><em>volume</em></span>
        <span><b>{m['dist']:.0f}%</b><em>52W room</em></span>
      </div>
    </article>"""


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
<section class="momentum-scanner-v2" aria-label="Momentum Scanner">
  <style>
    .momentum-scanner-v2{{margin:0 0 24px;padding:22px;border:1px solid var(--atlas-border,var(--border));border-radius:26px;background:linear-gradient(180deg,rgba(255,255,255,.075),rgba(255,255,255,.03));box-shadow:0 22px 70px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.06)}}
    .momentum-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}}
    .momentum-kicker{{color:var(--atlas-accent,var(--accent));font-size:.76rem;text-transform:uppercase;letter-spacing:.13em;font-weight:900;margin-bottom:5px}}
    .momentum-title{{font-size:1.35rem;font-weight:950;letter-spacing:-.055em;color:var(--atlas-text,var(--text))}}
    .momentum-sub{{color:var(--atlas-muted,var(--muted));font-size:.86rem;margin-top:5px;line-height:1.55}}
    .momentum-regime{{border:1px solid var(--atlas-border,var(--border));border-radius:999px;padding:8px 11px;font-size:.78rem;font-weight:900;white-space:nowrap;background:rgba(255,255,255,.045)}}
    .momentum-regime.bull{{color:var(--atlas-green,var(--green))}}.momentum-regime.bear{{color:var(--atlas-red,var(--red))}}.momentum-regime.neutral{{color:var(--atlas-amber,#f59e0b)}}
    .momentum-pulse{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}}
    .momentum-chip{{padding:12px;border-radius:18px;border:1px solid var(--atlas-border,var(--border));background:rgba(7,9,20,.34)}}
    .momentum-chip span{{display:block;color:var(--atlas-muted,var(--muted));font-size:.72rem;font-weight:850;text-transform:uppercase;letter-spacing:.06em}}.momentum-chip b{{display:block;margin-top:4px;color:var(--atlas-text,var(--text));font-size:.98rem}}
    .momentum-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.momentum-col{{display:flex;flex-direction:column;gap:10px}}.momentum-col h4{{margin:0 0 2px;font-size:.88rem;font-weight:950;letter-spacing:-.025em;color:var(--atlas-text,var(--text))}}
    .momentum-pick{{border:1px solid var(--atlas-border,var(--border));border-radius:20px;padding:13px;background:rgba(7,9,20,.36);box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}}
    .momentum-pick.bull{{border-left:3px solid var(--atlas-green,var(--green))}}.momentum-pick.bear{{border-left:3px solid var(--atlas-red,var(--red))}}
    .momentum-pick-top{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}}.momentum-name{{font-weight:900;color:var(--atlas-text,var(--text));line-height:1.2}}.momentum-meta{{color:var(--atlas-muted,var(--muted));font-size:.76rem;margin-top:3px}}.momentum-score{{font-weight:950;font-size:1.15rem;letter-spacing:-.04em}}
    .momentum-tags{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}}.momentum-tag{{border:1px solid var(--atlas-border,var(--border));border-radius:999px;padding:4px 7px;color:var(--atlas-muted,var(--muted));font-size:.68rem;background:rgba(255,255,255,.035)}}.momentum-tag b{{color:var(--atlas-text,var(--text))}}.momentum-tag.muted{{opacity:.7}}
    .momentum-bar{{height:5px;border-radius:99px;background:rgba(148,163,184,.16);overflow:hidden;margin:8px 0 10px}}.momentum-bar span{{display:block;height:100%;border-radius:99px;box-shadow:0 0 18px currentColor}}
    .momentum-metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}}.momentum-metrics span{{min-width:0}}.momentum-metrics b{{display:block;color:var(--atlas-text,var(--text));font-size:.74rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.momentum-metrics em{{display:block;color:var(--atlas-faint,var(--muted));font-size:.64rem;font-style:normal;text-transform:uppercase;letter-spacing:.05em;margin-top:2px}}
    .momentum-radar{{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:2px}}.momentum-radar-title{{grid-column:1/-1;margin:6px 0 0!important;color:var(--atlas-muted,var(--muted))!important;font-size:.82rem!important}}
    .momentum-empty{{padding:16px;border:1px dashed var(--atlas-border,var(--border));border-radius:18px;color:var(--atlas-muted,var(--muted));background:rgba(255,255,255,.025)}}
    @media(max-width:860px){{.momentum-head{{flex-direction:column}}.momentum-pulse{{grid-template-columns:repeat(2,1fr)}}.momentum-grid{{grid-template-columns:1fr}}.momentum-radar{{grid-template-columns:1fr}}}}
    @media(max-width:480px){{.momentum-scanner-v2{{padding:16px;border-radius:22px}}.momentum-pulse{{grid-template-columns:1fr}}.momentum-metrics{{grid-template-columns:repeat(2,1fr)}}}}
  </style>
  <div class="momentum-head">
    <div>
      <div class="momentum-kicker">Market pulse scanner</div>
      <div class="momentum-title">Momentum leaders & pressure zones</div>
      <div class="momentum-sub">Score composite : change, trend MA, volume, distance au 52W high, bougie et volatilité. Les barres indiquent la conviction normalisée.</div>
    </div>
    <div class="momentum-regime {regime_cls}">{regime} · {_fmt_score(avg_score)}</div>
  </div>
  <div class="momentum-pulse">
    <div class="momentum-chip"><span>Leader</span><b>{escape(_asset_symbol(leader[0]))} · {_fmt_score(leader[1]['score'])}</b></div>
    <div class="momentum-chip"><span>Pressure</span><b>{escape(_asset_symbol(pressure[0]))} · {_fmt_score(pressure[1]['score'])}</b></div>
    <div class="momentum-chip"><span>Breadth</span><b>{up}/{n} up · {round(up/n*100)}%</b></div>
    <div class="momentum-chip"><span>Conviction</span><b>{high_volume} vol spikes · {near_resistance} near 52W</b></div>
  </div>
  <div class="momentum-grid">
    <div class="momentum-col"><h4>▲ Bullish momentum</h4>{bull_html}</div>
    <div class="momentum-col"><h4>▼ Bearish pressure</h4>{bear_html}</div>
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
