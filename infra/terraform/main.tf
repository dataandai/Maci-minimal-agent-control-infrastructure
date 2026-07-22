module "dynamodb" {
  source      = "./modules/dynamodb"
  name_prefix = local.name_prefix
  kms_key_arn = aws_kms_key.data.arn
  tags        = local.tags
}

module "audit_archive" {
  source                     = "./modules/audit_archive"
  name_prefix                = local.name_prefix
  object_lock_retention_days = var.audit_archive_retention_days
  object_lock_mode           = var.audit_archive_object_lock_mode
  kms_key_arn                = aws_kms_key.data.arn
  log_bucket_id              = aws_s3_bucket.access_logs.id
  tags                       = local.tags
}

resource "aws_s3_bucket" "conversation_transcripts" {
  bucket        = "${local.name_prefix}-conversation-transcripts-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  force_destroy = var.environment == "dev"

  tags = merge(local.tags, { DataClass = "conversation-transcript" })
}

resource "aws_s3_bucket_public_access_block" "conversation_transcripts" {
  bucket                  = aws_s3_bucket.conversation_transcripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "conversation_transcripts" {
  bucket = aws_s3_bucket.conversation_transcripts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "conversation_transcripts" {
  bucket = aws_s3_bucket.conversation_transcripts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
    bucket_key_enabled = true
  }
}

# Deny any non-TLS access to transcripts, which may contain customer PII.
resource "aws_s3_bucket_policy" "conversation_transcripts" {
  bucket = aws_s3_bucket.conversation_transcripts.id
  policy = data.aws_iam_policy_document.conversation_transcripts_tls.json
}

data "aws_iam_policy_document" "conversation_transcripts_tls" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.conversation_transcripts.arn,
      "${aws_s3_bucket.conversation_transcripts.arn}/*"
    ]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# Server access logging for the transcript bucket.
resource "aws_s3_bucket" "access_logs" {
  bucket        = "${local.name_prefix}-access-logs-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  force_destroy = var.environment == "dev"
  tags          = merge(local.tags, { DataClass = "access-logs" })
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = var.log_retention_days
    }
  }
}

