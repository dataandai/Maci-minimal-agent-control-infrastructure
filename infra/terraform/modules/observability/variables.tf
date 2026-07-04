variable "name_prefix" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "metrics_namespace" { type = string }
variable "api_name" { type = string }
variable "lambda_function_names" { type = list(string) }
variable "dynamodb_table_names" { type = list(string) }
variable "monthly_cost_alarm_usd" { type = number }
variable "alarm_actions" {
  type    = list(string)
  default = []
}
variable "tags" {
  type    = map(string)
  default = {}
}
