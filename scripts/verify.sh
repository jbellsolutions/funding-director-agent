#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Checking shell scripts..."
while IFS= read -r script; do
  bash -n "$script"
done < <(find . -type f -name '*.sh' -not -path './.git/*' | sort)

echo "Checking Python files..."
python3 -m compileall -q \
  scripts \
  tests \
  sync \
  files/local-packages/funding-director/src

echo "Checking funding configuration..."
python3 -m json.tool files/local-packages/funding-director/config/products.json >/dev/null
python3 -m json.tool files/local-packages/funding-director/config/destinations.json >/dev/null
python3 -m json.tool files/local-packages/funding-director/config/training-sources.json >/dev/null
python3 -m json.tool policies/permissions.json >/dev/null
python3 -m json.tool org/registry.json >/dev/null
python3 scripts/validate_funding_config.py

echo "Running repository tests..."
PYTHONPATH="$ROOT/files/local-packages/funding-director/src${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest discover -s tests -v

echo "Checking a complete secret-free installation layout..."
./tests/smoke_deployment.sh

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Checking Compose configuration..."
  OPENROUTER_API_KEY=placeholder \
  BASE_DIR=/srv/funding-director \
  AGENT_NAME=funding-director \
    docker compose -f compose.yml config --quiet
fi

echo "Verification passed."
