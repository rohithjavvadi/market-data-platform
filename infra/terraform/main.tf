data "aws_caller_identity" "me" {}

locals {
  account_id = data.aws_caller_identity.me.account_id
  lake       = toset(["bronze", "silver"])

  # Pre-computed so the storage integration and the IAM role don't form a cycle
  snowflake_role_name = "${var.project}-snowflake-s3-read"
  snowflake_role_arn  = "arn:aws:iam::${local.account_id}:role/${local.snowflake_role_name}"
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

# ---------- IAM role Snowflake assumes to read the lake ----------
data "aws_iam_policy_document" "snowflake_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [snowflake_storage_integration.s3.storage_aws_iam_user_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [snowflake_storage_integration.s3.storage_aws_external_id]
    }
  }
}

resource "aws_iam_role" "snowflake" {
  name               = local.snowflake_role_name
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust.json
}

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

resource "aws_iam_role_policy" "snowflake_s3_read" {
  name   = "s3-lake-read"
  role   = aws_iam_role.snowflake.id
  policy = data.aws_iam_policy_document.snowflake_s3_read.json
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
