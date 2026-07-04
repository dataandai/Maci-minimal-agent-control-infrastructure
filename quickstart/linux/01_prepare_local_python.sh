#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

printf "\nPreparing local Python environment...\n"
python3.12 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -e '.[dev,aws]' >/dev/null
python -m pytest

printf "\nLocal tests passed.\n"
printf "Next:\n  ./quickstart/linux/02_terraform_plan_dev.sh\n"
