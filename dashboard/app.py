import json
import math
import os
import time
from pathlib import Path

import boto3
import pandas as pd
import plotly.graph_objects as go
import queries as Q
import snowflake.connector
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Market Data Platform", layout="wide")

SNAP_DIR = Path(__file__).parent / "snapshot"
RANGES = {"3M": 63, "1Y": 252, "3Y": 756, "All": None}
MARGIN = {"l": 10, "r": 10, "t": 10, "b": 10}
ARCH = "Finnhub stream → Redpanda → S3 → Spark + Snowflake/dbt (PROD marts) · latest price served from DynamoDB"


def secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return None


@st.cache_resource
def sf_conn():
    return snowflake.connector.connect(**Q.connect_kwargs(secret("snowflake")))


def _run(sql, params):
    cur = sf_conn().cursor()
    try:
        cur.execute(sql, params)
        df = cur.fetch_pandas_all()
    finally:
        cur.close()
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner="Querying Snowflake...")
def q(sql, params=None):
    try:
        return _run(sql, params or {})
    except snowflake.connector.Error:
        sf_conn.clear()
        return _run(sql, params or {})


@st.cache_data(ttl=600, show_spinner="Connecting to Snowflake...")
def warehouse_up():
    if os.environ.get("MDP_FORCE_SNAPSHOT") or secret("snowflake") is None:
        return False
    try:
        _run("select 1", {})
        return True
    except Exception:
        sf_conn.clear()
        return False


@st.cache_data(show_spinner=False)
def snap(name):
    return pd.read_parquet(SNAP_DIR / f"{name}.parquet")


def snap_meta():
    try:
        return json.loads((SNAP_DIR / "meta.json").read_text())
    except Exception:
        return {}


def securities(live):
    return q(Q.DIM_SECURITY_CURRENT) if live else snap("dim_security_current")


def daily_bars(live, ticker):
    if live:
        return q(Q.DAILY_BARS_ONE, {"t": ticker})
    d = snap("daily_bars")
    return d[d.ticker == ticker].reset_index(drop=True)


def symbols_1m(live):
    df = q(Q.SYMBOLS_1M) if live else snap("ohlcv_1m")[["symbol"]].drop_duplicates()
    return sorted(df.symbol.tolist())


def ohlcv(live, sym, hours):
    if live:
        return q(Q.OHLCV_ONE, {"s": sym, "h": hours})
    d = snap("ohlcv_1m")
    d = d[d.symbol == sym]
    return d[d.bar_ts_utc > d.bar_ts_utc.max() - pd.Timedelta(hours=hours)].reset_index(drop=True)


def health(live):
    return q(Q.HEALTH) if live else snap("health")


@st.cache_resource
def ddb_table():
    a = secret("aws")
    return boto3.resource(
        "dynamodb",
        region_name=a.get("region", "us-east-2"),
        aws_access_key_id=a["access_key_id"],
        aws_secret_access_key=a["secret_access_key"],
    ).Table(a.get("table", "mdp-latest-price"))


def latest_prices():
    if not os.environ.get("MDP_FORCE_SNAPSHOT"):
        try:
            return pd.DataFrame(Q.price_rows(ddb_table().scan().get("Items", []))), "live"
        except Exception:
            ddb_table.clear()
    path = SNAP_DIR / "latest_price.parquet"
    return (pd.read_parquet(path) if path.exists() else pd.DataFrame()), "snapshot"


def fmt_age(seconds):
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds / size:.0f}{unit}"
    return f"{seconds:.0f}s"


@st.fragment(run_every="10s")
def live_panel():
    df, src = latest_prices()
    st.subheader("Last trade, live from DynamoDB" if src == "live" else "Last trade (snapshot)")
    if df.empty:
        st.info("No prices available.")
        return
    now_ms = time.time() * 1000
    df = df.sort_values("symbol")
    cols = st.columns(min(len(df), 6))
    for i, r in enumerate(df.itertuples(index=False)):
        age = max(0.0, (now_ms - r.trade_ts_ms) / 1000)
        cols[i % len(cols)].metric(f"{r.symbol} · {fmt_age(age)} ago", f"{r.price:,.2f}")
    note = "Refreshes every 10 s. " if src == "live" else ""
    st.caption(f"{note}{int(df.trades_seen.sum()):,} trades folded into these rows by the stream writer.")


