variable "project_name" {
  description = "Short product/system name used in AWS resource names."
  type        = string
  default     = "maci"
}

variable "environment" {
  description = "Deployment environment, for example dev, staging or prod."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "environment must contain only lowercase letters, numbers and hyphens."
  }
}

variable "aws_region" {
  description = "AWS region where the stack will be deployed. Bedrock model and Agent availability is region-dependent."
  type        = string
  default     = "eu-west-1"
}

variable "owner" {
  description = "Owner tag value."
  type        = string
  default     = "platform"
}

variable "enable_real_bedrock" {
  description = "When false, the Python Bedrock gateway returns deterministic stub responses. Set true only after model access is enabled."
  type        = bool
  default     = false
}

variable "enable_bedrock_agent" {
  description = "When true, the router invokes an existing Bedrock Agent alias using bedrock_agent_id and bedrock_agent_alias_id."
  type        = bool
  default     = false
}

variable "bedrock_agent_id" {
  description = "Existing Bedrock Agent ID used by the router when enable_bedrock_agent=true. Terraform core stack does not create the agent by default."
  type        = string
  default     = ""
}

variable "bedrock_agent_alias_id" {
  description = "Existing Bedrock Agent alias ID used by the router when enable_bedrock_agent=true."
  type        = string
  default     = ""
}

variable "allowed_bedrock_agent_alias_arns" {
  description = "Optional IAM allowlist for Bedrock Agent aliases that the request router may invoke. Leave empty while Bedrock Agent integration is disabled."
  type        = list(string)
  default     = []
}

variable "allowed_bedrock_agent_source_arns" {
  description = "Concrete Bedrock Agent ARNs allowed to invoke action-group tool Lambdas. Empty means no Bedrock service principal invoke permission is created."
  type        = list(string)
  default     = []
}

variable "allowed_foundation_model_ids" {
  description = "Foundation model IDs allowed for direct Bedrock invocation. IDs are converted to foundation-model ARNs."
  type        = list(string)
  default = [
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "amazon.nova-pro-v1:0",
    "amazon.nova-lite-v1:0"
  ]
}

variable "allowed_knowledge_base_arns" {
  description = "Knowledge Base ARNs the request router can retrieve from. Use concrete tenant KB ARNs in production."
  type        = list(string)
  default     = []
}

variable "request_router_reserved_concurrency" {
  description = "Reserved concurrency for the public request router Lambda."
  type        = number
  default     = 20
}


variable "lambda_build_python" {
  description = "Python executable used by Terraform local packaging. Use a version compatible with the Lambda runtime, for example python3.12."
  type        = string
  default     = "python3.12"
}

variable "lambda_memory_size" {
  description = "Default Lambda memory size in MB."
  type        = number
  default     = 512
}

variable "lambda_timeout_seconds" {
  description = "Default Lambda timeout in seconds."
  type        = number
  default     = 30
}

variable "circuit_breaker_threshold" {
  description = "Number of failures before a tenant-scoped circuit breaker opens."
  type        = number
  default     = 3
}

variable "circuit_breaker_open_seconds" {
  description = "TTL/recovery window for circuit breaker open state."
  type        = number
  default     = 300
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for Lambda and API access logs."
  type        = number
  default     = 30
}

variable "monthly_cost_alarm_usd" {
  description = "Estimated custom metric cost alarm threshold for the control-plane ledger."
  type        = number
  default     = 100
}

variable "alarm_actions" {
  description = "Optional SNS topic ARNs or other alarm actions. Empty list means alarms are created without notifications."
  type        = list(string)
  default     = []
}

variable "cors_allowed_origins" {
  description = "Allowed origins for API Gateway CORS. Tighten this in staging/prod."
  type        = list(string)
  default     = ["*"]
}

variable "require_agent_id" {
  description = "When true, Bedrock tool Lambdas require an agent_id in trusted sessionAttributes. Keep false for first local/dev lab runs."
  type        = bool
  default     = false
}

variable "require_resource_ownership" {
  description = "When true, tool Lambdas require an explicit resource->tenant ownership record instead of allowing prefix-only demo fallback."
  type        = bool
  default     = false
}

variable "allow_dev_knowledge_base_wildcard" {
  description = "Allow wildcard Knowledge Base IAM access only for beginner dev lab mode. Production should set concrete allowed_knowledge_base_arns."
  type        = bool
  default     = true
}

variable "audit_archive_retention_days" {
  description = "Default Object Lock governance retention period for immutable audit archive objects."
  type        = number
  default     = 30
}
