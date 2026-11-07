{{ config(materialized='table') }}

with latest as (
    select
        record,
        file_name,
        regexp_substr(file_name, 'ticker=([^/]+)', 1, 1, 'e', 1) as ticker,
        regexp_substr(file_name, 'dt=([0-9-]+)', 1, 1, 'e', 1)::date as snapshot_date
    from {{ source('raw_market', 'edgar_filings') }}
    where file_name like 'edgar/companyfacts/%'
    qualify row_number() over (
        partition by record:cik
        order by snapshot_date desc, loaded_at desc
    ) = 1
)

select
    l.ticker,
    lpad(l.record:cik::string, 10, '0') as cik,
    l.record:entityName::string as entity_name,
    tax.key::string as taxonomy,
    con.key::string as concept,
    con.value:label::string as concept_label,
    unit.key::string as unit,
    obs.value:val::number(38, 6) as value,
    obs.value:start::date as period_start,
    obs.value:end::date as period_end,
    obs.value:fy::int as fiscal_year,
    obs.value:fp::string as fiscal_period,
    obs.value:form::string as form,
    obs.value:filed::date as filed_date,
    obs.value:accn::string as accession_number,
    obs.value:frame::string as frame,
    l.snapshot_date
from latest l,
    lateral flatten(input => l.record:facts) tax,
    lateral flatten(input => tax.value) con,
    lateral flatten(input => con.value:units) unit,
    lateral flatten(input => unit.value) obs