def daily_tab(live):
    sec = securities(live)
    eq = sec[sec.asset_class == "equity"]
    labels = {r.ticker: f"{r.ticker} · {r.company_name}" for r in eq.itertuples()}
    c1, c2 = st.columns([2, 1])
    ticker = c1.selectbox("Ticker", list(labels), format_func=labels.get)
    rng = c2.radio("Range", list(RANGES), index=1, horizontal=True)
    df = daily_bars(live, ticker)
    if df.empty:
        st.info("No daily bars for this ticker.")
        return
    n = RANGES[rng]
    view = df.tail(n) if n else df
    last = view.adj_close.iloc[-1]
    ret = last / view.adj_close.iloc[0] - 1
    vol = view.daily_return.dropna().std() * math.sqrt(252)
    dd = (view.adj_close / view.adj_close.cummax() - 1).min()
    k = st.columns(4)
    k[0].metric(f"Adj close · {view.bar_date.iloc[-1]}", f"{last:,.2f}")
    k[1].metric(f"Return ({rng})", f"{ret:+.1%}")
    k[2].metric("Annualised volatility", f"{vol:.1%}")
    k[3].metric("Max drawdown", f"{dd:.1%}")
    fig = go.Figure(go.Scatter(x=view.bar_date, y=view.adj_close, mode="lines", name=ticker))
    fig.update_layout(height=380, margin=MARGIN, yaxis_title="Adjusted close")
    st.plotly_chart(fig, width="stretch")
    h = go.Figure(go.Histogram(x=view.daily_return.dropna(), nbinsx=60))
    h.update_layout(height=260, margin=MARGIN, xaxis_tickformat=".1%", xaxis_title="Daily return", yaxis_title="Days")
    st.plotly_chart(h, width="stretch")
    st.caption("Each bar joins to the dim_security (SCD2) version valid on its date.")


def intraday_tab(live):
    syms = symbols_1m(live)
    if not syms:
        st.info("No one-minute bars yet.")
        return
    c1, c2 = st.columns([2, 1])
    default = syms.index("BINANCE:BTCUSDT") if "BINANCE:BTCUSDT" in syms else 0
    sym = c1.selectbox("Symbol", syms, index=default)
    hours = c2.slider("Hours, ending at the latest bar", 1, 48, 6)
    df = ohlcv(live, sym, hours)
    k = st.columns(3)
    k[0].metric("Bars", f"{len(df):,}")
    k[1].metric("Trades", f"{int(df.trade_count.sum()):,}")
    k[2].metric("Latest bar (UTC)", str(df.bar_ts_utc.max())[:16])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.03)
    fig.add_trace(
        go.Candlestick(x=df.bar_ts_utc, open=df.open, high=df.high, low=df.low, close=df.close, name="OHLC"),
        row=1,
        col=1,
    )
    fig.add_trace(go.Scatter(x=df.bar_ts_utc, y=df.vwap, mode="lines", name="VWAP", line={"width": 1}), row=1, col=1)
    fig.add_trace(go.Bar(x=df.bar_ts_utc, y=df.volume, name="Volume"), row=2, col=1)
    fig.update_layout(height=520, margin=MARGIN, xaxis_rangeslider_visible=False, showlegend=False)
    st.plotly_chart(fig, width="stretch")


def health_tab(live):
    st.dataframe(health(live), hide_index=True, width="stretch")
    st.caption("PROD marts are rebuilt by Airflow every 15 min on weekdays (14:00-21:45 UTC). Queries cached 10 min.")


LIVE = warehouse_up()
st.title("Market Data Platform")
st.caption(ARCH)
if not LIVE:
    exported = snap_meta().get("exported_at_utc", "unknown")
    st.info(
        f"Showing a snapshot exported {exported} UTC: the live Snowflake warehouse is offline. "
        "Pipeline code, tests and CI history are in the repo."
    )
live_panel()
tab_daily, tab_intraday, tab_health = st.tabs(["Daily", "Intraday", "Pipeline health"])
with tab_daily:
    daily_tab(LIVE)
with tab_intraday:
    intraday_tab(LIVE)
with tab_health:
    health_tab(LIVE)
