import os

from cryptography.hazmat.primitives import serialization

DIM_SECURITY_CURRENT = "select ticker, company_name, asset_class from dim_security where is_current order by ticker"

_DAILY = """
select b.ticker, b.bar_date, b.adj_close::float as adj_close, b.daily_return::float as daily_return
from fct_daily_bars b
join dim_security s on b.security_sk = s.security_sk
"""
DAILY_BARS_ONE = _DAILY + "where b.ticker = %(t)s order by b.bar_date"
DAILY_BARS_ALL = _DAILY + "order by b.ticker, b.bar_date"

SYMBOLS_1M = "select distinct symbol from fct_ohlcv_1m order by 1"

_OHLCV_COLS = """f.symbol, f.bar_ts_utc, f.open::float as open, f.high::float as high, f.low::float as low,
       f.close::float as close, f.volume::float as volume, f.vwap::float as vwap, f.trade_count"""
OHLCV_ONE = f"""
with mx as (select max(bar_ts_utc) as m from fct_ohlcv_1m where symbol = %(s)s)
select {_OHLCV_COLS}
from fct_ohlcv_1m f, mx
where f.symbol = %(s)s and f.bar_ts_utc > dateadd(hour, -%(h)s, mx.m)
order by f.bar_ts_utc
"""
OHLCV_RECENT_ALL = f"""
select {_OHLCV_COLS}
from fct_ohlcv_1m f
join (select symbol, max(bar_ts_utc) as m from fct_ohlcv_1m group by symbol) mx
  on f.symbol = mx.symbol and f.bar_ts_utc > dateadd(hour, -48, mx.m)
order by f.symbol, f.bar_ts_utc
"""

HEALTH = """
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


def connect_kwargs(cfg):
    kwargs = {k: cfg[k] for k in ("account", "user", "role", "warehouse", "database", "schema")}
    if cfg.get("private_key"):
        key = serialization.load_pem_private_key(cfg["private_key"].encode(), password=None)
        kwargs["private_key"] = key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    else:
        kwargs["private_key_file"] = os.path.expanduser(cfg["private_key_path"])
    kwargs.update(authenticator="SNOWFLAKE_JWT", login_timeout=20, network_timeout=60, client_session_keep_alive=True)
    return kwargs


def price_rows(items):
    return [
        {
            "symbol": i["symbol"],
            "price": float(i["price"]),
            "trade_ts_ms": int(i["trade_ts_ms"]),
            "trades_seen": int(i.get("trades_seen", 0)),
        }
        for i in items
    ]
