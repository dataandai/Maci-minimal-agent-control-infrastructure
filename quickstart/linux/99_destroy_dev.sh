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

cat <<'MSG'
This will destroy the Terraform dev stack.
It does not delete local .quickstart files unless you remove them manually.
MSG

read -r -p "Destroy dev stack? Type 'destroy': " answer
if [[ "$answer" != "destroy" ]]; then
  echo "Aborted."
  exit 1
fi

cd "$TF_ROOT"
terraform destroy -var-file="$TF_VAR_FILE"
