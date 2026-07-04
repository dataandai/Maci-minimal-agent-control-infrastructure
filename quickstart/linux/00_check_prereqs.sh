#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

AWS_REGION="${AWS_REGION:-eu-west-1}"

ok() { printf "\033[32mOK\033[0m %s\n" "$1"; }
warn() { printf "\033[33mWARN\033[0m %s\n" "$1"; }
fail() { printf "\033[31mFAIL\033[0m %s\n" "$1"; exit 1; }

require_cmd() {
  local cmd="$1"
  local hint="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd found: $(command -v "$cmd")"
  else
    fail "$cmd not found. $hint"
  fi
}

printf "\nMaci: minimal agent control infrastructure — AWS first deploy check\n"
printf "Repository: %s\n" "$ROOT_DIR"
printf "Target region: %s\n\n" "$AWS_REGION"

require_cmd aws "Install AWS CLI v2 and run: aws configure"
require_cmd terraform "Install Terraform >= 1.6"
require_cmd python3.12 "Install Python 3.12; Terraform Lambda packaging uses python3.12 by default"
require_cmd unzip "Install unzip"
require_cmd curl "Install curl"

python3.12 -m pip --version >/dev/null 2>&1 || fail "python3.12 pip is missing. Try: python3.12 -m ensurepip --upgrade"
ok "python3.12 pip is available"

TF_VERSION="$(terraform version -json 2>/dev/null | python3.12 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])' 2>/dev/null || terraform version | head -n1)"
ok "Terraform version: $TF_VERSION"

aws sts get-caller-identity >/tmp/maci_sts.json 2>/tmp/maci_sts.err || {
  cat /tmp/maci_sts.err >&2
  fail "AWS credentials are not configured or not valid. Run: aws configure"
}
ACCOUNT_ID="$(python3.12 -c 'import json; print(json.load(open("/tmp/maci_sts.json"))["Account"])')"
ARN="$(python3.12 -c 'import json; print(json.load(open("/tmp/maci_sts.json"))["Arn"])')"
ok "AWS account: $ACCOUNT_ID"
ok "AWS identity: $ARN"

if [[ ! -f infra/terraform/environments/dev/terraform.tfvars ]]; then
  fail "Missing infra/terraform/environments/dev/terraform.tfvars"
fi
ok "Terraform dev environment file exists"

if [[ ! -f scripts/seed_demo_policies.py ]]; then
  fail "Missing scripts/seed_demo_policies.py"
fi
ok "Demo seed script exists"

mkdir -p .quickstart
cat > .quickstart/dev.env <<ENV
AWS_REGION=$AWS_REGION
TF_ROOT=$ROOT_DIR/infra/terraform
TF_VAR_FILE=environments/dev/terraform.tfvars
DEMO_USERNAME=demo@example.com
DEMO_EMAIL=demo@example.com
DEMO_TENANT_ID=tenant-acme
ENV
chmod 600 .quickstart/dev.env

printf "\nNext:\n  ./quickstart/linux/01_prepare_local_python.sh\n"
