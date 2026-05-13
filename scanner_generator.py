#!/usr/bin/env python3
"""
⚡ Momentum Scanner Generator — Live Wiring
Reads all pipeline JSON outputs, computes momentum scores,
generates the scanner HTML section with real data (7 | 7 | 7).
"""

import json, sys, os
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("output")
NOW = datetime.now().strftime("%Y%m%d-%H%M%S")

# ── Scoring (mirrors sentiment.py momentum_scanner) ──
def scan_score(a):
    ch = a.get("change_pct", 0)
    trend = a.get("trend", "NEUTRAL")
    trend_bonus = {"BULLISH": 4, "NEUTRAL": 0, "BEARISH": -4}.get(trend, 0)
    
    vr = a.get("vol_ratio", 1.0)
    vol_bonus = 2 if vr > 1.5 else 0
    
    dist = a.get("dist_to_52w_high", 10)
    if dist > 5:      dist_bonus = 2
    elif dist < 2:    dist_bonus = -3
    else:             dist_bonus = 0
    
    cr = a.get("candle_ratio", 0.5)
    candle_penalty = -2 if cr > 0.8 else 0
    
    vol = a.get("volatility_20d", 0)
    vol_penalty = -max(0, (vol - 3.0)) * 1.0 if vol > 3 else 0
    
    raw = ch + trend_bonus + vol_bonus + dist_bonus + candle_penalty + vol_penalty
    return raw

def norm_score(raw):
    """Normalize to 0-100 scale"""
    return max(0, min(100, round(50 + raw * 3.0)))

def category(ns):
    if ns >= 75: return "hot"
    elif ns >= 60: return "watch"
    elif ns < 50: return "risk"
    return None

def load_latest(pattern: str):
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files:
        return []
    with open(files[0]) as f:
        data = json.load(f)
    # Handle different JSON structures
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return []

def main():
    print("⚡ Loading pipeline outputs...")
    
    all_assets = []
    sources = {
        "crypto":     "crypto_*.json",
        "commodities":"commodities_*.json",
        "indices":    "indices_*.json",
        "forex":      "forex_*.json",
        "actions":    "actions_*.json",
        "etf":        "etf_*.json",
    }
    
    for src, pattern in sources.items():
        assets = load_latest(pattern)
        for a in assets:
            a["source"] = src
        all_assets.extend(assets)
        print(f"  {src}: {len(assets)} assets")
    
    # Score & normalize
    for a in all_assets:
        a["momentum_raw"] = round(scan_score(a), 2)
        a["momentum_score"] = norm_score(a["momentum_raw"])
    
    # Categorize
    hot   = sorted([a for a in all_assets if a["momentum_score"] >= 75], key=lambda a: a["momentum_score"], reverse=True)
    watch = sorted([a for a in all_assets if 60 <= a["momentum_score"] < 75], key=lambda a: a["momentum_score"], reverse=True)
    risk  = sorted([a for a in all_assets if a["momentum_score"] < 50 or (a.get("volatility_20d", 0) > 4 and a["momentum_score"] < 55)], key=lambda a: a["momentum_score"])
    
    top_n = 7
    hot   = hot[:top_n]
    watch = watch[:top_n]
    risk  = risk[:top_n]
    
    print(f"\n  🔥 Top Momentum: {len(hot)}")
    print(f"  ⚡ Breakout Watch: {len(watch)}")
    print(f"  🛡️ Risk Flags: {len(risk)}")
    
    # ── Generate HTML cards ──
    def signal_card(title, emoji, items, score_class):
        if not items:
            return f"""<div class="signal-card"><h3>{emoji} {title}</h3><div class="signal-row"><div><span class="asset-name">—</span><span class="asset-meta">No signals in this range</span></div></div></div>"""
        
        rows = ""
        for a in items:
            name = a.get("name", a.get("symbol", "?"))
            src_tag = a.get("source", "")
            score = a["momentum_score"]
            meta_parts = []
            if a.get("trend") == "BULLISH":  meta_parts.append("trend strong")
            if a.get("vol_ratio", 0) > 1.5: meta_parts.append("volume confirmed")
            if a.get("candle_ratio", 0) > 0.8: meta_parts.append("vertical candle")
            if a.get("dist_to_52w_high", 10) < 2: meta_parts.append("near resistance")
            if a.get("volatility_20d", 0) > 3: meta_parts.append(f"vol {a['volatility_20d']:.0f}%")
            meta = " · ".join(meta_parts) if meta_parts else f"{src_tag} asset"
            
            rows += f"""<div class="signal-row">
<div><span class="asset-name">{name}</span><span class="asset-meta">{meta}</span></div>
<span class="score-pill {score_class}">{score}</span>
</div>"""
        
        return f"""<div class="signal-card"><h3>{emoji} {title}</h3>{rows}</div>"""
    
    hot_card   = signal_card("Top Momentum", "🔥", hot, "score-hot")
    watch_card = signal_card("Breakout Watch", "⚡", watch, "score-watch")
    risk_card  = signal_card("Risk Flags", "🛡️", risk, "score-risk")
    
    scanner_html = f"""<!-- ⚡ Momentum Scanner — Live Data {NOW} -->
<section id="scanner" class="scanner">
<div class="scanner-head">
<div>
<h2>⚡ Momentum Scanner</h2>
<p>Un radar transversal pour repérer les actifs qui accélèrent vraiment : tendance propre, volume confirmé, distance aux résistances et volatilité maîtrisée.</p>
<div class="formula">
<span class="chip">Trend strength</span>
<span class="chip">± Volume confirmation</span>
<span class="chip">± Resistance context</span>
<span class="chip">− Volatility noise</span>
</div>
</div>
<div class="scanner-score">
<div class="num">{len(all_assets)}</div>
<div class="label">assets scored</div>
</div>
</div>

<div class="scanner-board">
{hot_card}
{watch_card}
{risk_card}
</div>

<div class="legend">
<span>🔥 75+ strong momentum</span>
<span>⚡ 60–74 watchlist</span>
<span>🛡️ &lt;50 noisy / risky</span>
<span class="demo-tag">Live data · {NOW}</span>
</div>
</section>"""
    
    # Write scanner fragment
    frag_path = OUTPUT_DIR / f"scanner_{NOW}.html"
    frag_path.write_text(scanner_html)
    print(f"\n✅ Scanner fragment: {frag_path}")
    
    # Also write JSON
    report = {
        "generated": NOW,
        "total_assets": len(all_assets),
        "hot": [{"name": a.get("name"), "symbol": a.get("symbol"), "score": a["momentum_score"], "source": a.get("source")} for a in hot],
        "watch": [{"name": a.get("name"), "symbol": a.get("symbol"), "score": a["momentum_score"], "source": a.get("source")} for a in watch],
        "risk": [{"name": a.get("name"), "symbol": a.get("symbol"), "score": a["momentum_score"], "source": a.get("source")} for a in risk],
    }
    json_path = OUTPUT_DIR / f"scanner_{NOW}.json"
    json_path.write_text(json.dumps(report, indent=2))
    print(f"✅ Scanner JSON: {json_path}")
    
    return scanner_html

if __name__ == "__main__":
    main()
