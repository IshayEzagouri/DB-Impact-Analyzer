  terraform {
    required_providers {
      aws = {
        source  = "hashicorp/aws"
        version = "~> 5.0"  
      }
    }
  }

  provider "aws" {
    region  = "us-east-1"  
    profile = "develeap-ishay" 
  }

  resource "aws_lambda_function" "db_impact_agent" {
    filename = "${path.module}/../lambda-package.zip"
    function_name = var.function_name
    role = aws_iam_role.lambda_role.arn
    handler = "src.infra.lambda_handler.handler"
    runtime = var.lambda_runtime
    timeout = var.lambda_timeout
    #redeploys the lambda function if the zip hash changes
    source_code_hash = filebase64sha256("${path.module}/../lambda-package.zip")
  }


  resource "aws_apigatewayv2_api" "lambda_api" {
    name = "${var.function_name}-api"
    protocol_type = "HTTP"
  }

  resource "aws_apigatewayv2_integration" "lambda_integration" {
    api_id = aws_apigatewayv2_api.lambda_api.id
    integration_type="AWS_PROXY"
    integration_uri = aws_lambda_function.db_impact_agent.invoke_arn

  }

  resource "aws_apigatewayv2_route" "lambda_route" {
    api_id = aws_apigatewayv2_api.lambda_api.id
    route_key = "POST /"
    target = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
  }

  resource "aws_apigatewayv2_stage" "lambda_stage" {
    api_id = aws_apigatewayv2_api.lambda_api.id
    name = "default"
    auto_deploy = true
  }

  resource "aws_lambda_permission" "api_gateway_permission" {
    action = "lambda:InvokeFunction"
    function_name = aws_lambda_function.db_impact_agent.function_name
    principal = "apigateway.amazonaws.com"
    source_arn = "${aws_apigatewayv2_api.lambda_api.execution_arn}/*/*" 
  }