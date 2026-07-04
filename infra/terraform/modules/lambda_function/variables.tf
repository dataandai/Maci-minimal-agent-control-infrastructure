variable "function_name" { type = string }
variable "description" {
  type    = string
  default = ""
}
variable "source_dir" { type = string }
variable "handler" { type = string }
variable "python_bin" {
  description = "Python executable used for local dependency packaging."
  type        = string
  default     = "python3.12"
}
variable "runtime" {
  type    = string
  default = "python3.12"
}
variable "memory_size" {
  type    = number
  default = 512
}
variable "timeout" {
  type    = number
  default = 30
}
variable "reserved_concurrent_executions" {
  type    = number
  default = null
}
variable "environment_variables" {
  type    = map(string)
  default = {}
}
variable "policy_statements" {
  description = "Additional IAM policy statements attached inline to the Lambda execution role."
  type        = list(any)
  default     = []
}
variable "log_retention_days" {
  type    = number
  default = 30
}
variable "tags" {
  type    = map(string)
  default = {}
}
