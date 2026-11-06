{{ config(materialized='table') }}

select
    md5(ticker || '|' || to_varchar(dbt_valid_from))    as security_sk,
    ticker,
    cik,
    company_name,
    entity_type,
    filer_category,
    sic_code,
    sic_description,
    primary_exchange,
    fiscal_year_end_mmdd,
    state_of_incorporation,
    dbt_valid_from                                       as valid_from,
    dbt_valid_to                                         as valid_to,
    dbt_valid_to is null                                 as is_current
from {{ ref('snap_edgar_companies') }}
