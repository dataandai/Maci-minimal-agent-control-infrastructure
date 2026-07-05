environment = "staging"
aws_region  = "eu-west-1"
owner       = "platform"

enable_real_bedrock  = false
enable_bedrock_agent = false

monthly_cost_alarm_usd = 100
lambda_build_python = "python3.12"
log_retention_days     = 30

cors_allowed_origins = ["https://staging.example.com"]
allowed_knowledge_base_arns = []
alarm_actions = []

require_agent_id = true
require_resource_ownership = true
allow_dev_knowledge_base_wildcard = false
allowed_bedrock_agent_source_arns = []

# Recovery daemon schedule and leasing.
recovery_schedule_expression = "rate(5 minutes)"
recovery_max_items           = 25
recovery_stale_seconds       = 300
recovery_lease_seconds       = 120
recovery_max_attempts        = 3

# API abuse protection and local redaction.
api_throttling_burst_limit = 200
api_throttling_rate_limit  = 100
enable_api_waf             = true
waf_rate_limit_per_5min    = 2000
waf_blocked_country_codes  = []
enable_pii_redaction       = true
pii_redaction_salt         = "maci-redaction-v1"

# Test-only live red-team RAG/tool-output override plumbing. Keep false in production.
redteam_override_roles = ["redteam-operator"]

enable_redteam_overrides = true
