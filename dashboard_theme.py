#!/usr/bin/env python3
"""Shared Atlas Nexus dashboard theming helpers."""

from __future__ import annotations

from html import escape

NAV_ITEMS = [
    ("Home", "index.html"),
    ("Crypto", "crypto_dashboard.html"),
    ("Commodities", "commodities_dashboard.html"),
    ("Indices", "indices_dashboard.html"),
    ("Forex", "forex_dashboard.html"),
    ("Stocks", "actions_dashboard.html"),
    ("ETF", "etf_dashboard.html"),
]

PAGE_ACCENTS = {
    "crypto": ("#38bdf8", "#818cf8", "🪙"),
    "commodities": ("#f59e0b", "#f97316", "🛢️"),
    "indices": ("#8b5cf6", "#38bdf8", "🌍"),
    "forex": ("#22c55e", "#2dd4bf", "💱"),
    "stocks": ("#4ade80", "#38bdf8", "🏛️"),
    "etf": ("#ec4899", "#8b5cf6", "💼"),
}

PAGE_SUBTITLES = {
    "crypto": "Liquid majors, trend leaders and unusual volume across 24/7 digital assets.",
    "commodities": "Hard assets, energy and grains with clean momentum and volatility reads.",
    "indices": "Global risk pulse across US, Europe and Asia benchmark markets.",
    "forex": "Compact FX board for majors, crosses and selected exotics.",
    "stocks": "Equity momentum across mega-cap tech, luxury, banks and defensives.",
    "etf": "Cross-asset themes, sectors, bonds, commodities and broad exposure.",
}

