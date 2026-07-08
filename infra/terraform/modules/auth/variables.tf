variable "name_prefix" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

variable "mfa_configuration" {
  type        = string
  default     = "OPTIONAL"
  description = "Cognito MFA mode: OFF, OPTIONAL or ON. Use ON for governed/fintech-style deployments, especially for approver/admin users."

  validation {
    condition     = contains(["OFF", "OPTIONAL", "ON"], var.mfa_configuration)
    error_message = "mfa_configuration must be OFF, OPTIONAL or ON."
  }
}

variable "advanced_security_mode" {
  type        = string
  default     = "OFF"
  description = "Cognito advanced security mode: OFF, AUDIT or ENFORCED. ENFORCED enables adaptive/compromised-credentials protection (has a per-MAU cost)."

  validation {
    condition     = contains(["OFF", "AUDIT", "ENFORCED"], var.advanced_security_mode)
    error_message = "advanced_security_mode must be OFF, AUDIT or ENFORCED."
  }
}
