#!/usr/bin/env python3
"""
🦅 Hawkeye V4 — multi-asset market pressure radar.

Not a trade placement tool. It highlights directional pressure that deserves
manual inspection on xStation / TradingView.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from html import escape

from hawkeye_core import analyze_assets, safe_price
from market_sessions import MARKET_STATE_CSS, market_session_badge
from tradingview_links import TV_LINK_CSS, tradingview_link

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
GENERATED_AT = datetime.now().astimezone()
NOW = GENERATED_AT.strftime("%Y%m%d-%H%M%S")
UPDATED_AT_LABEL = GENERATED_AT.strftime("%d/%m/%Y %H:%M %Z")


def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    tmp.replace(path)


def load_latest(pattern: str):
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files:
        return []
    with open(files[0]) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return []


def score_class(score: int) -> str:
    if score >= 75: return "score-hot"
    if score >= 60: return "score-warm"
    return "score-muted"


def market_for_source(source: str) -> str:
    return {"actions": "stocks"}.get(source, source)


def direction_title(direction: str) -> str:
    if direction == "bullish": return "Bullish pressure"
    if direction == "bearish": return "Bearish pressure"
    return "Mixed / Neutral"


def direction_emoji(direction: str) -> str:
    return {"bullish": "📈", "bearish": "📉", "mixed": "⚪"}.get(direction, "⚪")


def row_html(a: dict) -> str:
    market = market_for_source(a.get("source", ""))
    direction = direction_title(a["direction"])
    ext = a.get("extension_atr", 0)
    warning = " · extension warning" if 1.5 < ext <= 2.5 else " · shock/extended" if ext > 2.5 else ""
    rel = f"<span style='color:#a7f3d0'>{escape(a['relative_label'])}</span>" if a.get("relative_label") else ""
    participation = escape(a.get("participation_label") or "Participation n/a")
    return f"""<div class="signal-row" data-market="{escape(market)}">
<div>
<span class="asset-name">{escape(a['name'])}</span>
<span class="asset-tag">{escape(direction)}</span>
<span class="asset-meta">{escape(a.get('source',''))} · {escape(a['regime'])} · {escape(a['signal_family'])}{warning}</span>
<span class="asset-levels">
<span style="color:#bae6fd">🎟️ {escape(a['price_label'])}</span>
{market_session_badge(market)}
{tradingview_link(a.get("symbol"), a.get("source", ""))}
{rel}
</span>
</div>
<div class="score-box">
<span class="score-pill {score_class(a['score'])}">{a['score']}/100</span>
<div class="score-meta">Net {a['net_pressure']:+d} · {escape(a['symbol'])}</div>
<div class="status-mini" style="color:{a['color']}">{escape(a['label']).replace("Active pressure", "Active")}</div>
</div>
</div>"""


def card_html(title: str, emoji: str, rows: list[dict], empty: str) -> str:
    if not rows:
        body = f'<div class="no-signal">{escape(empty)}</div>'
    else:
        body = "".join(row_html(x) for x in rows)
    return f'<div class="signal-card"><h3>{emoji} {escape(title)} ({len(rows)})</h3>{body}</div>'


def build_pressure_lists(analyses: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    usable = [a for a in analyses if a["score"] >= 40 and a["tier"] != "DEGRADED"]
    bullish = [a for a in usable if a["direction"] == "bullish" and a["score"] >= 60]
    bearish = [a for a in usable if a["direction"] == "bearish" and a["score"] >= 60]
    degraded = [a for a in analyses if a["tier"] == "DEGRADED"]
    bullish.sort(key=lambda x: x["score"], reverse=True)
    bearish.sort(key=lambda x: x["score"], reverse=True)
    degraded.sort(key=lambda x: x["name"])
    return bullish[:7], bearish[:7], degraded[:5]


def degraded_card(rows: list[dict]) -> str:
    if not rows:
        return ""
    body = ""
    for a in rows:
        issues = ", ".join(a["data_quality"].get("issues", [])) or "quality gate"
        body += f"""<div class="signal-row" data-market="{escape(market_for_source(a.get('source','')))}">
