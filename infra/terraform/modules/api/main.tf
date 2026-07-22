resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.name_prefix}-http-api"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.logs_kms_key_arn
  tags              = var.tags
}

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["authorization", "content-type", "x-request-id"]
    allow_methods = ["POST", "OPTIONS"]
    allow_origins = var.cors_allowed_origins
    max_age       = 300
  }

  tags = var.tags
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.this.id
  name             = "${var.name_prefix}-jwt-authorizer"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = var.jwt_audience
    issuer   = var.jwt_issuer
  }
}

resource "aws_apigatewayv2_integration" "router" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "invoke" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /agent/invoke"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
  target             = "integrations/${aws_apigatewayv2_integration.router.id}"
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = var.environment
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = var.throttling_burst_limit
    throttling_rate_limit  = var.throttling_rate_limit
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
    })
  }

  tags = var.tags
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_apigatewayv2_integration" "approval" {
  count                  = var.approval_lambda_invoke_arn == "" ? 0 : 1
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.approval_lambda_invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "approval_decision" {
  count              = var.approval_lambda_invoke_arn == "" ? 0 : 1
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /approvals/decide"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
  target             = "integrations/${aws_apigatewayv2_integration.approval[0].id}"
}

resource "aws_lambda_permission" "api_gateway_approval" {
  count         = var.approval_lambda_function_name == "" ? 0 : 1
  statement_id  = "AllowAPIGatewayInvokeApproval"
  action        = "lambda:InvokeFunction"
  function_name = var.approval_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_apigatewayv2_integration" "admin" {
  count                  = var.admin_lambda_invoke_arn == "" ? 0 : 1
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.admin_lambda_invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "admin_control_plane" {
  count              = var.admin_lambda_invoke_arn == "" ? 0 : 1
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /admin/control-plane"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
  target             = "integrations/${aws_apigatewayv2_integration.admin[0].id}"
}

resource "aws_lambda_permission" "api_gateway_admin" {
  count         = var.admin_lambda_function_name == "" ? 0 : 1
  statement_id  = "AllowAPIGatewayInvokeAdmin"
  action        = "lambda:InvokeFunction"
  function_name = var.admin_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}


resource "aws_wafv2_web_acl" "api" {
  count       = var.enable_waf ? 1 : 0
  name        = "${var.name_prefix}-api-waf"
  description = "Abuse protection for the governed agent HTTP API. Complements tenant budget checks."
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit-by-source-ip"
    priority = 10

    action {
      block {}
    }

    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = var.waf_rate_limit_per_5min
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-api-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-common-rule-set"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-api-waf-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-known-bad-inputs"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-api-waf-known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  dynamic "rule" {
    for_each = length(var.waf_blocked_country_codes) > 0 ? [1] : []
    content {
      name     = "block-configured-countries"
      priority = 40

      action {
        block {}
      }

      statement {
        geo_match_statement {
          country_codes = var.waf_blocked_country_codes
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.name_prefix}-api-waf-geo-block"
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name_prefix}-api-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

resource "aws_wafv2_web_acl_association" "api_stage" {
  count        = var.enable_waf ? 1 : 0
  resource_arn = aws_apigatewayv2_stage.this.arn
  web_acl_arn  = aws_wafv2_web_acl.api[0].arn
}

# WAF traffic logging (CKV2_AWS_31). CloudWatch destination log groups must be
# named with the aws-waf-logs- prefix.
resource "aws_cloudwatch_log_group" "waf" {
  count             = var.enable_waf ? 1 : 0
  name              = "aws-waf-logs-${var.name_prefix}-api"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.logs_kms_key_arn
  tags              = var.tags
}

resource "aws_wafv2_web_acl_logging_configuration" "api" {
  count                   = var.enable_waf ? 1 : 0
  log_destination_configs = [aws_cloudwatch_log_group.waf[0].arn]
  resource_arn            = aws_wafv2_web_acl.api[0].arn
}
