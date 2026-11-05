with trades as (
    select symbol, exchange, price, qty, trade_ts_utc
    from {{ ref('stg_trades') }}
)

select
    symbol || '|' || to_varchar(date_trunc('minute', trade_ts_utc), 'YYYY-MM-DD HH24:MI') as bar_key,
    symbol,
    any_value(exchange)                                as exchange,
    date_trunc('minute', trade_ts_utc)                 as bar_ts_utc,
    min_by(price, trade_ts_utc)                        as open,
    max(price)                                         as high,
    min(price)                                         as low,
    max_by(price, trade_ts_utc)                        as close,
    sum(qty)                                           as volume,
    sum(price * qty) / nullif(sum(qty), 0)             as vwap,
    count(*)                                           as trade_count
from trades
group by symbol, date_trunc('minute', trade_ts_utc)
