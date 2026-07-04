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
