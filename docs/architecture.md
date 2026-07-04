# Architecture

## Core principle

The LLM is probabilistic. The platform boundary around it must be deterministic.

This architecture applies deterministic controls around Bedrock-based agent workflows:

- identity-derived tenant context;
- first-class agent identities;
- strict Pydantic v2 schemas;
- tenant, tool, action and resource-level policy checks;
- per-step guardrails;
- tenant-scoped retrieval;
- human approval for high-risk actions;
- audit logs with event hashes and optional immutable archive;
- usage/cost ledger;
- tenant-scoped circuit breakers;
- OTel-shaped traces and eval export.

## Primary deployment path

The full Maci system is deployed through Terraform under `infra/terraform`.

The SAM template under `infra/template.yaml` is retained as a lightweight compatibility starter. It is useful for quick experiments, but it does not include the complete Maci hardening surface such as the agent registry table, approval queue, S3 audit archive, billing/account-credit tools and full Terraform observability module.

## Request lifecycle

```text
1. API Gateway receives a request and validates JWT/OIDC identity.
2. request_router Lambda derives tenant/user context from trusted authorizer claims.
3. Request body is validated using strict Pydantic schemas.
4. Optional body tenant/user echo fields are compared against trusted claims and rejected on mismatch.
5. Tenant policy is loaded from the policy store.
6. Policy engine checks model, task type, Knowledge Base, requested tools, token limit and budget.
7. Guardrail checker evaluates user input before model/retrieval execution.
8. Router optionally performs tenant-scoped retrieval and checks retrieved context.
9. Router invokes direct Bedrock Converse, Bedrock Agent alias, or Step Functions workflow depending on task mode.
10. Bedrock Agent tool Lambdas independently re-derive trusted tenant context from sessionAttributes.
11. Every tool handler performs tool allowlist, agent identity, action and resource-level authorization.
12. High-risk tools create/require human approval before execution.
13. Outputs are validated and guardrail-checked before response.
14. Audit, metrics, usage ledger and OTel-shaped trace events are emitted.
15. Circuit breakers open on repeated safety/policy/budget failures.
```

## Control-plane components

### Request Router Lambda

Owns the synchronous public request boundary:

- validates input;
- derives tenant context only from API Gateway authorizer claims;
- rejects body tenant/user mismatches;
- attaches request/trace context;
- loads tenant policy;
- performs deny-by-default policy checks;
- performs guardrail checks at input/retrieval/output boundaries;
- calls Bedrock Gateway, Bedrock Agent Runtime, or Step Functions;
- records audit, metrics, usage ledger and trace events.

### Policy Engine

The policy engine is deterministic Python. It decides:

- whether a tenant may call a requested model;
- whether a tenant may use a Knowledge Base;
- whether a tenant may request tools;
- whether requested token count fits policy;
- whether estimated cost exceeds budget;
- whether a request must be denied before reaching the model.

### Per-operation Authorization

Tool allowlisting is not enough. `authorization.py` checks the concrete operation and can call `resource_ownership.py` for explicit resource->tenant ownership:

- tenant;
- user/agent identity;
- tool name;
- resource action;
- resource identifier;
- risk level;
- approval requirement.

This is the defense-in-depth boundary used by every tool Lambda.

### Agent Registry

`agent_registry.py` models first-class agent identity:

- `agent_id`;
- tenant binding;
- human custodian;
- active/suspended/revoked status;
- allowed tools;
- allowed actions.

Production mode should set `require_agent_id=true` so action-group Lambdas fail closed when the agent identity is missing.

### Bedrock Gateway

A mockable boundary around Bedrock calls. In real deployment this wraps:

- Bedrock Runtime / Converse;
- Bedrock Agent Runtime / InvokeAgent;
- Bedrock Knowledge Base retrieval;
- guardrail configuration;
- usage token extraction;
- trace/audit boundaries.

### Lambda Tool Handlers

Each tool has:

- strict input schema;
- strict output schema;
- trusted tenant context from Bedrock Agent `sessionAttributes`;
- no model-controlled tenant/user fields;
- tenant tool allowlist check;
- agent identity check;
- resource/action authorization;
- audit/metric emission.

Current tools:

- `customer_lookup` — read customer status;
- `ticket_creation` — create ticket with idempotency;
- `billing_check` — read-only billing check;
- `account_credit` — high-risk credit action requiring approval.

### Human Approval Workflow

High-risk actions use:

- `approval.py` for approval records and store;
- `approval_review.handler` for approve/reject decisions;
- `account_credit` for pending/approved execution flow.

The current implementation provides the code boundary and API handler. Production should enforce MFA or hardware-backed approval in the IdP for approver roles.

### Deterministic Agent Graph

`agent_graph.py` implements a lightweight deterministic graph runtime:

```text
Orchestrator -> Planner -> Retrieval / Tool Agent -> Response Composer -> Validator -> Final Response
                                      ^                   |
                                      |                   v
                                  self-correction      Circuit Breaker
```

This graph demonstrates stateful orchestration, strict output validation, self-correction attempts and safe-stop behavior. It is intentionally small and deterministic rather than a high-abstraction agent framework.

### Audit Store

The audit logger writes to DynamoDB when configured and falls back to stdout locally. Events include a hash for tamper-evident export. When `AUDIT_ARCHIVE_BUCKET` is configured, events can also be archived to S3 Object Lock-enabled storage.

### Observability

The system emits:

- CloudWatch Embedded Metric Format metrics;
- Lambda/API/Step Functions logs;
- OTel-shaped JSON spans;
- trace-to-eval case exports.

This is an intentionally lightweight OTel-compatible shape. A full OpenTelemetry SDK exporter can be added when selecting Langfuse, Phoenix, Braintrust, X-Ray/ADOT or another backend.

## Fail-closed defaults

The system denies requests when:

- tenant context is missing;
- body tenant/user echo mismatches trusted claims;
- model is not explicitly allowlisted;
- tool is not explicitly allowlisted;
- agent identity is required but missing, suspended or revoked;
- resource/action is not allowed;
- high-risk action lacks approval;
- Knowledge Base is not explicitly allowlisted;
- request exceeds max token policy;
- budget is exhausted;
- guardrail intervenes;
- schema validation fails repeatedly;
- circuit breaker is open.

## Implemented vs. environment-specific

Implemented locally and covered by tests:

- strict schemas;
- identity-derived routing;
- body-vs-claim mismatch denial;
- tenant policy checks;
- Bedrock Gateway local invoke/retrieve/agent stubs;
- tool handlers with sessionAttributes identity;
- per-operation authorization;
- agent registry;
- approval flow;
- hashed audit events and optional S3 archive sink;
- deterministic guardrail checker;
- OTel-shaped trace recorder;
- deterministic graph safe-stop;
- adversarial tests.

Requires AWS-account validation before production:

- Terraform `fmt`, `validate`, `plan`, `apply`;
- concrete Knowledge Base and Bedrock Agent ARNs;
- real Bedrock model access;
- real backend integrations;
- immutable audit retention/legal hold policy;
- approval role MFA/hardware enforcement;
- billing reconciliation with CUR/Cost Explorer;
- load, chaos and red-team tests.