data "aws_iam_policy_document" "access_logs" {
  statement {
    sid     = "AllowS3ServerAccessLogging"
    effect  = "Allow"
    actions = ["s3:PutObject"]
    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }
    resources = ["${aws_s3_bucket.access_logs.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.access_logs.arn, "${aws_s3_bucket.access_logs.arn}/*"]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  policy = data.aws_iam_policy_document.access_logs.json
}

resource "aws_s3_bucket_logging" "conversation_transcripts" {
  bucket        = aws_s3_bucket.conversation_transcripts.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "conversation-transcripts/"
}

resource "aws_s3_bucket_lifecycle_configuration" "conversation_transcripts" {
  bucket = aws_s3_bucket.conversation_transcripts.id

  rule {
    id     = "expire-conversation-transcripts"
    status = "Enabled"

    filter {}

    expiration {
      days = var.conversation_transcript_retention_days
    }
  }
}

module "auth" {
  source                 = "./modules/auth"
  name_prefix            = local.name_prefix
  mfa_configuration      = var.cognito_mfa_configuration
  advanced_security_mode = var.cognito_advanced_security_mode
  tags                   = local.tags
}

module "customer_lookup" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-customer-lookup"
  description           = "Tenant-scoped customer lookup action group Lambda"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.agent_tools.customer_lookup.handler.lambda_handler"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid      = "ReadTenantPolicies"
      Effect   = "Allow"
      Action   = local.dynamodb_read_actions
      Resource = [module.dynamodb.policy_table_arn, module.dynamodb.agent_registry_table_arn, module.dynamodb.resource_ownership_table_arn, module.dynamodb.kill_switch_table_arn, module.dynamodb.mcp_registry_table_arn]
    },
    {
      Sid      = "WriteAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    }
  ]
}

module "ticket_creation" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-ticket-creation"
  description           = "Tenant-scoped ticket creation action group Lambda with idempotency"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.agent_tools.ticket_creation.handler.lambda_handler"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid      = "ReadTenantPolicies"
      Effect   = "Allow"
      Action   = local.dynamodb_read_actions
      Resource = [module.dynamodb.policy_table_arn, module.dynamodb.agent_registry_table_arn, module.dynamodb.resource_ownership_table_arn, module.dynamodb.kill_switch_table_arn, module.dynamodb.mcp_registry_table_arn]
    },
    {
      Sid      = "WriteAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    },
    {
      Sid      = "ManageTicketIdempotency"
      Effect   = "Allow"
      Action   = local.dynamodb_crud_actions
      Resource = [module.dynamodb.ticket_table_arn]
    }
  ]
}


module "billing_check" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-billing-check"
  description           = "Tenant-scoped read-only billing check action group Lambda"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.agent_tools.billing_check.handler.lambda_handler"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid      = "ReadTenantPoliciesAndAgentRegistry"
      Effect   = "Allow"
      Action   = local.dynamodb_read_actions
      Resource = [module.dynamodb.policy_table_arn, module.dynamodb.agent_registry_table_arn, module.dynamodb.resource_ownership_table_arn, module.dynamodb.kill_switch_table_arn, module.dynamodb.mcp_registry_table_arn]
    },
    {
      Sid      = "WriteAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    }
  ]
}

module "account_credit" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-account-credit"
  description           = "High-risk account credit action group Lambda with human approval"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.agent_tools.account_credit.handler.lambda_handler"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid      = "ReadTenantPoliciesAndAgentRegistry"
      Effect   = "Allow"
      Action   = local.dynamodb_read_actions
      Resource = [module.dynamodb.policy_table_arn, module.dynamodb.agent_registry_table_arn, module.dynamodb.resource_ownership_table_arn, module.dynamodb.kill_switch_table_arn, module.dynamodb.mcp_registry_table_arn]
    },
    {
      Sid      = "ManageApprovals"
      Effect   = "Allow"
      Action   = local.dynamodb_crud_actions
      Resource = [module.dynamodb.approval_table_arn]
    },
    {
      Sid      = "ManageOperationIdempotency"
      Effect   = "Allow"
      Action   = local.dynamodb_crud_actions
      Resource = [module.dynamodb.idempotency_table_arn]
    },
    {
      Sid      = "WriteAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    }
  ]
}

module "approval_review" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-approval-review"
  description           = "Human approval endpoint for high-risk agent actions"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.approval_review.handler.lambda_handler"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid      = "ManageApprovals"
      Effect   = "Allow"
      Action   = local.dynamodb_crud_actions
      Resource = [module.dynamodb.approval_table_arn]
    },
    {
      Sid      = "WriteAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    }
  ]
}

module "workflow_validate" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-workflow-validate"
  description           = "Step Functions workflow input validation"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.workflow_steps.validate_workflow_input"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags
}

module "workflow_invoke_bedrock" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-workflow-bedrock"
  description           = "Step Functions Bedrock invocation step"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.workflow_steps.invoke_bedrock_step"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid      = "InvokeAllowlistedFoundationModels"
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel", "bedrock:Converse"]
      Resource = local.allowed_model_arns
    }
  ]
}

module "workflow_finalize" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-workflow-finalize"
  description           = "Step Functions workflow finalizer"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.workflow_steps.finalize_workflow"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags
}

module "workflow" {
  source                    = "./modules/stepfunctions"
  name_prefix               = local.name_prefix
  definition_path           = local.workflow_definition_path
  validate_lambda_arn       = module.workflow_validate.function_arn
  invoke_bedrock_lambda_arn = module.workflow_invoke_bedrock.function_arn
  finalize_lambda_arn       = module.workflow_finalize.function_arn
  log_retention_days        = var.log_retention_days
  tags                      = local.tags
}

module "request_router" {
  source                         = "./modules/lambda_function"
  function_name                  = "${local.name_prefix}-request-router"
  description                    = "Public deterministic Maci request boundary"
  source_dir                     = local.source_dir
  python_bin                     = var.lambda_build_python
  handler                        = "maci.request_router.lambda_handler"
  runtime                        = "python3.12"
  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout_seconds
  reserved_concurrent_executions = var.request_router_reserved_concurrency
  log_retention_days             = var.log_retention_days

  environment_variables = merge(local.common_lambda_environment, {
    WORKFLOW_STATE_MACHINE_ARN = module.workflow.state_machine_arn
    ENABLE_BEDROCK_AGENT       = tostring(var.enable_bedrock_agent)
    BEDROCK_AGENT_ID           = var.bedrock_agent_id
    BEDROCK_AGENT_ALIAS_ID     = var.bedrock_agent_alias_id
  })

  tags = local.tags

  policy_statements = concat(
    [
      {
        Sid    = "ManageControlPlaneTables"
        Effect = "Allow"
        Action = local.dynamodb_crud_actions
        Resource = [
          module.dynamodb.policy_table_arn,
          module.dynamodb.usage_table_arn,
          module.dynamodb.circuit_breaker_table_arn,
          module.dynamodb.ticket_table_arn,
          module.dynamodb.approval_table_arn,
          module.dynamodb.agent_registry_table_arn,
          module.dynamodb.resource_ownership_table_arn,
          module.dynamodb.kill_switch_table_arn,
          module.dynamodb.mcp_registry_table_arn,
          module.dynamodb.conversation_table_arn,
          module.dynamodb.workflow_state_table_arn,
          module.dynamodb.idempotency_table_arn
        ]
      },
      {
        Sid      = "AppendAuditEvents"
        Effect   = "Allow"
        Action   = local.dynamodb_audit_append_actions
        Resource = [module.dynamodb.audit_table_arn]
      },
      {
        Sid      = "WriteImmutableAuditArchive"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${module.audit_archive.bucket_arn}/*"]
      },
      {
        Sid      = "WriteConversationTranscripts"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${aws_s3_bucket.conversation_transcripts.arn}/*"]
      },
      {
        Sid      = "StartGovernedWorkflow"
        Effect   = "Allow"
        Action   = ["states:StartSyncExecution"]
        Resource = [module.workflow.state_machine_arn]
      },
      {
        Sid    = "InvokeAllowlistedFoundationModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:Converse",
          "bedrock:ConverseStream"
        ]
        Resource = local.allowed_model_arns
      },
    ],
    length(local.effective_knowledge_base_arns) > 0 ? [
      {
        Sid      = "RetrieveFromTenantKnowledgeBases"
        Effect   = "Allow"
        Action   = ["bedrock:Retrieve"]
        Resource = local.effective_knowledge_base_arns
      }
    ] : [],
    length(var.allowed_bedrock_agent_alias_arns) > 0 ? [
      {
        Sid      = "InvokeGovernedBedrockAgentAliases"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeAgent"]
        Resource = var.allowed_bedrock_agent_alias_arns
      }
    ] : []
  )
}


module "recovery_daemon" {
  source                         = "./modules/lambda_function"
  function_name                  = "${local.name_prefix}-recovery-daemon"
  description                    = "Scheduled lease-based recovery daemon for stale governed agent workflows"
  source_dir                     = local.source_dir
  python_bin                     = var.lambda_build_python
  handler                        = "maci.recovery.lambda_handler"
  runtime                        = "python3.12"
  memory_size                    = var.lambda_memory_size
  timeout                        = 60
  reserved_concurrent_executions = 1
  log_retention_days             = var.log_retention_days
  environment_variables          = local.common_lambda_environment
  tags                           = local.tags

  policy_statements = [
    {
      Sid    = "ManageRecoveryTables"
      Effect = "Allow"
      Action = local.dynamodb_crud_actions
      Resource = [
        module.dynamodb.workflow_state_table_arn,
        module.dynamodb.conversation_table_arn,
        module.dynamodb.idempotency_table_arn
      ]
    },
    {
      Sid      = "AppendAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    },
    {
      Sid      = "WriteConversationRecoveryStatus"
      Effect   = "Allow"
      Action   = ["s3:PutObject"]
      Resource = ["${aws_s3_bucket.conversation_transcripts.arn}/*"]
    }
  ]
}

resource "aws_cloudwatch_event_rule" "recovery_daemon" {
  name                = "${local.name_prefix}-recovery-daemon"
  description         = "Periodic stale workflow recovery reconciliation"
  schedule_expression = var.recovery_schedule_expression
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "recovery_daemon" {
  rule      = aws_cloudwatch_event_rule.recovery_daemon.name
  target_id = "${local.name_prefix}-recovery-daemon"
  arn       = module.recovery_daemon.function_arn
  input     = jsonencode({ max_items = var.recovery_max_items })
}

resource "aws_lambda_permission" "allow_eventbridge_recovery_daemon" {
  statement_id  = "AllowEventBridgeRecoveryDaemon"
  action        = "lambda:InvokeFunction"
  function_name = module.recovery_daemon.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.recovery_daemon.arn
}


module "admin" {
  source                = "./modules/lambda_function"
  function_name         = "${local.name_prefix}-admin"
  description           = "Role-gated Maci control-plane admin endpoint"
  source_dir            = local.source_dir
  python_bin            = var.lambda_build_python
  handler               = "maci.admin.handler.lambda_handler"
  runtime               = "python3.12"
  memory_size           = var.lambda_memory_size
  timeout               = var.lambda_timeout_seconds
  log_retention_days    = var.log_retention_days
  environment_variables = local.common_lambda_environment
  tags                  = local.tags

  policy_statements = [
    {
      Sid    = "ManageControlPlaneAdminTables"
      Effect = "Allow"
      Action = local.dynamodb_crud_actions
      Resource = [
        module.dynamodb.agent_registry_table_arn,
        module.dynamodb.resource_ownership_table_arn,
        module.dynamodb.kill_switch_table_arn
      ]
    },
    {
      Sid      = "AppendAuditEvents"
      Effect   = "Allow"
      Action   = local.dynamodb_audit_append_actions
      Resource = [module.dynamodb.audit_table_arn]
    }
  ]
}

module "api" {
  source                        = "./modules/api"
  name_prefix                   = local.name_prefix
  environment                   = var.environment
  lambda_function_name          = module.request_router.function_name
  lambda_invoke_arn             = module.request_router.invoke_arn
  approval_lambda_function_name = module.approval_review.function_name
  approval_lambda_invoke_arn    = module.approval_review.invoke_arn
  admin_lambda_function_name    = module.admin.function_name
  admin_lambda_invoke_arn       = module.admin.invoke_arn
  jwt_issuer                    = module.auth.issuer
  jwt_audience                  = [module.auth.user_pool_client_id]
  cors_allowed_origins          = var.cors_allowed_origins
  log_retention_days            = var.log_retention_days
  throttling_burst_limit        = var.api_throttling_burst_limit
  throttling_rate_limit         = var.api_throttling_rate_limit
  enable_waf                    = var.enable_api_waf
  waf_rate_limit_per_5min       = var.waf_rate_limit_per_5min
  waf_blocked_country_codes     = var.waf_blocked_country_codes
  tags                          = local.tags
}

locals {
  bedrock_tool_permissions = {
    for pair in setproduct(toset(var.allowed_bedrock_agent_source_arns), toset([
      "customer_lookup",
      "ticket_creation",
      "billing_check",
      "account_credit"
      ])) : "${pair[1]}-${replace(replace(pair[0], ":", "-"), "/", "-")}" => {
      source_arn = pair[0]
      function_name = {
        customer_lookup = module.customer_lookup.function_name
        ticket_creation = module.ticket_creation.function_name
        billing_check   = module.billing_check.function_name
        account_credit  = module.account_credit.function_name
      }[pair[1]]
    }
  }
}

resource "aws_lambda_permission" "bedrock_tool_invoke" {
  for_each       = local.bedrock_tool_permissions
  statement_id   = "AllowBedrockAgent${substr(sha1(each.key), 0, 16)}"
  action         = "lambda:InvokeFunction"
  function_name  = each.value.function_name
  principal      = "bedrock.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
  source_arn     = each.value.source_arn
}

module "observability" {
  source                = "./modules/observability"
  name_prefix           = local.name_prefix
  environment           = var.environment
  aws_region            = var.aws_region
  metrics_namespace     = local.metrics_namespace
  api_name              = module.api.api_name
  lambda_function_names = local.all_lambda_function_names
  dynamodb_table_names = [
    module.dynamodb.audit_table_name,
    module.dynamodb.policy_table_name,
    module.dynamodb.usage_table_name,
    module.dynamodb.circuit_breaker_table_name,
    module.dynamodb.ticket_table_name,
    module.dynamodb.approval_table_name,
    module.dynamodb.agent_registry_table_name,
    module.dynamodb.resource_ownership_table_name,
    module.dynamodb.kill_switch_table_name,
    module.dynamodb.mcp_registry_table_name,
    module.dynamodb.conversation_table_name,
    module.dynamodb.workflow_state_table_name,
    module.dynamodb.idempotency_table_name
  ]
  monthly_cost_alarm_usd = var.monthly_cost_alarm_usd
  alarm_actions          = var.alarm_actions
  tags                   = local.tags
}
