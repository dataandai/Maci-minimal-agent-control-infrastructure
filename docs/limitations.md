# Limitations and deployment truth table

This repository is no longer a toy skeleton: it now includes deployable AWS infrastructure, tenant/JWT identity, per-tool and per-resource authorization, a first-class agent identity registry, high-risk approval workflow, durable audit/usage/circuit-breaker storage options, and adversarial tests.

However, **production-ready is an operational claim**, not just a code claim. The following points must still be validated in the target AWS account before real customer data is handled.

## Implemented locally and covered by tests

- Tenant identity comes from trusted JWT/Cognito or Bedrock Agent `sessionAttributes`, not model-generated parameters.
- Tool schemas use Pydantic v2 strict models and reject unknown identity/tool arguments.
- Every tool handler performs per-operation checks, not only an initial request-router check.
- Resource-level checks can deny semantically valid but cross-tenant-looking customer IDs.
- Agent identity can be active/suspended/revoked and constrained by tool/action permissions.
- High-risk account credit action requires explicit human approval before execution.
- Circuit breaker state supports DynamoDB backing with local fallback, and tenant-level any-category checks query the tenant partition in DynamoDB mode.
- Audit events are hash-chained locally and, when DynamoDB is configured, advance a per-tenant chain head with a conditional transaction before optional S3 Object Lock archive storage.
- OTel-shaped traces can be emitted and turned into eval/regression cases.
- A deterministic graph runtime demonstrates state graph orchestration, strict output validation, self-correction attempts, and safe-stop behavior.

## Still requires AWS-account validation

- `terraform fmt`, `terraform validate`, and `terraform plan` must pass in your environment. This sandbox does not include Terraform.
- Bedrock model access must be enabled in the chosen region before `enable_real_bedrock=true`.
- Bedrock Agent action groups and aliases must be wired to real agent IDs if `enable_bedrock_agent=true`.
- S3 Object Lock retention must be accepted as a compliance and lifecycle choice before using immutable audit archive in production.
- IAM policies must be reviewed and tightened to concrete production ARNs, especially Knowledge Base ARNs and Bedrock Agent source ARNs.
- The demo CRM/billing/ticketing tool implementations must be replaced with real backend integrations and tenant-scoped credentials.
- Cost estimates are still a control-plane estimator; reconcile them against CUR/Cost Explorer before chargeback.
- Hardware-backed approval/MFA must be enforced at the IdP layer for truly high-risk financial or destructive actions.

## Not included yet

- Full admin UI for tenant onboarding and policy editing.
- Real MCP transport server; `mcp_gateway.py` implements the policy boundary that such a server should call.
- Real SIEM integration.
- Production load tests and chaos/failover test suite.
- Full OpenTelemetry SDK exporter dependency; the code emits OTel-shaped JSON spans to avoid vendor lock-in and keep the lab lightweight.


## Code-audit follow-up

- Terraform still must be validated in a real toolchain (`terraform fmt`, `terraform validate`, `terraform plan`). The repository includes CI config for this, but this sandbox did not have Terraform installed.
- The MCP gateway module remains a policy-boundary adapter, not a complete MCP transport server with provenance/SCA/signing. Do not describe it as full ASI04 supply-chain mitigation by itself.
- Resource ownership is now implementable via a DynamoDB table. Production must set `REQUIRE_RESOURCE_OWNERSHIP=true`; prefix fallback exists only for the beginner dev lab.
- Human approval now binds approvals to the exact payload hash, but real production still needs IdP/MFA hardening for approver roles.
