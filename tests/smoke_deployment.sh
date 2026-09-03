#!/usr/bin/env bash
# Stamp a secret-free test deployment into a unique temporary directory and inspect it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SMOKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/funding-director-smoke.XXXXXX")"
cleanup() {
  [ -n "$SMOKE_DIR" ] && [ -d "$SMOKE_DIR" ] &&
    [ "$(basename "$SMOKE_DIR")" != "." ] &&
    [[ "$(basename "$SMOKE_DIR")" == funding-director-smoke.* ]] &&
    rm -rf -- "$SMOKE_DIR"
}
trap cleanup EXIT

PRIVATE_CONFIG="$SMOKE_DIR/.env"
cat > "$PRIVATE_CONFIG" <<EOF
AGENT_NAME=funding-director-smoke
BASE_DIR=$SMOKE_DIR
HERMES_PORT=18789
TZ=America/New_York
AGENT_PERSONA=concise
HERMES_MODEL=openai/gpt-5.6-luna
OPENROUTER_API_KEY=placeholder
TELEGRAM_BOT_TOKEN=placeholder
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
SLACK_ALLOWED_USERS=
DISCORD_BOT_TOKEN=
BLUEBUBBLES_SERVER_URL=
BLUEBUBBLES_PASSWORD=
GATEWAY_ALLOW_ALL_USERS=false
COMPOSIO_API_KEY=
HERMES_MEM_LIMIT=5g
HERMES_CPUS=3.0
EOF
chmod 600 "$PRIVATE_CONFIG"

FUNDING_DIRECTOR_TEST_ROOT="$SMOKE_DIR" "$ROOT/new-agent.sh" "$PRIVATE_CONFIG" >/dev/null

required=(
  "bin/connect-channels.sh"
  "bin/connect-tools.sh"
  "bin/finish-setup.sh"
  "bin/operator-lib.sh"
  "bin/render_config.py"
  "hermes/config.template.yaml"
  "hermes/data/AGENTS.md"
  "hermes/data/SOUL.md"
  "hermes/data/config.yaml"
  "hermes/data/skills/funding/file-underwriting/SKILL.md"
  "hermes/data/skills/funding/product-routing/SKILL.md"
  "hermes/data/skills/funding/provider-onboarding/SKILL.md"
  "hermes/data/skills/funding/submission-operator/SKILL.md"
  "hermes/data/skills/roles/funding-director/SKILL.md"
  "hermes/data/skills/business/operator-onboarding/SKILL.md"
  "funding-director/config/products.json"
  "funding-director/config/destinations.json"
  "funding-director/policies/permissions.json"
  "funding-director/org/registry.json"
  "slack-manifest.yml"
  "vault/agent-knowledge/00.Onboarding.md"
  "vault/agent-knowledge/04.Tool Connections.md"
)
for relative in "${required[@]}"; do
  [ -f "$SMOKE_DIR/$relative" ] || {
    echo "Missing deployed file: $relative" >&2
    exit 1
  }
done

file_mode() {
  python3 -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])' "$1"
}
[ "$(file_mode "$SMOKE_DIR/.env")" = "600" ]
[ "$(file_mode "$SMOKE_DIR/hermes/data/config.yaml")" = "600" ]
[ -L "$SMOKE_DIR/hermes/data/agent-knowledge" ]
grep -q 'Your Funding Director is online' "$SMOKE_DIR/hermes/data/AGENTS.md"
grep -q 'mcp-funding-director-approvals' "$SMOKE_DIR/hermes/data/config.yaml"
grep -q 'trust: untrusted' "$SMOKE_DIR/hermes/data/config.yaml"
grep -q 'enabled: true' "$SMOKE_DIR/hermes/data/config.yaml"
[ -d "$SMOKE_DIR/funding-director/private-knowledge" ]
[ "$(file_mode "$SMOKE_DIR/funding-director/private-knowledge")" = "700" ]
! find "$SMOKE_DIR/hermes/data/skills" -type f -path '*revenue-partner*' | grep -q .
! find "$SMOKE_DIR" -type f -path '*copywriting_retrieval*' | grep -q .

echo "Deployment layout smoke test passed."
