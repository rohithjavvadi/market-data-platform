data "aws_caller_identity" "me" {}

locals {
  account_id = data.aws_caller_identity.me.account_id
  lake       = toset(["bronze", "silver"])

}

# ---------- S3 data lake ----------
resource "aws_s3_bucket" "lake" {
  for_each      = local.lake
  bucket        = "${var.project}-${each.key}-${local.account_id}"
  force_destroy = true # lets `make down` tear it all down
}

resource "aws_s3_bucket_public_access_block" "lake" {
  for_each                = local.lake
  bucket                  = aws_s3_bucket.lake[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  for_each = local.lake
  bucket   = aws_s3_bucket.lake[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "bronze" {
  bucket = aws_s3_bucket.lake["bronze"].id
  rule {
    id     = "bronze-to-ia"
    status = "Enabled"
    filter {}
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}

# ---------- IAM user Snowflake uses to read the lake ----------
# Plan B: free-plan guardrails block cross-account role assumption,
# so Snowflake gets a read-only key scoped to the two lake buckets.
data "aws_iam_policy_document" "snowflake_s3_read" {
  statement {
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = [for b in aws_s3_bucket.lake : "${b.arn}/*"]
  }
  statement {
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [for b in aws_s3_bucket.lake : b.arn]
  }
}

resource "aws_iam_user" "snowflake" {
  name = "${var.project}-snowflake-reader"
}

resource "aws_iam_user_policy" "snowflake_s3_read" {
  name   = "s3-lake-read"
  user   = aws_iam_user.snowflake.name
  policy = data.aws_iam_policy_document.snowflake_s3_read.json
}

resource "aws_iam_access_key" "snowflake" {
  user = aws_iam_user.snowflake.name
}

# ---------- Cost guardrail ----------
resource "aws_budgets_budget" "monthly" {
  name         = "${var.project}-monthly"
  budget_type  = "COST"
  limit_amount = "20"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [10, 20]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "ABSOLUTE_VALUE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_email]
    }
  }
}
