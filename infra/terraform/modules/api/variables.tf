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
  default = 365
}
variable "logs_kms_key_arn" {
  description = "CMK used to encrypt API access-log and WAF-log CloudWatch log groups. Null falls back to AWS-managed encryption."
  type        = string
  default     = null
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


variable "throttling_burst_limit" {
  description = "API Gateway HTTP API stage burst limit. Use conservative defaults for dev and tighten per environment."
  type        = number
  default     = 100
}

variable "throttling_rate_limit" {
  description = "API Gateway HTTP API stage steady-state requests per second limit. This is separate from tenant budget checks."
  type        = number
  default     = 50
}

variable "enable_waf" {
  description = "Attach an AWS WAFv2 WebACL to the API Gateway stage. Recommended for shared dev/staging/prod."
  type        = bool
  default     = true
}

variable "waf_rate_limit_per_5min" {
  description = "AWS WAF rate-based rule limit per 5-minute evaluation window. This is an abuse-control layer, not tenant billing."
  type        = number
  default     = 1000
}

variable "waf_blocked_country_codes" {
  description = "Optional ISO country codes to block at WAF. Empty by default."
  type        = list(string)
  default     = []
}
