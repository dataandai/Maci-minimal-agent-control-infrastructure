resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/vendedlogs/states/${var.name_prefix}-workflow"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_iam_role" "this" {
  name = "${var.name_prefix}-workflow-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "this" {
  name = "${var.name_prefix}-workflow-policy"
  role = aws_iam_role.this.id

  # The logs:*LogDelivery actions used by Step Functions vended logging do not
  # support resource-level scoping and require Resource "*" per AWS docs.
  #tfsec:ignore:aws-iam-no-policy-wildcards
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeWorkflowLambdas"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          var.validate_lambda_arn,
          var.invoke_bedrock_lambda_arn,
          var.finalize_lambda_arn
        ]
      },
      {
        Sid    = "WriteWorkflowLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "this" {
  name     = "${var.name_prefix}-workflow"
  role_arn = aws_iam_role.this.arn
  type     = "EXPRESS"

  definition = templatefile(var.definition_path, {
    ValidateWorkflowFunctionArn      = var.validate_lambda_arn
    InvokeBedrockWorkflowFunctionArn = var.invoke_bedrock_lambda_arn
    FinalizeWorkflowFunctionArn      = var.finalize_lambda_arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.this.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tracing_configuration {
    enabled = true
  }

  tags = var.tags
}
