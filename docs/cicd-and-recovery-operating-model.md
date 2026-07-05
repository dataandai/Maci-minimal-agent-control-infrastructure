# CI/CD and Recovery Operating Model

This document describes how Maci should be built, tested, deployed, rolled back, and recovered.

The CI/CD pipeline must protect the system's security invariants, not only verify that Python imports work.

---

## CI/CD goal

Every deploy should preserve these invariants:

```text
Tenant identity never comes from prompt/body/tool arguments.
Cross-tenant resource access is denied.
Tool calls are policy-gated.
High-risk account_credit never executes without valid approval.
Approval replay is blocked by payload binding.
Write operations are idempotent.
Denied actions are audited.
Conversation transcript and audit trail remain separate.
Workflow state is durable.
Recovery daemon does not execute high-risk actions directly.
Circuit breaker state survives Lambda restart.
Kill switches fail closed.
```

---

## Pull request checks

Run on every PR:

```text
Python formatting/linting
Python compile check
Unit tests
Security regression tests
Terraform fmt
Terraform validate
Infrastructure sanity checks
Secret scanning
Dependency scanning
```

Recommended local equivalent:

```bash
python -m compileall -q src tests
pytest -q
terraform -chdir=infra/terraform fmt -recursive -check
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```

---

## Security regression tests

Every PR should prove:

```text
model cannot inject tenant_id
body tenant_id mismatch is rejected
customer from another tenant is rejected
account_credit without approval creates pending approval only
approval replay with changed amount is rejected
tool deny path writes audit event
billing_check deny path writes audit event
circuit breaker opens after repeated failures
kill switch blocks selected tool/agent/tenant
conversation transcript does not store hidden chain-of-thought
recovery daemon uses leases
recovery daemon escalates approval-adjacent states
recovery daemon does not double-claim stale workflow
```

---

## Terraform pipeline

Terraform should be handled in stages:

```text
fmt
validate
plan
review
apply
post-deploy smoke tests
```

`terraform validate` is not enough. It checks configuration shape, not whether AWS will accept the plan in your account.

Always review `terraform plan`.

Red flags:

```text
DynamoDB table replacement
S3 audit/conversation bucket replacement
Object Lock disabled unexpectedly
KMS encryption removed
IAM wildcard added
API authorizer weakened
recovery schedule removed
workflow state table removed
```

---

## Environment promotion

Suggested environments:

```text
dev      automatic after PR merge or manual for labs
staging  automated deploy + integration tests
prod     manual approval + restricted deploy role
```

Production promotion should require:

```text
all CI checks passed
Terraform plan reviewed
security regression tests passed
recovery tests passed
smoke tests passed in staging
rollback path known
operator on-call/runbook available
```

---

## Post-deploy smoke tests

After deploy, verify:

```text
API endpoint reachable
JWT authorizer works
trusted tenant context created
conversation is created/resumed
workflow state is written
customer_lookup works for owned customer
cross-tenant customer denied
billing_check writes audit/usage
account_credit creates pending approval
credit cannot execute before approval
approval replay is blocked
recovery daemon Lambda exists
EventBridge schedule exists
workflow state GSI exists
logs and metrics visible
```

---

## Rollback principles

Do not rely only on `terraform destroy`.

Safe rollback options:

```text
revert Lambda code version
use Lambda alias rollback if configured
disable specific agent through agent registry
enable tenant/tool/global kill switch
pause recovery EventBridge rule if daemon misbehaves
revert Terraform change
restore DynamoDB data if PITR enabled
preserve audit logs
```

High-risk incident rollback should first stop unsafe execution, then restore normal service.

---

## Restart/reconstruction principle

The runtime may restart.

State must survive.

The system reconstructs from:

```text
conversation metadata
conversation messages
workflow state
approval records
idempotency records
audit events
usage ledger
circuit breaker state
external backend state where necessary
```

It should never reconstruct critical state from model memory or hidden reasoning text.

---

## Recovery after partial failure

Example failure:

```text
customer_lookup done
billing_check done
ticket_created
Lambda crashes before final response
```

Recovery should find:

```text
workflow_state = ticket_created
idempotency_key exists
conversation_id exists
ticket_id stored in metadata or tool result
```

Expected decision:

```text
idempotent_resume_requested
```

It must not create a duplicate ticket.

---

## High-risk recovery rule

If state is ambiguous around a high-risk operation, fail closed.

Examples:

```text
approval approved but credit execution unknown
credit requested but approval status missing
payload hash mismatch
external billing backend timeout after write attempt
```

Expected behavior:

```text
escalate to human review
check idempotency record
check external backend state
never blindly retry high-risk write
```

---

## CI tests for recovery

Add tests for:

```text
crash after ticket creation
retry does not duplicate ticket
crash after approval created
restart shows pending approval
crash after approval approved but before credit execution
system does not execute credit twice
audit chain continues after restart
circuit breaker state survives restart
conversation transcript can be reconstructed
recovery lease prevents double-processing
max attempts escalate to human
```

---

## Minimal production operating model

A production-like deployment should have:

```text
CI security regression tests
Terraform plan review
manual production approval
post-deploy smoke tests
CloudWatch alarms
recovery daemon schedule
runbook for recovery incidents
kill-switch process
approval review process
backup/PITR decisions
audit retention decisions
conversation retention decisions
```
