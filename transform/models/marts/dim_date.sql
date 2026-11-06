{{ config(materialized='table') }}

with days as (
    select dateadd(day, seq4(), '2021-01-01'::date) as date_day
    from table(generator(rowcount => 3652))
),

market_days as (
    select distinct bar_date from {{ ref('stg_daily_bars') }}
)

select
    d.date_day,
    to_number(to_char(d.date_day, 'YYYYMMDD'))      as date_key,
    year(d.date_day)                                as year,
    quarter(d.date_day)                             as quarter,
    month(d.date_day)                               as month,
    monthname(d.date_day)                           as month_name,
    day(d.date_day)                                 as day_of_month,
    dayofweekiso(d.date_day)                        as day_of_week_iso,
    dayname(d.date_day)                             as day_name,
    weekiso(d.date_day)                             as iso_week,
    dayofweekiso(d.date_day) in (6, 7)              as is_weekend,
    m.bar_date is not null                          as is_market_day
from days d
left join market_days m on m.bar_date = d.date_day
