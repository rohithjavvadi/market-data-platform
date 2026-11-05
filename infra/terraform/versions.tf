terraform {
  required_version = ">= 1.10" # needed for S3-native state locking (use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = ">= 2.3, < 3.0"
    }
  }

  # Partial config: bucket/region come from backend.hcl (see backend.hcl.example)
  backend "s3" {
    key          = "market-data-platform/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "market-data-platform", ManagedBy = "terraform" }
  }
}

# Default Snowflake provider: SYSADMIN owns warehouse, databases, schemas
provider "snowflake" {
  organization_name        = var.snowflake_organization_name
  account_name             = var.snowflake_account_name
  user                     = var.snowflake_user
  role                     = "SYSADMIN"
  authenticator            = "SNOWFLAKE_JWT"
  private_key              = file(pathexpand(var.snowflake_private_key_path))
  preview_features_enabled = ["snowflake_table_resource"]
}

# ACCOUNTADMIN: storage integration, resource monitor, roles, grants
provider "snowflake" {
  alias                    = "admin"
  organization_name        = var.snowflake_organization_name
  account_name             = var.snowflake_account_name
  user                     = var.snowflake_user
  role                     = "ACCOUNTADMIN"
  authenticator            = "SNOWFLAKE_JWT"
  private_key              = file(pathexpand(var.snowflake_private_key_path))
  preview_features_enabled = ["snowflake_table_resource"]
}
