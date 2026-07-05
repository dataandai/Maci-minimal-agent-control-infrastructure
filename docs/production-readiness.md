# Production Readiness

Maci is a deployable foundation, not a production certificate.

A real production deployment must pass environment-specific gates.

---

## Readiness levels

### Level 0 — Local validated foundation

Evidence:

```text
unit tests pass
security regression tests pass
compile checks pass
local stores work
mocked AWS gateway tests pass
```

Current v0.1.6 local status:

```text
54 passed
```

### Level 1 — AWS dev lab

Evidence:

```text
Terraform init/fmt/validate/plan/apply runs in dev account
API endpoint reachable
Cognito/JWT auth works
seed data loaded
smoke tests pass
conversation/workflow/audit/usage records written
recovery daemon deployed and invokable
```

### Level 2 — AWS staging

Evidence:

```text
real Bedrock model access configured
realistic tenant policies
staging IAM least privilege review
integration tests
recovery tests
load tests
CloudWatch alarms
manual approval flow tested
Object Lock/retention reviewed
```

### Level 3 — Production candidate

Evidence:

```text
security review
IAM review
threat model review
privacy/legal retention review
red-team prompt-injection tests
chaos/recovery tests
runbook reviewed
on-call ownership
rollback plan tested
cost/budget limits tested
```

---

## Required production gates

### Identity gate

Prove:

```text
tenant_id comes only from trusted identity/session context
body/tool tenant_id cannot override context
missing identity fails closed
```

### Authorization gate

Prove:

```text
tool allowlist enforced
agent status enforced
role/action/resource checks enforced
cross-tenant resource access denied
```

### Approval gate

Prove:

```text
high-risk account_credit does not execute without approval
approval is payload-bound
approval replay is rejected
approver role is enforced
```

### Audit gate

Prove:

```text
allow and deny paths audited
audit includes tenant/user/agent/tool/resource/policy reason
audit write failure behavior is defined
hash-chain/archive behavior tested where enabled
```

### Conversation gate

Prove:

```text
conversation_id propagates
user/assistant messages persist
safe tool summaries persist
hidden chain-of-thought is not stored
conversation access is tenant-scoped
retention/redaction policy defined
```

### Recovery gate

Prove:

```text
workflow state persists
recovery_due_index works
lease prevents double processing
idempotent resume does not duplicate writes
approval-adjacent states escalate
max attempts escalate
recovery decisions are audited
```

### Cost gate

Prove:

```text
usage ledger records model/tool usage
budget checks work
tenant-level cost visibility exists
retry/recovery costs are visible
```

### Observability gate

Prove:

```text
logs are available
metrics are available
trace IDs connect request/tool/recovery events
alarms exist for key failures
log retention is explicit
```

---

## Required tests before production

```text
cross-tenant customer lookup denial
model-injected tenant_id denial
body tenant_id mismatch denial
account_credit pending approval
approval replay changed amount denial
billing_check deny audit
tool deny audit
conversation transcript persistence
conversation transcript redaction check
workflow crash after ticket creation
workflow crash after approval created
recovery daemon lease contention
recovery max-attempt escalation
kill switch stops tool/tenant/agent
circuit breaker survives Lambda restart
Bedrock throttling/fallback test
S3 audit archive write failure behavior
```

---

## Production risks still owned by the deploying team

- Bedrock model choice and access;
- tenant onboarding process;
- policy management process;
- real backend integrations;
- IAM least privilege;
- observability backend choice;
- legal/compliance retention policy;
- data deletion/export workflows;
- incident response process;
- cost allocation reconciliation with AWS billing/CUR;
- vulnerability management;
- dependency management;
- red-team/adversarial evaluation.

---

## Do not claim

Do not claim:

```text
enterprise certified
production certified
compliance certified
fully autonomous financial agent
complete MCP security gateway
complete SaaS platform
```

Safe claim:

```text
Maci is a locally verified AWS-native control-plane foundation for governed AI agent execution.
```
