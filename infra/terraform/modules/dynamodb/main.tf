resource "aws_dynamodb_table" "audit" {
  name         = "${var.name_prefix}-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "event_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "policy" {
  name         = "${var.name_prefix}-policy"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "usage" {
  name         = "${var.name_prefix}-usage"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "event_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "circuit_breaker" {
  name         = "${var.name_prefix}-circuit-breaker"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "category"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "category"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "ticket" {
  name         = "${var.name_prefix}-ticket"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "ticket_key"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "ticket_key"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "agent_registry" {
  name         = "${var.name_prefix}-agent-registry"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "agent_id"

  attribute {
    name = "agent_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "approval" {
  name         = "${var.name_prefix}-approval"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "approval_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "approval_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "resource_ownership" {
  name         = "${var.name_prefix}-resource-ownership"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "resource_id"

  attribute {
    name = "resource_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "kill_switch" {
  name         = "${var.name_prefix}-kill-switch"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "scope"
  range_key    = "key"

  attribute {
    name = "scope"
    type = "S"
  }

  attribute {
    name = "key"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "mcp_registry" {
  name         = "${var.name_prefix}-mcp-registry"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "server_id"

  attribute {
    name = "server_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "conversation" {
  name         = "${var.name_prefix}-conversation"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "record_key"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "record_key"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "workflow_state" {
  name         = "${var.name_prefix}-workflow-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "workflow_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "workflow_id"
    type = "S"
  }

  attribute {
    name = "recovery_partition"
    type = "S"
  }

  attribute {
    name = "recovery_due_at_epoch"
    type = "N"
  }

  global_secondary_index {
    name            = "recovery_due_index"
    hash_key        = "recovery_partition"
    range_key       = "recovery_due_at_epoch"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  tags = var.tags
}

resource "aws_dynamodb_table" "idempotency" {
  name         = "${var.name_prefix}-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "idempotency_key"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  tags = var.tags
}
