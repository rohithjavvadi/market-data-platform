{{ config(materialized='incremental', unique_key='daily_bar_key', incremental_strategy='merge') }}

with src as (
    select *
    from {{ ref('stg_daily_bars') }}
    {% if is_incremental() %}
    where bar_date >= (select dateadd(day, -20, max(bar_date)) from {{ this }})
    {% endif %}
),

with_returns as (
    select
        *,
        adj_close / nullif(lag(adj_close) over (partition by ticker order by bar_date), 0) - 1 as daily_return
    from src
)

select
    b.daily_bar_key,
    d.date_key,
    s.security_sk,
    b.ticker,
    b.bar_date,
    b.open,
    b.high,
    b.low,
    b.close,
    b.volume,
    b.adj_open,
    b.adj_high,
    b.adj_low,
    b.adj_close,
    b.adj_volume,
    b.div_cash,
    b.split_factor,
    b.daily_return,
    b.ingested_at_utc
from with_returns b
join {{ ref('dim_date') }} d
    on d.date_day = b.bar_date
left join {{ ref('dim_security') }} s
    on s.ticker = b.ticker
   and b.bar_date >= s.valid_from::date
   and (s.valid_to is null or b.bar_date < s.valid_to::date)
{% if is_incremental() %}
where b.bar_date >= (select dateadd(day, -10, max(bar_date)) from {{ this }})
{% endif %}
