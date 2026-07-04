variable "name_prefix" { type = string }
variable "environment" { type = string }
variable "lambda_function_name" { type = string }
variable "lambda_invoke_arn" { type = string }
variable "approval_lambda_function_name" {
  type    = string
  default = ""
}
variable "approval_lambda_invoke_arn" {
  type    = string
  default = ""
}
variable "jwt_issuer" { type = string }
variable "jwt_audience" { type = list(string) }
variable "cors_allowed_origins" {
  type    = list(string)
  default = ["*"]
}
variable "log_retention_days" {
  type    = number
  default = 30
}
variable "tags" {
  type    = map(string)
  default = {}
}

variable "admin_lambda_function_name" {
  type    = string
  default = ""
}
variable "admin_lambda_invoke_arn" {
  type    = string
  default = ""
}
