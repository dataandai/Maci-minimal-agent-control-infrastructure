locals {
  name_prefix = "${var.environment}-${var.project_name}"

  metrics_namespace = "${var.environment}/Maci"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }

  source_dir = abspath("${path.module}/../../src")
  workflow_definition_path = abspath("${path.module}/../step-functions/agent_workflow.asl.json")

  allowed_model_arns = [
    for model_id in var.allowed_foundation_model_ids :
    startswith(model_id, "arn:") ? model_id : "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}::foundation-model/${model_id}"
  ]

  default_knowledge_base_arns = [
    "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
  ]

  effective_knowledge_base_arns = length(var.allowed_knowledge_base_arns) > 0 ? var.allowed_knowledge_base_arns : (var.allow_dev_knowledge_base_wildcard && var.environment == "dev" ? local.default_knowledge_base_arns : [])

  common_lambda_environment = {
    AUDIT_TABLE_NAME           = module.dynamodb.audit_table_name
    POLICY_TABLE_NAME          = module.dynamodb.policy_table_name
    USAGE_TABLE_NAME           = module.dynamodb.usage_table_name
    CIRCUIT_BREAKER_TABLE_NAME = module.dynamodb.circuit_breaker_table_name
    TICKET_TABLE_NAME          = module.dynamodb.ticket_table_name
    APPROVAL_TABLE_NAME        = module.dynamodb.approval_table_name
    AGENT_REGISTRY_TABLE_NAME      = module.dynamodb.agent_registry_table_name
    RESOURCE_OWNERSHIP_TABLE_NAME  = module.dynamodb.resource_ownership_table_name
    KILL_SWITCH_TABLE_NAME         = module.dynamodb.kill_switch_table_name
    MCP_REGISTRY_TABLE_NAME        = module.dynamodb.mcp_registry_table_name
    CONVERSATION_TABLE_NAME        = module.dynamodb.conversation_table_name
    CONVERSATION_TRANSCRIPT_BUCKET = aws_s3_bucket.conversation_transcripts.bucket
    WORKFLOW_STATE_TABLE_NAME      = module.dynamodb.workflow_state_table_name
    IDEMPOTENCY_TABLE_NAME         = module.dynamodb.idempotency_table_name
    AUDIT_ARCHIVE_BUCKET           = module.audit_archive.bucket_name
    REQUIRE_AGENT_ID               = tostring(var.require_agent_id)
    REQUIRE_RESOURCE_OWNERSHIP     = tostring(var.require_resource_ownership)
    ENABLE_REAL_BEDROCK        = tostring(var.enable_real_bedrock)
    ENABLE_REAL_GUARDRAIL_CHECKS = tostring(var.enable_real_guardrail_checks)
    CIRCUIT_BREAKER_THRESHOLD  = tostring(var.circuit_breaker_threshold)
    CIRCUIT_BREAKER_OPEN_SECONDS = tostring(var.circuit_breaker_open_seconds)
    RECOVERY_STALE_SECONDS     = tostring(var.recovery_stale_seconds)
    RECOVERY_LEASE_SECONDS     = tostring(var.recovery_lease_seconds)
    RECOVERY_MAX_ATTEMPTS      = tostring(var.recovery_max_attempts)
    RECOVERY_BACKOFF_SECONDS   = "60"
    RECOVERY_MAX_BACKOFF_SECONDS = "3600"
    RECOVERY_MAX_ITEMS         = tostring(var.recovery_max_items)
    RECOVERY_ACTIVE_SHARDS     = tostring(var.recovery_active_shards)
    METRICS_NAMESPACE          = local.metrics_namespace
    ENABLE_PII_REDACTION       = tostring(var.enable_pii_redaction)
    PII_REDACTION_SALT         = var.pii_redaction_salt
    ENABLE_REDTEAM_OVERRIDES   = tostring(var.enable_redteam_overrides)
    REDTEAM_OVERRIDE_ROLES      = join(",", var.redteam_override_roles)
  }

  dynamodb_crud_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:BatchWriteItem",
    "dynamodb:ConditionCheckItem",
    "dynamodb:DeleteItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:UpdateItem"
  ]

  dynamodb_read_actions = [
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:Query"
  ]

  # Audit writers must be append-only. They may put new events, read/advance the
  # per-tenant hash-chain head, and run the append transaction, but must never be
  # able to delete or bulk-overwrite audit history. Deliberately excludes
  # DeleteItem, BatchWriteItem and Scan.
  dynamodb_audit_append_actions = [
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:GetItem",
    "dynamodb:ConditionCheckItem",
    "dynamodb:DescribeTable"
  ]

  workflow_lambda_names = [
    module.workflow_validate.function_name,
    module.workflow_invoke_bedrock.function_name,
    module.workflow_finalize.function_name
  ]

  all_lambda_function_names = concat(
    [
      module.customer_lookup.function_name,
      module.ticket_creation.function_name,
      module.billing_check.function_name,
      module.account_credit.function_name,
      module.approval_review.function_name,
      module.admin.function_name,
      module.request_router.function_name,
      module.recovery_daemon.function_name,
    ],
    local.workflow_lambda_names
  )
}
