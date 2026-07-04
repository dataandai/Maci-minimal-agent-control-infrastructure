# Operational runbook

## First checks

1. Check API Gateway 4XX/5XX metrics.
2. Check Lambda errors for `RequestRouterFunction`.
3. Check CloudWatch dashboard `<env>-maci`.
4. Query audit events by `tenant_id` and `request_id`.
5. Query circuit breaker table for open categories.
6. Check tenant policy for allowed model/tool/KB and current spend.

## Common incidents

### 401 missing_trusted_identity

Likely causes:

- Missing `Authorization: Bearer <id token>` header.
- API called with an access token that does not include the required custom claim.
- Wrong Cognito app client / issuer.

Action:

- Decode the JWT and verify `custom:tenant_id` and `sub`.
- Confirm API Gateway JWT authorizer issuer/audience.

### 403 identity_mismatch

Likely causes:

- Body contains `tenant_id` or `user_id` different from JWT claims.
- Client copied a sample request from another tenant.

Action:

- Remove identity fields from request body or make them match the token claims.
- Treat repeated events as a possible impersonation attempt.

### 403 policy_denied

Likely causes:

- Tenant requested a model not in `allowed_models`.
- Tenant requested a KB not in `allowed_knowledge_base_ids`.
- Tenant requested a tool not in `allowed_tools`.
- Budget would be exceeded.

Action:

- Review the audit event attributes for denial reason.
- Update tenant policy only through approved onboarding/change control.

### Tool denied

Likely causes:

- Bedrock Agent invoked an action group that the tenant policy does not allow.
- Session attributes contain an unknown tenant.

Action:

- Check Bedrock Agent trace and Lambda tool logs.
- Confirm the application sent `tenant_id`, `user_id`, and `request_id` in `sessionAttributes`.

### Duplicate ticket concern

The ticket creation tool is idempotent per tenant/request/payload. If a user reports duplicates:

- Query `TicketTable` by `tenant_id` and `ticket_key`.
- Verify backend ticket integration also honors idempotency.
- Check whether the external system created duplicates outside this control plane.

### Budget/cost issue

Action:

- Query `UsageTable` by tenant.
- Compare estimated usage with Bedrock/CUR billing data.
- If budget is exceeded, the policy engine should deny new requests and the circuit breaker may open.

## DynamoDB lookup examples

```bash
aws dynamodb query \
  --table-name <AuditTableName> \
  --key-condition-expression 'tenant_id = :t' \
  --expression-attribute-values '{":t":{"S":"tenant-acme"}}'
```

```bash
aws dynamodb get-item \
  --table-name <CircuitBreakerTableName> \
  --key '{"tenant_id":{"S":"tenant-acme"},"category":{"S":"tenant_budget_exceeded"}}'
```

## Rollback

1. Disable real Bedrock calls by redeploying with `EnableRealBedrock=false`.
2. Disable Bedrock Agent path by redeploying with `EnableBedrockAgent=false`.
3. If a tool is risky, remove it from tenant policy immediately.
4. If the API is unsafe, set reserved concurrency for the router Lambda to 0.
5. Preserve audit logs before deleting any stack resources.
