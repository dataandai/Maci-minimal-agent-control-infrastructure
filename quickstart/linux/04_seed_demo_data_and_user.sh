#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .quickstart/dev.env ]]; then
  # shellcheck disable=SC1091
  source .quickstart/dev.env
fi
AWS_REGION="${AWS_REGION:-eu-west-1}"
TF_ROOT="${TF_ROOT:-$ROOT_DIR/infra/terraform}"
DEMO_USERNAME="${DEMO_USERNAME:-demo@example.com}"
DEMO_EMAIL="${DEMO_EMAIL:-demo@example.com}"
DEMO_TENANT_ID="${DEMO_TENANT_ID:-tenant-acme}"
DEMO_PASSWORD="${DEMO_PASSWORD:-}"

# shellcheck disable=SC1091
source .venv/bin/activate

cd "$TF_ROOT"
POLICY_TABLE="$(terraform output -raw policy_table_name)"
AGENT_REGISTRY_TABLE="$(terraform output -raw agent_registry_table_name)"
RESOURCE_OWNERSHIP_TABLE="$(terraform output -raw resource_ownership_table_name)"
USER_POOL_ID="$(terraform output -raw cognito_user_pool_id)"
CLIENT_ID="$(terraform output -raw cognito_user_pool_client_id)"
API_URL="$(terraform output -raw agent_invoke_url)"
cd "$ROOT_DIR"

printf "\nSeeding demo tenant policies into %s...\n" "$POLICY_TABLE"
python scripts/seed_demo_policies.py --table "$POLICY_TABLE" --agent-registry-table "$AGENT_REGISTRY_TABLE" --resource-ownership-table "$RESOURCE_OWNERSHIP_TABLE" --region "$AWS_REGION"

if [[ -z "$DEMO_PASSWORD" ]]; then
  DEMO_PASSWORD="$(python3.12 - <<'PY'
import secrets,string
alphabet = string.ascii_letters + string.digits
while True:
    pw = ''.join(secrets.choice(alphabet) for _ in range(18))
    if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw):
        print(pw)
        break
PY
)"
fi

printf "\nCreating or updating demo Cognito user %s for tenant %s...\n" "$DEMO_USERNAME" "$DEMO_TENANT_ID"
python scripts/create_cognito_demo_user.py \
  --user-pool-id "$USER_POOL_ID" \
  --username "$DEMO_USERNAME" \
  --email "$DEMO_EMAIL" \
  --tenant-id "$DEMO_TENANT_ID" \
  --password "$DEMO_PASSWORD" \
  --region "$AWS_REGION"

cat > .quickstart/dev-user.env <<ENV
AWS_REGION=$AWS_REGION
DEMO_USERNAME=$DEMO_USERNAME
DEMO_EMAIL=$DEMO_EMAIL
DEMO_TENANT_ID=$DEMO_TENANT_ID
DEMO_PASSWORD=$DEMO_PASSWORD
COGNITO_USER_POOL_ID=$USER_POOL_ID
COGNITO_USER_POOL_CLIENT_ID=$CLIENT_ID
AGENT_INVOKE_URL=$API_URL
POLICY_TABLE_NAME=$POLICY_TABLE
AGENT_REGISTRY_TABLE_NAME=$AGENT_REGISTRY_TABLE
RESOURCE_OWNERSHIP_TABLE_NAME=$RESOURCE_OWNERSHIP_TABLE
ENV
chmod 600 .quickstart/dev-user.env

printf "\nDemo user credentials saved to .quickstart/dev-user.env\n"
printf "Username: %s\n" "$DEMO_USERNAME"
printf "Password: %s\n" "$DEMO_PASSWORD"
printf "Next:\n  ./quickstart/linux/05_get_token.sh\n"
