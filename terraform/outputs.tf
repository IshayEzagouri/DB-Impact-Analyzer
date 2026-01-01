output "api_gateway_url" {
description = "API Gateway URL for the DB Impact Agent"
value = "${aws_apigatewayv2_api.lambda_api.api_endpoint}/${aws_apigatewayv2_stage.lambda_stage.name}"
}

output "lambda_function_name" {
    description = "Name of the Lambda function"
    value = aws_lambda_function.db_impact_agent.function_name
}

output "lambda_function_arn" {
    description = "ARN of the Lambda function"
    value = aws_lambda_function.db_impact_agent.arn
}

output "s3_bucket_name" {
    description = "Name of the S3 bucket"
    value = aws_s3_bucket.db_impact_agent_bucket.id
}

output "s3_bucket_arn" {
    description = "ARN of the S3 bucket"
    value = aws_s3_bucket.db_impact_agent_bucket.arn
}