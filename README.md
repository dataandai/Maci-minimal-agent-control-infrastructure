# Maci: minimal agent control infrastructure

**Maci** is an AWS-native control-plane foundation for governed AI agent execution.

It is designed for teams that want to move beyond a proof-of-concept agent and operate AI workflows near real tenant data, support systems, billing workflows, and high-risk business actions.

The core idea:

> The LLM can reason and request actions.  
> The system decides whether those actions are allowed.

Maci focuses on the deterministic infrastructure around probabilistic model behavior:

- trusted tenant identity;
- per-operation authorization;
- tenant/resource ownership checks;
- strict tool schemas;
- guardrails;
- API Gateway throttling and AWS WAF abuse protection;
- deterministic PII/secrets redaction before transcript/audit persistence;
- human approval for high-risk actions;
- audit and usage ledgers;
- user-facing conversation history;
- workflow state;
- idempotency;
- scheduled recovery daemon;
- circuit breakers and kill switches;
- Terraform-first AWS deployment.

Recent v0.2.0 hardening adds API Gateway/WAF request-abuse protection and deterministic PII/secrets redaction before conversation transcripts and audit events are persisted.

Maci is intentionally **not** a custom GPU pool, vLLM, AIBrix, Kubernetes inference stack, or another agent framework. It assumes the model layer is managed by **Amazon Bedrock** and focuses on the control plane around Bedrock-based agent workflows.

---

## Current status

Current code release: **v0.2.0 — API WAF + PII Redaction Hardening**  
Current documentation state: **v0.2.0 code/docs alignment**

Local validation from the v0.2.0 build:

```text
python -m compileall -q src tests
pytest -q
61 passed
```

Important honesty boundary:

> This is a locally verified, AWS-deployable foundation. It is not a claim that your target AWS production environment has already been validated, certified, load-tested, red-teamed, or compliance-approved.

Terraform must still be run in the target AWS account:

```bash
terraform -chdir=infra/terraform fmt -recursive
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -var-file=environments/dev/terraform.tfvars
```

---

## Example use case

A B2B SaaS or fintech company wants to add an AI support agent.

A support user asks:

```text
Check billing for customer cust-123. If there was an overcharge, create a ticket and request account credit.
```

In a PoC, the agent might simply call tools.

In a product system, every step crosses trust boundaries:

- Who is the authenticated user?
- Which tenant are they acting for?
- Does this customer belong to that tenant?
- Is the requested tool allowed for this agent?
- Is the action read-only or high-risk?
- Does account credit require human approval?
- Was every allow/deny decision audited?
- If the workflow crashes halfway through, can the system reconstruct what already happened?

Maci models this production-style boundary.

Read the full narrative flow: [`docs/governed-ai-support-agent-workflow.md`](docs/governed-ai-support-agent-workflow.md)

---

## Architecture at a glance

```text
Client / Support Console
        |
        v
API Gateway + Cognito/JWT authorizer
        |   - stage throttling
        |   - AWS WAF rate-based and managed-rule protection
        v
Request Router Lambda
        |   - derive tenant context from trusted identity
        |   - policy, budget, kill switch, circuit breaker checks
        |   - input/retrieval/output guardrails
        |   - PII/secrets redaction before transcript/audit persistence
        |   - conversation + workflow state updates
        |
        +--> Amazon Bedrock Runtime / Converse
        +--> Amazon Bedrock Agent Runtime / InvokeAgent
        +--> Tenant-filtered Knowledge Base gateway
        +--> Tool Lambdas
        |       - customer_lookup
        |       - billing_check
        |       - ticket_creation
        |       - account_credit approval flow
        |
        v
DynamoDB
  - policies
  - audit metadata
  - usage ledger
  - conversations
  - workflow state
  - approvals
  - idempotency
  - circuit breakers
  - agent registry
  - resource ownership
  - kill switches

S3
  - audit archive
  - conversation transcript archive

EventBridge + Recovery Daemon Lambda
  - scans stale workflows
  - claims workflows with a lease
  - classifies resume policy
  - requests idempotent resume or human escalation

CloudWatch / OTel-shaped traces
  - logs
  - metrics
  - spans
  - alarms
```

Detailed architecture: [`docs/architecture.md`](docs/architecture.md)

Read the API/WAF/redaction hardening guide: [`docs/api-waf-rate-limiting-and-pii-redaction.md`](docs/api-waf-rate-limiting-and-pii-redaction.md)

---

## Runtime paths

Maci has two main runtime paths.

### 1. Normal request path

```text
login
identity bound
request received
conversation created or resumed
policy pre-check
input guardrail
LLM planning
tool request
tool authorization
resource ownership check
tool execution or approval creation
assistant response
output validation
audit + usage + trace
workflow state update
```

### 2. Recovery path

```text
EventBridge schedule
Recovery Daemon Lambda
query recovery_due_index
conditional lease claim
workflow reconstruction
resume policy classification
bounded retry/backoff
safe resume / idempotent resume / human escalation
audit recovery decision
non-user-visible conversation status message
```

Recovery daemon details: [`docs/recovery-daemon-operating-model.md`](docs/recovery-daemon-operating-model.md)  
Recovery playbooks: [`docs/recovery-playbooks.md`](docs/recovery-playbooks.md)

---

## Implemented control-plane foundations

### Identity and authorization

