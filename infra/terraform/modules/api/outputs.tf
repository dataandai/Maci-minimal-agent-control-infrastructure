output "api_id" { value = aws_apigatewayv2_api.this.id }
output "api_name" { value = aws_apigatewayv2_api.this.name }
output "invoke_url" { value = "${aws_apigatewayv2_stage.this.invoke_url}/agent/invoke" }
output "execution_arn" { value = aws_apigatewayv2_api.this.execution_arn }
