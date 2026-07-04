# AWS deployment guide

## Recommended path: Terraform

For the full Maci security-hardened system, use the Terraform deployment under `infra/terraform` or the Linux quickstart:

```bash
./quickstart/linux/dev_first_deploy.sh
```

The Terraform stack includes the Maci resources: agent registry, approval queue, S3 audit archive, billing/account-credit tools, CloudWatch observability, multi-environment tfvars and all core control-plane tables.

Detailed guides:

- `docs/aws-first-deploy-lab.md`
- `docs/terraform-deployment.md`
- `infra/terraform/README.md`

## Legacy/lightweight SAM starter

`infra/template.yaml` is kept for compatibility and fast experiments. It creates a smaller dev stack:

- Cognito User Pool and app client for dev JWT auth;
- API Gateway HTTP API with JWT authorizer;
- request router Lambda;
- customer lookup and ticket creation tool Lambdas;
- DynamoDB policy, audit, usage, circuit-breaker and ticket-idempotency tables;
- Step Functions Express workflow;
- CloudWatch dashboard;
- optional Bedrock Agent and alias with two action groups.

It does **not** include the complete Maci Terraform hardening layer:

- no agent registry table;
- no approval table/API;
- no billing check/account credit tools;
- no S3 Object Lock audit archive;
- no Terraform multi-environment controls.

Use SAM only when you explicitly want the lightweight starter.

## SAM deploy command

```bash
sam build --template-file infra/template.yaml
sam deploy --guided   --stack-name maci-dev   --capabilities CAPABILITY_IAM   --parameter-overrides     EnvironmentName=dev     EnableRealBedrock=false     CreateBedrockAgent=false     EnableBedrockAgent=false
```

## SAM demo data

Get `PolicyTableName` from stack outputs, then seed policies:

```bash
python scripts/seed_demo_policies.py --table <PolicyTableName> --region <region>
```

The SAM starter does not output an agent registry table because it does not create one. For the full Maci demo seed, use Terraform and pass both `--table` and `--agent-registry-table`.

## Create a Cognito demo user

```bash
python scripts/create_cognito_demo_user.py   --user-pool-id <CognitoUserPoolId>   --username adam@example.com   --email adam@example.com   --tenant-id tenant-acme   --password '<DemoPassword123>'   --region <region>
```

Fetch an ID token:

```bash
python scripts/get_cognito_token.py   --client-id <CognitoUserPoolClientId>   --username adam@example.com   --password '<DemoPassword123>'   --region <region>
```

The ID token must include a trusted tenant claim such as:

```json
{
  "custom:tenant_id": "tenant-acme",
  "sub": "user-123"
}
```

## Smoke-test the governed API

```bash
python scripts/smoke_test_api.py   --url <AgentInvokeUrl>   --id-token '<IdToken>'   --tenant-id tenant-acme
```

The smoke-test script omits tenant identity from the request body by default. Trusted identity comes from the JWT. Optional echo fields are supported only for mismatch detection.

## Turn on real Bedrock Runtime calls

After Bedrock model access and IAM are confirmed:

```bash
sam deploy   --stack-name maci-dev   --capabilities CAPABILITY_IAM   --parameter-overrides     EnvironmentName=dev     EnableRealBedrock=true     CreateBedrockAgent=false     EnableBedrockAgent=false
```

## Production cutover checklist

Do not use this with real customer data until all of these are true:

- full Terraform Maci stack is selected or the SAM template is intentionally extended to parity;
- API auth is backed by the real enterprise IdP or a hardened Cognito configuration;
- demo policies are replaced with real tenant onboarding/admin workflows;
- Bedrock model ARNs and Knowledge Base ARNs are scoped to approved resources;
- Knowledge Bases are tenant-isolated by one-KB-per-tenant or mandatory metadata filters;
- tool Lambdas call real backends using tenant-scoped credentials/secrets;
- CloudWatch alarms are configured for errors, throttling, guardrail interventions and budget thresholds;
- audit retention and S3 Object Lock/ SIEM export are approved;
- usage ledger is reconciled with AWS billing/CUR;
- prompt-injection, cross-tenant, load and failover tests pass in staging.
