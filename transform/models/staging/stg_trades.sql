with src as (
    select record, file_name, file_row_number, loaded_at
    from {{ source('raw_market', 'trades') }}
),

typed as (
    select
        record:_kafka_partition::int || '-' || record:_kafka_offset::int  as trade_key,
        record:_kafka_partition::int                                      as kafka_partition,
        record:_kafka_offset::int                                         as kafka_offset,
        to_timestamp_ntz(record:_kafka_ts::number, 3)                     as kafka_ts_utc,
        record:trade_id::string                                           as trade_id,
        record:symbol::string                                             as symbol,
        record:price::number(18, 6)                                       as price,
        record:qty::number(38, 8)                                         as qty,
        record:side::string                                               as side,
        record:exchange::string                                           as exchange,
        record:conditions                                                 as conditions,
        convert_timezone('UTC', record:ts::timestamp_tz)::timestamp_ntz   as trade_ts_utc,
        convert_timezone('UTC', record:ingested_at::timestamp_tz)::timestamp_ntz as ingested_at_utc,
        file_name,
        file_row_number,
        loaded_at
    from src
    where record:trade_id is not null
)

select *
from typed
qualify row_number() over (partition by kafka_partition, kafka_offset order by loaded_at, file_name) = 1
