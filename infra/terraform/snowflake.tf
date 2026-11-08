# ---------- Cost control ----------
resource "snowflake_resource_monitor" "mdp" {
  provider                  = snowflake.admin
  name                      = "MDP_MONITOR"
  credit_quota              = var.snowflake_monthly_credit_quota
  notify_triggers           = [75]
  suspend_trigger           = 100
  suspend_immediate_trigger = 110
}

resource "snowflake_warehouse" "mdp" {
  name                = "MDP_WH"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = "true"
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.mdp.fully_qualified_name
}

# ---------- Databases / schemas ----------
resource "snowflake_database" "raw" {
  name = "RAW"
}

resource "snowflake_schema" "raw_market" {
  database = snowflake_database.raw.name
  name     = "MARKET" # trades, bars, EDGAR raw tables + external stage
}

resource "snowflake_database" "analytics" {
  name = "ANALYTICS" # dbt creates STAGING / INTERMEDIATE / MARTS / ci_pr_<n>
}

# ---------- Roles ----------
resource "snowflake_account_role" "role" {
  provider = snowflake.admin
  for_each = toset(["LOADER", "TRANSFORMER", "REPORTER"])
  name     = each.key
}

resource "snowflake_grant_account_role" "to_sysadmin" {
  provider         = snowflake.admin
  for_each         = snowflake_account_role.role
  role_name        = each.value.name
  parent_role_name = "SYSADMIN"
}

# Warehouse usage for all three
resource "snowflake_grant_privileges_to_account_role" "wh_usage" {
  provider          = snowflake.admin
  for_each          = snowflake_account_role.role
  account_role_name = each.value.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.mdp.name
  }
}

# LOADER: write RAW.MARKET
resource "snowflake_grant_privileges_to_account_role" "loader_raw_db" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["LOADER"].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.raw.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_raw_schema" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["LOADER"].name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE STAGE", "CREATE FILE FORMAT", "CREATE PIPE"]
  on_schema {
    schema_name = snowflake_schema.raw_market.fully_qualified_name
  }
}

# TRANSFORMER: read RAW, build in ANALYTICS
resource "snowflake_grant_privileges_to_account_role" "transformer_raw_db" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["TRANSFORMER"].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.raw.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_schema" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["TRANSFORMER"].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = snowflake_schema.raw_market.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_future_tables" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["TRANSFORMER"].name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.raw_market.fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_analytics_db" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["TRANSFORMER"].name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.analytics.name
  }
}

# REPORTER (dashboard): read ANALYTICS
resource "snowflake_grant_privileges_to_account_role" "reporter_analytics_db" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["REPORTER"].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.analytics.name
  }
}

# REPORTER: read PROD marts only (schema is created by dbt CD)
locals {
  prod_marts = "\"${snowflake_database.analytics.name}\".\"PROD_MARTS\""
}

resource "snowflake_grant_privileges_to_account_role" "reporter_prod_marts_usage" {
  provider          = snowflake.admin
  account_role_name = snowflake_account_role.role["REPORTER"].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = local.prod_marts
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_prod_marts_select" {
  provider = snowflake.admin
  for_each = {
    all_tables    = { scope = "all", plural = "TABLES" }
    all_views     = { scope = "all", plural = "VIEWS" }
    future_tables = { scope = "future", plural = "TABLES" }
    future_views  = { scope = "future", plural = "VIEWS" }
  }
  account_role_name = snowflake_account_role.role["REPORTER"].name
  privileges        = ["SELECT"]
  on_schema_object {
    dynamic "all" {
      for_each = each.value.scope == "all" ? [1] : []
      content {
        object_type_plural = each.value.plural
        in_schema          = local.prod_marts
      }
    }
    dynamic "future" {
      for_each = each.value.scope == "future" ? [1] : []
      content {
        object_type_plural = each.value.plural
        in_schema          = local.prod_marts
      }
    }
  }
}
