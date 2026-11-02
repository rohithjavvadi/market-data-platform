output "bronze_bucket" {
  value = aws_s3_bucket.lake["bronze"].bucket
}

output "silver_bucket" {
  value = aws_s3_bucket.lake["silver"].bucket
}

output "snowflake_reader_key_id" {
  value = aws_iam_access_key.snowflake.id
}

output "snowflake_reader_secret" {
  value     = aws_iam_access_key.snowflake.secret
  sensitive = true
}
