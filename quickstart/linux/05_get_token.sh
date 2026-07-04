#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .quickstart/dev-user.env ]]; then
  echo "Missing .quickstart/dev-user.env. Run 04_seed_demo_data_and_user.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .quickstart/dev-user.env
# shellcheck disable=SC1091
source .venv/bin/activate

printf "\nGetting Cognito ID token for %s...\n" "$DEMO_USERNAME"
AUTH_JSON="$(python scripts/get_cognito_token.py \
  --client-id "$COGNITO_USER_POOL_CLIENT_ID" \
  --username "$DEMO_USERNAME" \
  --password "$DEMO_PASSWORD" \
  --region "$AWS_REGION")"

printf '%s\n' "$AUTH_JSON" > .quickstart/cognito-auth-result.json
ID_TOKEN="$(python - <<'PY'
import json
with open('.quickstart/cognito-auth-result.json') as f:
    print(json.load(f)['IdToken'])
PY
)"
printf '%s' "$ID_TOKEN" > .quickstart/id-token.txt
chmod 600 .quickstart/cognito-auth-result.json .quickstart/id-token.txt

printf "ID token saved to .quickstart/id-token.txt\n"
printf "Next:\n  ./quickstart/linux/06_smoke_test_api.sh\n"
