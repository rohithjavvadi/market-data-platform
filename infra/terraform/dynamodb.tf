resource "aws_dynamodb_table" "latest_price" {
  name           = "mdp-latest-price"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "symbol"

  attribute {
    name = "symbol"
    type = "S"
  }
}

resource "aws_iam_user" "ddb_writer" {
  name = "mdp-ddb-writer"
}

resource "aws_iam_user_policy" "ddb_writer" {
  name = "mdp-ddb-writer-latest-price"
  user = aws_iam_user.ddb_writer.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Scan", "dynamodb:DescribeTable"]
      Resource = aws_dynamodb_table.latest_price.arn
    }]
  })
}

resource "aws_iam_access_key" "ddb_writer" {
  user = aws_iam_user.ddb_writer.name
}
