variable "name_prefix" { type = string }
variable "definition_path" { type = string }
variable "validate_lambda_arn" { type = string }
variable "invoke_bedrock_lambda_arn" { type = string }
variable "finalize_lambda_arn" { type = string }
variable "log_retention_days" {
  type    = number
  default = 365
}
variable "kms_key_arn" {
  description = "CMK used to encrypt the workflow CloudWatch log group. Null falls back to AWS-managed encryption."
  type        = string
  default     = null
}
variable "tags" {
  type    = map(string)
  default = {}
}
