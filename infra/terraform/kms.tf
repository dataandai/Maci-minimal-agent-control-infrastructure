# Customer-managed CMK for all MACI data at rest: DynamoDB control-plane tables,
# the immutable audit archive, and conversation transcripts (which may carry PII).
# An AWS-owned key gives no key policy, no rotation control and no revoke path,
# which is not acceptable for tenant PII and a tamper-evident audit trail.

data "aws_iam_policy_document" "data_key" {
  # Root delegation so the key stays manageable via IAM and is never orphaned.
  statement {
    sid    = "EnableAccountAdmin"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  # Allow only the MACI Lambda execution roles to use the key, and only through
  # the DynamoDB and S3 services in this region. This avoids editing every
  # Lambda role while still scoping usage tightly.
  statement {
    sid    = "AllowMaciRolesViaService"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
      "kms:CreateGrant"
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values = [
        "dynamodb.${var.aws_region}.amazonaws.com",
        "s3.${var.aws_region}.amazonaws.com"
      ]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values   = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.name_prefix}-*-role"]
    }
  }
}

resource "aws_kms_key" "data" {
  description             = "${local.name_prefix} data-at-rest CMK (DynamoDB, audit archive, transcripts)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.data_key.json
  tags                    = local.tags
}

resource "aws_kms_alias" "data" {
  name          = "alias/${local.name_prefix}-data"
  target_key_id = aws_kms_key.data.key_id
}
