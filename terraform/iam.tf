resource "aws_iam_role" "lambda_role" {
    name = "${var.function_name}-role"
    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Action = "sts:AssumeRole"
                Effect = "Allow"
                Principal = {
                    Service = "lambda.amazonaws.com"
                }
            }
        ]
    })
}

resource "aws_iam_role_policy_attachment" "lambda_logs"{
    role = aws_iam_role.lambda_role.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "rds_read"{
    role = aws_iam_role.lambda_role.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "bedrock_invoke"{
    role = aws_iam_role.lambda_role.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}


resource "aws_iam_policy" "s3_read" {
    name = "${var.function_name}-s3-read"
    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Action = "s3:GetObject"
                Effect = "Allow"
                Resource = "arn:aws:s3:::${var.s3_bucket_name}/*"
            }
        ]
    })
}

resource "aws_iam_role_policy_attachment" "s3_read_attachment" {
    role = aws_iam_role.lambda_role.name
    policy_arn = aws_iam_policy.s3_read.arn
}

resource "aws_iam_policy" "cloudwatch_metrics" {
    name = "${var.function_name}-cloudwatch-metrics"
    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Action = [
                    "cloudwatch:PutMetricData"
                ]
                Effect = "Allow"
                Resource = "*"
            }
        ]
    })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_metrics_attachment" {
    role = aws_iam_role.lambda_role.name
    policy_arn = aws_iam_policy.cloudwatch_metrics.arn
}