"""Market session labels shared by Atlas dashboard components.

The labels are intentionally compact for dense Hawkeye rows. They are indicative
exchange-session states, not trading advice.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape


def _minutes_utc(dt: datetime) -> int:
    d = dt.astimezone(timezone.utc)
    return d.hour * 60 + d.minute


def _weekday(dt: datetime) -> bool:
    return dt.astimezone(timezone.utc).weekday() < 5


def _in_range(minutes: int, start: int, end: int) -> bool:
    return start <= minutes < end


def _forex_open(dt: datetime) -> bool:
    d = dt.astimezone(timezone.utc)
    day = d.weekday()  # Monday=0, Sunday=6
    minutes = _minutes_utc(d)
    if 0 <= day <= 3:
        return True
    if day == 4:
        return minutes < 22 * 60
    if day == 6:
        return minutes >= 22 * 60
    return False


def market_session(market: str, now: datetime | None = None) -> dict[str, str]:
    """Return compact indicative session state for a market family.

    States:
    - open: market is open / 24-7 / futures-global session active
    - clos: cash market is closed but an extended/CFD context may exist
    - closed: market is closed for the weekend or unavailable window
    """
    now = now or datetime.now(timezone.utc)
    key = {"actions": "stocks", "stock": "stocks", "fx": "forex"}.get((market or "").lower(), (market or "").lower())
    minutes = _minutes_utc(now)
    is_weekday = _weekday(now)
    utc_day = now.astimezone(timezone.utc).weekday()

    if key == "crypto":
        return {"state": "open", "label": "Ouvert · 24/7"}
    if key == "forex":
        return {"state": "open", "label": "Ouvert · FX"} if _forex_open(now) else {"state": "closed", "label": "Fermé · FX"}
    if key in {"stocks", "etf"}:
        if is_weekday and _in_range(minutes, 14 * 60 + 30, 21 * 60):
            return {"state": "open", "label": "Ouvert · US cash"}
        if is_weekday and (_in_range(minutes, 9 * 60, 14 * 60 + 30) or _in_range(minutes, 21 * 60, 24 * 60)):
            return {"state": "clos", "label": "Clos · hors séance"}
        return {"state": "closed", "label": "Fermé · US"}
    if key == "indices":
        if is_weekday or utc_day == 6:
            return {"state": "open", "label": "Ouvert · global/futures"}
        return {"state": "closed", "label": "Fermé · weekend"}
    if key == "commodities":
        if _forex_open(now):
            return {"state": "clos", "label": "Clos · CFD/extended"}
        return {"state": "closed", "label": "Fermé · CFD"}
    return {"state": "closed", "label": "Fermé"}


def market_session_badge(market: str, now: datetime | None = None, *, attr: str = "data-market-state") -> str:
    session = market_session(market, now)
    state = escape(session["state"])
    label = escape(session["label"])
    market_attr = escape({"actions": "stocks"}.get((market or "").lower(), (market or "").lower()))
    return f'<span class="market-state market-state-{state}" data-market="{market_attr}" {attr}>{label}</span>'


MARKET_STATE_CSS = """
.market-state{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;border:1px solid rgba(148,163,184,.18);background:rgba(15,23,42,.56);font-size:.72rem;font-weight:950;text-transform:uppercase;letter-spacing:.035em;white-space:nowrap}
.market-state:before{content:"";width:6px;height:6px;border-radius:999px;background:#94a3b8;box-shadow:0 0 12px rgba(148,163,184,.65)}
.market-state-open{color:#bbf7d0;border-color:rgba(34,197,94,.24);background:rgba(34,197,94,.09)}
.market-state-open:before{background:#22c55e;box-shadow:0 0 14px rgba(34,197,94,.9)}
.market-state-clos{color:#fde68a;border-color:rgba(245,158,11,.26);background:rgba(245,158,11,.09)}
.market-state-clos:before{background:#f59e0b;box-shadow:0 0 14px rgba(245,158,11,.85)}
.market-state-closed{color:#fecaca;border-color:rgba(251,113,133,.26);background:rgba(251,113,133,.09)}
.market-state-closed:before{background:#fb7185;box-shadow:0 0 14px rgba(251,113,133,.85)}
"""
