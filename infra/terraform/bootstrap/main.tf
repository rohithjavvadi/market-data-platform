# One-time bootstrap: creates the remote-state bucket with LOCAL state.
# Kept separate so `make down` (terraform destroy in ../) never touches it.

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "project" {
  type    = string
  default = "mdp"
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "market-data-platform", ManagedBy = "terraform" }
  }
}

data "aws_caller_identity" "me" {}

resource "aws_s3_bucket" "tf_state" {
  bucket = "${var.project}-tf-state-${data.aws_caller_identity.me.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket" {
  value = aws_s3_bucket.tf_state.bucket
}
