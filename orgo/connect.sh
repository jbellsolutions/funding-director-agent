#!/usr/bin/env bash
# One plain-language connection menu for Funding Director on Orgo.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="$HERMES_HOME/.env"
mkdir -p "$HERMES_HOME"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

secret() { local value; read -r -s -p "$1: " value; printf '\n' >&2; printf '%s' "$value"; }
fail() { printf 'Connection stopped: %s\n' "$*" >&2; exit 1; }
upsert() {
  local key=$1 value=$2 temp
  [[ "$value" != *$'\n'* ]] || fail "a private value cannot contain a new line"
  temp="$(mktemp "$HERMES_HOME/.env.tmp.XXXXXX")"
  awk -v key="$key" 'index($0, key "=") != 1 { print }' "$ENV_FILE" > "$temp"
  printf '%s=%s\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$ENV_FILE"
}
restart_gateway() {
  hermes gateway install >/dev/null
  hermes gateway restart >/dev/null 2>&1 || hermes gateway start >/dev/null
}

cat <<'MENU'
Connect Funding Director

  1. Slack
  2. Telegram
  3. Funding Machine (read-only underwriting and funding data)
  4. GoHighLevel (scoped official API)
  5. Calendar, inboxes, files, and other business apps
  6. Show connection status
MENU
read -r -p "Choose 1 through 6: " choice
case "$choice" in
  1)
    echo "Create the Slack app from slack-manifest.yml in this repository."
    echo "Install it, then create an app-level token with connections:write."
    bot="$(secret "Paste the xoxb- Bot Token")"
    app="$(secret "Paste the xapp- App Token")"
    [[ "$bot" == xoxb-* ]] || fail "the Bot Token must start with xoxb-"
    [[ "$app" == xapp-* ]] || fail "the App Token must start with xapp-"
    read -r -p "Paste the owner's Slack Member ID: " allowed
    [[ "$allowed" =~ ^[UW][A-Z0-9]+(,[UW][A-Z0-9]+)*$ ]] || fail "that Member ID is not valid"
    upsert SLACK_BOT_TOKEN "$bot"
    upsert SLACK_APP_TOKEN "$app"
    upsert SLACK_ALLOWED_USERS "$allowed"
    unset bot app
    hermes config set gateway.platforms.slack.enabled true >/dev/null
    restart_gateway
    echo "Slack is connected. Send hello, then verify the reply."
    ;;
  2)
    echo "Create the bot in Telegram with @BotFather, then copy its token."
    token="$(secret "Paste the Telegram bot token")"
    [[ "$token" == *:* ]] || fail "that does not look like a Telegram bot token"
    upsert TELEGRAM_BOT_TOKEN "$token"
    unset token
    hermes config set gateway.platforms.telegram.enabled true >/dev/null
    restart_gateway
    echo "Telegram is connected. Send hello, then verify the reply."
    ;;
  3)
    echo "Create a dedicated read-only AI key in Funding Machine. Keys begin fmk_."
    value="$(secret "Paste the fmk_ Funding Machine key")"
    [[ "$value" == fmk_* ]] || fail "the Funding Machine key must begin with fmk_"
    upsert FUNDING_MACHINE_API_KEY "$value"
    unset value
    hermes config set mcp_servers.funding-machine.url https://marketplace-app.myfundingmachine.com/api/mcp >/dev/null
    hermes config set mcp_servers.funding-machine.headers.Authorization 'Bearer ${FUNDING_MACHINE_API_KEY}' >/dev/null
    hermes config set mcp_servers.funding-machine.trust untrusted >/dev/null
    hermes config set mcp_servers.funding-machine.timeout 120 >/dev/null
    hermes config set mcp_servers.funding-machine.enabled true >/dev/null
    hermes config set platform_toolsets.cli '["hermes-cli","a2a","mcp-funding-director-core","mcp-funding-director-approvals","mcp-funding-machine"]' >/dev/null
    hermes config set platform_toolsets.slack '["hermes-slack","a2a","mcp-funding-director-core","mcp-funding-director-approvals","mcp-funding-machine"]' >/dev/null
    hermes config set platform_toolsets.telegram '["hermes-telegram","a2a","mcp-funding-director-core","mcp-funding-director-approvals","mcp-funding-machine"]' >/dev/null
    restart_gateway
    echo "Funding Machine is connected read-only. Verify by listing accessible locations."
    ;;
  4)
    echo "Create a location-scoped Private Integration Token in GoHighLevel."
    echo "Do not use or store a Firebase refresh token."
    token="$(secret "Paste the pit- Private Integration Token")"
    [[ "$token" == pit-* ]] || fail "the GoHighLevel token must begin with pit-"
    read -r -p "Paste the exact GoHighLevel Location ID: " location
    [[ "$location" =~ ^[A-Za-z0-9_-]{8,80}$ ]] || fail "that Location ID is not valid"
    upsert GHL_API_KEY "$token"
    upsert GHL_LOCATION_ID "$location"
    unset token
    hermes config set mcp_servers.funding-director-core.env.GHL_API_KEY '${GHL_API_KEY}' >/dev/null
    hermes config set mcp_servers.funding-director-core.env.GHL_LOCATION_ID '${GHL_LOCATION_ID}' >/dev/null
    restart_gateway
    echo "GoHighLevel is connected through the guarded Funding Director core."
    echo "First test: search for one known contact; do not change it."
    ;;
  5)
    echo "Open https://app.composio.dev and copy a consumer key beginning ck_."
    value="$(secret "Paste the ck_ consumer key")"
    [[ "$value" == ck_* ]] || fail "the consumer key must begin with ck_"
    upsert COMPOSIO_API_KEY "$value"
    unset value
    hermes config set mcp_servers.composio.url https://connect.composio.dev/mcp >/dev/null
    hermes config set mcp_servers.composio.headers.x-consumer-api-key '${COMPOSIO_API_KEY}' >/dev/null
    hermes config set mcp_servers.composio.trust untrusted >/dev/null
    hermes config set mcp_servers.composio.timeout 180 >/dev/null
    hermes config set mcp_servers.composio.enabled true >/dev/null
    restart_gateway
    echo "Connect only the intended accounts in Composio."
    echo "First test: Read my next three calendar events. Do not change anything."
    ;;
  6)
    hermes mcp list
    hermes gateway status || true
    ;;
  *) fail "choose a number from 1 through 6" ;;
esac
