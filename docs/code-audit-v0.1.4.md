# Code audit v0.1.4

This release closes the remaining locally-fixable findings from the v0.1.2 verification report after the v0.1.3 concurrency fixes.

## Fixed

1. **Billing-check deny audit coverage**
   - `billing_check` now emits `policy_denied` audit events for both tool-level denials and resource-authorization denials.
   - It also emits `ToolDenied` / `ToolResourceDenied` metrics consistently with the other tool handlers.

2. **MCP provenance verification depth**
   - `mcp_registry.compute_mcp_manifest_fingerprint()` computes a deterministic `sha256:` fingerprint from a canonical MCP server manifest.
   - `MCPToolGateway.authorize_operation()` can now accept `server_manifest` and let the policy boundary compute and verify the fingerprint.
   - If both `server_fingerprint` and `server_manifest` are supplied, they must match each other and the registry record.

## Local validation

```text
44 passed
python compileall OK
quickstart bash syntax OK
Markdown relative links OK
```

## Still not locally provable

The following still require a real AWS account or real external systems:

- Terraform `fmt`, `validate`, `plan`, and `apply`.
- Cognito JWT issuer/audience runtime validation.
- API Gateway/Lambda/DynamoDB/Step Functions route wiring.
- S3 Object Lock retention behavior.
- Bedrock Runtime, Bedrock Agent and Bedrock Guardrails integration tests.
- Real CRM, ticketing, billing and MCP transport integrations.
