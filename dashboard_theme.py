#!/usr/bin/env python3
"""Shared Atlas Nexus dashboard theming helpers."""

from __future__ import annotations

from html import escape
from tradingview_links import TV_LINK_CSS

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
/* ATLAS_PREMIUM_DASHBOARD_THEME_V1 — DUAL THEME (light default + dark toggle) */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html{scroll-behavior:smooth}
*{box-sizing:border-box}
/* ── LIGHT THEME (default) ── */
:root{
  --atlas-bg:#f8fafc;
  --atlas-panel:#ffffff;
  --atlas-panel-strong:#f1f5f9;
  --atlas-border:rgba(0,0,0,.12);
  --atlas-border-strong:rgba(0,0,0,.18);
  --atlas-text:#0f172a;
  --atlas-muted:#1e293b;
  --atlas-faint:#334155;
  --atlas-green:#16a34a;
  --atlas-red:#dc2626;
  --atlas-amber:#d97706;
  --atlas-accent:var(--accent,#0284c7);
  --atlas-accent2:var(--accent2,#7c3aed);
  --atlas-card-bg:rgba(255,255,255,.95);
  --atlas-card-border:rgba(0,0,0,.08);
  --atlas-shadow:0 8px 40px rgba(0,0,0,.08);
  --atlas-th-bg:rgba(248,250,252,.98);
  --atlas-td-color:#1e293b;
  --atlas-nav-bg:linear-gradient(180deg,rgba(248,250,252,.95),rgba(248,250,252,.75));
  --atlas-nav-border:rgba(0,0,0,.08);
  --atlas-body-bg:linear-gradient(180deg,#f8fafc 0%,#f1f5f9 48%,#f8fafc 100%);
  --atlas-grid-line:rgba(0,0,0,.04);
  --atlas-grid-line2:rgba(0,0,0,.03);
  --atlas-hero-bg:linear-gradient(135deg,rgba(255,255,255,.95),rgba(241,245,249,.9)),radial-gradient(circle at 88% 5%,color-mix(in srgb,var(--atlas-accent) 15%,transparent),transparent 36%);
  --atlas-hero-shadow:0 8px 40px rgba(0,0,0,.06),inset 0 1px 0 rgba(0,0,0,.04);
  --atlas-card-gradient:linear-gradient(180deg,rgba(255,255,255,.95),rgba(241,245,249,.9));
  --atlas-card-inset:inset 0 1px 0 rgba(255,255,255,.8);
  --unusual-bg:linear-gradient(135deg,rgba(245,158,11,.08),rgba(255,255,255,.9) 52%,rgba(239,68,68,.04));
  --unusual-border:rgba(245,158,11,.26);
  --unusual-card-bg:rgba(255,255,255,.7);
  --hawkeye-bg:linear-gradient(135deg,rgba(241,245,249,.95),rgba(248,250,252,.9) 48%,rgba(254,243,199,.5));
  --hawkeye-border:rgba(56,189,248,.25);
  --signal-card-bg:rgba(255,255,255,.7);
  --signal-row-bg:rgba(248,250,252,.7);
}
/* ── DARK THEME ── */
[data-theme="dark"]{
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
  --atlas-card-bg:rgba(255,255,255,.04);
  --atlas-card-border:rgba(148,163,184,.16);
  --atlas-shadow:0 18px 55px rgba(0,0,0,.22);
  --atlas-th-bg:rgba(12,18,30,.94);
  --atlas-td-color:#dbeafe;
  --atlas-nav-bg:linear-gradient(180deg,rgba(7,9,20,.92),rgba(7,9,20,.62));
  --atlas-nav-border:rgba(148,163,184,.16);
  --atlas-body-bg:radial-gradient(circle at 14% -10%,color-mix(in srgb,var(--atlas-accent) 22%,transparent),transparent 34%),radial-gradient(circle at 90% 6%,color-mix(in srgb,var(--atlas-accent2) 18%,transparent),transparent 30%),linear-gradient(180deg,#070914 0%,#0a0f1d 48%,#070914 100%);
  --atlas-grid-line:rgba(255,255,255,.035);
  --atlas-grid-line2:rgba(255,255,255,.028);
  --atlas-hero-bg:linear-gradient(135deg,rgba(255,255,255,.09),rgba(255,255,255,.035)),radial-gradient(circle at 88% 5%,color-mix(in srgb,var(--atlas-accent) 28%,transparent),transparent 36%);
  --atlas-hero-shadow:0 30px 90px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.08);
  --atlas-card-gradient:linear-gradient(180deg,rgba(255,255,255,.075),rgba(255,255,255,.035));
  --atlas-card-inset:inset 0 1px 0 rgba(255,255,255,.06);
  --unusual-bg:linear-gradient(135deg,rgba(245,158,11,.13),rgba(15,23,42,.72) 52%,rgba(239,68,68,.08));
  --unusual-border:rgba(245,158,11,.26);
  --unusual-card-bg:rgba(7,9,20,.38);
  --hawkeye-bg:linear-gradient(135deg,rgba(16,22,34,.92),rgba(18,14,33,.86) 48%,rgba(29,22,10,.76));
  --hawkeye-border:rgba(56,189,248,.20);
  --signal-card-bg:rgba(7,9,20,.38);
  --signal-row-bg:rgba(255,255,255,.035);
}

/* ── THEME TOGGLE BUTTON ── */
.theme-toggle-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:999px;border:1px solid var(--atlas-border);background:var(--atlas-panel);cursor:pointer;font-size:.78em;font-weight:700;color:var(--atlas-muted);transition:all .2s;margin-left:4px;white-space:nowrap}
.theme-toggle-btn:hover{border-color:var(--atlas-accent);color:var(--atlas-text)}
[data-theme="light"] .icon-moon{display:none}
[data-theme="dark"] .icon-sun{display:none}

/* ── BODY ── */
body{
  font-family:'Inter',system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
  min-height:100vh;
  color:var(--atlas-text)!important;
  background:var(--atlas-body-bg)!important;
  padding:0!important;
  transition:background .5s ease,color .4s ease;
}
{TV_LINK_CSS}
[data-theme="dark"] body:before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;
  background-image:linear-gradient(var(--atlas-grid-line) 1px,transparent 1px),linear-gradient(90deg,var(--atlas-grid-line2) 1px,transparent 1px);
  background-size:42px 42px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.7),transparent 72%);
}
[data-theme="light"] body:before{display:none!important}

