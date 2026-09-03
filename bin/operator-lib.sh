#!/usr/bin/env bash
# Shared private-config and Docker helpers for post-install setup menus.

OPERATOR_BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPERATOR_ENV="$OPERATOR_BASE_DIR/.env"

operator_fail() {
  printf '\nSetup stopped: %s\n' "$*" >&2
  exit 1
}

operator_secret() {
  local prompt=$1 value
  read -r -s -p "$prompt: " value
  printf '\n' >&2
  printf '%s' "$value"
}

operator_load_env() {
  [ -f "$OPERATOR_ENV" ] || operator_fail "private configuration not found at $OPERATOR_ENV"
  set -a
  # shellcheck disable=SC1090
  source "$OPERATOR_ENV"
  set +a
}

operator_init_docker() {
  if docker info >/dev/null 2>&1; then
    OPERATOR_DOCKER=(docker)
  elif command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    OPERATOR_DOCKER=(sudo docker)
  else
    operator_fail "Docker is not available to this account"
  fi
}

operator_docker() {
  "${OPERATOR_DOCKER[@]}" "$@"
}

operator_save_value() {
  local key=$1 value=$2 temp
  [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || operator_fail "invalid configuration name"
  [[ "$value" != *$'\n'* ]] || operator_fail "configuration values cannot contain a new line"
  temp="$(mktemp "$OPERATOR_ENV.tmp.XXXXXX")"
  awk -v key="$key" 'index($0, key "=") != 1 { print }' "$OPERATOR_ENV" > "$temp"
  printf '%s=%q\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$OPERATOR_ENV"
  export "$key=$value"
}

operator_refresh() {
  operator_load_env
  python3 "$OPERATOR_BASE_DIR/bin/render_config.py" \
    "$OPERATOR_BASE_DIR/hermes/config.template.yaml" \
    "$OPERATOR_BASE_DIR/hermes/data/config.yaml"
  (
    cd "$OPERATOR_BASE_DIR"
    operator_docker compose up -d --force-recreate hermes
  )
}

operator_hermes() {
  operator_docker exec -it -u hermes "${AGENT_NAME:-funding-director}" \
    /opt/hermes/.venv/bin/hermes "$@"
}

operator_generate_slack_manifest() {
  operator_docker exec -u hermes "${AGENT_NAME:-funding-director}" \
    /opt/hermes/.venv/bin/hermes slack manifest \
      --write /opt/data/slack-manifest.json \
      --name "${AGENT_NAME:-Funding Director}" \
      --description "Your private hosted AI Operator" \
      --agent-view >/dev/null
  printf '%s\n' "$OPERATOR_BASE_DIR/hermes/data/slack-manifest.json"
}
