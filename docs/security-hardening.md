# Security Hardening

This document summarizes the security-hardening controls implemented in Maci.

---

## Security principle

The model is not the security boundary.

Security decisions must be enforced by deterministic system components.

---

## Identity hardening

Implemented controls:

```text
trusted tenant context from JWT/OIDC/API Gateway claims
trusted Bedrock Agent tool context from sessionAttributes
body tenant/user echo mismatch denial
model/tool tenant_id not trusted
missing tenant context fails closed
```

Risk addressed:

```text
tenant impersonation
model-generated tenant override
body-parameter identity spoofing
```

---

## Schema hardening

Implemented controls:

```text
Pydantic v2 strict models
extra fields forbidden
strict tool input/output schemas
validation failure events
safe-stop behavior after repeated invalid outputs
```

Risk addressed:

```text
model invents unexpected fields
model injects tenant_id into tool payload
malformed tool call reaches backend
```

---

## Authorization hardening

Implemented controls:

```text
tenant policy engine
agent registry
agent active/suspended/revoked status
allowed tools per agent/tenant
per-operation authorization
resource ownership checks
high-risk approval requirement
```

Risk addressed:

```text
agent calls unauthorized tool
support role performs billing write
cross-tenant customer access
high-risk action without approval
```

---

## Guardrail hardening

Implemented boundaries:

```text
input guardrail
retrieved context guardrail
tool payload guardrail
model output guardrail
```

Risk addressed:

```text
prompt injection
tenant bypass attempts
policy bypass instructions
retrieved-document injection
unsafe final response
```

---

## Business action hardening

Implemented controls:

```text
ticket_creation idempotency
account_credit pending approval
approval payload hash binding
approval replay denial
generic operation idempotency store
```

Risk addressed:

```text
duplicate ticket creation
duplicate credit execution
approval reused for different amount/customer
financial action executed by model alone
```

---

## Runtime safety hardening

Implemented controls:

```text
circuit breaker
global/tenant/agent/tool kill switches
usage ledger and budget checks
recovery daemon with lease and bounded retry
human escalation for ambiguous/high-risk states
```

Risk addressed:

```text
runaway retries
repeated validation failures
unsafe tool behavior
partial workflow failure
crash/retry duplicate writes
```

---

## Audit and trace hardening

Implemented controls:

```text
allow and deny audit events
hash-based audit events
DynamoDB chain-head concurrency hardening
optional S3 Object Lock archive
OTel-shaped traces
usage/cost ledger
recovery audit events
```

Risk addressed:

```text
cannot prove why action was allowed/denied
lost deny events
concurrent audit chain forks
missing recovery accountability
```

---

## Conversation safety hardening

Implemented controls:

```text
ConversationStore separate from audit
user/assistant/system-status message types
non-user-visible system status for recovery
redaction_status field
no hidden chain-of-thought storage requirement
```

Still needed for production:

```text
read API authorization
redaction pipeline
retention enforcement
export/delete workflow
legal hold process
```

---

## Remaining hardening work

Before production:

```text
run IAM least-privilege review
run Terraform plan/apply in target account
configure Bedrock model/guardrail/KBS access
wire real backend credentials through approved secret manager
run load tests
run red-team prompt-injection tests
run chaos/recovery tests
review privacy/retention policy
```


## v0.2.1 Prompt-Injection Red-Team Layer

Maci now includes a deterministic red-team suite separate from control-plane authorization tests. It covers direct prompt injection, poisoned RAG documents, malicious tool outputs, jailbreak attempts, approval bypass, data exfiltration and hidden policy extraction.

The suite lives in `src/maci/redteam.py`, `tests/red_team/`, and `evals/redteam/default_cases.jsonl`. It is intended to run in CI without live model calls. External live-model tools such as promptfoo or garak can be layered on top for dev/staging red teaming.
