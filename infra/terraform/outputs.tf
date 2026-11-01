output "bronze_bucket" {
  value = aws_s3_bucket.lake["bronze"].bucket
}

output "silver_bucket" {
  value = aws_s3_bucket.lake["silver"].bucket
}

output "snowflake_role_arn" {
  value = aws_iam_role.snowflake.arn
}

output "storage_integration" {
  value = snowflake_storage_integration.s3.name
}
