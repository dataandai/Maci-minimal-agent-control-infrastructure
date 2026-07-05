# Changelog

## v0.2.0 - API WAF and PII redaction hardening

- Added API Gateway HTTP API stage throttling variables for burst and steady-state request limits.
- Added AWS WAFv2 WebACL attachment for the public API stage.
- Added WAF source-IP rate-based blocking, AWS managed common rule set, AWS known bad inputs rule set, and optional country block configuration.
- Added deterministic local `RedactionService` for PII/secrets redaction before persistence.
- ConversationStore now redacts user, assistant, tool-summary, approval-status, and system-status messages before DynamoDB/S3 transcript storage.
- AuditLogger now redacts audit event messages and attributes before hash-chain computation and persistence.
- Added non-sensitive PII finding labels/fingerprints to support correlation without storing raw values.
- Added tests for redaction and Terraform WAF/throttling configuration.
- Expanded local validation from 57 to 61 tests.
- Added dedicated documentation for API WAF, rate limiting, and PII redaction.

## v0.1.7 - conversation ownership and tool recovery wiring

- Fixed same-tenant conversation resume ownership: an authenticated user can no longer append to another user's conversation by guessing or reusing `conversation_id`.
- Added `conversation_id` binding checks so a request body cannot override a trusted conversation claim when one is present.
- Propagated the effective trusted `conversation_id` into router context and Bedrock Agent `sessionAttributes` for downstream tool Lambdas.
- Wired real tool handlers into durable workflow state transitions: customer lookup, billing check, ticket creation, pending approval, approved credit, and executed credit.
- Added ticket idempotency keys and account-credit idempotency keys into workflow state where recovery needs them.
- Added safe conversation transcript summaries for tool results and approval status updates.
- Added regression tests proving conversation ownership and real tool status transitions.
- Expanded local validation from 54 to 57 tests.
- Added dedicated documentation for conversation ownership and real tool recovery wiring.

## v0.1.6-docs-refactor - documentation consistency pass

- Refactored README around the current v0.1.6 system shape: normal request path, conversation history, workflow state, recovery daemon, CI/CD and operating model.
- Added `docs/index.md` as the main documentation map.
- Reworked `docs/architecture.md` into a dual-path architecture: normal runtime and recovery runtime.
- Added dedicated docs for conversation history, workflow state machine, and recovery playbooks.
- Updated production readiness, limitations, threat model, security hardening, deployment, and runbook docs to include conversation/recovery/CICD concerns.
- Clarified that the recovery daemon is a reconciliation foundation and does not directly execute high-risk business actions.
- Clarified that conversation transcript, audit trail, operational logs, and usage ledger are separate records with different purposes and retention policies.

## v0.1.6 - recovery daemon foundation

- Added an industry-style scheduled `RecoveryDaemon` for stale workflow reconciliation.
- Added durable recovery coordination fields to `WorkflowStateRecord`: recovery partition, due time, owner lease, lease expiry, attempt counter and last recovery timestamp.
- Added lease-based workflow claiming so overlapping daemon invocations do not double-process the same stale workflow.
- Added bounded retry/backoff and max-attempt escalation to human review.
- Added strict resume policy behavior: auto-resume for safe planning/read states, idempotent resume for write-adjacent states, human review for approval-adjacent states, and fail-closed handling for unsafe states.
- Added recovery audit event type and non-user-visible conversation system status messages for recovery decisions.
- Added DynamoDB `recovery_due_index` GSI to avoid whole-table workflow scans.
- Added SAM and Terraform deployment resources for the recovery daemon Lambda and EventBridge schedule.
- Added recovery daemon operating model documentation.
- Expanded local validation from 48 to 54 tests.

## v0.1.5 - conversation and recovery foundations

