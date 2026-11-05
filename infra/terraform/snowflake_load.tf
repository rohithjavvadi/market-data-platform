resource "snowflake_stage_external_s3" "bronze_trades" {
  name     = "BRONZE_TRADES"
  database = snowflake_database.raw.name
  schema   = snowflake_schema.raw_market.name
  url      = "s3://mdp-bronze-388260576625/trades/"
  comment  = "Bronze trades NDJSON.gz written by consumer/bronze_writer.py"

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

resource "snowflake_table" "trades" {
  database = snowflake_database.raw.name
  schema   = snowflake_schema.raw_market.name
  name     = "TRADES"
  comment  = "Raw trades loaded from bronze; one row per Kafka message"

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

resource "snowflake_grant_privileges_to_account_role" "loader_stage" {
  account_role_name = snowflake_account_role.role["LOADER"].name
  privileges        = ["USAGE"]
  on_schema_object {
    object_type = "STAGE"
    object_name = snowflake_stage_external_s3.bronze_trades.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_trades" {
  account_role_name = snowflake_account_role.role["LOADER"].name
  privileges        = ["INSERT", "SELECT"]
  on_schema_object {
    object_type = "TABLE"
    object_name = snowflake_table.trades.fully_qualified_name
  }
}
