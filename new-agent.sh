#!/usr/bin/env bash
# Stamp out or safely refresh one hosted Operator from one private env file.
set -euo pipefail

TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIVATE_CONFIG="${1:-}"

fail() {
  echo "Setup could not continue: $*" >&2
  exit 1
}

[ -n "$PRIVATE_CONFIG" ] && [ -f "$PRIVATE_CONFIG" ] || \
  fail "run ./setup.sh, or pass a filled agent.env to ./new-agent.sh"

# The private file is created by setup.sh and owned by the operator. Loading it
# here makes its values available to Compose and to the safe Python renderer.
# shellcheck disable=SC1090
set -a
source "$PRIVATE_CONFIG"
set +a

: "${AGENT_NAME:?AGENT_NAME is missing}"
: "${BASE_DIR:?BASE_DIR is missing}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is missing}"
[[ "$AGENT_NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]] || \
  fail "AGENT_NAME may contain lowercase letters, numbers, and dashes only"
if [[ "$BASE_DIR" != /srv/* ]]; then
  [ -n "${FUNDING_DIRECTOR_TEST_ROOT:-}" ] && [ "$BASE_DIR" = "$FUNDING_DIRECTOR_TEST_ROOT" ] || \
    fail "BASE_DIR must be a specific folder under /srv"
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && \
   { [ -z "${SLACK_BOT_TOKEN:-}" ] || [ -z "${SLACK_APP_TOKEN:-}" ]; }; then
  fail "connect Telegram, or provide both Slack tokens, before launching"
fi
if [ -n "${SLACK_BOT_TOKEN:-}" ] && [ -z "${SLACK_ALLOWED_USERS:-}" ]; then
  fail "SLACK_ALLOWED_USERS must contain the authorized owner's Slack Member ID"
fi

SLACK_ENABLED=false
TELEGRAM_ENABLED=false
[ -n "${SLACK_BOT_TOKEN:-}" ] && [ -n "${SLACK_APP_TOKEN:-}" ] && SLACK_ENABLED=true
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && TELEGRAM_ENABLED=true
COMPOSIO_ENABLED=false
[ -n "${COMPOSIO_API_KEY:-}" ] && COMPOSIO_ENABLED=true
JOBS_ENABLED=false
[ -n "${BRIEF_SLACK_CHANNEL:-}" ] && JOBS_ENABLED=true
VOICE_ENABLED=false
[ -n "${ELEVENLABS_API_KEY:-}" ] && [ -n "${VOICE_DOMAIN:-}" ] && \
  [ -n "${RELAY_TOKEN:-}" ] && VOICE_ENABLED=true

echo "Preparing Operator at $BASE_DIR"
echo "  Telegram: $TELEGRAM_ENABLED"
echo "  Slack: $SLACK_ENABLED"
echo "  Calendar and business apps: $COMPOSIO_ENABLED"
echo "  Scheduled briefings: $JOBS_ENABLED"
echo "  Browser voice front end: $VOICE_ENABLED"

mkdir -p \
  "$BASE_DIR/bin" \
  "$BASE_DIR/sync" \
  "$BASE_DIR/hermes/data/skills" \
  "$BASE_DIR/vault/daily-logs" \
  "$BASE_DIR/vault/agent-knowledge" \
  "$BASE_DIR/logs" \
  "$BASE_DIR/hermes-image" \
  "$BASE_DIR/files/local-packages" \
  "$BASE_DIR/funding-director/config" \
  "$BASE_DIR/funding-director/private-knowledge" \
  "$BASE_DIR/funding-director/state" \
  "$BASE_DIR/funding-director/policies" \
  "$BASE_DIR/funding-director/org"

# Runtime stack and exact build inputs.
cp "$TEMPLATE_DIR/compose.yml" "$BASE_DIR/compose.yml"
cp "$TEMPLATE_DIR/.dockerignore" "$BASE_DIR/.dockerignore"
cp "$TEMPLATE_DIR/bin/init-chown.sh" "$BASE_DIR/bin/init-chown.sh"
cp "$TEMPLATE_DIR/bin/start-hermes.sh" "$BASE_DIR/bin/start-hermes.sh"
cp "$TEMPLATE_DIR/bin/connect-tools.sh" "$BASE_DIR/bin/connect-tools.sh"
cp "$TEMPLATE_DIR/bin/connect-channels.sh" "$BASE_DIR/bin/connect-channels.sh"
cp "$TEMPLATE_DIR/bin/finish-setup.sh" "$BASE_DIR/bin/finish-setup.sh"
cp "$TEMPLATE_DIR/bin/operator-lib.sh" "$BASE_DIR/bin/operator-lib.sh"
cp "$TEMPLATE_DIR/scripts/render_config.py" "$BASE_DIR/bin/render_config.py"
cp "$TEMPLATE_DIR/hermes/config.template.yaml" "$BASE_DIR/hermes/config.template.yaml"
cp "$TEMPLATE_DIR/slack-manifest.yml" "$BASE_DIR/slack-manifest.yml"
cp "$TEMPLATE_DIR/hermes-image/Dockerfile" "$BASE_DIR/hermes-image/Dockerfile"
find "$TEMPLATE_DIR/sync" -maxdepth 1 -type f -exec cp {} "$BASE_DIR/sync/" \;
rm -rf "$BASE_DIR/files/local-packages/super-browser"
cp -R "$TEMPLATE_DIR/files/local-packages/super-browser" \
  "$BASE_DIR/files/local-packages/super-browser"
rm -rf "$BASE_DIR/files/local-packages/funding-director"
cp -R "$TEMPLATE_DIR/files/local-packages/funding-director" \
  "$BASE_DIR/files/local-packages/funding-director"

# Product and destination policy is durable and owner-controlled. A reinstall
# refreshes code but never overwrites activated provider rules or audit state.
for item in products.json destinations.json training-sources.json; do
  [ -f "$BASE_DIR/funding-director/config/$item" ] || \
    cp "$TEMPLATE_DIR/files/local-packages/funding-director/config/$item" \
      "$BASE_DIR/funding-director/config/$item"
done
[ -f "$BASE_DIR/funding-director/policies/permissions.json" ] || \
  cp "$TEMPLATE_DIR/policies/permissions.json" "$BASE_DIR/funding-director/policies/permissions.json"
[ -f "$BASE_DIR/funding-director/org/registry.json" ] || \
  cp "$TEMPLATE_DIR/org/registry.json" "$BASE_DIR/funding-director/org/registry.json"
chmod 700 "$BASE_DIR/funding-director/private-knowledge" "$BASE_DIR/funding-director/state"

# The supplied private config becomes Compose's private .env. Never print it.
if [ ! "$PRIVATE_CONFIG" -ef "$BASE_DIR/.env" ]; then
  cp "$PRIVATE_CONFIG" "$BASE_DIR/.env"
fi
chmod 600 "$BASE_DIR/.env"

# Watchdog values are not secrets; render the two path placeholders.
sed -e "s#__AGENT_NAME__#${AGENT_NAME}#g" \
    -e "s#__BASE_DIR__#${BASE_DIR}#g" \
    "$TEMPLATE_DIR/bin/watchdog.sh" > "$BASE_DIR/bin/watchdog.sh"
chmod +x "$BASE_DIR/bin/"*.sh

# A new Funding Director gets its governed identity, durable knowledge structure,
# and tool procedures. Existing owner-edited copies always win on re-runs.
if [ ! -f "$BASE_DIR/hermes/data/SOUL.md" ]; then
  cp "$TEMPLATE_DIR/files/SOUL.md" "$BASE_DIR/hermes/data/SOUL.md"
fi
if [ ! -f "$BASE_DIR/hermes/data/AGENTS.md" ]; then
  cp "$TEMPLATE_DIR/files/AGENTS.md" "$BASE_DIR/hermes/data/AGENTS.md"
fi
if [ ! -f "$BASE_DIR/vault/agent-knowledge/INDEX.md" ]; then
  cp -R "$TEMPLATE_DIR/files/agent-knowledge/." "$BASE_DIR/vault/agent-knowledge/"
fi
if [ ! -e "$BASE_DIR/hermes/data/agent-knowledge" ]; then
  ln -s ../../vault/agent-knowledge "$BASE_DIR/hermes/data/agent-knowledge"
fi

for skill_dir in "$TEMPLATE_DIR/files/skills"/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  [ -e "$BASE_DIR/hermes/data/skills/$skill_name" ] || \
    cp -R "$skill_dir" "$BASE_DIR/hermes/data/skills/$skill_name"
done
for skill_dir in "$TEMPLATE_DIR/files/local-packages/super-browser/skills"/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  [ -e "$BASE_DIR/hermes/data/skills/$skill_name" ] || \
    cp -R "$skill_dir" "$BASE_DIR/hermes/data/skills/$skill_name"
done

# Render the declared setup on each run so adding Calendar later is one smooth
# re-run. Preserve the previous private file locally for recovery.
CONFIG_PATH="$BASE_DIR/hermes/data/config.yaml"
if [ -f "$CONFIG_PATH" ]; then
  cp "$CONFIG_PATH" "$CONFIG_PATH.pre-setup.bak"
fi
python3 "$TEMPLATE_DIR/scripts/render_config.py" \
  "$TEMPLATE_DIR/hermes/config.template.yaml" "$CONFIG_PATH"
echo "  Rendered the private Hermes configuration."

render_overlay() {
  sed -e "s#__AGENT_NAME__#${AGENT_NAME}#g" \
      -e "s#__BASE_DIR__#${BASE_DIR}#g" \
      -e "s#__VOICE_DOMAIN__#${VOICE_DOMAIN:-}#g" \
      -e "s#__ELEVENLABS_VOICE_ID__#${ELEVENLABS_VOICE_ID:-}#g" \
      "$1" > "$2"
}

if [ "$JOBS_ENABLED" = true ]; then
  mkdir -p "$BASE_DIR/scripts/jobs" "$BASE_DIR/state"
  render_overlay "$TEMPLATE_DIR/scripts/jobs/jobs.py" "$BASE_DIR/scripts/jobs/jobs.py"
  render_overlay "$TEMPLATE_DIR/bin/setup-cron.sh" "$BASE_DIR/bin/setup-cron.sh"
  chmod +x "$BASE_DIR/bin/setup-cron.sh"
fi

if [ "$VOICE_ENABLED" = true ]; then
  mkdir -p "$BASE_DIR/voice/www"
  for item in relay.py create_agent.py patch_agent.py README-VOICE.md voice-relay.service Caddyfile; do
    render_overlay "$TEMPLATE_DIR/voice/$item" "$BASE_DIR/voice/$item"
  done
  render_overlay "$TEMPLATE_DIR/voice/www/talk.html" "$BASE_DIR/voice/www/talk.html"
  render_overlay "$TEMPLATE_DIR/bin/setup-voice.sh" "$BASE_DIR/bin/setup-voice.sh"
  chmod +x "$BASE_DIR/bin/setup-voice.sh"
fi

cat <<EOF

Operator files are ready.

Launch:
  cd $BASE_DIR
  docker compose up -d --build

Private dashboard:
  ssh -L ${HERMES_PORT:-18789}:127.0.0.1:${HERMES_PORT:-18789} <your-server>
  then open http://localhost:${HERMES_PORT:-18789}

After launch, connect optional accounts with:
  $BASE_DIR/bin/finish-setup.sh
EOF
