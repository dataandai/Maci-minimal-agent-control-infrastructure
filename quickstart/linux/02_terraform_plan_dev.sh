#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .quickstart/dev.env ]]; then
  # shellcheck disable=SC1091
  source .quickstart/dev.env
else
  AWS_REGION="${AWS_REGION:-eu-west-1}"
  TF_ROOT="$ROOT_DIR/infra/terraform"
  TF_VAR_FILE="environments/dev/terraform.tfvars"
fi

printf "\nTerraform init/validate/plan for dev...\n"
cd "$TF_ROOT"
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file="$TF_VAR_FILE" -out=tfplan-dev

printf "\nPlan saved to infra/terraform/tfplan-dev. Review the plan above.\n"
printf "Next:\n  ./quickstart/linux/03_terraform_apply_dev.sh\n"
