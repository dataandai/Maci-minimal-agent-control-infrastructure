variable "name_prefix" {
  type = string
}

variable "object_lock_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