THEME_CSS = """
/* ATLAS_PREMIUM_DASHBOARD_THEME_V1 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root{
  --atlas-bg:#070914;
  --atlas-panel:rgba(15,20,32,.74);
  --atlas-panel-strong:rgba(18,24,38,.92);
  --atlas-border:rgba(148,163,184,.16);
  --atlas-border-strong:rgba(255,255,255,.14);
  --atlas-text:#f8fafc;
  --atlas-muted:#b6c2d6;
  --atlas-faint:#8290a6;
  --atlas-green:#22c55e;
  --atlas-red:#ef4444;
  --atlas-amber:#f59e0b;
  --atlas-accent:var(--accent,#38bdf8);
  --atlas-accent2:var(--accent2,#818cf8);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  font-family:'Inter',system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
  min-height:100vh;
  color:var(--atlas-text)!important;
  background:
    radial-gradient(circle at 14% -10%, color-mix(in srgb,var(--atlas-accent) 22%, transparent), transparent 34%),
    radial-gradient(circle at 90% 6%, color-mix(in srgb,var(--atlas-accent2) 18%, transparent), transparent 30%),
    linear-gradient(180deg,#070914 0%,#0a0f1d 48%,#070914 100%)!important;
  padding:0!important;
}
body:before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;
  background-image:linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),linear-gradient(90deg,rgba(255,255,255,.028) 1px, transparent 1px);
  background-size:42px 42px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.7),transparent 72%);
}
.atlas-nav{
  position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:14px min(28px,5vw);backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
  background:linear-gradient(180deg,rgba(7,9,20,.92),rgba(7,9,20,.62));border-bottom:1px solid var(--atlas-border);
}
.atlas-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--atlas-text);font-weight:900;letter-spacing:-.04em}.atlas-brand span:first-child{filter:drop-shadow(0 0 18px color-mix(in srgb,var(--atlas-accent) 50%,transparent))}.atlas-links{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.atlas-links a{color:var(--atlas-muted);text-decoration:none;font-size:.78rem;font-weight:800;padding:8px 10px;border:1px solid transparent;border-radius:999px;transition:.18s}.atlas-links a:hover,.atlas-links a.active{color:var(--atlas-text);border-color:color-mix(in srgb,var(--atlas-accent) 34%,transparent);background:color-mix(in srgb,var(--atlas-accent) 13%,transparent)}
.header{
  max-width:1240px;margin:22px auto 22px!important;padding:34px min(34px,5vw)!important;text-align:left!important;
  border:1px solid var(--atlas-border)!important;border-radius:30px!important;overflow:hidden;position:relative;
  background:linear-gradient(135deg,rgba(255,255,255,.09),rgba(255,255,255,.035)),radial-gradient(circle at 88% 5%,color-mix(in srgb,var(--atlas-accent) 28%,transparent),transparent 36%)!important;
  box-shadow:0 30px 90px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.08);
}
.header:before{content:"";position:absolute;inset:auto -70px -120px auto;width:320px;height:320px;border-radius:999px;background:var(--atlas-accent);opacity:.13;filter:blur(12px)}
.title-emoji{font-size:3.1rem!important;line-height:1!important;margin-bottom:12px!important}.header h1{font-size:clamp(2rem,5vw,4.2rem)!important;line-height:.98!important;letter-spacing:-.075em!important;font-weight:900!important;margin:0 0 12px!important;background:linear-gradient(135deg,#fff,var(--atlas-accent),var(--atlas-accent2))!important;-webkit-background-clip:text!important;background-clip:text!important;-webkit-text-fill-color:transparent!important}.header p,.header .subtitle{color:var(--atlas-muted)!important;max-width:780px!important;font-size:1rem!important;line-height:1.65!important}.atlas-page-subtitle{margin-top:8px;color:#cbd5e1!important}.live-badge{border-radius:999px!important;border:1px solid color-mix(in srgb,var(--atlas-green) 24%,transparent)!important;background:rgba(34,197,94,.10)!important;color:#bbf7d0!important;padding:7px 11px!important;font-size:.78rem!important;font-weight:850!important}
.container{width:min(1240px,calc(100% - 28px))!important;max-width:1240px!important;margin:0 auto!important;padding:0 0 28px!important}.cards,.stats-grid{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))!important;gap:14px!important;margin:0 0 22px!important}.card,.stat-card{position:relative;overflow:hidden;background:linear-gradient(180deg,rgba(255,255,255,.075),rgba(255,255,255,.035))!important;border:1px solid var(--atlas-border)!important;border-radius:22px!important;padding:20px!important;text-align:left!important;box-shadow:0 18px 55px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.06);transition:transform .18s,border-color .18s}.card:hover,.stat-card:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--atlas-accent) 45%,transparent)!important}.card .value,.stat-card .value{font-size:clamp(1.65rem,4vw,2.5rem)!important;font-weight:900!important;letter-spacing:-.06em!important}.card .label,.stat-card .label{color:var(--atlas-muted)!important;font-size:.78rem!important;font-weight:800!important;text-transform:uppercase!important;letter-spacing:.06em!important;margin-top:8px!important}
h2{color:var(--atlas-text)!important;font-size:1.18rem!important;letter-spacing:-.04em!important;font-weight:900!important;margin:28px 0 12px!important}.table-wrapper, table{box-shadow:0 20px 60px rgba(0,0,0,.24)}.table-wrapper{background:var(--atlas-panel)!important;border:1px solid var(--atlas-border)!important;border-radius:24px!important;overflow:hidden!important;margin-bottom:24px!important}table{width:100%!important;border-collapse:separate!important;border-spacing:0!important;background:var(--atlas-panel)!important;border:1px solid var(--atlas-border)!important;border-radius:22px!important;overflow:hidden!important;font-size:.9rem!important}th{position:sticky;top:58px;z-index:3;background:rgba(12,18,30,.94)!important;color:var(--atlas-accent)!important;border-bottom:1px solid var(--atlas-border)!important;text-transform:uppercase!important;letter-spacing:.08em!important;font-size:.72rem!important;font-weight:900!important;padding:13px 14px!important;white-space:nowrap!important}td{padding:13px 14px!important;border-bottom:1px solid rgba(148,163,184,.095)!important;color:#dbeafe!important;vertical-align:middle!important}tr:hover td{background:rgba(255,255,255,.045)!important}td:first-child,th:first-child{position:sticky;left:0;background:linear-gradient(90deg,rgba(12,18,30,.98),rgba(12,18,30,.92))!important;z-index:4}td strong{color:var(--atlas-text)!important}.badge,.live-badge{white-space:nowrap}.badge{border-radius:999px!important;padding:5px 9px!important;font-size:.72rem!important;font-weight:900!important}.sentiment-banner{border-radius:24px!important;margin:0 0 22px!important;background:linear-gradient(135deg,rgba(255,255,255,.075),rgba(255,255,255,.035))!important;border:1px solid var(--atlas-border)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}.footer,footer{width:min(1240px,calc(100% - 28px));margin:26px auto!important;padding:22px!important;color:var(--atlas-muted)!important;text-align:center!important;border:1px solid var(--atlas-border)!important;border-radius:22px!important;background:rgba(255,255,255,.035)!important}.atlas-scroll-hint{display:none;color:var(--atlas-faint);font-size:.76rem;font-weight:800;margin:-10px 0 10px}.up,.gainer,.positive{color:var(--atlas-green)!important}.down,.loser,.negative{color:var(--atlas-red)!important}
@media(max-width:760px){.atlas-nav{align-items:flex-start;flex-direction:column;padding:12px 14px}.atlas-links{width:100%;overflow-x:auto;flex-wrap:nowrap;justify-content:flex-start;padding-bottom:3px}.atlas-links a{flex:0 0 auto}.header{width:min(100% - 22px,1240px)!important;margin:14px auto 18px!important;border-radius:24px!important}.container{width:min(100% - 22px,1240px)!important}.atlas-scroll-hint{display:block}.table-wrapper,div[style*="overflow-x"]{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important}table{min-width:760px!important}.card,.stat-card{padding:17px!important}.section{grid-template-columns:1fr!important}.header h1{font-size:clamp(2rem,12vw,3.3rem)!important}}
"""

