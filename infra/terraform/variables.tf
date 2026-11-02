variable "project" {
  type    = string
  default = "mdp"
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "budget_email" {
  type        = string
  description = "Where AWS budget alerts go"
}

variable "snowflake_organization_name" {
  type = string
}

variable "snowflake_account_name" {
  type = string
}

variable "snowflake_user" {
  type    = string
  default = "TERRAFORM_SVC"
}

variable "snowflake_private_key_path" {
  type    = string
  default = "~/.snowflake/terraform_svc_key.p8"
}

variable "snowflake_monthly_credit_quota" {
  type    = number
  default = 10
}
