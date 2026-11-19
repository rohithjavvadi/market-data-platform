"""Liveness rule for the Finnhub websocket: reconnect when trades stop arriving."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN, CLOSE = time(9, 30), time(16, 0)


def market_open(now_utc: datetime) -> bool:
    """US equity regular session, weekdays 09:30-16:00 ET (holidays not modelled)."""
    et = now_utc.astimezone(ET)
    return et.weekday() < 5 and OPEN <= et.time() < CLOSE


def is_stale(last_activity_utc: datetime, now_utc: datetime, market_s: int = 120, off_s: int = 600) -> bool:
    """True when no trade/connect for longer than the limit for the current session."""
    limit = market_s if market_open(now_utc) else off_s
    return (now_utc - last_activity_utc).total_seconds() > limit
