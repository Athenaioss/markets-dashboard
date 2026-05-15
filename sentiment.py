"""
🦅 Hawkeye V4 shared sentiment/pressure components.

Used by Atlas Nexus category dashboards. Hawkeye is a market-pressure radar,
not a trade placement widget.
"""

from __future__ import annotations

from html import escape
import statistics

from hawkeye_core import analyze_assets, num as _num, safe_price, asset_name, asset_symbol
from tradingview_links import TV_LINK_CSS, tradingview_link


def _change_pct(a: dict) -> float:
    if "change_pct" in a: return _num(a.get("change_pct"))
    if "change_24h" in a: return _num(a.get("change_24h"))
    return _num(a.get("change"))


def _asset_group(a: dict) -> str:
    for key in ("sector", "category", "region", "group", "mcap_tier", "source"):
        if a.get(key): return str(a[key])
    return "Market"


def _score_class(score: int) -> str:
    if score >= 75: return "score-hot"
    if score >= 60: return "score-warm"
    return "score-muted"


def _direction_title(direction: str) -> str:
    if direction == "bullish": return "Bullish pressure"
    if direction == "bearish": return "Bearish pressure"
    return "Mixed / Neutral"


def _row(a: dict, source: str = "") -> str:
    ext = a.get("extension_atr", 0)
    warning = " · extension warning" if 1.5 < ext <= 2.5 else " · shock/extended" if ext > 2.5 else ""
    rel = f"<span style='color:#a7f3d0'>{escape(a['relative_label'])}</span>" if a.get("relative_label") else ""
    participation = escape(a.get("participation_label") or "Participation n/a")
    return f"""<div class="signal-row hawk-row">
<div>
<span class="asset-name">{escape(a['name'])}</span>
<span class="asset-tag">{escape(_direction_title(a['direction']))}</span>
<span class="asset-meta">{escape(source or a.get('source') or 'market')} · {escape(a['regime'])} · {escape(a['signal_family'])}{warning}</span>
<span class="asset-levels">
<span style="color:#bae6fd">Reference price {escape(a['price_label'])}</span>
<span style="color:#c4b5fd">nROC5 {a['nroc5']:+.2f}</span>
<span style="color:#fbbf24">RSI {a['rsi']}</span>
<span style="color:#fca5a5">Ext {ext:.1f} ATR</span>
<span style="color:#93c5fd">{participation}</span>
{tradingview_link(a.get("symbol"), source or a.get("source", ""))}
{rel}
</span>
</div>
<div style="text-align:right">
<span class="score-pill {_score_class(a['score'])}">{a['score']}/100</span>
<div style="font-size:.72em;color:var(--muted);margin-top:3px">Net {a['net_pressure']:+d} · {escape(a['symbol'])}</div>
<div style="font-size:.7em;color:{a['color']};margin-top:2px">{escape(a['label'])}</div>
</div>
</div>"""


def _card(title: str, emoji: str, rows: list[dict], empty: str) -> str:
    body = "".join(_row(x, x.get("source", "")) for x in rows) if rows else f'<div class="momentum-empty">{escape(empty)}</div>'
    return f'<div class="signal-card"><h3>{emoji} {escape(title)} ({len(rows)})</h3>{body}</div>'


