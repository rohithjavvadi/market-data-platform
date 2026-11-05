resource "snowflake_service_user" "dbt" {
  provider          = snowflake.admin
  name              = "DBT_SVC"
  comment           = "dbt transformations"
  default_role      = snowflake_account_role.role["TRANSFORMER"].name
  default_warehouse = snowflake_warehouse.mdp.name
  rsa_public_key    = replace(replace(file(pathexpand("~/.snowflake/dbt_svc_key.pub")), "/-----[A-Z ]+-----/", ""), "\n", "")
}

resource "snowflake_grant_account_role" "transformer_to_dbt" {
  provider  = snowflake.admin
  role_name = snowflake_account_role.role["TRANSFORMER"].name
  user_name = snowflake_service_user.dbt.name
}
