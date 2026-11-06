with src as (
    select
        record,
        file_name,
        loaded_at,
        regexp_substr(file_name, 'ticker=([^/]+)', 1, 1, 'e', 1)            as ticker,
        regexp_substr(file_name, 'dt=([0-9-]+)', 1, 1, 'e', 1)::date        as snapshot_date
    from {{ source('raw_market', 'edgar_filings') }}
    where file_name like 'edgar/submissions/%'
)

select
    ticker,
    lpad(record:cik::string, 10, '0')                   as cik,
    record:name::string                                 as company_name,
    record:entityType::string                           as entity_type,
    record:category::string                             as filer_category,
    record:sic::string                                  as sic_code,
    record:sicDescription::string                       as sic_description,
    record:fiscalYearEnd::string                        as fiscal_year_end_mmdd,
    record:stateOfIncorporation::string                 as state_of_incorporation,
    record:ein::string                                  as ein,
    record:lei::string                                  as lei,
    record:website::string                              as website,
    record:tickers                                      as tickers,
    record:exchanges                                    as exchanges,
    record:exchanges[0]::string                         as primary_exchange,
    snapshot_date,
    file_name,
    loaded_at
from src
qualify row_number() over (
    partition by ticker
    order by snapshot_date desc, loaded_at desc
) = 1
