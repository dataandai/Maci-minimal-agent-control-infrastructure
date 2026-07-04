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
