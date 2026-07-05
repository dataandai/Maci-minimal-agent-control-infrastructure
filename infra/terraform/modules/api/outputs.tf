output "api_id" { value = aws_apigatewayv2_api.this.id }
output "api_name" { value = aws_apigatewayv2_api.this.name }
output "invoke_url" { value = "${aws_apigatewayv2_stage.this.invoke_url}/agent/invoke" }
output "execution_arn" { value = aws_apigatewayv2_api.this.execution_arn }

output "waf_web_acl_arn" { value = try(aws_wafv2_web_acl.api[0].arn, null) }
output "throttling_burst_limit" { value = var.throttling_burst_limit }
output "throttling_rate_limit" { value = var.throttling_rate_limit }