/* ── NAV ── */
.atlas-nav{
  position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:14px min(28px,5vw);backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
  background:var(--atlas-nav-bg)!important;border-bottom:1px solid var(--atlas-nav-border);
  transition:background .4s ease,border-color .4s ease;
}
.atlas-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--atlas-text);font-weight:900;letter-spacing:-.04em}.atlas-brand span:first-child{filter:drop-shadow(0 0 18px color-mix(in srgb,var(--atlas-accent) 50%,transparent))}.atlas-links{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.atlas-links a{color:var(--atlas-muted);text-decoration:none;font-size:.78rem;font-weight:800;padding:8px 10px;border:1px solid transparent;border-radius:999px;transition:.18s}.atlas-links a:hover,.atlas-links a.active{color:var(--atlas-text);border-color:color-mix(in srgb,var(--atlas-accent) 34%,transparent);background:color-mix(in srgb,var(--atlas-accent) 13%,transparent)}

/* ── HEADER ── */
.header{
  max-width:1240px;margin:22px auto 22px!important;padding:34px min(34px,5vw)!important;text-align:left!important;
  border:1px solid var(--atlas-border)!important;border-radius:30px!important;overflow:hidden;position:relative;
  background:var(--atlas-hero-bg)!important;
  box-shadow:var(--atlas-hero-shadow);
  transition:background .5s ease,box-shadow .5s ease;
}
.header:before{content:"";position:absolute;inset:auto -70px -120px auto;width:320px;height:320px;border-radius:999px;background:var(--atlas-accent);opacity:.13;filter:blur(12px)}
.title-emoji{font-size:3.1rem!important;line-height:1!important;margin-bottom:12px!important}.header h1{font-size:clamp(2rem,5vw,4.2rem)!important;line-height:.98!important;letter-spacing:-.075em!important;font-weight:900!important;margin:0 0 12px!important;background:linear-gradient(135deg,var(--atlas-accent),var(--atlas-accent2))!important;-webkit-background-clip:text!important;background-clip:text!important;-webkit-text-fill-color:transparent!important}.header p,.header .subtitle{color:var(--atlas-muted)!important;max-width:780px!important;font-size:1rem!important;line-height:1.65!important}.atlas-page-subtitle{margin-top:8px;color:var(--atlas-muted)!important}.live-badge{border-radius:999px!important;border:1px solid color-mix(in srgb,var(--atlas-green) 24%,transparent)!important;background:rgba(34,197,94,.10)!important;color:var(--atlas-green)!important;padding:7px 11px!important;font-size:.78rem!important;font-weight:850!important}
[data-theme="dark"] .live-badge{color:#bbf7d0!important}

/* ── CONTAINER & CARDS ── */
.container{width:min(1240px,calc(100% - 28px))!important;max-width:1240px!important;margin:0 auto!important;padding:0 0 28px!important}.cards,.stats-grid{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))!important;gap:14px!important;margin:0 0 22px!important}.card,.stat-card{position:relative;overflow:hidden;background:var(--atlas-card-gradient)!important;border:1px solid var(--atlas-card-border)!important;border-radius:22px!important;padding:20px!important;text-align:left!important;box-shadow:var(--atlas-shadow),var(--atlas-card-inset);transition:transform .18s,border-color .18s,background .4s ease}.card:hover,.stat-card:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--atlas-accent) 45%,transparent)!important}.card .value,.stat-card .value{font-size:clamp(1.65rem,4vw,2.5rem)!important;font-weight:900!important;letter-spacing:-.06em!important;color:var(--atlas-text)!important}.card .label,.stat-card .label{color:var(--atlas-muted)!important;font-size:.78rem!important;font-weight:800!important;text-transform:uppercase!important;letter-spacing:.06em!important;margin-top:8px!important}

