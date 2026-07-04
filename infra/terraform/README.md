# Terraform multi-environment deployment

This directory adds a Terraform deployment path alongside the existing SAM template.
The Terraform stack is intended for long-lived environments (`dev`, `staging`, `prod`) and creates the deployable AWS foundation for Maci:

- Cognito User Pool and JWT-compatible app client
- API Gateway HTTP API with JWT authorizer
- Request-router Lambda
- Bedrock action-group tool Lambdas
- Step Functions Express workflow
- DynamoDB policy/audit/usage/circuit-breaker/ticket/agent-registry/approval tables
- S3 audit archive bucket with Object Lock enabled
- CloudWatch dashboard and baseline alarms
- Lambda permissions for API Gateway and Bedrock Agent invocation

## Important status

The core control-plane stack is Terraform-managed. Bedrock Agent creation is intentionally not enabled in this Terraform stack yet because Bedrock Agent provider support and regional availability can vary. The stack supports invoking an existing Bedrock Agent alias via variables:

```hcl
enable_bedrock_agent = true
bedrock_agent_id = "AGENTID123"
bedrock_agent_alias_id = "ALIASID123"
allowed_bedrock_agent_alias_arns = [
  "arn:aws:bedrock:eu-west-1:123456789012:agent-alias/AGENTID123/ALIASID123"
]
```

The tool Lambdas are still permissioned for Bedrock Agent invocation using the account-local agent ARN pattern. Tighten this to a concrete agent ARN after the real agent is created.

## Local prerequisites

```bash
terraform -version
aws sts get-caller-identity
python3.12 --version
```

### Lambda packaging note

Terraform builds Lambda deployment packages locally. The machine running `terraform apply` must be able to run:

```bash
python3.12 -m pip install -r ../../src/requirements.txt -t <build-dir>
```

## Optional: remote state bootstrap

Create a state bucket and lock table once:

```bash
cd infra/terraform/state-backend
terraform init
terraform apply   -var='aws_region=eu-west-1'   -var='bucket_name=YOUR-GLOBALLY-UNIQUE-TF-STATE-BUCKET'   -var='lock_table_name=maci-tf-locks'
```

Copy the printed backend config into the relevant `environments/<env>/backend.hcl` file.

## Deploy dev

From `infra/terraform`:

```bash
terraform init
terraform plan  -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

With remote state:

```bash
terraform init -backend-config=environments/dev/backend.hcl
terraform apply -var-file=environments/dev/terraform.tfvars
```

## Seed demo tenant policies

After apply:

```bash
POLICY_TABLE=$(terraform output -raw policy_table_name)
python ../../scripts/seed_demo_policies.py --table "$POLICY_TABLE" --region eu-west-1
```

## Create a demo Cognito user and smoke test

```bash
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)
CLIENT_ID=$(terraform output -raw cognito_user_pool_client_id)
API_URL=$(terraform output -raw agent_invoke_url)

python ../../scripts/create_cognito_demo_user.py \
  --user-pool-id "$USER_POOL_ID" \
  --username demo@example.com \
  --password 'ChangeMe12345' \
  --tenant-id tenant-acme \
  --region eu-west-1

AUTH_JSON=$(python ../../scripts/get_cognito_token.py \
  --client-id "$CLIENT_ID" \
  --username demo@example.com \
  --password 'ChangeMe12345' \
  --region eu-west-1)

ID_TOKEN=$(python -c 'import json,sys; print(json.load(sys.stdin)["IdToken"])' <<< "$AUTH_JSON")

python ../../scripts/smoke_test_api.py \
  --url "$API_URL" \
  --id-token "$ID_TOKEN" \
  --tenant-id tenant-acme
```

## Environment strategy

- `dev`: cheap, permissive CORS, Bedrock stub mode by default.
- `staging`: stricter CORS, longer logs, still Bedrock stub until model access is validated.
- `prod`: real Bedrock intended, concrete CORS, concrete Knowledge Base ARNs, alarm actions required.

## What still needs account-level hardening

- Replace default wildcard Knowledge Base fallback with concrete tenant KB ARNs.
- Replace Bedrock Agent wildcard Lambda permission with the concrete Agent ARN once available.
- Add SNS/PagerDuty alarm actions.
- Set `require_agent_id=true` outside beginner/dev mode.
- Review Object Lock retention/legal hold policy for the audit archive.
- Add WAF, custom domain, ACM certificate and Route53 when exposing externally.
- Add CI/CD around `terraform fmt`, `terraform validate`, security scanning and controlled `apply`.
