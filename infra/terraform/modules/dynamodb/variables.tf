variable "name_prefix" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "kms_key_arn" {
  type        = string
  default     = ""
  description = "Customer-managed KMS key ARN for table encryption. Empty falls back to the AWS-owned key (dev/lab only)."
}
