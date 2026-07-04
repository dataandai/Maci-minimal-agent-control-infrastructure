# AWS First Deploy Lab

This lab is designed for people who want to deploy the project into their own AWS account from a Linux terminal. It is intentionally beginner-friendly: start in safe dev mode, deploy with Terraform, seed a demo tenant, create a Cognito user, get a JWT, and run the first API smoke test.

The first deploy uses:

- `enable_real_bedrock=false`
- `enable_bedrock_agent=false`

That means the control plane deploys without requiring Bedrock model access on day one. You validate the AWS foundation first: Cognito, API Gateway, Lambda, DynamoDB, Step Functions, CloudWatch, tenant identity, policy enforcement, audit, usage and circuit-breaker tables.

## What you need before starting

On Linux, you need:

- AWS CLI configured with an AWS account
- Terraform 1.6+
- Python 3.12
- `curl` and `unzip`

You also need AWS permissions to create IAM roles, Lambda functions, API Gateway, Cognito, DynamoDB, Step Functions and CloudWatch resources.

## One-command guided deploy

From the repository root:

```bash
./quickstart/linux/dev_first_deploy.sh
```

This runs the full dev flow:

```text
00_check_prereqs.sh
01_prepare_local_python.sh
02_terraform_plan_dev.sh
03_terraform_apply_dev.sh
04_seed_demo_data_and_user.sh
05_get_token.sh
06_smoke_test_api.sh
```

The script asks for confirmation before deploying because AWS resources may create costs.

For non-interactive CI/lab use:

```bash
AUTO_APPROVE=true ./quickstart/linux/dev_first_deploy.sh
```

## Step-by-step deploy

Use this mode if you are learning AWS/Terraform and want to inspect each step.

```bash
./quickstart/linux/00_check_prereqs.sh
```

Checks the Linux machine, AWS credentials, Terraform, Python 3.12 and repo paths.

```bash
./quickstart/linux/01_prepare_local_python.sh
```

Creates `.venv`, installs Python dependencies and runs tests.

```bash
./quickstart/linux/02_terraform_plan_dev.sh
```

Runs `terraform init`, `terraform fmt`, `terraform validate`, and creates a saved dev plan.

```bash
./quickstart/linux/03_terraform_apply_dev.sh
```

Applies the saved plan and stores Terraform outputs under `.quickstart/terraform-outputs-dev.json`.

```bash
./quickstart/linux/04_seed_demo_data_and_user.sh
```

Seeds demo tenant policies and creates/updates a Cognito demo user.

```bash
./quickstart/linux/05_get_token.sh
```

Gets a Cognito ID token and stores it under `.quickstart/id-token.txt`.

```bash
./quickstart/linux/06_smoke_test_api.sh
```

Calls the deployed API Gateway endpoint with the JWT token.

## Demo tenant and user

The default quickstart values are:

```text
Tenant:   tenant-acme
Username: demo@example.com
Email:    demo@example.com
Region:   eu-west-1
```

The generated demo password is saved locally in:

```text
.quickstart/dev-user.env
```

This file is chmod `600` and is ignored by Git. Do not commit it.

To override defaults:

```bash
AWS_REGION=eu-west-1 \
DEMO_USERNAME=student@example.com \
DEMO_EMAIL=student@example.com \
DEMO_TENANT_ID=tenant-acme \
./quickstart/linux/dev_first_deploy.sh
```

## Destroy the dev stack

When you are done:

```bash
./quickstart/linux/99_destroy_dev.sh
```

You must type `destroy` to confirm.

## Turning on real Bedrock later

Do this only after the basic dev stack works.

Edit:

```text
infra/terraform/environments/dev/terraform.tfvars
```

Change:

```hcl
enable_real_bedrock = true
```

Then run:

```bash
./quickstart/linux/02_terraform_plan_dev.sh
./quickstart/linux/03_terraform_apply_dev.sh
./quickstart/linux/05_get_token.sh
./quickstart/linux/06_smoke_test_api.sh
```

Before enabling real Bedrock, confirm the selected model is enabled in your AWS account and region.

## Why this lab exists

The project is not just a code sample. It is an AWS learning path for production-style GenAI systems:

1. Identity is derived from Cognito/JWT, not user input.
2. Tenant policy lives in DynamoDB.
3. The LLM cannot invent `tenant_id` for tools.
4. Usage and audit are persisted.
5. The system can be destroyed cleanly after the lab.

This makes the repo approachable for students while still teaching the correct production boundary: probabilistic AI behind deterministic software controls.
