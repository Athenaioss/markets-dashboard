# Atlas Nexus — Markets Dashboard

Live multi-asset market dashboards built as a static GitHub Pages site with automated data refreshes.

**Live demo:** https://atlasnexusops.github.io/markets-dashboard/

## What it is

Atlas Nexus Markets Dashboard is a public proof-of-work project for operational data products:

- fetch market data from public APIs;
- normalize multiple asset classes into generated JSON/CSV/HTML artifacts;
- render lightweight static dashboards on GitHub Pages;
- refresh automatically through a Hermes cron job;
- expose a compact market-pressure radar called **Hawkeye V4**.

The project is designed as a portfolio-grade example of a maintainable static data product: no backend server is required for visitors, while the data pipeline can keep publishing updated pages through Git commits.

## Dashboards

- **Home / Hawkeye radar:** https://atlasnexusops.github.io/markets-dashboard/
- **Commodities:** https://atlasnexusops.github.io/markets-dashboard/commodities_dashboard.html
- **Indices:** https://atlasnexusops.github.io/markets-dashboard/indices_dashboard.html
- **Forex:** https://atlasnexusops.github.io/markets-dashboard/forex_dashboard.html
- **Actions / Stocks:** https://atlasnexusops.github.io/markets-dashboard/actions_dashboard.html
- **ETF:** https://atlasnexusops.github.io/markets-dashboard/etf_dashboard.html
- **Crypto:** https://atlasnexusops.github.io/markets-dashboard/crypto_dashboard.html

## Key features

- Multi-asset coverage: commodities, indices, forex, stocks, ETFs and crypto.
- Generated static pages: fast, cheap to host and simple to audit.
- Export artifacts under `output/`: JSON, CSV and HTML snapshots.
- Shared dashboard theme and generated category pages.
- **Hawkeye V4** market-pressure radar for manual inspection workflows.
- Cron-based refresh pipeline suitable for GitHub Pages deployment.

## Hawkeye V4 boundary

Hawkeye V4 is a market-pressure radar, not a trade execution system.

It is intended to answer:

> Where is notable directional pressure worth manual inspection on xStation, TradingView or another charting surface?

It does **not** provide financial advice, trade tickets, target prices, stop losses, position sizing or execution instructions.

## Repository structure

```text
.
├── index.html                    # Home dashboard / Hawkeye radar
├── *_dashboard.html              # Generated category dashboards
├── *_pipeline.py                 # Per-asset-class data pipelines
├── scanner_generator.py          # Home scanner generation
├── scanner_inject.py             # Atomic scanner injection into index.html
├── hawkeye_core.py               # Shared Hawkeye V4 scoring/radar core
├── sentiment.py                  # Shared category-page pressure components
├── dashboard_theme.py            # Shared static dashboard styling helpers
└── output/                       # Generated JSON/CSV/HTML snapshots
```

## Local usage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # if present / needed by the active pipeline environment

python3 commodities_pipeline.py
python3 indices_pipeline.py
python3 forex_pipeline.py
python3 actions_pipeline.py
python3 etf_pipeline.py
python3 crypto_pipeline.py
python3 scanner_inject.py
```

Then serve locally:

```bash
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000/
```

## Publication workflow

The live site is served by GitHub Pages from the `main` branch.

Typical update flow:

```bash
python3 -m py_compile hawkeye_core.py scanner_generator.py scanner_inject.py sentiment.py *_pipeline.py
python3 commodities_pipeline.py
python3 indices_pipeline.py
python3 forex_pipeline.py
python3 actions_pipeline.py
python3 etf_pipeline.py
python3 crypto_pipeline.py
python3 scanner_inject.py

git status --short
git add .
git commit -m "data: refresh market dashboard YYYYMMDD-HHMMSS"
git push origin main
```

A Hermes cron job currently handles recurring refreshes.

## Maintenance checklist

Before pushing UI/source changes:

- patch generators or shared helpers first, not only rendered HTML;
- regenerate affected artifacts;
- compile modified Python files;
- parse generated HTML for basic sanity;
- verify exact visible strings on every affected page;
- keep commits scoped: avoid mixing unrelated market refreshes with UI-only changes when practical;
- check GitHub Pages deployment and fetch the live URL with a cache-busting query parameter.

## Commercial relevance

This repository is part of the Atlas Nexus public portfolio. It demonstrates the type of client work Atlas Nexus can deliver:

- live dashboards;
- automated data pipelines;
- market and operations monitoring;
- static reporting surfaces;
- maintainable agent-assisted refresh workflows.

For client work, see the Atlas Nexus landing page:

https://atlasnexusops.github.io/

## Disclaimer

This project is for informational and technical demonstration purposes only. Market data may be delayed, incomplete or unavailable. Nothing in this repository or dashboard is financial advice.