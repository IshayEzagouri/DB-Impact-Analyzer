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