/* ── TABLES ── */
h2{color:var(--atlas-text)!important;font-size:1.18rem!important;letter-spacing:-.04em!important;font-weight:900!important;margin:28px 0 12px!important}.table-wrapper,table{box-shadow:var(--atlas-shadow)}.table-wrapper{background:var(--atlas-panel)!important;border:1px solid var(--atlas-border)!important;border-radius:24px!important;overflow:hidden!important;margin-bottom:24px!important}table{width:100%!important;border-collapse:separate!important;border-spacing:0!important;background:var(--atlas-panel)!important;border:1px solid var(--atlas-border)!important;border-radius:22px!important;overflow:hidden!important;font-size:.9rem!important}th{position:sticky;top:58px;z-index:3;background:var(--atlas-th-bg)!important;color:var(--atlas-accent)!important;border-bottom:1px solid var(--atlas-border)!important;text-transform:uppercase!important;letter-spacing:.08em!important;font-size:.72rem!important;font-weight:900!important;padding:13px 14px!important;white-space:nowrap!important}td{padding:13px 14px!important;border-bottom:1px solid var(--atlas-border)!important;color:var(--atlas-td-color)!important;vertical-align:middle!important}tr:hover td{background:var(--atlas-panel-strong)!important}td:first-child,th:first-child{position:sticky;left:0;background:var(--atlas-th-bg)!important;z-index:4}td strong{color:var(--atlas-text)!important}.badge,.live-badge{white-space:nowrap}.badge{border-radius:999px!important;padding:5px 9px!important;font-size:.72rem!important;font-weight:900!important;color:var(--atlas-text)!important}

