#!/usr/bin/env bash
# Add messaging channels to an installed Operator without exposing secrets.
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/operator-lib.sh"
operator_load_env
operator_init_docker

echo
echo "Where else would you like to message your Operator?"
echo "The private browser dashboard already works. Add only what you want."

while true; do
  cat <<'MENU'

  1. Telegram
  2. Slack
  3. iMessage through BlueBubbles
  4. Discord
  5. WhatsApp
  6. Show channel status
  7. Finish
MENU
  read -r -p "Choose a number: " choice
  case "$choice" in
    1)
      echo "Create or open your bot with @BotFather in Telegram."
      token="$(operator_secret "Paste the Telegram bot token")"
      [ -n "$token" ] || operator_fail "the Telegram token cannot be blank"
      operator_save_value TELEGRAM_BOT_TOKEN "$token"
      operator_refresh
      echo "Telegram was added. Send the bot: hello"
      ;;
    2)
      echo "In Slack, create an app from this manifest:"
      echo "  $OPERATOR_BASE_DIR/slack-manifest.yml"
      echo "This manifest uses Slack Agent view, which cannot be reverted on that app."
      echo "Install it to the chosen workspace, then create an app-level token"
      echo "with connections:write under Basic Information → App-Level Tokens."
      bot_token="$(operator_secret "Paste the Slack Bot Token beginning xoxb-")"
      app_token="$(operator_secret "Paste the Slack App Token beginning xapp-")"
      [[ "$bot_token" == xoxb-* ]] || operator_fail "the Bot Token must begin with xoxb-"
      [[ "$app_token" == xapp-* ]] || operator_fail "the App Token must begin with xapp-"
      echo "Open your Slack profile → three dots → Copy member ID."
      read -r -p "Authorized Slack Member ID(s), comma separated: " allowed_users
      allowed_users="${allowed_users//[[:space:]]/}"
      [[ "$allowed_users" =~ ^[UW][A-Z0-9]+(,[UW][A-Z0-9]+)*$ ]] || \
        operator_fail "Member IDs look like U01ABC123"
      operator_save_value SLACK_BOT_TOKEN "$bot_token"
      operator_save_value SLACK_APP_TOKEN "$app_token"
      operator_save_value SLACK_ALLOWED_USERS "$allowed_users"
      operator_refresh
      full_manifest="$(operator_generate_slack_manifest)"
      echo "Slack was added. The complete slash-command manifest is at:"
      echo "  $full_manifest"
      echo "Invite the Operator app to each channel it may read."
      echo "Test a DM, then @mention it once in an approved channel and continue in the thread."
      ;;
    3)
      echo "iMessage needs the free BlueBubbles server running on a Mac."
      echo "Open https://bluebubbles.app and finish its server setup first."
      echo "Keep it on Tailscale or another approved private network; do not expose"
      echo "an unauthenticated BlueBubbles port to the public internet."
      server_url="$(read -r -p "BlueBubbles server URL: " value; printf '%s' "$value")"
      password="$(operator_secret "BlueBubbles server password")"
      [ -n "$server_url" ] && [ -n "$password" ] || \
        operator_fail "the BlueBubbles URL and password are required"
      operator_save_value BLUEBUBBLES_SERVER_URL "$server_url"
      operator_save_value BLUEBUBBLES_PASSWORD "$password"
      operator_refresh
      echo "iMessage was added. Use DM pairing before allowing another person."
      ;;
    4)
      echo "Create a Discord bot at https://discord.com/developers/applications."
      token="$(operator_secret "Paste the Discord bot token")"
      [ -n "$token" ] || operator_fail "the Discord token cannot be blank"
      operator_save_value DISCORD_BOT_TOKEN "$token"
      operator_refresh
      echo "Discord was added. Invite the bot only to approved servers."
      ;;
    5)
      echo "Hermes will display a WhatsApp QR code and complete pairing."
      operator_hermes whatsapp
      operator_docker restart "${AGENT_NAME:-funding-director}" >/dev/null
      echo "WhatsApp pairing finished and the Operator restarted."
      ;;
    6)
      operator_hermes gateway status
      ;;
    7)
      echo "Messaging setup is finished."
      break
      ;;
    *) echo "Choose a number from 1 through 7." ;;
  esac
done
