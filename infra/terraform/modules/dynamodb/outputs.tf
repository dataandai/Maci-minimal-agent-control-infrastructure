output "audit_table_name" { value = aws_dynamodb_table.audit.name }
output "audit_table_arn" { value = aws_dynamodb_table.audit.arn }

output "policy_table_name" { value = aws_dynamodb_table.policy.name }
output "policy_table_arn" { value = aws_dynamodb_table.policy.arn }

output "usage_table_name" { value = aws_dynamodb_table.usage.name }
output "usage_table_arn" { value = aws_dynamodb_table.usage.arn }

output "circuit_breaker_table_name" { value = aws_dynamodb_table.circuit_breaker.name }
output "circuit_breaker_table_arn" { value = aws_dynamodb_table.circuit_breaker.arn }

output "ticket_table_name" { value = aws_dynamodb_table.ticket.name }
output "ticket_table_arn" { value = aws_dynamodb_table.ticket.arn }

output "agent_registry_table_name" { value = aws_dynamodb_table.agent_registry.name }
output "agent_registry_table_arn" { value = aws_dynamodb_table.agent_registry.arn }

output "approval_table_name" { value = aws_dynamodb_table.approval.name }
output "approval_table_arn" { value = aws_dynamodb_table.approval.arn }

output "resource_ownership_table_name" { value = aws_dynamodb_table.resource_ownership.name }
output "resource_ownership_table_arn" { value = aws_dynamodb_table.resource_ownership.arn }

output "kill_switch_table_name" { value = aws_dynamodb_table.kill_switch.name }
output "kill_switch_table_arn" { value = aws_dynamodb_table.kill_switch.arn }

output "mcp_registry_table_name" { value = aws_dynamodb_table.mcp_registry.name }
output "mcp_registry_table_arn" { value = aws_dynamodb_table.mcp_registry.arn }
