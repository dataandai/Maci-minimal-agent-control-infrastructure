# Production readiness checklist

The repository implements the local control-plane protections needed for a serious governed Bedrock agent system. Production readiness still requires AWS-account validation, environment-specific IAM hardening, real backend integrations, and operational runbooks.

## Implemented in code

- **Resource ownership:** concrete customer/resource IDs can be checked against `RESOURCE_OWNERSHIP_TABLE_NAME`; staging/prod should set `REQUIRE_RESOURCE_OWNERSHIP=true` so prefix-only fallback cannot authorize unknown resources.
- **Approval payload binding:** high-risk approvals include a payload hash; execution rejects reused approval IDs when amount, reason or other approved fields changed.

- [x] JWT/sessionAttributes identity boundary.
- [x] Pydantic v2 strict schemas for requests and tool arguments.
- [x] Tenant policy engine with model, tool, Knowledge Base, token and budget controls.
- [x] Per-operation authorization inside each tool handler.
- [x] Agent identity registry with owner/human custodian/status/permissions.
- [x] High-risk human approval workflow.
- [x] DynamoDB-backed policy/audit/usage/circuit/approval/agent-registry stores with local fallback.
- [x] Optional S3 Object Lock audit archive sink.
- [x] Tenant-scoped circuit breaker state.
- [x] Token/model-based cost estimation and usage ledger.
- [x] Bedrock Converse/Retrieve/InvokeAgent gateway boundaries.
- [x] Per-step guardrail checker for input, retrieved context and output.
- [x] OTel-shaped trace records and trace-to-eval export.
- [x] Deterministic agent graph runtime with strict validation and safe stop.
- [x] Adversarial tests for identity, resource authorization, approval, guardrail and graph failure cases.

## Required before handling real customer data

- [ ] Run `terraform fmt`, `terraform validate`, `terraform plan`, and review the plan.
- [ ] Replace wildcard/dev ARNs with concrete production ARNs for Bedrock Agent and Knowledge Bases.
- [ ] Enable real Bedrock model access and test `enable_real_bedrock=true` in dev.
- [ ] Wire real Bedrock Agent action groups to `customer_lookup`, `ticket_creation`, `billing_check`, and `account_credit` Lambdas.
- [ ] Replace synthetic tool responses with CRM, ticketing and billing integrations using Secrets Manager and tenant-scoped credentials.
- [ ] Enforce MFA/hardware-backed approval at the identity provider for `risk-approver` role.
- [ ] Confirm S3 Object Lock retention and legal hold policy for audit archive.
- [ ] Configure SIEM export if required.
- [ ] Reconcile usage ledger with AWS CUR/Cost Explorer.
- [ ] Run load, chaos, rollback and red-team tests in staging.
- [ ] Review data retention, PII redaction and log minimization.

## Promotion gates

### Dev

Goal: prove deployability and basic auth/policy/tool flow.

- `enable_real_bedrock=false` initially.
- Demo tenant policies and agent identities seeded.
- API smoke test passes.
- Unit/adversarial test suite passes.

### Staging

Goal: prove real Bedrock and backend integrations.

- `enable_real_bedrock=true`.
- Real Knowledge Base IDs and model IDs.
- Real Bedrock Agent alias wired.
- Real backend test tenants only.
- CloudWatch alarms enabled.

### Production

Goal: controlled release with narrow blast radius.

- Concrete IAM resources only.
- `require_agent_id=true`.
- Approval role uses strong IdP policy.
- Audit archive enabled and retention reviewed.
- Runbooks and rollback tested.
- Cost alarms and kill switches tested.
