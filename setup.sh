#!/usr/bin/env bash
# Beginner-first, end-to-end setup for a fresh Ubuntu DigitalOcean Droplet.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say() {
  printf '\n%s\n' "$*"
}

fail() {
  printf '\nSetup stopped: %s\n' "$*" >&2
  exit 1
}

ask() {
  local prompt=$1
  local default_value=${2:-}
  local answer
  if [ -n "$default_value" ]; then
    read -r -p "$prompt [$default_value]: " answer
    printf '%s' "${answer:-$default_value}"
  else
    read -r -p "$prompt: " answer
    printf '%s' "$answer"
  fi
}

ask_secret() {
  local prompt=$1
  local answer
  read -r -s -p "$prompt: " answer
  printf '\n' >&2
  printf '%s' "$answer"
}

write_value() {
  local name=$1
  local value=$2
  printf '%s=%q\n' "$name" "$value" >> "$PRIVATE_CONFIG"
}

say "Funding Director setup"
echo "This will install an always-on private operator on this server."
echo "You will be asked for one connection at a time."
echo "Press Enter on any optional connection to add it later."

if [ "$(uname -s)" != "Linux" ]; then
  fail "run this installer on the Ubuntu DigitalOcean server, not on your laptop"
fi

if [ "$(id -u)" -eq 0 ]; then
  ELEVATE=()
else
  command -v sudo >/dev/null 2>&1 || fail "this account needs sudo access"
  ELEVATE=(sudo)
fi

say "Checking the server"
if ! command -v git >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  "${ELEVATE[@]}" apt-get update -qq
  "${ELEVATE[@]}" apt-get install -y -qq git python3 ca-certificates curl
fi
if ! command -v docker >/dev/null 2>&1; then
  install_script="$(mktemp)"
  curl -fsSL https://get.docker.com -o "$install_script"
  "${ELEVATE[@]}" sh "$install_script"
  rm -f "$install_script"
fi
docker compose version >/dev/null 2>&1 || {
  "${ELEVATE[@]}" apt-get update -qq
  "${ELEVATE[@]}" apt-get install -y -qq docker-compose-plugin
}
"${ELEVATE[@]}" systemctl enable --now docker >/dev/null 2>&1 || true

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
elif [ "$(id -u)" -ne 0 ] && "${ELEVATE[@]}" docker info >/dev/null 2>&1; then
  # Current setup uses sudo immediately; future login/cron sessions receive the
  # docker group so the health check works without storing privileged commands.
  "${ELEVATE[@]}" usermod -aG docker "$(id -un)"
  DOCKER=("${ELEVATE[@]}" docker)
else
  fail "Docker was installed but its service is not available"
fi

AGENT_NAME="$(ask "What should the operator be called" "funding-director")"
BASE_DIR="/srv/$AGENT_NAME"
TZ_VALUE="$(ask "What timezone should it use" "America/New_York")"
HERMES_PORT="$(ask "Private dashboard port" "18789")"

say "Connect the AI model"
echo "Open https://openrouter.ai/settings/keys and create one API key."
OPENROUTER_API_KEY="$(ask_secret "Paste the OpenRouter key")"
[ -n "$OPENROUTER_API_KEY" ] || fail "an OpenRouter key is required"

say "Choose how you will message the operator"
echo "1. Telegram (recommended for the first setup)"
echo "2. Slack"
echo "3. Both"
CHANNEL_CHOICE="$(ask "Choose 1, 2, or 3" "1")"
TELEGRAM_BOT_TOKEN=""
SLACK_BOT_TOKEN=""
SLACK_APP_TOKEN=""
SLACK_ALLOWED_USERS=""
SLACK_HOME_CHANNEL=""
case "$CHANNEL_CHOICE" in
  1|3)
    echo "In Telegram, open @BotFather, create a bot, and copy its token."
    TELEGRAM_BOT_TOKEN="$(ask_secret "Paste the Telegram bot token")"
    [ -n "$TELEGRAM_BOT_TOKEN" ] || fail "the Telegram token is required for this choice"
    ;;
esac
case "$CHANNEL_CHOICE" in
  2|3)
    echo "Create a Slack app from this current Agent-view manifest:"
    echo "  $REPO_DIR/slack-manifest.yml"
    echo "Choose 'From an app manifest' at https://api.slack.com/apps."
    echo "Agent view is permanent for this Slack app after Slack applies it."
    echo "Install the app, then create an app-level token with connections:write."
    SLACK_BOT_TOKEN="$(ask_secret "Paste the Slack bot token")"
    SLACK_APP_TOKEN="$(ask_secret "Paste the Slack app token")"
    [[ "$SLACK_BOT_TOKEN" == xoxb-* ]] || \
      fail "the Slack Bot Token must begin with xoxb-"
    [[ "$SLACK_APP_TOKEN" == xapp-* ]] || \
      fail "the Slack App Token must begin with xapp-"
    echo "In Slack, open your profile → three dots → Copy member ID."
    SLACK_ALLOWED_USERS="$(ask "Paste the owner's Slack Member ID; use commas for more than one")"
    SLACK_ALLOWED_USERS="${SLACK_ALLOWED_USERS//[[:space:]]/}"
    [[ "$SLACK_ALLOWED_USERS" =~ ^[UW][A-Z0-9]+(,[UW][A-Z0-9]+)*$ ]] || \
      fail "Slack Member IDs look like U01ABC123; separate multiple IDs with commas"
    echo "Optional: copy the ID of one private home channel for scheduled updates."
    SLACK_HOME_CHANNEL="$(ask "Paste the home channel ID, or press Enter to skip")"
    ;;
  1) ;;
  *) fail "choose 1, 2, or 3" ;;
