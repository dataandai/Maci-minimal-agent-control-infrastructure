variable "name_prefix" {
  type = string
}

variable "object_lock_retention_days" {
  type    = number
  default = 30
}

variable "object_lock_mode" {
  type        = string
  default     = "GOVERNANCE"
  description = "S3 Object Lock retention mode. Use COMPLIANCE in production so that even the root account cannot shorten retention or delete audit objects; GOVERNANCE is acceptable only for dev/lab."

  validation {
    condition     = contains(["GOVERNANCE", "COMPLIANCE"], var.object_lock_mode)
    error_message = "object_lock_mode must be GOVERNANCE or COMPLIANCE."
  }
}

variable "kms_key_arn" {
  type        = string
  default     = ""
  description = "Customer-managed KMS key ARN for archive object encryption. Empty falls back to SSE-S3 (dev/lab only)."
}

variable "log_bucket_id" {
  type        = string
  default     = ""
  description = "Target S3 bucket id for server access logging. Empty disables access logging."
}

variable "tags" {
  type    = map(string)
  default = {}
}
