# Documentation Audit

This document records the current documentation consistency boundary.

---

## Current state

The documentation has been refactored around the current v0.1.6 system shape:

```text
normal request path
conversation history layer
workflow state machine
scheduled recovery daemon
CI/CD and rollback model
runbook/recovery playbooks
production readiness gates
limitations
```

The README and docs now describe the same core system:

```text
trusted identity
policy and resource ownership
guardrails
tool enforcement
human approval
audit/usage/tracing
conversation history
workflow state
idempotency
recovery daemon
CI/CD and recovery operating model
```

---

## Documentation does not prove AWS production readiness

Documentation can explain design and operating model.

It cannot prove:

```text
Terraform applies successfully in your AWS account
IAM is least-privilege in your environment
Bedrock model access is configured
real backend integrations are correct
recovery works under real failure modes
retention/compliance settings match your obligations
```

Those require deployment, testing, and review in the target environment.

---

## Supporting context vs evidence

`industry-best-practices-2026.md` is supporting context.

It should not be treated as generated compliance evidence.

Actual evidence should come from:

```text
code review
test results
Terraform plan/apply output
AWS smoke tests
security tests
recovery/chaos tests
audit samples
runbook exercises
```

---

## Known documentation boundaries

- Some docs describe target production behavior that must be wired into a real application UI/API before production.
- Conversation history storage exists as a foundation, but product read/export/delete APIs are still environment-specific.
- Recovery daemon foundation exists, but orchestrator-specific resume/redrive integration is still deployment-specific.
- SAM remains a lightweight starter; Terraform is the primary/full deployment path.

---

## Recommended review checklist

Before publishing or presenting the repo:

```text
README links resolve
docs/index.md links resolve
README status matches tests
limitations are not softened
Terraform-not-run warning remains visible
conversation != audit distinction remains clear
recovery daemon limitations remain clear
no claim of production certification
```
