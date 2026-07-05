# Threat Model

This threat model focuses on governed AI agent execution in a multi-tenant AWS environment.

---

## Assets

```text
tenant identity
customer records
billing records
tickets
account credit/refund workflows
conversation transcripts
audit logs
usage/cost records
agent/tool policies
approval records
workflow state
idempotency records
AWS credentials and IAM roles
```

---

## Trust boundaries

```text
User browser / support console
API Gateway / authorizer
Request Router Lambda
LLM / Bedrock Runtime
Bedrock Agent Runtime / sessionAttributes
Tool Lambda handlers
DynamoDB state stores
S3 audit/transcript archives
External business backends
Recovery daemon
Human approval queue
```

---

## Key threats and mitigations

| Threat | Example | Mitigation |
|---|---|---|
| Tenant spoofing | User sends `tenant_id=other-tenant` | Tenant context derived from trusted identity; body mismatch denied |
| Model tenant injection | LLM adds `tenant_id` to tool payload | Strict schemas with extra fields forbidden |
| Cross-tenant resource access | Valid customer ID belongs to another tenant | Resource ownership table check |
| Unauthorized tool use | Agent calls billing/write tool | Tenant policy + agent registry + per-operation auth |
| High-risk action without approval | Model applies credit directly | `account_credit` creates/requires approval |
| Approval replay | 500 USD approval reused for 5000 USD | Payload hash binding |
| Duplicate write after retry | Ticket created twice | Idempotency store |
| Prompt injection | User says ignore instructions | Input/retrieval/tool/output guardrails |
| Retrieved-context injection | KB doc contains malicious instruction | Retrieved context guardrail |
| Audit gap | Denied action not logged | Audit allow and deny paths |
| Audit chain fork | Concurrent Lambda writes divergent hashes | DynamoDB chain-head conditional transaction pattern |
| Runaway failures | repeated validation/tool denial | Circuit breaker + kill switch |
| Partial workflow failure | crash after ticket but before response | Workflow state + recovery daemon + idempotency |
| Recovery double-processing | overlapping daemon invocations | Conditional lease/fencing |
| Unsafe recovery | daemon retries high-risk write | human-review classification for approval-adjacent states |
| Conversation leakage | raw transcript exposed broadly | separate store, tenant-scoped access requirement, redaction/retention policy |
| Secret leakage in logs | tokens printed in CloudWatch | redaction discipline and no raw credential logging |

---

## High-risk workflows

These should never be executed directly by the LLM or recovery daemon:

```text
account credit
refund
billing adjustment
permission escalation
data deletion
credential/secret operations
```

They require explicit policy, approval, idempotency and audit.

---

## Recovery-specific threats

### Duplicate external writes

If a workflow crashes after a write but before response, retry can duplicate the write.

Mitigation:

```text
idempotency key before write
workflow state after write
external backend correlation ID
recovery classification as idempotent_resume
```

### Ambiguous high-risk state

If approval is approved but credit execution is unknown, blind retry is dangerous.

Mitigation:

```text
human_review_required
check idempotency record
check billing backend
manual operator decision
audit operator decision
```

### Concurrent recovery workers

Overlapping scheduled Lambdas may process the same workflow.

Mitigation:

```text
conditional lease acquisition
recovery_owner
recovery_lease_until
lease_busy outcome
idempotency before writes
```

---

## Conversation-specific threats

### Storing too much

Full prompts, raw backend payloads and hidden chain-of-thought can create privacy and security risk.

Mitigation:

```text
store safe transcript messages
store structured decision traces instead of hidden CoT
redact secrets/PII where possible
separate transcript from audit
```

### Unauthorized transcript access

Support users should not see other tenants' conversations.

Mitigation requirement:

```text
tenant-scoped read API
role-based conversation access
legal hold/export/delete controls
```

The storage foundation exists; the product read API must enforce this before production.

---

## Residual risks

- LLM may still make poor plans or summaries.
- Guardrails may miss novel prompt injection.
- Real backend systems may have their own authorization bugs.
- Misconfigured IAM can bypass intended boundaries.
- Incorrect Terraform variables can deploy to wrong account/region.
- Recovery integration with external backends requires additional reconciliation logic.
- Compliance requirements depend on the deploying organization and jurisdiction.
