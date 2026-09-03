#!/usr/bin/env bash
# Safely refresh an installed Funding Director from a reviewed repository release.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIVATE_CONFIG="${1:-/srv/funding-director/.env}"

fail() {
  printf '\nUpdate stopped: %s\n' "$*" >&2
  exit 1
}

[ -f "$PRIVATE_CONFIG" ] || \
  fail "private configuration not found; pass its path, such as ./update.sh /srv/my-operator/.env"

set -a
# shellcheck disable=SC1090
source "$PRIVATE_CONFIG"
set +a
: "${AGENT_NAME:?AGENT_NAME is missing from the private configuration}"
: "${BASE_DIR:?BASE_DIR is missing from the private configuration}"

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
elif command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
else
  fail "Docker is not available to this account"
fi

echo "Checking the repository and exact runtime release..."
git -C "$REPO_DIR" pull --ff-only
"$REPO_DIR/scripts/verify.sh"

echo "Refreshing public files while preserving private memory and existing skills..."
"$REPO_DIR/new-agent.sh" "$PRIVATE_CONFIG"

echo "Building the reviewed image and restarting Funding Director..."
(
  cd "$BASE_DIR"
  "${DOCKER[@]}" compose build --pull hermes
  "${DOCKER[@]}" compose up -d --force-recreate hermes
)

for attempt in $(seq 1 30); do
  health="$("${DOCKER[@]}" inspect "$AGENT_NAME" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)"
  [ "$health" = "healthy" ] && break
  [ "$attempt" -lt 30 ] || fail "the updated Operator did not become healthy"
  sleep 10
done

"${DOCKER[@]}" exec -u hermes "$AGENT_NAME" \
  /opt/hermes/.venv/bin/hermes slack manifest \
    --write /opt/data/slack-manifest.json \
    --name "$AGENT_NAME" \
    --description "Your private hosted AI Operator" \
    --agent-view >/dev/null
"${DOCKER[@]}" exec -u hermes "$AGENT_NAME" \
  /opt/hermes/.venv/bin/hermes skills check
"${DOCKER[@]}" exec -u hermes "$AGENT_NAME" \
  /opt/hermes/.venv/bin/hermes skills audit

echo
echo "Funding Director is healthy on the reviewed runtime."
echo "Owner memory and existing skills were preserved."
echo "The refreshed Slack manifest is: $BASE_DIR/hermes/data/slack-manifest.json"
echo "Review optional skill updates before applying them with:"
echo "  ${DOCKER[*]} exec -it -u hermes $AGENT_NAME /opt/hermes/.venv/bin/hermes skills update"
