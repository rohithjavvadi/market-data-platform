resource "snowflake_stage_external_s3" "bronze_daily_bars" {
  name     = "BRONZE_DAILY_BARS"
  database = snowflake_database.raw.name
  schema   = snowflake_schema.raw_market.name
  url      = "s3://mdp-bronze-388260576625/daily_bars/"
  comment  = "Bronze Tiingo daily bars Parquet written by backfill/tiingo_daily.py"

  credentials {
    aws_key_id     = aws_iam_access_key.snowflake.id
    aws_secret_key = aws_iam_access_key.snowflake.secret
  }

  file_format {
    parquet {
      compression = "AUTO"
    }
  }
}

resource "snowflake_stage_external_s3" "bronze_edgar" {
  name     = "BRONZE_EDGAR"
  database = snowflake_database.raw.name
  schema   = snowflake_schema.raw_market.name
  url      = "s3://mdp-bronze-388260576625/edgar/"
  comment  = "Bronze SEC EDGAR submissions/companyfacts gzipped JSON written by edgar/edgar_extract.py"

  credentials {
    aws_key_id     = aws_iam_access_key.snowflake.id
    aws_secret_key = aws_iam_access_key.snowflake.secret
  }

  file_format {
    json {
      compression = "GZIP"
    }
  }
}

locals {
  raw_ref_tables = {
    DAILY_BARS    = "Raw Tiingo daily bars loaded from bronze; one row per ticker-day per file"
    EDGAR_FILINGS = "Raw SEC EDGAR JSON loaded from bronze; one row per file (endpoint/ticker in FILE_NAME)"
  }
}

resource "snowflake_table" "raw_ref" {
  for_each = local.raw_ref_tables

  database = snowflake_database.raw.name
  schema   = snowflake_schema.raw_market.name
  name     = each.key
  comment  = each.value

  column {
    name     = "RECORD"
    type     = "VARIANT"
    nullable = false
  }
  column {
    name = "FILE_NAME"
    type = "VARCHAR"
  }
  column {
    name = "FILE_ROW_NUMBER"
    type = "NUMBER(38,0)"
  }
  column {
    name = "LOADED_AT"
    type = "TIMESTAMP_LTZ(9)"
    default {
      expression = "CURRENT_TIMESTAMP()"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_ref_stages" {
  for_each = {
    DAILY_BARS = snowflake_stage_external_s3.bronze_daily_bars.fully_qualified_name
    EDGAR      = snowflake_stage_external_s3.bronze_edgar.fully_qualified_name
  }

  account_role_name = snowflake_account_role.role["LOADER"].name
  privileges        = ["USAGE"]
  on_schema_object {
    object_type = "STAGE"
    object_name = each.value
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_ref_tables" {
  for_each = snowflake_table.raw_ref

  account_role_name = snowflake_account_role.role["LOADER"].name
  privileges        = ["INSERT", "SELECT"]
  on_schema_object {
    object_type = "TABLE"
    object_name = each.value.fully_qualified_name
  }
}