def momentum_scanner_html(assets: list, top_n: int = 4, source: str = "") -> str:
    """Hawkeye V4 category component: compact pressure radar only."""
    if len(assets) < 2:
        return ""
    for a in assets:
        if source and not a.get("source"):
            a["source"] = source
    analyses = analyze_assets(assets)
    usable = [a for a in analyses if a["tier"] != "DEGRADED" and a["score"] >= 40]
    bullish = sorted([a for a in usable if a["direction"] == "bullish" and a["score"] >= 60], key=lambda x: x["score"], reverse=True)[:top_n]
    bearish = sorted([a for a in usable if a["direction"] == "bearish" and a["score"] >= 60], key=lambda x: x["score"], reverse=True)[:top_n]
    extreme = sum(1 for a in analyses if a["score"] >= 90)
    strong = sum(1 for a in analyses if 75 <= a["score"] < 90)
    active = sum(1 for a in analyses if 60 <= a["score"] < 75)
    return f"""
<section class="momentum-scanner-v2 scanner hawkeye-scanner hawkeye-v4" aria-label="Hawkeye V4">
  <style>
    .hawkeye-scanner{{margin:0 0 24px;padding:24px;border:1px solid rgba(56,189,248,.20);border-radius:28px;position:relative;overflow:hidden;text-align:left;background:linear-gradient(135deg,rgba(16,22,34,.92),rgba(18,14,33,.86) 48%,rgba(29,22,10,.76));box-shadow:0 22px 70px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.06)}}
    .hawkeye-scanner:before{{content:"";position:absolute;inset:-1px;background:radial-gradient(circle at 16% 0%,rgba(56,189,248,.18),transparent 35%),radial-gradient(circle at 92% 14%,rgba(245,158,11,.12),transparent 28%);pointer-events:none}}.hawkeye-scanner>*{{position:relative}}
    .scanner-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}}.scanner-head h2{{margin:0;color:var(--atlas-text,var(--text));font-size:1.18rem;font-weight:950;letter-spacing:-.04em}}.scanner-sub{{margin:6px 0 0;color:var(--muted);font-size:.82rem;line-height:1.45}}
    .scanner-head .tier-legend{{display:flex;gap:10px;flex-wrap:wrap;font-size:.74em;color:var(--muted)}}.scanner-head .tier-legend span{{padding:3px 8px;border-radius:999px;border:1px solid var(--border);background:rgba(255,255,255,.04)}}.scanner-board{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
    .signal-card{{border:1px solid var(--atlas-border,var(--border));border-radius:22px;padding:14px;background:rgba(7,9,20,.38);box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}}.signal-card h3{{margin:0 0 12px;color:var(--atlas-text,var(--text));font-size:.98rem;font-weight:950;letter-spacing:-.025em}}
    .signal-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px;border:1px solid rgba(148,163,184,.16);border-radius:16px;background:rgba(255,255,255,.035);margin-top:9px}}.signal-row:first-of-type{{margin-top:0}}.asset-name{{display:inline;font-weight:900;color:var(--atlas-text,var(--text));line-height:1.15;margin-right:6px}}
    .asset-tag{{display:inline-flex;vertical-align:middle;padding:2px 7px;border-radius:999px;background:rgba(56,189,248,.10);border:1px solid rgba(56,189,248,.22);color:#bae6fd;font-size:.66rem;font-weight:900;text-transform:uppercase}}.asset-meta{{display:block;color:var(--atlas-muted,var(--muted));font-size:.74rem;margin-top:4px;line-height:1.35}}
    .asset-levels{{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px;font-size:.72rem;font-weight:850}}.asset-levels span{{padding:4px 7px;border-radius:999px;background:rgba(15,23,42,.55);border:1px solid rgba(148,163,184,.16)}}.score-pill{{display:inline-flex;align-items:center;justify-content:center;min-width:58px;padding:7px 9px;border-radius:999px;font-weight:950;font-size:.86rem;border:1px solid transparent}}
    {TV_LINK_CSS}
    .score-hot{{color:#bbf7d0;background:rgba(34,197,94,.13);border-color:rgba(34,197,94,.22)}}.score-risk{{color:#fecaca;background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.22)}}.score-warm{{color:#ffd699;background:rgba(245,158,11,.14);border-color:rgba(245,158,11,.22)}}.score-muted{{color:#cbd5e1;background:rgba(100,116,139,.10);border-color:rgba(100,116,139,.18)}}.momentum-empty{{padding:16px;border:1px dashed var(--atlas-border,var(--border));border-radius:18px;color:var(--atlas-muted,var(--muted));background:rgba(255,255,255,.025)}}
    @media(max-width:860px){{.scanner-head{{display:block}}.scanner-board{{grid-template-columns:1fr}}}}@media(max-width:520px){{.hawkeye-scanner{{padding:16px;border-radius:22px}}.signal-row{{display:block}}.signal-row>div:last-child{{text-align:left!important;margin-top:10px}}}}
  </style>
  <div class="scanner-head"><div><h2>🦅 Hawkeye V4 — Market Pressure Radar</h2><p class="scanner-sub">Pressure, regime, normalized momentum and extension.</p></div><div class="tier-legend"><span>0-39 Weak</span><span>40-59 Watch</span><span>60-74 Active pressure</span><span>75-89 Strong pressure</span><span>90+ Extreme pressure</span><span>⚡ {extreme} · 🦅 {strong} · 👁️ {active}</span></div></div>
  <div class="scanner-board hawk-board">{_card('Bullish pressure', '📈', bullish, 'No active bullish pressure')}{_card('Bearish pressure', '📉', bearish, 'No active bearish pressure')}</div>
</section>"""


