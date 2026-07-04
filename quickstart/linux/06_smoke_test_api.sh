#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .quickstart/dev-user.env || ! -f .quickstart/id-token.txt ]]; then
  echo "Missing demo env or token. Run scripts 04 and 05 first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .quickstart/dev-user.env
# shellcheck disable=SC1091
source .venv/bin/activate
ID_TOKEN="$(cat .quickstart/id-token.txt)"

printf "\nInvoking API smoke test...\n"
python scripts/smoke_test_api.py \
  --url "$AGENT_INVOKE_URL" \
  --id-token "$ID_TOKEN" \
  --tenant-id "$DEMO_TENANT_ID"

printf "\nSmoke test finished. Check CloudWatch logs/dashboard if needed.\n"
printf "To destroy the dev stack later:\n  ./quickstart/linux/99_destroy_dev.sh\n"
