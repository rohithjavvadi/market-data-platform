{{ config(materialized='table') }}

with sec as (
    select
        ticker,
        cik,
        company_name,
        'equity'                    as asset_class,
        entity_type,
        filer_category,
        sic_code,
        sic_description,
        primary_exchange,
        fiscal_year_end_mmdd,
        state_of_incorporation,
        case
            when row_number() over (partition by ticker order by dbt_valid_from) = 1
                then '1900-01-01'::timestamp_ntz
            else dbt_valid_from
        end                         as valid_from,
        dbt_valid_to                as valid_to
    from {{ ref('snap_edgar_companies') }}
),

manual as (
    select
        ticker,
        null::varchar               as cik,
        company_name,
        asset_class,
        null::varchar               as entity_type,
        null::varchar               as filer_category,
        null::varchar               as sic_code,
        null::varchar               as sic_description,
        primary_exchange,
        null::varchar               as fiscal_year_end_mmdd,
        null::varchar               as state_of_incorporation,
        '1900-01-01'::timestamp_ntz as valid_from,
        null::timestamp_ntz         as valid_to
    from {{ ref('non_sec_securities') }}
),

unioned as (
    select * from sec
    union all
    select * from manual
)

select
    md5(ticker || '|' || to_varchar(valid_from))   as security_sk,
    *,
    valid_to is null                               as is_current
from unioned
