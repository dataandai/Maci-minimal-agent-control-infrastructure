variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name for Terraform state."
  type        = string
}

variable "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking."
  type        = string
  default     = "maci-tf-locks"
}
