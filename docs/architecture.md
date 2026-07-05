# Architecture

Maci is a deterministic control-plane foundation around probabilistic AI agent behavior.

The platform does not try to make the LLM deterministic. Instead, it keeps model behavior inside deterministic software boundaries: identity, policy, resource ownership, schema validation, approval, audit, idempotency, and recovery.

---

## Core principle

> The LLM can reason and request actions.  
> The system decides whether those actions are allowed.

A PoC agent asks:

```text
Can the model call the tool?
```

A production-style governed agent system asks:

```text
Can this authenticated user, in this tenant, through this agent,
perform this action, on this resource, right now,
under policy, with audit, cost tracking, idempotency, and recovery controls?
```

---

## High-level architecture

```text
Client / Support Console
        |
        v
API Gateway HTTP API + Cognito/JWT authorizer + stage throttling + AWS WAF
        |
        v
Request Router Lambda
        |
        +--> Policy Engine
        +--> Guardrails
        +--> RedactionService
        +--> ConversationStore
        +--> WorkflowStateStore
        +--> UsageLedger
        +--> AuditLogger
        +--> CircuitBreaker
        |
        +--> Amazon Bedrock Runtime / Converse
        +--> Amazon Bedrock Agent Runtime / InvokeAgent
        +--> Amazon Bedrock Knowledge Base gateway
        +--> Step Functions workflow skeleton
        |
        v
Tool Lambdas
        +--> customer_lookup
        +--> billing_check
        +--> ticket_creation
        +--> account_credit

EventBridge Schedule
        |
        v
Recovery Daemon Lambda
        |
        +--> workflow state scan through recovery_due_index
        +--> conditional lease acquisition
        +--> recovery classification
        +--> retry/backoff or human escalation
        +--> audit + non-user-visible conversation status
```

---

## Primary deployment path

The full Maci system is deployed through Terraform under:

```text
infra/terraform
```

Terraform includes the hardening resources that matter for this control-plane pattern:

- Cognito/JWT/API boundary;
- API Gateway stage throttling and AWS WAF WebACL;
- request router Lambda;
- tool Lambdas;
- DynamoDB state tables;
- S3 audit/conversation archives;
- EventBridge recovery daemon schedule;
- observability resources;
- IAM roles and Lambda environment wiring.

The SAM template under `infra/template.yaml` is retained as a lightweight compatibility/dev starter. It is not the source of truth for the full production-hardening surface.

---

## Normal request lifecycle

```text
1. User logs in through Cognito/OIDC.
2. API Gateway validates the JWT.
3. Request Router derives tenant/user context from trusted claims.
4. Request body is validated with strict Pydantic schemas.
5. Optional body echo fields are compared against trusted claims and rejected on mismatch.
6. Conversation is created or resumed.
7. Workflow state is written.
8. Tenant policy is loaded.
9. Kill switch, circuit breaker and budget checks run.
10. Input guardrail runs.
11. Conversation and audit payloads are redacted before persistence.
12. LLM plans the next step.
12. Tool request is produced.
13. Tool handler re-derives trusted context from Bedrock sessionAttributes where applicable.
14. Tool handler checks agent registry, tool allowlist, role, action and resource ownership.
15. Read-only tools execute after authorization.
16. Write tools use idempotency keys.
17. High-risk tools create or require human approval.
18. Assistant response is composed.
19. Output validation and guardrail checks run.
21. Conversation, audit, usage and trace records are written.
22. Workflow state transitions to the next durable status.
```

---

## Recovery lifecycle

The Lambda runtime is stateless, but workflow state is not.

A workflow that stalls because of timeout, crash, deploy interruption, throttling, or partial failure is reconstructed from durable stores.

```text
1. EventBridge invokes Recovery Daemon Lambda on a schedule.
2. Daemon queries workflow records due for recovery through recovery_due_index.
3. Daemon tries to claim each workflow using a conditional lease.
4. If another daemon owns a valid lease, the record is skipped.
5. Claimed workflow is classified by status.
6. Safe states may request auto-resume.
7. Write-adjacent states require idempotent resume.
8. Approval-adjacent or ambiguous states escalate to human review.
9. Retry/backoff is bounded by max attempts.
10. Every recovery decision emits audit and non-user-visible conversation status.
```

The daemon does not directly execute high-risk business operations such as refund, account credit, permission escalation, or data deletion.

---

## Component responsibilities

### API Gateway and Identity Provider

Owns request entry and authentication.

Responsibilities:

- validate JWT/OIDC identity;
- pass trusted claims to the router;
- avoid trusting tenant identity from request body or prompt;
- provide the root of tenant/user context.

### Request Router Lambda

Owns the synchronous public request boundary.

Responsibilities:

- build `TenantContext` from trusted identity;
- validate request schema;
- reject identity echo mismatches;
- create/resume conversation;
- transition workflow state;
- load tenant policy;
- enforce budget, kill switch and circuit breaker pre-checks;
- run guardrails;
- invoke Bedrock/agent gateway;
- append assistant/user messages;
- write audit, usage and trace records.

### Policy Engine

Determines whether a request should be allowed before reaching a model or tool.

Checks:

- allowed models;
- allowed tools;
- allowed knowledge bases;
- max tokens;
- budget;
- task type and workflow permissions.

### Agent Registry

Models first-class agent identity.

Tracks:

- `agent_id`;
- tenant binding;
- human custodian;
- active/suspended/revoked state;
- allowed tools;
- allowed actions.

Production mode should fail closed if agent identity is required but missing.

### Tool Handlers

