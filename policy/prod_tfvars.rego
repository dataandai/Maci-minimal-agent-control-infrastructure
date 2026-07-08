package main

import rego.v1

# Deterministic guardrails on the production tfvars so an insecure value can
# never be merged silently. Run with:
#   conftest test infra/terraform/environments/prod/terraform.tfvars \
#     --parser hcl2 --policy policy
#
# These assert literal values only (not resolved plan state), which is exactly
# what we want for a fast, credential-free CI gate on operator-set flags.

deny contains msg if {
	input.enable_redteam_overrides == true
	msg := "prod: enable_redteam_overrides must be false (test-only injection channel)"
}

deny contains msg if {
	input.enable_real_guardrail_checks != true
	msg := "prod: enable_real_guardrail_checks must be true (guardrail must not run substring-only)"
}

deny contains msg if {
	input.cognito_mfa_configuration != "ON"
	msg := "prod: cognito_mfa_configuration must be ON"
}

deny contains msg if {
	input.cognito_advanced_security_mode != "ENFORCED"
	msg := "prod: cognito_advanced_security_mode must be ENFORCED"
}

deny contains msg if {
	input.audit_archive_object_lock_mode != "COMPLIANCE"
	msg := "prod: audit_archive_object_lock_mode must be COMPLIANCE (tamper-evident audit)"
}

deny contains msg if {
	some origin in input.cors_allowed_origins
	origin == "*"
	msg := "prod: cors_allowed_origins must not contain a wildcard"
}

deny contains msg if {
	input.allow_dev_knowledge_base_wildcard == true
	msg := "prod: allow_dev_knowledge_base_wildcard must be false"
}