def _nav(active: str, emoji: str) -> str:
    active_norm = active.lower()
    links = []
    for label, href in NAV_ITEMS:
        cls = ' class="active"' if label.lower() == active_norm or (active_norm == 'stocks' and label == 'Stocks') else ''
        links.append(f'<a{cls} href="{href}">{escape(label)}</a>')
    return f'''<nav class="atlas-nav" aria-label="Atlas Nexus dashboard navigation"><a class="atlas-brand" href="index.html"><span>🔮</span><span>Atlas Nexus</span></a><div class="atlas-links">{''.join(links)}</div></nav>'''

def enhance_dashboard_html(html: str, page_key: str) -> str:
    """Inject premium shared CSS/navigation into generated dashboard HTML."""
    key = page_key.lower().replace('actions', 'stocks')
    accent, accent2, emoji = PAGE_ACCENTS.get(key, ("#38bdf8", "#818cf8", "🔮"))
    css = THEME_CSS.replace("var(--accent,#38bdf8)", accent).replace("var(--accent2,#818cf8)", accent2)
    html = html.replace("</style>", css + "\n</style>", 1) if "ATLAS_PREMIUM_DASHBOARD_THEME_V1" not in html else html
    if '<nav class="atlas-nav"' not in html:
        html = html.replace("<body>", "<body>\n" + _nav('Stocks' if key == 'stocks' else page_key.title(), emoji), 1)
    subtitle = PAGE_SUBTITLES.get(key)
    if subtitle and "atlas-page-subtitle" not in html:
        marker = "</div>\n<div class=\"container\">"
        if marker in html:
            html = html.replace(marker, f'<p class="atlas-page-subtitle">{escape(subtitle)}</p>{marker}', 1)
        else:
            html = html.replace("</div>\n    \n    <div", f'<p class="atlas-page-subtitle">{escape(subtitle)}</p></div>\n    \n    <div', 1)
    if "atlas-scroll-hint" not in html:
        html = html.replace("<table", '<div class="atlas-scroll-hint">Swipe sideways to inspect all columns →</div>\n<table', 1)
    return html
