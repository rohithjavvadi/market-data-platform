with trades as (
    select
        symbol,
        exchange,
        price,
        qty,
        trade_ts_utc,
        kafka_partition,
        kafka_offset,
        date_trunc('minute', trade_ts_utc) as bar_ts_utc
    from {{ ref('stg_trades') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by symbol, bar_ts_utc
            order by trade_ts_utc, kafka_partition, kafka_offset
        ) as rn_first,
        row_number() over (
            partition by symbol, bar_ts_utc
            order by trade_ts_utc desc, kafka_partition desc, kafka_offset desc
        ) as rn_last
    from trades
)

select
    symbol || '|' || to_varchar(bar_ts_utc, 'YYYY-MM-DD HH24:MI') as bar_key,
    symbol,
    any_value(exchange)                         as exchange,
    bar_ts_utc,
    max(iff(rn_first = 1, price, null))         as open,
    max(price)                                  as high,
    min(price)                                  as low,
    max(iff(rn_last = 1, price, null))          as close,
    sum(qty)                                    as volume,
    sum(price * qty) / nullif(sum(qty), 0)      as vwap,
    count(*)                                    as trade_count
from ranked
group by symbol, bar_ts_utc