esac

say "Optional: Calendar, Gmail, documents, and connected business apps"
echo "Open https://app.composio.dev and create a consumer API key."
echo "You can press Enter and connect it after the operator is running."
COMPOSIO_API_KEY="$(ask_secret "Paste the Composio key, or press Enter to skip")"

say "Saving the private configuration"
"${ELEVATE[@]}" mkdir -p "$BASE_DIR"
if [ "$(id -u)" -ne 0 ]; then
  "${ELEVATE[@]}" chown "$(id -u):$(id -g)" "$BASE_DIR"
fi
PRIVATE_CONFIG="$BASE_DIR/.env"
: > "$PRIVATE_CONFIG"
chmod 600 "$PRIVATE_CONFIG"
write_value AGENT_NAME "$AGENT_NAME"
write_value BASE_DIR "$BASE_DIR"
write_value HERMES_PORT "$HERMES_PORT"
write_value TZ "$TZ_VALUE"
write_value AGENT_PERSONA "concise"
write_value HERMES_MODEL "openai/gpt-5.6-luna"
write_value OPENROUTER_API_KEY "$OPENROUTER_API_KEY"
write_value TELEGRAM_BOT_TOKEN "$TELEGRAM_BOT_TOKEN"
write_value SLACK_BOT_TOKEN "$SLACK_BOT_TOKEN"
write_value SLACK_APP_TOKEN "$SLACK_APP_TOKEN"
write_value SLACK_ALLOWED_USERS "$SLACK_ALLOWED_USERS"
write_value SLACK_HOME_CHANNEL "$SLACK_HOME_CHANNEL"
write_value DISCORD_BOT_TOKEN ""
write_value BLUEBUBBLES_SERVER_URL ""
write_value BLUEBUBBLES_PASSWORD ""
write_value GATEWAY_ALLOW_ALL_USERS "false"
write_value COMPOSIO_API_KEY "$COMPOSIO_API_KEY"
write_value HERMES_MEM_LIMIT "5g"
write_value HERMES_CPUS "3.0"

say "Checking the public template"
"$REPO_DIR/scripts/verify.sh"

say "Preparing the operator"
"$REPO_DIR/new-agent.sh" "$PRIVATE_CONFIG"

say "Building and starting the operator"
cd "$BASE_DIR"
"${DOCKER[@]}" compose up -d --build

say "Installing the automatic health check"
watchdog_line="* * * * * $BASE_DIR/bin/watchdog.sh"
cron_file="$(mktemp)"
crontab -l 2>/dev/null | grep -Fv "$BASE_DIR/bin/watchdog.sh" > "$cron_file" || true
printf '%s\n' "$watchdog_line" >> "$cron_file"
crontab "$cron_file"
rm -f "$cron_file"

say "Waiting for the operator to become healthy"
for attempt in $(seq 1 30); do
  health="$("${DOCKER[@]}" inspect "$AGENT_NAME" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' 2>/dev/null || true)"
  if [ "$health" = "healthy" ]; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    "${DOCKER[@]}" compose logs --tail=100 hermes
    fail "the operator did not become healthy; the recent log is shown above"
  fi
  sleep 10
done

say "Your Funding Director is live"
"${DOCKER[@]}" compose ps
echo
if [ -n "$SLACK_BOT_TOKEN" ]; then
  "${DOCKER[@]}" exec -u hermes "$AGENT_NAME" /opt/hermes/.venv/bin/hermes slack manifest \
    --write /opt/data/slack-manifest.json \
    --name "$AGENT_NAME" \
    --description "Your private hosted AI Operator" \
    --agent-view >/dev/null || true
  echo "Complete Slack manifest: $BASE_DIR/hermes/data/slack-manifest.json"
  echo "Slack test 1: open the app in Slack and send: hello"
  echo "Slack test 2: invite it to one approved channel and send:"
  echo "  @$AGENT_NAME Give me a one-sentence status check."
  echo "Slack test 3: reply in that thread without another mention."
fi
echo
echo "To open the private dashboard from your computer, use:"
echo "  ssh -L $HERMES_PORT:127.0.0.1:$HERMES_PORT <your-server>"
echo "Then open http://localhost:$HERMES_PORT"
echo
FINISH_NOW="$(ask "Connect business tools or another messaging app now? y/n" "y")"
case "$FINISH_NOW" in
  y|Y|yes|YES) "$BASE_DIR/bin/finish-setup.sh" ;;
  *)
    echo "You can open the finish menu later with: $BASE_DIR/bin/finish-setup.sh"
    ;;
esac
echo
echo "Send 'hello' in your chosen messaging app."
echo "The first reply will offer quick start or guided personalization."
