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

variable "enable_real_guardrail_checks" {
  description = "When true, the guardrail boundary calls the Bedrock ApplyGuardrail API and fails closed if it is unavailable. The local substring filter is only a first-pass check and is never authoritative on its own. Keep aligned with enable_real_bedrock in staging/prod."
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
    "anthropic.claude-sonnet-5",
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

variable "conversation_transcript_retention_days" {
  description = "Retention period for conversation transcripts. Set per environment according to the data-retention policy; this is a deliberate control, not a dev-only cleanup."
  type        = number
  default     = 90
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
  description = "Allowed origins for API Gateway CORS. Must be an explicit origin list; wildcard is only acceptable for a throwaway dev lab."
  type        = list(string)
  default     = []
}

variable "cognito_mfa_configuration" {
  description = "Cognito MFA mode: OFF, OPTIONAL or ON. Prod should use ON."
  type        = string
  default     = "OPTIONAL"
}

variable "cognito_advanced_security_mode" {
  description = "Cognito advanced security mode: OFF, AUDIT or ENFORCED. Prod should use ENFORCED (per-MAU cost applies)."
  type        = string
  default     = "OFF"
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
  description = "Default Object Lock retention period for immutable audit archive objects."
  type        = number
  default     = 30
}

variable "audit_archive_object_lock_mode" {
  description = "S3 Object Lock mode for the audit archive. COMPLIANCE makes objects immutable even for the root account; use it in production. GOVERNANCE is for dev/lab only."
  type        = string
  default     = "GOVERNANCE"
}


variable "recovery_schedule_expression" {
  description = "EventBridge schedule expression for the recovery daemon."
  type        = string
  default     = "rate(5 minutes)"
}

variable "recovery_max_items" {
  description = "Maximum stale workflows reconciled by the recovery daemon per run."
  type        = number
  default     = 25
}

variable "recovery_stale_seconds" {
  description = "Grace period before active workflows become eligible for recovery."
  type        = number
  default     = 300
}

variable "recovery_lease_seconds" {
  description = "Lease duration used by the recovery daemon to fence concurrent workers."
  type        = number
  default     = 120
}

variable "recovery_max_attempts" {
  description = "Maximum recovery attempts before a stale workflow is escalated to human review."
  type        = number
  default     = 3
}

variable "recovery_active_shards" {
  description = "Number of shard keys spreading active workflows across the recovery GSI to avoid a hot partition. Increase for high active-workflow volume."
  type        = number
  default     = 8
}


variable "api_throttling_burst_limit" {
  description = "API Gateway HTTP API stage burst limit for the public agent API. Separate from tenant budget checks."
  type        = number
  default     = 100
}

variable "api_throttling_rate_limit" {
  description = "API Gateway HTTP API stage steady-state requests per second limit for the public agent API."
  type        = number
  default     = 50
}

variable "enable_api_waf" {
  description = "Attach AWS WAFv2 WebACL to the public API Gateway stage."
  type        = bool
  default     = true
}

variable "waf_rate_limit_per_5min" {
  description = "AWS WAF rate-based block limit per source IP over the WAF evaluation window."
  type        = number
  default     = 1000
}

variable "waf_blocked_country_codes" {
  description = "Optional ISO country codes to block at WAF. Empty by default; use only when legally/operationally justified."
  type        = list(string)
  default     = []
}


variable "enable_redteam_overrides" {
  description = "Enable test-only red-team override request fields in dev/staging. Keep false in production."
  type        = bool
  default     = false
}

variable "redteam_override_roles" {
  description = "Caller roles allowed to use test-only red-team override request fields when enable_redteam_overrides=true. Keep narrow and do not grant to normal support users."
  type        = list(string)
  default     = ["redteam-operator"]
}

variable "enable_pii_redaction" {
  description = "Enable deterministic local PII/secrets redaction before storing transcripts and audit events."
  type        = bool
  default     = true
}

variable "pii_redaction_salt" {
  description = "Stable salt for redaction fingerprints. Do not use a secret required for decryption; this is for correlation only."
  type        = string
  default     = "maci-redaction-v1"
}
