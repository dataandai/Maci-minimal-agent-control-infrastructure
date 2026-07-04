environment = "dev"
aws_region  = "eu-west-1"
owner       = "adam"

enable_real_bedrock  = false
enable_bedrock_agent = false

monthly_cost_alarm_usd = 25
lambda_build_python = "python3.12"
log_retention_days     = 14

cors_allowed_origins = ["*"]

# For production, replace wildcard KB access with concrete tenant Knowledge Base ARNs.
allowed_knowledge_base_arns = []

# Add SNS topic ARNs after creating alert destinations.
alarm_actions = []

# Keep false for beginner lab mode; set true once Bedrock Agent sessionAttributes include agent_id.
require_agent_id = false
require_resource_ownership = false
allow_dev_knowledge_base_wildcard = true
allowed_bedrock_agent_source_arns = []
