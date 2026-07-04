#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .quickstart/dev.env ]]; then
  # shellcheck disable=SC1091
  source .quickstart/dev.env
else
  TF_ROOT="$ROOT_DIR/infra/terraform"
  TF_VAR_FILE="environments/dev/terraform.tfvars"
fi

printf "\nApplying Terraform dev stack...\n"
cd "$TF_ROOT"
if [[ -f tfplan-dev ]]; then
  terraform apply tfplan-dev
else
  terraform apply -var-file="$TF_VAR_FILE"
fi

mkdir -p "$ROOT_DIR/.quickstart"
terraform output -json > "$ROOT_DIR/.quickstart/terraform-outputs-dev.json"
chmod 600 "$ROOT_DIR/.quickstart/terraform-outputs-dev.json"

printf "\nTerraform outputs saved to .quickstart/terraform-outputs-dev.json\n"
printf "Next:\n  ./quickstart/linux/04_seed_demo_data_and_user.sh\n"