def hawk_eye_html(assets: list, top_n: int = 4, source: str = "") -> str:
    return momentum_scanner_html(assets, top_n, source)


def back_to_dashboard_html() -> str:
    return """
<div style="margin-top:28px;text-align:center">
  <a href="index.html" style="display:inline-block;padding:12px 24px;border:1px solid var(--border);border-radius:12px;color:var(--muted);text-decoration:none;font-size:.88em;font-weight:700;transition:all .15s">← Retour Dashboard</a>
</div>"""


def unusual_activity_html(assets: list) -> str:
    analyses = analyze_assets(assets)
    alerts = []
    for a in analyses:
        flags = []
        if a["extension_atr"] > 2.5: flags.append(f"Extension {a['extension_atr']:.1f} ATR")
        if a["atr_percentile"] > 90: flags.append(f"ATR pct {a['atr_percentile']:.0f}")
        if a["rsi"] > 78: flags.append(f"RSI {a['rsi']} elevated")
        elif a["rsi"] < 22: flags.append(f"RSI {a['rsi']} depressed")
        if abs(a["nroc5"]) > 2.5: flags.append(f"nROC5 {a['nroc5']:+.1f}")
        if flags:
            alerts.append((a, flags))
    if not alerts:
        return ""
    rows = "".join(f"<div class='alert-row'><strong>{escape(a['name'])}</strong><span>{escape(' · '.join(flags))}</span></div>" for a, flags in alerts[:6])
    return f"""
<section class="unusual-activity" style="margin:0 0 24px;padding:18px;border:1px solid rgba(245,158,11,.28);border-radius:20px;background:rgba(245,158,11,.06)">
<h2 style="margin:0 0 10px;font-size:1.05rem">🚨 Unusual market pressure</h2>
<p style="margin:0 0 12px;color:var(--muted);font-size:.84rem">Extension, volatility or RSI readings that require manual chart inspection.</p>
{rows}
</section>"""


def compute_sentiment(assets: list) -> dict:
    n = len(assets)
    if n == 0:
        return {"direction": "NEUTRAL", "confidence": 0, "score": 0, "signals": {}, "summary": "No data"}
    up = sum(1 for a in assets if _change_pct(a) > 0)
    breadth = (up / n) * 100
    avg_change = sum(_change_pct(a) for a in assets) / n
    momentum_score = max(-100, min(100, avg_change * 20))
    bullish_trend = sum(1 for a in assets if str(a.get("trend", "")).upper() == "BULLISH")
    trend_score = (bullish_trend / n) * 100
    high_vol = sum(1 for a in assets if _num(a.get("vol_ratio"), 0) > 1.5)
    vol_conviction = (high_vol / n) * 100
    avg_volatility = sum(_num(a.get("volatility_20d")) for a in assets) / n
    if avg_volatility > 3: volatility_signal = -20
    elif avg_volatility < 1: volatility_signal = 10
    else: volatility_signal = 0
    raw_score = ((breadth - 50) * 0.35 + momentum_score * 0.30 + (trend_score - 50) * 0.20 + (vol_conviction - 15) * 0.10 + volatility_signal * 0.05)
    if raw_score > 20: direction = "BULLISH"
    elif raw_score > 7: direction = "SLIGHTLY BULLISH"
    elif raw_score >= -7: direction = "NEUTRAL"
    elif raw_score > -20: direction = "SLIGHTLY BEARISH"
    else: direction = "BEARISH"
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
        "summary": f"{direction} ({round(confidence)}% confidence) — {up}/{n} assets up, {avg_change:+.1f}% avg, {bullish_trend}/{n} bullish trend"
    }
