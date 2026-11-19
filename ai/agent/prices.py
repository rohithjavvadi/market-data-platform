"""Agent tool: price performance stats from the dashboard's daily-bar snapshot."""

import argparse
import json
import math
import os
from datetime import date, timedelta

import duckdb

DEFAULT_SOURCE = "dashboard/snapshot/daily_bars.parquet"
PERIOD_DAYS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095, "5y": 1826}
PERIODS = [*PERIOD_DAYS, "ytd"]


def period_start(end: date, period: str) -> date:
    if period == "ytd":
        return date(end.year, 1, 1)
    if period not in PERIOD_DAYS:
        raise ValueError(f"period must be one of {PERIODS}")
    return end - timedelta(days=PERIOD_DAYS[period])


def _max_drawdown(closes: list[float]) -> float:
    peak, mdd = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    return mdd


def _ann_vol(rets: list[float]) -> float | None:
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def get_price_stats(ticker: str, period: str = "1y", *, source: str | None = None) -> dict:
    """Return/volatility/drawdown for one ticker over a trailing period."""
    source = source or os.environ.get("AI_PRICES_URI", DEFAULT_SOURCE)
    period = period.lower()
    src = source.replace("'", "''")
    rows = duckdb.execute(
        f"select bar_date::DATE, adj_close, daily_return from read_parquet('{src}') "
        "where ticker = ? and adj_close is not null order by 1",
        [ticker.upper()],
    ).fetchall()
    if not rows:
        return {"ticker": ticker.upper(), "error": "no price data for this ticker"}
    end = rows[-1][0]
    start = period_start(end, period)
    win = [r for r in rows if r[0] >= start]
    closes = [float(r[1]) for r in win]
    rets = [float(r[2]) for r in win[1:] if r[2] is not None]
    vol = _ann_vol(rets)
    return {
        "ticker": ticker.upper(),
        "period": period,
        "start_date": str(win[0][0]),
        "end_date": str(end),
        "start_price": round(closes[0], 2),
        "end_price": round(closes[-1], 2),
        "total_return_pct": round((closes[-1] / closes[0] - 1) * 100, 2),
        "ann_vol_pct": None if vol is None else round(vol * 100, 2),
        "max_drawdown_pct": round(_max_drawdown(closes) * 100, 2),
        "high": round(max(closes), 2),
        "low": round(min(closes), 2),
        "trading_days": len(win),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ticker")
    p.add_argument("--period", default="1y", choices=PERIODS)
    a = p.parse_args()
    print(json.dumps(get_price_stats(a.ticker, a.period), indent=2))
