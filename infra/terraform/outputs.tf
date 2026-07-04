output "agent_invoke_url" {
  description = "HTTP API endpoint for POST /agent/invoke."
  value       = module.api.invoke_url
}

output "cognito_user_pool_id" {
  value = module.auth.user_pool_id
}

output "cognito_user_pool_client_id" {
  value = module.auth.user_pool_client_id
}

output "policy_table_name" {
  value = module.dynamodb.policy_table_name
}

output "audit_table_name" {
  value = module.dynamodb.audit_table_name
}

output "usage_table_name" {
  value = module.dynamodb.usage_table_name
}

output "circuit_breaker_table_name" {
  value = module.dynamodb.circuit_breaker_table_name
}

output "ticket_table_name" {
  value = module.dynamodb.ticket_table_name
}

output "request_router_function_name" {
  value = module.request_router.function_name
}

output "customer_lookup_function_arn" {
  value = module.customer_lookup.function_arn
}

output "ticket_creation_function_arn" {
  value = module.ticket_creation.function_arn
}

output "workflow_state_machine_arn" {
  value = module.workflow.state_machine_arn
}

output "cloudwatch_dashboard_name" {
  value = module.observability.dashboard_name
}

output "approval_table_name" { value = module.dynamodb.approval_table_name }
output "agent_registry_table_name" { value = module.dynamodb.agent_registry_table_name }
output "audit_archive_bucket" { value = module.audit_archive.bucket_name }
output "billing_check_lambda_name" { value = module.billing_check.function_name }
output "account_credit_lambda_name" { value = module.account_credit.function_name }
output "approval_review_lambda_name" { value = module.approval_review.function_name }

output "resource_ownership_table_name" { value = module.dynamodb.resource_ownership_table_name }
output "kill_switch_table_name" { value = module.dynamodb.kill_switch_table_name }
output "mcp_registry_table_name" { value = module.dynamodb.mcp_registry_table_name }
output "admin_lambda_name" { value = module.admin.function_name }
