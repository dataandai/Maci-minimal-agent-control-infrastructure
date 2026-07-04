# Terraform deployment guide

The repository now contains a Terraform multi-environment deployment under `infra/terraform`.
Use this path when you want a long-lived AWS product environment rather than a quick SAM demo.

## Stack layout

```text
infra/terraform/
  main.tf
  variables.tf
  outputs.tf
  environments/
    dev/terraform.tfvars
    staging/terraform.tfvars
    prod/terraform.tfvars
  modules/
    api/
    auth/
    audit_archive/
    dynamodb/
    lambda_function/
    observability/
    stepfunctions/
  state-backend/
```

## Recommended deployment order

1. Deploy `state-backend` once if you want remote state.
2. Deploy `dev` with `enable_real_bedrock=false`.
3. Seed demo tenant policies.
4. Create a Cognito demo user and run the API smoke test.
5. Enable real Bedrock only after model access is confirmed in the selected region.
6. Add concrete Knowledge Base ARNs and alarm actions before staging/prod.

## Why Terraform does not create the Bedrock Agent by default

The control-plane API, tools, policies, approval workflow, audit archive and observability are Terraform-managed. Bedrock Agent creation remains an integration step by default because regional/provider support can vary and many teams create agents manually or through a separate platform pipeline. The router can invoke an existing agent alias when these variables are set:

```hcl
enable_bedrock_agent = true
bedrock_agent_id = "..."
bedrock_agent_alias_id = "..."
allowed_bedrock_agent_alias_arns = ["arn:aws:bedrock:..."]
```

The tool Lambdas expose outputs that can be attached to Bedrock Agent action groups.

## Dev command sequence

```bash
cd infra/terraform
terraform init
terraform apply -var-file=environments/dev/terraform.tfvars

POLICY_TABLE=$(terraform output -raw policy_table_name)
python ../../scripts/seed_demo_policies.py --table "$POLICY_TABLE" --region eu-west-1
```

## Production checklist before `prod` apply

- `enable_real_bedrock=true` only after Bedrock model access is enabled.
- `allowed_knowledge_base_arns` contains concrete ARNs.
- `cors_allowed_origins` is not `*`.
- `alarm_actions` contains notification targets.
- Remote state backend is configured.
- WAF/custom domain are planned if internet-facing.
- `require_agent_id=true` for production tool execution.
- S3 Object Lock retention/legal hold policy reviewed.
- Approval reviewer roles are protected by MFA or hardware-backed IdP policy.
- Bedrock Agent alias ARNs are concrete if agent mode is enabled.


## Production hardening variables

For staging/prod, set these explicitly before applying:

```hcl
require_agent_id = true
require_resource_ownership = true
allow_dev_knowledge_base_wildcard = false
allowed_knowledge_base_arns = [
  "arn:aws:bedrock:<region>:<account>:knowledge-base/<tenant-kb-id>"
]
allowed_bedrock_agent_source_arns = [
  "arn:aws:bedrock:<region>:<account>:agent/<agent-id>"
]
```

Without `allowed_bedrock_agent_source_arns`, Terraform intentionally creates no Bedrock service-principal invoke permission for action-group Lambdas. This avoids the earlier `agent/*` wildcard pattern.