Tool handlers are not simple functions that blindly execute model output.

Every tool handler must:

- use trusted tenant context;
- validate strict schema;
- reject model-controlled tenant/user fields;
- check tenant tool policy;
- check agent tool policy;
- check resource ownership;
- run guardrails over tool payloads where needed;
- write audit and usage events;
- enforce idempotency for write operations;
- require approval for high-risk actions.

Current tools:

```text
customer_lookup   read-only customer data lookup
billing_check     read-only billing status check
ticket_creation   write operation with idempotency
account_credit    high-risk action requiring human approval
```

### ConversationStore

Stores user-facing conversation history separately from audit logs.

Responsibilities:

- create/resume conversations;
- append user messages;
- append assistant messages;
- append safe tool/result summaries;
- append non-user-visible system status messages;
- store searchable metadata in DynamoDB;
- optionally archive transcript messages to S3.

See [`conversation-history.md`](conversation-history.md).

### AuditLogger

Records security and business decisions.

Examples:

- identity bound;
- policy allowed/denied;
- tool requested;
- tool allowed/denied;
- resource ownership checked;
- approval created/approved/rejected;
- recovery action;
- guardrail intervention;
- circuit breaker opened.

The audit system uses event hashing and a DynamoDB chain-head pattern for concurrency-aware tamper-evident ordering in DynamoDB-backed mode.

### WorkflowStateStore

Stores durable workflow state for recovery and restart behavior.

Key fields:

```text
tenant_id
conversation_id
request_id
workflow_id
status
pending_action
approval_id
idempotency_key
recovery_due_at_epoch
recovery_owner
recovery_lease_until
recovery_attempts
last_recovery_at
```

See [`workflow-state-machine.md`](workflow-state-machine.md).

### RecoveryDaemon

Scheduled reconciliation worker.

Responsibilities:

- scan due workflows;
- claim records with a durable lease;
- classify recovery action;
- schedule retry/backoff;
- escalate ambiguous/high-risk states;
- emit audit events;
- append non-user-visible conversation recovery status.

See [`recovery-daemon-operating-model.md`](recovery-daemon-operating-model.md).

---

## State stores

| Store | Purpose | User-facing? | High-level retention |
|---|---|---:|---|
| Conversation metadata | List/resume conversations | Yes | Product policy |
| Conversation transcript archive | Conversation history | Yes / support-facing | Product/privacy policy |
| Audit table/archive | Security and business proof | No | Compliance/business policy |
| Usage ledger | Cost/budget tracking | No | Billing/reporting policy |
| Workflow state | Restart/recovery | No | Until terminal + retention |
| Idempotency store | Prevent duplicate writes | No | Operation-specific TTL |
| Approval table | High-risk action review | Partially | Business/compliance policy |
| Circuit breaker table | Failure containment | No | Short TTL/stateful |
| Resource ownership table | Tenant isolation | No | Business data lifecycle |

---

## Fail-closed defaults

The system should deny or stop when:

- tenant context is missing;
- body tenant/user echo mismatches trusted identity;
- model is not allowlisted;
- tool is not allowlisted;
- agent identity is required but missing/suspended/revoked;
- resource ownership cannot be proven;
- high-risk action lacks valid approval;
- approval payload does not match exactly;
- budget is exhausted;
- kill switch is enabled;
- circuit breaker is open;
- guardrail intervenes;
- output validation repeatedly fails;
- recovery state is ambiguous around a high-risk write.

---

## Implemented locally and covered by tests

- strict schemas;
- identity-derived routing;
- body-vs-claim mismatch denial;
- tenant policy checks;
- Bedrock gateway local invoke/retrieve/agent stubs;
- tool handlers with trusted session context;
- per-operation authorization;
- resource ownership checks;
- agent registry;
- approval flow;
- approval payload binding;
- idempotent ticket creation;
- generic operation idempotency;
- conversation store foundation;
- workflow state store;
- recovery scanner/daemon;
- lease-based recovery claims;
- bounded retry/backoff;
- recovery audit event;
- hashed audit events and optional S3 archive sink;
- guardrail checker;
- OTel-shaped trace recorder;
- deterministic graph safe-stop;
- local adversarial/security tests.

---

## Requires AWS/account validation before production

- Terraform `fmt`, `validate`, `plan`, `apply` in target account;
- concrete Bedrock model access in target region;
- concrete Knowledge Base IDs and filters;
- real Bedrock Agent aliases/action groups if using Agent Runtime;
- real CRM/ticketing/billing integrations;
- IAM least privilege review;
- CloudWatch/OTel backend selection;
- S3 Object Lock and retention policy review;
- KMS key ownership and rotation decisions;
- load tests;
- chaos/recovery tests;
- prompt-injection/adversarial red-team tests;
- compliance/privacy/legal review.


---

## API abuse protection and redaction boundary

v0.2.0 adds two production-hardening controls to the architecture:

```text
API Gateway stage throttling + AWS WAF
RedactionService before transcript/audit persistence
```

API Gateway throttling and WAF run before the request router Lambda. They reduce request-flood and known-bad-input pressure before the agent control plane has to spend model/tool budget.

The redaction boundary runs before conversation and audit records are persisted. This avoids treating `contains_pii` and `redaction_status` as placeholder fields: redaction is now an enforced write-path behavior.

Important distinction:

```text
WAF/rate limiting = outer availability and abuse protection
budget/circuit breaker = tenant/workflow runtime protection
RedactionService = persistence safety control
Guardrails = model/input/output safety control
```

These controls complement each other; none of them replaces the others.
