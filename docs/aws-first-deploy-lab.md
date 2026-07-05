# AWS First Deploy Lab

This lab helps you deploy the Maci dev stack into your own AWS account.

It is intended for learning and validation, not production.

---

## What you will prove

A useful first deploy should prove:

```text
Terraform can deploy the dev stack
API endpoint is reachable
authentication works
trusted tenant context is created
conversation state can be written
workflow state can be written
tool calls can be authorized/denied
audit and usage events are written
recovery daemon exists and can be invoked
```

---

## Prerequisites

Install:

```text
Python 3.11+
git
AWS CLI v2
Terraform CLI
```

Check:

```bash
python --version
git --version
aws --version
terraform version
```

Authenticate:

```bash
aws sso login --profile <profile>
aws sts get-caller-identity --profile <profile>
```

---

## Recommended quickstart

From the repository root:

```bash
./quickstart/linux/dev_first_deploy.sh
```

This script chains the individual lab steps.

---

## Step-by-step flow

```bash
./quickstart/linux/00_check_prereqs.sh
./quickstart/linux/01_prepare_local_python.sh
./quickstart/linux/02_terraform_plan_dev.sh
./quickstart/linux/03_terraform_apply_dev.sh
./quickstart/linux/04_seed_demo_data_and_user.sh
./quickstart/linux/05_get_token.sh
./quickstart/linux/06_smoke_test_api.sh
```

Destroy when done:

```bash
./quickstart/linux/99_destroy_dev.sh
```

---

## Local validation before AWS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,aws]'
python -m compileall -q src tests
pytest -q
```

Do not deploy broken local code to AWS.

---

## First smoke test expectations

A normal support request should:

```text
authenticate user
create trusted tenant context
create/resume conversation
write workflow state
run policy and guardrail checks
allow owned customer lookup
deny cross-tenant customer lookup
create ticket with idempotency
create pending approval for account_credit
audit decisions
write usage event
```

---

## Recovery smoke test

Create or simulate a stale workflow record due for recovery.

Then invoke the recovery daemon with a small limit.

Expected:

```text
daemon claims workflow with lease
classifies resume policy
writes recovery audit event
writes non-user-visible conversation status if configured
releases for retry or escalates to human review
```

---

## Common beginner pitfalls

```text
wrong AWS account
wrong region
Bedrock model access missing
installing only .[dev] instead of .[dev,aws]
missing seed data
missing resource ownership records
S3 Object Lock prevents destroy
Terraform validate passes but apply fails
IAM too broad after quick fix
```

Detailed pitfalls: [`aws-deployment-guide-for-junior-engineers.md`](aws-deployment-guide-for-junior-engineers.md)