[data-theme="dark"] .badge{color:#cbd5e1!important}
[data-theme="dark"] td strong{color:#f8fafc!important}
[data-theme="dark"] td{color:#dbeafe!important}
[data-theme="dark"] th{background:rgba(12,18,30,.94)!important}
[data-theme="dark"] td:first-child, [data-theme="dark"] th:first-child{background:linear-gradient(90deg,rgba(12,18,30,.98),rgba(12,18,30,.92))!important}
[data-theme="dark"] tr:hover td{background:rgba(255,255,255,.045)!important}

.sentiment-banner{border-radius:24px!important;margin:0 0 22px!important;background:var(--atlas-panel)!important;border:1px solid var(--atlas-border)!important;box-shadow:var(--atlas-shadow)}.footer,footer{width:min(1240px,calc(100% - 28px));margin:26px auto!important;padding:22px!important;color:var(--atlas-muted)!important;text-align:center!important;border:1px solid var(--atlas-border)!important;border-radius:24px!important}

/* ATLAS_LEADERBOARD_TABLE_REPAIR_20260517 */
.table-wrapper{overflow:hidden!important}
.table-wrapper>div,div[style*="overflow-x"]{max-width:100%!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch!important}
.table-wrapper table{min-width:860px!important;width:max-content!important;max-width:none!important;border-collapse:separate!important}
.table-wrapper th,.table-wrapper td{white-space:nowrap!important}
.table-wrapper td:first-child,.table-wrapper th:first-child{position:static!important;left:auto!important;z-index:auto!important;background:transparent!important}
.table-wrapper td:first-child strong{white-space:nowrap!important}

@media(max-width:760px){.atlas-nav{align-items:flex-start;flex-direction:column;padding:12px 14px}.atlas-links{width:100%;overflow-x:auto;flex-wrap:nowrap;justify-content:flex-start;padding-bottom:3px}.atlas-links a{flex:0 0 auto}.header{width:min(100% - 22px,1240px)!important;margin:14px auto 18px!important;border-radius:24px!important}.container{width:min(100% - 22px,1240px)!important}.atlas-scroll-hint{display:block}.table-wrapper,div[style*="overflow-x"]{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important}table{min-width:760px!important}.card,.stat-card{padding:17px!important}.section{grid-template-columns:1fr!important}.header h1{font-size:clamp(2rem,12vw,3.3rem)!important}}
"""

def _nav(active: str, emoji: str) -> str:
    active_norm = active.lower()
    links = []
    for label, href in NAV_ITEMS:
        cls = ' class="active"' if label.lower() == active_norm or (active_norm == 'stocks' and label == 'Stocks') else ''
        links.append(f'<a{cls} href="{href}">{escape(label)}</a>')
    toggle_btn = '<button class="theme-toggle-btn" id="themeToggle" aria-label="Toggle theme"><span class="icon-sun">☀️</span><span class="icon-moon">🌙</span></button>'
    return f'<nav class="atlas-nav" aria-label="Atlas Nexus dashboard navigation"><a class="atlas-brand" href="index.html"><span>🔮</span><span>Atlas Nexus</span></a><div class="atlas-links">{"" .join(links)}{toggle_btn}</div></nav>'

def enhance_dashboard_html(html: str, page_key: str) -> str:
    """Inject premium shared CSS/navigation + dual-theme toggle into generated dashboard HTML."""
    key = page_key.lower().replace('actions', 'stocks')
    accent, accent2, emoji = PAGE_ACCENTS.get(key, ("#38bdf8", "#818cf8", "🔮"))
    css = THEME_CSS.replace("var(--accent,#38bdf8)", accent).replace("var(--accent2,#818cf8)", accent2)
    html = html.replace("</style>", css + "\n</style>", 1) if "ATLAS_PREMIUM_DASHBOARD_THEME_V1" not in html else html
    # Add data-theme attribute for dual theme
    if 'data-theme=' not in html:
        html = html.replace('<html lang="en">', '<html lang="en" data-theme="light">', 1)
    if '<nav class="atlas-nav"' not in html:
        html = html.replace("<body>", "<body>\n" + _nav('Stocks' if key == 'stocks' else page_key.title(), emoji), 1)
    # Inject theme toggle localStorage script before </body>
    if 'atlas-theme' not in html:
        theme_script = """<script>
// Dual theme toggle with localStorage
(function(){var h=document.documentElement;var b=document.getElementById('themeToggle');var s=localStorage.getItem('atlas-theme')||'light';h.setAttribute('data-theme',s);b.addEventListener('click',function(){var n=h.getAttribute('data-theme')==='dark'?'light':'dark';h.setAttribute('data-theme',n);localStorage.setItem('atlas-theme',n)})})();
</script>"""
        html = html.replace("</body>", theme_script + "\n</body>", 1)
    subtitle = PAGE_SUBTITLES.get(key)
    if subtitle and "atlas-page-subtitle" not in html:
        marker = "</div>\n<div class=\"container\">"
        if marker in html:
            html = html.replace(marker, f'<p class="atlas-page-subtitle">{escape(subtitle)}</p>{marker}', 1)
        else:
            html = html.replace("</div>\n    \n    <div", f'<p class="atlas-page-subtitle">{escape(subtitle)}</p></div>\n    \n    <div', 1)
    if "atlas-scroll-hint" not in html:
        html = html.replace("<table", '<div class="atlas-scroll-hint">Swipe sideways to inspect all columns →</div>\n<table', 1)
    # Crypto: remove body page gradient + grid overlay, keep header gradient
    if key == "crypto":
        html = html.replace(
            "background:\n    radial-gradient(circle at 14% -10%, color-mix(in srgb,var(--atlas-accent) 22%, transparent), transparent 34%),\n    radial-gradient(circle at 90% 6%, color-mix(in srgb,var(--atlas-accent2) 18%, transparent), transparent 30%),\n    linear-gradient(180deg,#070914 0%,#0a0f1d 48%,#070914 100%)!important;",
            "background:#070914!important;",
        )
        # Hide grid overlay
        html = html.replace("</head>", "<style>body:before{display:none!important}</style>\n</head>", 1)
    return html
