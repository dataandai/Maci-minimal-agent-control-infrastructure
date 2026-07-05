# API WAF, Rate Limiting, and PII Redaction

This document describes the v0.2.0 production-hardening layer that adds two controls that must exist before the system is exposed to real users or real tenant data:

1. API Gateway throttling and AWS WAF abuse protection.
2. Deterministic local PII/secrets redaction before transcripts and audit events are persisted.

These controls are intentionally separate from the existing tenant budget, policy, audit, and guardrail layers.

---

## 1. Why this layer exists

A governed agent system can still fail in two very practical ways:

```text
1. Too many requests reach the API before tenant budget controls can help.
2. Sensitive values are stored in transcript/audit/log records before humans notice.
```

The first problem is an availability and abuse-control issue.

The second problem is a privacy and compliance issue.

Neither should be delegated to the LLM.

---

## 2. API Gateway throttling

The Terraform API module now configures HTTP API stage throttling:

```hcl
throttling_burst_limit = var.api_throttling_burst_limit
throttling_rate_limit  = var.api_throttling_rate_limit
```

This is a coarse API-layer protection. It limits request pressure before the request router Lambda, policy engine, model calls, or tool handlers become involved.

It is not a replacement for:

```text
tenant budgets
usage ledger checks
circuit breakers
per-tool authorization
per-tenant quotas
```

It is an outer availability guardrail.

---

## 3. AWS WAF WebACL

The Terraform API module now creates and attaches a regional AWS WAFv2 WebACL to the API Gateway stage when `enable_api_waf=true`.

The WebACL includes:

```text
rate-limit-by-source-ip
AWSManagedRulesCommonRuleSet
AWSManagedRulesKnownBadInputsRuleSet
optional country block rule
```

The rate-based rule is configured by:

```hcl
waf_rate_limit_per_5min = 1000
```

This protects against obvious request floods and known-bad HTTP inputs before they reach the application.

Important limitation:

> WAF rate limiting is not tenant-aware business quota enforcement.

Tenant-aware controls still live in the request router, usage ledger, policy engine, and circuit breaker.

---

## 4. Configuration variables

Root Terraform variables:

```hcl
api_throttling_burst_limit = 100
api_throttling_rate_limit  = 50

enable_api_waf             = true
waf_rate_limit_per_5min    = 1000
waf_blocked_country_codes  = []

enable_pii_redaction       = true
pii_redaction_salt         = "maci-redaction-v1"
```

Lambda environment variables wired from Terraform:

```text
ENABLE_PII_REDACTION=true
PII_REDACTION_SALT=maci-redaction-v1
```

Use environment-specific values for staging and production.

---

## 5. PII and secrets redaction

The new `src/maci/redaction.py` module provides deterministic local redaction.

It redacts obvious sensitive values such as:

```text
email addresses
authorization bearer tokens
sensitive dictionary keys such as access_token/refresh_token/auth_token/password/secret/api_key/cookie/session
payment-card-like numbers that pass Luhn validation
IBAN-like identifiers
SSN-like identifiers
phone-like values
```

The redactor returns:

```text
redacted value
non-sensitive finding metadata
stable fingerprints for correlation
```

It does not store the raw detected sensitive value in findings.

### Token metrics are not credentials

v0.2.4 explicitly prevents redaction from corrupting ordinary LLM usage metrics. These fields remain numeric in audit events and transcript metadata:

```text
input_tokens
output_tokens
total_token_count
token_count
```

Credential-like token keys are still redacted contextually:

```text
access_token
refresh_token
auth_token
bearer_token
api_token
```

This matters because audit records must preserve usage evidence while still removing actual credentials.

Example:

```text
alice@example.com
```

becomes something like:

```text
[REDACTED:EMAIL:7d1ebf5e4c153cb6]
```

The fingerprint allows correlation without storing the raw value.

---

## 6. Where redaction is enforced

Redaction is now enforced before persistence in two places.

### ConversationStore

Before any conversation message is written to DynamoDB or S3 transcript archive, `ConversationStore.append_message()` redacts the message content.

This applies to:

```text
user messages
assistant messages
tool result summaries
approval status messages
system status messages
```

If redaction occurs, the message receives:

```text
redaction_status = redacted
pii_findings     = non-sensitive labels
```

The conversation record is also marked:

```text
contains_pii = true
```

### AuditLogger

Before an audit event is hash-chained and persisted, `AuditLogger.emit()` redacts:

```text
event.message
event.attributes
```

This is important because audit events can become long-retention or Object-Lock-protected records.

The audit hash is computed over the redacted event.

---

## 7. What this does not solve

This is a local deterministic redaction layer, not a complete data governance program.

It does not prove:

```text
all PII in all languages is detected
all payment data is out of scope
PCI scope is avoided automatically
GDPR/CCPA workflows are complete
all backend logs are redacted
all third-party tool responses are safe
```

For regulated deployments, combine this with:

```text
Bedrock Guardrails sensitive information filters
Comprehend or another approved PII detector where appropriate
backend tokenization
PCI scope decision
explicit retention policy
export/delete workflows
security review
legal/compliance review
```

---

## 8. PCI/card-data stance

The recommended stance for this reference architecture is:

```text
Do not process, store, or log raw cardholder data.
Use tokenized payment references only.
```

The local redactor masks card-like values that pass Luhn validation, but this should be treated as a fail-safe control, not as permission to send raw payment card data through the agent system.

---

## 9. Tests added in v0.2.0

The v0.2.0 hardening tests verify that:

```text
emails, bearer tokens, phone-like values, and card-like values are redacted
conversation messages are redacted before transcript persistence
audit events are redacted before hash-chain persistence
Terraform contains API Gateway throttling
Terraform contains AWS WAF WebACL, rate-based rule, and managed rule groups
```

Current local validation:

```text
python -m compileall -q src tests
pytest -q
61 passed
```

---

## 10. Operational guidance

For first AWS dev deploy:

```text
keep WAF enabled
start with conservative rate limits
watch CloudWatch WAF metrics
watch API 4xx/5xx rates
verify redaction before sharing transcript/audit logs
confirm audit archive does not contain raw PII
```

For production promotion:

```text
review WAF sampled requests
review false positives
set environment-specific rate limits
test request floods in staging
test redaction with realistic support/billing text
confirm card data is tokenized before entering the system
```
