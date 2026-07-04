#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

cat <<'MSG'
This will deploy the dev AWS stack with Terraform using the dev tfvars file.
Default mode is safe starter mode:
  - enable_real_bedrock=false
  - enable_bedrock_agent=false

AWS costs may still occur for API Gateway, Lambda, DynamoDB, Step Functions, CloudWatch logs/metrics.
Use 99_destroy_dev.sh when you are done.
MSG

if [[ "${AUTO_APPROVE:-false}" != "true" ]]; then
  read -r -p "Continue? Type 'yes': " answer
  if [[ "$answer" != "yes" ]]; then
    echo "Aborted."
    exit 1
  fi
fi

./quickstart/linux/00_check_prereqs.sh
./quickstart/linux/01_prepare_local_python.sh
./quickstart/linux/02_terraform_plan_dev.sh
./quickstart/linux/03_terraform_apply_dev.sh
./quickstart/linux/04_seed_demo_data_and_user.sh
./quickstart/linux/05_get_token.sh
./quickstart/linux/06_smoke_test_api.sh

printf "\nDev stack deployed and smoke-tested.\n"
