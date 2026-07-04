locals {
  build_dir  = abspath("${path.root}/.terraform-build/${var.function_name}")
  output_zip = abspath("${path.root}/.terraform-build/${var.function_name}.zip")

  source_files = fileset(var.source_dir, "**")
  source_hash  = sha256(join("", [for file in local.source_files : filesha256("${var.source_dir}/${file}")]))
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_iam_role" "this" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "xray" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

resource "aws_iam_role_policy" "inline" {
  count = length(var.policy_statements) > 0 ? 1 : 0
  name  = "${var.function_name}-inline"
  role  = aws_iam_role.this.id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = var.policy_statements
  })
}

resource "null_resource" "package" {
  triggers = {
    source_hash = local.source_hash
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command = <<EOT
set -euo pipefail
rm -rf "${local.build_dir}"
mkdir -p "${local.build_dir}"
${var.python_bin} -m pip install --upgrade -r "${var.source_dir}/requirements.txt" -t "${local.build_dir}" >/dev/null
cp -R "${var.source_dir}/maci" "${local.build_dir}/"
EOT
  }
}

data "archive_file" "package" {
  type        = "zip"
  source_dir  = local.build_dir
  output_path = local.output_zip

  depends_on = [null_resource.package]
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  description   = var.description
  role          = aws_iam_role.this.arn
  handler       = var.handler
  runtime       = var.runtime
  memory_size   = var.memory_size
  timeout       = var.timeout

  filename         = data.archive_file.package.output_path
  source_code_hash = data.archive_file.package.output_base64sha256

  reserved_concurrent_executions = var.reserved_concurrent_executions

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = var.environment_variables
  }

  depends_on = [
    aws_cloudwatch_log_group.this,
    aws_iam_role_policy_attachment.basic,
    aws_iam_role_policy_attachment.xray,
    aws_iam_role_policy.inline
  ]

  tags = var.tags
}
