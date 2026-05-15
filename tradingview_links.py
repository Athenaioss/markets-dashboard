"""
TradingView link helpers for Atlas Nexus market dashboards.

These helpers intentionally create chart-inspection links only. They do not
represent execution, order placement, or investment advice.
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote


YAHOO_TO_TV = {
    "^GSPC": "SP:SPX",
    "^DJI": "DJ:DJI",
    "^IXIC": "NASDAQ:NDX",
    "^RUT": "TVC:RUT",
    "^FTSE": "TVC:UKX",
    "^FCHI": "EURONEXT:PX1",
    "^GDAXI": "XETR:DAX",
    "^STOXX50E": "TVC:SX5E",
    "^N225": "TSE:NI225",
    "^HSI": "HSI:HSI",
    "GC=F": "COMEX:GC1!",
    "SI=F": "COMEX:SI1!",
    "HG=F": "COMEX:HG1!",
    "CL=F": "NYMEX:CL1!",
    "BZ=F": "NYMEX:BRN1!",
    "NG=F": "NYMEX:NG1!",
    "ZC=F": "CBOT:ZC1!",
    "ZW=F": "CBOT:ZW1!",
    "ZS=F": "CBOT:ZS1!",
    "KC=F": "ICEUS:KC1!",
    "SB=F": "ICEUS:SB1!",
    "CC=F": "ICEUS:CC1!",
    "CT=F": "ICEUS:CT1!",
}

NASDAQ = {"AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ASML", "NVO", "QQQ", "TLT", "SOXX", "SMH", "ICLN", "ARKK"}
NYSE = {"JPM", "BAC", "GS", "V", "MA", "JNJ", "UNH", "LLY", "WMT", "KO", "PG", "MCD", "NKE", "CAT", "BA", "GE", "XOM", "SHEL"}
AMEX = {"SPY", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV", "GLD", "SLV", "VNQ"}
PARIS = {"MC.PA": "EURONEXT:MC", "RMS.PA": "EURONEXT:RMS"}
LONDON = {"SHEL.L": "LSE:SHEL"}


def _clean_symbol(symbol: str | None) -> str:
    return str(symbol or "").strip().upper()


def tradingview_symbol(symbol: str | None, source: str | None = "") -> str:
    sym = _clean_symbol(symbol)
    src = str(source or "").strip().lower()
    if not sym:
        return ""
    if sym in YAHOO_TO_TV:
        return YAHOO_TO_TV[sym]
    if sym in PARIS:
        return PARIS[sym]
    if sym in LONDON:
        return LONDON[sym]
    if sym.endswith("=X"):
        return f"FX:{sym.replace('=X', '')}"
    if sym.endswith("-USD"):
        sym = sym.replace("-USD", "")
    if src == "crypto":
        base = ''.join(ch for ch in sym if ch.isalnum())
        return f"BINANCE:{base}USDT" if base else ""
    if src in {"forex", "fx"}:
        return f"FX:{sym.replace('=X', '')}"
    if sym in NASDAQ:
        return f"NASDAQ:{sym}"
    if sym in NYSE:
        return f"NYSE:{sym}"
    if sym in AMEX:
        return f"AMEX:{sym}"
    return sym.replace("^", "")


def tradingview_url(symbol: str | None, source: str | None = "") -> str:
    tv = tradingview_symbol(symbol, source)
    if not tv:
        return "https://www.tradingview.com/"
    return f"https://www.tradingview.com/chart/?symbol={quote(tv, safe='')}"


def tradingview_link(symbol: str | None, source: str | None = "", label: str = "Chart ↗") -> str:
    tv = tradingview_symbol(symbol, source)
    url = tradingview_url(symbol, source)
    title = f"Open {tv or symbol or 'asset'} on TradingView"
    return (
        f'<a class="tv-link" href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
        f'title="{escape(title)}">{escape(label)}</a>'
    )


TV_LINK_CSS = """
.tv-link{display:inline-flex;align-items:center;justify-content:center;gap:5px;padding:5px 10px;border-radius:999px;border:1px solid rgba(56,189,248,.32);background:linear-gradient(135deg,rgba(56,189,248,.14),rgba(124,92,255,.12));color:#d9f3ff!important;text-decoration:none;font-size:.76rem;font-weight:950;white-space:nowrap;transition:all .16s;box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
.tv-link:hover{background:linear-gradient(135deg,rgba(56,189,248,.24),rgba(124,92,255,.20));border-color:rgba(56,189,248,.58);transform:translateY(-1px);box-shadow:0 8px 24px rgba(56,189,248,.12),inset 0 1px 0 rgba(255,255,255,.10)}
""".strip()
