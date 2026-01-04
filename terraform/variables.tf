variable "region"{
    type = string
    default = "us-east-1"
}


  variable "function_name" {
    description = "Name of the Lambda function"
    type        = string
    default     = "ishay-db-failure-impact-agent"
  }

  variable "aws_profile" {
    description = "AWS CLI profile to use"
    type        = string
    default     = "develeap-ishay"
  }

  variable "lambda_runtime" {
    description = "Lambda runtime version"
    type        = string
    default     = "python3.12"
  }

  variable "lambda_timeout" {
    description = "Lambda timeout in seconds"
    type        = number
    default     = 30
  }

  variable "s3_bucket_name" {
    description = "Name of the S3 bucket"
    type        = string
    default     = "db-impact-agent-business-context"
  }

  variable "api_key" {
    description = "API key for the DB Impact Agent"
    type        = string
    sensitive   = true
  }

  variable "reserved_concurrent_executions" {
    description = "Reserved concurrent executions for the Lambda function"
    type        = number
    default     = 2
  }
  variable "throttling_rate_limit" {
    description = "Throttling rate limit for the API Gateway"
    type        = number
    default     = 5
  }
  variable "throttling_burst_limit" {
    description = "Throttling burst limit for the API Gateway"
    type        = number
    default     = 10
  }