- Added `ConversationStore` for user-facing conversation metadata and message history, separate from the security audit trail.
- Added `conversation_id` propagation through API requests/responses and trusted identity context.
- Request router now records user and assistant messages and marks conversation status on success or safe failure.
- Added `WorkflowStateStore`, explicit workflow states, `RecoveryScanner`, and safe/idempotent/human-review resume classification.
- Added generic `OperationIdempotencyStore` and approval-bound idempotency for `account_credit` execution.
- Added SAM resources/env vars for conversation table, transcript bucket, workflow state table, and generic idempotency table.
- Added CI workflow with tests, compile checks, and infrastructure sanity checks.
- Added wiki docs for governed support workflow, junior AWS deployment, conversation logging/audit, and CI/CD recovery operating model.
- Expanded local validation from 44 to 48 tests.

## v0.1.4 - provenance and deny-audit polish

- Added audit-on-deny coverage for `billing_check` tool security and resource-authorization failures.
- Added MCP manifest fingerprint computation so the gateway can verify a canonical server manifest instead of only comparing a caller-supplied fingerprint string.
- Added MCP manifest tamper test and billing deny-audit regression test.
- Expanded local validation from 42 to 44 tests.

## v0.1.3 - concurrency audit hardening

- Hardened audit hash chaining for DynamoDB-backed deployments: audit events now advance a per-tenant chain-head record with a conditional `TransactWriteItems` append, preventing hash-chain forks across concurrent Lambda execution environments.
- Added audit sequence numbers so event order can be verified alongside `previous_event_hash` and `event_hash`.
- Fixed DynamoDB-backed tenant circuit-breaker visibility for `is_open(tenant_id)` without a category by querying the tenant partition instead of returning a blind `False`.
- Added tests proving cross-logger DynamoDB audit chaining and any-category circuit-breaker visibility.
- Expanded local validation from 40 to 42 tests.

## v0.1.2 - local hardening completion

- Added operator kill-switch controls for global, tenant, agent and tool scope.
- Added a role-gated admin handler for agent lifecycle, resource ownership and kill-switch operations.
- Added MCP server provenance/fingerprint registry checks to the MCP gateway boundary.
- Added nested payload guardrail scanning for tool inputs before Pydantic validation.
- Added local audit hash chaining with `previous_event_hash` for tamper-evident event sequences.
- Added Terraform resources and environment variables for kill-switch and MCP registry tables, plus admin API wiring.
- Added seed support for demo MCP registry data.
- Expanded local adversarial/security tests from 33 to 40.

## v0.1.1 - code-audited hardening

- Added explicit resource ownership enforcement via `resource_ownership.py` and optional DynamoDB table.
- Added payload binding for high-risk approvals so approval IDs cannot be replayed with modified amounts or reasons.
- Hardened Terraform defaults: Bedrock Agent Lambda permissions now require explicit agent source ARNs; Knowledge Base wildcard access is dev-only.
- Updated quickstart seed flow to seed demo resource ownership records.
- Added adversarial tests for resource-ownership override and approval payload replay.

## v0.1.0 - Maci baseline

Initial public baseline for **Maci: minimal agent control infrastructure**.

This release provides a Terraform-first AWS foundation for governed agent systems:

- Cognito/JWT identity and tenant context propagation.
- API Gateway and Lambda request router.
- Strict Pydantic v2 request and tool schemas.
- Agent registry with active/suspended/revoked identities.
- Per-operation resource authorization for tool calls.
- Human approval workflow for high-risk account-credit actions.
- DynamoDB-backed policy, audit, usage, circuit-breaker, idempotency, agent-registry and approval state.
- Optional S3 Object Lock audit archive for tamper-evident audit retention.
- Deterministic agent graph runtime with validation, self-correction and safe-stop behavior.
- Guardrail checks for user input, retrieved context and model output.
- OTel-shaped trace records and trace-to-eval export.
- Linux quickstart scripts for first AWS deployment.
- Terraform multi-environment setup for dev, staging and prod.
- Unit and adversarial test coverage for identity, policy, tools, authorization, approval, guardrails and graph safety.

The version number is intentionally separate from the product name. The product is **Maci**, and this is its first baseline release: **v0.1.0**.
