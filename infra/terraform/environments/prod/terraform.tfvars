environment = "prod"
aws_region  = "eu-west-1"
owner       = "platform"

enable_real_bedrock  = true
enable_bedrock_agent = false

monthly_cost_alarm_usd = 500
lambda_build_python = "python3.12"
log_retention_days     = 90

cors_allowed_origins = ["https://app.example.com"]

# Production should use concrete tenant KB ARNs, not the default wildcard fallback.
allowed_knowledge_base_arns = [
  # "arn:aws:bedrock:eu-west-1:123456789012:knowledge-base/KBXXXXXXXX"
]

# Add SNS/PagerDuty/etc. action ARNs.
alarm_actions = []

require_agent_id = true
require_resource_ownership = true
allow_dev_knowledge_base_wildcard = false
allowed_bedrock_agent_source_arns = [
  # "arn:aws:bedrock:eu-west-1:123456789012:agent/AGENTID"
]

# Recovery daemon schedule and leasing.
recovery_schedule_expression = "rate(5 minutes)"
recovery_max_items           = 25
recovery_stale_seconds       = 300
recovery_lease_seconds       = 120
recovery_max_attempts        = 3

# API abuse protection and local redaction. Tune with real traffic and WAF sampled requests.
api_throttling_burst_limit = 500
api_throttling_rate_limit  = 250
enable_api_waf             = true
waf_rate_limit_per_5min    = 5000
waf_blocked_country_codes  = []
enable_pii_redaction       = true
pii_redaction_salt         = "maci-redaction-v1"

# Test-only live red-team RAG/tool-output override plumbing. Keep false in production.
enable_redteam_overrides = false
