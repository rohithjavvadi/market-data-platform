with src as (
    select record, file_name, loaded_at
    from {{ source('raw_market', 'daily_bars') }}
),

typed as (
    select
        record:ticker::string as ticker,
        record:date::date as bar_date,
        record:open::number(18, 6) as open,
        record:high::number(18, 6) as high,
        record:low::number(18, 6) as low,
        record:close::number(18, 6) as close,
        record:volume::number(38, 0) as volume,
        record:adjOpen::number(18, 6) as adj_open,
        record:adjHigh::number(18, 6) as adj_high,
        record:adjLow::number(18, 6) as adj_low,
        record:adjClose::number(18, 6) as adj_close,
        record:adjVolume::number(38, 4) as adj_volume,
        record:divCash::number(18, 6) as div_cash,
        record:splitFactor::number(18, 6) as split_factor,
        record:source::string as source,
        convert_timezone('UTC', record:ingested_at::timestamp_tz)::timestamp_ntz as ingested_at_utc,
        file_name,
        loaded_at
    from src
    where record:ticker is not null and record:date is not null
)

select
    ticker || '|' || to_varchar(bar_date, 'YYYY-MM-DD') as daily_bar_key,
    *
from typed
qualify
    row_number() over (
        partition by ticker, bar_date
        order by ingested_at_utc desc, loaded_at desc, file_name desc
    ) = 1
-- ci smoke test