- Trusted tenant identity from API Gateway JWT claims or Bedrock Agent `sessionAttributes`.
- Body/tool `tenant_id` is not trusted.
- Strict request and tool schemas using Pydantic `extra="forbid"`.
- Per-tenant policy engine.
- Agent registry with active/suspended/revoked states.
- Per-operation authorization.
- Resource ownership checks.

### Guardrails and safety

- Input guardrail.
- Retrieved-context guardrail.
- Tool payload guardrail.
- Output guardrail.
- Circuit breaker.
- Operator kill switches at global, tenant, agent, and tool scope.

### Business action control

- Read-only `customer_lookup`.
- Read-only `billing_check`.
- Write `ticket_creation` with idempotency.
- High-risk `account_credit` requiring human approval.
- Approval payload binding to prevent approval replay.

### Conversation and audit

- User-facing `ConversationStore`.
- `conversation_id` / `message_id` support.
- DynamoDB conversation metadata/message index.
- Optional S3 transcript archive.
- Separate security audit trail.
- Hashed audit events with DynamoDB chain-head hardening and optional S3 Object Lock archive.
- Usage/cost ledger.
- OTel-shaped trace recorder.

### Recovery and operations

- Durable workflow state.
- Explicit workflow statuses.
- Recovery due index.
- Lease-based workflow claiming.
- Bounded retry and backoff.
- Human escalation for high-risk or ambiguous states.
- Generic idempotency store.
- Scheduled EventBridge recovery daemon.

---

## What this is not

Maci is not:

- a full SaaS product;
- a complete enterprise compliance platform;
- a replacement for Bedrock Agents, LangGraph, CrewAI, MCP gateways, or observability vendors;
- a finished production deployment for your AWS account;
- a guarantee that the LLM will always reason correctly;
- a substitute for IAM review, legal review, security review, load testing, or red-team testing.

Maci is a foundation for the control-plane layer that many PoC agent demos skip.

Limitations: [`docs/limitations.md`](docs/limitations.md)

---

## Quickstart: local validation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,aws]'
python -m compileall -q src tests
python -m pytest
```

Tests do not require AWS credentials. AWS calls are behind mockable gateway/store abstractions.

---

## Quickstart: AWS dev lab

For a beginner-friendly Linux flow:

```bash
./quickstart/linux/dev_first_deploy.sh
```

Step-by-step:

```bash
./quickstart/linux/00_check_prereqs.sh
./quickstart/linux/01_prepare_local_python.sh
./quickstart/linux/02_terraform_plan_dev.sh
./quickstart/linux/03_terraform_apply_dev.sh
./quickstart/linux/04_seed_demo_data_and_user.sh
./quickstart/linux/05_get_token.sh
./quickstart/linux/06_smoke_test_api.sh
```

Full lab guide: [`docs/aws-first-deploy-lab.md`](docs/aws-first-deploy-lab.md)  
Junior deployment guide: [`docs/aws-deployment-guide-for-junior-engineers.md`](docs/aws-deployment-guide-for-junior-engineers.md)

Destroy the dev stack when finished:

```bash
./quickstart/linux/99_destroy_dev.sh
```

---

## Terraform deployment

Primary deployment path:

```bash
cd infra/terraform
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

The SAM template in `infra/template.yaml` remains as a lightweight/dev compatibility starter. Terraform is the source of truth for the full Maci hardening surface.

Terraform guide: [`docs/terraform-deployment.md`](docs/terraform-deployment.md)

---

## Documentation map

Start with:

- [`docs/index.md`](docs/index.md) — documentation index;
- [`docs/business-painpoint.md`](docs/business-painpoint.md) — business framing;
- [`docs/governed-ai-support-agent-workflow.md`](docs/governed-ai-support-agent-workflow.md) — narrative use case;
- [`docs/architecture.md`](docs/architecture.md) — technical architecture;
- [`docs/conversation-history.md`](docs/conversation-history.md) — user-facing conversation history;
- [`docs/agent-conversation-logging-and-audit-guide.md`](docs/agent-conversation-logging-and-audit-guide.md) — transcript vs audit vs logs;
- [`docs/workflow-state-machine.md`](docs/workflow-state-machine.md) — workflow states and recovery classification;
- [`docs/recovery-daemon-operating-model.md`](docs/recovery-daemon-operating-model.md) — recovery daemon details;
- [`docs/cicd-and-recovery-operating-model.md`](docs/cicd-and-recovery-operating-model.md) — CI/CD and recovery principles;
- [`docs/runbook.md`](docs/runbook.md) — operational runbook;
- [`docs/production-readiness.md`](docs/production-readiness.md) — promotion gates;
- [`docs/limitations.md`](docs/limitations.md) — honest boundaries.

Latest local code audit: [`docs/code-audit-v0.2.0.md`](docs/code-audit-v0.2.0.md)

---

## Core invariant

The LLM is allowed to propose.

The system must enforce.

That is the difference between a PoC agent and a production-style governed agent system.


## v0.2.0 production hardening documentation

- [`docs/api-waf-rate-limiting-and-pii-redaction.md`](docs/api-waf-rate-limiting-and-pii-redaction.md)
- [`docs/code-audit-v0.2.0.md`](docs/code-audit-v0.2.0.md)

## v0.1.7 review-fix documentation

- [`docs/conversation-ownership-and-tool-recovery-wiring.md`](docs/conversation-ownership-and-tool-recovery-wiring.md)
- [`docs/code-audit-v0.1.7.md`](docs/code-audit-v0.1.7.md)