<div><span class="asset-name">{escape(a['name'])}</span><span class="asset-tag">Degraded</span><span class="asset-meta">{escape(issues)}</span></div>
<div style="text-align:right"><span class="score-pill score-muted">n/a</span><div style="font-size:.7em;color:#94a3b8;margin-top:2px">Manual data check</div></div>
</div>"""
    return f'<div class="signal-card mixed-card"><h3>🧪 Data degraded ({len(rows)})</h3>{body}</div>'


def main(run_id: str | None = None):
    run_id = run_id or NOW
    print("🦅 Hawkeye V4 — Market Pressure Radar")
    print("-" * 50)
    sources = {
        "crypto": "crypto_*.json", "commodities": "commodities_*.json",
        "indices": "indices_*.json", "forex": "forex_*.json",
        "actions": "actions_*.json", "etf": "etf_*.json",
    }
    all_assets = []
    for src, pattern in sources.items():
        assets = load_latest(pattern)
        for a in assets:
            a["source"] = src
        all_assets.extend(assets)
        print(f"  {src}: {len(assets)} assets")

    assets_clean = []
    for a in all_assets:
        ch = a.get("change_pct", a.get("change_24h", 0))
        try:
            absurd = abs(float(ch)) >= 80
        except (TypeError, ValueError):
            absurd = False
        if safe_price(a) and not absurd:
            assets_clean.append(a)
    skipped = len(all_assets) - len(assets_clean)
    if skipped:
        print(f"  ⚠️ Filtered {skipped} artifacts")

    analyses = analyze_assets(assets_clean)
    bullish, bearish, degraded = build_pressure_lists(analyses)
    dist = {
        "extreme": sum(1 for a in analyses if a["score"] >= 90),
        "strong": sum(1 for a in analyses if 75 <= a["score"] < 90),
        "active": sum(1 for a in analyses if 60 <= a["score"] < 75),
        "watch": sum(1 for a in analyses if 40 <= a["score"] < 60),
        "weak": sum(1 for a in analyses if a["score"] < 40),
        "degraded": len(degraded),
    }
    print(f"  📈 Bullish pressure: {len(bullish)}")
    print(f"  📉 Bearish pressure: {len(bearish)}")
    print(f"  ⚡ Extreme count: {dist['extreme']}")

    scanner_html = f"""<!-- 🦅 Hawkeye V4 — run_id:{escape(run_id)} — {NOW} -->
<section id="scanner" class="scanner hawkeye-v4" data-run-id="{escape(run_id)}">
<style>{MARKET_STATE_CSS}</style>
<div class="scanner-head">
<div>
<h2>🦅 Hawkeye V4 — Market Pressure Radar</h2>
<p class="scanner-sub">Top bullish and bearish assets ranked by composite pressure score — built for quick manual chart inspection. Each slot shows indicative market state: Ouvert, Clos, or Fermé.</p>
<div class="scanner-quicklegend"><span>60–74 Active</span><span>75+ Strong</span><span>90+ Extreme</span><span>Chart ↗ opens TradingView</span></div>
</div>
<div class="scanner-score"><div class="num">{len(analyses)}</div><div class="label">assets scanned</div></div>
</div>
<div class="scanner-board" style="grid-template-columns:repeat(2,1fr)">
{card_html('Bullish pressure', '📈', bullish, 'No active bullish pressure')}
{card_html('Bearish pressure', '📉', bearish, 'No active bearish pressure')}
{degraded_card(degraded)}
</div>
<div class="legend">
<span>0-39 Weak</span><span>40-59 Watch</span><span>60-74 Active pressure</span><span>75-89 Strong pressure</span><span>90-100 Extreme pressure</span>
<span class="demo-tag">Updated {UPDATED_AT_LABEL}</span>
</div>
</section>"""

    frag_path = OUTPUT_DIR / f"scanner_{run_id}.html"
    json_path = OUTPUT_DIR / f"scanner_{run_id}.json"
    atomic_write(frag_path, scanner_html)
    report = {
        "run_id": run_id,
        "generated": NOW,
        "scoring": "Hawkeye V4 — market pressure radar /100",
        "total": len(analyses),
        "distribution": dist,
        "bullish_pressure": [{"name": a["name"], "score": a["score"], "regime": a["regime"], "family": a["signal_family"], "reference_price": a["price_label"]} for a in bullish],
        "bearish_pressure": [{"name": a["name"], "score": a["score"], "regime": a["regime"], "family": a["signal_family"], "reference_price": a["price_label"]} for a in bearish],
        "degraded": [{"name": a["name"], "issues": a["data_quality"].get("issues", [])} for a in degraded],
    }
    atomic_write(json_path, json.dumps(report, indent=2))
    print(f"\n✅ Scanner: {frag_path}")
    return scanner_html


if __name__ == "__main__":
    main()
