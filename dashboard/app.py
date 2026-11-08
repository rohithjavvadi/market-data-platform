import math
import os
import time

import boto3
import pandas as pd
import plotly.graph_objects as go
import snowflake.connector
import streamlit as st
from cryptography.hazmat.primitives import serialization
from plotly.subplots import make_subplots

st.set_page_config(page_title="Market Data Platform", layout="wide")

RANGES = {"3M": 63, "1Y": 252, "3Y": 756, "All": None}
MARGIN = {"l": 10, "r": 10, "t": 10, "b": 10}


@st.cache_resource
def sf_conn():
    cfg = st.secrets["snowflake"]
    kwargs = {k: cfg[k] for k in ("account", "user", "role", "warehouse", "database", "schema")}
    if cfg.get("private_key"):
        key = serialization.load_pem_private_key(cfg["private_key"].encode(), password=None)
        kwargs["private_key"] = key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    else:
        kwargs["private_key_file"] = os.path.expanduser(cfg["private_key_path"])
    return snowflake.connector.connect(authenticator="SNOWFLAKE_JWT", client_session_keep_alive=True, **kwargs)


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


@st.cache_resource
def ddb_table():
    a = st.secrets["aws"]
    return boto3.resource(
        "dynamodb",
        region_name=a.get("region", "us-east-2"),
        aws_access_key_id=a["access_key_id"],
        aws_secret_access_key=a["secret_access_key"],
    ).Table(a.get("table", "mdp-latest-price"))


def latest_prices():
    items = ddb_table().scan().get("Items", [])
    rows = [
        {
            "symbol": i["symbol"],
            "price": float(i["price"]),
            "trade_ts_ms": int(i["trade_ts_ms"]),
            "trades_seen": int(i.get("trades_seen", 0)),
        }
        for i in items
    ]
    return pd.DataFrame(rows).sort_values("symbol") if rows else pd.DataFrame()


def fmt_age(seconds):
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds / size:.0f}{unit}"
    return f"{seconds:.0f}s"


@st.fragment(run_every="10s")
def live_panel():
    st.subheader("Last trade, live from DynamoDB")
    try:
        df = latest_prices()
    except Exception as e:
        st.warning(f"Live feed unavailable: {e}")
        return
    if df.empty:
        st.info("No live prices yet.")
        return
    now_ms = time.time() * 1000
    cols = st.columns(min(len(df), 6))
    for i, r in enumerate(df.itertuples(index=False)):
        age = max(0.0, (now_ms - r.trade_ts_ms) / 1000)
        cols[i % len(cols)].metric(r.symbol, f"{r.price:,.2f}", f"{fmt_age(age)} ago", delta_color="off")
    st.caption(
        f"Refreshes every 10 s. {int(df.trades_seen.sum()):,} trades folded into these rows by the stream writer."
    )


def daily_tab():
    sec = q("select ticker, company_name, asset_class from dim_security where is_current order by ticker")
    eq = sec[sec.asset_class == "equity"]
    labels = {r.ticker: f"{r.ticker} · {r.company_name}" for r in eq.itertuples()}
    c1, c2 = st.columns([2, 1])
    ticker = c1.selectbox("Ticker", list(labels), format_func=labels.get)
    rng = c2.radio("Range", list(RANGES), index=1, horizontal=True)
    df = q(
        """
        select b.bar_date, b.adj_close::float as adj_close, b.daily_return::float as daily_return
        from fct_daily_bars b
        join dim_security s on b.security_sk = s.security_sk
        where b.ticker = %(t)s
        order by b.bar_date
        """,
        {"t": ticker},
    )
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
    k[0].metric("Adj close", f"{last:,.2f}", f"as of {view.bar_date.iloc[-1]}", delta_color="off")
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


def intraday_tab():
    syms = q("select distinct symbol from fct_ohlcv_1m order by 1").symbol.tolist()
    if not syms:
        st.info("No one-minute bars yet.")
        return
    c1, c2 = st.columns([2, 1])
    default = syms.index("BINANCE:BTCUSDT") if "BINANCE:BTCUSDT" in syms else 0
    sym = c1.selectbox("Symbol", syms, index=default)
    hours = c2.slider("Hours, ending at the latest bar", 1, 48, 6)
    df = q(
        """
        with mx as (select max(bar_ts_utc) as m from fct_ohlcv_1m where symbol = %(s)s)
        select f.bar_ts_utc, f.open::float as open, f.high::float as high, f.low::float as low,
               f.close::float as close, f.volume::float as volume, f.vwap::float as vwap, f.trade_count
        from fct_ohlcv_1m f, mx
        where f.symbol = %(s)s and f.bar_ts_utc > dateadd(hour, -%(h)s, mx.m)
        order by f.bar_ts_utc
        """,
        {"s": sym, "h": hours},
    )
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


def health_tab():
    df = q(
        """
        select 'fct_ohlcv_1m' as model, count(*) as row_count, max(bar_ts_utc)::string as latest_data,
               convert_timezone('UTC', max(max_loaded_at))::timestamp_ntz::string as last_loaded_utc
        from fct_ohlcv_1m
        union all
        select 'fct_daily_bars', count(*), max(bar_date)::string, max(ingested_at_utc)::string from fct_daily_bars
        union all
        select 'dim_security', count(*), null, null from dim_security
        union all
        select 'dim_date', count(*), max(date_day)::string, null from dim_date
        """
    )
    st.dataframe(df, hide_index=True, width="stretch")
    st.caption("PROD marts are rebuilt by Airflow every 15 min on weekdays (14:00-21:45 UTC). Queries cached 10 min.")


st.title("Market Data Platform")
st.caption("Finnhub stream → Redpanda → S3 → Spark + Snowflake/dbt (PROD marts) · latest price served from DynamoDB")
live_panel()
tab_daily, tab_intraday, tab_health = st.tabs(["Daily", "Intraday", "Pipeline health"])
with tab_daily:
    daily_tab()
with tab_intraday:
    intraday_tab()
with tab_health:
    health_tab()
